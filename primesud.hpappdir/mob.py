"""Mobile creation, reset handling, wandering, and area updates."""

from urandom import randint

from config import SIZE_RANK, POS_FROM_SHORT
import world
from world import ROOM_DEFS, MOB_DEFS, AREA_DEFS, DOOR_DEFS
from races import RACE_TABLE
from handler import equip_char, act, _char_base, is_awake, TO_ROOM, can_see
from item import create_object
from special import SPEC_TABLE
from debug import DBG, dbg  # [PRIMESUD]


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


def create_mobile(tpl_vnum):
    """Instantiate a mob from its template (cf. 1stMud create_mobile in db.c).

    Returns a placement-agnostic instance dict; caller must set "room" and
    "home_area" before registering it in mob_instances.

    Args:
        tpl_vnum (int): Mob template VNUM.

    Returns:
        dict: Mob instance dict.
    """
    tpl = MOB_DEFS[tpl_vnum]
    _n, _s, _b = tpl["hp_dice"]
    hp = _b
    for _ in range(_n):
        hp += randint(1, _s)
    hp = max(1, hp)
    base = _stat_from_level(tpl["level"])

    # Merge race defaults into template flags (cf. 1stMud db2.c:88-136,
    # where race->act/aff/off/imm/res/vuln/form/parts are OR'd into mob index).
    race = RACE_TABLE.get(tpl.get("race", "Human"))
    if race is None:
        race = RACE_TABLE["Human"]

    def _merge(tpl_key, race_key):
        merged = dict(race.get(race_key, {}))
        merged.update(tpl.get(tpl_key, {}))
        return merged

    act_flags = _merge("act_flags", "act")
    off       = _merge("off_flags", "off")
    affected_by = _merge("affected_by", "aff")
    imm_flags = _merge("imm_flags", "imm")
    res_flags = _merge("res_flags", "res")
    vuln_flags = _merge("vuln_flags", "vuln")
    # [not ported] form and parts merged but not yet used in gameplay
    form_flags = _merge("form_flags", "form")
    part_flags = _merge("part_flags", "parts")

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
    size_delta = SIZE_RANK.get(tpl.get("size", "medium"), 2) - 2   # 2 = SIZE_MEDIUM
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

    ch = _char_base()
    ch.update({
        # -- Mob identity
        "tpl":        tpl_vnum,    # cf. 1stMud pIndexData ptr
        "is_npc":     True,
        "name":       tpl["short_descr"],
        "level":      tpl["level"],
        "sex":        tpl.get("sex", "neutral"),
        "race":       tpl.get("race", "Human"),
        "alignment":  tpl.get("alignment", 0),
        "size":       tpl.get("size", "medium"),
        # -- Resources
        "hit":        hp,  "max_hit":  hp,
        "gold":       mob_gold,
        "silver":     mob_silver,
        # -- Combat stats
        "hitroll":    tpl["hitroll"],
        "damroll":    tpl["damage"][2],  # bonus = damroll (cf. 1stMud damage[DICE_BONUS])
        "armor":      tuple(v * 10 for v in tpl["armor"]),  # area units -> PrimeSUD runtime units
        "perm_stat":  {"str": s_str, "dex": s_dex, "int": s_int,
                       "wis": s_wis, "con": s_con},
        # -- Flags (race+template merged; cf. 1stMud create_mobile db2.c:88-136)
        "act_flags":  dict(act_flags),
        "off_flags":  off,
        "affected_by":  dict(affected_by),
        "imm_flags":  imm_flags,
        "res_flags":  res_flags,
        "vuln_flags": vuln_flags,
        "form_flags": form_flags,
        "part_flags": part_flags,
        # cf. 1stMud create_mobile: mob->position = mob->start_pos
        "pos":        POS_FROM_SHORT.get(tpl.get("start_pos", "stand"), "standing"),
    })
    return ch


