"""Own-inventory visibility gating (cf. 1stMud get_obj_carry/get_obj_wear
can_see_obj gates in handler.c:2017-2061 -- every player-facing lookup passes
the acting char as viewer, so unseen items can't be worn/quaffed/fetched).
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

from handler import _char_base
import handler
import inventory
import world
from world import ROOM_DEFS, MOB_DEFS, ITEM_DEFS

PLAIN_VNUM = 9420
GLOW_VNUM = 9421
POTION_VNUM = 9422


def _stub_room(vnum, **extra):
    room = {"name": "Test Room", "desc": "A test room.", "exits": {},
            "items": [], "mobs": [], "area": "test", "flags": {},
            "sector": "inside"}
    room.update(extra)
    ROOM_DEFS._data[vnum] = room
    world.rooms._data[vnum] = room
    return room


def _make_player(room=9001, **aff):
    ch = _char_base()
    ch["id"] = 1
    ch["name"] = "Tester"
    ch["level"] = 20
    ch["room"] = room
    ch["equip"] = {"body": None, "light": None}
    ch["affected_by"] = dict(aff)
    world.chars[1] = ch
    return ch


@pytest.fixture(autouse=True)
def _clean_world_state():
    old_rooms = dict(ROOM_DEFS._data)
    old_wrooms = dict(world.rooms._data)
    old_chars = dict(world.chars)
    old_items = dict(ITEM_DEFS._data)
    ITEM_DEFS._data[PLAIN_VNUM] = {
        "keywords": "tunic plain", "short_descr": "a plain tunic",
        "type": "armor", "level": 1, "extra_flags": {},
        "wear_flags": {"take": True, "body": True},
    }
    ITEM_DEFS._data[GLOW_VNUM] = {
        "keywords": "vest glowing", "short_descr": "a glowing vest",
        "type": "armor", "level": 1, "extra_flags": {"glow": True},
        "wear_flags": {"take": True, "body": True},
    }
    ITEM_DEFS._data[POTION_VNUM] = {
        "keywords": "potion murky", "short_descr": "a murky potion",
        "type": "potion", "level": 1, "extra_flags": {},
        "wear_flags": {"take": True},
    }
    _stub_room(9001)
    _stub_room(9002, sector="field", flags={"dark": True})
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
    monkeypatch.setattr(inventory, "tprint", capture)
    monkeypatch.setattr(handler, "tprint", capture)
    return lines


class TestDarkRoomGating:
    def test_wear_unseen_item_fails(self, out):
        player = _make_player(room=9002)
        tunic = {"vnum": PLAIN_VNUM}
        player["inv"].append(tunic)
        inventory.do_wear(player, ["tunic"])
        assert "You do not have that item." in out
        assert tunic in player["inv"]
        assert player["equip"]["body"] is None

    def test_wear_glow_item_works(self, out):
        player = _make_player(room=9002)
        vest = {"vnum": GLOW_VNUM}
        player["inv"].append(vest)
        inventory.do_wear(player, ["vest"])
        assert player["equip"]["body"] is vest
        assert vest not in player["inv"]

    def test_wear_all_skips_unseen(self, out):
        player = _make_player(room=9002)
        tunic = {"vnum": PLAIN_VNUM}
        vest = {"vnum": GLOW_VNUM}
        player["inv"].extend([tunic, vest])
        inventory.do_wear(player, ["all"])
        assert player["equip"]["body"] is vest
        assert tunic in player["inv"]

    def test_get_all_skips_unseen(self, out):
        player = _make_player(room=9002)
        tunic = {"vnum": PLAIN_VNUM}
        vest = {"vnum": GLOW_VNUM}
        world.rooms._data[9002]["items"].extend([tunic, vest])
        inventory.do_get(player, ["all"])
        assert vest in player["inv"]
        assert tunic not in player["inv"]
        assert tunic in world.rooms._data[9002]["items"]

    def test_remove_unseen_item_fails(self, out):
        player = _make_player(room=9002)
        tunic = {"vnum": PLAIN_VNUM}
        player["equip"]["body"] = tunic
        inventory.do_remove(player, ["tunic"])
        assert "You do not have that item." in out
        assert player["equip"]["body"] is tunic


class TestBlindGating:
    def test_blind_quaff_potion_works(self, out, monkeypatch):
        # cf. 1stMud can_see_obj blind exemption for potions (handler.c:2467)
        player = _make_player(blind=True)
        potion = {"vnum": POTION_VNUM}
        player["inv"].append(potion)
        called = []
        monkeypatch.setattr(inventory, "validate_item_spell_payload",
                            lambda obj: obj)
        monkeypatch.setattr(inventory, "cast_item_spells",
                            lambda ch, obj, victim, target: called.append(obj))
        inventory.do_quaff(player, ["potion"])
        assert called == [potion]
        assert potion not in player["inv"]

    def test_blind_wear_fails(self, out):
        player = _make_player(blind=True)
        tunic = {"vnum": PLAIN_VNUM}
        player["inv"].append(tunic)
        inventory.do_wear(player, ["tunic"])
        assert "You do not have that item." in out
        assert tunic in player["inv"]
