# HP Prime Firmware Heap Bugs (physical hardware)

Two distinct, confirmed firmware defects corrupt the MicroPython heap on
physical HP Prime calculators.  Neither reproduces on the PC Virtual
Calculator (same firmware source on x86), so all probing must happen
on-device.  Shared family traits: physical-only, heap-context sensitive,
corruption lands at block starts (first bytes, object headers).

- **Format bug (G1 + G2)**: any `%` or `.format()` call can zero the
  first byte of its output, corrupt unrelated *resident* strings, or
  hard-crash the calculator, depending on operator x context x device x
  heap layout.  Rule: build ALL strings with concatenation; no `%`, no
  `.format()`, period.  See sec. Format bug.
- **str(int)-GC bug (G1)**: bulk `str(int)` transients plus any garbage
  collection (explicit or automatic) corrupt the heap -- crash, stall,
  or delayed type confusion.  Rule: never loop plain `str()` over
  numbers; use `util.int_str()` (digit-table + concat), `util.num_str()`
  (cached), or `util.sstr()` (typed dispatch).  See sec. str(int)-GC
  bug.

Safe formatting API: `handler.chprintf`/`chprintlnf` format via
`_safe_fmt`, a manual concat parser that never touches the firmware
formatter (supports `%s`/`%c`/`%d`/`%%` with `-`/`0`/width).

## Format bug: `%`/`.format()` output corruption and crashes (G1 + G2)

Physical HP Prime Python corrupts strings produced by `%` or `.format()`
in certain contexts. The corruption zeroes or mangles the first byte of the
result. A standalone call with identical arguments is clean; the bug triggers
under memory pressure, particularly inside list comprehensions with nested dict
lookups.

### Observed Triggers

#### Trigger 1 — `%` formatting in save payload loop

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

#### Trigger 2 — `.format()` inside list comprehension with nested dict lookups

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

### Mechanism

Cause appears to be heap write-before-allocation or buffer underwrite triggered
by memory pressure during comprehension evaluation. Debug `tr.print()` calls
can mask the bug. The corruption is not reproducible from the emulator — only
physical hardware.

### Workaround

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

Avoid both `%` and `.format()` everywhere on-device -- see the FINAL rule
at the end of sec. Battery results.  (An earlier revision of this section
allowed `%` for transient UI-only strings; the 28 Jul 2026 battery
falsified that carve-out: outcomes are heap-layout-dependent and the
formatter under collect pressure corrupts even resident strings it never
touched, on both devices.)

### Status

Two independent triggers confirmed on physical HP Prime hardware.
MWE in `debug/test_fmt_bug.py`.

### Battery results (debug/fmt_battery.py, 27 Jul 2026)

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

## str(int)-GC bug: GC over small-string churn (G1; investigation, 27 Jul 2026)

Sessions on the physical G1 die stochastically when a garbage
collection walks garbage containing many small string objects.
Measured with `debug/save_bench.py` across many controlled runs (clean
pool = on+symb checkpoint restore before each):

- **Symptom spectrum, all at the same code zones**: hard reset; an
  impossible Python `TypeError` (`'list' object is not an iterator` on
  a `for` over a healthy list -- non-fatal, repeatable within the
  session); an uninterruptible stall (native call never returns; the
  On key cannot raise KeyboardInterrupt inside native code).
- **Acquitted by controlled runs**: `HVars` interop (a zero-HVars run
  reset on a clean pool; 22 8 KB HVars calls/session run clean),
  USB/Connectivity-Kit attachment, plain `ppleval` volume (100+
  `Ticks` calls fine), big *bytes* allocations (247 x 32 KB clean,
  twice), `str(int)` conversion, gc-call interplay, bad RAM (7.6 MB
  pattern-verified twice), heap size config, session residency.
- **Convicted (bigloop bisect + composition matrices)**: the
  `str()` BUILTIN APPLIED TO INTS -- narrower than "the formatter":
  `"%d" % t` producing the same 690 digit strings per cycle ran
  13.8K conversions / 20 collects clean in the same session whose
  `str(int)` control died at its iteration 2 (save_bench-14.log).
  Same-output different-route, opposite fates.  Confirmation run
  (save_bench-15.log): 80 straight clean collects (40 cache + 40 %)
  before the str(int) control corrupted at its iteration 2 again.
  Cumulative: cache fix 60 collects clean, `%` 60 clean, `str(int)`
  guilty 6/6 sessions.  The cycle [~965 `str(int)` allocs +
  ~173 list allocs -> drop -> collect] kills or corrupts within ~4-9
  iterations, 4/4 sessions (`smallonly`,
  save_bench-10/-11/-13.log + one unlogged hard crash).  Everything
  else acquitted by matrices: identical churn from tuples
  (`smallnostr`, 20 collects clean), identical small strs made by
  *slicing* -- mixed content (`smallslice`) and pure digit content
  (`digitslice`), 80/80 collects clean over 2 sessions.  Since a
  slice-made and a str(int)-made 3-char str are identical heap
  objects once created, the creation path itself is doing something
  GC/IRQ-unsafe -- same family as the format bug (sec. Format bug).
  Medium/big strings were passengers in every earlier deadly kind.
  This is the real save path's exact shape (serialize str() storm +
  gc_collect per autosave): the game's occasional G1 crashes are
  this bug, rate-limited only by saves being minutes apart.
