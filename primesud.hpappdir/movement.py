"""Movement, doors, and recall command handlers."""

from classes import is_class
from handler import (can_see_room, chprintln, act, TO_CHAR, TO_ROOM, TO_VICT,
                     get_char_room, is_awake, is_name, affect_strip,
                     affect_to_char)
from combat import stop_fighting
from skill_utils import WaitState, check_improve, get_skill
from stances import valid_stance, get_stance, STANCE_CURRENT
from config import (EXIT_ORDER, EXIT_NAMES, REV_DIR, DIR_ALIASES,
                    MOVEMENT_LOSS, POS_ORDER,
                    SECT_AIR, SECT_WATER_NOSWIM,
                    R_RECALL, PULSE_PER_SECOND)
from info import do_look, find_area_paths
from picker import pick_from
from quest import quest_room_check
from skills_table import (GSN_RECALL, GSN_PICK_LOCK, GSN_SNEAK, GSN_HIDE,
                          GSN_INVIS, GSN_MASS_INVIS, SKILLS)
from terminal import tprint
from urandom import randint
import world
from world import ROOM_DEFS


def _exit_to(exit_val):
    """Return destination vnum from a plain-vnum or dict exit."""
    return exit_val["to"] if isinstance(exit_val, dict) else exit_val


def _has_boat(ch):
    """Return True if ch carries a boat item (cf. 1stMud ITEM_BOAT check in move_char).

    Direct children only -- matches 1stMud carrying_first (act_move.c:131),
    which does not recurse into containers.
    """
    from world import ITEM_DEFS
    for obj in ch.get("inv", []):
        vnum = obj.get("vnum") if isinstance(obj, dict) else obj
        if ITEM_DEFS.get(vnum, {}).get("type") == "boat":
            return True
    for obj in ch.get("equip", {}).values():
        if obj is not None:
            vnum = obj.get("vnum") if isinstance(obj, dict) else obj
            if ITEM_DEFS.get(vnum, {}).get("type") == "boat":
                return True
    return False


