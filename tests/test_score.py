"""Tests for the do_score header title (cf. 1stMud dlm_score / set_title)."""
import pytest

import info
from colors import color_len
from config import TERMINAL_COLS
from player import create_char
from classes import CLASS_WARRIOR, CLASS_MAGE


@pytest.fixture
def score_out(monkeypatch):
    """Capture do_score output lines at the info level."""
    lines = []
    monkeypatch.setattr(info, "chprintln", lambda ch, s="": lines.append(s))
    # gc.mem_free() is MicroPython-only; stub the memory readout on CPython
    monkeypatch.setattr(info, "free_mem", lambda: "245k")
    monkeypatch.setattr(info, "gc_collect", lambda: None)
    return lines


def _score_lines(score_out, class_idx, name):
    p = create_char(class_idx)
    p["name"] = name
    info.do_score(p, [])
    return score_out


def test_header_shows_name_and_title(score_out):
    lines = _score_lines(score_out, CLASS_WARRIOR, "Hero")
    assert "Hero the Human Warrior" in lines[1]


def test_header_title_prime_class_only(score_out):
    lines = _score_lines(score_out, CLASS_MAGE, "Xyz")
    assert "Xyz the Human Mage" in lines[1]


def test_all_lines_align(score_out):
    lines = _score_lines(score_out, CLASS_WARRIOR, "Maximilianxx")  # 12-char cap
    widths = {color_len(ln) for ln in lines}
    assert widths == {TERMINAL_COLS}


def test_header_falls_back_to_bare_name_on_overflow(score_out):
    p = create_char(CLASS_WARRIOR)
    p["name"] = "X" * 40  # impossible via chargen (12-char cap), but be safe
    info.do_score(p, [])
    assert "the Human" not in score_out[1]
    assert color_len(score_out[1]) == TERMINAL_COLS
