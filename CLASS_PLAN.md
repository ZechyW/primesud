# CLASS_PLAN.md -- Class + remort/multiclass port from 1stMud

Port of 1stMud's class system (`multiclass.c`, `classes.dat`) into PrimeSUD,
replacing the current classless placeholders. Decisions confirmed 02/07/2026.

## Decisions

1. **Save compat:** none needed -- dev phase, no existing players.
2. **Remort cost:** gold only (500,000). Quest-point requirement (500 qp)
   dropped with `# TODO` for when auto-quests are ported.
3. **Guild rooms:** port `G <class>` fields from 1stMud midgaard.are into
   `area_midgaard.dat` (see table below). Two uses: remort/gating location
   (`do_remort`) and entry restriction for non-members (act_move.c:101).
4. **Chargen:** class choice via `pick_from` picker at new game, with a
   [PRIMESUD] one-line summary per class (1stMud shows a bare list; help
   texts are the only info source there).
5. **Memory:** not a concern; un-flattening `skills_table` removes duplicate
   dicts anyway.

## Class table (from 1stMud data/classes.dat)

| # | Name (remort tiers)   | Prime | thac0 00/32 | HP die | fMana | Weapon |
|---|-----------------------|-------|-------------|--------|-------|--------|
| 0 | Mage / Wizard         | int   | 20 / 6      | 6-8    | yes   | 3701   |
| 1 | Cleric / Priest       | wis   | 20 / 2      | 7-10   | yes   | 3700   |
| 2 | Thief / Bandit        | dex   | 20 / -4     | 8-13   | no    | 3701   |
| 3 | Warrior / Gladiator   | str   | 20 / -10    | 11-15  | no    | 3702   |
| 4 | Paladin / Knight      | wis   | 20 / 2      | 7-10   | yes   | 3700   |
| 5 | Ranger / Strider      | str   | 20 / -10    | 11-15  | no    | 3702   |

All classes: skill_adept 75. attr_prime indices: 0=str 1=int 2=wis 3=dex.
Class indices match the 6-tuples already in `skills_table.py`
(`skill_level` / `rating` per skill -- data is already in the repo, only
flattened at load by `_flatten_skill`).

`MAX_REMORT = 2`, but `do_remort` refuses when class count reaches
MAX_REMORT -> stock cap is **2 classes (1 remort)**. The `@` in the name
list is the dat-format array terminator, not a name; exactly 2 name tiers
exist (e.g. Mage/Wizard).

### Remort-tier names (multiclass.c ClassName/class_long/class_who)

Name tier = character's remort count (`GetRemort`), applied to ALL held
classes: a mage who remorts into cleric displays tier-1 names for both ->
`class_long` = "Wizard/Priest", `class_who` = "Wi+1" (2-char prime-class
prefix + remort count), `class_short` = "Wiza/Prie". `prime_class` is a
player-chosen slot (`do_prime`) used for who/score prominence.
Allowing 3+ classes would need MAX_REMORT raised and a third name tier
authored -- [PRIMESUD] decision if we ever want it; not in scope.

## Guild rooms (1stMud midgaard.are `G <class>` fields)

| Class   | Rooms                                                |
|---------|------------------------------------------------------|
| Mage    | 3018 (Mage's Bar), 3019 (Mage's Laboratory)          |
| Cleric  | 3002 (Cleric's Inner Sanctum), 3003 (Cleric's Bar)   |
| Thief   | 3028 (Thieves Bar), 3029 (The Secret Yard)           |
| Warrior | 3022 (Bar of Swordsmen), 3023 (Tournament Yard)      |

No Paladin/Ranger guilds in midgaard -- [PRIMESUD] decision (02/07/2026):
Paladin maps to the Cleric guild rooms, Ranger to the Warrior guild rooms,
until areas with proper guilds are ported.

## Status (02/07/2026)

All three phases implemented; see commits tagged "class system phase A/B/C".
Regression tests in `tests/test_classes.py`.

## Notes for human review

- **Level cap changed by calc_max_level**: gain_exp previously capped at
  MAX_MORTAL_LEVEL (51); now capped at calc_max_level = 49 single-class,
  50 after one remort (faithful to 1stMud LEVEL_HERO + remorts, and fits
  the existing [PRIMESUD] MAX_LEVEL=50). Existing dev saves above 49 keep
  their level but stop gaining.
- **Remort prerequisites**: gold-only (500,000); the 500-quest-point
  requirement is `# TODO` in do_remort/finish_remort for when auto-quests
  are ported.
- **lvl_bonus magnitude**: at remort the multiplier is 60 (level 49, new
  class already appended -- ordering fixed 03/07/2026), so a remorted char
  restarts with 6000 hp/mana/move, 300 trains and 420 practices. Faithful
  to 1stMud's formula but dwarfs PrimeSUD's economy (a fresh char has 20
  hp). Accepted 03/07/2026 as an NG+-style feature; revisit after playtest.

- **1stMud skill data is permissive** (verified in skills.dat): most spells
  are learnable by every class at higher level/worse rating -- e.g.
  sanctuary is Cleric 20/rating 1 but also Warrior 30/rating 2. Class
  identity comes from level/rating gaps and the hard 53s (bash is
  warrior-line only), not blanket spell locks. Ported faithfully; if
  PrimeSUD wants sharper class identity, tightening the data is a design
  decision, not a porting task. 03/07/2026: resolved via Phase D -- the
  cost side (default groups + gain) is what makes the permissive data
  balanced; see below.
