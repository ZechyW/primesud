# TODO

Loose ends that don't belong in a specific plan file. Sections come and go
with their items; engine 1.0 is tagged `v1.0.0` (23/07/2026) and the content
track is open on top of it.

## Items

- Item snapshot device gates still to measure on hardware before the next
  content release (design in DESIGN.md sec. Item template snapshots;
  startup owner-load and save/readback gates already passed 29/07/2026,
  docs/PERFORMANCE.md sec. Save path): heap after travel/eviction cycles;
  one content-revision mismatch causing exactly one corrective load;
  snapshot obj program firing from an unloaded owner. Probe ready:
  debug/snapshot_gates.py (all gates pass on desktop 30/07/2026; swap it
  in for save_smoke.py in the debug appdir -- only one self-running .py).
  If save size bites, first lever is field-name tags inside the snapshot
  codec -- never silently dropping `description`/`extra_descs`.
