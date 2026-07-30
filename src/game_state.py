"""Game lifecycle helpers for new, load, save, and migration UX."""

from util import sstr
from prime_platform import hvars_get, hvars_set, ticks
from config import SAVE_VAR, FNKEY_NAMES, KEY_COMMANDS, R_STARTING_ROOM
from game_time import time_info, SUN_DARK, SUN_RISE, SUN_LIGHT, SUN_SET
from item import serialize_item_token, parse_item_token
import terminal
from terminal import tprint
import world
from world import ROOM_DEFS, AREA_DEFS, MOB_DEFS
from inventory import do_outfit
from macros import _MACRO_SUBST
from quest import rescale_quest_gear
from gquest import gq_save_lines, gq_load_line, gq_reset
from mob import reset_area, create_area_states, spawn_pet
from player import create_char, reset_char, _EQUIP_SAVE_ORDER
from picker import pick_from
from classes import CLASS_TABLE
from races import race_lookup, PC_RACE_ORDER, RACE_TABLE
from skills_table import WEAPON_GSN_MAP
from colors import capitalize
from debug import DBG, dbg
from handler import affect_to_char, chprintln
from info import do_help
from explored import encode_rle, decode_rle


# -- Save format version --------------------------------------------------------
# Increment SAVE_VERSION whenever a core mechanic changes in a way that makes
# old saves load incorrectly: e.g. flag-bit layout changes, AC formula changes,
# stat renaming, or any field whose semantics change rather than just new fields
# being added.  Additive changes (new skills, new item slots, new flags that
# default to 0) do NOT require a bump -- missing keys are silently left at their
# create_char() defaults, and unknown keys are silently ignored on load.
#
# Skill numeric IDs (GSN_*) are permanent once assigned: recycling an ID for a
# different skill would cause old saves to corrupt the new skill's learned %.
SAVE_VERSION = 10  # v10: packed-only records (p.n/p.eq/a.<tag>/m), home_owned in p.n; v9: p.explored RLE mask

# Per-area state packed save line:
# a.<tag>=<age>|<temp>|<tv>|<precip>|<pv>|<wind>|<wv>
# (cf. game_time weather model). [PRIMESUD] Missing/short weather keeps
# freshly seeded random values.
_WEATHER_PACK_FIELDS = ("temp", "temp_vector", "precip", "precip_vector",
                        "wind", "wind_vector")

# Fixed-order compact player fields. Never reorder or extend without a
# SAVE_VERSION bump plus a one-off save conversion (load old, save new);
# the p.n parser is exact-length and silently skips a mismatched line. [PRIMESUD]
_PLAYER_STRING_SAVE_KEYS = (
    "name", "title", "race", "sex", "true_sex",
    "quest_mob_name", "quest_room_name", "quest_area_name",
    # additive-safe: p.<key> string lines parse generically, unlike p.n
    "quest_obj_name",
)
_PLAYER_NUMBER_SAVE_KEYS = (
    "level", "xp", "xp_next", "hit", "mana", "move",
    "perm_hit", "perm_mana", "perm_move", "room", "trivia",
    "practice", "train", "flags", "played", "backup", "alignment",
    "tier", "gold", "silver", "gold_bank", "shares", "wimpy",
    "quest_points", "quest_status", "quest_time", "quest_mob",
    "quest_obj", "quest_room", "quest_giver", "prime_class",
    "home_owned",
)
_PLAYER_STAT_SAVE_KEYS = ("str", "dex", "int", "wis", "con")

# -- Persistence ---------------------------------------------------------------
# Dual-save strategy:
#   - HVar (SAVE_VAR): survives app reinstall, but only flushed to disk on
#     normal calculator shutdown -- a hard crash may leave HVar stale.
#   - File (SAVE_FILE): written immediately on every save, so survives hard
#     crashes, but is wiped on app update/reinstall.
# Save writes both.  Load prefers file (better crash safety); falls back to
# HVar when file is missing or unreadable (e.g. after reinstall).
# Serialisation constraints:
#   - Lines are joined with '~'; no saved field value may contain '~'.
#   - No field value may contain '"' (would break the PPL string literal).
#   - HVars returns the string "Error: Invalid input" when the variable does
#     not exist yet (i.e. no save found); load_char treats this as no-save.
SAVE_FILE = "primesud.sav"

# [PRIMESUD] (segment, ms) pairs from the most recent _serialize_world
# call while the "save" debug channel is on -- read by perf probes
# (debug/save_smoke.py). Stays empty when the channel is off.
_SAVE_TIMING = []


