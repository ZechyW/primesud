import gc


def fmt_bytes(n, precision=1):
    """Format a byte count as a human-readable string."""
    fmt = "{:." + str(precision) + "f}{}"
    for unit in ("B", "K", "M"):
        if n < 1024:
            return fmt.format(n, unit)
        n /= 1024
    return fmt.format(n, "G")


def free_mem():
    """Return current free heap as a human-readable string."""
    return fmt_bytes(gc.mem_free())

def gc_collect():
    """Convenience function for gc within the game"""
    return gc.collect()