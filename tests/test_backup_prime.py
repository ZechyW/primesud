"""Tests for `backup` (cf. 1stMud do_backup in act_comm.c) and `prime`
(cf. 1stMud do_prime in multiclass.c)."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

from terminal import init_terminal
init_terminal()

import handler
import world
from classes import CLASS_MAGE, CLASS_WARRIOR, CLASS_THIEF, class_who, prime_class
from config import MAX_MORTAL_LEVEL
from player import create_char, _EQUIP_SAVE_ORDER
from system_cmds import do_backup
from training import do_prime


@pytest.fixture(autouse=True)
def _clean_world_state():
    old_chars = dict(world.chars)
    old_areas = world.areas
    yield
    world.chars.clear()
    world.chars.update(old_chars)
    world.areas = old_areas


@pytest.fixture
def out(monkeypatch):
    lines = []
    capture = lambda *a, **kw: lines.append(" ".join(str(x) for x in a))
    monkeypatch.setattr(handler, "tprint", capture)
    return lines


def _make_player(room=9901):
    """Player with no area owning *room* -- save/load exercised without a
    full area load (same trick as test_tier.py)."""
    world.areas = []
    player = create_char()
    player["name"] = "Tester"
    player["room"] = room
    player["_macros"] = {}
    world.chars[1] = player
    return player


# -- backup ---------------------------------------------------------------------

class TestBackup:
    def test_writes_second_slot_without_clobbering_primary(self, tmp_path, monkeypatch, out):
        import game_state
        save_file = tmp_path / "primary.sav"
        backup_file = tmp_path / "backup.sav"
        monkeypatch.setattr(game_state, "SAVE_FILE", str(save_file))
        monkeypatch.setattr(game_state, "BACKUP_FILE", str(backup_file))

        player = _make_player()
        player["played"] = 500
        assert game_state.save_world(quiet=True)
        primary_before = save_file.read_text()
        assert not backup_file.exists()

        do_backup(player, [])

        assert backup_file.exists()
        assert save_file.read_text() == primary_before  # primary untouched
        assert player["backup"] == 500  # cf. pcdata->backup = pcdata->played
        assert any("Tester has been saved to a backup." in l for l in out)

        # backup slot round-trips like any other save when pointed at it
        monkeypatch.setattr(game_state, "SAVE_FILE", str(backup_file))
        world.chars.clear()
        player2 = create_char()
        player2["name"] = "Tester"
        player2["room"] = 9901
        player2["_macros"] = {}
        world.chars[1] = player2
        assert game_state.load_world() == "file"
        assert player2["played"] == 500
        # cf. 1stMud backup_char_obj (save.c:162): the file write happens
        # *before* pcdata->backup is bumped, so the backup slot's own
        # "p.backup" line still carries the pre-backup value (0 here) --
        # matches do_backup's in-memory player["backup"] = 500 assertion
        # above, which reflects the post-write update the live session sees.
        assert player2["backup"] == 0

    def test_check_silent_under_an_hour_with_no_backup(self, out):
        player = _make_player()
        player["played"] = 1000
        player["backup"] = 0
        do_backup(player, ["check"])
        assert out == []

    def test_check_reports_no_backup_after_an_hour(self, out):
        player = _make_player()
        player["played"] = 4000
        player["backup"] = 0
        do_backup(player, ["check"])
        assert out == ["{RThere is currently no backup for your character.{x"]

    def test_check_hour_singular(self, out):
        player = _make_player()
        player["backup"] = 100
        player["played"] = 100 + 3600  # elapsed == 1 hour exactly
        do_backup(player, ["check"])
        assert out == ["{RYou have not backed up for {W1{R hour of gameplay.{x"]

    def test_check_hours_plural_under_a_day(self, out):
        player = _make_player()
        player["backup"] = 100  # nonzero: "no backup" branch requires backup == 0
        player["played"] = 100 + 3600 * 5  # elapsed == 5h, still under the 24h branch
        do_backup(player, ["check"])
        assert out == ["{RYou have not backed up for {W5{R hours of gameplay.{x"]

    def test_check_hours_over_a_day(self, out):
        player = _make_player()
        player["backup"] = 100
        player["played"] = 100 + 3600 * 30  # elapsed >= 24h -> the other formatting branch
        do_backup(player, ["check"])
        assert out == ["{RYou have not backed up for {W30{R hours of gameplay.{x"]

    def test_backup_does_not_touch_primary_save_fields(self, tmp_path, monkeypatch):
        # Sanity check requested by the port task: after a backup, a later
        # plain save() still targets the primary slot untouched by the backup.
        import game_state
        save_file = tmp_path / "primary.sav"
        backup_file = tmp_path / "backup.sav"
        monkeypatch.setattr(game_state, "SAVE_FILE", str(save_file))
        monkeypatch.setattr(game_state, "BACKUP_FILE", str(backup_file))
        player = _make_player()
        player["played"] = 10
        game_state.save_world(quiet=True)
        do_backup(player, [])
        player["played"] = 20
        game_state.save_world(quiet=True)
        played_i = game_state._PLAYER_NUMBER_SAVE_KEYS.index("played")
        primary_n = next(line for line in save_file.read_text().split("~")
                         if line.startswith("p.n="))
        backup_n = next(line for line in backup_file.read_text().split("~")
                        if line.startswith("p.n="))
        assert int(primary_n.split("=", 1)[1].split("|")[played_i]) == 20
        assert int(backup_n.split("=", 1)[1].split("|")[played_i]) == 10


class TestCompactPlayerSave:
    def test_numeric_and_equipment_roundtrip(self, tmp_path, monkeypatch):
        import game_state
        save_file = tmp_path / "compact.sav"
        monkeypatch.setattr(game_state, "SAVE_FILE", str(save_file))

        player = _make_player()
        player["level"] = 12
        player["xp"] = 3456
        player["gold_bank"] = 789
        player["perm_stat"]["str"] = 19
        player["equip"]["wield"] = {"vnum": 3702, "cost": 0}
        expected_numbers = {
            k: player[k] for k in game_state._PLAYER_NUMBER_SAVE_KEYS}
        expected_numbers["room"] = game_state.R_STARTING_ROOM
        expected_stats = dict(player["perm_stat"])

        game_state._serialize_world()
        payload = save_file.read_text()
        assert "~p.n=" in payload
        assert "~p.level=" not in payload
        assert "~p.eq=" in payload
        assert "~p.eq.wield=" not in payload

        world.chars.clear()
        loaded = create_char()
        loaded["_macros"] = {}
        world.chars[1] = loaded
        assert game_state.load_world() == "file"
        assert {
            k: loaded[k] for k in game_state._PLAYER_NUMBER_SAVE_KEYS
        } == expected_numbers
        assert loaded["perm_stat"] == expected_stats
        assert loaded["equip"]["wield"] == {"vnum": 3702, "cost": 0}
        assert set(loaded["equip"]) == set(_EQUIP_SAVE_ORDER)


# -- prime ------------------------------------------------------------------------

class TestPrime:
    def _hero(self):
        player = _make_player()
        player["level"] = MAX_MORTAL_LEVEL
        player["classes"] = [CLASS_WARRIOR, CLASS_MAGE]
        player["prime_class"] = 0
        player["trivia"] = 5
        return player

    def test_level_gate(self, out):
        player = self._hero()
        player["level"] = MAX_MORTAL_LEVEL - 1
        do_prime(player, ["mage"])
        assert player["prime_class"] == 0
        assert player["trivia"] == 5
        assert any("You must be level %d" % MAX_MORTAL_LEVEL in l for l in out)

    def test_no_args_prints_syntax_and_falls_through(self, out):
        # [PRIMESUD] bug-faithful port of upstream's missing `return` after
        # the syntax message (multiclass.c:699-704) -- see do_prime docstring.
        player = self._hero()
        do_prime(player, [])
        assert player["prime_class"] == 0
        assert player["trivia"] == 5
        assert any(l.startswith("Syntax: prime") for l in out)
        assert any("costs" in l for l in out)
        assert any("No such class!" in l for l in out)

    def test_unknown_class_name(self, out):
        player = self._hero()
        do_prime(player, ["bogus"])
        assert any("No such class!" in l for l in out)
        assert player["prime_class"] == 0

    def test_class_not_held(self, out):
        player = self._hero()
        do_prime(player, ["thief"])  # holds warrior/mage only
        assert any("You aren't part" in l for l in out)
        assert player["prime_class"] == 0

    def test_already_prime(self, out):
        player = self._hero()
        do_prime(player, ["warrior"])  # slot 0 is already prime
        assert any("already" in l for l in out)
        assert player["trivia"] == 5

    def test_insufficient_trivia(self, out):
        player = self._hero()
        player["trivia"] = 4
        do_prime(player, ["mage"])
        assert any("costs" in l for l in out)
        assert player["prime_class"] == 0
        assert player["trivia"] == 4

    def test_successful_swap_and_consumers(self, out, tmp_path, monkeypatch):
        player = self._hero()
        before_tag = class_who(player)
        assert before_tag == "Gl+1"  # remort-tier warrior name, cf. test_tier.py

        do_prime(player, ["mage"])

        assert player["prime_class"] == 1
        assert player["trivia"] == 0
        assert any("Your prime class is now Wizard" in l for l in out)
        assert prime_class(player) == CLASS_MAGE
        after_tag = class_who(player)
        assert after_tag == "Wi+1"
        # classes list itself is untouched -- prime is a slot index, not a
        # reorder (cf. 1stMud class_slot/prime_class in multiclass.c)
        assert player["classes"] == [CLASS_WARRIOR, CLASS_MAGE]

        # save/load round trip preserves the new prime slot
        import game_state
        monkeypatch.setattr(game_state, "SAVE_FILE", str(tmp_path / "t.sav"))
        game_state._serialize_world()
        world.chars.clear()
        player2 = create_char()
        player2["name"] = "Tester"
        player2["room"] = 9901
        player2["_macros"] = {}
        world.chars[1] = player2
        assert game_state.load_world() == "file"
        assert player2["prime_class"] == 1
        assert player2["classes"] == [CLASS_WARRIOR, CLASS_MAGE]
        assert prime_class(player2) == CLASS_MAGE
