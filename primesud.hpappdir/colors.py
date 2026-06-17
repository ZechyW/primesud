COLOR_CODE = '{'

# {X color codes -> RGB.  Lowercase = dim, uppercase = bright (1stMud convention).
# White is the default foreground
ANSI_COLORS = {
    'd': 0x000000,   # black
    'r': 0x800000,   # maroon
    'g': 0x008000,   # green,
    'y': 0x808000,   # olive
    'b': 0x4169E1,   # royalblue
    'm': 0x800080,   # purple
    'c': 0x008080,   # teal
    'w': 0xC0C0C0,   # silver
    'D': 0x808080,   # gray
    'R': 0xFF0000,   # red
    'G': 0x00FF00,   # lime
    'Y': 0xFFFF00,   # yellow
    'B': 0x6495ED,   # cornflowerblue
    'M': 0xFF00FF,   # magenta
    'C': 0x00FFFF,   # cyan
    'W': 0xFFFFFF,   # white
}

_RESET_CODES = ('x', 'X')


def strip_colors(text):
    """Return text with all {X color codes removed."""
    if COLOR_CODE not in text:
        return text
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


def color_len(text):
    """Return the visible (non-color-code) length of text."""
    return len(strip_colors(text))


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


def _colour_after(text, initial=None):
    """Return the active colour code letter after scanning text, given initial active colour."""
    active = initial
    i = 0
    n = len(text)
    while i < n:
        if text[i] == COLOR_CODE and i + 1 < n:
            code = text[i + 1]
            if code in ANSI_COLORS:
                active = code
            elif code in _RESET_CODES:
                active = None
            i += 2
        else:
            i += 1
    return active


def color_wrap_full(text, cols):
    """Like color_wrap, but each continuation piece is prefixed with the active colour.

    Ensures each piece is self-contained for colour-first rendering: if a colour is
    active at a split point, the next piece is prefixed with that colour code so the
    renderer can treat all pieces identically. Returns [text] when the line fits.
    """
    lines = []
    active = None
    while True:
        raw_i = _wrap_raw_index(text, cols)
        if raw_i is None:
            break
        piece = text[:raw_i]
        active = _colour_after(piece, active)
        lines.append(piece)
        rest = text[raw_i:]
        j = 0
        while j < len(rest) and rest[j] == ' ':
            j += 1
        text = rest[j:]
        if active is not None:
            text = COLOR_CODE + active + text
    lines.append(text)
    return lines


def color_parse_runs(piece):
    """Parse a self-contained colour-code piece into (colour, segment) runs.

    Returns [(colour_or_None, segment), ...] where colour_or_None is an ANSI int
    (from ANSI_COLORS) or None for default/reset. Handles {{ escapes.
    """
    runs = []
    current = None
    parts = []
    i = 0
    n = len(piece)
    _CC = COLOR_CODE
    while i < n:
        if piece[i] == _CC and i + 1 < n:
            code = piece[i + 1]
            if code == _CC:
                parts.append(_CC)
                i += 2
                continue
            if parts:
                runs.append((current, ''.join(parts)))
                parts = []
            if code in ANSI_COLORS:
                current = ANSI_COLORS[code]
            elif code in _RESET_CODES:
                current = None
            else:
                parts.append(_CC + code)
            i += 2
        else:
            parts.append(piece[i])
            i += 1
    if parts:
        runs.append((current, ''.join(parts)))
    return runs


