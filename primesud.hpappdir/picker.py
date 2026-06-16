_MAX_OPTS = 9


def pick_from(tr, title, options):
    """Display a numbered list and read a digit + Enter to select.

    Prints title, then up to 9 options numbered 1-9, then a cancel hint.
    Calls tr.input() to read the response; re-prompts on invalid input.
    Blocks until a valid selection or cancel — no game pulses fire during
    this time (all pulse processing runs in the main loop after interpret()
    returns, not inside command handlers).

    Args:
        tr: tml renderer (tr.print is the colour-aware wrapped version).
        title (str): Header line, colour codes supported.
        options (list[str]): Display strings. At most 9 are shown.

    Returns:
        int: 0-based index of the selected option, or -1 if cancelled.
    """
    shown = options[:_MAX_OPTS]
    tr.print("{Y" + title + "{x")
    for i, opt in enumerate(shown):
        suffix = " {C(default){x" if i == 0 else ""
        tr.print("  {y" + str(i + 1) + "){x " + opt + suffix)
    if len(options) > _MAX_OPTS:
        tr.print("  {w(" + str(len(options) - _MAX_OPTS) + " more not shown){x")
    tr.print("  {w0) cancel{x")

    while True:
        raw = tr.input(prompt=": ", alpha=False)
        raw = raw.strip()
        if not raw:
            return 0
        if raw[0] == '0':
            return -1
        if raw[0].isdigit():
            idx = int(raw[0]) - 1
            if 0 <= idx < len(shown):
                return idx
        rang = "1" if len(shown) == 1 else "1-" + str(len(shown))
        tr.print("{wEnter " + rang + " (or 0 to cancel).{x")
