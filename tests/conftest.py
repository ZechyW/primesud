"""Test fixtures for PrimeSUD lazy area loading tests.

Convention: new synthetic/stub vnums in tests should be >= 20000.  Real areas
span 1-17899, so a stub above that can never fall inside `world._VNUM_RANGES`
and trigger a surprise lazy area load if some earlier test leaks world state.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))
sys.path.insert(0, ROOT)  # `from tools import ...` in a few tests

def pytest_configure(config):
    """Run the whole suite from src/, exactly as run_source.py does.

    The calculator has a flat filesystem, so runtime data files (area_*.txt,
    help.txt/.idx, socials, music, *.idx) are opened by bare name relative to
    the cwd.  Pinning it here means no test has to invent its own chdir, and
    a lazy area load that fires unexpectedly just works instead of raising
    FileNotFoundError depending on run order.

    A hook, not a fixture or a module-level call: test modules do work at
    import time, which happens during collection -- after configure, but
    before any fixture runs.  Doing it at import time instead would land
    before pytest resolves `testpaths`.

    Under pytest-xdist the controller must NOT chdir: workers inherit its
    cwd at spawn and then resolve the (relative) collection args against
    it, so a controller sitting in src/ makes every worker collect zero
    tests.  The controller runs no tests itself; each worker re-runs this
    hook and pins its own cwd.
    """
    if (getattr(config.option, "numprocesses", None)
            and not hasattr(config, "workerinput")):
        return  # xdist controller: coordinate only, keep rootdir cwd
    os.chdir(os.path.join(ROOT, _SRC))

import pytest
from terminal import init_terminal
init_terminal()
import world


def _world_sig():
    """Cheap O(1) signature of the world tables lazy loading depends on."""
    return (world._WORLD_READY, len(world._VNUM_RANGES),
            len(world._TAG_TO_FILE), len(world._TAG_TO_NAME),
            len(world.AREA_DEFS), len(world._LOADED_AREAS))


def pytest_runtest_setup(item):
    """Record the world-state signature before anything sets up (tripwire)."""
    item._world_sig_before = _world_sig()


@pytest.hookimpl(wrapper=True)
def pytest_runtest_teardown(item, nextitem):
    """Fail the test that leaks global world state, not its innocent successor.

    An unrestored `init_world()` leaves `_VNUM_RANGES` populated, so a later
    test's fake vnum can land inside a real area's range and trigger a lazy
    load against tables its own fixture already tore down.  Reading before
    setup and after teardown catches the fixture that never restores at all,
    not just the one that restores incompletely.

    A hook wrapper, not an autouse fixture: the check has to see state after
    everything has put back what it borrowed, and fixture teardown order does
    not reliably put an autouse fixture last -- the shared `monkeypatch`
    instance (pulled in by `isolate_persistence`) undoes after it.

    Modules whose own module/session-scoped fixture deliberately holds real
    world state across their tests opt out with the `world_state_persists`
    marker; that fixture's teardown is what guarantees the restore.
    """
    result = yield
    before = getattr(item, "_world_sig_before", None)
    after = _world_sig()
    if (before is not None and after != before
            and item.get_closest_marker("world_state_persists") is None):
        pytest.fail(
            "test leaked global world state (see tests/conftest.py "
            "stock_world / fresh_world for the restore pattern)\n"
            "  (_WORLD_READY, _VNUM_RANGES, _TAG_TO_FILE, _TAG_TO_NAME, "
            "AREA_DEFS, _LOADED_AREAS)\n"
            "  before: " + repr(before) + "\n  after:  " + repr(after))
    return result


@pytest.fixture(autouse=True)
def isolate_persistence(tmp_path, monkeypatch):
    """Keep tests away from the PC player's real save files."""
    import game_state
    import prime_platform

    monkeypatch.setattr(prime_platform, "_HVARS_FILE",
                        str(tmp_path / "hvars.json"))
    monkeypatch.setattr(game_state, "SAVE_FILE",
                        str(tmp_path / "primesud.sav"))
    monkeypatch.setattr(game_state, "BACKUP_FILE",
                        str(tmp_path / "primesud_backup.sav"))