def move_char(ch, direction):
    """Move a character through an exit (cf. 1stMud move_char in act_move.c).

    Actor-generic: players get full checks plus room display; mobs (wander
    via mobile_update, follower recursion) get leave/arrive acts and
    room-list bookkeeping. Followers recurse into move_char, matching
    1stMud's move_char(fch, door, true).

    Checks: exit existence, visibility, closed doors (with pass_door /
    nopass), charm anchor, and for players: guild rooms, sector
    restrictions (air, water), movement-point cost, haste/slow modifiers.

    Position gate handled by command table (do_north etc. have
    min_pos = "standing").

    [Verified: 03/07/2026; quest_room_check moved after follower loop to
    match 1stMud order and re-verified same day] -- private-room /
    area-closed checks, area entry sound, and exit/entry/greet progs not
    ported (see comments).

    Args:
        ch (dict): Moving character (player or mob instance).
        direction (str): Single-char direction key (n/e/s/w/u/d).
    """
    # -- p_exit_trigger (mob/obj/room progs) not ported --

    in_room = ROOM_DEFS[ch["room"]]
    exits = in_room.get("exits", {})
    is_npc = ch.get("is_npc", False)

    if direction not in exits:
        chprintln(ch, "Alas, you cannot go that way.")
        return

    exit_val = exits[direction]
    dest = _exit_to(exit_val)
    if dest not in ROOM_DEFS:
        chprintln(ch, "Alas, you cannot go that way.")
        return
    to_room = ROOM_DEFS[dest]

    if not can_see_room(ch, dest):
        chprintln(ch, "Alas, you cannot go that way.")
        return

    aff = ch.get("affected_by", {})

    # -- Closed door (with pass_door / nopass) --
    is_exit_dict = isinstance(exit_val, dict)
    if is_exit_dict and exit_val.get("closed"):
        if not aff.get("pass_door") or exit_val.get("nopass"):
            # 1stMud act "$d": first word of exit keyword, "door" if unset
            keyword = exit_val.get("keyword")
            keyword = keyword.split()[0] if keyword else "door"
            chprintln(ch, "The " + keyword + " is closed.")
            return

    # -- Charm anchor (cf. 1stMud AFF_CHARM && master in same room) --
    if aff.get("charm") and ch.get("master") is not None:
        master = world.chars.get(ch["master"])
        if master is not None and master.get("room") == ch["room"]:
            chprintln(ch, "What?  And leave your beloved master?")
            return

    # -- Private room / area closed checks not ported --

    if not is_npc:
        # -- Guild room (cf. 1stMud act_move.c: to_room->guild + is_class) --
        # "guild" tuple patched onto rooms by patch_1stmud_deltas.py;
        # Paladin/Ranger share the Cleric/Warrior guilds (CLASS_PLAN.md).
        allowed = to_room.get("guild")
        if allowed is not None:
            member = False
            for cl in allowed:
                if is_class(ch, cl):
                    member = True
                    break
            if not member:
                chprintln(ch, "You aren't allowed in there.")
                return

        # -- Sector: air --
        in_sect = in_room.get("sector", "inside")
        to_sect = to_room.get("sector", "inside")
        if in_sect == SECT_AIR or to_sect == SECT_AIR:
            if not aff.get("flying"):
                chprintln(ch, "You can't fly.")
                return

        # -- Sector: deep water (need boat or flying) --
        if (in_sect == SECT_WATER_NOSWIM or to_sect == SECT_WATER_NOSWIM) \
                and not aff.get("flying"):
            found = _has_boat(ch)
            if not found:
                chprintln(ch, "You need a boat to go there.")
                return

        # -- Movement point cost --
        move_cost = (MOVEMENT_LOSS.get(in_sect, 1)
                     + MOVEMENT_LOSS.get(to_sect, 1)) // 2
        if aff.get("flying") or aff.get("haste"):
            move_cost //= 2
        if aff.get("slow"):
            move_cost *= 2
        if ch.get("move", 0) < move_cost:
            chprintln(ch, "You are too exhausted.")
            return

        WaitState(ch, 1)
        ch["move"] = ch.get("move", 0) - move_cost

    # -- Stance drop on movement (cf. 1stMud move_char act_move.c:169)
    # [PRIMESUD] 1stMud passed "" (bare toggle); bare stance is now a
    # status screen, so relax explicitly via 'none'
    if valid_stance(get_stance(ch, STANCE_CURRENT)):
        from combat import do_stance  # lazy import (combat imports movement targets)
        do_stance(ch, ["none"])

    # -- Leave message (1stMud: act("$n leaves $T.", ch, NULL, dir_name[door], TO_ROOM))
    # Player actor: single-player, nobody to notify; skip.
    # 1stMud suppresses leave/arrive acts under AFF_SNEAK (invis_level n/a).
    if is_npc and not aff.get("sneak"):
        act("$n leaves $T.", ch, None, EXIT_NAMES.get(direction, direction), TO_ROOM)

    from_vnum = ch["room"]
    ch["room"] = dest
    if is_npc:
        # Mobs are tracked in per-room lists (players are not)
        if from_vnum in world.rooms and ch["id"] in world.rooms[from_vnum]["mobs"]:
            world.rooms[from_vnum]["mobs"].remove(ch["id"])
        if dest in world.rooms:
            world.rooms[dest]["mobs"].append(ch["id"])
        if not aff.get("sneak"):
            act("$n has arrived.", ch, type=TO_ROOM)
    else:
        # 1stMud: do_function(ch, &do_look, "auto") -- "auto" triggers brief mode;
        # PrimeSUD has no brief mode, so empty args shows full room.
        # [PRIMESUD] During speedwalk, intermediate rooms get brief one-liners.
        run_buf = ch.get("run_buf")
        if run_buf and any(a == "move" for a, _ in run_buf):
            _brief_room_line(ch)
        else:
            do_look(ch, [])

    # cf. 1stMud move_char: exit looping back to the same room skips
    # followers and quest checks
    if from_vnum == dest:
        return

    # -- Followers move too (cf. 1stMud move_char follower loop, act_move.c:232-257).
    # Mob followers come from the old room's mob list; the player (not tracked
    # in room lists) is checked separately so following a wandering mob works.
    followers = []
    if from_vnum in world.rooms:
        for fid in list(world.rooms[from_vnum]["mobs"]):
            fch = world.chars.get(fid)
            if fch is not None and fch.get("master") == ch["id"]:
                followers.append(fch)
    _p = world.chars.get(1)
    if (_p is not None and _p is not ch and _p.get("master") == ch["id"]
            and _p.get("room") == from_vnum):
        followers.append(_p)

    for fch in followers:
        # 1stMud: charmed follower below standing -> do_stand
        if (fch.get("affected_by", {}).get("charm")
                and POS_ORDER[fch["pos"]] < POS_ORDER["standing"]):
            fch["pos"] = "standing"

        if fch["pos"] != "standing" or not can_see_room(fch, dest):
            continue

        # 1stMud: ROOM_LAW blocks aggressive pets from entering the city
        if (to_room.get("flags", {}).get("law")
                and fch.get("is_npc")
                and fch.get("act_flags", {}).get("aggressive")):
            act("You can't bring $N into the city.", ch, None, fch, TO_CHAR)
            act("You aren't allowed in the city.", fch, None, None, TO_CHAR)
            continue

        act("You follow $N.", fch, None, ch, TO_CHAR)
        move_char(fch, direction)  # cf. 1stMud move_char(fch, door, true)

    # cf. 1stMud move_char act_move.c:266: quest check runs after the
    # follower loop (entry/greet progs, also there, not ported)
    if not is_npc:
        quest_room_check(ch)


