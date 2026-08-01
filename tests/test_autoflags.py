"""Tests for PLR_AUTOEXIT / PLR_AUTODAMAGE / PLR_AUTOASSIST (act_info.c/fight.c)."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

from handler import (_char_base, PLR_AUTOEXIT, PLR_AUTODAMAGE, PLR_AUTOASSIST,
                     PLR_DEFAULTS)
import combat
from combat import check_assist, dam_message
from config import TYPE_HIT
import handler
import info
import world
from world import ROOM_DEFS, MOB_DEFS

MOB_TPL = 9401


def _stub_room(vnum, **extra):
    room = {"name": "Test Room", "desc": "A test room.", "exits": {},
            "items": [], "mobs": [], "area": "test", "flags": {},
            "sector": "inside"}
    room.update(extra)
    ROOM_DEFS._data[vnum] = room
    world.rooms._data[vnum] = room
    return room


def _make_player(room=9001):
    ch = _char_base()
    ch["id"] = 1
    ch["name"] = "Tester"
    ch["level"] = 20
    ch["room"] = room
    ch["flags"] = PLR_DEFAULTS
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
def _clean_world_state():
    old_rooms = dict(ROOM_DEFS._data)
    old_wrooms = dict(world.rooms._data)
    old_chars = dict(world.chars)
    old_mobs = dict(MOB_DEFS._data)
    MOB_DEFS._data[MOB_TPL] = {
        "short_descr": "a test dog", "long_descr": "A test dog is here.",
        "keywords": "dog test", "level": 5, "race": "Human",
        "hp_dice": (1, 1, 10), "hitroll": 0, "damage": (1, 4, 0),
        "armor": (0, 0, 0, 0),
    }
    _stub_room(9001, exits={"n": 9002})
    _stub_room(9002)
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
    capture = lambda *a, **kw: lines.append(" ".join(str(x) for x in a))
    monkeypatch.setattr(handler, "tprint", capture)
    return lines


# -- toggles -----------------------------------------------------------------

def test_toggles_flip_bits_and_report(out):
    player = _make_player()
    for do_fn, bit, on_msg in (
        (info.do_autoexit, PLR_AUTOEXIT, "Exits will now be displayed."),
        (info.do_autodamage, PLR_AUTODAMAGE, "You now see damage amounts in combat."),
        (info.do_autoassist, PLR_AUTOASSIST, "You now assist group members in combat."),
    ):
        assert player["flags"] & bit  # default on (cf. pload_default)
        do_fn(player, [])
        assert not player["flags"] & bit
        do_fn(player, [])
        assert player["flags"] & bit
        assert on_msg in out


def test_autolist_shows_new_toggles(out):
    player = _make_player()
    info.do_autolist(player, [])
    listing = "\n".join(out)
    for name in ("autodamage", "autoassist", "autoexit"):
        assert name in listing


# -- autoexit gates do_look exits line ----------------------------------------

def test_look_exits_respect_autoexit(out):
    player = _make_player()
    player["flags"] &= ~1  # automap off; keep the look output simple
    info.do_look(player, [])
    assert any("[Exits:" in l for l in out)
    del out[:]
    player["flags"] &= ~PLR_AUTOEXIT
    info.do_look(player, [])
    assert not any("[Exits:" in l for l in out)


# -- autodamage gates dam_message tags -----------------------------------------

def test_dam_message_tag_follows_autodamage(out):
    player = _make_player()
    mob = _make_mob(2)
    dam_message(player, mob, 42, TYPE_HIT, False)
    assert any("[{R42{W]" in l for l in out)
    del out[:]
    player["flags"] &= ~PLR_AUTODAMAGE
    dam_message(player, mob, 42, TYPE_HIT, False)
    assert not any("42" in l for l in out)
    # victim side: mob hits player, tag follows the player's flag
    del out[:]
    dam_message(mob, player, 7, TYPE_HIT, False)
    assert not any("[{R7{W]" in l for l in out)
    player["flags"] |= PLR_AUTODAMAGE
    del out[:]
    dam_message(mob, player, 7, TYPE_HIT, False)
    assert any("[{R7{W]" in l for l in out)


# -- autoassist: player joins the pet's fight -----------------------------------

def _pet_fight_scene():
    player = _make_player()
    pet = _make_mob(2)
    pet["affected_by"] = {"charm": True}
    pet["master"] = 1
    pet["leader"] = 1
    victim = _make_mob(3)
    pet["fighting"] = 3
    return player, pet, victim


def test_autoassist_player_joins_pet_fight(out, monkeypatch):
    player, pet, victim = _pet_fight_scene()
    hits = []
    monkeypatch.setattr(combat, "multi_hit", lambda ch, v, *a: hits.append((ch["id"], v["id"])))
    check_assist(pet, victim)
    assert (1, 3) in hits


def test_autoassist_off_player_stays_idle(out, monkeypatch):
    player, pet, victim = _pet_fight_scene()
    player["flags"] &= ~PLR_AUTOASSIST
    hits = []
    monkeypatch.setattr(combat, "multi_hit", lambda ch, v, *a: hits.append((ch["id"], v["id"])))
    check_assist(pet, victim)
    assert (1, 3) not in hits


def test_autoassist_ignores_uncharmed_attacker(out, monkeypatch):
    player, pet, victim = _pet_fight_scene()
    pet["affected_by"] = {}
    hits = []
    monkeypatch.setattr(combat, "multi_hit", lambda ch, v, *a: hits.append((ch["id"], v["id"])))
    check_assist(pet, victim)
    assert (1, 3) not in hits
