"""Contextual picker UI for selecting mobs, items, and options."""

from hpprime import eval as ppleval
import terminal
from terminal import tprint

_MAX_OPTS = 10


def _cancel():
    """Print cancellation message and return sentinel. [PRIMESUD]"""
    tprint("Cancelled.")
    return -1


def _read_key():
    """Block until a keypress is available and return the character. [PRIMESUD]"""
    tr = terminal.tr
    while True:
        result = tr.poll_char()
        if result is not None:
            char, _auto_submit = result
            if tr._scrollback_ms:
                tr._scrollback_ms = 0
            return char
        ppleval("WAIT(1/1e3)")


def _force_numeric_keys():
    """Reset keyboard state to unshifted numeric entry mode. [PRIMESUD]"""
    tr = terminal.tr
    tr.resync_keyboard()
    tr.alpha_lock = False
    tr.shift_lock = False
    tr.is_alpha = False
    tr.is_shift = False
    tr.alpha_hold = False
    tr.shift_hold = False
    tr.symb_hold = False
    tr._refresh_indicators()


def _render(title, options, page, max_page):
    """Display one page of numbered picker options with navigation hints. [PRIMESUD]"""
    shown = options[page * _MAX_OPTS : page * _MAX_OPTS + _MAX_OPTS]
    tprint("{Y" + title + "{x")
    for i, opt in enumerate(shown):
        label = str(i + 1) if i < 9 else "0"
        suffix = " {C(default){x" if i == 0 else ""
        tprint("  {y" + label + "){x " + opt + suffix)
    if max_page > 0:
        tprint(
            "{wPage " + str(page + 1) + "/" + str(max_page + 1) + " [+] next  [-] prev  [Esc] cancel{x"
        )
    else:
        tprint("{w[Esc] cancel{x")


def pick_from(title, options, start_page=0):
    """Display a numbered list and read digit+Enter to select, or Esc to cancel.

    Prints title, then up to 10 options labelled 1-9 then 0 per page.
    Uses tr.poll_char() directly: Esc and +/- act on single keypress;
    digit selection requires Enter to confirm. Bare Enter selects the first
    option on the current page.

    Args:
        title (str): Header line, plain text -- colour wrapping applied internally.
        options (list[str]): Display strings.
        start_page (int): 0-based page to open on, so a caller that reopens
            the picker in a loop can resume where the player left off
            (`selected_index // 10`). Out of range falls back to page 0.

    Returns:
        int: 0-based index of the selected option, or -1 if cancelled.
    """
    if not options:
        return -1

    _force_numeric_keys()
    max_page = (len(options) - 1) // _MAX_OPTS
    page = start_page if 0 <= start_page <= max_page else 0
    _render(title, options, page, max_page)

    while True:
        tprint("> ", end="")
        while True:  # FIRST_KEY: loop until action taken
            char = _read_key()
            if char == "\\e":
                return _cancel()
            elif char == "\n":
                tprint("")
                return page * _MAX_OPTS
            elif char == "+":
                if page < max_page:
                    page += 1
                    tprint("")
                    _render(title, options, page, max_page)
                    break
            elif char == "-":
                if page > 0:
                    page -= 1
                    tprint("")
                    _render(title, options, page, max_page)
                    break
            elif char is None:
                pass
            elif isinstance(char, str) and char.isdigit():
                page_idx = (int(char) - 1) % 10  # '1'->0 ... '9'->8, '0'->9
                tprint(char, end="")
                while True:  # CONFIRM
                    char2 = _read_key()
                    if char2 == "\n":
                        absolute_idx = page * _MAX_OPTS + page_idx
                        if absolute_idx < len(options):
                            tprint("")
                            return absolute_idx
                        n_shown = min(_MAX_OPTS, len(options) - page * _MAX_OPTS)
                        if n_shown == _MAX_OPTS:
                            rang = "1-9,0"
                        elif n_shown == 1:
                            rang = "1"
                        else:
                            rang = "1-" + str(n_shown)
                        tprint("")
                        tprint("{wEnter " + rang + " (or Esc to cancel).{x")
                        break
                    elif char2 == "\b":
                        tprint("")
                        break
                    elif char2 == "\\e":
                        return _cancel()
                break
