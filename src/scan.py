"""Scan command support (cf. 1stMud scan.c)."""

import world
from config import DIR_ALIASES, EXIT_NAMES
from handler import chprintln
from world import ROOM_DEFS, MOB_DEFS

_DISTANCE = (
    "right here.",
    "nearby to the %s.",
    "not far %s.",
    "off in the distance %s.",
)


def _scan_char_line(victim, depth, door):
    """Build one scan result line (cf. 1stMud scan_char in scan.c)."""
    tpl = MOB_DEFS[victim["tpl"]]
    direction = EXIT_NAMES.get(door, door)
    suffix = _DISTANCE[depth]
    if depth > 0:
        suffix = suffix % direction
    return tpl["short_descr"] + ", " + suffix


def scan_list(room_vnum, ch, depth, door):
    """Print visible characters in one room (cf. 1stMud scan_list in scan.c)."""
    room_state = world.rooms.get(room_vnum)
    if room_state is None:
        return
    for mob_id in room_state.get("mobs", []):
        mob = world.chars.get(mob_id)
        if mob is not None:
            chprintln(ch, _scan_char_line(mob, depth, door))


def do_scan(player, args):
    """Scan nearby rooms for creatures (cf. 1stMud do_scan in scan.c)."""
    arg = args[0] if args else ""
    if not arg:
        chprintln(player, "Looking around you see:")
        scan_list(player["room"], player, 0, "")
        for door, exit_val in ROOM_DEFS[player["room"]].get("exits", {}).items():
            dest = exit_val["to"] if isinstance(exit_val, dict) else exit_val
            scan_list(dest, player, 1, door)
        return

    door = DIR_ALIASES.get(arg)
    if door is None:
        chprintln(player, "Which way do you want to scan?")
        return

    chprintln(player, "You peer intently " + EXIT_NAMES.get(door, door) + ".")
    room_vnum = player["room"]
    for depth in range(1, 4):
        exit_val = ROOM_DEFS.get(room_vnum, {}).get("exits", {}).get(door)
        if exit_val is None:
            break
        room_vnum = exit_val["to"] if isinstance(exit_val, dict) else exit_val
        scan_list(room_vnum, player, depth, door)
