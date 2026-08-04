# HP Prime Performance Measurements

Durable on-device benchmark results and resulting engineering decisions.
Numbers are hardware-, firmware-, heap-, and workload-specific; each section
names its device and probe where known. Re-run on target hardware before
generalising a result, especially between G1 and G2.

## File I/O

Measured 05 Jul 2026 via the `debug time` channel on `do_help` (`help.idx`,
283 lines / ~7 KB):

| Pattern | Cost |
|:--------|:-----|
| `f.readline()` per line | ~20 ms **per call** -- 283 lines took ~5.9 s |
| One `f.read()` of the same file | ~40 ms total |
| `f.seek(offset)` + short read | ~40 ms (seek verified working on-device) |

Per-call file I/O overhead dominates everything else. For any file scanned at
runtime, read it in one `f.read()` (or one `seek` + bounded read) and
split/iterate in memory. Never loop `readline()` over more than a handful of
lines. Watch heap size: bulk reads are fine for KB-scale files, not the 150 KB
`help.dat`.

## Recommend scans (G1 + G2, measured 02 Aug 2026)

The `recommend` perf stream (rounds 1-5, via `debug/recommend_bench.py`
on a real L10 save; design in DESIGN.md sec. Lazy area loading) is the
canonical demonstration that **allocation cost, not I/O or row count, is
the on-device floor for file scans**: every text row parsed with
`split()` costs ~10-30 heap allocs at ~0.5 ms each at full game heap
(~13 ms/line), so index re-shapes that only cut row counts plateaued at
8 s. Binary fixed-layout records walked with raw byte arithmetic (zero
allocs per reject) removed the constant:

| Scan | Text index (G1) | gear.bin/foes.bin (G1) | (G2) |
|:-----|--------:|-------:|-----:|
| `recommend gear` summary | 8,012 ms | 194 ms | 85 ms |
| `recommend gear wield` | 3,024 ms | 164 ms | 67 ms |
| `recommend mobs` | 2,383 ms | 75 ms | -- |

Of the 194 ms summary, ~39 ms is I/O (one header read + one ~55 KB
record-region read + one string-table read); the scanner handles 1,890
records in ~155 ms, ~82 us/record. Winner display strings resolve from
a deduplicated string table in one read -- per-winner seek+read pairs
would have cost ~40 ms each. Device binary-read semantics (`"rb"`
returns str, char-counted sized reads) in docs/BUILTINS.md.

### Keyword index scans (G1, measured 02 Aug 2026)

The same recipe applied to the last two hot text indexes (mobs.idx /
objs.idx -> KX01 mobs.bin / objs.bin, `src/keyidx.py`; measured via
`debug/keyidx_bench.py`, log `keyidx_bench-1.log`). Name search is a
native `find()` sweep of a lowercased keyword blob with word-boundary
checks, so a miss never allocates at all; only confirmed candidates pay
the slice + `is_name` cost:

| Lookup | KX01 (G1) | Notes |
|:-------|----------:|:------|
| mob name hit ("guard", 50 records) | 287 ms | ~72 ms sweep + ~4 ms per candidate confirm |
| mob name miss | 72 ms | ~40 ms of it whole-file read (45 KB) |
| obj name hit ("sword", 45 records) | 302 ms | objs.bin, 1,358 records |
| `_mob_stats` full record walk | 110 ms | 1,003 records, 30-vnum counts dict |

Old text scans were never device-timed but shared the shape of the
measured 2.4 s foes.idx scan at ~1.6x the line count (~4 s class).
Candidate counts matched PC ground truth exactly, which also proves
firmware `bytes.find(needle, start)` honours its start argument
(keyidx guards against the alternative rather than hanging).

### paths.idx parse (G1, measured 05 Aug 2026)

`info._parse_index` is cached per session, but its first call -- the
first `path`/`run` command -- paid the full split()/int() parse of the
898-line index. Byte-walk rewrite (digit accumulation over raw bytes,
only route strings and interned direction chars allocate; text format
unchanged) measured via `debug/pathidx_bench.py` against a frozen
replica of the old parse, log `pathidx_bench-1.log`, real save loaded:

| Variant | min | avg (N=3) |
|:--------|----:|----------:|
| old split parse (frozen control) | 4,537 ms | 5,047 ms |
| byte-walk `_parse_index` | 751 ms | 758 ms |

6.7x; record tallies from both variants agreed exactly. Remaining
~750 ms is dominated by the real payload (727 seg tuples + route
strings and the dict/list builds), i.e. near the eager-materialise
floor. On desktop CPython the byte-walk is ~3x *slower* than split
(C-level `split`/`int` beat per-byte bytecode) -- irrelevant there, and
the inversion is expected; format stayed text because a binary index
would still pay the same payload allocation, saving only the digit
loops.

## Area loading

### Initial load probe (measured 25 Jul 2026)

