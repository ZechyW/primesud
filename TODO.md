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

- Save/load round-trip tests are order-dependent by luck. `world._load_area`
  opens `area_<tag>.txt` relative to the cwd (flat filesystem on device), so a
  `load_world()` whose saved room resolves through `world.rooms` needs
  cwd == `src/`; the ~16 existing sites only pass because the vnum index is
  still empty at their point in the run, so the room check never triggers a
  load. Pinning cwd to `src/` suite-wide is NOT the fix -- tried 25/07/2026:
  it breaks `test_help.py` (hardcodes root-relative `src/help.txt`) and makes
  previously-inert lazy loads real, perturbing world state for later tests
  (`test_magic_fidelity_todos.py` scavenger). A real fix means unifying data
  path resolution first. Failure mode is a loud `FileNotFoundError`, so this
  is cleanup, not a risk.

## Platform

(nothing outstanding)
