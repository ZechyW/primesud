# TODO

Loose ends that don't belong in a specific plan file.

## Mob wandering

- **`no_mob` room flag.** Room data in `area_school.py` already stores `"flags": {"no_mob": True, ...}` for school corridor rooms and the arena safe room (3760). When wander logic is implemented, gate every mob move on `not target_room.get("flags", {}).get("no_mob")` — mirrors `update.c` line 500 (`ROOM_NO_MOB` check). The arena topology keeps most mobs contained regardless, but the safe room and school corridor rely on this as the backstop.

## Door system

Doors are annotated as comments in `area_school.py` (e.g. `# door: {"isdoor": True, "closed": True}`) but the data is not stored — exits are plain `{dir: vnum}` mappings. Nothing enforces closed doors for players or mobs.

- **Store door state in exit data.** Change closed exits from plain `vnum` to `{"to": vnum, "closed": True}` (optionally `"locked": True`, `"pickproof": True`). Open exits stay as plain vnums to keep the common case cheap. Update `are_to_primesud.py` to emit this format and regenerate `area_school.py`. Reference: `EX_CLOSED`, `EX_LOCKED`, `EX_PICKPROOF` in `merc.h`; exit parsing in `db.c`.

- **Enforce `EX_CLOSED` in `do_move` (`commands.py`).** Reject movement through a closed door with "The door is closed." — mirrors 1stMud `move_char` in `act_move.c`. Player-facing only; open/close/lock/unlock commands are a separate item.

- **Enforce `EX_CLOSED` in mob wander (`mobile_update`, `player.py`).** Skip any exit whose door data has `"closed": True` — mirrors `update.c` line 499 (`IsSet(pexit->exit_info, EX_CLOSED)`). Currently documented as a `[PRIMESUD]` deviation in the wandering plan.

## Multi-area

- **`_area_state` / `area_update` are single-area only.** `Game._area_state` is a single dict and `area_update` always uses `RESETS` from `area_school`. When a second area is added, refactor to a list of area descriptors (one per area), each carrying `"tag"`, `"age"`, and a `"resets"` reference, and have `area_update` iterate over all of them. `world.py` will also need to merge multiple area modules' `ROOMS`, `MOBILES`, `OBJECTS`, and `RESETS` into the global tables rather than aliasing a single module.

## Area system

- **School area post-reset age.** After each reset, 1stMud sets the school area's age to `15 - 2 = 13` (cf. `db.c:1330`) so it resets every 2 ticks instead of the normal 0–3 tick randomisation. PrimeSUD's `area_update` currently uses `randint(0, 3)`. Add a `_AREA_AGE_POST_RESET = 13` constant and use it in place of `randint(0, 3)` in `primesud.py:area_update`. This is hard-coded special handling for the school area.
