"""Tests for brief/compact/show/title (cf. 1stMud act_info.c do_brief/do_compact/
do_show/do_title -- COMM_BRIEF/COMM_COMPACT/COMM_SHOW_AFFECTS comm bits)."""
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
import info
import world
from handler import _char_base
from player import (COMM_BRIEF, COMM_COMPACT, COMM_SHOW_AFFECTS, PLR_DEFAULTS,
                    create_char, set_title)
from world import ROOM_DEFS, MOB_DEFS


def _stub_room(vnum, **extra):
    room = {"name": "Test Room", "desc": "A plain test room.", "exits": {},
            "items": [], "mobs": [], "area": "test", "flags": {},
            "sector": "inside"}
    room.update(extra)
    ROOM_DEFS._data[vnum] = room
    world.rooms._data[vnum] = room
    return room


def _make_player(room=9001):
    ch = _char_base()
    ch["id"] = 1
    ch["name"] = "Tester"
    ch["level"] = 20
    ch["room"] = room
    ch["flags"] = PLR_DEFAULTS
    world.chars[1] = ch
    return ch


@pytest.fixture(autouse=True)
def _clean_world_state():
    old_rooms = dict(ROOM_DEFS._data)
    old_wrooms = dict(world.rooms._data)
    old_chars = dict(world.chars)
    _stub_room(9001, exits={"n": 9002})
    _stub_room(9002)
    yield
    ROOM_DEFS._data.clear()
    ROOM_DEFS._data.update(old_rooms)
    world.rooms._data.clear()
    world.rooms._data.update(old_wrooms)
    world.chars.clear()
    world.chars.update(old_chars)


@pytest.fixture
def out(monkeypatch):
    lines = []
    capture = lambda *a, **kw: lines.append(" ".join(str(x) for x in a))
    monkeypatch.setattr(handler, "tprint", capture)
    return lines


# -- brief --------------------------------------------------------------------

def test_brief_toggle_messages_and_flag(out):
    player = _make_player()
    assert not player["flags"] & COMM_BRIEF  # off by default (not in PLR_DEFAULTS)
    info.do_brief(player, [])
    assert player["flags"] & COMM_BRIEF
    assert "You no longer see room descriptions." in out
    del out[:]
    info.do_brief(player, [])
    assert not player["flags"] & COMM_BRIEF
    assert "You now see room descriptions." in out


def test_brief_suppresses_desc_on_auto_look_only(out):
    player = _make_player()
    player["flags"] |= COMM_BRIEF
    info.do_look(player, ["auto"])  # cf. move_char's post-move do_look("auto")
    assert not any("plain test room" in l for l in out)
    assert any("Test Room" in l for l in out)  # room name/title still shown
    del out[:]
    info.do_look(player, [])  # explicit `look` always shows the desc
    assert any("plain test room" in l for l in out)


def test_brief_does_not_suppress_exits_items_mobs(out):
    player = _make_player()
    player["flags"] |= COMM_BRIEF
    from player import PLR_AUTOEXIT
    player["flags"] |= PLR_AUTOEXIT
    info.do_look(player, ["auto"])
    assert any("[Exits:" in l for l in out)


# -- compact --------------------------------------------------------------------

def test_compact_toggle_messages_and_flag(out):
    player = _make_player()
    info.do_compact(player, [])
    assert player["flags"] & COMM_COMPACT
    assert "Compact mode set." in out
    del out[:]
    info.do_compact(player, [])
    assert not player["flags"] & COMM_COMPACT
    assert "Compact mode removed." in out


def test_autolist_includes_compact_but_not_brief_or_show(out):
    # cf. 1stMud do_autolist (act_info.c:750-751): only "compact" is listed;
    # brief/show never appear there upstream either.
    player = _make_player()
    info.do_autolist(player, [])
    listing = "\n".join(out)
    assert "compact" in listing
    assert "brief" not in listing
    assert "show" not in listing


# -- show -----------------------------------------------------------------------

def test_show_toggle_messages_and_flag(out):
    player = _make_player()
    info.do_show(player, [])
    assert player["flags"] & COMM_SHOW_AFFECTS
    assert "Affects will now be shown in score." in out
    del out[:]
    info.do_show(player, [])
    assert not player["flags"] & COMM_SHOW_AFFECTS
    assert "Affects will no longer be shown in score." in out


