# HANDOFF -- save-path crash investigation (31/07/2026)

Live workstream, mid-investigation. Continue by running the phase C/D probe
on a physical G1 and reading `debug/save_smoke.log`. Everything below is
current as of the last commit on `dev`.

Related: `TODO.md` sec. "Save path lost its soak cover",
`docs/PRIME_FIRMWARE_BUGS.md`, `docs/PERFORMANCE.md` sec. Save path.

## Why this exists

An unexplained hard crash on the physical G1 on 31/07/2026 -- the first since
the physical-glitch investigation closed on 28/07. Not reproducible; the
player was not near any particular command. This workstream is establishing
whether it is systematic or a one-off.

## What has been established

### 1. One real format-bug survivor, found and fixed -- but not the cause

`scan.py` kept its distance strings in a module table (`"nearby to the %s."`)
and applied `%` to the hoisted variable, so every `scan` that spotted a mob
ran a banned `%` on-device. Present since the early port. Fixed to concat
(`1885284`).

**Ruled out as the cause of this crash** -- the player was nowhere near a
`scan`. It stays a real latent bug (the format bug is layout roulette, and a
rarely-exercised `%` is exactly the profile of an intermittent killer).

`tools/check_ascii_py.py` missed it because it only flagged `%` with a
str-literal *left operand*; a format string parked in a variable or table
slipped through -- the hole its own docstring named. It now also flags any
string literal carrying a printf conversion spec, exempting docstrings and
`chprintf`/`chprintlnf`/`_safe_fmt` arguments. 0 false positives across
`src/` (`dad20d6`, tests in `tests/test_check_ascii_py.py`).

### 2. Rest of the static sweep is clean

No `.format()`, no f-strings, 37 other `%` sites all numeric modulo
(hand-verified), every `open()` inside a `with`, no bulk `str(int)` loops,
all 7 `gc.collect()` sites documented and away from int-render bursts,
`ppleval` fed only int-derived strings, no `hex()` anywhere.

Static analysis is out of road. The bug docs' own conclusion applies:
*"validate fixes by soak, not arithmetic."*

### 3. The save-stall UX work is close to exonerated (save_smoke-8)

Standing suspicion was that the 30-31/07 save-stall UX work put allocating
work inside the serialize churn window that the 28/07 250-autosave soak had
validated as straight-line. `debug/save_smoke-8.log` (device, G1) measured
it across three modes:

| mode | bytes/save | in-save collects |
|:--|--:|--:|
| baseline (no checkpoints) | 307,024 | 0 |
| pump (13 checkpoints, no echo) | 307,024 | 0 |
| pump+echo (checkpoint + prompt redraw) | 313,376 | 0 |

13 pump calls cost **zero** bytes. The echo adds ~489 B per redraw
(+6,352 B/save, +2%) and ~80 ms/save. Not what pressures the heap.

Note the harness itself was the reason this went unmeasured for so long: its
`_TRStub` had no `_pump_keyboard`, so `_serialize_world`'s `_pump` stayed
`None` and every checkpoint was skipped. Every save_smoke run before -8 timed
a straight-line save without noticing. The probe now reports `pumps=` and
`echoes=` per save so a silent no-op reads as zeroes instead of passing for a
clean result.

### 4. The actual finding: the save path is a garbage pump with no collector

From save_smoke-8: free memory falls **monotonically** for the whole run and
never recovers once -- 6,167,024 -> 3,205,008 across 9 saves. ~307 KB burned
per save, ~3 MB gone, **zero collects**. A 29,490 B payload costs 307 KB of
heap to produce (~10x amplification).

So the collect is not *in* the save -- it is downstream and unscheduled. The
save path pumps garbage until the heap fills, then an **auto**-collect fires
at whatever arbitrary moment that lands, walking save-shaped small-string
garbage. That is the documented killer verbatim: *"died the moment heap
exhaustion forced the first auto-collect."*

Autosave is `AUTOSAVE_TICKS=4` x `TICK_SECS=30` = **every 2 minutes**. At
307 KB a pop a real session hits exhaustion in roughly 10-20 saves -- 20-40
minutes of play -- then rolls the ~25-30% per-collect death dice. This fits
the crash profile (rare, unreproducible, no command implicated) far better
than any earlier hypothesis, and matches the bug docs' own line that *"the
game's occasional G1 crashes are this bug, rate-limited only by saves being
minutes apart."*

