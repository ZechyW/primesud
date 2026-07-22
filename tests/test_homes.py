"""Tests for static single-player housing adapted from 1stMud homes.c."""

import handler
import world
from game_state import load_world, save_world
from homes import (DEFAULT_HOME_DESC, HOME_KEY_VNUM, HOME_OFFICE_VNUM,
                   HOME_ROOM_VNUM, HOUSE_PRICE, HOUSE_TRIVIA, do_home)
from item import obj_vnum
from mob import create_area_states
from player import create_char


def _estate(fresh_world):
    rooms = {
        HOME_OFFICE_VNUM: {
            "name": "Office", "desc": "Office", "sector": "inside",
            "exits": {"n": {"to": HOME_ROOM_VNUM, "isdoor": True,
                              "closed": True, "locked": True,
                              "pickproof": True, "key": HOME_KEY_VNUM}},
        },
        HOME_ROOM_VNUM: {
            "name": "Unclaimed", "desc": "Empty", "sector": "inside",
            "exits": {"s": {"to": HOME_OFFICE_VNUM, "isdoor": True,
                              "closed": True, "key": HOME_KEY_VNUM}},
        },
    }
    objects = {
        HOME_KEY_VNUM: {
            "keywords": "key estate home", "short_descr": "an estate key",
            "description": "An estate key lies here.", "type": "key",
            "wear_flags": {"take": True}, "level": 0, "weight": 0,
            "value": 0,
        },
    }
    fresh_world.register_area("pestates", 17700, 17899, rooms=rooms,
                              objects=objects)
    fresh_world.setup()


def _player(room=HOME_OFFICE_VNUM):
    player = create_char()
    player["name"] = "Tester"
    player["room"] = room
    player["gold"] = HOUSE_PRICE
    player["trivia"] = HOUSE_TRIVIA
    player["_macros"] = {}
    world.chars[1] = player
    return player


def test_buy_customize_recall_and_round_trip(fresh_world, monkeypatch):
    _estate(fresh_world)
    monkeypatch.setattr(handler, "tprint", lambda *args, **kwargs: None)
    monkeypatch.setattr(world, "save_pending", False)
    player = _player()
    world.ROOM_DEFS[HOME_OFFICE_VNUM]  # load static estate and key template

    do_home(player, "buy")
    assert player["home_owned"] == 1
    assert player["gold"] == 0 and player["trivia"] == 0
    assert [obj_vnum(obj) for obj in player["inv"]].count(HOME_KEY_VNUM) == 1
    assert world.ROOM_DEFS[HOME_ROOM_VNUM]["desc"] == DEFAULT_HOME_DESC

    player["room"] = HOME_ROOM_VNUM
    do_home(player, "name The Snug Burrow")
    do_home(player, "describe Warm lamplight pools across the worn rug.")
    assert world.ROOM_DEFS[HOME_ROOM_VNUM]["name"] == "The Snug Burrow"
    assert world.ROOM_DEFS[HOME_ROOM_VNUM]["desc"].startswith("Warm lamplight")

    player["room"] = HOME_OFFICE_VNUM
    do_home(player, "recall")
    assert player["room"] == HOME_ROOM_VNUM
    assert save_world(quiet=True)

    world.reset_lazy()
    world.areas = create_area_states()
    loaded = create_char()
    loaded["_macros"] = {}
    world.chars[1] = loaded
    assert load_world() == "file"
    assert loaded["home_owned"] == 1
    assert loaded["home_name"] == "The Snug Burrow"
    assert world.ROOM_DEFS[HOME_ROOM_VNUM]["desc"].startswith("Warm lamplight")


def test_buy_gates_and_cosmetic_save_validation(fresh_world, monkeypatch):
    _estate(fresh_world)
    lines = []
    monkeypatch.setattr(handler, "tprint",
                        lambda text="", end="\n": lines.append(text))
    player = _player(room=HOME_ROOM_VNUM)
    world.ROOM_DEFS[HOME_ROOM_VNUM]

    do_home(player, "buy")
    assert not player["home_owned"]
    assert any("Player Estates office" in line for line in lines)

    player["home_owned"] = 1
    player["home_name"] = "Old Name"
    player["home_desc"] = DEFAULT_HOME_DESC
    do_home(player, 'name Bad~Name')
    do_home(player, 'describe Bad "description')
    assert player["home_name"] == "Old Name"
    assert player["home_desc"] == DEFAULT_HOME_DESC


def test_recall_loads_evicted_home_before_pet_transfer(fresh_world, monkeypatch):
    _estate(fresh_world)
    player = _player(room=1)
    player["home_owned"] = 1
    assert HOME_ROOM_VNUM not in world.rooms._data

    called = []

    def fake_recall(ch, location, what):
        assert HOME_ROOM_VNUM in world.rooms._data
        called.append((ch, location, what))

    monkeypatch.setattr("homes.perform_recall", fake_recall)
    do_home(player, "recall")
    assert called == [(player, HOME_ROOM_VNUM, "go home")]
