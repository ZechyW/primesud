"""Tests for do_group (comm.py) vs 1stMud do_group in act_comm.c."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

from handler import _char_base
from comm import do_group, add_follower, die_follower, nuke_pets, do_order
from mob import spawn_pet
import combat
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
    ch["classes"] = [3]        # warrior
    ch["prime_class"] = 0
    ch["xp"] = 1234
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
        "description": "A friendly dog.", "keywords": "dog test",
        "level": 5, "race": "Human", "hp_dice": (1, 1, 10), "hitroll": 0,
        "damage": (1, 4, 0), "armor": (0, 0, 0, 0),
    }
    _stub_room(9001, exits={"n": 9002})
    _stub_room(9002)
    yield
    ROOM_DEFS._data.clear(); ROOM_DEFS._data.update(old_rooms)
    world.rooms._data.clear(); world.rooms._data.update(old_wrooms)
    world.chars.clear(); world.chars.update(old_chars)
    MOB_DEFS._data.clear(); MOB_DEFS._data.update(old_mobs)


# ===========================================================================
# Roster (no arg)
# ===========================================================================

class TestRoster:
    def test_solo_roster_format(self, capsys):
        player = _make_player()
        do_group(player, [])
        out = capsys.readouterr().out
        assert "Tester's group:" in out
        # two-line member render: name/class line, then indented stats line
        assert "[20 Warr] Tester" in out
        assert "20/  20 hp" in out
        assert "mana" in out and "mv" in out
        assert "1234 xp" in out
        assert "Type 'group where'" in out

    def test_pet_shows_in_roster(self, capsys):
        player = _make_player()
        pet = _make_mob(2, master=1, leader=1)
        pet["affected_by"]["charm"] = True
        do_group(player, [])
        out = capsys.readouterr().out
        # NPC renders "Mob" for class (padded) and 0 xp
        assert "[ 5 Mob ] A test dog" in out   # capitalized short_descr
        assert "    0 xp" in out

    def test_ungrouped_mob_excluded(self, capsys):
        player = _make_player()
        _make_mob(2)                          # no leader link -> not in group
        do_group(player, [])
        out = capsys.readouterr().out
        assert "A test dog" not in out


# ===========================================================================
# where
# ===========================================================================

class TestWhere:
    def test_where_lists_locations(self, capsys):
        player = _make_player()
        _make_mob(2, master=1, leader=1)["affected_by"]["charm"] = True
        do_group(player, ["where"])
        out = capsys.readouterr().out
        assert "Tester is in Test Room the general area of test." in out
        # where uses Pers (no capitalize) unlike the roster line
        assert "a test dog is in Test Room" in out


# ===========================================================================
# add / remove member
# ===========================================================================

class TestAddRemove:
    def test_join_then_remove_uncharmed_follower(self, capsys):
        player = _make_player()
        mob = _make_mob(2)
        add_follower(mob, player)             # master=1, leader=None
        capsys.readouterr()

        do_group(player, ["dog"])             # not same group -> join
        out = capsys.readouterr().out
        assert "joins your group" in out
        assert mob["leader"] == 1

        do_group(player, ["dog"])             # now same group -> remove
        out = capsys.readouterr().out
        assert "remove" in out.lower()
        assert mob["leader"] is None

    def test_remove_charmed_refused(self, capsys):
        player = _make_player()
        pet = _make_mob(2, master=1, leader=1)
        pet["affected_by"]["charm"] = True
        do_group(player, ["dog"])
        out = capsys.readouterr().out
        assert "can't remove charmed mobs" in out
        assert pet["leader"] == 1             # unchanged

    def test_not_following_you(self, capsys):
        player = _make_player()
        _make_mob(2)                          # master None
        do_group(player, ["dog"])
        out = capsys.readouterr().out
        assert "isn't following you" in out

    def test_target_absent(self, capsys):
        player = _make_player()
        do_group(player, ["griffin"])
        out = capsys.readouterr().out
        assert "They aren't here." in out

    def test_following_someone_else(self, capsys):
        player = _make_player()
        player["master"] = 99
        _make_mob(2, master=1)
        do_group(player, ["dog"])
        out = capsys.readouterr().out
        assert "But you are following someone else!" in out


# ===========================================================================
# End-to-end pet lifecycle (spawn -> group -> order -> die -> nuke)
# save/load with pet_name is covered in test_pet_shop.py
# ===========================================================================

class TestPetLifecycle:
    def test_lifecycle(self, capsys, monkeypatch):
        player = _make_player()
        pet = spawn_pet(MOB_TPL, player, name_arg="fluffy", announce=False)
        assert pet["pet_name"] == "fluffy"
        assert pet["master"] == 1 and pet["leader"] == 1

        # group shows the custom-named pet
        do_group(player, [])
        assert "A test dog" in capsys.readouterr().out

        # order fluffy to attack (multi_hit stubbed)
        target = _make_mob(3)
        hits = []
        monkeypatch.setattr(combat, "multi_hit",
                            lambda ch, v, dt=None: hits.append((ch["id"], v["id"])))
        do_order(player, ["fluffy", "kill", "dog"])
        assert (pet["id"], 3) in hits

        # pet dies -> links cleaned
        die_follower(pet)
        assert pet["master"] is None and pet["leader"] is None
        assert player["pet"] is None

        # player death nukes a fresh pet
        pet2 = spawn_pet(MOB_TPL, player, name_arg="rex", announce=False)
        pid = pet2["id"]
        nuke_pets(player)
        assert player["pet"] is None
        assert pid not in world.chars
