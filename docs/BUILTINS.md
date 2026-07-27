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
| `swapcase`     | Swap upper/lower case                              |
| `istitle`      | True if title-cased                                |
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

## Area load performance (measured on-device)

Measured 25 Jul 2026 via `debug/loadprobe.py` (standalone app, full game
modules imported, ~7.1MB free at start). Phases of `world._load_area`:
read (one `f.read()`), exec (compile + build the def dict tree), reset
(mob/object spawning via `reset_area`), plus the cost of a `gc.collect()`
run just before the load.

| Area (file size) | total | read | exec | reset | gc | heap+ |
|:-----------------|------:|-----:|-----:|------:|---:|------:|
| pestates (4KB), fresh heap | 20ms | 2 | 18 | 0 | 73 | 10KB |
| catacomb (61KB), fresh heap | 683ms | 20 | 467 | 192 | 73 | 400KB |
| newthalos (265KB), fresh heap | 6243ms | 233 | 2658 | 3754 | 79 | 2.4MB |
| newthalos reload, pressured heap, gc first | 4307ms | 237 | 2812 | 1620 | 132 | 2.3MB |
| newthalos reload, pressured heap, no gc | 4813ms | 238 | 2418 | 1631 | 0 | — |

Conclusions:

- Reset dominates first loads (60% on newthalos); eviction reloads reset
  ~2.1s cheaper (delta replay spawns less). exec is ~45% and stable across
  heap states; read is noise. Load time scales roughly linearly with file
  size (~2.4ms/KB fresh).
- `gc.collect()` immediately before the load is a net win: 73-132ms cost
  buys ~500ms on a big-area load at pressured heap (~375ms net); worst
  case ~+75ms on a tiny area. `_load_area` now collects unconditionally.
- A big area costs ~2.4MB resident heap; 15 loaded areas left 2.3MB free,
  so the `AREA_CACHE_MAX` eviction cap is load-bearing.
- A fresh load's reset number can include neighbours: cross-area resets
  trigger `_ensure_area` inside the reset drain, so the pulled area's full
  read+exec+reset lands there (newthalos pulls midgaard).

### Reset-phase breakdown (measured 25 Jul 2026, `debug/resetprobe.py`)

newthalos reload reset went 1050ms -> 510ms (-51%) across three fixes;
`create_mobile` micro (50x, one template) went 3160us -> 2580us per call:

| Fix | Saving |
|:----|:-------|
| `_mob_count_maps`: one O(chars) walk + local increments replaced per-M-reset full `world.chars` scans (271 M-resets x 2 scans = ~73k dict iterations on newthalos) | ~270ms/reset |
| `_RACE_CACHE` in `create_mobile`: `race_lookup` scans RACE_TABLE lowering every key (~1.2ms/call on-device, dict order is hash order in MicroPython so "Human" is not necessarily early) | ~275ms/reset |
| `create_mobile` merge-into-base diet (~27 fewer allocs/mob) | ~0 at light probe heap; kept -- allocs cost ~14x more at full game heap (see above) |

Remaining `create_mobile` cost: `_char_base` 45-key dict literal build =
880us; `dict(d)` shallow copy of the same dict is *slower* (1720-2400us),
so building via copy-a-frozen-base loses -- per-key insert dominates, not
the container allocs. Next cut would be redesigning the instance dict
(fewer keys / deferred defaults) for maybe ~150ms/area -- parked as
diminishing returns.

---

## Text rendering performance (measured on-device)

Measured 21 Jul 2026 via `debug/render_bench.py` (synthetic 14-line
busy-room look, ~690 visible chars, 10 alternating passes, +-1ms
variance; full game modules loaded, i.e. in-game heap):

| Path | Cost |
|:-----|:-----|
| Per-line `tr.print` (pre-batch) | 596 ms |
| Batched offscreen compose, str glyph loop (superseded) | 465 ms |
| Batched offscreen compose, alloc-free glyph loop | **156 ms (-74% vs per-line)** |
| Perceived transition of the offscreen path (final blit) | ~2 ms |
| `strblit2`, char-sized, raw constant-arg loop | **10 us/call, heap-flat** |
| `pixon` raw loop | 4-6 us/call, heap-flat |
| Per-char glyph draw via per-pixel `pixon` (avg 9 fg px) | 46 us/char -- rejected, loses to the 10 us char blit |
| Font recolour, per colour *switch* (never per char): `set_color` pixon loop (~1037 fg px) / `reset_color` full-grob strblit2 | 3.6 / ~2.5 ms per call (PRIME_COLOURS.md sec. Cost breakdown) |
| **One small heap alloc** | **~35 us standalone -> ~490 us at full game heap** |

