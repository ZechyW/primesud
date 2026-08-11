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
    assert out == ["{D[Calculating path...]{x",
                   "No mob or area by that name."]

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

    assert out == ["{D[Calculating path...]{x",
                   "You cannot sense a path to so powerful a creature."]


def _mob_in_beta(fw, monkeypatch, tags=("alpha", "beta"), level=10,
                 room=200, tpl=250):
    """Chain of areas plus a visible mob parked in the second one. [PRIMESUD]"""
    _setup_chain(fw, monkeypatch, tags)
    _ = ROOM_DEFS[100]
    world._ensure_area_by_tag(tags[1])
    MOB_DEFS._data[tpl] = {"keywords": "red dragon",
                           "short_descr": "a red dragon"}
    mob = _char_base()
    mob.update({"id": 2, "is_npc": True, "tpl": tpl,
                "room": room, "level": level})
    world.chars[2] = mob
    return mob


def test_mob_path_unknown_keyword_names_the_bucket(fresh_world, monkeypatch):
    """[PRIMESUD] Upstream's single vague failure is split per reason."""
    _setup_chain(fresh_world, monkeypatch, ("alpha", "beta"))
    player = _player()
    _ = ROOM_DEFS[100]
    monkeypatch.setattr(path_cmd, "_find_unloaded_mob",
                        lambda _arg, _ch: (None, None))
    out = []
    monkeypatch.setattr(path_cmd, "chprintln",
                        lambda _ch, text="": out.append(text))

    path_cmd.do_path(player, ["wombat"])

    assert out == ["{D[Calculating path...]{x",
                   "No mob or area by that name."]


def test_mob_path_no_recall_room_blames_the_room(fresh_world, monkeypatch):
    """[PRIMESUD] A no_recall source room blocks pathing to anything, so it
    outranks every mob-side reason."""
    fw = fresh_world
    fw.register_area("alpha", 100, 199,
                     rooms={100: {"name": "alpha", "exits": {"n": 200},
                                  "flags": {"no_recall": True}}})
    fw.register_area("beta", 200, 299,
                     rooms={200: {"name": "beta", "exits": {}}})
    fw.setup()
    _write_index(fw.tmp_path, monkeypatch, {
        100: {"area": "alpha", "exits": {"n": 200}},
        200: {"area": "beta", "exits": {}},
    })
    player = _player()
    _ = ROOM_DEFS[100]
    world._ensure_area_by_tag("beta")
    MOB_DEFS._data[250] = {"keywords": "red dragon",
                           "short_descr": "a red dragon"}
    mob = _char_base()
    mob.update({"id": 2, "is_npc": True, "tpl": 250,
                "room": 200, "level": 10})
    world.chars[2] = mob
    out = []
    monkeypatch.setattr(path_cmd, "chprintln",
                        lambda _ch, text="": out.append(text))

    path_cmd.do_path(player, ["dragon"])

    assert out == ["{D[Calculating path...]{x",
                   "Magic here prevents you from sensing a path."]


def test_mob_path_gquest_target_is_named_as_quest(fresh_world, monkeypatch):
    """[PRIMESUD] gquest targets stay unpathable, but the player is told why."""
    _mob_in_beta(fresh_world, monkeypatch)
    player = _player()
    monkeypatch.setattr(path_cmd, "gq_is_target", lambda vnum: vnum == 250)
    out = []
    monkeypatch.setattr(path_cmd, "chprintln",
                        lambda _ch, text="": out.append(text))

    path_cmd.do_path(player, ["dragon"])

    assert out == ["{D[Calculating path...]{x",
                   "You must track down quest targets on your own."]


def test_mob_path_own_quest_mob_is_named_as_quest(fresh_world, monkeypatch):
    """[PRIMESUD] Same message for the player's personal quest target."""
    _mob_in_beta(fresh_world, monkeypatch)
    player = _player()
    player["quest_mob"] = 250
    monkeypatch.setattr(path_cmd, "is_quester", lambda _ch: True)
    out = []
    monkeypatch.setattr(path_cmd, "chprintln",
                        lambda _ch, text="": out.append(text))

    path_cmd.do_path(player, ["dragon"])

    assert out == ["{D[Calculating path...]{x",
                   "You must track down quest targets on your own."]


