"""Border-graph routing vs unrestricted BFS on the real world data. [PRIMESUD]

Loads every real area, builds the border graph in memory with the same
build_records the offline tool uses, then checks sample routes three ways:
step count equals a full-world unrestricted BFS, the route string actually
walks to the destination through real room exits, and the walked length
equals the reported step count.
"""

import os
import sys

import pytest

import info
import world
from config import EXIT_ORDER

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
from build_path_index import build_records


@pytest.fixture(scope="module")
def real_world(tmp_path_factory):
    """Load all real areas; snapshot/restore world state like fresh_world.

    Module-scoped: the force-load of every area plus build_records costs
    ~10s on slow hardware, and both tests only read from the loaded world.
    """
    old_area_files = world._AREA_FILES[:]
    old_state = {
        "_LOADED_AREAS": set(world._LOADED_AREAS),
        "_TAG_TO_FILE": dict(world._TAG_TO_FILE),
        "_TAG_TO_NAME": dict(world._TAG_TO_NAME),
        "_VNUM_RANGES": list(world._VNUM_RANGES),
        "_pending_mob_saves": dict(world._pending_mob_saves),
        "_pending_room_items": dict(world._pending_room_items),
        "ROOM_DEFS": dict(world.ROOM_DEFS._data),
        "MOB_DEFS": dict(world.MOB_DEFS._data),
        "ITEM_DEFS": dict(world.ITEM_DEFS._data),
        "DOOR_DEFS": dict(world.DOOR_DEFS),
        "MOBPROGS": dict(world.MOBPROGS),
        "OBJPROGS": dict(world.OBJPROGS),
        "ROOMPROGS": dict(world.ROOMPROGS),
        "AREA_DEFS": list(world.AREA_DEFS),
        "rooms": dict(world.rooms._data),
        "chars": dict(world.chars),
        "areas": list(world.areas),
        "_WORLD_READY": world._WORLD_READY,
    }

    if not world._WORLD_READY:
        world.init_world()
    for _ in world.ROOM_DEFS:  # force-load every area (LazyDict.__iter__)
        pass

    lines = build_records(world.ROOM_DEFS._data)
    idx = tmp_path_factory.mktemp("realworld") / "paths.idx"
    idx.write_text("# realworld test index\n" + "\n".join(lines) + "\n")
    mp = pytest.MonkeyPatch()
    mp.setattr(info, "PATH_INDEX_FILE", str(idx))

    yield world.ROOM_DEFS._data

    mp.undo()
    world._AREA_FILES[:] = old_area_files
    world._LOADED_AREAS.clear()
    world._LOADED_AREAS.update(old_state["_LOADED_AREAS"])
    for name in ("_TAG_TO_FILE", "_TAG_TO_NAME", "_pending_mob_saves",
                 "_pending_room_items", "DOOR_DEFS", "MOBPROGS",
                 "OBJPROGS", "ROOMPROGS", "chars"):
        d = getattr(world, name)
        d.clear()
        d.update(old_state[name])
    world._VNUM_RANGES[:] = old_state["_VNUM_RANGES"]
    world.AREA_DEFS[:] = old_state["AREA_DEFS"]
    for name in ("ROOM_DEFS", "MOB_DEFS", "ITEM_DEFS"):
        d = getattr(world, name)._data
        d.clear()
        d.update(old_state[name])
    world.rooms._data.clear()
    world.rooms._data.update(old_state["rooms"])
    world.areas = old_state["areas"]
    world._area_seq.clear()
    world._player_room = None
    world._seq_counter = 0
    world._last_evict_area = None
    world._WORLD_READY = old_state["_WORLD_READY"]


def _exit_to(room, direction):
    ev = (room.get("exits") or {}).get(direction)
    if ev is None:
        return None
    return ev.get("to") if isinstance(ev, dict) else ev


