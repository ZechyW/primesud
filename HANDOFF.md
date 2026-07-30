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

Shipped, awaiting device validation:

- **Active-fighter index** (`world.FIGHTERS`; commit `4eefb22`): replaces
  the ~100ms full-world sorted scan in `violence_update`. Membership at
  `set_fighting`/`stop_fighting` (audited as the only None<->id writers);
  stale ids self-clean; `debug fidx` channel sweeps + heals + logs.
  `violence_update` is `[Verified:]` -- tag extended twice on 30/07
  (drain checkpoints, index scan); both were pre-approved targeted perf
  edits, flagged to the user, no objection raised.
- **Paced combat reveal** (`terminal.py` `print_lines(paced=True)` via
  `end_batch`; commit `dcdded4`): batched round output reveals one text
  row at a time, `REVEAL_MS_PER_LINE = 25` (config.py, 0 disables),
  keyboard pumped during delays, any queued key fast-forwards the rest
  in one blit. FEATURES.md line added.

## Immediate next step (needs physical G1 + Connectivity Kit)

1. Rerun `combat_bench` -> `combat_bench-6.log`. Expectations:
   - `combat_basic` ~360 -> ~260ms, `combat_busy` ~1.07s -> ~970ms,
     `combat_autoskill` down ~100ms (index win; these call
     `violence_update` directly -- no batching/pacing in their numbers).
   - `pulse_violence_only`/`pulse_aligned` now INCLUDE deliberate reveal
     delay (~25ms per line beyond the first, no key pending in synthetic
     runs) -- do not misread as regression.
   - `scan_skeleton` (~100ms) is the OLD scan cost kept as reference.
2. Manual play session -- the reveal is a feel feature, logs can't judge
   it: line-at-a-time cadence, type-to-skip snapping, death/autoloot/
   multi-line ordering, scroll-boundary + shift/alpha indicators clean,
   and a real low-HP `flee`-spam test (the founding complaint).
3. Record run 6 + Phase D outcomes in `docs/PERFORMANCE.md`; then per
   repo convention harvest `COMBAT_LAG.md`'s durable decisions into
   `DESIGN.md`/docs and DELETE both it and this handoff (git history
   keeps full text).

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

Roughly by value; user leaned "reassess after playing a fight":

1. `mobile_update` full-world scan every 5s (~100ms class). NOT index-
   shaped: wander/despawn legitimately needs all NPCs -- cheaper
   iteration (drop sorted()/snapshot allocs) or per-area lists; measure
   first.
2. Autosave 880ms stall every 120s -> defer-while-fighting (smallest
   fix, COMBAT_LAG.md candidate 4).
3. 30s aligned pulse ~550-700ms -> phase-offset stagger (candidate 3;
   changes update ordering, needs regression care).
4. Attack-chain ~245ms/round residue -> needs per-hit profiling,
   diminishing returns.
- Interpret-level batching: MEASURED DEAD END (look render share ~0,
  combat_bench-5) -- do not revisit without new evidence.
- `combat_autoskill` first-round ~2x spike: warm-up (rotation build +
  first-cast affects), noted, not actioned.

## Watch items / loose ends

- Paced reveal in tests: pc_shim shadows `src/terminal.py` for the whole
  suite except `tests/test_terminal_batch.py`, which never enters the
  paced path. If a future test drives `end_batch` through the real
  closure, the delay loop is iteration-bounded (`_REVEAL_MAX_ITERS`) so
  it cannot hang, but it will sleep-spin ~25ms/line with a live clock.
- Direct `["fighting"]` writes bypass the index -- chokepoint comments
  exist at both sites in combat.py; `tests/test_progs_engine.py` shows
  the sanctioned fixture pattern (`world.FIGHTERS.add(...)`).
- `hunting` is dormant scaffolding; if content ever sets it, also
  `world.FIGHTERS.add` (noted in `hunt.py` docstring).
- Mob-vnum 3090 ("no specials" pick) is the probe's standard opponent;
  `_pick_mob()` re-derives it, no hardcode.
