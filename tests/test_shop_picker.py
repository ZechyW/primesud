"""Tests for no-argument shop pickers. [PRIMESUD]"""

import pytest

from handler import _char_base
from item import create_object
import shop
import world
from world import ITEM_DEFS, MOB_DEFS, ROOM_DEFS


ROOM = 9000
KEEPER = 9001
SWORD = 9010
SHIELD = 9011
POTION = 9012
QUEST_SWORD = 9013


def _item(short, item_type, value, **extra):
    tpl = {
        "short_descr": short,
        "description": short + " is here.",
        "keywords": short,
        "type": item_type,
        "material": "steel",
        "wear_flags": {"take": True},
        "weight": 1,
        "value": value,
        "level": 1,
    }
    tpl.update(extra)
    return tpl


@pytest.fixture
def store(fresh_world):
    shop_data = {
        "keeper": KEEPER,
        "buy_types": ["weapon"],
        "profit_buy": 100,
        "profit_sell": 50,
        "open_hour": 0,
        "close_hour": 23,
    }
    room = {
        "name": "Shop",
        "desc": ".",
        "exits": {},
        "items": [],
        "mobs": [2],
        "area": "test",
        "flags": {},
        "sector": "inside",
    }
    ROOM_DEFS._data[ROOM] = room
    world.rooms._data[ROOM] = room
    MOB_DEFS._data[KEEPER] = {
        "short_descr": "a shopkeeper",
        "keywords": "shopkeeper",
        "shop": shop_data,
    }
    ITEM_DEFS._data[SWORD] = _item("a sword", "weapon", 100)
    ITEM_DEFS._data[SHIELD] = _item("a shield", "armor", 200)
    ITEM_DEFS._data[POTION] = _item("a potion", "potion", 75)
    ITEM_DEFS._data[QUEST_SWORD] = _item(
        "a quest sword", "weapon", 300, extra_flags={"quest": True})

    player = _char_base()
    player.update({"id": 1, "name": "Tester", "room": ROOM,
                   "level": 20, "gold": 100})
    keeper = _char_base()
    keeper.update({"id": 2, "name": "Shopkeeper", "is_npc": True,
                   "tpl": KEEPER, "room": ROOM, "level": 20, "gold": 100})
    world.chars[1] = player
    world.chars[2] = keeper
    return player, keeper


def test_bare_buy_picks_stock_item(store, monkeypatch):
    player, keeper = store
    keeper["inv"] = [create_object(SWORD), create_object(SHIELD)]
    seen = {}

    def pick(title, labels):
        seen["title"] = title
        seen["labels"] = labels
        return 1

    monkeypatch.setattr(shop, "pick_from", pick)
    shop.do_buy(player, [])

    assert [obj["vnum"] for obj in player["inv"]] == [SHIELD]
    assert seen["title"] == "Buy what? [Lv Price Qty]"
    assert "a sword" in seen["labels"][0]
    assert "a shield" in seen["labels"][1]


def test_bare_sell_only_lists_accepted_items(store, monkeypatch):
    player, keeper = store
    sword = create_object(SWORD)
    potion = create_object(POTION)
    quest_sword = create_object(QUEST_SWORD)
    player["inv"] = [sword, potion, quest_sword]
    seen = {}

    def pick(title, labels):
        seen["labels"] = labels
        return 0

    monkeypatch.setattr(shop, "pick_from", pick)
    shop.do_sell(player, [])

    assert seen["labels"] == ["[   50] a sword"]
    assert sword not in player["inv"]
    assert potion in player["inv"]
    assert quest_sword in player["inv"]
    assert sword in keeper["inv"]


def test_cancelled_buy_changes_nothing(store, monkeypatch):
    player, keeper = store
    sword = create_object(SWORD)
    keeper["inv"] = [sword]
    monkeypatch.setattr(shop, "pick_from", lambda title, labels: -1)

    shop.do_buy(player, [])

    assert keeper["inv"] == [sword]
    assert player["inv"] == []
    assert player["gold"] == 100
