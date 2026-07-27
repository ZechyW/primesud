# PrimeSUD -- CLAUDE.md

## What this project is

**PrimeSUD** = text-based single-user RPG for HP Prime graphing calculator. Port of ROM 2.4-based MUD codebase, 1stmud.

Runs in terminal-style text UI on calculator's 320x240 screen via custom text layer (`tml.py`).

## Tech stack

- **Language:** Python -- HP Prime's restricted MicroPython-like subset, not standard CPython
- **Available modules:** `hpprime`, `uio`, `cas`, `math`, `urandom`, `gc`; also present but unverified: `sys`, `ure`, `ustruct`, `ucollections`, `uhashlib` and more -- see docs/BUILTINS.md sec. Module inventory. `utime` is NOT importable on-device (confirmed 2026-07-07); use PPL `Ticks`/`WAIT` via `hpprime.eval`
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

6. **Python source must be ASCII-only and BOM-free.** HP Prime's Python loader can misparse UTF-8 BOM or non-ASCII bytes, even in comments. Use surgical edit tools for `.py` changes; do not rewrite Python files with PowerShell `Set-Content`, `Out-File`, or redirection unless explicitly writing bytes / UTF-8 without BOM. After editing Python files, run:

```
python tools/check_ascii_py.py
```

7. **File I/O calls are expensive (~20ms each).** Never loop `readline()` at runtime; use one `f.read()` (or `seek` + bounded read) and split in memory. Measured numbers in `docs/BUILTINS.md` sec. File I/O performance. Always use `with open(...) as f:` (works on-device): MicroPython has no refcounting, `open(f).read()` leaks the handle, and the Prime's small FD table exhausts as `OSError: 0` on a later `open()`.

8. **No `%` and no `.format()` on-device, period. No bulk `str(int)` either.** Two distinct confirmed firmware heap bugs (physical hardware only; emulator clean):
   - **Format bug (G1 + G2):** any `%` or `.format()` call can zero the first byte of its output, corrupt unrelated *resident* strings, or hard-crash the calculator, depending on operator x context x device x heap layout. Layout-dependence makes shape-level "safe subsets" unprovable -- a construction that ran clean 30/30 in one session crashed 2/2 in another. Build ALL strings with concatenation. See `docs/PRIME_STRING_FORMAT_BUG.md`.
   - **str(int)-GC bug (G1):** bulk `str(int)` transients plus any garbage collection (explicit or automatic) corrupt the heap -- crash, stall, or delayed type-confusion. For int rendering use `util.int_str()` (digit-table + concat), `util.num_str()` (cached), or `util.sstr()` (typed dispatch for mixed values); never loop plain `str()` over numbers. See `docs/BUILTINS.md` sec. G1 memory-corruption bug.

   Occasional single `str(x)` calls outside loops are fine. `str()` on values that are already strings is fine.

9. **Allocation dominates hot loops on device.** One small heap alloc costs ~0.5ms at full game heap (~35us standalone) -- ~49x a native `strblit2` call. In per-char/per-item loops avoid anything that allocates: iterate `s.encode()` (ints) instead of a str (1-char str alloc each), no slices, `%` formatting, or tuple churn. Measured numbers in `docs/BUILTINS.md` sec. Text rendering performance.

## Colour codes

Embed `{G`, `{r`, `{x`, etc. directly in strings passed to `tr.print()` -- handled by `colors.py`. Build the strings with concatenation only (`"{G" + name + "{x"`, `"hp: " + num_str(hp)`) -- `%` and `.format()` are banned on-device per pitfall 8, which also conveniently sidesteps `.format()`'s brace conflict with `{X` colour delimiters. Full table in docs/REFERENCE.md sec. Colour codes.

When porting 1stMud code using `CTAG(_CONSTANT)` (e.g. `CTAG(_MOBILES)`), default colour per constant documented in docs/REFERENCE.md sec. CTAG colour scheme. Use that table to pick equivalent `{X` code.

## Porting from 1stmud

When porting features from 1stmud, aim for full fidelity. In particular, match 1stmud's function signatures, logic flow, and output messages. Match data and naming conventions wherever possible. Add inline comments for features that aren't available yet or that are `[PRIMESUD]`-specific, so that these are easy to find/validate/address later.

