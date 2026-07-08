# 1stMud 4.5.3 — Skills Table Reference

Source: `reference/1stMud4.5.3/data/skills.dat`  
Struct: `struct skill_type` (`src/h/structs.h:949`)  
Loader: `rw_skill_data` (`src/data_table.c:2390`) → `rw_table(act_read, SKILL_FILE, SkillData, skill)`  
Field table: `skill_data_table[]` (`src/data_table.c:329`)

## Overview

`skills.dat` is a plain-text key-value file.  Each skill/spell is one
`#SKILL … #END` block.  The first field of each block is `name`.

On load, `rw_skill_data` calls `rw_table` which walks the file and populates
`skill_table[]` (a dynamic array of `SkillData`, a.k.a. `struct skill_type`).
After all entries are read, `top_skill` is set to the count and a sentinel entry
`skill_table[top_skill].name = NULL` marks the end.

Then, for every loaded skill whose `pgsn` points to a real `gsn_*` variable
(not `&gsn_null`), that variable is set to the skill's load-order index (`sn`):

```c
// src/data_table.c
if (skill_table[sn].pgsn != NULL && skill_table[sn].pgsn != &gsn_null)
    *skill_table[sn].pgsn = sn;
```

This is why **pgsn values are load-order indices** — not a separate numbering
scheme.

Skills with `spell_fun == spell_null` are **skills** (passive/active combat
abilities).  Skills with any other `spell_fun` are **spells** (castable via
`cast`).

There are **149 entries** (indices 0–148).

## File format

```
N                 ← number of entries (integer header, ignored by loader)

#SKILL
name        <name>~
skill_level  <v0> <v1> <v2> <v3> <v4> <v5> @
rating       <v0> <v1> <v2> <v3> <v4> <v5> @
spell_fun    <function-name>~
target       <flag-string>~
minimum_position <flag-string>~
pgsn         <gsn-name>~
min_mana     <int>
beats        <int>
noun_damage  <string>~
msg_off      <string>~
msg_obj      <string>~
flags        <flag-string>~      ← optional; OLC-only
sound        …                   ← optional MSP block
#END
```

Tilde (`~`) terminates variable-length strings.  `@` terminates integer arrays.
The 6-element arrays map to class indices 0–5 (see Classes below).

## Classes (array index mapping)

| Index | Class name |
|-------|-----------|
| 0 | Mage |
| 1 | Cleric |
| 2 | Thief |
| 3 | Warrior |
| 4 | Paladin |
| 5 | Ranger |

Source: `data/classes.dat`, confirmed by the `6` at line 1 of that file.

## Fields

### `name` — string

The canonical skill/spell name used in player input (`cast armor`), help lookups,
and `skill_lookup()` / `spell_lookup()`.  Entry 0 is always `reserved` — a
placeholder that ensures no real skill gets `sn == 0` (which many NULL-check paths
treat as invalid).

---

### `skill_level` — int array [top_class]

Minimum level at which each class can *learn* (or be taught) this skill/spell.

Helper (cf. `multiclass.c:skill_level`):

```c
int skill_level(CharData *ch, int sn)
```

Returns the lowest `skill_table[sn].skill_level[cls]` across all of the
character's classes.  Race/deity skills return 1 regardless.

Special values:

| Value | Constant | Meaning |
|-------|----------|---------|
| 1–51 | — | Learnable at that mortal level |
| 52 | `LEVEL_IMMORTAL` (`MAX_LEVEL - 8`) | Immortal-only |
| 53 | `ANGEL` (`MAX_LEVEL - 7`) | Not available to this class (default for new skills) |

`MAX_LEVEL = 60`, `MAX_MORTAL_LEVEL = 51`.

---

### `rating` — int array [top_class]

Train cost (in practice points) for each class to learn this skill/spell.
Also used as a difficulty multiplier in practice success calculation
(`src/skills.c:813`: `chance /= (multiplier * skill_rating(ch, sn) * 4)`).

Helper (cf. `multiclass.c:skill_rating`):

```c
int skill_rating(CharData *ch, int sn)
```

Returns the minimum `rating[cls]` across the character's classes, ignoring
entries where `rating[cls] < 1`.  Returns 0 if no class has a positive rating
(skill unavailable).

`rating == 0` for a class means that class cannot learn the skill individually
(it may still be in a group for that class).

---

### `spell_fun` — function pointer (stored as name string in file)

Resolves via `spell_index[]` (`src/db2.c:1105`).  Names map directly to C
function symbols (e.g. `spell_fireball`, `spell_null`).

`spell_null` → **passive skill** (no casting, no spell effect).  
Any other value → **spell** (dispatched by `do_cast` via `magic.c`).

On cast, the function receives `(int sn, int level, CharData *ch, void *vo,
target_t target)`.