**This is inference, not yet proof.** Phases C and D below are built to
settle it.

### 5. save_smoke-9 (G1, 31/07): not a leak; 5 collect rolls survived clean

`debug/save_smoke-9.log`, run with the real 31/07 32.5 KB save:

- **Phase C: transient garbage, ~100% reclaimed.** One collect returned
  4,351,056 B in 267 ms; free rose above the post-load baseline. Not a
  leak -- the exposure is *when* the collect fires, not lost memory.
- **Phase D: 60 saves, 4 auto-collects, zero deaths.** ~420 KB burned per
  save (bigger save than -8; `ln.room` now dominant at ~970 ms). Every
  auto-collect fired on the 14th save, **always inside `hvset`**, cost
  ~200 ms, restored free to ~6.2 MB with no drift across cycles.
- With phase C's explicit collect that is 5 collects walking save-shaped
  garbage with no death. At the documented 25-30% per-collect rate, clean
  survival odds were 17-24% -- evidence leaning against the hypothesis,
  but not an acquittal (survival does not transfer between layouts).
- Real-play projection: one auto-collect per ~14 autosaves, ~28 min of
  play. Matches the crash cadence.

**Coverage gap found:** back-to-back saves tip the heap over at the same
deterministic spot every cycle (mid-`hvset`), so -9 only ever rolled the
dice there. Real play interleaves ~2 min of gameplay allocation between
autosaves, so the collect can land at ANY allocation site with save
garbage still on the heap. The pump/echo path itself was audited clean of
both bug signatures (no `%`/`.format()`, no bulk `str(int)`; `show_prompt`
is a guaranteed `_PROMPT_CACHE` hit mid-save), and "player typing through
a save" is exactly what pump+echo models -- the gap is collect landing
site, not player activity.

## The prepped probe -- run this next

`debug/save_smoke.py`, staged and ready. Phases run in order; `log()`
rewrites the log file on every call, so everything up to a death survives.

- **A/B** -- the three save modes + payload breakdown. Already answered by
  save_smoke-8; re-run is cheap and re-establishes the baseline on whatever
  heap state the device is in.
- **C: reclaim test.** One explicit `gc.collect()`, measured, logging free
  before and after. Answers the question inference cannot: is the 307 KB
  *transient garbage* (a collect hands it back -- bad, but the heap
  recovers) or *retained* (a leak -- the game dies of exhaustion eventually
  regardless of the GC bug). **Read this before anything else; if it is a
  leak the whole framing changes.** Doubles as a probe in its own right: an
  explicit collect right after a churn burst is the documented worst-case
  roll, so a death can land right here.
- **D: drive to exhaustion.** Saves flat out in pump+echo (the real game's
  shape) until `TARGET_COLLECTS = 5` auto-collects have been survived or
  `MAX_DRIVE_SAVES = 60` is hit. An auto-collect shows as free *rising*,
  either between saves or across marks within one. Each is a death roll at
  ~25-30% in probe conditions, so 5 is >80% odds of a kill if the crash is
  this bug. **A death in phase D is the crash reproduced on the bench.**
  Since -9: each save is preceded by a gameplay-shaped churn gap
  (`(i % 8) * CHURN_STEP` bytes of combat-message-style small strings) so
  the tip-over collect lands at a different site each cycle instead of
  always mid-`hvset` -- including mid-churn, the real-play scenario -9
  never rolled. A churn-site death is the strongest possible signal.

Supporting change: `_SAVE_TIMING` marks are now `(segment, ms, free)`
triples, `free` being `gc.mem_free()` at that boundary. Free memory falls
monotonically as the payload builds, so a rise between consecutive marks can
only mean a collect fired. Desktop CPython has no `mem_free`, so `free` reads
0 there -- **only a device run answers anything.**

### Reading the results

| Outcome | Meaning |
|:--|:--|
| Phase C reclaims most of the 307 KB | Transient garbage. Heap recovers; the exposure is *when* the collect fires, not that memory is lost. Attack per-save allocation and/or control when the collect happens. |
| Phase C reclaims little | Retained -- a real leak. Different, more urgent problem; re-scope before touching the GC angle. |
| Phase D dies / stalls / throws an impossible `TypeError` | Crash reproduced. Record which, per the manifestation spectrum in the bug docs -- it discriminates where the stale write landed. |
| Phase D survives 5 auto-collects clean | Does **not** acquit. Per the bug docs, *"survival evidence does not transfer between layouts; only deaths/corruptions are informative."* Re-run on a different heap history before drawing anything. |

