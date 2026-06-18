# Area Lazy Load Plan

## Goal

Reduce HP Prime heap pressure and improve physical-device stability by delaying
world-data runtime work until it is needed.

HP Prime caveat: Python appears to load all `.py` files in the app before
`primesud.py` can benchmark startup. Lazy imports may not reduce first-launch
wait if area source files remain packaged in the app. Main early target is heap
stability: avoid duplicate merged catalogs, bulk mutable state, and all-world
resets before gameplay needs them.

## Baseline Problems

- `world.py` imports every `area_*.py` module at top level.
- `world.py` eagerly merges all area dicts into global catalogs.
- `RESETS = RESETS + area.RESETS` creates repeated tuple copies during import.
- `DOOR_RESET` snapshots every room at import time.
- `reset_area()` creates mutable room state for every room and spawns mobs/items
  across all areas before player visits them.

## Level 1: Defer World Initialisation

Move heavy `world.py` setup into `init_world()`:

- keep public globals (`ROOMS`, `ROOM_AREAS`, `MOB_TEMPLATES`,
  `ITEM_TEMPLATES`, `RESETS`, `AREA_DEFS`, `DOOR_RESET`)
- initialise them empty at import time
- fill existing dict/list objects in place when `init_world()` runs
- guard with `_WORLD_READY`
- call `init_world()` once from `PrimeSud.run()` before constructing `Game`

Do not rebind exported containers after other modules import them. Code uses
`from world import RESETS`, so `RESETS` must be mutated in place rather than
reassigned. Use a list for `RESETS`; current callers only iterate over it.
Avoid spreading defensive `init_world()` calls through gameplay helpers; the app
entry point is the runtime boundary.

Expected benefit:

- `import world` has fewer heavy side effects.
- benchmarking inside runtime becomes cleaner.
- duplicate merged catalogs and door snapshots are delayed until game state
  setup.

Limit:

- top-level area imports still happen, so HP loader may still pay parse/import
  cost.
- all catalogs still merge before actual gameplay.

## Level 2: Defer Area Module Imports

Replace module refs in `_AREA_LIST` with module names or loader functions:

```python
_AREA_LIST = (
    ("area_limbo", "limbo"),
    ("area_school", "mudschool"),
)
```

`init_world()` then imports/resolves modules when needed.

Expected benefit on normal Python:

- `import world` no longer loads all area data.

HP Prime risk:

- if app loader preloads all `.py` files anyway, first-launch wait may not
  improve.

## Level 3: Per-Area Runtime State

Keep static catalogs per area and load/reset only visited or referenced areas.

- add `ensure_area(tag)` / `ensure_room(vnum)` / template lookup helpers
- create `room_state` entries per loaded area only
- reset mobs/items per loaded area only
- make `area_update()` skip unloaded areas
- make save/load load referenced areas before applying saved room/mob/item state

Expected benefit:

- largest heap reduction during normal play
- player in Mud School does not pay runtime state for Midgaard/Chapel/etc.

Risks:

- cross-area VNUM lookup needs an owner index
- automap/map must avoid accidentally loading whole world
- save/load and mob wander need careful area boundary handling

## Measurement

Track on emulator and physical Prime:

- perceived app launch wait
- free memory at first line of `PrimeSud().run()`
- free memory after `init_game_state()`
- free memory after `reset_area()`
- free memory after first `do_look()`

Use temporary benchmark code only; remove before final build.
