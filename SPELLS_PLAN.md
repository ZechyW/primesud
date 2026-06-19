# PrimeSUD Spell System Fidelity Plan

## Scope

Compare current PrimeSUD spell runtime against 1stMud 4.5.3 equivalents and define a full-fidelity port plan for command flow, spell dispatch, effect handling, output text, naming, and data conventions.

Primary files:

- PrimeSUD: `primesud.hpappdir/magic.py`, `actor.py`, `skill_utils.py`, `skills_table.py`, `world.py`, `player.py`, `combat.py`, `info.py`
- 1stMud: `reference/1stMud4.5.3/src/magic.c`, `magic2.c`, `effects.c`, `skills.c`, `update.c`, `fight.c`, `act_obj.c`

## Current State

PrimeSUD already has a generated skill table with 1stMud spell metadata:

- `spell_fun`
- `target`
- `min_pos`
- `min_mana`
- `beats`
- `noun_damage`
- `msg_off`
- `msg_obj`
- per-class `skill_level` and `rating`, flattened in `world.py`

Runtime support is shallow. `magic.py` currently does:

1. choose a known spell through no-arg picker, or prefix-match `args[0]`;
2. reject unknown/unlearned spells;
3. check current `wait`;
4. spend raw `min_mana`;
5. set `WaitState`;
6. run a local `effect == "heal"` helper if present;
7. call `check_improve(..., True, 1)`.

No `skills_table.py` entry currently defines `effect` or `heal_dice`, so most spells spend mana and do no effect.

## Comparison Table

