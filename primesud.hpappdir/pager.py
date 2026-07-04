"""General-purpose output pager (cf. 1stMud sendpage/show_string in comm.c). [PRIMESUD]"""

import terminal
from hpprime import eval as ppleval

_ESC = "\\e"  # tml key_map escape char (literal backslash-e, not \x1b)


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
    page prints it again.  Blocked time is added to tr._scrollback_ms
    so the game loop shifts its pulse clock, as scrollback does; time
    spent in a nested scrollback (shift+- while paging) is already
    inside our span, so its own contribution is discarded.

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
    old_status = tr.status_text
    t0 = int(ppleval("Ticks"))
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
                tr.set_status("-- page " + str(page + 1) + "/" + str(total)
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
        tr._scrollback_ms = sb0 + (int(ppleval("Ticks")) - t0)
        tr.set_status(old_status)
        tr.resync_keyboard()
