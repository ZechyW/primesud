# Combat and General Input Lag Assessment

Status: assessment and benchmark proposal only. No optimisation has been
implemented from this document.

## Executive summary

The reported sluggishness is credible and has more than one likely cause.
PrimeSUD has a cooperative, single-threaded game loop: keyboard polling,
command handling, periodic updates, rendering, and saving all run serially.
While any update or render is running, no keyboard pump runs. The firmware
buffers only four key presses until PrimeSUD drains them, so a sufficiently
long synchronous operation can turn ordinary delay into a missed input.

Combat makes the problem more visible because every violence pulse combines:

- a sorted snapshot and scan of every loaded character;
- one or more attacks per combatant;
- defensive checks, assists, autoskill, and program triggers;
- immediate rendering of every combat message;
- a condition line and another status-bar render afterward.

This is probably not one isolated `violence_update()` arithmetic bottleneck.
The strongest broad suspect is the status bar: every typed character rebuilds
and redraws the whole coloured HP/mana/move/input line. The strongest
combat-specific suspect is synchronous line-by-line output. Existing G1
measurements show that rendering 14 lines separately costs about 596 ms,
versus 156 ms through the batched renderer. Allocation, not native drawing,
dominates at the full game heap.

Periodic work can amplify the hitch. Violence, mobile, music, regen, area,
and world-tick schedules all coincide every 30 seconds. Every fourth world
tick also starts a synchronous autosave, currently measured at about 0.88
seconds steady-state on G1. Those larger stalls affect typing during combat
and ordinary play alike.

Recommended order:

1. Measure keyboard-service gaps and update/render phase durations on physical
   hardware with the full game heap.
2. A/B a differential status-bar renderer.
3. A/B batching output produced during one violence round.
4. Separate coincident periodic work and prevent combat-time autosave stalls
   if measurements still show large tails.
5. Optimise character scans, autoskill construction, or trigger scans only if
   phase timings identify them.

## Reported symptom

Typing feels generally slower during combat. Rapidly entering `flee` at low
health feels awkward and may require repetition.

Two different behaviours can look like the same symptom:

1. **Delayed feedback:** keys are retained, but the input buffer and status
   bar do not update until synchronous work finishes.
2. **Lost input:** more key events arrive during a stall than the firmware
   FIFO can retain.

The benchmark must distinguish these. Optimising display latency will improve
the first. Keeping keyboard-service gaps short enough, or draining between
long phases, is required for the second.

## Current execution model

### Main loop

`Game.game_loop()` performs one non-blocking keyboard poll, handles at most one
translated local event, checks the pulse clock, runs all due work, then waits
when no local keys remain (`src/primesud.py`).

There is no background input thread or interrupt-driven command queue. During
these operations, keyboard pumping stops:

- command interpretation and the command handler;
- `update_handler()`;
- terminal rendering;
- area loading or eviction;
- save serialisation and storage.

The normal idle poll target is 10 ms. That number describes idle polling, not
worst-case input latency. Responsiveness is governed by the longest interval
between calls to `_pump_keyboard()`.

### Keyboard queues

`tml_prime.py` has a 16-entry translated local queue. It helps only after
PrimeSUD gets control and drains firmware `GETKEY`.

Physical-device probing established a four-entry firmware FIFO. It preserves
presses during pure Python work, in order, but later presses are lost once the
four slots fill. This creates an important boundary:

- typing `flee` and pressing Enter produces five key events;
- pressing the default `8` macro and Enter produces two.

Therefore `flee` plus Enter can overflow the firmware FIFO during one
uninterrupted stall, while `8` plus Enter fits. The local 16-entry queue cannot
recover an event that firmware already discarded.

### Per-character prompt rendering

Every accepted character, backspace, history operation, buffer clear, and
several pulse/command paths call `show_prompt()` (`src/player.py`).

`show_prompt()`:

1. Builds the coloured HP/mana/move/XP prefix.
2. Computes visible width.
3. Slices the visible input tail.
4. Calls `terminal.tr.set_status()`.

