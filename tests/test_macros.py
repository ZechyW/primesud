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


def test_tilde_in_macro_rejected(out):
    # '~' is the save-payload line separator (game_state.py) -- a macro
    # containing it would corrupt the save on the next write.
    before = dict(_MACRO_SUBST)
    do_macro(None, ["3", "say", "hi~quit"])
    assert _MACRO_SUBST == before
    assert any("may not contain" in l for l in out)
