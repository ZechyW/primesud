# HP Prime Python — Built-in Type Reference

Methods and attributes verified on the HP Prime's MicroPython via `dir()`.
Use this to check what's available before reaching for a CPython-only feature.

Signatures are **not** verified — only name presence from `dir()` is confirmed.
Assume CPython semantics unless noted otherwise.

---

## `str`

Verified with `dir(str)` on-device.

### Available

| Method       | Notes                                                                     |
|:-------------|:--------------------------------------------------------------------------|
| `center`     |                                                                           |
| `count`      |                                                                           |
| `encode`     |                                                                           |
| `endswith`   |                                                                           |
| `find`       |                                                                           |
| `format`     | Caution: `{` conflicts with `{X` colour codes — use `%` formatting instead |
| `index`      |                                                                           |
| `isalpha`    |                                                                           |
| `isdigit`    |                                                                           |
| `islower`    |                                                                           |
| `isspace`    |                                                                           |
| `isupper`    |                                                                           |
| `join`       |                                                                           |
| `lower`      |                                                                           |
| `lstrip`     |                                                                           |
| `partition`  |                                                                           |
| `replace`    |                                                                           |
| `rfind`      |                                                                           |
| `rindex`     |                                                                           |
| `rpartition` |                                                                           |
| `rsplit`     |                                                                           |
| `rstrip`     |                                                                           |
| `split`      |                                                                           |
| `splitlines` |                                                                           |
| `startswith` |                                                                           |
| `strip`      |                                                                           |
| `upper`      |                                                                           |

### Not available (CPython only)

| Method         | CPython behaviour                                  |
|:---------------|:---------------------------------------------------|
| `capitalize`   | First char upper, rest lower                       |
| `casefold`     | Aggressive lowercase for case-insensitive matching |
| `expandtabs`   | Replace `\t` with spaces                           |
| `format_map`   | Like `format` but takes a mapping directly         |
| `isalnum`      | True if all chars are alphanumeric                 |
| `isascii`      | True if all chars are ASCII                        |
| `isdecimal`    | True if all chars are decimal characters           |
| `isidentifier` | True if valid Python identifier                    |
| `isnumeric`    | True if all chars are numeric                      |
| `isprintable`  | True if all chars are printable                    |
| `ljust`        | Left-justify in field of given width — use `"%-10s" % s` instead |
| `maketrans`    | Build translation table for `translate`            |
| `removeprefix` | Strip prefix if present (Python 3.9+)              |
| `removesuffix` | Strip suffix if present (Python 3.9+)              |
| `rjust`        | Right-justify in field of given width — use `"%10s" % s` instead |
| `title`        | Title-case the string                              |
| `translate`    | Map chars through translation table                |
| `zfill`        | Pad with leading zeros                             |

> **`ljust`/`rjust` workaround caveat:** `%` padding uses actual byte length, not visual width.
> Strings containing `{X` colour codes have `len() > visual_width`, so `"%-10s" % coloured_str`
> will underpad. For coloured strings keep manual `s + ' ' * (width - color_len(s))` padding.

> **Physical HP Prime string formatting caveat:** `%s` and `.format()` formatting have 
> a confirmed heap/timing-sensitive bug in some cases. See
> [PRIME_STRING_FORMAT_BUG.md](PRIME_STRING_FORMAT_BUG.md).

---

## Language / Syntax Restrictions

Features not supported by HP Prime's MicroPython (confirmed via `SyntaxError` at runtime):

| Feature | Workaround |
|:--------|:-----------|
| `{**a, **b}` dict unpacking in literals | `d = {}; d.update(a); d.update(b)` |
| `f"..."` f-strings | `"... %s ..." % x` — prefer `%` over `.format()` when colour codes are present, as `%` uses no `{` delimiters |
| `next(iter, default)` 2-arg form | `try: v = next(iter)` / `except StopIteration: v = default` |

Also note: `dict` iteration order is **not** guaranteed to match insertion
order (MicroPython dicts are plain hash tables, unlike CPython 3.7+). Never
rely on `dict.items()`/`keys()` order for user-facing output — keep an
explicit ordering tuple alongside the dict (e.g. `PC_RACE_ORDER` in
`races.py`) or `sorted()` the keys.

---

## OOP / subclassing (confirmed working)

Verified via smoke tests in `primesud.py` (June 2026).

| Feature | Notes |
|:--------|:------|
| `super()` (no-arg form) | Works — `super().__init__(...)` and `super().method()` both dispatch correctly |
| `**kwargs` in function signatures | Works — `def f(**kw)` and `f(**kw)` call-site spreading both work |
| Polymorphic dispatch from within base class | Works — `self.method()` inside a base-class method calls the subclass override when `self` is a subclass instance |

---

## `__import__` (confirmed working)

`__import__("module_name")` returns the module object, equivalent to `import module_name`. Verified June 2026 via dynamic area loading in `world.py`.

---

## File I/O performance (measured on-device)

Measured 05 Jul 2026 via the `debug time` channel on `do_help` (help.idx,
283 lines / ~7KB):

| Pattern | Cost |
|:--------|:-----|
| `f.readline()` per line | ~20 ms **per call** — 283 lines took ~5.9 s |
| One `f.read()` of the same file | ~40 ms total |
| `f.seek(offset)` + short read | ~40 ms (seek verified working on-device) |

