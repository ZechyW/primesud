# OPUS_HANDOFF.md -- Session prompts for executing the committed plans

Copy-paste prompts for implementing the six `*_PLAN.md` docs, one fresh
Claude Code session per stage, run from the repo root on `dev`. Written by
Fable (08/07/2026) against the plans as committed; if a plan file has
changed since, trust the plan file.

**How to use**

- One stage per session, in the order below. Fresh session each time --
  the prompt + plan file + CLAUDE.md are the full contract; nothing relies
  on chat history.
- Review the diff between stages (or at least between plans). Stages
  commit as they go, so a bad stage is a `git revert`, not an untangle.
- Device-only checks (heap, timing, physical keys) can't run in-session:
  each prompt ends by collecting them into a checklist for you. Run them
  on the calculator when convenient; nothing downstream blocks on them.

**Model choice.** Any Opus works; the prompts don't change between 4.6
and 4.8. Use the strongest available (4.8) with extended thinking for the
stages marked HARD (design judgment / riskiest integration): DARKNESS 1,
MOBPROG 1. The rest are careful-porting stages where the plan has already
made the decisions -- 4.6 is fine.

**Subagents.** Per the repo owner's standing rule, spawn subagents only
when clearly net-gain. In practice that means: an Explore agent to pull
together scattered 1stMud source blocks is fine; all edits happen in the
main thread. Each prompt repeats this.

