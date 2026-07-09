# MOBPROG_PLAN.md -- MOBprogram engine port from 1stMud (programs.c / prog_cmds.c)

> **Progress -- Phases B + C DONE (09/07/2026, commits a38**** + 4bd****).**
> Phase B (a38****): trigger firing wired into every engine seam --
> `pulse_mob` random/delay in `mobile_update` gated on `position ==
> default_pos` (consumes the template `default_pos`; TODO.md bullet struck),
> `speech_trigger` in `do_say`, `greet_trigger`/`entry_trigger` in `move_char`
> + `do_enter`, `give_trigger`/`bribe_trigger` in `do_give`. New in mobprog.py:
> `percent_trigger`/`act_trigger` primitives + the per-trigger entry points, and
> the `mob_interpret` + `MP_COMMANDS` dispatch (the give->delay chain drives
> `mob delay`, so the command table lands here).
> Phase C (4bd****): combat triggers wired into fight.c's seams --
> `fight_trigger` (fight + hpcnt) in `violence_update`, `kill_trigger` /
> `death_trigger` in `damage()` (all inside [Verified] functions, tags
> extended). mpdamage uses the self-attacker no-retaliation path
> (`damage(v, v, ...)`). Skipped per decision 5: mpgtransfer/mpgforce/mpvforce
> (group/mass) -> logged `_mp_skip` stubs. Exit/exall + act triggers remain
> Phase E.
> Tests (tests/test_mobprog.py): percent-roll boundary, has_trigger
> short-circuit, speech/greet (default_pos gating), the scripted
> speech+give+delay integration chain, bribe, random pulse; per-mp-command
> units (mload/oload/purge/transfer/damage/force/remember/delay/call/junk +
> skip/unknown logs); combat integration (kill/death via damage(), fight/hpcnt
> via violence_update). Full suite green (818). Remaining: Phase D content
> pilot, Phase E (act + exit/exall).
>
> **Progress -- Phase A DONE (09/07/2026, commit 07a****).**
> `src/mobprog.py` shipped: `program_flow` (iterative state/cond stack,
> buggy-prog abort -> `dbg()`), `cmd_eval` (representative check subset;
> valid-but-unported check = log + false; unknown keyword = buggy abort),
> `expand_arg` ($-codes verbatim from programs.c), `num_eval`, `has_trigger`
> (empty-tuple early-out). Lazy per-area `MOBPROGS` registry wired into
> `world._load_area` (+ `reset_lazy` clear). Tests in
> `tests/test_mobprog.py`: if/else nesting, or/and, num_eval, expand_arg
> codes, buggy-prog aborts, and the say/emote/north spike. Full suite green
> (792, after the interpret free-text follow-ups below).
>
> **Spike findings -- which commands are prog-safe for a mob actor** (drove
> decision 6; full detail in mobprog.py module docstring):
> - PROG-SAFE: `say`/`'`, `emote`/`,`, movement (`north`..`down`). All route
>   through `act()`/`move_char`, which are already actor-generic; the mob is
>   the actor and the player sees only the TO_ROOM view. `move_char`'s NPC
>   branch handles leave/arrive acts + room mob-list bookkeeping.
> - ASSUMES A PLAYER (guard/avoid): (1) ARGUMENT CASE -- originally
>   `interpret()`/`one_argument()` lowercased the *entire* argument, mangling
>   say/emote text and colour codes (`{G`->`{g`). FIXED 09/07/2026 (commits
>   630****, 8bb****): `one_argument` lowercases only the command word, and
>   `interpret` dispatches the free-text set (`_FREETEXT_FUNS` =
>   say/emote/tell/reply/yell) with the verbatim argument tail, so a bare
>   say/emote through the interpreter now preserves case and colour codes. The
>   Phase C `mob echo` family stays available for output that must bypass the
>   interpreter entirely. (2) `mark_explored` allocated a ~2KB explored mask per mob --
>   now guarded (is_npc early-return). (3) `interpret`'s blank separator line
>   -- now guarded for NPC actors. (4) picker/`tprint`/pcdata commands
>   (train, score, quest, save, shop pickers...) assume the local player;
>   progs must not invoke them, mirroring `comm._order_interpret`'s NPC-safe
>   hand-dispatch stance.
>
> Not done here (later phases): trigger wiring (B), the `mob <subcmd>`
> command set + combat triggers (C), content pilot (D).


> 1stMud sources: `reference/1stMud4.5.3/src/`. Depends on: nothing hard;
> do last -- RESETS_PLAN decision 7 (default_pos annotation) and the other
> plans' combat/movement seams should settle first.
> On completion: harvest scope decisions 1/2/5 (MOB-only, trigger set,
> command subset) into DESIGN.md; strike TODO.md `mob_triggers` +
> `default_pos` bullets; delete this file.