def test_mob_path_safe_room_falls_in_vague_bucket(fresh_world, monkeypatch):
    """[PRIMESUD] Gates with no player-actionable cause keep a vague message."""
    fw = fresh_world
    fw.register_area("alpha", 100, 199,
                     rooms={100: {"name": "alpha", "exits": {"n": 200}}})
    fw.register_area("beta", 200, 299,
                     rooms={200: {"name": "beta", "exits": {},
                                  "flags": {"safe": True}}})
    fw.setup()
    _write_index(fw.tmp_path, monkeypatch, {
        100: {"area": "alpha", "exits": {"n": 200}},
        200: {"area": "beta", "exits": {}},
    })
    player = _player()
    _ = ROOM_DEFS[100]
    world._ensure_area_by_tag("beta")
    MOB_DEFS._data[250] = {"keywords": "red dragon",
                           "short_descr": "a red dragon"}
    mob = _char_base()
    mob.update({"id": 2, "is_npc": True, "tpl": 250,
                "room": 200, "level": 10})
    world.chars[2] = mob
    out = []
    monkeypatch.setattr(path_cmd, "chprintln",
                        lambda _ch, text="": out.append(text))

    path_cmd.do_path(player, ["dragon"])

    assert out == ["{D[Calculating path...]{x",
                   "You cannot sense a path to them."]


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

    # the picker resolves to the typed speedwalk form for history replay
    assert movement.do_run(player, []) == "run 2n"
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


def _sliver_layout():
    """[PRIMESUD] Area bee split in two: a 2-room sliver (200-201) wedged
    between aye and cee, and the real 6-room body entered from cee at 210."""
    layout = {
        100: ("aye", {"n": 200}),
        200: ("bee", {"e": 201}),
        201: ("bee", {"e": 300}),
        300: ("cee", {"e": 210}),
        210: ("bee", {"w": 300, "n": 211}),
        211: ("bee", {"n": 212}),
        212: ("bee", {"n": 213}),
        213: ("bee", {"n": 214}),
        214: ("bee", {"n": 215}),
        215: ("bee", {}),
    }
    return {v: {"area": tag, "exits": exits}
            for v, (tag, exits) in layout.items()}


def _register_sliver_world(fw, monkeypatch, rooms_data):
    bounds = {"aye": (100, 199), "bee": (200, 299), "cee": (300, 399)}
    by_area = {}
    for vnum, room in rooms_data.items():
        by_area.setdefault(room["area"], {})[vnum] = {
            "name": "r" + str(vnum), "exits": room["exits"]}
    for tag, rooms in by_area.items():
        lo, hi = bounds[tag]
        fw.register_area(tag, lo, hi, rooms=rooms)
    fw.setup()
    _write_index(fw.tmp_path, monkeypatch, rooms_data)


def test_build_records_flags_only_sliver_border_rooms():
    """[PRIMESUD] V records mark border rooms whose in-area BFS reaches
    less than half the area; well-connected border rooms stay unflagged."""
    lines = build_records(_sliver_layout())
    flagged = set(int(l.split("|")[1]) for l in lines if l[0] == "V")

    # 200/201 reach 2 and 1 of bee's 8 rooms; 210 reaches 6.  100 and 300
    # are their whole (single-room) areas.
    assert flagged == {200, 201}


def test_area_path_skips_sliver_entry(fresh_world, monkeypatch):
    """[PRIMESUD] The 1-step hop into the sliver is not a valid landing:
    the route continues to the real body of the area."""
    _register_sliver_world(fresh_world, monkeypatch, _sliver_layout())
    player = _player()
    _ = ROOM_DEFS[100]
    out = []
    monkeypatch.setattr(path_cmd, "chprintln",
                        lambda _ch, text="": out.append(text))

    path_cmd.do_path(player, ["bee"])

    assert out == ["{D[Calculating path...]{x",
                   "Shortest path to bee is 4 steps: n3e."]


def test_mob_path_still_reaches_sliver_room(fresh_world, monkeypatch):
    """[PRIMESUD] The skip is area-target only -- a mob standing on a
    sliver room stays pathable at its true distance."""
    _register_sliver_world(fresh_world, monkeypatch, _sliver_layout())
    player = _player()
    _ = ROOM_DEFS[100]
    world._ensure_area_by_tag("bee")
    MOB_DEFS._data[250] = {"keywords": "red dragon",
                           "short_descr": "a red dragon"}
    mob = _char_base()
    mob.update({"id": 2, "is_npc": True, "tpl": 250,
                "room": 201, "level": 10})
    world.chars[2] = mob
    out = []
    monkeypatch.setattr(path_cmd, "chprintln",
                        lambda _ch, text="": out.append(text))

    path_cmd.do_path(player, ["dragon"])

    assert out == ["{D[Calculating path...]{x",
                   "Shortest path to a red dragon is 2 steps: ne."]


