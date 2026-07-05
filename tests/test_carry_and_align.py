"""Tests for do_get/do_put carry limits, anti-align wear zap, and drop-coins
(cf. 1stMud act_obj.c get_obj/do_put/do_drop, handler.c equip_char). [PRIMESUD test]
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
from world import ROOM_DEFS, ITEM_DEFS

ROOM_VNUM = 9601
SWORD_VNUM = 9602
ROBE_VNUM = 9603
ANTI_EVIL_ROBE_VNUM = 9604
CHEST_VNUM = 9605
HEAVY_ITEM_VNUM = 9606
LIGHT_ITEM_VNUM = 9607
NODROP_VNUM = 9608
CORPSE_VNUM = 9609

_EQUIP_SLOTS = ("light", "finger_l", "finger_r", "neck_1", "neck_2", "body",
                "head", "legs", "feet", "hands", "arms", "shield", "about",
                "waist", "wrist_l", "wrist_r", "wield", "hold", "float",
                "secondary")


def _stub_room(vnum=ROOM_VNUM, **extra):
    room = {"name": "Test Room", "desc": "A test room.", "exits": {},
            "items": [], "mobs": [], "area": "test", "flags": {},
            "sector": "inside"}
    room.update(extra)
    ROOM_DEFS._data[vnum] = room
    world.rooms._data[vnum] = room
    return room


def _make_player(room=ROOM_VNUM, **overrides):
    ch = _char_base()
    ch.update({"id": 1, "name": "Tester", "level": 10, "room": room,
               "equip": {slot: None for slot in _EQUIP_SLOTS}})
    ch.update(overrides)
    world.chars[1] = ch
    return ch


@pytest.fixture(autouse=True)
def _clean_world_state():
    old_rooms = dict(ROOM_DEFS._data)
    old_wrooms = dict(world.rooms._data)
    old_chars = dict(world.chars)
    old_items = dict(ITEM_DEFS._data)

    ITEM_DEFS._data[SWORD_VNUM] = {
        "keywords": "sword test", "short_descr": "a test sword",
        "type": "weapon", "weapon_type": "sword", "dam_type": "slash",
        "dice": (1, 4, 0), "weapon_flags": {}, "level": 1, "weight": 20,
        "wear_flags": {"take": True, "wield": True}, "extra_flags": {},
    }
    ITEM_DEFS._data[ROBE_VNUM] = {
        "keywords": "robe test", "short_descr": "a test robe",
        "type": "armor", "level": 1, "weight": 10,
        "wear_flags": {"take": True, "body": True}, "extra_flags": {},
    }
    ITEM_DEFS._data[ANTI_EVIL_ROBE_VNUM] = {
        "keywords": "holy robe test", "short_descr": "a holy test robe",
        "type": "armor", "level": 1, "weight": 10,
        "wear_flags": {"take": True, "body": True},
        "extra_flags": {"anti_evil": True},
    }
    ITEM_DEFS._data[CHEST_VNUM] = {
        "keywords": "chest test", "short_descr": "a test chest",
        "type": "container", "level": 0, "weight": 0,
        "wear_flags": {}, "extra_flags": {},
        "container_max_weight": 10, "container_max_item_weight": 5,
        "container_weight_mult": 100, "container_flags": {},
    }
    ITEM_DEFS._data[HEAVY_ITEM_VNUM] = {
        "keywords": "anvil test", "short_descr": "a test anvil",
        "type": "misc", "level": 0, "weight": 60,
        "wear_flags": {"take": True}, "extra_flags": {},
    }
    ITEM_DEFS._data[LIGHT_ITEM_VNUM] = {
        "keywords": "pebble test", "short_descr": "a test pebble",
        "type": "misc", "level": 0, "weight": 10,
        "wear_flags": {"take": True}, "extra_flags": {},
    }
    ITEM_DEFS._data[NODROP_VNUM] = {
        "keywords": "cursed dagger test", "short_descr": "a cursed test dagger",
        "type": "misc", "level": 0, "weight": 5,
        "wear_flags": {"take": True}, "extra_flags": {"nodrop": True},
    }
    ITEM_DEFS._data[CORPSE_VNUM] = {
        "keywords": "corpse test", "short_descr": "a test corpse",
        "type": "npc_corpse", "level": 0, "weight": 0,
        "wear_flags": {}, "extra_flags": {},
    }
    # Real money templates (area_limbo.txt vnums 1-5), pre-seeded so
    # combat.create_money's create_object() calls don't trigger LazyDict
    # area loading (world._LOADED_AREAS is process-global and can be left
    # stale by other tests' fresh_world fixture use -- pre-seeding sidesteps
    # that entirely). [PRIMESUD test]
    ITEM_DEFS._data[world.I_COIN_SILVER_GCASH] = {
        "keywords": "coin silver gcash", "short_descr": "A silver coin",
        "type": "money", "wear_flags": {"take": True}, "level": 0,
        "weight": 10, "value": 0,
    }
    ITEM_DEFS._data[world.I_COIN_GOLD_GCASH] = {
        "keywords": "coin gold gcash", "short_descr": "A gold coin",
        "type": "money", "wear_flags": {"take": True}, "level": 0,
        "weight": 10, "value": 0,
    }
    ITEM_DEFS._data[world.I_COINS_GOLD_GCASH] = {
        "keywords": "coins gold gcash", "short_descr": "%d gold coins",
        "type": "money", "wear_flags": {"take": True}, "level": 0,
        "weight": 10, "value": 0,
    }
    ITEM_DEFS._data[world.I_COINS_SILVER_GCASH] = {
        "keywords": "coins silver gcash", "short_descr": "%d silver coins",
        "type": "money", "wear_flags": {"take": True}, "level": 0,
        "weight": 10, "value": 0,
    }
    ITEM_DEFS._data[world.I_COINS_SILVER_GOLD_GCASH] = {
        "keywords": "coins silver gold gcash",
        "short_descr": "%d silver coins and %d gold coins",
        "type": "money", "wear_flags": {"take": True}, "level": 0,
        "weight": 10, "value": 0,
    }
    _stub_room()
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


# -- Task 1: do_get carry count/weight limits -----------------------------------

def test_get_blocked_by_carry_count(out, monkeypatch):
    monkeypatch.setattr(inventory, "can_carry_n", lambda ch: 0)
    player = _make_player()
    world.rooms[ROOM_VNUM]["items"].append({"vnum": SWORD_VNUM})
    inventory.do_get(player, ["sword"])
    assert any("you can't carry that many items" in l for l in out)
    assert player["inv"] == []
    assert len(world.rooms[ROOM_VNUM]["items"]) == 1


def test_get_blocked_by_carry_weight(out, monkeypatch):
    monkeypatch.setattr(inventory, "can_carry_w", lambda ch: 0)
    player = _make_player()
    world.rooms[ROOM_VNUM]["items"].append({"vnum": SWORD_VNUM})
    inventory.do_get(player, ["sword"])
    assert any("you can't carry that much weight" in l for l in out)
    assert player["inv"] == []
    assert len(world.rooms[ROOM_VNUM]["items"]) == 1


def test_get_within_limits_succeeds(out):
    player = _make_player()
    world.rooms[ROOM_VNUM]["items"].append({"vnum": SWORD_VNUM})
    inventory.do_get(player, ["sword"])
    assert any("You get a test sword." in l for l in out)
    assert len(player["inv"]) == 1
    assert world.rooms[ROOM_VNUM]["items"] == []


def test_get_money_exempt_from_item_count_limit(out, monkeypatch):
    # cf. 1stMud get_obj_number in handler.c -- money contributes 0 to
    # carry_number, so a maxed-out item count still allows coin pickup.
    monkeypatch.setattr(inventory, "can_carry_n", lambda ch: 0)
    player = _make_player()
    coin = {"vnum": world.I_COIN_GOLD_GCASH, "gold": 3, "silver": 0}
    world.rooms[ROOM_VNUM]["items"].append(coin)
    inventory.do_get(player, ["gold"])
    assert not any("you can't carry that many items" in l for l in out)
    assert player["gold"] == 3
    assert world.rooms[ROOM_VNUM]["items"] == []


# -- Task 1: do_put container capacity -------------------------------------------

def test_put_item_too_heavy_for_container(out):
    player = _make_player()
    chest = {"vnum": CHEST_VNUM, "contents": []}
    player["inv"].append({"vnum": HEAVY_ITEM_VNUM})
    world.rooms[ROOM_VNUM]["items"].append(chest)
    inventory.do_put(player, ["anvil", "chest"])
    assert any("It won't fit." in l for l in out)
    assert chest["contents"] == []
    assert len(player["inv"]) == 1


def test_put_item_fits_container(out):
    player = _make_player()
    chest = {"vnum": CHEST_VNUM, "contents": []}
    player["inv"].append({"vnum": LIGHT_ITEM_VNUM})
    world.rooms[ROOM_VNUM]["items"].append(chest)
    inventory.do_put(player, ["pebble", "chest"])
    assert any("You put a test pebble in a test chest." in l for l in out)
    assert len(chest["contents"]) == 1
    assert player["inv"] == []


def test_put_rejects_corpse_container(out):
    player = _make_player()
    corpse = {"vnum": CORPSE_VNUM, "contents": []}
    player["inv"].append({"vnum": LIGHT_ITEM_VNUM})
    world.rooms[ROOM_VNUM]["items"].append(corpse)
    inventory.do_put(player, ["pebble", "corpse"])
    assert "That's not a container." in out
    assert corpse["contents"] == []
    assert len(player["inv"]) == 1


# -- Container closed/locked flags (TODO.md Items section) ------------------------

def test_get_from_closed_container_blocked(out):
    """cf. 1stMud do_get CONT_CLOSED check, act_obj.c:280."""
    player = _make_player()
    chest = {"vnum": CHEST_VNUM, "contents": [{"vnum": LIGHT_ITEM_VNUM}],
             "container_flags": {"closed": True}}
    world.rooms[ROOM_VNUM]["items"].append(chest)
    inventory.do_get(player, ["pebble", "chest"])
    assert any("The chest is closed." in l for l in out)
    assert len(chest["contents"]) == 1
    assert player["inv"] == []


def test_put_into_closed_container_blocked(out):
    """cf. 1stMud do_put CONT_CLOSED check, act_obj.c:370."""
    player = _make_player()
    chest = {"vnum": CHEST_VNUM, "contents": [],
             "container_flags": {"closed": True}}
    player["inv"].append({"vnum": LIGHT_ITEM_VNUM})
    world.rooms[ROOM_VNUM]["items"].append(chest)
    inventory.do_put(player, ["pebble", "chest"])
    assert any("The chest is closed." in l for l in out)
    assert chest["contents"] == []
    assert len(player["inv"]) == 1


def test_put_nodrop_item_blocked(out):
    """cf. 1stMud do_put can_drop_obj check, act_obj.c:391."""
    player = _make_player()
    chest = {"vnum": CHEST_VNUM, "contents": []}
    nodrop = {"vnum": NODROP_VNUM}
    player["inv"].append(nodrop)
    world.rooms[ROOM_VNUM]["items"].append(chest)
    inventory.do_put(player, ["cursed", "chest"])
    assert any("You can't let go of it." in l for l in out)
    assert chest["contents"] == []
    assert nodrop in player["inv"]


# -- Task 2: anti-align wear zap --------------------------------------------------

def test_wear_anti_evil_item_zaps_evil_player(out):
    player = _make_player(alignment=-500)
    robe = {"vnum": ANTI_EVIL_ROBE_VNUM}
    player["inv"].append(robe)
    inventory.wear_obj(player, robe, True)
    assert any("You are zapped by a holy test robe and drop it." in l for l in out)
    assert player["equip"]["body"] is None
    assert robe not in player["inv"]
    assert robe in world.rooms[ROOM_VNUM]["items"]


def test_wear_anti_evil_item_succeeds_for_good_player(out):
    player = _make_player(alignment=500)
    robe = {"vnum": ANTI_EVIL_ROBE_VNUM}
    player["inv"].append(robe)
    inventory.wear_obj(player, robe, True)
    assert not any("zapped" in l for l in out)
    assert player["equip"]["body"] is robe
    assert robe not in player["inv"]


def test_wear_plain_item_unaffected_by_alignment(out):
    player = _make_player(alignment=-1000)
    robe = {"vnum": ROBE_VNUM}
    player["inv"].append(robe)
    inventory.wear_obj(player, robe, True)
    assert not any("zapped" in l for l in out)
    assert player["equip"]["body"] is robe


# -- Task 3: drop <n> gold/silver --------------------------------------------------

def test_drop_gold_creates_room_pile(out):
    player = _make_player(gold=100, silver=0)
    inventory.do_drop(player, ["40", "gold"])
    assert player["gold"] == 60
    assert any("OK." in l for l in out)
    piles = [o for o in world.rooms[ROOM_VNUM]["items"]
             if isinstance(o, dict) and o.get("gold")]
    assert len(piles) == 1
    assert piles[0]["gold"] == 40


def test_drop_gold_merges_with_existing_pile(out):
    player = _make_player(gold=100, silver=0)
    world.rooms[ROOM_VNUM]["items"].append(
        {"vnum": world.I_COIN_GOLD_GCASH, "gold": 1, "silver": 0})
    inventory.do_drop(player, ["9", "gold"])
    assert player["gold"] == 91
    money_items = [o for o in world.rooms[ROOM_VNUM]["items"]
                   if isinstance(o, dict) and (o.get("gold") or o.get("silver"))]
    assert len(money_items) == 1
    assert money_items[0]["gold"] == 10


def test_drop_silver_word_variant(out):
    player = _make_player(gold=0, silver=20)
    inventory.do_drop(player, ["5", "silver"])
    assert player["silver"] == 15
    piles = [o for o in world.rooms[ROOM_VNUM]["items"]
             if isinstance(o, dict) and o.get("silver")]
    assert len(piles) == 1
    assert piles[0]["silver"] == 5


def test_drop_more_coins_than_carried_blocked(out):
    player = _make_player(gold=5, silver=0)
    inventory.do_drop(player, ["10", "gold"])
    assert any("You don't have that much gold." in l for l in out)
    assert player["gold"] == 5
    assert world.rooms[ROOM_VNUM]["items"] == []


def test_drop_coins_bad_denomination_word(out):
    player = _make_player(gold=5, silver=0)
    inventory.do_drop(player, ["3", "bogus"])
    assert any("Sorry, you can't do that." in l for l in out)
    assert player["gold"] == 5


# -- Task 1 follow-ups: coin weight + carried-container exemption ------------------
# cf. 1stMud get_carry_weight (macro.h) and act_obj.c get_obj's
# `!obj->in_obj || obj->in_obj->carried_by != ch` weight-check guard.

def test_coin_weight_counts_against_carry_weight(out, monkeypatch):
    monkeypatch.setattr(inventory, "can_carry_w", lambda ch: 50)
    player = _make_player(gold=0, silver=600)  # 600 silver = 60 tenths
    world.rooms[ROOM_VNUM]["items"].append({"vnum": LIGHT_ITEM_VNUM})
    inventory.do_get(player, ["pebble"])
    assert any("you can't carry that much weight" in l for l in out)
    assert player["inv"] == []


def test_get_from_carried_container_skips_weight_check(out, monkeypatch):
    monkeypatch.setattr(inventory, "can_carry_w", lambda ch: 0)
    player = _make_player()
    anvil = {"vnum": HEAVY_ITEM_VNUM}
    chest = {"vnum": CHEST_VNUM, "contents": [anvil]}
    player["inv"].append(chest)
    inventory.do_get(player, ["anvil", "chest"])
    assert not any("you can't carry that much weight" in l for l in out)
    assert anvil in player["inv"]