The native draw calls were never the bottleneck: all ~690 char blits
of a busy screen cost ~7 ms, recolours ~20 ms, final blit ~2 ms. The
batch cost is Python-side **allocation**: a small alloc costs ~490 us
with the full dist live vs ~35 us standalone (14x), while zero-alloc
native calls stay flat. `gc.disable()` around the pass changes
nothing, so it is the allocator's scan over the big live heap, not
amortized collections (`gc.threshold` exists on-device but is
irrelevant to this). Measured via render_bench's noblit pass, where a
`lambda *a: None` stand-in -- one tuple alloc per call -- made the
pass ~8x SLOWER than doing the real native blits.

Consequences for hot-path code: on a loaded heap, one avoided
allocation buys 49 native blit calls. Iterate `seg.encode()` (ints,
no alloc) instead of a str (one 1-char str alloc per char); avoid
slices, `%` formatting, and tuple churn in per-char loops.
`terminal.print_lines` composes with an int-keyed glyph-offset map
for this reason (465 -> 156 ms). The residual 156 ms is ~30 ms native
draw + ~200 remaining allocs in wrap/group. Benchmark rendering with
the full dist present or the numbers flatter (same code measured
2.4-3x faster standalone).

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

- Baseline `gc.mem_free()`: **~8.19 MB** on the test device with an enlarged
  heap. PrimeSUD cannot run within the stock 1 MB, but no exact minimum is
  claimed: usable headroom varies with firmware and loaded content and must
  be checked on-device. Prefer the smallest heap size proven stable, keep
  heap use as low as practical, and do not treat the test device's capacity
  as a design budget.
- Import costs: `config`+`races` 41 KB (109 ms), `skills_table` (149
  skills) 58 KB (180 ms), `classes` 11 KB (28 ms), `groups` 9 KB (30 ms).
  Total ~119 KB, leaving ~8.07 MB free.

## G1 memory-corruption bug under big-string + alloc churn (investigation, 27 Jul 2026)

Sessions on the physical G1 die stochastically at zones of sustained
small-allocation churn, and the death rate rises sharply when 16/32 KB
strings were built in the same session. Measured with
`debug/save_bench.py` across many controlled runs (clean pool =
on+symb checkpoint restore before each):

- **Symptom spectrum, all at the same code zones**: hard reset; an
  impossible Python `TypeError` (`'list' object is not an iterator` on
  a `for` over a healthy list -- non-fatal, repeatable within the
  session); an uninterruptible stall (native call never returns; the
  On key cannot raise KeyboardInterrupt inside native code).
- **Acquitted by controlled runs**: `HVars` interop (a zero-HVars run
  reset on a clean pool; 22 8 KB HVars calls/session run clean),
  USB/Connectivity-Kit attachment, plain `ppleval` volume (100+
  `Ticks` calls fine), big *bytes* allocations (247 x 32 KB clean,
  twice), `str(int)` conversion, gc-call interplay, bad RAM (7.6 MB
  pattern-verified twice), heap size config, session residency.
- **Convicted (bigloop bisect)**: the tight cycle [fresh medium/large
  string alloc -> drop -> ~1000-small-alloc storm -> collect] kills
  within ~3 iterations, at 8 KB strings just as at 16/32 KB
  (`both`/`both8k` kinds).  Either ingredient alone is clean: concat
  chains + collects with no storm survived ~60+ trials (`bigonly`),
  storms with no fresh big strings survived ~50 passes.  Fresh ~8 KB
  allocs *separated in time* from storms also ran clean -- the
  interleaving is the trigger, and repetition rate sets the death
  rate.  This is the real save path's exact shape ("~".join payload +
  serialize storm + gc_collect per autosave): the game's occasional
  G1 crashes are this bug at today's payload size, rate-limited only
  by saves being minutes apart.
- **Stochastic**: byte-identical runs on clean pools split
  dead/clean.  Iterator-slot type confusion plus stochastic behaviour
  under churn fits a GC root-scan defect (live object collected when a
  collection fires at an unlucky VM state, block reused; stale read =>
  TypeError, stale write => corruption/reset/stall) -- working
  hypothesis, not confirmed.
