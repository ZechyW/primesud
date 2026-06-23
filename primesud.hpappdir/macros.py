"""Function-key macro defaults and macro command handling."""

from config import (DEFAULT_MACROS, DEFAULT_FNKEY_MACROS, FNKEY_NAMES,
                    TERMINAL_COLS)


_MACRO_SUBST = dict(DEFAULT_MACROS)   # [PRIMESUD] user-configurable macros -- no 1stMud equivalent
_MACRO_SUBST.update(DEFAULT_FNKEY_MACROS)

_CELL_W         = (TERMINAL_COLS - 4) // 3  # width of each of the 3 display columns
_MACRO_SEP      = "+" + ("-" * _CELL_W + "+") * 3
_MACRO_SEP_STRONG = "+" + ("=" * _CELL_W + "+") * 3

_FNKEY_ORDER   = sorted(FNKEY_NAMES.keys())
_FNKEY_BY_NAME = {v: k for k, v in FNKEY_NAMES.items()}  # 'x2' -> 14 etc.

_fns = [(s, FNKEY_NAMES[s]) for s in _FNKEY_ORDER]
while len(_fns) % 3:
    _fns.append(None)
_MACRO_TABLE = [_fns[i:i+3] for i in range(0, len(_fns), 3)] + [
    None,
    [("7","7"), ("8","8"), ("9","9")],
    [("4","4"), ("5","5"), ("6","6")],
    [("1","1"), ("2","2"), ("3","3")],
    [("0","0"), None,      None     ],
]
del _fns


def _macro_cell(key, label=None):
    """Return padded display lines for one cell; key=None -> blank."""
    def pad(s):
        return s + " " * (_CELL_W - len(s))
    if key is None:
        return [" " * _CELL_W]
    if label is None:
        label = key
    label = " " * (3 - len(label)) + label
    cmd = _MACRO_SUBST.get(key)
    if cmd is None:
        return [pad(" {}:".format(label))]
    indent = len(label) + 3
    content_w = _CELL_W - indent
    lines = []
    rest = cmd
    while rest:
        prefix = " {}: ".format(label) if not lines else " " * indent
        lines.append(pad(prefix + rest[:content_w]))
        rest = rest[content_w:]
    return lines


def _macro_row(entries):
    """Render one 3-cell row; each entry is (key, label) or None for blank."""
    cells = [_macro_cell(*(e if e is not None else (None, None))) for e in entries]
    height = max(len(c) for c in cells)
    for c in cells:
        while len(c) < height:
            c.append(" " * _CELL_W)
    for ki, e in enumerate(entries):
        if e is not None:
            label = e[1]
            pad_len = max(3, len(label))
            s = cells[ki][0]
            cells[ki][0] = s[:1 + pad_len - len(label)] + "{R" + label + "{x" + s[1 + pad_len:]
    return ["|{}|{}|{}|".format(cells[0][i], cells[1][i], cells[2][i])
            for i in range(height)]


def do_macro(tr, player, args):  # [PRIMESUD]
    if not args:
        next_sep = _MACRO_SEP
        for row in _MACRO_TABLE:
            if row is None:
                next_sep = _MACRO_SEP_STRONG
            else:
                tr.print(next_sep)
                for line in _macro_row(row):
                    tr.print(line)
                next_sep = _MACRO_SEP
        tr.print(next_sep)
        return None
    if args[0] == "default":
        _MACRO_SUBST.clear()
        _MACRO_SUBST.update(DEFAULT_MACROS)
        _MACRO_SUBST.update(DEFAULT_FNKEY_MACROS)
        tr.print("Macros reset to defaults.")
        return None
    key = args[0].lower()
    sentinel = _FNKEY_BY_NAME.get(key)
    if sentinel is not None:
        target = sentinel
        label = key
    elif len(key) == 1 and key in "0123456789":
        target = key
        label = key
    else:
        tr.print("Key must be a digit 0-9 or one of: {}.".format(
            " ".join(sorted(_FNKEY_BY_NAME))))
        return None
    if len(args) == 1:
        if target in _MACRO_SUBST:
            del _MACRO_SUBST[target]
            tr.print("Macro {} cleared.".format(label))
        else:
            tr.print("No macro on {}.".format(label))
    else:
        cmd = " ".join(args[1:])
        _MACRO_SUBST[target] = cmd
        tr.print("{R%s{x mapped to '%s'." % (label, cmd))
    return None
