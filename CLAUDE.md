# PrimeSUD -- CLAUDE.md

## What this project is

**PrimeSUD** = text-based single-user RPG for HP Prime graphing calculator. Port of ROM 2.4-based MUD codebase, 1stmud.

Runs in terminal-style text UI on calculator's 320x240 screen via custom text layer (`tml.py`).

## Tech stack

- **Language:** Python -- HP Prime's restricted MicroPython-like subset, not standard CPython
- **Available modules:** `hpprime`, `uio`, `cas`, `math`, `urandom`, `gc` -- ask user if unsure about others. `utime` is NOT importable on-device (confirmed 2026-07-07); use PPL `Ticks`/`WAIT` via `hpprime.eval`
- **No package manager.** No pip, no pypi dependencies

## Architecture

### `tml` (Text Mode Layer)

Reusable terminal abstraction by Piotr Kowalewski (komame). Renders chars onto HP Prime graphic buffers using bitmap font; handles scrolling, cursor, dark/light mode, tab stops, keyboard state. **Stable library -- don't break public API or add game logic to it.**

## Constraints and pitfalls

1. **HP Prime Python is not CPython.** Many stdlib modules missing, built-ins have reduced method sets. See **[docs/BUILTINS.md](docs/BUILTINS.md)** for verified availability (confirmed via `dir()` on-device).

2. **Memory very limited.** Small heap. Avoid large structures, deep call stacks, string concat in loops (use lists + `join`), or unnecessary caching.

3. **No floats in tight loops if avoidable.** Integer arithmetic faster and safer.

4. **PPL interop via `ppleval`.** Calculator built-ins (`Ticks`, `WAIT`, `HSeparator`, `AAngle`) called via PPL expression strings through `hpprime.eval`. Keep strings minimal and correct -- errors surface as silent failures or runtime exceptions.

5. **`KeyboardInterrupt` is exit signal.** On key raises it. `PrimeSUD.__exit__` handles it -- don't swallow elsewhere.

6. **Python source must be ASCII-only and BOM-free.** HP Prime's Python loader can misparse UTF-8 BOM or non-ASCII bytes, even in comments. Prefer `apply_patch` for `.py` edits; do not rewrite Python files with PowerShell `Set-Content`, `Out-File`, or redirection unless explicitly writing bytes / UTF-8 without BOM. After editing Python files, run:

```
python tools/check_ascii_py.py
```

7. **File I/O calls are expensive (~20ms each).** Never loop `readline()` at runtime; use one `f.read()` (or `seek` + bounded read) and split in memory. Measured numbers in `docs/BUILTINS.md` sec. File I/O performance.

8. **Use str() + concat in persisted/serialized strings.** Physical HP Prime Python has confirmed heap-sensitive string formatting bug. Values can behave like strings at first, then fail later during list/string operations such as `"~".join(lines)`. For save payloads, HVars/PPL strings, file formats, area-data generated strings, or any string that will be joined/stored/parsing-critical, use explicit `str()` plus concatenation. See `docs/PRIME_STRING_FORMAT_BUG.md`.

## Colour codes

Embed `{G`, `{r`, `{x`, etc. directly in strings passed to `tr.print()` -- handled by `colors.py`. For transient UI-only strings, `%` (`"{G%s{x" % name`, `"hp: %d" % hp`) avoids `.format()` conflicts with `{X` colour delimiters. For persisted/serialized strings, do **not** use `%`; use explicit `str()` plus concatenation. Concatenation (`"{G" + name + "{x"`) works but verbose. Full table in docs/REFERENCE.md sec. Colour codes.

When porting 1stMud code using `CTAG(_CONSTANT)` (e.g. `CTAG(_MOBILES)`), default colour per constant documented in docs/REFERENCE.md sec. CTAG colour scheme. Use that table to pick equivalent `{X` code.

## Porting from 1stmud

When porting features from 1stmud, aim for full fidelity. In particular, match 1stmud's function signatures, logic flow, and output messages. Match data and naming conventions wherever possible. Add inline comments for features that aren't available yet or that are PRIMESUD specific, so that these are easy to find/validate/address later.

Exception: fix typos, grammatical errors, and other linguistic slips in 1stmud output text where appropriate (e.g. "does" used for first person, "a outlaw", "beleive"); mark such fixes with a `[PRIMESUD]` comment.

## Verified port

If a given function is marked as being verified against 1stmud in its docstring (`[Verified: <date>]`), NEVER edit it without asking for explicit permission first.

Exception: targeted edits that resolve a documented TODO / "not ported" note toward 1stMud fidelity are allowed without asking. Keep the edit minimal, re-verify the function against the 1stMud source, and extend the tag (e.g. `[Verified: <old date>; <feature> added and re-verified <new date>]`). Anything beyond the documented TODO still needs explicit permission.

## PrimeSUD-only extensions -- `[PRIMESUD]` tag

Code with no 1stMud equivalent or intentional deviation marked `# [PRIMESUD]`. When porting from 1stMud, don't overwrite tagged items without checking if Prime variant differs on purpose.

## Docstrings

Google-style: one-line summary, then `Args:` / `Returns:` / `Raises:` as needed; omit empty sections. For ported functions append `(cf. 1stMud <symbol> in <file>)` to summary (exact name + source file, e.g. `fight.c`); PrimeSUD-only functions and helpers should be explicitly marked [PRIMESUD].

## Documentation map

Root: `README.md`, `CLAUDE.md`, `DESIGN.md` (intentional deviations + settled decisions), `TODO.md` (loose ends). Everything else lives in `docs/`:

- 1stMud reference: `REFERENCE.md`, `COMMANDS.md`, `SKILLS.md`
- Device limits/perf: `BUILTINS.md`, `PRIME_STRING_FORMAT_BUG.md`, `PRIME_COLOURS.md`
- PrimeSUD systems: `AREA_FILES.md`, `PRIME_UX.md`, `FIXES.md`, `SHOP_DEVIATIONS.md`, `CROSS_RESETS.md`

Completed plan documents are deleted, not archived -- durable decisions get harvested into `DESIGN.md`/`TODO.md` first; full text stays in git history.

## Working style

- Read `DESIGN.md`, and relevant reference docs before porting behavior from 1stMud.
- Provide sanity check and brief explanation of key decisions -- especially HP Prime constraints or PPL interop -- before complex coding.
- Minimal targeted changes. No surrounding refactor unless it is substantially cleaner or better; if so, raise for review.
- Unsure if Python feature is available on HP Prime? Ask for human check.
