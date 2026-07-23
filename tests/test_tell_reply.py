"""Regression tests for do_tell / do_reply (cf. 1stMud act_comm.c).

Both took the verbatim-argument signature in the interpret free-text refactor
(commit 8bb****) but their parameter stayed named ``args`` while the body read
``argument`` -- an UnboundLocalError on every reachable message path.  No test
exercised either command, so the crash shipped.  Fixed 09/07/2026.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import comm
import world
from handler import _char_base
from world import ROOM_DEFS, MOB_DEFS


@pytest.fixture
def two_chars(monkeypatch):
    """A player and a mob in one room; captured chprintlnf output."""
    old_rd = dict(ROOM_DEFS._data)
    old_wr = dict(world.rooms._data)
    old_ch = dict(world.chars)
    old_md = dict(MOB_DEFS._data)
    room = {"name": "R", "desc": "x", "exits": {}, "items": [], "mobs": [2],
            "area": "test", "flags": {}, "sector": "inside"}
    ROOM_DEFS._data[9001] = room
    world.rooms._data[9001] = room
    MOB_DEFS._data[9405] = {"short_descr": "a guard", "keywords": "guard"}

    player = _char_base(); player["id"] = 1; player["is_npc"] = False
    player["name"] = "Alice"; player["room"] = 9001
    mob = _char_base(); mob["id"] = 2; mob["is_npc"] = True; mob["tpl"] = 9405
    mob["name"] = "guard"; mob["short_descr"] = "a guard"; mob["room"] = 9001
    world.chars[1] = player
    world.chars[2] = mob

    out = []
    monkeypatch.setattr(comm, "chprintlnf",
                        lambda ch, fmt, *a: out.append(fmt % a))
    yield player, mob, out

    ROOM_DEFS._data.clear(); ROOM_DEFS._data.update(old_rd)
    world.rooms._data.clear(); world.rooms._data.update(old_wr)
    world.chars.clear(); world.chars.update(old_ch)
    MOB_DEFS._data.clear(); MOB_DEFS._data.update(old_md)


def test_do_tell_delivers_verbatim_tail(two_chars):
    player, mob, out = two_chars
    comm.do_tell(player, "guard Hello {Cthere")
    # target head resolved; message tail kept verbatim (case + colour)
    assert any("Hello {Cthere" in l for l in out)
    # do_tell sets the victim's reply pointer to the speaker's id
    assert mob["reply"] == 1


def test_do_reply_delivers_verbatim_tail(two_chars):
    player, mob, out = two_chars
    player["reply"] = 2  # last told by the mob
    comm.do_reply(player, "Right {Rback")
    assert any("Right {Rback" in l for l in out)
