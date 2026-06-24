"""PrimeSUD colour-aware terminal print/status wrappers."""

from tml_prime import tml_prime as tml
from config import (
    TERMINAL_COLS, FONT_GROB, COLOR_GROB,
    DARK_MODE, BG_COLOR, TAB_SIZE, FONT,
    SCROLLBACK_SIZE, SCROLL_STEP, SWIPE_THRESHOLD, TOUCH_SCROLL_STEP,
)
from colors import COLOR_CODE, ANSI_COLORS, _RESET_CODES, color_wrap_full
from hpprime import dimgrob, getpix, grobh, grobw, pixon, strblit2


def tprint(*args, **kwargs):
    """Module-level print -- delegates to tr.print (colour-aware)."""
    tr.print(*args, **kwargs)


def _wrap_plain(text, width):
    """Plain-text word-wrap with no colour-code scanning."""
    lines = []
    while len(text) > width:
        i = text.rfind(' ', 0, width)
        if i <= 0:
            i = width - 1
        lines.append(text[:i])
        text = text[i:].lstrip(' ')
    lines.append(text)
    return lines


def install_color_print(tr):
    """Install PrimeSUD colour-code aware print wrappers on a tml instance."""
    font_w = grobw(FONT_GROB)
    font_h = grobh(FONT_GROB)
    dimgrob(COLOR_GROB, font_w, font_h, 0)
    strblit2(COLOR_GROB, 0, 0, font_w, font_h, FONT_GROB, 0, 0, font_w, font_h)
    _w_x = (ord('W') - 32) * tr.char_width + tr.char_width // 2
    font_fg = getpix(FONT_GROB, _w_x, tr.char_height // 2)
    fg_rows = [
        [x for x in range(font_w) if getpix(FONT_GROB, x, y) == font_fg]
        for y in range(font_h)
    ]
    current_fg = [None]

    def set_color(color):
        if color == current_fg[0]:
            return
        current_fg[0] = color
        _po = pixon
        for y, xs in enumerate(fg_rows):
            for x in xs:
                _po(FONT_GROB, x, y, color)

    def reset_color():
        if current_fg[0] is None:
            return
        current_fg[0] = None
        strblit2(FONT_GROB, 0, 0, font_w, font_h, COLOR_GROB, 0, 0, font_w, font_h)

    orig_print = tr.print
    cols = TERMINAL_COLS
    # Closure-captured for faster lookup than globals in the hot print path.
    _CC = COLOR_CODE
    _ANSI = ANSI_COLORS
    _RST = _RESET_CODES
    _pxy = tr.print_xy
    _pch = tr._put_char

    def wrapped_print(*args, sep=' ', end='\n'):
        text = sep.join(str(a) for a in args)
        if _CC not in text:
            # Fast path: skip color_wrap and all colour-code scanning.
            if current_fg[0] is not None:
                reset_color()
            lines = _wrap_plain(text, cols)
            n = len(lines)
            for idx, line in enumerate(lines):
                orig_print(line, end='')
                auto_wrapped = line and tr.cursor_x == 0
                if not auto_wrapped:
                    orig_print('', end=end if idx == n - 1 else '\n')
            return
        # Colour-first rendering: split+group in one pass, then render one
        # set_color/reset_color per distinct colour.
        if len(text) - 2 * text.count(_CC) <= cols and '{{' not in text:
            pieces = (text,)
        else:
            pieces = color_wrap_full(text, cols)
        n = len(pieces)
        for idx, piece in enumerate(pieces):
            x = 0
            current = None
            colour_order = []
            groups = {}
            parts = piece.split(_CC)
            seg = parts[0]
            if seg:
                colour_order.append(None)
                groups[None] = [(0, seg)]
                x = len(seg)
            skip = False
            for part in parts[1:]:
                if not part:
                    # '{{' escape: literal '{'.
                    if current not in groups:
                        colour_order.append(current)
                        groups[current] = []
                    groups[current].append((x, _CC))
                    x += 1
                    skip = True
                    continue
                if skip:
                    skip = False
                    seg = part
                else:
                    code = part[0]
                    seg = part[1:]
                    if code in _ANSI:
                        current = _ANSI[code]
                    elif code in _RST:
                        current = None
                    else:
                        seg = _CC + part
                if seg:
                    if current not in groups:
                        colour_order.append(current)
                        groups[current] = []
                    groups[current].append((x, seg))
                    x += len(seg)
            row = tr.cursor_y
            for colour in colour_order:
                if colour is None:
                    reset_color()
                else:
                    set_color(colour)
                for x_pos, seg in groups[colour]:
                    _pxy(x_pos, row, seg)
            is_last = idx == n - 1
            if not is_last:
                _pch('\n')
            elif end:
                for c in end:
                    _pch(c)

    tr.print = wrapped_print
    orig_set_status = tr.set_status

    def wrapped_set_status(text):
        if current_fg[0] is not None:
            reset_color()
        orig_set_status(text)

    tr.set_status = wrapped_set_status


tr = tml(
    dark_mode=DARK_MODE, tab_size=TAB_SIZE, bg_color=BG_COLOR, font=FONT,
    scrollback_size=SCROLLBACK_SIZE, scroll_step=SCROLL_STEP,
    touch_scroll_step=TOUCH_SCROLL_STEP, swipe_threshold=SWIPE_THRESHOLD,
)
install_color_print(tr)
