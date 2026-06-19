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

Status: complete pending review.

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

Status: complete pending review.

## Phase 4a: Check player-facing output

Mini-phase 4a completed the low-risk player-facing output pass before Phase 5:

- non-self healing wound spells now show caster `Ok.` only;
- non-self buff/debuff/save/cure messages now use target-name caster-visible text instead of generic `They...` wording;
- cure condition and dispel paths suppress victim-only `msg_off` when the player terminal represents a different caster;
- `spell_dispel_magic` success now prints caster `Ok.`, including direct self-cast.

Remaining gaps before/after Phase 5:

- object spell stubs still print PrimeSUD placeholder text and are deferred to Phase 5;
- command-level `cast dispel magic self` still does not resolve because `dispel magic` is a `char_offensive` spell and current offensive routing only targets mobs; changing that may also expose self-target offensive damage crashes, so keep it separate from message parity;
- spell damage output uses PrimeSUD combat adapter text, not exact 1stMud `damage()` / `dam_message()` output. Spell damage text is close enough for Phase 5 unless magical items expose damage spells; unify the separate spell damage path before Phase 6.

Status: complete pending review.

### Phase 5: Object Spells and Magical Items

Phase 5 should stop at explicit review gates. Do not bundle runtime dispatch,
item schema backfill, command wiring, and object-affect persistence into one
sweep.

### Phase 5a: Object-Cast Runtime and Item Spell Payload

Port:

- `obj_cast_spell`
- shared target routing for item casts, reusing spell target constants and as
  much command-path logic as practical without reopening player `cast`
  behavior
- item-spell payload normalization for PrimeSUD item templates and instances:
  - `spell_level`
  - `spells` list for potions/scrolls/pills
  - `charges` and `max_charges` for wands/staves
  - single-spell slot for wand/staff activation
- minimal area-data backfill for shipped magical items that already exist in
  PrimeSUD areas but do not yet carry enough metadata to cast
- developer-visible failure path for bad item spell data; no silent consume,
  no silent zero-effect activation

Item save-format decision for Phase 5a:

- bump `SAVE_VERSION` to `2`
- replace legacy item token `vnum:cost`
- keep outer save lines unchanged:
  - `p.inv=...`
  - `p.eq.<slot>=...`
  - `r.<room>.items=...`
- each item token becomes `;`-separated tagged fields
- item lists stay `|`-separated

Grammar:

```text
item-token := field (';' field)*
field      := key ':' value
```

Reserved separators:

- `~` line separator
- `=` line key/value separator
- `|` item-list separator
- `;` item-field separator
- `:` item key/value separator
- `,` compact tuple separator inside one field

Required item field:

- `v:<vnum>`

Core mutable-state fields:

- `c:<cost>` item cost override
- `ch:<n>` current charges
- `mx:<n>` max charges
- `en:1` enchanted flag

Future-proof object-state fields:

- `ef:<flag1>,<flag2>,...`
  - full active extra-flag override set
  - absent means "use template flags"
- repeatable `af:<sn>,<level>,<duration>,<location>,<modifier>,<bitvector>,<where>`
  - source of truth for object spell affects
  - empty bitvector allowed, e.g. `...,1,,obj`
  - compact wire format only; in-memory object affects should reuse the same
    explicit dict keys already used for character affects:
    `where`, `type`, `level`, `duration`, `location`, `modifier`,
    `bitvector`

Examples:

```text
v:3988;c:200
v:3610;c:320;ch:7;mx:10
v:5001;c:1200;en:1;ef:magic,bless;af:42,20,24,AC,-20,bless,obj
p.inv=v:3610;c:320;ch:7;mx:10|v:3988;c:200
p.eq.hold=v:3718;c:4700;ch:2;mx:3
r.3001.items=v:5001;c:1200;en:1;ef:magic,bless;af:42,20,24,AC,-20,bless,obj
```

Deferred from initial v2 item schema:

- no `sb:` stat-bonus field in v2; derive object stat effects from `af`,
  matching 1stMud's object-affect-first model
- no wear-flag persistence unless runtime starts mutating wear flags
- no extra-description persistence
- no nested container persistence redesign yet

Implementation notes:

- area/item templates keep 1stMud-style spell names
- save payload stores only runtime mutable item state
- item-token encode/decode helpers should live in `item.py`, not `player.py`,
  so Phase 5b/5c item mutation code shares one schema authority
