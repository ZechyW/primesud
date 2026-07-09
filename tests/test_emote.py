"""Tests for do_emote (cf. 1stMud do_emote in act_comm.c)."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import combat
from comm import do_emote
import handler
from handler import _char_base
import world
from world import ROOM_DEFS, MOB_DEFS

MOB_TPL = 9405


def _stub_room(vnum):
    room = {"name": "Test Room", "desc": "x", "exits": {}, "items": [],
            "mobs": [], "area": "test", "flags": {}, "sector": "inside"}
    ROOM_DEFS._data[vnum] = room
    world.rooms._data[vnum] = room
    return room


def _make_char(cid=1, npc=False, **overrides):
    ch = _char_base()
    ch["id"] = cid
    ch["is_npc"] = npc
    ch["name"] = "Tester" if not npc else "a test mob"
    ch["level"] = 20
    ch["room"] = 9001
    if npc:
        ch["tpl"] = MOB_TPL
    ch.update(overrides)
    world.chars[cid] = ch
    if npc and 9001 in world.rooms._data:
        world.rooms._data[9001]["mobs"].append(cid)
    return ch


@pytest.fixture(autouse=True)
def _clean_world_state():
    old_rooms = dict(ROOM_DEFS._data)
    old_wrooms = dict(world.rooms._data)
    old_chars = dict(world.chars)
    old_mobs = dict(MOB_DEFS._data)
    MOB_DEFS._data[MOB_TPL] = {
        "short_descr": "a test mob", "long_descr": "A test mob is here.",
        "keywords": "mob test", "level": 5, "race": "Human",
        "hp_dice": (1, 1, 10), "hitroll": 0, "damage": (1, 4, 0),
        "armor": (0, 0, 0, 0),
    }
    _stub_room(9001)
    yield
    ROOM_DEFS._data.clear()
    ROOM_DEFS._data.update(old_rooms)
    world.rooms._data.clear()
    world.rooms._data.update(old_wrooms)
    world.chars.clear()
    world.chars.update(old_chars)
    MOB_DEFS._data.clear()
    MOB_DEFS._data.update(old_mobs)


@pytest.fixture
def out(monkeypatch):
    lines = []
    capture = lambda s="", end="\n": lines.append(s)
    monkeypatch.setattr(handler, "tprint", capture)
    return lines


def test_player_emote_shows_to_self(out):
    player = _make_char()
    do_emote(player, "grins wickedly.")
    # TO_CHAR: actor sees "$n $T" with their own name
    assert any("Tester grins wickedly." in l for l in out)


def test_player_emote_no_args(out):
    player = _make_char()
    do_emote(player, "")
    assert "Emote what?" in out


def test_npc_emote_visible_to_player(out):
    _make_char()  # player, same room
    npc = _make_char(2, npc=True)
    do_emote(npc, "screams and attacks!")
    # TO_ROOM from the NPC reaches the player; NPC's own TO_CHAR must not
    assert sum(1 for l in out if "screams and attacks!" in l) == 1
    assert any("A test mob screams and attacks!" in l for l in out)


def test_check_assist_scream_routes_through_emote(out, monkeypatch):
    # cf. fight.c:134 do_function(rch, &do_emote, "screams and attacks!")
    player = _make_char()
    victim = _make_char(2, npc=True)
    assister = _make_char(3, npc=True)
    assister["off_flags"] = {"assist_players": True}
    player["fighting"] = 2
    victim["fighting"] = 1
    hits = []
    monkeypatch.setattr(combat, "multi_hit",
                        lambda a, b, dt=None: hits.append((a["id"], b["id"])))
    combat.check_assist(player, victim)
    assert hits == [(3, 2)]
    assert any("A test mob screams and attacks!" in l for l in out)
