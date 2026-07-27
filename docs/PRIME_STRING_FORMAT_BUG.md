# Physical HP Prime String Formatting Bug

## Summary

Physical HP Prime Python corrupts strings produced by `%` or `.format()`
in certain contexts. The corruption zeroes or mangles the first byte of the
result. A standalone call with identical arguments is clean; the bug triggers
under memory pressure, particularly inside list comprehensions with nested dict
lookups.

## Observed Triggers

### Trigger 1 — `%` formatting in save payload loop

In PrimeSUD `save_char()`, this area-state serialization was unstable:

```python
"a.%s.age=%s" % (_as["tag"], _as["age"])
```

The failure reproduced when:

- `_as["tag"] == "mud_school"`
- `_as["age"] == 0`
- the line was built as part of the save payload prefix through area-state
  serialization

Probe result:

```text
normal percent/through_areas n=62 bad=58 join=True
```

Changing only the probe tag from `mud_school` to `mudschool` made the same
suite pass.

A later physical-device autosave isolation test reproduced a crash after about
200 autosaves when area resets were enabled and save payload lines used `%`
formatting. The crash disappeared after converting save payload construction to
explicit `str()` plus concatenation; the same build ran past 300 autosaves.
Payload length was not the trigger: a 20x payload padding test did not
meaningfully change the autosave count before failure.

### Trigger 2 — `.format()` inside list comprehension with nested dict lookups

In PrimeSUD `do_practice()`, this names list was unstable:

```python
names = ["{} ({}%)".format(SKILLS[vnum]["name"], pct) for vnum, pct in practicable]
```

Observed on physical device (G2): entry 5 ("parry") produced `'\x00arry (35%)'` —
first byte zeroed, rest of string intact. A standalone call with the same
arguments was clean:

```python
"{} ({}%)".format("parry", 35)  # correct on its own
```

A minimal reproduction (`debug/test_fmt_bug.py`) confirmed the pattern:
10-entry comprehension iterating a dict, each entry doing a nested dict lookup
(`_skills[k]["name"]`) and `.format()`, reliably produced `\x00`-corrupted
first bytes on at least one entry.

With tr.print, the corrupted `\x00` first byte caused the string to print with the first
visible character missing and the underlying HP Prime Python terminal to bleed
through on the first print of the affected string.

Note: On the G1, the MWE as is doesn't trigger the bug; might need more reliable example
if we intend to file a report.

## Mechanism

Cause appears to be heap write-before-allocation or buffer underwrite triggered
by memory pressure during comprehension evaluation. Debug `tr.print()` calls
can mask the bug. The corruption is not reproducible from the emulator — only
physical hardware.

## Workaround

Use explicit `str()` plus concatenation everywhere a string is built from
dict-sourced values, especially inside list comprehensions and loops:

```python
# Instead of:
"{} ({}%)".format(SKILLS[vnum]["name"], pct)
# Use:
str(SKILLS[vnum]["name"]) + " (" + str(pct) + "%)"

# Instead of:
"a.%s.age=%s" % (_as["tag"], _as["age"])
# Use:
"a." + str(_as["tag"]) + ".age=" + str(_as["age"])
```

Avoid both `%` and `.format()` for:
- List comprehensions with nested dict lookups
- Save payloads, HVars/PPL strings, file formats, generated area data
- Any string that will be joined/stored/parsing-critical

Transient UI-only strings built from simple literals (no dict lookup) may still
use `%` when useful for `{X` colour-code compatibility.


## Status

Two independent triggers confirmed on physical HP Prime hardware.
MWE in `debug/test_fmt_bug.py`.

## Relation to the G1 str(int)-GC crash bug (27 Jul 2026)

A second, distinct string-subsystem defect was isolated later: bulk
`str(int)` transients plus a garbage collection stochastically corrupt
the heap on the G1 (BUILTINS.md sec. G1 memory-corruption bug).  Shared
family traits: physical-only (emulator clean), heap-context sensitive,
corruption lands at block starts (first byte here, object headers
there).  Discriminating traits: this bug is near-deterministic and
content/alignment-dependent (`mud_school` vs `mudschool`), corrupts its
own output, and reproduces on G2; the GC bug is stochastic,
content-independent, corrupts unrelated live objects, and `"%d"`
formatting is *acquitted* for it while `str(int)` is convicted -- the
opposite polarity of this bug's workaround.  Keep both rules: no
`%`/`.format()` in persisted strings (this bug), no bulk `str(int)`
between collects (the GC bug -- use the number-string cache +
`int_str`, see save_bench.py `cachedstr`).

## Battery results (debug/fmt_battery.py, 27 Jul 2026)

Six-phase differentiation battery run on both devices
(debug/fmt_battery-g1.log / -g2.log):

- G2, MWE baseline: entry 5 ("parry") first-byte-zeroed 30/30 reps --
  deterministic, exact historical signature.