@pytest.fixture
def stock_world():
    """Run a test against the real, fully initialised world; restore after.

    Snapshots every mutable world table `init_world()` (and any lazy load it
    enables) can touch, then puts them back at teardown.  Restores in place --
    module-level names are aliased elsewhere -- except `world.areas`, which
    world.py rebinds itself.
    """
    snap = {
        "chars": dict(world.chars),
        "rooms": dict(world.rooms._data),
        "_LOADED_AREAS": set(world._LOADED_AREAS),
        "ROOM_DEFS": dict(world.ROOM_DEFS._data),
        "MOB_DEFS": dict(world.MOB_DEFS._data),
        "ITEM_DEFS": dict(world.ITEM_DEFS._data),
        "DOOR_DEFS": dict(world.DOOR_DEFS),
        "areas": list(world.areas),
        "AREA_DEFS": list(world.AREA_DEFS),
        "_VNUM_RANGES": list(world._VNUM_RANGES),
        "_TAG_TO_FILE": dict(world._TAG_TO_FILE),
        "_TAG_TO_NAME": dict(world._TAG_TO_NAME),
        "_pending_mob_saves": dict(world._pending_mob_saves),
        "_pending_room_items": dict(world._pending_room_items),
        "_WORLD_READY": world._WORLD_READY,
    }
    world.init_world()
    yield
    for name in ("chars", "DOOR_DEFS", "_TAG_TO_FILE", "_TAG_TO_NAME",
                 "_pending_mob_saves", "_pending_room_items"):
        d = getattr(world, name)
        d.clear()
        d.update(snap[name])
    world._LOADED_AREAS.clear()
    world._LOADED_AREAS.update(snap["_LOADED_AREAS"])
    world.rooms._data.clear()
    world.rooms._data.update(snap["rooms"])
    for name in ("ROOM_DEFS", "MOB_DEFS", "ITEM_DEFS"):
        d = getattr(world, name)._data
        d.clear()
        d.update(snap[name])
    world.AREA_DEFS[:] = snap["AREA_DEFS"]
    world._VNUM_RANGES[:] = snap["_VNUM_RANGES"]
    world.areas = snap["areas"]
    world._WORLD_READY = snap["_WORLD_READY"]


def _write_area_txt(path, rooms, mobiles=None, objects=None, resets=None,
               area=None, mobprogs=None, objprogs=None, roomprogs=None):
    """Write a synthetic area .txt data file for testing.

    spec_fun/shop data is baked directly into individual MOBILES entries
    by the caller (cf. tools/are_to_primesud.py) -- there are no
    longer separate SPECIALS/SHOPS sections.
    """
    lines = []
    lines.append("AREA = %r" % (area or {"name": "test", "vnums": (0, 0)},))
    lines.append("ROOMS = %r" % (rooms or {},))
    lines.append("MOBILES = %r" % (mobiles or {},))
    lines.append("OBJECTS = %r" % (objects or {},))
    lines.append("RESETS = %r" % (resets or (),))
    lines.append("MOBPROGS = %r" % (mobprogs or {},))
    lines.append("OBJPROGS = %r" % (objprogs or {},))
    lines.append("ROOMPROGS = %r" % (roomprogs or {},))
    with open(path, "w") as f:
        f.write("\n".join(lines))


