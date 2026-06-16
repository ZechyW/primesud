# PrimeSUD -- CLAUDE.md

## What this project is

**PrimeSUD** = text-based single-user RPG for HP Prime graphing calculator. Port of ROM 2.4-based MUD codebase, 1stmud. Name: **Prime** (calculator) + **SUD** (Single-User Dungeon).

Runs in terminal-style text UI on calculator's 320x240 screen via custom text layer (`tml.py`).

## Repository layout

```
CLAUDE.md                # This file
DESIGN.md                # Intentional design decisions and 1stMud deviations -- read before porting
REFERENCE.md             # 1stMud implementation reference snippets + colour code table
AREA_FILES.md            # Python area module format reference
primesud.hpappdir/
+-- primesud.py          # Main game entry point -- PrimeSUD + Game classes
+-- colors.py            # {X colour codec (parse/strip colour escape sequences)
+-- config.py            # KEY_COMMANDS, NAV_KEYS, stat tables, THAC0 constants
+-- world_consts.py      # Cross-area VNUM constants used by game logic
+-- world.py             # Area loader, SKILL_TABLE, global mob/item/room tables
+-- area_school.py       # Mud School area data module (rooms/mobs/items/resets)
+-- player.py            # Character state, levelling, area resets
+-- combat.py            # one_hit, multi_hit, flee
+-- commands.py          # do_* command handlers + interpret()
+-- picker.py            # Contextual target picker (pick_from)
+-- automap.py           # Automap renderer
+-- tml.py               # Text Mode Layer library (reusable, treat as stable)
+-- std5x10.font         # Custom bitmap font; 64 cols x 22 rows usable (excluding status bar)
+-- primesud.hpapp       # Binary HP Prime app package
+-- primesud.hpappprgm   # Binary program metadata
+-- primesud.hpappnote   # Binary note file
reference/               # Reference game implementations (1stMud, JezzBall, Star Trek)
```

## Tech stack

- **Language:** Python -- HP Prime's restricted MicroPython-like subset, not standard CPython
- **Available modules:** `hpprime`, `uio`, `cas`, `math`, `utime` -- ask user if unsure about others
- **No package manager.** No pip, no pypi dependencies
- **Font:** `std5x10.font` -- PNG-based bitmap font with custom trailer byte encoding character dimensions

## Architecture

### `PrimeSUD` (context manager)
Handles env setup/teardown: saves/restores calculator settings (`AAngle`, `AFormat`, `AComplex`, `Bits`, `HSeparator`), clears graphic buffers on exit. Suppresses `KeyboardInterrupt` for clean On-key exit.

### `Game`
Game state + main loop. Uses `ppleval("Ticks")` (milliseconds) for tick timing. Keyboard via `hpprime.keyboard()` bitmask -- bit positions map to physical keys.

### `tml` (Text Mode Layer)
Reusable terminal abstraction by Piotr Kowalewski (komame). Renders chars onto HP Prime graphic buffers using bitmap font; handles scrolling, cursor, dark/light mode, tab stops, keyboard state. **Stable library -- don't break public API or add game logic to it.**

## Deployment and testing

- **Emulator:** HP Prime Virtual Calculator (PC/Mac) -- use for rapid iteration
- **Physical device:** Transfer via HP Connectivity Kit
- Workflow: develop/test on emulator, validate on hardware before "done"

## Constraints and pitfalls

1. **HP Prime Python is not CPython.** Many stdlib modules missing, built-ins have reduced method sets. See **[BUILTINS.md](BUILTINS.md)** for verified availability (confirmed via `dir()` on-device).

2. **Memory very limited.** Small heap. Avoid large structures, deep call stacks, string concat in loops (use lists + `join`), or unnecessary caching.

3. **No floats in tight loops if avoidable.** Integer arithmetic faster and safer.

4. **PPL interop via `ppleval`.** Calculator built-ins (`Ticks`, `WAIT`, `HSeparator`, `AAngle`) called via PPL expression strings through `hpprime.eval`. Keep strings minimal and correct -- errors surface as silent failures or runtime exceptions.

5. **Graphic buffers G1-G9.** G9 used by `tml` for font. G0 is display. Don't clobber G9 or `tml`-owned buffers.

6. **`KeyboardInterrupt` is exit signal.** On key raises it. `PrimeSUD.__exit__` handles it -- don't swallow elsewhere.

## Colour codes

Embed `{G`, `{r`, `{x`, etc. directly in strings passed to `tr.print()` -- handled by `colors.py`. When mixing with Python formatting, prefer `%` (`"{G%s{x" % name`, `"hp: %d" % hp`) over `.format()` -- `%` uses no `{` delimiters, composes cleanly. Concatenation (`"{G" + name + "{x"`) works but verbose. Full table in REFERENCE.md sec. Colour codes.

When porting 1stMud code using `CTAG(_CONSTANT)` (e.g. `CTAG(_MOBILES)`), default colour per constant documented in REFERENCE.md sec. CTAG colour scheme. Use that table to pick equivalent `{X` code.

## PrimeSUD-only extensions -- `[PRIMESUD]` tag

Code with no 1stMud equivalent or intentional deviation marked `# [PRIMESUD]`. When porting from 1stMud, don't overwrite tagged items without checking if Prime variant differs on purpose.

Find all tagged locations:

    grep -r "\[PRIMESUD\]" primesud.hpappdir/

## Benchmarking

No profiler on HP Prime. Add block to `run()` in `primesud.py` (before `game.show_greeting()`): capture `int(ppleval("Ticks"))` before/after N-rep loop, print delta, call `tr.input("")` to pause. Clean side-effects before pause for consistent game start.

## Docstrings

Google-style: one-line summary, then `Args:` / `Returns:` / `Raises:` as needed; omit empty sections. For ported functions append `(cf. 1stMud <symbol> in <file>)` to summary (exact name + source file, e.g. `fight.c`); omit for PrimeSUD-invented functions.

## Working style

- Code first, then brief explanation of key decisions -- especially HP Prime constraints or PPL interop.
- Minimal targeted changes. No surrounding refactor unless asked.
- Unsure if Python feature available on HP Prime? Ask for human check.