# 1stMud Reference Notes

Snippets of implementation detail from the reference 1stMud 4.5.3 source
(`reference/1stMud4.5.3/`).

See also: **[COMMANDS.md](COMMANDS.md)** — full command table with load order,
positions, levels, flags, and categories (source: `data/commands.dat`).

See also: **[CMD_PLAN.md](CMD_PLAN.md)** — plan for porting the command dispatch
infrastructure and extending the command set.

See also: **[BUILTINS.md](BUILTINS.md)** — HP Prime Python built-in type method
availability (verified via `dir()` on-device).

---

## Custom colour slots

Defined in `src/h/ansi.h`; in-game names and ordering from `src/tables.c`
(`custom_colors[]`); default values from `data/color_templates.dat` (the
"Default" colour scheme loaded at startup via `data_table.c:2602`).

At the source level, a colour tag is written as `CTAG(_CONSTANT)`, which
expands to the byte sequence `\x11 <slot-number> \x12`.  At render time
(`ansi.c:make_color`) the slot is looked up in `ch->pcdata->colors[]` and
converted to an ANSI escape.

| Slot | Constant     | In-game name | Default colour   | ANSI code   |
| ---- | ------------ | ------------ | ---------------- | ----------- |
| 0    | `_DEFAULT`   | clear        | reset            | `ESC[0m`    |
| 1    | `_GOSSIP`    | gossip       | bright + magenta | `ESC[1;35m` |
| 2    | `_MUSIC`     | music        | bright + red     | `ESC[1;31m` |
| 3    | `_QA`        | qa           | bright + yellow  | `ESC[1;33m` |
| 4    | `_QUOTE`     | quote        | bright + white   | `ESC[1;37m` |
| 5    | `_GRATS`     | gratz        | bright + green   | `ESC[1;32m` |
| 6    | `_SHOUT1`    | shout1       | magenta          | `ESC[0;35m` |
| 7    | `_SHOUT2`    | shout2       | bright + magenta | `ESC[1;35m` |
| 8    | `_IMMTALK`   | immtalk      | cyan             | `ESC[0;36m` |
| 9    | `_TELLS1`    | tells1       | cyan             | `ESC[0;36m` |
| 10   | `_TELLS2`    | tells2       | bright + cyan    | `ESC[1;36m` |
| 11   | `_SAY1`      | say1         | green            | `ESC[0;32m` |
| 12   | `_SAY2`      | say2         | bright + green   | `ESC[1;32m` |
| 13   | `_SKILL`     | skills       | bright + yellow  | `ESC[1;33m` |
| 14   | `_YHIT`      | yhit         | bright + green   | `ESC[1;32m` |
| 15   | `_OHIT`      | ohit         | bright + blue    | `ESC[1;34m` |
| 16   | `_VHIT`      | vhit         | bright + red     | `ESC[1;31m` |
| 17   | `_WRACE`     | whorace      | bright + red     | `ESC[1;31m` |
| 18   | `_WCLASS`    | whoclass     | bright + cyan    | `ESC[1;36m` |
| 19   | `_WLEVEL`    | wholvl       | bright + blue    | `ESC[1;34m` |
| 20   | `_RTITLE`    | roomtitle    | bright + yellow  | `ESC[1;33m` |
| 21   | `_SCORE1`    | score1       | cyan             | `ESC[0;36m` |
| 22   | `_SCORE2`    | score2       | bright + cyan    | `ESC[1;36m` |
| 23   | `_SCORE3`    | score3       | white            | `ESC[0;37m` |
| 24   | `_SCOREB`    | score4       | bright + white   | `ESC[1;37m` |
| 25   | `_WIZNET`    | wiznet       | green            | `ESC[0;32m` |
| 26   | `_GTELL1`    | gtell1       | yellow           | `ESC[0;33m` |
| 27   | `_GTELL2`    | gtell2       | bright + green   | `ESC[1;32m` |
| 28   | `_BTALK`     | btalk        | bright + blue    | `ESC[1;34m` |
| 29   | `_WSEX`      | whosex       | green            | `ESC[0;32m` |
| 30   | `_AUTOMAP`   | automap      | bright + red     | `ESC[1;31m` |
| 31   | `_AUTOEXITS` | autoexits    | green            | `ESC[0;32m` |
| 32   | `_MOBILES`   | mobiles      | bright + magenta | `ESC[1;35m` |
| 33   | `_OBJECTS`   | objects      | bright + yellow  | `ESC[1;33m` |
| 34   | `_SOCIALS`   | socials      | bright + random  | `ESC[1;?m`  |
| 35   | `_OLCBORDER` | olcborder    | cyan             | `ESC[0;36m` |
| 36   | `_OLCVAR`    | olcvar       | bright + white   | `ESC[1;37m` |
| 37   | `_OLCVAL`    | olcval       | white            | `ESC[0;37m` |

`_CUSTOM_COLORS = 38` is the count, not a slot.

**Note — slot 1 (`_GOSSIP`):** the raw data has `CT_BACK = 35`, which fails
`VALID_BG()` (requires ≥ 40), so no background is actually applied.

**How to check a slot's default:** read the `colors` blob in
`data/color_templates.dat` under the "Default" scheme.  Values are packed as
`<count> [CT_ATTR CT_FORE CT_BACK] × count`, zero-indexed by slot number.