def _serialize_world(hvar_name=None, file_name=None):
    """Serialise world state to a PPL HVars variable (cf. 1stMud save_char_obj in save.c).

    Args:
        hvar_name (str or None): HVar name to write; None (default) resolves
            to module-global SAVE_VAR at call time -- not a bound default
            argument, so tests/callers that patch game_state.SAVE_VAR still
            take effect. backup_world passes BACKUP_VAR for the manual
            second save slot.
        file_name (str or None): File path to write; None (default) resolves
            to module-global SAVE_FILE at call time, same reasoning.
            backup_world passes BACKUP_FILE.

    Raises:
        Exception: If the PPL write fails, readback does not match the written
            payload, or the save-file mirror cannot be written.
    """
    if hvar_name is None:
        hvar_name = SAVE_VAR
    if file_name is None:
        file_name = SAVE_FILE
    # [PRIMESUD] Segment timing behind the "save" debug channel; a few
    # boolean checks when off, ticks() bookends per segment when on.
    global _SAVE_TIMING
    _timed = "save" in DBG
    if _timed:
        _SAVE_TIMING = []
        _tmark = ticks()
    # [PRIMESUD] Keyboard-service checkpoints: the save is the longest
    # keyboard-dead stall left (~0.9s steady, docs/PERFORMANCE.md sec.
    # Save path) and the firmware FIFO holds only 4 presses. Draining it
    # into the 16-entry local queue at each segment boundary caps the
    # worst pump gap at the largest single segment (~255ms) so typing
    # through a save loses nothing; the keys replay after the save.
    # Same pattern as the violence_update checkpoints in combat.py.
    _pump = getattr(terminal.tr, "_pump_keyboard", None)  # tests stub tr without it
    if _pump:
        _pump(KEY_COMMANDS)
    player = world.chars[1]
    # No gc_collect() here: a collect adjacent to bulk int rendering is the
    # G1 heap-corruption trigger (PRIME_FIRMWARE_BUGS.md sec. str(int)-GC bug);
    # sstr's cached digit path below is the validated fix.
    lines = ["v=" + sstr(SAVE_VERSION)]
    for key in _PLAYER_STRING_SAVE_KEYS:
        lines.append("p." + key + "=" + sstr(player[key]))
    number_parts = []
    for key in _PLAYER_NUMBER_SAVE_KEYS:
        number_parts.append(sstr(player[key]))
    for stat in _PLAYER_STAT_SAVE_KEYS:
        number_parts.append(sstr(player["perm_stat"][stat]))
    lines.append("p.n=" + "|".join(number_parts))
    # cf. 1stMud ch->Class[] -- comma-joined ints (str+concat per PRIME_FIRMWARE_BUGS)
    cls_str = ""
    for c in player["classes"]:
        cls_str = cls_str + ("," if cls_str else "") + sstr(c)
    lines.append("p.classes=" + cls_str)
    # cf. 1stMud fwrite_char "Pos" -- fighting saved as standing
    lines.append("p.pos=" + sstr("standing" if player.get("pos") == "fighting"
                                 else player.get("pos", "standing")))
    # cf. 1stMud pcdata->group_known -- comma-joined group indices
    grp_str = ""
    for g in player.get("groups", []):
        grp_str = grp_str + ("," if grp_str else "") + sstr(g)
    lines.append("p.groups=" + grp_str)
    # cf. 1stMud ch->stance[] (fwrite_char "Stances" line) -- comma-joined ints
    st_str = ""
    for s in player.get("stance", []):
        st_str = st_str + ("," if st_str else "") + sstr(s)
    lines.append("p.stance=" + st_str)
    armor = player["armor"]
    lines.append("p.armor=" + sstr(armor[0]) + "|" + sstr(armor[1]) + "|" + sstr(armor[2]) + "|" + sstr(armor[3]))
    if _timed:
        _SAVE_TIMING.append(("ln.plr1", ticks() - _tmark))
        _tmark = ticks()
    if _pump:
        _pump(KEY_COMMANDS)
    inv_parts = []
    for o in player["inv"]:
        inv_parts.append(serialize_item_token(o))
    lines.append("p.inv=" + "|".join(inv_parts))
    equip_parts = []
    for slot in _EQUIP_SAVE_ORDER:
        obj = player["equip"][slot]
        val = serialize_item_token(obj) if obj is not None else ""
        equip_parts.append(val)
    lines.append("p.eq=" + "|".join(equip_parts))
    if _timed:
        _SAVE_TIMING.append(("ln.pinv", ticks() - _tmark))
        _tmark = ticks()
    if _pump:
        _pump(KEY_COMMANDS)
    learned_parts = []
    for sk in sorted(player["learned"]):
        learned_parts.append(sstr(sk) + ":" + sstr(player["learned"][sk]))
    lines.append("p.learned=" + "|".join(learned_parts))
    # [PRIMESUD] autoskill rotation -- custom order/exclusions only; absent
    # key means pure heuristic default (see autoskill.py)
    if "autoskill_rot" in player:
        lines.append("p.autoskill_rot=" + ",".join(player["autoskill_rot"]))
    if _timed:
        _SAVE_TIMING.append(("ln.plearn", ticks() - _tmark))
        _tmark = ticks()
    if _pump:
        _pump(KEY_COMMANDS)
    # cf. 1stMud write_rle (explored.c) -- RLE run-length string, str()+concat
    lines.append("p.explored=" + encode_rle(player))
    if _timed:
        _SAVE_TIMING.append(("ln.rle", ticks() - _tmark))
        _tmark = ticks()
    if _pump:
        _pump(KEY_COMMANDS)
    af_parts = []
    for af in player.get("affect_list", []):
        af_parts.append(
            sstr(af.get("type", "")) + ","
            + sstr(af.get("level", 0)) + ","
            + sstr(af.get("duration", 0)) + ","
            + sstr(af.get("location", "")) + ","
            + sstr(af.get("modifier", 0)) + ","
            + sstr(af.get("bitvector", "")) + ","
            + sstr(af.get("where", ""))
        )
    if af_parts:
        lines.append("p.affects=" + "|".join(af_parts))
    # cf. 1stMud write_pet in save.c -- [PRIMESUD] persists tpl/hp/max_hp/name
    # and timed affects; other fields (exp, gold, inventory) respawn from the
    # template since PrimeSUD pets cannot accumulate them
    pet = world.chars.get(player["pet"]) if player.get("pet") is not None else None
    if pet is not None:
        lines.append("p.pet=" + sstr(pet["tpl"]) + "|" + sstr(pet["hit"])
                     + "|" + sstr(pet.get("pet_name", "")))
        pet_af_parts = []
        for af in pet.get("affect_list", []):
            pet_af_parts.append(
                sstr(af.get("type", "")) + ","
                + sstr(af.get("level", 0)) + ","
                + sstr(af.get("duration", 0)) + ","
                + sstr(af.get("location", "")) + ","
                + sstr(af.get("modifier", 0)) + ","
                + sstr(af.get("bitvector", "")) + ","
                + sstr(af.get("where", ""))
            )
        if pet_af_parts:
            lines.append("p.pet.affects=" + "|".join(pet_af_parts))
    _mk_int = sorted(k for k in player["_macros"] if isinstance(k, int))
    _mk_str = sorted(k for k in player["_macros"] if isinstance(k, str))
    for k in _mk_int + _mk_str:
        lines.append("p.macro." + sstr(FNKEY_NAMES.get(k, k)) + "=" + sstr(player["_macros"][k]))
    # cf. 1stMud pcdata->alias[]/alias_sub[] (fwrite_char); one line per
    # alias, order preserved (do_alias/do_unalias keep the list compact).
    for _al_name, _al_sub in player.get("aliases", []):
        lines.append("p.alias." + _al_name + "=" + _al_sub)
    if player.get("home_owned"):
        lines.append("p.home_name=" + sstr(player.get("home_name", "")))
        lines.append("p.home_desc=" + sstr(player.get("home_desc", "")))
    if _timed:
        _SAVE_TIMING.append(("ln.paff", ticks() - _tmark))
        _tmark = ticks()
    if _pump:
        _pump(KEY_COMMANDS)
    for _as in world.areas:
        # HP Prime G1 has unstable percent-format strings in save payloads.
        _aparts = [sstr(_as["age"])]
        weather = _as.get("weather")
        if weather is not None:
            for _wfld in _WEATHER_PACK_FIELDS:
                _aparts.append(sstr(weather.get(_wfld, 0)))
        lines.append("a." + sstr(_as["tag"]) + "=" + "|".join(_aparts))
    lines.append("g.time=" + sstr(time_info["hour"]) + "|" + sstr(time_info["day"]) + "|" + sstr(time_info["month"]) + "|" + sstr(time_info["year"]))
    lines.append("g.share=" + sstr(world.share_value))
    if _timed:
        _SAVE_TIMING.append(("ln.wstate", ticks() - _tmark))
        _tmark = ticks()
    if _pump:
        _pump(KEY_COMMANDS)
    # [PRIMESUD] value-pair keyed line caches (world._MOB_STAT_LINE_CACHE):
    # the stat lists mutate in place, so only entries fought since the
    # last save re-render (ln.stats was 250ms of a 937ms save, smoke-5).
    for _vnum in sorted(world.mob_stats):
        _stat = world.mob_stats[_vnum]
        _sc = world._MOB_STAT_LINE_CACHE.get(_vnum)
        if _sc is not None and _sc[0] == _stat[0] and _sc[1] == _stat[1]:
            lines.append(_sc[2])
            continue
        _sl = "s.m." + sstr(_vnum) + "=" + sstr(_stat[0]) + "|" + sstr(_stat[1])
        world._MOB_STAT_LINE_CACHE[_vnum] = (_stat[0], _stat[1], _sl)
        lines.append(_sl)
    for _tag in sorted(world.area_stats):
        _stat = world.area_stats[_tag]
        _sc = world._AREA_STAT_LINE_CACHE.get(_tag)
        if _sc is not None and _sc[0] == _stat[0] and _sc[1] == _stat[1]:
            lines.append(_sc[2])
            continue
        _sl = "s.a." + sstr(_tag) + "=" + sstr(_stat[0]) + "|" + sstr(_stat[1])
        world._AREA_STAT_LINE_CACHE[_tag] = (_stat[0], _stat[1], _sl)
        lines.append(_sl)
    for _gql in gq_save_lines():  # [PRIMESUD] gquest state
        lines.append(_gql)
    if _timed:
        _SAVE_TIMING.append(("ln.stats", ticks() - _tmark))
        _tmark = ticks()
    if _pump:
        _pump(KEY_COMMANDS)
    # Build reset-room map for single-instance mobs (gl=1): if the only live
    # instance is already in its reset room, omit it -- reset_area() will
    # restore it there on load without any save entry needed.
    _single_reset_room = {}
    for _adef in AREA_DEFS:
        for entry in _adef["resets"]:
            if entry[0] == "M" and entry[2] == 1:
                _single_reset_room[entry[1]] = entry[3]

    # Serialize mob positions by template vnum. Cross-area wanderers (mob
    # from area A at room in area B) are saved here but silently dropped on
    # load by _apply_pending_deltas -- 1stMud never persists NPC positions
    # and the 5% despawn keeps cross-area wanderers transient anyway.
    tpl_rooms = {}
    tpl_order = []
    mob_parts = []
    for mob_id in sorted(world.chars):
        inst = world.chars[mob_id]
        if not inst.get("is_npc"):
            continue
        if mob_id == player.get("pet"):
            continue  # pet persisted via p.pet, not as a template position
        tpl = inst["tpl"]
        if tpl not in tpl_rooms:
            tpl_rooms[tpl] = []
            tpl_order.append(tpl)
        tpl_rooms[tpl].append(inst["room"])
    for tpl_vnum in tpl_order:
        rooms = tpl_rooms[tpl_vnum]
        if (len(rooms) == 1
                and _single_reset_room.get(tpl_vnum) == rooms[0]):
            continue
        room_parts = []
        for r in rooms:
            room_parts.append(sstr(r))
        mob_parts.append(sstr(tpl_vnum) + "," + "|".join(room_parts))
    # Re-serialize pending mob deltas for unloaded areas (not in world.chars).
    # [PRIMESUD] world._PENDING_MOB_CACHE holds each template's part string,
    # validated by room-list identity (prefilled at load from the raw save
    # entry) -- re-rendering every pending template cost ln.mob=750ms of a
    # 1.6s save on-device (debug/save_smoke-3.log).
    for tpl_vnum in sorted(world._pending_mob_saves):
        if tpl_vnum in tpl_rooms:
            continue
        _pm_rooms = world._pending_mob_saves[tpl_vnum]
        _pm = world._PENDING_MOB_CACHE.get(tpl_vnum)
        if _pm is not None and _pm[0] is _pm_rooms:
            mob_parts.append(_pm[1])
            continue
        room_parts = []
        for r in _pm_rooms:
            room_parts.append(sstr(r))
        _pm_part = sstr(tpl_vnum) + "," + "|".join(room_parts)
        world._PENDING_MOB_CACHE[tpl_vnum] = (_pm_rooms, _pm_part)
        mob_parts.append(_pm_part)
    if mob_parts:
        lines.append("m=" + ";".join(mob_parts))
    if _timed:
        _SAVE_TIMING.append(("ln.mob", ticks() - _tmark))
        _tmark = ticks()
    if _pump:
        _pump(KEY_COMMANDS)
    for rvnum in sorted(world.rooms):
        rs = world.rooms[rvnum]
        if not rs["items"]:
            continue
        item_parts = []
        for o in rs["items"]:
            item_parts.append(serialize_item_token(o))
        lines.append("r." + sstr(rvnum) + ".items=" + "|".join(item_parts))
    if _timed:
        _SAVE_TIMING.append(("ln.room", ticks() - _tmark))
        _tmark = ticks()
    if _pump:
        _pump(KEY_COMMANDS)
    # Re-serialize pending room items for unloaded areas (not in world.rooms).
    # [PRIMESUD] world._PENDING_ROOM_LINE_CACHE holds each finished line,
    # validated by raw-string identity (same rule as _PENDING_MOB_CACHE):
    # rebuilding ~100 passthrough lines cost ln.rpend=247ms (smoke-5).
    for rvnum in sorted(world._pending_room_items):
        _pr_raw = world._pending_room_items[rvnum]
        _pr = world._PENDING_ROOM_LINE_CACHE.get(rvnum)
        if _pr is not None and _pr[0] is _pr_raw:
            lines.append(_pr[1])
            continue
        _pr_line = "r." + sstr(rvnum) + ".items=" + sstr(_pr_raw)
        world._PENDING_ROOM_LINE_CACHE[rvnum] = (_pr_raw, _pr_line)
        lines.append(_pr_line)
    if _timed:
        _SAVE_TIMING.append(("ln.rpend", ticks() - _tmark))
        _tmark = ticks()
    if _pump:
        _pump(KEY_COMMANDS)
    # [PRIMESUD] Item-template snapshots (DESIGN.md sec. Item template
    # snapshots). One deduplicated "it.<vnum>=<revision>|<record>" line
    # per VNUM world._snap_save_vnums() says is required (player gear
    # always, foreign-owner room/pending items only) -- never the whole
    # ITEM_SNAPSHOTS registry. Resident template data wins when the owning
    # area is loaded; otherwise the current registry snapshot answers
    # (orphans keep their already-stamped revision). Neither source: the
    # line is omitted and the VNUM falls back to its normal lazy area load
    # on next boot -- not an error.
    for _it_vnum in sorted(world._snap_save_vnums()):
        _it_entry = None
        if _it_vnum in world.ITEM_DEFS._data:
            _it_rev = world.CONTENT_REVISION
        else:
            _it_entry = world.ITEM_SNAPSHOTS.get(_it_vnum)
            if _it_entry is None:
                continue  # no source: normal lazy-load fallback next boot
            _it_rev = _it_entry[0]
        # [PRIMESUD] Encoded-line cache (world._SNAP_ENC_CACHE): reuse the
        # line while the revision we would stamp matches the cached one --
        # the codec is deterministic and templates immutable per build, so
        # a matching revision guarantees byte-identical output. On-device
        # the encode was ~1s of every save (debug/save_smoke-1.log).
        _it_cached = world._SNAP_ENC_CACHE.get(_it_vnum)
        if _it_cached is not None and _it_cached[0] == _it_rev:
            lines.append(_it_cached[1])
            continue
        if _it_entry is None:
            _it_tpl = world.ITEM_DEFS._data[_it_vnum]
            _it_progs = {}
            for _it_trig in _it_tpl.get("obj_triggers", ()):
                _it_pv = _it_trig[1]
                if _it_pv in world.OBJPROGS:
                    _it_progs[_it_pv] = world.OBJPROGS[_it_pv]
        else:
            _it_rev, _it_tpl, _it_progs = _it_entry
        try:
            _it_enc = world._snap_encode((_it_tpl, _it_progs))
        except ValueError:
            continue  # unsupported value type: skip the line, keep save valid
        _it_line = "it." + sstr(_it_vnum) + "=" + _it_rev + "|" + _it_enc
        world._SNAP_ENC_CACHE[_it_vnum] = (_it_rev, _it_line)
        lines.append(_it_line)
    if _timed:
        _SAVE_TIMING.append(("snap", ticks() - _tmark))
        _tmark = ticks()
    if _pump:
        _pump(KEY_COMMANDS)
    # Cold mark/sweep (DESIGN.md sec. Item template snapshots): free
    # registry
    # entries no live object or deferred token references once their owning
    # area is not resident to rebuild them from. Runs on every save,
    # primary or backup; never touches a VNUM the block above just wrote --
    # every save-marked VNUM is also runtime-marked.
    _it_live = world._snap_live_vnums()
    for _it_vnum in [_k for _k in world.ITEM_SNAPSHOTS
                     if _k not in _it_live
                     and world._vnum_to_tag(_k) not in world._LOADED_AREAS]:
        del world.ITEM_SNAPSHOTS[_it_vnum]
    if _timed:
        _SAVE_TIMING.append(("sweep", ticks() - _tmark))
        _tmark = ticks()
    if _pump:
        _pump(KEY_COMMANDS)
    for i in range(len(lines)):
        if not isinstance(lines[i], str):
            raise Exception("non-str save line " + sstr(i))
    payload = "~".join(lines)
    if _timed:
        _SAVE_TIMING.append(("join", ticks() - _tmark))
        _tmark = ticks()
    hvars_set(hvar_name, payload)
    if _timed:
        _SAVE_TIMING.append(("hvset", ticks() - _tmark))
        _tmark = ticks()
    saved = hvars_get(hvar_name)
    _match = saved == payload
    if _timed:
        _SAVE_TIMING.append(("verify", ticks() - _tmark))
        _tmark = ticks()
    if not _match:
        raise Exception("save verification failed (readback mismatch)")
    with open(file_name, "w") as f:
        f.write(payload)
    if _timed:
        _SAVE_TIMING.append(("fwrite", ticks() - _tmark))


