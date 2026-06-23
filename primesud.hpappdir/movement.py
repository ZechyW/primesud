"""Movement, doors, recall, and flee command handlers."""

from config import R_RECALL
from skills_table import GSN_RECALL
from world import ROOMS
from picker import pick_from
from combat import stop_fighting, WaitState, check_improve
from info import do_look
from config import EXIT_ORDER, EXIT_NAMES, REV_DIR, DIR_ALIASES

from urandom import randint


def _exit_to(exit_val):
    """Return destination vnum from a plain-vnum or dict exit."""
    return exit_val["to"] if isinstance(exit_val, dict) else exit_val


def do_move(tr, player, direction, world):
    if player["fighting"] is not None:
        tr.print("No way! You are fighting!")
        return
    exits = ROOMS[player["room"]]["exits"]
    if direction not in exits:
        tr.print("Alas, you cannot go that way.")
        return
    exit_val = exits[direction]
    if isinstance(exit_val, dict) and exit_val.get("closed"):
        tr.print("The door is closed.")
        return
    dest = _exit_to(exit_val)
    if dest not in ROOMS:
        tr.print("That way is not yet open.")
        return
    player["room"] = dest
    do_look(tr, player, [], world)


def do_open(tr, player, args, world):
    """Open a door in a given direction (cf. 1stMud do_open in act_move.c)."""
    exits = ROOMS[player["room"]]["exits"]
    _picked_dir = None
    if args:
        direction = DIR_ALIASES.get(args[0].lower())
        if direction is None:
            tr.print("Open what?")
            return
    else:
        candidates = [d for d in EXIT_ORDER
                      if isinstance(exits.get(d), dict)
                      and exits[d].get("isdoor") and exits[d].get("closed")]
        if not candidates:
            tr.print("There are no doors to open here.")
            return
        idx = pick_from(tr, "Open which door?",
                        [EXIT_NAMES[d] for d in candidates])
        if idx < 0:
            return
        direction = candidates[idx]
        _picked_dir = direction
    exit_val = exits.get(direction)
    if not isinstance(exit_val, dict) or not exit_val.get("isdoor"):
        tr.print("You can't do that.")
        return
    if not exit_val.get("closed"):
        tr.print("It's already open.")
        return
    if exit_val.get("locked"):
        tr.print("It's locked.")
        return
    exit_val["closed"] = False
    tr.print("Ok.")
    dest = exit_val["to"]
    rev = REV_DIR.get(direction)
    if rev and dest in ROOMS:
        rev_exit = ROOMS[dest]["exits"].get(rev)
        if isinstance(rev_exit, dict) and _exit_to(rev_exit) == player["room"]:
            rev_exit["closed"] = False
    return ("open " + EXIT_NAMES[_picked_dir].lower()) if _picked_dir is not None else None


def do_close(tr, player, args, world):
    """Close a door in a given direction (cf. 1stMud do_close in act_move.c)."""
    exits = ROOMS[player["room"]]["exits"]
    _picked_dir = None
    if args:
        direction = DIR_ALIASES.get(args[0].lower())
        if direction is None:
            tr.print("Close what?")
            return
    else:
        candidates = [d for d in EXIT_ORDER
                      if isinstance(exits.get(d), dict)
                      and exits[d].get("isdoor") and not exits[d].get("closed")]
        if not candidates:
            tr.print("There are no open doors to close here.")
            return
        idx = pick_from(tr, "Close which door?",
                        [EXIT_NAMES[d] for d in candidates])
        if idx < 0:
            return
        direction = candidates[idx]
        _picked_dir = direction
    exit_val = exits.get(direction)
    if not isinstance(exit_val, dict) or not exit_val.get("isdoor"):
        tr.print("You can't do that.")
        return
    if exit_val.get("closed"):
        tr.print("It's already closed.")
        return
    if exit_val.get("noclose"):
        tr.print("You can't do that.")
        return
    exit_val["closed"] = True
    tr.print("Ok.")
    dest = exit_val["to"]
    rev = REV_DIR.get(direction)
    if rev and dest in ROOMS:
        rev_exit = ROOMS[dest]["exits"].get(rev)
        if isinstance(rev_exit, dict) and _exit_to(rev_exit) == player["room"]:
            rev_exit["closed"] = True
    return ("close " + EXIT_NAMES[_picked_dir].lower()) if _picked_dir is not None else None


def perform_recall(tr, player, location, world, what="recall"):
    """Move player to recall destination (cf. 1stMud perform_recall in act_move.c)."""
    room = ROOMS[player["room"]]

    if room.get("flags", {}).get("no_recall") \
            or player.get("aff_flags", {}).get("curse"):
        tr.print("Your deity has forsaken you.")
        return False

    if location is None:
        tr.print("You are completely lost.")
        return False

    if player["room"] == location:
        return True

    if player["fighting"] is not None:
        skill = player["learned"].get(GSN_RECALL, 50)
        if randint(1, 100) < 80 * skill // 100:
            check_improve(tr, player, GSN_RECALL, False, 6)
            WaitState(player, 4)
            tr.print("You failed!.")
            return False
        player["xp"] = max(0, player["xp"] - 25)
        check_improve(tr, player, GSN_RECALL, True, 4)
        tr.print("You " + what + " from combat!  You lose 25 exps.")
        stop_fighting(player, world["chars"], both=False)

    player["room"] = location
    do_look(tr, player, [], world)
    return True


def do_recall(tr, player, args, world):
    """Teleport to the area's recall room (cf. 1stMud perform_recall in act_move.c).

    Per-area recall VNUMs (area->recall in 1stMud) are not yet implemented;
    all areas fall back to R_RECALL (ROOM_VNUM_TEMPLE).  When a pet system is
    added, pet teleport should mirror the player teleport here.
    """
    location = R_RECALL
    perform_recall(tr, player, location, world, "recall")


def do_flee(tr, player, args, world):
    if player["fighting"] is None:
        tr.print("You're not fighting anyone.")
        return
    exits = list(ROOMS[player["room"]]["exits"].items())
    if not exits:
        tr.print("There is nowhere to run!")
        return
    # Try exits in random order (up to 6 attempts, cf. 1stMud)
    attempts = list(range(len(exits)))
    for _ in range(min(6, len(exits))):
        idx = randint(0, len(attempts) - 1)
        direction, exit_val = exits[attempts.pop(idx)]
        if isinstance(exit_val, dict) and exit_val.get("closed"):
            continue
        dest = _exit_to(exit_val)
        if dest not in ROOMS:
            continue
        player["room"] = dest
        stop_fighting(player, world["chars"], both=False)
        tr.print("You flee {}!".format(direction))
        player["xp"] = max(0, player["xp"] - 10)
        tr.print("You lost 10 exp.")
        do_look(tr, player, [], world)
        return
    tr.print("There is nowhere to run!")