| Area | PrimeSUD now | 1stMud equivalent | Fidelity gap |
|---|---|---|---|
| Spell catalog | Generated `skills_table.py` mirrors 1stMud fields. | `SkillData skill_table`, loaded from `skills.dat`. | Good base. Runtime ignores most fields. |
| Spell classification | `spell_fun != "spell_null"` means spell. | `skill_table[sn].spell_fun != spell_null`. | Aligned. |
| Spell lookup | `do_cast` manually scans first prefix match. | `find_spell()` records first prefix, but returns usable learned match first. | Use `skill_utils.find_skill_spell()` or port exact logic into `magic.py`. |
| No-arg cast | Opens PrimeSUD picker. | Prints `Cast which what where?` and returns. | PrimeSUD UX extension. Mark `[PRIMESUD]` if kept. |
| Unknown spell output | `You don't know any spell called that.` | `You don't know any spells of that name.` | Text mismatch. |
| Position check | Command table only says `cast` works in `fighting`. | Per-spell `minimum_position`; failure `You can't concentrate enough.` | Missing. |
| Mana cost | Raw `min_mana`. | `max(min_mana, 100 / (2 + ch->level - skill_level(ch, sn)))`, with early-learn special `50`. | `skill_utils.spell_mana()` handles display formula but misses early-learn special. `do_cast` not using it. |
| Target args | Only `args[0]` used. | `arg1 = spell`, `target_name = rest`, `arg2 = first target word`. | Missing command tail parsing. |
| Target types | None. | `TAR_IGNORE`, `TAR_CHAR_OFFENSIVE`, `TAR_CHAR_DEFENSIVE`, `TAR_CHAR_SELF`, `TAR_OBJ_INV`, `TAR_OBJ_CHAR_OFF`, `TAR_OBJ_CHAR_DEF`. | Largest missing piece. |
| Runtime target enum | None. | Spell receives `TARGET_CHAR`, `TARGET_OBJ`, `TARGET_ROOM`, or `TARGET_NONE`. | Need constants and resolved `vo`. |
| Offensive default target | None. | If no target, use `ch->fighting`; else ask `Cast the spell on whom?`. | Missing. |
| Defensive default target | Self. | If no target, self; else room character. | Missing except implicit self. |
| Self-only handling | None. | Reject other target with `You cannot cast this spell on another.` | Missing. |
| Object targeting | None. | Inventory or room object depending target type. | Missing. |
| Safety checks | None. | `is_safe`, `is_safe_spell`, `check_killer`, charm/follower blocks. | Need single-player equivalents: no PvP, but offensive target validation and aggro needed. |
| Incantation output | None. | `say_spell()` emits true/scrambled spell words to room. Skips `ventriloquate`. | Missing. In single-user, can omit room-only text or show compact room event. |
| Wait state | Set before effect. | Set after incantation and before concentration roll. | Mostly aligned. |
| Concentration | Always succeeds. | `number_percent() > get_skill(ch, sn)` fails; prints `You lost your concentration.`, spends half mana, improves failure. | Missing. |
| Spell dispatch | String `effect` switch. | Function pointer call: `spell_fun(sn, level, ch, vo, target) -> bool`. | Need Python registry. |
| Spell level passed | Player level always. | Full level for NPCs or spellcasters; `3 * level / 4` if player has no spells. | Classes deferred; likely use full level for PrimeSUD until class system exists. Mark if deviating. |
| Improvement | Always success. | `check_improve(ch, sn, ret, 1)` after function return; failed concentration uses `false`. | Need return bool from spell funcs. |
| Spell output | Custom heal prints HP numbers. | Individual spell functions print exact messages, e.g. cure light: `You feel better!`, caster sees `Ok.` if other victim. | Need exact visible strings. |
| Offensive aftermath | None. | Offensive casts make victim attack if not already fighting. | Need integration with PrimeSUD fight state. |
| Damage | Not handled by spells. | Spells call `damage(ch, victim, dam, sn, dam_type, true)`. | Need spell damage adapter using existing combat/raw kill flow. |
| Saves | None. | `saves_spell(level, victim, dam_type)` with saving throw, berserk, immunity/resistance/vulnerability. | Saving throws explicitly not ported in `DESIGN.md`; full fidelity needs design change. |
| Dispel | None. | `saves_dispel()` and `check_dispel()`, strips affects and prints `msg_off`. | Missing. |
| Affects | `char["affects"]` keyed by `sn`, one `loc/modifier/duration`. | Linked `AffectData`: `where/type/level/duration/location/modifier/bitvector`; multiple affects possible. | Need expanded model. |
| Affect expiry | Player ticks decrement and print `msg_off` unless it starts with `!`. | `update.c` prints `skill_table[paf->type].msg_off`; object affects use `msg_obj`. | Char side partial. Object side missing. |
| Affect flags | Static mob `aff_flags`; dynamic spell flags not tracked for player display. | Bitvectors like `AFF_BLIND`, `AFF_SANCTUARY`, `AFF_POISON`. | Need dynamic flags or compact flag set per actor. |
| Object spell casts | Not present. | `obj_cast_spell()` handles pills, potions, scrolls, wands, staves. | Needed for magical items already present in areas. |
| Element effects | Not present. | `acid_effect`, `cold_effect`, `fire_effect`, `poison_effect`, `shock_effect` affect chars, rooms, objects. | Later phase. |
| Display: `spells` | Level list uses dynamic mana. | `do_spells` same structure. | Mostly aligned; update `spell_mana()` exact formula. |
| Display: `affects` | Prints name, loc, modifier, duration. | 1stMud shows type/level/modifier/duration in act info. | Acceptable partial; update after affect model changes. |

## Full-Fidelity Naming Conventions

Use 1stMud names where directly ported:

- `do_cast`
- `find_spell`
- `say_spell`
- `saves_spell`
- `saves_dispel`
- `check_dispel`
- `obj_cast_spell`
- `spell_null`
- `spell_cure_light`, `spell_armor`, etc.
- `TARGET_CHAR`, `TARGET_OBJ`, `TARGET_ROOM`, `TARGET_NONE`
- target strings from generated data: `ignore`, `char_offensive`, `char_defensive`, `char_self`, `obj_inventory`, `obj_char_defensive`, `obj_char_offensive`

Python adapters may keep PrimeSUD readability when no exact 1stMud symbol exists, but docstrings should cite 1stMud source symbols for ported functions.

## Data Conventions

Do not hand-edit `skills_table.py`. It is generated from 1stMud `skills.dat`.

Runtime spell implementation belongs in `magic.py` or a split module only if `magic.py` becomes too large for HP Prime memory/readability. If split, prefer:

- `magic.py`: `do_cast`, target routing, saves/dispatch shared helpers
- `spells.py`: `spell_*` functions
- `effects.py`: elemental/object effects if ported

