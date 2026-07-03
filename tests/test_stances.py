"""Tests for the stance system (stances.py + combat.py commands) vs 1stMud fight.c/tables.c."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "primesud.hpappdir")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

from handler import _char_base
import stances
from stances import (STANCE_TABLE, MAX_STANCE,
                     STANCE_NONE, STANCE_NORMAL, STANCE_VIPER, STANCE_CRANE,
                     STANCE_MANTIS, STANCE_CURRENT, STANCE_AUTODROP,
                     valid_stance, get_stance, set_stance,
                     stance_name, stance_lookup, can_use_stance,
                     improve_stance, autodrop)
from combat import do_stance, do_autostance, do_sskill
import world
from world import ROOM_DEFS


def _make_char(**overrides):
    ch = _char_base()
    ch["id"] = 1
    ch["name"] = "Tester"
    ch["level"] = 20
    ch["room"] = 9001
    ch.update(overrides)
    world.chars[1] = ch
    return ch


@pytest.fixture(autouse=True)
def _clean_world_state():
    old_rooms = dict(ROOM_DEFS._data)
    old_wrooms = dict(world.rooms._data)
    old_chars = dict(world.chars)
    room = {"name": "Test Room", "desc": "x", "exits": {"n": 9002},
            "items": [], "mobs": [], "area": "test", "flags": {},
            "sector": "inside"}
    room2 = dict(room)
    room2["exits"] = {}
    room2["mobs"] = []
    ROOM_DEFS._data[9001] = room
    world.rooms._data[9001] = room
    ROOM_DEFS._data[9002] = room2
    world.rooms._data[9002] = room2
    yield
    ROOM_DEFS._data.clear()
    ROOM_DEFS._data.update(old_rooms)
    world.rooms._data.clear()
    world.rooms._data.update(old_wrooms)
    world.chars.clear()
    world.chars.update(old_chars)


class TestTable:
    def test_table_shape(self):
        assert len(STANCE_TABLE) == MAX_STANCE
        # entry stance id matches its index for the trainable stances
        for i, entry in enumerate(STANCE_TABLE):
            assert entry[1] == i

    def test_prereq_tree(self):
        # advanced stances (cf. tables.c:1644-1658)
        assert STANCE_TABLE[STANCE_MANTIS][2] == (STANCE_CRANE, STANCE_VIPER)

    def test_valid_stance_bounds(self):
        assert not valid_stance(STANCE_NONE)
        assert valid_stance(STANCE_NORMAL)
        assert valid_stance(10)
        assert not valid_stance(STANCE_CURRENT)
        assert not valid_stance(STANCE_AUTODROP)

    def test_lookup_prefix(self):
        assert stance_lookup("vip") == STANCE_VIPER
        assert stance_lookup("bogus") == -1
        assert stance_lookup("") == -1

    def test_stance_name(self):
        assert stance_name(STANCE_VIPER) == "viper"
        assert stance_name(99) == "unknown"


class TestCanUse:
    def test_base_stances_free(self):
        ch = _make_char()
        assert can_use_stance(ch, STANCE_VIPER)
        assert can_use_stance(ch, STANCE_NORMAL)

    def test_advanced_needs_mastery(self):
        ch = _make_char()
        assert not can_use_stance(ch, STANCE_MANTIS)
        set_stance(ch, STANCE_CRANE, 200)
        set_stance(ch, STANCE_VIPER, 200)
        assert can_use_stance(ch, STANCE_MANTIS)

    def test_invalid_ids(self):
        ch = _make_char()
        assert not can_use_stance(ch, STANCE_NONE)
        assert not can_use_stance(ch, STANCE_CURRENT)


class TestDoStance:
    def test_noarg_toggles(self):
        ch = _make_char()
        # fresh char: current == 0 == normal (1stMud zeroed stance[])
        do_stance(ch, [])
        assert get_stance(ch, STANCE_CURRENT) == STANCE_NONE
        do_stance(ch, [])
        assert get_stance(ch, STANCE_CURRENT) == STANCE_NORMAL

    def test_set_stance_by_name(self):
        ch = _make_char()
        set_stance(ch, STANCE_CURRENT, STANCE_NONE)
        do_stance(ch, ["viper"])
        assert get_stance(ch, STANCE_CURRENT) == STANCE_VIPER

    def test_no_change_while_in_stance(self):
        ch = _make_char()
        set_stance(ch, STANCE_CURRENT, STANCE_VIPER)
        do_stance(ch, ["crane"])
        assert get_stance(ch, STANCE_CURRENT) == STANCE_VIPER

    def test_advanced_refused_without_mastery(self):
        ch = _make_char()
        set_stance(ch, STANCE_CURRENT, STANCE_NONE)
        do_stance(ch, ["mantis"])
        assert get_stance(ch, STANCE_CURRENT) == STANCE_NONE

    def test_unknown_shows_available(self, capsys):
        ch = _make_char()
        set_stance(ch, STANCE_CURRENT, STANCE_NONE)
        do_stance(ch, ["bogus"])
        out = capsys.readouterr().out
        assert "Valid stances are" in out
        assert "mantis" not in out   # advanced not listed without mastery

    def test_npc_gets_trained_skill(self):
        mob = _make_char(is_npc=True, level=30)
        set_stance(mob, STANCE_CURRENT, STANCE_NONE)
        do_stance(mob, ["viper"])
        # min(30 * 4 / 2, 200) = 60
        assert get_stance(mob, STANCE_VIPER) == 60


class TestAutostance:
    def test_set_and_clear(self):
        ch = _make_char()
        do_autostance(ch, ["viper"])
        assert get_stance(ch, STANCE_AUTODROP) == STANCE_VIPER
        do_autostance(ch, ["none"])
        assert get_stance(ch, STANCE_AUTODROP) == STANCE_NONE

    def test_advanced_refused(self):
        ch = _make_char()
        do_autostance(ch, ["mantis"])
        assert get_stance(ch, STANCE_AUTODROP) == 0  # unchanged

    def test_autodrop_on_combat(self):
        ch = _make_char()
        set_stance(ch, STANCE_AUTODROP, STANCE_VIPER)
        set_stance(ch, STANCE_CURRENT, STANCE_NONE)
        autodrop(ch)
        assert get_stance(ch, STANCE_CURRENT) == STANCE_VIPER

    def test_autodrop_keeps_current(self):
        ch = _make_char()
        set_stance(ch, STANCE_AUTODROP, STANCE_VIPER)
        set_stance(ch, STANCE_CURRENT, STANCE_CRANE)
        autodrop(ch)
        assert get_stance(ch, STANCE_CURRENT) == STANCE_CRANE


class TestImprove:
    def test_improves_on_high_rolls(self, monkeypatch):
        ch = _make_char()
        set_stance(ch, STANCE_CURRENT, STANCE_VIPER)
        monkeypatch.setattr(stances, "randint", None, raising=False)
        # improve_stance imports randint locally from urandom
        import urandom
        monkeypatch.setattr(urandom, "randint", lambda a, b: 100)
        improve_stance(ch)
        assert get_stance(ch, STANCE_VIPER) == 1

    def test_capped_at_200(self, monkeypatch):
        ch = _make_char()
        set_stance(ch, STANCE_CURRENT, STANCE_VIPER)
        set_stance(ch, STANCE_VIPER, 200)
        import urandom
        monkeypatch.setattr(urandom, "randint", lambda a, b: 100)
        improve_stance(ch)
        assert get_stance(ch, STANCE_VIPER) == 200

    def test_no_improve_out_of_stance(self, monkeypatch):
        ch = _make_char()
        set_stance(ch, STANCE_CURRENT, STANCE_NONE)
        import urandom
        monkeypatch.setattr(urandom, "randint", lambda a, b: 100)
        improve_stance(ch)
        assert get_stance(ch, STANCE_VIPER) == 0


class TestDisplayAndMovement:
    def test_sskill_output(self, capsys):
        ch = _make_char()
        set_stance(ch, STANCE_VIPER, 42)
        do_sskill(ch, [])
        out = capsys.readouterr().out
        assert "viper" in out
        assert "42" in out
        assert "requires master in crane and viper" in out  # mantis row

    def test_move_drops_stance(self):
        from movement import move_char
        ch = _make_char()
        ch["run_buf"] = [("move", "n")]  # brief room line; skip full look
        set_stance(ch, STANCE_CURRENT, STANCE_VIPER)
        move_char(ch, "n")
        assert ch["room"] == 9002
        assert get_stance(ch, STANCE_CURRENT) == STANCE_NONE


class TestPersistence:
    def test_stance_save_roundtrip(self, tmp_path, monkeypatch):
        import game_state
        from player import create_char
        monkeypatch.setattr(game_state, "SAVE_FILE", str(tmp_path / "t.sav"))
        world.areas = []
        player = create_char()
        player["name"] = "Tester"
        player["room"] = 9001
        player["_macros"] = {}
        world.chars[1] = player
        set_stance(player, STANCE_VIPER, 150)
        set_stance(player, STANCE_CURRENT, STANCE_VIPER)
        set_stance(player, STANCE_AUTODROP, STANCE_CRANE)
        game_state._serialize_world()

        world.chars.clear()
        player2 = create_char()
        player2["name"] = "Tester"
        player2["room"] = 9001
        player2["_macros"] = {}
        world.chars[1] = player2
        assert game_state.load_world() == "file"
        assert get_stance(player2, STANCE_VIPER) == 150
        assert get_stance(player2, STANCE_CURRENT) == STANCE_VIPER
        assert get_stance(player2, STANCE_AUTODROP) == STANCE_CRANE
