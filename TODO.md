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

- G1 memory-corruption bug (docs/BUILTINS.md sec. G1 memory-corruption
  bug): HVars acquitted (bignohv reset with zero HVars traffic);
  current suspect is a stochastic GC/alloc defect whose death rate
  rises with 16/32 KB string concat chains. Quantify with the probe's
  `bigloop` mode, then fix the save path: chunk payload assembly and
  the HVar mirror so no single string exceeds ~6 KB (primary + backup
  slots, load joins chunks), and consider pruning zero-information
  `s.m.` entries to slow payload growth past the danger zone. Payload
  measured 7990 B mid-game.
- Save optimisation (probe data in docs/BUILTINS.md sec. Save-path
  primitive costs): add debug-gated `ticks()` instrumentation to
  `_serialize_world` ("save" DBG channel), then alloc-diet the line
  loop and re-evaluate the up-front `gc_collect()` (78-198 ms). HVars
  and file I/O measured negligible.
- 6mb-vs-8mb app scaffolding question is closed: 8 MB is fully backable
  and healthy on the G1 (mem_soak); Connectivity Kit needs the Python
  app closed (reset) regardless of heap size.
