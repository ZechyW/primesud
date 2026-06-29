# Code Reorganization Plan

## Current state

32 non-area modules, no circular imports. Most modules have clean single
responsibilities. 1stMud's `act_info.c` / `fight.c` / `handler.c` split is
roughly mirrored. Three concrete misplacements to fix, one structural
improvement, one optional rename.

## Tier 1: Fix misplacements

### A. `get_char_room()`: `item.py` -> `actor.py`

Finds mob by name-prefix in room's instance list. Nothing to do with items.
In 1stMud this lives in `handler.c` alongside `get_char_world()`,
`get_mob_vnum()`, etc. -- exactly what our `actor.py` does.

Importers that change source: `info.py`, `magic.py`, `combat.py`, `comm.py`.

### B. `save_world()` / `load_world()` / `_serialize_world()`: `player.py` -> `game_state.py`

These serialize the entire world (rooms, mobs, items, player, areas) -- not
just player. `game_state.py` already owns game lifecycle (`new_game`,
`load_game`, `save_game`) and currently imports these from `player.py`.
Consolidating eliminates split responsibility.

Importers that change source: `combat.py`, `system_cmds.py`, `game_state.py`
(last one simplifies).

### C. `mob_condition()`: `combat.py` -> `actor.py`

Pure display function -- returns description string like "is in excellent
condition." Not combat engine logic. Used by `info.py` (look/score) and
`primesud.py` (target status in game loop). Belongs with other character-query
functions in `actor.py`.

Importers that change source: `info.py`, `primesud.py`.

## Tier 2: Structural improvement

### D. Extract skill-timing utilities from `combat.py` -> `skill_utils.py`

Functions: `get_skill()`, `check_improve()`, `WaitState()`, `DazeState()`,
`_int_learn()`.

Used by 5 modules (movement, inventory, magic, shop + combat itself).
Skill-system plumbing, not fight engine. Moving to `skill_utils.py`:
- Reduces `combat.py`'s role as dependency hub
- Gives `skill_utils.py` complete "skill runtime" identity (currently only
  query/lookup helpers)

New deps added to `skill_utils.py`: `world`, `terminal`. Both already loaded
by every consumer -- no new modules loaded overall.

## Tier 3: Optional cosmetic

### E. Rename `actor.py` -> `handler.py`

Matches 1stMud's `handler.c` -- module that manages character state, affects,
equipment, finding, visibility. "Actor" is vague; "handler" signals role as
core object-manipulation layer.

14 files change import lines. Worth it if doing Tier 1 moves anyway (touching
many of same files). Skip if doing Tier 1 alone.

## Leave alone

| Module | Reason |
|--------|--------|
| `info.py` (25 fn) | Matches 1stMud `act_info.c`. "Information commands" valid grouping. Splitting adds files + HP Prime memory overhead. |
| `combat.py` (50+ fn) | Large but cohesive. Commands and engine tightly coupled. Matches `fight.c`. |
| `magic.py` (100+ fn) | Casting engine + spells = one unit. Matches `magic.c` + `magic2.c`. |
| `game_time.py` (1 fn) | Tiny but 3 independent consumers. Clean boundary. |
| `scan.py` (3 fn) | Clean self-contained scan command. |
| All other small modules | Already well-scoped. |

## Dependency layers (after Tier 1+2)

```
Layer 0 -- No project deps:
  config  colors  races  skills_table  util  prime_platform  game_time

Layer 1 -- Platform/terminal:
  tml -> tml_prime -> terminal
  picker -> terminal
  automap -> config

Layer 2 -- World data:
  world -> area_*

Layer 3 -- Core object manipulation:
  actor       -> colors, config, terminal, world
  item        -> world, actor
  skill_utils -> skills_table, config, world, terminal

Layer 4 -- Game systems:
  combat   -> actor, item, player, skill_utils, ...
  magic    -> actor, item, combat, movement, skill_utils, ...
  mob      -> actor, item, world, special
  movement -> actor, combat, info, skill_utils, ...

Layer 5 -- Command handlers:
  info  inventory  comm  scan  shop  training  macros  system_cmds

Layer 6 -- Lifecycle:
  player  game_state  update

Layer 7 -- Entry:
  commands -> all command modules
  primesud -> commands, game_state, ...
```

Cross-layer dep: `movement` (L4) -> `info.do_look` (L5). "Show room after
moving" -- same pattern as 1stMud `act_move.c`. Pragmatic, not worth breaking.

## Impact summary

| Change | Files touched | Impact |
|--------|:---:|--------|
| A. Move `get_char_room` | ~5 | Fix semantic misplacement |
| B. Move `save/load_world` | ~4 | Consolidate save/load lifecycle |
| C. Move `mob_condition` | ~3 | Fix semantic misplacement |
| D. Extract skill utilities | ~6 | Reduce combat.py as dep hub |
| E. Rename actor->handler | ~15 | Cosmetic, matches 1stMud |
