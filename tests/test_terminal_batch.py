"""Multiline colour rendering tests (offscreen batch compose)."""

import importlib.util
import os


_ROOT = os.path.dirname(os.path.dirname(__file__))
_PATH = os.path.join(_ROOT, "src", "terminal.py")
_SPEC = importlib.util.spec_from_file_location("src_terminal_batch", _PATH)
terminal = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(terminal)
# Streaming reveal off regardless of config: these tests assert the
# single-blit compose shape (individual tests re-enable via monkeypatch).
terminal.REVEAL_MS_PER_LINE = 0
terminal.REVEAL_MS_PER_CHAR = 0

_SCRATCH = terminal.SCRATCH_GROB
_FONT = terminal.FONT_GROB
_HIST = 7


class _Terminal:
    def __init__(self, rows=4, cursor_y=0):
        self.rows = rows
        self.columns = 64
        self.width = 64
        self.char_width = 1
        self.char_height = 1
        self.back_color = 0xFFFFFF
        self.grob = _FONT
        self.char_map = {chr(i): i - 32 for i in range(32, 127)}
        self.cursor_x = 0
        self.cursor_y = cursor_y
        self.drawn = []
        self.scrolled = 0
        self._hist_grob = _HIST
        self._hist_size = 8
        self._hist_write = 0
        self._hist_count = 0

    def print(self, *args, sep=" ", end="\n"):
        text = sep.join(str(arg) for arg in args) + end
        for char in text:
            self._put_char(char)

    def print_xy(self, x, y, text):
        self.drawn.append((x, y, text))

    def set_status(self, text):
        self.status_text = text

    def _put_char(self, char):
        if char == "\n":
            self.cursor_x = 0
            self.cursor_y += 1
        else:
            self.drawn.append((self.cursor_x, self.cursor_y, char))
            self.cursor_x += 1

    def _scroll_up(self):
        self.scrolled += 1
        self.cursor_y -= 1

    def _pump_keyboard(self, key_commands=None):
        pass

    def has_queued_keys(self):
        return False


def _installed(monkeypatch, rows=4, cursor_y=0):
    palettes = []
    blits = []
    dims = []
    monkeypatch.setattr(terminal, "grobw", lambda grob: 1)
    monkeypatch.setattr(terminal, "grobh", lambda grob: 1)
    monkeypatch.setattr(terminal, "getpix", lambda grob, x, y: 1)
    monkeypatch.setattr(terminal, "pixon",
                        lambda grob, x, y, colour: palettes.append(colour))
    monkeypatch.setattr(terminal, "dimgrob",
                        lambda *args: dims.append(args))
    monkeypatch.setattr(terminal, "strblit2",
                        lambda *args: blits.append(args))
    fills = []
    monkeypatch.setattr(terminal, "fillrect",
                        lambda *args: fills.append(args))
    tr = _Terminal(rows, cursor_y)
    tr.fills = fills
    terminal.install_color_print(tr)
    # Drop install-time font-copy dimgrob/strblit2 noise.
    blits.clear()
    dims.clear()
    return tr, palettes, blits, dims


def _chars(blits):
    """Decode compose blits to absolute (x, y, char) draws.

    Uses the single scratch->screen blit for the row offset; mock char
    cell is 1x1 px so pixel coords equal char coords.
    """
    final = [b for b in blits if b[0] == 0 and b[5] == _SCRATCH]
    assert len(final) == 1, "expected exactly one scratch->screen blit"
    top = final[0][2]
    out = []
    for b in blits:
        if b[0] == _SCRATCH and b[5] == _FONT:
            out.append((b[1], b[2] + top, chr(b[6] + 32)))
    return out


def _expand(segs):
    out = []
    for x, y, seg in segs:
        for i, char in enumerate(seg):
            out.append((x + i, y, char))
    return out


def test_multiline_groups_same_palette_across_rows(monkeypatch):
    tr, palettes, blits, _ = _installed(monkeypatch)

    tr.print("{Rred{x\n{Ggreen{x\n{Ragain{x")

    assert palettes == [0xFF0000, 0x00FF00]
    assert _chars(blits) == _expand([(0, 0, "red"), (0, 2, "again"),
                                     (0, 1, "green")])
    assert tr.drawn == []
    assert (tr.cursor_x, tr.cursor_y) == (0, 3)


