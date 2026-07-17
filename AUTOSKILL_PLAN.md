# AUTOSKILL_PLAN.md -- `autoskill` automated combat actions [PRIMESUD]

Status: reviewed in discussion 17/07/2026; approved for build pending final
sign-off. Delete this file after shipping (harvest decisions into DESIGN.md /
FEATURES.md first, per CLAUDE.md).

## What

New player auto-setting: while fighting, the game fires one appropriate
skill or spell per combat round on the player's behalf -- offensive skills,
in-combat buffs, debuffs, offensive spells -- so a calculator player uses
their full kit without retyping commands every round.

No 1stMud equivalent -- pure [PRIMESUD] feature. Complements `autostance`
(defensive posture automation, see stances.py `autodrop`) and `wimpy`
(auto-flee). Deliberately does NOT automate survival: no auto-heal, no
auto-quaff, no flee logic.

## Settled design decisions (from review, 17/07/2026)

1. **Name: `autoskill`.** Covers spells too; no command-table prefix
   conflict with `autosac`/`autosplit`/`autostance`.
2. **No auto-heal in v1.** Cure/heal spells are `min_pos=fighting` so it is
   technically possible, but auto-heal plus PrimeSUD's lenient death penalty
   would make the player effectively unkillable while mana lasts. Survival
   decisions (heal, quaff, flee) stay manual; `wimpy` remains the safety
   net. Possible later opt-in subtoggle.
3. **Buff tier is haste + berserk only.** Verified against
   `skills_table.py`: nearly all classic buffs (sanctuary, frenzy, giant
   strength, shield, armor, stone skin, bark skin, bless, the three
   *shield spells) are `min_pos=standing`, and `POS_ORDER` places fighting
   below standing, so `do_cast` faithfully refuses them mid-combat. Only
   `haste` (spell, pos=fighting) and `berserk` (skill, pos=fighting) are
   castable while fighting. Pre-combat auto-buffing = separate future
   feature (different trigger point), out of scope.
4. **Proficiency floor: `learned >= 75`** (named constant) for auto-picked
   spells and debuffs. Fizzle costs half mana plus a full round of lag, so
   low-practiced powerful spells are strictly worse than well-practiced
   weak ones. Training low spells stays a manual activity. Floor does not
   apply to the physical skill rotation (no mana at stake; failures still
   run check_improve).
5. **Full normal cost -- no power multiplier.** Auto actions go through the
   existing `do_*` handlers, so mana, `WaitState` lag, fizzle,
   `check_improve`, messages, and retaliation all run unchanged. The engine
   only acts when `player["wait"] == 0`, so it self-throttles to the same
   cadence a fast typist could achieve.

## Engine policy (one action per eligible round, first match wins)

1. **haste** -- known, `learned >= FLOOR`, not `is_affected`, mana after
   cast >= 50% max.
   **berserk** -- known, not already berserk/frenzy/calm, mana >= 50 plus
   50%-max guard (handler re-checks its own 50-mana cost).
2. **Debuffs, once each** -- `blindness`, `weaken`, `curse`: known,
   `learned >= FLOOR`, victim not already `is_affected` by that sn.
3. **Offensive spell** -- highest class-level known spell with
   `target in (char_offensive, obj_char_offensive)`, `learned >= FLOOR`,
   and post-cast mana >= 25% max (reserve so the player can still choose to
   heal manually).
4. **Skill rotation** -- first eligible of `bash`, `trip`, `dirt kicking`,
   `disarm`, `kick`: `get_skill > 0` plus cheap pre-filters (victim
   position for bash/trip, victim wields weapon for disarm, victim not
   blind for dirt). Free actions, so they are the low-mana fallback.
5. Nothing eligible -> plain combat round, no action.

Thresholds as named constants in autoskill.py:
`_LEARNED_FLOOR = 75`, `_BUFF_MANA_PCT = 50`, `_OFFENSE_RESERVE_PCT = 25`.

## Architecture

