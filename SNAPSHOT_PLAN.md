# Item Template Snapshot Plan

Status: approved 29/07/2026 with amendments (recorded inline below):

1. Single global content digest, not per-area `AREA_ITEM_REVISIONS`.
2. Orphan machinery reduced to minimum viable (retain + one-time
   revalidation stamp; no retry ladder).
3. Save-size risk accepted up front; revisit via device gate 4 only if it
   bites. Field-name tags remain the first fallback.
4. Sequencing: `can_see_obj` and `get_obj_list` hot-path conversions land
   immediately as standalone fixes, ahead of Phase A.

Date: 29/07/2026

## Goal

Keep live item operations from loading an item's template-owning area when the
item survives outside that area, including across save/load.

Examples:

- player inventory and equipment;
- contents nested inside player-held or dropped containers;
- objects dropped into another loaded area;
- objects buffered in `_pending_room_items` for another unloaded area;
- foreign objects held by surviving NPCs or shopkeepers.

The solution must preserve real per-instance mutations, adopt updated area
template data after a content change, avoid duplicate snapshots for repeated
instances of one VNUM, and remove snapshots after no surviving object needs
them.

## Current WIP assessment

Commit `05efd79` proves the important runtime seam:

- `_snapshot_foreign_objs` finds objects that outlive their template area;
- `item_tpl(obj)` can answer without touching `ITEM_DEFS`;
- `test_snapshots_objects_held_outside_the_area` proves the basic eviction
  case.

The current representation is not the target design. `snapshot_item` flattens
template fields into each instance and sets `SNAP_KEY`. This causes four
problems:

1. Template data and real instance overrides become indistinguishable.
2. `serialize_item_token` accidentally saves copied `level`, `type`, and flag
   fields as permanent instance mutations.
3. Every instance duplicates template dictionary slots.
4. Completeness depends on `SNAP_KEY` and the manually maintained
   `_SNAP_FIELDS` union.

The WIP also misses hot paths that still force lazy loads:

- `handler.can_see_obj`;
- `item.get_obj_list`;
- `handler._obj_keywords` and `_obj_short`, whose `vnum in ITEM_DEFS`
  membership check itself loads the area;
- `info._look_scan_items`;
- the remaining shop lookups over keeper stock.

The existing WIP snapshot/save behavior is unreleased. It does not require a
compatibility layer. Legitimate item-instance token fields remain unchanged;
only accidental template flattening is removed.

## Decisions

### 1. Shared registry, not per-instance snapshots

Add one runtime registry in `world.py`:

```python
ITEM_SNAPSHOTS = {
    # item_vnum: (validated_revision, template_dict, objprog_dict)
}
```

(Amended: no `home_tag` slot -- the owning tag is derivable from
`_VNUM_RANGES` when needed, and the global digest removes per-area
validation.)

One VNUM has one snapshot regardless of instance count. Item instances retain
only their existing mutable/runtime fields and VNUM.

Template dictionaries and their child values are immutable. A shallow
`dict(tpl)` is therefore enough: copy-on-write item helpers already copy flags
before mutation, and the separate registry is never returned as mutable
instance state.

Do not add snapshot references or markers to individual item dictionaries.
The VNUM already provides the registry key.

### 2. Keep `item_tpl`; do not invert all accessor signatures

`item_tpl(obj)` remains the single lookup seam:

1. Return `ITEM_DEFS._data[vnum]` when resident.
2. Return a current registry snapshot when available.
3. Otherwise use `ITEM_DEFS[vnum]`, intentionally triggering the normal lazy
   load.

Resident area data always wins. This lets a pre-existing item adopt updated
template-backed stats as soon as its home area loads. Genuine instance fields
continue to win through the existing `item_*` accessors.

Accessor inversion would still leave direct template consumers such as
`short_descr`, `armor`, `weight`, `extra_descs`, and `obj_triggers`, while
adding repeated lookups and changing every caller that currently fetches one
template and uses several fields. The registry removes the marker/completeness
problem without that refactor.

`item_tpl_get(obj)` follows the same order but returns `None` for an unknown
VNUM after exhausting the orphan fallback described below.

### 3. Snapshot all foreign survivors