# -- Manual backup slot (cf. 1stMud do_backup/backup_char_obj in
# act_comm.c/save.c) -----------------------------------------------------------
# Distinct from SAVE_VAR + "_bak" above, which load_world writes as an
# automatic pre-migration snapshot on a SAVE_VERSION mismatch: that one is a
# machine-written safety net, this one is the player-triggered `backup` slot.
BACKUP_VAR = SAVE_VAR + "_backup"
BACKUP_FILE = "primesud_backup.sav"


def backup_world():
    """Save world state to the manual backup slot. [PRIMESUD] (cf. 1stMud
    do_backup/backup_char_obj in act_comm.c/save.c)

    Same write path as save_world (HVar + file, with HVar readback
    verification) but targets BACKUP_VAR/BACKUP_FILE instead of SAVE_VAR/
    SAVE_FILE, so the primary save slot is untouched.

    Upstream has no player-facing restore command -- backup_char_obj's only
    other caller is the immortal-only rename_char cleanup (act_wiz.c).
    Restoring a PrimeSUD backup is a manual step: rename
    primesud_backup.sav to primesud.sav via the calculator's file manager
    (same "calculator file manager covers it" precedent as PARITY.md's
    `delete` entry).

    Returns:
        bool: True on success, False if the write failed.
    """
    try:
        _serialize_world(BACKUP_VAR, BACKUP_FILE)
        return True
    except Exception:
        return False


