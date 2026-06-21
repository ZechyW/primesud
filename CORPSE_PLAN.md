# Corpse & Decay System — Implementation Plan

## Project Context

PrimeSUD is a single-user MUD ported from 1stMud (ROM 2.4-based) to HP Prime
graphing calculator. See `CLAUDE.md` for full project docs, constraints (HP Prime
Python subset, no `%` formatting in persisted strings, ASCII-only
`.py` files), and coding conventions.

This plan ports the 1stMud corpse/body-part/object-decay system to PrimeSUD.
Player death is intentionally simplified: a narrative corpse spawns, but the
player keeps all gear and gold (no corpse-run mechanic). Implementation should otherwise 
follow 1stmud naming and data conventions where possible and appropriate.

**1stMud reference code** lives under `reference/1stMud4.5.3/src/`. Key files:
- `fight.c` — `make_corpse()` (~line 1673), `death_cry()` (~line 1794), `raw_kill()` (~line 1974)
- `update.c` — `obj_update()` (~line 768): object timer tick-down and decay
- `h/vnums.h` — corpse/body-part vnum constants (~line 60)
- `h/bits.h` — `PART_*` body-part flags (~line 286), `ITEM_INVENTORY`/`ITEM_ROT_DEATH`/`ITEM_VIS_DEATH` item flags (~line 357)

**PrimeSUD code** lives under `primesud.hpappdir/`. Key files for this feature:
- `combat.py` — current `raw_kill()` (~line 963), `_death_cry()` (~line 958)
- `player.py` — `tick_update()` (~line 124): per-tick regen/affect decay
- `update.py` — `obj_update()`: world-state update loops (mirrors 1stMud `update.c`)
- `primesud.py` — `Game.run()` (~line 252): main loop, tick dispatch (~line 217), player death/respawn (~line 200)
- `item.py` — `create_object()` (~line 12), `obj_vnum()`, `item_extra_flags()`
- `inventory.py` — `do_get()` (~line 20): current item pickup logic
- `info.py` — `do_look()` (~line 87): room/item display
- `area_limbo.py` — corpse and body-part item templates (I_CORPSE ~line 148, I_HEAD ~line 167, etc.) — **already defined, currently unused**

**Phases are sequential.** Each phase builds on the prior one. A new session
implementing any phase should read this plan top-to-bottom through that phase,
then read the actual source files referenced (both PrimeSUD and 1stMud) before
writing code. Line numbers are approximate — grep for function/variable names
to find current locations.

---

## Phase 1: Object Timer System [completed: 55e****]

**Goal:** Items can decay over time. Prerequisite for all other phases.

**Read before implementing:**
- 1stMud `reference/1stMud4.5.3/src/update.c`, function `obj_update()` (~line 768–928) — full timer/decay logic
- PrimeSUD `primesud.hpappdir/player.py`, function `tick_update()` (~line 124) — understand existing tick cadence
- PrimeSUD `primesud.hpappdir/primesud.py`, `Game.run()` tick dispatch block (~line 217–224) — where to hook in

### Item instance changes

Add optional `"timer"` field to item instance dicts:
- `-1` or absent = no decay (default, backward-compatible)
- `> 0` = ticks remaining until decay

No changes to `create_object()` needed — timer is set by callers (Phase 2+), not by default construction.

### `obj_update()` — new function in `update.py`

`update.py` is a new module mirroring 1stMud's `update.c` — natural home for future
world-update loops (char_update, weather_update, etc.).

Called once per world tick from `Game.run()`, same cadence as `tick_update()`.

Signature: `obj_update(tr, player, world)` — needs `tr` for messaging, `player` to check if player is in room, `world` for room iteration.

Logic (mirrors 1stMud `obj_update` in `update.c`):
1. Iterate `world["rooms"]`. For each room, iterate `room["items"]` list (copy list before iterating — items may be removed mid-loop).
2. For each item with `"timer"` present and `> 0`: decrement by 1.
3. When `timer` reaches 0:
   - Look up item type from `ITEM_TEMPLATES[obj_vnum(item)]`.
   - Pick decay message by item type:
     - `npc_corpse` → `"{short_descr} decays into dust."`
     - `pc_corpse` → `"{short_descr} decays into dust."`
     - `food` → `"{short_descr} decomposes."`
     - `potion` → `"{short_descr} has evaporated from disuse."`
     - default → `"{short_descr} crumbles into dust."`
   - `short_descr` comes from instance override if present, else template.
   - If player is in same room, print decay message.
   - Handle contents spill (Phase 2 adds this; Phase 1 just removes item).
   - Remove item from room's items list.

