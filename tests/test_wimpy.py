"""Tests for do_wimpy (cf. 1stMud do_wimpy in act_info.c)."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import handler
import info
from handler import _char_base
from info import do_wimpy


@pytest.fixture
def out(monkeypatch):
    """Capture tprint output as list of lines."""
    lines = []
    capture = lambda s="", end="\n": lines.append(s)
    monkeypatch.setattr(handler, "tprint", capture)
    # player dict is not registered as world.chars[1], so chprintln's
    # local-player gate would drop output -- capture at the info level
    monkeypatch.setattr(info, "chprintln", lambda ch, s="": lines.append(s))
    return lines


@pytest.fixture
def player():
    ch = _char_base()
    ch.update({"id": 1, "max_hit": 100, "hit": 100})
    return ch


def test_no_args_defaults_to_fifth_of_max_hit(player, out):
    do_wimpy(player, [])
    assert player["wimpy"] == 20
    assert out == ["Wimpy set to 20 hit points."]


def test_explicit_value(player, out):
    do_wimpy(player, ["35"])
    assert player["wimpy"] == 35
    assert out == ["Wimpy set to 35 hit points."]


def test_negative_rejected(player, out):
    do_wimpy(player, ["-5"])
    assert player["wimpy"] == 0
    assert out == ["Your courage exceeds your wisdom."]


def test_over_half_max_hit_rejected(player, out):
    do_wimpy(player, ["51"])
    assert player["wimpy"] == 0
    assert out == ["Such cowardice ill becomes you."]


def test_non_numeric_yields_zero(player, out):
    # cf. atoi() -- non-numeric input yields 0
    do_wimpy(player, ["abc"])
    assert player["wimpy"] == 0
    assert out == ["Wimpy set to 0 hit points."]
