"""Function-key macro defaults and macro command handling."""

from config import (DEFAULT_MACROS, DEFAULT_FNKEY_MACROS, FNKEY_NAMES,
                    TERMINAL_COLS)
from terminal import tprint

_MACRO_SUBST = dict(DEFAULT_MACROS)   # [PRIMESUD] user-configurable macros -- no 1stMud equivalent
_MACRO_SUBST.update(DEFAULT_FNKEY_MACROS)

_FNKEY_BY_NAME = {v: k for k, v in FNKEY_NAMES.items()}


def _fn(name, label=None):
    """Return a function-key display cell. [PRIMESUD]"""
    return (_FNKEY_BY_NAME[name], label or name)


# Physical HP Prime layout. A labelled None is a dim, non-configurable key;
# its optional third item annotates the second line. A short row makes its
# final cell span the unused trailing columns.
_MACRO_SECTIONS = (
    (
        (_fn("vars", "Vars"), _fn("tool", "Toolbox"), _fn("tmpl", "Templt"),
         _fn("math", "Math"), _fn("abc", "a b/c"), (None, "Del")),
        (_fn("xy", "x^y"), _fn("sin"), _fn("cos"), _fn("tan"),
         _fn("ln"), _fn("log")),
        (_fn("x2", "x^2"), _fn("pm", "+/-"), _fn("()"), _fn(","),
         (None, "Enter")),
    ),
    (
        (_fn("eex", "EEX"), ("7", "7"), ("8", "8"), ("9", "9"),
         (None, "/", "[Recall]")),
        ((None, "ALPHA"), ("4", "4"), ("5", "5"), ("6", "6"), (None, "*")),
        ((None, "Shift"), ("1", "1"), ("2", "2"), ("3", "3"), (None, "-")),
        ((None, "On", "[Exit]"), ("0", "0"), (".", "."), (None, "Space"), (None, "+")),
    ),
)


def _center(s, width):
    """Pad text to a fixed-width cell. [PRIMESUD]"""
    left = (width - len(s)) // 2
    return " " * left + s + " " * (width - len(s) - left)


def _macro_widths(count):
    """Distribute terminal width across count cells. [PRIMESUD]"""
    inner = TERMINAL_COLS - count - 1
    base, extra = divmod(inner, count)
    return [base + (1 if i < extra else 0) for i in range(count)]


def _macro_cell(key, label, width, note=None):
    """Render label and truncated binding for one physical key. [PRIMESUD]"""
    if label is None:
        return (" " * width, " " * width)
    if key is None:
        value = "{D" + _center(note, width) + "{x" if note else " " * width
        return ("{D" + _center(label, width) + "{x", value)
    cmd = _MACRO_SUBST.get(key)
    if cmd is None:
        value = "{D" + _center("unset", width) + "{x"
    else:
        preview = cmd if len(cmd) <= width else cmd[:width - 3] + "..."
        value = _center(preview, width).replace("{", "{{")
    return ("{R" + _center(label, width) + "{x", value)


def _row_widths(entries, widths):
    """Let a short row's final cell span trailing columns. [PRIMESUD]"""
    row_widths = widths[:len(entries)]
    if len(entries) < len(widths):
        row_widths[-1] += sum(widths[len(entries):]) + len(widths) - len(entries)
    return row_widths


def _macro_row(entries, widths):
    """Render one physical key row as label and binding lines. [PRIMESUD]"""
    cells = []
    widths = _row_widths(entries, widths)
    for i in range(len(entries)):
        entry = entries[i] if entries[i] is not None else (None, None)
        note = entry[2] if len(entry) > 2 else None
        cells.append(_macro_cell(entry[0], entry[1], widths[i], note))
    return ("|" + "|".join(c[0] for c in cells) + "|",
            "|" + "|".join(c[1] for c in cells) + "|")


def _macro_sep(widths, fill="-"):
    """Render a full-width grid separator. [PRIMESUD]"""
    return "+" + "+".join(fill * width for width in widths) + "+"


def _macro_target(key):
    """Resolve a command-facing key name to its macro-map key. [PRIMESUD]"""
    key = key.lower()
    sentinel = _FNKEY_BY_NAME.get(key)
    if sentinel is not None:
        return sentinel, key
    if len(key) == 1 and key in "0123456789.":
        return key, key
    return None, None


def _print_key_error():
    """Print valid macro key names. [PRIMESUD]"""
    tprint("Key must be 0-9, '.', or one of: "
           + " ".join(sorted(_FNKEY_BY_NAME)) + ".")


def do_macro(player, args):
    """Display or set function-key and digit-key macros. [PRIMESUD]"""
    if not args:
        # [PRIMESUD] Exactly TERMINAL_ROWS grid lines, filling the screen.
        # terminal.print_lines scrolls lazily -- the cursor parks one row
        # past the bottom and the pending scroll is consumed by the next
        # batch -- so a 22-line batch lands on rows 0-21 with no row lost
        # to the cursor. A 23rd line would scroll the leading border off.
        last_section = len(_MACRO_SECTIONS) - 1
        for section_i in range(len(_MACRO_SECTIONS)):
            section = _MACRO_SECTIONS[section_i]
            widths = _macro_widths(len(section[0]))
            tprint(_macro_sep(widths, "=" if section_i else "-"))
            for row_i in range(len(section)):
                row = section[row_i]
                for line in _macro_row(row, widths):
                    tprint(line)
                # The next section's '=' boundary closes the last row of a
                # non-final section -- one rule there, not two. [PRIMESUD]
                if section_i == last_section or row_i != len(section) - 1:
                    tprint(_macro_sep(_row_widths(row, widths)))
        return None
    if args[0] == "default":
        if len(args) != 1:
            tprint("Usage: macro default")
            return None
        _MACRO_SUBST.clear()
        _MACRO_SUBST.update(DEFAULT_MACROS)
        _MACRO_SUBST.update(DEFAULT_FNKEY_MACROS)
        tprint("Macros reset to defaults.")
        return None
    if args[0] == "unset":
        if len(args) != 2:
            tprint("Usage: macro unset <key>")
            return None
        target, label = _macro_target(args[1])
        if target is None:
            _print_key_error()
        elif target in _MACRO_SUBST:
            del _MACRO_SUBST[target]
            tprint("Macro " + label + " unset.")
        else:
            tprint("No macro configured for " + label + ".")
        return None
    target, label = _macro_target(args[0])
    if target is None:
        _print_key_error()
        return None
    if len(args) == 1:
        cmd = _MACRO_SUBST.get(target)
        if cmd is None:
            tprint("No macro configured for " + label + ".")
        else:
            tprint("{R" + label + "{x is mapped to '"
                   + cmd.replace("{", "{{") + "'.")
        return None
    cmd = " ".join(args[1:])
    # [PRIMESUD] '~' is the save-payload line separator (game_state.py);
    # a macro containing it would corrupt the save on the next write.
    if "~" in cmd:
        tprint("Macro text may not contain '~'.")
        return None
    _MACRO_SUBST[target] = cmd
    tprint("{R" + label + "{x mapped to '" + cmd.replace("{", "{{") + "'.")
    return None
