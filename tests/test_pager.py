"""Tests for the tpage pager and the enhanced do_commands listing."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import commands
import terminal
from pager import tpage, hpan, clamp_pan, _ESC


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
    tr._scrollback_ms = 77
    tpage(["L%d" % i for i in range(12)])  # 3 pages
    # page 1 (5) + page 2 (5) printed; esc exits before page 3
    assert tr.lines == ["L%d" % i for i in range(10)]
    assert any("page 1/3" in s for s in tr.statuses)
    assert any("page 2/3" in s for s in tr.statuses)
    assert tr.status_text == "old status"  # restored
    assert tr.resynced == 1
    # interpret-span shift covers paging time; pager must not add on top
    assert tr._scrollback_ms == 77


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


# -- hpan (wide verbatim art) ----------------------------------------------

def test_clamp_pan_bounds():
    assert clamp_pan(-5, 16) == 0
    assert clamp_pan(0, 16) == 0
    assert clamp_pan(7, 16) == 7
    assert clamp_pan(99, 16) == 16
    # art narrower than the window: every offset collapses to 0
    assert clamp_pan(4, -3) == 0


def test_hpan_declines_without_an_in_place_terminal(fake_tr):
    # FakeTr (and the ANSI/headless shims) have no save grob, so the modal
    # never opens -- this is what keeps the suite from blocking on a key.
    fake_tr()
    assert hpan(["x" * 80, "y" * 80], 64) == 0


class PanTr(FakeTr):
    """FakeTr that can draw in place and replays scripted poll_char keys."""

    _save_grob = 6
    width = 320
    height = 220

    def __init__(self, keys=()):
        FakeTr.__init__(self, rows=4, keys=keys)
        self.cursor_x = 3
        self.cursor_y = 9
        self._in_scrollback = False
        self.windows = []

    def print_xy(self, x, y, text):
        if y == 0:
            self.windows.append([])
        self.windows[-1].append(text)

    def poll_char(self, key_commands=None):
        return (self.keys.pop(0), None) if self.keys else ("\n", None)


def test_hpan_declines_for_narrow_or_coloured_art(monkeypatch):
    monkeypatch.setattr(terminal, "tr", PanTr())
    assert hpan(["short", "also short"], 64) == 0
    assert hpan(["{Rwide" + "x" * 80, "y" * 80], 64) == 0
    assert hpan([], 64) == 0


def test_hpan_pans_clamps_and_restores(monkeypatch):
    art = [chr(65 + i) + "." * 14 for i in range(6)]  # 6 rows x 15 cols
    tr = PanTr(keys=["\\R", "\\R", "\\R", "\\D", "\\D", "z", "\n"])
    monkeypatch.setattr(terminal, "tr", tr)

    # width 10 -> max_col 5, step 5; rows 4 -> max_row 2, step 2
    assert hpan(art, 10) == 5  # third \\R clamps at the right edge
    # initial draw + one per accepted key ('z' ignored, Enter exits)
    assert len(tr.windows) == 6
    assert tr.windows[0] == ["A" + "." * 9, "B" + "." * 9, "C" + "." * 9, "D" + "." * 9]
    # final window: panned fully right, scrolled to the last rows, padded
    assert tr.windows[-1] == ["." * 10, "." * 10, "." * 10, "." * 10]
    assert tr.windows[-1] == [art[i][5:15] for i in range(2, 6)]
    # modal state fully unwound
    assert (tr.cursor_x, tr.cursor_y) == (3, 9)
    assert tr._in_scrollback is False
    assert tr.status_text == "old status"
    assert tr.resynced == 1
    assert "Esc done" in tr.statuses[0]


def test_hpan_short_art_pads_rows_and_omits_scroll_hint(monkeypatch):
    tr = PanTr(keys=[_ESC])
    monkeypatch.setattr(terminal, "tr", tr)
    assert hpan(["x" * 20, "y" * 20], 10) == 0  # Esc keeps the starting offset
    assert tr.windows[0] == ["x" * 10, "y" * 10, " " * 10, " " * 10]
    assert "scroll" not in tr.statuses[0]


# -- do_commands -----------------------------------------------------------

@pytest.fixture
def paged(monkeypatch):
    captured = []
    monkeypatch.setattr(commands, "tpage", lambda lines: captured.extend(lines))
    return captured


def test_commands_have_descriptions(paged, monkeypatch):
    monkeypatch.setattr(commands, "CMD_DESC_FILE",
                        os.path.join(ROOT, _SRC, "commands.txt"))
    commands.do_commands({}, [])
    assert len(paged) == len(commands._CMD_TABLE)
    # every ported command must have a description line in commands.txt
    missing = [l for l in paged if l.rstrip().endswith("{x")]
    assert missing == [], "commands.txt missing descriptions: %s" % missing


def test_commands_missing_dat_fails_loud(paged, monkeypatch):
    # commands.txt always shipped in a dist: missing file is a build error
    monkeypatch.setattr(commands, "CMD_DESC_FILE", "no_such_file.dat")
    with pytest.raises(OSError):
        commands.do_commands({}, [])
