"""Contextual picker UI for selecting mobs, items, and options."""

from hpprime import eval as ppleval

_MAX_OPTS = 10


def _cancel(tr):
    tr.print("Cancelled.")
    return -1


def _read_key(tr):
    while True:
        result = tr.poll_char()
        if result is not None:
            char, _auto_submit = result
            # In picker we are already inside a blocking command; game_loop
            # accounts for elapsed time around interpret(), so don't also carry
            # scrollback time back to the main poll loop.
            if tr._scrollback_ms:
                tr._scrollback_ms = 0
            return char
        ppleval("WAIT(1/1e3)")


def _force_numeric_keys(tr):
    tr.resync_keyboard()
    tr.alpha_lock = False
    tr.shift_lock = False
    tr.is_alpha = False
    tr.is_shift = False
    tr.alpha_hold = False
    tr.shift_hold = False
    tr.symb_hold = False
    tr._refresh_indicators()


def _render(tr, title, options, page, max_page):
    shown = options[page * _MAX_OPTS : page * _MAX_OPTS + _MAX_OPTS]
    tr.print("{Y" + title + "{x")
    for i, opt in enumerate(shown):
        label = str(i + 1) if i < 9 else "0"
        suffix = " {C(default){x" if i == 0 else ""
        tr.print("  {y" + label + "){x " + opt + suffix)
    if max_page > 0:
        tr.print(
            "{wPage " + str(page + 1) + "/" + str(max_page + 1) + " [+] next  [-] prev  [Esc] cancel{x"
        )
    else:
        tr.print("{w[Esc] cancel{x")


def pick_from(tr, title, options):
    """Display a numbered list and read digit+Enter to select, or Esc to cancel.

    Prints title, then up to 10 options labelled 1-9 then 0 per page.
    Uses tr.read_key() directly: Esc and +/- act on single keypress;
    digit selection requires Enter to confirm. Bare Enter selects item 1.

    Args:
        tr: tml renderer instance.
        title (str): Header line, plain text -- colour wrapping applied internally.
        options (list[str]): Display strings.

    Returns:
        int: 0-based index of the selected option, or -1 if cancelled.
    """
    if not options:
        return -1

    _force_numeric_keys(tr)
    max_page = (len(options) - 1) // _MAX_OPTS
    page = 0
    _render(tr, title, options, page, max_page)

    while True:
        tr.print("> ", end="")
        while True:  # FIRST_KEY: loop until action taken
            char = _read_key(tr)
            if char == "\e":
                return _cancel(tr)
            elif char == "\n":
                tr.print("")
                return page * _MAX_OPTS
            elif char == "+":
                if page < max_page:
                    page += 1
                    tr.print("")
                    _render(tr, title, options, page, max_page)
                    break
            elif char == "-":
                if page > 0:
                    page -= 1
                    tr.print("")
                    _render(tr, title, options, page, max_page)
                    break
            elif char is None:
                pass
            elif char.isdigit():
                page_idx = (int(char) - 1) % 10  # '1'->0 ... '9'->8, '0'->9
                tr.print(char, end="")
                while True:  # CONFIRM
                    char2 = _read_key(tr)
                    if char2 == "\n":
                        absolute_idx = page * _MAX_OPTS + page_idx
                        if absolute_idx < len(options):
                            tr.print("")
                            return absolute_idx
                        n_shown = min(_MAX_OPTS, len(options) - page * _MAX_OPTS)
                        if n_shown == _MAX_OPTS:
                            rang = "1-9,0"
                        elif n_shown == 1:
                            rang = "1"
                        else:
                            rang = "1-" + str(n_shown)
                        tr.print("")
                        tr.print("{wEnter " + rang + " (or Esc to cancel).{x")
                        break
                    elif char2 == "\b":
                        tr.print("")
                        break
                    elif char2 == "\e":
                        return _cancel(tr)
                break
