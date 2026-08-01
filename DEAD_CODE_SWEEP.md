# Dead / Legacy Code Sweep (interim)

Status: dead/legacy pass CLOSED 01/08. All candidates resolved -- deletes
applied, retains decided (upstream-parity data kept: SECT_*, CON_APP_SHOCK,
race points, TO_SOCIALS, CLASS_PALADIN/RANGER).

Reopened 01/08 for a second, different pass: the **Class C scan** (unnecessary
*guards*, not unreachable code) -- see bottom section. Findings recorded;
no edits applied, awaiting go/no-go plus `[Verified]` permission.

Update 2026-08-01: candidates re-verified against 1stMud 4.5.3 source for
hidden bugs / fidelity gaps. Three items flipped to retain (dead upstream too,
so dormancy is bug-faithful); one item promoted to a fidelity *fix*; remaining
deletes confirmed safe with evidence noted inline.

## Confirmed candidates

### Dormant NPC hunt pipeline -- RETAIN (verified 01/08: dormant upstream too)

- `src/hunt.py:150` says `hunt_victim()` is dormant scaffolding.
- No runtime code assigns a non-`None` `ch["hunting"]`; repository references
  only clear/read it. Tests seed it directly.
- Runtime plumbing remains in `src/combat.py:87,124-130`,
  `src/mob.py:11,671-674`, `src/world.py:1645`, and character defaults.
- `tests/test_hunt.py:172+` tests unreachable seeded state.
- Verdict: retain. Stock 1stMud 4.5.3 never assigns a non-NULL `ch->hunting`
  either -- only NULL clears (`hunt.c:524,555,569`); `do_hunt` (`hunt.c:421`,
  ported at `src/commands.py:260`) only reports a direction and never sets it;
  no mobprog or spec_fun setter exists. Dormancy is bug-faithful, the
  "quirk contradicts nothing" case `CLAUDE.md` says to keep. Deleting would be
  a deviation, not cleanup.

### Obsolete gquest waiting-state conversion -- DONE (deleted 01/08)

- `src/gquest.py:31` declares `GQUEST_WAITING` as unused live state.
- Only runtime use is `src/gquest.py:574-578`, converting old waiting saves.
- Current `src/game_state.py:610-623` rejects every save whose version is not
  exactly `SAVE_VERSION == 10` before `gq_load_line()` runs.
- Join window was removed 2026-07-05; save v10 began 2026-07-22. Therefore no
  accepted legacy save can contain old waiting state through normal code.
- Candidate: delete constant and conversion branch (about 6 production lines).
- Verified 01/08: version gate at `game_state.py:617` confirmed to return
  before any gquest line parses; conversion branch unreachable. Safe.

### Unreferenced helper -- DONE (deleted 01/08)

- `src/item.py:350-354` `item_max_charges()` has no reference outside its own
  definition across `src/`, `tests/`, `tools/`, and shims.
- Current call sites read `max_charges` directly.
- Candidate: delete helper (5 lines plus spacing).
- Verified 01/08: no stale-template bug behind the direct reads --
  `promote_obj` copies `max_charges` onto every instance at creation
  (`item.py:49-51`), and all live readers (`shop.py:121`, `magic.py:2337`
  recharge, `item.py:768`) are already instance-aware. Safe.

### Shopkeeper ID returned but never consumed -- DONE (simplified 01/08)

- `src/shop.py:44-76` `find_keeper()` builds and returns `(keeper, keeper_id)`.
- All five callers unpack `keeper_id` but never use it; no external callers.
- Keeper dict already contains `keeper["id"]`, used by nearby code.
- Candidate: return keeper/`None` only and simplify five callers.
- Verified 01/08: 1stMud `find_keeper` returns `CharData *` only; the tuple is
  a PrimeSUD-ism. Simplifying also restores the upstream signature.

### Dead `stone skin` branch -- RETAIN (verified 01/08: mirrors upstream)

- `src/skills_table.py:1272-1276` fixes `stone skin` target as `char_self`.
- `src/magic.py:2499-2507` explicitly notes `vo is not ch` message branch is
  dead, but still keeps conditional and alternate message.
- Verdict: retain. Upstream `spell_stone_skin` (`magic.c:4170-4196`) carries
  the same `victim == ch` conditional with alternate message, equally dead
  there (self-target spell). Our branch mirrors upstream dead code; function
  is `[Verified]`. Fidelity says keep.

### Always-true room-visibility hook -- RETAIN (confirmed 01/08)

- `src/handler.py:1270-1286` defines `can_see_room()` as an unconditional
  `True`; `DESIGN.md:125` records this as intentional for single-player.