`debug/loadprobe.py` ran as a standalone app with full game modules imported
and ~7.1 MB free at start. Phases of `world._load_area` were read (one
`f.read()`), exec (compile + build the definition tree), reset (mob/object
spawning), and a `gc.collect()` immediately before the load.

| Area (file size) | total | read | exec | reset | gc | heap+ |
|:-----------------|------:|-----:|-----:|------:|---:|------:|
| pestates (4 KB), fresh heap | 20 ms | 2 | 18 | 0 | 73 | 10 KB |
| catacomb (61 KB), fresh heap | 683 ms | 20 | 467 | 192 | 73 | 400 KB |
| newthalos (265 KB), fresh heap | 6243 ms | 233 | 2658 | 3754 | 79 | 2.4 MB |
| newthalos reload, pressured heap, GC first | 4307 ms | 237 | 2812 | 1620 | 132 | 2.3 MB |
| newthalos reload, pressured heap, no GC | 4813 ms | 238 | 2418 | 1631 | 0 | -- |

Findings:

- Reset dominates first loads (60% on New Thalos); eviction reloads reset
  ~2.1 s faster because delta replay spawns less. Exec is ~45% and
  stable across heap states; read is noise. Load time scales roughly linearly
  with file size (~2.4 ms/KB fresh).
- `gc.collect()` immediately before the load is a net win: 73-132 ms cost
  buys ~500 ms on a big-area load at pressured heap (~375 ms net);
  worst case is about +75 ms on a tiny area. `_load_area` now collects
  unconditionally.
- A big area costs ~2.4 MB resident heap; 15 loaded areas left 2.3 MB
  free, so the `AREA_CACHE_MAX` eviction cap is load-bearing.
- A fresh load's reset number can include neighbours: cross-area resets
  trigger `_ensure_area` inside the reset drain, so the pulled area's full
  read/exec/reset lands there (New Thalos pulls Midgaard).

### Full-game A/B (G1, measured 29 Jul 2026)

`debug/area_load_bench.py` v2 measured candidate changes inside the normal
PrimeSUD application heap. Startup initialized the terminal and world and
imported the normal pre-loop modules, but deliberately skipped save loading
and the game loop. Each result was checkpointed to `area_load_bench.log` and
shown onscreen outside the timed sections.

Raw captures: [`area_load_bench-1.log`](../debug/area_load_bench-1.log) and
[`area_load_bench-2.log`](../debug/area_load_bench-2.log).

Build and run the transfer-only probe with:

```text
python tools/build_dist.py --area-bench --zip bench
```

Each area was loaded once, unloaded, collected, then reloaded for every case.
The pressure pass held exactly `AREA_CACHE_MAX` (12) real areas before loading
New Thalos. `load_ms` includes `_load_area`'s existing opening collection,
file read/exec, merge, and reset. Heap deltas below compare `free0 - free1`;
they are endpoint measurements, not peak allocation.

#### Shared immutable flag dictionaries

The candidate replaced repeated all-True template flag dictionaries with
references to one dictionary per identical value within each area file.
Runtime mob/item mutations remain safe: constructors merge or copy template
flags into instance dictionaries before editing them (pinned by
`tests/test_area_load_bench.py`). Empty dicts are excluded: sharing them cost
bytes (`_F0` is longer than `{}`) and `{}` is the shape runtime code is most
likely to reach for with `setdefault`.

| Case | Baseline | Shared flags | Saving | Heap saved |
|:-----|---------:|-------------:|-------:|-----------:|
| pestates reload | 206 ms | 208 ms | -2 ms | 0 |
| catacomb reload | 2244 ms | 2123 ms | 121 ms (5.4%) | 3.6 KB |
| newthalos reload | 10759 ms | 9902 ms | 857 ms (8.0%) | 23.2 KB |
| newthalos, 12-area pressure | 11969 ms | 11019 ms | 950 ms (7.9%) | 23.3 KB |

The previous G1 pass measured 123, 858, and 974 ms savings for Catacomb,
New Thalos, and pressured New Thalos respectively. Near-identical repeats
make the large-area result strong rather than timer noise.

**Adopted:** normal `build_dist.py` builds now apply the transform to every
generated area. It avoids 4,980 duplicate dictionaries across the 50 area
files and removes ~48 KB from the minified area payload. `--area-bench` leaves
the normal target files unshared and emits separate `bench_` variants so the
A/B remains reproducible. `build_dist.py --check` executes both forms and
verifies transformed area payloads equal their source values exactly.

The measured savings above predate the empty-dict exclusion, which drops 238
of the shared dictionaries; the transform is otherwise unchanged.

#### Post-merge collection

Collecting after definitions merge but before reset reclaimed temporary exec
containers early. On New Thalos it left ~259 KB more free heap at the
end of the unpressured load, but cost 128 ms. Costs were 122 ms on Pestates,
134 ms on Catacomb, and 196 ms on pressured New Thalos. Combined with shared
flags, New Thalos still beat baseline by 748 ms unpressured and 775 ms under
pressure, but was 109-175 ms slower than shared flags alone.