def save_world(quiet=False):
    """Save world state and optionally print success."""
    # [PRIMESUD] Status-bar indicator for the ~0.9s save stall (quiet
    # autosaves included): an explained pause reads as working, an
    # unlabelled input freeze reads as lag. Restore follows the pager/
    # autoskill-editor pattern (tr.status_text holds the plain copy).
    _tr = terminal.tr
    # status_text_raw keeps colour codes; plain status_text is the
    # fallback for stubs that only track the tml-level copy.
    _old_status = getattr(_tr, "status_text_raw", None)
    if _old_status is None:
        _old_status = getattr(_tr, "status_text", None)
    if _old_status is not None:
        _tr.set_status("{c[Saving...]{x")
    try:
        _serialize_world()
        if not quiet:
            tprint("Saved.")
        else:
            # [PRIMESUD] 'debug save' channel makes silent autosaves visible
            if "save" in DBG:
                dbg("autosave")
        return True
    except Exception as e:
        tprint("Save failed: " + str(e))
        return False
    finally:
        if _old_status is not None:
            _tr.set_status(_old_status)


def load_world():
    """Deserialise world state from save file or HVar (cf. 1stMud load_char_obj in save.c).

    Tries SAVE_FILE first (survives hard crashes); falls back to SAVE_VAR HVar
    (survives reinstalls).  Mutates world.chars[1] and world state in-place.  Macros are read
    from world.chars[1]["_macros"] (must be set by caller before calling).

    Returns:
        bool: True if a save was found and loaded, False if no save exists or on error.
    """
    player = world.chars[1]
    data = None
    _source = None
    try:
        with open(SAVE_FILE, "r") as f:
            data = f.read()
        if not data or not isinstance(data, str):
            data = None
        else:
            _source = "file"
    except Exception:
        data = None

    if data is None:
        try:
            data = hvars_get(SAVE_VAR)
            if not data or not isinstance(data, str) or data.startswith("Error:"):
                return False
            _source = "hvar"
        except Exception:
            return False

    # Reject saves from a different format version.  Additive changes (new
    # fields, new skills) don't require a bump; only semantic/structural changes
    # to existing core fields do.  See SAVE_VERSION comment above for the rule.
    # Returns None (not False) so the caller can distinguish mismatch from
    # "no save found" and prompt the user rather than silently starting fresh.
    _ver_prefix = "v="
    _first = data.split("~", 1)[0]
    if not _first.startswith(_ver_prefix) or int(_first[len(_ver_prefix):]) != SAVE_VERSION:
        try:
            hvars_set(SAVE_VAR + "_bak", data)
            _backup_ok = True
        except Exception:
            _backup_ok = False
        return (None, _backup_ok)

    if player["_macros"] is not None:
        player["_macros"].clear()
    player["aliases"] = []

    _area_by_tag = {s["tag"]: s for s in world.areas} if world.areas is not None else {}
    mob_saves = {}  # tpl_vnum -> [room, room, ...]

    _name_to_fn = {name: sentinel for sentinel, name in FNKEY_NAMES.items()}
    _pet_save = None
    _pet_affects = None
    for line in data.split("~"):
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        if key == "p.pet":
            _pet_save = val
        elif key == "p.pet.affects":
            _pet_affects = val
        elif key == "p.n":
            parts = val.split("|")
            if len(parts) == (len(_PLAYER_NUMBER_SAVE_KEYS)
                              + len(_PLAYER_STAT_SAVE_KEYS)):
                for i in range(len(_PLAYER_NUMBER_SAVE_KEYS)):
                    player[_PLAYER_NUMBER_SAVE_KEYS[i]] = int(parts[i])
                offset = len(_PLAYER_NUMBER_SAVE_KEYS)
                for i in range(len(_PLAYER_STAT_SAVE_KEYS)):
                    player["perm_stat"][_PLAYER_STAT_SAVE_KEYS[i]] = int(parts[offset + i])
        elif key == "p.eq":
            parts = val.split("|")
            if len(parts) == len(_EQUIP_SAVE_ORDER):
                for i in range(len(parts)):
                    player["equip"][_EQUIP_SAVE_ORDER[i]] = (
                        parse_item_token(parts[i]) if parts[i] else None)
        elif key == "p.inv":
            player["inv"] = [parse_item_token(v) for v in val.split("|") if v]
        elif key == "p.classes":
            player["classes"] = [int(v) for v in val.split(",") if v]
        elif key == "p.groups":
            player["groups"] = [int(v) for v in val.split(",") if v]
        elif key == "p.stance":
            _st = [int(v) for v in val.split(",") if v]
            if len(_st) == len(player.get("stance", [])):
                player["stance"] = _st
        elif key == "p.learned":
            # authoritative: discard create_char() group grants (the save's
            # class may differ from the default create_char class)
            player["learned"] = {}
            for entry in val.split("|"):
                if ":" in entry:
                    sk_str, pct_str = entry.split(":", 1)
                    try:
                        player["learned"][int(sk_str)] = int(pct_str)
                    except ValueError:
                        pass
        elif key == "p.autoskill_rot":  # [PRIMESUD] autoskill rotation
            player["autoskill_rot"] = val.split(",") if val else []
        elif key == "p.explored":
            decode_rle(player, val)  # cf. 1stMud read_rle (explored.c)
        elif key == "p.armor":
            parts = val.split("|")
            if len(parts) == 4:
                player["armor"] = (int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3]))
        elif key == "p.affects":
            player["affect_list"] = []
            for entry in val.split("|"):
                if not entry:
                    continue
                parts = entry.split(",")
                while len(parts) < 7:
                    parts.append("")
                af = {
                    "type": int(parts[0]) if parts[0].lstrip("-").isdigit() else parts[0],
                    "level": int(parts[1]) if parts[1] else 0,
                    "duration": int(parts[2]) if parts[2].lstrip("-").isdigit() else 0,
                    "location": parts[3],
                    "modifier": int(parts[4]) if parts[4].lstrip("-").isdigit() else 0,
                    "bitvector": parts[5],
                    "where": parts[6],
                }
                player["affect_list"].append(af)
        elif key.startswith("p.macro.") and player["_macros"] is not None:
            raw = key[8:]
            player["_macros"][_name_to_fn.get(raw, raw)] = val
        elif key.startswith("p.alias."):
            player["aliases"].append([key[8:], val])
        elif key.startswith("p."):
            # Named string fields: _PLAYER_STRING_SAVE_KEYS plus conditional
            # extras (p.home_name/p.home_desc); numbers all ride p.n.
            player[key[2:]] = val
        elif key.startswith("r.") and key.endswith(".items"):
            rvnum = int(key.split(".")[1])
            world._pending_room_items[rvnum] = val
        elif key.startswith("it."):
            # [PRIMESUD] Item-template snapshot cache line (DESIGN.md sec.
            # Item template snapshots): "it.<vnum>=<revision>|<record>".
            # Populates ITEM_SNAPSHOTS only -- never touches ITEM_DEFS or
            # loads an area. A malformed record (bad vnum, missing "|", codec
            # ValueError, wrong decoded shape) is skipped individually: this
            # is an optional cache, so a corrupt line must never make the
            # rest of the save unloadable. Line order within the save is
            # irrelevant -- item-token parsing (p.inv/p.eq/r.*.items above)
            # needs no template, so ITEM_SNAPSHOTS only has to be populated
            # before reset_char runs after load_world returns.
            try:
                it_vnum = int(key[3:])
                it_rev, it_enc = val.split("|", 1)
                it_record = world._snap_decode(it_enc)
                if (isinstance(it_record, tuple) and len(it_record) == 2
                        and isinstance(it_record[0], dict)
                        and isinstance(it_record[1], dict)):
                    world.ITEM_SNAPSHOTS[it_vnum] = (it_rev, it_record[0], it_record[1])
                    # [PRIMESUD] Prefill the encoded-line cache from the
                    # raw save bytes (deterministic codec: re-encoding
                    # this entry reproduces them), so the first save
                    # after boot skips the encode too.
                    world._SNAP_ENC_CACHE[it_vnum] = (it_rev, key + "=" + val)
            except ValueError:
                pass
        elif key.startswith("a."):
            tag = key[2:]
            parts = val.split("|")
            if tag in _area_by_tag and parts:
                _area_by_tag[tag]["age"] = int(parts[0])
                if len(parts) == len(_WEATHER_PACK_FIELDS) + 1:
                    w = _area_by_tag[tag].setdefault("weather", {})
                    for i in range(len(_WEATHER_PACK_FIELDS)):
                        w[_WEATHER_PACK_FIELDS[i]] = int(parts[i + 1])
        elif key.startswith("g.gq") and gq_load_line(key, val):  # [PRIMESUD]
            pass
        elif key == "g.share":
            world.share_value = int(val)
        elif key.startswith("s.m."):
            parts = val.split("|")
            if len(parts) == 2:
                world.mob_stats[int(key[4:])] = [int(parts[0]), int(parts[1])]
        elif key.startswith("s.a."):
            parts = val.split("|")
            if len(parts) == 2:
                world.area_stats[key[4:]] = [int(parts[0]), int(parts[1])]
        elif key == "g.time":
            parts = val.split("|")
            if len(parts) == 4:
                time_info["hour"] = int(parts[0])
                time_info["day"] = int(parts[1])
                time_info["month"] = int(parts[2])
                time_info["year"] = int(parts[3])
                h = time_info["hour"]
                if h < 5 or h >= 20:
                    time_info["sunlight"] = SUN_DARK
                elif h == 5:
                    time_info["sunlight"] = SUN_RISE
                elif h >= 18:
                    time_info["sunlight"] = SUN_SET
                else:
                    time_info["sunlight"] = SUN_LIGHT
        elif key == "m":
            for entry in val.split(";"):
                if "," in entry:
                    tpl, rooms = entry.split(",", 1)
                    _tpl_i = int(tpl)
                    _rl = [int(r) for r in rooms.split("|") if r]
                    mob_saves[_tpl_i] = _rl
                    # [PRIMESUD] Prefill the part-string cache from the raw
                    # save entry (the serializer's exact output), keyed to
                    # this list object -- first save renders nothing.
                    world._PENDING_MOB_CACHE[_tpl_i] = (_rl, entry)

    # Buffer mob saves for deferred application: _load_area will apply
    # each area's deltas when it actually loads (player enters the area).
    world._pending_mob_saves.update(mob_saves)

    # [PRIMESUD] Prewarm the pending-token vnum cache so the first save
    # after boot skips the one-time ~4.5s token rescan (save_smoke-2.log
    # save 1 snap=4518ms) -- the cost lands in the already-signposted
    # load screen instead of the first mid-play autosave.
    for _rv in world._pending_room_items:
        world._snap_pending_cached(_rv, world._pending_room_items[_rv])

    # Player room access triggers the player's area load, which applies
    # pending deltas for that area via _apply_pending_deltas.
    if player["room"] not in world.rooms:
        player["room"] = R_STARTING_ROOM

    # Restore pet in the player's room (cf. 1stMud fread_pet in save.c)
    if _pet_save:
        parts = _pet_save.split("|")
        try:
            _tpl = int(parts[0])
        except ValueError:
            _tpl = None
        if _tpl is not None and _tpl in MOB_DEFS:
            _hp = (int(parts[1]) if len(parts) > 1
                   and parts[1].lstrip("-").isdigit() else None)
            _pname = parts[2] if len(parts) > 2 and parts[2] else None
            player["pet"] = None
            _pet = spawn_pet(_tpl, player, name_arg=_pname, announce=False)
            # [PRIMESUD] max_hit is derived from owner level/tier, not saved.
            if _hp is not None:
                _pet["hit"] = max(1, min(_hp, _pet["max_hit"]))
            # Re-apply saved affects (cf. 1stMud fread_pet "Affc" entries)
            if _pet_affects:
                for entry in _pet_affects.split("|"):
                    if not entry:
                        continue
                    _ap = entry.split(",")
                    while len(_ap) < 7:
                        _ap.append("")
                    affect_to_char(_pet, {
                        "type": int(_ap[0]) if _ap[0].lstrip("-").isdigit() else _ap[0],
                        "level": int(_ap[1]) if _ap[1] else 0,
                        "duration": int(_ap[2]) if _ap[2].lstrip("-").isdigit() else 0,
                        "location": _ap[3],
                        "modifier": int(_ap[4]) if _ap[4].lstrip("-").isdigit() else 0,
                        "bitvector": _ap[5],
                        "where": _ap[6],
                    })

    return _source


