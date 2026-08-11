"""Build paths.idx: precomputed border-graph segments and cross-area exits.

src/path.py's `path <area or mob>` command Dijkstras over this offline index
at runtime instead of BFSing a static area-adjacency "corridor" -- areas are
often internally partitioned (entering from one side can't reach every exit
without crossing a third area), so a single corridor chain misses or
lengthens many real routes. See DESIGN.md "Lazy area loading" for the full
design.

Three record types, one per line:

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
        to_vnum in a different area.  `dir` is "*" when from_vnum is a
        shuffled room (see below); the runtime then synthesizes the route
        step "*<to_vnum>" from the to field.

Rooms carrying an "R" reset with num_dirs >= 2 (mob._reset_randomize_exits)
have their exits Fisher-Yates shuffled at every area reset, so a compass
direction out of one is only valid until the next reset.  Steps leaving such
a room are therefore written as room-target tokens "*<vnum>" ("take whichever
live exit leads to room <vnum>") instead of a direction char, in both S dirs
strings and X records.  The shuffle permutes exit pointers within a room but
preserves its neighbour set, so tokens -- and BFS distances through a maze --
are shuffle-invariant.  Tokens never merge into direction runs, and a run
count is never written straight after one (its digits would fuse with the
token's vnum), so "*3054" + "3n" is emitted as "*3054nnn".  [PRIMESUD]

    V|<vnum>
        Sliver border room: a border room (entry or cross-area exit room)
        whose in-area forward BFS reaches less than half of its area's
        rooms -- i.e. it sits in a disconnected fragment of the area, such
        as New Thalos' river rooms 9772-9775 (they carry the newthalos tag
        but only connect Midgaard to Haon Dor). `path`/`run <area>` skips
        these as landing spots so it arrives at a real entrance.

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


def _encode_steps(steps):
    """Run-length compress a step list into a route string. [PRIMESUD]

    Args:
        steps (list): Per-step parts: a direction char, or a "*<vnum>"
            room-target token.

    Returns:
        str: Compressed route, e.g. "3s2en" or "3s*8903nn".
    """
    out = []
    prev_token = False
    i = 0
    n = len(steps)
    while i < n:
        d = steps[i]
        count = 1
        if len(d) == 1:  # tokens are atomic, never merged into a run
            while i + count < n and steps[i + count] == d:
                count += 1
        i += count
        if count == 1:
            out.append(d)
        elif prev_token:
            # A count right after a token would fuse with the token's own
            # digits ("*89033n"), so spell the run out instead.
            out.append(d * count)
        else:
            out.append(str(count))
            out.append(d)
        prev_token = d[0] == "*"
    return "".join(out)


def _compress_path(parent, source, target, shuffled=()):
    """Trace a BFS parent chain and compress directions into runs.

    Duplicated from info._compress_path (the build tool avoids importing
    the heavy info.py module graph); keep the two in sync. [PRIMESUD]

    Args:
        parent (dict): BFS parent chain {vnum: (from_vnum, dir)}.
        source (int): Path start vnum.
        target (int): Path end vnum.
        shuffled (set): Rooms whose exits an "R" reset shuffles; steps
            leaving one are emitted as "*<to_vnum>" tokens.
    """
    steps = []
    v = target
    while v != source:
        pv, d = parent[v]
        steps.append("*" + str(v) if pv in shuffled else d)
        v = pv
    steps.reverse()
    return _encode_steps(steps)


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


def build_records(rooms_data, shuffled=()):
    """Compute paths.idx's S/X/V records from a {vnum: room_dict} mapping.

    Pure function so tests can build a border graph from a synthetic world
    without touching the filesystem. [PRIMESUD]

    Args:
        rooms_data (dict): {vnum: room_dict}; each room_dict must carry
            "area" (owning area tag) and "exits" ({dir: to_vnum_or_dict}).
        shuffled (set): Rooms whose exits are reshuffled on every area
            reset (see module docstring); steps leaving one are written as
            "*<to_vnum>" room-target tokens, and their X records carry "*"
            as the direction field.

    Returns:
        list: Sorted "S|..."/"X|..."/"V|..." record strings (X records
            first, then S, then V).
    """
    area_adj = {}      # tag -> {vnum: [(dir, to), ...]}
    exit_rooms = {}     # tag -> set(vnum) with a cross-area exit out
    entry_rooms = {}    # tag -> set(vnum) targeted by a cross-area exit in
    x_recs = []         # (from_vnum, dir, to_vnum)
    room_count = {}     # tag -> number of rooms carrying that area tag

    for vnum, room in rooms_data.items():
        tag = room.get("area")
        room_count[tag] = room_count.get(tag, 0) + 1
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
                x_recs.append(
                    (vnum, "*" if vnum in shuffled else direction, to))
                exit_rooms.setdefault(tag, set()).add(vnum)
                entry_rooms.setdefault(to_tag, set()).add(to)

    s_recs = []  # (from_vnum, to_vnum, dist, dirs)
    v_recs = []  # border rooms stranded in a disconnected in-area fragment
    tags = set(entry_rooms)
    tags.update(exit_rooms)
    for tag in tags:
        adj = area_adj.get(tag, {})
        entries = entry_rooms.get(tag, ())
        xrooms = exit_rooms.get(tag, ())
        borders = set(entries)
        borders.update(xrooms)
        for b in borders:
            dist, parent = _bfs_area(adj, b)
            if len(dist) * 2 < room_count.get(tag, 0):
                v_recs.append(b)
            if b not in entries:
                continue
            for x in xrooms:
                if x == b or x not in dist:
                    continue
                s_recs.append((b, x, dist[x],
                               _compress_path(parent, b, x, shuffled)))

    x_recs.sort(key=lambda r: (r[0], r[1]))
    s_recs.sort(key=lambda r: (r[0], r[1]))
    v_recs.sort()
    lines = ["X|" + str(v) + "|" + d + "|" + str(t) for v, d, t in x_recs]
    lines.extend("S|" + str(e) + "|" + str(x) + "|" + str(dist) + "|" + dirs
                 for e, x, dist, dirs in s_recs)
    lines.extend("V|" + str(v) for v in v_recs)
    return lines


def _shuffled_rooms(rooms_data):
    """Rooms an "R" reset reshuffles on every area reset. [PRIMESUD]

    Derived from the loaded reset data rather than hardcoded, so new or
    re-converted areas need no tool edit.  num_dirs < 2 is a no-op shuffle
    (mob._reset_randomize_exits returns early), so those rooms keep plain
    compass directions.
    """
    out = set()
    for room in rooms_data.values():
        for entry in room.get("resets") or ():
            if entry[0] == "R" and entry[2] >= 2:
                out.add(entry[1])
    return out


def main():
    os.chdir(APPDIR)  # area file names in _TAG_TO_FILE are relative to src/
    # A few rooms (e.g. hitower's Shadow Grove, the daycare maze) carry an
    # "R" reset that Fisher-Yates shuffles at every area reset (mob.py
    # _reset_randomize_exits), including the initial load below. Pin the
    # RNG so the index is byte-reproducible.  The frozen layout no longer
    # leaks into the index: steps leaving a shuffled room are written as
    # "*<vnum>" room-target tokens (see module docstring), which survive
    # the live game's reshuffles; only the shuffle-invariant neighbour
    # sets and distances are read off this layout. [PRIMESUD]
    import random
    random.seed(20260720)
    from terminal import init_terminal
    init_terminal()
    import world
    world.init_world()
    for _ in world.ROOM_DEFS:  # force-load every area (LazyDict.__iter__)
        pass

    rooms_data = world.ROOM_DEFS._data
    lines = build_records(rooms_data, _shuffled_rooms(rooms_data))

    out_path = os.path.join(APPDIR, "paths.idx")
    header = ("# S|from|to|dist|dirs intra-area segments, X|from|dir|to"
              " cross-area exits, V|vnum sliver border rooms; dir/dirs step"
              " *<vnum> = take the live exit to <vnum> (shuffled room) --"
              " built by tools/build_path_index.py, do not edit\n")
    with open(out_path, "w", newline="\n") as f:
        f.write(header + "\n".join(lines) + "\n")

    n_x = sum(1 for l in lines if l[0] == "X")
    n_v = sum(1 for l in lines if l[0] == "V")
    n_s = len(lines) - n_x - n_v
    print("Wrote", out_path, "-", n_x, "X records,", n_s, "S records,",
          n_v, "V records")


if __name__ == "__main__":
    main()