When area A is evicted, snapshot every A-owned item that will remain live
outside A:

- player inventory/equipment and nested contents;
- inventory/equipment of NPCs that survive the eviction;
- items in loaded rooms outside A;
- nested contents of those items;
- items buffered in `_pending_room_items` for rooms outside A.

Do not snapshot:

- items in A's own rooms, because those rooms and items are serialized and
  later reload alongside A's templates;
- inventory of NPCs that the same eviction deletes;
- transient objects already being extracted.

This scope prevents all foreign-item template cascades, not only startup loads
from player gear.

### 4. Save snapshots separately

Keep `serialize_item_token` and `parse_item_token` limited to instance state.
Add one save line per required template VNUM:

```text
it.<vnum>=<revision>|<encoded-record>
```

`encoded-record` contains:

- the full item template dictionary;
- object-program source strings referenced by its `obj_triggers`.

The section is deduplicated by VNUM. It is additive, so it does not require a
`SAVE_VERSION` bump: old saves have no `it.*` lines and take the existing
one-time lazy-load path; unknown lines are already ignored by older parsers.

On load, parse `it.*` records into `ITEM_SNAPSHOTS`. Item-token parsing itself
needs no template, so line order is irrelevant before `load_world` returns and
`reset_char` starts reading equipped items.

### 5. Use a small typed codec

Do not use `eval`, `repr` parsing, JSON, or a new dependency. HP Prime lacks a
verified JSON module, and save data must not become executable code.

Add a private snapshot codec supporting only types present in generated item
templates and object programs:

- `None`;
- `bool`;
- `int`;
- `str`;
- `list`;
- `tuple`;
- dictionaries with supported keys and values.

Use a one-character type tag, element count for containers, and length-prefixed
strings. Replace raw backslash, `~`, `"`, newline, and carriage return with
two-character backslash sequences before counting string length (amended:
REPLACED, not merely backslash-prefixed -- `load_world` splits the payload
with a naive `data.split("~")` and `hvars_set` embeds it in a PPL
`HVars("..."):="..."` string literal where backslash is not an escape, so
the unsafe bytes must be physically absent; real template descriptions
contain quotes and newlines).

Sort dictionary keys during encoding for deterministic saves. Check `bool`
before `int`, because Python models booleans as integers. Build integer text
through `util.sstr`; never bulk-render integers with plain `str`.

Malformed or unsupported snapshot records are ignored individually. The item
then falls back to its normal area load. Corrupt optional cache data must not
make the character save unloadable.

Desktop tests must round-trip every generated `OBJECTS` template plus every
referenced `OBJPROGS` string. This replaces `_SNAP_FIELDS` as the drift guard:
a newly introduced unsupported value type fails the all-area codec test
instead of silently disappearing.

## Runtime lifecycle

### Lookup

`item_tpl` resolves a dict item or plain VNUM without a `LazyDict` membership
test:

```text
resident ITEM_DEFS._data
    then current ITEM_SNAPSHOTS entry
    then lazy ITEM_DEFS lookup
    then orphan snapshot fallback if the current area no longer defines VNUM
```

A snapshot is current when its `validated_revision` equals the generated
global `CONTENT_REVISION` digest (amended: single global digest, see
Template drift below).

### Area eviction

Before deleting A's item definitions:

1. Determine which characters will survive this eviction.
2. Walk survivor inventory/equipment, loaded foreign rooms, and deferred
   foreign room tokens recursively.
3. Collect distinct A-owned item VNUMs.
4. Replace A's registry entries with an exact snapshot of those VNUMs from
   resident `ITEM_DEFS._data`.
5. Include every object program referenced by each template.
6. Remove obsolete A registry entries not in the collected set.
7. Delete A's definitions and program tables as today.

The existing linear world walk remains appropriate. Eviction happens on area
movement, not each pulse, and the current measured world has roughly 787 live
objects. Do not add ownership indices or mutation-path reference counts unless
profiling shows this cold scan is material.

### Area load

Fresh resident definitions take priority immediately. Once an area has loaded
successfully:

- remove registry entries for VNUMs now present in `ITEM_DEFS._data`;
- retain an orphan entry when the new area no longer contains that VNUM;
- let the next eviction rebuild any still-required snapshots from current
  resident definitions.