The colour-aware status wrapper then strips and parses colour codes, renders
each colour run, pads the rest of the row, and stores a plain status copy
(`src/terminal.py`). The underlying `tml.set_status()` also represents status
updates as a full-row operation.

Much of the prefix is unchanged between adjacent keystrokes, yet it is rebuilt
and redrawn every time. This affects all typing, not only combat. Combat adds
more status redraws when HP changes and after a violence pulse.

## Combat pulse cost

### Full character snapshot

`violence_update()` starts with:

```python
for ch in [chars[k] for k in sorted(chars)]:
```

The snapshot is required because deaths and programs can modify
`world.chars` during iteration. Its present shape sorts and allocates a list
containing every loaded character, then inspects each one. Loaded areas retain
their spawned NPCs, so this cost scales with the loaded world rather than only
the player's room or current fight.

The loop also services remote hunters and any other active fights. Restricting
it to the player's opponent without tracking active remote combatants would
change behaviour. An active-fighter/hunter index is possible, but it adds
invalidation obligations to every fight, death, extraction, load, and program
path. That complexity is not justified before measuring snapshot and scan
time.

### Attack expansion

One combatant can produce several attacks:

- primary and secondary weapon hits;
- haste or fast extra hits;
- second and third attacks;
- stance extra attacks and special moves;
- mob offensive specials;
- player autoskill;
- assisting characters.

Each hit performs skill, stance, defence, immunity, damage, position, and
improvement work. Most of this is normal combat logic and should remain unless
profiling names a shared helper with disproportionate cost.

### Output and program triggers

Combat output is rendered immediately through `act()`/`chprintln()`. `act()`
also checks MOB, object, and room act triggers. Triggerless paths have several
short-circuits, but repeated messages can still mean repeated recipient and
trigger checks.

Immediate line rendering is a strong suspect because device measurements
already show:

| Render path | G1 cost for 14 busy-room lines |
|---|---:|
| Separate `tr.print()` calls | 596 ms |
| Batched allocation-free renderer | 156 ms |

Native glyph blits are cheap. At the full game heap, one small allocation was
measured around 0.49 ms, about 49 times the cost of one native character blit.
Combat message construction, act substitution, colour grouping, wrapping,
and per-line rendering all allocate.

Batching a complete violence round could provide a large win, but must
preserve exact output order across normal attacks, program output, deaths,
autoloot, condition output, and prompts. It should be tested as a terminal
defer/flush operation, not by changing combat messages or bypassing `act()`.

### Autoskill

When enabled and otherwise eligible, `auto_skill_round()` materialises the
effective rotation every violence round. Candidate construction can scan
learned skills, sort offensive spells, merge saved order, and create tuples,
lists, sets, and dictionaries.

The early exit is cheap when autoskill is disabled, the player is waiting, or
a manual command is queued. Rotation caching may help an autoskill-heavy
profile, but invalidation must cover learning, level/class/tier changes,
rotation edits, and resets. Treat it as a measured secondary candidate.

## Periodic general-operation stalls

### Thirty-second alignment

PrimeSUD uses four base pulses per second:

| Work | Period |
|---|---:|
| Violence | 2 seconds |
| Mobile | 5 seconds |
| Music | 6 seconds |
| Regen | 5 seconds |
| Tick | 30 seconds |
| Area | 30 seconds |

All countdowns begin due, and all periods divide 30 seconds. Consequently,
every 30 seconds one pulse can run every category.

The world tick includes weather, time, player tick effects, object updates,
quests, and global quests. Area work scans area states and may reset an area.
Mobile work snapshots and scans all loaded characters every five seconds.
Any one phase may be acceptable alone while their aligned total creates a
visible hitch.

Changing phase offsets by a few base pulses would preserve frequencies while
avoiding the single 30-second pile-up. This intentionally shifts exact update
ordering, so it should follow measurements and receive gameplay regression
coverage.

### Autosave

`AUTOSAVE_TICKS = 4` produces a save every 120 seconds. The current steady G1
save is about 879-881 ms. It is much faster than the former 11.7-second path,
but it remains a guaranteed synchronous input gap.