**Not adopted:** the existing collection before `_load_area` remains. An
unconditional second collection slows every load. The candidate toggle was
removed from `world.py` after this measurement; re-add the two lines (drop
`_ns`, `gc.collect()` after the merge, before the reset queue drains) if a
device ever demonstrates load-time `MemoryError`. `free1` after reset is
GC-order-sensitive and must not be read as steady live-heap size.

#### Eviction order

Normal movement loads the destination first; `update_handler` runs
`maybe_evict` on the following pulse. Pathfinding similarly force-evicts
after its remote lookups. The benchmark compared that effective post-load
order with reserving one cache slot before the load:

| Strategy | Eviction | Load | Total | Final areas |
|:---------|---------:|-----:|------:|------------:|
| current post-load eviction | 277 ms after | 11990 ms | 12267 ms | 12 |
| pre-load eviction | 580 ms before | 12196 ms | 12776 ms | 12 |
| pre-load + shared flags + post-merge GC | 543 ms before | 11394 ms | 11937 ms | 12 |

**Not adopted:** pre-eviction was 509 ms slower than current behavior and did
not accelerate the subsequent load. The G1 still had ~6.2 MB free before
New Thalos, so removing one small LRU area supplied no useful headroom.
Current post-load eviction also lets its final collection reclaim loader and
reset garbage in the same pass.

Benchmark v1's pre-eviction rows are invalid: its pressure setup let cascade
loads overshoot the cap, so those rows start at 13 areas and the pre-evict
case finishes at 14 -- above the cap it was meant to be testing. V2 trims
cascades through production `maybe_evict` and resets `_last_evict_area`
between cases; its pressure cases start and finish at 12 areas. These results
are G1-specific until repeated on G2.

Bench v3 drops the post-merge-collection case along with the toggle it drove;
its remaining cases match the tables above.

### Reset-phase breakdown (measured 25 Jul 2026)

`debug/resetprobe.py` measured New Thalos reload reset falling from 1050 ms to
510 ms (-51%) across three fixes. `create_mobile` micro (50 calls, one
template) fell from 3160 us to 2580 us per call.

| Fix | Saving |
|:----|:-------|
| `_mob_count_maps`: one O(chars) walk + local increments replaced per-M-reset full `world.chars` scans (271 M-resets x 2 scans = ~73k dict iterations on New Thalos) | ~270 ms/reset |
| `_RACE_CACHE` in `create_mobile`: `race_lookup` scans `RACE_TABLE`, lowering every key (~1.2 ms/call on-device; dict order is hash order in MicroPython, so `Human` is not necessarily early) | ~275 ms/reset |
| `create_mobile` merge-into-base diet (~27 fewer allocations/mob) | ~0 at light probe heap; kept because allocations cost ~14x more at full game heap |

Remaining `create_mobile` cost: `_char_base` 45-key dict literal build is
880 us. `dict(d)` shallow copy of the same dict is slower (1720-2400 us), so
copying a frozen base loses; per-key insertion dominates, not container
allocation. Redesigning the instance dict (fewer keys/deferred defaults)
might save ~150 ms/area, but remains parked as diminishing returns.

## Text rendering

Measured 21 Jul 2026 via `debug/render_bench.py`: synthetic 14-line busy-room
look, ~690 visible chars, 10 alternating passes, +/-1 ms variance, full
game modules loaded.

| Path | Cost |
|:-----|:-----|
| Per-line `tr.print` (pre-batch) | 596 ms |
| Batched offscreen compose, str glyph loop (superseded) | 465 ms |
| Batched offscreen compose, allocation-free glyph loop | **156 ms (-74% vs per-line)** |
| Perceived transition of offscreen path (final blit) | ~2 ms |
| `strblit2`, char-sized, raw constant-arg loop | **10 us/call, heap-flat** |
| `pixon` raw loop | 4-6 us/call, heap-flat |
| Per-char glyph draw via per-pixel `pixon` (average 9 foreground pixels) | 46 us/char -- rejected, loses to the 10 us char blit |
| Font recolour, per colour *switch* (never per char): `set_color` pixon loop (~1037 fg px) / `reset_color` full-grob `strblit2` | 3.6 ms set / ~2.5 ms reset |
| **One small heap allocation** | **~35 us standalone, 490 us at full game heap** |

Detailed colour-path results live in
[`PRIME_COLOURS.md`](PRIME_COLOURS.md) sec. Cost breakdown.

Native draw calls were never the bottleneck: all roughly 690 character blits
cost ~7 ms, recolours ~20 ms, and final blit ~2 ms. Batch cost
is Python allocation: one small allocation costs ~490 us with the full
dist live versus 35 us standalone (14x), while allocation-free native calls
stay flat. `gc.disable()` changes nothing, so this is allocator scanning over
the large live heap, not amortized collections (`gc.threshold` exists
on-device but is irrelevant to this). The sharpest demonstration is
render_bench's noblit pass: swapping the real native blits for a
`lambda *a: None` stand-in -- one tuple allocation per call -- made the pass
~8x **slower** than drawing for real.