The eviction collector must inspect `_pending_room_items`; otherwise an item
buffered in unloaded room B can lose its A snapshot after A loads and evicts
again.

### Serialization

Recompute the persisted snapshot set instead of serializing the whole runtime
registry:

- every player inventory/equipment VNUM, recursively;
- every foreign item VNUM in a loaded saved room, recursively;
- every foreign item VNUM in `_pending_room_items`, recursively.

Player items are always included. Their count is bounded and this guarantees
that `reset_char` and the first inventory/look scan do not load souvenir
areas. Room items are included only when their template owner differs from the
room's area; own-area items reload with their room.

NPC inventories are not persisted by the existing save format and therefore
do not add save-section records unless the same VNUM is also required by a
persisted object.

For each required VNUM:

- encode the resident template when present;
- otherwise encode the current registry snapshot;
- preserve a validated orphan snapshot when the current resident area no
  longer defines the VNUM;
- if neither source exists, omit the record and retain normal lazy-load
  behavior.

Build records transiently when their area is resident rather than retaining a
second registry copy solely for saving.

### Runtime pruning

At eviction, prune registry entries for the victim area exactly as described
above.

At save, run a cold mark/sweep over all live items and deferred room tokens:

- runtime marks include player, surviving NPC/shop inventories, loaded rooms,
  and `_pending_room_items`;
- save marks are the persisted subset described above;
- remove registry entries that have no runtime mark and whose owner area is
  unloaded;
- write only save-marked entries.

Do not maintain incremental reference counts across get/drop/give/sell,
extraction, resets, programs, container moves, and room eviction. A missed
mutation path would leak or prematurely delete snapshots; the existing cold
walk is smaller and safer.

### Deferred-token VNUM scan

Add a lightweight item-token walker that collects VNUMs, including nested
`co:[...]` contents, without constructing full item dictionaries or consulting
templates. Reuse the current item-token escaping/bracket rules.

Use it for `_pending_room_items` during eviction and save collection. Avoid
calling `parse_item_token` across all deferred rooms merely to discover VNUMs:
that creates unnecessary dict/list churn on the device's constrained heap.

## Template drift

Snapshots are caches, not permanent historical copies. Current area content is
authoritative for fields that remain template-backed.

Extend `tools/gen_area_adj.py` to generate (amended: one global digest, not
per-area):

```python
CONTENT_REVISION = "<stable digest>"
```

The digest covers every area's complete `OBJECTS` mapping and `OBJPROGS`
mapping in a deterministic canonical order. Use desktop `hashlib.sha256` and
store a short hex prefix sufficient for change detection. Runtime performs
only string comparison; it never imports a hashing module.

Global granularity is deliberate (amended from per-area): content changes
ship with app updates, so whole-cache invalidation costs one corrective
load per snapshot owner after an update -- exactly today's behavior -- and
in exchange there is no 50-entry revision table, no per-area digesting, and
no `home_tag` bookkeeping. Revisit per-area granularity only if content
updates become frequent enough that whole-cache invalidation stings.

On revision mismatch:

1. Ignore the stale snapshot for normal lookup.
2. Load the owning area once through `ITEM_DEFS[vnum]`.
3. Use the current resident template.
4. Refresh the saved record on the next save or eviction.

This intentionally permits a one-time corrective load after a content update.
Avoiding that load would require a second current-template catalog and defeat
the memory goal.

Only template-backed values drift. Existing instance state keeps its current
semantics: for example, mutated flags, quest-gear level, remaining charges,
liquid amount, poison state, and `create_object`'s instance `cost` continue to
override the template.

### Removed templates

If the revision changed and the VNUM no longer exists (amended: minimum
viable orphan handling):

- retain the saved snapshot as an orphan so a valid saved item does not break
  or disappear;
- when the corrective load confirms the owning area no longer defines the
  VNUM, restamp the registry entry with the current `CONTENT_REVISION` (one
  assignment) so subsequent sessions skip the pointless reload;
- no further retry ladder. A later content change simply repeats the single
  corrective load once.

