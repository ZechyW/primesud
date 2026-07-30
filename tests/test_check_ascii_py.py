"""Guard the on-device format-bug checker (tools/check_ascii_py.py)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "tools"))

from check_ascii_py import format_violations  # noqa: E402


def test_flags_direct_percent_and_format_and_fstring():
    assert format_violations('x = "hi %s" % name\n')
    assert format_violations('x = "hi {}".format(name)\n')
    assert format_violations('x = f"hi {name}"\n')


def test_flags_hoisted_format_string_in_table():
    # the scan.py _DISTANCE shape that slipped past the old direct-% rule
    src = '_D = ("nearby to the %s.",)\ndef f(s, d):\n    return s % d\n'
    assert format_violations(src)


def test_allows_docstrings_and_safe_formatters():
    src = ('def f(ch, n):\n'
           '    """Print a line, e.g. "%d gold"."""\n'
           '    chprintf(ch, "%s has %d gold", ch, n)\n'
           '    return n % 100\n')
    assert format_violations(src) == []
