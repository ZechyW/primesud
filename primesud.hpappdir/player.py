"""Player creation, progression, prompt, and save/load state."""

from util import gc_collect
from colors import color_len
from terminal import tprint, tr
from prime_platform import hvars_get, hvars_set
from config import (
    SAVE_VAR,
    TERMINAL_COLS,
    FNKEY_NAMES,
)
from config import R_STARTING_ROOM, MAX_MORTAL_LEVEL
from skills_table import SKILL_TABLE, SKILLS, GSN_SWORD, GSN_RECALL
import world
from world import ROOM_DEFS, AREA_DEFS
from item import serialize_item_token, parse_item_token

_EQUIP_SAVE_ORDER = (
    "light", "finger_l", "finger_r", "neck_1", "neck_2", "body", "head",
    "legs", "feet", "hands", "arms", "shield", "about", "waist", "wrist_l",
    "wrist_r", "wield", "hold", "float", "secondary",
)

# -- Player flag bits (cf. 1stMud PLR_* in bits.h) -----------------------------
PLR_AUTOMAP = 1
PLR_AUTOLOOT = 16    # BIT_E
PLR_AUTOSAC = 32     # BIT_F
PLR_AUTOGOLD = 64    # BIT_G
PLR_AUTOSPLIT = 128  # BIT_H
PLR_DEFAULTS = PLR_AUTOMAP | PLR_AUTOLOOT | PLR_AUTOSAC | PLR_AUTOGOLD | PLR_AUTOSPLIT

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
SAVE_VERSION = 5

# -- Player model --------------------------------------------------------------


def create_char():
    """Return fresh player state dict with default starting values.

    Overlays player-only (pcdata) fields onto _char_base()
    (cf. 1stMud new_char + new_pcdata in recycle.c; char_data in structs.h:560).

    Returns:
        dict: Player state dict.
    """
    ch = _char_base()
    ch.update({
        "hit":      20,   "max_hit":  20,   "perm_hit":  20,
        "mana":     100,  "max_mana": 100,  "perm_mana": 100,
        "move":     100,  "max_move": 100,  "perm_move": 100,
        "room":     R_STARTING_ROOM,
        "id":       1,
        # pcdata fields (cf. 1stMud PcData in structs.h):
        "xp_next":  1000,
        "practice": 5,
        "train":    3,
        "trivia":   0,
        "flags":    PLR_DEFAULTS,  # PLR_* bits; [DEVIATION] separate from act_flags
        "played":   0,
        # [PRIMESUD] Classless: grant all learnable skills at 1% from creation.
        # Level-gated via can_use_skill_spell; practice list filters by level.
        # Sword=40 mirrors nanny.c weapon choice; recall=50 explicit in nanny.c.
        "learned": {
            sn: (40 if sn == GSN_SWORD else 50 if sn == GSN_RECALL else 1)
            for sn, data in SKILL_TABLE
            if data["skill_level"] <= MAX_MORTAL_LEVEL
        },
        "equip": {
            "light":     None, "finger_l":  None, "finger_r":  None,
            "neck_1":    None, "neck_2":    None, "body":      None,
            "head":      None, "legs":      None, "feet":      None,
            "hands":     None, "arms":      None, "shield":    None,
            "about":     None, "waist":     None, "wrist_l":   None,
            "wrist_r":   None, "wield":     None, "hold":      None,
            "float":     None, "secondary": None,
        },
    })
    return ch




from actor import (get_curr_stat, affect_remove, _char_base,
                   _apply_item_modifiers, _item_armor_runtime)
from world import ITEM_DEFS


def reset_char(player):
    """Strip and reapply all equipment bonuses from scratch (cf. 1stMud reset_char in handler.c).

    Sets max_hit/mana/move back to perm_* baselines, clears combat modifiers,
    then re-applies every equipped item's armor and stat bonuses.

    Args:
        player (dict): Player state dict.
    """
    player["sex"] = player.get("true_sex", "neutral")
    for k in player.get("mod_stat", {}):
        player["mod_stat"][k] = 0
    player["max_hit"] = player["perm_hit"]
    player["max_mana"] = player["perm_mana"]
    player["max_move"] = player["perm_move"]
    player["armor"] = (100, 100, 100, 100)
    player["hitroll"] = 0
    player["damroll"] = 0
    player["saving_throw"] = 0
    for slot in _EQUIP_SAVE_ORDER:
        obj = player["equip"].get(slot)
        if obj is None:
            continue
        tpl = ITEM_DEFS.get(obj["vnum"])
        if tpl is None:
            continue
        armor = _item_armor_runtime(tpl)
        if armor is not None:
            a = player["armor"]
            player["armor"] = (a[0]-armor[0], a[1]-armor[1], a[2]-armor[2], a[3]-armor[3])
        _apply_item_modifiers(player, obj, tpl, True)


# -- Tick regen ---------------------------------------------------------------