Keep generated table fields as strings and map to Python functions with a compact registry:

```python
SPELL_FUNS = {
    "spell_cure_light": spell_cure_light,
    "spell_armor": spell_armor,
}
```

Use exact spell function names as keys. Missing spell functions should fail without spending mana during development, with a developer-facing message or `spell_null` fallback. Final gameplay should not expose missing implementation.

## Proposed Runtime Flow

Port `do_cast` in this order:

1. Parse `arg1` as spell name and `target_name` as remaining words.
2. If no `arg1`, either:
   - strict fidelity: print `Cast which what where?`; or
   - keep PrimeSUD picker, tagged `[PRIMESUD]`, then continue with selected spell and empty target.
3. Resolve `sn` through `find_spell`.
4. Reject unknown, non-spell, unusable, or unlearned spell with `You don't know any spells of that name.`
5. Check `min_pos`; reject with `You can't concentrate enough.`
6. Compute mana with exact 1stMud formula.
7. Resolve target from `sk["target"]`:
   - `ignore`: `vo = None`, `target = TARGET_NONE`
   - `char_offensive`: target mob in room or current fighting target
   - `char_defensive`: target actor in room, default player
   - `char_self`: player only
   - `obj_inventory`: carried object only
   - `obj_char_offensive`: room actor or room object, default fighting actor
   - `obj_char_defensive`: actor or carried object, default player
8. Check mana; reject with `You don't have enough mana.`
9. `say_spell()` unless spell name is `ventriloquate`.
10. `WaitState(player, sk["beats"])`.
11. Roll concentration against `get_skill(player, sn)`.
12. On failure:
    - print `You lost your concentration.`
    - `check_improve(..., False, 1)`
    - spend `mana // 2`
13. On success:
    - spend full mana
    - call registered `spell_fun`
    - `check_improve(..., ret, 1)`
14. If offensive target survived and is not already fighting, start combat against player.

## Affect Model Proposal

Current keyed-by-`sn` dict is too small for 1stMud fidelity. Use compact list of dicts:

```python
{
    "where": "affects",
    "type": sn,
    "level": level,
    "duration": 24,
    "location": "AC",
    "modifier": -20,
    "bitvector": "",
}
```

Reasons:

- 1stMud spells can apply no stat modifier but set bitvector.
- Some spells may need multiple affects of same `type`.
- `check_dispel` needs affect level and duration.
- Expiry text uses `skill_table[type].msg_off`.

Add helpers:

- `is_affected(char, sn)`
- `affect_find(char, sn)`
- `affect_to_char(char, af)`
- `affect_remove(char, af)`
- `affect_strip(char, sn)`
- `affect_check(char, where, bitvector)` if dynamic flags need recalculation

Keep existing `affect_modify` for stat locations, but accept 1stMud-style `location` names. Add location mapping only as needed:

- `APPLY_NONE` -> `none`
- `APPLY_STR` -> `str`
- `APPLY_DEX` -> `dex`
- `APPLY_INT` -> `int`
- `APPLY_WIS` -> `wis`
- `APPLY_CON` -> `con`
- `APPLY_HIT` -> `hp`
- `APPLY_MANA` -> `mp`
- `APPLY_AC` -> `AC`
- `APPLY_HITROLL` -> `hitroll`
- `APPLY_DAMROLL` -> `damroll`

## Saves Proposal

`DESIGN.md` currently says saving throws are not ported. Full spell fidelity needs this decision reopened.

Minimum viable fidelity:

- Add `saving_throw` field to player and mobs, default `0`.
- Implement `saves_spell(level, victim, dam_type)` formula:
  - `save = 50 + (victim_level - level) * 5 - saving_throw * 2`
  - berserk bonus later when berserk exists
  - immune/resist/vuln later when damage flags exist
  - clamp `5..95`
  - `randint(1, 100) < save`
- Implement `saves_dispel(dis_level, spell_level, duration)`.
- Implement `check_dispel(dis_level, victim, sn)`.

Tag deferred immunity/resist/vuln branches with TODOs tied to `DESIGN.md`.

## Output Rules

Default: exact 1stMud visible text.

Examples:

