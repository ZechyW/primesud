"""ANSI colour install_color_print for PC -- replaces HP Prime pixel-font version."""
import sys
from colors import COLOR_CODE, _RESET_CODES, color_wrap
from config import TERMINAL_COLS
from tml_prime import tml_prime as tml

_ANSI = {
    'd': '\033[30m', 'r': '\033[31m', 'g': '\033[32m', 'y': '\033[33m',
    'b': '\033[34m', 'm': '\033[35m', 'c': '\033[36m', 'w': '\033[37m',
    'D': '\033[90m', 'R': '\033[91m', 'G': '\033[92m', 'Y': '\033[93m',
    'B': '\033[94m', 'M': '\033[95m', 'C': '\033[96m', 'W': '\033[97m',
}
_RST = '\033[0m'


def _to_ansi(text):
    if COLOR_CODE not in text:
        return text
    out = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] == COLOR_CODE and i + 1 < n:
            code = text[i + 1]
            if code == COLOR_CODE:
                out.append(COLOR_CODE)
            elif code in _ANSI:
                out.append(_ANSI[code])
            elif code in _RESET_CODES:
                out.append(_RST)
            i += 2
        else:
            out.append(text[i])
            i += 1
    return ''.join(out)


def install_color_print(tr):
    def wrapped_print(*args, sep=' ', end='\n'):
        text = sep.join(str(a) for a in args)
        # Word-wrap at the calc's 64-col width so PC output matches the
        # device (console otherwise hard-wraps long lines mid-word).
        # Wrap before ANSI conversion; colour state carries across lines.
        if text:
            wrapped = []
            for ln in text.split('\n'):
                wrapped.extend(color_wrap(ln, TERMINAL_COLS) if ln else [''])
            text = '\n'.join(wrapped)
        out = _to_ansi(text)
        if COLOR_CODE in text:
            out += _RST
        prefix = '\n' if tr._at_prompt else ''
        tr._at_prompt = False
        sys.stdout.write(prefix + out + end)
        sys.stdout.flush()

    tr.print = wrapped_print

    def wrapped_set_status(text):
        sys.stdout.write('\r' + _to_ansi(text) + _RST + '\033[K')
        sys.stdout.flush()
        tr._at_prompt = True

    tr.set_status = wrapped_set_status


tr = None


def tprint(*args, **kwargs):
    """Module-level print -- delegates to tr.print (colour-aware)."""
    tr.print(*args, **kwargs)


def init_terminal():
    """Create the tml instance and install colour wrappers. [PRIMESUD]"""
    global tr
    if tr is not None:
        return
    tr = tml()
    install_color_print(tr)