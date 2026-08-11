"""Shortest route to an area or mob (cf. 1stMud do_path in act_enter.c)."""

import world
from config import MAX_MORTAL_LEVEL
from gquest import gq_is_target
from handler import can_see, can_see_room, chprintln, is_name
from info import _route
from magic import _find_unloaded_mob
from quest import is_quester
from util import count_str
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
    """Apply the intended 1stMud do_path mob restrictions. [PRIMESUD]

    [PRIMESUD] Returns a reason code alongside the destination so do_path can
    say *why* a mob is unreachable.  Upstream collapses every failure into one
    vague message, which is anti-oracle on a multiplayer MUD; PrimeSUD is
    single-user, so the vagueness only costs the player information.  Which
    mobs are blocked is unchanged -- the gates are merely evaluated in order
    of how actionable the answer is.

    Args:
        player (dict): Player state dict.
        mob (dict): Target mob state dict, or None if no keyword matched.

    Returns:
        tuple: (destination room vnum, None) when pathable, else
            (None, reason code) -- one of "nomob", "norecall_here", "quest",
            "level", "blocked".
    """
    if mob is None:
        return None, "nomob"
    src_flags = ROOM_DEFS.get(player.get("room"), {}).get("flags", {})
    # Checked first: it blocks pathing to anything at all from this room.
    if src_flags.get("no_recall"):
        return None, "norecall_here"
    if mob.get("is_npc") and (gq_is_target(mob.get("tpl"))
                              or (is_quester(player)
                                  and mob.get("tpl")
                                  == player.get("quest_mob", 0))):
        return None, "quest"
    if mob.get("level", 0) >= player.get("level", 1) + 3:
        return None, "level"
    dst = mob.get("room")
    if dst is None:
        return None, "blocked"
    dst_flags = ROOM_DEFS.get(dst, {}).get("flags", {})
    # [PRIMESUD] 1stMud also gates on saves_spell(ch->level, victim,
    # DAM_OTHER).  Dropped: no skill or stat feeds it, so it is pure
    # level-difference RNG on a free, no-feedback info command --
    # the optimal play is to spam path until it rolls through.  The
    # level signal it encoded is already carried deterministically by
    # the level + 3 gate above.  It also made DAM_OTHER-immune (i.e.
    # IMM_MAGIC) mobs permanently unpathable, which pathing never
    # intended.  See docs/FIXES.md.
    if (not can_see_room(player, dst)
            or dst_flags.get("safe")
            # TODO [PRIMESUD] arena, clans, and area access flags not ported
            or dst_flags.get("no_recall")
            or dst_flags.get("private")
            or dst_flags.get("solitary")
            or (not mob.get("is_npc")
                and mob.get("level", 0) >= MAX_MORTAL_LEVEL)
            or mob.get("imm_flags", {}).get("summon")):
        return None, "blocked"
    return dst, None


def _display_route(route):
    """Render a route's "*<vnum>" room-target tokens as "?". [PRIMESUD]

    Tokens mean "take whichever live exit leads to room <vnum>" (steps out
    of a shuffle-reset maze, see tools/build_path_index.py); the vnum is
    noise to the player, so the walk shows one "?" per such step.  `run`
    still gets the raw token string.
    """
    out = []
    i = 0
    n = len(route)
    while i < n:
        c = route[i]
        i += 1
        if c == "*":
            out.append("?")
            while i < n and "0" <= route[i] <= "9":
                i += 1
        else:
            out.append(c)
    return "".join(out)


def do_path(player, args):
    """Show the shortest route to an area or mob (cf. 1stMud do_path in act_enter.c).

    [PRIMESUD] Fixes upstream's inverted mob-target condition, drops its
    random saving-throw gate (see _mob_destination), and searches unloaded
    mobs through mobs.bin. Routing runs over the precomputed border graph
    (paths.idx) and never loads areas at routing time.

    [PRIMESUD] Upstream's single "No such destination." for every mob-target
    failure is split into per-reason messages (see _mob_destination); the
    area-lookup and routing messages are unchanged.

    [PRIMESUD] Steps out of a shuffle-reset maze print as "?" (see
    _display_route) plus one helper line; player["last_path"] keeps the raw
    "*<vnum>" tokens so `run` can resolve them live.

    [PRIMESUD] Side effect: a computed route is stashed in
    player["last_path"] so the no-args `run` picker can offer it as the
    default destination (see movement.do_run).

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

    # [PRIMESUD] Mob lookup and routing can briefly block input.
    chprintln(player, "{D[Calculating path...]{x")
    argument = " ".join(args)
    try:
        target_tag, target_name = _area_lookup(argument)
        target_room = None
        if target_tag is None:
            mob = _loaded_mob(argument, player)
            if mob is None:
                mob = _find_unloaded_mob(argument, player)[1]
            target_room, reason = _mob_destination(player, mob)
            if target_room is None:
                if reason == "nomob":
                    chprintln(player, "No mob or area by that name.")
                elif reason == "norecall_here":
                    chprintln(player,
                              "Magic here prevents you from sensing a path.")
                elif reason == "quest":
                    chprintln(player,
                              "You must track down quest targets on your own.")
                elif reason == "level":
                    chprintln(
                        player,
                        "You cannot sense a path to so powerful a creature.")
                else:
                    chprintln(player, "You cannot sense a path to them.")
                return
            target_tag = world._vnum_to_tag(target_room)
            target_name = MOB_DEFS[mob["tpl"]]["short_descr"]

        route, steps = _route(player, target_tag, target_room)
        if route == "":
            chprintln(player, "No need to walk to get there!")
        elif route is None:
            chprintln(player, "No path to destination.")
        else:
            # [PRIMESUD] singular/plural fixed; 1stMud always prints "steps"
            chprintln(player, "Shortest path to " + target_name + " is "
                      + count_str(steps, "step") + ": "
                      + _display_route(route) + ".")
            if "*" in route:
                chprintln(player,
                          "{D(? = random maze exit){x")
            # [PRIMESUD] Offer the route as the default entry in the no-args
            # `run` picker (movement.do_run).  Transient: saving is a
            # whitelist (game_state._PLAYER_STRING_SAVE_KEYS and friends), so
            # this never persists, and the stored room vnum invalidates it the
            # moment the player moves, since the route is only valid from
            # where it was computed.
            player["last_path"] = (target_name, route, steps,
                                   player.get("room"))
    finally:
        # Unlike run/gate, path does not move the player and trigger eviction.
        world.maybe_evict(player, True)
