# TODO

Loose ends that don't belong in a specific plan file. Sections come and go
with their items; engine 1.0 is tagged `v1.0.0` (23/07/2026) and the content
track is open on top of it.

## G1 crash watch (31/07/2026, dormant)

The unexplained 31/07 hard crash was investigated to exhaustion
(docs/PRIME_FIRMWARE_BUGS.md sec. Remediation status, 31 Jul follow-up):
the static sweep found and fixed one live `%` (scan.py -- real latent
bug, not this crash's cause); save-path heap churn benched fully
transient and collect-safe 12/12 (`debug/save_smoke-8..-10.log`); the
pump/echo path audited clean of both bug shapes. The
auto-collect-over-save-garbage hypothesis is downgraded to residual, and
a threshold-gated post-save collect now pins reclaim to the
bench-validated site anyway (docs/PERFORMANCE.md sec. Save-path heap
churn). Nothing left to chase actively.

- If a crash recurs, record the symptom FIRST: hard reset vs
  uninterruptible stall vs an impossible `TypeError` discriminates the
  bug family (docs/PRIME_FIRMWARE_BUGS.md sec. Manifestation spectrum).
- Second-order residual: `util.num_str`'s `_NCACHE.clear()` at >4096
  dumps 4096 small strings at once and can land mid-save. Right shape,
  acquitted creation path (`int_str` concat, not `str(int)`).
  Downgraded to low 01/08: the post-sweep soak rolled the
  clear-and-rebuild 20 times with an explicit collect after each, all
  clean (`debug/str_soak-1.log` phase B).
- 01/08 update: the src-wide bare-`str()` sweep (0de25e7) removed the
  remaining `str(int)`-in-loop sites the static audits had missed (route
  RLE builder in info.py, mobprog trace) -- a plausible retro-fix for
  this crash. Device heap soak with the sweep applied passed same day:
  70 clean collects, canaries clean (docs/PRIME_FIRMWARE_BUGS.md sec.
  Remediation status, 01 Aug follow-up).

## Device checks pending (11/08/2026)

- Confirm GROB memory is separate from Python heap: `gc.mem_free()` before/after the scrollback `dimgrob` calls (tml_prime.py `__init__`) should be ~unchanged. Validates the 250->500 `SCROLLBACK_SIZE` bump (~3.2MB of history pixels at 16bpp); note result in docs/PERFORMANCE.md.
- Bank reopening + remort-bank-gold (12/08/2026): load an existing G1 save against the bumped `CONTENT_REVISION` (buffered save deltas), then walk Temple Square -> e -> u, `bank deposit/withdraw`, and a remort with split purse/bank funds.

## Counted-target residue (12/08/2026)

- `get_obj_here` still restarts its `N.` counter per list (room, then
  inventory, then worn) -- same family as the do_look counter unified in
  docs/FIXES.md ("do_look N.-prefix counter"), reachable via
  `look in N.<kw>`, `get`, `put`, `open`, etc. Blast radius is every
  object-resolving command, so it wants its own decision pass: unify to
  one cumulative sequence (and pick the scan order), or keep upstream
  per-list semantics and document.

## Input-lag stream leftovers (30/07/2026, measure-first)

Low-priority residue from the closed input-lag stream (history:
docs/PERFORMANCE.md sec. Input-lag phase benchmark; decisions in
DESIGN.md sec. Input responsiveness). Both need in-context device
profiling before any code:

- Attack-chain cost (~245 ms of the ~355 ms 1-mob round) -- needs
  per-hit profiling to subdivide; diminishing returns expected.
- `info._route` was ~4.0s per call on-device (str_soak-1 phase A: 50
  routes ~201.5s per iteration, near-constant across source rooms -- so
  dominated by the fixed per-call cost: `_parse_index` re-reading and
  re-parsing paths.idx every call, not Dijkstra). Fixed 01/08:
  `_parse_index` now caches `(segs, xedges)` at module level keyed by
  filename. Pending device re-measure: post-cache `_route` latency and
  the resident-dict footprint (paths.idx is 18KB/873 lines source;
  expect tens of KB against ~7MB free).
- `mobile_update` 5s full-world scan -- its "~100 ms class" estimate
  used the scan-shape reasoning run 6 disproved (violence scan was
  ~6-20 ms in-context); likely single-digit ms, likely a dead end. Not
  index-shaped anyway (wander/despawn needs all NPCs).
- Save live-data serialization (post-diet residue, save_smoke-7): with
  areas resident, ln.room ~270 ms (per-item serialize_item_token) +
  ln.mob ~140 ms (live NPC walk) dominate the ~0.83 s save. Caching
  needs dirty flags at scattered mutation sites (pickup/drop/loot/
  decay/resets; wander) -- only worth it if the save-stall UX (segment
  pumps + live echo preview, docs/PRIME_UX.md sec. Autosave) ever stops
  being enough.