Exception: fix typos, grammatical errors, and other linguistic slips in 1stmud output text where appropriate (e.g. "does" used for first person, "a outlaw", "beleive"); mark such fixes with a `[PRIMESUD]` comment.

Exception: intent-parity over bug-parity. If 1stMud's code contradicts its own help text, comments, or player-visible output messages, port the stated intent and `[PRIMESUD]`-comment the contradiction at the site. Covers both bugs that make a feature unreachable (e.g. do_flag help lists `off`, dispatch chain lacks the branch) and behaviour that belies what the code itself prints (e.g. bank hours message vs. its hour check; a deposit check whose failure message names gold but compares silver). Notable fixes also get a `docs/FIXES.md` entry so deviations stay easy to review. Quirks that contradict nothing the code says about itself stay bug-faithful (e.g. mobdeaths/mobkills inverted naming); unsure -> keep the bug, note it.

## Verified port

If a given function is marked as being verified against 1stmud in its docstring (`[Verified: <date>]`), NEVER edit it without asking for explicit permission first.

Exception: targeted edits that resolve a documented TODO / "not ported" note toward 1stMud fidelity are allowed without asking. Keep the edit minimal, re-verify the function against the 1stMud source, and extend the tag (e.g. `[Verified: <old date>; <feature> added and re-verified <new date>]`). Anything beyond the documented TODO still needs explicit permission.

## PrimeSUD-only extensions -- `[PRIMESUD]` tag

Code with no 1stMud equivalent or intentional deviation marked `# [PRIMESUD]`. When porting from 1stMud, don't overwrite tagged items without checking if Prime variant differs on purpose.

When shipping a notable player-facing `[PRIMESUD]` feature or deviation (new system, balance change, UX behaviour -- not micro-fixes), add a one-liner to the matching section of root `FEATURES.md` in the same commit.

## Docstrings

Google-style: one-line summary, then `Args:` / `Returns:` / `Raises:` as needed; omit empty sections. For ported functions append `(cf. 1stMud <symbol> in <file>)` to summary (exact name + source file, e.g. `fight.c`); PrimeSUD-only functions and helpers should be explicitly marked [PRIMESUD].

## Documentation map

Root: `README.md`, `CLAUDE.md`, `DESIGN.md` (intentional deviations + settled decisions), `FEATURES.md` (curated what's-different-from-1stMud index for readers -- one-liners pointing at DESIGN.md/docs; add a line when shipping a notable [PRIMESUD] feature), `TODO.md` (loose ends). Everything else lives in `docs/`:

- 1stMud reference: `REFERENCE.md`, `COMMANDS.md`, `SKILLS.md`
- Device limits/perf: `BUILTINS.md`, `PRIME_STRING_FORMAT_BUG.md`, `PRIME_COLOURS.md`
- PrimeSUD systems: `AREA_FILES.md`, `PRIME_UX.md`, `FIXES.md`, `CROSS_RESETS.md`
- Status/audits: `PARITY.md` (1stMud parity sweep; engine 1.0 release-gate checklist)

Completed plan documents are deleted, not archived -- durable decisions get harvested into `DESIGN.md`/`TODO.md` first; full text stays in git history.

## Working style

- Assessment-shaped questions ("Possible?", "Worth it?", "Should we...?") want the assessment for review, not implementation. Propose the approach, wait for the go-ahead.
- Read `DESIGN.md`, and relevant reference docs before porting behavior from 1stMud.
- Provide sanity check and brief explanation of key decisions -- especially HP Prime constraints or PPL interop -- before complex coding.
- Minimal targeted changes. No surrounding refactor unless it is substantially cleaner or better; if so, raise for review.
- After code changes, run the desktop test suite: `python -m pytest -q` (CPython via `pc_shim/` device shims), plus `python tools/check_ascii_py.py` per pitfall 6.
- The suite runs with cwd == `src/` (pinned in `tests/conftest.py`), matching the device's flat filesystem and `run_source.py`, so runtime data files resolve by bare name. Tests must not chdir, and tools must resolve paths from `__file__`, not the cwd.
- Commit messages: Conventional Commits (`feat(scope): ...`, `fix:`, `docs:`, ...).
- Git flow: dev rebases onto main (never merge main into dev); main takes fast-forward merges from dev only. Keeps history linear.
- Unsure if Python feature is available on HP Prime? Ask for human check.
