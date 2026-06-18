# PrimeSUD — Design Decisions

General mechanics and gameplay feel are inspired by, and sometimes ported directly from, 1stmud (`reference/1stMud4.5.3`).
This doc lists intentional deviations from 1stMud and design choices made for PrimeSUD.
Reference this before porting a new mechanic to avoid re-litigating settled decisions.

---

## HP Prime runtime constraints

- HP Prime Python appears to load all `.py` files in the app before `primesud.py`
  can run benchmark code. Startup-time measurements taken inside `primesud.py`
  therefore miss some app-load cost, and lazy `import` patterns may not reduce
  first-launch wait if the source file is still packaged in the app. Prefer lazy
  runtime initialisation when the goal is heap stability: avoid duplicate merged
  catalogs, bulk mutable state, and all-world resets until data is actually
  needed.

---

## Not ported

| Feature | Decision | Reason |
|---|---|---|
| Intercardinal directions (NE/NW/SE/SW) | **Removed** | 1stMud has no diagonal movement (`MAX_DIR = 6`: N E S W U D). Intercardinals were briefly added as a d-pad experiment but no world areas use them; removed for simplicity |
| Move / MV | **Not ported** | No gameplay value in a single-player calculator game; MV drain/regen omitted entirely |
| Race system | **Deferred** | All characters use human baseline stats (13 flat, max 18). Add when content justifies it |
| Class system | **Deferred** | Classless for now; THAC0 curve uses a balanced midpoint. Add when skill trees justify it |
| Stat rolling | **Deferred** | Fixed 13 across the board; no chargen reroll screen |
| AC types (Pierce/Bash/Slash/Exotic) | **Deferred** | 1stMud `one_hit` (`fight.c`) selects one of four `armor[]` buckets (pierce/bash/slash/exotic) based on `dam_class`; `GetArmor` then adds the DEX defensive bonus. PrimeSUD keeps a single `AC` field. `ATTACK_TABLE` already carries the correct `dam_class` per weapon — expand to per-bucket AC (and then to res/imm/vuln flag checks) when the content warrants it |
| Mob THAC0 by act type | **Deferred** | 1stMud `one_hit` uses per-class curves for NPCs: warrior `thac0_32 = -10`, thief `-4`, cleric `+2`, mage `+6`, default `-4`. PrimeSUD uses the single classless plateau (`THAC0_MIN = -2`) for both players and mobs. Port when NPC class diversity is needed for balance |
| Saving throws | **Not ported** | Not implemented; add alongside spell effects if/when needed |
| Alignment / deity | **Not ported** | Multiplayer/world-state concepts with no single-player hook |
| Clan / rank / trivia | **Not ported** | Multiplayer concepts |
| Hunger / thirst | **Not ported** | No meaningful single-player gameplay hook |
| Age / hours played | **Not ported** | No persistent wall-clock; calculator has no reliable RTC |
| Gold / silver | **Not yet** | Planned; placeholder slot exists in `do_score` right-column bottom |
| Explore tracking | **Not yet** | Planned; placeholder exists in `do_score` footer area |
| Pkills / pdeaths | **Not ported** | Single-player |
| Per-mob `S kills deaths` stats | **Not ported** | 1stMud writes cumulative kill/death counts per mob prototype back to the `.are` file on shutdown (`fight.c:update_death`, `db2.c:load_mobiles`).  PrimeSUD area modules are static Python files — no write-back mechanism, and no analytics use for the data in a single-player game |
| Stance system | **Not ported** | 1stMud-specific combat extension; out of scope |

---

## Simplified or adjusted