For hot paths, one avoided allocation buys ~49 native blit calls.
Iterate `seg.encode()` (ints, no allocation) instead of a string (one
one-character string allocation per character); avoid slices, `%` formatting,
and tuple churn. `terminal.print_lines` uses an integer-keyed glyph-offset map
for this reason (465 -> 156 ms). The residual 156 ms is ~30 ms native draw
plus ~200 remaining allocations in wrap/group. Benchmark rendering with full
dist residency; standalone numbers measured 2.4-3x faster.

## Heap size and module import cost

Measured 06 Jul 2026 via `debug/mem_footprint.py` in a fresh Python session.
Imports are cached per session, so a cached import costs ~0 and reports
nothing useful -- measure in a fresh session or not at all.

- Baseline `gc.mem_free()`: **~8.19 MB** on the test device with an
  enlarged heap. PrimeSUD cannot run within the stock 1 MB, but no exact
  minimum is claimed. Usable headroom varies with firmware and loaded content;
  prefer the smallest heap size proven stable, keep heap use as low as
  practical, and do not treat the test device's capacity as a design budget.
- Import costs: `config` + `races` 41 KB (109 ms), `skills_table` (149 skills)
  58 KB (180 ms), `classes` 11 KB (28 ms), and `groups` 9 KB (30 ms). Total:
  ~119 KB, leaving ~8.07 MB free.

## Boot import phase (G1, measured 02 Aug 2026)

Full G1 boot ~43 s = **37.2 s firmware auto-import phase** + 6.2 s
`load_world`. The firmware auto-imports every `.py` in the appdir in
reverse-alphabetical filename order (game starts when it reaches
`primesud.py`); a `zz_`-prefixed file sorts first and runs before
anything else is loaded — the bench slot used by
`debug/zz_import_bench.py` and the probes below.

- Costs are first-import closure attribution (module + not-yet-loaded
  deps charged to the first importer): `update` 20.1 s (pulls the game
  bulk: combat/handler/item/mob/player/quest/economy/debug), `mobprog`
  7.1 s (own 62 KB + `commands` closure), `training` 6.0 s
  (magic/info/inventory/game_state/skills_table wave), `world` 1.3 s,
  `recommend` 1.1 s, `shop` 0.9 s; everything else <0.3 s. The lazy
  import trio (mobprog/socials/namegen) buys nothing at device boot —
  the auto-import pass loads them regardless.
- **Minification is a null result**: the 52 % byte cut from
  `tools/build_dist.py` left the phase identical (37,207 vs 37,181 ms).
  Import cost is structure-bound (per-construct compiler allocs), not
  byte-bound. Minified payload kept anyway: resident heap 339 KB
  lighter.
- **Compile share is 98–99 %** (`zz_compile_probe`: combat 3,433 ms
  compile vs 12 ms exec). The phase is compiler allocs re-paid every
  boot. Compile cost per KB grows with heap occupancy (combat
  ~55 ms/KB early, mobprog ~96 ms/KB later) — compile is the alloc
  floor phenomenon.
- **`.mpy` precompilation is dead** (`zz_mpy_probe` +
  `zz_syspath_probe`, 02 Aug 2026): toy `.mpy` files (mpy-cross 1.9.4,
  bytecode v3, both unicode flag variants) fail with `ImportError: no
  module named` — the importer never stats them. `sys.path` is `[]`
  and appending to it changes nothing; `uos`/`os` absent; a
  runtime-written `.py` imports fine. HP's custom import hook scans the
  filesystem dynamically but is hardwired to `.py`. Unfixable from
  userland.

Conclusion: the ~37 s floor stands. Deferring modules out of
`.py`-space (ship as data, `compile()`+`exec()` on first use) only
moves the cost to a first-use stall, and the expensive closures
(update/mobprog/training) are all hot in the first minutes of play.

## Save path (G1, measured 27 Jul 2026)

`debug/save_bench.py` used a real 7990-byte, 173-line, 965-token save payload,
five repetitions, clean pool:

| Segment | Bare | +2.6 MB ballast |
|:--------|-----:|----------------:|
| `gc.collect()` | 78-84 ms | 186-198 ms |
| build (`str()` + append + join line loop) | 100-240 ms* | same as bare |
| `"~".join(lines)` | 1-2 ms | same |
| HVars set (8 KB) | 9-10 ms, linear ~1.1 ms/KB | same |
| HVars get + compare | 3-4 ms | same |
| file write (open + write) | 9-13 ms | same |

\* Build cost swung from 240 ms to 101 ms between sessions with identical
code and payload. Allocator cost is highly sensitive to heap composition
(what else is live/fragmented), not only live bytes: 2.6 MB of
list/string/tuple ballast did not affect build while doubling `gc.collect()`.
Do not extrapolate probe numbers to the game; instrument in-game for
optimization decisions. In the roughly 1 s in-game save, serialization
allocations and `gc_collect()` dominate; HVars and file I/O are negligible.

