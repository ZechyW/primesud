# Character State Management

## Goal

Full-fidelity port of 1stMud's character state management pipeline to PrimeSUD.
Reference: `handler.c`, `update.c`, `skills.c`, `act_info.c`, `act_move.c` in `reference/1stMud4.5.3/src/`.
Intentional deviations are marked `[PRIMESUD]` and documented below.

**Status: complete** — all planned items implemented.

## Design

**[PRIMESUD]** No race/class — single archetype. Stats are trained directly; no
class-based HP/MP roll table.

**[PRIMESUD]** No hunger/thirst/condition, no alignment, no move-points — omitted
as overhead unsuited to a calculator game.

**Affect system** — 1stMud uses a linked list of `AFFECT_DATA` structs. PrimeSUD uses
a nested dict keyed by skill/spell number (`sn`):

    player["affects"] = {
        sn: {"loc": str, "modifier": int, "duration": int}
    }

`loc` choices match 1stMud's `apply_type` enum, restricted to the subset in use:
`"str"`, `"dex"`, `"int"`, `"wis"`, `"con"`, `"hit"`, `"mp"`, `"ac"`, `"hitroll"`, `"damroll"`.

`affect_modify` mutates `hp_max`/`mp_max`/all armor buckets/`hitroll`/`damroll` directly in the char dict
(like 1stMud's `mod_stat` fields for those slots). `str`/`dex`/`int`/`wis`/`con` are never
mutated — `get_curr_stat(char, stat)` folds affect modifiers in on the fly, keeping
permanent stats clean. All combat reads (hitroll/damroll/AC lookups, regen formula,
`check_improve`, `do_score`) go through `get_curr_stat` or the getters.

Duration decay in `tick_update`: decrement if `> 0`, remove at `0` (prints `msg_off` from
`SKILLS` if set). Negative duration = permanent affect (never decremented). No `affect_check`
or bitvectors — not needed for the current loc subset.

`do_train`: 1 train point → permanently +1 stat, cap 25. Requires a mob with
`act_flags["train"]` in the room (cf. `ACT_TRAIN` in 1stMud). No hp/mp training [PRIMESUD].

`do_practice`: 1 practice point → skill % += `INT_learn` (`max(1, int//3)`), cap 75%.
Requires `act_flags["practice"]` mob. Per-skill only (no group system). 75% cap matches
1stMud `skill_adept` for all classes. Skill lookup is by name prefix over `player["learned"]`.

## Implemented

`player.py`: `create_char`, `get_curr_stat`, `affect_modify`, `affect_to_char`,
`affect_remove`, `get_hitroll`, `get_damroll`, `get_AC`, `tick_update` (regen + decay).

`combat.py`: `advance_level` (flat 1000 XP/level; no class HP table), `check_improve`,
`_xp_for_kill`, `raw_kill`.

`commands.py`: `do_score` (affect-adjusted stats), `do_skills`, `do_train`, `do_practice`,
`do_affects`.

## Deferred

| Feature | 1stMud ref | Reason |
|---------|-----------|--------|
| Race/class system | `nanny.c`, `const.c` | [PRIMESUD] single-archetype design |
| Hunger/thirst/condition decay | `gain_condition` in `update.c` | Not wanted for calculator game |
| Alignment | `handler.c`, `act_obj.c` | No items/mobs use it yet |
| Skill group system (`do_gain`, `gn_add`) | `skills.c` | Too complex; per-skill practice is sufficient |
| Stat rolling at character creation | `nanny.c` | Fixed starting stats; name entry already in `primesud.py` |
| Move points / `move_gain` | `update.c` | No movement cost system planned |
| Age tracking | `handler.c` | Cosmetic, no gameplay impact |
| `mobile_update` (wandering, patrol, aggro on enter) | `update.c` | Not yet designed — own phase |