# -- Direction command handlers (cf. 1stMud do_north..do_down in act_move.c) --
# Each registered in command table with min_pos = "standing".
# was_room check cancels run_buf on blocked movement (cf. 1stMud free_runbuf).

def do_north(player, args):
    """Walk north (cf. 1stMud do_north in act_move.c). [Verified: 03/07/2026]"""
    was_room = player["room"]
    move_char(player, "n")
    if was_room == player["room"]:
        free_runbuf(player)


def do_east(player, args):
    """Walk east (cf. 1stMud do_east in act_move.c). [Verified: 03/07/2026]"""
    was_room = player["room"]
    move_char(player, "e")
    if was_room == player["room"]:
        free_runbuf(player)


def do_south(player, args):
    """Walk south (cf. 1stMud do_south in act_move.c). [Verified: 03/07/2026]"""
    was_room = player["room"]
    move_char(player, "s")
    if was_room == player["room"]:
        free_runbuf(player)


def do_west(player, args):
    """Walk west (cf. 1stMud do_west in act_move.c). [Verified: 03/07/2026]"""
    was_room = player["room"]
    move_char(player, "w")
    if was_room == player["room"]:
        free_runbuf(player)


def do_up(player, args):
    """Walk up (cf. 1stMud do_up in act_move.c). [Verified: 03/07/2026]"""
    was_room = player["room"]
    move_char(player, "u")
    if was_room == player["room"]:
        free_runbuf(player)


def do_down(player, args):
    """Walk down (cf. 1stMud do_down in act_move.c). [Verified: 03/07/2026]"""
    was_room = player["room"]
    move_char(player, "d")
    if was_room == player["room"]:
        free_runbuf(player)


def _find_door(player, arg, exits):
    """Resolve a direction word or door keyword to a door exit
    (cf. 1stMud find_door in act_move.c).

    Args:
        player (dict): Player state dict.
        arg (str): Direction alias ("n", "north") or door keyword ("grate").
        exits (dict): Current room's exits.

    Returns:
        str: Direction key, or None after printing feedback.

    [Verified: 03/07/2026]
    """
    direction = DIR_ALIASES.get(arg.lower())
    if direction is None:
        for d in EXIT_ORDER:
            ev = exits.get(d)
            if (isinstance(ev, dict) and ev.get("isdoor")
                    and ev.get("keyword") and is_name(arg, ev["keyword"])):
                return d
        act("I see no $T here.", player, None, arg, TO_CHAR)
        return None
    if direction not in exits:
        act("I see no door $T here.", player, None, arg, TO_CHAR)
        return None
    exit_val = exits[direction]
    if not isinstance(exit_val, dict) or not exit_val.get("isdoor"):
        chprintln(player, "You can't do that.")
        return None
    return direction


def do_open(player, args):
    """Open a door in a given direction or by keyword (cf. 1stMud do_open in act_move.c).

    ITEM_PORTAL / ITEM_CONTAINER branches not ported -- doors only [PRIMESUD].
    [Verified: 03/07/2026]
    """
    exits = ROOM_DEFS[player["room"]]["exits"]
    _picked_dir = None
    if args:
        # 1stMud prints "Open what?" on no args; [PRIMESUD] picker below instead
        direction = _find_door(player, " ".join(args), exits)
        if direction is None:
            return
    else:
        candidates = [d for d in EXIT_ORDER
                      if isinstance(exits.get(d), dict)
                      and exits[d].get("isdoor") and exits[d].get("closed")]
        if not candidates:
            tprint("There are no doors to open here.")
            return
        idx = pick_from("Open which door?", [EXIT_NAMES[d] for d in candidates])
        if idx < 0:
            return
        direction = candidates[idx]
        _picked_dir = direction
    exit_val = exits[direction]
    if not exit_val.get("closed"):
        tprint("It's already open.")
        return
    if exit_val.get("locked"):
        tprint("It's locked.")
        return
    exit_val["closed"] = False
    tprint("Ok.")
    dest = exit_val["to"]
    rev = REV_DIR.get(direction)
    if rev and dest in ROOM_DEFS:
        rev_exit = ROOM_DEFS[dest]["exits"].get(rev)
        if isinstance(rev_exit, dict) and _exit_to(rev_exit) == player["room"]:
            rev_exit["closed"] = False
    return ("open " + EXIT_NAMES[_picked_dir].lower()) if _picked_dir is not None else None