def init_game_state(game):
    """Initialise mutable game state fields. [PRIMESUD]"""
    game._backup_ok = False


# Weapon pick order for new_game (cf. 1stMud const.c weapon_table -- the
# array order send_weapon_info/HANDLE_CON_PICK_WEAPON iterate in). MicroPython
# dict iteration order is not guaranteed, so this explicit tuple stands in for
# looping over weapon_table directly. The 5th entry is "staff" (weapon_table's
# name for the WEAPON_SPEAR class); it resolves to gsn_spear via
# WEAPON_GSN_MAP, while the skill itself is still named 'spear'.
_WEAPON_PICK_ORDER = ("sword", "mace", "dagger", "axe", "staff", "flail",
                      "whip", "polearm")


def _pick_required(title, options):
    """pick_from that re-prompts until a choice is made. [PRIMESUD]

    Chargen choices are permanent, so a fat-fingered Esc must not silently
    lock in a default; 1stMud nanny.c likewise re-prompts on invalid input
    at every creation step.
    """
    while True:
        idx = pick_from(title, options)
        if idx >= 0:
            return idx


def _sanitize_name(raw):
    """Filter a chargen name entry down to a safe, capitalized ASCII name. [PRIMESUD]

    cf. 1stMud check_parse_name in nanny.c (CON_GET_NAME): ROM allows 2-12
    ASCII letters and rejects banned/reserved/duplicate names. PrimeSUD is
    single-user with no player roster to collide with, so only the
    length/character-set checks are ported: non-letters are dropped and the
    result is capped at 12 characters. Capitalizes the first letter like
    1stMud's capitalize() (db.c). The '~'/'"'-delimited save payload (see
    _serialize_world) forbids those characters in any saved field; keeping
    only ASCII letters guarantees that by construction.

    Args:
        raw (str): Raw input string from tr.input.

    Returns:
        str: Sanitized name, or "" if fewer than 2 letters remain (caller
        re-prompts, cf. nanny.c "Illegal name, try another.").
    """
    letters = []
    for c in raw:
        if ("a" <= c <= "z") or ("A" <= c <= "Z"):
            letters.append(c)
            if len(letters) == 12:
                break
    if len(letters) < 2:  # ROM minimum name length (check_parse_name: 2-12)
        return ""
    return capitalize("".join(letters))


