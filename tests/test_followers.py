"""Tests for the follower/master/pet system (comm.py) vs 1stMud act_comm.c."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

from handler import _char_base
from comm import (add_follower, stop_follower, nuke_pets, die_follower,
                  do_follow, do_ditch, do_order)
import combat
import magic
import world
from world import ROOM_DEFS, MOB_DEFS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
    world.chars[1] = ch
    if room in world.rooms._data:
        pass  # player not tracked in room mob lists
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


# ===========================================================================
# add_follower / stop_follower
# ===========================================================================

class TestAddStopFollower:
    def test_add_follower_sets_master_clears_leader(self):
        player = _make_player()
        mob = _make_mob(2)
        mob["leader"] = 99
        add_follower(mob, player)
        assert mob["master"] == 1
        assert mob["leader"] is None

    def test_add_follower_refuses_existing_master(self):
        # cf. 1stMud bug("Add_follower: non-null master.")
        player = _make_player()
        mob = _make_mob(2, master=42)
        add_follower(mob, player)
        assert mob["master"] == 42

    def test_stop_follower_clears_links_and_charm(self):
        player = _make_player()
        mob = _make_mob(2)
        add_follower(mob, player)
        mob["affected_by"]["charm"] = True
        mob["leader"] = 1
        player["pet"] = 2
        stop_follower(mob)
        assert mob["master"] is None
        assert mob["leader"] is None
        assert not mob["affected_by"].get("charm")
        assert player["pet"] is None

    def test_stop_follower_null_master_noop(self):
        mob = _make_mob(2)
        stop_follower(mob)   # must not raise (cf. 1stMud bug log)
        assert mob["master"] is None


# ===========================================================================
# nuke_pets / die_follower
# ===========================================================================

class TestNukeDie:
    def test_nuke_pets_extracts_pet(self):
        player = _make_player()
        pet = _make_mob(2)
        add_follower(pet, player)
        pet["leader"] = 1
        player["pet"] = 2
        nuke_pets(player)
        assert player["pet"] is None
        assert 2 not in world.chars
        assert 2 not in world.rooms._data[9001]["mobs"]

    def test_die_follower_releases_followers(self):
        player = _make_player()
        m1 = _make_mob(2)
        m2 = _make_mob(3)      # grouped under player but not following
        add_follower(m1, player)
        m2["leader"] = 1
        die_follower(player)
        assert m1["master"] is None
        # follower's leader nulled via stop_follower (matches 1stMud order)
        assert m1["leader"] is None
        assert m2["leader"] == 3   # 1stMud: fch->leader = fch

    def test_extract_char_severs_links(self):
        # pet dies: master's pet pointer cleared via die_follower
        player = _make_player()
        pet = _make_mob(2)
        add_follower(pet, player)
        player["pet"] = 2
        combat._extract_char(pet, pull=True)
        assert player["pet"] is None
        assert 2 not in world.chars


# ===========================================================================
# do_follow / do_ditch
# ===========================================================================

class TestFollowDitch:
    def test_follow_mob_and_self_stop(self):
        player = _make_player()
        _make_mob(2)
        do_follow(player, ["dog"])
        assert player["master"] == 2
        do_follow(player, ["self"])
        assert player["master"] is None

    def test_follow_charmed_refused(self):
        player = _make_player()
        _make_mob(2)
        player["affected_by"]["charm"] = True
        player["master"] = 2
        do_follow(player, ["dog"])
        assert player["master"] == 2

    def test_ditch_follower(self):
        player = _make_player()
        mob = _make_mob(2)
        add_follower(mob, player)
        do_ditch(player, ["dog"])
        assert mob["master"] is None

    def test_ditch_non_follower(self):
        player = _make_player()
        mob = _make_mob(2)
        do_ditch(player, ["dog"])
        assert mob["master"] is None


# ===========================================================================
# do_order
# ===========================================================================

class TestOrder:
    def _charmed_pet(self, player):
        pet = _make_mob(2)
        add_follower(pet, player)
        pet["leader"] = 1
        pet["affected_by"]["charm"] = True
        return pet

    def test_order_kill_dispatches(self, monkeypatch):
        player = _make_player()
        pet = self._charmed_pet(player)
        _make_mob(3, keywords="rat")
        MOB_DEFS._data[MOB_TPL]["keywords"] = "dog rat test"
        hits = []
        monkeypatch.setattr(combat, "multi_hit", lambda ch, v, dt=None: hits.append((ch["id"], v["id"])))
        monkeypatch.setattr(combat, "is_safe", lambda ch, v: False)
        do_order(player, ["dog", "kill", "rat"])
        # pet (id 2) attacks first non-self match (id 3)
        assert hits == [(2, 3)]
        assert player["wait"] > 0

    def test_order_uncharmed_refused(self):
        player = _make_player()
        pet = _make_mob(2)
        add_follower(pet, player)
        do_order(player, ["dog", "kill", "rat"])
        assert pet["fighting"] is None

    def test_order_while_charmed_refused(self):
        player = _make_player()
        self._charmed_pet(player)
        player["affected_by"]["charm"] = True
        do_order(player, ["all", "kill", "rat"])
        assert player["wait"] == 0

    def test_order_delete_refused(self, monkeypatch):
        player = _make_player()
        self._charmed_pet(player)
        called = []
        monkeypatch.setattr(combat, "multi_hit", lambda *a, **k: called.append(1))
        do_order(player, ["all", "delete"])
        assert not called


# ===========================================================================
# Movement: followers move with master
# ===========================================================================

class TestFollowerMovement:
    def _walk_north(self, player):
        from movement import move_char
        # run_buf triggers the brief room line, avoiding full do_look deps
        player["run_buf"] = [("move", "n")]
        move_char(player, "n")

    def test_charmed_standing_follower_moves(self):
        player = _make_player()
        pet = _make_mob(2)
        add_follower(pet, player)
        pet["affected_by"]["charm"] = True
        self._walk_north(player)
        assert player["room"] == 9002
        assert pet["room"] == 9002
        assert 2 in world.rooms._data[9002]["mobs"]
        assert 2 not in world.rooms._data[9001]["mobs"]

    def test_charmed_resting_follower_stands_and_moves(self):
        player = _make_player()
        pet = _make_mob(2, pos="resting")
        add_follower(pet, player)
        pet["affected_by"]["charm"] = True
        self._walk_north(player)
        assert pet["pos"] == "standing"
        assert pet["room"] == 9002

    def test_uncharmed_resting_follower_stays(self):
        player = _make_player()
        mob = _make_mob(2, pos="resting")
        add_follower(mob, player)
        self._walk_north(player)
        assert mob["room"] == 9001

    def test_aggressive_pet_blocked_from_law_room(self):
        world.rooms._data[9002]["flags"]["law"] = True
        player = _make_player()
        pet = _make_mob(2)
        pet["act_flags"]["aggressive"] = True
        add_follower(pet, player)
        pet["affected_by"]["charm"] = True
        self._walk_north(player)
        assert player["room"] == 9002
        assert pet["room"] == 9001

    def test_non_follower_stays(self):
        player = _make_player()
        mob = _make_mob(2)
        self._walk_north(player)
        assert mob["room"] == 9001


# ===========================================================================
# Charm spell linkage / mobile_update guard
# ===========================================================================

class TestWanderFollow:
    def test_player_follows_wandering_mob(self, monkeypatch):
        # mob wander goes through move_char, dragging the following player
        # (cf. 1stMud mobile_update -> move_char(ch, door, false))
        import mob as mob_mod
        player = _make_player()
        player["run_buf"] = [("move", "n")]   # brief room line; skip full look
        leader = _make_mob(2, home_area="test")
        player["master"] = 2
        monkeypatch.setattr(mob_mod, "randint", lambda a, b: a)
        mob_mod.mobile_update(None, player)
        assert leader["room"] == 9002
        assert player["room"] == 9002

    def test_move_char_directly_moves_npc(self):
        from movement import move_char
        mob = _make_mob(2)
        move_char(mob, "n")
        assert mob["room"] == 9002
        assert 2 in world.rooms._data[9002]["mobs"]
        assert 2 not in world.rooms._data[9001]["mobs"]

    def test_charmed_pet_anchored_to_present_master(self):
        # pet alone can't walk away while its master is in the room
        from movement import move_char
        player = _make_player()
        pet = _make_mob(2)
        add_follower(pet, player)
        pet["affected_by"]["charm"] = True
        move_char(pet, "n")
        assert pet["room"] == 9001


class TestMobAffectTick:
    def test_mob_affect_expires(self):
        from player import tick_update
        from handler import affect_to_char
        player = _make_player()
        player["xp_next"] = 1000
        mob = _make_mob(2)
        affect_to_char(mob, {"type": 999, "level": 20, "duration": 1,
                             "location": "str", "modifier": 2,
                             "bitvector": "", "where": "to_affects"})
        room = ROOM_DEFS._data[9001]
        tick_update(None, player, room)   # duration 1 -> 0
        assert mob["affect_list"][0]["duration"] == 0
        tick_update(None, player, room)   # duration 0 -> removed
        assert mob["affect_list"] == []
        assert mob["mod_stat"].get("str", 0) == 0   # modifier backed out


class TestCharmIntegration:
    def test_spell_charm_person_adds_follower(self, monkeypatch):
        player = _make_player()
        mob = _make_mob(2)
        monkeypatch.setattr(magic, "is_safe", lambda ch, v: False)
        monkeypatch.setattr(magic, "saves_spell", lambda level, v, dam: False)
        sn = magic._skill_lookup("charm person")
        assert magic.spell_charm_person(sn, 20, player, mob, None) is True
        assert mob["master"] == 1
        assert mob["leader"] == 1
        assert mob["affected_by"].get("charm")

    def test_charmed_mob_does_not_wander_or_despawn(self, monkeypatch):
        import mob as mob_mod
        player = _make_player()
        pet = _make_mob(2, home_area="elsewhere")
        pet["affected_by"]["charm"] = True
        # force both the 5% despawn and the 1/8 wander to trigger if reached
        monkeypatch.setattr(mob_mod, "randint", lambda a, b: a)
        mob_mod.mobile_update(None, player)
        assert 2 in world.chars
        assert pet["room"] == 9001