---

### `target` — enum `tar_t` (stored as flag string)

Controls what `do_cast` / `magic.c:do_cast` asks the player to specify as a
target, and who `vo` points to when the spell function is invoked.

| File value | Constant | Meaning |
|-----------|----------|---------|
| `ignore` | `TAR_IGNORE` | No target; `vo` is NULL |
| `char_offensive` | `TAR_CHAR_OFFENSIVE` | A character; offensive spells (checks `IS_AFFECTED(AFF_CHARM)` etc.) |
| `char_defensive` | `TAR_CHAR_DEFENSIVE` | A character; defensive/healing spells |
| `char_self` | `TAR_CHAR_SELF` | Caster only; `vo = ch` |
| `obj_inventory` | `TAR_OBJ_INV` | An object in inventory |
| `obj_char_defensive` | `TAR_OBJ_CHAR_DEF` | Object or character (defensive) |
| `obj_char_offensive` | `TAR_OBJ_CHAR_OFF` | Object or character (offensive) |

Source: `src/tables.c:1406`.

Offensive targets trigger a check at cast time: if the target is in a non-arena
safe room, casting is blocked (cf. `magic.c:508`).

---

### `minimum_position` — enum `position_t` (stored as flag string)

The minimum position the *caster* must be in to use this skill/spell.
Checked in `magic.c` before dispatch.

| File value | Constant | Value |
|-----------|----------|-------|
| `dead` | `POS_DEAD` | 0 |
| `mortal` | `POS_MORTAL` | 1 |
| `incap` | `POS_INCAP` | 2 |
| `stunned` | `POS_STUNNED` | 3 |
| `sleeping` | `POS_SLEEPING` | 4 |
| `resting` | `POS_RESTING` | 5 |
| `sitting` | `POS_SITTING` | 6 |
| `fighting` | `POS_FIGHTING` | 7 |
| `standing` | `POS_STANDING` | 8 |

Most attack spells use `fighting`; most utility/buff spells use `standing`.

Source: `src/tables.c:1230`.

---

### `pgsn` — pointer to int (stored as gsn-variable name)

"Global Skill Number" — a named C variable that gets assigned the skill's
load-order index on boot.  Used throughout the codebase to reference specific
skills without a string lookup.

File stores the variable name string (e.g. `gsn_sword~`).  On load, resolved via
`gsn_index[]` (`src/db2.c:1098`) to the corresponding `&gsn_*` variable.
After all skills load, `*pgsn = sn` is executed for every non-null entry.

`gsn_null` → skill has no named C reference (it is only accessed by name-lookup
or by iterating `skill_table[]`).

Skills referenced in combat, affect handling, or update code all require a named
`gsn_*` variable so the engine can find them by index without a string search.

Full list of named gsn variables: see `src/h/index.h:47–95`.

---

### `min_mana` — int

Minimum mana cost floor for spells.  The actual mana cost is:

```c
// magic.c:243
int mana_cost(CharData *ch, int min_mana, int level) {
    return Max(min_mana, (100 / (2 + ch->level - level)));
}
```

For passive skills (`spell_fun == spell_null`), `min_mana` is 0 and is not used.

---

### `beats` — int

Lag applied to the caster/user on successful use, in server pulses.
One pulse = `1/PULSE_PER_SECOND` seconds (default from `mud.dat`).

Reference constants:

| Constant | Value |
|----------|-------|
| `PULSE_PER_SECOND` | from `mud_info.pulsepersec` |
| `PULSE_VIOLENCE` | `3 * PULSE_PER_SECOND` |

Applied via `WaitState(ch, skill_table[sn].beats)` (`magic.c:479`).

Typical values in `skills.dat`: `12` (one combat round), `18`, `24`.
Skills with `beats == 0` impose no lag (e.g. weapon proficiencies).

---

### `noun_damage` — string

Short noun used in combat damage messages when `dt` (damage type) equals this
skill's `sn` (cf. `fight.c:2632`: `attack = skill_table[dt].noun_damage`).

Examples: `"acid blast"`, `"backstab"`, `"lightning bolt"`.
Empty string for spells that do not deal typed damage or for passive skills.

---

### `msg_off` — string

Message sent to the character (and echoed as an affect-worn-off notice) when an
affect of this type expires (cf. `magic.c:229`).

Wrap with `!…!` to also send a sound trigger (MSP). Example: `!Acid Blast!`.
Plain string for text-only: `You can see again.`.
Empty string if the skill/spell has no expiry message.

---

### `msg_obj` — string

Message displayed (via `act()`) to the room when an object affect of this type
wears off (cf. `update.c:797`).  Uses `act()` substitution tokens: `$p` = object.

Example: `$p's holy aura fades.`  
Empty string for most skills.

---