### Running it

The device bundle is at `debug/transfer/Python debug.hpappdir/`, but
**`debug/transfer/` is gitignored -- it will not be on the new workstation.**
Rebuild it there:

1. Copy the `Python debug.hpappdir` bundle from the device (or an existing
   backup). Never overwrite the binary `.hpapp` / `.hpappnote` /
   `.hpappprgm` files -- payload only.
2. Copy `src/*.py` **except `src/primesud.py`**, plus `src/*.txt` and
   `src/*.idx`, plus `debug/save_smoke.py` into it.
3. Copy the real `primesud.sav` in as read-only input. The probe redirects
   `SAVE_VAR` to `smoketest` before `load_world` and `SAVE_FILE` to
   `save_smoke.sav` after, so the real slot is never written.
4. Transfer via Connectivity Kit, run, retrieve `save_smoke.log`, commit it
   as `debug/save_smoke-10.log`.

(Bundle on this workstation refreshed 31/07 against the churn-gap probe;
`primesud.sav` inside it is the fresh 31/07 32.5 KB copy from the repo
root.)

A correctly prepped bundle holds 54 `.py` (53 from `src/` + `save_smoke.py`,
no `primesud.py`), the 3 `.hpapp*` binaries, `primesud.sav`, and the data
files `commands.txt` `help.txt` `help.idx` `mobs.idx` `music.txt`
`music.idx` `objs.idx` `paths.idx` `socials.txt` `socials.idx` plus every
`area_*.txt`. Verify from the repo root before transferring:

```sh
A="debug/transfer/Python debug.hpappdir"
# every shipped .py identical to src/, and nothing self-running but the probe
for f in "$A"/*.py; do b=$(basename "$f"); [ -f "src/$b" ] && \
  { cmp -s "$f" "src/$b" || echo "STALE $b"; }; done
grep -ln "^PrimeSud()\|^main()" "$A"/*.py   # must print only save_smoke.py
ls "$A/primesud.py"                          # must be "No such file"
```

**`src/primesud.py` must not ship in this bundle.** It ends in
`PrimeSud().run()`, and the Prime auto-imports every `.py` in an appdir, so
it would launch the real game alongside the probe -- and the game's quit path
saves to the *real* slot, outside the probe's redirect. It was found in the
bundle on 31/07 and removed; `save_smoke.py` must be the only self-running
module present.

## Do not do these without measuring first

- **Do not add a `gc.collect()` to the save path.** The save's opening
  `gc_collect()` was removed precisely because it was a guaranteed
  worst-case roll per save; an earlier "may be load-bearing protection"
  guess in the bug docs was backwards.
- **Do not treat a clean run as an acquittal.** See the table above.
- `util.num_str`'s `_NCACHE.clear()` at >4096 entries dumps 4096 small
  strings at once and can land mid-save. Right *shape*, but the strings are
  `int_str` concat -- the validated fix path, not the convicted `str(int)`
  one. Weaker than it first looks; logged in TODO.md at that weight.

## Repo state

Branch `dev`, clean, `1467 passed`, `tools/check_ascii_py.py` OK.

```
e622cf5 debug(save): free-heap marks + pump/echo mode split in save_smoke
8fb3b34 'recommend' proposal            <- yours, unrelated
7cdb412 docs(todo): record save path lost its soak cover
a2a14fe fix(combat): consider picker gates on can_see
dad20d6 chore(tools): checker flags hoisted format strings
1885284 fix(scan): drop live %-format from distance strings
```

`a2a14fe` is an unrelated side bug fixed in the same session: the no-arg
`consider` picker built its menu straight from `rs["mobs"]`, so a
hidden/invis mob the player had no detect for was still offered by name.
Same class of miss as `7e1c77a`, which gated the get/drop/loot pickers and
`scan` but not this one. (Watch the key names there: char affects use
`invisible`, item extra_flags use `invis` -- swapping them makes a
visibility test pass vacuously against unfixed code.)

Untracked and left alone: `primesud_backup.sav` at the repo root.
