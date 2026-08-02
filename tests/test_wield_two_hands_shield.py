"""Two-handed wield auto-removes a blocking shield (wear_obj, inventory.py).
[PRIMESUD test]

Upstream 1stMud (act_obj.c:1631-1637) simply refuses the wield when a small
character already wears a shield.  PrimeSUD treats an explicit `wield` as an
unambiguous request for both hands and removes the shield first, but only on
the fReplace path (`wear all` must never strip a shield silently), and only
when the shield is actually removable.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

from handler import _char_base, equip_char
import handler
import inventory
import world
from world import ROOM_DEFS, ITEM_DEFS

ROOM_VNUM = 9801
GREATSWORD_VNUM = 9802
SHIELD_VNUM = 9803
CURSED_SHIELD_VNUM = 9804

_EQUIP_SLOTS = ("light", "finger_l", "finger_r", "neck_1", "neck_2", "body",
                "head", "legs", "feet", "hands", "arms", "shield", "about",
                "waist", "wrist_l", "wrist_r", "wield", "hold", "float",
                "secondary")


@pytest.fixture(autouse=True)
def _clean_world_state():
    old_rooms = dict(ROOM_DEFS._data)
    old_wrooms = dict(world.rooms._data)
    old_chars = dict(world.chars)
    old_items = dict(ITEM_DEFS._data)

    ITEM_DEFS._data[GREATSWORD_VNUM] = {
        "keywords": "greatsword test", "short_descr": "a test greatsword",
        "type": "weapon", "weapon_type": "sword", "dam_type": "slash",
        "dice": (1, 4, 0), "weapon_flags": {"two_hands": True},
        "level": 1, "weight": 10,
        "wear_flags": {"take": True, "wield": True}, "extra_flags": {},
    }
    ITEM_DEFS._data[SHIELD_VNUM] = {
        "keywords": "shield test", "short_descr": "a test shield",
        "type": "armor", "level": 1, "weight": 10,
        "wear_flags": {"take": True, "shield": True}, "extra_flags": {},
    }
    ITEM_DEFS._data[CURSED_SHIELD_VNUM] = {
        "keywords": "cursed shield test",
        "short_descr": "a cursed test shield",
        "type": "armor", "level": 1, "weight": 10,
        "wear_flags": {"take": True, "shield": True},
        "extra_flags": {"noremove": True},
    }

    room = {"name": "Test Room", "desc": "A test room.", "exits": {},
            "items": [], "mobs": [], "area": "test", "flags": {},
            "sector": "inside"}
    ROOM_DEFS._data[ROOM_VNUM] = room
    world.rooms._data[ROOM_VNUM] = room

    yield

    ROOM_DEFS._data.clear()
    ROOM_DEFS._data.update(old_rooms)
    world.rooms._data.clear()
    world.rooms._data.update(old_wrooms)
    world.chars.clear()
    world.chars.update(old_chars)
    ITEM_DEFS._data.clear()
    ITEM_DEFS._data.update(old_items)


@pytest.fixture
def out(monkeypatch):
    lines = []
    capture = lambda *a, **kw: lines.append(" ".join(str(x) for x in a))
    monkeypatch.setattr(handler, "tprint", capture)
    return lines


def _make_player(size="medium"):
    ch = _char_base()
    ch.update({"id": 1, "name": "Tester", "level": 10, "room": ROOM_VNUM,
               "size": size, "learned": {},
               "equip": {slot: None for slot in _EQUIP_SLOTS}})
    world.chars[1] = ch
    return ch


def _setup(size="medium", shield_vnum=SHIELD_VNUM):
    """Player of the given size wearing a shield, greatsword in inventory."""
    player = _make_player(size)
    shield = {"vnum": shield_vnum}
    player["inv"].append(shield)
    equip_char(player, shield, "shield")
    sword = {"vnum": GREATSWORD_VNUM}
    player["inv"].append(sword)
    return player, shield, sword


def test_wield_two_hands_auto_removes_shield(out):
    """Intentional wield (fReplace) removes the shield, then wields."""
    player, shield, sword = _setup()

    inventory.wear_obj(player, sword, True)

    assert any("You stop using a test shield." in l for l in out)
    assert not any("You need two hands free" in l for l in out)
    assert player["equip"]["shield"] is None
    assert shield in player["inv"]
    assert player["equip"]["wield"] is sword
    assert sword not in player["inv"]


def test_cursed_shield_still_blocks_the_wield(out):
    """remove_obj refuses a noremove shield -> original block message."""
    player, shield, sword = _setup(shield_vnum=CURSED_SHIELD_VNUM)

    inventory.wear_obj(player, sword, True)

    assert any("You can't remove a cursed test shield." in l for l in out)
    assert any("You need two hands free for that weapon." in l for l in out)
    assert player["equip"]["shield"] is shield
    assert player["equip"]["wield"] is None
    assert sword in player["inv"]


def test_large_character_keeps_shield_and_wields(out):
    """Size >= large never hits the check, so nothing is removed."""
    player, shield, sword = _setup(size="large")

    inventory.wear_obj(player, sword, True)

    assert not any("You stop using" in l for l in out)
    assert player["equip"]["shield"] is shield
    assert player["equip"]["wield"] is sword


def test_wear_all_path_blocks_without_stripping_shield(out):
    """fReplace False (e.g. `wear all`) keeps the upstream hard block."""
    player, shield, sword = _setup()

    inventory.wear_obj(player, sword, False)

    assert any("You need two hands free for that weapon." in l for l in out)
    assert not any("You stop using" in l for l in out)
    assert player["equip"]["shield"] is shield
    assert player["equip"]["wield"] is None
    assert sword in player["inv"]
