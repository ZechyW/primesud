# PrimeSUD — Colour Print Performance

Findings from benchmarking the colour print path (June 2025).
All timings on a physical HP Prime G1. N=100 per run.

---

## Test strings

Both strings are exactly `TERMINAL_COLS = 64` visible characters wide, so neither
triggers wrapping overhead — the only variable is the colour processing.

**Coloured** — equivalent to `_row(_stat('Strength', 18), _val('Level', 1))`:

```
{W|{x {cStrength     : [{w18/18{c]{x       {W|{x {cLevel        : [{w          1{c ]{x {W|{x
```

Raw length: 92 chars (64 visible + 28 colour-code bytes = 14 codes × 2).
Colour operations emitted per print:

| Code sequence | Operation | Count |
|---------------|-----------|-------|
| `{W`, `{c`, `{w`, `{c`, `{W`, `{c`, `{w`, `{c`, `{W` | `set_color` (pixon loop, ~1037 px) | 9 |
| `{x` followed by text | `reset_color` (strblit2 full grob) | 4 |
| text segments | `_orig_print` calls | 13 |

**Plain** — `_MACRO_SEP` exactly:

```
+--------------------+--------------------+--------------------+
```

Raw length = visible length = 64 chars. Takes `_CC not in text` fast path; no colour
processing at all.

---

## Benchmark results

### 1 — Colour vs plain (`tr.print`)

| Line | ms / 100 | ms / call |
|------|----------|-----------|
| Coloured (score row) | 10415 ms | **104 ms** |
| Plain (macro sep)    |  1794 ms |  **18 ms** |
| Ratio                |          | **5.8×**   |

Practical impact: `do_score` has ~15 coloured lines → ~1.5 s display time.

### 1b — Same, after `color_wrap` fix (benchmark 3)

| Line | ms / 100 | ms / call |
|------|----------|-----------|
| Coloured (score row) |  7473 ms |  **74.7 ms** |
| Plain (macro sep)    |  1801 ms |   **18 ms** |
| Ratio                |           | **4.15×**  |
| Saved vs baseline    |  2942 ms  | **~29 ms/line** |

`do_score` display time: ~15 × 74.7 ms ≈ **1.12 s** (was ~1.56 s).

### 3 — Colour-first `print_xy` prototype (benchmark 4)

Instead of rendering left-to-right (set_color on each transition), parse the string
into colour-grouped `(colour, x, segment)` runs, then render one colour at a time:
one `set_color`/`reset_color` per distinct colour, then `print_xy` per segment, then
`_put_char('\n')` to advance the cursor and trigger any scroll.

For the test string: 4 distinct colour states (default, white, teal, silver) →
**4 state changes** instead of 13 (9 set_color + 4 reset_color).

| Variant | ms / 100 | ms / call |
|---------|----------|-----------|
| Current (post color_wrap fix) | 7330 ms | 73.3 ms |
| Colour-first prototype        | 3227 ms | **32.3 ms** |
| Saved                         | 4103 ms | **~41 ms/line** |

`do_score` display time: ~15 × 32.3 ms ≈ **0.48 s** (was ~1.12 s, ~1.56 s originally).
Colour-to-plain ratio: **1.8×** (was 4.15×, 5.8× originally).

### 4 — First colour-first implementation: `color_parse_runs` + grouping loop

Implemented `color_wrap_full` and `color_parse_runs` in `colors.py`; wired into
`_wrapped_print`. Benchmark showed no improvement over pre-colour-first baseline:

| Variant | ms / 100 | ms / call |
|---------|----------|-----------|
| Implementation (full)    | 7142 ms | 71.4 ms |
| Parse+group only (no render) | 3557 ms | 35.6 ms |
| Rendering only (full − parse+group) | 3585 ms | 35.9 ms |

**Root cause:** `color_parse_runs` uses a 92-iteration char-by-char Python loop +
creates an intermediate `runs` list (13 `.append()` calls, 13 `''.join()` calls,
13 tuple allocations). A separate grouping loop iterates runs again. Total parse+group
overhead ≈ 3557 ms — essentially equal to rendering cost, negating all colour-first
savings vs the original 7330 ms baseline.

The prototype achieved 3227 ms because it used pre-computed hardcoded groups (zero
parsing overhead). The general implementation needs to match that by eliminating the
Python char loop.