def tick_update(tr, player, room):
    """Regenerate HP and MP once per world tick (cf. 1stMud hit_gain/mana_gain in update.c).

    Position is always treated as resting -- no position system [PRIMESUD].
    Hunger/thirst conditions omitted [PRIMESUD].

    Args:
        tr: Terminal for affect wear-off messages.
        player (dict): Player state dict.
        room (dict): Current room (supplies heal_rate/mana_rate).

    Uses imported world module for player stat lookups.
    """
    con  = get_curr_stat(player, "con")
    int_ = get_curr_stat(player, "int")
    wis  = get_curr_stat(player, "wis")
    level = player.get("level", 1)

    # HP (cf. 1stMud hit_gain in update.c)
    hp_gain = max(3, con - 3 + level // 2) + (player["max_hit"] - 10)
    # TODO: fast_healing bonus -- if roll < skill%, gain += roll * gain / 100
    # Position: always resting [PRIMESUD] -- sleeping=/1, resting=/2, standing=/4, fighting=/6
    hp_gain //= 2
    # Hunger/thirst omitted [PRIMESUD]
    hp_gain = hp_gain * room.get("heal_rate", 100) // 100
    # TODO: poison /4, plague /8, haste/slow /2
    hp_gain = max(1, hp_gain)

    # MP (cf. 1stMud mana_gain in update.c) -- base (WIS+INT+level)/2, resting /2
    mp_gain = (int_ + wis + level) // 4
    mp_gain = mp_gain * room.get("mana_rate", 100) // 100
    # TODO: poison /4, plague /8, haste/slow /2
    mp_gain = max(1, mp_gain)

    # MV (cf. 1stMud move_gain in update.c) -- base max(15, level), resting +DEX/2
    dex = get_curr_stat(player, "dex")
    mv_gain = max(15, level) + dex // 2
    mv_gain = mv_gain * room.get("heal_rate", 100) // 100
    # TODO: poison /4, plague /8, haste/slow /2
    mv_gain = max(1, mv_gain)

    player["hit"] = min(player["max_hit"], player["hit"] + hp_gain)
    player["mana"] = min(player["max_mana"], player["mana"] + mp_gain)
    player["move"] = min(player["max_move"], player["move"] + mv_gain)

    for aff in list(player.get("affect_list", [])):
        if aff["duration"] > 0:
            aff["duration"] -= 1
        elif aff["duration"] == 0:
            msg = SKILLS.get(aff.get("type"), {}).get("msg_off", "")
            if msg and not msg.startswith("!"):
                tr.print(msg)
            affect_remove(player, aff)


# -- Display -------------------------------------------------------------------

def show_prompt(player, buf):
    """Update the terminal status bar with the current HP/MP/XP prompt.

    Args:
        player (dict): Player state dict.
        buf (str): Current input buffer shown on the right of the prompt.
    """
    prefix = "{R%d/%dhp {M%d/%dmn {B%d/%dmv{x %dtnl>" % (
        player["hit"], player["max_hit"],
        player["mana"], player["max_mana"],
        player["move"], player["max_move"],
        player["xp_next"] - player["xp"],
    )
    avail = max(1, TERMINAL_COLS - 6 - color_len(prefix))
    tr.set_status(prefix + buf[-avail:])


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
                "gold", "silver"):
        lines.append("p." + key + "=" + str(player[key]))
    for stat in ("str", "dex", "int", "wis", "con"):
        lines.append("p." + stat + "=" + str(player["perm_stat"][stat]))
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
    # Build reset-room map for single-instance mobs (gl=1): if the only live
    # instance is already in its reset room, omit it -- reset_area() will
    # restore it there on load without any save entry needed.
    _single_reset_room = {}
    for _adef in AREA_DEFS:
        for entry in _adef["resets"]:
            if entry[0] == "M" and entry[2] == 1:
                _single_reset_room[entry[1]] = entry[3]

    tpl_rooms = {}
    tpl_order = []
    for mob_id in sorted(world.chars):
        inst = world.chars[mob_id]
        if not inst.get("is_npc"):
            continue
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
    for rvnum in sorted(world.rooms):
        rs = world.rooms[rvnum]
        if not rs["items"]:
            continue
        item_parts = []
        for o in rs["items"]:
            item_parts.append(serialize_item_token(o))
        lines.append("r." + str(rvnum) + ".items=" + "|".join(item_parts))
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
                "room", "alignment",
                "practice", "train", "flags", "played",
                "gold", "silver"}

    if player["_macros"] is not None:
        player["_macros"].clear()

    _area_by_tag = {s["tag"]: s for s in world.areas} if world.areas is not None else {}
    mob_saves = {}  # tpl_vnum -> [room, room, ...]

    _name_to_fn = {name: sentinel for sentinel, name in FNKEY_NAMES.items()}
    for line in data.split("~"):
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        if key.startswith("p.eq."):
            slot = key[5:]
            player["equip"][slot] = parse_item_token(val) if val else None
        elif key == "p.inv":
            player["inv"] = [parse_item_token(v) for v in val.split("|") if v]
        elif key == "p.learned":
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
            if rvnum in world.rooms:
                world.rooms[rvnum]["items"] = [parse_item_token(v) for v in val.split("|") if v]
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
        elif key.startswith("m."):
            mob_saves[int(key[2:])] = [int(r) for r in val.split("|") if r]

    # Apply saved mob rooms: delete killed instances, patch wandered rooms.
    # Same vnum appearing multiple times means multiple instances in one room -- correct.
    for tpl_vnum, saved_rooms in mob_saves.items():
        inst_ids = sorted(i for i, inst in world.chars.items() if inst.get("is_npc") and inst["tpl"] == tpl_vnum)
        for mid in inst_ids[len(saved_rooms):]:   # excess = killed since last save
            del world.chars[mid]
        for mid, room_vnum in zip(inst_ids, saved_rooms):
            if room_vnum in ROOM_DEFS:
                world.chars[mid]["room"] = room_vnum

    if player["room"] not in world.rooms:
        player["room"] = R_STARTING_ROOM

    for rs in world.rooms.values():
        rs["mobs"] = []
    for mob_id, inst in world.chars.items():
        if inst.get("is_npc"):
            world.rooms[inst["room"]]["mobs"].append(mob_id)

    return _source