- keep those `item.py` helpers data-only:
  - no `player.py` import
  - no `magic.py` import
  - no spell-function lookup during save/load parsing
  - `af` entries stay plain dicts until normal runtime code consumes them
- reuse exact affect dict shape in memory for readability and helper sharing;
  only the save wire format is compact/positional
- parser requires `v`, collects repeated `af`, and treats absent optional
  fields as template/default values
- bad area spell names must fail loud and must not silently consume/expend the
  item
- `SAVE_VERSION = 2` intentionally invalidates legacy v1 saves
- do not build a v1-to-v2 item-token migration path in Phase 5a
- rely on existing version-mismatch flow:
  - backup old payload to `SAVE_VAR + "_bak"`
  - warn the player
  - offer new game or quit
- rationale: v1 item tokens only preserve `vnum:cost`, so there is no richer
  mutable magical item state worth rescuing through a bespoke migration layer

Validation checkpoint:

- add focused CPython tests for `obj_cast_spell` target resolution:
  - offensive default to current fighting target;
  - defensive default to self;
  - object-target spells reject missing object cleanly;
  - offensive item casts still trigger aggro when target survives
- run:
  - `python -m unittest tests.test_magic_phase1`
  - `python tools/check_ascii_py.py`

Review gate:

- before code, validate exact v2 item schema above
- after parser/save draft, confirm `af` still covers all implemented object
  stat overrides; only add a non-1stMud `sb` field later if a PrimeSUD-only
  object mechanic truly cannot be expressed as affects

- chosen direction: keep area templates readable with 1stMud-style spell
  names, resolve through runtime lookup, and store only mutable charges on
  instances
- on missing/typoed spell names, fail loud during development and do not
  silently consume or expend item use

Status: complete pending review.

### Phase 5b: Player Commands for Magical Items

Port:

- replace current `do_quaff` placeholder with 1stMud potion flow
- add `do_recite`
- add `do_zap`
- add `do_brandish`
- add command-table entries in 1stMud order where practical
- enforce visible prerequisites and failure text:
  - potion/scroll item-type checks;
  - held-item checks for wand/staff;
  - level gating;
  - wait state for wand/staff;
  - scroll/wand/staff skill checks and `check_improve`
- consume/exhaust items exactly enough for player-visible parity:
  - potions/scrolls always consumed after attempted use;
  - wand/staff charges decrement on each activation;
  - empty wand/staff destruction text matches 1stMud where visible

Validation checkpoint:

- targeted tests for:
  - `quaff` potion self-cast;
  - `recite` self default and explicit object target;
  - `zap` default fighting target;
  - `brandish` defensive vs offensive room filtering;
  - charge depletion and item removal
- manual review of command text against `act_obj.c`

Review gate:

- once command flow passes, review whether PrimeSUD should support `pill`
  casting in same phase. Default: no; keep pills deferred unless existing area
  data already uses them.

Status: complete pending review.

### Phase 5c: Object-Target Spell Functions

Port in two slices.

Slice 1: low-risk inspection and flag toggles

- `spell_detect_poison`
- `spell_identify` player-visible subset
- object branches of `spell_bless`
- object branches of `spell_curse`

Slice 2: object mutation and persistence

- `spell_fireproof`
- `spell_enchant_armor`
- `spell_enchant_weapon`
- any helper needed for object affects / extra flags / enchanted-state
  persistence

Object-model work likely needed:

- extend item instances beyond `{vnum, cost}` when mutable magic state starts
  to matter
- decide where object affects live:
  - compact `affect_list` on item instances; or
  - narrower per-item override fields for extra flags and stat mods
- confirm save/load path preserves:
  - charges
  - enchanted flag/state
  - object extra-flag mutations
  - object stat modifiers from enchantment

Validation checkpoint after Slice 1:

- `identify` shows spell/charge fields for magical items when applicable
- `detect poison` matches 1stMud visible text for food/drink vs other objects
- bless/curse object paths update visible item state and messages correctly

Validation checkpoint after Slice 2:

- enchanted or fireproofed items survive save/load
- equipped-item stat changes apply and unapply correctly after enchantment
- no duplicated object modifiers after reload/equip cycles

Review gate:

- stop before Slice 2 implementation if persistence shape gets messy. Review
  exact item-instance schema first; this is biggest Phase 5 risk.

Acceptance:

- area potions with `spell_level` and spell slots invoke same spell funcs
- scroll/wand/staff commands match 1stMud visible flow and failure text where
  the player is recipient