def _prompt_name(default="Hero", allow_cancel=False):
    """Name picker: generated suggestions, reroll, or typed entry. [PRIMESUD]

    Replaces 1stMud's typed-only CON_GET_NAME with a pick_from list of
    namegen suggestions (cf. get_random_name in namegen.c) -- typing a name
    on the calculator keyboard is painful. "Type my own..." drops to the
    original tr.input flow with *default* pre-filled.

    Args:
        default (str): Pre-filled name for the typed-entry path.
        allow_cancel (bool): If True, Esc returns None (rename command);
            if False, Esc re-shows the same picker (a fat-fingered Esc in
            chargen must not dump the player into typed entry -- cf.
            _pick_required).

    Returns:
        str or None: Sanitized 2-12 letter name, or None if cancelled.
    """
    from namegen import random_name  # deferred: keep namegen off the boot path
    names = [random_name() for _ in range(6)]
    while True:
        idx = pick_from("By what name do you wish to be known?",
                        names + ["More names...", "Type my own..."])
        if 0 <= idx < 6:
            return names[idx]
        if idx == 6:
            names = [random_name() for _ in range(6)]  # reroll
            continue
        if idx < 0:  # Esc
            if allow_cancel:
                return None
            continue  # re-show same suggestions
        while True:  # "Type my own..." chosen explicitly
            raw = terminal.tr.input("By what name do you wish to be known?\n",
                                    default=default)
            name = _sanitize_name(raw)
            if name:
                return name
            tprint("Illegal name, try another.")


