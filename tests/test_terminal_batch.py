"""Multiline colour rendering tests."""

import importlib.util
import os


_ROOT = os.path.dirname(os.path.dirname(__file__))
_PATH = os.path.join(_ROOT, "src", "terminal.py")
_SPEC = importlib.util.spec_from_file_location("src_terminal_batch", _PATH)
terminal = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(terminal)


class _Terminal:
    def __init__(self, rows=4, cursor_y=0):
        self.rows = rows
        self.columns = 64
        self.char_width = 1
        self.char_height = 1
        self.cursor_x = 0
        self.cursor_y = cursor_y
        self.drawn = []
        self.scrolled = 0

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


def _installed(monkeypatch, rows=4, cursor_y=0):
    palettes = []
    monkeypatch.setattr(terminal, "grobw", lambda grob: 1)
    monkeypatch.setattr(terminal, "grobh", lambda grob: 1)
    monkeypatch.setattr(terminal, "getpix", lambda grob, x, y: 1)
    monkeypatch.setattr(terminal, "pixon",
                        lambda grob, x, y, colour: palettes.append(colour))
    tr = _Terminal(rows, cursor_y)
    terminal.install_color_print(tr)
    return tr, palettes


def test_multiline_groups_same_palette_across_rows(monkeypatch):
    tr, palettes = _installed(monkeypatch)

    tr.print("{Rred{x\n{Ggreen{x\n{Ragain{x")

    assert palettes == [0xFF0000, 0x00FF00]
    assert tr.drawn == [(0, 0, "red"), (0, 2, "again"),
                        (0, 1, "green")]
    assert (tr.cursor_x, tr.cursor_y) == (0, 3)


def test_multiline_prescrolls_before_absolute_draw(monkeypatch):
    tr, _ = _installed(monkeypatch, rows=4, cursor_y=3)

    tr.print("{Rone{x\n{Gtwo{x")

    assert tr.scrolled == 1
    assert tr.drawn == [(0, 2, "one"), (0, 3, "two")]
    assert (tr.cursor_x, tr.cursor_y) == (0, 4)


def test_list_arg_batches_without_join(monkeypatch):
    tr, palettes = _installed(monkeypatch)

    tr.print(["{Rred{x", "plain"])

    assert palettes == [0xFF0000]
    assert tr.drawn == [(0, 0, "red"), (0, 1, "plain")]
    assert (tr.cursor_x, tr.cursor_y) == (0, 2)


def test_blank_line_advances_row(monkeypatch):
    tr, _ = _installed(monkeypatch)

    tr.print("a\n\nb")

    assert tr.drawn == [(0, 0, "a"), (0, 2, "b")]
    assert (tr.cursor_x, tr.cursor_y) == (0, 3)


def test_brace_escape_renders_literal(monkeypatch):
    tr, _ = _installed(monkeypatch)

    tr.print("{{x\nplain")

    assert tr.drawn == [(0, 0, "{"), (1, 0, "x"), (0, 1, "plain")]
    assert (tr.cursor_x, tr.cursor_y) == (0, 2)


def test_oversized_batch_prefix_scrolls_normally(monkeypatch):
    tr, palettes = _installed(monkeypatch, rows=2)

    tr.print("{Ra{x\n{Rb{x\n{Rc{x\n{Rd{x")

    # First two lines rendered normally (scroll through history ring),
    # last screenful drawn batched after pre-scroll.
    assert palettes == [0xFF0000]
    assert tr.scrolled == 2
    assert tr.drawn == [(0, 0, "a"), (0, 1, "b"), (0, 0, "c"), (0, 1, "d")]
    assert (tr.cursor_x, tr.cursor_y) == (0, 2)