### `flags` — flag field (`skill_flags[]`)

OLC state flags only; not used by game logic.

| Value | Meaning |
|-------|---------|
| `none` | `OLC_NONE` — clean |
| `changed` | `OLC_CHANGED` — pending write-back |
| `deleted` | `OLC_DELETED` — pending removal |

---

### `sound` — MspData (optional)

MSP (MUD Sound Protocol) trigger attached to the skill.  Stored as a sub-block
in the file.  Fields: `file`, `type`, `volume`, `loop`, `priority`, `restart`,
`url`, `to`.  If absent the field is NULL.

---

## Load order and pgsn table

`sn` = index into `skill_table[]` = value written to `gsn_*` at boot.

For skills with `pgsn == gsn_null`, `sn` is not stored in any named C variable.
Those skills are accessed only via `skill_lookup()` by name.

| sn | Name | pgsn |
|----|------|------|
| 0 | reserved | gsn_null |
| 1 | trivia pill | gsn_null |
| 2 | acid blast | gsn_null |
| 3 | armor | gsn_null |
| 4 | bless | gsn_null |
| 5 | blindness | **gsn_blindness** |
| 6 | burning hands | gsn_null |
| 7 | call lightning | gsn_null |
| 8 | calm | gsn_null |
| 9 | cancellation | gsn_null |
| 10 | cause critical | gsn_null |
| 11 | cause light | gsn_null |
| 12 | cause serious | gsn_null |
| 13 | chain lightning | gsn_null |
| 14 | change sex | gsn_null |
| 15 | charm person | **gsn_charm_person** |
| 16 | chill touch | gsn_null |
| 17 | color spray | gsn_null |
| 18 | continual light | gsn_null |
| 19 | control weather | gsn_null |
| 20 | create food | gsn_null |
| 21 | create rose | gsn_null |
| 22 | create spring | gsn_null |
| 23 | create water | gsn_null |
| 24 | cure blindness | gsn_null |
| 25 | cure critical | gsn_null |
| 26 | cure disease | gsn_null |
| 27 | cure light | gsn_null |
| 28 | cure poison | gsn_null |
| 29 | cure serious | gsn_null |
| 30 | curse | **gsn_curse** |
| 31 | demonfire | gsn_null |
| 32 | detect evil | gsn_null |
| 33 | detect good | gsn_null |
| 34 | detect hidden | gsn_null |
| 35 | detect invis | gsn_null |
| 36 | detect magic | gsn_null |
| 37 | detect poison | gsn_null |
| 38 | dispel evil | gsn_null |
| 39 | dispel good | gsn_null |
| 40 | dispel magic | gsn_null |
| 41 | earthquake | gsn_null |
| 42 | enchant armor | gsn_null |
| 43 | enchant weapon | gsn_null |
| 44 | energy drain | gsn_null |
| 45 | faerie fire | gsn_null |
| 46 | faerie fog | gsn_null |
| 47 | farsight | gsn_null |
| 48 | fireball | gsn_null |
| 49 | fireproof | gsn_null |
| 50 | flamestrike | gsn_null |
| 51 | fly | **gsn_fly** |
| 52 | floating disc | gsn_null |
| 53 | frenzy | gsn_null |
| 54 | gate | gsn_null |
| 55 | giant strength | gsn_null |
| 56 | harm | gsn_null |
| 57 | haste | gsn_null |
| 58 | heal | gsn_null |
| 59 | heat metal | gsn_null |
| 60 | holy word | gsn_null |
| 61 | identify | gsn_null |
| 62 | infravision | gsn_null |
| 63 | invisibility | **gsn_invis** |
| 64 | know alignment | gsn_null |
| 65 | lightning bolt | gsn_null |
| 66 | locate object | gsn_null |
| 67 | magic missile | gsn_null |
| 68 | mass healing | gsn_null |
| 69 | mass invis | **gsn_mass_invis** |
| 70 | nexus | gsn_null |
| 71 | pass door | gsn_null |
| 72 | plague | **gsn_plague** |
| 73 | poison | **gsn_poison** |
| 74 | portal | gsn_null |
| 75 | protection evil | gsn_null |
| 76 | protection good | gsn_null |
| 77 | ray of truth | gsn_null |
| 78 | recharge | gsn_null |
| 79 | refresh | gsn_null |
| 80 | remove curse | gsn_null |
| 81 | sanctuary | **gsn_sanctuary** |
| 82 | shield | gsn_null |
| 83 | shocking grasp | gsn_null |
| 84 | sleep | **gsn_sleep** |
| 85 | slow | gsn_null |
| 86 | stone skin | gsn_null |
| 87 | summon | gsn_null |
| 88 | teleport | gsn_null |
| 89 | ventriloquate | gsn_null |
| 90 | weaken | gsn_null |
| 91 | word of recall | gsn_null |
| 92 | acid breath | gsn_null |
| 93 | fire breath | gsn_null |
| 94 | frost breath | gsn_null |
| 95 | gas breath | gsn_null |
| 96 | lightning breath | gsn_null |
| 97 | general purpose | gsn_null |
| 98 | high explosive | gsn_null |
| 99 | axe | **gsn_axe** |
| 100 | dagger | **gsn_dagger** |
| 101 | flail | **gsn_flail** |
| 102 | mace | **gsn_mace** |
| 103 | polearm | **gsn_polearm** |
| 104 | shield block | **gsn_shield_block** |
| 105 | spear | **gsn_spear** |
| 106 | sword | **gsn_sword** |
| 107 | whip | **gsn_whip** |
| 108 | backstab | **gsn_backstab** |
| 109 | bash | **gsn_bash** |
| 110 | berserk | **gsn_berserk** |
| 111 | dirt kicking | **gsn_dirt** |
| 112 | disarm | **gsn_disarm** |
| 113 | dodge | **gsn_dodge** |
| 114 | enhanced damage | **gsn_enhanced_damage** |
| 115 | envenom | **gsn_envenom** |
| 116 | hand to hand | **gsn_hand_to_hand** |
| 117 | kick | **gsn_kick** |
| 118 | parry | **gsn_parry** |
| 119 | rescue | **gsn_rescue** |
| 120 | trip | **gsn_trip** |
| 121 | second attack | **gsn_second_attack** |
| 122 | third attack | **gsn_third_attack** |
| 123 | fast healing | **gsn_fast_healing** |
| 124 | haggle | **gsn_haggle** |
| 125 | hide | **gsn_hide** |
| 126 | lore | **gsn_lore** |
| 127 | meditation | **gsn_meditation** |
| 128 | peek | **gsn_peek** |
| 129 | hunt | **gsn_hunt** |
| 130 | pick lock | **gsn_pick_lock** |
| 131 | sneak | **gsn_sneak** |
| 132 | steal | **gsn_steal** |
| 133 | scrolls | **gsn_scrolls** |
| 134 | staves | **gsn_staves** |
| 135 | wands | **gsn_wands** |
| 136 | recall | **gsn_recall** |
| 137 | forceshield | gsn_null |
| 138 | staticshield | gsn_null |
| 139 | flameshield | gsn_null |
| 140 | channel | gsn_null |
| 141 | investiture | gsn_null |
| 142 | powerstorm | gsn_null |
| 143 | mana burn | gsn_null |
| 144 | bark skin | gsn_null |
| 145 | spell mantle | gsn_null |
| 146 | animal instinct | gsn_null |
| 147 | chaos flare | gsn_null |
| 148 | wild magic | gsn_null |

