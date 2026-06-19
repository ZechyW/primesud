"""Player creation, progression, prompt, and save/load state."""

from util import gc_collect
from prime_platform import hvars_get, hvars_set
from config import (
    SAVE_VAR,
    TERMINAL_COLS,
    FNKEY_NAMES,
)
from world import (
    ROOMS,
    RESETS,
    SKILL_TABLE,
    SKILLS,
    R_STARTING_ROOM,
    GSN_SWORD,
    GSN_RECALL,
)

_EQUIP_SAVE_ORDER = (
    "light", "finger_l", "finger_r", "neck_1", "neck_2", "body", "head",
    "legs", "feet", "hands", "arms", "shield", "about", "waist", "wrist_l",
    "wrist_r", "wield", "hold", "float", "secondary",
)

# -- Player flag bits (cf. 1stMud PLR_* in bits.h) -----------------------------
PLR_AUTOMAP = 1
PLR_DEFAULTS = PLR_AUTOMAP

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
SAVE_VERSION = 1

# -- Player model --------------------------------------------------------------


def create_char():
    """Return a fresh player state dict with default starting values (cf. 1stMud new_char + new_pcdata in recycle.c).

    Returns:
        dict: Player state dict.
    """
    return {
        "name": "",
        "is_npc": False,
        "level": 1,
        "xp": 0,
        "xp_next": 1000,
        "str": 13,
        "dex": 13,
        "int": 13,
        "wis": 13,
        "con": 13,
        "hp": 20,
        "hp_max": 20,
        "mp": 100,
        "mp_max": 100,
        "practice": 5,
        "train": 3,
        "hitroll": 0,
        "damroll": 0,
        "saving_throw": 0,
        "AC": 100,  # base unarmored (100 = poor; negative = better)
        "wait": 0,  # skill lag in pulses
        "daze": 0,  # stun in pulses
        "affects": {},
        "affect_list": [],
        "mod_stat": {},
        "room": R_STARTING_ROOM,
        "inv": [],
        "equip": {
            "light":     None,
            "finger_l":  None,
            "finger_r":  None,
            "neck_1":    None,
            "neck_2":    None,
            "body":      None,
            "head":      None,
            "legs":      None,
            "feet":      None,
            "hands":     None,
            "arms":      None,
            "shield":    None,
            "about":     None,
            "waist":     None,
            "wrist_l":   None,
            "wrist_r":   None,
            "wield":     None,
            "hold":      None,
            "float":     None,
            "secondary": None,
        },
        # All level-1 skills start at 1% (cf. 1stMud group_add sets learned=1).
        # Sword=40 mirrors nanny.c weapon choice; recall=50 explicit in nanny.c.
        "learned": {
            sn: (40 if sn == GSN_SWORD else 50 if sn == GSN_RECALL else 1)
            for sn, data in SKILL_TABLE
            if data["skill_level"] == 1
        },
        "fighting": None,
        "pos": "standing",
        "flags": PLR_DEFAULTS,
        "played": 0,  # cumulative playtime in seconds (cf. 1stMud pcdata->played)
    }




from actor import get_curr_stat, affect_remove


# -- Tick regen ---------------------------------------------------------------

