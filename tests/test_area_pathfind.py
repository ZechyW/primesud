"""Tests for border-graph run pathfinding and the zero-load do_areas render.

Covers:
- find_path_to_area: border-graph routing wrapper (exact shortest route,
  zero area loads at routing time)
- do_areas: renders purely from static tables, never triggers an area load
[PRIMESUD]
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import world
import info
import movement
from handler import _char_base
from world import ROOM_DEFS
from info import find_path_to_area, do_areas

sys.path.insert(0, os.path.join(ROOT, "tools"))
from build_path_index import build_records


def _write_index(tmp_path, monkeypatch, rooms_data):
    """Build a border-graph index from raw room dicts and point info at it."""
    lines = build_records(rooms_data)
    idx = tmp_path / "paths.idx"
    idx.write_text("# test index\n" + "\n".join(lines) + "\n")
    monkeypatch.setattr(info, "PATH_INDEX_FILE", str(idx))


# ===== do_areas: zero-load rendering ========================================

class TestDoAreasZeroLoad:
    """do_areas must render purely from static tables -- no area loads."""

    def test_no_area_loads_and_renders_all(self, fresh_world, monkeypatch):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}})
        fw.register_area("beta", 200, 299,
                         rooms={200: {"name": "R200", "exits": {}}})
        fw.setup()
        monkeypatch.setattr(world, "AREA_LEVELS",
                            {"alpha": (1, 10), "beta": (5, 15)})
        monkeypatch.setattr(world, "AREA_BUILDERS",
                            {"alpha": "Bob", "beta": "Amy"})

        # Player has no room set (fresh char) -- exercises the same
        # "safe zero-load lookup" path as a loaded room would, without
        # needing to load anything to prove the point.
        player = _char_base()
        lines = []
        monkeypatch.setattr(info, "chprintln", lambda p, s="": lines.append(s))

        assert world._LOADED_AREAS == set()
        do_areas(player, [])
        assert world._LOADED_AREAS == set()

        joined = "\n".join(lines)
        assert "alpha" in joined
        assert "beta" in joined
        assert "2 areas found" in joined

    def test_current_area_marked_without_new_loads(self, fresh_world, monkeypatch):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}})
        fw.register_area("beta", 200, 299,
                         rooms={200: {"name": "R200", "exits": {}}})
        fw.setup()
        monkeypatch.setattr(world, "AREA_LEVELS",
                            {"alpha": (1, 10), "beta": (5, 15)})
        monkeypatch.setattr(world, "AREA_BUILDERS",
                            {"alpha": "Bob", "beta": "Amy"})

        # Player already standing in alpha, as in real play (current
        # room is always loaded before any command handler runs).
        player = _char_base()
        player["room"] = 100
        _ = ROOM_DEFS[100]
        before = set(world._LOADED_AREAS)
        assert before == {"alpha"}

        lines = []
        monkeypatch.setattr(info, "chprintln", lambda p, s="": lines.append(s))
        do_areas(player, [])

        # beta stays unloaded -- do_areas itself never loads anything.
        assert world._LOADED_AREAS == before

        alpha_line = next(l for l in lines if "alpha" in l)
        beta_line = next(l for l in lines if "beta" in l)
        assert "{G>{x" in alpha_line
        assert "{G>{x" not in beta_line


# ===== level-comment areas ("All"/"None") ===================================

class TestAreaLevelComments:
    """Areas with a non-numeric credits token show it verbatim in the level
    slot (cf. 1stMud print_area_levels lvl_comment branch in db.c)."""

    def test_print_area_levels_comment_centered_in_7(self):
        # 1stMud str_align(7, Center, ...): left pad (7-len)//2, right
        # fill comes from the caller's %-7s.
        assert info._print_area_levels((1, 60), "None") == " None"
        assert info._print_area_levels((1, 50), "All") == "  All"

    def test_print_area_levels_no_comment_unchanged(self):
        assert info._print_area_levels((1, 10)) == "001 010"

    def test_do_areas_shows_comment_token(self, fresh_world, monkeypatch):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}})
        fw.setup()
        monkeypatch.setattr(world, "AREA_LEVELS", {"alpha": (1, 60)})
        monkeypatch.setattr(world, "AREA_BUILDERS", {"alpha": "Bob"})
        monkeypatch.setattr(world, "AREA_LVL_COMMENTS", {"alpha": "None"})

        player = _char_base()
        lines = []
        monkeypatch.setattr(info, "chprintln", lambda p, s="": lines.append(s))
        do_areas(player, [])

        alpha_line = next(l for l in lines if "alpha" in l)
        assert "None" in alpha_line
        assert "001" not in alpha_line


# ===== find_path_to_area: synthetic border-graph routing ====================

class TestFindPathToAreaBorderGraph:
    """Wrapper over info._route: exact routes, zero loads at routing time."""

    def test_route_found_without_loading_target_area(
            self, fresh_world, monkeypatch):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {"n": 101}},
                                101: {"name": "R101", "exits": {"e": 200}}})
        fw.register_area("beta", 200, 299,
                         rooms={200: {"name": "R200", "exits": {}}})
        fw.setup()
        _write_index(fw.tmp_path, monkeypatch, {
            100: {"area": "alpha", "exits": {"n": 101}},
            101: {"area": "alpha", "exits": {"e": 200}},
            200: {"area": "beta", "exits": {}},
        })

        ch = _char_base()
        ch["room"] = 100
        _ = ROOM_DEFS[100]

        buf = find_path_to_area(ch, "beta")

        assert buf == "ne"
        assert world._LOADED_AREAS == {"alpha"}, \
            "routing must load nothing beyond the source area"

    def test_unreachable_returns_none_without_any_loads(
            self, fresh_world, monkeypatch):
        """No cross-area exit out of alpha -> None, nothing loaded."""
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}})
        fw.register_area("beta", 200, 299,
                         rooms={200: {"name": "R200", "exits": {}}})
        fw.setup()
        _write_index(fw.tmp_path, monkeypatch, {
            100: {"area": "alpha", "exits": {}},
            200: {"area": "beta", "exits": {}},
        })

        ch = _char_base()
        ch["room"] = 100
        _ = ROOM_DEFS[100]
        before = set(world._LOADED_AREAS)

        buf = find_path_to_area(ch, "beta")

        assert buf is None
        assert world._LOADED_AREAS == before, \
            "unreachable target must load nothing new"

    def test_current_area_returns_none(self, fresh_world, monkeypatch):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}})
        fw.setup()
        _write_index(fw.tmp_path, monkeypatch, {
            100: {"area": "alpha", "exits": {}},
        })

        ch = _char_base()
        ch["room"] = 100
        _ = ROOM_DEFS[100]

        assert find_path_to_area(ch, "alpha") is None


# ===== find_path_to_area: real area data (e2e) ==============================

@pytest.fixture
def real_world():
    """Load the real stock area tables for one test, restoring all mutable
    world state afterward.  Unlike the `fresh_world` fixture (conftest.py)
    this keeps the real world._AREA_FILES/_AREA_ADJ/etc -- it only snapshots
    and restores the *mutable* lazy-loading state so tests in other files
    that run later in the same session don't see areas we loaded here.
    [PRIMESUD]
    """
    old_state = {
        "_LOADED_AREAS": set(world._LOADED_AREAS),
        "_pending_mob_saves": dict(world._pending_mob_saves),
        "_pending_room_items": dict(world._pending_room_items),
        "ROOM_DEFS": dict(world.ROOM_DEFS._data),
        "MOB_DEFS": dict(world.MOB_DEFS._data),
        "ITEM_DEFS": dict(world.ITEM_DEFS._data),
        "DOOR_DEFS": dict(world.DOOR_DEFS),
        "AREA_DEFS": list(world.AREA_DEFS),
        "rooms": dict(world.rooms._data),
        "chars": dict(world.chars),
        "areas": list(world.areas),
        "_WORLD_READY": world._WORLD_READY,
    }

    world.init_world()
    world.reset_lazy()

    try:
        yield
    finally:
        world._LOADED_AREAS.clear()
        world._LOADED_AREAS.update(old_state["_LOADED_AREAS"])
        world._pending_mob_saves.clear()
        world._pending_mob_saves.update(old_state["_pending_mob_saves"])
        world._pending_room_items.clear()
        world._pending_room_items.update(old_state["_pending_room_items"])
        world.DOOR_DEFS.clear()
        world.DOOR_DEFS.update(old_state["DOOR_DEFS"])
        world.chars.clear()
        world.chars.update(old_state["chars"])
        world.AREA_DEFS[:] = old_state["AREA_DEFS"]
        for name in ("ROOM_DEFS", "MOB_DEFS", "ITEM_DEFS"):
            d = getattr(world, name)._data
            d.clear()
            d.update(old_state[name])
        world.rooms._data.clear()
        world.rooms._data.update(old_state["rooms"])
        world.areas = old_state["areas"]
        world._WORLD_READY = old_state["_WORLD_READY"]


class TestFindPathToAreaRealData:
    """cf. task example: midgaard -> shire via the real stock area files.

    Uses the real committed src/paths.idx (the suite runs with cwd == src/,
    so the default PATH_INDEX_FILE resolves). The route avoids the
    randomized-exit rooms (hitower's Shadow Grove, the daycare maze), so
    the index's frozen maze layout can't diverge from this world load.
    """

    def test_midgaard_to_shire_loads_nothing_and_path_is_walkable(self, real_world):
        ch = _char_base()
        ch["room"] = 3001  # Temple of Mota (cf. config.R_RECALL)
        _ = ROOM_DEFS[3001]  # player's current room is always loaded

        buf = find_path_to_area(ch, "shire")

        assert buf is not None
        # Border-graph routing loads no areas at all -- only the source
        # area (loaded because the player stands in it) is resident.
        assert world._LOADED_AREAS == {"midgaard"}

        steps = movement._parse_run_buf(buf)
        assert steps is not None

        # Walking the route lazily loads areas along it, like a real run.
        cur = 3001
        for action, d in steps:
            assert action == "move"
            room = ROOM_DEFS[cur]
            ev = room["exits"][d]
            cur = ev["to"] if isinstance(ev, dict) else ev
        assert ROOM_DEFS[cur].get("area") == "shire"
