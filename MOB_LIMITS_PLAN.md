# Mob Limits System

## Goal

Full-fidelity port of 1stMud's `M`-reset limit fields to PrimeSUD: each `M` entry carries a
`global_limit` (max live instances of that template across all rooms) and a `room_limit` (max
live instances in that specific room). At reset time, a spawn is skipped when either cap is
already met.

Reference: `reset_room` 'M' case and `create_mobile` in `db.c`; `extract_char` in `handler.c`.
1stMud `.are` wire format: `M 0 <mob_vnum> <global_limit> <room_vnum> <room_limit>`

Intentional deviations are marked `[PRIMESUD]`.

## Reset format

```python
("M", mob_vnum, global_limit, room_vnum, room_limit) # always 5-tuple; .are always carries both
```

The source `.are` format always includes both limit fields, so there are no optional fields or
defaults — the converter always emits the full 5-tuple.

## Model

**Dynamic allocation** — matching 1stMud's approach.

- Dead mobs are **dropped from `mob_instances`** immediately on death (no `state="dead"`).
  Equivalent to 1stMud's `extract_char` removing the mob from the world.
- `reset_mobs(mob_instances, room_state, resets)` replaces `revive_dead_mobs`. For each `M`
  entry it counts live instances of the template globally and in the target room, then spawns
  up to the limits — identical to 1stMud's `reset_room` 'M' logic.
- `reset_area()` — full initialisation (game start / full wipe only): creates a fresh
  `room_state` (items etc.) and a fresh empty `mob_instances`, then calls `reset_mobs` to
  populate it. The area tick calls `reset_mobs` directly on live state, not `reset_area()`.
- `reset_mobs` reads limits directly from the `resets` entries it receives; instances carry no redundant limit fields.

**`[PRIMESUD]` Save format.** 1stMud persists nothing about mob state between sessions (area
resets are time-driven). PrimeSUD saves alive mob counts so killed mobs stay dead across
save/load within a reset cycle. Format: `m.{tpl_vnum}={count}` — one entry per template with
at least one live instance. On load, `count` instances are spawned at the M entry's room; dead
mobs are simply absent and `reset_mobs` fills them on the next area tick. When wandering is
implemented this extends to `m.{tpl_vnum}={room}|{room}|...` (one room per live instance).

Assumption: each template vnum appears in at most one M entry per area. True for all existing
area files; revisit if violated.

## Planned

- [x] **1** — Extend `("M", …)` to 5-tuple in `reset_area()` and `reset_mobs()`; `reset_area()` calls `reset_mobs` on empty `mob_instances` *(cf. `M` case in `reset_room`, `db.c`; `create_mobile`, `db.c`)*
- [x] **2** — `_tpl_live_count(mob_instances, tpl_vnum)` and `_tpl_room_count(mob_instances, room_vnum, tpl_vnum)`; no `room_state` needed — each instance carries `"room"` *(cf. `pMobIndex->count` and per-room scan in `reset_room`, `db.c`; scanned at reset time, not a running counter)*
- [x] **3** — `reset_mobs` replaces `revive_dead_mobs` (deleted); skips M entry if global or room count is at limit *(cf. `reset_room` 'M' case, `db.c`)*
- [x] **4** — Death removes mob from `mob_instances` and `room_state` immediately; `state="dead"` guard removed from `save_char`, dead-state restore replaced with removal in `load_char` *(cf. `extract_char`, `handler.c`)*
- [x] **5** — Save/load: `save_char` emits `m.{tpl}={room}|{room}|...` (one entry per live instance); `load_char` trims killed instances and patches wandered rooms. Load is treated as a new session — fully-killed templates have no entry and respawn via `reset_area`, consistent with 1stMud server-restart behaviour. *[PRIMESUD]*
- [x] **6** — `are_to_primesud.py`: `parse_resets` captures global/room limits; `emit` outputs 5-tuple; fixed swapped field comment; `area_school.py` regenerated *(cf. `school.are` `#RESETS`)*
- [x] **7** — `AREA_FILES.md` updated: 5-tuple format and dynamic allocation model documented

## Deferred

| Feature | 1stMud ref | Reason |
|---------|-----------|--------|
| Cross-area global count | `pMobIndex->count` accumulates across all areas | Each template appears in only one area's RESETS in practice; `_tpl_live_count` scoped to current `mob_instances` is equivalent |
| `ACT_STAY_AREA` enforcement in wander logic | `update.c` wander check | Done — `mobile_update` gates cross-area moves on this flag |
| `ACT_SENTINEL` enforcement in wander logic | `update.c` wander check | Done — `mobile_update` skips sentinel mobs |
| Cross-area despawn (5% / `mobile_update`) | `char_update`, `update.c:541` | Done — mobs outside `home_area` have 5% chance to despawn each `mobile_update` |
| Save wandered rooms | `save_char` / `load_char`, `player.py` | Done in step 5 |
