# PrimeSUD Refactor Plan

## Goal

Organize the code by conceptual ownership instead of mirroring 1stMud's broad
source files. Keep modules flat for HP Prime compatibility and memory limits.
Avoid class-heavy rewrites; preserve dict-based state.

## Import Direction

Target dependency flow:

```text
config / colors / platform / terminal
        -> world / area data / skills_table
        -> actor / player / mob / item
        -> combat / inventory / magic / movement / training
        -> info / macros / commands
        -> primesud
```

Rules:

- Lower layers do not import `commands` or `primesud`.
- `world.py` stays loader/catalog, not gameplay behavior.
- `area_*.py` stays generated data only.
- `tml.py` stays stable/vendor; game logic does not enter it.
- New imports should point to owning modules, not compatibility re-exports.

## Current State

Completed cuts:

- `actor.py`: shared stat, affect, name-match, hit/dam/AC, equip helpers.
- `item.py`: object creation, item flags, item lookup, room mob lookup.
- `mob.py`: mob creation, mob resets, full area reset, mobile update.
- `inventory.py`: get/drop/inventory/wear/remove/equipment/second/quaff/outfit.
- `movement.py`: exit helper, move/open/close/recall/flee.
- `magic.py`: cast command and current spell effect helpers.
- `training.py`: train/practice and practice cap.
- `info.py`: look/score/skills/help/affects/credits/map/autolist/automap.
- `macros.py`: macro substitution table, macro rendering, macro command.
- `prime_platform.py`: HP Prime `Ticks`, `WAIT`, settings, and `HVars` wrappers.
- `player.py`: player creation, tick regen, prompt, save/load. Compatibility
  re-exports have been removed.
- `commands.py`: position gates, direction dispatch, command table, `interpret`,
  plus save/quit glue only.

Current validation status:

- CPython ASCII and compile checks pass.
- Fake HP Prime import smoke checks passed during the split.
- Emulator/hardware validation is still required before packaging.

## Phase 1: Stabilize Current Split

Done.

Notes:

- `do_outfit` remains in `inventory.py` unless character creation grows enough
  to justify a separate `chargen.py`.

## Phase 2: Split Movement

Create `movement.py`:

- `_exit_to`
- `do_move`
- `do_open`
- `do_close`
- `do_recall`
- `do_flee`

Keep recall here because it changes rooms and exits combat as movement logic.
`commands.py` imports these handlers.

Risks:

- `do_recall` calls `stop_fighting`, `WaitState`, `check_improve`.
- Avoid circular imports by importing from `combat`, not from `commands`.
- `do_flee` also stops combat and shows the destination room; keeping it here
  avoids a `combat.py` -> `movement.py` -> `combat.py` cycle.

Status: done.

## Phase 3: Split Magic

Create `magic.py`:

- `do_cast`
- spell effect helpers
- later: potion/scroll/wand effect dispatch if `do_quaff` outgrows inventory

Short-term `do_quaff` may stay in `inventory.py` because it consumes carried
objects. Move only effect resolution when effects become broader than HP gain.

Status: done.

## Phase 4: Split Training And Skills

Create `training.py`:

- `do_train`
- `do_practice`
- practice cap/constants

Keep `check_improve` in `combat.py` for now only because combat uses it heavily.
Later move `check_improve` to `skills.py` if both combat and training depend on
it equally.

Status: done.

## Phase 5: Split Info/UI Commands

Create `info.py`:

- `_wrap`, `_wrap_paragraphs`
- `do_look`, `_look_item`
- `do_score`
- `do_skills`
- `do_help`
- `do_affects`
- `do_credits`
- `do_map`, `do_automap`, `do_autolist`

Consider `look.py` only if room rendering becomes complex. Keep automap renderer
in `automap.py`; `info.py` should call it only.

Status: done. The temporary `world["look_fn"]` callback used by movement during
the split has been removed; `movement.py` imports `do_look` from `info.py`.

## Phase 6: Split Macros

Create `macros.py`:

- `_MACRO_SUBST`
- macro table rendering helpers
- `do_macro`

`primesud.py` imports `_MACRO_SUBST` from `macros.py` for input substitution and
save/load attachment.

Status: done.

## Phase 7: Thin Commands

After Phases 2-6, `commands.py` should contain only:

- position gates
- direction aliases dispatch
- command table
- `interpret`

No command body should live there unless it is purely dispatcher glue.

Status: done. Remaining local handlers are `do_save` and `do_quit`.

## Phase 8: Thin Main And Platform

Create `prime_platform.py` only after command/system splits are stable
(`platform.py` collides with CPython's stdlib during smoke tests):

- HP Prime `ppleval` wrappers
- save variable helpers if useful
- memory/GC helpers currently in `util.py`, if naming improves clarity

Create `terminal.py` only if color-print wrapping grows beyond `Game.__init__`.
Do not disturb `tml.py` public API.

Status: partial.

- `prime_platform.py` owns `Ticks`, `WAIT`, settings save/restore, and `HVars`
  get/set wrappers.
- `player.py` save/load now uses `prime_platform.hvars_get/hvars_set`.
- Main still owns `Game`, terminal setup, graphic buffer cleanup, input loop,
  save format migration UX, and the save-format probe.
- Leave `util.py` alone unless a broader platform cleanup is needed.

Next:

1. Run in HP Prime emulator and confirm startup, movement, look, inventory,
   combat, recall/flee, save/load, macros, and score.
2. If emulator passes, rebuild/package `.hpapp` separately.
3. Consider a small `system_cmds.py` only if `do_save`/`do_quit` should leave
   `commands.py`; current dispatcher glue is acceptable.

## Validation Checklist

After each cut:

```powershell
python tools/check_ascii_py.py
python -B -m py_compile primesud.hpappdir\<changed>.py
```

Also run a fake HP Prime import smoke test from CPython when imports change.
Run emulator before calling a phase done.

## Commit Discipline

- One conceptual split per commit.
- Do not mix generated `area_*.py` changes with refactor commits.
- Do not stage `.hpapp` or reference runtime files unless the task is packaging
  or reference-state capture.
- Leave unrelated dirty files untouched.