- **Manifestation spectrum confirmed as one root** (save_bench-13):
  a matrix2 run survived all 60 iterations but its smallonly phase
  persistently type-confused exactly one heap object (work[83]'s
  toks list) from iteration 44 on -- 17 straight identical
  non-fatal TypeErrors, first time the corruption landed in
  scannable data rather than VM iterator/stack slots.  Where the
  stale write lands picks the symptom: data object => persistent
  catchable TypeError; VM slot => "impossible" TypeError with a
  clean data scan; native state => stall or reset.
- **Not reproducible on the Virtual Calculator** (27 Jul 2026): the
  same matrix probe that killed the physical G1 at iteration 24 ran
  60/60 clean on the PC emulator.  Same firmware source on x86, so a
  pure GC/string logic bug should have reproduced -- points at
  something physical-level (IRQ timing mid-collect, ARM codegen,
  memory ordering).  Also means all probing must happen on hardware.
- **G1-specific -- the G2 is acquitted** (fmt_battery, 27 Jul 2026):
  the exact str(int) storm + collect cycle that killed the G1 in 2-9
  iterations across 6/6 sessions ran 20/20 clean on a physical G2,
  after 40 further clean collects in the same session.  The G2 has
  its own, mechanistically distinct string bug (output corruption,
  collect-SUPPRESSED -- see sec. Battery results); the serializer
  fix below still applies game-wide since the game ships on both
  devices.
- **Stochastic**: byte-identical runs on clean pools split
  dead/clean.  Iterator-slot type confusion plus stochastic behaviour
  under churn fits a GC root-scan defect (live object collected when a
  collection fires at an unlucky VM state, block reused; stale read =>
  TypeError, stale write => corruption/reset/stall) -- working
  hypothesis, not confirmed.