def do_close(player, args):
    """Close a door in a given direction or by keyword (cf. 1stMud do_close in act_move.c).

    ITEM_PORTAL / ITEM_CONTAINER branches not ported -- doors only [PRIMESUD].
    [Verified: 03/07/2026]
    """
    exits = ROOM_DEFS[player["room"]]["exits"]
    _picked_dir = None
    if args:
        # 1stMud prints "Close what?" on no args; [PRIMESUD] picker below instead
        direction = _find_door(player, " ".join(args), exits)
        if direction is None:
            return
    else:
        candidates = [d for d in EXIT_ORDER
                      if isinstance(exits.get(d), dict)
                      and exits[d].get("isdoor") and not exits[d].get("closed")]
        if not candidates:
            tprint("There are no open doors to close here.")
            return
        idx = pick_from("Close which door?", [EXIT_NAMES[d] for d in candidates])
        if idx < 0:
            return
        direction = candidates[idx]
        _picked_dir = direction
    exit_val = exits[direction]
    if exit_val.get("closed"):
        tprint("It's already closed.")
        return
    # [PRIMESUD] 1stMud only checks EX_NOCLOSE on portals, not doors;
    # guard kept so noclose exits stay open
    if exit_val.get("noclose"):
        tprint("You can't do that.")
        return
    exit_val["closed"] = True
    tprint("Ok.")
    dest = exit_val["to"]
    rev = REV_DIR.get(direction)
    if rev and dest in ROOM_DEFS:
        rev_exit = ROOM_DEFS[dest]["exits"].get(rev)
        if isinstance(rev_exit, dict) and _exit_to(rev_exit) == player["room"]:
            rev_exit["closed"] = True
    return ("close " + EXIT_NAMES[_picked_dir].lower()) if _picked_dir is not None else None


# -- Locks ---------------------------------------------------------------------
# [PRIMESUD] ITEM_PORTAL / ITEM_CONTAINER branches of lock/unlock/pick not
# ported -- container open/close itself not ported yet.  Doors only.

def _has_key(ch, key_vnum):
    """True if ch carries the key item (cf. 1stMud has_key in act_move.c). [Verified: 03/07/2026]"""
    from item import obj_vnum
    for obj in ch["inv"] + [o for o in ch["equip"].values() if o is not None]:
        if obj_vnum(obj) == key_vnum:
            return True
    return False


def _door_for_lock_cmd(player, args, verb, want_locked):
    """Resolve target door for lock/unlock/pick: direction arg or picker [PRIMESUD].

    Args:
        player (dict): Player state dict.
        args (list): Command args; first token is a direction alias if present.
        verb (str): Command verb for prompts ("Lock" etc.).
        want_locked (bool): Picker candidates must be locked (True) or unlocked (False).

    Returns:
        (direction, exit_dict, picked) or (None, None, False) after printing feedback.
    """
    exits = ROOM_DEFS[player["room"]]["exits"]
    picked = False
    if args:
        direction = _find_door(player, " ".join(args), exits)
        if direction is None:
            return None, None, False
    else:
        candidates = [d for d in EXIT_ORDER
                      if isinstance(exits.get(d), dict)
                      and exits[d].get("isdoor") and exits[d].get("closed")
                      and exits[d].get("key") is not None
                      and bool(exits[d].get("locked")) == want_locked]
        if not candidates:
            tprint("There are no doors to " + verb.lower() + " here.")
            return None, None, False
        idx = pick_from(verb + " which door?", [EXIT_NAMES[d] for d in candidates])
        if idx < 0:
            return None, None, False
        direction = candidates[idx]
        picked = True
    return direction, exits[direction], picked


def _set_rev_lock(player, direction, exit_val, locked):
    """Mirror a lock state change onto the reverse exit (cf. 1stMud pexit_rev)."""
    dest = exit_val["to"]
    rev = REV_DIR.get(direction)
    if rev and dest in ROOM_DEFS:
        rev_exit = ROOM_DEFS[dest]["exits"].get(rev)
        if isinstance(rev_exit, dict) and _exit_to(rev_exit) == player["room"]:
            rev_exit["locked"] = locked


