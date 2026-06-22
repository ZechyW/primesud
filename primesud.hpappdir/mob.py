"""Mobile creation, reset handling, wandering, and area updates."""

from urandom import randint

from config import EXIT_NAMES
from world import ROOMS, ROOM_AREAS, AREA_DEFS, MOB_TEMPLATES, RESETS, DOOR_RESET
from actor import equip_char
from item import create_object
from actor import act


# Area age thresholds (cf. 1stMud area_update: age < 3 skip; age >= 15 reset
# when player present; age >= 31 hard cap).  Single-player simplification:
# player is always present, so the condition collapses to age >= 15.
_AREA_AGE_MIN   = 3
_AREA_AGE_RESET = 15


_RESET_MSGS = (
    "The area repopulates itself.",
    "You notice a change in the area.",
    "Time completes another cycle bringing life to the area.",
    "You feel a sudden deja-vu bringing change to the area.",
    "You hear noises off in the distance...",
)


def _stat_from_level(level):
    """Uniform mob stat derived from level (cf. 1stMud create_mobile perm_stat).

    Args:
        level (int): Mob level.

    Returns:
        int: Stat value in range [11, 25].
    """
    # 25 cap intentional: 1stMud create_mobile also hardcodes 25 for mob perm_stat (db.c)
    return min(25, 11 + level // 4)


_SIZE_RANK = {"tiny": 0, "small": 1, "medium": 2, "large": 3, "huge": 4, "giant": 5}


def create_mobile(tpl_vnum):
    """Instantiate a mob from its template (cf. 1stMud create_mobile in db.c).

    Returns a placement-agnostic instance dict; caller must set "room" and
    "home_area" before registering it in mob_instances.

    Args:
        tpl_vnum (int): Mob template VNUM.

    Returns:
        dict: Mob instance dict.
    """
    tpl = MOB_TEMPLATES[tpl_vnum]
    _n, _s, _b = tpl["hp_dice"]
    hp = _b
    for _ in range(_n):
        hp += randint(1, _s)
    hp = max(1, hp)
    base = _stat_from_level(tpl["level"])
    act_flags = tpl.get("act_flags", {})
    off  = tpl.get("off_flags", {})

    # Per-stat values start uniform then receive class/off/size bonuses
    # (cf. 1stMud create_mobile perm_stat loop + ACT_WARRIOR/THIEF/CLERIC/MAGE blocks)
    s_str = s_dex = s_int = s_wis = s_con = base
    if act_flags.get("warrior"):
        s_str += 3; s_int -= 1; s_con += 2
    if act_flags.get("thief"):
        s_dex += 3; s_int += 1; s_wis -= 1
    if act_flags.get("cleric"):
        s_wis += 3; s_dex -= 1; s_str += 1
    if act_flags.get("mage"):
        s_int += 3; s_str -= 1; s_dex += 1
    if off.get("fast"):
        s_dex += 2
    size_delta = _SIZE_RANK.get(tpl.get("size", "medium"), 2) - 2   # 2 = SIZE_MEDIUM
    s_str += size_delta
    s_con += size_delta // 2

    wealth = tpl.get("wealth", 0)
    if wealth > 0:
        w = randint(wealth // 2, 3 * wealth // 2)
        mob_gold = randint(w // 200, w // 100) if w >= 200 else 0
        mob_silver = w - mob_gold * 100
    else:
        mob_gold = 0
        mob_silver = 0

    return {
        "tpl":       tpl_vnum,
        "is_npc":    True,
        "hp":        hp,
        "hp_max":    hp,
        "affects":   {},
        "wait":      0,
        "daze":      0,
        "fighting":  None,
        "off_flags": dict(off),
        "inv":       [],
        "equip":     {},
        "level":     tpl["level"],
        "str":       s_str,
        "dex":       s_dex,
        "int":       s_int,
        "wis":       s_wis,
        "con":       s_con,
        "hitroll":   tpl["hitroll"],
        "damroll":   tpl["damage"][2],   # bonus = damroll (cf. 1stMud damage[DICE_BONUS])
        "armor":     tuple(v * 10 for v in tpl["armor"]),  # area-template buckets -> PrimeSUD runtime units
        "gold":      mob_gold,
        "silver":    mob_silver,
    }


def _tpl_live_count(mob_instances, tpl_vnum):
    """Count live instances of a template across all rooms (cf. pMobIndex->count in db.c)."""
    return sum(1 for inst in mob_instances.values() if inst.get("is_npc") and inst["tpl"] == tpl_vnum)


def _tpl_room_count(mob_instances, room_vnum, tpl_vnum):
    """Count live instances of a template in a specific room (cf. per-room scan in reset_room, db.c)."""
    return sum(1 for inst in mob_instances.values()
               if inst.get("is_npc") and inst["tpl"] == tpl_vnum and inst["room"] == room_vnum)


def reset_mobs(mob_instances, room_state, resets, tr=None, debug=False):
    """Spawn mobs for each M entry up to global and room limits (cf. 1stMud reset_room 'M' case, db.c).

    E and G entries following a successful M equip or give items to the spawned mob,
    matching 1stMud's LastMob/last context chain.  O and P entries clear the context.

    Mutates mob_instances and room_state in place.  Safe to call on a
    partially-populated mob_instances (area tick) as well as an empty one
    (full reset via reset_area).

    Args:
        mob_instances (dict): Mob instance mapping mob ID -> instance dict.
        room_state (dict): Room state mapping room vnum -> room state dict.
        resets (tuple): Area RESETS sequence.
        tr: Optional terminal for reset debug output.
        debug (bool): True to print each spawned mob.
    """
    mob_id = max(mob_instances, default=1) + 1
    last_mob_id  = None   # cf. 1stMud LastMob in reset_room
    last_spawned = False  # cf. 1stMud `last` flag in reset_room
    for entry in resets:
        cmd = entry[0]
        if cmd == "M":
            tpl_vnum, gl, room_vnum, rl = entry[1], entry[2], entry[3], entry[4]
            if _tpl_live_count(mob_instances, tpl_vnum) >= gl:
                last_spawned = False
                continue
            if _tpl_room_count(mob_instances, room_vnum, tpl_vnum) >= rl:
                last_spawned = False
                continue
            inst = create_mobile(tpl_vnum)
            inst["room"] = room_vnum
            inst["home_area"] = ROOM_AREAS.get(room_vnum)
            mob_instances[mob_id] = inst
            room_state[room_vnum]["mobs"].append(mob_id)
            if debug and tr is not None:
                tr.print("{D[reset] spawned %s in %s{x" % (
                    MOB_TEMPLATES[tpl_vnum]["short_descr"],
                    ROOMS[room_vnum]["name"]))
            last_mob_id  = mob_id
            last_spawned = True
            mob_id += 1
        elif cmd == "E" and last_spawned:
            mob = mob_instances[last_mob_id]
            obj = create_object(entry[1])
            mob["inv"].append(obj)
            equip_char(mob, obj, entry[2])
        elif cmd == "G" and last_spawned:
            mob_instances[last_mob_id]["inv"].append(create_object(entry[1]))
        elif cmd in ("O", "P"):
            last_spawned = False  # breaks mob context (cf. 1stMud last=false on O)


def reset_area():
    """Create fresh room state and mob instances (cf. 1stMud reset_area).

    Returns:
        tuple: (room_state (dict), mob_instances (dict)).
    """
    room_state = {vnum: {"items": [], "mobs": []} for vnum in ROOMS}
    mob_instances = {}
    reset_mobs(mob_instances, room_state, RESETS)
    for entry in RESETS:
        if entry[0] == "O":
            room_state[entry[2]]["items"].append(create_object(entry[1]))
    # Restore all door states to their reset-to values (cf. 1stMud reset_room door loop, db.c:1411)
    for vnum, doors in DOOR_RESET.items():
        exits = ROOMS[vnum]["exits"]
        for d, state in doors.items():
            exits[d]["closed"] = state["closed"]
            exits[d]["locked"] = state["locked"]
    return room_state, mob_instances


def create_area_states():
    """Create mutable area tick state from static area definitions."""
    states = []
    for d in AREA_DEFS:
        # [PRIMESUD] Simplified interim weather model for spell gating. This
        # keeps only precipitation and its drift, not full 1stMud weather.c.
        states.append({
            "tag": d["tag"],
            "age": 0,
            "resets": d["resets"],
            "weather": {
                "precip": randint(-2, 2),
                "precip_vector": randint(-1, 1),
            },
        })
    return states


def mobile_update(tr, player, world):
    """Wander mobs and despawn any that strayed out of their home area (cf. 1stMud mobile_update, char_update in update.c)."""
    for mob_id, inst in list(world["chars"].items()):
        if not inst.get("is_npc"):
            continue
        if ROOM_AREAS.get(inst["room"]) != inst["home_area"] and randint(1, 100) <= 5:
            # 5% chance to despawn when outside home area (cf. char_update, update.c:541)
            if player["room"] == inst["room"]:
                tpl = MOB_TEMPLATES[inst["tpl"]]
                _sd = tpl["short_descr"]
                act(tr, "{} wanders on home.".format(_sd))
            world["rooms"][inst["room"]]["mobs"].remove(mob_id)
            del world["chars"][mob_id]
            continue
        if inst["fighting"] is not None:
            continue
        act_flags = MOB_TEMPLATES[inst["tpl"]].get("act_flags", {})
        if act_flags.get("sentinel"):
            continue
        if randint(0, 7) != 0:  # 1/8 chance -- matches number_bits(3)==0
            continue
        exits = ROOMS[inst["room"]].get("exits", {})
        if not exits:
            continue
        dirs = list(exits.keys())
        direction = dirs[randint(0, len(dirs) - 1)]
        exit_val = exits[direction]
        if isinstance(exit_val, dict) and exit_val.get("closed"):  # cf. EX_CLOSED check, update.c:499
            continue
        dest_vnum = exit_val["to"] if isinstance(exit_val, dict) else exit_val
        if dest_vnum not in ROOMS:
            continue
        dest_flags = ROOMS[dest_vnum].get("flags", {})
        if dest_flags.get("no_mob"):  # cf. ROOM_NO_MOB check, update.c:500
            continue
        if act_flags.get("stay_area") and ROOM_AREAS.get(dest_vnum) != ROOM_AREAS.get(inst["room"]):
            continue  # cf. ACT_STAY_AREA check, update.c:501
        if act_flags.get("outdoors") and dest_flags.get("indoors"):
            continue
        if act_flags.get("indoors") and not dest_flags.get("indoors"):
            continue
        old_room = inst["room"]
        tpl = MOB_TEMPLATES[inst["tpl"]]
        _sd = tpl["short_descr"]
        if player["room"] == old_room:
            act(tr, "{} leaves {}.".format(_sd, EXIT_NAMES.get(direction, direction)))
        world["rooms"][old_room]["mobs"].remove(mob_id)
        inst["room"] = dest_vnum
        world["rooms"][dest_vnum]["mobs"].append(mob_id)
        if player["room"] == dest_vnum:
            act(tr, "{} has arrived.".format(_sd))


def area_update(tr, player, world):
    """Increment area ages and reset areas at threshold (cf. 1stMud area_update in db.c)."""
    for area in world["areas"]:
        weather = area.get("weather")
        if weather is not None:
            weather["precip"] += weather.get("precip_vector", 0)
            if weather["precip"] < -3:
                weather["precip"] = -3
            elif weather["precip"] > 3:
                weather["precip"] = 3
            weather["precip_vector"] += randint(-1, 1)
            if weather["precip"] <= -3 and weather["precip_vector"] < 0:
                weather["precip_vector"] = 0
            elif weather["precip"] >= 3 and weather["precip_vector"] > 0:
                weather["precip_vector"] = 0
            if weather["precip_vector"] < -1:
                weather["precip_vector"] = -1
            elif weather["precip_vector"] > 1:
                weather["precip_vector"] = 1
        area["age"] += 1
        if area["age"] >= _AREA_AGE_MIN and area["age"] >= _AREA_AGE_RESET:
            reset_mobs(world["chars"], world["rooms"], area["resets"])
            if area["tag"] == "mud_school":
                area["age"] = 13  # resets every 2 ticks (cf. db.c:1330: age = 15-2)
            else:
                area["age"] = randint(0, 3)
                # School area is intentionally silent (cf. db.c:1335 else-if excludes it).
                if ROOM_AREAS.get(player["room"]) == area["tag"]:
                    tr.print(_RESET_MSGS[randint(0, len(_RESET_MSGS) - 1)])
