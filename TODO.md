# TODO

Loose ends that don't belong in a specific plan file.

## Roadmap (23/07/2026)

Engine 1.0 was tagged as `v1.0.0` on 23/07/2026. Content track is now open:

1. Keep engine parity fixes auditable against the `v1.0.0` baseline.
2. Release new classes, areas, and quests as content versions on top of that
   stable engine.

## Combat

(nothing outstanding)

## Items

- Invert control in the item accessors, retiring the `snap` marker.
  `world.item_tpl(obj)` currently answers "does this instance still need its
  template?" from an explicit marker key that `item.snapshot_item` writes last.
  The drift-free shape is `item_*(obj)` fetching the template itself, lazily,
  only when the field is missing -- then completeness is emergent and there is
  no marker to keep in sync, and no `_SNAP_FIELDS` list to forget to extend
  when a new template field appears. Costs all 14 accessor signatures in
  `item.py` plus every caller that threads `tpl` for other reasons, so it was
  deliberately deferred. `item_tpl` is the seam to refactor through.
  Note: inverting control replaces the *marker*, not the eviction-time copy --
  a lazy per-field template fetch on a gone template is exactly the area drag
  this work removes, so `snapshot_item` (or equivalent materialization before
  the template dies) stays either way.

- WIP review of the snapshot/`item_tpl` sweep (29/07/2026). Mechanism is
  sound (eviction-time `_snapshot_foreign_objs` walk + `item_tpl` seam;
  covered by `test_snapshots_objects_held_outside_the_area`), but the sweep
  is incomplete and the save format undoes it. In priority order:
  1. `can_see_obj` (handler.py:1379) still reads `ITEM_DEFS[vnum]`
     unconditionally. It gates every look/list/get/inventory scan, so any
     snapshotted foreign item still drags its area back on the very paths the
     snapshot exists for. Convert to `item_tpl(obj)` (handler already imports
     it). Highest value single fix.
  2. `get_obj_list` (item.py:646) does `templates[vnum]` per candidate --
     every keyword lookup over inv/room (`get`/`drop`/`wear`/`give` ...)
     drags areas the same way. Use `item_tpl(item)` for dict items; the
     `templates` param is then only needed for plain-int room/mob vnums.
  3. Save round-trip loses the snapshot ("first load" case).
     `serialize_item_token` stores mutated fields only; `SNAP_KEY` and the
     copied template fields are dropped, so restored foreign gear is bare
     again and the first post-login scan drags each owning area in (multi-
     second stalls; New Thalos alone is ~10s). It self-heals only after a
     full load->evict cycle re-snapshots. Proposal: persist the snapshot in
     the v2 token (`sn:1` plus the copied scalars/strings not already
     serialized); re-snapshotting at restore is impossible by definition
     (the template's area is exactly what we refuse to load). Decide save-
     size budget first: `description` is the only big field -- consider
     dropping it from `_SNAP_FIELDS`/lookup fallback for saved gear.
  4. Serialization side effect today: snapshot fields sit in the instance
     dict, so `serialize_item_token` now emits `lv:`/`ef:`/`wf:`/`cf:`/`ty:`
     for every snapshotted item -- save bloat plus permanent instance
     overrides after reload (level/type pinned even if area data is later
     rebalanced). Resolving 3 with a distinct `sn:` token also fixes the
     provenance ambiguity here.
  5. Remaining direct `ITEM_DEFS[...]` reads worth converting: shop.py:158
     and shop.py:472 (keeper-stock browse/list; cross-area stock templates
     exist) and info.py:509 (look extra-descs sweep over room+inv). Safe to
     leave: combat.py:2488 (pinned limbo body parts), mob.py:584 +
     mob.py:518 (own-area reset), quest.py:917 (quest-area vnum),
     debug.py (tooling).
  6. `snapshot_item` copies dicts but aliases lists (`values`,
     `extra_descs`, `stat_bonuses`, `flag_affects`, `spells`). Harmless
     against the template (it is discarded at eviction) but sibling
     snapshotted instances of one vnum share the list objects; nothing
     mutates them in place today. Cheap hedge while the marker design
     stands: copy lists too.
  7. `_QUEST_VNUM_LO/HI` (quest.py) hardcodes the quest area's 200-249
     range, duplicating `world._AREA_FILES`. Derive it at import or add a
     drift assert next to the existing `AREA_LEVELS` cross-check.

- `parse_item_token` nested-`co:` mis-split (found 29/07/2026 during
  snapshot work). Nested container contents are `^`-joined and re-split
  with a flat `inner.split("^")` -- no bracket-depth tracking -- so a
  container holding >=2 children where one child has its own nested
  `co:[...]` contents would slice the inner item's `^` separators across
  siblings. Save-format-affecting; fix in `parse_item_token` itself.
  NOTE: `world._snap_token_vnums` deliberately mirrors the flat split so
  the eviction/save walkers agree with the real parser -- update it in
  the same commit when fixing, or the walkers drift.

## Magic

(nothing outstanding)

## Classes

(nothing outstanding)

## Commands

(nothing outstanding)

## Housing

(nothing outstanding)

## Area data

(nothing outstanding)

## Tests

- Fold `world.ITEM_SNAPSHOTS` save/restore into the shared `fresh_world`
  fixture (tests/conftest.py). Currently guarded per-module: autouse
  clearing fixture in test_area_eviction.py, `reset_lazy()` in
  test_snapshot_codec.py. Fine today, but any new module touching the
  registry silently leaks entries between tests until this lands.

## Platform

- Save optimisation (probe data in docs/PERFORMANCE.md sec. Save path):
  add debug-gated `ticks()` instrumentation to
  `_serialize_world` ("save" DBG channel); the cache conversion is
  also the alloc diet, and dropping the up-front `gc_collect()`
  returns 78-198 ms. HVars and file I/O measured negligible.
- 6mb-vs-8mb app scaffolding question is closed: 8 MB is fully backable
  and healthy on the G1 (mem_soak); Connectivity Kit needs the Python
  app closed (reset) regardless of heap size.
