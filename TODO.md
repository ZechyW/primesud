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

- Firmware string-bug remediation (both bugs root-caused and CLOSED;
  see CLAUDE.md pitfall 8, docs/BUILTINS.md sec. G1 memory-corruption
  bug, docs/PRIME_STRING_FORMAT_BUG.md sec. Battery results): Part 1
  DONE (serializer on util.sstr/num_str/int_str, pre-save gc_collect
  removed); Part 2 DONE (policy docs); Part 3 DONE (de-format sweep:
  all `%`/`.format()` sites converted to concat; chprintf/chprintlnf
  kept but reimplemented on handler._safe_fmt, a concat-based parser).
  REMAINING: on-device soak -- autosave + room-render heavy session on
  the G1 validating both fixes.
- Save optimisation (probe data in docs/BUILTINS.md sec. Save-path
  primitive costs): add debug-gated `ticks()` instrumentation to
  `_serialize_world` ("save" DBG channel); the cache conversion is
  also the alloc diet, and dropping the up-front `gc_collect()`
  returns 78-198 ms. HVars and file I/O measured negligible.
- 6mb-vs-8mb app scaffolding question is closed: 8 MB is fully backable
  and healthy on the G1 (mem_soak); Connectivity Kit needs the Python
  app closed (reset) regardless of heap size.