---

## .are file format

Sources: `src/db2.c` (mob/object loaders), `src/db.c` (room/reset loaders),
`src/h/bits.h` (flag constants), `src/h/defines.h` (enums), `src/const.c`
(weapon/attack tables).

1stMud parses `.are` files at server boot; PrimeSUD does not parse them at
runtime.  Use this section when porting data from existing `.are` files into
Python area modules.

---

### Flag encoding

Two formats exist in `.are` files:

**Numeric/letter sum** (older areas): a raw integer, or uppercase letters
OR'd together (e.g. `AB` = BIT_A | BIT_B = 3).

**Bit-string** (version 2+, used throughout `school.are`): a `+` followed by
a string of `Y`/`n` characters.  Each character is one bit, left-to-right
starting at bit 0.  `Y` = bit set, `n` = bit clear.  The string ends at any
character other than `Y` or `n`.

```
+nnnnnnnnnnnnnnnnnnnnY  +YnnnnnnnnnnnnY
  0123456789...     ^     ^           ^
                 pos 20  pos 0      pos 13
```

**Bit-letter mapping:** `A`=0, `B`=1, … `Z`=25, `a`=26, `b`=27, … `f`=31.
So position 0 in the string = BIT_A, position 1 = BIT_B, etc.

To decode manually: find each `Y`, note its zero-based position, look that
position up in the flag table for that field.

Two separate flag fields on the same line are separated by whitespace; each
starts with its own `+`.

---

### #AREADATA

Key-value block terminated by `End`.  All keys optional.

| Key                     | Value         | Notes                                          |
| ----------------------- | ------------- | ---------------------------------------------- |
| `Name`                  | string~       | Display name                                   |
| `Builders`              | string~       | Builder credits                                |
| `VNUMs`                 | `min max`     | VNUM range owned by this area                  |
| `Version`               | int           | Format version; `school.are` is v4             |
| `MinLevel` / `MaxLevel` | int           | Suggested level range                          |
| `Security`              | int           | OLC access level                               |
| `Climate`               | int int int   | Server weather simulation; ignored in PrimeSUD |
| `Stats`                 | int int `END` | Boot-time kill/death counters; ignored         |
| `Flags`                 | flag          | `AREA_*` bits; ignored in PrimeSUD             |

---

### #MOBILES

All strings are `~`-terminated; a lone `~` on its own line ends a multi-line
string.

#### Field sequence

| Line | Content                                       | Notes                                        |
| ---- | --------------------------------------------- | -------------------------------------------- |
| 1    | `keywords~`                                   | Space-separated lookup names                 |
| 2    | `short_descr~`                                | Shown in room ("A rat is here.")             |
| 3    | `long_descr~`                                 | Shown on walk-in; multi-line                 |
| 4    | `description~`                                | Shown on `look mob`; multi-line              |
| 5    | `race~`                                       | Race name string                             |
| 6    | `act_flags  aff_flags  alignment  group`      | Two flag fields + two integers               |
| 7    | `level  random  autoset  hitroll`             | `random`/`autoset` only in version ≥ 4       |
| 8    | `NdD+B  NdD+B  NdD+B  'dam_type'`             | HP dice, mana dice, damage dice, attack name |
| 9    | `ac_pierce  ac_bash  ac_slash  ac_exotic`     | Values stored × 10 (so 100 = AC 10)          |
| 10   | `off_flags  imm_flags  res_flags  vuln_flags` | Four flag fields                             |
| 11   | `start_pos  default_pos  sex  wealth`         | Position/sex names + gold integer            |
| 12   | `form_flags  part_flags  size  material`      | Size/material are name strings               |

**`random`** — level variance radius applied at spawn time.  The mob's actual
level is randomised to `number_range(level - random, level + random)`; `0`
means always exactly `level`.

**`autoset`** — OLC editor hint only; ignored at boot.  Tells the in-game mob
editor which stat formula (0=default, 1=easy, 2=normal, 3=hard, 4=random) to
use when the builder triggers the `autoset` command, which auto-generates AC,
HP/mana/damage dice, and `hitroll` from the mob's level.