def do_lock(player, args):
    """Lock a closed door with its key (cf. 1stMud do_lock in act_move.c). [Verified: 03/07/2026]"""
    direction, exit_val, picked = _door_for_lock_cmd(player, args, "Lock", False)
    if exit_val is None:
        return
    if not exit_val.get("closed"):
        tprint("It's not closed.")
        return
    if exit_val.get("key") is None:
        tprint("It can't be locked.")
        return
    if not _has_key(player, exit_val["key"]):
        tprint("You lack the key.")
        return
    if exit_val.get("locked"):
        tprint("It's already locked.")
        return
    exit_val["locked"] = True
    tprint("*Click*")
    _set_rev_lock(player, direction, exit_val, True)
    return ("lock " + EXIT_NAMES[direction].lower()) if picked else None


def do_unlock(player, args):
    """Unlock a closed door with its key (cf. 1stMud do_unlock in act_move.c). [Verified: 03/07/2026]"""
    direction, exit_val, picked = _door_for_lock_cmd(player, args, "Unlock", True)
    if exit_val is None:
        return
    if not exit_val.get("closed"):
        tprint("It's not closed.")
        return
    if exit_val.get("key") is None:
        tprint("It can't be unlocked.")
        return
    if not _has_key(player, exit_val["key"]):
        tprint("You lack the key.")
        return
    if not exit_val.get("locked"):
        tprint("It's already unlocked.")
        return
    exit_val["locked"] = False
    tprint("*Click*")
    _set_rev_lock(player, direction, exit_val, False)
    return ("unlock " + EXIT_NAMES[direction].lower()) if picked else None


def do_pick(player, args):
    """Pick a door lock using the pick lock skill (cf. 1stMud do_pick in act_move.c).

    [Verified: 03/07/2026] -- target door resolved (with picker) before
    WaitState/close-stander/skill roll; 1stMud rolls before find_door.
    """
    direction, exit_val, picked = _door_for_lock_cmd(player, args, "Pick", True)
    if exit_val is None:
        return

    WaitState(player, SKILLS[GSN_PICK_LOCK]["beats"])

    # 1stMud: awake NPC more than 5 levels above ch blocks the attempt
    rs = world.rooms[player["room"]]
    for mob_id in rs["mobs"]:
        gch = world.chars[mob_id]
        if is_awake(gch) and player["level"] + 5 < gch["level"]:
            act("$N is standing too close to the lock.", player, None, gch, TO_CHAR)
            return

    if randint(1, 100) > get_skill(player, GSN_PICK_LOCK):
        tprint("You failed.")
        check_improve(player, GSN_PICK_LOCK, False, 2)
        return

    if not exit_val.get("closed"):
        tprint("It's not closed.")
        return
    if exit_val.get("key") is None:
        tprint("It can't be picked.")
        return
    if not exit_val.get("locked"):
        tprint("It's already unlocked.")
        return
    if exit_val.get("pickproof"):
        tprint("You failed.")
        return

    exit_val["locked"] = False
    tprint("*Click*")
    check_improve(player, GSN_PICK_LOCK, True, 2)
    _set_rev_lock(player, direction, exit_val, False)
    return ("pick " + EXIT_NAMES[direction].lower()) if picked else None


# -- Position commands ---------------------------------------------------------
# [PRIMESUD] ITEM_FURNITURE branches (stand/rest/sit/sleep at/on/in objects,
# count_users, ch->on) not ported in all five commands below -- few furniture
# items in current areas.  Revisit if furniture matters later.

def do_stand(player, args):
    """Stand up, waking first if asleep (cf. 1stMud do_stand in act_move.c). [Verified: 03/07/2026]

    Args:
        player (dict): Player state dict.
        args (list): Furniture keyword -- not ported, ignored [PRIMESUD].
    """
    pos = player.get("pos", "standing")
    if pos == "sleeping":
        if player.get("affected_by", {}).get("sleep"):
            chprintln(player, "You can't wake up!")
            return
        chprintln(player, "You wake and stand up.")
        act("$n wakes and stands up.", player, None, None, TO_ROOM)
        player["pos"] = "standing"
        do_look(player, [])
    elif pos in ("resting", "sitting"):
        chprintln(player, "You stand up.")
        act("$n stands up.", player, None, None, TO_ROOM)
        player["pos"] = "standing"
    elif pos == "standing":
        chprintln(player, "You are already standing.")
    elif pos == "fighting":
        chprintln(player, "You are already fighting!")


