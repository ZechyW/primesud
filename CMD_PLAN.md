# Command Handling System Plan

## Goal

Port 1stMud's command dispatch infrastructure to PrimeSUD, then extend the
command set incrementally on top of it.  Reference: `interp.c`, `act_info.c`,
`act_obj.c`, `act_move.c`, `act_comm.c`, `fight.c` in `reference/1stMud4.5.3/src/`.
Intentional deviations are marked `[PRIMESUD]` and documented below.

**Status: in progress.**

---

## Design

### Dispatch model

1stMud stores commands in a hash table keyed by `tolower(name[0]) % 126` and
walks each bucket in **load order** (the order entries appear in `commands.dat`),
taking the first entry that prefix-matches the typed verb and passes the level
check.  The `noprefix` flag forces exact-match for that entry.

PrimeSUD replaces the hash table with a flat list — same asymptotic cost for our
command count — but preserves the **load-order prefix-match** semantics exactly.
Because 1stMud's hash bucket for letter X is a contiguous subsequence of the
global load order, adopting the full `commands.dat` sequence as the order of
`_CMD_TABLE` gives correct intra-letter (prefix-collision) behaviour for free,
with no need to reason about buckets separately.

`interpret()` scans `_CMD_TABLE` top-to-bottom and takes the first entry where:
- `noprefix=False` and `name.startswith(verb)`, or
- `noprefix=True` and `name == verb`.

**[PRIMESUD]** No level check — all mortal commands accessible at level 0;
immortal commands omitted entirely.

**[PRIMESUD]** `no_order` flag — in 1stMud this prevents a command from being
issued via `order <mob> <cmd>` (so charmed mobs can't be told to `quit`,
`shutdown`, etc.).  PrimeSUD has no `order` command and no charmed-follower
mechanic, so `no_order` is irrelevant and ignored.

**[PRIMESUD]** `noalias` flag — no alias system (the macro system replaces it).
Ignored.

**[PRIMESUD]** Log flag (`never`/`normal`/`always`) — no admin logging
infrastructure.  Ignored.

### Table schema

Current: `(name, fn)`
Target:  `(name, fn, min_pos, noprefix)`

```python
# Example entries in 1stMud load order
("cast",     do_cast,     "fighting", False),
("get",      do_get,      "resting",  False),
("kill",     do_kill,     "fighting", False),
("look",     do_look,     "resting",  False),
("practice", do_practice, "sleeping", False),
("quit",     do_quit,     "dead",     True),   # noprefix
```

### Position system

`player["pos"]` holds a string from the ordered set below.
Default at `create_char`: `"standing"`.

```python
_POS_ORDER = {
    "dead": 0, "sleeping": 4, "resting": 5,
    "sitting": 6, "fighting": 7, "standing": 8,
}
```

Values match 1stMud's `position_t` enum directly (gaps 1–3 are `mortal`,
`incap`, `stunned`).  PrimeSUD omits those three — no command uses them as
`min_pos`, and the HP-damage states they represent are not yet designed.
Adding them later requires only inserting new keys; no existing values change.

`interpret()` rejects a command when
`_POS_ORDER[player["pos"]] < _POS_ORDER[cmd_min_pos]`
and prints the standard 1stMud position messages (cf. `interp.c`):

| Player position | Message |
|-----------------|---------|
| `dead` | Lie still; you are DEAD. |
| `sleeping` | In your dreams, or what? |
| `resting` | Nah... You feel too relaxed... |
| `sitting` | Better stand up first. |
| `fighting` | No way!  You are still fighting! |

Practical consequence of `fighting (7) < standing (8)` in 1stMud's enum:
commands with `min_pos = "fighting"` (e.g. `kill`, `cast`, `kick`, `flee`) are
usable both mid-combat and while standing.  Commands with `min_pos = "standing"`
(movement directions, `sneak`, `hide`) are blocked while fighting — that is what
triggers "No way!  You are still fighting!"

`combat.py`: `set_fighting()` sets `player["pos"] = "fighting"`;
`stop_fighting()` resets to `"standing"`.

Regen scaling by position will be added to `tick_update` (`player.py`) when
`do_rest`/`do_sleep` are implemented in Phase 1.

### Interpreter flow (target)

1. Strip + split raw input.
2. Macro substitution: if verb is a digit key in `_MACRO_SUBST`, replace the
   raw input and re-split.  (Currently applied upstream before `interpret()`;
   moving it here means all input paths go through one substitution point.)
3. Direction shorthand via `_DIRECTION_MAP` (unchanged).
4. Scan `_CMD_TABLE` in load order:
   a. Skip if `noprefix=True` and `verb != name`.
   b. Skip if `noprefix=False` and `not name.startswith(verb)`.
   c. On first match: check position — if blocked, print message and return.
   d. Dispatch `fn(tr, player, args, room_state, mob_instances)` and return.
5. No match → `"Unknown command. ? for help."`

`prefix_lookup()` becomes unused and is removed.

---

## Phase 0 — Infrastructure (no new commands)

Changes only to dispatch machinery; no observable behaviour change for any
existing command except that position messages become possible.

1. Add `_POS_ORDER` and position-message table to `commands.py`.
2. Change `_CMD_TABLE` tuples to `(name, fn, min_pos, noprefix)`.
3. Reorder `_CMD_TABLE` entries to match COMMANDS.md load order.
4. Update `interpret()` with the new dispatch flow above; remove `prefix_lookup`.
5. Add `player["pos"] = "standing"` to `create_char` in `player.py`.
6. Update `set_fighting()` / `stop_fighting()` in `combat.py` to set/clear pos.

