"""Tests for do_eat: poison on food and type override handling (cf. 1stMud act_obj.c).

Tests mirror patterns from test_death_cry.py (poison_food fixtures) and verify that:
- Instance-level type override prevents eating trash-downgraded food
- Instance-level poisoned flag applies poison affect with proper messages
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import inventory
import world
from handler import _char_base
from world import ITEM_DEFS

FOOD_TPL = 9470       # plain food template
PILL_TPL = 9471       # plain pill template
TRASH_TPL = 9472      # plain trash template (non-food)


@pytest.fixture(autouse=True)
def scene():
    old_defs = dict(ITEM_DEFS._data)
    old_chars = dict(world.chars)
    ITEM_DEFS._data[FOOD_TPL] = {
        "keywords": "meat food", "short_descr": "a piece of meat",
        "description": "A piece of raw meat is here.",
        "type": "food", "level": 0, "weight": 20, "value": 3,
        "food_hours": 10, "food_hunger": 10,
    }
    ITEM_DEFS._data[PILL_TPL] = {
        "keywords": "pill potion", "short_descr": "a blue pill",
        "description": "A blue pill is lying here.",
        "type": "pill", "level": 0, "weight": 1, "value": 0,
        "spell_level": 10, "spells": ["magic missile"],
    }
    ITEM_DEFS._data[TRASH_TPL] = {
        "keywords": "trash trash", "short_descr": "some trash",
        "description": "Some trash is lying here.",
        "type": "trash", "level": 0, "weight": 50, "value": 0,
    }
    yield
    ITEM_DEFS._data.clear()
    ITEM_DEFS._data.update(old_defs)
    world.chars.clear()
    world.chars.update(old_chars)


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


# -- do_eat: normal food -------------------------------------------------------

def test_eat_plain_food(player, out):
    player["inv"].append(FOOD_TPL)
    inventory.do_eat(player, ["meat"])
    assert any("You eat a piece of meat." in l for l in out)
    assert len(player["inv"]) == 0  # item consumed


def test_eat_no_args(player, out):
    inventory.do_eat(player, [])
    assert out[-1] == "Eat what?"


def test_eat_not_in_inventory(player, out):
    inventory.do_eat(player, ["meat"])
    assert out[-1] == "You do not have that item."


def test_eat_non_food_item(player, out):
    player["inv"].append(TRASH_TPL)
    inventory.do_eat(player, ["trash"])
    assert out[-1] == "That's not edible."
    assert len(player["inv"]) == 1  # item not consumed


# -- do_eat: poisoned food -------------------------------------------------------

def test_eat_poisoned_food_applies_affect(player, out):
    """Poisoned food applies poison affect with level and duration from food value."""
    player["inv"].append({"vnum": FOOD_TPL, "poisoned": True})
    inventory.do_eat(player, ["meat"])
    assert any("You choke and gag." in l for l in out)
    afs = [af for af in player["affect_list"] if af.get("bitvector") == "poison"]
    # food_amount = 10 (template food_hours, 1stMud value[0]; NOT the gold
    # cost "value" field), so duration = 2 * 10 = 20
    assert afs and afs[0]["duration"] == 20
    assert len(player["inv"]) == 0  # item consumed


def test_eat_poisoned_food_messages(player, out):
    """Poisoned food triggers choke/gag messages."""
    player["inv"].append({"vnum": FOOD_TPL, "poisoned": True})
    inventory.do_eat(player, ["meat"])
    # Player sees both messages (to_char "You eat" and choke messages)
    assert any("You eat a piece of meat." in l for l in out)
    assert any("You choke and gag." in l for l in out)


def test_eat_food_template_poisoned(player, out):
    """Poisoned template food applies poison even without instance override."""
    ITEM_DEFS._data[FOOD_TPL]["poisoned"] = True
    player["inv"].append(FOOD_TPL)
    inventory.do_eat(player, ["meat"])
    assert any("You choke and gag." in l for l in out)
    afs = [af for af in player["affect_list"] if af.get("bitvector") == "poison"]
    assert afs


# -- do_eat: type override (trash downgrade) -------------------------------------------------------

def test_eat_food_downgraded_to_trash_not_edible(player, out):
    """Food downgraded to type 'trash' (by death_cry) is not edible."""
    player["inv"].append({"vnum": FOOD_TPL, "type": "trash"})
    inventory.do_eat(player, ["meat"])
    assert out[-1] == "That's not edible."
    assert len(player["inv"]) == 1  # item not consumed


def test_eat_template_food_instance_trash_checked_first(player, out):
    """Instance type override takes precedence over template."""
    # Template says food, but instance says trash
    player["inv"].append({"vnum": FOOD_TPL, "type": "trash"})
    inventory.do_eat(player, ["meat"])
    assert out[-1] == "That's not edible."


# -- do_eat: combination (poisoned + trash downgrade) -------------------------------------------------------

def test_eat_poisoned_trash_downgraded_not_edible(player, out):
    """Even if poisoned, trash-downgraded food is not edible."""
    player["inv"].append({"vnum": FOOD_TPL, "type": "trash", "poisoned": True})
    inventory.do_eat(player, ["meat"])
    assert out[-1] == "That's not edible."
    assert len(player["affect_list"]) == 0  # no poison effect applied


def test_eat_with_missing_food_hours_defaults_to_zero(player, out):
    """Food without food_hours acts like 1stMud value[0] == 0: duration 0,
    level floored to 1 by number_fuzzy."""
    food_no_hours = dict(ITEM_DEFS._data[FOOD_TPL])
    del food_no_hours["food_hours"]
    ITEM_DEFS._data[9473] = food_no_hours
    player["inv"].append({"vnum": 9473, "poisoned": True})
    inventory.do_eat(player, ["meat"])
    afs = [af for af in player["affect_list"] if af.get("bitvector") == "poison"]
    assert afs and afs[0]["duration"] == 0
    assert afs[0]["level"] >= 1
