# HP Prime Python — Built-in Type Reference

Methods and attributes verified on the HP Prime's MicroPython via `dir()`.
Use this to check what's available before reaching for a CPython-only feature.

Signatures are **not** verified — only name presence from `dir()` is confirmed.
Assume CPython semantics unless noted otherwise.
On-device timing records live in [PERFORMANCE.md](PERFORMANCE.md).

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
| `format`     | Present but BANNED on-device (heap corruption; CLAUDE.md pitfall 8) — concat only |
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
| `ljust`        | Left-justify in field of given width — use `util.pad_right(s, w)` instead |
| `maketrans`    | Build translation table for `translate`            |
| `removeprefix` | Strip prefix if present (Python 3.9+)              |
| `removesuffix` | Strip suffix if present (Python 3.9+)              |
| `rjust`        | Right-justify in field of given width — use `util.pad_left(s, w)` instead |
| `swapcase`     | Swap upper/lower case                              |
| `istitle`      | True if title-cased                                |
| `title`        | Title-case the string                              |
| `translate`    | Map chars through translation table                |
| `zfill`        | Pad with leading zeros                             |

> **`pad_left`/`pad_right` caveat:** they pad by actual byte length, not visual width.
> Strings containing `{X` colour codes have `len() > visual_width`, so byte padding
> will underpad. For coloured strings keep manual `s + ' ' * (width - color_len(s))`
> padding (see `info._pad_color`).

> **Physical HP Prime string formatting caveat:** `%` and `.format()` are BANNED on-device
> entirely — confirmed heap-corruption bugs on both G1 and G2, layout-dependent, can
> corrupt strings the formatter never touched. Concat + `util.int_str`/`num_str`/`sstr`
> only. Full findings in [PRIME_FIRMWARE_BUGS.md](PRIME_FIRMWARE_BUGS.md).

---

## Module inventory (menu-derived, unverified)

From the Python app's CMDS menu, as transcribed at
<https://udel.edu/~mm/hp/primePython/upython.html> (checked 2026-07-25).
**Menu-derived, not `dir()`-verified** — the menu is curated and may omit
real attributes or list menu-only entries. Its `str` list matches our
on-device `dir(str)` exactly, so accuracy looks good, but re-verify with
`dir()` before relying on anything load-bearing. No signatures/semantics.

Modules present (beyond the CLAUDE.md core of `hpprime`, `uio`, `cas`,
`math`, `urandom`, `gc`):

| Module | Contents (per menu) |
|:-------|:--------------------|
| `sys` | `argv`, `byteorder`, `exc_info`, `exit`, `implementation`, `maxsize`, `modules`, `path`, `platform`, `print_exception`, `stderr`, `stdin`, `stdout`, `version`, `version_info` |
| `ure` | `compile`, `match`, `search`, `DEBUG` — regex exists on device (MicroPython-subset syntax) |
| `ustruct` | `calcsize`, `pack`, `pack_into`, `unpack`, `unpack_from` |
| `ucollections` | `namedtuple`, `OrderedDict` (full dict method set), `deque` (**minimal: `append`/`popleft` only**) |
| `uhashlib` | `sha256` (`digest`, `update`) |
| `uerrno` | `errorcode` + errno constants |
| `utimeq` | `utimeq` (`push`, `pop`, `peektime`) |
| `micropython` | `const`, `heap_lock`/`heap_unlock`, `kbd_intr`, `mem_info`, `opt_level`, `pystack_use`, `qstr_info`, `stack_use` |
| `array` | `array` (**minimal: `append`/`extend` only**) |
| calc-specific | `arith` (gcd/isprime/...), `graphic` (draw_* wrappers), `linalg`, `cmath`, `matplotl` (page misspells it "maplotl") |

Still absent: `utime` (confirmed 2026-07-07 independently of this list),
`os`, `json`, `re` (only `ure`), `collections` (only `ucollections`).

Built-in container methods per the menu (unverified — see caveat above):

| Type | Methods |
|:-----|:--------|
| `list` | full standard set: `append`, `clear`, `copy`, `count`, `extend`, `index`, `insert`, `pop`, `remove`, `reverse`, `sort` |
| `dict` | full standard set: `clear`, `copy`, `fromkeys`, `get`, `items`, `keys`, `pop`, `popitem`, `setdefault`, `update`, `values` |
| `set` | full standard set incl. `difference_update`, `symmetric_difference`, etc. |
| `tuple` | `count`, `index` |
| `bytes` | same set as `str` (incl. `decode`; menu misspells `partition` as "parition") |
| `bytearray` | `append`, `extend` only per menu — likely understated, re-verify before use |
| `int` | `from_bytes`, `to_bytes` |
| `frozenset` | `copy`, `difference`, `intersection`, `isdisjoint`, `issubset`, `issuperset`, `symmetric_difference`, `union` |

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