**Verification.** Two extra prompts at the bottom: a stage-review prompt
(run in a FRESH session after any stage; mandatory after the HARD stages
and any stage whose diff you didn't read yourself) and a final audit
prompt for after the whole queue. The reviewer session must be fresh --
an implementer reviewing its own work in-context rubber-stamps it.

---

## Stage 1 -- RESETS (whole plan, one session) -- DONE 08/07/2026

Completed and reviewed (commits `8ef****..c2c****` on dev; RESETS_PLAN.md
deleted, `room_is_dark`/`room_light` landed in handler.py). Skip to
Stage 2. Prompt kept below for reference.

```
Implement RESETS_PLAN.md in full (all decisions, all touch points).

Read first: RESETS_PLAN.md, DESIGN.md, docs/AREA_FILES.md, the 1stMud
reset_room source (reference/1stMud4.5.3/src/db.c:1393-1724), and the
current mob.py reset_room / reset_area plus the world.py:378 cross-area
caller. Re-read the exact db.c block for each reset case immediately
before porting it -- the plan cites line ranges; the source is the truth
for limits, order, and messages.

One scope addition the plan coordinates but doesn't own: decision 6's
infrared grant needs room_is_dark, which doesn't exist yet. Port it now
per DARKNESS_PLAN.md decision 1 + the handler.c:2308 semantics (computed
room light, [PRIMESUD] comment) into handler.py, so the grant is real
rather than gated. Keep it to the predicate + its room_light helper --
the rest of DARKNESS is a later session.

Rules: CLAUDE.md governs (ASCII-only Python -- run
`python tools/check_ascii_py.py` after every edit batch; str()+concat for
any persisted string; [Verified] functions only per the documented-TODO
exception, minimal diff, extend the tag). Match 1stMud messages exactly.
Commit per logical chunk (limit helper + E/G, P, R, M extras) with
conventional-commit messages.

Verify: the plan's Verification section -- write the pytest cases it
lists (tests/ has fresh_world fixtures for synthetic areas; real areas
also load under pytest via pc_shim). All existing tests must stay green.
The buy-pet end-to-end check can be a pytest exercising do_buy in the
midgaard pet shop after a reset.

Finish: execute the plan header's "On completion" block -- harvest the
named decisions into DESIGN.md, strike the TODO.md bullets, delete
RESETS_PLAN.md, update the TODO.md active-plans list -- and note in
DARKNESS_PLAN.md's Phase A that room_is_dark/room_light already landed
(cite the commit). Anything you couldn't verify in-session goes in a
final "device checklist" message.
```

## Stage 2 -- DARKNESS part 1: Phases A + B (HARD) -- DONE 08/07/2026

```
Implement DARKNESS_PLAN.md Phases A and B (core predicates + command/UI
gating). Phases C and D are a later session -- do not start them.

Read first: DARKNESS_PLAN.md in full (decisions + 1stMud semantics
sections especially), docs/PRIME_UX.md, and the cited 1stMud blocks:
reference/1stMud4.5.3/src/handler.c:2300-2510 and act_info.c:470-515 +
1100-1130 + the do_exits region (~1476). Note: room_is_dark/room_light
may already exist from the RESETS session (check handler.py and the
plan's Phase A note) -- if so, verify them against handler.c:2308 instead
of rewriting.

Order of work: can_see dark gate, can_see_obj full port (the plan lists
the exact check order -- keep it), check_blind; then Phase B call sites
one at a time (do_look pitch-black + red-eyes + item filtering, exits
"Too dark to tell", automap.py:84 TODO, scan, inventory pickers). Exact
1stMud message strings, including the trailing space in
"It is pitch black ... ". For every Phase B site, read the surrounding
PrimeSUD function fully before editing -- several are [Verified]; only
the documented-TODO exception applies, minimal diffs, extend tags.

Rules: CLAUDE.md governs; `python tools/check_ascii_py.py` after every
edit batch. can_see must work with either player or mob observer (mob
aggro routes through it -- the plan's aggro note is intended behaviour).
Commit Phase A and Phase B separately.

Verify: room_is_dark truth-table pytest (each sunlight state, sector,
flag, lit-char case); a pytest that a dark room blocks look output and
infrared unblocks it; aggro shielding case. Existing tests green.

Finish: add a short progress note at the top of DARKNESS_PLAN.md ("Phases
A+B done <date>, commits <hashes>"). Do NOT delete the plan or run its
completion block -- Phases C/D remain. End with the device checklist
(automap rendering in a dark room, red-eyes on physical screen).
```

## Stage 3 -- DARKNESS part 2: Phases C + D -- DONE 08/07/2026

```
Implement DARKNESS_PLAN.md Phases C and D (light fuel + do_time /
do_weather). Phases A/B are already done -- read the progress note at the
top of the plan and the relevant commits first.

Read first: DARKNESS_PLAN.md decisions 4-6, the 1stMud sources:
reference/1stMud4.5.3/src/update.c:395-615 (weather_update + char_update
light block 597-613) and act_info.c do_time/do_weather; PrimeSUD's
game_time.py, update.py, game_state.py serializer, quest.py:371 seam.

Phase C: seed obj["light_hours"] at every template->instance seam the
plan lists (keep it ONE seam if reset spawning already funnels through a
single create_object path -- check first); burnout in the tick handler
with the exact messages ("$p flickers.", "$p flickers and goes out.",
"$p goes out."); serialize light_hours only-when-present; bump
SAVE_VERSION. light_hours is persisted -- str()+concat rules apply to the
save payload (docs/PRIME_STRING_FORMAT_BUG.md).

Phase D: weather_update port on PULSE_TICK, do_time/do_weather with exact
1stMud output, uncomment _CMD_TABLE rows #55/#57 -- verify row numbers
against the current commands.py before uncommenting.

Rules: CLAUDE.md governs; ASCII check after every edit batch; commit
Phase C and D separately.

Verify: burnout pytest (tick to <=5 -> flicker, to 0 -> extract + both
messages, negative fuel never decrements); save/load round-trip of
light_hours; do_time output format test. Existing tests green.

Finish: execute DARKNESS_PLAN.md's header "On completion" block (harvest
to DESIGN.md, strike TODO.md bullets, delete the plan, update the TODO.md
active-plans list). Device checklist at the end (school banner burnout
pacing, weather message cadence).
```

## Stage 4 -- REGEN (whole plan, one session) -- DONE 08/07/2026

```
Implement REGEN_PLAN.md in full (player gain modifiers + mob hp regen;
decision 3 means NO furniture work beyond its DESIGN.md row).

Read first: REGEN_PLAN.md, reference/1stMud4.5.3/src/update.c:161-373 and
520-565, PrimeSUD player.py tick_update (the TODO comments are the work
order), skill_utils.py get_skill/check_improve, classes.py has_spells.

Follow 1stMud's modifier ORDER exactly (position divisor -> room rate ->
poison/plague/haste-slow); resolve the plan's flagged ambiguities against
the source as instructed (the max(1,...) floor question; the plague
affect key). Mob branch: hp only, POS_STUNNED gate, shared-tail helper
marked [PRIMESUD]. Do not add mob mana/move pools.

Rules: CLAUDE.md governs; ASCII check after edits; integer math only in
the tick path; commit player and mob halves separately.

Verify: the plan's pytest table -- roll boundaries (roll == skill% is a
miss), warrior-vs-mage has_spells halving, modifier stacking, mob
position branches, regeneration doubling, full-hp early-out. Existing
tests green.

Finish: execute the plan header's "On completion" block (DESIGN.md
furniture row, strike player.py TODOs, delete the plan, update TODO.md
active-plans list). Device checklist: idle tick cost with a full
midgaard loaded.
```

## Stage 5 -- EXPLORED (whole plan, one session) -- DONE 08/07/2026

```
Implement EXPLORED_PLAN.md in full.

Read first: EXPLORED_PLAN.md, reference/1stMud4.5.3/src/explored.c (all
of it -- it's small) + handler.c:1360 + act_info.c:1841, PrimeSUD
world.py static tables + tools/gen_area_adj.py, the main command dispatch
loop, game_state.py serializer, docs/PRIME_STRING_FORMAT_BUG.md (the RLE
save string is persisted -- str()+concat only).

Work order: gen_area_adj.py AREA_ROOM_COUNTS emission + regenerate
world.py tables (commit the regenerated tables); mark_explored helper +
the two mark seams (per-command-dispatch + per-update-tick, cached
last-room compare, [PRIMESUD] note explaining why there's no
char_to_room choke point); RLE serialize/deserialize + SAVE_VERSION bump;
do_explored + the do_score line (exact 1stMud formats per the plan --
integer permille, no floats); uncomment the commands.py row (verify the
row number against current _CMD_TABLE).

Rules: CLAUDE.md governs; ASCII check after edits; do_explored must never
lazy-load an area (static tables only) -- add a pytest asserting
_LOADED_AREAS is unchanged by the command.

Verify: the plan's Verification section (RLE round-trips, areacount
against a hand-set mask, permille edges, list sorting). Existing tests
green.

Finish: execute the plan header's "On completion" block (DESIGN.md row ->
Ported, harvest the mark-seam deviation, delete the plan, update TODO.md
active-plans list). Device checklist: gc.mem_free before/after mask
alloc + save.
```

## Stage 6 -- PETS_GROUPS (whole plan, one session) -- DONE 08/07/2026

```
Implement PETS_GROUPS_PLAN.md in full. Prerequisite: the RESETS stage
must already be merged (item 1's buy-pet fix lands there -- verify
`buy kitten` works under pytest before starting; if it doesn't, stop and
report rather than fixing it here).

Read first: PETS_GROUPS_PLAN.md, reference/1stMud4.5.3/src/act_comm.c:
1304-1402 (do_group) and fight.c is_safe/is_safe_spell, PrimeSUD
comm.py follower block (204-401), combat.py:897-1028, commands.py.

Item 2 (do_group): port faithfully per the plan; make the 32-col
rendering call the plan allows, mark it [PRIMESUD] if you split lines.
Item 3 (safety gates): combat.py is_safe/is_safe_spell are [Verified] --
these edits resolve documented inline TODOs so they're allowed, but keep
them minimal, re-verify each function line-by-line against fight.c, and
extend the tags exactly as the plan specifies. Item 4: the verification
sweep is read-only; report findings, only edit if you find an actual
fidelity break.

Rules: CLAUDE.md governs; ASCII check after edits; commit items 2 and 3
separately.

Verify: pytest for group output format + add/remove branches; the plan's
end-to-end pet lifecycle as pytest steps (buy/name/follow/order/group/
die_follower/nuke_pets/save-load with pet_name). Existing tests green.

Finish: execute the plan header's "On completion" block (stale comment
cleanup, DESIGN.md row if the wrap concession was taken, strike TODO.md
group bullet, delete the plan, update TODO.md active-plans list).
```

## Stage 7 -- MOBPROG part 1: Phase A (HARD) -- DONE 09/07/2026

```
Implement MOBPROG_PLAN.md Phase A only: the interpreter core + the
mob-as-command-actor spike. This is the riskiest stage of the whole
queue -- the goal is a working, tested engine and a DOCUMENTED answer to
"which PrimeSUD commands are safe for a mob actor", not breadth.

Read first: MOBPROG_PLAN.md in full, reference/1stMud4.5.3/src/
programs.c (program_flow 2495-2830, cmd_eval_mob 421-761, expand_arg_mob
1433+, get_random_char 208, num_eval 186), PrimeSUD commands.py dispatch
+ comm.py do_say/emote paths, world.py _load_area (for the MOBPROGS
registry plumbing).

Build: new src/mobprog.py with program_flow (state/cond stacks, buggy-
prog abort -> dbg()), table-driven cmd_eval (the plan lists the check
subset; unknown check = log + false), expand_arg ($-codes verbatim from
source); MOBPROGS lazy per-area registry in world._load_area; per-
instance mprog_delay/mprog_target fields. Then the spike: drive a
fabricated prog that makes a mob `say`, `emote`, and walk north through
the real command interpreter; document in mobprog.py's module docstring
which command categories are prog-safe and which assume a player (with
the failure mode for each you tested).

Rules: CLAUDE.md governs; ASCII check after edits; keep program_flow
iterative (HP Prime stack); has_trigger must early-out on the empty
case before any other work. No trigger wiring yet -- Phase B does that.

Verify: the plan's unit tests (if/else nesting, or/and, num_eval
operators, expand_arg codes, abort paths) as pytest; the spike as a
pytest. Existing tests green.

Finish: progress note at the top of MOBPROG_PLAN.md (Phase A done, spike
findings summary, commits). Do not delete the plan.
```

## Stage 8 -- MOBPROG part 2: Phases B + C

```
Implement MOBPROG_PLAN.md Phases B and C: trigger wiring (random, delay,
speech, greet/grall, entry, give, bribe) and the combat triggers + the
mp-command set. Phase A is done -- read the progress note at the top of
the plan and mobprog.py's prog-safety docstring first; respect its
findings when implementing mpforce and friends.

Read first: MOBPROG_PLAN.md trigger-wiring table (each row cites the
PrimeSUD marker site -- go to each marker), programs.c:2835+ (the
p_*_trigger matching semantics), prog_cmds.c for each mp-command as you
port it (reference/1stMud4.5.3/src/). fight.c do_mpdamage semantics for
the no-retaliation path.

Work order: percent/simple triggers first (Phase B), commit; then combat
triggers + mp-commands (Phase C), commit. The random/delay pulse gates on
position == default_pos (update.c:444-462) -- default_pos is on
templates, unconsumed until now; consume it here and update the TODO.md
default_pos bullet. Skip the commands the plan skips (mpgtransfer/
mpgforce/mpvforce) with inline notes.

Rules: CLAUDE.md governs; ASCII check after edits; every trigger site
edit is inside existing combat/movement/comm functions -- some
[Verified]; the marker comments are the documented TODOs, keep diffs
minimal, extend tags.

Verify: scripted integration pytest per the plan (speech+give+delay
chain on a synthetic mob); percent-trigger roll boundary; per-mp-command
unit tests for load/purge/transfer/damage at minimum. Existing tests
green; specifically re-run combat and movement suites.

Finish: progress note at the top of the plan (Phases B+C done, commits).
Do not delete the plan.
```

## Stage 9 -- MOBPROG part 3: Phase D (+ optional E)

```
Finish MOBPROG_PLAN.md: Phase D content pilot, and Phase E (act +
exit/exall triggers) ONLY if Phase D surfaces no engine bugs and the
session has room.

Read first: the plan + both progress notes + docs/AREA_FILES.md (for
authoring area data by hand or via patch_1stmud_deltas.py -- check how
existing [PRIMESUD] data patches are applied and follow that mechanism).

Phase D: author a small [PRIMESUD] demo prog on a school or limbo mob --
a speech-keyword response, a give-reward, and a delay follow-up is the
right shape (it exercises expansion, checks, load, and the delay pulse).
The prog rides the area file's MOBPROGS dict + a mob_triggers tuple,
exactly the converter-emitted format (are_to_primesud.py:480-528 shows
the shapes). End-to-end pytest: walk a synthetic player through the
whole interaction.

Rules: CLAUDE.md governs; ASCII check after edits (area .txt files are
Python source -- ASCII rules apply to them too); area-data strings are
persisted-class strings (str()+concat if generated).

Verify: the end-to-end pytest; idle-cost sanity -- a room of trigger-less
mobs must not measurably slow the pulse (has_trigger early-out test).

Finish: execute MOBPROG_PLAN.md's header "On completion" block (harvest
scope decisions to DESIGN.md, strike TODO.md mob_triggers/default_pos
bullets, delete the plan, update the TODO.md active-plans list, and
delete this OPUS_HANDOFF.md -- it's a plan-class doc, same lifecycle).
Device checklist: prog-heavy room idle CPU + heap on the calculator.
```

---

## Review prompt -- run in a FRESH session after a stage

Replace `<STAGE>` with the stage name and `<COMMITS>` with the commit
range (e.g. `abc1234..def5678`, or the hashes from the stage's progress
note / git log).

```
You are reviewing another session's implementation of the <STAGE> stage
of a plan doc in this repo. Commits under review: <COMMITS>. You did not
write this code; your job is to find where it deviates from the plan and
from 1stMud, not to praise it. Do not trust the commit messages or the
plan's progress notes -- verify against the diff and the sources.

Read: the governing *_PLAN.md (if the stage completed a plan, it was
deleted -- recover it with `git show <first-commit>^:<PLAN>.md`), the
full diff (`git diff <COMMITS>`), and for every ported function the
actual 1stMud source block it cites (reference/1stMud4.5.3/src/).

Check, in order of importance:
1. Plan coverage: walk the plan's decisions/phase bullets one by one;
   for each, point to the diff hunk that implements it or flag it as
   MISSING. Silent scope-skips are the #1 failure mode.
2. 1stMud fidelity: for each ported function, compare logic flow, check
   order, arithmetic (integer division direction!), and every player-
   facing message character-for-character against the source. Flag typo
   "fixes" that lack a [PRIMESUD] comment.
3. Repo protocol: [Verified] functions edited only under the documented-
   TODO exception with tags extended; [PRIMESUD] comments on deviations;
   ASCII check passes (`python tools/check_ascii_py.py`); persisted
   strings use str()+concat (docs/PRIME_STRING_FORMAT_BUG.md); no edits
   to tml.
4. Tests: do the new pytest cases assert the PLAN's expected values
   (recompute them yourself from the 1stMud source) or just mirror the
   implementation? Run the full suite; report the real output.
5. Completion protocol: if this was a plan's final stage -- DESIGN.md
   harvest present, TODO.md bullets struck, plan file deleted; if
   mid-plan -- progress note accurate.

Fix directly: mechanical, unambiguous deviations (wrong message string,
missed TODO strike, missing [PRIMESUD] comment, tag not extended) --
commit as fix(<area>) with the ASCII check re-run. Report only, do NOT
fix: logic/structure findings, anything touching a [Verified] function
beyond the above, anything where the plan itself seems wrong.

End with: findings table (severity: BLOCKER / DEFECT / NIT), what you
fixed vs what needs a follow-up session, and the pytest summary line.
```

## Final audit prompt -- run once after the whole queue

```
All six plan docs in this repo's 08/07/2026 planning queue (RESETS,
DARKNESS, REGEN, EXPLORED, PETS_GROUPS, MOBPROG) have been implemented
and their plan files deleted. Audit the end state; trust nothing that
isn't verified in-session.

1. Leftovers: grep the repo for plan-queue debris -- `*_PLAN.md` files,
   OPUS_HANDOFF.md, "TODO dark", stale "not ported" comments the plans
   scheduled for removal, TODO.md bullets that should be struck (E/G
   limit, containers-P, R-reset, default_pos, mob_triggers, light_hours,
   condition, group command), the TODO.md active-plans section itself.
2. Doc consistency: DESIGN.md must contain the harvest rows each plan's
   header promised (recover headers via git log on the deleted files:
   `git log --diff-filter=D --name-only -- '*_PLAN.md'`). Explore
   tracking row says Ported; furniture row exists; no doc references a
   deleted plan.
3. Cross-feature seams the plans coordinated: reset-time infrared grant
   uses the real room_is_dark; buy-pet works end to end; explored marks
   fire on mobprog-driven transfers (mpgoto/mptransfer move the player
   without the normal movement path -- check the mark seam catches it);
   light burnout extraction doesn't break the P-reset container counting
   walk.
4. Run the FULL pytest suite and `python tools/check_ascii_py.py`;
   report real output.
5. Sanity-read the three most complex diffs of the queue (git log since
   the planning commits) for anything a stage-review missed.

Fix mechanical findings directly (same rules as the stage-review prompt);
produce a findings table for the rest. Finish with a consolidated
device-test checklist merging every stage's deferred on-calculator
checks, deduplicated, ordered by area so one walk of the world covers
them all.
```
