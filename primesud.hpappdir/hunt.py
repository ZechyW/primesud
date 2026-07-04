"""Hunt skill: locate a mob in the current area (cf. 1stMud hunt.c)."""

from config import EXIT_ORDER, EXIT_NAMES
from handler import (act, chprintln, TO_CHAR, TO_ROOM, TO_VICT, TO_NOTVICT,
                     get_char_room, number_argument, can_see, is_name)
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
    hunters use hunt_victim (ported as dormant [PRIMESUD] scaffolding --
    nothing in-game sets ch["hunting"] yet; see hunt_victim docstring).

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


def hunt_victim(ch):
    """NPC pursuit AI: chase down ch's hunting target (cf. 1stMud hunt_victim in hunt.c).
    [Verified: 04/07/2026] -- dormant scaffolding (see [PRIMESUD] note below).

    [PRIMESUD] Dormant scaffolding: nothing in 1stMud ever sets ch->hunting
    during play (only the imm `set` command does), so this mechanism has no
    in-game trigger yet. Ported faithfully so a future [PRIMESUD] trigger
    can flip ch["hunting"] and have it picked up automatically --
    violence_update (combat.py) and mobile_update (mob.py) already call
    this whenever "hunting" is set.

    Args:
        ch (dict): NPC instance state dict, or None.
    """
    if ch is None or ch.get("hunting") is None or not ch.get("is_npc"):
        return

    # 1stMud scans char_first for ch->hunting; our chars dict membership
    # is equivalent (get() returns None if the id is stale/gone).
    victim = world.chars.get(ch["hunting"])
    if victim is None or not can_see(ch, victim):
        from comm import do_say
        # do_say(ch, args) rejoins args with " ".join -- splitting on the
        # literal separator " " (not whitespace-collapsing .split()) round
        # trips exactly, preserving the double space in "Damn!  My" that
        # hunt.c's literal C string has.
        do_say(ch, "Damn!  My prey is gone!!".split(" "))
        ch["hunting"] = None
        return

    if ch["room"] == victim["room"]:
        if randint(1, 100) < 60:
            act("{g$n{g glares at $N{g and says, '{GYe shall DIE!{g'{x",
                ch, None, victim, TO_NOTVICT)
            act("{g$n{g glares at you and says, '{GYe shall DIE!{g'{x",
                ch, None, victim, TO_VICT)
            act("{gYou glare at $N{g and say, '{GYe shall DIE!{g'{x",
                ch, None, victim, TO_CHAR)
        else:
            act("{g$n{g glares at $N{g and says, '{GHey, I remember you!{g'{x",
                ch, None, victim, TO_NOTVICT)
            act("{g$n{g glares at you and says, '{GHey, I remember you!{g'{x",
                ch, None, victim, TO_VICT)
            act("{gYou glare at $N{g and say, '{GHey, I remember you!{g'{x",
                ch, None, victim, TO_CHAR)
        from combat import multi_hit
        multi_hit(ch, victim)
        ch["hunting"] = None
        return

    WaitState(ch, SKILLS[GSN_HUNT]["beats"])
    direction = find_path(ch["room"], victim["room"])
    if direction is None:
        # 1stMud checks `dir < 0 || dir >= MAX_DIR`; find_path only returns
        # a valid letter or None, so the upper-bound half of that check is
        # unreachable here (same collapse as do_hunt above, hunt.py:126-132).
        act("{g$n{g says '{GDamn!  Lost $M{g!'{x", ch, None, victim, TO_ROOM)
        ch["hunting"] = None
        return

    if randint(1, 100) > 50:
        exits = ROOM_DEFS[ch["room"]].get("exits", {})
        candidates = [d for d in EXIT_ORDER if exits.get(d) is not None]
        if candidates:  # [PRIMESUD] exitless room would hang 1stMud's do/while loop
            direction = candidates[randint(0, len(candidates) - 1)]

    exit_val = ROOM_DEFS[ch["room"]].get("exits", {}).get(direction)
    if isinstance(exit_val, dict) and exit_val.get("closed"):
        from movement import do_open
        do_open(ch, [EXIT_NAMES[direction]])
        return

    from movement import move_char
    move_char(ch, direction)


def player_room_exit(player, d):
    """Return the exit value of player's room in direction d, or None. [PRIMESUD]"""
    return ROOM_DEFS[player["room"]].get("exits", {}).get(d)
