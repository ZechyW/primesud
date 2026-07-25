"""Tests for the [PRIMESUD] macro command (macros.py)."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

from terminal import init_terminal
init_terminal()

import macros
from macros import do_macro, _MACRO_SUBST
from colors import color_len, color_parse_runs, strip_colors
from config import FNKEY_NAMES, TERMINAL_COLS


@pytest.fixture(autouse=True)
def _clean_macros():
    old = dict(_MACRO_SUBST)
    yield
    _MACRO_SUBST.clear()
    _MACRO_SUBST.update(old)


@pytest.fixture
def out(monkeypatch):
    lines = []
    monkeypatch.setattr(macros, "tprint", lambda s="", end="\n": lines.append(s))
    return lines


def test_set_digit_macro(out):
    do_macro(None, ["3", "cast", "fireball"])
    assert _MACRO_SUBST["3"] == "cast fireball"


def test_query_is_non_destructive_and_unset_is_explicit(out):
    _MACRO_SUBST["9"] = "cast fireball"
    before = dict(_MACRO_SUBST)

    do_macro(None, ["9"])
    assert _MACRO_SUBST == before
    assert "cast fireball" in out[-1]

    do_macro(None, ["unset", "9"])
    assert "9" not in _MACRO_SUBST
    assert out[-1] == "Macro 9 unset."


def test_unset_requires_one_valid_key(out):
    before = dict(_MACRO_SUBST)

    do_macro(None, ["unset"])
    assert _MACRO_SUBST == before
    assert out[-1] == "Usage: macro unset <key>"

    do_macro(None, ["unset", "bogus"])
    assert _MACRO_SUBST == before
    assert out[-1].startswith("Key must be")


def test_macro_defaults_and_keys_remain_configurable(out):
    by_name = {name: key for key, name in FNKEY_NAMES.items()}
    do_macro(None, ["default"])
    assert _MACRO_SUBST[by_name["xy"]] == "run"
    assert _MACRO_SUBST[by_name["ln"]] == "quest info"
    assert _MACRO_SUBST[by_name["log"]] == "gquest check"
    assert _MACRO_SUBST["4"] == "give"
    assert _MACRO_SUBST["3"] == "train"
    assert _MACRO_SUBST["."] == "help"

    do_macro(None, ["xy", "scan"])
    assert _MACRO_SUBST[by_name["xy"]] == "scan"
    do_macro(None, [".", "commands"])
    assert _MACRO_SUBST["."] == "commands"


def test_grid_matches_physical_layout_and_truncates_preview(out):
    _MACRO_SUBST["9"] = "cast fireball"
    do_macro(None, [])

    plain = [strip_colors(line) for line in out]
    assert len(out) == 20
    assert all(color_len(line) == TERMINAL_COLS for line in out)
    assert all(label in plain[1] for label in ("x^y", "sin", "cos", "tan", "ln", "log"))
    assert all(label in plain[4] for label in ("x^2", "+/-", "()", ",", "Enter"))
    assert plain[1].count("|") == 7
    assert plain[4].count("|") == 6
    assert plain[6].count("+") == 6
    assert all(label in plain[8] for label in ("EEX", "7", "8", "9", "/"))
    assert "[Recall]" in plain[9]
    assert "On" in plain[17]
    assert "[Exit]" in plain[18]
    assert "help" in plain[18]
    assert "cast fir..." in plain[9]
    assert "cast fireball" not in "".join(plain)


def test_macro_display_treats_color_codes_as_literal_text(out):
    do_macro(None, ["9", "say", "{Rcharge"])
    assert "{{Rcharge" in out[-1]

    do_macro(None, ["9"])
    assert "{{Rcharge" in out[-1]

    out[:] = []
    do_macro(None, [])
    assert "{{Rch..." in out[9]
    assert all(sum(len(segment) for _, segment in color_parse_runs(line))
               == TERMINAL_COLS for line in out)


def test_tilde_in_macro_rejected(out):
    # '~' is the save-payload line separator (game_state.py) -- a macro
    # containing it would corrupt the save on the next write.
    before = dict(_MACRO_SUBST)
    do_macro(None, ["3", "say", "hi~quit"])
    assert _MACRO_SUBST == before
    assert any("may not contain" in l for l in out)


def test_macro_bindings_survive_save_load(tmp_path, monkeypatch):
    # '.' is the only non-alphanumeric macro key, so it is the one that can
    # break the "p.macro.<key>=<cmd>" save line (game_state.py).
    import game_state
    import world
    from player import create_char
    monkeypatch.setattr(game_state, "SAVE_FILE", str(tmp_path / "t.sav"))
    world.areas = []
    saved = {".": "help", "7": "kill", _fn_key("xy"): "run"}
    player = create_char()
    player["name"] = "Tester"
    player["room"] = 9001
    player["_macros"] = dict(saved)
    world.chars[1] = player
    game_state._serialize_world()

    world.chars.clear()
    player2 = create_char()
    player2["name"] = "Tester"
    player2["room"] = 9001
    player2["_macros"] = {}
    world.chars[1] = player2
    assert game_state.load_world() == "file"
    assert player2["_macros"] == saved


def _fn_key(name):
    """Sentinel for a function-key display name."""
    return {v: k for k, v in FNKEY_NAMES.items()}[name]
