"""Hunt skill: locate a mob in the current area (cf. 1stMud hunt.c)."""

from config import EXIT_ORDER, EXIT_NAMES
from handler import (act, chprintln, TO_CHAR, TO_ROOM, get_char_room,
                     number_argument, can_see, is_name)
from skill_utils import WaitState, check_improve, get_skill
from skills_table import GSN_HUNT, SKILLS
from urandom import randint
import world
from world import ROOM_DEFS, MOB_DEFS


def _exit_to(exit_val):
    """Return destination vnum from a plain-vnum or dict exit."""
    return exit_val["to"] if isinstance(exit_val, dict) else exit_val


def get_char_area(ch, argument):
    """Find a visible mob in ch's area by name (cf. 1stMud get_char_area in hunt.c).

    Checks ch's room first, then every mob in the same area, with
    '2.guard' counted syntax. [PRIMESUD] Only NPCs: no other PCs exist.

    Returns:
        dict or None: Matching mob instance.
    """
    rs = world.rooms[ch["room"]]
    vid = get_char_room(argument, rs["mobs"], world.chars, viewer=ch)
    if vid is not None:
        return world.chars[vid]
    number, arg = number_argument(argument)
    area = ROOM_DEFS[ch["room"]].get("area")
    count = 0
    for _c in world.chars.values():
        if not _c.get("is_npc"):
            continue
        # ._data: mobs of this area are loaded; anything else can't match
        if ROOM_DEFS._data.get(_c.get("room"), {}).get("area") != area:
            continue
        if not can_see(ch, _c):
            continue
        if not is_name(arg, MOB_DEFS.get(_c.get("tpl"), {}).get("keywords", "")):
            continue
        count += 1
        if count == number:
            return _c
    return None


def find_path(in_vnum, out_vnum, area_only=True):
    """First-step direction of the shortest path between two rooms
    (cf. 1stMud find_path in hunt.c).

    BFS through all exits including closed doors (1stMud thru_doors /
    GO_OK_SMARTER: hunt always passes depth -40000). Expansion is limited
    to the start room's area when area_only is set (1stMud in_zone).

    Args:
        in_vnum (int): Start room vnum.
        out_vnum (int): Target room vnum.
        area_only (bool): Restrict the search to the start area.

    Returns:
        str or None: Exit letter ("n", "e", ...) of the first step, or
        None if no path was found.
    """
    start_area = ROOM_DEFS.get(in_vnum, {}).get("area")
    visited = {in_vnum}
    queue = [(in_vnum, None)]  # (room vnum, first-step direction)
    qi = 0
    while qi < len(queue):
        vnum, first = queue[qi]
        qi += 1
        # ._data: never force-load a neighbouring area during BFS
        room = ROOM_DEFS._data.get(vnum)
        if room is None:
            continue
        if area_only and room.get("area") != start_area:
            continue
        for d in EXIT_ORDER:
            ev = room.get("exits", {}).get(d)
            if ev is None:
                continue
            to = _exit_to(ev)
            if to == out_vnum:
                return first if first is not None else d
            if to not in visited:
                visited.add(to)
                queue.append((to, first if first is not None else d))
    return None


def do_hunt(player, args):
    """Track down a mob in the current area (cf. 1stMud do_hunt in hunt.c).
    [Verified: 04/07/2026] -- mortal branch only: fArea is always true
    (no immortals), so the search and pathfinding stay in-area. NPC
    hunters (hunt_victim) not ported -- see TODO in combat.py.

    Args:
        player (dict): Player state dict.
        args (list): Victim name arguments.
    """
    if get_skill(player, GSN_HUNT) == 0:
        chprintln(player, "You don't know how to hunt.")
        return
    if not args:
        chprintln(player, "Whom are you trying to hunt?")
        return

    victim = get_char_area(player, " ".join(args))
    if victim is None:
        chprintln(player, "No-one around by that name.")
        return
    if player["room"] == victim["room"]:
        act("$N is here!", player, None, victim, TO_CHAR)
        return

    if player["move"] > 2:
        player["move"] -= 3
    else:
        chprintln(player, "You're too exhausted to hunt anyone!")
        return

    act("$n carefully sniffs the air.", player, None, None, TO_ROOM)
    WaitState(player, SKILLS[GSN_HUNT]["beats"])
    direction = find_path(player["room"], victim["room"])
    if direction is None:
        act("You couldn't find a path to $N from here.", player, None,
            victim, TO_CHAR)
        return
    # 1stMud's direction range guard ("Hmm... Something seems to be
    # wrong.") is unreachable here: find_path returns a valid letter.

    # Failed skill roll points a random (existing) direction instead
    if randint(1, 100) > get_skill(player, GSN_HUNT):
        exits = [d for d in EXIT_ORDER
                 if player_room_exit(player, d) is not None]
        if exits:  # [PRIMESUD] exitless room would hang 1stMud's loop
            direction = exits[randint(0, len(exits) - 1)]

    act("$N is " + EXIT_NAMES[direction] + " from here.", player, None,
        victim, TO_CHAR)
    check_improve(player, GSN_HUNT, True, 1)


def player_room_exit(player, d):
    """Return the exit value of player's room in direction d, or None. [PRIMESUD]"""
    return ROOM_DEFS[player["room"]].get("exits", {}).get(d)
