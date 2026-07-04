"""Game lifecycle helpers for new, load, save, and migration UX."""

from util import gc_collect
from prime_platform import hvars_get, hvars_set
from config import SAVE_VAR, FNKEY_NAMES, R_STARTING_ROOM
from game_time import time_info
from item import serialize_item_token, parse_item_token
from terminal import tprint
import world
from world import ROOM_DEFS, AREA_DEFS
from inventory import do_outfit
from macros import _MACRO_SUBST
from quest import rescale_quest_gear
from gquest import gq_save_lines, gq_load_line, gq_reset
from mob import reset_area, create_area_states
from player import create_char, reset_char, _EQUIP_SAVE_ORDER
from picker import pick_from
from classes import CLASS_TABLE, CLASS_WARRIOR
from skills_table import WEAPON_GSN_MAP
from colors import capitalize


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
SAVE_VERSION = 7  # v7: skill groups -- p.groups field; learned granted via groups, not grant-all

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


def _serialize_world():
    """Serialise world state to a PPL HVars variable (cf. 1stMud save_char_obj in save.c).

    Raises:
        Exception: If the PPL write fails, readback does not match the written
            payload, or the save-file mirror cannot be written.
    """
    player = world.chars[1]
    gc_collect()
    lines = ["v=" + str(SAVE_VERSION)]
    for key in ("name", "level", "xp", "xp_next",
                "hit", "mana", "move",
                "perm_hit", "perm_mana", "perm_move",
                "room", "trivia",
                "practice", "train", "flags", "played", "alignment",
                "gold", "silver", "wimpy",
                # cf. 1stMud fwrite_char QuestPnts/QuestNext; PrimeSUD also
                # persists the active quest (vnum-based, see quest.py)
                "quest_points", "quest_status", "quest_time",
                "quest_mob", "quest_obj", "quest_room", "quest_giver",
                "quest_mob_name", "quest_room_name", "quest_area_name"):
        lines.append("p." + key + "=" + str(player[key]))
    for stat in ("str", "dex", "int", "wis", "con"):
        lines.append("p." + stat + "=" + str(player["perm_stat"][stat]))
    # cf. 1stMud ch->Class[] -- comma-joined ints (str+concat per PRIME_STRING_FORMAT_BUG)
    cls_str = ""
    for c in player["classes"]:
        cls_str = cls_str + ("," if cls_str else "") + str(c)
    lines.append("p.classes=" + cls_str)
    lines.append("p.prime_class=" + str(player["prime_class"]))
    # cf. 1stMud fwrite_char "Pos" -- fighting saved as standing
    lines.append("p.pos=" + str("standing" if player.get("pos") == "fighting"
                                else player.get("pos", "standing")))
    # cf. 1stMud pcdata->group_known -- comma-joined group indices
    grp_str = ""
    for g in player.get("groups", []):
        grp_str = grp_str + ("," if grp_str else "") + str(g)
    lines.append("p.groups=" + grp_str)
    # cf. 1stMud ch->stance[] (fwrite_char "Stances" line) -- comma-joined ints
    st_str = ""
    for s in player.get("stance", []):
        st_str = st_str + ("," if st_str else "") + str(s)
    lines.append("p.stance=" + st_str)
    armor = player["armor"]
    lines.append("p.armor=" + str(armor[0]) + "|" + str(armor[1]) + "|" + str(armor[2]) + "|" + str(armor[3]))
    inv_parts = []
    for o in player["inv"]:
        inv_parts.append(serialize_item_token(o))
    lines.append("p.inv=" + "|".join(inv_parts))
    for slot in _EQUIP_SAVE_ORDER:
        obj = player["equip"][slot]
        val = serialize_item_token(obj) if obj is not None else ""
        lines.append("p.eq." + slot + "=" + val)
    learned_parts = []
    for sk in sorted(player["learned"]):
        learned_parts.append(str(sk) + ":" + str(player["learned"][sk]))
    lines.append("p.learned=" + "|".join(learned_parts))
    af_parts = []
    for af in player.get("affect_list", []):
        af_parts.append(
            str(af.get("type", "")) + ","
            + str(af.get("level", 0)) + ","
            + str(af.get("duration", 0)) + ","
            + str(af.get("location", "")) + ","
            + str(af.get("modifier", 0)) + ","
            + str(af.get("bitvector", "")) + ","
            + str(af.get("where", ""))
        )
    if af_parts:
        lines.append("p.affects=" + "|".join(af_parts))
    # cf. 1stMud write_pet in save.c -- [PRIMESUD] persists tpl/hp/max_hp/name
    # and timed affects; other fields (exp, gold, inventory) respawn from the
    # template since PrimeSUD pets cannot accumulate them
    pet = world.chars.get(player["pet"]) if player.get("pet") is not None else None
    if pet is not None:
        lines.append("p.pet=" + str(pet["tpl"]) + "|" + str(pet["hit"])
                     + "|" + str(pet["max_hit"])
                     + "|" + str(pet.get("pet_name", "")))
        pet_af_parts = []
        for af in pet.get("affect_list", []):
            pet_af_parts.append(
                str(af.get("type", "")) + ","
                + str(af.get("level", 0)) + ","
                + str(af.get("duration", 0)) + ","
                + str(af.get("location", "")) + ","
                + str(af.get("modifier", 0)) + ","
                + str(af.get("bitvector", "")) + ","
                + str(af.get("where", ""))
            )
        if pet_af_parts:
            lines.append("p.pet.affects=" + "|".join(pet_af_parts))
    _mk_int = sorted(k for k in player["_macros"] if isinstance(k, int))
    _mk_str = sorted(k for k in player["_macros"] if isinstance(k, str))
    for k in _mk_int + _mk_str:
        lines.append("p.macro." + str(FNKEY_NAMES.get(k, k)) + "=" + str(player["_macros"][k]))
    for _as in world.areas:
        # HP Prime G1 has unstable percent-format strings in save payloads.
        lines.append("a." + str(_as["tag"]) + ".age=" + str(_as["age"]))
        weather = _as.get("weather")
        if weather is not None:
            lines.append("a." + str(_as["tag"]) + ".precip=" + str(weather.get("precip", 0)))
            lines.append("a." + str(_as["tag"]) + ".precipv=" + str(weather.get("precip_vector", 0)))
    lines.append("g.time=" + str(time_info["hour"]) + "|" + str(time_info["day"]) + "|" + str(time_info["month"]) + "|" + str(time_info["year"]))
    for _gql in gq_save_lines():  # [PRIMESUD] gquest state
        lines.append(_gql)
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
            room_parts.append(str(r))
        lines.append("m." + str(tpl_vnum) + "=" + "|".join(room_parts))
    # Re-serialize pending mob deltas for unloaded areas (not in world.chars)
    for tpl_vnum in sorted(world._pending_mob_saves):
        if tpl_vnum in tpl_rooms:
            continue
        room_parts = []
        for r in world._pending_mob_saves[tpl_vnum]:
            room_parts.append(str(r))
        lines.append("m." + str(tpl_vnum) + "=" + "|".join(room_parts))
    for rvnum in sorted(world.rooms):
        rs = world.rooms[rvnum]
        if not rs["items"]:
            continue
        item_parts = []
        for o in rs["items"]:
            item_parts.append(serialize_item_token(o))
        lines.append("r." + str(rvnum) + ".items=" + "|".join(item_parts))
    # Re-serialize pending room items for unloaded areas (not in world.rooms)
    for rvnum in sorted(world._pending_room_items):
        lines.append("r." + str(rvnum) + ".items=" + str(world._pending_room_items[rvnum]))
    for i in range(len(lines)):
        if not isinstance(lines[i], str):
            raise Exception("non-str save line %s" % i)
    payload = "~".join(lines)
    hvars_set(SAVE_VAR, payload)
    saved = hvars_get(SAVE_VAR)
    if saved != payload:
        raise Exception("save verification failed (readback mismatch)")
    with open(SAVE_FILE, "w") as f:
        f.write(payload)