def do_rename(ch, args):
    """Change your character's name at any time. [PRIMESUD]

    Solo game: no player roster or other players, and the save file name is
    fixed, so renaming is free and consequence-free. Upstream do_rename
    (act_wiz.c:4284, imm renames another player) is not ported. With an
    argument renames directly (same 2-12 letter rules as chargen); with no
    argument opens the chargen name picker (Esc cancels).

    Args:
        ch (dict): Acting character.
        args (list): Optional [new_name].
    """
    if args:
        name = _sanitize_name(args[0])
        if not name:
            chprintln(ch, "Illegal name, try another.")
            return
    else:
        name = _prompt_name(default=ch.get("name", "Hero"), allow_cancel=True)
        if name is None:
            return
    ch["name"] = name
    chprintln(ch, "You are now known as " + name + ".")


def new_game(game):
    """Create a new game world with a fresh player character. [PRIMESUD]

    Mirrors 1stMud nanny.c chargen order: name (CON_GET_NAME) -> race
    (CON_GET_NEW_RACE) -> sex (CON_GET_NEW_SEX) -> class (CON_GET_NEW_CLASS)
    -> create_char (fixed stats/skill grants) -> alignment
    (HANDLE_CON_GET_ALIGNMENT) -> weapon pick (send_weapon_info /
    HANDLE_CON_PICK_WEAPON) -> outfit -> newbie info (CON_READ_MOTD
    level==0 block) -> save. Deity/timezone/email/screen-size prompts are not
    ported [PRIMESUD] -- single-user, no deity or telnet negotiation system.

    Args:
        game: Game instance (supplies the terminal for prompts).
    """
    # Name prompt (cf. 1stMud nanny.c CON_GET_NAME). [PRIMESUD] picker of
    # namegen suggestions; "Type my own..." path keeps "Hero" pre-filled
    # and re-prompts on invalid entry like nanny's illegal-name path.
    name = _prompt_name()

    # Race choice (cf. 1stMud nanny.c CON_GET_NEW_RACE; [PRIMESUD] picker with
    # one-line summaries instead of bare list + 'help <race>'). PC_RACE_ORDER,
    # not RACE_TABLE.items() -- HP Prime dicts don't guarantee insertion order.
    race_labels = [rn + " - " + RACE_TABLE[rn]["summary"] for rn in PC_RACE_ORDER]
    race_idx = _pick_required("Choose your race:", race_labels)
    race_name = PC_RACE_ORDER[race_idx]

    # Sex choice (cf. 1stMud nanny.c CON_GET_NEW_SEX).
    sex_idx = _pick_required("Choose your sex:", ["Male", "Female", "Neutral"])
    sex_val = ("male", "female", "neutral")[sex_idx]

    # Class choice (cf. 1stMud nanny.c CON_GET_NEW_CLASS; [PRIMESUD] picker with
    # one-line summaries instead of a bare list + 'help <class>').
    labels = [c["names"][0] + " - " + c["summary"] for c in CLASS_TABLE]
    idx = _pick_required("Choose your class:", labels)
    world.reset_lazy()
    world.areas = create_area_states()
    gq_reset()  # [PRIMESUD] fresh gquest schedule per game
    player = create_char(idx, race_name)
    player["name"] = name
    player["sex"] = sex_val
    player["true_sex"] = sex_val
    player["_macros"] = _MACRO_SUBST
    world.chars[1] = player

    # Alignment pick (cf. 1stMud nanny.c HANDLE_CON_GET_ALIGNMENT).
    align_idx = _pick_required("Choose your alignment:", ["Good", "Neutral", "Evil"])
    player["alignment"] = (750, 0, -750)[align_idx]

    # Weapon pick (cf. 1stMud nanny.c send_weapon_info + HANDLE_CON_PICK_WEAPON).
    # Candidates are weapons create_char's group grants already gave nonzero
    # skill in (nanny.c: learned[*weapon_table[i].gsn] > 0), in weapon_table
    # order (see _WEAPON_PICK_ORDER above).
    candidates = [wname for wname in _WEAPON_PICK_ORDER
                  if player["learned"].get(WEAPON_GSN_MAP[wname], 0) > 0]
    if candidates:
        # colors.capitalize, not str.capitalize -- the latter is missing on
        # HP Prime (see BUILTINS.md).
        widx = _pick_required("Please pick a weapon from the following choices:",
                              [capitalize(w) for w in candidates])
        wname = candidates[widx]
    else:
        wname = CLASS_TABLE[idx]["weapon"]
    wgsn = WEAPON_GSN_MAP[wname]
    player["learned"][wgsn] = max(40, player["learned"].get(wgsn, 0))

    # do_outfit (cf. 1stMud do_outfit in nanny.c for new chars) picks the
    # wield weapon by highest learned% (inventory.py); the weapon just raised
    # to >=40 above outranks any other weapon skill still sitting at its 1%
    # group-grant floor, so it drives the starting wield item.
    do_outfit(player, "")

    # Newbie info help (cf. 1stMud nanny.c CON_READ_MOTD level==0 block:
    # do_function(ch, &nanny_help, "newbie info")). Local import: matches this
    # module's existing lazy-import style for less-frequently-used deps.
    do_help(player, ["newbie", "info"])

    save_game(game, quiet=True)