- Nine runtime checks therefore contain dead terms/blocks:
  `path.py:43`, `movement.py:135,303,423,491`, and
  `magic.py:1915,2877,2885` (plus the function definition itself).
- Verdict: retain. Collapsing touches nine call sites, several `[Verified]`,
  for zero behavior change -- churn against a DESIGN.md-documented hook. If
  immortal/clan/access-controlled rooms become real, the shared predicate is
  already in place.

### Unused imports -- DONE (applied 01/08)

Applied via auto-optimiser + manual follow-up (ae8470d). The optimiser also
stripped the transitive re-exports the scan had excluded, so those were
retired for good: PLR_*/COMM_* flags now import from handler.py everywhere
(player.py re-export gone), MAX_REMORT from config (classes.py pass-through
gone). Lesson: re-export patterns don't survive auto-optimisers; import from
the definition site.

AST name-use scan found 22 unused import bindings after excluding intentional
player-flag re-exports:

- `classes.py`: `MAX_REMORT`
- `combat.py`: `MAX_MORTAL_LEVEL`, `get_obj_list`, `obj_vnum`, `RACE_TABLE`
- `effects.py`: `ITEM_DEFS`, `obj_vnum`
- `game_state.py`: `ROOM_DEFS`, `reset_area`
- `info.py`: `ITEM_DEFS`
- `inventory.py`: `set_item_container_flag`
- `item.py`: `MOB_DEFS`, `item_tpl_get`
- `magic.py`: `item_tpl_get`
- `music.py`: `ITEM_DEFS`, `obj_vnum`
- `player.py`: `tprint`, `AREA_DEFS`
- `skill_utils.py`: `MAX_MORTAL_LEVEL`
- `special.py`: `ITEM_DEFS`
- `update.py`: `ITEM_DEFS`, `obj_vnum`

Candidate: delete bindings only. Same modules remain imported through used
names, so no import side effects disappear.

Verified 01/08 that the bug-suspect ones are leftovers, not half-ports:
`combat.py` `RACE_TABLE` (superseded by `race_lookup`, which is used);
`MAX_MORTAL_LEVEL` (upstream fight.c immortal-level checks intentionally
unported -- single-player, no immortals); `get_obj_list`/`obj_vnum` (autoloot
implemented inline using the corpse returned by `raw_kill`,
`combat.py:1453-1469`, a deliberate `[PRIMESUD]` deviation).

### Unused constants -- RESOLVED 01/08 (split)

Deleted: automap `GW`/`GH`/`_CH` (PrimeSUD-local geometry, no upstream
names) and `OBJ_VNUM_DIPLOMA` (no upstream constant). Retained for upstream
parity -- same category as CLASS_PALADIN/RANGER (upstream-named bindings
over live game data or genuine upstream tables): 13 `SECT_*` strings
(defines.h sector_t names; all 15 sectors live in MOVEMENT_LOSS),
`CON_APP_SHOCK` (upstream con_app[].shock table -- unread upstream too),
`TO_SOCIALS` (live upstream; placeholder for the unported CTAG colour
prefix, handler.py:932), `CLASS_PALADIN`/`CLASS_RANGER` (live playable
classes; ordinal symmetry with used CLASS_SWORDSMAN = 6).

Exact-token scan found bindings with no repository references:

- `src/automap.py:7-10`: `GW`, `GH`, `_CH` (duplicated by live
  `_CW`/derived height; `_CH` survives only in a docstring)
- `src/classes.py:20-21`: `CLASS_PALADIN`, `CLASS_RANGER`
- `src/config.py:176-190`: 13 `SECT_*` names unused; only
  `SECT_WATER_NOSWIM` and `SECT_AIR` are referenced
- `src/config.py:218`: `CON_APP_SHOCK`
- `src/handler.py:57`: `TO_SOCIALS` (only comments mention it)
- `src/world.py:34`: `OBJ_VNUM_DIPLOMA`

Candidate: delete 21 bindings if no intended external/public constant API.
PrimeSUD is an app, not a package; no in-repo consumer exists.

Verified 01/08, no fidelity gaps behind these:

- `SECT_*` ints: sector movement cost IS ported -- `movement.py:193-222`
  charges `MOVEMENT_LOSS` keyed by sector *string*, matching
  `act_move.c:148`. The int constants died when sectors went stringly.
- `OBJ_VNUM_DIPLOMA`: absent from 1stMud source entirely (ROM-ism); the
  diploma exists only as school-area content. Nothing to port.
- `CLASS_PALADIN`/`CLASS_RANGER`: not checked against upstream class list;
  trivially re-derivable either way, low stakes.

