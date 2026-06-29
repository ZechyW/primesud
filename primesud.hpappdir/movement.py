"""Movement, doors, and recall command handlers."""

from handler import can_see_room, chprintln
from combat import stop_fighting
from skill_utils import WaitState, check_improve
from config import (EXIT_ORDER, EXIT_NAMES, REV_DIR, DIR_ALIASES,
                    MOVEMENT_LOSS,
                    SECT_AIR, SECT_WATER_NOSWIM,
                    R_RECALL, PULSE_PER_SECOND)
from info import do_look
from picker import pick_from
from skills_table import GSN_RECALL
from terminal import tprint
from urandom import randint
from world import ROOM_DEFS


def _exit_to(exit_val):
    """Return destination vnum from a plain-vnum or dict exit."""
    return exit_val["to"] if isinstance(exit_val, dict) else exit_val


def _has_boat(ch):
    """Return True if ch carries a boat item (cf. 1stMud ITEM_BOAT check in move_char)."""
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


def move_char(player, direction):
    """Move player through an exit (cf. 1stMud move_char in act_move.c).

    Checks: exit existence, visibility, closed doors (with pass_door /
    nopass), charm anchor, sector restrictions (air, water),
    movement-point cost, and haste/slow modifiers.

    Position gate handled by command table (do_north etc. have
    min_pos = "standing").
    """
    # -- p_exit_trigger (mob/obj/room progs) not ported --

    in_room = ROOM_DEFS[player["room"]]
    exits = in_room.get("exits", {})

    if direction not in exits:
        chprintln(player, "Alas, you cannot go that way.")
        return

    exit_val = exits[direction]
    dest = _exit_to(exit_val)
    if dest not in ROOM_DEFS:
        chprintln(player, "Alas, you cannot go that way.")
        return
    to_room = ROOM_DEFS[dest]

    if not can_see_room(player, dest):
        chprintln(player, "Alas, you cannot go that way.")
        return

    aff = player.get("affected_by", {})

    # -- Closed door (with pass_door / nopass) --
    is_exit_dict = isinstance(exit_val, dict)
    if is_exit_dict and exit_val.get("closed"):
        if not aff.get("pass_door") or exit_val.get("nopass"):
            keyword = exit_val.get("keyword", EXIT_NAMES.get(direction, "door"))
            chprintln(player, "The " + keyword + " is closed.")
            return

    # -- Charm anchor (cf. 1stMud AFF_CHARM && master in same room) --
    if aff.get("charm") and player.get("master") is not None:
        # master/follower system not ported; stub for fidelity
        chprintln(player, "What?  And leave your beloved master?")
        return

    # -- Private room / area closed / guild room checks not ported --

    if not player.get("is_npc", False):
        # -- Sector: air --
        in_sect = in_room.get("sector", "inside")
        to_sect = to_room.get("sector", "inside")
        if in_sect == SECT_AIR or to_sect == SECT_AIR:
            if not aff.get("flying"):
                chprintln(player, "You can't fly.")
                return

        # -- Sector: deep water (need boat or flying) --
        if (in_sect == SECT_WATER_NOSWIM or to_sect == SECT_WATER_NOSWIM) \
                and not aff.get("flying"):
            found = _has_boat(player)
            if not found:
                chprintln(player, "You need a boat to go there.")
                return

        # -- Movement point cost --
        move_cost = (MOVEMENT_LOSS.get(in_sect, 1)
                     + MOVEMENT_LOSS.get(to_sect, 1)) // 2
        if aff.get("flying") or aff.get("haste"):
            move_cost //= 2
        if aff.get("slow"):
            move_cost *= 2
        if player.get("move", 0) < move_cost:
            chprintln(player, "You are too exhausted.")
            return

        WaitState(player, 1)
        player["move"] = player.get("move", 0) - move_cost

    # -- Stance reset (stance system not ported) --
    # if ValidStance(GetStance(ch, STANCE_CURRENT)): do_stance(ch, "")

    # -- Leave message (1stMud: act("$n leaves $T.", ch, NULL, dir_name[door], TO_ROOM))
    # Single-player: no other chars in room to notify; skip.

    player["room"] = dest

    # -- Arrive message (single-player: skip) --

    # 1stMud: do_function(ch, &do_look, "auto") -- "auto" triggers brief mode;
    # PrimeSUD has no brief mode, so empty args shows full room.
    do_look(player, [])


# -- Direction command handlers (cf. 1stMud do_north..do_down in act_move.c) --
# Each registered in command table with min_pos = "standing".
# 1stMud also tracks was_room for run-buffer; not applicable to PrimeSUD.

def do_north(player, args):
    """Walk north (cf. 1stMud do_north in act_move.c)."""
    move_char(player, "n")


def do_east(player, args):
    """Walk east (cf. 1stMud do_east in act_move.c)."""
    move_char(player, "e")


def do_south(player, args):
    """Walk south (cf. 1stMud do_south in act_move.c)."""
    move_char(player, "s")


def do_west(player, args):
    """Walk west (cf. 1stMud do_west in act_move.c)."""
    move_char(player, "w")


def do_up(player, args):
    """Walk up (cf. 1stMud do_up in act_move.c)."""
    move_char(player, "u")


def do_down(player, args):
    """Walk down (cf. 1stMud do_down in act_move.c)."""
    move_char(player, "d")


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

    player["move"] = player.get("move", 0) // 2
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


