# PrimeSUD - Design Decisions

Intentional deviations from 1stMud and design choices made for PrimeSUD. Read before porting a new mechanic to avoid re-litigating settled decisions. Features not listed here: assume 1stMud behaviour unless code says otherwise.

**Guiding principle:** PrimeSUD is single-player. Multiplayer mechanics are excluded unless they add meaningful solo gameplay value. Mechanics with no current content hook are deferred, not eliminated.

---

## HP Prime runtime

HP Prime Python appears to load all `.py` files in the app before `primesud.py` runs. Lazy `import` patterns may not reduce first-launch wait if the source file is still packaged. Prefer lazy runtime initialisation for heap stability: avoid duplicate merged catalogs, bulk mutable state, and all-world resets until data is actually needed.

---

## Not ported

| Feature | Reason |
|---|---|
| Move / MV | No solo gameplay hook identified; omitted entirely |
| Race system | Human baseline (13 flat, max 18); add when content justifies |
| Class system | Classless; THAC0 uses balanced midpoint. Add when skill trees justify |
| Stat rolling | Fixed 13 across the board; no chargen reroll |
| AC types (Pierce/Bash/Slash/Exotic) | Bucket AC stored and selected in `one_hit`; broader combat fidelity (res/imm/vuln, damage flow) incomplete |
| Mob THAC0 by act type | 1stMud NPC curves: warrior -10, thief -4, cleric +2, mage +6. PrimeSUD uses single classless plateau (`THAC0_MIN = -2`). Port when NPC class diversity needed |
| Saving throws | `saving_throw = 0` baseline with `saves_spell`/`saves_dispel`/`check_dispel`; race/class modifiers and equipment bonuses deferred |
| Alignment / deity | No solo gameplay hook identified |
| Clan / rank | Multiplayer |
| Hunger / thirst | No solo gameplay hook identified |
| Stance system | 1stMud-specific extension; no equivalent content planned |
| Age / hours played | HP Prime has no reliable RTC |
| Gold / silver | Planned; placeholder in `do_score` |
| Explore tracking | Planned; placeholder in `do_score` |
| Trivia economy | Counter and trivia pill retained for quest compatibility; shop/reward system later |
| Pkills / pdeaths | Single-player |
| Per-mob kill/death stats | 1stMud writes back to `.are` on shutdown; PrimeSUD areas are static Python files |

---

## Adjusted from 1stMud

| Feature | 1stMud | PrimeSUD | Reason |
|---|---|---|---|
| EXP per level | `exp_per_level()` -- scales with creation points and race/class mult | Flat 1000 XP / level | Equivalent at 40 creation points, human baseline |
| Class HP die | Per-class `hp_min`/`hp_max` (Warrior 11-15, Mage 6-8, ...) | 7-10 (Cleric/Paladin midpoint) | Classless placeholder; update when classes added |
| Level-up heal | Adds gains to `max_hit`/`max_mana`; current HP/MP unchanged | Fully restores current HP and MP | Eliminates "levelled at 1 HP mid-fight" |
| Pulse timing | `PULSE_VIOLENCE = 3xPPS`, `PULSE_MOBILE = 4xPPS`, `PULSE_TICK = 45xPPS` | `2xPPS`, `5xPPS`, `30xPPS` | Faster combat/regen; slower mob wander |

---

## Area files

Python modules (`area_<name>.py`) instead of parsed `.are` files -- runtime text parsing too memory-intensive. See **[AREA_FILES.md](AREA_FILES.md)** for full format reference.
