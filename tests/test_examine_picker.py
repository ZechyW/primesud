"""Tests for do_examine no-args picker. [PRIMESUD]"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import handler
import info
import world
from handler import _char_base
from world import ITEM_DEFS, MOB_DEFS, ROOM_DEFS


@pytest.fixture
def out(monkeypatch):
    """Capture tprint output as list of lines."""
    lines = []
    capture = lambda s="", end="\n": lines.append(s)
    monkeypatch.setattr(handler, "tprint", capture)
    # some tests use players not registered as world.chars[1]; capture
    # chprintln at the info level so their output is not gate-dropped
    monkeypatch.setattr(info, "chprintln", lambda ch, s="": lines.append(s))
    return lines


@pytest.fixture
def scene(monkeypatch):
    """Room 3001 with one mob and one item; player carrying one item."""
    old_rooms = dict(world.rooms._data)
    old_defs = dict(ROOM_DEFS._data)
    old_chars = dict(world.chars)
    old_mobs = dict(MOB_DEFS._data)
    old_items = dict(ITEM_DEFS._data)

    room = {"name": "Test Room", "desc": "x", "exits": {}, "items": [],
            "mobs": [], "area": "test", "sector": "inside"}
    world.rooms._data[3001] = room
    ROOM_DEFS._data[3001] = room

    MOB_DEFS._data[9001] = {"short_descr": "a guard", "keywords": "guard",
                            "level": 5, "description": "A burly guard."}
    mob = _char_base()
    mob.update({"is_npc": True, "id": 2, "tpl": 9001, "room": 3001,
                "hit": 50, "max_hit": 50})
    world.chars[2] = mob
    room["mobs"] = [2]

    ITEM_DEFS._data[8001] = {"type": "trash", "short_descr": "a rock",
                             "keywords": "rock", "description": "Just a rock."}
    ITEM_DEFS._data[8002] = {"type": "trash", "short_descr": "a stick",
                             "keywords": "stick", "description": "Just a stick."}
    room["items"] = [8001]

    player = _char_base()
    player.update({"id": 1, "room": 3001, "inv": [8002]})
    world.chars[1] = player

    yield player

    world.rooms._data.clear()
    world.rooms._data.update(old_rooms)
    ROOM_DEFS._data.clear()
    ROOM_DEFS._data.update(old_defs)
    world.chars.clear()
    world.chars.update(old_chars)
    MOB_DEFS._data.clear()
    MOB_DEFS._data.update(old_mobs)
    ITEM_DEFS._data.clear()
    ITEM_DEFS._data.update(old_items)


def test_empty_scene_prints_prompt(monkeypatch, out):
    """No targets anywhere -> 'nothing here' notice, no picker."""
    room = {"name": "Empty", "desc": "x", "exits": {}, "items": [],
            "mobs": [], "area": "test", "sector": "inside"}
    old = dict(world.rooms._data)
    old_defs = dict(ROOM_DEFS._data)
    world.rooms._data[3001] = room
    ROOM_DEFS._data[3001] = room
    player = _char_base()
    player.update({"room": 3001, "inv": []})
    called = []
    monkeypatch.setattr(info, "pick_from", lambda t, o: called.append(o) or 0)
    try:
        info.do_examine(player, [])
    finally:
        world.rooms._data.clear()
        world.rooms._data.update(old)
        ROOM_DEFS._data.clear()
        ROOM_DEFS._data.update(old_defs)
    assert called == []
    assert "There is nothing here to examine." in out


def test_picker_lists_mobs_then_items(monkeypatch, out, scene):
    seen = {}
    monkeypatch.setattr(info, "pick_from",
                        lambda title, opts: seen.update(opts=opts) or -1)
    info.do_examine(scene, [])
    assert seen["opts"] == ["a guard", "a rock", "a stick"]


def test_pick_mob_shows_char(monkeypatch, out, scene):
    monkeypatch.setattr(info, "pick_from", lambda t, o: 0)
    # resolved history string uses a single-word token: typed examine reads
    # args[0] only
    assert info.do_examine(scene, []) == "examine guard"
    assert "A burly guard." in out


def test_pick_room_item_shows_description(monkeypatch, out, scene):
    monkeypatch.setattr(info, "pick_from", lambda t, o: 1)
    assert info.do_examine(scene, []) == "examine rock"
    assert "Just a rock." in out


def test_pick_inventory_item_shows_description(monkeypatch, out, scene):
    monkeypatch.setattr(info, "pick_from", lambda t, o: 2)
    info.do_examine(scene, [])
    assert "Just a stick." in out


def test_cancel_prints_nothing(monkeypatch, out, scene):
    monkeypatch.setattr(info, "pick_from", lambda t, o: -1)
    info.do_examine(scene, [])
    assert out == []


class TestPickerRoomDetailsAndExits:
    """[PRIMESUD] picker also offers room extra descriptions ({c, first keyword)
    and exits that carry a description ({g, full direction name), after the mob
    and room-object entries but before carried items and worn equipment."""

    def _decorate(self):
        """Add extra_descs and a mix of exits (with and without descriptions)."""
        room = ROOM_DEFS._data[3001]
        room["extra_descs"] = [("plant plants", "A leafy green plant."),
                               ("sign", "The sign reads: keep out.")]
        room["exits"] = {
            "n": 3002,                                    # plain int: no desc
            "e": {"to": 3002, "desc": "A shimmering gate."},
            "s": {"to": 3002},                            # dict, but no desc
            "d": {"to": 3002, "desc": "A dark hole.",
                  "keyword": "trapdoor", "isdoor": True, "closed": True},
        }

    def _offers(self, monkeypatch, idx=-1):
        offered = []

        def pick(title, opts):
            offered.append(opts)
            return idx

        monkeypatch.setattr(info, "pick_from", pick)
        return offered

    def test_picker_order_mobs_room_objs_eds_exits_carried(self, monkeypatch, out, scene):
        self._decorate()
        offered = self._offers(monkeypatch)
        info.do_examine(scene, [])
        assert offered == [["a guard", "a rock",
                            "{cplant{x", "{csign{x",
                            "{geast{x", "{gdown{x",
                            "a stick"]]

    def test_exits_without_desc_not_offered(self, monkeypatch, out, scene):
        self._decorate()
        offered = self._offers(monkeypatch)
        info.do_examine(scene, [])
        assert "{gnorth{x" not in offered[0]  # plain int exit
        assert "{gsouth{x" not in offered[0]  # dict exit with no desc

    def test_no_eds_or_exits_leaves_menu_unchanged(self, monkeypatch, out, scene):
        offered = self._offers(monkeypatch)
        info.do_examine(scene, [])
        assert offered == [["a guard", "a rock", "a stick"]]

    def test_pick_room_object_shows_desc(self, monkeypatch, out, scene):
        self._decorate()
        self._offers(monkeypatch, idx=1)
        assert info.do_examine(scene, []) == "examine rock"
        assert "Just a rock." in out

    def test_pick_ed_shows_desc(self, monkeypatch, out, scene):
        self._decorate()
        self._offers(monkeypatch, idx=2)
        assert info.do_examine(scene, []) == "examine plant"
        assert "A leafy green plant." in out

    def test_pick_second_ed_shows_desc(self, monkeypatch, out, scene):
        self._decorate()
        self._offers(monkeypatch, idx=3)
        assert info.do_examine(scene, []) == "examine sign"
        assert "The sign reads: keep out." in out

    def test_pick_exit_shows_desc(self, monkeypatch, out, scene):
        self._decorate()
        self._offers(monkeypatch, idx=4)
        assert info.do_examine(scene, []) == "examine east"
        assert "A shimmering gate." in out
        assert not any("closed" in line for line in out)

    def test_pick_door_exit_shows_desc_and_door_state(self, monkeypatch, out, scene):
        self._decorate()
        self._offers(monkeypatch, idx=5)
        assert info.do_examine(scene, []) == "examine down"
        assert "A dark hole." in out
        assert "The trapdoor is closed." in out

    def test_pick_carried_object_after_eds_and_exits(self, monkeypatch, out, scene):
        """carried entries sit last, so their index is shifted past eds/exits"""
        self._decorate()
        self._offers(monkeypatch, idx=6)
        assert info.do_examine(scene, []) == "examine stick"
        assert "Just a stick." in out

    def test_dark_room_hides_eds_and_exits(self, monkeypatch, out, scene):
        """eds/exits honour do_look's pitch-black gate; mobs/objs are already
        hidden by can_see/can_see_obj, so the picker never opens and the
        empty-menu fallthrough explains why with do_look's dark line."""
        self._decorate()
        ROOM_DEFS._data[3001]["flags"] = {"dark": True}
        offered = self._offers(monkeypatch)
        info.do_examine(scene, [])
        assert offered == []
        assert out == ["It is pitch black ... "]

    def test_blind_player_gets_no_eds_or_exits(self, monkeypatch, out, scene):
        """eds/exits honour do_look's blind gate; the empty picker falls
        through to check_blind's line rather than the bare arg prompt."""
        self._decorate()
        scene["affected_by"]["blind"] = True
        offered = self._offers(monkeypatch)
        info.do_examine(scene, [])
        assert offered == []
        assert out == ["You can't see a thing!"]


def test_pick_object_shows_its_extra_desc(monkeypatch, out, scene):
    """Bank-letter regression: the picker delegates to do_look's typed scan,
    which prefers the object's extra_desc over its "taped to the wall" desc."""
    ITEM_DEFS._data[8004] = {
        "type": "furniture", "short_descr": "a letter", "keywords": "letter",
        "description": "The letter is taped to the wall.",
        "extra_descs": [("letter", "To whom it may concern.")],
    }
    world.rooms._data[3001]["items"].append(8004)
    monkeypatch.setattr(info, "pick_from", lambda t, o: 2)  # guard, rock, letter
    assert info.do_examine(scene, []) == "examine letter"
    assert "To whom it may concern." in out
    assert "The letter is taped to the wall." not in out


def test_pick_object_sharing_keyword_uses_cumulative_token(monkeypatch, out, scene):
    """Carried and room copies of one keyword: the selected entry resolves via
    a cumulative "N." token counting mobs, then carried, then room objects."""
    scene["inv"].append({"vnum": 8001, "description": "Carried rock."})
    world.rooms._data[3001]["items"].append({"vnum": 8001,
                                             "description": "Room rock."})
    # guard, rock, room rock, stick, carried rock
    monkeypatch.setattr(info, "pick_from", lambda t, o: 2)
    assert info.do_examine(scene, []) == "examine 3.rock"
    assert "Room rock." in out
    assert "Carried rock." not in out


class TestLookEmitsExamineExtras:
    """[PRIMESUD] examine's extras live in do_look's object path, so a typed
    look and a typed examine of the same target print identically (DESIGN.md,
    "Look/examine merged for targeted lookups")."""

    def _money(self):
        ITEM_DEFS._data[8005] = {
            "type": "money", "short_descr": "a pile of coins",
            "keywords": "pile coins", "description": "A pile of coins.",
            "silver": 0, "gold": 5,
        }
        world.rooms._data[3001]["items"].append({"vnum": 8005, "silver": 0,
                                                 "gold": 5})

    def _chest(self):
        ITEM_DEFS._data[8006] = {
            "type": "container", "short_descr": "a chest", "keywords": "chest",
            "description": "A wooden chest.", "extra_flags": {},
        }
        world.rooms._data[3001]["items"].append(
            {"vnum": 8006, "contents": [{"vnum": 8002}]})

    def test_look_money_shows_coin_count(self, out, scene):
        self._money()
        info.do_look(scene, ["pile"])
        assert "A pile of coins." in out
        assert "There are 5 gold coins in the pile." in out

    def test_look_container_shows_contents(self, out, scene):
        self._chest()
        info.do_look(scene, ["chest"])
        assert "A wooden chest." in out
        assert "a chest holds:" in out
        assert "  a stick" in out

    def test_typed_examine_matches_typed_look(self, out, scene):
        self._chest()
        info.do_look(scene, ["chest"])
        looked = list(out)
        del out[:]
        info.do_examine(scene, ["chest"])
        assert out == looked

    def test_look_closed_container_says_closed(self, out, scene):
        ITEM_DEFS._data[8007] = {
            "type": "container", "short_descr": "a locked chest",
            "keywords": "chest", "description": "A locked chest.",
            "container_flags": {"closed": True},
        }
        world.rooms._data[3001]["items"].append(
            {"vnum": 8007, "contents": [{"vnum": 8002}]})
        info.do_look(scene, ["chest"])
        assert "It is closed." in out
        assert "a stick" not in out

    def test_look_drink_shows_fill_line(self, out, scene):
        ITEM_DEFS._data[8008] = {
            "type": "drink", "short_descr": "a fountain",
            "keywords": "fountain", "description": "A marble fountain.",
            "liquid_total": 100, "liquid_left": 100, "liquid_type": "water",
        }
        world.rooms._data[3001]["items"].append({"vnum": 8008})
        info.do_look(scene, ["fountain"])
        assert "A marble fountain." in out
        assert "It's more than half-filled with  a clear liquid." in out

    def test_extras_come_from_the_matched_instance(self, out, scene):
        """The scan's own instance is used, so a cumulative "N." token cannot
        drift onto a different pile the way get_obj_here re-resolution did."""
        self._money()
        scene["inv"].append({"vnum": 8005, "silver": 0, "gold": 1})
        # inventory is scanned first, so the room pile is match 2
        info.do_look(scene, ["2.pile"])
        assert "There are 5 gold coins in the pile." in out
        assert "Wow. One gold coin." not in out


def test_examine_legacy_sparse_money_uses_template(out, scene):
    ITEM_DEFS._data[8003] = {
        "type": "money", "short_descr": "A gold coin", "keywords": "gold coin",
        "description": "One valuable gold coin.", "silver": 0, "gold": 1,
    }
    info._examine_extras(scene, {"vnum": 8003})
    assert "Wow. One gold coin." in out
