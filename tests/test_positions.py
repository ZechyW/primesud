"""Tests for position system: rest/sit/stand/sleep/wake, regen, mob positions."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import info
import movement
import world
from handler import _char_base
from world import ITEM_DEFS, MOB_DEFS, ROOM_DEFS


@pytest.fixture
def out(monkeypatch):
    lines = []
    # do_look sends a pre-split list batch; flatten so assertions see lines
    cap = lambda s="", end="\n": (
        lines.extend(s) if type(s) is list else lines.append(s))
    import handler
    monkeypatch.setattr(handler, "tprint", cap)
    return lines


@pytest.fixture
def scene():
    old_rooms = dict(world.rooms._data)
    old_chars = dict(world.chars)
    old_mobs = dict(MOB_DEFS._data)

    room = {"name": "Test Room", "desc": "x", "exits": {}, "items": [],
            "mobs": [], "area": "test", "sector": "inside"}
    world.rooms._data[3001] = room
    ROOM_DEFS._data[3001] = room

    MOB_DEFS._data[9001] = {"short_descr": "a guard", "keywords": "guard",
                            "long_descr": "A guard walks his beat.",
                            "level": 5, "start_pos": "sleep",
                            "default_pos": "sleep", "description": "A guard."}
    mob = _char_base()
    mob.update({"is_npc": True, "id": 2, "tpl": 9001, "room": 3001,
                "pos": "sleeping", "hit": 50, "max_hit": 50})
    world.chars[2] = mob
    room["mobs"] = [2]

    player = _char_base()
    player.update({"id": 1, "room": 3001, "level": 5})
    world.chars[1] = player

    yield player

    world.rooms._data.clear()
    world.rooms._data.update(old_rooms)
    world.chars.clear()
    world.chars.update(old_chars)
    MOB_DEFS._data.clear()
    MOB_DEFS._data.update(old_mobs)


class TestTransitions:
    def test_rest_from_standing(self, scene, out):
        movement.do_rest(scene, [])
        assert scene["pos"] == "resting"
        assert "You rest." in out

    def test_sit_from_standing(self, scene, out):
        movement.do_sit(scene, [])
        assert scene["pos"] == "sitting"
        assert "You sit down." in out

    def test_sleep_then_stand_wakes(self, scene, out):
        movement.do_sleep(scene, [])
        assert scene["pos"] == "sleeping"
        movement.do_stand(scene, [])
        assert scene["pos"] == "standing"
        assert "You wake and stand up." in out

    def test_sleep_affect_blocks_wake(self, scene, out):
        scene["pos"] = "sleeping"
        scene["affected_by"]["sleep"] = True
        movement.do_stand(scene, [])
        assert scene["pos"] == "sleeping"
        assert "You can't wake up!" in out

    def test_already_standing(self, scene, out):
        movement.do_stand(scene, [])
        assert "You are already standing." in out

    def test_rest_while_fighting(self, scene, out):
        scene["pos"] = "fighting"
        movement.do_rest(scene, [])
        assert scene["pos"] == "fighting"
        assert "You are already fighting!" in out


class TestWake:
    def test_wake_no_args_stands(self, scene, out):
        scene["pos"] = "sleeping"
        movement.do_wake(scene, [])
        assert scene["pos"] == "standing"

    def test_wake_sleeping_mob(self, scene, out):
        movement.do_wake(scene, ["guard"])
        assert world.chars[2]["pos"] == "standing"

    def test_wake_awake_mob(self, scene, out):
        world.chars[2]["pos"] = "standing"
        movement.do_wake(scene, ["guard"])
        assert any("is already awake" in l for l in out)


class TestRegen:
    def _gain(self, player, pos):
        import player as player_mod
        player["pos"] = pos
        player["hit"] = 1
        player["max_hit"] = 100
        player["mana"] = 1
        player["max_mana"] = 100
        room = {"heal_rate": 100, "mana_rate": 100}
        player_mod.tick_update(None, player, room)
        return player["hit"] - 1

    def test_sleeping_beats_resting_beats_standing(self, scene):
        sleeping = self._gain(scene, "sleeping")
        resting = self._gain(scene, "resting")
        standing = self._gain(scene, "standing")
        assert sleeping > resting > standing


class TestLookPositions:
    def test_long_descr_at_start_pos(self, scene, out):
        info.do_look(scene, [])
        assert any("A guard walks his beat." in l for l in out)

    def test_position_string_when_moved(self, scene, out):
        world.chars[2]["pos"] = "standing"  # differs from start_pos sleep
        info.do_look(scene, [])
        assert any("A guard is here." in l for l in out)

    def test_sleeping_string_when_start_pos_differs(self, scene, out):
        MOB_DEFS._data[9001]["start_pos"] = "stand"
        info.do_look(scene, [])
        assert any("A guard is sleeping here." in l for l in out)


class TestSpawnPos:
    def test_create_mobile_uses_start_pos(self, scene):
        import mob as mob_mod
        MOB_DEFS._data[9001].update({
            "hp_dice": (1, 1, 10), "level": 5, "hitroll": 0,
            "damage": (1, 4, 0), "armor": (0, 0, 0, 0),
        })
        inst = mob_mod.create_mobile(9001)
        assert inst["pos"] == "sleeping"
