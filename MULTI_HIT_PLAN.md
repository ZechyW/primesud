# multi_hit unification plan

Mirror 1stMud's combat flow: generic `multi_hit(ch, victim)` dispatches to `mob_hit(ch, victim)` for NPCs; both use the same `one_hit(ch, victim)`.

## Current → target function map

| now | after | change |
|---|---|---|
| `one_hit(tr, player, target_inst, bonus_damroll, slot)` | `one_hit(tr, ch, victim, bonus_damroll, slot)` | merge mob side in |
| `_mob_one_hit(tr, mob_inst, player)` | *(deleted)* | folded into `one_hit` |
| `mob_hit(tr, mob_inst, player, world)` | `mob_hit(tr, ch, victim, world)` | calls unified `one_hit` |
| `multi_hit(tr, player, target_inst)` | `multi_hit(tr, ch, victim, world=None)` | dispatches to `mob_hit` for NPCs |
| `check_parry(tr, player, mob_inst, mob_is_attacker)` | `check_parry(tr, ch, victim)` | `victim` is always parrier |
| `violence_update` | no sig change | call sites updated |

## Patch A — unify `one_hit` + `check_parry`

**`check_parry(tr, ch, victim)`**
- `victim` is always the parrying side; drop `mob_is_attacker` param
- Internal logic: player parries if `not victim["is_npc"]`, mob parries if `victim["is_npc"]`

**`one_hit(tr, ch, victim, bonus_damroll=0, slot="wield")`**
- `ch` = attacker (player or mob), `victim` = defender
- Rename `slot` default from `"weapon"` → `"wield"` (matches equip dict key; fixes inconsistency)
- THAC0/skill/AC/damage math is identical for both sides
- Message direction: `ch["is_npc"]` → `{R mob's noun verbs you` / else → `{G Your noun verbs mob`
- `check_parry(tr, ch, victim)` replaces both existing call sites
- Delete `_mob_one_hit`

## Patch B — unify `multi_hit` / `mob_hit`

**`mob_hit(tr, ch, victim, world)`** (renamed args only, keep NPC-specific logic)
- Replace `_mob_one_hit(tr, ch, player)` calls → `one_hit(tr, ch, victim)`
- NPC extras stay: area-attack off-flag, OFF_FAST haste, second/third attack chance

**`multi_hit(tr, ch, victim, world=None)`**
- If `ch["is_npc"]`: `mob_hit(tr, ch, victim, world); return False`
- Else: existing player sequence, each `one_hit` call uses unified sig
- Returns `True` if victim killed (player side only; mob death detected via `victim["hp"] == 0`)

**`violence_update`** call-site updates:
```python
# player's round
multi_hit(tr, player, target, world)
# each mob's round
multi_hit(tr, mob_inst, player, world)
```
Player death check (`player["hp"] == 0`) stays in `violence_update`.

## Out of scope

- `do_kick` — doesn't route through `one_hit`; no changes needed
- `_try_special_move` — player-only; no changes needed
- Future: mob-vs-mob combat requires `violence_update` to iterate fight pairs, not just mob→player; defer