def spawn_pet(tpl_vnum, owner, name_arg=None, hp=None, announce=True):
    """Create and register a pet mob owned by owner. [PRIMESUD]

    Shared by pet-shop purchase (do_buy pet branch in shop.py) and save
    restore (load_world in game_state.py). Mirrors the pet setup in 1stMud
    do_buy: ACT_PET, AFF_CHARM, optional custom name appended to keywords,
    neck-tag description, follower/leader/pet linkage.

    Args:
        tpl_vnum (int): Pet mob template VNUM.
        owner (dict): Player state dict; pet spawns in owner's room.
        name_arg (str): Optional custom name appended to keywords.
        hp (int): Optional current hp override (save restore).
        announce (bool): False suppresses add_follower messages (save restore).

    Returns:
        dict: The registered pet mob instance.
    """
    pet = create_mobile(tpl_vnum)
    pet["act_flags"]["pet"] = True           # cf. SetBit(pet->act, ACT_PET)
    pet["affected_by"]["charm"] = True       # cf. SetBit(pet->affected_by, AFF_CHARM)
    # 1stMud: pet->comm = COMM_NOTELL|NOSHOUT|NOCHANNELS -- comm flags not ported

    if name_arg:
        # cf. 1stMud replace_strf(&pet->name, "%s %s", pet->name, arg)
        pet["keywords"] = MOB_DEFS[tpl_vnum].get("keywords", "") + " " + str(name_arg)
        pet["pet_name"] = str(name_arg)      # [PRIMESUD] persisted for save/load

    # cf. 1stMud: description += "A neck tag says 'I belong to <name>'."
    _desc = MOB_DEFS[tpl_vnum].get("description", "")
    if _desc and not _desc.endswith("\n"):
        _desc = _desc + "\n"
    pet["description"] = _desc + "A neck tag says 'I belong to " + str(owner.get("name", "")) + "'."

    if hp is not None:
        pet["hit"] = max(1, min(int(hp), pet["max_hit"]))

    room_vnum = owner["room"]
    next_id = max(world.chars, default=1) + 1
    pet["id"] = next_id
    pet["room"] = room_vnum
    pet["home_area"] = ROOM_DEFS[room_vnum].get("area")
    world.chars[next_id] = pet
    world.rooms[room_vnum]["mobs"].append(next_id)

    if announce:
        from comm import add_follower  # lazy import to avoid circular dependency
        add_follower(pet, owner)
    else:
        pet["master"] = owner["id"]
    pet["leader"] = owner["id"]
    owner["pet"] = next_id
    return pet


def _tpl_live_count(mob_instances, tpl_vnum):
    """Count live instances of a template across all rooms (cf. pMobIndex->count in db.c)."""
    return sum(1 for inst in mob_instances.values() if inst.get("is_npc") and inst["tpl"] == tpl_vnum)


def _tpl_room_count(mob_instances, room_vnum, tpl_vnum):
    """Count live instances of a template in a specific room (cf. per-room scan in reset_room, db.c)."""
    return sum(1 for inst in mob_instances.values()
               if inst.get("is_npc") and inst["tpl"] == tpl_vnum and inst["room"] == room_vnum)


def reset_room(vnum, next_id):
    """Reset one room's doors and process its resets (cf. 1stMud reset_room, db.c:1393).

    Resets door closed/locked state to initial values, then processes the
    room's M/O/E/G/P reset commands with count-based dedup.

    Args:
        vnum (int): Room VNUM.
        next_id (int): Next available mob instance ID.

    Returns:
        int: Updated next_id after any mob spawns.
    """
    rdef = ROOM_DEFS[vnum]
    # Door reset (cf. db.c:1411)
    doors = DOOR_DEFS.get(vnum)
    if doors:
        exits = rdef["exits"]
        for d, state in doors.items():
            exits[d]["closed"] = state["closed"]
            exits[d]["locked"] = state["locked"]
    # Process resets (cf. db.c:1427 switch on pReset->command)
    room_resets = rdef.get("resets")
    if not room_resets:
        return next_id
    rs = world.rooms[vnum]
    last_mob_id = None
    last_spawned = False
    for entry in room_resets:
        cmd = entry[0]
        if cmd == "M":
            tpl_vnum, gl, room_vnum, rl = entry[1], entry[2], entry[3], entry[4]
            if _tpl_live_count(world.chars, tpl_vnum) >= gl:
                last_spawned = False
                continue
            if _tpl_room_count(world.chars, room_vnum, tpl_vnum) >= rl:
                last_spawned = False
                continue
            inst = create_mobile(tpl_vnum)
            inst["room"] = room_vnum
            inst["home_area"] = ROOM_DEFS[room_vnum].get("area")
            inst["id"] = next_id
            world.chars[next_id] = inst
            world.rooms[room_vnum]["mobs"].append(next_id)
            if "spawn" in DBG:  # [PRIMESUD]
                dbg("spawn mob " + str(tpl_vnum) + " " + inst["name"] + " @" + str(room_vnum))
            last_mob_id = next_id
            last_spawned = True
            next_id += 1
        elif cmd == "E" and last_spawned:
            mob = world.chars[last_mob_id]
            obj = create_object(entry[1])
            if MOB_DEFS[mob["tpl"]].get("shop"):
                obj.setdefault("extra_flags", {})["inventory"] = True
            mob["inv"].append(obj)
            equip_char(mob, obj, entry[2])
        elif cmd == "G" and last_spawned:
            obj = create_object(entry[1])
            if MOB_DEFS[world.chars[last_mob_id]["tpl"]].get("shop"):
                obj.setdefault("extra_flags", {})["inventory"] = True
            world.chars[last_mob_id]["inv"].append(obj)
        elif cmd == "O":
            # [PRIMESUD] nplayer check omitted -- single-player, no reset delay
            obj_tpl = entry[1]
            has_one = False
            for o in rs.get("items", []):
                if (o["vnum"] if isinstance(o, dict) else o) == obj_tpl:
                    has_one = True
                    break
            if has_one:
                last_spawned = False
                continue
            obj = create_object(obj_tpl)
            obj["cost"] = 0  # cf. db.c:1527 -- O-placed items have zero cost
            rs["items"].append(obj)
            if "spawn" in DBG:  # [PRIMESUD]
                dbg("spawn obj " + str(obj_tpl) + " @" + str(vnum))
            last_spawned = True
        elif cmd == "P":
            last_spawned = False  # [PRIMESUD] containers not implemented
    return next_id


