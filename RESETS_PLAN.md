# RESETS_PLAN.md -- World-reset fidelity pack (E/G/P/R semantics, spawn extras)

> 1stMud sources: `reference/1stMud4.5.3/src/`. Depends on: DARKNESS_PLAN
> Phase A `room_is_dark` for decision 6's infrared grant (or gate it --
> see decision 6). Everything else independent.
> On completion: harvest decision 1 (per-pass computed object counts),
> decision 4 (P-reset room-restricted container lookup), and decision 5's
> door-skip into DESIGN.md "Adjusted from 1stMud"; strike the TODO.md
> bullets listed under Touch points; delete this file.

Close the gap between 1stMud `reset_room` (db.c:1393-1724) and PrimeSUD's
`mob.py reset_room` (mob.py:226). The converter already emits everything
needed; this is runtime-only work. Current state (verified 08/07/2026):

- M resets: global + room limits already enforced (`_tpl_live_count` /
  `_tpl_room_count`).
- O resets: per-room dedup + zero cost done; area `nplayer` check
  deliberately omitted (single-player, documented inline).
- E/G resets: items always spawn -- **no template-count limit, no 1-in-5
  override** (db.c:1656-1677 not ported). Shopkeeper `inventory` flag done.
- P resets: **stubbed** (`last_spawned = False`, mob.py:304) -- written when
  containers didn't exist. Containers are now fully ported (inventory.py
  do_put/do_get, container_max_* fields), so this can be a real port.
- R resets: **dropped on the floor** (no case at all). Data exists:
  daycare 6613-6616 (shuffle 4 dirs), limbo room 3 (shuffle 1 = no-op).
- M spawn extras (db.c:1476-1488): dark-room infrared grant and
  pet-shop-adjacent ACT_PET grant both missing. The latter is a **live
  bug**: midgaard pet templates (3090-3093) carry no `"pet"` act flag --
  1stMud sets ACT_PET at reset because the spawn room (3032) follows the
  pet_shop room (3031); PrimeSUD's `_buy_pet` (shop.py:209) requires the
  flag, so `buy kitten` fails with "Sorry, you can't buy that here."

## Decisions

1. **Global object-instance counting: computed per reset pass, not a
   persistent counter.** 1stMud maintains `pObjIndex->count` incrementally
   at create/extract; PrimeSUD has many extraction paths (sacrifice, quaff,
   corpse decay, future light burnout) and a persistent counter would drift
   and need saving. Instead `reset_area` computes a per-template count dict
   once per pass -- walk `world.rooms[*]["items"]` (including container
   `contents`, one level of nesting is enough for stock data), all
   `world.chars[*]` inv/eq, and player inv/eq -- then increments it locally
   as the pass spawns items. Lazy loading makes this correct-by-
   construction: unloaded areas contain no instances. Mark `[PRIMESUD]`.
   Heap note: dict of int->int, bounded by distinct templates in loaded
   world; fine.
2. **Limit decode helper** shared by E/G/P: arg2 > 50 -> 6; arg2 in
   (-1, 0) -> 999 (unlimited; db.c P-case treats only -1, E/G-case treats
   -1 and 0 -- match each case exactly); else arg2.
3. **E/G limit semantics** (db.c:1656-1677): for non-shopkeeper mobs, spawn
   only if template count < limit OR `number_range(0, 4) == 0` (the 1-in-5
   over-limit trickle). Shopkeeper branch is unchanged (always spawns,
   `inventory` flag; the old-format `olevel` table db.c:1602-1649 applies
   only to `new_format == false` objects -- converted data is all
   new-format, so skip with an inline note).
4. **P resets** (db.c:1532-1578): decode limit per decision 2; find the
   target container as the most recent instance of `arg3`'s template in
   the *resetting room's* items ([PRIMESUD] restriction: 1stMud's
   `get_obj_type` scans the global object list, but in converted stock
   data P always targets a container O-placed in the same room; global
   scan would fight lazy loading). Skip when: container instance absent,
   template count >= limit, or container already holds > arg4 of the item
   (count against instance `contents`). Refill loop while contents-count
   < arg4, breaking when template count reaches limit. After filling,
   restore the container's closed/locked state from the template
   (db.c:1576 `LastObj->value[1] = pIndexData->value[1]`) -- PrimeSUD
   equivalent: reset instance container flags from template
   `container_flags`. Set `last_spawned = True` (P can chain).
