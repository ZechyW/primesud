"""Tests for bounded lazy path routing. [PRIMESUD]"""

import config
import path as path_cmd
import world
from handler import _char_base
from world import MOB_DEFS, ROOM_DEFS


def _setup_chain(fw, monkeypatch, tags):
    for i, tag in enumerate(tags):
        vnum = (i + 1) * 100
        exits = {"n": vnum + 100} if i + 1 < len(tags) else {}
        fw.register_area(tag, vnum, vnum + 99,
                         rooms={vnum: {"name": tag, "exits": exits}})
    fw.setup()
    monkeypatch.setattr(world, "_AREA_ADJ", {
        tag: ((tags[i + 1],) if i + 1 < len(tags) else ())
        for i, tag in enumerate(tags)
    })


def _player(room=100, level=20):
    player = _char_base()
    player.update({"id": 1, "name": "Tester", "room": room,
                   "level": level})
    return player


def test_area_path_loads_one_corridor_then_evicts_remote_area(
        fresh_world, monkeypatch):
    _setup_chain(fresh_world, monkeypatch, ("alpha", "beta", "gamma"))
    monkeypatch.setattr(config, "AREA_CACHE_MAX", 2)
    player = _player()
    _ = ROOM_DEFS[100]
    out = []
    monkeypatch.setattr(path_cmd, "chprintln",
                        lambda _ch, text="": out.append(text))

    path_cmd.do_path(player, ["gam"])

    assert out == ["Shortest path to gamma is 2 steps: 2n."]
    assert world._LOADED_AREAS == {"alpha", "beta"}


def test_mob_path_uses_index_fallback_and_actual_room(fresh_world, monkeypatch):
    fw = fresh_world
    fw.register_area("alpha", 100, 199,
                     rooms={100: {"name": "alpha", "exits": {"n": 200}}})
    fw.register_area("beta", 200, 299,
                     rooms={200: {"name": "beta", "exits": {"e": 201}},
                            201: {"name": "lair", "exits": {}}})
    fw.setup()
    monkeypatch.setattr(world, "_AREA_ADJ",
                        {"alpha": ("beta",), "beta": ()})
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
    monkeypatch.setattr(path_cmd, "saves_spell", lambda *args: False)
    out = []
    monkeypatch.setattr(path_cmd, "chprintln",
                        lambda _ch, text="": out.append(text))

    path_cmd.do_path(player, ["dragon"])

    assert calls == ["dragon"]
    assert out == ["Shortest path to a red dragon is 2 steps: ne."]


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

    assert out == ["No need to walk to get there!"]


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
    monkeypatch.setattr(path_cmd, "saves_spell", lambda *args: False)
    out = []
    monkeypatch.setattr(path_cmd, "chprintln",
                        lambda _ch, text="": out.append(text))

    path_cmd.do_path(player, ["dragon"])

    assert out == ["No need to walk to get there!"]


def test_mob_path_within_current_area(fresh_world, monkeypatch):
    fw = fresh_world
    fw.register_area("alpha", 100, 199,
                     rooms={100: {"name": "alpha", "exits": {"n": 101}},
                            101: {"name": "lair", "exits": {}}})
    fw.setup()
    monkeypatch.setattr(world, "_AREA_ADJ", {"alpha": ()})
    player = _player()
    _ = ROOM_DEFS[100]
    MOB_DEFS._data[150] = {"keywords": "red dragon",
                           "short_descr": "a red dragon"}
    mob = _char_base()
    mob.update({"id": 2, "is_npc": True, "tpl": 150,
                "room": 101, "level": 10})
    world.chars[2] = mob
    monkeypatch.setattr(path_cmd, "saves_spell", lambda *args: False)
    out = []
    monkeypatch.setattr(path_cmd, "chprintln",
                        lambda _ch, text="": out.append(text))

    path_cmd.do_path(player, ["dragon"])

    assert out == ["Shortest path to a red dragon is 1 steps: n."]


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
    monkeypatch.setattr(path_cmd, "saves_spell", lambda *args: False)
    out = []
    monkeypatch.setattr(path_cmd, "chprintln",
                        lambda _ch, text="": out.append(text))

    path_cmd.do_path(player, ["dragon"])
    assert out == ["No such destination."]

    # detect invis restores get_char_world visibility
    player["affected_by"] = {"detect_invis": True}
    out[:] = []
    path_cmd.do_path(player, ["dragon"])
    assert out == ["No need to walk to get there!"]


def test_area_path_unreachable_chain_reports_no_path(fresh_world, monkeypatch):
    fw = fresh_world
    fw.register_area("alpha", 100, 199,
                     rooms={100: {"name": "alpha", "exits": {}}})
    fw.register_area("beta", 200, 299,
                     rooms={200: {"name": "beta", "exits": {}}})
    fw.setup()
    monkeypatch.setattr(world, "_AREA_ADJ", {"alpha": (), "beta": ()})
    player = _player()
    _ = ROOM_DEFS[100]
    out = []
    monkeypatch.setattr(path_cmd, "chprintln",
                        lambda _ch, text="": out.append(text))

    path_cmd.do_path(player, ["bet"])

    assert out == ["No path to destination."]


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
    monkeypatch.setattr(path_cmd, "saves_spell", lambda *args: False)
    out = []
    monkeypatch.setattr(path_cmd, "chprintln",
                        lambda _ch, text="": out.append(text))

    path_cmd.do_path(player, ["dragon"])

    assert out == ["No such destination."]
