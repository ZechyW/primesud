"""Tests for border-graph path routing. [PRIMESUD]"""

import os
import sys

import pytest

import config
import info
import movement
import path as path_cmd
import world
from handler import _char_base
from world import MOB_DEFS, ROOM_DEFS

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
from build_path_index import build_records


def _write_index(tmp_path, monkeypatch, rooms_data):
    """Build a border-graph index from raw room dicts and point path at it.

    rooms_data mirrors ROOM_DEFS._data shape: {vnum: {"area": tag,
    "exits": {dir: to_vnum}}}. Pure build_records call -- no area loads,
    so _LOADED_AREAS assertions in tests stay meaningful.
    """
    lines = build_records(rooms_data)
    idx = tmp_path / "paths.idx"
    idx.write_text("# test index\n" + "\n".join(lines) + "\n")
    monkeypatch.setattr(info, "PATH_INDEX_FILE", str(idx))


def _setup_chain(fw, monkeypatch, tags):
    """Register a linear n-exit chain of single-room areas + its index."""
    rooms_data = {}
    for i, tag in enumerate(tags):
        vnum = (i + 1) * 100
        exits = {"n": vnum + 100} if i + 1 < len(tags) else {}
        fw.register_area(tag, vnum, vnum + 99,
                         rooms={vnum: {"name": tag, "exits": exits}})
        rooms_data[vnum] = {"area": tag, "exits": exits}
    fw.setup()
    _write_index(fw.tmp_path, monkeypatch, rooms_data)


def _player(room=100, level=20):
    player = _char_base()
    player.update({"id": 1, "name": "Tester", "room": room,
                   "level": level})
    return player


def test_area_path_loads_nothing_beyond_source_area(fresh_world, monkeypatch):
    _setup_chain(fresh_world, monkeypatch, ("alpha", "beta", "gamma"))
    monkeypatch.setattr(config, "AREA_CACHE_MAX", 2)
    player = _player()
    _ = ROOM_DEFS[100]
    out = []
    monkeypatch.setattr(path_cmd, "chprintln",
                        lambda _ch, text="": out.append(text))

    path_cmd.do_path(player, ["gam"])

    assert out == ["{D[Calculating path...]{x",
                   "Shortest path to gamma is 2 steps: 2n."]
    assert world._LOADED_AREAS == {"alpha"}


def test_mob_path_uses_index_fallback_and_actual_room(fresh_world, monkeypatch):
    fw = fresh_world
    fw.register_area("alpha", 100, 199,
                     rooms={100: {"name": "alpha", "exits": {"n": 200}}})
    fw.register_area("beta", 200, 299,
                     rooms={200: {"name": "beta", "exits": {"e": 201}},
                            201: {"name": "lair", "exits": {}}})
    fw.setup()
    _write_index(fw.tmp_path, monkeypatch, {
        100: {"area": "alpha", "exits": {"n": 200}},
        200: {"area": "beta", "exits": {"e": 201}},
        201: {"area": "beta", "exits": {}},
    })
    player = _player()
    _ = ROOM_DEFS[100]
    mob = _char_base()
    mob.update({"id": 2, "is_npc": True, "tpl": 250,
                "room": 201, "level": 10})
    calls = []

    def find_mob(argument, _ch):
        calls.append(argument)
        world._ensure_area_by_tag("beta")
        MOB_DEFS._data[250] = {"keywords": "red dragon",
                               "short_descr": "a red dragon"}
        world.chars[2] = mob
        return 2, mob

    monkeypatch.setattr(path_cmd, "_find_unloaded_mob", find_mob)
    out = []
    monkeypatch.setattr(path_cmd, "chprintln",
                        lambda _ch, text="": out.append(text))

    path_cmd.do_path(player, ["dragon"])

    assert calls == ["dragon"]
    assert out == ["{D[Calculating path...]{x",
                   "Shortest path to a red dragon is 2 steps: ne."]


def test_path_no_args_prints_syntax(fresh_world, monkeypatch):
    _setup_chain(fresh_world, monkeypatch, ("alpha",))
    player = _player()
    out = []
    monkeypatch.setattr(path_cmd, "chprintln",
                        lambda _ch, text="": out.append(text))

    path_cmd.do_path(player, [])

    assert out == ["Syntax: path <destination mob or area>"]


