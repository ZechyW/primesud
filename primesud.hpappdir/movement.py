"""Movement, doors, and recall command handlers."""

from combat import stop_fighting, WaitState, check_improve
from config import EXIT_ORDER, EXIT_NAMES, REV_DIR, DIR_ALIASES
from config import R_RECALL, PULSE_PER_SECOND
from info import do_look
from picker import pick_from
from skills_table import GSN_RECALL
from terminal import tprint
from urandom import randint
from world import ROOM_DEFS


def _exit_to(exit_val):
    """Return destination vnum from a plain-vnum or dict exit."""
    return exit_val["to"] if isinstance(exit_val, dict) else exit_val


def do_move(player, direction):
    if player["fighting"] is not None:
        tprint("No way! You are fighting!")
        return
    exits = ROOM_DEFS[player["room"]]["exits"]
    if direction not in exits:
        tprint("Alas, you cannot go that way.")
        return
    exit_val = exits[direction]
    if isinstance(exit_val, dict) and exit_val.get("closed"):
        tprint("The door is closed.")
        return
    dest = _exit_to(exit_val)
    if dest not in ROOM_DEFS:
        tprint("That way is not yet open.")
        return
    player["room"] = dest
    do_look(player, [])


def do_open(player, args):
    """Open a door in a given direction (cf. 1stMud do_open in act_move.c)."""
    exits = ROOM_DEFS[player["room"]]["exits"]
    _picked_dir = None
    if args:
        direction = DIR_ALIASES.get(args[0].lower())
        if direction is None:
            tprint("Open what?")
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
    exit_val = exits.get(direction)
    if not isinstance(exit_val, dict) or not exit_val.get("isdoor"):
        tprint("You can't do that.")
        return
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
    """Close a door in a given direction (cf. 1stMud do_close in act_move.c)."""
    exits = ROOM_DEFS[player["room"]]["exits"]
    _picked_dir = None
    if args:
        direction = DIR_ALIASES.get(args[0].lower())
        if direction is None:
            tprint("Close what?")
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
    exit_val = exits.get(direction)
    if not isinstance(exit_val, dict) or not exit_val.get("isdoor"):
        tprint("You can't do that.")
        return
    if exit_val.get("closed"):
        tprint("It's already closed.")
        return
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


def perform_recall(player, location, what="recall"):
    """Move player to recall destination (cf. 1stMud perform_recall in act_move.c)."""
    room = ROOM_DEFS[player["room"]]

    if room.get("flags", {}).get("no_recall") \
            or player.get("affected_by", {}).get("curse"):
        tprint("Your deity has forsaken you.")
        return False

    if location is None:
        tprint("You are completely lost.")
        return False

    if player["room"] == location:
        return True

    if player["fighting"] is not None:
        skill = player["learned"].get(GSN_RECALL, 50)
        if randint(1, 100) < 80 * skill // 100:
            check_improve(player, GSN_RECALL, False, 6)
            WaitState(player, PULSE_PER_SECOND)
            tprint("You failed!")
            return False
        player["xp"] = max(0, player["xp"] - 25)
        check_improve(player, GSN_RECALL, True, 4)
        tprint("You " + what + " from combat!  You lose 25 exps.")
        stop_fighting(player, both=True)

    player["room"] = location
    do_look(player, [])
    return True


def do_recall(player, args):
    """Teleport to the area's recall room (cf. 1stMud perform_recall in act_move.c).

    Per-area recall VNUMs (area->recall in 1stMud) are not yet implemented;
    all areas fall back to R_RECALL (ROOM_VNUM_TEMPLE).  When a pet system is
    added, pet teleport should mirror the player teleport here.
    """
    location = R_RECALL
    perform_recall(player, location, "recall")


