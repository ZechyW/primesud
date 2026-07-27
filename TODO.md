# TODO

Loose ends that don't belong in a specific plan file.

## Roadmap (23/07/2026)

Engine 1.0 was tagged as `v1.0.0` on 23/07/2026. Content track is now open:

1. Keep engine parity fixes auditable against the `v1.0.0` baseline.
2. Release new classes, areas, and quests as content versions on top of that
   stable engine.

## Combat

(nothing outstanding)

## Items

(nothing outstanding)

## Magic

(nothing outstanding)

## Classes

(nothing outstanding)

## Commands

(nothing outstanding)

## Housing

(nothing outstanding)

## Area data

(nothing outstanding)

## Tests

(nothing outstanding)

## Platform

- G1 memory-corruption bug -- ROOT ISOLATED (docs/BUILTINS.md sec. G1
  memory-corruption bug): bulk `str(int)` transients + any gc collect.
  Chunking falsified; size/content/HVars/`%d` all acquitted; fix
  pattern (number-string cache + `int_str` digit-concat misses)
  validated at probe level, confirmation run 40/40/20 pending.  Game
  fix queued: remove `_serialize_world`'s opening `gc_collect()`,
  convert the serializer to the cache, audit other bulk-str(int) and
  post-churn `gc_collect` sites (area-data generation first), then
  in-game autosave soak via the "save" DBG channel.
- Save optimisation (probe data in docs/BUILTINS.md sec. Save-path
  primitive costs): add debug-gated `ticks()` instrumentation to
  `_serialize_world` ("save" DBG channel); the cache conversion above
  is also the alloc diet, and dropping the up-front `gc_collect()`
  returns 78-198 ms. HVars and file I/O measured negligible.
- Optional closure probe, low priority: run the `%`-format-bug MWE
  (debug/test_fmt_bug.py) with vs without interleaved `gc.collect()`
  -- corruption rate tracking collects would tie it to the str(int)-GC
  bug (see PRIME_STRING_FORMAT_BUG.md sec. Relation).
- 6mb-vs-8mb app scaffolding question is closed: 8 MB is fully backable
  and healthy on the G1 (mem_soak); Connectivity Kit needs the Python
  app closed (reset) regardless of heap size.