- **Any collect over mixed churned garbage is the trigger**
  (`chunkedng`/`autogc` bisects): the cycle minus its explicit collect
  ran clean exactly as long as no collect happened at all (20-iter
  sessions, heap never filled), and died the moment heap exhaustion
  forced the first *auto*-collect (300-iter run, dead at ~iter 33
  where free hit zero).  Explicit-vs-auto is irrelevant; what matters
  is the garbage composition the collect walks: a few big uniform
  blocks is safe (mem_soak forced ~243 auto-collects clean; `bigonly`
  60+ explicit collects clean), fragmented mixed small+medium garbage
  from a serialize-shaped storm is a ~25-30%-per-collect death roll.
  Every collect is a dice roll weighted by churn since the last one.
  Mitigation is therefore statistical, not absolute: do not add
  explicit collects right after churn bursts (the save path's opening
  `gc_collect()` was a guaranteed worst-case roll per save -- earlier
  "may be load-bearing protection" guess in this file was backwards),
  keep hot-path garbage small and uniform (alloc diet), and rely on
  headroom to keep collects rare.

Consequences for game code until better understood: keep single-string
builds at or under ~8 KB (the save payload measures 7990 B mid-game and
grows with play -- chunk it before it crosses); keep alloc churn low in
hot paths (already policy); prefer explicit `gc.collect()` at
shallow-stack safe points ahead of unavoidable churn bursts (the
`gc_collect()` opening `_serialize_world` may be load-bearing crash
protection, not just perf hygiene -- do not remove it on timing grounds
alone).

Related community-documented PPL parse bug (unrelated mechanism, same
fragile bridge): numeric literals with a plus-sign exponent (`2e+1`)
error out in `hpprime.eval`, and MicroPython float-to-string can emit
exactly that form -- never `str()` a float into a PPL expression
(PrimeSUD sends only ints). See <https://udel.edu/~mm/hp/primePython/>.

## Save-path primitive costs (G1, measured 27 Jul 2026)

`debug/save_bench.py` with a real 7990 B / 173-line / 965-token save
payload, N=5, clean pool:

| Segment | bare | +2.6 MB ballast |
| --- | --- | --- |
| `gc.collect()` | 78-84 ms | 186-198 ms |
| build (str()+append+join line loop) | 100-240 ms* | same as bare |
| `"~".join(lines)` | 1-2 ms | same |
| HVars set (8 KB) | 9-10 ms, linear ~1.1 ms/KB | same |
| HVars get + compare | 3-4 ms | same |
| file write (open+write) | 9-13 ms | same |

\* Build cost swung 240 ms -> 101 ms between sessions with identical
code and payload -- allocator cost is highly sensitive to heap
*composition* (what else is live/fragmented), not just live bytes:
2.6 MB of list/str/tuple ballast changed build not at all while
doubling `gc.collect()`. Do not extrapolate probe numbers to the game;
instrument in-game for optimization decisions. Implication for the
~1 s in-game save: serialization allocs + `gc_collect()` dominate;
HVars and file I/O are negligible.

## Session / memory behaviour (G1, measured 27 Jul 2026)

`debug/mem_soak.py` (fill heap with 32 KB pattern chunks to
MemoryError, verify twice) plus observed session behaviour:

- The configured 8 MB heap is fully backable: 7904 KB filled, clean
  MemoryError at the boundary, zero pattern mismatches over two 7.6 MB
  verify passes. No bad RAM in the heap range.
- Alloc churn at a ~full heap is safe: 243 iterations of (32 KB alloc +
  compare) under ~130 KB headroom, one forced full-heap collect per
  iteration (~67 ms each), survived twice.
- Sessions are deterministic: two runs (fresh restore vs 'Clear'
  softkey re-run) matched `gc.mem_free()` at start to the byte and all
  fill checkpoints. The Python app rebuilds its heap fully per run;
  there is no cross-session depletion or damage at the Python level.
- Small run-to-run wobble in *post-collect* free numbers (16 B .. one
  32 KB block) is conservative-GC pinning: stale C-stack/register words
  can pin dead blocks through a collect. A dead 32 KB string surviving
  a collect is normal, not a leak.
- The Python app has no clean exit; it stays resident (holding its
  whole heap carve-out) until an on+symb reset. While resident, the
  Connectivity Kit fails with a system-level "insufficient memory" --
  close the app (reset) before kit transfers. This is pool occupancy by
  a resident app, not a leak: gameplay itself is unaffected.
- The Prime executes every `.py` in an appdir at app start -- keep one
  probe per debug appdir, and expect module-level code in *any* shipped
  file to run.