- G2, MWE + collect before each rep: 6/30 bad (reps 8/10/18/20/28/30,
  periodic).  Collects SUPPRESS the corruption; the periodic pattern
  tracks the session's slowly-growing log garbage, i.e. heap LAYOUT
  decides whether a given construction corrupts.  This is opposite
  polarity to the G1 str(int)-GC bug (collect-triggered) -- the two
  bugs are mechanistically distinct, settled.
- G2, MWE + 2.5MB live ballast: back to 30/30 bad.  Pressure/layout
  drives the rate, not collections.
- G2, bulk flat-arg conversions: 27,600 verified `"%d" %` and
  `"{}".format` conversions, 0 bad, 40 collects clean -- corruption
  requires the comprehension/nested-dict context, matching the
  original "standalone is clean" observation.
- G2, str(int) storm + collect x20 (the 6/6 G1 killer): CLEAN.  The
  GC bug is G1-specific; G2 needs only this output bug's rules.
- G2 sleeper: the battery log's own second line lost its first byte
  ("free at start" -> " ree...") -- that string was built by concat +
  digit-table lookup, NO %/format involved.  Single instance, but it
  suggests the defect sits in G2 string construction generally, with
  %/.format-in-comprehension merely the reliable trigger context.
- G1: session DIED in the MWE baseline phase -- zero collects, zero
  str(int) in play, so the G1 GC bug cannot explain it.  REPRODUCED
  2/2 sessions (28 Jul 2026), both dying right after the phase-A
  header: the G1 manifestation of THIS bug is a crash rather than
  output corruption -- which explains why the old MWE "didn't
  trigger" on G1; it watched for corrupt output while the G1 failure
  mode was death.  Both devices are exposed to this bug, with
  different symptoms (G2 corrupts, G1 dies); the no-%/.format rules
  are load-bearing on BOTH.
- Evidence-file curio: the G2 battery log itself contains the
  corruption -- its second line's first byte is a literal \x00
  (git/editors sniff the log as binary because of it).
- Battery v2 (28 Jul 2026, fmt_battery-g1-2/-g2-2.log): `%` in the
  same comprehension + nested-dict trigger context hard-crashed BOTH
  devices immediately (phase A0, before a single verified rep, no
  collects involved).  The % ban is independently necessary -- and
  in this context % is WORSE than .format(): the G2, which survived
  the whole v1 battery with only output corruption under fmt-comp,
  dies outright under pct-comp.  Manifestation (corrupt vs crash) is
  a function of operator x context x device, not device alone.  The
  rest of the operator x context matrix (pct-loop, pct-t1, fmt-loop)
  is being bisected one phase per session (fmt_battery.py
  START_PHASE).
- Bisect continuation (28 Jul 2026, -3/-4 logs, both devices each
  time): pct-loop (plain loop, subscripts in the % expression) DEAD;
  pct-loop-locals (same loop, lookups hoisted to plain locals before
  the % line) ALSO DEAD.  No comprehension, no dict access at the
  format site, still fatal on G1 and G2.
- Standing contrast that bounds the safe set: single-int `"%d" % t`
  in a plain loop is proven clean at scale (60 collects G1, 27.6K
  verified conversions G2).  The A1L shape differs only in
  {multi-arg tuple, %s-with-str-arg, %% escape} -- the poison is in
  that set; bisectable via further START_PHASE rungs if wanted.
- Poison-isolation session (28 Jul 2026, -5 logs, both devices):
  single ingredients ALL clean 30/30 -- %s-with-str, tuple-of-ints,
  int+%% escape, and even the historical trigger-1 subscript shape.
  The A1L killer combined all three.  But the same session showed
  the acquittals are untrustworthy:
  - fmt-comp, which killed the G1 2/2 as a fresh-session phase, ran
    30/30 CLEAN on the G1 as the 7th phase of this session.  Phase
    outcome depends on heap history/layout, not shape alone.
    Survival evidence does not transfer between layouts; only
    deaths/corruptions are informative.
  - Phase B (fmt-comp + the session's first collects) progressively
    zeroed first bytes of the EXPECTED-value strings on BOTH
    devices -- strings built at startup via concat+int_str, held
    live, never touched by the formatter.  Both devices then died
    mid-phase.  The format machinery under collect pressure
    corrupts ARBITRARY resident strings; safe construction does not
    confer safe residence while formatting happens elsewhere.
- Game-code implication, FINAL: no % and no .format() on-device,
  period.  The bisect is closed as unconvergeable (layout roulette
  defeats shape-level acquittal).  Only construction method with a
  clean record across every tested layout: concat + str(), with the
  int_str/number-cache path for bulk int rendering ("%d"-single-int
  has real mileage -- 60 collects G1, 27.6K conversions G2 -- but
  its safety claim is now the same epistemic class as fmt-comp's
  was before this session).

Caution on Trigger 1's crash counts: the ~200-autosave crash vs 300+
clean comparison was one run each, and any save build of that era also
did bulk `str(int)` + an opening `gc_collect()` -- the *crash* (unlike
the probed output corruption) may have been the GC bug, so do not
treat those counts as evidence about `%`.  Discriminating probe if
closure is ever wanted: run the MWE with and without interleaved
`gc.collect()` -- corruption rate tracking collects implies one root.
