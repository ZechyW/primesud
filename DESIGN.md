# PrimeSUD - Design Decisions

Intentional deviations from 1stMud and design choices made for PrimeSUD. Read before porting a new mechanic to avoid re-litigating settled decisions. Features not listed here: assume 1stMud behaviour unless code says otherwise.

**Guiding principle:** PrimeSUD is single-player. Multiplayer mechanics are excluded unless they add meaningful solo gameplay value. Mechanics with no current content hook are deferred, not eliminated.

---

## HP Prime runtime

HP Prime Python appears to load all `.py` files in the app before `primesud.py` runs. Lazy `import` patterns may not reduce first-launch wait if the source file is still packaged. Prefer lazy runtime initialisation for heap stability: avoid duplicate merged catalogs, bulk mutable state, and all-world resets until data is actually needed.

Pickers force numeric keyboard mode on entry (`picker.py:_force_numeric_keys`) so stale alpha/shift-lock state doesn't eat digit selections.

---

## Not ported

| Feature | Reason |
|---|---|
| Move / MV | No solo gameplay hook identified; omitted entirely |
| Race system | Ported: RACE_TABLE in races.py, race defaults merged at mob creation, check_immune in combat. Chargen (name, class, alignment, weapon) exists but has no race-selection step; race stays at the fixed human default |
| Class system | Ported: CLASS_TABLE (6 classes) in classes.py, remort/multiclass, chargen class picker, per-class THAC0 and HP/mana gain, skill groups + `gain`. Creation-point group customisation at chargen not ported |
| Stat rolling | Fixed 13 across the board; no chargen reroll |
| Saving throws | `saving_throw = 0` baseline with `saves_spell`/`saves_dispel`/`check_dispel`; race/class modifiers and equipment bonuses deferred |
| Alignment / deity | No solo gameplay hook identified |
| Clan / rank | Multiplayer |
| Hunger / thirst | No solo gameplay hook identified |
| Age / hours played | HP Prime has no reliable RTC |
| Explore tracking | Planned; placeholder in `do_score` |
| Trivia economy | Counter and trivia pill retained for quest compatibility; shop/reward system later |
| Pkills / pdeaths | Single-player |
| Per-mob kill/death stats | 1stMud writes back to `.are` on shutdown; PrimeSUD areas are static Python files |

---

## Adjusted from 1stMud

| Feature | 1stMud | PrimeSUD | Reason |
|---|---|---|---|
| EXP per level | `exp_per_level()` -- scales with creation points and race/class mult | Flat 1000 XP / level | Equivalent at 40 creation points, human baseline |
| Level-up heal | Adds gains to `max_hit`/`max_mana`; current HP/MP unchanged | Fully restores current HP and MP | Eliminates "levelled at 1 HP mid-fight" |
| Remort progression | `lvl_bonus` multiplier against 1stMud's economy | Same formula against PrimeSUD's flatter economy (20 HP at creation) -- first remort lands ~6000 HP/mana/move, 300 trains, 420 practices | Accepted 03/07/2026 as an NG+-style feature; revisit after playtest |
| Pulse timing | `PULSE_VIOLENCE = 3xPPS`, `PULSE_MOBILE = 4xPPS`, `PULSE_TICK = 45xPPS` | `2xPPS`, `5xPPS`, `30xPPS` | Faster combat/regen; slower mob wander |

---

## Area files

Python modules (`area_<name>.py`) instead of parsed `.are` files -- runtime text parsing too memory-intensive. See **[AREA_FILES.md](AREA_FILES.md)** for full format reference.
