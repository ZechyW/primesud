"""Tests for lazy area-graph pathfinding and the zero-load do_areas render.

Covers:
- _area_chain: pure BFS helper over the static area-adjacency graph
- find_path_to_area: staged lazy pathfinder (area-graph BFS -> chain load
  -> restricted room BFS -> load-all fallback)
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
from info import _area_chain, find_path_to_area, do_areas


# ===== _area_chain (pure helper) ============================================

class TestAreaChain:
    """Zero-load BFS over a static {tag: neighbor_tuple} graph."""

    def test_source_equals_target(self):
        assert _area_chain("a", "a", {}) == ["a"]

    def test_direct_neighbor(self):
        adj = {"a": ("b",), "b": ()}
        assert _area_chain("a", "b", adj) == ["a", "b"]

    def test_multi_hop(self):
        adj = {"a": ("b",), "b": ("c",), "c": ()}
        assert _area_chain("a", "c", adj) == ["a", "b", "c"]

    def test_unreachable(self):
        adj = {"a": ("b",), "b": (), "c": ()}
        assert _area_chain("a", "c", adj) is None

    def test_unknown_source_has_no_edges(self):
        adj = {"b": ()}
        assert _area_chain("a", "b", adj) is None

    def test_prefers_first_listed_neighbor_on_tie(self):
        # a -> b, c both lead to d in one more hop; "b" is listed first
        # in a's neighbor tuple, so BFS discovers d via b first.
        adj = {"a": ("b", "c"), "b": ("d",), "c": ("d",), "d": ()}
        assert _area_chain("a", "d", adj) == ["a", "b", "d"]

    def test_deterministic_across_repeated_calls(self):
        adj = {"a": ("c", "b"), "b": ("d",), "c": ("d",), "d": ()}
        results = {tuple(_area_chain("a", "d", adj)) for _ in range(5)}
        assert results == {("a", "c", "d")}


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


# ===== find_path_to_area: synthetic fallback ================================

class TestFindPathToAreaFallback:
    """Stage 4: restricted room BFS can't complete the area-graph chain."""

    def test_falls_back_when_restricted_bfs_cannot_complete_chain(
            self, fresh_world, monkeypatch):
        fw = fresh_world
        # alpha's only room has no exits at all, so the room-level BFS
        # can never reach beta even though the area graph claims an
        # edge -- mirrors a real one-way-exit situation where the graph
        # edge exists (recorded from the *other* direction) but isn't
        # walkable from this particular room.
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}})
        fw.register_area("beta", 200, 299,
                         rooms={200: {"name": "R200", "exits": {}}})
        fw.setup()
        monkeypatch.setattr(world, "_AREA_ADJ", {"alpha": ("beta",), "beta": ()})

        ch = _char_base()
        ch["room"] = 100
        _ = ROOM_DEFS[100]

        calls = []
        monkeypatch.setattr(
            info, "find_area_paths",
            lambda ch: calls.append(1) or {"beta": "5n"})
        lines = []
        monkeypatch.setattr(info, "chprintln", lambda p, s="": lines.append(s))

        buf = find_path_to_area(ch, "beta")

        assert calls == [1], "fallback should call find_area_paths exactly once"
        assert buf == "5n"
        assert any("Loading all area paths" in l for l in lines)

    def test_no_chain_returns_none_without_any_loads(self, fresh_world, monkeypatch):
        """No area-graph edge at all -> bail out before loading anything."""
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}})
        fw.register_area("beta", 200, 299,
                         rooms={200: {"name": "R200", "exits": {}}})
        fw.setup()
        monkeypatch.setattr(world, "_AREA_ADJ", {"alpha": (), "beta": ()})

        ch = _char_base()
        ch["room"] = 100
        _ = ROOM_DEFS[100]
        before = set(world._LOADED_AREAS)

        buf = find_path_to_area(ch, "beta")

        assert buf is None
        assert world._LOADED_AREAS == before, "unreachable chain must load nothing new"


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
    old_cwd = os.getcwd()
    os.chdir(os.path.join(ROOT, "src"))

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
        os.chdir(old_cwd)


class TestFindPathToAreaRealData:
    """cf. task example: midgaard -> shire via the real stock area files."""

    def test_midgaard_to_shire_loads_chain_only_and_path_is_walkable(self, real_world):
        ch = _char_base()
        ch["room"] = 3001  # Temple of Mota (cf. config.R_RECALL)
        _ = ROOM_DEFS[3001]  # player's current room is always loaded

        buf = find_path_to_area(ch, "shire")

        assert buf is not None
        # The area-graph chain (midgaard -> haon -> shire) got loaded...
        assert {"midgaard", "haon", "shire"} <= world._LOADED_AREAS
        # ...but this did not fall back to loading every area. (Loading
        # haon/shire can cross-area-reset-cascade in a couple of extra
        # areas beyond the chain -- that's pre-existing world.py
        # behavior, not part of the pathfinding search itself.)
        assert len(world._LOADED_AREAS) < len(world._AREA_FILES)
        assert "tohell" not in world._LOADED_AREAS
        assert "newthalos" not in world._LOADED_AREAS

        steps = movement._parse_run_buf(buf)
        assert steps is not None

        cur = 3001
        for action, d in steps:
            assert action == "move"
            room = ROOM_DEFS[cur]
            ev = room["exits"][d]
            cur = ev["to"] if isinstance(ev, dict) else ev
        assert ROOM_DEFS[cur].get("area") == "shire"
