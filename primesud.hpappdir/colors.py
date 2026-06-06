COLOR_CODE = '{'

# {X color codes → RGB.  Lowercase = dim, uppercase = bright (1stMud convention).
# White is the default foreground; {g is a readable green, not the default.
ANSI_COLORS = {
    'd': 0x555555,   # dark  (grey — pure black invisible on dark bg)
    'r': 0xCC3333,
    'g': 0x55AA55,
    'y': 0xAAAA00,
    'b': 0x3366CC,   # bumped vs. pure ANSI blue for legibility
    'm': 0xAA33AA,
    'c': 0x33AAAA,
    'w': 0xCCCCCC,
    'D': 0x888888,
    'R': 0xFF5555,
    'G': 0x55FF55,
    'Y': 0xFFFF55,
    'B': 0x5577FF,
    'M': 0xFF55FF,
    'C': 0x55FFFF,
    'W': 0xFFFFFF,
}

_RESET_CODES = ('x', 'X')


def strip_colors(text):
    """Return text with all {X color codes removed."""
    out = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] == COLOR_CODE and i + 1 < n:
            i += 2
        else:
            out.append(text[i])
            i += 1
    return ''.join(out)


def _wrap_raw_index(text, cols):
    """Raw string index to split at for a `cols`-wide visible line.

    Returns None if the text fits entirely.  Prefers splitting at a space;
    falls back to a hard break at the visible column limit.
    """
    vis = 0
    last_sp_raw = -1
    i = 0
    n = len(text)
    while i < n:
        if text[i] == COLOR_CODE and i + 1 < n:
            i += 2
            continue
        if vis == cols:
            break
        if text[i] == ' ':
            last_sp_raw = i
        vis += 1
        i += 1
    if i >= n:
        return None
    return last_sp_raw if last_sp_raw > 0 else i


def color_wrap(text, cols):
    """Split `text` into lines of at most `cols` visible characters.

    Color codes are preserved in the correct segment; they contribute no width.
    """
    lines = []
    while True:
        raw_i = _wrap_raw_index(text, cols)
        if raw_i is None:
            break
        lines.append(text[:raw_i])
        rest = text[raw_i:]
        j = 0
        while j < len(rest) and rest[j] == ' ':
            j += 1
        text = rest[j:]
    lines.append(text)
    return lines


def colored_print(text, tr_print, set_color, reset_color):
    """Parse {X codes and call set_color/reset_color around each coloured segment.

    {{  is an escaped literal {.
    {x / {X  reset to default colour.
    Unknown codes are silently skipped.
    Always leaves the font in the default (reset) state on return.
    """
    i = 0
    n = len(text)
    buf = []
    colored = False
    while i < n:
        if text[i] == COLOR_CODE and i + 1 < n:
            code = text[i + 1]
            if buf:
                tr_print(''.join(buf), end='')
                buf = []
            if code in ANSI_COLORS:
                set_color(ANSI_COLORS[code])
                colored = True
            elif code in _RESET_CODES:
                reset_color()
                colored = False
            elif code == COLOR_CODE:
                buf.append(COLOR_CODE)
            i += 2
        else:
            buf.append(text[i])
            i += 1
    if buf:
        tr_print(''.join(buf), end='')
    if colored:
        reset_color()