Options, in increasing complexity:

1. Defer an autosave while the player is fighting, then run it immediately
   after combat.
2. Add safe keyboard-pump checkpoints between existing serialisation phases.
3. Restructure saving into incremental work over several pulses.

The first is smallest, but extends the unsaved interval during long fights.
The second keeps save timing and can drain the four-entry firmware FIFO into
the 16-entry local queue, but needs a carefully scoped callback or save hook.
The third is unnecessary unless the first two fail.

### Area loading

Area loads are already known multi-second operations for large areas and have
their own physical-device benchmarks. They are explicit transition stalls,
not a combat-specific regression. They should remain a separate benchmark
class so their scale does not hide smaller recurring input delays.

### Command interpretation

The command interpreter linearly scans `_CMD_TABLE` in load order to preserve
prefix semantics. This happens once per submitted command, not per character.
It may be measurable with hundreds of commands, but rendering and periodic
updates have stronger evidence. A first-character bucket preserving table
order is straightforward only if command timing proves material.

## Benchmark design

### Requirements

Run on physical G1 with normal application residency and a representative
save. Repeat on G2 before generalising device-specific conclusions.
CPython timings can validate instrumentation and relative call counts, but
cannot predict Prime allocator or graphics cost.

Instrumentation must:

- be opt-in;
- avoid floats;
- avoid building strings in timed hot paths;
- avoid per-event terminal output;
- avoid retaining an unbounded sample list;
- use integer totals, maxima, counts, and fixed histogram buckets;
- dump results only after the scenario.

`hpprime.eval("Ticks")` costs about 0.3 ms per call. Phase-boundary timing is
acceptable. Timing every inner-loop helper or glyph would perturb the result.

### Responsiveness metrics

Primary metric: time between keyboard pumps.

`tml_prime._pump_keyboard()` already reads `Ticks` and stores
`_last_pump_ticks`. An opt-in profiler can compute the elapsed gap without an
additional timer call. Record:

- count;
- total gap;
- maximum gap;
- fixed buckets such as `<25`, `<50`, `<100`, `<250`, `<500`, `<1000`, and
  `>=1000` ms;
- local translated-queue drops.

Firmware FIFO drops are not directly observable. Infer risk from pump gaps and
confirm behaviour with scripted human input such as repeated `8`, Enter pairs.

Secondary input metrics:

- dequeue-to-finished-status-render time;
- status-render count;
- full versus unchanged-prefix status updates;
- submitted versus observed commands in a controlled sequence.

### Phase metrics

Instrument only coarse boundaries:

- `show_prompt`;
- complete `update_handler`;
- `maybe_evict`;
- area and bank;
- music;
- mobile;
- violence, including `update_mob_timers`;
- regen;
- tick;
- aggression;
- save;
- command interpretation.

For violence, also count:

- total loaded characters;
- characters inspected;
- active attackers;
- attacks or `one_hit()` calls;
- room population;
- emitted terminal lines;
- autoskill enabled/fired;
- mob/object/room programs fired.

These counts explain scaling. Duration alone cannot distinguish a slow scan
from a legitimately busy ten-attacker round.

### Rendering split

First measure production `violence_update()` end to end.

Then use one opt-in terminal timing wrapper to aggregate time spent inside
production `tr.print()`/`set_status()` calls. Timer overhead should be reported
and kept out of the normal build. Do not replace native rendering with
`lambda *args: None`: existing testing showed tuple allocation in such a
stand-in can be slower than real native blits and produces misleading data.

### Scenario matrix

Use the same loaded areas and save for every A/B.

1. **Idle:** no combat, no typing, at least 35 seconds.
2. **Typing:** continuously enter and erase a fixed string outside combat.
3. **Basic combat:** one normal opponent, autoskill off, no relevant programs.
4. **Autoskill combat:** same opponent, autoskill on.
5. **Busy combat:** multiple attackers/assists in one room.
6. **Program combat:** known fight/HP/act object or room program carriers.
7. **Aligned pulse:** capture the 30-second boundary during combat.
8. **Autosave:** capture the 120-second save boundary during combat and idle.
9. **Long session:** repeat after area travel and heap pressure.

