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
- `mob.py`: mob creation, mob resets, area state creation, full area reset,
  mobile/area update.
- `inventory.py`: get/drop/inventory/wear/remove/equipment/second/quaff/outfit.
- `movement.py`: exit helper, move/open/close/recall/flee.
- `magic.py`: cast command and current spell effect helpers.
- `training.py`: train/practice and practice cap.
- `info.py`: look/score/skills/help/affects/credits/map/autolist/automap.
- `macros.py`: macro substitution table, macro rendering, macro command.
- `game_state.py`: new/load/save game lifecycle and save-format migration UX.
- `system_cmds.py`: save/quit commands.
- `terminal.py`: PrimeSUD colour-code print/status wrapping and font recolour
  cache around the stable `tml.py` terminal.
- `prime_platform.py`: HP Prime `Ticks`, `WAIT`, settings, `HVars`, and direct
  graphic primitive ownership for game code.
- `save_probe.py`: dormant save-format replay/debug probe.
- `player.py`: player creation, tick regen, prompt, save/load. Compatibility
  re-exports have been removed.
- `commands.py`: position gates, direction dispatch, command table, `interpret`.
- `primesud.py`: owns `Game`, top-level terminal construction, and input loop.
  It no longer imports `hpprime` directly.

Current validation status:

- CPython ASCII and compile checks pass.
- Fake HP Prime import smoke checks passed during the split.
- Emulator smoke passed after the main/platform/terminal/game-state splits.
- Post-refactor discrepancy audit against checkpoint
  `f8e52e72057c70031629db8b875217b9fa11c989` found command/user-facing
  message text preserved. The only intentional runtime/output change noted was
  disabling the old startup save-format probe and moving it to dormant
  `save_probe.py`.
- Final local checks after the skill-list SSOT cleanup:
  `python tools/check_ascii_py.py` passes, and `ast.parse` passes for
  `info.py`, `training.py`, and `commands.py`.
- Hardware validation is still required before packaging/release.

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
Skill-list rendering has a single source of truth in `info.print_skills`;
`do_skills` and `training.do_practice` both call that helper.

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

Status: done. Save/quit handlers moved to `system_cmds.py`.

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
- `prime_platform.py` also owns HP Prime graphic primitive imports used by
  higher-level modules, plus graphic buffer cleanup.
- `player.py` save/load now uses `prime_platform.hvars_get/hvars_set`.
- `terminal.py` owns colour-aware print/status wrapping and the font recolour
  cache; `tml.py` remains untouched.
- `game_state.py` owns new/load/save lifecycle and save-format migration UX.
- Main still owns `Game`, top-level terminal construction, and input loop. The
  dormant save-format replay helper lives in `save_probe.py`.
- Leave `util.py` alone unless a broader platform cleanup is needed.

Next:

1. Run a broader hardware or long emulator play session before declaring Phase 8
   fully done.
2. Rebuild/package `.hpapp` separately when requested.
3. Keep reference runtime files and `.hpapp` binary out of refactor commits
   unless doing an explicit packaging or reference-state capture commit.

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
