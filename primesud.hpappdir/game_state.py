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
from mob import reset_area, create_area_states
from player import create_char, reset_char, _EQUIP_SAVE_ORDER


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
    lines.append("g.time=" + str(time_info["hour"]) + "|" + str(time_info["day"]) + "|" + str(time_info["month"]) + "|" + str(time_info["year"]))
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

    return _source


def init_game_state(game):
    """Initialise mutable game state fields. [PRIMESUD]"""
    game._backup_ok = False


def new_game(game, name="Hero"):
    """Create a new game world with a fresh player character. [PRIMESUD]"""
    world.reset_lazy()
    world.areas = create_area_states()
    player = create_char()
    player["name"] = name
    player["_macros"] = _MACRO_SUBST
    world.chars[1] = player
    do_outfit(player, "")  # cf. 1stMud do_outfit in nanny.c for new chars
    save_game(game, quiet=True)


def load_game(game):
    """Load a saved game from persistent storage and restore world state. [PRIMESUD]"""
    world.reset_lazy()
    world.areas = create_area_states()
    player = create_char()
    player["_macros"] = _MACRO_SUBST
    world.chars[1] = player
    result = load_world()
    if isinstance(result, tuple):   # (None, backup_ok) -- version mismatch
        _, game._backup_ok = result
        return None
    # Retry deltas skipped during cascade (dest room states not yet created)
    world._retry_pending_deltas()
    reset_char(player)
    return result


def save_game(game, quiet=False):
    """Persist the current world state to storage. [PRIMESUD]"""
    return save_world(quiet)
