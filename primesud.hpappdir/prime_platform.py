from hpprime import eval as ppl_eval


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
