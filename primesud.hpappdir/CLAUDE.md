# PrimeSUD — CLAUDE.md

## What this project is

**PrimeSUD** is a text-based, single-user RPG for the HP Prime graphing calculator, heavily inspired by MUDs (Multi-User Dungeons). The name: **Prime** (calculator) + **SUD** (Single-User Dungeon).

The game runs entirely in a terminal-style text UI rendered directly on the calculator's 320×240 screen via a custom text layer (`tml.py`).

## Repository layout

```
primesud.hpappdir/
├── primesud.py          # Main game entry point — PrimeSUD + Game classes
├── tml.py               # Text Mode Layer library (reusable, treat as stable)
├── std5x10.font    # Custom bitmap font used by tml. 64 cols x 24 rows (excluding status bar)
├── DESIGN.md            # Intentional design decisions and 1stMud deviations — read before porting
├── primesud.hpapp       # Binary HP Prime app package
├── primesud.hpappprgm   # Binary program metadata
└── primesud.hpappnote   # Binary note file
../reference/            # Reference game implementations (JezzBall, Star Trek)
```

## Tech stack

- **Language:** Python — but HP Prime's restricted MicroPython-like subset, not standard CPython
- **Available modules:** `hpprime`, `uio`, `cas`, `math`, `utime` — ask the user if unsure about others.
- **No package manager.** There is no pip and no ability to bring in pypi external dependencies in general.
- **Font:** `std5x10.font` — a PNG-based bitmap font with a custom trailer byte encoding character dimensions

## Architecture

### `PrimeSUD` (context manager)
Handles environment setup/teardown: saves and restores calculator settings (`AAngle`, `AFormat`, `AComplex`, `Bits`, `HSeparator`) and clears graphic buffers on exit. Suppresses `KeyboardInterrupt` so the user can exit cleanly with the calculator's On key.

### `Game`
Contains game state and the main loop. Uses `ppleval("Ticks")` (milliseconds) for tick-based timing. Keyboard state is read via `hpprime.keyboard()` which returns a bitmask — bit positions map to physical keys.

### `tml` (Text Mode Layer)
A reusable terminal abstraction written by Piotr Kowalewski (komame). Renders characters onto HP Prime graphic buffers using the bitmap font, handles scrolling, cursor, dark/light mode, tab stops, and keyboard state (alpha/shift lock). **Treat this as a stable library — do not break its public API or add game-specific logic to it.**

## Deployment and testing

- **Emulator:** HP Prime Virtual Calculator (PC/Mac app) — use for rapid iteration
- **Physical device:** Transfer via HP Connectivity Kit
- Workflow: develop and test on emulator, validate on physical hardware before considering anything "done"

## Constraints and pitfalls

1. **HP Prime Python is not CPython.** Many standard library modules do not exist.

2. **Memory is very limited.** The HP Prime has a small heap. Avoid large data structures, deep call stacks, string concatenation in loops (build lists and `join`), or caching things that can be recomputed.

3. **No floats in tight loops if avoidable.** Integer arithmetic is faster and safer on this platform.

4. **PPL interop via `ppleval`.** Calculator built-in functions (e.g., `Ticks`, `WAIT`, `HSeparator`, `AAngle`) are called by evaluating PPL expression strings through `hpprime.eval`. Keep these strings minimal and correct — errors surface as silent failures or exceptions at runtime only.

5. **Graphic buffers G1–G9.** The HP Prime has 9 graphic buffers (GROBs). G9 is used by `tml` for the font. G0 is the display. Avoid clobbering G9 or buffers `tml` relies on.

6. **`KeyboardInterrupt` is the exit signal.** The calculator's On key raises it. The context manager in `PrimeSUD.__exit__` already handles this — don't swallow it elsewhere.

## Colour codes

PrimeSUD uses the **same `{X` escape syntax as 1stMud** — embed codes directly in any string passed to `tr.print()` and they are handled transparently by `colors.py`. No need to read that file to use colours.

| Code | Colour | Code | Colour |
|------|--------|------|--------|
| `{d` | dark grey | `{D` | grey |
| `{r` | red | `{R` | bright red |
| `{g` | green | `{G` | bright green |
| `{y` | yellow | `{Y` | bright yellow |
| `{b` | blue | `{B` | bright blue |
| `{m` | magenta | `{M` | bright magenta |
| `{c` | cyan | `{C` | bright cyan |
| `{w` | light grey | `{W` | white |
| `{x` / `{X` | reset to default | | |

Example: `tr.print("{Ghello{x world")` — "hello" in bright green, " world" in default foreground.

To mix colour codes with Python string formatting, build by concatenation (`"{G" + name + "{x"`) rather than `.format()` — the `{` delimiter conflicts with format-string syntax.

## PrimeSUD-only extensions — `[PRIMESUD]` tag

Code with no 1stMud equivalent, or that intentionally diverges from 1stMud behaviour,
is marked with a `# [PRIMESUD]` comment. When porting mechanics from 1stMud, do not
overwrite tagged items without checking whether the Prime variant differs on purpose.

Find all tagged locations:

    grep -r "\[PRIMESUD\]" primesud.hpappdir/

Currently tagged:
- `config.py` — `KEY_COMMANDS`, `NAV_KEYS` (HP Prime hardware key mappings)
- `primesud.py` — nav-pad auto-submit branch in game loop
- `commands.py` — `_MACRO_SUBST`, `do_macro`
- `combat.py` — `_SPECIAL_MOVES` section, unarmed special-move block in `multi_hit`

## Benchmarking

HP Prime has no profiler, so timing is done inline with `ppleval("Ticks")` (milliseconds).

**Pattern:** add a benchmark block to `run_title()` in `primesud.py` — it runs after `Game.__init__` (so all GROBs and precomputed data are ready) but before the game loop, and the screen is clear.

Example (adapt as needed):

```python
REPS = 100
t0 = int(ppleval("Ticks"))
for i in range(REPS):
    # ... code under test ...
t_ms = int(ppleval("Ticks")) - t0
tr.print("result: {} ms ({} ms/call)".format(t_ms, t_ms // REPS))
```

End the block with `tr.input("")` to pause and read results before the game continues.  Clean up any side-effects (e.g. restore FONT_GROB via `strblit2` and reset `self._current_fg = None`) before the `tr.input` call so the game starts in a consistent state.

## Working style

- Write code first, then briefly explain key decisions — especially anything non-obvious about HP Prime's constraints or PPL interop.
- Keep changes minimal and targeted. Do not refactor surrounding code unless asked.
- When in doubt about whether a Python feature is available on HP Prime, assume it is not and use the simplest possible alternative.