Per-call file I/O overhead dominates everything else. For any file scanned
at runtime: read it in one `f.read()` (or one `seek` + bounded read) and
split/iterate in memory. Never loop `readline()` over more than a handful
of lines. Watch heap size — bulk reads are fine for KB-scale files, not
the 150KB help.dat.

---

## Text rendering performance (measured on-device)

Measured 21 Jul 2026 via `debug/render_bench.py` (synthetic 14-line
busy-room look, ~690 visible chars, 10 alternating passes, +-1ms
variance):

| Path | Cost |
|:-----|:-----|
| Per-line `tr.print` (pre-batch) | 591 ms |
| Batched `tr.print(list)` -> `print_lines` | 484 ms (-18%) |
| Glyph blit floor (`tml` per-char `strblit2`) | ~0.7 ms/char |
| Font recolour (`set_color` pixon loop) | ~2.5 ms/repaint |

Batching wins by collapsing per-colour-switch font repaints (~40 for a
colour-heavy screen) to one per distinct colour. The residual cost is
pure per-char glyph blitting. Since 21 Jul 2026 `print_lines` composes
the batch offscreen (`SCRATCH_GROB`) and blits once: total time is
unchanged, but the screen updates atomically -- perceived latency is
the single scratch->screen blit (`render_bench` "blit-only" row)
instead of a visible char-by-char crawl.

---

## Keyboard input semantics (measured on-device)

Probed 06 Jul 2026 on physical Prime G2 via `debug/keydrop_probe.py`
(see git history for probe versions and raw logs):

| Mechanism | Semantics |
|:----------|:----------|
| `hpprime.keyboard()` | Instantaneous hardware bitmask. A press+release entirely inside a long computation is **invisible** — edge-detection alone drops those keys. |
| PPL `GETKEY` (via `hpprime.eval`) | Drains a firmware press-event FIFO: **depth 4, drops newest when full**, chronological (modifier combos like Shift-then-digit arrive in order), no hold auto-repeat, survives long pure-Python busy loops. Returns -1 when empty. **Codes equal `keyboard()` bit indices** (verified 10/10 across Esc/Enter/Bksp/arrows/Shift/Alpha/letter/digit/fn row). |
| `cas.get_key()` | Reads the **same firmware queue** as GETKEY; returns instantly when an event is buffered, else blocks until the next press. Queue population lags one firmware poll behind the `keyboard()` bitmask — pairing bitmask edge-detect with `get_key()` (as base `tml.read_key` does) can swallow a keystroke. |

`src/tml_prime.py` `_pump_keyboard` builds on this: presses from GETKEY
drain, modifier hold state reconciled from the live bitmask (a modifier
tapped inside a computation never produces a release edge and would
otherwise stick).

---

## Touch input semantics (measured on-device)

Probed 07 Jul 2026 on physical Prime G2 via `debug/touch_probe.py`
(v1-v3; see git history for probe versions and raw logs):

- `hpprime.mouse()` returns `((x, y), ())` while touched, `((), ())`
  when idle — test the first tuple for truthiness before indexing.
  Second slot stayed empty (no second pointer observed).
- Position updates only every **~16ms (60Hz)**, no matter how fast you
  poll — consecutive `mouse()` reads within a frame return the same
  coordinates. Anything derived from position deltas (e.g. swipe
  velocity) must sample at frame cadence, not loop cadence: per-loop
  sampling sees `dy=0` between frames and px-level jitter over ms-level
  `dt` explodes into +/-1000s px/s spikes.
- **GETKEY corrupts touch state**: a PPL `GETKEY` call landing on a
  touch-release latches `mouse()` into a garbage down-state of
  `(2147483647, 0)` (INT32_MAX) for **>1s**, during which real touches
  do not register at all. Without GETKEY in the loop, lifts are clean
  (no stale/garbage samples, no stuck pointer). Consequences:
  - never call GETKEY unconditionally in a polling loop that coexists
    with touch input — gate it on `keyboard()` bitmask activity
    (`src/tml_prime.py` `_pump_keyboard`);
  - filter `mouse()` reads through a sanity bound (`0 <= x < 1000`)
    and treat the sentinel as lifted (`_touch_point`).
- PPL `WAIT` per iteration is harmless to touch state.

Per-call costs (same probe): `hpprime.eval` of `GETKEY`/`Ticks` ~0.3ms,
`keyboard()`/`mouse()` ~0ms, `WAIT(0.001)` ~5ms actual. `utime` is NOT
importable on-device despite older notes listing it.

---

## Heap size / module import cost (measured on-device)

Measured 06 Jul 2026 via `debug/mem_footprint.py`, fresh Python session
(imports are cached per session — a cached import costs ~0 and reports
nothing useful):

- Baseline `gc.mem_free()`: **~8.19 MB**. NOTE: heap size is a
  calculator-side setting — **stock default is 1 MB**; this device is
  configured up to 8 MB (works decently so far). Don't design against
  the 8 MB figure: stay conservative with heap/stack where appropriate
  (CLAUDE.md constraints still apply), and keep the game viable near the
  1 MB default — the ~119 KB of table imports fit there, with far less
  slack.
- Import costs: `config`+`races` 41 KB (109 ms), `skills_table` (149
  skills) 58 KB (180 ms), `classes` 11 KB (28 ms), `groups` 9 KB (30 ms).
  Total ~119 KB, leaving ~8.07 MB free.