## Phase 1 — Position commands and room information

| # | Command | do_fun | min_pos | noprefix | 1stMud ref |
|---|---------|--------|---------|----------|-----------|
| 12 | `exits` | `do_exits` | resting | no | `act_info.c` |
| 20 | (extend `look`) | — | — | — | add `look` at direction |
| 25 | `rest` | `do_rest` | sleeping | no | `act_move.c` |
| 26 | `sit` | `do_sit` | sleeping | no | `act_move.c` |
| 28 | `stand` | `do_stand` | sleeping | no | `act_move.c` |
| 38 | `compare` | `do_compare` | resting | no | `act_info.c` |
| 39 | `consider` | `do_consider` | resting | no | `act_info.c` |
| 43 | `examine` | `do_examine` | resting | no | `act_info.c` |
| 86 | `wimpy` | `do_wimpy` | dead | no | `act_comm.c` |
| 163 | `recall` | `do_recall` | fighting | no | `act_move.c` |
| 167 | `sleep` | `do_sleep` | sleeping | no | `act_move.c` |
| 173 | `visible` | `do_visible` | sleeping | no | `act_move.c` |
| 174 | `wake` | `do_wake` | sleeping | no | `act_move.c` |
| 174 | `where` | `do_where` | resting | no | `act_info.c` |

Also: scale regen in `tick_update` by position (sleeping > resting > sitting > standing).

## Phase 2 — Extended object interaction

| # | Command | do_fun | min_pos | Notes |
|---|---------|--------|---------|-------|
| 112 | `brandish` | `do_brandish` | resting | Use a staff |
| 113 | `close` | `do_close` | resting | Doors and containers |
| 115 | (extend `drop`) | — | — | Drop into container |
| 119 | `give` | `do_give` | resting | Give item to mob |
| 122 | `list` | `do_list` | resting | Shop inventory |
| 123 | `lock` | `do_lock` | resting | Requires key in inv |
| 124 | `open` | `do_open` | resting | Doors and containers |
| 127 | `put` | `do_put` | resting | Into container |
| 129 | (extend `quaff`) | — | — | Use scroll (`recite`) |
| 130 | `recite` | `do_recite` | resting | Use scroll |
| 131 | (extend `remove`) | — | — | Already done |
| 133 | (extend `get`) | — | — | Two-arg: get from container |
| 134 | `sacrifice`/`junk` | `do_sacrifice` | resting | Destroy for small gold |
| 137 | `value` | `do_value` | resting | Ask shop price |
| 139 | `zap` | `do_zap` | resting | Use wand |
| 31 | `unlock` | `do_unlock` | resting | Requires key |

Door state stored in `room_state[rid]["doors"][direction]`; container state as
mutable overlay on the item template (design TBD).

## Phase 3 — Shop system

Depends on Phase 2.  Requires `act_flags["shop"]` on mob templates and a
`"shop"` dict `{"buy_types": [...], "profit_buy": float, "profit_sell": float}`.
Shop stock is the mob's carried item list; `player["gold"]` tracks currency.

| # | Command | do_fun | Notes |
|---|---------|--------|-------|
| 10 | `buy` | `do_buy` | Transfer item from shop mob to player |
| 132 | `sell` | `do_sell` | Transfer item from player to shop mob |

## Phase 4 — Combat extensions

| # | Command | do_fun | min_pos | Notes |
|---|---------|--------|---------|-------|
| 141 | `backstab`/`bs` | `do_backstab` | fighting | Requires hidden |
| 142 | `bash` | `do_bash` | fighting | Knockdown |
| 144 | `berserk` | `do_berserk` | fighting | Rage: +hit/dam, -AC |
| 145 | `dirt` | `do_dirt` | fighting | Temporary blind |
| 146 | `disarm` | `do_disarm` | fighting | Strip weapon |
| 150 | `rescue` | `do_rescue` | fighting | Draw aggro to self |
| 151 | `surrender` | `do_surrender` | fighting | End combat |
| 152 | `trip` | `do_trip` | fighting | Dex knockdown |
| 153 | `hunt` | `do_hunt` | standing | Track mob |
| 117 | `envenom` | `do_envenom` | resting | Coat weapon |
| 160 | `hide` | `do_hide` | resting | Prereq for backstab |
| 168 | `sneak` | `do_sneak` | standing | Prereq for backstab |
| 305 | `stance` | `do_stance` | standing | Combat stance selection |

---

## Deferred

| Feature | 1stMud ref | Reason |
|---------|-----------|--------|
| Communication channels (tell, say, gossip, shout, …) | `act_comm.c` | [PRIMESUD] single-player; no recipients |
| `alias`/`unalias` | `act_comm.c` | [PRIMESUD] macro system replaces |
| `no_order` flag | `interp.c` | [PRIMESUD] no `order` command |
| Hunger/thirst: `drink`/`eat`/`fill`/`pour` | `act_obj.c` | [PRIMESUD] condition system omitted |
| `follow`/`group`/`order` | `act_move.c` | No NPC followers designed |
| `gain` (skill groups) | `skills.c` | [PRIMESUD] per-skill practice sufficient |
| Clan/quest/auction/bank commands | various | [PRIMESUD] omitted |
| Settings toggles (`brief`, `color`, `compact`, `prompt`, …) | various | Add on demand |
| `steal`, `pick` (lockpick) | `fight.c`, `act_obj.c` | Low priority |
| `run`/`path` | `act_move.c` | Pathfinding not yet designed |
| `play` (bard songs) | `act_move.c` | No bard system designed |
| Immortal commands | `act_wiz.c` | [PRIMESUD] no admin layer |
