"""Test fixtures for PrimeSUD lazy area loading tests."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import pytest
from terminal import init_terminal
init_terminal()
import world


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
    world.MOBPROGS.clear()
    world.OBJPROGS.clear()
    world.ROOMPROGS.clear()
    del world.AREA_DEFS[:]
    world.rooms._data.clear()
    world.chars.clear()
    world.areas = []
    world._WORLD_READY = False
    world._area_seq.clear()
    world._player_room = None
    world._seq_counter = 0

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
    # Restored tables make the snapshotted value safe again: if it was True,
    # lazy loading keeps working for later tests; if False, the next
    # init_world() rebuilds as usual.
    world._WORLD_READY = old_state["_WORLD_READY"]
