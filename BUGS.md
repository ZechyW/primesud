# PrimeSUD — Known Bugs

Verified against source code. Grouped by severity, ranked by impact within each
group.

---

## Critical

### 1. `do_flee` crash on wimpy auto-flee

`combat.py` `damage()` calls `do_flee([])` instead of `do_flee(victim, [])`.
Passes `[]` as `ch`, omits `args`. Crashes with `TypeError` when any wimpy mob
drops below HP threshold or player has wimpy set.

Intermittent: requires specific HP% to trigger wimpy check.

### 2. Enchantment makes items weaker, not stronger

Two compounding bugs:

- `spell_enchant_armor` writes per-bucket AC locations (`ac_pierce`, `ac_bash`,
  `ac_slash`, `ac_exotic`) that `affect_modify` does not recognize. Falls
  through every `elif` silently. Enchanting armor has zero AC effect.

- Enchanting any item with template `stat_bonuses` sets `enchanted = True`
  without first copying template bonuses to runtime `affect_list`. Since
  `_apply_item_modifiers` skips template bonuses when `enchanted` is True,
  a +3 hitroll sword becomes +1 after "successful" enchant.

  1stMud copies all template affects to object runtime list before setting
  `enchanted = true`. PrimeSUD skips this step.

### 3. Player spell affects not saved or loaded

`game_state.py` never serializes `affect_list`. All active spell buffs
(sanctuary, haste, armor, giant strength, etc.) vanish silently on save/load.
Current HP/MP from save may exceed recomputed max values with no clamping.

### 4. Corpse contents destroyed on decay

`update.py` `obj_update` deletes the `contents` list when corpse timer reaches
0. Items inside unlooted corpses are permanently gone. 1stMud drops NPC corpse
contents to room floor before removing corpse.

---

## High

### 5. Unequip clears bitvector flags shared with active spells

Unequipping an item whose bitvector matches an active spell flag (e.g. haste
boots while haste spell is active) removes `affected_by["haste"]` entirely. No
`affect_check` rebuild runs afterward. All code checking for haste returns
False despite spell still in `affect_list`.

Affects all bitvector flags: `haste`, `sanctuary`, `invisible`, `flying`,
`detect_*`, `protect_*`, etc.

### 6. `spell_haste` on slowed target: slow removed but haste never applied

`magic.py` `spell_haste`: when target is slowed, `check_dispel` succeeds
(returns True), `not check_dispel` is False, the `if` block is skipped, and
`return False` fires unconditionally. Slow is removed but haste never applied.
`do_cast` treats it as failed spell.

### 7. `spell_stone_skin` checks caster instead of target

`magic.py` `spell_stone_skin`: `is_affected(ch, sn)` should be
`is_affected(vo, sn)`. When cast on another target, checks whether the
**caster** already has stone skin. Stacking duplicates or false rejections
possible.

### 8. `spell_teleport` loads entire world into memory

`magic.py` `spell_teleport` iterates `ROOM_DEFS` which has
`load_all_on_iter=True`. Forces every area to load. On HP Prime's constrained
heap, likely OOM crash.

---

## Medium

### 9. Autoloot targets oldest corpse, not the freshly killed one

`make_corpse` appends new corpse to end of `room["items"]`.
`get_obj_list("corpse", ...)` returns first match. When multiple NPC corpses
exist in room, autoloot operates on oldest (already-looted) corpse.

### 10. Double area reset on lazy load

Unloaded areas have age capped at 15 ticks. When lazy-loaded, `_load_area`
calls `reset_area` (first reset). Age is not zeroed, so next `area_update` tick
sees age >= threshold and triggers second reset. Duplicate mob spawns and item
placements.

### 11. `spell_chill_touch` STR debuff stacks without bound

Uses `affect_to_char` (always appends new affect) instead of 1stMud's
`affect_join` (merges with existing). Each chill touch hit that fails saving
throw adds independent -1 STR. Long fights accumulate many stacks.

### 12. `obj_cast_spell` sets target name to spell name

`magic.py` `obj_cast_spell` sets `ch["_spell_target_name"] = spell_name`
instead of actual target name. Spells using `_spell_tail(ch)` (locate object,
farsight, control weather, continual light) receive spell name as argument when
cast from scrolls/wands/staves.

### 13. Player inventory item timers never tick

`update.py` `obj_update` skips player with `if not ch.get("is_npc"): continue`.
Items with `rot_death` flag picked up by player (which get
`timer = randint(5, 10)` from `make_corpse`) never have timer decremented.
Become permanent.

### 14. Item instance level not serialized

`item.py` `serialize_item_token` never writes item level. Enchant spells
increment `vo["level"]`, but after save/load it reverts to template default.
Successive enchants don't accumulate level bump. Affects enchant failure
calculations and `dispel_magic`/`remove_curse` difficulty.

---

## Low

### 15. Container content timers never tick

`update.py` `obj_update` only iterates top-level room items. Items nested
inside containers/corpses never have timers decremented. Less impactful because
container timer fires first (but see bug 4 -- those items are destroyed, not
dropped).

### 16. Cross-area object resets miss on first load

Loading an area with resets targeting rooms in other areas triggers loading the
target area, which runs `reset_area` before the cross-area reset is appended.
Objects don't appear until target area's next natural reset (~15 ticks). Affects
4 specific resets in current area data.

### 17. No recursion guard during area reset partitioning

`_load_area` adds to `_LOADED_AREAS` after the reset loop that can trigger
cross-area loads via `LazyDict`. Mutual cross-area resets would cause infinite
recursion. Not triggered by current data, but latent crash.

### 18. Cross-area mob deferred saves silently dropped

Mob template from area A saved at room in area B. When B loads,
`_vnum_to_tag(mob_vnum) != "B"` skips the entry. Mob lingers until next save,
then silently dropped. Cross-area mob position permanently lost.

---

## Test priorities

Highest-ROI test scenarios that expose multiple bugs:

1. **Enchant any item** -- exposes bugs 2, 5, 14
2. **Save/load with active buffs** -- exposes bug 3
3. **Wimpy flee** -- exposes bug 1 (outright crash)
4. **Let corpse decay with loot inside** -- exposes bug 4
5. **Cast haste on slowed target** -- exposes bug 6
6. **Cast teleport** -- exposes bug 8 (OOM on device)