def do_rest(player, args):
    """Rest to speed regeneration (cf. 1stMud do_rest in act_move.c). [Verified: 03/07/2026]

    Args:
        player (dict): Player state dict.
        args (list): Furniture keyword -- not ported, ignored [PRIMESUD].
    """
    pos = player.get("pos", "standing")
    if pos == "fighting":
        chprintln(player, "You are already fighting!")
        return
    if pos == "sleeping":
        if player.get("affected_by", {}).get("sleep"):
            chprintln(player, "You can't wake up!")
            return
        chprintln(player, "You wake up and start resting.")
        act("$n wakes up and starts resting.", player, None, None, TO_ROOM)
        player["pos"] = "resting"
    elif pos == "resting":
        chprintln(player, "You are already resting.")
    elif pos == "standing":
        chprintln(player, "You rest.")
        act("$n sits down and rests.", player, None, None, TO_ROOM)
        player["pos"] = "resting"
    elif pos == "sitting":
        chprintln(player, "You rest.")
        act("$n rests.", player, None, None, TO_ROOM)
        player["pos"] = "resting"


def do_sit(player, args):
    """Sit down (cf. 1stMud do_sit in act_move.c). [Verified: 03/07/2026]

    Args:
        player (dict): Player state dict.
        args (list): Furniture keyword -- not ported, ignored [PRIMESUD].
    """
    pos = player.get("pos", "standing")
    if pos == "fighting":
        chprintln(player, "Maybe you should finish this fight first?")
        return
    if pos == "sleeping":
        if player.get("affected_by", {}).get("sleep"):
            chprintln(player, "You can't wake up!")
            return
        chprintln(player, "You wake and sit up.")
        act("$n wakes and sits up.", player, None, None, TO_ROOM)
        player["pos"] = "sitting"
    elif pos == "resting":
        chprintln(player, "You stop resting.")
        player["pos"] = "sitting"
    elif pos == "sitting":
        chprintln(player, "You are already sitting down.")
    elif pos == "standing":
        chprintln(player, "You sit down.")
        act("$n sits down on the ground.", player, None, None, TO_ROOM)
        player["pos"] = "sitting"


def do_sleep(player, args):
    """Go to sleep for maximum regeneration (cf. 1stMud do_sleep in act_move.c). [Verified: 03/07/2026]

    Args:
        player (dict): Player state dict.
        args (list): Furniture keyword -- not ported, ignored [PRIMESUD].
    """
    pos = player.get("pos", "standing")
    if pos == "sleeping":
        chprintln(player, "You are already sleeping.")
    elif pos in ("resting", "sitting", "standing"):
        chprintln(player, "You go to sleep.")
        act("$n goes to sleep.", player, None, None, TO_ROOM)
        player["pos"] = "sleeping"
    elif pos == "fighting":
        chprintln(player, "You are already fighting!")


def do_wake(player, args):
    """Wake yourself (stand) or a sleeping character (cf. 1stMud do_wake in act_move.c). [Verified: 03/07/2026]

    Args:
        player (dict): Player state dict.
        args (list): Optional target keyword; without it, acts as stand.
    """
    if not args:
        do_stand(player, [])
        return

    if not is_awake(player):
        chprintln(player, "You are asleep yourself!")
        return

    rs = world.rooms[player["room"]]
    victim_id = get_char_room(" ".join(args), rs["mobs"], world.chars, player)
    if victim_id is None:
        chprintln(player, "They aren't here.")
        return
    victim = world.chars[victim_id]

    if is_awake(victim):
        act("$N is already awake.", player, None, victim, TO_CHAR)
        return

    if victim.get("affected_by", {}).get("sleep"):
        act("You can't wake $M!", player, None, victim, TO_CHAR)
        return

    act("$n wakes you.", player, None, victim, TO_VICT)
    # 1stMud passes ch to do_stand here (apparent bug -- ROM 2.4 stands the
    # victim); [PRIMESUD] stand the victim so waking mobs actually works
    victim["pos"] = "standing"
    # ROM 2.4 victim do_stand side effect, so the waker sees it happen
    act("$n wakes and stands up.", victim, None, None, TO_ROOM)


# -- Stealth -------------------------------------------------------------------

def do_sneak(player, args):
    """Attempt to move silently via the sneak skill (cf. 1stMud do_sneak in act_move.c). [Verified: 03/07/2026]

    Args:
        player (dict): Player state dict.
        args (list): Parsed command arguments (unused).
    """
    tprint("You attempt to move silently.")
    affect_strip(player, GSN_SNEAK)

    if player.get("affected_by", {}).get("sneak"):
        return

    if randint(1, 100) < get_skill(player, GSN_SNEAK):
        check_improve(player, GSN_SNEAK, True, 3)
        affect_to_char(player, {
            "where":     "to_affects",
            "type":      GSN_SNEAK,
            "level":     player["level"],
            "duration":  player["level"],
            "location":  "none",
            "modifier":  0,
            "bitvector": "sneak",
        })
    else:
        check_improve(player, GSN_SNEAK, False, 3)


