"""Tests for pet shops (shop.py ROOM_PET_SHOP branch) vs 1stMud act_obj.c."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "primesud.hpappdir")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

from handler import _char_base, get_char_room
from shop import do_buy, do_list
from mob import spawn_pet, create_mobile
import world
from world import ROOM_DEFS, MOB_DEFS


PET_TPL = 9402
SHOP_ROOM = 9010     # pet_shop flag
STOCK_ROOM = 9011    # SHOP_ROOM + 1


def _stub_room(vnum, **extra):
    room = {"name": "Test Room", "desc": "A test room.", "exits": {},
            "items": [], "mobs": [], "area": "test", "flags": {},
            "sector": "inside"}
    room.update(extra)
    ROOM_DEFS._data[vnum] = room
    world.rooms._data[vnum] = room
    return room


def _make_player(room=SHOP_ROOM, gold=100):
    ch = _char_base()
    ch["id"] = 1
    ch["name"] = "Tester"
    ch["level"] = 20
    ch["room"] = room
    ch["gold"] = gold
    ch["learned"] = {}
    world.chars[1] = ch
    return ch


def _stock_pet(mid=2):
    pet = create_mobile(PET_TPL)
    pet["id"] = mid
    pet["room"] = STOCK_ROOM
    pet["home_area"] = "test"
    world.chars[mid] = pet
    world.rooms._data[STOCK_ROOM]["mobs"].append(mid)
    return pet


@pytest.fixture(autouse=True)
def _clean_world_state():
    old_rooms = dict(ROOM_DEFS._data)
    old_wrooms = dict(world.rooms._data)
    old_chars = dict(world.chars)
    old_mobs = dict(MOB_DEFS._data)
    MOB_DEFS._data[PET_TPL] = {
        "short_descr": "a fat beagle", "long_descr": "A fat beagle is here.",
        "description": "The beagle looks friendly.",
        "keywords": "beagle dog pet", "level": 5, "race": "Human",
        "hp_dice": (1, 1, 10), "hitroll": 0, "damage": (1, 4, 0),
        "armor": (0, 0, 0, 0),
        "act_flags": {"sentinel": True, "pet": True},
    }
    _stub_room(SHOP_ROOM, flags={"pet_shop": True, "indoors": True})
    _stub_room(STOCK_ROOM)
    yield
    ROOM_DEFS._data.clear()
    ROOM_DEFS._data.update(old_rooms)
    world.rooms._data.clear()
    world.rooms._data.update(old_wrooms)
    world.chars.clear()
    world.chars.update(old_chars)
    MOB_DEFS._data.clear()
    MOB_DEFS._data.update(old_mobs)


class TestBuyPet:
    def test_buy_pet_links_and_flags(self):
        player = _make_player()
        _stock_pet()
        do_buy(player, ["beagle"])
        pid = player["pet"]
        assert pid is not None
        pet = world.chars[pid]
        assert pet["master"] == 1
        assert pet["leader"] == 1
        assert pet["act_flags"].get("pet")
        assert pet["affected_by"].get("charm")
        assert pet["room"] == SHOP_ROOM
        assert pid in world.rooms._data[SHOP_ROOM]["mobs"]
        # cost = 10 * 5 * 5 = 250 silver = 2 gold 50 silver
        assert player["gold"] * 100 + player["silver"] == 100 * 100 - 250
        # neck tag appended to description
        assert "I belong to Tester" in pet["description"]

    def test_buy_pet_custom_name(self):
        player = _make_player()
        _stock_pet()
        do_buy(player, ["beagle", "fido"])
        pet = world.chars[player["pet"]]
        assert pet["pet_name"] == "fido"
        # custom name matchable in the pet's room
        found = get_char_room("fido", world.rooms._data[SHOP_ROOM]["mobs"],
                              world.chars)
        assert found == pet["id"]

    def test_buy_pet_only_one(self):
        player = _make_player()
        _stock_pet(2)
        _stock_pet(3)
        do_buy(player, ["beagle"])
        first = player["pet"]
        do_buy(player, ["beagle"])
        assert player["pet"] == first

    def test_buy_pet_cant_afford(self):
        player = _make_player(gold=0)
        _stock_pet()
        do_buy(player, ["beagle"])
        assert player["pet"] is None

    def test_buy_pet_level_too_low(self):
        player = _make_player()
        player["level"] = 3
        _stock_pet()
        do_buy(player, ["beagle"])
        assert player["pet"] is None

    def test_buy_non_pet_refused(self):
        player = _make_player()
        stock = _stock_pet()
        stock["act_flags"].pop("pet")
        do_buy(player, ["beagle"])
        assert player["pet"] is None

    def test_list_pets(self, capsys):
        player = _make_player()
        _stock_pet()
        do_list(player, [])
        out = capsys.readouterr().out
        assert "Pets for sale:" in out
        assert "a fat beagle" in out
        assert "250" in out

    def test_list_empty(self, capsys):
        player = _make_player()
        do_list(player, [])
        out = capsys.readouterr().out
        assert "out of pets" in out


class TestPetPersistence:
    def _full_player(self):
        from player import create_char
        player = create_char()
        player["name"] = "Tester"
        player["room"] = SHOP_ROOM
        player["gold"] = 100
        player["_macros"] = {}
        world.chars[1] = player
        return player

    def test_pet_save_line_and_m_exclusion(self, tmp_path, monkeypatch):
        import game_state
        monkeypatch.setattr(game_state, "SAVE_FILE", str(tmp_path / "t.sav"))
        world.areas = []
        player = self._full_player()
        pet = spawn_pet(PET_TPL, player, name_arg="fido", announce=False)
        pet["hit"] = 7
        game_state._serialize_world()
        with open(str(tmp_path / "t.sav")) as f:
            payload = f.read()
        assert "p.pet=" + str(PET_TPL) + "|7|fido" in payload
        # pet must not be serialized as a template position
        assert "m." + str(PET_TPL) + "=" not in payload

    def test_pet_load_roundtrip(self, tmp_path, monkeypatch):
        import game_state
        monkeypatch.setattr(game_state, "SAVE_FILE", str(tmp_path / "t.sav"))
        world.areas = []
        player = self._full_player()
        pet = spawn_pet(PET_TPL, player, name_arg="fido", announce=False)
        pet["hit"] = 7
        game_state._serialize_world()

        # fresh world: drop pet, reset player links
        del world.chars[pet["id"]]
        world.rooms._data[SHOP_ROOM]["mobs"].remove(pet["id"])
        world.chars.clear()
        player2 = self._full_player()

        assert game_state.load_world() == "file"
        pid = player2["pet"]
        assert pid is not None
        pet2 = world.chars[pid]
        assert pet2["tpl"] == PET_TPL
        assert pet2["hit"] == 7
        assert pet2["pet_name"] == "fido"
        assert pet2["master"] == 1
        assert pet2["room"] == player2["room"]
