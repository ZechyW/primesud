"""Tests for do_slist (cf. 1stMud do_slist in skills.c)."""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import groups
from classes import CLASS_MAGE
from player import create_char


def test_slist_class_skill_and_syntax(monkeypatch):
    player = create_char(CLASS_MAGE)
    paged = []
    out = []
    monkeypatch.setattr(groups, "tpage", lambda lines: paged.extend(lines))
    monkeypatch.setattr(groups, "chprintln", lambda player, line: out.append(line))

    groups.do_slist(player, ["war"])
    assert any("Level" in line for line in paged)
    assert any("sword" in line for line in paged)
    assert all("charm person" not in line for line in paged)

    groups.do_slist(player, ["magic", "miss"])
    assert any("Magic missile:" in line and "Mag: 001" in line for line in out)
    assert any("War: 002" in line and "Ran: 002" in line for line in out)
    assert all(len(re.sub(r"{.", "", line)) <= 64 for line in out)

    groups.do_slist(player, [])
    assert any("Syntax: slist <skill>" in line for line in out)
