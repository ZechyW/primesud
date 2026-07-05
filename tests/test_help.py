"""Tests for do_help lazy file-scan port (cf. 1stMud do_help in act_info.c)."""
import os

import pytest

import handler
import info


@pytest.fixture
def help_out(monkeypatch):
    """Point do_help at the generated help file and capture tprint output."""
    monkeypatch.setattr(info, "HELP_FILE",
                        os.path.join("src", "help.dat"))
    monkeypatch.setattr(info, "HELP_INDEX",
                        os.path.join("src", "help.idx"))
    lines = []
    capture = lambda *a, **kw: lines.append(a[0] if a else "")
    monkeypatch.setattr(handler, "tprint", capture)
    # PLAYER dict is not registered as world.chars[1], so chprintln's
    # local-player gate would drop output -- capture at the info level
    monkeypatch.setattr(info, "chprintln", lambda ch, s="": lines.append(s))
    return lines


PLAYER = {"level": 1}


def test_entry_lookup(help_out):
    info.do_help(PLAYER, ["cast"])
    text = "\n".join(help_out)
    assert "Help Keywords : CAST" in text
    assert "Syntax" in text


def test_default_is_summary(help_out):
    info.do_help(PLAYER, [])
    assert any("SUMMARY" in ln for ln in help_out)


def test_quoted_multiword_keyword(help_out):
    info.do_help(PLAYER, ["acid", "blast"])
    assert any("ACID BLAST" in ln for ln in help_out)


def test_single_letter_lists(help_out):
    info.do_help(PLAYER, ["m"])
    text = "\n".join(help_out)
    assert "start with the letter 'M'" in text
    assert "total help files." in text


def test_no_match(help_out):
    info.do_help(PLAYER, ["xyzzy"])
    assert any("No help found for xyzzy" in ln for ln in help_out)


def test_numbered_selection(help_out):
    info.do_help(PLAYER, ["2.s"])
    # single char after number -> list mode is NOT triggered upstream?
    # number_argument("2.s") -> target "s", len 1 -> list mode; use a word
    del help_out[:]
    info.do_help(PLAYER, ["2.sc"])
    text = "\n".join(help_out)
    assert "Help Keywords :" in text


def test_level_filter(help_out):
    # negative-level helps (e.g. hidden keyword entries) still visible
    info.do_help(PLAYER, ["wizlist"])
    assert not any("No help found" in ln for ln in help_out)


def test_last_entry_prints_to_eof(help_out):
    # last entry's body terminates on EOF, not a following '#' header
    info.do_help(PLAYER, ["worship"])
    text = "\n".join(help_out)
    assert "Help Keywords : WORSHIP DEITY" in text
    assert "No help found" not in text


def test_index_offsets_align():
    # every index offset must sit immediately after its own header line
    with open(os.path.join("src", "help.dat"), "rb") as f:
        data = f.read()
    with open(os.path.join("src", "help.idx"), "rb") as f:
        for line in f:
            level, off_s, kw = line.rstrip(b"\n").split(b"|", 2)
            off = int(off_s)
            header = b"#" + level + b"|" + kw + b"\n"
            assert data[off - len(header):off] == header, kw


def test_help_is_name():
    assert info._help_is_name("acid blast", "'ACID BLAST' 'BURNING HANDS'")
    assert info._help_is_name("acid", "'ACID BLAST' FIREBALL")
    assert info._help_is_name("fire", "'ACID BLAST' FIREBALL")
    assert not info._help_is_name("blast acid", "'ACID BLAST' FIREBALL")
    assert not info._help_is_name("frost", "'ACID BLAST' FIREBALL")
