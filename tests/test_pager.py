"""Tests for the tpage pager and the enhanced do_commands listing."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "primesud.hpappdir")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import commands
import terminal
from pager import tpage, _ESC


class FakeTr:
    """Minimal tr stand-in: captures prints, replays scripted keys."""

    def __init__(self, rows=22, keys=()):
        self.rows = rows
        self.status_text = "old status"
        self._scrollback_ms = 0
        self.lines = []
        self.statuses = []
        self.keys = list(keys)
        self.resynced = 0

    def print(self, s="", end="\n"):
        self.lines.append(s)

    def set_status(self, text):
        self.status_text = text
        self.statuses.append(text)

    def read_key(self, code=False):
        return self.keys.pop(0)

    def resync_keyboard(self):
        self.resynced += 1


@pytest.fixture
def fake_tr(monkeypatch):
    def make(rows=22, keys=()):
        tr = FakeTr(rows=rows, keys=keys)
        monkeypatch.setattr(terminal, "tr", tr)
        return tr
    return make


# -- tpage -----------------------------------------------------------------

def test_single_page_prints_all_no_keys(fake_tr):
    tr = fake_tr(rows=22)
    tpage(["line %d" % i for i in range(10)])
    assert len(tr.lines) == 10
    assert tr.statuses == []  # never entered pager mode
    assert tr.resynced == 0


def test_multipage_enter_then_esc(fake_tr):
    tr = fake_tr(rows=6, keys=["\n", _ESC])  # 5 lines per page
    tpage(["L%d" % i for i in range(12)])  # 3 pages
    # page 1 (5) + page 2 (5) printed; esc exits before page 3
    assert tr.lines == ["L%d" % i for i in range(10)]
    assert any("page 1/3" in s for s in tr.statuses)
    assert any("page 2/3" in s for s in tr.statuses)
    assert tr.status_text == "old status"  # restored
    assert tr.resynced == 1


def test_plus_also_pages_forward(fake_tr):
    tr = fake_tr(rows=6, keys=["+", _ESC])
    tpage(["L%d" % i for i in range(12)])
    assert len(tr.lines) == 10


def test_back_reprints_previous_page(fake_tr):
    tr = fake_tr(rows=6, keys=["\n", "-", _ESC])
    tpage(["L%d" % i for i in range(12)])
    # page 1, page 2, page 1 again (streamed duplicate by design)
    assert tr.lines == (["L%d" % i for i in range(5)]
                        + ["L%d" % i for i in range(5, 10)]
                        + ["L%d" % i for i in range(5)])


def test_enter_on_last_page_exits(fake_tr):
    tr = fake_tr(rows=6, keys=["\n", "\n", "\n"])
    tpage(["L%d" % i for i in range(12)])
    # 3 pages shown, third enter exits; keys fully consumed
    assert len(tr.lines) == 12
    assert tr.keys == []


def test_minus_on_first_page_stays(fake_tr):
    tr = fake_tr(rows=6, keys=["-", _ESC])
    tpage(["L%d" % i for i in range(12)])
    assert tr.lines == ["L%d" % i for i in range(5)]  # no reprint


def test_unmapped_keys_ignored(fake_tr):
    # fat-finger guard: letters/digits neither page nor exit
    tr = fake_tr(rows=6, keys=["q", "x", "5", _ESC])
    tpage(["L%d" % i for i in range(12)])
    assert tr.lines == ["L%d" % i for i in range(5)]
    assert tr.keys == []


# -- do_commands -----------------------------------------------------------

@pytest.fixture
def paged(monkeypatch):
    captured = []
    monkeypatch.setattr(commands, "tpage", lambda lines: captured.extend(lines))
    return captured


def test_commands_have_descriptions(paged, monkeypatch):
    monkeypatch.setattr(commands, "CMD_DESC_FILE",
                        os.path.join(ROOT, _SRC, "commands.dat"))
    commands.do_commands({}, [])
    assert len(paged) == len(commands._CMD_TABLE)
    # every ported command must have a description line in commands.dat
    missing = [l for l in paged if l.rstrip().endswith("{x")]
    assert missing == [], "commands.dat missing descriptions: %s" % missing


def test_commands_missing_dat_falls_back_to_names(paged, monkeypatch):
    monkeypatch.setattr(commands, "CMD_DESC_FILE", "no_such_file.dat")
    commands.do_commands({}, [])
    assert len(paged) == len(commands._CMD_TABLE)
    assert any("north" in l for l in paged)