def test_area_path_falls_back_to_sliver_only_entry(fresh_world, monkeypatch):
    """[PRIMESUD] An area whose only entry is a sliver still routes -- the
    second Dijkstra pass accepts flagged rooms rather than reporting the
    area unreachable."""
    rooms_data = {
        100: {"area": "aye", "exits": {"n": 200}},
        200: {"area": "bee", "exits": {}},
        202: {"area": "bee", "exits": {"n": 203}},
        203: {"area": "bee", "exits": {"n": 204}},
        204: {"area": "bee", "exits": {}},
    }
    bounds = {"aye": (100, 199), "bee": (200, 299)}
    by_area = {}
    for vnum, room in rooms_data.items():
        by_area.setdefault(room["area"], {})[vnum] = {
            "name": "r" + str(vnum), "exits": room["exits"]}
    for tag, rooms in by_area.items():
        lo, hi = bounds[tag]
        fresh_world.register_area(tag, lo, hi, rooms=rooms)
    fresh_world.setup()
    _write_index(fresh_world.tmp_path, monkeypatch, rooms_data)
    assert 200 in info._parse_index()[2]

    player = _player()
    _ = ROOM_DEFS[100]
    out = []
    monkeypatch.setattr(path_cmd, "chprintln",
                        lambda _ch, text="": out.append(text))

    path_cmd.do_path(player, ["bee"])

    assert out == ["{D[Calculating path...]{x",
                   "Shortest path to bee is 1 step: n."]


def test_merge_runs_unit():
    assert info._merge_runs(["2n", "n"]) == "3n"
    assert info._merge_runs(["3n2e", "2e", "s"]) == "3n4es"
    assert info._merge_runs(["", "n", ""]) == "n"
    assert info._merge_runs([]) == ""


# ===== Shuffle-reset maze tokens ===========================================
# Rooms with an "R" reset get their exits reshuffled every area reset, so the
# index writes steps out of one as "*<vnum>" room-target tokens instead of a
# compass direction. [PRIMESUD]

# The layout the index is built from: aye -> a 3-room maze -> zed.
_MAZE_INDEX_LAYOUT = {
    100: {"area": "aye", "exits": {"n": 200}},
    200: {"area": "maze", "exits": {"n": 201, "s": 100}},
    201: {"area": "maze", "exits": {"n": 202, "s": 200}},
    202: {"area": "maze", "exits": {"e": 300, "s": 201}},
    300: {"area": "zed", "exits": {"w": 202}},
}

# The same maze after a reset reshuffled 200 and 201: same neighbours, other
# directions -- what the player actually walks.
_MAZE_LIVE_EXITS = {
    200: {"w": 201, "d": 100},
    201: {"e": 202, "u": 200},
    202: {"e": 300, "s": 201},
}

_MAZE_SHUFFLED = frozenset((200, 201))


def _register_maze_world(fw, monkeypatch, live=True):
    """Register the maze world (live layout) + an index of the frozen one."""
    exits = _MAZE_LIVE_EXITS if live else None
    for tag, lo, hi in (("aye", 100, 199), ("maze", 200, 299),
                        ("zed", 300, 399)):
        rooms = {}
        for vnum, room in _MAZE_INDEX_LAYOUT.items():
            if room["area"] != tag:
                continue
            rooms[vnum] = {"name": "r" + str(vnum),
                           "exits": (exits or {}).get(vnum, room["exits"])}
        fw.register_area(tag, lo, hi, rooms=rooms)
    fw.setup()
    lines = build_records(_MAZE_INDEX_LAYOUT, _MAZE_SHUFFLED)
    idx = fw.tmp_path / "paths.idx"
    idx.write_text("# test index\n" + "\n".join(lines) + "\n")
    monkeypatch.setattr(info, "PATH_INDEX_FILE", str(idx))