def test_area_path_to_current_area_needs_no_walk(fresh_world, monkeypatch):
    _setup_chain(fresh_world, monkeypatch, ("alpha", "beta"))
    player = _player()
    _ = ROOM_DEFS[100]
    out = []
    monkeypatch.setattr(path_cmd, "chprintln",
                        lambda _ch, text="": out.append(text))

    path_cmd.do_path(player, ["alp"])

    assert out == ["{D[Calculating path...]{x",
                   "No need to walk to get there!"]


def test_mob_path_in_current_room_needs_no_walk(fresh_world, monkeypatch):
    _setup_chain(fresh_world, monkeypatch, ("alpha",))
    player = _player()
    _ = ROOM_DEFS[100]
    MOB_DEFS._data[150] = {"keywords": "red dragon",
                           "short_descr": "a red dragon"}
    mob = _char_base()
    mob.update({"id": 2, "is_npc": True, "tpl": 150,
                "room": 100, "level": 10})
    world.chars[2] = mob
    out = []
    monkeypatch.setattr(path_cmd, "chprintln",
                        lambda _ch, text="": out.append(text))

    path_cmd.do_path(player, ["dragon"])

    assert out == ["{D[Calculating path...]{x",
                   "No need to walk to get there!"]


def test_mob_path_within_current_area(fresh_world, monkeypatch):
    fw = fresh_world
    fw.register_area("alpha", 100, 199,
                     rooms={100: {"name": "alpha", "exits": {"n": 101}},
                            101: {"name": "lair", "exits": {}}})
    fw.setup()
    _write_index(fw.tmp_path, monkeypatch, {
        100: {"area": "alpha", "exits": {"n": 101}},
        101: {"area": "alpha", "exits": {}},
    })
    player = _player()
    _ = ROOM_DEFS[100]
    MOB_DEFS._data[150] = {"keywords": "red dragon",
                           "short_descr": "a red dragon"}
    mob = _char_base()
    mob.update({"id": 2, "is_npc": True, "tpl": 150,
                "room": 101, "level": 10})
    world.chars[2] = mob
    out = []
    monkeypatch.setattr(path_cmd, "chprintln",
                        lambda _ch, text="": out.append(text))

    path_cmd.do_path(player, ["dragon"])

    assert out == ["{D[Calculating path...]{x",
                   "Shortest path to a red dragon is 1 step: n."]


def test_mob_path_invisible_mob_hidden_without_detect(fresh_world, monkeypatch):
    _setup_chain(fresh_world, monkeypatch, ("alpha",))
    player = _player()
    _ = ROOM_DEFS[100]
    MOB_DEFS._data[150] = {"keywords": "red dragon",
                           "short_descr": "a red dragon"}
    mob = _char_base()
    mob.update({"id": 2, "is_npc": True, "tpl": 150, "room": 100,
                "level": 10, "affected_by": {"invisible": True}})
    world.chars[2] = mob
    monkeypatch.setattr(path_cmd, "_find_unloaded_mob",
                        lambda _arg, _ch: (None, None))
    out = []
    monkeypatch.setattr(path_cmd, "chprintln",
                        lambda _ch, text="": out.append(text))

    path_cmd.do_path(player, ["dragon"])
    assert out == ["{D[Calculating path...]{x", "No such destination."]

    # detect invis restores get_char_world visibility
    player["affected_by"] = {"detect_invis": True}
    out[:] = []
    path_cmd.do_path(player, ["dragon"])
    assert out == ["{D[Calculating path...]{x",
                   "No need to walk to get there!"]


def test_area_path_unreachable_reports_no_path(fresh_world, monkeypatch):
    fw = fresh_world
    fw.register_area("alpha", 100, 199,
                     rooms={100: {"name": "alpha", "exits": {}}})
    fw.register_area("beta", 200, 299,
                     rooms={200: {"name": "beta", "exits": {}}})
    fw.setup()
    _write_index(fw.tmp_path, monkeypatch, {
        100: {"area": "alpha", "exits": {}},
        200: {"area": "beta", "exits": {}},
    })
    player = _player()
    _ = ROOM_DEFS[100]
    out = []
    monkeypatch.setattr(path_cmd, "chprintln",
                        lambda _ch, text="": out.append(text))

    path_cmd.do_path(player, ["bet"])

    assert out == ["{D[Calculating path...]{x", "No path to destination."]