Scripted mob behaviour: triggers on mobs fire small line-interpreted
programs (echo, load, force, damage, delay...). 1stMud sources:
`programs.c` (3008 lines: trigger dispatch + `program_flow` interpreter +
`cmd_eval_mob` if-checks + `expand_arg_mob` $-expansion) and `prog_cmds.c`
(2679 lines: the `mob <subcmd>` / `do_mp*` command set). Author-facing
spec (trigger semantics, if-check table, MOBcommand syntax, $-codes):
`reference/1stMud4.5.3/doc/MPDocs/Programs.doc`.

**Content reality check (drives scope):** no loaded PrimeSUD area contains
`mob_triggers` -- stock 1stMud/converted data has zero mobprogs. The
converter already handles them losslessly (`#MOBPROGS` section ->
`MOBPROGS = {vnum: code}` per area file; mob `M <type> <vnum> <phrase>`
trailers -> `mob["mob_triggers"]` tuples, are_to_primesud.py:153/480-528/
1249/1638). Surveyed 08/07/2026: **zero** stock QuickMUD areas
(`reference/quickmud/area/*.are`) contain `#MOBPROGS` either, so the
engine's only content path is PrimeSUD-authored progs (Phase D demo, then
quest content). Build it engine-first, content-pilot last, and don't wire
dead weight.

## Scope decisions

1. **MOB programs only.** 1stMud also has obj/room progs
   (`cmd_eval_obj/room`, `p_greet_trigger(ch, PRG_OPROG)` etc.) -- the
   converter emits neither; skip entirely, note `[PRIMESUD]` at the greet
   hook.
2. **Trigger set** (converter accepts: act, bribe, death, entry, fight,
   give, greet, grall, kill, hpcnt, random, speech, exit, exall, delay,
   surr). Port all except `surr` (surrender mechanic not ported -- reject
   or warn at load).
