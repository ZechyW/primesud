"""Tests for the autoskill automated combat action engine [PRIMESUD].

See AUTOSKILL_PLAN.md for the design (flat rotation walk, custom order,
learned-floor heuristic, status-line editor).
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import classes
import handler
import info
import game_state
import terminal
import world
from handler import _char_base, PLR_AUTOSKILL, PLR_DEFAULTS
from player import create_char

import autoskill
from autoskill import (auto_skill_round, get_rotation, do_autoskill,
                       _edit_rotation, _LEARNED_FLOOR, GSN_WEAKEN)
from skills_table import (GSN_BLINDNESS, GSN_CURSE, GSN_BASH, GSN_TRIP,
                          GSN_DIRT, GSN_DISARM, GSN_KICK)

# sn 48 / 67 in skills_table.py -- real char_offensive spells with runtime
# spell_fun implementations, but no exported GSN_* constant (only debuffs and
# physical skills get pgsn constants). Skill numeric IDs are permanent once
# assigned (see game_state.py SAVE_VERSION comment) so hardcoding is safe.
_SN_FIREBALL = 48
_SN_MAGIC_MISSILE = 67


@pytest.fixture(autouse=True)
def _clean_world_state():
    old_chars = dict(world.chars)
    old_areas = list(world.areas)
    old_wrooms = dict(world.rooms._data)
    yield
    world.chars.clear()
    world.chars.update(old_chars)
    world.areas = old_areas
    world.rooms._data.clear()
    world.rooms._data.update(old_wrooms)


@pytest.fixture
def out(monkeypatch):
    """Capture chprintln/tprint output as list of lines.

    autoskill.py imports chprintln by value from handler, but chprintln's
    real implementation (_send_player_text) still looks up handler's own
    module-level `tprint` at call time, so patching handler.tprint alone
    captures output regardless of which module invoked chprintln.
    """
    lines = []
    capture = lambda *a, **kw: lines.append(" ".join(str(x) for x in a))
    monkeypatch.setattr(handler, "tprint", capture)
    return lines


def _make_player(**overrides):
    """Minimal player dict registered as world.chars[1] (autoskill is player-only)."""
    ch = _char_base()
    ch["id"] = 1
    ch["name"] = "Tester"
    ch["level"] = 20
    ch["room"] = 9001
    ch["flags"] = PLR_DEFAULTS
    ch["learned"] = {}
    ch["mana"] = 100
    ch["max_mana"] = 100
    ch.update(overrides)
    world.chars[1] = ch
    return ch


def _make_mob(mid, **overrides):
    """Minimal fighting-target mob dict registered as world.chars[mid]."""
    ch = _char_base()
    ch["id"] = mid
    ch["is_npc"] = True
    ch["level"] = 5
    ch["room"] = 9001
    ch["pos"] = "fighting"
    ch.update(overrides)
    world.chars[mid] = ch
    return ch


# -- 1. Command status and toggle ----------------------------------------------

def test_bare_shows_status_and_help_without_toggling(out):
    player = _make_player()
    assert player["flags"] & PLR_AUTOSKILL == 0  # not in PLR_DEFAULTS -> off
    do_autoskill(player, [])
    assert not player["flags"] & PLR_AUTOSKILL
    assert "Autoskill is off." in out[0]
    assert "autoskill <on|off|edit|list|reset>" in out[1]


def test_explicit_on_off_sets_flag(out):
    player = _make_player()
    do_autoskill(player, ["on"])
    assert player["flags"] & PLR_AUTOSKILL
    assert "You now attack with your skills and spells automatically." in out
    do_autoskill(player, ["off"])
    assert not player["flags"] & PLR_AUTOSKILL
    assert "You no longer attack with your skills and spells automatically." in out


# -- 2. autolist row ------------------------------------------------------------

def test_autolist_includes_autoskill_row(out):
    player = _make_player()
    info.do_autolist(player, [])
    listing = "\n".join(out)
    assert "autoskill" in listing


# -- 3. Persistence round trip --------------------------------------------------

def test_autoskill_rot_persistence_round_trip(monkeypatch, tmp_path):
    monkeypatch.setattr(game_state, "SAVE_FILE", str(tmp_path / "t.sav"))
    world.areas = []
    # Room 9001 must resolve without triggering lazy area loading (real
    # vnum ranges/area files are registered by other test modules that ran
    # earlier in the suite) -- stub it directly, cf. test_stances.py.
    world.rooms._data[9001] = {"name": "Test Room", "desc": "x", "exits": {},
                               "items": [], "mobs": [], "area": "test",
                               "flags": {}, "sector": "inside"}

    # Custom rotation incl. an excluded ("!") entry round-trips exactly.
    player = create_char()
    player["name"] = "Tester"
    player["room"] = 9001
    player["_macros"] = {}
    player["autoskill_rot"] = ["fireball", "!blindness", "bash"]
    world.chars[1] = player
    game_state._serialize_world()

    world.chars.clear()
    player2 = create_char()
    player2["name"] = "Tester"
    player2["room"] = 9001
    player2["_macros"] = {}
    world.chars[1] = player2
    assert game_state.load_world() == "file"
    assert player2["autoskill_rot"] == ["fireball", "!blindness", "bash"]

    # Absent key stays absent (pure heuristic default).
    world.chars.clear()
    player3 = create_char()
    player3["name"] = "Tester"
    player3["room"] = 9001
    player3["_macros"] = {}
    assert "autoskill_rot" not in player3
    world.chars[1] = player3
    game_state._serialize_world()

    world.chars.clear()
    player4 = create_char()
    player4["name"] = "Tester"
    player4["room"] = 9001
    player4["_macros"] = {}
    world.chars[1] = player4
    assert game_state.load_world() == "file"
    assert "autoskill_rot" not in player4


# -- 4. Engine no-ops ------------------------------------------------------------

def test_engine_noops_when_gates_fail(monkeypatch):
    calls = []
    monkeypatch.setattr(autoskill, "get_rotation", lambda p: calls.append(1) or [])

    # flag off
    p = _make_player(flags=PLR_DEFAULTS, wait=0, pos="fighting", fighting=2)
    auto_skill_round(p)
    assert calls == []

    # wait > 0
    p = _make_player(flags=PLR_AUTOSKILL, wait=5, pos="fighting", fighting=2)
    auto_skill_round(p)
    assert calls == []

    # manual command queued this round
    p = _make_player(flags=PLR_AUTOSKILL, wait=0, pos="fighting", fighting=2,
                     _cmd_queued=True)
    auto_skill_round(p)
    assert calls == []

    # not fighting position
    p = _make_player(flags=PLR_AUTOSKILL, wait=0, pos="standing", fighting=2)
    auto_skill_round(p)
    assert calls == []

    # NPC (pets/charmies excluded -- engine is player-only)
    p = _make_player(flags=PLR_AUTOSKILL, wait=0, pos="fighting", fighting=2,
                     is_npc=True)
    auto_skill_round(p)
    assert calls == []

    # fighting id missing from world.chars
    p = _make_player(flags=PLR_AUTOSKILL, wait=0, pos="fighting", fighting=999)
    auto_skill_round(p)
    assert calls == []


# -- 5. Default rotation order ---------------------------------------------------

def test_default_rotation_order_debuffs_then_spells_then_skills(monkeypatch):
    monkeypatch.setattr(classes, "can_use_skill_spell", lambda ch, sn: True)
    levels = {_SN_FIREBALL: 30, _SN_MAGIC_MISSILE: 10}
    monkeypatch.setattr(classes, "skill_level", lambda ch, sn: levels.get(sn, 1))

    learned = {
        GSN_BLINDNESS: 80, GSN_WEAKEN: 80, GSN_CURSE: 80,
        _SN_FIREBALL: 80,          # >= floor -> default included
        _SN_MAGIC_MISSILE: 40,     # < floor -> default excluded
        GSN_BASH: 50, GSN_TRIP: 50, GSN_DIRT: 50, GSN_DISARM: 50, GSN_KICK: 50,
    }
    player = _make_player(learned=learned)

    rot = get_rotation(player)
    names = [name for sn, name, kind, incl in rot]
    assert names == ["blindness", "weaken", "curse", "fireball", "magic missile",
                     "bash", "trip", "dirt kicking", "disarm", "kick"]

    incl = {name: incl for sn, name, kind, incl in rot}
    assert incl["fireball"] is True
    assert incl["magic missile"] is False
    for phys in ("bash", "trip", "dirt kicking", "disarm", "kick"):
        assert incl[phys] is True  # physical skills always included, floor doesn't apply


# -- 6. Custom order: reorder, exclusion, floor bypass ---------------------------

def test_custom_rotation_order_exclusion_and_floor_bypass(monkeypatch):
    monkeypatch.setattr(classes, "can_use_skill_spell", lambda ch, sn: True)
    monkeypatch.setattr(classes, "skill_level", lambda ch, sn: 1)
    fired = []
    monkeypatch.setattr(autoskill, "do_cast", lambda p, args: fired.append(args[0]))

    learned = {GSN_BLINDNESS: 80, _SN_FIREBALL: 40}  # fireball below the 75 floor
    player = _make_player(flags=PLR_AUTOSKILL, wait=0, pos="fighting", fighting=2,
                          learned=learned, mana=100, max_mana=100)
    _make_mob(2)
    player["autoskill_rot"] = ["!blindness", "fireball"]

    auto_skill_round(player)
    # blindness excluded -> never fires even though eligible; fireball fires
    # despite being below the floor because it is explicitly kept (bypass).
    assert fired == ["fireball"]


# -- 7. Newly learned entry appends at the end -----------------------------------

def test_new_candidate_appends_at_end_default_included(monkeypatch):
    monkeypatch.setattr(classes, "can_use_skill_spell", lambda ch, sn: True)
    monkeypatch.setattr(classes, "skill_level", lambda ch, sn: 1)

    learned = {GSN_BLINDNESS: 80, _SN_FIREBALL: 80}
    player = _make_player(learned=learned)
    player["autoskill_rot"] = ["fireball"]  # blindness not saved -> newly learned

    rot = get_rotation(player)
    names = [name for sn, name, kind, incl in rot]
    assert names[-1] == "blindness"
    incl = {name: incl for sn, name, kind, incl in rot}
    assert incl["blindness"] is True  # default inclusion (>= floor)


# -- 8. Debuff fires once, then skipped once victim is affected ------------------

def test_debuff_fires_once_then_skipped_once_affected(monkeypatch):
    monkeypatch.setattr(classes, "can_use_skill_spell", lambda ch, sn: True)
    fired = []
    monkeypatch.setattr(autoskill, "do_cast", lambda p, args: fired.append(args[0]))

    learned = {GSN_BLINDNESS: 80}
    player = _make_player(flags=PLR_AUTOSKILL, wait=0, pos="fighting", fighting=2,
                          learned=learned, mana=100, max_mana=100)
    victim = _make_mob(2)

    auto_skill_round(player)
    assert fired == ["blindness"]

    # do_cast is mocked (doesn't apply the real affect), so simulate the
    # spell having landed, and confirm the engine skips to the next entry
    # (there is none here, so no further action fires).
    victim["affect_list"] = [{"type": GSN_BLINDNESS}]
    auto_skill_round(player)
    assert fired == ["blindness"]


# -- 9. Offensive spell mana reserve ----------------------------------------------

def test_offensive_spell_respects_mana_reserve(monkeypatch):
    monkeypatch.setattr(classes, "can_use_skill_spell", lambda ch, sn: True)
    monkeypatch.setattr(classes, "skill_level", lambda ch, sn: 1)
    fired = []
    monkeypatch.setattr(autoskill, "do_cast", lambda p, args: fired.append(args[0]))

    learned = {_SN_FIREBALL: 80}
    player = _make_player(flags=PLR_AUTOSKILL, wait=0, pos="fighting", fighting=2,
                          learned=learned, level=20, max_mana=100)
    _make_mob(2)

    # fireball min_mana=15; spell_mana formula -> max(15, 100//21) = 15
    player["mana"] = 20  # 20-15=5 < 25% of 100 -> skipped
    auto_skill_round(player)
    assert fired == []

    player["mana"] = 50  # 50-15=35 >= 25 -> fires
    auto_skill_round(player)
    assert fired == ["fireball"]


# -- 10. Skill pre-filters ---------------------------------------------------------

def test_skill_prefilters_gate_bash_disarm_dirt(monkeypatch):
    monkeypatch.setattr(classes, "can_use_skill_spell", lambda ch, sn: True)
    fired = []
    monkeypatch.setattr(autoskill, "_SKILL_HANDLERS", {
        GSN_BASH: lambda p, a: fired.append("bash"),
        GSN_DISARM: lambda p, a: fired.append("disarm"),
        GSN_DIRT: lambda p, a: fired.append("dirt"),
    })

    # bash: victim below fighting position -> skipped, fires once standing
    player = _make_player(flags=PLR_AUTOSKILL, wait=0, pos="fighting", fighting=2,
                          learned={GSN_BASH: 80})
    victim = _make_mob(2, pos="stunned")
    auto_skill_round(player)
    assert fired == []
    victim["pos"] = "standing"
    auto_skill_round(player)
    assert fired == ["bash"]

    # disarm: victim not wielding -> skipped, fires once wielding
    del fired[:]
    player = _make_player(flags=PLR_AUTOSKILL, wait=0, pos="fighting", fighting=3,
                          learned={GSN_DISARM: 80})
    player["equip"]["wield"] = 3001  # player is armed -- satisfies the attacker gate
    victim = _make_mob(3, pos="fighting")
    auto_skill_round(player)
    assert fired == []
    victim["equip"]["wield"] = 3010
    auto_skill_round(player)
    assert fired == ["disarm"]

    # dirt kicking: victim already blind -> skipped, fires once sighted
    del fired[:]
    player = _make_player(flags=PLR_AUTOSKILL, wait=0, pos="fighting", fighting=4,
                          learned={GSN_DIRT: 80})
    victim = _make_mob(4, pos="fighting", affected_by={"blind": True})
    auto_skill_round(player)
    assert fired == []
    victim["affected_by"] = {}
    auto_skill_round(player)
    assert fired == ["dirt"]


# -- 11. Lag self-throttle -----------------------------------------------------

def test_lag_self_throttles_next_round(monkeypatch):
    monkeypatch.setattr(classes, "can_use_skill_spell", lambda ch, sn: True)
    fired = []

    def _fake_cast(p, args):
        fired.append(args[0])
        p["wait"] = 12  # simulate the WaitState lag a real do_cast would set

    monkeypatch.setattr(autoskill, "do_cast", _fake_cast)
    learned = {GSN_BLINDNESS: 80}
    player = _make_player(flags=PLR_AUTOSKILL, wait=0, pos="fighting", fighting=2,
                          learned=learned, mana=100, max_mana=100)
    _make_mob(2)

    auto_skill_round(player)
    assert fired == ["blindness"]

    auto_skill_round(player)  # still lagged -> no-op
    assert fired == ["blindness"]


# -- 12. Editor -----------------------------------------------------------------

class _FakeTr:
    """Minimal tr stand-in for the status-line editor: captures prints,
    replays a scripted (char, auto_submit) key sequence via poll_char."""

    def __init__(self, keys):
        self.status_text = "old status"
        self._scrollback_ms = 0
        self.keys = list(keys)
        self.lines = []
        self.resynced = 0

    def print(self, s="", end="\n"):
        self.lines.append(s)

    def poll_char(self, key_commands=None):
        return self.keys.pop(0)

    def set_status(self, text):
        self.status_text = text

    def resync_keyboard(self):
        self.resynced += 1

    def _refresh_indicators(self):
        pass


def test_editor_reorder_toggle_and_save(monkeypatch):
    monkeypatch.setattr(classes, "can_use_skill_spell", lambda ch, sn: True)
    monkeypatch.setattr(classes, "skill_level", lambda ch, sn: 1)

    learned = {GSN_BLINDNESS: 80, GSN_WEAKEN: 80, GSN_CURSE: 80}
    player = _make_player(learned=learned)
    # default order: [blindness, weaken, curse], sel starts at 0 (blindness)
    fake = _FakeTr([("\\D", None), ("*", None), ("+", None), ("\n", None)])
    monkeypatch.setattr(terminal, "tr", fake)

    _edit_rotation(player)

    # \D -> sel=1 (weaken); * -> toggles weaken off; + -> swaps weaken/curse
    # (weaken moves to the end); Enter saves.
    assert player["autoskill_rot"] == ["blindness", "curse", "!weaken"]
    assert fake.status_text == "old status"  # restored in the finally block
    assert fake.resynced == 2  # _force_numeric_keys() at entry + finally block


def test_editor_escape_cancels_without_saving(monkeypatch):
    monkeypatch.setattr(classes, "can_use_skill_spell", lambda ch, sn: True)

    learned = {GSN_BLINDNESS: 80}
    player = _make_player(learned=learned)
    fake = _FakeTr([("*", None), ("\\e", None)])
    monkeypatch.setattr(terminal, "tr", fake)

    _edit_rotation(player)

    assert "autoskill_rot" not in player
