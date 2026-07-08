# REGEN_PLAN.md -- Regen fidelity: player gain modifiers + mob regeneration

> 1stMud sources: `reference/1stMud4.5.3/src/`. Depends on: nothing;
> independent of the other plans.
> On completion: add DESIGN.md "Not ported" row for furniture mechanics
> (decision 3) unless Phase C was built; strike player.py TODO comments;
> delete this file.

Close the gaps in `player.py tick_update` (cf. 1stMud `hit_gain` /
`mana_gain` / `move_gain`, update.c:161-373). Current state (verified
08/07/2026):

- Player position divisors, `heal_rate`/`mana_rate` room multipliers: done.
- Player TODOs in place (player.py:241/251/263/275): fast healing,
  meditation, poison/plague/haste-slow penalties -- not ported.
- `has_spells` mana halving (update.c:281): not ported; helper already
  exists (classes.py:203).
- **Mobs never regen hp/mana at all.** tick_update's `world.chars` loop
  (player.py:284+) only ticks affects; 1stMud's NPC branch
  (update.c:169-190, 251-267) is absent. Gameplay impact: fled-from mobs
  stay wounded forever; troll `regeneration` racial and the quest
  regeneration ring (area_quest.txt:307) are dead keys.
- Furniture (`ch->on`, sit/rest/sleep targets, value[3]/value[4] regen
  multipliers): not ported, and **content is dead everywhere** -- the 7
  furniture-typed items in loaded areas are signs/letters/junk with zero
  values, and all 16 furniture objects across the entire stock QuickMUD
  set carry `0 0 0 0 0` values (surveyed 08/07/2026). See decision 3.

## Decisions

1. **Player gain modifiers -- full port, 1stMud order.** In tick_update,
   per gain, matching update.c exactly:
   - hp (update.c:193-201): after base, roll `number_percent()`; if roll <
     get_skill('fast healing'): `gain += roll * gain // 100`, and if
     hp < max_hit call `check_improve(player, <fast healing>, True, 8)`
     (skill_utils.py:131; resolve the skill vnum the same way other
     consumers of skills_table do).
   - mana (update.c:274-282): same shape with 'meditation' (improve gated
     on mana < max_mana), then `if not has_spells(player): gain //= 2`.
   - All three gains, after the room-rate multiply (update.c:231-238):
     poison affect -> `//= 4`; plague -> `//= 8`; haste OR slow -> `//= 2`.
     Affect keys per affected_by dict ('poison', 'plague', 'haste',
     'slow' -- verify plague key exists; if plague isn't ported yet, keep
     the branch with an inline note). Hunger/thirst halving stays omitted
     [PRIMESUD] (settled in DESIGN.md).
   - Keep integer math throughout; final `max(1, ...)` clamp is a
     PrimeSUD deviation (1stMud allows 0 gain via Min-with-deficit) --
     actually re-check: 1stMud has no floor, so drop the `max(1, ...)` and
     rely on the min-with-max clamp to match upstream exactly, or keep the
     floor with a [PRIMESUD] comment; decide against the source when
     editing, don't leave it ambiguous.
2. **Mob regen -- port the NPC branch** into the existing mob loop in
   tick_update (player.py:284+), same tick cadence as the player:
   - hp (update.c:171-188): `gain = 5 + level`; `affected_by.regeneration`
     -> `gain *= 2`; position: sleeping -> `3 * gain // 2`, resting ->
     unchanged, fighting -> `//= 3`, anything else -> `//= 2`.
   - mana (update.c:253-267): same minus the regeneration doubling.
   - Then the shared tail: room heal_rate/mana_rate (mob's own room, not
     the player's -- resolve `world.rooms[mob["room"]]`... via ROOM_DEFS
     for the rates) and the poison/plague/haste/slow divisors. Factor the
     tail as one small shared helper [PRIMESUD] rather than duplicating.
   - Clamp to max_hit/max_mana. Verify the mob dict's position key and
     value spellings (mob.py sets start_pos at spawn) before branching.
   - Heap/CPU note: loop already exists and iterates loaded mobs only;
     the added work is integer arithmetic, no new allocations. Skip mobs
     already at full hp AND full mana early.
3. **Furniture: skip (default).** No object in loaded areas or anywhere in
   stock QuickMUD carries furniture flags/occupancy/heal values -- an
   engine port would be 100% dead code until PrimeSUD authors its own
   furniture content. Inns already regen faster via room heal_rate 110
   (e.g. area_midgaard.txt:2160), which covers the "rest at the inn" loop.
   Add a DESIGN.md "Not ported" row: furniture mechanics (sit/rest/sleep
   AT/ON/IN targets, occupancy, regen bonuses) omitted for lack of any
   content; revisit alongside authored content. If that decision is ever
   reversed, the full source map is: flag bits bits.h:404-419 (STAND_AT..
   PUT_INSIDE), command handling act_move.c:1010-1470 (do_stand/do_rest/
   do_sit/do_sleep furniture-argument paths, exact messages, count_users
   occupancy gate), `ch->on` lifecycle handler.c:83 (count_users),
   handler.c:1328 (char_from_room clears), handler.c:1681 (extract clears),
   look rendering act_info.c:265-352 ("is sleeping in $p" variants), regen
   multipliers update.c:228-229/309-310/360-361 (value[3] hp+mv,
   value[4] mana). The current do_sit/do_rest/do_sleep/do_stand docstrings
   already say "Furniture keyword -- not ported, ignored [PRIMESUD]" --
   leave those as-is under this decision.

## Touch points

- `player.py tick_update`: decisions 1-2 (the function is cf.-tagged but
  not `[Verified]`; the TODO comments are the work order).
- `classes.py has_spells`: consume, don't change.
- `DESIGN.md`: furniture row (decision 3).
- `TODO.md`: nothing listed for regen; no strikes needed.

## Verification

- pytest: gain-math table -- fast-healing roll boundary (roll == skill%
  is a miss: `<` not `<=`), meditation + has_spells stacking for a
  warrior (no spells) vs mage, poison+haste stacking order, mob position
  branches, regeneration doubling, heal_rate interaction.
- PC shim: wound a mob, flee, wait ticks -> it heals; troll PC vs human
  PC regen delta; hasted player regens at half; sleeping at the inn
  (heal_rate 110) beats sleeping on the street.
- Confirm no per-tick slowdown with a full midgaard loaded (mob loop
  early-out).
- `python tools/check_ascii_py.py`.
