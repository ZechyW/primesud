# TODO

Loose ends that don't belong in a specific plan file.

## Roadmap (18/07/2026)

Two-track release plan:

1. **Engine 1.0 first**: sweep that all general 1stMud systems/mechanics are
   ported (minus multiplayer-only ones -- see DESIGN.md for settled
   non-ports) and finalised; close the open items below and the
   on-calculator checklist, then tag a main release (`v1.0.0`).
2. **Content track after**: new-content additions (new classes, areas,
   quests -- e.g. SWORDSMAN_PLAN.md) land only after the 1.0 tag, released
   as content versions on top of the stable engine. Keeps "1stMud parity"
   auditable separately from "PrimeSUD original content".

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