An orphan continues using its saved object-program source, if any, until the
item is extracted. Once no live or deferred object references it, mark/sweep
drops it.

## Object programs

`obj_triggers` alone is insufficient for full decoupling. The trigger tuple
contains a program VNUM, while executable source currently lives in
`world.OBJPROGS` and is evicted with the area.

Each item snapshot therefore includes only the `OBJPROGS` entries referenced
by that template's `obj_triggers`. Add one lookup seam used by
`mobprog._run_oprog`:

1. resident `world.OBJPROGS`;
2. the item's current snapshot program map;
3. existing missing-program debug behavior.

Revision validation covers both template and program source. Current data has
only one object template with an object program, so embedding referenced code
per template is smaller than introducing a second global snapshot registry.

## Consumer sweep

After the registry exists, route instance-aware reads through `item_tpl` or
`item_tpl_get`:

- `handler.can_see_obj` (landed early, pre-Phase A);
- `handler._obj_keywords` and `_obj_short` without `in ITEM_DEFS`;
- `item.get_obj_list` for dict instances, retaining its `templates` argument
  for plain VNUMs (landed early, pre-Phase A);
- `info._look_scan_items`;
- `shop._get_obj_keeper`;
- `shop.do_list`;
- any other direct `ITEM_DEFS[obj_vnum(obj)]` read over player, NPC, shop, or
  room instances.

Direct template reads remain appropriate for:

- `create_object(vnum)`, which intentionally needs a resident template;
- reset construction in `mob.py`;
- quest-template generation constrained to the quest-area VNUM range;
- pinned limbo body-part creation;
- explicit debug/admin VNUM lookups.

Audit `ITEM_DEFS[...]`, `.get`, and `vnum in ITEM_DEFS`: all three trigger
`LazyDict` loading.

## Save compatibility and migration

### Existing pre-snapshot saves

They contain no `it.*` section. First startup may load item-owning areas as it
does today. The next successful save writes snapshots, so later startups avoid
those loads.

It is impossible to reconstruct missing template data without reading the
area at least once. Do not add a fake migration that guesses fields.

### Saves produced by the unreleased flat WIP

The WIP did not save `SNAP_KEY`, so accidentally copied fields are
indistinguishable from legitimate instance overrides after reload. No safe
automatic normalization exists.

The current workspace `primesud.sav` remains sparse and is suitable for
migration.
If a private save was written after flat snapshot fields had been emitted,
restore its pre-WIP backup. Do not add permanent compatibility complexity for
an unreleased ambiguous format.

### Format version

Do not bump `SAVE_VERSION` for additive `it.*` lines. Bump only if the existing
item-instance token meaning changes, which this plan avoids.

## Implementation phases

### Phase A - Registry and codec

1. Add `ITEM_SNAPSHOTS` and clear it in `reset_lazy`.
2. Add typed snapshot encode/decode helpers.
3. Add global `CONTENT_REVISION` generation to `tools/gen_area_adj.py`.
4. Add all-area codec/revision tests.

No consumer behavior changes in this phase.

### Phase B - Lookup seam

1. Replace `SNAP_KEY`, `_SNAP_FIELDS`, and flat `snapshot_item`.
2. Implement resident/snapshot/lazy/orphan ordering in `item_tpl` and
   `item_tpl_get`.
3. Keep existing accessor signatures.
4. Add lookup-order and revision-drift tests.

### Phase C - Eviction collection

1. Replace `_snapshot_foreign_objs` with distinct-VNUM registry
   materialization.
2. Filter characters deleted by the same eviction.
3. Include loaded foreign rooms, nested contents, and deferred room tokens.
4. Capture referenced object programs.
5. Prune obsolete victim-area records.

### Phase D - Save/load

1. Build runtime/save mark sets.
2. Write deduplicated `it.*` lines.
3. Load valid records without touching area definitions.
4. Ignore malformed records individually.
5. Preserve current instance-token behavior.
6. Cover primary and manual-backup save paths through their shared
   `_serialize_world` seam.

### Phase E - Consumer sweep

Convert the hot instance paths listed above and add an end-to-end assertion
that ordinary operations over restored snapshots leave the owner areas
unloaded.

### Phase F - Object programs and cleanup