### 5 — Inline split+group (final implementation)

Replaced `color_parse_runs` call + separate grouping loop with a single inline pass
using C-level `str.split(_CC)`. Builds `colour_order` and `groups` directly in one
loop over 15 parts (vs 92-char Python loop + separate grouping pass). No intermediate
`runs` list; no function-call overhead.

Sanity-check benchmark (inline loop standalone, bypassing `_wrapped_print` wrapper):

| Variant | ms / 100 | ms / call |
|---------|----------|-----------|
| `color_parse_runs` + group (v2) | 7230 ms | 72.3 ms |
| Inline split+group+render (standalone) | 4376 ms | 43.8 ms |

Final benchmark through `_wrapped_print` (includes join, capitalise, fast-check overhead):

| Variant | ms / 100 | ms / call |
|---------|----------|-----------|
| Colour (inline split) | 4709 ms | **47.1 ms** |
| Plain                 | 1800 ms |  **18.0 ms** |
| Ratio                 |          | **2.62×**  |

`do_score` display time: ~15 × 47.1 ms ≈ **0.71 s** (was ~1.56 s originally).

**Why not at prototype speed (32.3 ms):** The remaining 14.8 ms/line gap is the
irreducible cost of runtime parsing — `str.split`, 15-part Python loop, dict/list
allocation, 13 tuple allocations per call. A cache could close this gap but hit rate
would be low in practice (score rows contain live stat values; combat/room output
varies widely). Accepted as the stopping point.

### 2 — Function call overhead (`_orig_print` directly)

Same 64 visible chars, printed as 1 call vs 13 calls (matching the exact segment
breakdown of the colour path).

| Variant | ms / 100 | ms / call |
|---------|----------|-----------|
| 1 × `_orig_print(full_line)` | 2853 ms | 28.5 ms |
| 13 × `_orig_print(segment)` | 3517 ms | 35.2 ms |
| Overhead of 12 extra calls  |  664 ms | **6.6 ms total ≈ 0.55 ms/call** |

Function calls are a minor contributor — only ~7 ms of the 86 ms colour gap.

---

## Overhead breakdown (coloured vs plain, per line)

Final implementation: 47.1 ms coloured / 18.0 ms plain = 29.1 ms gap (2.62×).
Of that gap, ~14.8 ms is runtime parse+group overhead (irreducible without caching);
the remaining ~14.3 ms is 13 `print_xy` calls vs the single `_orig_print` in the
plain fast path — irreducible without tml changes.

Pre-colour-first breakdown (74.7 ms coloured / 18 ms plain = 56.7 ms gap):

| Source | Estimated cost | Notes |
|--------|---------------|-------|
| 9 × `set_color` (pixon loop, ~1037 px) | ~32 ms | 3.6 ms/call (precomputed coords) |
| 4 × `reset_color` (strblit2 full grob) | ~10 ms | strblit2 is native; faster than pixon for this |
| Python loop in `_wrapped_print` (15 parts) | ~7–10 ms | conditionals, dict lookups, flag updates |
| 12 extra `_orig_print` calls | ~7 ms | confirmed by benchmark 2 |

---

## Failed optimisation: pixon-based `reset_color`

Hypothesis: replace the `strblit2` full-grob copy in `reset_color` with the same
targeted pixon loop used by `set_color` (paint only the ~1037 precomputed fg pixel
coords back to `_font_fg`).

Result: **worse** — 11626 ms vs 10415 ms for N=100.

Conclusion: `strblit2` is a native C-level memcpy and completes in well under 3.6 ms,
faster than 1037 Python-level `pixon` calls even though it copies the whole grob.
The Python call overhead dominates once you enter that loop.

---

## Applied optimisation: skip unnecessary `color_wrap` call

The original check in `_wrapped_print`:

```python
lines = [text] if len(text) <= _cols else color_wrap(text, _cols)
```

used **raw** length. For our coloured line: raw=92 > 64=`_cols`, so `color_wrap` was
called and `_wrap_raw_index` did a full Python char-by-char scan over 92 chars — only
to conclude the line fits and return `None`. Cost: **~29 ms per print**.