- Unknown spell: `You don't know any spells of that name.`
- Missing target offensive: `Cast the spell on whom?`
- Missing target object/offensive: `Cast the spell on whom or what?`
- Missing inventory object: `What should the spell be cast upon?`
- Target not present: `They aren't here.`
- Self-only rejection: `You cannot cast this spell on another.`
- Mana fail: `You don't have enough mana.`
- Concentration fail: `You lost your concentration.`
- Cure light victim output: `You feel better!`
- Cure light caster output when different victim: `Ok.`

Do not add HP deltas or explanatory text to fidelity spells unless marked `[PRIMESUD]`.

## Port Phases

### Phase 1: Cast Infrastructure

- Replace manual lookup with exact `find_spell` behavior.
- Add exact `spell_mana` formula.
- Add target constants and target resolver.
- Add `SPELL_FUNS` registry and `spell_null`.
- Add concentration roll.
- Add exact player-visible error strings.
- Keep no-arg picker only if tagged `[PRIMESUD]`.

Acceptance:

- `cast` with no args matches chosen decision.
- unknown spell text matches 1stMud.
- `cast cure light` resolves self and spends dynamic mana.
- unsupported spell does not silently spend mana.

Status: complete in checkpoint `8c1****`.

### Phase 2: Healing and Simple Damage

Port:

- `spell_cure_light`
- `spell_cure_serious`
- `spell_cure_critical`
- `spell_heal`
- `spell_cause_light`
- `spell_cause_serious`
- `spell_cause_critical`
- `spell_harm`
- `spell_magic_missile`

Add spell damage adapter that:

- subtracts HP;
- prints through existing damage messaging where possible;
- calls `raw_kill` / advancement path if target dies;
- starts combat for offensive spell.

Acceptance:

- Cure spells print exact target/caster messages.
- Cause/damage spells can kill mobs and advance XP through existing combat kill path.

Status: complete pending review.

### Phase 3: Buffs and Affect Expiry

Port affect model and:

- `spell_armor`
- `spell_shield`
- `spell_bless` char path first
- `spell_giant_strength`
- `spell_weaken`
- `spell_faerie_fire`

Acceptance:

- duplicate affect rejection messages match 1stMud.
- stat/AC modifiers apply and unapply.
- `msg_off` prints on expiry unless `!`.

### Phase 4: Saves, Debuffs, and Cure/Dispel

Before this phase, update `DESIGN.md` to reopen the saving-throws decision and document PrimeSUD's minimal `saving_throw = 0` baseline plus deferred immunity/resistance/vulnerability branches.

Port:

- `saves_spell`
- `saves_dispel`
- `check_dispel`
- `spell_blindness`
- `spell_poison`
- `spell_curse`
- `spell_plague`
- `spell_cure_blindness`
- `spell_cure_poison`
- `spell_cure_disease`
- `spell_dispel_magic`

Acceptance:

- saved spell halves/blocks exactly per spell function.
- cure spells fail with exact text when target lacks condition.
- dispel strips effects and prints `msg_off`.

### Phase 5: Object Spells and Magical Items

Port:

- `obj_cast_spell`
- potion/quaff integration
- scroll recite integration
- wand/staff use integration
- object-target spell paths for `bless`, `curse`, `enchant_*`, `fireproof`, `detect_poison`, `identify`

Acceptance:

- area potions with `spell_level` and spell slots invoke same spell funcs.
- object target messages match 1stMud where visible.

### Phase 6: Area/Element/Travel Spells

Port as content needs:

- elemental effects from `effects.c`
- breath spells
- `earthquake`, `call_lightning`, `chain_lightning`
- `word_of_recall`, `teleport`, `summon`, `gate`, `portal`, `nexus`
- `locate_object`, `farsight`, weather spells

Acceptance:

- no spell listed to player silently no-ops.
- unsupported/deferred spells are hidden or explicitly unavailable until implemented.

## Test Plan

CPython sanity tests where possible:

- import all touched modules;
- run ASCII check: `python tools/check_ascii_py.py`;
- targeted fake-terminal tests for:
  - unknown spell;
  - no mana;
  - concentration fail using forced RNG seam;
  - cure light self;
  - offensive target missing;
  - duplicate armor;
  - affect expiry.