### Full-game save, post-cache (G1, measured 29 Jul 2026)

`debug/save_smoke.py` through the real game code on the real 23 KB
full-world save (`debug/save_smoke-1/-2/-3/-4.log`), `_serialize_world`
segment timing via the "save" DBG channel. Before caches: 11.7 s steady,
dominated by re-scanning every `_pending_room_items` token line (snap
5.6 s + sweep 4.5 s) and re-rendering every pending mob part
(ln.mob 750 ms). After `_PENDING_VNUM_CACHE` / `_SNAP_ENC_CACHE` /
`_PENDING_MOB_CACHE` (DESIGN.md sec. Item template snapshots,
"Save-path caches"): 879/881 ms steady (save_smoke-4.log), all in
genuinely-changing data -- ln.plr1 168 / ln.rle 113 / ln.plr2 255 /
ln.mob 10 / ln.room 246 / hvset 32, snap and sweep ~5 ms each.
(Segments split finer on 30/07 for the next diet -- plr1 into
plr1/pinv/plearn, plr2 into paff/wstate/stats, room into room/rpend --
and save_smoke.py now prints a per-prefix payload breakdown.)

Fine-grained run (save_smoke-5.log, G1, 30/07, 26.6 KB payload, 0 areas
resident): 937 ms steady = stats 250 (44 s.m. + 8 s.a. lines + gquest)
/ rpend 247 (102 pending-room passthrough lines) / rle 113 / pinv 70 /
plr1 55 / paff 52 / plearn 36 / hvset 36 / mob 12 / fwrite 17 / join 10
/ verify 11 / wstate 7 / room 0 / snap 4 / sweep 6. Warm-up save 1437 ms
(num_str cache, as before). Both hot segments are alloc-bound line
builds (~2.4-5 ms/line at ~0.5 ms/alloc), not data cost -- the cached
m= block builds one 7.7 KB line from 100+ parts in 12 ms.

### Save diet round 2 (G1, measured 30 Jul 2026)

Three caches from the smoke-5 attribution (DESIGN.md sec. Item template
snapshots, "Save-path caches" round 2): pending-room lines (identity),
kill-stat lines (value-pair -- the lists mutate in place), and the RLE
explored-mask encode (player-held, revisits never invalidate).

- All-pending config (save_smoke-6.log, same shape as smoke-5): 937 ->
  **373 ms** steady; rpend 247->2, stats 250->43 (residue is the gquest
  lines + dict walk), rle 113->1.
- 3 areas resident, 37 resident item rooms (save_smoke-7.log): **834 ms**
  steady. The caches hold (rpend 1 / stats 46 / rle 2), but live-data
  serialization takes over: ln.room 271 (37 rooms of per-item
  `serialize_item_token`, ~7 ms/room) and ln.mob 137 (live NPC position
  walk), plus honest snap 20 / sweep 36 with real foreign-item scans.
  First save after the loads: 2187 ms (cache warm-up, as always).

Uncached remainder is live data: player segments ~220 ms (plr1/pinv/
plearn/paff), room+mob ~410 ms when areas are resident, I/O floor
~80 ms. Room-item and mob-position caching would need dirty flags at
many scattered mutation sites (pickup/drop/loot/decay/resets; wander) --
parked as measure-first candidates, not clear wins: the ~0.83 s worst
case already runs with FIFO drains and a live echo preview.
Note: smoke-4/-5/-6 ran without `init_world()`, so their snap/sweep
numbers used empty vnum ranges (foreign-item semantics slightly off,
~5 ms class); smoke-7 is the faithful configuration.
`load_world` prewarms the pending-token cache (7.7 s -> 12.3 s load), so
the first save skips the one-time 4.5 s token rescan; its remaining
overhead (1333 ms, spread evenly across the ln.* segments) is
`util.num_str` cache warm-up, not a cache miss.

The ~880 ms save is synchronous, so autosaves (tick-timer and
after-kill `save_pending`) are deferred while the player is fighting and
fire on the first non-fighting pulse (`game_loop` in primesud.py).
Mid-fight saves had negative value anyway: mob HP/fight state never
persists, so they only snapshotted the player's transient combat damage.
Since 30/07 the save is no longer keyboard-dead: `_serialize_world`
drains the firmware FIFO at each segment boundary (worst pump gap = the
largest single segment, ~270 ms steady post-diet, sec. Save diet round
2). Typed keys replay after the save, and boundaries whose drain queued
new keys redraw the prompt with an echo preview (`_save_echo`), so the
echo lags by at most one segment rather than the whole save. With the
preview keeping typing responsive, the per-save `[Saving...]` scrollback
notice was removed as noise (31/07); `load_world` prints a
`[Restoring save data...]` notice over its parse + prewarm stretch
instead.

