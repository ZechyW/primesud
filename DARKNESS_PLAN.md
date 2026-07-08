# DARKNESS_PLAN.md -- Room darkness / visibility / light system port from 1stMud

> 1stMud sources: `reference/1stMud4.5.3/src/`. Depends on: nothing.
> RESETS_PLAN decision 6 consumes Phase A's `room_is_dark` -- land Phase A
> first if both plans run, else gate (see that plan).
> On completion: harvest decision 1 (computed room light) and decision 3
> (permissive `can_see_room`) into DESIGN.md "Adjusted from 1stMud"; strike
> TODO.md `light_hours`/`condition` bullets touched; delete this file.

Port of 1stMud's darkness and visibility layer (`handler.c` visibility
predicates, `update.c` light burnout, `act_info.c` look/exits gating), plus
the small `do_time`/`do_weather` bundle that darkness depends on. Biggest
outstanding fidelity gap with live content: ~600 rooms in the loaded areas
carry `"dark": True` (sewer 145, tohell 139, moria 82, chapel 66,
newthalos 49, haon 47, ...) and none of it currently does anything.

Scaffolding already in place -- do NOT rebuild these, extend them:

- `game_time.py` ticks `time_info["sunlight"]` (SUN_RISE/LIGHT/SET/DARK).
- Room data carries `"sector"` and `"flags": {"dark": True, ...}` per room.
- Light wear slot exists (`player.py` slot `"light"`, wear/remove in
  `inventory.py:750`); school banner auto-equipped at chargen.