def test_build_records_emits_tokens_for_shuffled_rooms():
    """[PRIMESUD] Steps leaving a shuffled room become "*<vnum>" tokens, in
    both X records (dir field "*") and S segment strings."""
    plain = build_records(_MAZE_INDEX_LAYOUT)
    tokened = build_records(_MAZE_INDEX_LAYOUT, _MAZE_SHUFFLED)

    assert "X|200|s|100" in plain
    assert "S|200|202|2|2n" in plain

    # 200 and 201 are shuffled: their outgoing steps are room targets...
    assert "X|200|*|100" in tokened
    assert "S|200|202|2|*201*202" in tokened
    # ...202 is not, so its own steps stay compass directions.
    assert "X|202|e|300" in tokened
    assert "S|202|200|2|s*200" in tokened


def test_encoders_never_write_a_count_after_a_token():
    """[PRIMESUD] A run count straight after a token would fuse with the
    token's vnum digits, so both encoders spell the run out instead."""
    import build_path_index

    assert build_path_index._encode_steps(["*200", "n", "n", "n"]) == "*200nnn"
    assert build_path_index._encode_steps(["n", "n", "*200"]) == "2n*200"
    assert info._merge_runs(["*200", "3n"]) == "*200nnn"
    assert info._merge_runs(["2n*201", "n"]) == "2n*201n"
    assert info._merge_runs(["n", "*200", "*201"]) == "n*200*201"


def test_path_prints_tokens_as_question_marks(fresh_world, monkeypatch):
    """[PRIMESUD] Token steps show as "?" plus one helper line; last_path
    keeps the raw tokens so `run` can resolve them live."""
    _register_maze_world(fresh_world, monkeypatch)
    player = _player()
    _ = ROOM_DEFS[100]
    out = []
    monkeypatch.setattr(path_cmd, "chprintln",
                        lambda _ch, text="": out.append(text))

    path_cmd.do_path(player, ["zed"])

    assert out == ["{D[Calculating path...]{x",
                   "Shortest path to zed is 4 steps: n??e.",
                   "{D(? = random maze exit){x"]
    assert player["last_path"] == ("zed", "n*201*202e", 4, 100)


def test_path_without_tokens_prints_no_helper_line(fresh_world, monkeypatch):
    _setup_chain(fresh_world, monkeypatch, ("alpha", "beta"))
    player = _player()
    out = []
    monkeypatch.setattr(path_cmd, "chprintln",
                        lambda _ch, text="": out.append(text))

    path_cmd.do_path(player, ["bet"])

    assert out == ["{D[Calculating path...]{x",
                   "Shortest path to beta is 1 step: n."]


def test_run_walks_token_route_through_a_reshuffled_maze(
        fresh_world, monkeypatch):
    """[PRIMESUD] The whole loop: route from the index, tokens parsed into
    "goto" steps, each resolved against the live (reshuffled) exits."""
    _register_maze_world(fresh_world, monkeypatch)
    player = _player()
    player["move"] = 100
    _ = ROOM_DEFS[100]
    monkeypatch.setattr(path_cmd, "chprintln", lambda _ch, text="": None)
    out = []
    monkeypatch.setattr(movement, "chprintln",
                        lambda _ch, text="": out.append(text))
    monkeypatch.setattr(movement, "do_look", lambda _ch, _args: None)

    path_cmd.do_path(player, ["zed"])
    movement.do_run(player, [player["last_path"][1]])

    assert player["run_buf"] == [("move", "n"), ("goto", 201),
                                 ("goto", 202), ("move", "e")]
    while movement.run_buf_step(player):
        pass
    assert player["room"] == 300
    assert "Alas, you cannot go that way." not in out


def test_run_token_with_no_matching_exit_cancels_the_run(
        fresh_world, monkeypatch):
    """[PRIMESUD] An unresolvable token cancels like blocked movement."""
    _register_maze_world(fresh_world, monkeypatch)
    player = _player(room=200)
    player["move"] = 100
    _ = ROOM_DEFS[200]
    out = []
    monkeypatch.setattr(movement, "chprintln",
                        lambda _ch, text="": out.append(text))

    movement.do_run(player, ["*999w"])
    assert player["run_buf"] == [("goto", 999), ("move", "w")]

    assert movement.run_buf_step(player) is True
    assert player["room"] == 200
    assert out[-1] == "Alas, you cannot go that way."
    assert not player.get("run_buf")


def test_run_rejects_a_token_with_no_vnum(fresh_world, monkeypatch):
    _register_maze_world(fresh_world, monkeypatch)
    player = _player(room=200)
    out = []
    monkeypatch.setattr(movement, "chprintln",
                        lambda _ch, text="": out.append(text))

    movement.do_run(player, ["n*"])

    assert out == ["Invalid direction!"]
    assert not player.get("run_buf")
