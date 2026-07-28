# TODO

Loose ends that don't belong in a specific plan file.

## Roadmap (23/07/2026)

Engine 1.0 was tagged as `v1.0.0` on 23/07/2026. Content track is now open:

1. Keep engine parity fixes auditable against the `v1.0.0` baseline.
2. Release new classes, areas, and quests as content versions on top of that
   stable engine.

## Combat

(nothing outstanding)

## Items

(nothing outstanding)

## Magic

(nothing outstanding)

## Classes

(nothing outstanding)

## Commands

(nothing outstanding)

## Housing

(nothing outstanding)

## Area data

(nothing outstanding)

## Tests

(nothing outstanding)

## Platform

- Graphical PC shim (`pc_gui_shim/`, `run_graphical.py`) -- committed as WIP;
  rework `pc_gui_shim/tml_prime.py` before treating GUI runs as device-path
  verification.
  - Assessment: bottom layer is right -- `pc_gui_shim/hpprime.py` shims the
    GROB/blit/mouse API so the real `src/tml.py` atlas renderer and
    `src/terminal.py` history capture run unmodified. But
    `pc_gui_shim/tml_prime.py` shadows `src/tml_prime.py` and *reimplements*
    it (`_scroll_up`, `_put_char`, `input`, `poll_char`, the `_scrollback`
    drag/fling state machine, `_render_scrollback`), and `pc_gui_shim/fling.py`
    is a verbatim copy of `src/tml_prime._advance_fling`. The layer with the
    most device logic never runs in GUI mode -- a parallel copy does, so it
    will drift and GUI "verification" of scrollback/fling proves nothing about
    the device code. It also skips src's alloc-free `print_xy` override.
    Known behaviour breaks from the fork: `poll_char` ignores `key_commands`
    (autoskill editor nav-pad `_NAV_KEYS` dead, `config.KEY_COMMANDS`
    movement keys never fire), arrow semantics diverge from device (GUI Up =
    history vs device Up = "n"), and the reimplemented `input()` lacks
    `\L`/`\R` cursor editing.
  - Proposal: the shim's `eval` already handles `Ticks`/`WAIT`/`GETKEY`, and
    `mouse()` works, so the device class runs verbatim on it. Load
    `src/tml_prime.py` via importlib (name is shadowed), subclass, and
    override only `_pump_keyboard`: pump Tk, translate keysyms, feed
    `self._queue_key(...)`. Keys with device equivalents (arrows -> bits
    2/7/8/12, Esc -> 4, Enter -> 30, Backspace -> 19) route through the real
    `_translate_key_press(bit, key_commands)`; plain typed chars queue as
    `(char, None)`. Deletes ~300 lines incl. `fling.py` and its
    copy-targeting test in `tests/test_gui_grob.py`; scrollback, fling,
    input replay, and `key_commands` handling become the real device code.
  - Minor while in there: `pc_gui_shim/hpprime.py` `fillrect` arg names are
    inverted vs device signature `(g, x, y, w, h, edge_color, fill_color)` --
    harmless today (all callers pass edge == fill) but fix before a
    two-colour call lands; `pc_gui_shim/prime_platform.py` duplicates
    `pc_shim/prime_platform.py` hvars/ticks, could import-and-override just
    `wait_ms`/`clear_graphics`.

- Save optimisation (probe data in docs/BUILTINS.md sec. Save-path
  primitive costs): add debug-gated `ticks()` instrumentation to
  `_serialize_world` ("save" DBG channel); the cache conversion is
  also the alloc diet, and dropping the up-front `gc_collect()`
  returns 78-198 ms. HVars and file I/O measured negligible.
- 6mb-vs-8mb app scaffolding question is closed: 8 MB is fully backable
  and healthy on the G1 (mem_soak); Connectivity Kit needs the Python
  app closed (reset) regardless of heap size.