def do_hide(player, args):
    """Attempt to hide via the hide skill (cf. 1stMud do_hide in act_move.c). [Verified: 03/07/2026]

    Hide is a bare AFF bit with no affect entry; any command except
    stealth/info commands removes it (see interpret in commands.py).

    Args:
        player (dict): Player state dict.
        args (list): Parsed command arguments (unused).
    """
    tprint("You attempt to hide.")

    aff = player.setdefault("affected_by", {})
    aff.pop("hide", None)

    if randint(1, 100) < get_skill(player, GSN_HIDE):
        aff["hide"] = True
        check_improve(player, GSN_HIDE, True, 3)
    else:
        check_improve(player, GSN_HIDE, False, 3)


def do_visible(player, args):
    """Strip invisibility, sneak, and hide (cf. 1stMud do_visible in act_move.c). [Verified: 03/07/2026]

    Args:
        player (dict): Player state dict.
        args (list): Parsed command arguments (unused).
    """
    affect_strip(player, GSN_INVIS)
    affect_strip(player, GSN_MASS_INVIS)
    affect_strip(player, GSN_SNEAK)
    aff = player.get("affected_by", {})
    aff.pop("hide", None)
    aff.pop("invisible", None)
    aff.pop("sneak", None)
    tprint("Ok.")


def perform_recall(player, location, what="recall"):
    """Move player to recall destination (cf. 1stMud perform_recall in act_move.c).

    Only-players / arena checks and the "$n prays for transportation!" /
    "$n disappears." / "$n appears in the room." room acts are not ported
    (single-player, no arena). [PRIMESUD]

    [Verified: 03/07/2026]
    """
    room = ROOM_DEFS[player["room"]]

    if location is None:
        tprint("You are completely lost.")
        return False

    if player["room"] == location:
        return True

    if room.get("flags", {}).get("no_recall") \
            or player.get("affected_by", {}).get("curse"):
        # 1stMud: act "$g has forsaken you." ($g = deity name; no deities here)
        tprint("Your deity has forsaken you.")
        return False

    if player["fighting"] is not None:
        skill = get_skill(player, GSN_RECALL)
        if randint(1, 100) < 80 * skill // 100:
            check_improve(player, GSN_RECALL, False, 6)
            WaitState(player, PULSE_PER_SECOND)
            tprint("You failed!")  # [PRIMESUD] 1stMud typo "You failed!."
            return False
        player["xp"] = max(0, player["xp"] - 25)
        check_improve(player, GSN_RECALL, True, 4)
        tprint("You " + what + " from combat!  You lose 25 exps.")
        stop_fighting(player, both=True)

    player["move"] = player.get("move", 0) // 2
    from_vnum = player["room"]
    player["room"] = location

    # cf. 1stMud do_recall: pet recalls with its master
    pet = world.chars.get(player.get("pet")) if player.get("pet") is not None else None
    if (pet is not None and pet.get("room") == from_vnum
            and from_vnum in world.rooms and location in world.rooms):
        if pet["id"] in world.rooms[from_vnum]["mobs"]:
            world.rooms[from_vnum]["mobs"].remove(pet["id"])
        pet["room"] = location
        world.rooms[location]["mobs"].append(pet["id"])

    do_look(player, [])
    return True


def do_recall(player, args):
    """Teleport to the area's recall room (cf. 1stMud perform_recall in act_move.c).

    Per-area recall VNUMs (area->recall in 1stMud) are not yet implemented;
    all areas fall back to R_RECALL (ROOM_VNUM_TEMPLE).  Pet recall is
    handled in perform_recall.

    [Verified: 03/07/2026]
    """
    location = R_RECALL
    perform_recall(player, location, "recall")


_RUN_DIRS = frozenset(("n", "e", "s", "w", "u", "d"))


def _parse_run_buf(buf):
    """Parse a speedwalk string into a list of (action, direction) tuples.

    Format matches 1stMud run_buf: digits are repeat counts, direction
    chars (n/e/s/w/u/d) are steps, 'o' prefix means open door before
    moving (cf. 1stMud read_from_buffer in comm.c).

    Returns:
        list: [(action, dir), ...] where action is "move" or "open".
              None on parse error.
    """
    steps = []
    i = 0
    while i < len(buf):
        count = 0
        while i < len(buf) and buf[i].isdigit():
            count = count * 10 + int(buf[i])
            i += 1
        if i >= len(buf):
            break
        ch = buf[i]
        i += 1
        if ch == "o":
            if i >= len(buf) or buf[i] not in _RUN_DIRS:
                return None
            steps.append(("open", buf[i]))
            i += 1
        elif ch in _RUN_DIRS:
            if count < 1:
                count = 1
            for _ in range(count):
                steps.append(("move", ch))
        else:
            return None
    return steps


