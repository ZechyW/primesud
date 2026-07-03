"""Debug channel toggles for playtesting. [PRIMESUD]"""

import terminal

# Active debug channels.  Callers must guard with `if "x" in DBG:` BEFORE
# building the message string -- concat costs even when discarded, and some
# call sites are in per-mob per-pulse loops.
DBG = set()

_CHANNELS = ("spawn", "move", "tick", "reset")


def dbg(msg):
    """Print one debug line in dark grey. [PRIMESUD]"""
    terminal.tr.print("{D[dbg] " + msg + "{x")


def do_debug(player, args):
    """Toggle debug channels; no args lists channel states. [PRIMESUD]"""
    if not args:
        terminal.tr.print("Debug channels:")
        for name in _CHANNELS:
            state = "{Gon{x" if name in DBG else "{Doff{x"
            terminal.tr.print("  " + name + ": " + state)
        return
    name = args[0]
    match = None
    for c in _CHANNELS:
        if c.startswith(name):
            match = c
            break
    if match is None:
        terminal.tr.print("No such debug channel: " + name)
        return
    if match in DBG:
        DBG.discard(match)
        terminal.tr.print("Debug channel '" + match + "' off.")
    else:
        DBG.add(match)
        terminal.tr.print("Debug channel '" + match + "' on.")