def test_multiline_scroll_folds_into_compose(monkeypatch):
    tr, _, blits, dims = _installed(monkeypatch, rows=4, cursor_y=3)

    tr.print("{Rone{x\n{Gtwo{x")

    # No on-screen scroll: the scrolled-off row is captured into the
    # history ring, surviving rows shift inside the full-area scratch.
    assert tr.scrolled == 0
    assert (tr._hist_write, tr._hist_count) == (1, 1)
    assert [b for b in blits if b[0] == _HIST] == [
        (_HIST, 0, 0, 64, 1, 0, 0, 0, 64, 1)]
    assert [b for b in blits if b[0] == _SCRATCH and b[5] == 0] == [
        (_SCRATCH, 0, 0, 64, 2, 0, 0, 1, 64, 2)]
    assert dims == [(_SCRATCH, 64, 4, 0xFFFFFF)]
    assert _chars(blits) == _expand([(0, 2, "one"), (0, 3, "two")])
    assert (tr.cursor_x, tr.cursor_y) == (0, 4)


def test_pending_blank_line_never_reads_past_text_area(monkeypatch):
    # Full screen + blank echo line leaves cursor_y = rows + 1; the fold
    # must not source G0 rows >= rows (separator/status band).
    tr, _, blits, _ = _installed(monkeypatch, rows=4, cursor_y=5)

    tr.print("{Rone{x\n{Gtwo{x")

    for b in blits:
        if b[5] == 0:  # any blit reading from G0
            assert b[7] + b[9] <= 4, "read past text area: %r" % (b,)
    # Shift-copy clamped to the one surviving G0 row; the pending blank
    # row stays scratch background.
    assert [b for b in blits if b[0] == _SCRATCH and b[5] == 0] == [
        (_SCRATCH, 0, 0, 64, 1, 0, 0, 3, 64, 1)]
    assert (tr._hist_write, tr._hist_count) == (3, 3)
    assert _chars(blits) == _expand([(0, 2, "one"), (0, 3, "two")])
    assert (tr.cursor_x, tr.cursor_y) == (0, 4)


def test_scrolloff_past_screen_fills_hist_blank(monkeypatch):
    # n > rows: the scrolled-off blank line has no G0 row to capture;
    # its history slot is background-filled instead.
    tr, _, blits, _ = _installed(monkeypatch, rows=2, cursor_y=3)

    tr.print("{Rone{x\n{Gtwo{x")

    for b in blits:
        if b[5] == 0:
            assert b[7] + b[9] <= 2, "read past text area: %r" % (b,)
    assert [b for b in blits if b[0] == _HIST] == [
        (_HIST, 0, 0, 64, 1, 0, 0, 0, 64, 1),
        (_HIST, 0, 1, 64, 1, 0, 0, 1, 64, 1)]
    assert tr.fills == [(_HIST, 0, 2, 64, 1, 0xFFFFFF, 0xFFFFFF)]
    assert (tr._hist_write, tr._hist_count) == (3, 3)
    assert _chars(blits) == _expand([(0, 0, "one"), (0, 1, "two")])
    assert (tr.cursor_x, tr.cursor_y) == (0, 2)


def test_paced_reveal_scrolls_one_row_at_a_time(monkeypatch):
    tr, _, blits, _ = _installed(monkeypatch, rows=4, cursor_y=3)
    monkeypatch.setattr(terminal, "REVEAL_MS_PER_LINE", 1)

    tr.print("{Rone{x\n{Gtwo{x")

    # No whole-batch jump: every scratch->screen blit is a single row,
    # landing at the live bottom row.
    assert [b for b in blits if b[0] == 0 and b[5] == _SCRATCH] == [
        (0, 0, 3, 64, 1, _SCRATCH, 0, 2, 64, 1),
        (0, 0, 3, 64, 1, _SCRATCH, 0, 3, 64, 1)]
    # The screen itself scrolls one row between them (G0 self-blit +
    # vacated-row fill), tml._scroll_up shape.
    assert [b for b in blits if b[0] == 0 and b[5] == 0] == [
        (0, 0, 0, 64, 3, 0, 0, 1, 64, 3)]
    assert tr.fills == [(0, 0, 3, 64, 1, 0xFFFFFF, 0xFFFFFF)]
    # History still captured once, from the pristine pre-reveal screen.
    assert [b for b in blits if b[0] == _HIST] == [
        (_HIST, 0, 0, 64, 1, 0, 0, 0, 64, 1)]
    assert (tr.cursor_x, tr.cursor_y) == (0, 4)


