"""Tests for hide/sneak/visible/steal and can_see."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "primesud.hpappdir")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import handler
import inventory
import movement
import world
from handler import _char_base, can_see
from skills_table import GSN_HIDE, GSN_SNEAK, GSN_STEAL
from world import ITEM_DEFS, MOB_DEFS, ROOM_DEFS


@pytest.fixture
def out(monkeypatch):
    lines = []
    cap = lambda s="", end="\n": lines.append(s)
    monkeypatch.setattr(movement, "tprint", cap)
    monkeypatch.setattr(inventory, "tprint", cap)
    monkeypatch.setattr(handler, "tprint", cap)
    return lines


@pytest.fixture
def scene():
    old_rooms = dict(world.rooms._data)
    old_chars = dict(world.chars)
    old_mobs = dict(MOB_DEFS._data)
    old_items = dict(ITEM_DEFS._data)

    room = {"name": "Test Room", "desc": "x", "exits": {}, "items": [],
            "mobs": [], "area": "test", "sector": "inside"}
    world.rooms._data[3001] = room
    ROOM_DEFS._data[3001] = room

    MOB_DEFS._data[9001] = {"short_descr": "a merchant", "keywords": "merchant",
                            "level": 5, "description": "rich"}
    ITEM_DEFS._data[8001] = {"type": "treasure", "keywords": "gem",
                             "short_descr": "a gem", "level": 1}
    mob = _char_base()
    mob.update({"is_npc": True, "id": 2, "tpl": 9001, "room": 3001,
                "level": 5, "hit": 50, "max_hit": 50,
                "gold": 100, "silver": 100, "inv": [{"vnum": 8001}]})
    world.chars[2] = mob
    room["mobs"] = [2]

    player = _char_base()
    player.update({"id": 1, "name": "Tester", "room": 3001, "level": 10,
                   "learned": {GSN_HIDE: 100, GSN_SNEAK: 100, GSN_STEAL: 100}})
    world.chars[1] = player

    yield player

    world.rooms._data.clear()
    world.rooms._data.update(old_rooms)
    world.chars.clear()
    world.chars.update(old_chars)
    MOB_DEFS._data.clear()
    MOB_DEFS._data.update(old_mobs)
    ITEM_DEFS._data.clear()
    ITEM_DEFS._data.update(old_items)


class TestCanSee:
    def test_sees_plain_char(self, scene):
        assert can_see(scene, world.chars[2])

    def test_blind_sees_nothing(self, scene):
        scene["affected_by"]["blind"] = True
        assert not can_see(scene, world.chars[2])

    def test_invisible_hidden_without_detect(self, scene):
        world.chars[2]["affected_by"]["invisible"] = True
        assert not can_see(scene, world.chars[2])
        scene["affected_by"]["detect_invis"] = True
        assert can_see(scene, world.chars[2])

    def test_hide_hidden_without_detect(self, scene):
        world.chars[2]["affected_by"]["hide"] = True
        assert not can_see(scene, world.chars[2])
        scene["affected_by"]["detect_hidden"] = True
        assert can_see(scene, world.chars[2])

    def test_fighting_char_never_hidden(self, scene):
        world.chars[2]["affected_by"]["hide"] = True
        world.chars[2]["fighting"] = 1
        assert can_see(scene, world.chars[2])


class TestHideSneak:
    def test_hide_success(self, scene, out, monkeypatch):
        monkeypatch.setattr(movement, "get_skill", lambda ch, sn: 100)
        monkeypatch.setattr(movement, "randint", lambda a, b: 1)
        monkeypatch.setattr(movement, "check_improve", lambda *a: None)
        movement.do_hide(scene, [])
        assert scene["affected_by"].get("hide") is True
        assert "You attempt to hide." in out

    def test_hide_fail(self, scene, out, monkeypatch):
        monkeypatch.setattr(movement, "get_skill", lambda ch, sn: 0)
        monkeypatch.setattr(movement, "randint", lambda a, b: 100)
        monkeypatch.setattr(movement, "check_improve", lambda *a: None)
        movement.do_hide(scene, [])
        assert not scene["affected_by"].get("hide")

    def test_sneak_success_applies_affect(self, scene, out, monkeypatch):
        monkeypatch.setattr(movement, "get_skill", lambda ch, sn: 100)
        monkeypatch.setattr(movement, "randint", lambda a, b: 1)
        monkeypatch.setattr(movement, "check_improve", lambda *a: None)
        movement.do_sneak(scene, [])
        assert scene["affected_by"].get("sneak") is True
        assert any(af["type"] == GSN_SNEAK for af in scene["affect_list"])

    def test_visible_strips_all(self, scene, out):
        scene["affected_by"]["hide"] = True
        scene["affected_by"]["invisible"] = True
        movement.do_visible(scene, [])
        assert not scene["affected_by"].get("hide")
        assert not scene["affected_by"].get("invisible")
        assert "Ok." in out


class TestSteal:
    def _prep(self, monkeypatch, skill, roll):
        monkeypatch.setattr(inventory, "get_skill", lambda ch, sn: skill)
        monkeypatch.setattr(inventory, "randint", lambda a, b: roll)
        monkeypatch.setattr(inventory, "check_improve", lambda *a: None)

    def test_steal_coins(self, scene, out, monkeypatch):
        self._prep(monkeypatch, 100, 10)
        inventory.do_steal(scene, ["gold", "merchant"])
        assert scene["gold"] > 0
        assert world.chars[2]["gold"] < 100
        assert any("Bingo!" in l for l in out)

    def test_steal_item(self, scene, out, monkeypatch):
        self._prep(monkeypatch, 100, 1)
        inventory.do_steal(scene, ["gem", "merchant"])
        assert any(o.get("vnum") == 8001 for o in scene["inv"])
        assert world.chars[2]["inv"] == []
        assert "Got it!" in out

    def test_steal_fail_starts_fight(self, scene, out, monkeypatch):
        self._prep(monkeypatch, 0, 3)
        hits = []
        monkeypatch.setattr(inventory, "multi_hit", lambda v, c, dt: hits.append(v))
        inventory.do_steal(scene, ["gold", "merchant"])
        assert "Oops." in out
        assert hits and hits[0] is world.chars[2]

    def test_steal_no_args(self, scene, out):
        inventory.do_steal(scene, [])
        assert "Steal what from whom?" in out