Bold `pgsn` entries have a corresponding named C variable in `src/h/index.h`.
Entries 137–148 are 1stMud additions beyond the ROM 2.4 base set; none have
named `gsn_*` variables.

## PrimeSUD notes

PrimeSUD's `SKILL_TABLE` in `world.py` mirrors this structure but as a Python
dict keyed by skill name.  The `pgsn` concept is replaced by `WEAPON_GSN_MAP`
and named constants in `world_consts.py`.  `skill_level` (per-class array) is replaced by a single `min_level` int and
`rating` stays a single int — no per-class arrays needed in a single-player game.

### Why gsn matters for PrimeSUD

The same two reasons apply on HP Prime:

**1. Hot-path cost.** String comparison is costlier than integer comparison.
Skills checked on every combat tick (dodge, parry, weapon proficiency, second/
third attack, poison, plague, sanctuary, fast-healing) should be reached via a
pre-resolved integer constant — not a repeated `SKILL_TABLE["dodge"]` string
lookup inside a tight loop.

**2. Affect type storage.** `affect_data` stores `type` as an integer sn
(cf. `player.py`).  When an affect expires the engine only has that integer —
it must be able to do `SKILL_TABLE_BY_SN[paf.type]` rather than re-scanning
by name.  This requires a second lookup table indexed by sn alongside the
primary name-keyed dict, or pre-resolved constants.

**Rule of thumb (mirrors 1stMud):**

| Skill category | Access method |
|----------------|---------------|
| Combat passives checked per-attack (dodge, parry, weapon profs, second/third attack, bash, kick, …) | Integer constant from `world_consts.py` |
| Persistent affects checked per-tick (poison, plague, sanctuary, blindness, fly, …) | Integer constant (also needed as affect type) |
| Spells invoked only by player command (`cast fireball`) | String lookup via `SKILL_TABLE` — one lookup per command is fine |
| Passive utility skills checked in `do_*` handlers (hide, sneak, steal, …) | Either; prefer constant if checked frequently |
