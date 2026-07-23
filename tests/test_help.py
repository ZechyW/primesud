"""Tests for lazy help and category-index ports from 1stMud act_info.c."""
import os

import pytest

import handler
import info


@pytest.fixture
def help_out(monkeypatch):
    """Point do_help at the generated help file and capture tprint output."""
    monkeypatch.setattr(info, "HELP_FILE",
                        os.path.join("src", "help.txt"))
    monkeypatch.setattr(info, "HELP_INDEX",
                        os.path.join("src", "help.idx"))
    lines = []
    capture = lambda *a, **kw: lines.append(a[0] if a else "")
    monkeypatch.setattr(handler, "tprint", capture)
    # PLAYER dict is not registered as world.chars[1], so chprintln's
    # local-player gate would drop output -- capture at the info level
    monkeypatch.setattr(info, "chprintln", lambda ch, s="": (lines.extend(s) if type(s) is list else lines.append(s)))
    monkeypatch.setattr(info, "tpage", lambda page: lines.extend(page))
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


def test_motd_entry(help_out):
    # [PRIMESUD] single-user MOTD rewrite; also what do_motd shows
    info.do_help(PLAYER, ["motd"])
    text = "\n".join(help_out)
    assert "PrimeSUD" in text
    assert "No help found" not in text


def test_last_entry_prints_to_eof(help_out):
    # last entry's body terminates on EOF, not a following '#' header
    info.do_help(PLAYER, ["worship"])
    text = "\n".join(help_out)
    assert "Help Keywords : WORSHIP DEITY" in text
    assert "No help found" not in text


def test_credits_show_upstream_entries(help_out):
    info.do_credits(PLAYER, [])
    text = "\n".join(help_out)
    assert "Help Keywords : DIKU 'DIKU CREDITS'" in text
    assert "Help Keywords : ROM 'ROM CREDITS'" in text
    assert "Help Keywords : 1STMUD '1STMUD CREDITS'" in text


def test_index_offsets_align():
    # every index offset must sit immediately after its own header line
    with open(os.path.join("src", "help.txt"), "rb") as f:
        data = f.read()
    with open(os.path.join("src", "help.idx"), "rb") as f:
        for line in f:
            level, category, off_s, kw = line.rstrip(b"\n").split(b"|", 3)
            off = int(off_s)
            header = b"#" + level + b"|" + category + b"|" + kw + b"\n"
            assert data[off - len(header):off] == header, kw


def test_category_index_lists_counts(help_out):
    info.do_index(PLAYER, [])
    text = "\n".join(help_out)
    assert " 3) spells (76 helps)" in text
    assert " 4) commands (83 helps)" in text


def test_category_index_lists_topics_by_name(help_out):
    info.do_index(PLAYER, ["spells"])
    text = "\n".join(help_out)
    assert "[ SPELLS ]" in text
    assert "ACID BLAST" in text


def test_category_index_filters_by_level(help_out):
    info.do_index(PLAYER, ["commands"])
    assert "BID" not in "\n".join(help_out)
    del help_out[:]
    info.do_index({"level": 2}, ["commands"])
    assert "BID" in "\n".join(help_out)


def test_category_index_opens_numbered_topic(help_out):
    info.do_index(PLAYER, ["3", "1"])
    text = "\n".join(help_out)
    assert "Help Keywords : 'ACID BLAST'" in text
    assert "Help Category : spells" in text
    assert "These spells inflict damage" in text


def test_category_index_rejects_bad_input(help_out):
    info.do_index(PLAYER, ["bogus"])
    assert help_out == ["Unknown category."]


def test_category_import_is_complete_and_idempotent():
    from tools import import_help_categories

    categories = import_help_categories.upstream_categories(
        import_help_categories.SRC.read_bytes())
    current = import_help_categories.DST.read_bytes()
    result, entries, imported, custom, _digest = \
        import_help_categories.add_categories(current, categories)
    assert result == current
    assert (entries, imported, custom) == (284, 282, 2)


def test_help_is_name():
    assert info._help_is_name("acid blast", "'ACID BLAST' 'BURNING HANDS'")
    assert info._help_is_name("acid", "'ACID BLAST' FIREBALL")
    assert info._help_is_name("fire", "'ACID BLAST' FIREBALL")
    assert not info._help_is_name("blast acid", "'ACID BLAST' FIREBALL")
    assert not info._help_is_name("frost", "'ACID BLAST' FIREBALL")