def reset_area(pArea):
    """Reset one area's rooms (cf. 1stMud reset_area, db.c:1726).

    Creates room state entries if missing, then calls reset_room per room.

    Args:
        pArea (dict): Area definition with 'room_vnums' key.
    """
    next_id = max(world.chars, default=1) + 1
    for vnum in pArea["room_vnums"]:
        if vnum not in world.rooms:
            world.rooms[vnum] = {"items": [], "mobs": []}
        next_id = reset_room(vnum, next_id)


def create_area_states():
    """Create mutable area tick state from static area definitions.

    room_vnums is omitted until the area is lazy-loaded; area_update skips
    reset for areas without it.
    """
    states = []
    for d in AREA_DEFS:
        # [PRIMESUD] Simplified interim weather model for spell gating. This
        # keeps only precipitation and its drift, not full 1stMud weather.c.
        entry = {
            "tag": d["tag"],
            "age": 0,
            "weather": {
                "precip": randint(-2, 2),
                "precip_vector": randint(-1, 1),
            },
        }
        if "room_vnums" in d:
            entry["room_vnums"] = d["room_vnums"]
        states.append(entry)
    return states


def mobile_update(tr, player):
    """Wander mobs and despawn any that strayed out of their home area (cf. 1stMud mobile_update, char_update in update.c).

    Args:
        tr: Terminal instance.
        player (dict): Player state dict.
    """
    for mob_id, inst in list(world.chars.items()):
        if not inst.get("is_npc"):
            continue
        if inst.get("affected_by", {}).get("charm"):
            # Charmed mobs (pets) neither wander nor despawn
            # (cf. 1stMud IsAffected(ch, AFF_CHARM) skips in update.c)
            continue
        if ROOM_DEFS[inst["room"]].get("area") != inst["home_area"] and randint(1, 100) <= 5:
            # 5% despawn outside home area (cf. 1stMud char_update, update.c:541-547).
            # 1stMud never persists NPC positions; this despawn keeps cross-area
            # wanderers short-lived, so losing their position on save/load is
            # fine -- they respawn at home on next area reset.
            act("$n wanders on home.", inst, type=TO_ROOM)
            world.rooms[inst["room"]]["mobs"].remove(mob_id)
            del world.chars[mob_id]
            if "move" in DBG:  # [PRIMESUD]
                dbg("despawn " + inst["name"] + " @" + str(inst["room"]))
            continue
        # Special function dispatch (cf. 1stMud update.c:429-433)
        tpl = MOB_DEFS[inst["tpl"]]
        spec_name = tpl.get("spec_fun")
        if spec_name is not None:
            spec = SPEC_TABLE.get(spec_name)
            if spec is not None and spec(inst):
                continue
        if inst["fighting"] is not None:
            continue
        act_flags = tpl.get("act_flags", {})
        if act_flags.get("sentinel"):
            continue
        if randint(0, 7) != 0:  # 1/8 chance -- matches number_bits(3)==0
            continue
        exits = ROOM_DEFS[inst["room"]].get("exits", {})
        if not exits:
            continue
        dirs = list(exits.keys())
        direction = dirs[randint(0, len(dirs) - 1)]
        exit_val = exits[direction]
        if isinstance(exit_val, dict) and exit_val.get("closed"):  # cf. EX_CLOSED check, update.c:499
            continue
        dest_vnum = exit_val["to"] if isinstance(exit_val, dict) else exit_val
        if dest_vnum not in ROOM_DEFS:
            continue
        dest_flags = ROOM_DEFS[dest_vnum].get("flags", {})
        if dest_flags.get("no_mob"):  # cf. ROOM_NO_MOB check, update.c:500
            continue
        if act_flags.get("stay_area") and ROOM_DEFS.get(dest_vnum, {}).get("area") != ROOM_DEFS[inst["room"]].get("area"):
            continue  # cf. ACT_STAY_AREA check, update.c:501
        if act_flags.get("outdoors") and dest_flags.get("indoors"):
            continue
        if act_flags.get("indoors") and not dest_flags.get("indoors"):
            continue
        old_room = inst["room"]
        # Wander via move_char so leave/arrive acts fire and followers are
        # dragged along (cf. 1stMud mobile_update move_char(ch, door, false),
        # update.c:503)
        from movement import move_char  # lazy import to avoid circular dependency
        move_char(inst, direction)
        if "move" in DBG and inst["room"] != old_room:  # [PRIMESUD]
            dbg("move " + inst["name"] + " " + str(old_room) + ">" + str(inst["room"]))


