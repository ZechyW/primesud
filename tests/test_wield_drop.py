"""Wield-drop on strength loss (cf. 1stMud affect_modify handler.c:1030-1045). [PRIMESUD test]

affect_modify drops a wielded weapon to the room when a stat-draining affect
leaves the char too weak to hold it (weight > str_app[str].wield * 10).

The recursion case is the reason the _affect_depth guard exists: unequip_char
reverses the weapon's own stat_bonuses via affect_modify, so a +str weapon
lowers str again and, unguarded, would re-fire the wield-drop and drop twice.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

from handler import _char_base, affect_modify, equip_char
import world
from world import ITEM_DEFS

ROOM_VNUM = 9701
SWORD_VNUM = 9710


def _stub_room():
    room = {"name": "Test Room", "desc": "A test room.", "exits": {},
            "items": [], "mobs": [], "area": "test", "flags": {},
            "sector": "inside"}
    world.rooms._data[ROOM_VNUM] = room
    return room


def _player(str_stat):
    ch = _char_base()
    ch["id"] = 1
    ch["name"] = "Tester"
    ch["room"] = ROOM_VNUM
    ch["perm_stat"] = dict(ch["perm_stat"], str=str_stat)
    ch["mod_stat"] = {}
    world.chars[1] = ch
    return ch


def _drain(location="str", modifier=-4):
    return {"where": "to_affects", "location": location,
            "modifier": modifier, "bitvector": ""}


def _wield(ch, weight, stat_bonuses=None):
    tpl = {"short_descr": "a heavy sword", "weight": weight}
    if stat_bonuses:
        tpl["stat_bonuses"] = stat_bonuses
    ITEM_DEFS._data[SWORD_VNUM] = tpl
    obj = {"vnum": SWORD_VNUM}
    ch["inv"].append(obj)
    equip_char(ch, obj, "wield")   # str-16 wield limit is 160; 150 is holdable
    return obj


def test_drops_weapon_when_str_drained_below_limit():
    """str 16 (limit 160) wielding a 150 sword; drain to 12 (limit 120) -> drops."""
    _stub_room()
    ch = _player(16)
    sword = _wield(ch, 150)

    affect_modify(ch, _drain(modifier=-4), True)   # str -> 12

    room_items = world.rooms._data[ROOM_VNUM]["items"]
    assert ch["equip"]["wield"] is None
    assert sword not in ch["inv"]
    assert room_items.count(sword) == 1


def test_str_weapon_drops_exactly_once():
    """+3-str sword: dropping reverses its own bonus, which re-enters
    affect_modify. The _affect_depth guard must stop a second drop."""
    _stub_room()
    ch = _player(13)                       # base 13; +3 sword -> curr 16, limit 160
    sword = _wield(ch, 150, stat_bonuses={"str": 3})
    assert ch["mod_stat"]["str"] == 3      # weapon bonus applied

    affect_modify(ch, _drain(modifier=-4), True)   # curr str 16 -> 12, drop fires

    room_items = world.rooms._data[ROOM_VNUM]["items"]
    assert ch["equip"]["wield"] is None
    assert sword not in ch["inv"]
    assert room_items.count(sword) == 1            # NOT duplicated by recursion
    # base drain -4, weapon +3 reversed exactly once: 3 - 4 - 3 = -4.
    # A double drop would reverse +3 twice -> -7.
    assert ch["mod_stat"]["str"] == -4


def test_no_drop_when_still_strong_enough():
    """Drain that leaves str above the wield limit keeps the weapon seated."""
    _stub_room()
    ch = _player(18)                       # limit STR_APP_WIELD[18]=25 -> 250
    sword = _wield(ch, 150)

    affect_modify(ch, _drain(modifier=-2), True)   # str 16, limit 160 > 150

    assert ch["equip"]["wield"] is sword
    assert world.rooms._data[ROOM_VNUM]["items"].count(sword) == 0