- Converter emits `light_hours` on light objects (TODO.md "deferred runtime
  hooks"); not yet consumed.
- Affects: `infrared` (races.py grants + `spell_infravision` magic.py:1901),
  `detect_invis`, `detect_hidden`, `blind` all live.
- `can_see` (handler.py:956) ports blind/invis/sneak/hide already;
  `can_see_room` (handler.py:937) and `can_see_obj` (handler.py:1002) are
  documented always-True stubs.
- Gating TODOs already marked at the call sites: `automap.py:84`
  (`[TODO dark]`), `info.py:429` ("Too dark to tell" exits note),
  `info.py:453` (check_blind + dark gates on look).

## Decisions

1. **Room light counter: computed, not incremental.** 1stMud maintains
   `room->light` via +-/-- in char_to_room/char_from_room
   (handler.c:1321/1369) and equip_char/unequip_char (handler.c:1578/1648).
   PrimeSUD instead computes on demand: `room_light(room_vnum)` = count of
   characters in the room (player if present + `world.rooms[vnum]["mobs"]`)
   with an equipped light-slot item of type `light` and nonzero fuel.
   Same observable behaviour, no counter drift, nothing new to save.
   Mark `[PRIMESUD]`. Floor lights do NOT light rooms (1stMud fidelity).
2. **HOLYLIGHT / invis_level / incog / arena / clan gates: skip.** No
   immortals, single-player. Keep the existing `[PRIMESUD]` docstring notes.
3. **`can_see_room` stays permissive for now.** The 1stMud room-flag gates
   (IMP_ONLY/GODS_ONLY/HEROES_ONLY/NEWBIES_ONLY, handler.c:2362) guard
   immortal areas; the only carrier in loaded data is area_immort (already
   unreachable). Leave the stub, extend its docstring. This plan's
   `can_see_room` work is ONLY the automap dark check.
4. **Fuel on instances.** Item instances are plain dicts: seed
   `obj["light_hours"]` from template at spawn (`spawn_object` path used by
   resets/quests) when template type == `light`. Template value absent /
   negative = infinite (never decrement, never burn out) -- matches 1stMud
   `value[2]` semantics (0 = dead, <0 = infinite, >0 = hours left).
   quest.py:371 already notes the seam ("light fuel not modeled").
5. **Save format.** Whatever the item-instance serializer in
   `game_state.py`/`world.py` persists must gain the `light_hours` field
   (only when present). Bump SAVE_VERSION; no migration needed beyond
   default-absent (= infinite, same as today's behaviour).
6. **`do_time` + `do_weather` bundled here** -- darkness outdoors is driven
   by sunlight, so the player needs a way to check it. Port
   `weather_update` (weather.c: barometric pressure + sky state) and the two
   info commands from act_info.c; uncomment their `_CMD_TABLE` rows
   (#55 time, #57 weather).

## 1stMud semantics (source of truth)

- **`room_is_dark`** (handler.c:2308): light > 0 -> not dark; ROOM_DARK
  flag -> dark; SECT_INSIDE or SECT_CITY -> not dark; sunlight SUN_SET or
  SUN_DARK -> dark; else not dark. PrimeSUD: flag key `"dark"`, sector
  strings `'inside'`/`'city'`.
- **`can_see` dark gate** (handler.c:2428): after quest/gquest overrides,
  `room_is_dark(ch->in_room) && !AFF_INFRARED` -> False. Insert into
  handler.py:956 after the blind check, before invis (keep the existing
  quest-target override order if/where quest overrides get ported -- they
  are currently absent; note inline).
- **`can_see_obj`** (handler.c:2456), full port order matters:
  quest-object override (PrimeSUD: quest.py tracks quest obj by vnum --
  check `is_questobj` equivalent; if awkward, note TODO inline);
  ITEM_VIS_DEATH -> False; blind (except potions) -> False; lit light
  (`type == "light"` and fuel != 0) -> True; ITEM_INVIS without
  detect_invis -> False; ITEM_GLOW -> True; dark room without
  AFF_DARK_VISION -> False; else True. `dark_vision` is an affect flag only
  (tables.c:200, no spell/race grant) -- support the key, nothing grants it
  yet.
- **Look gating** (act_info.c:1110-1125): `do_look` with no arg in a dark
  room without infrared prints exactly `"It is pitch black ... "` and shows
  nothing (room name/desc/contents/chars all suppressed). check_blind
  (act_info.c:495) gates first: `"You can't see a thing!"`.
- **Red eyes** (act_info.c:486): in show_char_to_char, a victim who fails
  can_see but has AFF_INFRARED in a dark room prints
  `"You see glowing red eyes watching YOU!"` instead of being hidden.
- **Exits** (act_info.c:1476 region): `do_exits`/auto-exits show a dark
  destination room's name as `"Too dark to tell"` (exact string per source;
  re-read the block when implementing).
- **Light burnout** (update.c:597-613, in char_update, once per tick,
  players below immortal only): equipped light with value[2] > 0 loses 1;
  at 0: `"$p goes out."` TO_ROOM, `"$p flickers and goes out."` TO_CHAR,
  extract_obj; at <= 5 remaining: `"$p flickers."` TO_CHAR.
- **Aggro interaction**: mob aggression already routes through `can_see`
  (verify in mob.py); once the dark gate lands, dark rooms shield the
  player from non-infrared aggressive mobs -- this is correct 1stMud
  behaviour, not a bug. Mobs need their room resolved from `mob["room"]`;
  make the dark gate work with either a player or mob observer.

## Phases

### Phase A -- core predicates

> **Already landed (08/07/2026, commit 8ef****):** `room_is_dark(room_vnum)`
> and its `room_light(room_vnum)` helper (decision 1) shipped early in
> `handler.py` so the RESETS pack could grant infrared to mobs spawned in
> dark rooms. Extend these here -- do NOT rebuild them. Still outstanding
> below: the `can_see` dark/infrared gate, `can_see_obj`, and `check_blind`.

- `handler.py`: DONE `room_is_dark(room_vnum)` + `room_light(room_vnum)`
  helper (decision 1). Still TODO: extend `can_see` with the dark/infrared
  gate; full `can_see_obj` port (decision + order above); `check_blind` port
  (act_info.c:495) if not already present (info.py:453 says it is not).
- `game_time.py`: nothing -- sunlight already correct. Verify SUN_SET is
  set at hour 18 and SUN_DARK at 20 against weather.c while there.
- Room lookup: both `player["room"]` and `mob["room"]` must resolve; keep
  `ROOM_DEFS[vnum]` access inside the predicate (single area lazy-load is
  fine -- observer is always in a loaded room).

### Phase B -- command/UI gating

- `info.py` `do_look`: check_blind gate, pitch-black gate (exact message),
  red-eyes branch in the char-listing loop, `can_see_obj` filter on room
  item listing.
- `info.py` exits rendering: "Too dark to tell" for dark destinations.
- `automap.py:84`: resolve the `[TODO dark]` -- unmapped/blank cell when
  `not can_see_room(...)` per 1stMud automap.c; for PrimeSUD this means
  `room_is_dark(vnum) and not infrared`.
- `scan.py`: gate scanned chars through `can_see` (verify current state --
  may already comply once can_see gains the dark gate).
- `inventory.py` get/drop pickers: filter through `can_see_obj` where
  1stMud does (act_obj.c uses get_obj_list -> can_see_obj). Check the
  existing `_loot_container_picker`/`do_get` paths.

### Phase C -- light fuel

- Spawn seam: seed `light_hours` on instances of type `light`
  (decision 4) wherever templates become instances (world reset spawn,
  quest reward path quest.py:371, shop buy if shops instantiate).
- `update.py` tick handler: burnout per update.c:597-613, exact messages,
  flicker warning, extraction, and (nothing to decrement on the room --
  light is computed).
- `game_state.py`: serialize/restore `light_hours`; SAVE_VERSION bump.
- `spell_continual_light` / light-ball object: confirm the created object's
  template has infinite fuel (value[2] = -1 upstream); no code change
  expected, just verify.

### Phase D -- time + weather commands

- New/extended `game_time.py` or `info.py`: `weather_update` port
  (weather.c -- pressure `change`, sky states, weather messages to outdoor
  players) called from the same PULSE_TICK as `time_update`.
- `do_time`, `do_weather` (act_info.c) with 1stMud output formats;
  `do_weather` requires outdoors (`sector` not inside + not indoors flag --
  per source `IS_OUTSIDE`).
- `commands.py`: uncomment rows #55/#57.

## Verification

- Unit: `room_is_dark` truth table (lit char present / dark flag / inside /
  city / each sunlight state). pytest already in repo (`tests/`).
- On-PC shim run: walk Midgaard at night (outdoor rooms dark after hour 20
  unless city sector -- Midgaard streets are `city`, so unaffected; use
  plains/marsh), enter sewers without a light -> pitch black; wear school
  banner -> room visible; wait for burnout messages at <=5 and 0.
- Aggro check: aggressive non-infrared mob in a dark room must not attack
  an unlit player; infrared mob must.
- `python tools/check_ascii_py.py` after every edit batch.

## Deliberately out of scope

- ROOM_SAFE (combat gate) and other room-flag combat/regen consumers
  (heal_rate/mana_rate) -- separate concern, see RESETS/room-fidelity work.
- `dark_vision` granters, holylight, invis_level.
- Mobs carrying/using lights beyond what resets already equip.