### Save-path heap churn and gated collect (G1, measured 31 Jul 2026)

`debug/save_smoke.py` phases C/D (`save_smoke-8/-9/-10.log`), real 31/07
save (31,082 B payload):

- Each save burns ~420 KB of heap (~13x payload amplification): 307 KB
  with the smaller -8 save, 418-434 KB with the 31/07 save (49 resident
  item rooms). Free falls monotonically across saves -- the serialize
  takes zero collects of its own.
- The garbage is fully transient: one explicit collect reclaimed
  4,351,056 B in ~270 ms, restoring free above the post-load baseline
  (identical result in -9 and -10). No leak, no drift across cycles.
- Undirected, the reclaim was an auto-collect at whatever allocation hit
  the empty heap -- every ~14 back-to-back saves on the bench, or
  mid-gameplay in real play. 12 such collects across -9/-10 (hvset x6,
  sweep x1, mid-churn gameplay-shaped x2, explicit x2, between-saves x1)
  all ran clean: `int_str`/`sstr` save garbage is not the convicted
  `str(int)` shape (docs/PRIME_FIRMWARE_BUGS.md sec. Remediation status).
- Since 31/07 `_serialize_world` ends with a threshold-gated collect
  (`_GC_FREE_FLOOR` = 1.5 MB, timing mark `gcpost`): fires ~once per 11
  autosaves (~22 min), hides the ~270 ms inside the save stall, and
  keeps enough headroom (next save ~430 KB + ~2 min of gameplay churn)
  that random mid-gameplay auto-collects should essentially never fire.

### Item-snapshot device gates (G1, measured 30 Jul 2026)

`debug/snapshot_gates.py` (`debug/snapshot_gates-1.log`), real save, all
three remaining hardware gates from the snapshot design PASS:

- **Heap across travel/eviction:** 13-area tour x 4 cycles at
  `AREA_CACHE_MAX` 12; cycle-end `mem_free` after collect settled
  5336832 -> 5333088 -> 5332976 -> 5332928 -- a converging warm-up
  tail (-3744/-112/-48 B), no downward drift. Cycle cost ~100 s
  (13 loads + 13 evictions once the tour exceeds the cap; area load
  cost itself is the known multi-second item, sec. Area loading).
- **Stale-revision corrective load:** exactly one owner-area load
  (869 ms), vnum resident after, snapshot entry pruned.
- **Snapshot obj prog from unloaded owner:** fires via the
  `_run_oprog` fallback in 85 ms; owner area never loads.
- Save over the post-tour state: 4161 ms -- first save after mass
  eviction repopulates the pending caches for every newly-evicted
  area, then steady-state economics apply again.

### Boot load phase split (G1, measured 02 Aug 2026)

`debug/loadworld_bench.py` decomposed `load_world()`'s 13.0 s boot
(keyidx_bench-1.log baseline, real 27 KB / 194-line save) into
attributable phases, then re-ran after the byte-walk rewrite of the two
dominant parsers (0b7946e). Raw captures:
[`loadworld_bench-1.log`](../debug/loadworld_bench-1.log) (before) and
[`loadworld_bench-2.log`](../debug/loadworld_bench-2.log) (after).

| Phase | before | after |
|:------|-------:|------:|
| read + split | ~190 ms | ~190 ms |
| `_snap_decode` (39 `it.*` records, 13.2 KB) | 6606 ms | 1587 ms |
| `m=` parse (344 mob entries, 8.8 KB) | 2189 ms | ~400 ms |
| area load (hood, 56 KB) | 1951 ms | 1947 ms |
| parse-loop remainder (p.* fields, caches, pet) | ~2240 ms | ~2220 ms |
| **boot total** (area + `load_world_rest`) | **12984 ms** | **6154 ms** |

- Both parsers lost to the same allocation floor (sec. Recommend scans):
  the old `_snap_decode` walked its record with per-char str indexing +
  `int(slice)` at ~0.5 ms/byte; the `m=` branch paid split-token churn
  plus ~1,000 `int()` parses. Byte-walk rewrites (index bytes for
  unboxed ints, accumulate digits, slice only real payloads) recover
  4.2x and ~5x respectively. The bench's `m_parse` phase is a frozen
  replica of the OLD split parse and now serves as a built-in control:
  it read 2185 ms in the after-run, pinning device conditions equal.
- `_snap_decode`'s remaining 1587 ms is dominated by real payload
  allocation (the decoded dicts/lists/strings themselves), i.e. near
  the floor for eager decode; further gains would need lazy decode,
  rejected for UX (mid-play hitches vs the signposted load screen).
- Area load is unchanged and normal for hood's size class (sec. Area
  loading) -- not a save-parse item.
- Boot creep explained: `it.*` snapshot lines accrete as more item
  templates are touched, and each encoded byte cost ~0.5 ms at boot
  (11.9 s at the 02/08 recommend_bench run vs 13.0 s days later).
  Post-rewrite the per-byte cost is ~4x lower, so the creep slope
  flattens by the same factor.