def save_world(quiet=False):
    """Save world state and optionally print success."""
    try:
        _serialize_world()
        if not quiet:
            tprint("Saved.")
        else:
            # [PRIMESUD] 'debug save' channel makes silent autosaves visible
            from debug import DBG, dbg
            if "save" in DBG:
                dbg("autosave")
        return True
    except Exception as e:
        tprint("Save failed: %s" % e)
        return False


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

    _STAT_KEYS = {"str", "dex", "int", "wis", "con"}
    int_keys = {"level", "xp", "xp_next", "trivia",
                "str", "dex", "int", "wis", "con",
                "hit", "mana", "move",
                "perm_hit", "perm_mana", "perm_move",
                "room", "alignment", "prime_class",
                "practice", "train", "flags", "played",
                "gold", "silver", "wimpy",
                "quest_points", "quest_status", "quest_time",
                "quest_mob", "quest_obj", "quest_room", "quest_giver"}

    if player["_macros"] is not None:
        player["_macros"].clear()

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
        elif key.startswith("p.eq."):
            slot = key[5:]
            player["equip"][slot] = parse_item_token(val) if val else None
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
        elif key.startswith("p."):
            pkey = key[2:]
            if pkey in _STAT_KEYS:
                player["perm_stat"][pkey] = int(val)
            else:
                player[pkey] = int(val) if pkey in int_keys else val
        elif key.startswith("r.") and key.endswith(".items"):
            rvnum = int(key.split(".")[1])
            world._pending_room_items[rvnum] = val
        elif key.startswith("a.") and key.endswith(".age"):
            tag = key[2:-4]
            if tag in _area_by_tag:
                _area_by_tag[tag]["age"] = int(val)
        elif key.startswith("a.") and key.endswith(".precip"):
            tag = key[2:-7]
            if tag in _area_by_tag:
                _area_by_tag[tag].setdefault("weather", {})
                _area_by_tag[tag]["weather"]["precip"] = int(val)
        elif key.startswith("a.") and key.endswith(".precipv"):
            tag = key[2:-8]
            if tag in _area_by_tag:
                _area_by_tag[tag].setdefault("weather", {})
                _area_by_tag[tag]["weather"]["precip_vector"] = int(val)
        elif key.startswith("g.gq") and gq_load_line(key, val):  # [PRIMESUD]
            pass
        elif key == "g.time":
            parts = val.split("|")
            if len(parts) == 4:
                time_info["hour"] = int(parts[0])
                time_info["day"] = int(parts[1])
                time_info["month"] = int(parts[2])
                time_info["year"] = int(parts[3])
                from game_time import SUN_DARK, SUN_RISE, SUN_LIGHT, SUN_SET
                h = time_info["hour"]
                if h < 5 or h >= 20:
                    time_info["sunlight"] = SUN_DARK
                elif h == 5:
                    time_info["sunlight"] = SUN_RISE
                elif h >= 18:
                    time_info["sunlight"] = SUN_SET
                else:
                    time_info["sunlight"] = SUN_LIGHT
        elif key.startswith("m."):
            mob_saves[int(key[2:])] = [int(r) for r in val.split("|") if r]

    # Buffer mob saves for deferred application: _load_area will apply
    # each area's deltas when it actually loads (player enters the area).
    world._pending_mob_saves.update(mob_saves)

    # Player room access triggers the player's area load, which applies
    # pending deltas for that area via _apply_pending_deltas.
    if player["room"] not in world.rooms:
        player["room"] = R_STARTING_ROOM

    # Restore pet in the player's room (cf. 1stMud fread_pet in save.c)
    if _pet_save:
        from world import MOB_DEFS
        parts = _pet_save.split("|")
        try:
            _tpl = int(parts[0])
        except ValueError:
            _tpl = None
        if _tpl is not None and _tpl in MOB_DEFS:
            from mob import spawn_pet
            _hp = (int(parts[1]) if len(parts) > 1
                   and parts[1].lstrip("-").isdigit() else None)
            _max = (int(parts[2]) if len(parts) > 2
                    and parts[2].lstrip("-").isdigit() else None)
            _pname = parts[3] if len(parts) > 3 and parts[3] else None
            player["pet"] = None
            _pet = spawn_pet(_tpl, player, name_arg=_pname, announce=False)
            # max_hit rerolls in create_mobile; restore the saved roll
            if _max is not None:
                _pet["max_hit"] = _max
            if _hp is not None:
                _pet["hit"] = max(1, min(_hp, _pet["max_hit"]))
            # Re-apply saved affects (cf. 1stMud fread_pet "Affc" entries)
            if _pet_affects:
                from handler import affect_to_char
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
# looping over weapon_table directly. 1stMud's 5th entry displays as "staff"
# but resolves to gsn_spear; WEAPON_GSN_MAP (skills_table.py) has no "staff"
# key, so "spear" (the underlying skill name) is used here instead.
_WEAPON_PICK_ORDER = ("sword", "mace", "dagger", "axe", "spear", "flail",
                      "whip", "polearm")


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
        str: Sanitized name, or "Hero" if nothing valid remains.
    """
    letters = []
    for c in raw:
        if ("a" <= c <= "z") or ("A" <= c <= "Z"):
            letters.append(c)
            if len(letters) == 12:
                break
    if len(letters) < 2:  # ROM minimum name length (check_parse_name: 2-12)
        return "Hero"
    return capitalize("".join(letters))


def new_game(game):
    """Create a new game world with a fresh player character. [PRIMESUD]

    Mirrors 1stMud nanny.c chargen order: name (CON_GET_NAME) -> class
    (CON_GET_NEW_CLASS) -> create_char (fixed stats/skill grants) -> alignment
    (HANDLE_CON_GET_ALIGNMENT) -> weapon pick (send_weapon_info /
    HANDLE_CON_PICK_WEAPON) -> outfit -> newbie info (CON_READ_MOTD
    level==0 block) -> save. Deity/timezone/email/screen-size prompts are not
    ported [PRIMESUD] -- single-user, no deity or telnet negotiation system.

    Args:
        game: Game instance (supplies the terminal for prompts).
    """
    # Name prompt (cf. 1stMud nanny.c CON_GET_NAME).
    raw_name = game.tr.input("By what name do you wish to be known? ")
    name = _sanitize_name(raw_name)

    # Class choice (cf. 1stMud nanny.c CON_GET_NEW_CLASS; [PRIMESUD] picker with
    # one-line summaries instead of a bare list + 'help <class>').
    labels = [c["names"][0] + " - " + c["summary"] for c in CLASS_TABLE]
    idx = pick_from("Choose your class:", labels)
    if idx < 0:
        idx = CLASS_WARRIOR  # [PRIMESUD] Esc at new game defaults to Warrior
    world.reset_lazy()
    world.areas = create_area_states()
    gq_reset()  # [PRIMESUD] fresh gquest schedule per game
    player = create_char(idx)
    player["name"] = name
    player["_macros"] = _MACRO_SUBST
    world.chars[1] = player

    # Alignment pick (cf. 1stMud nanny.c HANDLE_CON_GET_ALIGNMENT).
    align_idx = pick_from("Choose your alignment:", ["Good", "Neutral", "Evil"])
    if align_idx < 0:
        align_idx = 1  # [PRIMESUD] Esc defaults to Neutral; 1stMud re-prompts instead
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
        widx = pick_from("Please pick a weapon from the following choices:",
                          [capitalize(w) for w in candidates])
        wname = candidates[widx] if widx >= 0 else CLASS_TABLE[idx]["weapon"]
        # [PRIMESUD] Esc defaults to the class's own starting weapon;
        # 1stMud re-prompts instead of allowing cancellation.
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
    from info import do_help
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
    reset_char(player)
    return result


def save_game(game, quiet=False):
    """Persist the current world state to storage. [PRIMESUD]"""
    return save_world(quiet)