### Data retained for an unported creation-point system -- RETAIN (decided 01/08: upstream races.dat parity)

- Six PC-race entries in `src/races.py:51-231` store a `"points"` value.
- Runtime never reads that key; `groups.py` and `classes.py` explicitly say
  creation points are not ported.
- Only `tools/decode_races.py` parses/emits the values.
- Candidate: remove six runtime rows and stop decoder emission. This saves
  always-loaded table data, useful on constrained HP Prime heap.
- Tradeoff: race-table value parity becomes intentionally partial; document
  omission beside decoder instead of keeping dead runtime data.

### Dead character-state `affects` map / `m_hitroll` path -- FIDELITY FIX, DONE

Promoted 01/08: this is the one item where cleanup *improves* 1stMud
fidelity, not just line count. Applied 01/08 (combat.py one_hit THAC0 fold +
Verified-tag extension, handler.py `_char_base` dict removal, info.py stale
comment); 1502 tests pass, ASCII lint clean.

- `src/handler.py:158` allocates an empty `"affects"` dict for every
  character.
- Repository-wide search finds no writer to this map or to `m_hitroll`.
- Sole runtime read is `src/combat.py:1567`; it therefore always contributes
  zero to NPC THAC0.
- Upstream `one_hit` (`fight.c:651`) is plain
  `thac0 -= GetHitroll(ch) * skill / 100` -- no NPC extra term. The
  `extra_hr` term is a PrimeSUD invention reading a never-written map.
- Affect hitroll modifiers already land in `ch["hitroll"]` via
  `affect_modify` (`handler.py:307`), NPCs included; saves persist
  `affect_list` (`game_state.py:255-267`), not this dict, so save format is
  untouched.
- Candidate: remove the per-character dict and fold the THAC0 line to
  `get_hitroll(ch) * skill // 100`. Restores upstream formula exactly, plus
  per-mob heap win.
- Constraint: `one_hit` is `[Verified]` -- targeted fidelity-restoring edit,
  highlight for human review.

## Lower-value cleanup -- DONE (applied 01/08)

- `src/shop.py:629`: `tpl = item_tpl(obj)` in `do_value()` is unused. Deleted.
- `src/aliases.py:111`: `pos` from `enumerate()` is unused; iterates pairs now.
- Loop variables such as `combat.py:3579` `_attempt` are intentionally ignored
  and already named accordingly; no meaningful cleanup.

## Investigated and retain

- Save version mismatch backup/migration UX: active and protects incompatible
  current saves.
- `world.py` item-template/orphan fallbacks: needed for lazy-loaded areas,
  snapshots, removed templates, and synthetic objects.
- `item.promote_obj()`: active because reset-spawned/test objects can still be
  plain integer vnums.
- Sparse money fallbacks: instance/template copy-on-write behavior, not merely
  old-save support.
- `recommend.py` six-field row check: malformed/stale generated-index guard;
  current checked-in `mobs.idx` rows all have seven fields.
- `tml_prime.py` raw key path: stable base-library API; `CLAUDE.md` says not to
  break `tml` public API.
- Unused command `args` parameters: required uniform command-handler signature.
- `mobprog.py` `call_level` plumbing is semantically replaced by global
  `_call_depth`, but removing it conflicts with stated 1stMud signature
  fidelity and yields little line reduction. Leave unless API cleanup desired.
- `mobprog.py:1564-1567,1833-1836` final unknown-check guards are unreachable
  through `program_flow`, but `cmd_eval()` is a documented/directly-tested
  entry point. Keep defensive failure behavior.
- `special.spec_executioner()` is an inert registered callback, but source
  area 3011 names it and converter deliberately hard-fails unknown specials.
  `DESIGN.md` records its inert state as a user decision. Retain.
- Commented unported command-table entries duplicate `docs/COMMANDS.md`, but
  `CLAUDE.md` explicitly requires inline markers for unavailable ported
  features and their ordinals preserve upstream dispatch order. Retain.
- `RECOMMEND_PLAN.md` is mostly implemented but still has a pending G1
  heap/latency acceptance check. Delete only after that check, per project rule
  that completed plans are removed rather than archived.

## Scan notes

- All `src/*.py` modules are reachable from `primesud` through static imports.
- No statements occur after unconditional `return`/`raise`/`break`/`continue`
  within the same suite.
- No `if False`, `if 0`, or `while False` runtime blocks found.
- `ruff` and `pyflakes` are not installed; scans used Python AST plus exact
  repository token/reference checks.

# Class C scan -- unnecessary guards (01/08; FULLY APPLIED 01/08)

