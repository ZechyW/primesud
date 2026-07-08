"""Tests for do_heal (healer NPC services, cf. 1stMud healer.c)."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import handler
import world
from handler import _char_base
from healer import do_heal
from world import MOB_DEFS, ROOM_DEFS


@pytest.fixture
def out(monkeypatch):
    lines = []
    monkeypatch.setattr(handler, "tprint", lambda s="", end="\n": lines.append(s))
    import magic
    monkeypatch.setattr(magic, "chprintln",
                        lambda ch, s="": lines.append(s) if ch is world.chars.get(1) else None,
                        raising=False)
    return lines


@pytest.fixture
def scene():
    old_rooms = dict(world.rooms._data)
    old_chars = dict(world.chars)
    old_mobs = dict(MOB_DEFS._data)
    old_room_defs = dict(ROOM_DEFS._data)

    r1 = {"name": "Temple", "desc": "x", "exits": {}, "items": [],
          "mobs": [], "area": "test", "sector": "inside"}
    world.rooms._data[3001] = r1
    ROOM_DEFS._data[3001] = r1

    MOB_DEFS._data[9060] = {"short_descr": "the healer", "keywords": "healer",
                            "level": 30, "description": "A healer."}
    hlr = _char_base()
    hlr.update({"is_npc": True, "id": 2, "tpl": 9060, "room": 3001,
                "level": 30, "act_flags": {"healer": True}})
    world.chars.clear()
    world.chars[2] = hlr
    r1["mobs"] = [2]

    player = _char_base()
    player.update({"id": 1, "name": "Tester", "room": 3001, "level": 10,
                   "hit": 10, "max_hit": 100, "mana": 5, "max_mana": 50,
                   "move": 5, "max_move": 80, "gold": 100, "silver": 0})
    world.chars[1] = player

    yield {"player": player, "healer": hlr, "r1": r1}

    world.rooms._data.clear()
    world.rooms._data.update(old_rooms)
    world.chars.clear()
    world.chars.update(old_chars)
    MOB_DEFS._data.clear()
    MOB_DEFS._data.update(old_mobs)
    ROOM_DEFS._data.clear()
    ROOM_DEFS._data.update(old_room_defs)


def test_no_healer_here(scene, out):
    scene["healer"]["act_flags"] = {}
    do_heal(scene["player"], [])
    assert "You can't do that here." in out


def test_list_spells(scene, out):
    do_heal(scene["player"], [])
    assert any("I offer the following spells" in l for l in out)
    assert any("cure light wounds" in l and "10 gold" in l for l in out)
    assert any("Type heal <type> to be healed." in l for l in out)


def test_unknown_type(scene, out):
    do_heal(scene["player"], ["frobnicate"])
    assert any("Type 'heal' for a list of spells." in l for l in out)


def test_not_enough_gold(scene, out):
    scene["player"]["gold"] = 0
    do_heal(scene["player"], ["light"])
    assert any("You do not have enough gold" in l for l in out)
    assert scene["player"]["hit"] == 10


def test_heal_light_heals_and_charges(scene, out):
    p = scene["player"]
    do_heal(p, ["light"])
    assert p["gold"] * 100 + p["silver"] == 90 * 100
    assert scene["healer"]["gold"] == 10
    assert p["hit"] > 10
    assert p["wait"] > 0
    assert any("judicandus dies" in l for l in out)


def test_heal_mana(scene, out):
    p = scene["player"]
    do_heal(p, ["mana"])
    assert p["mana"] > 5
    assert p["mana"] <= p["max_mana"]
    assert any("A warm glow passes through you." in l for l in out)
    assert p["gold"] * 100 + p["silver"] == 90 * 100


def test_heal_prefix_match(scene, out):
    p = scene["player"]
    do_heal(p, ["ref"])  # refresh, 5 gold
    assert p["move"] > 5
    assert p["gold"] * 100 + p["silver"] == 95 * 100


def test_heal_uncurse_runs(scene, out):
    # remove curse on an uncursed target still charges and prints words
    p = scene["player"]
    do_heal(p, ["uncurse"])
    assert p["gold"] * 100 + p["silver"] == 50 * 100
    assert any("candussido judifgz" in l for l in out)
