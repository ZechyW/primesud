"""Tests for mob special functions (special.py) vs 1stMud special.c."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

from handler import _char_base
import combat
import special
import world
from world import ROOM_DEFS, MOB_DEFS, ITEM_DEFS


MOB_TPL = 9401
TRASH_TPL = 9451
GEM_TPL = 9452


def _stub_room(vnum, **extra):
    room = {"name": "Test Room", "desc": "A test room.", "exits": {},
            "items": [], "mobs": [], "area": "test", "flags": {},
            "sector": "inside"}
    room.update(extra)
    ROOM_DEFS._data[vnum] = room
    world.rooms._data[vnum] = room
    return room


def _make_player(room=9001, **overrides):
    ch = _char_base()
    ch["id"] = 1
    ch["name"] = "Tester"
    ch["level"] = 20
    ch["room"] = room
    ch.update(overrides)
    world.chars[1] = ch
    return ch


def _make_mob(mid, room=9001, **overrides):
    ch = _char_base()
    ch["id"] = mid
    ch["is_npc"] = True
    ch["tpl"] = MOB_TPL
    ch["name"] = "a test mob"
    ch["level"] = 20
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
    old_items = dict(ITEM_DEFS._data)
    MOB_DEFS._data[MOB_TPL] = {
        "short_descr": "a test mob", "long_descr": "A test mob is here.",
        "keywords": "mob test", "level": 20, "race": "Human",
        "hp_dice": (1, 1, 10), "hitroll": 0, "damage": (1, 4, 0),
        "armor": (0, 0, 0, 0),
    }
    ITEM_DEFS._data[TRASH_TPL] = {
        "short_descr": "some trash", "keywords": "trash",
        "type": "trash", "wear_flags": {"take": True}, "value": 0,
    }
    ITEM_DEFS._data[GEM_TPL] = {
        "short_descr": "a gem", "keywords": "gem",
        "type": "gem", "wear_flags": {"take": True}, "value": 500,
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
    ITEM_DEFS._data.clear()
    ITEM_DEFS._data.update(old_items)


@pytest.fixture
def low_rolls(monkeypatch):
    """Force every randint to its minimum -- all chance gates pass."""
    monkeypatch.setattr(special, "randint", lambda a, b: a)


@pytest.fixture
def cast_log(monkeypatch):
    """Record _cast_spell calls instead of running real spells."""
    calls = []

    def fake(ch, spell_name, victim):
        calls.append((spell_name, victim))
        return True

    monkeypatch.setattr(special, "_cast_spell", fake)
    return calls


# ---------------------------------------------------------------------------
# Breath specs
# ---------------------------------------------------------------------------

def test_dragon_breathes_on_fighting_victim(low_rolls, cast_log):
    dragon = _make_mob(2, pos="fighting")
    player = _make_player()
    player["fighting"] = 2
    assert special.spec_breath_acid(dragon) is True
    assert cast_log == [("acid breath", player)]


def test_dragon_needs_fighting_position(low_rolls, cast_log):
    dragon = _make_mob(2)  # pos standing
    player = _make_player()
    player["fighting"] = 2
    assert special.spec_breath_acid(dragon) is False
    assert cast_log == []


def test_gas_breath_targets_room(low_rolls, cast_log):
    dragon = _make_mob(2, pos="fighting")
    _make_player()
    assert special.spec_breath_gas(dragon) is True
    assert cast_log == [("gas breath", None)]


def test_breath_any_dispatches(low_rolls, cast_log):
    dragon = _make_mob(2, pos="fighting")
    player = _make_player()
    player["fighting"] = 2
    assert special.spec_breath_any(dragon) is True  # roll 0 -> fire
    assert cast_log == [("fire breath", player)]


# ---------------------------------------------------------------------------
# spec_poison
# ---------------------------------------------------------------------------

def test_poison_bites_and_casts(low_rolls, cast_log):
    snake = _make_mob(2, pos="fighting")
    player = _make_player()
    snake["fighting"] = 1
    assert special.spec_poison(snake) is True
    assert cast_log == [("poison", player)]


# ---------------------------------------------------------------------------
# spec_thief
# ---------------------------------------------------------------------------

def test_thief_steals_from_sleeping_player(low_rolls):
    thief = _make_mob(2)  # pos standing
    player = _make_player(pos="sleeping", gold=1000, silver=500)
    assert special.spec_thief(thief) is True
    # randint -> min: gold = 1000 * min(1, 10) // 100 = 10
    assert player["gold"] == 990 and thief["gold"] == 10
    assert player["silver"] == 495 and thief["silver"] == 5


def test_thief_caught_by_awake_player(low_rolls):
    thief = _make_mob(2)
    player = _make_player(gold=1000)
    assert special.spec_thief(thief) is True
    assert player["gold"] == 1000  # caught -- nothing stolen


# ---------------------------------------------------------------------------
# spec_guard
# ---------------------------------------------------------------------------

def test_guard_attacks_most_evil_fighter(monkeypatch):
    guard = _make_mob(2)
    victim_mob = _make_mob(3)
    player = _make_player(alignment=-500)
    player["fighting"] = 3
    victim_mob["fighting"] = 1
    hits = []
    monkeypatch.setattr(special, "multi_hit",
                        lambda ch, victim, dt: hits.append((ch, victim)))
    assert special.spec_guard(guard) is True
    assert hits == [(guard, player)]  # player align -500 < mob align 0


def test_guard_ignores_good_fighters(monkeypatch):
    guard = _make_mob(2)
    victim_mob = _make_mob(3, alignment=350)
    player = _make_player(alignment=350)
    player["fighting"] = 3
    victim_mob["fighting"] = 1
    monkeypatch.setattr(special, "multi_hit",
                        lambda ch, victim, dt: pytest.fail("should not attack"))
    assert special.spec_guard(guard) is False


# ---------------------------------------------------------------------------
# spec_janitor
# ---------------------------------------------------------------------------

def test_janitor_picks_up_trash_vnum():
    janitor = _make_mob(2)
    room = world.rooms._data[9001]
    room["items"].append(TRASH_TPL)  # plain vnum, as area resets place them
    _make_player()
    assert special.spec_janitor(janitor) is True
    assert room["items"] == []
    assert janitor["inv"] == [TRASH_TPL]


def test_janitor_leaves_valuables():
    janitor = _make_mob(2)
    room = world.rooms._data[9001]
    room["items"].append({"vnum": GEM_TPL, "cost": 500})
    _make_player()
    assert special.spec_janitor(janitor) is False
    assert len(room["items"]) == 1


# ---------------------------------------------------------------------------
# spec_nasty
# ---------------------------------------------------------------------------

def test_nasty_slashes_purse(low_rolls):
    nasty = _make_mob(2, pos="fighting")
    player = _make_player(gold=100)
    nasty["fighting"] = 1
    assert special.spec_nasty(nasty) is True  # roll 0 -> purse slash
    assert player["gold"] == 90 and nasty["gold"] == 10


# ---------------------------------------------------------------------------
# spec_cast_undead / judge dispatch
# ---------------------------------------------------------------------------

def test_cast_judge_uses_high_explosive(low_rolls, cast_log):
    judge = _make_mob(2, pos="fighting")
    player = _make_player()
    player["fighting"] = 2
    assert special.spec_cast_judge(judge) is True
    assert cast_log == [("high explosive", player)]


def test_cast_undead_picks_level_spell(low_rolls, cast_log):
    undead = _make_mob(2, pos="fighting")
    player = _make_player()
    player["fighting"] = 2
    assert special.spec_cast_undead(undead) is True
    assert cast_log == [("curse", player)]  # roll 0 -> curse


# ---------------------------------------------------------------------------
# Gangland: spec_troll_member / spec_ogre_member / spec_patrolman
# ---------------------------------------------------------------------------

TROLL_TPL = 9403
OGRE_TPL = 9404


def _stub_gang_tpls():
    MOB_DEFS._data[TROLL_TPL] = {
        "short_descr": "a troll gangster", "level": 20,
        "group": special.MOB_VNUM_GROUP_TROLLS,
    }
    MOB_DEFS._data[OGRE_TPL] = {
        "short_descr": "an ogre gangster", "level": 20,
        "group": special.MOB_VNUM_GROUP_OGRES,
    }
    MOB_DEFS._data[special.MOB_VNUM_PATROLMAN] = {
        "short_descr": "a patrolman", "level": 25,
        "spec_fun": "spec_patrolman",
    }


def test_troll_member_attacks_ogre(low_rolls, monkeypatch):
    _stub_gang_tpls()
    troll = _make_mob(2, tpl=TROLL_TPL)
    ogre = _make_mob(3, tpl=OGRE_TPL)
    hits = []
    monkeypatch.setattr(special, "multi_hit",
                        lambda ch, victim, dt: hits.append((ch, victim)))
    assert special.spec_troll_member(troll) is True
    assert hits == [(troll, ogre)]


def test_gang_member_stands_down_near_patrolman(low_rolls, monkeypatch):
    _stub_gang_tpls()
    ogre = _make_mob(2, tpl=OGRE_TPL)
    _make_mob(3, tpl=special.MOB_VNUM_PATROLMAN)
    _make_mob(4, tpl=TROLL_TPL)
    monkeypatch.setattr(special, "multi_hit",
                        lambda ch, victim, dt: pytest.fail("should not attack"))
    assert special.spec_ogre_member(ogre) is False


def test_gang_member_idle_without_rivals(low_rolls, monkeypatch):
    _stub_gang_tpls()
    troll = _make_mob(2, tpl=TROLL_TPL)
    _make_mob(3, tpl=TROLL_TPL)  # same gang, not a target
    monkeypatch.setattr(special, "multi_hit",
                        lambda ch, victim, dt: pytest.fail("should not attack"))
    assert special.spec_troll_member(troll) is False


def test_patrolman_attacks_higher_level_fighter(low_rolls, monkeypatch):
    _stub_gang_tpls()
    patrolman = _make_mob(2, tpl=special.MOB_VNUM_PATROLMAN, level=25)
    brawler_hi = _make_mob(3, tpl=TROLL_TPL, level=22)
    brawler_lo = _make_mob(4, tpl=OGRE_TPL, level=18)
    brawler_hi["fighting"] = 4
    brawler_lo["fighting"] = 3
    hits = []
    monkeypatch.setattr(special, "multi_hit",
                        lambda ch, victim, dt: hits.append((ch, victim)))
    assert special.spec_patrolman(patrolman) is True
    assert hits == [(patrolman, brawler_hi)]


def test_patrolman_ignores_peaceful_room(low_rolls, monkeypatch):
    _stub_gang_tpls()
    patrolman = _make_mob(2, tpl=special.MOB_VNUM_PATROLMAN)
    _make_mob(3, tpl=TROLL_TPL)
    monkeypatch.setattr(special, "multi_hit",
                        lambda ch, victim, dt: pytest.fail("should not attack"))
    assert special.spec_patrolman(patrolman) is False