def test_mob_path_applies_fixed_level_restriction(fresh_world, monkeypatch):
    _setup_chain(fresh_world, monkeypatch, ("alpha", "beta"))
    player = _player()
    _ = ROOM_DEFS[100]
    world._ensure_area_by_tag("beta")
    MOB_DEFS._data[250] = {"keywords": "red dragon",
                           "short_descr": "a red dragon"}
    mob = _char_base()
    mob.update({"id": 2, "is_npc": True, "tpl": 250,
                "room": 200, "level": 23})
    world.chars[2] = mob
    out = []
    monkeypatch.setattr(path_cmd, "chprintln",
                        lambda _ch, text="": out.append(text))

    path_cmd.do_path(player, ["dragon"])

    assert out == ["{D[Calculating path...]{x", "No such destination."]


def test_mob_path_is_deterministic(fresh_world, monkeypatch):
    """[PRIMESUD] 1stMud's saves_spell gate is dropped: an eligible mob routes
    every time, never a coin flip.  A magic-immune mob (IS_IMMUNE to DAM_OTHER,
    which used to save unconditionally) must route too."""
    _setup_chain(fresh_world, monkeypatch, ("alpha", "beta"))
    player = _player()
    _ = ROOM_DEFS[100]
    world._ensure_area_by_tag("beta")
    MOB_DEFS._data[250] = {"keywords": "red dragon",
                           "short_descr": "a red dragon"}
    mob = _char_base()
    mob.update({"id": 2, "is_npc": True, "tpl": 250, "room": 200,
                "level": 10, "imm_flags": {"magic": True}})
    world.chars[2] = mob
    out = []
    monkeypatch.setattr(path_cmd, "chprintln",
                        lambda _ch, text="": out.append(text))

    for _ in range(30):
        out[:] = []
        path_cmd.do_path(player, ["dragon"])
        assert out == ["{D[Calculating path...]{x",
                       "Shortest path to a red dragon is 1 step: n."]


def _register_partitioned_world(fw, monkeypatch):
    """Areas where B is internally split: a1 -> b1, b2 -> c1, and the only
    b1 -> b2 link detours through D (b1 -> d1 -> b2). The old area-level
    corridor found no route; the border graph must find a1-b1-d1-b2-c1."""
    layout = {
        100: ("aye", {"n": 200}),
        200: ("bee", {"e": 400}),
        201: ("bee", {"s": 300}),
        300: ("cee", {}),
        400: ("dee", {"w": 201}),
    }
    bounds = {"aye": (100, 199), "bee": (200, 299),
              "cee": (300, 399), "dee": (400, 499)}
    by_area = {}
    rooms_data = {}
    for vnum, (tag, exits) in layout.items():
        by_area.setdefault(tag, {})[vnum] = {"name": tag, "exits": exits}
        rooms_data[vnum] = {"area": tag, "exits": exits}
    for tag, rooms in by_area.items():
        lo, hi = bounds[tag]
        fw.register_area(tag, lo, hi, rooms=rooms)
    fw.setup()
    _write_index(fw.tmp_path, monkeypatch, rooms_data)


def test_area_path_through_partitioned_area(fresh_world, monkeypatch):
    _register_partitioned_world(fresh_world, monkeypatch)
    player = _player()
    _ = ROOM_DEFS[100]
    out = []
    monkeypatch.setattr(path_cmd, "chprintln",
                        lambda _ch, text="": out.append(text))

    path_cmd.do_path(player, ["cee"])

    assert out == ["{D[Calculating path...]{x",
                   "Shortest path to cee is 4 steps: news."]


def test_mob_path_through_partitioned_area(fresh_world, monkeypatch):
    _register_partitioned_world(fresh_world, monkeypatch)
    player = _player()
    _ = ROOM_DEFS[100]
    world._ensure_area_by_tag("cee")
    MOB_DEFS._data[350] = {"keywords": "red dragon",
                           "short_descr": "a red dragon"}
    mob = _char_base()
    mob.update({"id": 2, "is_npc": True, "tpl": 350,
                "room": 300, "level": 10})
    world.chars[2] = mob
    out = []
    monkeypatch.setattr(path_cmd, "chprintln",
                        lambda _ch, text="": out.append(text))

    path_cmd.do_path(player, ["dragon"])

    assert out == ["{D[Calculating path...]{x",
                   "Shortest path to a red dragon is 4 steps: news."]