- **New module `src/autoskill.py`** [PRIMESUD], single public entry
  `auto_skill_round(player)`. ~150 lines.
- **Hook**: in `violence_update` (combat.py:87-133) player branch, right
  after the player's `multi_hit` -- mirrors where ROM mobs fire their
  `off_flags` specials. One call, guarded by the flag bit.
- **Gates before acting** (all cheap, checked in order):
  - `PLR_AUTOSKILL` bit set in `player["flags"]`
  - `player["wait"] == 0` (lagged rounds skip, exactly like the mob guard
    at combat.py:1914)
  - no `_pending_cmd` queued in primesud.py (manual input always wins;
    needs a small accessor or module flag exposed from primesud.py --
    resolve at build time, keep the coupling one-way)
  - `player["position"] == fighting` and `player["fighting"]` set
  - not an NPC (engine is player-only; pets/charmies excluded)
- **Action dispatch calls existing handlers**: `do_cast(player, [name])` /
  `do_cast(player, [name, target])`, `do_bash(player, [])`, etc. Zero
  duplicated combat logic. The engine pre-filters so it never calls a
  handler that would just print a failure message every round.
- **Candidate scan**: per-round walk of `player["learned"]` intersected
  with `SPELL_FUNS` / target-type classification from `SKILLS[sn]`.
  Learned dicts are small (tens of entries); no caching in v1. If device
  profiling shows cost, cache candidate lists keyed on a learned-dict
  revision counter -- not before.

## Setting storage

- New bit `PLR_AUTOSKILL = 2` (currently free) in handler.py PLR_* block.
- NOT in `PLR_DEFAULTS` -- off by default, opt-in.
- Toggle command `do_autoskill` in info.py following the do_autoX pattern
  (`player["flags"] ^= PLR_AUTOSKILL` + on/off message).
- Row in `_FLAG_TABLE` for `autolist` output.
- Persists free via existing `p.flags` save line (game_state.py:76/312) --
  no save-format change.

## Implementation steps

1. `handler.py`: add `PLR_AUTOSKILL = 2` constant.
2. `src/autoskill.py`: engine module (policy above). Docstrings mark
   [PRIMESUD] throughout; Google style per CLAUDE.md.
3. `combat.py`: one guarded call in `violence_update` player branch.
   NOTE: check `violence_update` docstring for `[Verified:]` tag first --
   if tagged, this is a [PRIMESUD]-marked insertion resolving no TODO, so
   ask before editing per CLAUDE.md verified-port rule.
4. `info.py`: `do_autoskill` toggle + `_FLAG_TABLE` row; `commands.py`
   `_CMD_TABLE` entry (position: alphabetical with other auto* commands).
5. Tests `tests/test_autoskill.py`:
   - flag toggle + autolist row + persistence round-trip (`p.flags`)
   - fires nothing when flag off / wait > 0 / not fighting / NPC
   - haste cast once, skipped when affected / mana below 50%
   - debuff fired once, skipped when victim affected
   - offensive spell respects learned floor and 25% reserve
   - skill rotation order and pre-filters (bash position gate, disarm
     weapon gate)
   - lag: engine action sets wait; next round skipped
   - manual `_pending_cmd` suppresses auto action
6. Docs, same commit: FEATURES.md one-liner; DESIGN.md row (decisions 2-5
   above -- the why); docs/PRIME_UX.md section if it fits the existing UX
   doc structure. ASCII check + full pytest.

## Non-goals / future extensions (do not build now)

- Pre-combat auto-buffing (standing-position buffs) -- different trigger.
- Auto-heal subtoggle.
- Per-category subtoggles or picker-based policy config.
- Custom rotation ordering.

## On-device validation (add to TODO.md platform checklist when shipping)

- Idle-fight CPU: `gc.mem_free` / responsiveness with autoskill on during a
  long fight in a mobprog-heavy room (engine scan is per violence pulse).
- Message volume on the 64-col screen: one auto action per ~2s round plus
  combat spam -- confirm readable, adjust if drowning combat prompts.