5. **R resets** (db.c:1700-1710 default branch only): Fisher-Yates swap
   over the first arg2 exits in fixed direction order
   (north, east, south, west, up, down). PrimeSUD rooms keep exits in a
   dict keyed by direction name -- shuffle by collecting the exit values
   for the first arg2 direction keys (absent exits shuffle as None, as in
   1stMud where NULL pointers swap too) and reassigning. The `arg3 == 1/2`
   `add_random_exit` variants are a 1stMud extension the converter never
   emits (2-tuple R only) -- skip. **DOOR_DEFS caution:** door reset state
   is keyed by (room, direction); a shuffled room with doors would desync.
   Stock carriers (daycare maze, limbo) have no doors on shuffled exits --
   assert/skip shuffle if any affected exit is a door, with a comment.
   **Automap/do_run caution:** `_AREA_ADJ` and pathfinding read static
   exits; post-shuffle room graph diverges from ROOM_DEFS. Shuffle mutates
   the loaded ROOM_DEFS entry (same as 1stMud mutating live exits), which
   pathfinding also reads once loaded -- acceptable, note it.
6. **M spawn extras** (db.c:1476-1488), in `reset_room` after
   `create_mobile`:
   - `room_is_dark(room)` -> set instance `affected_by["infrared"]`.
     Depends on DARKNESS_PLAN Phase A; if resets land first, gate behind
     `hasattr`/try-import or land the predicate early -- coordinate.
   - previous room (`room_vnum - 1`) has `pet_shop` flag -> set instance
     `act_flags["pet"]` (fixes the buy-pet bug; the special 9621->9706
     newthalos mapping in do_buy's lookup direction already exists in
     shop.py `_buy_pet` -- verify).
7. **default_pos: annotate, don't build.** Its only 1stMud runtime
   consumers are mobprog trigger gating (update.c:444-462) and nothing
   else -- there is no "return to default position" mechanic. Update
   TODO.md to say so; defer to MOBPROG work.
8. **Object `condition` / `light_hours` spawn seeding: out of scope** here
   except that reset spawning goes through the same `create_object` seam
   DARKNESS_PLAN Phase C touches -- keep the seam single.

## Touch points

- `mob.py reset_room` / `reset_area`: all reset-case work above; count
  dict threaded from `reset_area` into `reset_room` (signature change --
  update both callers: `reset_area` and world.py:378 cross-area
  `reset_room` calls, which need their own count computation or a shared
  helper).
- `world.py _reset_loaded_area`: no structural change expected; verify the
  cross-area path gets the count dict.
- `shop.py _buy_pet`: no change expected once flag lands; verify.
- `TODO.md`: strike the E/G-limit, containers-P, R-reset, and default_pos
  bullets from "Deferred runtime hooks"; leave condition/light_hours to
  DARKNESS, mob_triggers to MOBPROG.

## Verification quickies (do during implementation)

- `mobile_update` parity check while in mob.py: ACT_SCAVENGER pickup
  (update.c:467-493) and the wander gates OUTDOORS/INDOORS
  (update.c:503-506) -- confirm ported or add TODO notes; not part of this
  plan's mandate but same file, cheap to audit.
- pytest: unit-test limit decode + E/G trickle (seed randint), P refill
  count semantics, R shuffle preserves the exit set.
- PC shim: `buy kitten` in midgaard pet shop now works end to end
  (buy, follow through a door, order pet, pet assists in combat).
- Daycare maze: exits differ across two resets; `do_run`/automap still
  functional after shuffle.
- Area reset with a loaded shopkeeper: potion stock doesn't multiply past
  limits across repeated resets (the E/G bug this plan fixes).
- `python tools/check_ascii_py.py`.
