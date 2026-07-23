"""Build paths.idx: precomputed border-graph segments and cross-area exits.

src/path.py's `path <area or mob>` command Dijkstras over this offline index
at runtime instead of BFSing a static area-adjacency "corridor" -- areas are
often internally partitioned (entering from one side can't reach every exit
without crossing a third area), so a single corridor chain misses or
lengthens many real routes. See DESIGN.md "Lazy area loading" for the full
design.

Two record types, one per line:

    S|<from_vnum>|<to_vnum>|<dist>|<dirs>
        Intra-area segment: for an area with entry room `from_vnum` (target
        of some cross-area exit into this area) and exit room `to_vnum`
        (source of some cross-area exit out of this area), the shortest
        walk between them *staying inside the area*, as a distance and a
        compressed direction string (info._compress_path format, e.g.
        "3n2e"). Omitted when from_vnum == to_vnum (zero-length, handled at
        runtime) or when to_vnum is unreachable from from_vnum inside the
        area.

    X|<from_vnum>|<dir>|<to_vnum>
        A single cross-area exit: room from_vnum's `dir` exit leads to room
        to_vnum in a different area.

Re-run after re-converting any area:

    python tools/build_path_index.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPDIR = os.path.join(ROOT, "src")
sys.path.insert(0, APPDIR)
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

from config import EXIT_ORDER


def _compress_path(parent, source, target):
    """Trace a BFS parent chain and compress directions into runs.

    Duplicated from info._compress_path (the build tool avoids importing
    the heavy info.py module graph); keep the two in sync. [PRIMESUD]
    """
    path = []
    v = target
    while v != source:
        pv, d = parent[v]
        path.append(d)
        v = pv
    path.reverse()
    if not path:
        return ""
    parts = []
    count = 1
    for i in range(1, len(path)):
        if path[i] == path[i - 1]:
            count += 1
        else:
            if count > 1:
                parts.append(str(count))
            parts.append(path[i - 1])
            count = 1
    if count > 1:
        parts.append(str(count))
    parts.append(path[-1])
    return "".join(parts)


def _bfs_area(area_adj, start):
    """Restricted BFS over one area's intra-area adjacency. [PRIMESUD]

    Args:
        area_adj (dict): {vnum: [(dir, to_vnum), ...]} for one area only.
        start (int): Starting room vnum (an entry room).

    Returns:
        tuple: (dist, parent) dicts as produced by a standard BFS.
    """
    dist = {start: 0}
    parent = {}
    queue = [start]
    qi = 0
    while qi < len(queue):
        cur = queue[qi]
        qi += 1
        for direction, to in area_adj.get(cur, ()):
            if to in dist:
                continue
            dist[to] = dist[cur] + 1
            parent[to] = (cur, direction)
            queue.append(to)
    return dist, parent


def build_records(rooms_data):
    """Compute paths.idx's S/X records from a {vnum: room_dict} mapping.

    Pure function so tests can build a border graph from a synthetic world
    without touching the filesystem. [PRIMESUD]

    Args:
        rooms_data (dict): {vnum: room_dict}; each room_dict must carry
            "area" (owning area tag) and "exits" ({dir: to_vnum_or_dict}).

    Returns:
        list: Sorted "S|..."/"X|..." record strings (X records first).
    """
    area_adj = {}      # tag -> {vnum: [(dir, to), ...]}
    exit_rooms = {}     # tag -> set(vnum) with a cross-area exit out
    entry_rooms = {}    # tag -> set(vnum) targeted by a cross-area exit in
    x_recs = []         # (from_vnum, dir, to_vnum)

    for vnum, room in rooms_data.items():
        tag = room.get("area")
        exits = room.get("exits") or {}
        for direction in EXIT_ORDER:
            ev = exits.get(direction)
            if ev is None:
                continue
            to = ev.get("to") if isinstance(ev, dict) else ev
            if to is None:
                continue
            to_room = rooms_data.get(to)
            if to_room is None:
                continue
            to_tag = to_room.get("area")
            if to_tag is None:
                continue
            if to_tag == tag:
                area_adj.setdefault(tag, {}).setdefault(vnum, []).append(
                    (direction, to))
            else:
                x_recs.append((vnum, direction, to))
                exit_rooms.setdefault(tag, set()).add(vnum)
                entry_rooms.setdefault(to_tag, set()).add(to)

    s_recs = []  # (from_vnum, to_vnum, dist, dirs)
    for tag, entries in entry_rooms.items():
        adj = area_adj.get(tag, {})
        xrooms = exit_rooms.get(tag, ())
        for e in entries:
            dist, parent = _bfs_area(adj, e)
            for x in xrooms:
                if x == e or x not in dist:
                    continue
                s_recs.append((e, x, dist[x], _compress_path(parent, e, x)))

    x_recs.sort(key=lambda r: (r[0], r[1]))
    s_recs.sort(key=lambda r: (r[0], r[1]))
    lines = ["X|" + str(v) + "|" + d + "|" + str(t) for v, d, t in x_recs]
    lines.extend("S|" + str(e) + "|" + str(x) + "|" + str(dist) + "|" + dirs
                 for e, x, dist, dirs in s_recs)
    return lines


def main():
    os.chdir(APPDIR)  # area file names in _TAG_TO_FILE are relative to src/
    # A few rooms (e.g. hitower's Shadow Grove, the daycare maze) carry an
    # "R" reset that Fisher-Yates shuffles at every area reset (mob.py
    # _reset_randomize_exits), including the initial load below. Pin the
    # RNG so the index is byte-reproducible; this freezes one arbitrary
    # (but valid) maze layout -- the live game keeps reshuffling those
    # rooms on its own reset clock, so paths through them can drift stale
    # until the index is rebuilt. [PRIMESUD]
    import random
    random.seed(20260720)
    from terminal import init_terminal
    init_terminal()
    import world
    world.init_world()
    for _ in world.ROOM_DEFS:  # force-load every area (LazyDict.__iter__)
        pass

    lines = build_records(world.ROOM_DEFS._data)

    out_path = os.path.join(APPDIR, "paths.idx")
    header = ("# S|from|to|dist|dirs intra-area segments, X|from|dir|to"
              " cross-area exits -- built by tools/build_path_index.py,"
              " do not edit\n")
    with open(out_path, "w", newline="\n") as f:
        f.write(header + "\n".join(lines) + "\n")

    n_x = sum(1 for l in lines if l[0] == "X")
    n_s = len(lines) - n_x
    print("Wrote", out_path, "-", n_x, "X records,", n_s, "S records")


if __name__ == "__main__":
    main()