| Feature | 1stMud | PrimeSUD | Reason |
|---|---|---|---|
| EXP per level | `exp_per_level(ch, points)` — scales with creation points and race/class mult | Flat **1000 XP / level** | Equivalent to 1stMud formula at 40 creation points, human race (100% mult) |
| Class HP die | Per-class `hp_min`/`hp_max` (Warrior 11–15, Mage 6–8, …) | **7–10** (Cleric/Paladin midpoint) | Classless placeholder; change when classes are added |
| Level-up heal | Adds gains to `max_hit`/`max_mana` only; current HP/MP unchanged | **[PRIMESUD]** fully restores current HP and MP | Quality-of-life: eliminates "levelled at 1 HP mid-fight" awkwardness |
| Pulse timing | `PULSE_VIOLENCE = 3×PPS`, `PULSE_MOBILE = 4×PPS`, `PULSE_TICK = 45×PPS` | **`2×PPS`, `5×PPS`, `30×PPS`** | Faster combat and regen ticks for single-player UX; slower mob wander |
| Trainer mechanic | `do_train` / `do_practice` commands at trainer NPCs | **Implemented** | Stat cap in `TRAIN_STAT_CAP` (config.py, revisit for races); `train hp`/`mana` each +10; `do_train` no-arg shows picker [PRIMESUD] |
| Stats display | `[perm/curr]` where curr includes active affects | `[val/val]` (identical until affect system added) | Slot is future-proofed in `do_score` — expand when affects are implemented |
| Score layout | 75-col three-column box | **64-col two-column box** | HP Prime font gives 64 columns; two-column fits all relevant fields |

---

## Area file system

See **[AREA_FILES.md](AREA_FILES.md)** for the full format reference — module layout,
section order, field schemas for rooms/mobs/items/resets, and conventions.

Key design decisions summarised here for completeness:

- Areas are Python modules (`area_<name>.py`) rather than parsed `.are` text files —
  runtime text parsing would be memory-intensive and slow on the HP Prime.
- Mob reset limits (`global_limit`, `room_limit`) are dropped: each `RESETS` entry owns
  exactly one fixed slot; `revive_dead_mobs()` enforces this implicitly.
- `#SPECIALS` adapted: `"special"` string key in `MOBILES`, resolved to a Python
  function at load time in `world.py`.
- `#SHOPS` is deferred until economy is implemented.
- `P` resets (container contents) and `R` resets (randomize exits) are stored as
  deferred tuples in `RESETS`; no runtime handler yet.
- `E`/`G` resets (mob equipment/inventory) and `F`/`D` resets (door state) are
  fully implemented.
- `#MOBPROGS / #OBJPROGS / #ROOMPROGS` skipped — full scripting VM, no equivalent
  planned.
- `SKILL_TABLE` and `SKILLS` stay in `world.py` — skills are global, not per-area.
- Cross-area VNUMs hardcoded in game logic belong in `world_consts.py`.
- Stat tables (`STR_APP_TOHIT`, etc.) and THAC0 constants are in `config.py` — game
  mechanics, not world data.

---

## Explicitly kept from 1stMud

- `{X` colour-code syntax — identical to 1stMud (see *Colour codes* in CLAUDE.md)
- THAC0 combat curve — formula `thac0_00 + (thac0_32 - thac0_00) * level / 32` from `interpolate()` in `fight.c`; [PRIMESUD] `THAC0_MIN = -2` (classless midpoint; see *Mob THAC0 by act type* above)
- `advance_level` HP/MP formulas: `(CON_APP_HITP[con] + hp_roll) * 9/10`, min 2; two-step HP roll mirrors `get_hp_gain` in `multiclass.c`
- MP formula: `randint(2, (2*INT + WIS) // 5) * 9/10`, min 2
- `WIS_APP_PRACTICE` table for per-level practice gains
- `CON_APP_HITP`, `STR_APP_TOHIT/TODAM`, `DEX_APP_DEF`, `INT_APP_LEARN` stat application tables (indices 0–25; 1stMud goes to 30 but stats are capped at 25)
- Pulse rate: 4 pulses/sec (see *Pulse timing* above for per-pulse adjustments)
- `check_improve` skill improvement mechanic
- AC soft cap: `if victim_ac < -15: victim_ac = (victim_ac + 15) / 5 - 15` (both `one_hit` paths)
- Multi-hit combat structure (`one_hit` → `multi_hit`)
- Flee mechanic (random exit, up to 6 attempts)
- Level-up message style: `"You raise a level!!"` then `"You gain N hit points, N mana, and N practices."`