- 1stMud `has_spells` has an upstream indexing bug (see FIXES.md) that made
  every un-remorted character count as a caster; PrimeSUD fixes it, so
  Thief/Warrior mana gain is halved as designed -- a real balance change
  vs. 1stMud-as-shipped.

## Phases

### Phase A -- single-class system (the big one)

- New `classes.py`: `CLASS_TABLE` data + multiclass.c helper ports
  (`skill_level`, `skill_rating`, `prime_class`, `current_class`,
  `is_class`, `lvl_bonus`, `class_mult`, `get_thac00/32`, `hp_gain` range,
  `has_spells`/`can_use_skpell` equivalents).
- `skills_table.py` + `tools/skills_to_primesud.py`: stop flattening;
  expose per-class tuples. Keep flattened lookups only if something needs
  a class-independent view.
- `skill_utils.py`: make `skill_level` / `skill_rating` /
  `can_use_skill_spell` class-aware (min/best across owned classes).
- `player.py`: `"classes": [n]` on create_char; `learned` filtered to
  skills the class can learn (rating > 0, level <= MAX_MORTAL_LEVEL);
  chargen class picker with [PRIMESUD] summaries.
- `combat.py`: `_get_thac0` -> per-class interpolate(thac0_00, thac0_32);
  `advance_level` HP die from class, mana gain only if fMana.
- Skip: skill groups point-buy (groups.dat), creation points, race
  selection at chargen (keep current default race), titles.

### Phase B -- displays + training integration

- `training.py`: practice cost from class rating; adept cap 75
  (currently what?  verify against 1stMud gain/practice).
- `info.py`: score shows class; `do_skills`/`do_spells` per-class levels;
  non-casters (`fMana` false, no spell classes) get "You can't cast" path
  via `has_spells`.
- `movement.py`: guild-room entry restriction (act_move.c:101).
- `area_midgaard.dat`: add `guild` field to the 8 rooms above.

### Phase C -- remort/multiclass

- `do_remort` + `finish_remort` port (fight through the pcdata deltas:
  level 1, keep learned>0 at 1%, hp/mana/move = 100 * lvl_bonus, train =
  5*b, practice = 7*b, gold -500k, re-outfit).  # TODO: quest points req.
- Class picker for the new class (exclude already-held).
- Multiclass lookups exercise the min/best paths in `classes.py` (written
  in Phase A, single-element list until now).
- `calc_max_level` / level cap growth per remort -- check 1stMud
  `calc_max_level` and port.
- Remort-tier display names (Wizard, Priest, ...).

### Phase D -- skill groups + gain (03/07/2026)

Phases A-C granted every class-learnable skill at 1% on create/remort --
more permissive than 1stMud, where the nanny default path grants only the
class's *base* + *default* groups (a warrior's default groups do NOT
include protective/sanctuary; cross-class spells cost 8 creation points or
8 trains at a gain trainer). Phase D restores the faithful cost side:

- New `groups.py`: `GROUP_TABLE` ported verbatim from 1stMud
  data/groups.dat (31 groups, per-class rating 6-tuples, member skill /
  sub-group names). `group_lookup`, `group_rating` (min positive across
  held classes, cf. multiclass.c), `gn_add` (recursive grant at 1%,
  cf. skills.c), `add_base_groups`, `add_default_groups`.
- `classes.py`: `base_group` / `default_group` fields on CLASS_TABLE
  (from classes.dat).
- `player.py` `create_char`: replace grant-all with 1stMud nanny default
  path -- "rom basics" + class basics + class defaults, recall 50,
  class weapon 40. Player gains `"groups"` list (known group indices,
  cf. pcdata->group_known).
- `training.py` `finish_remort`: same replacement -- re-grant base +
  default groups for ALL held classes (nanny remort flow re-runs
  creation grants on the remorted char).
- `training.py` `do_gain` + wire `gain` into commands.py: list / convert
  (10 practices -> 1 train) / gain group by name / gain non-spell skill
  by name. Spells refuse individual gain ("You must learn the full
  group.") exactly as 1stMud skills.c.
- `game_state.py`: persist `p.groups` (comma-joined ints; missing key
  defaults empty, no SAVE_VERSION bump needed).

Skipped permanently ([PRIMESUD], single-player scope):

- `gen_groups` creation-point customization UI. Default-path characters
  sit at the flat exp rate (points <= max_points 40 never escalates
  exp_per_level), so skipping the whole points economy changes nothing
  observable.
- `gain points` (refunds creation points -- nothing to refund).
- The >40-point exp_per_level escalation.

Fidelity notes:

- groups.dat says `invis`; the skill is `invisibility` (1stMud
  skill_lookup is prefix-based). Stored under the full name.
- 1stMud nanny order quirk: weapon-at-40 (and re-granted recall-at-50)
  are set BEFORE finish_remort's in-progress reset, so a remorted 1stMud
  char actually restarts with them at 1%. PrimeSUD sets the new class's
  weapon to 40 and recall to 50 AFTER the reset -- deliberate [PRIMESUD]
  deviation (kinder, matches fresh-char feel; confirmed 03/07/2026).

Each phase ends playable: A = pick a class and level in it; B = class
visible everywhere it should be; C = remort loop closes; D = cross-class
skills cost trains at a gain trainer instead of arriving free.