1. Add snapshot program lookup to `_run_oprog`.
2. Remove WIP marker/field-list comments and obsolete TODO review text.
3. Record the settled design in `DESIGN.md`.
4. Update `docs/AREA_FILES.md` for generated revisions and saved object-program
   behavior.
5. Delete this completed plan after durable decisions are harvested, per
   project convention.

## Tests

Minimum desktop coverage:

### Codec

- every generated item template round-trips exactly;
- referenced object-program source round-trips exactly;
- deterministic output across repeated encodes;
- no encoded record contains raw `~` or `"`;
- nested lists, tuples, dictionaries, negative integers, booleans, backslashes,
  and delimiter characters round-trip;
- malformed record is ignored without losing the item/save;
- unsupported generated type fails loudly in the all-area test.

### Registry lookup

- resident template wins over snapshot;
- current snapshot prevents a lazy load;
- missing snapshot loads exactly one owning area;
- stale revision loads current area and uses updated stats;
- genuine instance override still wins after drift;
- removed VNUM uses orphan snapshot;
- later revision change retries orphan resolution.

### Eviction

- player inventory and equipment survive without owner reload;
- nested contents survive;
- foreign loaded-room item survives;
- surviving NPC/shop inventory survives;
- items on deleted NPCs do not leave snapshots;
- own-area room items do not get snapshots;
- deferred foreign-room tokens retain snapshots;
- loading and re-evicting an owner while host room remains deferred retains
  the required snapshot;
- repeated instances of one VNUM create one registry entry;
- extracted last instance is pruned at the next cold sweep.

### Save/load

- player snapshots round-trip through `p.inv` and `p.eq`;
- loaded and deferred foreign-room snapshots round-trip;
- own-area room items do not bloat the snapshot section;
- repeated VNUMs produce one `it.*` line;
- pending room deltas remain byte-for-byte valid;
- old save without `it.*` loads normally;
- re-save of old save adds snapshots;
- manual backup uses the same snapshot section;
- snapshot program fires while owner area remains unloaded.

### End to end

Restore a player carrying gear from several unloaded areas, then run:

- `reset_char`;
- `can_see_obj`;
- inventory/name lookup through `get_obj_list`;
- look/examine extra-description paths;
- shop list/browse over foreign stock;
- save again.

Assert that unchanged snapshot owner areas remain unloaded throughout.

Run:

```text
python -m pytest -q -p no:cacheprovider
python tools/check_ascii_py.py
python tools/gen_area_adj.py
```

## Device acceptance gates

Measure on HP Prime before merging:

1. Startup from `primesud.sav`: list areas loaded before first prompt and
   confirm item-only owner loads disappear.
2. Heap after startup, after twelve-area travel, and after repeated
   eviction/reload cycles.
3. Snapshot count and distinct VNUM count after representative travel,
   shopping, drops, and container use.
4. Primary save byte size, peak free-heap loss during serialization, save
   duration, HVar readback equality, and file mirror equality.
5. One content-revision mismatch: confirm exactly one corrective area load,
   current template behavior, and refreshed next save.
6. Object-program item from an unloaded area: confirm trigger still fires.

Current workspace save provides a useful budget case:

- 30 held/equipped item instances;
- 19 distinct template VNUMs;
- four owning areas;
- 16,952-byte current save;
- roughly 7.5 KB of deduplicated full-template `repr` data before the compact
  codec.

The final codec size must be measured, not inferred from `repr`. If save size
or peak heap is unacceptable, first optimization is field-name tags inside
the snapshot codec. Do not drop `description`, `extra_descs`, or other behavior
silently; that would no longer be a full snapshot.

## Acceptance criteria

Implementation is complete when:

- no item instance contains `SNAP_KEY` or copied template fields solely for
  snapshotting;
- one shared snapshot exists per required VNUM;
- player and foreign-room/NPC/shop item operations do not load unchanged
  owner areas;
- snapshots survive save/load and deferred room eviction;
- current area templates replace stale cached data after revision change;
- genuine runtime overrides remain intact;
- object programs work without resident owner areas;
- unused snapshots are pruned;
- old sparse saves still load;
- full desktop suite, ASCII check, generator idempotence, and device gates pass.
