"""Tests for lazy help and category-index ports from 1stMud act_info.c."""
import pytest

import handler
import info


@pytest.fixture
def help_out(monkeypatch):
    """Capture tprint output; do_help reads the real src/ help files."""
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


def test_quoted_multiword_keyword(help_out):
    info.do_help(PLAYER, ["acid", "blast"])
    assert any("ACID BLAST" in ln for ln in help_out)


def test_single_letter_opens_a_picker_of_matches(help_out, monkeypatch):
    # [PRIMESUD] bare list replaced by a picker -- see test_help_browser.py
    seen = {}
    monkeypatch.setattr(info, "pick_from",
                        lambda title, opts, page=0:
                        seen.update(title=title, opts=opts) or -1)
    info.do_help(PLAYER, ["m"])
    assert seen["title"] == "Help files starting with 'M'"
    assert "MOTD" in seen["opts"]
    assert help_out == []


def test_no_match(help_out):
    info.do_help(PLAYER, ["xyzzy"])
    assert any("No help found for xyzzy" in ln for ln in help_out)


def test_numbered_selection(help_out):
    # number_argument("2.s") -> target "s", len 1 -> list mode, which ignores
    # the number and opens the picker instead; two letters select directly
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
    # last entry's body terminates on EOF, not a following '#' header;
    # max-level player so the test holds whatever entry sits last
    with open(info.HELP_INDEX, "rb") as f:
        last = f.read().rstrip(b"\n").rsplit(b"\n", 1)[-1]
    keywords = last.split(b"|", 3)[3].decode()
    info.do_help({"level": 60}, [keywords.split(" ")[0].lower()])
    text = "\n".join(help_out)
    assert "Help Keywords : %s" % keywords in text
    assert "No help found" not in text


def test_credits_show_upstream_entries(help_out):
    info.do_credits(PLAYER, [])
    text = "\n".join(help_out)
    assert "Help Keywords : DIKU 'DIKU CREDITS'" in text
    assert "Help Keywords : ROM 'ROM CREDITS'" in text
    assert "Help Keywords : 1STMUD '1STMUD CREDITS'" in text


def test_index_offsets_align():
    # every index offset must sit immediately after its own header line
    with open(info.HELP_FILE, "rb") as f:
        data = f.read()
    with open(info.HELP_INDEX, "rb") as f:
        for line in f:
            level, category, off_s, kw = line.rstrip(b"\n").split(b"|", 3)
            off = int(off_s)
            header = b"#" + level + b"|" + category + b"|" + kw + b"\n"
            assert data[off - len(header):off] == header, kw


def test_category_index_lists_counts(help_out):
    # Slots are pinned, counts are not: the numbering is what `index <n>`
    # resolves against, while a literal count only drifts on help.txt edits.
    # Level filtering is covered by test_category_index_filters_by_level.
    counts = dict(info._help_visible_categories(PLAYER["level"]))
    info.do_index(PLAYER, [])
    text = "\n".join(help_out)
    assert " 2) commands (%d helps)" % counts["commands"] in text
    assert " 4) spells (%d helps)" % counts["spells"] in text
    # unported systems sit at level 51, so they never reach the listing
    assert "olc" not in text
    assert "deities" not in text


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
    info.do_index(PLAYER, ["4", "1"])
    text = "\n".join(help_out)
    assert "Help Keywords : 'ACID BLAST'" in text
    assert "Help Category : spells" in text
    assert "These spells inflict damage" in text


def test_category_index_rejects_bad_input(help_out):
    info.do_index(PLAYER, ["bogus"])
    assert help_out == ["Unknown category."]


def test_every_entry_has_a_listed_category():
    # [PRIMESUD] a category missing from HELP_CATEGORIES is silently dropped
    # from both the index and the browser, so entries would vanish unnoticed
    with open(info.HELP_INDEX, "rb") as f:
        for line in f:
            _level, category, _off, kw = line.rstrip(b"\n").split(b"|", 3)
            assert category.decode() in info.HELP_CATEGORIES, kw


def test_help_is_name():
    assert info._help_is_name("acid blast", "'ACID BLAST' 'BURNING HANDS'")
    assert info._help_is_name("acid", "'ACID BLAST' FIREBALL")
    assert info._help_is_name("fire", "'ACID BLAST' FIREBALL")
    assert not info._help_is_name("blast acid", "'ACID BLAST' FIREBALL")
    assert not info._help_is_name("frost", "'ACID BLAST' FIREBALL")