def _global_bfs(data, src, target_tag, target_room, slivers=()):
    """Unrestricted full-world BFS oracle: steps to goal or None.

    Mirrors _route's [PRIMESUD] sliver rule for area targets: rooms flagged
    as slivers in the index are walked through but not landed on, and are
    only accepted on a second pass if nothing else in the area is reachable.
    """
    if target_room is not None:
        if src == target_room:
            return 0
    elif data[src].get("area") == target_tag:
        return 0
    dist = {src: 0}
    queue = [src]
    qi = 0
    while qi < len(queue):
        cur = queue[qi]
        qi += 1
        for direction in EXIT_ORDER:
            to = _exit_to(data[cur], direction)
            if to is None or to not in data or to in dist:
                continue
            dist[to] = dist[cur] + 1
            if target_room is not None:
                if to == target_room:
                    return dist[to]
            elif data[to].get("area") == target_tag and to not in slivers:
                return dist[to]
            queue.append(to)
    if target_room is None and slivers:
        return _global_bfs(data, src, target_tag, None)
    return None


def _walk(data, src, route):
    """Walk a compressed route through real exits; return (end, steps)."""
    pos = src
    steps = 0
    i = 0
    while i < len(route):
        j = i
        while "0" <= route[j] <= "9":
            j += 1
        count = int(route[i:j]) if j > i else 1
        direction = route[j]
        i = j + 1
        for _ in range(count):
            to = _exit_to(data[pos], direction)
            assert to is not None, "route walks a missing exit"
            pos = to
            steps += 1
    return pos, steps


def _sliver_fragment(data, tag, slivers):
    """Every room reachable in-area from one of tag's flagged rooms.

    The index only flags border rooms, but the disconnected fragment they
    sit in holds ordinary rooms too; the router can only ever land on a
    border room, so the oracle must refuse the whole fragment to stay
    comparable.  Sound by construction: anything a flagged room reaches
    in-area has a reach no larger than its own, so it is a sliver too.
    """
    out = set()
    stack = [v for v in slivers if data.get(v, {}).get("area") == tag]
    while stack:
        cur = stack.pop()
        if cur in out:
            continue
        out.add(cur)
        for direction in EXIT_ORDER:
            to = _exit_to(data[cur], direction)
            if (to is not None and to in data and to not in out
                    and data[to].get("area") == tag):
                stack.append(to)
    return out


def _first_room(data, tag):
    return min(v for v, r in data.items() if r.get("area") == tag)


def test_routes_match_unrestricted_bfs(real_world):
    data = real_world
    pairs = [
        # (src, target_tag, target_room) -- target_room None = area target
        (_first_room(data, "catacomb"), "midgaard", None),
        (2, "olympus", None),                    # old corridor: 71 vs ~18
        (3001, "chess2", None),
        (_first_room(data, "chess2"), "midgaard", None),
        (3001, "moria", None),
        (3001, "newthalos", None),               # sliver river rooms skipped
        (_first_room(data, "newthalos"), "midgaard", None),
        (_first_room(data, "olympus"), "catacomb", None),
        (3001, "thalos", _first_room(data, "thalos")),
        (_first_room(data, "catacomb"), "midgaard", 3054),
        (2, "moria", _first_room(data, "moria")),
    ]
    slivers = info._parse_index()[2]
    for src, tag, room in pairs:
        label = "%s -> %s/%s" % (src, tag, room)
        skip = () if room is not None else _sliver_fragment(data, tag,
                                                            slivers)
        oracle = _global_bfs(data, src, tag, room, skip)
        route, steps = info._route({"room": src}, tag, room)
        if oracle is None:
            assert route is None, label
            continue
        assert route is not None, label
        assert steps == oracle, label + \
            " (steps %d != oracle %d)" % (steps, oracle)
        end, walked = _walk(data, src, route)
        assert walked == steps, label
        if room is not None:
            assert end == room, label
        else:
            assert data[end].get("area") == tag, label
            assert end not in slivers, label


def test_area_route_skips_disconnected_sliver(real_world):
    """[PRIMESUD] Rooms 9772-9775 ("On the Dark River") carry the newthalos
    tag but only link Midgaard to Haon Dor -- landing there strands the
    player outside New Thalos proper.  The route must reach the West Gate
    (9669) via Miden'nir instead."""
    data = real_world
    slivers = info._parse_index()[2]
    assert 9772 in slivers and 9774 in slivers
    route, steps = info._route({"room": 3001}, "newthalos")
    end, walked = _walk(data, 3001, route)
    assert end == 9669
    assert walked == steps
