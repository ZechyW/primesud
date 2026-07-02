"""Movement, doors, and recall command handlers."""

from classes import is_class
from handler import can_see_room, chprintln
from combat import stop_fighting
from skill_utils import WaitState, check_improve
from config import (EXIT_ORDER, EXIT_NAMES, REV_DIR, DIR_ALIASES,
                    MOVEMENT_LOSS,
                    SECT_AIR, SECT_WATER_NOSWIM,
                    R_RECALL, PULSE_PER_SECOND)
from info import do_look, find_area_paths
from picker import pick_from
from skills_table import GSN_RECALL
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


def move_char(player, direction):
    """Move player through an exit (cf. 1stMud move_char in act_move.c).

    Checks: exit existence, visibility, closed doors (with pass_door /
    nopass), charm anchor, sector restrictions (air, water),
    movement-point cost, and haste/slow modifiers.

    Position gate handled by command table (do_north etc. have
    min_pos = "standing").

    Args:
        player (dict): Player state dict.
        direction (str): Single-char direction key (n/e/s/w/u/d).
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

    # -- Private room / area closed checks not ported --

    if not player.get("is_npc", False):
        # -- Guild room (cf. 1stMud act_move.c: to_room->guild + is_class) --
        # "guild" tuple patched onto rooms by patch_1stmud_deltas.py;
        # Paladin/Ranger share the Cleric/Warrior guilds (CLASS_PLAN.md).
        allowed = to_room.get("guild")
        if allowed is not None:
            member = False
            for cl in allowed:
                if is_class(player, cl):
                    member = True
                    break
            if not member:
                chprintln(player, "You aren't allowed in there.")
                return

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
    # [PRIMESUD] During speedwalk, intermediate rooms get brief one-liners.
    run_buf = player.get("run_buf")
    if run_buf and any(a == "move" for a, _ in run_buf):
        _brief_room_line(player)
    else:
        do_look(player, [])


# -- Direction command handlers (cf. 1stMud do_north..do_down in act_move.c) --
# Each registered in command table with min_pos = "standing".
# was_room check cancels run_buf on blocked movement (cf. 1stMud free_runbuf).

def do_north(player, args):
    """Walk north (cf. 1stMud do_north in act_move.c)."""
    was_room = player["room"]
    move_char(player, "n")
    if was_room == player["room"]:
        free_runbuf(player)


def do_east(player, args):
    """Walk east (cf. 1stMud do_east in act_move.c)."""
    was_room = player["room"]
    move_char(player, "e")
    if was_room == player["room"]:
        free_runbuf(player)


def do_south(player, args):
    """Walk south (cf. 1stMud do_south in act_move.c)."""
    was_room = player["room"]
    move_char(player, "s")
    if was_room == player["room"]:
        free_runbuf(player)


def do_west(player, args):
    """Walk west (cf. 1stMud do_west in act_move.c)."""
    was_room = player["room"]
    move_char(player, "w")
    if was_room == player["room"]:
        free_runbuf(player)


def do_up(player, args):
    """Walk up (cf. 1stMud do_up in act_move.c)."""
    was_room = player["room"]
    move_char(player, "u")
    if was_room == player["room"]:
        free_runbuf(player)


def do_down(player, args):
    """Walk down (cf. 1stMud do_down in act_move.c)."""
    was_room = player["room"]
    move_char(player, "d")
    if was_room == player["room"]:
        free_runbuf(player)


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
        tprint("{YLoading area paths...{x")
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