@pytest.fixture
def score_out(monkeypatch):
    lines = []
    monkeypatch.setattr(info, "chprintln", lambda ch, s="": (lines.extend(s) if type(s) is list else lines.append(s)))
    monkeypatch.setattr(info, "free_mem", lambda: "245k")
    monkeypatch.setattr(info, "gc_collect", lambda: None)
    return lines


def test_score_appends_affects_when_show_on(score_out):
    from classes import CLASS_WARRIOR
    p = create_char(CLASS_WARRIOR)
    p["name"] = "Hero"
    p["flags"] |= COMM_SHOW_AFFECTS
    p["affect_list"] = [{"type": 1, "level": 10, "duration": 5,
                          "location": "hitroll", "modifier": 2,
                          "bitvector": "", "where": "to_affects"}]
    info.do_score(p, [])
    assert any("affected by the following spells" in l for l in score_out)


def test_score_omits_affects_when_show_off(score_out):
    from classes import CLASS_WARRIOR
    p = create_char(CLASS_WARRIOR)
    p["name"] = "Hero"
    p["affect_list"] = [{"type": 1, "level": 10, "duration": 5,
                          "location": "hitroll", "modifier": 2,
                          "bitvector": "", "where": "to_affects"}]
    info.do_score(p, [])
    assert not any("affected by the following spells" in l for l in score_out)


# -- title ------------------------------------------------------------------

def test_set_title_prepends_space_by_default():
    ch = {}
    set_title(ch, "Slayer of Dragons")
    assert ch["title"] == " Slayer of Dragons"


def test_set_title_no_space_for_leading_punctuation():
    ch = {}
    for punct in (".", ",", "!", "?"):
        set_title(ch, punct + "no space")
        assert ch["title"] == punct + "no space"


def test_create_char_default_title():
    from classes import CLASS_WARRIOR
    p = create_char(CLASS_WARRIOR)
    assert p["title"] == " the Human Warrior"


def test_do_title_empty_prompts(out):
    player = _make_player()
    info.do_title(player, "")
    assert "Change your title to what?" in out


def test_do_title_sets_and_reports_ok(out):
    player = _make_player()
    info.do_title(player, "the Dragonslayer")
    assert player["title"] == " the Dragonslayer"
    assert "Ok." in out


def test_do_title_length_cap_45_chars(out):
    player = _make_player()
    info.do_title(player, "x" * 100)
    # cf. 1stMud act_info.c:3531 -- capped at 45 chars before the leading
    # space set_title prepends, so the stored title is 46 chars long.
    assert player["title"] == " " + "x" * 45
    assert len(player["title"]) == 46


def test_do_title_rejects_tilde_and_quote(out):
    player = _make_player()
    player["title"] = " old title"
    info.do_title(player, "bad~title")
    assert player["title"] == " old title"
    assert any("may not contain" in l for l in out)
    del out[:]
    info.do_title(player, 'bad"title')
    assert player["title"] == " old title"
    assert any("may not contain" in l for l in out)


# -- version --------------------------------------------------------------------

def test_do_version_prints_version_constant(out):
    from config import VERSION
    player = _make_player()
    info.do_version(player, [])
    assert any(VERSION in l for l in out)
    assert any("PrimeSUD" in l and "1stMud" in l for l in out)


# -- persistence round trip ----------------------------------------------------

class TestSaveLoad:
    def test_comm_flags_and_title_roundtrip(self, tmp_path, monkeypatch):
        import game_state
        monkeypatch.setattr(game_state, "SAVE_FILE", str(tmp_path / "t.sav"))
        world.areas = []
        player = create_char()
        player["name"] = "Tester"
        player["room"] = 9001
        player["_macros"] = {}
        player["flags"] |= COMM_BRIEF | COMM_COMPACT | COMM_SHOW_AFFECTS
        set_title(player, "the Dragonslayer")
        world.chars[1] = player
        game_state._serialize_world()

        world.chars.clear()
        player2 = create_char()
        player2["name"] = "Tester"
        player2["room"] = 9001
        player2["_macros"] = {}
        world.chars[1] = player2
        assert game_state.load_world() == "file"
        assert player2["flags"] & COMM_BRIEF
        assert player2["flags"] & COMM_COMPACT
        assert player2["flags"] & COMM_SHOW_AFFECTS
        assert player2["title"] == " the Dragonslayer"