def tick_update(tr, player, room):
    """Regenerate HP and MP once per world tick (cf. 1stMud hit_gain/mana_gain in update.c).

    Position is always treated as resting -- no position system [PRIMESUD].
    Hunger/thirst conditions omitted [PRIMESUD].

    Args:
        tr: Terminal for affect wear-off messages.
        player (dict): Player state dict.
        room (dict): Current room (supplies heal_rate/mana_rate).
    """
    con  = get_curr_stat(player, "con")
    int_ = get_curr_stat(player, "int")
    wis  = get_curr_stat(player, "wis")
    level = player.get("level", 1)

    # HP (cf. 1stMud hit_gain in update.c)
    hp_gain = max(3, con - 3 + level // 2) + (player["hp_max"] - 10)
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

    player["hp"] = min(player["hp_max"], player["hp"] + hp_gain)
    player["mp"] = min(player["mp_max"], player["mp"] + mp_gain)

    for aff in list(player.get("affect_list", [])):
        if aff["duration"] > 0:
            aff["duration"] -= 1
        elif aff["duration"] == 0:
            msg = SKILLS.get(aff.get("type"), {}).get("msg_off", "")
            if msg and not msg.startswith("!"):
                tr.print(msg)
            affect_remove(player, aff)


# -- Display -------------------------------------------------------------------

def show_prompt(tr, player, buf):
    """Update the terminal status bar with the current HP/MP/XP prompt.

    Args:
        tr: Terminal instance.
        player (dict): Player state dict.
        buf (str): Current input buffer shown on the right of the prompt.
    """
    prefix = "HP:{}/{} MP:{}/{} {}tnl>".format(
        player["hp"], player["hp_max"],
        player["mp"], player["mp_max"],
        player["xp_next"] - player["xp"],
    )
    avail = max(1, TERMINAL_COLS - 6 - len(prefix))
    tr.set_status(prefix + buf[-avail:])


# -- Persistence ---------------------------------------------------------------
# Save data is stored in a PPL home variable (SAVE_VAR) via HVars so it
# survives app reinstalls.  Serialisation constraints:
#   - Lines are joined with '~'; no saved field value may contain '~'.
#   - No field value may contain '"' (would break the PPL string literal).
#   - HVars returns the string "Error: Invalid input" when the variable does
#     not exist yet (i.e. no save found); load_char treats this as no-save.
# The same payload is also mirrored to SAVE_FILE for inspection/backup.
# (Issue is that files are overwritten on app update/reinstall)
SAVE_FILE = "primesud.sav"

def save_char(player, world):
    """Serialise player and world state to a PPL HVars variable (cf. 1stMud save_char_obj in save.c).

    Reads macros from player["_macros"].

    Args:
        player (dict): Player state dict.
        world (dict): Game world state (keys: rooms, mobs, areas).

    Raises:
        Exception: If the PPL write fails, readback does not match the written
            payload, or the save-file mirror cannot be written.
    """
    gc_collect()
    lines = ["v=" + str(SAVE_VERSION)]
    for key in ("name", "level", "xp", "xp_next",
                "str", "dex", "int", "wis", "con",
                "hp", "hp_max", "mp", "mp_max",
                "hitroll", "damroll", "saving_throw", "AC", "room",
                "practice", "train", "flags", "played"):
        lines.append("p." + key + "=" + str(player[key]))
    inv_parts = []
    for o in player["inv"]:
        inv_parts.append(str(o["vnum"]) + ":" + str(o["cost"]))
    lines.append("p.inv=" + "|".join(inv_parts))
    for slot in _EQUIP_SAVE_ORDER:
        obj = player["equip"][slot]
        val = str(obj["vnum"]) + ":" + str(obj["cost"]) if obj is not None else ""
        lines.append("p.eq." + slot + "=" + val)
    learned_parts = []
    for sk in sorted(player["learned"]):
        learned_parts.append(str(sk) + ":" + str(player["learned"][sk]))
    lines.append("p.learned=" + "|".join(learned_parts))
    for k in sorted(player["_macros"]):
        lines.append("p.macro." + str(FNKEY_NAMES.get(k, k)) + "=" + str(player["_macros"][k]))
    for _as in world["areas"]:
        # HP Prime G1 has unstable percent-format strings in save payloads.
        lines.append("a." + str(_as["tag"]) + ".age=" + str(_as["age"]))
    # Build reset-room map for single-instance mobs (gl=1): if the only live
    # instance is already in its reset room, omit it -- reset_area() will
    # restore it there on load without any save entry needed.
    _single_reset_room = {}
    for entry in RESETS:
        if entry[0] == "M" and entry[2] == 1:
            _single_reset_room[entry[1]] = entry[3]

    tpl_rooms = {}
    tpl_order = []
    for mob_id in sorted(world["mobs"]):
        inst = world["mobs"][mob_id]
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
    for rvnum in sorted(world["rooms"]):
        rs = world["rooms"][rvnum]
        if not rs["items"]:
            continue
        item_parts = []
        for o in rs["items"]:
            item_parts.append(str(o["vnum"]) + ":" + str(o["cost"]))
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


def save_state(tr, player, world, quiet=False):
    """Save player/world state and optionally print success."""
    try:
        save_char(player, world)
        if not quiet:
            tr.print("Saved.")
        return True
    except Exception as e:
        tr.print("Save failed: %s" % e)
        return False


def _parse_item(s):
    """Parse a saved item token ('vnum:cost') into an instance dict."""
    v, c = s.split(":", 1)
    return {"vnum": int(v), "cost": int(c)}


def load_char(player, world):
    """Deserialise player and world state from the PPL HVars variable (cf. 1stMud load_char_obj in save.c).

    Mutates player and world in-place.  Macros are read from player["_macros"]
    (must be set by caller before calling).

    Args:
        player (dict): Player state dict to populate.
        world (dict): Game world state (keys: rooms, mobs, areas).

    Returns:
        bool: True if a save was found and loaded, False if no save exists or on error.
    """
    try:
        data = hvars_get(SAVE_VAR)
        if not data or not isinstance(data, str) or data.startswith("Error:"):
            return False
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

    int_keys = {"level", "xp", "xp_next",
                "str", "dex", "int", "wis", "con",
                "hp", "hp_max", "mp", "mp_max",
                "hitroll", "damroll", "saving_throw", "AC", "room",
                "practice", "train", "flags", "played"}

    if player["_macros"] is not None:
        player["_macros"].clear()

    _area_by_tag = {s["tag"]: s for s in world["areas"]} if world["areas"] is not None else {}
    mob_saves = {}  # tpl_vnum -> [room, room, ...]

    _name_to_fn = {name: sentinel for sentinel, name in FNKEY_NAMES.items()}
    for line in data.split("~"):
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        if key.startswith("p.eq."):
            slot = key[5:]
            player["equip"][slot] = _parse_item(val) if val else None
        elif key == "p.inv":
            player["inv"] = [_parse_item(v) for v in val.split("|") if v]
        elif key == "p.learned":
            for entry in val.split("|"):
                if ":" in entry:
                    sk_str, pct_str = entry.split(":", 1)
                    try:
                        player["learned"][int(sk_str)] = int(pct_str)
                    except ValueError:
                        pass
        elif key.startswith("p.macro.") and player["_macros"] is not None:
            raw = key[8:]
            player["_macros"][_name_to_fn.get(raw, raw)] = val
        elif key.startswith("p."):
            pkey = key[2:]
            player[pkey] = int(val) if pkey in int_keys else val
        elif key.startswith("r.") and key.endswith(".items"):
            rvnum = int(key.split(".")[1])
            if rvnum in world["rooms"]:
                world["rooms"][rvnum]["items"] = [_parse_item(v) for v in val.split("|") if v]
        elif key.startswith("a.") and key.endswith(".age"):
            tag = key[2:-4]
            if tag in _area_by_tag:
                _area_by_tag[tag]["age"] = int(val)
        elif key.startswith("m."):
            mob_saves[int(key[2:])] = [int(r) for r in val.split("|") if r]

    # Apply saved mob rooms: delete killed instances, patch wandered rooms.
    # Same vnum appearing multiple times means multiple instances in one room -- correct.
    for tpl_vnum, saved_rooms in mob_saves.items():
        inst_ids = sorted(i for i, inst in world["mobs"].items() if inst["tpl"] == tpl_vnum)
        for mid in inst_ids[len(saved_rooms):]:   # excess = killed since last save
            del world["mobs"][mid]
        for mid, room_vnum in zip(inst_ids, saved_rooms):
            if room_vnum in ROOMS:
                world["mobs"][mid]["room"] = room_vnum

    if player["room"] not in world["rooms"]:
        player["room"] = R_STARTING_ROOM

    for rs in world["rooms"].values():
        rs["mobs"] = []
    for mob_id, inst in world["mobs"].items():
        world["rooms"][inst["room"]]["mobs"].append(mob_id)

    return True
