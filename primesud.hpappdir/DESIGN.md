# PrimeSud — Design Decisions

General mechanics and gameplay feel are inspired by, and sometimes ported directly from, 1stmud (`reference/1stMud4.5.3`).
This doc lists intentional deviations from 1stMud and design choices made for PrimeSud.
Reference this before porting a new mechanic to avoid re-litigating settled decisions.

---

## Not ported

| Feature | Decision | Reason |
|---|---|---|
| Move / MV | **Not ported** | No gameplay value in a single-player calculator game; MV drain/regen omitted entirely |
| Race system | **Deferred** | All characters use human baseline stats (13 flat, max 18). Add when content justifies it |
| Class system | **Deferred** | Classless for now; THAC0 curve uses a balanced midpoint. Add when skill trees justify it |
| Stat rolling | **Deferred** | Fixed 13 across the board; no chargen reroll screen |
| AC types (Pierce/Bash/Slash/Exotic) | **Not ported** | Single AC value; expand only if weapon damage types are added |
| Saving throws | **Not ported** | Not implemented; add alongside spell effects if/when needed |
| Alignment / deity | **Not ported** | Multiplayer/world-state concepts with no single-player hook |
| Clan / rank / trivia | **Not ported** | Multiplayer concepts |
| Hunger / thirst | **Not ported** | No meaningful single-player gameplay hook |
| Age / hours played | **Not ported** | No persistent wall-clock; calculator has no reliable RTC |
| Gold / silver | **Not yet** | Planned; placeholder slot exists in `do_score` right-column bottom |
| Explore tracking | **Not yet** | Planned; placeholder exists in `do_score` footer area |
| Pkills / pdeaths | **Not ported** | Single-player |
| Stance system | **Not ported** | 1stMud-specific combat extension; out of scope |

---

## Simplified or adjusted

| Feature | 1stMud | PrimeSud | Reason |
|---|---|---|---|
| EXP per level | `exp_per_level(ch, points)` — scales with creation points and race/class mult | Flat **1000 XP / level** | Equivalent to 1stMud formula at 40 creation points, human race (100% mult) |
| Class HP die | Per-class `hp_min`/`hp_max` (Warrior 11–15, Mage 6–8, …) | **7–10** (Cleric/Paladin midpoint) | Classless placeholder; change when classes are added |
| Trainer mechanic | `do_train` / `do_practice` commands at trainer NPCs | **Tracked but unimplemented** | `practice` and `train` fields accumulate each level; no spend mechanic yet |
| Stats display | `[perm/curr]` where curr includes active affects | `[val/val]` (identical until affect system added) | Slot is future-proofed in `do_score` — expand when affects are implemented |
| Score layout | 75-col three-column box | **64-col two-column box** | HP Prime font gives 64 columns; two-column fits all relevant fields |

---

## Explicitly kept from 1stMud

- THAC0 combat curve (`THAC0_00 = 20`, `THAC0_32 = -2`, classless midpoint)
- `advance_level` HP/MP formulas: `(CON_APP_HITP[con] + hp_roll) * 9/10`, min 2
- MP formula: `randint(2, (2*INT + WIS) // 5) * 9/10`, min 2
- `WIS_APP_PRACTICE` table for per-level practice gains
- `CON_APP_HITP`, `STR_APP_TOHIT/TODAM`, `DEX_APP_DEF` stat application tables
- Pulse timing system (4 pulses/sec, PULSE_VIOLENCE = 3s, PULSE_TICK = 30s)
- `check_improve` skill improvement mechanic
- Multi-hit combat structure (`one_hit` → `multi_hit`)
- Flee mechanic (random exit, up to 6 attempts)
- Level-up message style: `"You raise a level!!"` then `"You gain N hit points, N mana, and N practices."`
