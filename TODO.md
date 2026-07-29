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

- Item snapshot device gates (registry design landed 29/07/2026; see
  DESIGN.md sec. Item template snapshots). Measured 29/07/2026 via
  `debug/save_smoke.py` on the G1: startup from `primesud.sav` with no
  item-only owner loads (areas loaded: 0, snapshots: 28) and save byte
  size + HVar readback equality with the `it.*` section (23 KB payload,
  19 lines, ok=True x3). Still to measure on hardware before the next
  content release: heap after travel/eviction cycles; one
  content-revision mismatch causing exactly one corrective load;
  snapshot obj program firing from an unloaded owner. If save size
  bites, first lever is field-name tags inside the snapshot codec --
  never silently dropping `description`/`extra_descs`.

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

- Fold `world.ITEM_SNAPSHOTS` save/restore into the shared `fresh_world`
  fixture (tests/conftest.py). Currently guarded per-module: autouse
  clearing fixture in test_area_eviction.py, `reset_lazy()` in
  test_snapshot_codec.py. Fine today, but any new module touching the
  registry silently leaks entries between tests until this lands.

## Platform

- Save optimisation: done 29/07/2026 -- "save" DBG segment timing landed
  in `_serialize_world`, save-path caches took the full-world save from
  11.7 s to ~0.9 s steady on the G1 (docs/PERFORMANCE.md sec. Save path;
  DESIGN.md "Save-path caches"). Remaining ~0.9 s is genuinely-changing
  data; next levers (RLE cache keyed on newly-explored, per-area `a.`
  line cache keyed on age) each add invalidation surface for ~100 ms --
  only revisit if autosave cost ever bites again.
- 6mb-vs-8mb app scaffolding question is closed: 8 MB is fully backable
  and healthy on the G1 (mem_soak); Connectivity Kit needs the Python
  app closed (reset) regardless of heap size.