### Integration

In `primesud.py` `Game.run()`, inside the `if pulse % PULSE_TICK == 0:` block, add `obj_update(tr, player, world)` call after `tick_update()`. Import `obj_update` from `update`.

---

## Phase 2: Corpse Creation (`make_corpse`) [completed: 2cb****]

**Goal:** Dead mobs produce corpse container objects with loot inside, replacing current direct-drop.

**Read before implementing:**
- 1stMud `reference/1stMud4.5.3/src/fight.c`, function `make_corpse()` (~line 1673–1791) — full corpse creation logic, item flag handling, gold transfer
- PrimeSUD `primesud.hpappdir/combat.py`, function `raw_kill()` (~line 963–999) — current death handler with `[PRIMESUD]` direct-drop comment
- PrimeSUD `primesud.hpappdir/area_limbo.py`, `I_CORPSE` template (~line 148) — NPC corpse template (already defined)
- PrimeSUD `primesud.hpappdir/item.py`, `create_object()` (~line 12) — how item instances are built
- PrimeSUD `primesud.hpappdir/item.py`, `item_extra_flags()` (~line 31) — how extra_flags merge between instance and template
- Grep for `rot_death` and `ITEM_INVENTORY` across area files to see which items use these flags

### `make_corpse()` — new function in `combat.py`

Called from `raw_kill()`, replaces current direct-drop logic (lines ~984–993).

Steps (cf. 1stMud `make_corpse` in `fight.c`):
1. Create corpse instance via `create_object(I_CORPSE)` (NPC corpse).
2. Set `instance["timer"]` = `randint(3, 6)`.
3. Stamp mob name into instance-level `short_descr` and `description` using str concatenation (not `%` — HP Prime string formatting bug, see `PRIME_STRING_FORMAT_BUG.md` and `CLAUDE.md`):
   - `"The corpse of " + mob_short`
   - `"The corpse of " + mob_short + " is lying here."`