Record at least several violence rounds per case. One maximum from one round
is useful for discovery but insufficient for an optimisation decision.

### Initial success criteria

Final gates should be set from baseline data. Useful provisional goals:

- no missing `8`, Enter sequence during ordinary combat;
- no local queue drops;
- normal non-loading keyboard-pump gaps usually below 100 ms;
- ordinary combat pulse tail below roughly 250 ms;
- no combined periodic pulse large enough to overflow normal emergency input;
- status rendering materially faster without visual regressions;
- no change to combat ordering, trigger order, damage, or pulse frequency.

Area loads and explicit blocking menus need separate expectations.

## Optimisation candidates

### 1. Differential status rendering

Confidence: high. Reach: all typing. Risk: moderate visual-state risk, low
gameplay risk.

Best target is the colour-aware wrapper in `terminal.py`, leaving stable
`tml.py` API behaviour untouched.

Possible implementation:

1. Keep the last visible status line and colour runs.
2. Find the unchanged visible prefix.
3. Redraw only the changed suffix.
4. Clear any leftover tail from the previous value.
5. Restore the correct colour at the first changed position.
6. Fall back to a full redraw when colours or truncation make a partial update
   ambiguous.

`show_prompt()` can separately cache its stats prefix using a tuple of HP,
maximum HP, mana, maximum mana, move, maximum move, and XP-to-level. That
removes repeated concatenation, but full-row drawing likely remains the
larger cost. Measure prefix caching and differential drawing separately.

Tests should cover:

- append, backspace, clear, and history replacement;
- input tail scrolling past available width;
- HP/mana/move/XP changes;
- colour reset and padding;
- dark/light mode if both are supported;
- identical status call as a no-op.

### 2. Violence-round output batching

Confidence: high that rendering matters; medium on achievable integration.
Reach: combat. Risk: output-order and memory regressions.

Capture terminal lines produced during one violence update, then flush them
through the existing batch renderer in original order. Do not rewrite combat
handlers to return messages; output crosses too many handlers and program
paths.

Required checks:

- exact visible output and ordering;
- wrapping and scrollback history;
- death/autoloot/program output order;
- condition line placement;
- prompt placement;
- no blocking input inside a deferred section;
- bounded temporary memory under a large combat round.

If a whole-round capture is too broad, batch only consecutive combat lines
until a non-combat terminal operation forces a flush.

### 3. Stagger periodic phases

Confidence: high that alignment exists; impact requires measurement.
Reach: recurring general and combat spikes. Risk: update-order differences.

Assign stable phase offsets so mobile, music, regen, area, and tick do not all
fire on one base pulse. Preserve each period exactly. Keep violence cadence
unchanged unless combat balance explicitly changes.

This should be considered only after phase timings show the aligned pulse is
meaningfully worse than ordinary violence pulses.

### 4. Avoid combat-time autosave stalls

Confidence: high for the 0.88-second stall. Reach: one event every 120 seconds.
Risk: longer unsaved interval or save-layer coupling.

Smallest candidate: mark autosave due during combat and execute on the first
safe post-combat pulse. If long-combat durability is unacceptable, add
keyboard-pump checkpoints between existing save phases instead.

Do not attempt concurrent or incremental saving without evidence that these
smaller options fail.

### 5. Active combatant/hunter index

Confidence: medium. Reach depends on loaded-character scan share. Risk: high
state-consistency burden.

Maintain IDs of characters that are fighting or hunting and snapshot only
that set. Every state transition must update it:

- `set_fighting()` and `stop_fighting()`;
- death/extraction and purge;
- area load/unload;
- program commands;
- hunting start/stop;
- save load and new game.

A stale index could silently skip attacks. Adopt only if the full-world
snapshot/scan is a leading measured phase after rendering improvements.

### 6. Mobile scan reduction

