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
full-world save (`debug/save_smoke-1/-2/-3.log`), `_serialize_world`
segment timing via the "save" DBG channel. Before caches: 11.7 s steady,
dominated by re-scanning every `_pending_room_items` token line (snap
5.6 s + sweep 4.5 s) and re-rendering every pending mob part
(ln.mob 750 ms). After `_PENDING_VNUM_CACHE` / `_SNAP_ENC_CACHE` /
`_PENDING_MOB_CACHE` (DESIGN.md sec. Item template snapshots,
"Save-path caches"): ~0.9 s steady, all in genuinely-changing data --
ln.plr1 168 / ln.rle 113 / ln.plr2 254 / ln.room 249 / hvset 33, snap
and sweep ~5 ms each. `load_world` prewarms the pending-token cache
(7.7 s -> 12.2 s load), so the first save matches steady state instead
of paying a one-time 4.5 s scan.

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