- Load-bearing invariant made explicit by the rewrite: the snapshot
  encoder's length prefix counts chars of the escaped str, the decoder
  counts bytes -- equal only while save content stays ASCII (guaranteed
  today: area files are ASCII-only source, names are sanitized to
  ASCII letters). The old str-based decoder was accidentally immune.

### Boot cost is save-location-dependent (G1, measured 05 Aug 2026)

A ~25 s boot (`loadworld_bench-3.log`, same device, save at room 9636)
prompted a creep scare; the phase split cleared the save side entirely.
`snap_decode` had *shrunk* to 623 ms (22 records / 7.0 KB encoded vs the
02/08 run's 39 / 13.2 KB -- the save-diet caches working), the frozen
`m_parse` control read 2337 ms (conditions equal), and `area_load` was
17,310 ms: room 9636 is newthalos, the biggest area file (265 KB), and
its reset drain pulls midgaard defs (257 KB, second biggest -- see
docs/CROSS_RESETS.md sec. newthalos), so quitting there boots the two
largest areas back to back. `load_world_rest` scaled with save line
count (7,826 ms at 276 lines vs ~4.2 s at 194). Structural, not creep:
worst-case boot is set by where the player saves, and the exec + reset
cost of big areas is not a parse item (sec. Area loading).

`debug/combat_bench.py` (`debug/combat_bench-1.log`): synthetic phase
timings against the real save (139 chars, 2 areas loaded), real terminal
rendering, no keyboard input. Companion to root `COMBAT_LAG.md`.

| Phase | Cost |
|---|---:|
| `show_prompt` per keystroke | 187-241 ms (~210 typical) |
| `tr.set_status`, prefix precomputed | 130-137 ms |
| -> prompt prefix build share | ~78 ms |
| `interpret("look")` | ~440 ms |
| Violence round, 1 mob | 338-401 ms (~375 typical) |
| Violence round, 4 mobs | 981-1262 ms (~1.1 s typical) |
| `update_handler`, violence only | 330-507 ms |
| `update_handler`, all 6 pulses aligned | 524-764 ms |
| `update_handler`, idle floor | 18-19 ms/pulse |

Conclusions:

- **Every typed character costs ~210 ms**, all of it synchronous before
  the next keyboard pump. Raw full-row status render is ~132 ms of that
  (deterministic, 130-137 across 20 calls); prefix concatenation the
  remaining ~78 ms. This is the general typing-sluggishness baseline and
  the top optimisation target.
- **Busy combat rounds stall ~1.1 s.** With the 4-deep firmware key FIFO,
  typing `flee` + Enter (5 events) inside one such stall is guaranteed to
  drop input; `8` + Enter (2 events) fits. Confirms COMBAT_LAG.md's
  loss-vs-latency split.
- Aligned 30-second pulse adds ~150-350 ms over a violence-only pulse --
  real but secondary.
- Idle `update_handler` floor is ~19 ms per 250 ms pulse
  (`maybe_evict` + `mark_explored` + regen check), acceptable.
- `combat_autoskill` self-skipped: the loaded save's rotation had no
  included entries.
- `load_world` at 23.0 s is the known area-load class (sec. Area
  loading), not an input-lag item.

A/B after the Phase B fixes (`combat_bench-2.log` after colour-band
cache + prompt prefix cache + violence FIFO drains; `combat_bench-3.log`
after offscreen status compose):

| Phase | run 1 | run 2 | run 3 |
|---|---:|---:|---:|
| `show_prompt` per keystroke | ~210 ms | ~145 ms | ~84 ms (max 150) |
| `tr.set_status` raw | ~132 ms | ~123 ms | ~72 ms |
| Violence round, 1 mob | ~375 ms | ~360 ms | ~360 ms |
| Violence round, 4 mobs | ~1.1 s | ~1.08 s | ~1.07 s |
| Violence round, autoskill (sim) | n/a | invalid (mana drain) | 375-620 ms steady |

- Direct `set_color` A/B (`set_color_ab` scenario, 1050 fg pixels):
  pixon repaint ~4 ms/call, cached-band blit ~1 ms/call. The pixon loop
  was a minor cost, not the dominant one -- the band cache is kept for
  its ~9 ms/status-line saving, but the big status win was the offscreen
  compose (123 -> 72 ms) and the prefix cache (~70 ms/keystroke).
- Remaining ~72 ms `set_status` cost is spread across Python-side
  strip/truncate/group loops and per-call `dimgrob`; diminishing
  returns vs the combat-round render tax, which is untouched by Phase B
  (per-line `wrapped_print` straight to screen) and is Phase C's target
  (violence-round batching through `print_lines`).
- Violence FIFO drain checkpoints did not measurably change round cost
  (within run-to-run noise).

Phase C/D A/B (`combat_bench-4.log` after violence-round output batching;
`combat_bench-5.log` adds `scan_skeleton` + batched A/B scenarios;
`combat_bench-6.log` after active-fighter index + paced reveal):

| Phase | run 5 | run 6 | delta |
|---|---:|---:|---:|
| Violence round, 1 mob (unbatched) | 360.6 ms | 354.6 ms | -6 ms |
| Violence round, 4 mobs (unbatched) | 1025.7 ms | 1006.1 ms | -20 ms |
| Autoskill round, steady (r2-10) | 587 ms | 570 ms | -17 ms |
| 1-mob round, batched | 392 ms | 444 ms | +52 ms (pacing) |
| `update_handler`, violence only | 435 ms | 516 ms | +81 ms (pacing) |
| Aligned pulse | 634 ms | 701 ms | +67 ms (pacing) |
| `interpret("look")`, batched | 427 ms | 857 ms | +430 ms (pacing) |
| Typing / status / idle / `scan_skeleton` | -- | -- | unchanged |

- **Full-world scan attribution was wrong.** `combat_basic` is a clean A/B
  (same save, 139 chars, unbatched, only scan-vs-index differs): the old
  `[chars[k] for k in sorted(chars)]` snapshot cost **~6-20 ms in-context**,
  not the ~100 ms `scan_skeleton` suggested. `scan_skeleton`'s steady ~110 ms
  is a tight-loop artifact -- note its own ramp 30 -> 115 ms across 10
  back-to-back iterations; its fresh-heap first iteration (30 ms) is closer
  to truth. The index is kept (no cost, O(fighters) scaling for larger
  loaded worlds), but the measured win is marginal.
  - Corollary: `mobile_update`'s "~100 ms class" estimate came from the same
    scan-shape reasoning and is likely also single-digit ms in-context.
    Measure in-context before touching it.
- **Paced reveal costs exactly its design figure**: ~25 ms per text row
  beyond the first on every batched path (+52 ms on a 1-mob round, +430 ms
  on a 17-row `look`). Deliberate delay, key-skippable in play; synthetic
  bench runs never skip, so batched/pulse numbers now include it -- not a
  regression.
- Run-5 finding (unchanged in 6): `interpret_look` vs `interpret_look_batched`
  were identical (~427 ms), so `look`'s render share is ~nil and
  interpret-level batching is a measured dead end.
- Remaining 1-mob round cost (~355 ms) is attack chain + per-line rendering;
  needs per-hit profiling to subdivide further. Diminishing returns.

Bench conventions (for future runs):

- Probe is `debug/combat_bench.py`; deploy its copy into the debug appdir
  payload, only ONE self-running probe .py per appdir (this OR
  snapshot_gates.py OR save_smoke.py). Copy the real `primesud.sav` in
  first -- the probe reads it read-only (SAVE_VAR redirected). Logs come
  back as `combat_bench.log` -> save as `debug/combat_bench-N.log` and
  commit with a `docs(perf)` entry.
- **Pacing comparability:** runs 1-6 measured `interpret`/look paths
  UNPACED; the global streaming reveal (settled after run 6) adds
  `REVEAL_MS_PER_LINE` (~25 ms) per row to every multi-row path. A/B
  against runs 1-6 must subtract that budget or set the knob to 0 for
  the run.

## Session and memory behaviour (G1, measured 27 Jul 2026)

`debug/mem_soak.py` filled the heap with 32 KB pattern chunks to
`MemoryError`, verified twice, and recorded session behavior:

- The configured 8 MB heap is fully backable: 7904 KB filled, clean
  `MemoryError` at the boundary, and zero pattern mismatches over two 7.6 MB
  verification passes. No bad RAM exists in the tested heap range.
- Allocation churn at a nearly full heap is safe: 243 iterations of 32 KB
  allocate + compare under ~130 KB headroom, with one forced full-heap
  collection per iteration (~67 ms each), survived twice.
- Sessions are deterministic: fresh restore and Clear-softkey rerun matched
  starting `gc.mem_free()` to the byte and all fill checkpoints. The app
  rebuilds its Python heap per run; no cross-session depletion was observed.
- Post-collection free values wobble by 16 bytes to one 32 KB block because
  conservative GC can retain dead blocks referenced by stale C stack/register
  words. A dead 32 KB string surviving one collection is not evidence of a
  leak.
- **Hazard:** pressing On+Symb while the Python app is open, without first
  power-cycling (Shift+On, then On), restores the checkpoint and immediately
  reruns the app. If that rerun crashes, the calculator can initiate a full
  memory reset and wipe all user apps and variables (observed 27 Jul 2026).
  Always power-cycle before On+Symb, and keep transferable copies of anything
  on the device.
- The Python app has no clean exit and keeps its heap carve-out resident until
  an On+Symb reset. While resident, Connectivity Kit can report insufficient
  memory. Close/reset the app before transfers; this is resident pool
  occupancy, not a gameplay leak.
- Prime executes every `.py` in an appdir at startup. Keep one probe per debug
  appdir; module-level code in every shipped file will run.
