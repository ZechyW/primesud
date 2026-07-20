"""Tests for spell_locate_object visibility fidelity (magic.c:3509)."""

import magic
import world
from handler import _char_base
from world import ITEM_DEFS, MOB_DEFS, ROOM_DEFS


def _setup(fw, monkeypatch):
    fw.register_area("alpha", 100, 199,
                     rooms={100: {"name": "alpha", "exits": {}}})
    fw.setup()
    _ = ROOM_DEFS[100]
    monkeypatch.setattr(magic, "randint", lambda a, b: 1)
    out = []
    monkeypatch.setattr(magic, "chprintln",
                        lambda _ch, text="": out.append(text))
    player = _char_base()
    player.update({"id": 1, "name": "Tester", "room": 100, "level": 20,
                   "_target_name": "sword"})
    return player, out


def test_locate_finds_carried_item(fresh_world, monkeypatch):
    player, out = _setup(fresh_world, monkeypatch)
    ITEM_DEFS._data[5000] = {"keywords": "long sword", "level": 0}
    player["inv"] = [{"vnum": 5000}]

    assert magic.spell_locate_object(0, 20, player, None, "char")
    assert out == ["one is carried by you"]


def test_locate_skips_invis_item_without_detect(fresh_world, monkeypatch):
    player, out = _setup(fresh_world, monkeypatch)
    ITEM_DEFS._data[5000] = {"keywords": "long sword", "level": 0,
                             "extra_flags": {"invis": True}}
    player["inv"] = [{"vnum": 5000}]

    assert not magic.spell_locate_object(0, 20, player, None, "char")
    assert out == ["Nothing like that in heaven or earth."]

    out[:] = []
    player["affected_by"] = {"detect_invis": True}
    assert magic.spell_locate_object(0, 20, player, None, "char")
    assert out == ["one is carried by you"]


def test_locate_hides_invisible_carrier(fresh_world, monkeypatch):
    player, out = _setup(fresh_world, monkeypatch)
    ITEM_DEFS._data[5000] = {"keywords": "long sword", "level": 0}
    MOB_DEFS._data[150] = {"keywords": "shadow guard",
                           "short_descr": "a shadow guard"}
    mob = _char_base()
    mob.update({"id": 2, "is_npc": True, "tpl": 150, "room": 100,
                "level": 10, "inv": [{"vnum": 5000}]})
    world.chars[2] = mob

    assert magic.spell_locate_object(0, 20, player, None, "char")
    assert out == ["one is carried by a shadow guard"]

    out[:] = []
    mob["affected_by"] = {"invisible": True}
    assert magic.spell_locate_object(0, 20, player, None, "char")
    assert out == ["one is in somewhere"]