3. **Program storage:** `MOBPROGS` dict merges into a lazy per-area
   registry like MOB_DEFS (add to `world._load_area`; prog code strings
   ride the area file, so heap cost is only for loaded areas).
   `mob["mob_triggers"]` is already on templates -- instances read the
   template's tuple list; per-instance state is only
   `mprog_delay` (int) and `mprog_target` (char id, for
   remember/forget/TRIG_DELAY's rch).
4. **Interpreter limits:** MAX_NESTED_LEVEL and MAX_CALL_LEVEL small
   (1stMud values; check h/ -- nested 12ish, call 5ish). `mpcall` is the
   only recursion source -- keep `program_flow` iterative over lines
   (it already is) and cap call depth conservatively (HP Prime stack).
5. **Command subset:** port the solo-relevant mp-commands:
   mpecho / mpechoat / mpechoaround / mpasound / mpgecho / mpzecho
   (render as plain echoes -- no channels), mpkill, mpassist, mpjunk,
   mpmload, mpoload, mppurge, mpgoto, mpat, mptransfer, mpforce,
   mpcast, mpdamage, mpremember / mpforget, mpdelay / mpcancel, mpcall,
   mpflee, mpotransfer, mpremove, mppeace. Skip: mpgtransfer / mpgforce /
   mpvforce (group/mass-multiplayer). Unknown command in a prog = logged
   bug + skip line (1stMud buggy_prog behaviour).
6. **Dispatch model** mirrors 1stMud program_flow tail: control lines
   (`if`/`or`/`and`/`else`/`endif`, `*` comment, `break`?) handled by the
   interpreter; every other line gets `expand_arg_mob` $-expansion then
   goes to command dispatch -- `mob <subcmd>` routes to the mp-table, any
   other verb goes through the normal `commands.py` interpreter as the mob
   (1stMud `interpret(mob, data)`), which PrimeSUD's command table
   supports for mob actors in principle -- verify which do_* assume the
   player and guard (this is the riskiest integration surface; Phase A
   spike it with `say`/`emote` first).

## Architecture (new module `mobprog.py`)

- `TRIG_*` handling as string keys matching converter words.
- `has_trigger(mob, ttype)` over template `mob_triggers`.
- `program_flow(prog_vnum, mob, ch, arg1, arg2)` -- line loop with
  state/cond stacks (programs.c:2495-2830): `if <check> <args>` pushes,
  `or`/`and` combine on current level, `else` flips, `endif` pops;
  misplaced-keyword paths log and abort (buggy_prog equivalents ->
  PrimeSUD dbg()).
- `cmd_eval(check_line, mob, ch, ...)` -- port the check table from
  `cmd_eval_mob` (programs.c:421-761). Checks fall into shapes:
  argless (rand N, delay, hour), char-target ($n/$t/$r: ispc, isnpc,
  isgood/isevil/isneutral, isfight, ischarm, isfollow, isactive, isdelay,
  isvisible, hastarget, istarget, affected, act, off, imm, carries,
  wears, has, uses, name, pos, clan->skip, race, class, objtype-carried,
  level, align, money, hpcnt...), world (mobhere/objhere by vnum or name,
  mobexists, people/players/mobs counts, order->skip, exists). Port
  table-driven with a comparison helper (`num_eval`, programs.c:186:
  == != > < >= <=). Skip clan/order/multiplayer-only checks with inline
  notes; unknown check = buggy_prog + false.
- `expand_arg(fmt, mob, ch, arg1, arg2, rch)` -- $-codes from
  expand_arg_mob (programs.c:1433): $i/$I mob short/name, $n/$N ch,
  $t/$T arg1-char, $r/$R random char (get_random_char = random visible
  player in room, programs.c:208), $q/$Q mprog_target, $o/$O / $p/$P
  objects, $j pronouns etc. -- port the code list verbatim from source.
- `mp_commands` dict for decision-5 subset; each command is a small
  function taking (mob, args) -- most map onto existing helpers
  (create_mobile, create_object, extract paths, do_cast, damage()).
  `mpdamage` must use the no-retaliation damage path (check fight.c
  do_mpdamage semantics when porting).

## Trigger wiring (all sites already carry TODO markers)

| Trigger | Fire site | Marker |
|---|---|---|
| random, delay | mob update pulse, gated `position == default_pos` (update.c:444-462; finally consumes `default_pos` -- see RESETS_PLAN decision 7) | mob.py wander loop |
| greet/grall | after player move completes; greet = mob must see ch, grall = regardless | movement.py:308 comment |
| entry | mob's own move into a room (act_move.c:259) | movement.py:308 comment |
| speech | player `say` in room | comm.py:70/158 |
| act | act()-emitted text matching phrase | handler.py act_new -- defer to last, widest blast radius |
| fight | violence pulse while fighting | combat.py:128 |
| hpcnt | violence pulse, hp% below phrase number | combat.py:128 |
| kill | mob kills victim | combat.py:1127 |
| death | mob dies (before extraction) | combat.py:1312 |
| give | player gives obj to mob (phrase = obj name/vnum/all) | do_give in inventory.py |
| bribe | player gives coins to mob (phrase = min amount) | do_give coin path |
| exit/exall | player leaves via direction number; exit = only if mob sees ch | movement.py leave path |

Trigger phrase matching semantics per `p_act_trigger`/`p_percent_trigger`/
`p_exit_trigger`/`p_give_trigger` (programs.c:2835+) -- percent-type
triggers roll `number_percent() < atoi(phrase)`.

## Phases

- **A -- interpreter core:** mobprog.py with program_flow, cmd_eval
  (checks subset), expand_arg; area-load plumbing for MOBPROGS; spike the
  mob-as-command-actor path (`say`, `emote`, `north`) and document which
  commands are prog-safe.
- **B -- percent/simple triggers:** random, speech, greet/grall, entry,
  give, bribe (highest content value, simplest call sites).
- **C -- combat triggers + commands:** fight, hpcnt, kill, death; the
  mp-command set (mload/oload/purge/transfer/force/damage/cast/
  remember/delay chains).
- **D -- content pilot:** write a small `[PRIMESUD]` demo prog on a
  school/limbo mob (stock QuickMUD ships no `#MOBPROGS` -- surveyed
  08/07/2026); end-to-end validation on device (heap + timing).
- **E (optional, later) -- act trigger + exit/exall.** Port the global
  `MOBtrigger` latch here (1stMud sets it false around prog-emitted `act()`
  output so scripted speech/acts do not re-trigger). Until then a known gap
  exists: a mob's prog `say` fires *other* room mobs' speech triggers
  (`speech_trigger` only self-excludes), so two speech-trigger mobs whose
  phrases match each other's output can mutually recurse. Harmless while no
  content ships (Phase D authors the first prog); the act trigger is the
  widest re-entrancy surface, so the latch lands with it.

## Verification

- Unit-test the interpreter pure parts (no world): if/else nesting, or/and,
  num_eval operators, expand_arg codes against fabricated mob/ch dicts,
  buggy-prog abort paths.
- Scripted integration test on PC shim: demo mob with speech+give+delay
  chain (say keyword -> mob responds, give item -> mob loads reward,
  delay -> follow-up line).
- Device check: prog-heavy room idle CPU (random triggers each pulse) --
  ensure has_trigger short-circuits cheaply for the 99% of mobs with no
  triggers (empty-tuple check before anything else).
- `python tools/check_ascii_py.py`.

## Explicitly out of scope

Obj/room progs, TRIG_SURR/GET/DROP/SIT (bits exist upstream; converter
rejects words it doesn't know), OLC prog editing, ptrace/pdump debug
commands (1stMud imm tooling), prog `disabled` flag persistence.
