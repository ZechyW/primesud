"""Tests for do_hunt / find_path / get_char_area (cf. 1stMud hunt.c)."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

from handler import _char_base
import handler
import hunt
import world
from world import ROOM_DEFS, MOB_DEFS, ITEM_DEFS

MOB_TPL = 9401


def _stub_room(vnum, area="test", **extra):
    room = {"name": "Test Room", "desc": "A test room.", "exits": {},
            "items": [], "mobs": [], "area": area, "flags": {},
            "sector": "inside"}
    room.update(extra)
    ROOM_DEFS._data[vnum] = room
    world.rooms._data[vnum] = room
    return room


def _make_player(room=9001):
    ch = _char_base()
    ch["id"] = 1
    ch["name"] = "Tester"
    ch["level"] = 30
    ch["room"] = room
    ch["learned"] = {}  # pcdata field: check_improve reads it
    world.chars[1] = ch
    return ch


def _make_mob(mid, room=9001, **overrides):
    ch = _char_base()
    ch["id"] = mid
    ch["is_npc"] = True
    ch["tpl"] = MOB_TPL
    ch["name"] = "a test dog"
    ch["level"] = 5
    ch["room"] = room
    ch.update(overrides)
    world.chars[mid] = ch
    if room in world.rooms._data:
        world.rooms._data[room]["mobs"].append(mid)
    return ch


@pytest.fixture(autouse=True)
def _clean_world_state(monkeypatch):
    old_rooms = dict(ROOM_DEFS._data)
    old_wrooms = dict(world.rooms._data)
    old_chars = dict(world.chars)
    old_mobs = dict(MOB_DEFS._data)
    old_items = dict(ITEM_DEFS._data)
    MOB_DEFS._data[MOB_TPL] = {
        "short_descr": "a test dog", "long_descr": "A test dog is here.",
        "keywords": "dog test", "level": 5, "race": "Human",
        "hp_dice": (1, 1, 10), "hitroll": 0, "damage": (1, 4, 0),
        "armor": (0, 0, 0, 0),
    }
    # 9001 -n-> 9002 -e-> 9003; 9004 in another area
    _stub_room(9001, exits={"n": 9002})
    _stub_room(9002, exits={"s": 9001, "e": 9003})
    _stub_room(9003, exits={"w": 9002})
    _stub_room(9004, area="elsewhere")
    monkeypatch.setattr(hunt, "get_skill", lambda ch, sn, *a: 100)
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
    monkeypatch.setattr(handler, "tprint", capture)
    return lines


def test_find_path_first_step():
    assert hunt.find_path(9001, 9003) == "n"
    assert hunt.find_path(9003, 9001) == "w"
    assert hunt.find_path(9001, 9002) == "n"


def test_find_path_area_restricted():
    ROOM_DEFS._data[9003]["exits"]["e"] = 9004
    ROOM_DEFS._data[9004]["exits"] = {"w": 9003, "n": 9005}
    _stub_room(9005, area="elsewhere")
    # direct neighbour across the border is still found...
    assert hunt.find_path(9001, 9004) == "n"
    # ...but rooms beyond it are not expanded
    assert hunt.find_path(9001, 9005) is None


def test_hunt_reports_direction(out):
    player = _make_player(9001)
    _make_mob(2, room=9003)
    hunt.do_hunt(player, ["dog"])
    assert any("is north from here" in l for l in out)
    assert player["move"] == 100 - 3
    assert player["wait"] > 0


def test_hunt_same_room(out):
    player = _make_player(9001)
    _make_mob(2, room=9001)
    hunt.do_hunt(player, ["dog"])
    assert any("is here!" in l for l in out)
    assert player["move"] == 100  # no cost


def test_hunt_no_victim(out):
    player = _make_player(9001)
    _make_mob(2, room=9004)  # other area: not huntable
    hunt.do_hunt(player, ["dog"])
    assert any("No-one around by that name" in l for l in out)


def test_hunt_no_path(out):
    player = _make_player(9001)
    _stub_room(9006)  # same area, unconnected
    _make_mob(2, room=9006)
    hunt.do_hunt(player, ["dog"])
    assert any("couldn't find a path" in l for l in out)


def test_hunt_exhausted(out):
    player = _make_player(9001)
    player["move"] = 2
    _make_mob(2, room=9003)
    hunt.do_hunt(player, ["dog"])
    assert any("too exhausted" in l for l in out)


def test_hunt_unskilled(monkeypatch, out):
    player = _make_player(9001)
    _make_mob(2, room=9003)
    monkeypatch.setattr(hunt, "get_skill", lambda ch, sn, *a: 0)
    hunt.do_hunt(player, ["dog"])
    assert any("don't know how to hunt" in l for l in out)


def test_hunt_failed_roll_random_direction(monkeypatch, out):
    player = _make_player(9002)  # exits s and e
    _make_mob(2, room=9003)
    monkeypatch.setattr(hunt, "get_skill", lambda ch, sn, *a: 50)
    # roll 90 > 50 fails; then pick exits[0] = "e" (EXIT_ORDER order)
    rolls = iter([90, 0])
    monkeypatch.setattr(hunt, "randint", lambda a, b: next(rolls))
    hunt.do_hunt(player, ["dog"])
    assert any("is east from here" in l for l in out)


# -- hunt_victim (cf. 1stMud hunt_victim in hunt.c) --------------------------
# [PRIMESUD] Dormant scaffolding: nothing sets ch["hunting"] in-game, so
# these tests drive hunt_victim() directly with a pre-seeded "hunting" id.

def test_hunt_victim_prey_gone(out):
    _make_player(9001)  # so TO_ROOM act messages have somewhere to route
    hunter = _make_mob(2, room=9001, hunting=99)  # 99: no such char
    hunt.hunt_victim(hunter)
    assert hunter["hunting"] is None
    assert any("Damn!  My prey is gone!!" in l for l in out)


def test_hunt_victim_prey_not_visible(monkeypatch, out):
    _make_player(9001)
    hunter = _make_mob(2, room=9001, hunting=3)
    _make_mob(3, room=9001)
    monkeypatch.setattr(hunt, "can_see", lambda ch, v: False)
    hunt.hunt_victim(hunter)
    assert hunter["hunting"] is None
    assert any("Damn!  My prey is gone!!" in l for l in out)


def test_hunt_victim_same_room_kills_prey(monkeypatch, out):
    import combat
    _make_player(9001)
    hunter = _make_mob(2, room=9001, hunting=3)
    _make_mob(3, room=9001)
    monkeypatch.setattr(hunt, "randint", lambda a, b: 10)  # < 60 -> "Ye shall DIE!" trio
    calls = []
    monkeypatch.setattr(combat, "multi_hit", lambda a, b: calls.append((a["id"], b["id"])))
    hunt.hunt_victim(hunter)
    assert calls == [(2, 3)]
    assert hunter["hunting"] is None
    assert any("Ye shall DIE!" in l for l in out)


def test_hunt_victim_same_room_recognizes_prey(monkeypatch, out):
    import combat
    _make_player(9001)
    hunter = _make_mob(2, room=9001, hunting=3)
    _make_mob(3, room=9001)
    monkeypatch.setattr(hunt, "randint", lambda a, b: 90)  # >= 60 -> "Hey, I remember you!" trio
    calls = []
    monkeypatch.setattr(combat, "multi_hit", lambda a, b: calls.append((a["id"], b["id"])))
    hunt.hunt_victim(hunter)
    assert calls == [(2, 3)]
    assert hunter["hunting"] is None
    assert any("Hey, I remember you!" in l for l in out)


def test_hunt_victim_moves_toward_prey(monkeypatch):
    import movement
    hunter = _make_mob(2, room=9001, hunting=3)
    _make_mob(3, room=9003)
    # 10 <= 50: keep find_path's computed direction (no random override)
    monkeypatch.setattr(hunt, "randint", lambda a, b: 10)
    calls = []
    monkeypatch.setattr(movement, "move_char", lambda ch, d: calls.append((ch["id"], d)))
    hunt.hunt_victim(hunter)
    assert calls == [(2, "n")]
    # 1stMud does not clear ch->hunting after a successful move
    assert hunter["hunting"] == 3
    assert hunter["wait"] > 0


def test_hunt_victim_closed_door_opens_instead_of_moving(monkeypatch):
    import movement
    hunter = _make_mob(2, room=9001, hunting=3)
    _make_mob(3, room=9003)
    ROOM_DEFS._data[9001]["exits"]["n"] = {"to": 9002, "closed": True, "isdoor": True}
    monkeypatch.setattr(hunt, "randint", lambda a, b: 10)
    open_calls = []
    move_calls = []
    monkeypatch.setattr(movement, "do_open", lambda ch, args: open_calls.append((ch["id"], args)))
    monkeypatch.setattr(movement, "move_char", lambda ch, d: move_calls.append((ch["id"], d)))
    hunt.hunt_victim(hunter)
    assert open_calls == [(2, ["north"])]
    assert move_calls == []


def test_hunt_victim_real_do_open_routes_output(monkeypatch, out):
    # NPC invoker: player in the room sees "$n opens the $d."; the
    # invoker-only "Ok." must NOT reach the terminal.
    _make_player(9001)
    hunter = _make_mob(2, room=9001, hunting=3)
    _make_mob(3, room=9003)
    ROOM_DEFS._data[9001]["exits"]["n"] = {"to": 9002, "closed": True,
                                           "isdoor": True}
    ROOM_DEFS._data[9002]["exits"]["s"] = {"to": 9001, "closed": True,
                                           "isdoor": True}
    monkeypatch.setattr(hunt, "randint", lambda a, b: 10)
    hunt.hunt_victim(hunter)
    assert not ROOM_DEFS._data[9001]["exits"]["n"]["closed"]
    assert not ROOM_DEFS._data[9002]["exits"]["s"]["closed"]
    assert any("opens the door" in l for l in out)
    assert not any("Ok." in l for l in out)


def test_hunt_victim_do_open_far_side_message(monkeypatch, out):
    # Player on the far side of the door sees "The $d opens."
    # (cf. act_move.c:483-485).
    _make_player(9002)
    hunter = _make_mob(2, room=9001, hunting=3)
    _make_mob(3, room=9003)
    ROOM_DEFS._data[9001]["exits"]["n"] = {"to": 9002, "closed": True,
                                           "isdoor": True}
    ROOM_DEFS._data[9002]["exits"]["s"] = {"to": 9001, "closed": True,
                                           "isdoor": True}
    monkeypatch.setattr(hunt, "randint", lambda a, b: 10)
    hunt.hunt_victim(hunter)
    assert any("The door opens." in l for l in out)


def test_hunt_victim_no_path_gives_up(out):
    _make_player(9001)
    _stub_room(9006)  # same area, unconnected
    hunter = _make_mob(2, room=9001, hunting=3)
    _make_mob(3, room=9006)
    hunt.hunt_victim(hunter)
    assert hunter["hunting"] is None
    assert any("Damn!  Lost" in l for l in out)