Status update 01/08 (second pass): sweep COMPLETE across src. Measurement
gate waived (user call: mechanical net gain regardless of magnitude); one
overall on-device playtest replaces the per-slice G1 probe. Applied on top
of the combat.py slice: 205 script conversions across 22 files (per-file
receiver whitelists; three patterns: `.get(K, {}/[])`, `.setdefault(K,
{}/[])`, `(x.get(K) or {})` -- the or-form allocates whenever the dict is
empty, since `{}` is falsy) plus 5 hand edits (game_state save-path x3;
magic.py:1372 dead tpl imm_flags fallback; mobprog `uses` check rewrite).
Retained by classification: template receivers (`tpl`, `MOB_DEFS[...]`),
object receivers (`obj.get("affect_list"...)` -- obj dicts are sparse),
`path.py:64` (`mob` can be a mobs.idx record, not a live char),
`game_state.py:670` (load path parses raw save data; also once-per-boot).
`learned` still EXCLUDED (absent from `_char_base`; only `create_char`
overlays it -- guard is load-bearing on NPC-reachable paths).

Earlier slice (same day): all 63 char-receiver flag/container
`.get(K, {}/[])` sites in combat.py converted to direct subscript;
`get_curr_stat` double-alloc removed; `max_stats` inline tuple default
hoisted to `_MAX_STATS_DEFAULT` (MicroPython const-tuple folding is
version-dependent, so an inline literal may allocate per call on-device).
Test fixtures routed through `_char_base()` (runtime-fidelity call, user
approved). Save policy recorded in DESIGN.md (bump `SAVE_VERSION`, never
migrate in core; migrations ship as standalone tools).

Different question from the sweep above. That pass asked "is this code
reachable?". This one asks "is this *check* necessary, given that we control
the app, the source, and the data pipeline?" -- and ranks by **device cost**,
not line count. A compat shim in a cold path is worth ~0; a redundant guard in
a combat loop is worth real milliseconds.

Triage classes used (from the 01/08 discussion):

- **A -- delete free:** readers for data shapes nothing in-repo can produce.
  Sweep above already ate the only real one (`GQUEST_WAITING`). Last remaining:
  `recommend.py:75` six-field row guard (`mobs.idx` is GENERATED, all rows
  7 fields). ~2 lines, cold path, low priority.
- **B -- keep, and not a shim:** `game_state.py:616` version gate plus
  `primesud.py:54` backup prompt. Reads no old format -- hard-rejects,
  snapshots, prompts. Value is *highest* in dev (frequent SAVE_VERSION bumps,
  single G1 test save). ~20 lines, boot-only, zero runtime.
- **C -- measure first:** defensive guards in per-tick / per-char / per-alloc
  paths. Only these move the needle. Everything below is Class C.

Policy proposal (kills the category rather than instances), for `DESIGN.md`:

> Save policy until engine 1.0: bump `SAVE_VERSION`, never migrate. The
> version gate plus backup prompt is the whole compat story.

## The cost rule

`d.get(k, {})` builds that dict on **every call** -- arguments are evaluated
before the call and `{}` is mutable, so it cannot be constant-folded.
`d.get(k, 0)` / `d.get(k, "")` / `d.get(k, (18, 18, 18))` fold to constants and
cost nothing. The hunt is therefore exactly `{}` and `[]` defaults.

Price: **one small heap allocation is ~490 us at full game heap** (~35 us
standalone), per `docs/PERFORMANCE.md` sec. Text rendering -- "for hot paths,
one avoided allocation buys ~49 native blit calls".

## C1 -- Eager mutable defaults on char dicts (204 sites) -- CANDIDATE

`_char_base()` (`handler.py:108-163`) hard-codes all 45 char keys. Every char
in `world.chars` passes through it:

- `create_char` (`player.py:68`)
- `create_mobile` (`mob.py:107`)
- load path too -- `game_state.py:1099` builds via `create_char`, then overlays
  saved fields; it never constructs a bare dict

Nothing deletes those keys. The only `del`/`pop` of a flag key repo-wide is on
*item* dicts (`item.py:302,565`, `magic.py:819,907` -- `vo` there is an object,
confirmed by the adjacent `vo["extra_flags"]` / `ch["inv"].remove(vo)`).

So on a char receiver the default is unreachable, and the allocation is pure
waste:

```python
ch.get("affected_by", {}).get("charm")   # allocates a dict, always
ch["affected_by"].get("charm")           # same result, no allocation
```

Counts by receiver (`ch`/`rch`/`victim`/`player`/`vch`/`mob`/`pet`/`inst`/
`target`/`gch`):