- **Any collect over mixed churned garbage is the trigger**
  (`chunkedng`/`autogc` bisects): the cycle minus its explicit collect
  ran clean exactly as long as no collect happened at all (20-iter
  sessions, heap never filled), and died the moment heap exhaustion
  forced the first *auto*-collect (300-iter run, dead at ~iter 33
  where free hit zero).  Explicit-vs-auto is irrelevant; what matters
  is what the cycle churned: uniform big blocks are safe (mem_soak
  forced ~243 auto-collects clean; `bigonly` 60+ explicit collects
  clean; `medonly` 2 KB string slices clean over multiple sessions;
  `smallnostr` tuple churn and `smallslice`/`digitslice` slice-made
  small strs all clean), cycles rich in `str(int)` transients are a
  ~25-30%-per-collect death roll in probe conditions.  Deaths land
  in the alloc burst right *after* a logged-ok collect: the collect
  (or the formatter racing it) plants the corruption, the next storm
  detonates it.  Mitigation can now be near-deterministic for bulk
  paths: eliminate bulk `str(int)` calls (number-string cache /
  precomputed tables), and do not add explicit collects right after
  churn bursts (the save path's opening `gc_collect()` was a
  guaranteed worst-case roll per save -- earlier "may be
  load-bearing protection" guess in this file was backwards).
  Caveat on rates: the clean -4/-5 sessions survived ~25
  storm+collect passes, improbably lucky at the probe rate --
  per-collect risk also depends on heap state, so probe rates do not
  transfer to in-game rates; validate fixes by soak, not arithmetic.

### Consequences for game code

Until better understood: eliminate bulk `str(int)` production
(serialize, area-data generation) via a number-string cache or
precomputed tables -- sporadic single calls are background-level risk,
~1000-call storms are the repro; payload chunking does NOT mitigate
(`chunked` died; the formatter call count is the exposure, not string
size); never call `gc.collect()` immediately after such a burst; keep
alloc churn low in hot paths (already policy).  Bench addendum (31 Jul,
save_smoke-9/-10): collects over *validated-path* garbage
(`int_str`/`sstr` concat, the save's shape) ran clean 12/12 at every
landing site tried, so the save path now takes a deliberate
threshold-gated collect at its tail (`game_state._GC_FREE_FLOOR`) --
the ban stands for churn rich in raw `str(int)`/formatter transients,
not for the validated replacement shapes.  `"%d" %` formatting is
acquitted for the CRASH bug (13.8K bulk conversions clean) -- but
remains banned everywhere for the separate format bug (sec. Format
bug); the two bugs are distinct and both real.  A validated `str(int)`
replacement exists: number-string cache with `int_str()` digit-concat
misses (debug/save_bench.py `cachedstr`), clean over collects that
killed the `str(int)` control in the same session.  `hex()` remains
unprobed.

## Relation between the two bugs (27 Jul 2026)

Shared family traits: physical-only (emulator clean), heap-context
sensitive, corruption lands at block starts (first byte for the format
bug, object headers for the GC bug).  Discriminating traits: the
format bug is near-deterministic and content/alignment-dependent
(`mud_school` vs `mudschool`), corrupts its own output, and reproduces
on G2; the GC bug is stochastic, content-independent, corrupts
unrelated live objects, and `"%d"` formatting is *acquitted* for it
while `str(int)` is convicted -- the opposite polarity of the format
bug's workaround.  Keep both rules: no `%`/`.format()` anywhere (the
format bug), no bulk `str(int)` between collects (the GC bug -- use
the number-string cache + `int_str`, see save_bench.py `cachedstr`).

## Remediation status (soak-validated on-device, G1, 28 Jul 2026)

A 1 Hz full-save-path autosave hammer (serialize + HVars + readback +
file write every second) plus movement-heavy room rendering ran 250
autosaves with zero crashes, stalls, or type confusion -- far past the
pre-fix crash horizon (probe sessions died within a handful of
save-shaped churn+collect cycles). Covers both bugs: the serializer
now runs on `util.sstr`/`num_str`/`int_str` (str(int)-GC bug) and all
game output is concat-built with zero `%`/`.format()` (format bug).

Survivor found 31 Jul 2026: `scan.py` held its distance strings in a
module-level table (`"nearby to the %s."`) and applied `%` to the
hoisted variable, so `check_ascii_py.py`'s direct-`%`-on-literal rule
never saw it -- a live `%` on every `scan` that spotted a mob, for the
whole life of the project.  Fixed to concat, and the checker now also
flags any string literal carrying a printf conversion spec unless it is
a docstring or an argument to `chprintf`/`chprintlnf` (0 false
positives across `src/`).  Rest of the sweep was clean: no `.format()`,
no f-strings, 37 other `%` sites all numeric modulo, every `open()` in
a `with`, no bulk `str(int)` loops, `gc.collect()` sites all away from
int-render bursts, `ppleval` fed only int-derived strings.

31 Jul follow-up (`debug/save_smoke-9/-10.log`, real save): the
unexplained 31/07 crash prompted a drive-to-exhaustion bench.  Save-path
garbage is fully transient (~420 KB/save, ~13x payload; one collect
reclaims ~100%), and 12 collects walked it clean across two heap
histories and every landing site tried (`hvset`, `sweep`, mid-gameplay
churn, explicit).  At the probe-era 25-30%-per-collect death rate, clean
survival odds were 1-3% -- the auto-collect-over-save-garbage hypothesis
is downgraded from prime suspect to residual, and the crash stays an
unexplained one-off (watch entry in TODO.md sec. G1 crash watch).  The
save path now ends with a threshold-gated collect (docs/PERFORMANCE.md
sec. Save-path heap churn) so reclaim happens at the bench-validated
site instead of a random mid-gameplay auto-collect.

01 Aug follow-up: a src-wide sweep converted every remaining bare
`str()` call to `num_str`/`sstr` (or a `# str-ok` audited exemption),
including `str(int)`-in-loop sites the earlier static audits had missed
(route RLE builder in info.py, mobprog trace) -- plausible candidates
for the 31/07 one-off.  `tools/check_ascii_py.py` now flags any bare
`str()` in `src/`, so the class cannot silently return.  Heap stability
with the sweep applied has NOT been re-soaked on-device; the 28 Jul
soak numbers predate it.

## Related PPL parse bug (unrelated mechanism, same fragile bridge)

Community-documented: numeric literals with a plus-sign exponent
(`2e+1`) error out in `hpprime.eval`, and MicroPython float-to-string
can emit exactly that form -- never `str()` a float into a PPL
expression (PrimeSUD sends only ints). See
<https://udel.edu/~mm/hp/primePython/>.
