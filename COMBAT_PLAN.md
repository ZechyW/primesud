# Combat Fidelity Plan

## Goal

Port PrimeSUD combat toward 1stMud `fight.c` fidelity while preserving explicit
PrimeSUD design decisions.  Primary references:

- `reference/1stMud4.5.3/src/fight.c`
- `primesud.hpappdir/combat.py`
- `DESIGN.md`
- `REFERENCE.md`

This plan covers `one_hit`, `damage`, `multi_hit`, AC handling, defensive
skills, attack-count skills, and user-visible combat output.

**Status: proposed.**

---

## Fixed decisions

- NPC dodge/parry follows 1stMud.  This means `OFF_DODGE` and `OFF_PARRY` are
  effectively ignored for core defense checks, as in 1stMud.
- Full 1stMud-equivalent AC buckets will be ported for mobs and players:
  pierce, bash, slash, exotic.
- Stances remain explicitly not ported.  Omitted stance branches should be
  marked with `[PRIMESUD]`.
- Full PC classes and races remain deferred.  Player THAC0 can stay classless
  until those systems are introduced.
- Keep HP Prime constraints in mind: no new dependencies, small data structures,
  ASCII-only Python source, and avoid broad refactors outside combat/actor/item
  boundaries.

---

## Current gaps

| Area | 1stMud behavior | PrimeSUD current behavior | Gap |
| ---- | --------------- | ------------------------- | --- |
| Entry guards | `one_hit` rejects null/self/dead/different-room cases | Assumes valid pair | Add guard equivalent where useful |
| Attack type | `dt` drives attack noun and damage class; `TYPE_UNDEFINED` resolves to weapon or mob `dam_type` | Uses weapon/mob `dam_type`; no `dt` convention | Add lightweight `dt`/attack-type convention when needed for backstab and specials |
| AC | Selects `AC_PIERCE`, `AC_BASH`, `AC_SLASH`, or `AC_EXOTIC` from `dam_type` | Single `AC` value | Port AC buckets for all actors |
| NPC THAC0 | NPC act flags pick `thac0_32`: warrior -10, thief -4, cleric +2, mage +6, default -4 | Classless curve for all | Port NPC act-type THAC0; keep PC classless |
| Defense checks | `damage()` checks dodge, parry, shield block, force/static shield | `one_hit()` checks parry only | Move/centralize defense in `damage()` |
| Dodge | `get_skill(dodge)/2`, visibility penalty, level delta | Missing | Add `check_dodge` |
| Shield block | `get_skill(shield block)/5 + 3`, requires shield, level delta | Missing | Add `check_shield_block` |
| Parry | Awake/equipment/visibility/level formula | Partial formula | Align with 1stMud |
| Enhanced damage | Skill chance adds variable damage and improves skill | Missing | Add after base damage |
| Second/third attack | `second/2`, `third/4`, with improvement on success | Uses full learned percent, no improvement | Match 1stMud chances and improvement |
| NPC fast/extra hits | `AFF_HASTE` or `OFF_FAST` grants extra hit; second/third use `get_skill` chances | Synthetic level-derived second/third | Match 1stMud attack count |
| Damage output | Central `dam_message()` handles misses/hits/immune text | Direct custom prints | Add central message path |
| Resist/immune/vuln | `damage()` applies after shields/flame shield | Missing for weapon hits | Add after AC/data migration |
| Weapon flags | sharp, poison, vampiric, flaming, frost, shocking | Mostly missing | Later phase |

---

## Target combat flow

### `multi_hit`

Target order mirrors 1stMud, with stance branches omitted:

1. Decrement `wait` and `daze` for NPCs without descriptors if still relevant.
2. Return if actor cannot fight.
3. NPC path delegates to `mob_hit`.
4. PC primary `one_hit`.
5. PC secondary weapon `one_hit(..., secondary=True)` if equipped.
6. Haste extra hit when affect system supports it.
7. Return early for special `dt` cases such as backstab.
8. `[PRIMESUD]` omit stance `special_move`.
9. Second attack chance: `get_skill(ch, GSN_SECOND_ATTACK) // 2`.
10. Third attack chance: `get_skill(ch, GSN_THIRD_ATTACK) // 4`.
11. Apply `AFF_SLOW` rules when affect system supports it.

On successful second/third attacks for players:

- `check_improve(tr, ch, GSN_SECOND_ATTACK, True, 5)`
- `check_improve(tr, ch, GSN_THIRD_ATTACK, True, 6)`

### `mob_hit`

Target order mirrors 1stMud:

1. Primary `one_hit`.
2. Area attack if `OFF_AREA_ATTACK` is meaningful in single-player room combat.
3. Extra hit from `AFF_HASTE` or `off_flags["fast"]`, unless slowed.
4. Second attack chance: `get_skill(ch, GSN_SECOND_ATTACK, is_mob=True) // 2`.
5. Third attack chance: `get_skill(ch, GSN_THIRD_ATTACK, is_mob=True) // 4`.
6. Skip stance branches.
7. Existing special attacks (`kick`, later `bash`, `trip`, etc.) keep 1stMud
   random-switch order as they are ported.