def _brief_room_line(player):
    """One-line room summary for speedwalk intermediate steps. [PRIMESUD]"""
    room = ROOM_DEFS[player["room"]]
    exits = " ".join(
        EXIT_NAMES.get(d, d) for d in EXIT_ORDER
        if d in room.get("exits", {})
        and not (isinstance(room["exits"][d], dict)
                 and room["exits"][d].get("closed"))
    )
    exit_str = "[" + exits + "]" if exits else "[none]"
    tprint("{Y" + room["name"] + "{x {g" + exit_str + "{x")


def free_runbuf(player):
    """Clear player's run buffer (cf. 1stMud free_runbuf in comm.c)."""
    player.pop("run_buf", None)


_DIR_CMDS = {
    "n": do_north, "e": do_east, "s": do_south,
    "w": do_west, "u": do_up, "d": do_down,
}


def run_buf_step(player):
    """Consume one step from player's run_buf (cf. 1stMud read_from_buffer in comm.c).

    Called once per pulse from game_loop when wait==0. Delegates move
    steps to direction commands (do_north etc.) for SSOT -- any future
    mechanics added there apply during runs too. Blocked-movement
    cancellation handled by direction commands via free_runbuf
    (cf. 1stMud do_north in act_move.c). Brief vs full room display
    handled by move_char checking run_buf state.

    Returns:
        bool: True if a step was consumed.
    """
    run_buf = player.get("run_buf")
    if not run_buf:
        return False

    # Combat cancels run (cf. 1stMud read_from_buffer POS_FIGHTING check).
    # [PRIMESUD] 1stMud cancels silently; we notify the player.
    if player.get("fighting") is not None:
        chprintln(player, "You stop running -- you are fighting!")
        free_runbuf(player)
        return False

    action, d = run_buf.pop(0)

    if action == "open":
        do_open(player, [EXIT_NAMES[d]])
    else:
        _DIR_CMDS[d](player, [])

    if not player.get("run_buf"):
        free_runbuf(player)

    return True


def do_run(player, args):
    """Parse speedwalk and store in run_buf for tick-based execution
    (cf. 1stMud do_run in act_move.c).

    With args: parse speedwalk string (e.g. '3s2en', 'son2e').
    Without args: [PRIMESUD] present picker of reachable areas from BFS
    pathfinding, then store selected path.

    Steps are consumed one-per-pulse by run_buf_step() in game_loop
    (cf. 1stMud read_from_buffer consuming run_buf in comm.c).
    move_char WaitState(1) means each move takes two pulses (one to
    move, one recovery). Movement-point cost applies per step so the
    player can exhaust mid-run.

    Intermediate rooms show brief one-liners. [PRIMESUD] Final
    destination gets full do_look. Combat or blocked movement cancels
    the run (cf. 1stMud free_runbuf). Keyboard input (Enter) also
    cancels. [PRIMESUD]

    Args:
        player (dict): Player state dict.
        args (list): Parsed command arguments (speedwalk string tokens).
    """
    # [PRIMESUD] 1stMud overwrites run_buf; we guard instead.
    if player.get("run_buf"):
        chprintln(player, "You are already running!")
        return

    if not args:
        # [PRIMESUD] No-args picker: show reachable areas
        # (1stMud prints "You run in place!" on no args)
        tprint("{YLoading all area paths...{x")
        paths = find_area_paths(player)
        source_area = ROOM_DEFS.get(player.get("room"), {}).get("area")
        sorted_areas = sorted(world.AREA_DEFS,
                              key=lambda a: a.get("name", "").lower())
        candidates = []
        for area in sorted_areas:
            tag = area["tag"]
            if tag == source_area:
                continue
            path = paths.get(tag)
            if not path:
                continue
            candidates.append((area.get("name", tag), path))
        if not candidates:
            chprintln(player, "No accessible areas from here.")
            return
        labels = [str(c[0]) + " {D(" + c[1] + "){x" for c in candidates]
        idx = pick_from("Run to which area?", labels)
        if idx < 0:
            return
        buf = candidates[idx][1]
    else:
        buf = "".join(args)

    # Validate (cf. 1stMud do_run validation in act_move.c)
    has_dir = False
    for ch in buf:
        if ch in _RUN_DIRS:
            has_dir = True
        elif ch != "o" and not ch.isdigit():
            chprintln(player, "Invalid direction!")
            return
    if not has_dir:
        chprintln(player, "No directions specified!")
        return

    steps = _parse_run_buf(buf)
    if steps is None:
        chprintln(player, "Invalid direction!")
        return

    player["run_buf"] = steps
    chprintln(player, "You start running...")