@pytest.fixture
def fresh_world(tmp_path):
    """Reset world module state and provide helpers for test area setup.

    Yields a namespace with:
        tmp_path: temp directory for area .txt files
        write_area_txt: helper to write synthetic area .txt files
        register_area: register an area in world internals
        setup: finalize registration (call after all register_area calls)
    """
    # Snapshot and clear world state (restored in full at teardown so a
    # later test lazily loading a real vnum via ITEM_DEFS[vnum] still works
    # regardless of run order -- see TODO.md Tests, resolved 06/07/2026)
    old_area_files = world._AREA_FILES[:]
    old_state = {
        "_LOADED_AREAS": set(world._LOADED_AREAS),
        "_TAG_TO_FILE": dict(world._TAG_TO_FILE),
        "_TAG_TO_NAME": dict(world._TAG_TO_NAME),
        "_VNUM_RANGES": list(world._VNUM_RANGES),
        "_pending_mob_saves": dict(world._pending_mob_saves),
        "_pending_room_items": dict(world._pending_room_items),
        "ITEM_SNAPSHOTS": dict(world.ITEM_SNAPSHOTS),
        "mob_stats": dict(world.mob_stats),
        "area_stats": dict(world.area_stats),
        "share_value": world.share_value,
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
        "FIGHTERS": set(world.FIGHTERS),
        "areas": list(world.areas),
        "_WORLD_READY": world._WORLD_READY,
    }

    world._LOADED_AREAS.clear()
    world._TAG_TO_FILE.clear()
    world._TAG_TO_NAME.clear()
    world._VNUM_RANGES.clear()
    world._pending_mob_saves.clear()
    world._pending_room_items.clear()
    world.ITEM_SNAPSHOTS.clear()
    # Derived caches over pending tokens / snapshot records: cleared both
    # here and at teardown, never snapshotted -- they rebuild on demand,
    # and stale entries could otherwise serve a previous test's template
    # for a reused vnum at the same CONTENT_REVISION.
    world._PENDING_VNUM_CACHE.clear()
    world._PENDING_MOB_CACHE.clear()
    world._SNAP_ENC_CACHE.clear()
    world.mob_stats.clear()
    world.area_stats.clear()
    world.share_value = 100
    world.ROOM_DEFS._data.clear()
    world.MOB_DEFS._data.clear()
    world.ITEM_DEFS._data.clear()
    world.DOOR_DEFS.clear()
    world.MOBPROGS.clear()
    world.OBJPROGS.clear()
    world.ROOMPROGS.clear()
    del world.AREA_DEFS[:]
    world.rooms._data.clear()
    world.chars.clear()
    world.FIGHTERS.clear()
    world.areas = []
    world._WORLD_READY = False
    world._area_seq.clear()
    world._player_room = None
    world._seq_counter = 0
    world._last_evict_area = None

    _area_entries = []

    class Ns:
        pass

    ns = Ns()
    ns.tmp_path = tmp_path

    def register_area(tag, vnum_lo, vnum_hi, rooms=None, mobiles=None,
                      objects=None, resets=None, area=None, mobprogs=None,
                      objprogs=None, roomprogs=None):
        fname = "area_%s.txt" % tag
        fpath = str(tmp_path / fname)
        _write_area_txt(fpath, rooms, mobiles, objects, resets, area,
                        mobprogs, objprogs, roomprogs)
        _area_entries.append((fpath, tag, tag, vnum_lo, vnum_hi))

    def setup():
        world._AREA_FILES[:] = _area_entries
        world._TAG_TO_FILE.clear()
        world._VNUM_RANGES.clear()
        for fpath, tag, name, lo, hi in _area_entries:
            world._TAG_TO_FILE[tag] = fpath
            world._TAG_TO_NAME[tag] = name
            world._VNUM_RANGES.append((lo, hi, tag))
        del world.AREA_DEFS[:]
        for _, tag, _, _, _ in _area_entries:
            world.AREA_DEFS.append({"tag": tag, "resets": []})
        world.areas = [{"tag": d["tag"], "age": 0} for d in world.AREA_DEFS]

    ns.register_area = register_area
    ns.setup = setup

    yield ns

    # Restore snapshots in place (module-level names are aliased elsewhere,
    # so mutate, don't rebind -- except world.areas, which world.py itself
    # rebinds)
    world._AREA_FILES[:] = old_area_files
    world._PENDING_VNUM_CACHE.clear()
    world._PENDING_MOB_CACHE.clear()
    world._SNAP_ENC_CACHE.clear()
    world._LOADED_AREAS.clear()
    world._LOADED_AREAS.update(old_state["_LOADED_AREAS"])
    for name in ("_TAG_TO_FILE", "_TAG_TO_NAME", "_pending_mob_saves",
                 "_pending_room_items", "ITEM_SNAPSHOTS",
                 "mob_stats", "area_stats",
                 "DOOR_DEFS", "MOBPROGS",
                 "OBJPROGS", "ROOMPROGS", "chars", "FIGHTERS"):
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
    # Restored tables make the snapshotted value safe again: if it was True,
    # lazy loading keeps working for later tests; if False, the next
    # init_world() rebuilds as usual.
    world._WORLD_READY = old_state["_WORLD_READY"]
    world.share_value = old_state["share_value"]
