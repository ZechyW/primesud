"""Tests for do_drink / do_fill / do_pour vs 1stMud act_obj.c."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "primesud.hpappdir")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import inventory
import world
from handler import _char_base
from item import parse_item_token, serialize_item_token
from world import ITEM_DEFS, ROOM_DEFS

FOUNTAIN_TPL = 9461   # unlimited (total 0), like Midgaard 3135
SKIN_TPL = 9462       # water skin, capacity 32
BOTTLE_TPL = 9463     # wine bottle, full
SWORD_TPL = 9464


@pytest.fixture(autouse=True)
def scene():
    old_rooms = dict(world.rooms._data)
    old_defs = dict(ROOM_DEFS._data)
    old_chars = dict(world.chars)
    old_items = dict(ITEM_DEFS._data)
    ITEM_DEFS._data[FOUNTAIN_TPL] = {
        "keywords": "fountain", "short_descr": "a fountain",
        "type": "fountain", "wear_flags": {},
        "liquid_total": 0, "liquid_left": 0, "liquid_type": "water",
    }
    ITEM_DEFS._data[SKIN_TPL] = {
        "keywords": "skin water", "short_descr": "a water skin",
        "type": "drink", "wear_flags": {"take": True},
        "liquid_total": 32, "liquid_left": 32, "liquid_type": "water",
    }
    ITEM_DEFS._data[BOTTLE_TPL] = {
        "keywords": "bottle wine", "short_descr": "a bottle",
        "type": "drink", "wear_flags": {"take": True},
        "liquid_total": 20, "liquid_left": 20, "liquid_type": "red wine",
    }
    ITEM_DEFS._data[SWORD_TPL] = {
        "keywords": "sword", "short_descr": "a sword",
        "type": "weapon", "wear_flags": {"take": True},
    }
    room = {"name": "Test Room", "desc": "x", "exits": {}, "items": [],
            "mobs": [], "area": "test", "flags": {}, "sector": "inside"}
    ROOM_DEFS._data[9001] = room
    world.rooms._data[9001] = room
    yield
    ROOM_DEFS._data.clear()
    ROOM_DEFS._data.update(old_defs)
    world.rooms._data.clear()
    world.rooms._data.update(old_rooms)
    world.chars.clear()
    world.chars.update(old_chars)
    ITEM_DEFS._data.clear()
    ITEM_DEFS._data.update(old_items)


@pytest.fixture
def player():
    ch = _char_base()
    ch["id"] = 1
    ch["name"] = "Tester"
    ch["level"] = 20
    ch["room"] = 9001
    world.chars[1] = ch
    return ch


@pytest.fixture
def out(monkeypatch):
    lines = []
    import handler
    monkeypatch.setattr(handler, "tprint", lambda s="", end="\n": lines.append(s))
    monkeypatch.setattr(inventory, "tprint", lambda s="", end="\n": lines.append(s))
    return lines


def _room_items():
    return world.rooms._data[9001]["items"]


# -- do_drink ---------------------------------------------------------------

def test_drink_from_unlimited_fountain(player, out):
    _room_items().append(FOUNTAIN_TPL)  # plain vnum, total 0 = unlimited
    inventory.do_drink(player, [])
    assert any("You drink water from a fountain." in l for l in out)
    # unlimited fountain never mutates -> must stay a plain vnum (no
    # persistent instance dict in room items / save payload)
    assert _room_items() == [FOUNTAIN_TPL]


def test_drink_named_fountain_stays_unlimited(player, out):
    _room_items().append(FOUNTAIN_TPL)
    inventory.do_drink(player, ["fountain"])
    inventory.do_drink(player, ["fountain"])
    drinks = [l for l in out if "You drink water" in l]
    assert len(drinks) == 2


def test_drink_container_vnum_promoted_and_consumed(player, out):
    player["inv"].append(SKIN_TPL)  # plain vnum from pickup
    inventory.do_drink(player, ["skin"])
    obj = player["inv"][0]
    assert isinstance(obj, dict)
    assert obj["liquid_left"] == 32 - 16  # water sip = 16


def test_drink_empty_container(player, out):
    player["inv"].append({"vnum": SKIN_TPL, "liquid_left": 0,
                          "liquid_total": 32, "liquid_type": "water"})
    inventory.do_drink(player, ["skin"])
    assert out[-1] == "It is already empty."


def test_drink_non_drinkable(player, out):
    player["inv"].append(SWORD_TPL)
    inventory.do_drink(player, ["sword"])
    assert out[-1] == "You can't drink from that."


def test_drink_poisoned_applies_affect_without_save(player, out):
    player["inv"].append({"vnum": SKIN_TPL, "liquid_left": 32,
                          "liquid_total": 32, "liquid_type": "water",
                          "poisoned": True})
    inventory.do_drink(player, ["skin"])
    assert any("You choke and gag." in l for l in out)
    afs = [af for af in player["affect_list"] if af.get("bitvector") == "poison"]
    assert afs and afs[0]["duration"] == 16 * 3  # 3 * amount, no save


# -- do_fill ----------------------------------------------------------------

def test_fill_from_zero_capacity_fountain(player, out):
    _room_items().append(FOUNTAIN_TPL)
    player["inv"].append(SKIN_TPL)
    player["inv"][0] = {"vnum": SKIN_TPL, "liquid_left": 0,
                        "liquid_total": 32, "liquid_type": "water"}
    inventory.do_fill(player, ["skin"])
    assert player["inv"][0]["liquid_left"] == 32
    assert any("You fill a water skin with water from a fountain." in l
               for l in out)


def test_fill_no_fountain(player, out):
    player["inv"].append(SKIN_TPL)
    inventory.do_fill(player, ["skin"])
    assert out[-1] == "There is no fountain here!"


def test_fill_other_liquid(player, out):
    _room_items().append(FOUNTAIN_TPL)
    player["inv"].append({"vnum": BOTTLE_TPL, "liquid_left": 5,
                          "liquid_total": 20, "liquid_type": "red wine"})
    inventory.do_fill(player, ["bottle"])
    assert out[-1] == "There is already another liquid in it."


def test_fill_full_container(player, out):
    _room_items().append(FOUNTAIN_TPL)
    player["inv"].append(SKIN_TPL)  # template full of water
    inventory.do_fill(player, ["skin"])
    assert out[-1] == "Your container is full."


def test_fill_does_not_transfer_poison(player, out):
    _room_items().append({"vnum": FOUNTAIN_TPL, "poisoned": True})
    player["inv"].append({"vnum": SKIN_TPL, "liquid_left": 0,
                          "liquid_total": 32, "liquid_type": "water"})
    inventory.do_fill(player, ["skin"])
    assert not player["inv"][0].get("poisoned")


# -- do_pour ----------------------------------------------------------------

def test_pour_needs_two_args(player, out):
    inventory.do_pour(player, ["bottle"])
    assert out[-1] == "Pour what into what?"


def test_pour_out_empties_and_clears_poison(player, out):
    player["inv"].append({"vnum": BOTTLE_TPL, "liquid_left": 20,
                          "liquid_total": 20, "liquid_type": "red wine",
                          "poisoned": True})
    inventory.do_pour(player, ["bottle", "out"])
    obj = player["inv"][0]
    assert obj["liquid_left"] == 0
    assert obj["poisoned"] is False
    assert any("You invert a bottle, spilling red wine all over the ground."
               in l for l in out)


def test_pour_transfer_without_into_keyword(player, out):
    player["inv"].append({"vnum": BOTTLE_TPL, "liquid_left": 20,
                          "liquid_total": 20, "liquid_type": "red wine"})
    player["inv"].append({"vnum": SKIN_TPL, "liquid_left": 0,
                          "liquid_total": 32, "liquid_type": "water"})
    inventory.do_pour(player, ["bottle", "skin"])
    assert player["inv"][0]["liquid_left"] == 0
    assert player["inv"][1]["liquid_left"] == 20
    assert player["inv"][1]["liquid_type"] == "red wine"
    assert any("You pour red wine from a bottle into a water skin." in l
               for l in out)


def test_pour_into_itself(player, out):
    player["inv"].append(BOTTLE_TPL)
    inventory.do_pour(player, ["bottle", "bottle"])
    assert out[-1] == "You cannot change the laws of physics!"


def test_pour_liquid_mismatch(player, out):
    player["inv"].append({"vnum": BOTTLE_TPL, "liquid_left": 20,
                          "liquid_total": 20, "liquid_type": "red wine"})
    player["inv"].append({"vnum": SKIN_TPL, "liquid_left": 5,
                          "liquid_total": 32, "liquid_type": "water"})
    inventory.do_pour(player, ["bottle", "skin"])
    assert out[-1] == "They don't hold the same liquid."


# -- serialization ----------------------------------------------------------

def test_cleared_poison_survives_save_roundtrip():
    obj = {"vnum": BOTTLE_TPL, "liquid_left": 0, "liquid_total": 20,
           "liquid_type": "red wine", "poisoned": False}
    loaded = parse_item_token(serialize_item_token(obj))
    assert loaded["poisoned"] is False
    assert loaded["liquid_left"] == 0
    assert loaded["liquid_type"] == "red wine"