### `one_hit`

`one_hit` should compute attack setup and base damage, then call `damage()`.

1. Guard invalid/self/dead/out-of-room cases.
2. Resolve weapon slot: `wield` or `secondary`.
3. Resolve attack type:
   - undefined/default -> weapon `dam_type` if armed, else mob/player unarmed
   - explicit skill `dt` later for backstab/specials
4. Resolve `dam_class` from `ATTACK_TABLE`.
5. Resolve weapon skill:
   - `sn = get_weapon_sn(ch)`
   - `skill = 20 + get_weapon_skill(ch, sn)`
6. Compute THAC0:
   - NPC: 1stMud act-type curve
   - PC: PrimeSUD classless curve until classes are ported
   - apply 1stMud soft caps
   - subtract hitroll scaled by skill
   - add poor-skill penalty
7. Compute victim AC via `get_armor(victim, dam_class) // 10`.
8. Apply AC soft cap:
   - `if victim_ac < -15: victim_ac = (victim_ac + 15) // 5 - 15`
9. Apply visibility/position AC adjustments when those systems exist.
10. Roll d20 equivalent:
   - natural 0 misses
   - natural 19 hits
11. On miss, call `damage(..., dam=0, show=True)`.
12. Compute base damage:
   - NPC damage dice
   - weapon dice scaled by skill
   - unarmed formula
13. Add no-shield weapon bonus:
   - if wielding weapon and no shield, `dam = dam * 11 // 10`
14. Add `WEAPON_SHARP` later when weapon flags are ported.
15. `[PRIMESUD]` omit stance damage branches.
16. Apply enhanced damage.
17. Apply sleeping/resting modifiers when positions exist.
18. Apply backstab modifier when `dt == GSN_BACKSTAB`.
19. Add damroll scaled by skill.
20. Clamp minimum damage to 1.
21. Call `damage(ch, victim, dam, dt, dam_class, show=True)`.
22. Apply weapon special effects later if `damage()` returned true and combat
    still targets same victim.

### `damage`

`damage` owns defense checks, reductions, HP subtraction, and output.

Target order:

1. Return false if victim already dead.
2. Cap absurd damage defensively if needed.
3. Apply 1stMud soft damage caps:
   - `>35`: `(dam - 35) // 2 + 35`
   - `>80`: `(dam - 80) // 2 + 80`
4. Establish combat state if needed.
5. Reveal invisible attacker when invisibility exists.
6. Apply drunk/sanctuary/protection reductions when those systems exist.
7. For weapon hits against another actor:
   - `check_dodge`
   - `[PRIMESUD]` omit stance extra dodge checks
   - `check_parry`
   - `[PRIMESUD]` omit stance extra parry checks
   - `check_shield_block`
   - `check_force_shield`
   - `check_static_shield`
8. If victim has flame shield and damage class is physical, call
   `check_flame_shield`.
9. Apply immunity/resistance/vulnerability.
10. `[PRIMESUD]` skip broken 1stMud `randomize_damage` unless intentionally
    restored.  In 1stMud the result is not assigned.
11. Print via `dam_message` when `show` is true.
12. Subtract HP, update death/fight state, and return whether damage landed.

---

## AC system migration

### Data model

Use 1stMud order everywhere:

```python
AC_PIERCE = 0
AC_BASH = 1
AC_SLASH = 2
AC_EXOTIC = 3
```

Compact tuple storage is preferred for HP Prime memory:

```python
"armor": (100, 100, 100, 100)
```

Meaning:

- index 0: pierce
- index 1: bash
- index 2: slash
- index 3: exotic

For readability in conversion tools/docs, source fields may still be named
`ac_pierce`, `ac_bash`, `ac_slash`, `ac_exotic`.

### Actors

Players and mobs both need four armor buckets.

- Mob templates keep area-file AC values in 1stMud scale.
- Player base armor defaults should match current behavior as closely as
  possible.
- Save/load must include new player armor representation only if derived state
  cannot be recomputed from base stats and equipment. Prefer recomputing when
  possible.

### Items

Armor items should store four values in 1stMud order.

Existing item data using one AC value should be migrated by copying that value
to pierce/bash/slash and choosing an exotic value consistent with converted
area data. For converted `.are` armor, use exact four values.

### Helpers

Add or migrate toward:

```python
def get_armor(ch, ac_type):
    """Return actor armor for a 1stMud AC_* bucket."""
```

`get_armor` should:

1. Start from actor base armor tuple.
2. Add equipment armor tuple contributions.
3. Add DEX defensive bonus through existing `DEX_APP_DEF`.
4. Return integer in 1stMud scale.

Keep `get_AC(ch)` temporarily as a compatibility wrapper. Remove or narrow it
after combat callers use `get_armor`.

---

## Defensive skills

### `check_dodge`

1stMud formula:

```text
chance = get_skill(victim, gsn_dodge) / 2
if victim cannot see attacker: chance /= 2
success if number_percent() < chance + victim.level - attacker.level
```

Messages:

- Victim player: `You dodge <attacker>'s attack.`
- Attacker player: `<victim> dodges your attack.`

NPCs use `get_skill(..., is_mob=True)` and do not require `OFF_DODGE`.

### `check_parry`

1stMud formula:

```text
chance = get_skill(victim, gsn_parry) / 2
if victim has no wielded weapon:
    NPC chance /= 2
    PC cannot parry
if attacker cannot see victim: chance /= 2
success if number_percent() < chance + victim.level - attacker.level
```

Messages:

- Victim player: `You parry <attacker>'s attack.`
- Attacker player: `<victim> parries your attack.`

NPCs use `get_skill(..., is_mob=True)` and do not require `OFF_PARRY`.

### `check_shield_block`

1stMud formula:

```text
chance = get_skill(victim, gsn_shield_block) / 5 + 3
requires shield
success if number_percent() < chance + victim.level - attacker.level
```

Messages:

- Victim player: `You block <attacker>'s attack with your shield.`
- Attacker player: `<victim> blocks your attack with a shield.`

### Shield spells

Port after base defense checks:

- `check_force_shield`
- `check_static_shield`
- `check_flame_shield`

Use affect names matching skill table spell names where possible:

- `forceshield`
- `staticshield`
- `flameshield`

---

## Enhanced damage

Use 1stMud behavior:

```text
if get_skill(ch, gsn_enhanced_damage) > 0:
    roll = number_percent()
    if roll <= skill:
        check_improve(ch, gsn_enhanced_damage, true, 6)
        dam += 2 * (dam * roll / 300)
```

Python integer form:

```python
dam += 2 * (dam * roll // 300)
```

No combat output.  Player may see normal skill-improvement output.

---

## User-visible output

Long-term target is a central `dam_message()` equivalent rather than direct
printing in each attack path.

PrimeSUD is single-user, so output only needs player-visible channels:

- player attacking mob
- mob attacking player
- player defending with dodge/parry/shield block
- mob defending with dodge/parry/shield block

Multiplayer-only channels (`TO_ROOM`, `TO_NOTVICT`) collapse or disappear.

Use 1stMud text where it matters for fidelity:

- `You dodge $n's attack.`
- `$N dodges your attack.`
- `You parry $n's attack.`
- `$N parries your attack.`
- `You block $n's attack with your shield.`
- `$N blocks your attack with a shield.`
- `Your force-shield blocks $n's attack!`
- `$N's force-shield blocks your attack.`

Damage verb thresholds already mostly match 1stMud and should move behind
`dam_message()`.

---

## Phases

### Phase 1: AC buckets

- Add AC constants.
- Add `get_armor(ch, ac_type)`.
- Migrate mob/player/item armor data.
- Update `one_hit` to choose AC bucket by `dam_class`.
- Keep `get_AC` compatibility wrapper during transition.

### Phase 2: defense checks

- Add `check_dodge`.
- Align `check_parry`.
- Add `check_shield_block`.
- Move defense checks into `damage()` or a transitional shared resolver.
- Preserve exact player-facing messages.

### Phase 3: attack count skills

- Change second/third attack chances to 1stMud formulas.
- Add skill improvement on successful second/third attacks.
- Update NPC `mob_hit` for `OFF_FAST` and 1stMud `get_skill` chances.

### Phase 4: enhanced damage

- Add `GSN_ENHANCED_DAMAGE` import.
- Apply 1stMud enhanced damage formula.
- Add player skill improvement.

### Phase 5: central `damage` and `dam_message`

- Route misses and hits through common output.
- Keep death handling compatible with `raw_kill` and existing single-player
  fight state.
- Move soft damage caps into `damage`.

### Phase 6: resist/immune/vuln and weapon flags

- Apply `imm_flags`, `res_flags`, `vuln_flags`.
- Port `WEAPON_SHARP`.
- Port poison/vampiric/flaming/frost/shocking effects as supporting spell/effect
  systems allow.

### Phase 7: shield spells

- Wire force/static/flame shield checks into weapon-hit defense flow.
- Reuse existing spell/affect conventions from `magic.py`.

---

## Test plan

Use deterministic or monkeypatched RNG tests where possible.

Core tests:

- `one_hit` selects pierce/bash/slash/exotic AC bucket from weapon/mob damage
  type.
- Natural miss and natural hit behavior.
- Dodge success prevents HP loss and prints expected message.
- Parry success prevents HP loss and prints expected message.
- Shield block requires shield and prevents HP loss.
- NPC dodge/parry works without `OFF_DODGE`/`OFF_PARRY`.
- Second attack fires at skill/2, not full skill.
- Third attack fires at skill/4, not full skill.
- Enhanced damage increases damage only on successful skill roll.
- Existing kill/XP flow still works after routing through `damage`.

Manual emulator checks:

- Player attacks school mobs with different weapon damage types.
- Mobs with and without wielded weapons can/cannot parry according to 1stMud
  rules.
- Shield-equipped player sees shield block text.
- Combat output fits 64-column display without awkward wraps.

After Python edits:

```powershell
python tools/check_ascii_py.py
```