4. Add `"contents": []` list to corpse instance.
5. If mob has gold > 0, create gold item and append to `corpse["contents"]`.
6. Move all mob equipment (from `inst.get("equip", {})`) and inventory (from `inst.get("inv", [])`) into `corpse["contents"]`:
   - Check `item_extra_flags(obj, tpl)` for each item:
     - `inventory` flag set → destroy item (don't move to corpse). These are shop-restock items per 1stMud convention.
     - `rot_death` flag set → set `obj["timer"]` = `randint(5, 10)`, clear flag on instance.
     - `vis_death` flag set → clear flag on instance.
   - All other items → append to `corpse["contents"]`.
7. Place corpse in `world["rooms"][inst["room"]]["items"]`.

### Update `raw_kill()`

Replace the `[PRIMESUD]` direct-drop block (~lines 984–993) with a single `make_corpse(inst, tpl, world)` call. Remove the individual "falls to the ground" act messages — loot is now inside corpse, accessed via `get` command (Phase 3).

### Update `obj_update()` for corpse contents on decay

When an NPC corpse timer reaches 0:
- Destroy all contents with the corpse (items vanish). Matches 1stMud behavior for NPC corpses.

When a PC corpse timer reaches 0 (Phase 5 only):
- Spill contents to room floor before removing corpse.

### Room display consideration

After this phase, corpses appear in room item lists. Verify that `do_look` room display (~`info.py`) shows the corpse's stamped description properly. The instance-level `description` override should take precedence over template. Check how `do_look` currently resolves item descriptions — grep for `description` usage in the room-item display section of `do_look`.

---

## Phase 3: Container Interaction [completed: 7c6****]

**Goal:** Player can loot corpses (`get sword corpse`) and interact with containers.

**Read before implementing:**
- 1stMud `reference/1stMud4.5.3/src/act_obj.c` — `do_get()` for container get logic, `do_put()` for put logic. Grep for `ITEM_CONTAINER`, `ITEM_CORPSE_NPC`, `ITEM_CORPSE_PC` in that file.
- PrimeSUD `primesud.hpappdir/inventory.py`, `do_get()` (~line 20) — current picker-based get logic. Understand arg handling, `pick_from` usage, and the `get all` / `get all.<keyword>` paths.
- PrimeSUD `primesud.hpappdir/info.py`, `do_look()` (~line 87) — current room display and any existing `look in` handling.
- PrimeSUD `primesud.hpappdir/picker.py` — `pick_from()` UI for interactive selection.
- PrimeSUD `primesud.hpappdir/commands.py` — command table (~line 40+) for adding `put` command.
- Check `DESIGN.md` for any relevant design decisions about item interaction.

### `do_get` changes (`inventory.py`)

Extend to support `get <item> <container>` syntax:
1. **No-arg picker path:** If room has container-type items (types `npc_corpse`, `pc_corpse`, `container`), present them as selectable targets alongside loose floor items. When player picks a container, show its contents as a secondary picker.
2. **`get <item> <container>` text path:** Parse two arguments. Find container in room by keyword (`is_name` match). Validate it's a container/corpse type. Find item inside container's `"contents"` by keyword. Move from contents to `player["inv"]`.
3. **`get all <container>`** / **`get all corpse`:** Move all takeable items from container contents to player inventory.
4. **`get all` (no container):** Only picks up loose room items (skip container contents). Matches 1stMud.

### `do_look` changes (`info.py`)

Extend `look in <container>`:
- Parse `look in <keyword>`. Match container in room items or player inventory.
- List contents by short_descr, or "Nothing." if empty.
- Check how 1stMud formats container-look output in `act_info.c` (grep for `ITEM_CONTAINER` or `look_in`).

### `do_put` — new command (`inventory.py`)

`put <item> <container>`:
- Find item in player inventory by keyword.
- Find container in room or player inventory by keyword.
- Move item from `player["inv"]` to `container["contents"]`.
- Add `("put", do_put, "resting", False)` to command table in `commands.py`.

### Room display

Verify corpses show their stamped `description` in room look output. Standard items use template `description`; corpses use instance-level `description` set during `make_corpse`. If room display doesn't already prefer instance `description` over template, fix that.

---

## Phase 4: Body Parts via `death_cry`

**CRITICAL: PENDING PREREQS.** Do not implement until race data is properly ported.

**Goal:** Death messages conditionally drop body-part objects, matching 1stMud probability distribution and part-checking logic.

**Read before implementing:**
- 1stMud `reference/1stMud4.5.3/src/fight.c`, function `death_cry()` (~line 1794–1907) — full body-part drop logic, adjacent-room death cry broadcast
- 1stMud `reference/1stMud4.5.3/src/h/bits.h`, `PART_*` flags (~line 286) — which body parts exist
- PrimeSUD `primesud.hpappdir/combat.py`, `_death_cry()` (~line 958) and `_DEATH_CRIES` (~line 945) — current text-only implementation (marked `[PRIMESUD]`)
- PrimeSUD `primesud.hpappdir/area_limbo.py`, body-part templates (I_HEAD ~line 167, I_HEART ~line 176, I_ARM ~line 185, I_LEG ~line 194, I_GUTS_ENTRAILS ~line 203, I_BRAINS_BRAIN ~line 212) — already defined, currently unused
- Grep for existing mob template structure in area files (e.g., `area_school.py`) to see where `"parts"` field should go

### Mob template `"parts"` field

Add to mob templates in are_to_primesud.py and run regen_areas.sh:
```python
"parts": {"head": True, "arms": True, "legs": True,
          "heart": True, "guts": True, "brains": True}
```

Default (if `"parts"` key absent from template): treat as all standard parts present. Matches 1stMud `race_table` defaults for most humanoid races. Only specify `"parts"` explicitly for non-standard mobs (elementals, slimes, etc.).

### Update `_death_cry()` (`combat.py`)

Replace current uniform-random text-only system with 1stMud's `number_bits(4)` distribution:

1. Roll `randint(0, 15)` (equivalent to 1stMud `number_bits(4)` which returns 0–15).
   - Cases 0–7 are specific messages. Cases 8–15 all fall through to default.
   - This gives ~50% chance of generic "death cry" fallback, matching 1stMud.
2. Cases 2–7 check mob template's `"parts"` dict. If part missing, fall through to default.

| Case | Part key | Body part template | Message |
|------|----------|-------------------|---------|
| 0 | — | — | `"{name} hits the ground ... DEAD."` |
| 1 | — | — | `"{name} splatters blood on your armor."` |
| 2 | `guts` | `I_GUTS_ENTRAILS` | `"{name} spills its guts all over the floor."` |
| 3 | `head` | `I_HEAD` | `"{name}'s severed head plops on the ground."` |
| 4 | `heart` | `I_HEART` | `"{name}'s heart is torn from its chest."` |
| 5 | `arms` | `I_ARM` | `"{name}'s arm is sliced from its dead body."` |
| 6 | `legs` | `I_LEG` | `"{name}'s leg is sliced from its dead body."` |
| 7 | `brains` | `I_BRAINS_BRAIN` | `"{name}'s head is shattered, and its brains splash all over you."` |
| 8–15 | — | — | `"You hear {name}'s death cry."` |

3. When a body-part vnum is selected: create object via `create_object(vnum)`, set `timer` = `randint(4, 7)`, stamp mob name into instance `short_descr`/`description` using str concat, place in room.
4. Body parts are typed `food` in their templates (already correct in `area_limbo.py`).
5. **Deferred:** Poison food sub-feature (checking mob `form` flags like `FORM_POISON` to set food poison flag). Not needed for MVP.
6. **Deferred:** Adjacent-room death cry broadcast (1stMud sends "You hear something's death cry" to neighboring rooms). Low priority for SUD.

### Area data updates

Add `"parts"` to mob templates that have non-standard body composition. Humanoid mobs (most mobs) don't need explicit `"parts"` — absence means all-standard-parts. Check each area file's mob templates and add `"parts"` only for non-humanoid mobs with reduced part sets.

---

## Phase 5: Simplified Player Death

**Goal:** Player death spawns a narrative corpse in the death room. Player keeps all gear and gold. Gentler than 1stMud for single-player context.

**Read before implementing:**
- 1stMud `reference/1stMud4.5.3/src/fight.c`, `raw_kill()` (~line 1974–2001) — PC death path: extract, strip affects, reset armor, set resting
- 1stMud `reference/1stMud4.5.3/src/fight.c`, `make_corpse()` PC branch (~line 1698–1717) — PC corpse: timer 25–40, owner field, clan gold penalty
- PrimeSUD `primesud.hpappdir/primesud.py`, player death/respawn block (~line 200–214) — current auto-respawn with messages
- PrimeSUD `primesud.hpappdir/area_limbo.py`, `I_CORPSE_11` template (~line 157) — PC corpse template (already defined)

### On player death (in `primesud.py` respawn block, ~line 200)

After existing respawn logic (teleport, hp/mp=1, messages), add:
1. Create PC corpse from `I_CORPSE_11` template via `create_object()` in the **death room** (the room where the player died, before teleport — capture `player["room"]` before overwriting it).
2. Stamp player name into instance `short_descr`/`description` using str concat.
3. Set `timer` = `randint(25, 40)` (matches 1stMud).
4. Corpse `"contents"` = `[]` — **empty**. Player keeps all gear and gold.
5. Place corpse in death room's `items` list.
6. Corpse is a narrative marker only ("The corpse of Rilias is lying here.").

On decay: `obj_update` removes it normally. No contents to handle.

**Intentionally not ported** (SUD simplification — document in code with `[PRIMESUD]` tag):
- Gold/item transfer to corpse
- Morgue room teleport for low-level PCs
- Corpse `owner` field / loot permissions
- Naked respawn
- Clan-specific gold penalty

---

## Dependency Chain

```
Phase 1 (timers)
  └──→ Phase 2 (make_corpse)
         └──→ Phase 3 (container get/put/look-in)
Phase 1 (timers)
  └──→ Phase 4 (body parts) — independent of Phases 2–3
Phase 1 (timers)
  └──→ Phase 5 (player death corpse) — independent of Phases 2–4
```

Implement sequentially: **1 → 2 → 3 → 4 → 5**.

Minimum viable: Phase 1 + 2 + 3 (corpses exist, can be looted, decay naturally).
Phase 4 adds flavour. Phase 5 adds narrative.

---

## Data Conventions

| Concept | Item type string | Template constant | Defined in |
|---------|-----------------|-------------------|------------|
| NPC corpse | `"npc_corpse"` | `I_CORPSE` | `area_limbo.py` ~line 148 |
| PC corpse | `"pc_corpse"` | `I_CORPSE_11` | `area_limbo.py` ~line 157 |
| Severed head | `"food"` | `I_HEAD` | `area_limbo.py` ~line 167 |
| Torn heart | `"food"` | `I_HEART` | `area_limbo.py` ~line 176 |
| Sliced arm | `"food"` | `I_ARM` | `area_limbo.py` ~line 185 |
| Sliced leg | `"food"` | `I_LEG` | `area_limbo.py` ~line 194 |
| Guts | `"food"` | `I_GUTS_ENTRAILS` | `area_limbo.py` ~line 203 |
| Brains | `"food"` | `I_BRAINS_BRAIN` | `area_limbo.py` ~line 212 |

All templates already defined and unused. No new vnums needed.

---

## Memory Budget

- NPC corpses: 3–6 tick lifetime, cleaned by `obj_update`. Max ~5–10 in world at once.
- Body parts: 4–7 tick lifetime, simple items (no contents list). Lightweight.
- PC corpses: 25–40 ticks but empty (no contents), minimal overhead.
- `obj_update` prevents accumulation — rooms self-clean each tick.