- object target messages match 1stMud where visible
- magical item activation never silently no-ops

Status: complete pending review.

### Phase 6: Area/Element/Travel Spells

Before this phase, unify spell damage with the combat damage adapter. Current spell
damage text is close to 1stMud `dam_message()` for caster-visible lines, but
`magic._damage_char()` is a separate mini-damage path and will diverge once Phase
6 adds area/element damage. Extract shared damage-message formatting first, then
route spell damage through shared damage application when feasible.

### Phase 6a: Damage-path unification

Completed:

- extracted shared player-to-mob direct damage helper in `combat.py`
- routed spell damage through shared combat damage text + kill plumbing
- kept existing XP/death/target-advance behavior intact

Validation:

- `python -m unittest tests.test_magic_phase1 tests.test_magic_phase5a tests.test_magic_phase5b tests.test_magic_phase5c`
- `python tools/check_ascii_py.py`

Status: complete in current workspace, pending follow-on Phase 6 review gate.

### Phase 6b: First area spell and fanout rules

Port first:

- `spell_earthquake`

Scope for first slice:

- caster-visible `TO_CHAR` text
- same-room hostile mob damage / flying zero-damage behavior
- survivor aggro hookup
- no cross-room player-hidden fanout yet unless the PrimeSUD player would
  directly receive it

Validation checkpoint:

- focused CPython tests for:
  - earthquake damages all grounded room mobs;
  - flying mobs take zero damage;
  - surviving damaged mobs aggro the player;
  - dead mobs route through normal kill flow
- area weather model exists for `call lightning`, marked `[PRIMESUD]`
  simplified interim until fuller 1stMud-style weather runtime lands

Review gate:

- after `earthquake`, validate message fanout rules before porting
  `call_lightning`, `chain_lightning`, travel, or weather spells

### Phase 6c: Low-risk runtime spells completed

Completed in current workspace:

- `spell_earthquake`
- `spell_call_lightning`
- `spell_chain_lightning`
- `spell_word_of_recall`
- `spell_teleport`
- `spell_farsight`
- `spell_locate_object`
- `spell_control_weather`

Supporting runtime work:

- shared spell-tail storage for `target_name`-style ignore spells
- simplified interim area weather persistence/update model `[PRIMESUD]`
- shared `perform_recall(...)`

Validation:

- focused CPython coverage in `tests.test_magic_phase6`
- full regression run:
  `python -m unittest tests.test_magic_phase1 tests.test_magic_phase5a tests.test_magic_phase5b tests.test_magic_phase5c tests.test_magic_phase6`
- ASCII check:
  `python tools/check_ascii_py.py`

Status: complete for low-risk Phase 6 slice.

### Phase 6d: Remaining high-risk spells

Still deferred because they need larger runtime/model work, not just isolated
spell functions:

- elemental room/object side effects from `effects.c`
- breath spells
- `summon`, `gate`, `portal`, `nexus`

Main reasons:

- no world-wide character search / visibility model yet
- no object/room elemental-effect runtime
- no private/solitary/closed-area destination filtering model matching 1stMud
- no player-safe handling yet for self-hit / room-fanout parity on broader area
  spells
Port as content needs after review:

- elemental effects from `effects.c`
- breath spells
- `earthquake`, `call_lightning`, `chain_lightning`
- `word_of_recall`, `teleport`, `summon`, `gate`, `portal`, `nexus`
- `locate_object`, `farsight`, weather spells

Acceptance:

- no spell listed to player silently no-ops.
- unsupported/deferred spells are hidden or explicitly unavailable until implemented.

Review gates:

- after damage-path unification, review before any room/object side-effect work
- after first area spell (`earthquake` or `call_lightning`), validate message
  fanout rules before porting travel/weather spells

Status: not started.

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
8. Keep magical item spell data in `area_*.py` templates as 1stMud-style spell
   names, not canonical `sn` ids. Resolve names at runtime; only mutable item
   state belongs on instances. Bad spell names must fail loud and must not
   silently consume the item.
9. Keep object stat persistence affect-first like 1stMud. In save format v2,
   do not add a separate `sb` stat-bonus field unless a later PrimeSUD-only
   item mechanic cannot be represented by object affects plus flag/value state.
10. `SAVE_VERSION = 2` is a hard format break for item persistence. Use the
    existing save-version mismatch backup/prompt flow; do not add legacy item
    token migration unless a later change introduces real player data worth
    rescuing.

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
