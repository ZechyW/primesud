# HANDOFF -- input-lag optimisation work (2026-07-30)

Workstation handoff for the combat/typing lag investigation. Companion
assessment doc: `COMBAT_LAG.md` (root, committed alongside this). Measured
history: `docs/PERFORMANCE.md` sec. Input-lag phase benchmark +
`debug/combat_bench-1..5.log`.

## Where things stand

All Phase B/C/D changes are COMMITTED on `dev` and DEPLOYED to the debug
appdir payload (`debug/transfer/Python debug.hpappdir/` -- verified
byte-fresh incl. `.font` files). The last two commits (`4eefb22` index,
`dcdded4` paced reveal) are **implemented and green on the desktop suite
but NOT yet device-validated**.

Shipped, device-validated (runs 1-5, G1):

- Prompt prefix cache (`player.py` `_PROMPT_CACHE`) + offscreen status
  compose (`terminal.py` `wrapped_set_status`) + colour-band font cache
  (`set_color` / `COLORFONT_GROB`): typing ~210 -> ~84ms/keystroke,
  status render 132 -> 72ms.
- Violence FIFO-drain checkpoints (`combat.py`, `_pump_keyboard` between
  combatants): input loss during long rounds structurally gone.
- Violence-round output batching (`update.py` wraps `violence_update` in
  `tr.begin_batch()`/`end_batch()`): neutral for 2-line rounds, wins on
  line-heavy ones; kept as the substrate for the paced reveal.

Shipped, bench-validated on device (run 6, `combat_bench-6.log`,
reviewed 30/07 -- results recorded in `docs/PERFORMANCE.md` sec.
Input-lag phase benchmark):

- **Active-fighter index** (`world.FIGHTERS`; commit `4eefb22`): works,
  no regression, but the ~100ms expectation was WRONG -- the old scan
  cost ~6-20ms in-context (`combat_basic` clean A/B run 5 vs 6);
  `scan_skeleton`'s ~110ms steady state is a tight-loop artifact. Index
  kept for O(fighters) scaling; win recorded honestly. Corollary:
  `mobile_update`'s "~100ms class" estimate used the same reasoning --
  demoted to measure-first.
- **Paced combat reveal** (commit `dcdded4`): pacing costs exactly
  ~25ms/row on every batched path (+52ms 1-mob round, +430ms 17-row
  batched look). Deliberate, key-skippable in play; benched as designed.

Shipped since run 6, desktop-suite green, NOT on device yet:

- **Autosave deferred while fighting** (`primesud.py` `game_loop`): both
  triggers (tick-timer, after-kill `save_pending`) gate on
  `player["fighting"] is None`, accumulate during combat, one merged
  save on the first non-fighting pulse. Removes the guaranteed ~880ms
  mid-combat keyboard-dead stall. Rationale: mob HP/fight state never
  persists, so mid-fight saves only snapshotted transient player damage
  (negative value). Kill-saves already cover real progress.
- **Reveal safety-valve fix** (`terminal.py` `_reveal_wait`): the
  `_REVEAL_MAX_ITERS` bound now counts consecutive zero-clock-progress
  spins, not total spins -- a fixed total truncated the reveal to ~12ms
  /line on the fast PC shim (~6us/spin). Device behaviour unchanged
  (slow spins always advance the clock); frozen-clock protection kept.
- **Global streaming reveal** (`terminal.py`): the paced reveal now
  covers ALL output paths (per-line prints, list/multiline prints,
  colour path, end_batch) with shared cross-call cadence -- greeting,
  looks, help, pager pages all stream at `REVEAL_MS_PER_LINE`/row. A
  key during any reveal wait latches pacing off (instant blit of the
  remainder, key kept as pending input); any `set_status` call (prompt
  redraw, pager/autoskill indicators) clears the latch and re-arms the
  first-row-instant rule. Verified on the PC graphical stack: all five
  render paths + cross-call cadence at exact budget, latch <10ms.
  Char-by-char streaming deliberately deferred until the line cadence
  has been felt on device.
  NOTE: this workstation has no appdir scaffolding -- the debug payload
  is now STALE (`src/primesud.py`, `src/terminal.py`, `src/config.py`);
  redeploy before the next device session.

