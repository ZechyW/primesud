from world import ROOMS, GSN_RECALL, R_RECALL
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


def do_close(tr, player, args, world):
    """Close a door in a given direction (cf. 1stMud do_close in act_move.c)."""
    exits = ROOMS[player["room"]]["exits"]
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


def do_recall(tr, player, args, world):
    """Teleport to the area's recall room (cf. 1stMud perform_recall in act_move.c).

    Per-area recall VNUMs (area->recall in 1stMud) are not yet implemented;
    all areas fall back to R_RECALL (ROOM_VNUM_TEMPLE).  When a pet system is
    added, pet teleport should mirror the player teleport here.
    """
    room = ROOMS[player["room"]]

    if room.get("flags", {}).get("no_recall") \
            or player.get("affects", {}).get("curse"):
        tr.print("Your deity has forsaken you.")
        return

    location = R_RECALL
    if player["room"] == location:
        return

    if player["fighting"] is not None:
        skill = player["learned"].get(GSN_RECALL, 50)
        if randint(1, 100) < 80 * skill // 100:
            check_improve(tr, player, GSN_RECALL, False, 6)
            WaitState(player, 4)
            tr.print("You failed!.")
            return
        player["xp"] = max(0, player["xp"] - 25)
        check_improve(tr, player, GSN_RECALL, True, 4)
        tr.print("You recall from combat!  You lose 25 exps.")
        stop_fighting(player, world["mobs"])

    player["room"] = location
    do_look(tr, player, [], world)
