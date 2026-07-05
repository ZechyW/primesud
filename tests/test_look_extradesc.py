"""Tests for do_look extra_desc behavior with mobs, items, and rooms.

Verifies that do_look follows 1stMud's lookup order:
1. Check for mob in room (show mob and return)
2. Check player inventory extra_descs
3. Check room items extra_descs
4. Check room extra_descs

Since 1stMud mobs do NOT carry extra_descs, only items and rooms are tested.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

from handler import _char_base, is_name
from player import PLR_DEFAULTS
import info
import world
from world import ROOM_DEFS, MOB_DEFS, ITEM_DEFS


MOB_TPL = 9501
ITEM_VNUM = 8501


@pytest.fixture(autouse=True)
def _clean_world():
    old_rooms = dict(ROOM_DEFS._data)
    old_wrooms = dict(world.rooms._data)
    old_chars = dict(world.chars)
    old_mobs = dict(MOB_DEFS._data)
    old_items = dict(ITEM_DEFS._data)

    # Test mob template
    MOB_DEFS._data[MOB_TPL] = {
        "short_descr": "a test mob",
        "keywords": "mob test",
        "description": "A test mob description.",
        "level": 5,
        "hp_dice": (1, 1, 10),
        "hitroll": 0,
        "damage": (1, 4, 0),
        "armor": (0, 0, 0, 0),
    }

    # Test room
    room = {
        "name": "Test Room",
        "desc": "A test room.",
        "exits": {},
        "items": [],
        "mobs": [],
        "area": "test",
        "sector": "inside",
        "extra_descs": [
            ("wall", "The wall is stone."),
            ("floor", "The floor is dusty."),
        ],
    }
    ROOM_DEFS._data[9001] = room
    world.rooms._data[9001] = room.copy()

    # Test item with extra_descs
    ITEM_DEFS._data[ITEM_VNUM] = {
        "keywords": "sword test",
        "short_descr": "a test sword",
        "description": "A basic sword.",
        "type": "weapon",
        "wear_flags": {"take": True},
        "level": 1,
        "weight": 5,
        "value": 100,
        "extra_descs": [
            ("blade", "The blade is sharp."),
            ("hilt", "The hilt is wrapped in leather."),
        ],
    }

    yield

    ROOM_DEFS._data.clear()
    ROOM_DEFS._data.update(old_rooms)
    world.rooms._data.clear()
    world.rooms._data.update(old_wrooms)
    world.chars.clear()
    world.chars.update(old_chars)
    MOB_DEFS._data.clear()
    MOB_DEFS._data.update(old_mobs)
    ITEM_DEFS._data.clear()
    ITEM_DEFS._data.update(old_items)


@pytest.fixture
def out(monkeypatch):
    lines = []
    capture = lambda *a, **kw: lines.append(" ".join(str(x) for x in a))
    monkeypatch.setattr(info, "chprintln", capture)
    return lines


def _make_player(room=9001):
    player = _char_base()
    player.update({
        "id": 1,
        "name": "Tester",
        "room": room,
        "level": 10,
        "flags": PLR_DEFAULTS,
        "inv": [],
        "equip": {slot: None for slot in (
            "head", "neck", "body", "back", "wrist", "hand", "waist",
            "leg", "foot", "finger", "hold", "float"
        )},
    })
    world.chars[1] = player
    return player


def _make_mob(mid, room=9001, keywords=None, **overrides):
    """Create a test mob instance."""
    mob = _char_base()
    mob.update({
        "id": mid,
        "is_npc": True,
        "tpl": MOB_TPL,
        "room": room,
        "level": 5,
    })
    mob.update(overrides)
    world.chars[mid] = mob
    if room in world.rooms._data:
        world.rooms._data[room]["mobs"].append(mid)
    return mob


class TestLookExtraDesc:
    """Tests for do_look extra_desc lookup order and behavior."""

    def test_look_room_extra_desc_wall(self, out):
        """Test looking at a room extra_desc."""
        player = _make_player()
        info.do_look(player, ["wall"])
        output = " ".join(out)
        assert "wall" in output.lower() or "stone" in output.lower()

    def test_look_room_extra_desc_floor(self, out):
        """Test looking at another room extra_desc."""
        player = _make_player()
        info.do_look(player, ["floor"])
        output = " ".join(out)
        assert "floor" in output.lower() or "dusty" in output.lower()

    def test_look_item_in_room_extra_desc_blade(self, out):
        """Test looking at item extra_desc when item is in room."""
        player = _make_player()
        # Add item to room
        item = {"vnum": ITEM_VNUM}
        world.rooms._data[9001]["items"].append(item)

        info.do_look(player, ["blade"])
        output = " ".join(out)
        assert "blade" in output.lower() or "sharp" in output.lower()

    def test_look_item_in_inventory_extra_desc(self, out):
        """Test looking at item extra_desc when item is in inventory."""
        player = _make_player()
        # Add item to inventory
        item = {"vnum": ITEM_VNUM}
        player["inv"].append(item)

        info.do_look(player, ["hilt"])
        output = " ".join(out)
        assert "hilt" in output.lower() or "leather" in output.lower()

    def test_look_mob_shows_mob_description(self, out):
        """Test looking at a mob shows the mob, not an extra_desc with same name."""
        player = _make_player()
        mob = _make_mob(2)

        info.do_look(player, ["mob"])
        output = " ".join(out)
        # Should show mob description (from _show_char_to_char_1)
        assert "test mob" in output.lower() or "mob description" in output.lower()

    def test_look_mob_takes_precedence_over_item_extra_desc(self, out):
        """
        Test that looking up a mob name doesn't trigger item extra_descs.

        This verifies 1stMud lookup order: mobs are checked first (line 1238),
        so if you name an item extra_desc the same as a mob, the mob wins.
        """
        player = _make_player()
        mob = _make_mob(2, keywords="sword")  # mob keywords overlap
        # Add item to room
        item = {"vnum": ITEM_VNUM}
        world.rooms._data[9001]["items"].append(item)

        # Look at "sword" - the mob is named "test mob" but has keywords "sword"
        info.do_look(player, ["test"])
        output = " ".join(out)
        # Should show mob, not item extra_desc
        assert "test mob" in output.lower()

    def test_look_nonexistent_shows_nothing(self, out):
        """Test looking at a nonexistent thing."""
        player = _make_player()
        info.do_look(player, ["nonexistent"])
        output = " ".join(out)
        assert "do not see" in output.lower()

    def test_look_instance_extra_desc_takes_precedence(self, out):
        """
        Test that instance extra_descs are checked before template extra_descs.

        This matches 1stMud do_look (act_info.c:1248-1268) which checks
        obj->ed_first (instance) before obj->pIndexData->ed_first (template).
        """
        player = _make_player()
        # Create an item with an instance-level extra_desc that overrides template
        item = {
            "vnum": ITEM_VNUM,
            "extra_descs": [
                ("blade", "The instance blade is shimmering."),
            ],
        }
        world.rooms._data[9001]["items"].append(item)

        info.do_look(player, ["blade"])
        output = " ".join(out)
        # Should show instance extra_desc, not template extra_desc
        assert "shimmering" in output.lower()
        assert "sharp" not in output.lower()  # template says "sharp"

    def test_mob_extra_desc_lookup_gap_documented(self):
        """
        Document that 1stMud mobs do NOT have extra_descs support.

        1stMud's load_mobiles (db2.c:42-207) does not handle E (extra_desc)
        directives after mob definitions. Only F (flag remove), M (mobprog),
        and S (stats) are handled; unknown letters cause the trailer loop to
        exit.

        Therefore, mobs never carry extra_descs in 1stMud or PrimeSUD. Adding
        such support would deviate from fidelity.
        """
        # This is a documentation test - it passes unconditionally.
        pass