**`group`** — faction tag for automatic mutual assist.  Any NPC will join
combat on behalf of another NPC that shares the same non-zero `group` value,
without requiring `ASSIST_ALL` or `ASSIST_RACE` flags (see `fight.c`).  `0`
means no group (mob won't assist via this mechanism).

**`hitroll` but no `damroll`** — mobs have no separate `damroll` field.  The
`+B` bonus in the damage dice (`NdD+B`, line 8) serves that role — it is a flat
damage bonus packed into the dice spec.  `hitroll` exists as its own field
because there is no dice analogue for a to-hit bonus.

Followed by zero or more optional trailer lines, terminated by any non-trailer
character (the next `#` or section header):

| Letter | Arguments                     | Meaning                                                                    |
| ------ | ----------------------------- | -------------------------------------------------------------------------- |
| `F`    | `field_name  flag`            | Remove bits from a field (`act` `aff` `off` `imm` `res` `vul` `for` `par`) |
| `M`    | `trigger  prog_vnum  phrase~` | Attach a MobProg                                                           |
| `S`    | `kills  deaths`               | Persistent kill/death counters: `kills` = kills scored by this mob prototype (players or other mobs killed); `deaths` = times this prototype has been killed.  Written back to the `.are` file on shutdown so stats survive server restarts.  Optional — absent if both are zero.  Source: `db2.c:load_mobiles`, `fight.c:update_death`. |

#### Annotated example — #3702 monster

| `.are` content                                                    | Field                                          | Notes                              |
| ----------------------------------------------------------------- | ---------------------------------------------- | ---------------------------------- |
| `#3702`                                                           | VNUM                                           |                                    |
| `monster~`                                                        | keywords                                       | space-separated lookup names       |
| `the monster~`                                                    | short_descr                                    | shown in room                      |
| `There is a monster leashed here.\n~`                             | long_descr                                     | multi-line; shown on walk-in       |
| `He looks mean...\n~`                                             | description                                    | multi-line; shown on `look mob`    |
| `School monster~`                                                 | race                                           |                                    |
| `+YYnnnnnnnnnnnnnnnnnnY +n 0 0`                                   | act · aff · alignment · group                  |                                    |
| `1 0 0 0`                                                         | level · random · autoset · hitroll             | random/autoset only in version ≥ 4 |
| `1d1+7 1d1+99 1d3+0 'claw'`                                       | hit_dice · mana_dice · dam_dice · dam_type     |                                    |
| `10 10 10 10`                                                     | ac[pierce] · ac[bash] · ac[slash] · ac[exotic] | stored ×10                         |
| `+n +YY +n +nnY`                                                  | off · imm · res · vuln                         |                                    |
| `standing standing either 10`                                     | start_pos · default_pos · sex · wealth         |                                    |
| `+nnnnnnYnnnnnYnnnnnnnnY +YnYYYYnYnYYnnnnnYnnnY medium 'unknown'` | form · parts · size · material                 |                                    |
| `S 0 20`                                                          | kills · deaths                                 | optional trailer                   |

Flag values decoded:
- `act` `+YYnnnnnnnnnnnnnnnnnnY` → IS_NPC(0) SENTINEL(1) NOALIGN(20)
- `aff` `+n` → none
- `imm` `+YY` → SUMMON(0) CHARM(1)
- `vuln` `+nnY` → MAGIC(2)
- `form` `+nnnnnnYnnnnnYnnnnnnnnY` → ANIMAL(6) BIPED(12) + undefined BIT_U(20)
- `parts` `+YnYYYYnYnYYnnnnnYnnnY` → HEAD(0) LEGS(2) HEART(3) BRAINS(4) GUTS(5) FEET(7) EAR(9) EYE(10) TAIL(16) CLAWS(20)

#### act flags

| Pos | Constant            | Notes                                    |
| --- | ------------------- | ---------------------------------------- |
| 0   | `ACT_IS_NPC`        | Always set; added automatically at load  |
| 1   | `ACT_SENTINEL`      | Does not wander                          |
| 2   | `ACT_SCAVENGER`     | Picks up items from floor                |
| 5   | `ACT_AGGRESSIVE`    | Attacks players on sight                 |
| 6   | `ACT_STAY_AREA`     | Won't leave area                         |
| 7   | `ACT_WIMPY`         | Flees at low HP                          |
| 8   | `ACT_PET`           | Charmed pet                              |
| 9   | `ACT_TRAIN`         | Can train stats                          |
| 10  | `ACT_PRACTICE`      | Can teach skills                         |
| 14  | `ACT_UNDEAD`        | Undead creature                          |
| 16  | `ACT_CLERIC`        | Casts cleric spells                      |
| 17  | `ACT_MAGE`          | Casts mage spells                        |
| 18  | `ACT_THIEF`         | Uses thief abilities                     |
| 19  | `ACT_WARRIOR`       | Uses warrior abilities                   |
| 20  | `ACT_NOALIGN`       | No alignment restrictions when attacking |
| 21  | `ACT_NOPURGE`       | Not removed on area reset                |
| 22  | `ACT_OUTDOORS`      | Only active outdoors                     |
| 24  | `ACT_INDOORS`       | Only active indoors                      |
| 26  | `ACT_IS_HEALER`     | Healer NPC (server-side)                 |
| 27  | `ACT_GAIN`          | Trainer NPC (server-side)                |
| 28  | `ACT_UPDATE_ALWAYS` | Updates even without players in area     |
| 29  | `ACT_IS_CHANGER`    | Money-changer NPC (server-side)          |

#### affected_by flags (AFF_*)

| Pos | Constant            | Effect                    |
| --- | ------------------- | ------------------------- |
| 0   | `AFF_BLIND`         | Blinded                   |
| 1   | `AFF_INVISIBLE`     | Invisible                 |
| 2   | `AFF_DETECT_EVIL`   | Detects evil              |
| 3   | `AFF_DETECT_INVIS`  | Detects invisible         |
| 4   | `AFF_DETECT_MAGIC`  | Detects magic             |
| 5   | `AFF_DETECT_HIDDEN` | Detects hidden            |
| 6   | `AFF_DETECT_GOOD`   | Detects good              |
| 7   | `AFF_SANCTUARY`     | Half damage               |
| 8   | `AFF_FAERIE_FIRE`   | Outlined, harder to dodge |
| 9   | `AFF_INFRARED`      | Sees in dark              |
| 10  | `AFF_CURSE`         | Cursed                    |
| 12  | `AFF_POISON`        | Poisoned                  |
| 13  | `AFF_PROTECT_EVIL`  | Protected from evil       |
| 14  | `AFF_PROTECT_GOOD`  | Protected from good       |
| 15  | `AFF_SNEAK`         | Silent movement           |
| 16  | `AFF_HIDE`          | Hidden                    |
| 17  | `AFF_SLEEP`         | Sleeping via spell        |
| 18  | `AFF_CHARM`         | Charmed                   |
| 19  | `AFF_FLYING`        | Flying                    |
| 20  | `AFF_PASS_DOOR`     | Passes through doors      |
| 21  | `AFF_HASTE`         | Extra attacks             |
| 22  | `AFF_CALM`          | Won't attack              |
| 23  | `AFF_PLAGUE`        | Plague                    |
| 24  | `AFF_WEAKEN`        | Strength reduced          |
| 25  | `AFF_DARK_VISION`   | Full dark sight           |
| 26  | `AFF_BERSERK`       | Berserk                   |
| 27  | `AFF_SWIM`          | Can swim                  |
| 28  | `AFF_REGENERATION`  | Faster HP regen           |
| 29  | `AFF_SLOW`          | Loses attacks             |

#### off_flags — offensive behaviours

| Pos | Constant          | Notes                       |
| --- | ----------------- | --------------------------- |
| 0   | `OFF_AREA_ATTACK` | Hits all enemies in room    |
| 1   | `OFF_BACKSTAB`    | Can backstab                |
| 2   | `OFF_BASH`        | Uses bash                   |
| 3   | `OFF_BERSERK`     | Goes berserk in combat      |
| 4   | `OFF_DISARM`      | Uses disarm                 |
| 5   | `OFF_DODGE`       | Dodges attacks              |
| 6   | `OFF_FADE`        | Fade dodge                  |
| 7   | `OFF_FAST`        | Extra attacks               |
| 8   | `OFF_KICK`        | Uses kick                   |
| 9   | `OFF_KICK_DIRT`   | Kicks dirt in eyes          |
| 10  | `OFF_PARRY`       | Can parry                   |
| 11  | `OFF_RESCUE`      | Rescues allies              |
| 12  | `OFF_TAIL`        | Tail attack                 |
| 13  | `OFF_TRIP`        | Uses trip                   |
| 14  | `OFF_CRUSH`       | Crushing attacks            |
| 15  | `ASSIST_ALL`      | Assists any mob in combat   |
| 16  | `ASSIST_ALIGN`    | Assists same-alignment mobs |
| 17  | `ASSIST_RACE`     | Assists same-race mobs      |
| 18  | `ASSIST_PLAYERS`  | Assists players             |
| 19  | `ASSIST_GUARD`    | Guard-style assist          |
| 20  | `ASSIST_VNUM`     | Assists mobs with same VNUM |

#### imm / res / vuln flags (shared layout)

`imm_flags`, `res_flags`, and `vuln_flags` all use the same bit positions with
`IMM_*` / `RES_*` / `VULN_*` prefixes respectively.

| Pos | Suffix       | Damage type            |
| --- | ------------ | ---------------------- |
| 0   | `_SUMMON`    | Summon magic           |
| 1   | `_CHARM`     | Charm effects          |
| 2   | `_MAGIC`     | All magic              |
| 3   | `_WEAPON`    | Physical weapon damage |
| 4   | `_BASH`      | Bashing                |
| 5   | `_PIERCE`    | Piercing               |
| 6   | `_SLASH`     | Slashing               |
| 7   | `_FIRE`      | Fire                   |
| 8   | `_COLD`      | Cold                   |
| 9   | `_LIGHTNING` | Lightning              |
| 10  | `_ACID`      | Acid                   |
| 11  | `_POISON`    | Poison                 |
| 12  | `_NEGATIVE`  | Negative energy        |
| 13  | `_HOLY`      | Holy                   |
| 14  | `_ENERGY`    | Energy                 |
| 15  | `_MENTAL`    | Mental                 |
| 16  | `_DISEASE`   | Disease                |
| 17  | `_DROWNING`  | Drowning               |
| 18  | `_LIGHT`     | Light                  |
| 19  | `_SOUND`     | Sound                  |
| 23  | `_WOOD`      | Wood weapons           |
| 24  | `_SILVER`    | Silver weapons         |
| 25  | `_IRON`      | Iron weapons           |

#### form flags

| Pos | Constant             | Notes                         |
| --- | -------------------- | ----------------------------- |
| 0   | `FORM_EDIBLE`        | Can be eaten                  |
| 1   | `FORM_POISON`        | Poisonous                     |
| 2   | `FORM_MAGICAL`       | Magical                       |
| 3   | `FORM_INSTANT_DECAY` | Corpse disappears immediately |
| 4   | `FORM_OTHER`         | Misc                          |
| 6   | `FORM_ANIMAL`        | Animal                        |
| 7   | `FORM_SENTIENT`      | Sentient                      |
| 8   | `FORM_UNDEAD`        | Undead                        |
| 9   | `FORM_CONSTRUCT`     | Golem/construct               |
| 10  | `FORM_MIST`          | Gas/mist form                 |
| 11  | `FORM_INTANGIBLE`    | Intangible                    |
| 12  | `FORM_BIPED`         | Two-legged                    |
| 13  | `FORM_CENTAUR`       | Centaur body                  |
| 14  | `FORM_INSECT`        | Insect                        |
| 15  | `FORM_SPIDER`        | Spider                        |
| 16  | `FORM_CRUSTACEAN`    | Crab/lobster                  |
| 17  | `FORM_WORM`          | Worm                          |
| 18  | `FORM_BLOB`          | Blob/ooze                     |
| 21  | `FORM_MAMMAL`        | Mammal                        |
| 22  | `FORM_BIRD`          | Bird                          |
| 23  | `FORM_REPTILE`       | Reptile                       |
| 24  | `FORM_SNAKE`         | Snake                         |
| 25  | `FORM_DRAGON`        | Dragon                        |
| 26  | `FORM_AMPHIBIAN`     | Amphibian                     |
| 27  | `FORM_FISH`          | Fish                          |
| 28  | `FORM_COLD_BLOOD`    | Cold-blooded                  |

#### parts flags

| Pos | Constant       |     | Pos | Constant           |
| --- | -------------- | --- | --- | ------------------ |
| 0   | `PART_HEAD`    |     | 9   | `PART_EAR`         |
| 1   | `PART_ARMS`    |     | 10  | `PART_EYE`         |
| 2   | `PART_LEGS`    |     | 11  | `PART_LONG_TONGUE` |
| 3   | `PART_HEART`   |     | 12  | `PART_EYESTALKS`   |
| 4   | `PART_BRAINS`  |     | 13  | `PART_TENTACLES`   |
| 5   | `PART_GUTS`    |     | 14  | `PART_FINS`        |
| 6   | `PART_HANDS`   |     | 15  | `PART_WINGS`       |
| 7   | `PART_FEET`    |     | 16  | `PART_TAIL`        |
| 8   | `PART_FINGERS` |     | 20  | `PART_CLAWS`       |
|     |                |     | 21  | `PART_FANGS`       |
|     |                |     | 22  | `PART_HORNS`       |
|     |                |     | 23  | `PART_SCALES`      |
|     |                |     | 24  | `PART_TUSKS`       |

#### Mob enums

| Field                       | Values (integer order)                                                                   |
| --------------------------- | ---------------------------------------------------------------------------------------- |
| `start_pos` / `default_pos` | dead · mortal · incap · stunned · sleeping · resting · sitting · fighting · **standing** |
| `sex`                       | neutral (or "either") · male · female · random                                           |
| `size`                      | tiny · small · **medium** · large · huge · giant                                         |

---

### #OBJECTS

All strings are `~`-terminated.

#### Field sequence

| Line | Content                               | Notes                                       |
| ---- | ------------------------------------- | ------------------------------------------- |
| 1    | `keywords~`                           | Lookup names                                |
| 2    | `short_descr~`                        | "A sword is here."                          |
| 3    | `description~`                        | "You see a sword here."                     |
| 4    | `material~`                           | Material name (wood, bronze, leather, etc.) |
| 5    | `item_type  extra_flags  wear_flags`  | Type name + two flag fields                 |
| 6    | Item-type-specific values (see below) |                                             |
| 7    | `level  weight  cost  condition`      | Condition is a single letter                |

Followed by optional trailer lines:

| Letter | Arguments                               | Meaning                                                       |
| ------ | --------------------------------------- | ------------------------------------------------------------- |
| `A`    | `apply_loc  modifier`                   | Stat bonus while equipped                                     |
| `F`    | `where  apply_loc  modifier  bitvector` | Flag-type affect (`A`=affects `I`=immune `R`=resist `V`=vuln) |
| `E`    | `keyword~  description~`                | Extra description block                                       |
| `O`    | `trigger  prog_vnum  phrase~`           | ObjProg                                                       |

**Condition letters:**

| Letter | %   | Condition |
| ------ | --- | --------- |
| `P`    | 100 | Perfect   |
| `G`    | 90  | Good      |
| `A`    | 75  | Average   |
| `W`    | 50  | Worn      |
| `D`    | 25  | Damaged   |
| `B`    | 10  | Broken    |
| `R`    | 0   | Ruined    |

**apply_loc values (for `A` lines):**

| #   | Constant                    | Stat        |
| --- | --------------------------- | ----------- |
| 0   | `APPLY_NONE`                | —           |
| 1–5 | `APPLY_STR/DEX/INT/WIS/CON` | Stats       |
| 12  | `APPLY_MANA`                | Max mana    |
| 13  | `APPLY_HIT`                 | Max HP      |
| 17  | `APPLY_AC`                  | Armor class |
| 18  | `APPLY_HITROLL`             | Hit roll    |
| 19  | `APPLY_DAMROLL`             | Damage roll |

#### Item-type-specific values (line 6)

| `item_type`                  | Values format                                                       |
| ---------------------------- | ------------------------------------------------------------------- |
| `weapon`                     | `weapon_class  num_dice  die_size  dam_type  weapon_flags`          |
| `armor`                      | `v0  v1  v2  v3  v4` (v0=AC pierce; server copies v0→v1→v2 at load) |
| `container`                  | `capacity  cont_flags  key_vnum  max_weight  weight_mult`           |
| `potion` / `pill` / `scroll` | `level  spell1  spell2  spell3  spell4`                             |
| `wand` / `staff`             | `level  max_charges  cur_charges  spell  recharge`                  |
| `light`                      | `v0  v1  hours  v3  v4` (hours = 0 → permanent)                     |
| `key` / `treasure` / other   | `v0  v1  v2  v3  v4` (generic values)                               |

**weapon_class names** (`weapon_table` in `src/const.c`):

| Name      | Proficiency    | Note                                       |
| --------- | -------------- | ------------------------------------------ |
| `sword`   | WEAPON_SWORD   |                                            |
| `mace`    | WEAPON_MACE    |                                            |
| `dagger`  | WEAPON_DAGGER  |                                            |
| `axe`     | WEAPON_AXE     |                                            |
| `staff`   | WEAPON_SPEAR   | Name "staff" resolves to spear proficiency |
| `flail`   | WEAPON_FLAIL   |                                            |
| `whip`    | WEAPON_WHIP    |                                            |
| `polearm` | WEAPON_POLEARM |                                            |

**dam_type names** (attack_table in `src/const.c`, affects damage class):

| Name      | Class  |     | Name     | Class  |
| --------- | ------ | --- | -------- | ------ |
| `none`    | —      |     | `slice`  | slash  |
| `stab`    | pierce |     | `slash`  | slash  |
| `claw`    | slash  |     | `bite`   | pierce |
| `pierce`  | pierce |     | `thrust` | pierce |
| `pound`   | bash   |     | `crush`  | bash   |
| `blast`   | bash   |     | `chop`   | slash  |
| `beating` | bash   |     | `whip`   | slash  |

#### Annotated example — #3717 spear (ITEM_WEAPON)

| `.are` content                                           | Field                                                        | Notes                 |
| -------------------------------------------------------- | ------------------------------------------------------------ | --------------------- |
| `#3717`                                                  | VNUM                                                         |                       |
| `spear sub merc~`                                        | keywords                                                     |                       |
| `A sub issue spear~`                                     | short_descr                                                  |                       |
| `You see a sub issue spear here.~`                       | description                                                  |                       |
| `wood~`                                                  | material                                                     |                       |
| `weapon +nnnnnnnnnnnnnnnnnnnnY +YnnnnnnnnnnnnY`          | item_type · extra_flags · wear_flags                         |                       |
| `staff 1 6 thrust +n`                                    | weapon_class · num_dice · die_size · dam_type · weapon_flags | ITEM_WEAPON values    |
| `1 50 111 P`                                             | level · weight · cost · condition                            |                       |
| `A`                                                      | affect line                                                  |                       |
| `18 1`                                                   | └ apply_loc · modifier                                       | APPLY_HITROLL(18), +1 |
| `E`                                                      | extra description                                            |                       |
| `spear~`                                                 | └ keyword                                                    |                       |
| `You see a spear of great but cheap craftsmanship...\n~` | └ text                                                       |                       |

Flag values decoded:
- `extra_flags` `+nnnnnnnnnnnnnnnnnnnnY` → `ITEM_MELT_DROP` (pos 20) — dissolves when mob body decays
- `wear_flags` `+YnnnnnnnnnnnnY` → `ITEM_TAKE` (pos 0) + `ITEM_WIELD` (pos 13)
- `weapon_class` `staff` → resolves to `WEAPON_SPEAR` proficiency (see weapon_table)
- `weapon_flags` `+n` → none

#### extra_flags

| Pos | Constant            | Notes                                    |
| --- | ------------------- | ---------------------------------------- |
| 0   | `ITEM_GLOW`         | Glows                                    |
| 1   | `ITEM_HUM`          | Hums                                     |
| 2   | `ITEM_DARK`         | Emits darkness                           |
| 3   | `ITEM_LOCK`         | Locked                                   |
| 4   | `ITEM_EVIL`         | Evil aura                                |
| 5   | `ITEM_INVIS`        | Invisible                                |
| 6   | `ITEM_MAGIC`        | Magical                                  |
| 7   | `ITEM_NODROP`       | Cannot be dropped                        |
| 8   | `ITEM_BLESS`        | Blessed                                  |
| 9   | `ITEM_ANTI_GOOD`    | Good characters cannot use               |
| 10  | `ITEM_ANTI_EVIL`    | Evil characters cannot use               |
| 11  | `ITEM_ANTI_NEUTRAL` | Neutral characters cannot use            |
| 12  | `ITEM_NOREMOVE`     | Cannot be removed once worn              |
| 13  | `ITEM_INVENTORY`    | Mob inventory item; not dropped on reset |
| 14  | `ITEM_NOPURGE`      | Not removed on area reset                |
| 15  | `ITEM_ROT_DEATH`    | Rots when owner dies                     |
| 16  | `ITEM_VIS_DEATH`    | Only visible on death                    |
| 20  | `ITEM_MELT_DROP`    | Dissolves when dropped from corpse       |
| 23  | `ITEM_BURN_PROOF`   | Immune to fire                           |
| 24  | `ITEM_NOUNCURSE`    | Cannot be uncursed                       |
| 26  | `ITEM_QUEST`        | Quest item                               |

#### wear_flags

| Pos | Constant           | Slot                 |
| --- | ------------------ | -------------------- |
| 0   | `ITEM_TAKE`        | Can be picked up     |
| 1   | `ITEM_WEAR_FINGER` | Finger               |
| 2   | `ITEM_WEAR_NECK`   | Neck                 |
| 3   | `ITEM_WEAR_BODY`   | Body/chest           |
| 4   | `ITEM_WEAR_HEAD`   | Head                 |
| 5   | `ITEM_WEAR_LEGS`   | Legs                 |
| 6   | `ITEM_WEAR_FEET`   | Feet                 |
| 7   | `ITEM_WEAR_HANDS`  | Hands                |
| 8   | `ITEM_WEAR_ARMS`   | Arms                 |
| 9   | `ITEM_WEAR_SHIELD` | Shield               |
| 10  | `ITEM_WEAR_ABOUT`  | About body (cloak)   |
| 11  | `ITEM_WEAR_WAIST`  | Waist                |
| 12  | `ITEM_WEAR_WRIST`  | Wrist                |
| 13  | `ITEM_WIELD`       | Weapon hand          |
| 14  | `ITEM_HOLD`        | Off hand (held)      |
| 15  | `ITEM_NO_SAC`      | Cannot be sacrificed |
| 16  | `ITEM_WEAR_FLOAT`  | Floating about body  |

#### weapon_flags (value[4] of ITEM_WEAPON)

| Pos | Constant           | Effect                 |
| --- | ------------------ | ---------------------- |
| 0   | `WEAPON_FLAMING`   | Fire damage bonus      |
| 1   | `WEAPON_FROST`     | Cold damage bonus      |
| 2   | `WEAPON_VAMPIRIC`  | Life steal             |
| 3   | `WEAPON_SHARP`     | Can decapitate         |
| 4   | `WEAPON_VORPAL`    | Extra decap chance     |
| 5   | `WEAPON_TWO_HANDS` | Requires both hands    |
| 6   | `WEAPON_SHOCKING`  | Lightning damage bonus |
| 7   | `WEAPON_POISON`    | Poisons on hit         |

---

### #ROOMS

All strings are `~`-terminated.

#### Field sequence

| Line | Content                      | Notes                                                   |
| ---- | ---------------------------- | ------------------------------------------------------- |
| 1    | `name~`                      | Room title                                              |
| 2    | `description~`               | Room description; multi-line                            |
| 3    | `0  room_flags  sector_type` | First integer discarded; `sector_type` is an enum index |

Followed by optional lines terminated by `S`:

| Letter | Arguments                                                         | Meaning                              |
| ------ | ----------------------------------------------------------------- | ------------------------------------ |
| `D`    | `direction` then `desc~  keyword~  exit_flags  key_vnum  to_room` | Exit record                          |
| `E`    | `keyword~  description~`                                          | Extra description                    |
| `H`    | `int`                                                             | Heal rate (% of normal; default 100) |
| `M`    | `int`                                                             | Mana rate (% of normal; default 100) |
| `G`    | `int`                                                             | Guild class index                    |
| `S`    | —                                                                 | End-of-room sentinel (required)      |

**Exit direction codes:** 0=N  1=E  2=S  3=W  4=Up  5=Down

#### Annotated example — #3700 Entrance to Mud School

| `.are` content                 | Field                              | Notes                               |
| ------------------------------ | ---------------------------------- | ----------------------------------- |
| `#3700`                        | VNUM                               |                                     |
| `Entrance to Mud School~`      | name                               |                                     |
| `This is the entrance...\n~`   | description                        | multi-line                          |
| `0 +nnYY 0`                    | ignored · room_flags · sector_type |                                     |
| `D0`                           | exit north                         | direction code 0                    |
| `You see the doorway...~`      | └ exit desc                        |                                     |
| `~`                            | └ keyword                          | empty (no door keyword)             |
| `+n 0 3757`                    | └ exit_flags · key_vnum · to_room  | open passage                        |
| `D2`                           | exit south                         | direction code 2                    |
| `You see the one way door...~` | └ exit desc                        |                                     |
| `door~`                        | └ keyword                          |                                     |
| `+YY -1 3744`                  | └ exit_flags · key_vnum · to_room  | closed door; key=-1 (no key needed) |
| `D5`                           | exit down                          | direction code 5                    |
| `You see the Temple...~`       | └ exit desc                        |                                     |
| `~`                            | └ keyword                          | empty                               |
| `+n 0 3001`                    | └ exit_flags · key_vnum · to_room  | open passage                        |
| `S`                            | end sentinel                       | required                            |

Flag values decoded:
- `room_flags` `+nnYY` → `ROOM_NO_MOB` (pos 2) + `ROOM_INDOORS` (pos 3)
- North exit `+n` → open passage, no door
- South exit `+YY` → `EX_ISDOOR`(0) + `EX_CLOSED`(1) — a closed but unlocked door (`key = -1`)
- Down exit `+n` → open passage

#### room_flags

| Pos | Constant         | Notes                                   |
| --- | ---------------- | --------------------------------------- |
| 0   | `ROOM_DARK`      | Always dark; needs light source         |
| 2   | `ROOM_NO_MOB`    | Mobs cannot enter                       |
| 3   | `ROOM_INDOORS`   | Indoors; protected from weather         |
| 4   | `ROOM_ARENA`     | Arena combat room                       |
| 5   | `ROOM_BANK`      | Bank                                    |
| 9   | `ROOM_PRIVATE`   | Max 2 occupants                         |
| 10  | `ROOM_SAFE`      | No combat                               |
| 11  | `ROOM_SOLITARY`  | Max 1 occupant                          |
| 12  | `ROOM_PET_SHOP`  | Pet shop                                |
| 13  | `ROOM_NO_RECALL`    | Cannot recall from here                 |
| 14  | `ROOM_IMP_ONLY`     | Immortal (imp) access only              |
| 15  | `ROOM_GODS_ONLY`    | God-level access only                   |
| 16  | `ROOM_HEROES_ONLY`  | Hero-level access only                  |
| 17  | `ROOM_NEWBIES_ONLY` | Newbie access only                      |
| 18  | `ROOM_LAW`          | Law zone (auto-set for VNUMs 3000–3399) |
| 19  | `ROOM_NOWHERE`   | Unreachable via normal exits            |
| 20  | `ROOM_NOEXPLORE` | Not counted for explore tracking        |
| 21  | `ROOM_NOAUTOMAP` | Hidden from automap                     |
| 22  | `ROOM_SAVE_OBJS` | Items persist across resets             |

#### sector_type

| #   | Constant            | Move cost |
| --- | ------------------- | --------- |
| 0   | `SECT_INSIDE`       | 1         |
| 1   | `SECT_CITY`         | 2         |
| 2   | `SECT_FIELD`        | 2         |
| 3   | `SECT_FOREST`       | 3         |
| 4   | `SECT_HILLS`        | 4         |
| 5   | `SECT_MOUNTAIN`     | 6         |
| 6   | `SECT_WATER_SWIM`   | 4         |
| 7   | `SECT_WATER_NOSWIM` | 1         |
| 8   | `SECT_ICE`          | 6         |
| 9   | `SECT_AIR`          | 10        |
| 10  | `SECT_DESERT`       | 6         |
| 11  | `SECT_ROAD`         | 1         |
| 12  | `SECT_PATH`         | 1         |
| 13  | `SECT_SWAMP`        | 6         |
| 14  | `SECT_JUNGLE`       | 4         |

#### exit_flags (per `D` record)

| Pos | Constant         | Notes                      |
| --- | ---------------- | -------------------------- |
| 0   | `EX_ISDOOR`      | A door exists on this exit |
| 1   | `EX_CLOSED`      | Currently closed           |
| 2   | `EX_LOCKED`      | Locked (requires key)      |
| 3   | `EX_DOORBELL`    | Has a doorbell             |
| 5   | `EX_PICKPROOF`   | Cannot be picked           |
| 6   | `EX_NOPASS`      | Blocks `pass_door` spell   |
| 7   | `EX_EASY`        | Easy to pick               |
| 8   | `EX_HARD`        | Hard to pick               |
| 9   | `EX_INFURIATING` | Very hard to pick          |
| 10  | `EX_NOCLOSE`     | Cannot be closed           |
| 11  | `EX_NOLOCK`      | Cannot be locked           |

---

### #RESETS

One command per line; section ends at `S`.  Lines beginning with `*` are
comments.  The first integer after the command letter is always discarded
(`read_number(fp)` with no assignment).

| Cmd | Arguments                                    | Meaning                                                          |
| --- | -------------------------------------------- | ---------------------------------------------------------------- |
| `M` | `0  mob_vnum  room_max  room_vnum  area_max` | Spawn mob; `room_max` = per-room cap, `area_max` = area-wide cap |
| `O` | `0  obj_vnum  0  room_vnum`                  | Place object in room                                             |
| `E` | `0  obj_vnum  0  equip_slot`                 | Equip object on last `M` mob (deferred in PrimeSUD)              |
| `G` | `0  obj_vnum  0`                             | Give object to last `M` mob's inventory (deferred)               |
| `P` | `0  obj_vnum  0  container_vnum  max`        | Put object inside container (deferred)                           |
| `R` | `0  room_vnum  num_dirs`                     | Randomize exits in room (deferred)                               |
| `D` | `0  room_vnum  exit_num  locks`              | Set door state: 0=open 1=closed 2=locked (deferred)              |
| `F` | `0  room_vnum  exit_num  flags`              | Set exit flags directly (deferred)                               |

PrimeSUD currently processes `M` and `O` only; see DESIGN.md § *Area file system*.

---

## Colour codes

Same `{X` escape syntax as 1stMud — embed in strings passed to `tr.print()`, handled by `colors.py`.

| Code | Colour | Code | Colour |
|------|--------|------|--------|
| `{d` | dark grey | `{D` | grey |
| `{r` | red | `{R` | bright red |
| `{g` | green | `{G` | bright green |
| `{y` | yellow | `{Y` | bright yellow |
| `{b` | blue | `{B` | bright blue |
| `{m` | magenta | `{M` | bright magenta |
| `{c` | cyan | `{C` | bright cyan |
| `{w` | light grey | `{W` | white |
| `{x` / `{X` | reset to default | | |