def test_route_merges_direction_runs_across_boundaries(
        fresh_world, monkeypatch):
    fw = fresh_world
    fw.register_area("alpha", 100, 199,
                     rooms={100: {"name": "a1", "exits": {"n": 101}},
                            101: {"name": "a2", "exits": {"n": 102}},
                            102: {"name": "a3", "exits": {"n": 200}}})
    fw.register_area("beta", 200, 299,
                     rooms={200: {"name": "beta", "exits": {}}})
    fw.setup()
    _write_index(fw.tmp_path, monkeypatch, {
        100: {"area": "alpha", "exits": {"n": 101}},
        101: {"area": "alpha", "exits": {"n": 102}},
        102: {"area": "alpha", "exits": {"n": 200}},
        200: {"area": "beta", "exits": {}},
    })
    player = _player()
    _ = ROOM_DEFS[100]
    out = []
    monkeypatch.setattr(path_cmd, "chprintln",
                        lambda _ch, text="": out.append(text))

    path_cmd.do_path(player, ["bet"])

    # source leg "2n" + cross-area "n" merge into a single "3n" run
    assert out == ["{D[Calculating path...]{x",
                   "Shortest path to beta is 3 steps: 3n."]


def test_path_result_leads_run_picker(fresh_world, monkeypatch):
    """[PRIMESUD] do_path hands its route to the no-args `run` picker as the
    default entry, and it expires the moment the player leaves the room it
    was computed in."""
    _setup_chain(fresh_world, monkeypatch, ("alpha", "beta", "gamma"))
    player = _player()
    monkeypatch.setattr(path_cmd, "chprintln", lambda _ch, text="": None)
    monkeypatch.setattr(movement, "chprintln", lambda _ch, text="": None)
    monkeypatch.setattr(movement, "find_path_to_area",
                        lambda *_a: pytest.fail("stored route was re-routed"))
    shown = []
    picked = [0]

    def fake_pick(title, labels, *_a):
        shown.append((title, labels))
        return picked[0]

    monkeypatch.setattr(movement, "pick_from", fake_pick)

    path_cmd.do_path(player, ["gam"])
    assert player["last_path"] == ("gamma", "2n", 2, 100)

    movement.do_run(player, [])
    assert shown[0][0] == "Run where?"
    assert shown[0][1][0] == "{Cgamma{x (2 steps)"
    assert player["run_buf"] == [("move", "n"), ("move", "n")]

    # Route is only valid from where it was computed: one room on, it is gone
    # and the picker is areas-only again.
    movement.free_runbuf(player)
    player["room"] = 200
    picked[0] = -1

    movement.do_run(player, [])
    assert shown[1][0] == "Run to which area?"
    assert not any(label.startswith("{C") for label in shown[1][1])


def test_run_picker_offers_route_with_no_areas(fresh_world, monkeypatch):
    """[PRIMESUD] A stored route keeps the `run` picker alive even when it is
    the only entry -- a lone area has no other area to offer."""
    _setup_chain(fresh_world, monkeypatch, ("alpha", "beta"))
    player = _player()
    monkeypatch.setattr(path_cmd, "chprintln", lambda _ch, text="": None)
    out = []
    monkeypatch.setattr(movement, "chprintln",
                        lambda _ch, text="": out.append(text))
    shown = []
    monkeypatch.setattr(movement, "pick_from",
                        lambda title, labels, *_a: shown.append((title, labels)) or 0)

    path_cmd.do_path(player, ["bet"])
    # Empty the area list only after routing: _area_lookup needs beta to
    # resolve the target.
    monkeypatch.setattr(movement, "_sorted_area_files", lambda: [])
    movement.do_run(player, [])

    assert shown == [("Run where?", ["{Cbeta{x (1 step)"])]
    assert player["run_buf"] == [("move", "n")]

    # Without the route it is the "nowhere to go" message again.
    movement.free_runbuf(player)
    del player["last_path"]
    movement.do_run(player, [])
    assert out[-1] == "No accessible areas from here."


def test_merge_runs_unit():
    assert info._merge_runs(["2n", "n"]) == "3n"
    assert info._merge_runs(["3n2e", "2e", "s"]) == "3n4es"
    assert info._merge_runs(["", "n", ""]) == "n"
    assert info._merge_runs([]) == ""