## Immediate next step (needs physical G1 + Connectivity Kit)

1. Redeploy payload (staleness check per convention below), then manual
   play session -- the reveal is a feel feature, logs can't judge it:
   line-at-a-time cadence on EVERYTHING (greeting, look, help/pager
   pages, combat rounds), type-to-skip snapping + latch holding until
   the prompt returns, death/autoloot/multi-line ordering,
   scroll-boundary + shift/alpha indicators clean, a real low-HP
   `flee`-spam test (the founding complaint), and combat spanning a
   120s autosave boundary (save must land after the fight, never
   during). Judge whether 25ms/row cadence wants tuning and whether
   char-by-char streaming is still wanted on top.
2. Then per repo convention harvest `COMBAT_LAG.md`'s durable decisions
   into `DESIGN.md`/docs and DELETE both it and this handoff (git
   history keeps full text).

## Bench/probe conventions (established this stream)

- Probe: `debug/combat_bench.py`, deployed copy in the appdir payload.
  Only ONE self-running probe .py per appdir (this OR snapshot_gates.py
  OR save_smoke.py). Copy the real `primesud.sav` in first (read-only;
  SAVE_VAR redirected to "smoketest", SAVE_FILE to combat_bench.sav).
  Logs come back as `combat_bench.log` -> save as `debug/combat_bench-N.log`,
  commit with a `docs(perf)` entry.
- Payload staleness check after ANY src edit:
  `for f in src/*: cmp with appdir copy` (include `*.font` -- they were
  missed once). Never touch the binary `.hpapp*` files.

## Open decision queue (after validation, user call on stop-vs-continue)

Reordered 30/07 after run-6 findings (autosave defer DONE, mobile scan
demoted):

1. 30s aligned pulse ~550-700ms -> phase-offset stagger (COMBAT_LAG.md
   candidate 3; changes update ordering, needs regression care).
2. Attack-chain ~245ms/round residue (now ~all of the 355ms 1-mob
   round) -> needs per-hit profiling, diminishing returns.
3. `mobile_update` full-world scan every 5s -- DEMOTED: its "~100ms
   class" estimate came from the same scan-shape reasoning run 6
   disproved for violence (~6-20ms in-context there). Measure
   in-context first; likely a dead end. NOT index-shaped anyway
   (wander/despawn needs all NPCs).
- Interpret-level batching: MEASURED DEAD END (look render share ~0,
  combat_bench-5) -- do not revisit without new evidence.
- `combat_autoskill` first-round ~2x spike: warm-up (rotation build +
  first-cast affects), noted, not actioned.

## Watch items / loose ends

- Streaming reveal in tests: pc_shim shadows `src/terminal.py` for the
  whole suite except `tests/test_terminal_batch.py`, which now sets
  `terminal.REVEAL_MS_PER_LINE = 0` at load (its fakes have no keyboard
  pump, and it asserts single-blit compose shape). Any future test
  driving the real closures should do the same or provide
  `_pump_keyboard`/`has_queued_keys`.
- Bench comparability: runs 1-6 measured `interpret`/look paths
  UNPACED; the global reveal adds ~25ms/row to every multi-row output
  in future runs. A/B against old numbers must subtract the pacing
  budget or set `REVEAL_MS_PER_LINE = 0` for the run.
- Direct `["fighting"]` writes bypass the index -- chokepoint comments
  exist at both sites in combat.py; `tests/test_progs_engine.py` shows
  the sanctioned fixture pattern (`world.FIGHTERS.add(...)`).
- `hunting` is dormant scaffolding; if content ever sets it, also
  `world.FIGHTERS.add` (noted in `hunt.py` docstring).
- Mob-vnum 3090 ("no specials" pick) is the probe's standard opponent;
  `_pick_mob()` re-derives it, no hardcode.
