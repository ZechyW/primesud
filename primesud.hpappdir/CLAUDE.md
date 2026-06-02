# PrimeSud — CLAUDE.md

## What this project is

**PrimeSud** is a text-based, single-user RPG for the HP Prime graphing calculator, heavily inspired by MUDs (Multi-User Dungeons). The name: **Prime** (calculator) + **SUD** (Single-User Dungeon).

The game runs entirely in a terminal-style text UI rendered directly on the calculator's 320×240 screen via a custom text layer (`tml.py`).

## Repository layout

```
primesud.hpappdir/
├── primesud.py          # Main game entry point — PrimeSud + Game classes
├── tml.py               # Text Mode Layer library (reusable, treat as stable)
├── std5x10green.font    # Custom bitmap font used by tml
├── primesud.hpapp       # Binary HP Prime app package
├── primesud.hpappprgm   # Binary program metadata
└── primesud.hpappnote   # Binary note file
../reference/            # Reference game implementations (JezzBall, Star Trek)
```

## Tech stack

- **Language:** Python — but HP Prime's restricted MicroPython-like subset, not standard CPython
- **Available modules:** `hpprime`, `uio`, `cas`, `math`, `utime` — ask the user if unsure about others.
- **No package manager.** There is no pip and no ability to bring in pypi external dependencies in general.
- **Font:** `std5x10green.font` — a PNG-based bitmap font with a custom trailer byte encoding character dimensions

## Architecture

### `PrimeSud` (context manager)
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

6. **`KeyboardInterrupt` is the exit signal.** The calculator's On key raises it. The context manager in `PrimeSud.__exit__` already handles this — don't swallow it elsewhere.

## Working style

- Write code first, then briefly explain key decisions — especially anything non-obvious about HP Prime's constraints or PPL interop.
- Keep changes minimal and targeted. Do not refactor surrounding code unless asked.
- When in doubt about whether a Python feature is available on HP Prime, assume it is not and use the simplest possible alternative.
