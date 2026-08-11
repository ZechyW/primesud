"""General-purpose output pager (cf. 1stMud sendpage/show_string in comm.c). [PRIMESUD]"""

from hpprime import eval as ppleval, strblit2
import terminal
from util import num_str

_ESC = "\\e"  # tml key_map escape char (literal backslash-e, not \x1b)

# [PRIMESUD] Navpad claimed for the duration of the art pan only; the
# game-loop KEY_COMMANDS binding of Left/Right to w/e is untouched, since
# poll_char consults whichever map the caller hands it (cf. autoskill's
# _NAV_KEYS).  Sentinels match tml_prime.key_map's own \\L/\\R/\\U/\\D.
_PAN_KEYS = {2: ("\\U", None), 12: ("\\D", None),
             7: ("\\L", None), 8: ("\\R", None)}


def tpage(lines):
    """Show lines a page at a time. [PRIMESUD]

    Keys: Enter or '+' next page (on the last page: exit), '-' previous
    page, Esc exit; all other keys ignored.  1stMud show_string maps
    Enter/C=next, B=back, R=refresh, H/?=help, any other key exits;
    refresh/help are not ported, and ignoring unmapped keys instead of
    exiting is a [PRIMESUD] deviation -- fat-finger guard for the
    calculator keypad.

    Pages print through the normal print path, so they land in the
    scrollback history like ordinary streamed output -- revisiting a
    page prints it again.  Pulse timing: the game loop already shifts
    next_pulse by the whole interpret() span (primesud.py), which
    covers time blocked here, so tpage must NOT add to
    tr._scrollback_ms -- that would double-count.  Any nested
    scrollback entered while paging (shift+-) is inside the same span,
    so its accrual is discarded on exit, as picker.py does.

    Callers should keep each line within the terminal width; wrapped
    lines make a page taller than one screen.

    Args:
        lines (list): Pre-rendered output lines (colour codes allowed).
    """
    tr = terminal.tr
    page_rows = tr.rows - 1
    total = (len(lines) + page_rows - 1) // page_rows
    if total <= 1:
        for line in lines:
            tr.print(line)
        return
    # raw copy keeps colour codes; plain status_text is the stub fallback
    old_status = getattr(tr, "status_text_raw", tr.status_text)
    sb0 = tr._scrollback_ms
    page = 0
    shown = -1
    try:
        while True:
            if page != shown:
                start = page * page_rows
                for line in lines[start:start + page_rows]:
                    tr.print(line)
                shown = page
                tr.set_status("-- page " + num_str(page + 1) + "/" + num_str(total)
                              + "  [Enter] next  [-] back  [Esc] done --")
            key = tr.read_key()
            if key == "\n" or key == "+":
                if page + 1 >= total:
                    break
                page += 1
            elif key == "-":
                if page > 0:
                    page -= 1
            elif key == _ESC:
                break
            # other keys ignored
    finally:
        # Discard scrollback accrual from paging; interpret-span shift
        # in the game loop already compensates for our blocked time.
        tr._scrollback_ms = sb0
        tr.set_status(old_status)
        tr.resync_keyboard()


def clamp_pan(value, limit):
    """Clamp a pan offset into [0, limit] (limit itself floored at 0). [PRIMESUD]"""
    if limit < 0:
        limit = 0
    if value < 0:
        return 0
    return limit if value > limit else value


def _draw_window(tr, lines, col, top, width, rows):
    """Blit one width x rows window of the art straight onto the screen. [PRIMESUD]

    print_xy draws glyphs without touching the cursor, the scroll, or the
    history ring, so nothing the pan shows can leak into the scrollback
    record.  Short rows are space-padded rather than fillrect-cleared:
    the blank glyph is the same single strblit2 as any other cell.
    """
    blank = ' ' * width
    n = len(lines)
    for y in range(rows):
        i = top + y
        row = lines[i][col:col + width] if i < n else ''
        if len(row) < width:
            row = row + blank[len(row):]
        tr.print_xy(0, y, row)


def hpan(lines, width):
    """Pan oversized verbatim ASCII art in place; return the chosen column. [PRIMESUD]

    Art carrying ROM's leading-dot no-format marker (see _wrap_paragraphs
    in info.py) routinely runs 80 columns wide and 40 rows tall -- the
    stock Midgaard/Thera maps do -- which the 64x22 screen can only
    hard-wrap into mush.  Draw it directly onto the screen grob instead,
    outside the scrollback entirely, and let the navpad slide a window
    over it until Enter or Esc.  The screen is saved and restored around
    the modal, so the caller can then print the art sliced at the returned
    offset as the one scrollback record of what the player last saw.

    Returns 0 (caller prints unchanged) when the art already fits, when it
    carries colour codes -- slicing would cut a `{X` pair in half -- or
    when the terminal cannot draw in place.  That last case covers the
    ANSI/PC shim and the headless test harness, whose tr has no save grob,
    so no test can ever block here waiting on a keypress.

    Args:
        lines (list[str]): Verbatim art rows.
        width (int): Terminal column count.

    Returns:
        int: Final column offset; 0 if no modal ran.
    """
    tr = terminal.tr
    if tr is None or getattr(tr, "_save_grob", None) is None:
        return 0
    span = 0
    for ln in lines:
        if "{" in ln:
            return 0
        if len(ln) > span:
            span = len(ln)
    if span <= width:
        return 0

    rows = tr.rows
    max_col = span - width
    max_row = len(lines) - rows
    col = 0
    top = 0
    hint = "<- -> pan"
    if max_row > 0:
        hint = hint + "   ^ v scroll"
    hint = hint + "   Esc done"
    # raw copy keeps colour codes; plain status_text is the stub fallback
    old_status = getattr(tr, "status_text_raw", tr.status_text)
    sb0 = tr._scrollback_ms
    cx = tr.cursor_x
    cy = tr.cursor_y
    strblit2(tr._save_grob, 0, 0, tr.width, tr.height,
             0, 0, 0, tr.width, tr.height)
    # [PRIMESUD] Borrow the scrollback flag: it parks poll_char's touch and
    # shift+- entry points, both of which reuse _save_grob and would
    # overwrite the screen we have to put back.
    tr._in_scrollback = True
    try:
        tr.set_status(hint)
        dirty = True
        while True:
            if dirty:
                _draw_window(tr, lines, col, top, width, rows)
                dirty = False
            result = tr.poll_char(_PAN_KEYS)
            if result is None:
                ppleval("WAIT(1/1e3)")
                continue
            char = result[0]
            if char == "\n" or char == _ESC:
                break
            if char == "\\L":
                col = clamp_pan(col - width // 2, max_col)
            elif char == "\\R":
                col = clamp_pan(col + width // 2, max_col)
            elif char == "\\U":
                top = clamp_pan(top - rows // 2, max_row)
            elif char == "\\D":
                top = clamp_pan(top + rows // 2, max_row)
            else:
                continue  # fat-finger guard, as in tpage
            dirty = True
    finally:
        tr._in_scrollback = False
        strblit2(0, 0, 0, tr.width, tr.height,
                 tr._save_grob, 0, 0, tr.width, tr.height)
        tr.cursor_x = cx
        tr.cursor_y = cy
        # Discard scrollback accrual from panning; the interpret-span shift
        # in the game loop already compensates for our blocked time (tpage).
        tr._scrollback_ms = sb0
        tr.set_status(old_status)
        tr.resync_keyboard()
    return col