- **133** flag-dict sites (`act_flags`, `affected_by`, `off_flags`,
  `imm_flags`, `res_flags`, `vuln_flags`, `form_flags`, `part_flags`,
  `perm_stat`, `mod_stat`)
- **71** container sites (`inv`, `equip`, `affect_list`, `stance`, `learned`)

`combat.py` alone holds 54 flag-dict sites, **all** char receivers -- the
hottest file in the game. Densest stretches: `combat.py:2096-2149` (attack
speed / berserk), `3179-3519` (bash/trip/kick_dirt/disarm skill checks),
`1028-1137` (is_safe / killing paths).

The codebase already carries both idioms for the same invariant:
`mob.py:116` writes `ch["act_flags"]` directly, `mob.py:796` writes
`ch.get("act_flags", {})`.

Safest mechanical transform -- kill only the allocation, keep inner defaults:

```python
char.get("perm_stat", {}).get(stat, 10)   # before
char["perm_stat"].get(stat, 10)           # after -- do NOT also drop `, 10`
```

## C2 -- Template receivers are the opposite -- RETAIN (8 sites)

The "we control the data pipeline" argument reverses here. Generated area
files **omit empty flag dicts**: `area_limbo.txt` mob 30 carries `act_flags`
and `form_flags`/`part_flags` but has no `affected_by`, `off_flags`,
`imm_flags`, `res_flags`, or `vuln_flags`. The converter emits them
(`are_to_primesud.py:623-624`) and the emitter prunes falsy values to save
device space. `build_dist.py:101` `_share_area_flag_dicts` only *shares*
duplicate all-True dicts -- it does not strip keys, so it is not the cause.

`tpl.get("off_flags", {})` on a MOB_DEFS/ITEM_DEFS/ROOM_DEFS value is
load-bearing. 8 such sites (e.g. `mob.py:707`, `quest.py:185,190,193`).
Retain every one. Any sweep of C1 must classify receivers, not pattern-match
the string.

## C3 -- `get_curr_stat` (`handler.py:204`) -- CANDIDATE

```python
v = char.get("perm_stat", {}).get(stat, 10) + char.get("mod_stat", {}).get(stat, 0)
```

Two allocations per call for two `_char_base`-guaranteed keys. The function is
documented as running in combat loops (`handler.py:190` comment: "get_curr_stat
runs in combat loops", which is why `_STAT_IDX` is a dict and not
`tuple.index()`). Highest cost-per-line-changed in the scan.

Note `_race.get("max_stats", (18, 18, 18, 18, 18))` on line 208 is a *constant
tuple* default -- folded, no allocation. Leave it.

## C4 -- `promote_obj` / `isinstance(obj, dict)` -- RETAIN

18 `isinstance` checks in `item.py`, 17 `promote_obj` call sites. The
`and "key" in obj` half of those accessors is **required by design** --
instances are sparse copy-on-write (`item.py:64` liquid fields, `item.py:54-63`
light fuel stay template-only until mutated). Only the `isinstance` half guards
against plain-int vnums, it is a cheap early return, and it is not per-tick.
Not worth the churn; consistent with the sweep's existing `promote_obj` retain.

## Not to be touched

- `.get(k, 0)` / `.get(k, "")` / constant-tuple defaults -- no allocation.
- Template and ROOM_DEFS receivers -- see C2.
- I/O `try/except` -- `OSError: 0` FD exhaustion is a real device failure mode,
  not a legacy data shape.

## Gates before applying

1. **`[Verified]` permission required.** Most of `combat.py` is `[Verified]`.
   This is not a documented-TODO fidelity fix, so it falls outside the standing
   pre-approval and needs explicit human sign-off. Behaviour is unchanged by
   construction (same value returned), but the tag rule still applies.
2. **Do not extrapolate the arithmetic.** `PERFORMANCE.md` warns against
   projecting probe numbers into the game. 490 us is per-allocation, not a
   per-round total; not all 204 sites execute per round.

Proposed slice: convert the ~54 `combat.py` sites plus `handler.py:204` first
(highest density, one file family), instrument a combat-round probe on G1, and
only sweep the remaining ~150 if measured gain justifies it. `python -m pytest -q`
(1502 tests) plus `python tools/check_ascii_py.py` cover the transform.

## Class C scan notes

- Receiver classification was done by variable name plus constructor tracing,
  not by pattern alone; a few `.get(K, {})` sites use other receiver names and
  still need per-site classification before any sweep.
- Invariant verified three ways: `_char_base` key list, all `_char_base()`
  callers, and a repo-wide search for `del`/`pop` of the guarded keys.
