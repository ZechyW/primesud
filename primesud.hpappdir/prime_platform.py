"""HP Prime platform wrappers and graphic primitive ownership."""

from hpprime import dimgrob, eval as ppl_eval, getpix, grobh, grobw, pixon, strblit2


def ticks():
    """Return HP Prime millisecond tick counter."""
    return int(ppl_eval("Ticks"))


def wait(seconds):
    """Wait for seconds via PPL WAIT."""
    ppl_eval("WAIT({})".format(seconds))


def wait_ms(ms):
    """Wait for milliseconds via PPL WAIT."""
    ppl_eval("WAIT({}/1e3)".format(ms))


def save_prime_settings():
    """Save calculator settings touched by PrimeSUD."""
    sep = ppl_eval("HSeparator")
    ppl_eval("HSeparator:=0")
    return tuple(ppl_eval("{AAngle,AFormat,AComplex,Bits}")) + (sep,)


def configure_prime():
    """Set calculator settings expected by PrimeSUD."""
    ppl_eval("AAngle:=1;AFormat:=1;AComplex:=0;Bits:=32")


def restore_prime_settings(values):
    """Restore calculator settings saved by save_prime_settings."""
    ppl_eval(
        "AAngle:=%d;AFormat:=%d;AComplex:=%d;Bits:=%d;HSeparator:=%d;TOff:=TOff"
        % values
    )


def clear_graphics(first=1, last=8):
    """Clear HP Prime graphic buffers in the inclusive range."""
    for n in range(first, last + 1):
        dimgrob(n, 0, 0, 0)


def hvars_get(name):
    """Read a PPL home variable through HVars."""
    return ppl_eval('HVars("' + name + '")')


def hvars_set(name, value):
    """Write a PPL home variable through HVars."""
    ppl_eval('HVars("' + name + '"):="' + value + '"')