On HP Prime emulator:

- cast known healing spell from prompt;
- cast offensive spell in combat and out of combat;
- verify wait prevents immediate recast;
- verify prompt MP changes;
- verify no heap-sensitive `%` formatting enters persisted strings.

## Decisions

1. Keep no-arg `cast` picker as a `[PRIMESUD]` calculator-UX extension. Typed casts still follow exact 1stMud command flow and output. Picker flow may use multiple stages:
   - `cast` opens a spell picker, then opens a target picker if the chosen spell needs a target and no default applies;
   - `cast <spell>` opens a target picker only if the spell needs a target and no default applies;
   - `cast <spell> <target>` never opens a picker and uses exact typed-flow errors.
   Target picker defaults by target type:
   - `char_offensive`: use current fighting target, otherwise pick visible hostile mobs in room;
   - `char_defensive`: default to self;
   - `char_self`: self only, no picker;
   - `obj_inventory`: pick carried item;
   - `obj_char_offensive`: use current fighting target, otherwise pick visible hostile mobs and room objects;
   - `obj_char_defensive`: first pass defaults to self; later object-useful spells may offer carried item picker.
2. Port minimal saving throws and update `DESIGN.md`. Full spell fidelity needs `saves_spell`, `saves_dispel`, and `check_dispel`. Start with `saving_throw = 0` on player/mobs; defer immunity/resistance/vulnerability and class/race modifiers.
3. Classless PrimeSUD casts at full `player["level"]`. Do not apply the 1stMud `has_spells()` / `3 * level / 4` non-spellcaster penalty until classes exist. Mark this as `[PRIMESUD]`.
4. Reproduce every 1stMud message where the PrimeSUD player is the recipient:
   - show `TO_CHAR` when `ch` is the player;
   - show `TO_VICT` when `victim` is the player;
   - show `TO_ROOM` only when the player would be among room recipients, such as mob/NPC spellcasting in the player's room;
   - do not show player-cast `say_spell()` output, because 1stMud sends it only to others;
   - show mob-cast `say_spell()` if the player is in the room, using scrambled words unless a later class system makes true-word visibility meaningful.
5. Hide unimplemented spells from `spells` and `cast` until their `spell_fun` exists in the runtime registry. Generated `skills_table.py` still keeps all 1stMud spell data.
6. Implement cast dispatch, healing, and simple damage before rewriting the full affect model. Port affects when first buff/debuff spells land.
7. Port magical item casting after character spell dispatch and affect model, but before exotic area/element/travel spells.

## Final Validation: Expected Remaining Gaps

After this plan is fully implemented, PrimeSUD should match 1stMud's core player-visible cast flow: spell lookup, target resolution, mana cost, wait state, concentration failure, spell dispatch, saves/dispel, affects, user-facing spell messages, and offensive aggro.

Remaining differences should be limited to systems outside the spell port or explicit PrimeSUD deviations:

- classless design: flattened spell levels, no multiclass `has_spells()` penalty;
- no race system: no race skills, stat caps, save modifiers, or race resist/vuln;
- minimal saving ecosystem: `saving_throw = 0` baseline unless gear/class/race saves are later added;
- deferred immunity/resistance/vulnerability branches until combat damage flags support them;
- no alignment/deity model, so good/evil/deity-dependent spells may need PrimeSUD-specific handling;
- simplified multiplayer safety: no PK, clans, followers, or full `is_safe`/`check_killer` semantics;
- output limited to messages the player would receive; other-player and mob-only messages are omitted;
- `say_spell()` true-word visibility remains classless, so mob-cast words are likely scrambled;
- object/room elemental side effects from `effects.c` may remain partial unless content needs them;
- travel/weather/sector-dependent spells may be constrained by PrimeSUD's simpler world model;
- NPC spellcasting AI and specials remain separate from player `do_cast` fidelity;
- exact C linked-list affect ordering and bitvector recomputation may differ where behavior is not player-visible;
- spell damage may use PrimeSUD's combat adapter instead of exact 1stMud `damage()` message/death plumbing;
- pfile/OLC/admin/web/MSP sound behavior remains out of scope.
