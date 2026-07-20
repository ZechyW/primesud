"""Shortest route to an area or mob (cf. 1stMud do_path in act_enter.c)."""

import world
from config import DAM_OTHER, MAX_MORTAL_LEVEL
from gquest import gq_is_target
from handler import can_see, can_see_room, chprintln, is_name
from info import _route
from magic import _find_unloaded_mob, saves_spell
from quest import is_quester
from world import MOB_DEFS, ROOM_DEFS


def _area_lookup(argument):
    """Return static area metadata for a name/tag prefix. [PRIMESUD]"""
    arg = argument.lower()
    for _fname, tag, name, _lo, _hi in world._AREA_FILES:
        if name.lower().startswith(arg) or tag.lower().startswith(arg):
            return tag, name
    return None, None


def _loaded_mob(argument, player):
    """Find the first loaded mob by keyword, matching get_char_world. [PRIMESUD]"""
    for mob in world.chars.values():
        if mob is player or not mob.get("is_npc"):
            continue
        tpl = MOB_DEFS.get(mob.get("tpl"), {})
        if is_name(argument, tpl.get("keywords", "")) and can_see(player, mob):
            return mob
    return None


def _mob_destination(player, mob):
    """Apply the intended 1stMud do_path mob restrictions. [PRIMESUD]"""
    if mob is None:
        return None
    dst = mob.get("room")
    if dst is None:
        return None
    src_flags = ROOM_DEFS.get(player.get("room"), {}).get("flags", {})
    dst_flags = ROOM_DEFS.get(dst, {}).get("flags", {})
    if (not can_see_room(player, dst)
            or dst_flags.get("safe")
            # TODO [PRIMESUD] arena, clans, and area access flags not ported
            or src_flags.get("no_recall")
            or dst_flags.get("no_recall")
            or dst_flags.get("private")
            or dst_flags.get("solitary")
            or (mob.get("is_npc") and gq_is_target(mob.get("tpl")))
            or (mob.get("is_npc") and is_quester(player)
                and mob.get("tpl") == player.get("quest_mob", 0))
            or mob.get("level", 0) >= player.get("level", 1) + 3
            or (not mob.get("is_npc")
                and mob.get("level", 0) >= MAX_MORTAL_LEVEL)
            or mob.get("imm_flags", {}).get("summon")
            or saves_spell(player.get("level", 1), mob, DAM_OTHER)):
        return None
    return dst


def do_path(player, args):
    """Show the shortest route to an area or mob (cf. 1stMud do_path in act_enter.c).

    [PRIMESUD] Fixes upstream's inverted mob-target condition and searches
    unloaded mobs through mobs.idx. Routing runs over the precomputed
    border graph (paths.idx) and never loads areas at routing time.

    Args:
        player (dict): Player state dict.
        args (list): Destination area or mob name words.
    """
    if not args:
        chprintln(player, "Syntax: path <destination mob or area>")
        return
    if player.get("room") is None:
        chprintln(player, "You must be somewhere to go anywhere.")
        return

    argument = " ".join(args)
    try:
        target_tag, target_name = _area_lookup(argument)
        target_room = None
        if target_tag is None:
            mob = _loaded_mob(argument, player)
            if mob is None:
                mob = _find_unloaded_mob(argument, player)[1]
            target_room = _mob_destination(player, mob)
            if target_room is None:
                chprintln(player, "No such destination.")
                return
            target_tag = world._vnum_to_tag(target_room)
            target_name = MOB_DEFS[mob["tpl"]]["short_descr"]

        route, steps = _route(player, target_tag, target_room)
        if route == "":
            chprintln(player, "No need to walk to get there!")
        elif route is None:
            chprintln(player, "No path to destination.")
        else:
            chprintln(player, "Shortest path to %s is %d steps: %s."
                      % (target_name, steps, route))
    finally:
        # Unlike run/gate, path does not move the player and trigger eviction.
        world.maybe_evict(player, True)
