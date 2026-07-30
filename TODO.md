# TODO

Loose ends that don't belong in a specific plan file. Sections come and go
with their items; engine 1.0 is tagged `v1.0.0` (23/07/2026) and the content
track is open on top of it.

## Save path lost its soak cover (31/07/2026)

An unexplained G1 crash on 31/07 prompted a full firmware-bug sweep
(docs/PRIME_FIRMWARE_BUGS.md sec. Remediation status). The sweep found
and fixed one live `%` in scan.py, but the player was nowhere near a
`scan`, so that fix does not explain the crash.

Standing suspicion: the 250-autosave clean soak (28/07) validated a
straight-line save. Since then `_serialize_world` gained 13
`_pump(KEY_COMMANDS)` checkpoints, and `SAVE_ECHO_HOOK` calls
`_save_echo` -> `peek_queued_events()` (list alloc) + `show_prompt`
(slice + concat + native `set_status`) *inside* the serialize churn
window. No convicted shape there (no `str(int)`, no `%`; slices and
concat are both acquitted), but it adds allocation pressure to a path
that was deliberately tuned to take zero collects, and heap exhaustion
forcing an *auto*-collect mid-churn is the documented killer.

- Re-soak the current save path with keys held through the saves, so
  the echo preview is actually exercised (`debug/save_smoke.py` needs a
  typing variant). Static analysis is out of road here -- the bug docs'
  own conclusion is "validate fixes by soak, not arithmetic".
- Second-order: `util.num_str`'s `_NCACHE.clear()` at >4096 dumps 4096
  small strings at once and can land mid-save. Right shape, acquitted
  creation path (`int_str` concat, not `str(int)`). Low-moderate.
- If it recurs, record the symptom before anything else: hard reset vs
  uninterruptible stall vs an impossible `TypeError` discriminates
  which bug family is in play (sec. Manifestation spectrum).

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
  decay/resets; wander) -- only worth it if the save-stall UX (segment
  pumps + live echo preview, docs/PRIME_UX.md sec. Autosave) ever stops
  being enough.