Confidence: medium. Reach: every five seconds. Risk: behaviour changes if
remote loaded mobs stop updating.

`mobile_update()` snapshots all characters and processes all loaded NPCs.
Possible later work includes a maintained NPC ID collection or per-area
collections. Restricting updates to the player's area is simpler but changes
remote wandering, hunting, programs, and despawn behaviour. Profile first.

### 7. Cache autoskill rotation

Confidence: medium for allocation saving when enabled. Reach: one player per
violence round. Risk: stale eligibility/order.

Cache only the structural rotation, not dynamic eligibility. Continue checking
mana, current affects, equipment, position, victim state, wait, and queued
manual input every round. Invalidate structural data on learning, class/tier
changes, reset, and rotation edits.

### 8. Per-room trigger summaries

Confidence: medium. Reach depends on program-bearing loaded content. Risk:
cache invalidation during area load/unload and snapshot fallback.

Current global OBJPROGS/ROOMPROGS presence can lead to room recipient scans
even when the current room has no relevant trigger. Per-room summaries could
skip those scans. Add only if trigger timing shows material cost.

### 9. Command lookup bucket

Confidence: low priority. Reach: once per submitted command. Risk: prefix-order
regression.

Bucket commands by first character while preserving original table order and
`noprefix` semantics. This is small, but should remain behind status,
rendering, pulse, and save work unless measured command dispatch is slow.

## Immediate gameplay mitigations

These do not solve general latency, but reduce emergency-input risk:

- Use default `8` macro, then Enter, instead of typing `flee`.
- Submit it once while recovering. PrimeSUD's wait queue is single-slot and
  latest-wins; repeated identical submissions normally add no advantage.
- Configure `wimpy <hp>` to auto-flee below a chosen threshold. The command
  allows up to half maximum HP.

A dedicated one-key auto-submit flee binding would reduce emergency input to
one firmware event, but adds a special input mode that is probably unnecessary
unless `8`, Enter still fails after latency fixes.

## Recommended work sequence

### Phase A: observe

Add opt-in aggregate timings and keyboard-gap histograms. Run the scenario
matrix on G1. Record raw logs and a concise result section in
`docs/PERFORMANCE.md`.

### Phase B: broad typing fix

Implement and A/B differential status rendering. Keep only the smallest
version that produces a clear device win. Validate status visuals and
scrolling.

### Phase C: combat rendering

Prototype violence-round batching using the existing terminal batch path.
Compare total violence duration, render share, heap headroom, and exact output.

### Phase D: tail latency

If 30-second or 120-second tails remain unacceptable, stagger periodic phases
and defer or checkpoint autosave. Measure each independently.

### Phase E: internal loops

Only after rendering and scheduling work, profile full-world violence/mobile
scans, autoskill construction, and trigger scans. Avoid new indexes or caches
without a measured win large enough to pay their state-consistency cost.

## Conclusion

Combat lag is likely a latency-composition problem:

- expensive full status redraws create a general typing baseline;
- synchronous combat output blocks polling every two seconds;
- full-world scans and program machinery add workload;
- periodic schedules create a larger 30-second combined pulse;
- autosave creates an occasional roughly 0.88-second gap.

The correct optimisation target is worst keyboard-service gap, not average
frame or pulse time. Physical-device aggregate profiling should precede code
changes. Current evidence makes differential status rendering and
violence-output batching the best first A/B candidates; active indexes and
new caches remain later options only if measured.

## Existing evidence

- `docs/PERFORMANCE.md`: rendering, allocation, save, area-load, and heap
  measurements.
- `docs/BUILTINS.md`: keyboard/touch behaviour and PPL call costs.
- `debug/keydrop_probe.py`: firmware FIFO and pure-Python input-capture probe.
- `src/primesud.py`: cooperative game loop and autosave dispatch.
- `src/update.py`: periodic phase scheduling.
- `src/combat.py`: violence scan, attacks, and flee handling.
- `src/player.py` and `src/terminal.py`: prompt construction and status
  rendering.