def load_game(game):
    """Load a saved game from persistent storage and restore world state. [PRIMESUD]"""
    world.reset_lazy()
    world.areas = create_area_states()
    gq_reset()  # [PRIMESUD] clear stale state; save lines re-populate below
    player = create_char()
    player["_macros"] = _MACRO_SUBST
    world.chars[1] = player
    result = load_world()
    if isinstance(result, tuple):   # (None, backup_ok) -- version mismatch
        _, game._backup_ok = result
        return None
    # Retry deltas skipped during cascade (dest room states not yet created)
    world._retry_pending_deltas()
    # Quest gear armor/dice overrides are regenerated, not saved [PRIMESUD]
    rescale_quest_gear(player)
    # Race-derived fields (size, flags, form, parts) are not saved -- re-derive
    # from the loaded race name before reset_char re-applies equipment/spell
    # affects (cf. create_char race-merge block in player.py).
    _race = race_lookup(player.get("race", "Human")) or RACE_TABLE["Human"]
    player["size"] = _race.get("size", "medium")
    player["affected_by"] = dict(_race.get("aff", {}))
    player["imm_flags"] = dict(_race.get("imm", {}))
    player["res_flags"] = dict(_race.get("res", {}))
    player["vuln_flags"] = dict(_race.get("vuln", {}))
    player["form_flags"] = dict(_race.get("form", {}))
    player["part_flags"] = dict(_race.get("parts", {}))
    reset_char(player)
    return result


def save_game(game, quiet=False):
    """Persist the current world state to storage. [PRIMESUD]"""
    return save_world(quiet)