def aggr_update(tr, player):
    """Aggressive mobs attack the player.

    Single-player simplification: 1stMud iterates player_first then scans
    each player's room for aggressive NPCs.  We only have one player, so we
    scan the player's room directly and skip the random-victim selection
    (victim is always the player).

    Uses imported world module for mob/room data access.

    (cf. 1stMud aggr_update in update.c).
    [Verified: 23/06/2026]

    Args:
        tr: Terminal for printing combat messages.
        player (dict): Player state dict.
    """
    from combat import multi_hit

    # cf. update.c:951 -- immortal / empty area / ROOM_SAFE early-outs
    room_vnum = player["room"]
    room = ROOM_DEFS[room_vnum]
    if room.get("flags", {}).get("safe"):
        return

    mob_ids = list(world.rooms[room_vnum].get("mobs", []))
    for mob_id in mob_ids:
        ch = world.chars.get(mob_id)
        if ch is None:
            continue

        # cf. update.c:962-966 -- gate conditions on the aggressive mob
        if not ch.get("is_npc"):
            continue
        act_flags = ch.get("act_flags", {})
        if not act_flags.get("aggressive"):
            continue
        if ch.get("affected_by", {}).get("calm"):          # cf. IsAffected(ch, AFF_CALM)
            continue
        if ch["fighting"] is not None:
            continue
        if ch.get("affected_by", {}).get("charm"):          # cf. IsAffected(ch, AFF_CHARM)
            continue
        if not is_awake(ch):
            continue
        # cf. update.c:965 -- wimpy mob won't attack awake player
        if act_flags.get("wimpy") and is_awake(player):
            continue
        if not can_see(ch, player):                       # cf. update.c can_see check
            continue
        if randint(0, 1) == 0:                            # cf. number_bits(1) == 0
            continue

        # cf. update.c:976-978 -- level check: mob must be within 5 levels of victim
        # [PRIMESUD] no LEVEL_IMMORTAL check (single-player, no imm levels)
        if ch["level"] < player["level"] - 5:
            continue

        # cf. update.c:990 -- multi_hit(ch, victim, TYPE_UNDEFINED)
        multi_hit(ch, player)


def area_update(tr, player):
    """Increment area ages and reset areas at threshold (cf. 1stMud area_update, db.c:1296).

    Args:
        tr: Terminal for reset messages.
        player (dict): Player state dict.
    """
    for area in world.areas:
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
            if "room_vnums" not in area:
                area["age"] = _AREA_AGE_RESET
                continue
            if "reset" in DBG:  # [PRIMESUD]
                dbg("reset area " + area["tag"])
            reset_area(area)
            if area["tag"] == "mud_school":
                area["age"] = 13  # resets every 2 ticks (cf. db.c:1330: age = 15-2)
            else:
                area["age"] = randint(0, 3)
                # School area is intentionally silent (cf. db.c:1335 else-if excludes it).
                if ROOM_DEFS[player["room"]].get("area") == area["tag"]:
                    tr.print("{D" + _RESET_MSGS[randint(0, len(_RESET_MSGS) - 1)] + "{x")
