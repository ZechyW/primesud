# TODO

Loose ends that don't belong in a specific plan file. Sections come and go
with their items; engine 1.0 is tagged `v1.0.0` (23/07/2026) and the content
track is open on top of it.

## Input-lag stream leftovers (30/07/2026, measure-first)

Low-priority residue from the closed input-lag stream (history:
docs/PERFORMANCE.md sec. Input-lag phase benchmark; decisions in
DESIGN.md sec. Input responsiveness). Both need in-context device
profiling before any code:

- Attack-chain cost (~245 ms of the ~355 ms 1-mob round) -- needs
  per-hit profiling to subdivide; diminishing returns expected.
- `mobile_update` 5s full-world scan -- its "~100 ms class" estimate
  used the scan-shape reasoning run 6 disproved (violence scan was
  ~6-20 ms in-context); likely single-digit ms, likely a dead end. Not
  index-shaped anyway (wander/despawn needs all NPCs).
- Save live-data serialization (post-diet residue, save_smoke-7): with
  areas resident, ln.room ~270 ms (per-item serialize_item_token) +
  ln.mob ~140 ms (live NPC walk) dominate the ~0.83 s save. Caching
  needs dirty flags at scattered mutation sites (pickup/drop/loot/
  decay/resets; wander) -- only worth it if the indicator+pump UX ever
  stops being enough.