def test_char_streaming_blits_cells_left_to_right(monkeypatch):
    tr, _, blits, _ = _installed(monkeypatch)
    monkeypatch.setattr(terminal, "REVEAL_MS_PER_CHAR", 1)

    tr.print("{Rone{x")

    # One cell blit per visible char, then a remainder blit squaring
    # the rest of the row with the scratch background.
    assert [b for b in blits if b[0] == 0 and b[5] == _SCRATCH] == [
        (0, 0, 0, 1, 1, _SCRATCH, 0, 0, 1, 1),
        (0, 1, 0, 1, 1, _SCRATCH, 1, 0, 1, 1),
        (0, 2, 0, 1, 1, _SCRATCH, 2, 0, 1, 1),
        (0, 3, 0, 61, 1, _SCRATCH, 3, 0, 61, 1)]
    assert (tr.cursor_x, tr.cursor_y) == (0, 1)


def test_list_arg_batches_without_join(monkeypatch):
    tr, palettes, blits, _ = _installed(monkeypatch)

    tr.print(["{Rred{x", "plain"])

    assert palettes == [0xFF0000]
    assert _chars(blits) == _expand([(0, 0, "red"), (0, 1, "plain")])
    assert (tr.cursor_x, tr.cursor_y) == (0, 2)


def test_offscreen_single_blit_covers_batch(monkeypatch):
    tr, _, blits, dims = _installed(monkeypatch)

    tr.print("{Ra{x\n{Gb{x\n{Rc{x")

    # Scratch sized to the batch and background-filled, one screen blit.
    assert dims == [(_SCRATCH, 64, 3, 0xFFFFFF)]
    screen = [b for b in blits if b[0] == 0]
    assert screen == [(0, 0, 0, 64, 3, _SCRATCH, 0, 0, 64, 3)]


def test_blank_line_advances_row(monkeypatch):
    tr, _, blits, _ = _installed(monkeypatch)

    tr.print("a\n\nb")

    assert _chars(blits) == _expand([(0, 0, "a"), (0, 2, "b")])
    assert (tr.cursor_x, tr.cursor_y) == (0, 3)


def test_brace_escape_renders_literal(monkeypatch):
    tr, _, blits, _ = _installed(monkeypatch)

    tr.print("{{x\nplain")

    assert _chars(blits) == _expand([(0, 0, "{x"), (0, 1, "plain")])
    assert (tr.cursor_x, tr.cursor_y) == (0, 2)


def test_oversized_batch_prefix_scrolls_normally(monkeypatch):
    tr, palettes, blits, _ = _installed(monkeypatch, rows=2)

    tr.print("{Ra{x\n{Rb{x\n{Rc{x\n{Rd{x")

    # First two lines rendered normally, last screenful composed with
    # the full-screen scroll folded in (both rows captured to history).
    assert palettes == [0xFF0000]
    assert tr.scrolled == 0
    assert tr.drawn == [(0, 0, "a"), (0, 1, "b")]
    assert (tr._hist_write, tr._hist_count) == (2, 2)
    assert _chars(blits) == _expand([(0, 0, "c"), (0, 1, "d")])
    assert (tr.cursor_x, tr.cursor_y) == (0, 2)


def test_plain_line_draws_as_one_run(monkeypatch):
    tr, _, blits, _ = _installed(monkeypatch)

    tr.print("hello", end="")
    tr.print(" world")

    # Plain fast path: whole runs via print_xy, no per-char draws and
    # no batch compose.
    assert tr.drawn == [(0, 0, "hello"), (5, 0, " world")]
    assert [b for b in blits if b[0] in (0, _SCRATCH)] == []
    assert (tr.cursor_x, tr.cursor_y) == (0, 1)


def test_plain_run_wraps_mid_line(monkeypatch):
    tr, _, _, _ = _installed(monkeypatch)

    tr.print("x" * 60, end="")
    tr.print("y" * 10, end="")

    # Continuation exceeding the 64-col row wraps like _put_char would.
    assert tr.drawn == [(0, 0, "x" * 60), (60, 0, "yyyy"), (0, 1, "yyyyyy")]
    assert (tr.cursor_x, tr.cursor_y) == (6, 1)


def test_empty_list_is_noop(monkeypatch):
    tr, palettes, blits, dims = _installed(monkeypatch)

    tr.print([])

    assert palettes == [] and dims == []
    assert [b for b in blits if b[0] in (0, _SCRATCH)] == []
    assert (tr.cursor_x, tr.cursor_y) == (0, 0)
