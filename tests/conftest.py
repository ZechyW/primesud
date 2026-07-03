"""Test fixtures for PrimeSUD lazy area loading tests."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "primesud.hpappdir")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import pytest
from terminal import init_terminal
init_terminal()
import world


def _write_dat(path, rooms, mobiles=None, objects=None, resets=None,
               specials=None, shops=None, area=None):
    """Write a synthetic .dat file for testing."""
    lines = []
    lines.append("AREA = %r" % (area or {"name": "test", "vnums": (0, 0)},))
    lines.append("ROOMS = %r" % (rooms or {},))
    lines.append("MOBILES = %r" % (mobiles or {},))
    lines.append("OBJECTS = %r" % (objects or {},))
    lines.append("RESETS = %r" % (resets or (),))
    lines.append("SPECIALS = %r" % (specials or (),))
    lines.append("SHOPS = %r" % (shops or (),))
    with open(path, "w") as f:
        f.write("\n".join(lines))


@pytest.fixture
def fresh_world(tmp_path):
    """Reset world module state and provide helpers for test area setup.

    Yields a namespace with:
        tmp_path: temp directory for .dat files
        write_dat: helper to write synthetic .dat files
        register_area: register an area in world internals
        setup: finalize registration (call after all register_area calls)
    """
    # Snapshot and clear world state
    old_area_files = world._AREA_FILES[:]
    old_world_ready = world._WORLD_READY

    world._LOADED_AREAS.clear()
    world._TAG_TO_FILE.clear()
    world._TAG_TO_NAME.clear()
    world._VNUM_RANGES.clear()
    world._pending_mob_saves.clear()
    world._pending_room_items.clear()
    world.ROOM_DEFS._data.clear()
    world.MOB_DEFS._data.clear()
    world.ITEM_DEFS._data.clear()
    world.DOOR_DEFS.clear()
    del world.AREA_DEFS[:]
    world.rooms._data.clear()
    world.chars.clear()
    world.areas = []
    world._WORLD_READY = False

    _area_entries = []

    class Ns:
        pass

    ns = Ns()
    ns.tmp_path = tmp_path

    def register_area(tag, vnum_lo, vnum_hi, rooms=None, mobiles=None,
                      objects=None, resets=None, specials=None, shops=None,
                      area=None):
        fname = "area_%s.dat" % tag
        fpath = str(tmp_path / fname)
        _write_dat(fpath, rooms, mobiles, objects, resets, specials, shops, area)
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

    # Restore
    world._AREA_FILES[:] = old_area_files
    world._LOADED_AREAS.clear()
    world._TAG_TO_FILE.clear()
    world._TAG_TO_NAME.clear()
    world._VNUM_RANGES.clear()
    world._pending_mob_saves.clear()
    world._pending_room_items.clear()
    world.ROOM_DEFS._data.clear()
    world.MOB_DEFS._data.clear()
    world.ITEM_DEFS._data.clear()
    world.DOOR_DEFS.clear()
    del world.AREA_DEFS[:]
    world.rooms._data.clear()
    world.chars.clear()
    world.areas = []
    world._WORLD_READY = old_world_ready
