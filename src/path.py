"""Shortest route to an area or mob (cf. 1stMud do_path in act_enter.c)."""

import world
from config import DAM_OTHER, EXIT_ORDER, MAX_MORTAL_LEVEL
from gquest import gq_is_target
from handler import can_see, can_see_room, chprintln, is_name
from info import _compress_path
from magic import _find_unloaded_mob, saves_spell
from quest import is_quester
from world import MOB_DEFS, ROOM_DEFS

# Precomputed border-graph index (tools/build_path_index.py); cwd is src/
# both on-device and at runtime. Tests monkeypatch this to a tmp file.
PATH_INDEX_FILE = "paths.idx"


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


def _parse_index():
    """Read paths.idx in one f.read() and parse both record types. [PRIMESUD]

    Returns:
        tuple: (segs, xedges) where segs maps entry vnum ->
            [(exit_vnum, dist, dirs), ...] intra-area segments and xedges
            maps exit vnum -> [(dir, to_vnum), ...] cross-area exits.
    """
    segs = {}
    xedges = {}
    with open(PATH_INDEX_FILE) as f:
        data = f.read()
    for line in data.split("\n"):
        if not line or line[0] == "#":
            continue
        parts = line.split("|")
        if parts[0] == "S":
            segs.setdefault(int(parts[1]), []).append(
                (int(parts[2]), int(parts[3]), parts[4]))
        elif parts[0] == "X":
            xedges.setdefault(int(parts[1]), []).append(
                (parts[2], int(parts[3])))
    return segs, xedges


def _bfs_leg(start, tag):
    """BFS from start over one already-loaded area's rooms only. [PRIMESUD]

    Returns:
        tuple: (dist, parent) dicts; parent chains feed _compress_path.
    """
    dist = {start: 0}
    parent = {}
    queue = [start]
    qi = 0
    while qi < len(queue):
        cur = queue[qi]
        qi += 1
        room = ROOM_DEFS._data.get(cur)
        if room is None:
            continue
        for direction in EXIT_ORDER:
            exit_val = room.get("exits", {}).get(direction)
            if exit_val is None:
                continue
            to = exit_val.get("to") if isinstance(exit_val, dict) else exit_val
            if to is None or to in dist:
                continue
            to_room = ROOM_DEFS._data.get(to)
            if to_room is None or to_room.get("area") != tag:
                continue
            dist[to] = dist[cur] + 1
            parent[to] = (cur, direction)
            queue.append(to)
    return dist, parent


def _merge_runs(parts):
    """Concatenate compressed direction strings, merging boundary runs.

    "3n" + "2n" -> "5n"; format is count-then-dir with count omitted when
    1, matching info._compress_path / do_run's parser. [PRIMESUD]
    """
    runs = []  # [dir, count] pairs
    for s in parts:
        i = 0
        n = len(s)
        while i < n:
            j = i
            while "0" <= s[j] <= "9":
                j += 1
            count = int(s[i:j]) if j > i else 1
            d = s[j]
            i = j + 1
            if runs and runs[-1][0] == d:
                runs[-1][1] += count
            else:
                runs.append([d, count])
    out = []
    for d, count in runs:
        if count > 1:
            out.append(str(count))
        out.append(d)
    return "".join(out)


def _route(player, target_tag, target_room=None):
    """Exact shortest route via the precomputed border graph. [PRIMESUD]

    Dijkstra over paths.idx segments plus two live BFS legs inside
    already-loaded areas (source area; target area for mob targets, loaded
    by the mob lookup). Loads no areas at routing time. Step count matches
    an unrestricted full-world BFS; the chosen equal-length route may
    differ from upstream's.

    Returns:
        tuple: ("", 0) no walk needed; (route, steps) compressed route;
            (None, 0) unreachable.
    """
    source = player.get("room")
    if source is None:
        return None, 0
    source_tag = ROOM_DEFS[source].get("area")
    if source_tag == target_tag:
        if target_room is None or source == target_room:
            return "", 0

    segs, xedges = _parse_index()
    START = -1
    GOAL = -2

    # Source leg: virtual start -> each source-area exit room; plus a
    # direct edge to the goal for a same-area mob target (the graph still
    # considers leave-and-re-enter routes alongside it).
    sdist, sparent = _bfs_leg(source, source_tag)
    start_edges = []
    for room in sdist:
        if room in xedges:
            start_edges.append(
                (room, sdist[room], _compress_path(sparent, source, room)))
    if target_room is not None and target_room in sdist:
        start_edges.append((GOAL, sdist[target_room],
                            _compress_path(sparent, source, target_room)))

    # Target leg (mob targets): each entry room of the target area -> the
    # mob's room, BFS inside the target area (loaded by the mob lookup).
    tgt_entry = {}
    if target_room is not None:
        entries = set()
        for xlist in xedges.values():
            for _direction, to in xlist:
                if world._vnum_to_tag(to) == target_tag:
                    entries.add(to)
        for entry in entries:
            tdist, tparent = _bfs_leg(entry, target_tag)
            if target_room in tdist:
                tgt_entry[entry] = (tdist[target_room],
                                    _compress_path(tparent, entry,
                                                   target_room))

    # Dijkstra, integer weights, O(V^2) linear-min (no heapq: device
    # availability unverified).
    dist = {START: 0}
    prev = {}
    settled = set()
    goal_node = None
    while goal_node is None:
        u = None
        du = 0
        for node in dist:
            if node not in settled and (u is None or dist[node] < du):
                u = node
                du = dist[node]
        if u is None:
            return None, 0
        settled.add(u)
        if target_room is None:
            # Area target: done on first arrival inside the target area
            # (upstream path_to_area stops at the first such room).
            if u >= 0 and world._vnum_to_tag(u) == target_tag:
                goal_node = u
                break
        elif u == GOAL:
            goal_node = u
            break
        if u == START:
            edges = start_edges
        else:
            edges = [(to, w, dirs) for to, w, dirs in segs.get(u, ())]
            for direction, to in xedges.get(u, ()):
                edges.append((to, 1, direction))
            if target_room is not None and u in tgt_entry:
                w, dirs = tgt_entry[u]
                edges.append((GOAL, w, dirs))
        for to, w, dirs in edges:
            nd = du + w
            if to not in dist or nd < dist[to]:
                dist[to] = nd
                prev[to] = (u, dirs)

    parts = []
    node = goal_node
    while node != START:
        node, dirs = prev[node]
        parts.append(dirs)
    parts.reverse()
    return _merge_runs(parts), dist[goal_node]


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