Fix: estimate visible length via C-level `str.count`, with a `{{` guard (the
count-based formula undercounts visible chars for `{{` escapes, which could
incorrectly skip wrapping for lines that need it):

```python
lines = ([text] if len(text) - 2 * text.count(_CC) <= _cols
                   and '{{' not in text
         else color_wrap(text, _cols))
```

Result: **2942 ms saved over N=100** (29 ms/line). Colour ratio drops from 5.8× to 4.15×.

---

## Current implementation: colour-first rendering

### Design

```
_wrapped_print
  ├─ fast path (_CC not in text): unchanged — _orig_print, no colour processing
  └─ colour path:
       color_wrap_full(text, cols)   →  [self-contained piece, ...]   (colors.py)
       for each piece:
           inline split+group pass   →  colour → [(x, seg), ...]      (_wrapped_print)
           for each colour group:
               set_color / reset_color once
               print_xy(x, row, seg) per segment
           _put_char('\n')
```

### `color_wrap_full(text, cols)` — `colors.py` ✓ implemented

Wraps `text` into lines of at most `cols` visible characters, like the existing
`color_wrap`, but ensures each continuation piece is **self-contained**: if the active
colour at a split point is non-default, the next piece is prefixed with that colour code.
The colour-first renderer treats every piece identically regardless of whether wrapping
occurred. Returns `[text]` (single element) when the line fits.

### `color_parse_runs(piece)` — `colors.py` ✓ implemented (utility only)

Char-by-char scan returning `[(colour_or_None, segment), ...]`. **Not called from the
hot path** — too slow (3557 ms/100 calls overhead). Retained in `colors.py` as a
utility / reference implementation.

### Inline split+group pass — `_wrapped_print`

Parse and build colour groups in one pass using C-level `str.split(_CC)`. Avoids:
- The `color_parse_runs` function call (global lookup + frame creation)
- The intermediate `runs` list (13 `.append()` + 13 `''.join()` + 13 tuple allocs)
- A separate grouping loop

`parts[0]` = text before any code. Each `parts[1:]` entry = `code_char + text` (or
empty for `{{` escape). `colour_order` list tracks insertion order so groups render in
first-seen sequence.

For each piece from `color_wrap_full`:
1. `parts = piece.split(_CC)` (C-level).
2. Single loop: decode code, update `current` colour, append `(x, seg)` to `groups[current]`.
3. Capture `row = tr.cursor_y`.
4. For each colour in `colour_order`: `set_color`/`reset_color` once, `print_xy(x, row, seg)` per segment.
5. `_put_char('\n')` to advance cursor and trigger scroll.

### What stays put

- Plain fast path (`_CC not in text`) — untouched.
- `set_color`, `reset_color` — untouched.
- `color_wrap` — untouched (used internally by `color_wrap_full`).

### Cursor / scroll notes

- `print_xy` does not update `cursor_x`/`cursor_y`.
- `_put_char('\n')` unconditionally does `cursor_y += 1` then `_end_of_screen_check` —
  no auto-wrap tracking, safe to call with `cursor_x` still at 0.
- Scroll (`_scroll_up` via `_end_of_screen_check`) fires correctly inside `_put_char`.

---

## Architecture notes

- `set_color(color)` — cache check first (`_current_fg`); miss paints ~1037 precomputed
  fg pixel coords via `pixon`. ~3.6 ms/miss, ~0 ms/hit.
- `reset_color()` — restores font grob via `strblit2` from `COLOR_GROB` (a full copy of
  the original `FONT_GROB` taken at init). Fast because native; no pixon loop.
- `_wrapped_print` fast path — `_CC not in text`: skips colour processing entirely,
  calls `_orig_print` 1–2 times. Plain lines use this exclusively.
- `_wrapped_print` colour path (v1, removed) — `text.split(_CC)` into parts, iterates,
  calls `set_color`/`reset_color` per code, calls `_orig_print` per text segment.
- `_wrapped_print` colour path (v2, failed) — `color_parse_runs` → group by colour →
  render. Parse+group overhead (3557 ms/100) negated colour-first savings.
- `_wrapped_print` colour path (v3, current) — inline `str.split` parse+group →
  colour-first `print_xy` render. Eliminates intermediate list, function call overhead.
  Result: 47.1 ms/line (2.62× plain), do_score ~0.71 s (was ~1.56 s).
