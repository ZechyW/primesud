# Recommend Command Plan

Status: implemented on desktop; G1 heap/latency check pending. First G1
check (01/08/2026) measured 10+ s per mode: full-file scans were dominated
by per-row split allocation. Re-shaped same day -- `foes.idx` (per-level
segments, band read) replaces the mobs.idx scan; `gear.idx` gained 5-level
item bands sorted by max-score bound with break/jump shortcuts. Awaiting
G1 re-check.

02/08/2026 perf round (approved plan): wield weapon-type sub-segments
(`@=type|max_static|max_wmax|bytes`, adept bound rescaled to player
proficiency for arithmetic type skips), full-result floor early-stop
(jump threshold rises to the weakest kept score once a slot's list is
full), and chunked contiguous segment reads (summary: 16 seeks+reads ->
~4). PC-side row-split counts on the shipped index with save-like
baselines (L10, sword 80): summary 985 -> 642, wield detail 350 -> 287.
Reject profile shows the residue is loot rows outside the source-level
window (197 splits, and they suppress the early-stop floor) plus
unlearnt-weapon rows adept-bound-sorted past the jump. Both follow-up
levers approved and implemented same day: loot rows now lead each
segment in "@@min_source_level|bytes" 5-level source-level bands
(skipped whole outside the loot window; the non-loot item-band break
stays safe because loot comes first), and row fields were reordered so
all score rejects resolve from split("|", 9) -- the source/display tail
is only parsed for keep-grade rows. Same PC probe: summary 642 -> 487
row splits (at roughly half the allocs each; ~250 full-split
equivalents vs the original 985), wield detail 287 -> 213. Remaining
residue is boundary-band loot rows (5-level bands vs 4-level window)
and genuine tie/candidate churn. First G1 re-check (02/08/2026, via
debug/recommend_bench.py on the real save): I/O floor solved (82ms of
8.0s summary), but parse/score still 8.0s summary / 3.0s wield detail /
2.3s mobs -- round 3 shipped same day: rows drop the slot field (implied
by the segment; 16 fields, rejects from split("|", 8)), loot bands hold
"@@=source_level|bytes" exact-level sub-segments (boundary-band rows
skip unparsed; loot wield type subs dropped -- post-window volume too
small to pay for headers), and summary mode keeps a single winner per
slot with no alt bookkeeping or loser-tie dicts. Same PC probe: summary
487 -> 425 splits (zero loot-window tail parses, was the residue), wield
213 -> 167, gear.idx 183KB -> 174KB.

Round 4 (02/08/2026, first-principles redesign): the text format itself
was the floor -- every parsed row cost ~10-30 allocations (line slice +
splits + int()s) at ~0.5ms/alloc at full heap, i.e. ~13ms/line, matching
the measured 8.0s for ~600 handled lines. Rounds 1-3 cut N; round 4 cuts
the per-row constant: `gear.idx` replaced by binary `gear.bin`
(fixed-width 30-byte records, header with per-slot record/loot counts +
weapon-type/area-tag name tables, deduplicated trailing string table;
layout beside _GEAR_RECORD in tools/build_mob_index.py, readable dump
via tools/dump_gear_bin.py). The scanner rejects records with raw byte
arithmetic -- zero allocations -- so the whole band/sub-band apparatus
(@, @@, @@=, @= headers) is deleted: per slot, loot records lead and
non-loot follow, each region sorted by precomputed bound descending, and
one break per region replaces every skip. Bounds, flag bitmasks, and
weapon-type ids are baked at build time; per-type effective skill is
precomputed per scan; winner display strings resolve from one bounded
string-table read after scanning. gear.bin is 80KB (records ~55KB: one
summary-mode chunk read). Estimated scan_summary 8.0s -> ~0.3-0.5s.

G1 re-check 02/08/2026 (recommend_bench-4.log): scan_summary 8012 ->
194ms (41x), scan_wield 3024 -> 164ms, results identical. First device
run surfaced that Prime `open(.., "rb")` returns str with
character-counted sized reads (byte-faithful payload; see
docs/BUILTINS.md sec. File open() binary-mode semantics) -- fixed by the
`_as_bytes()` encode cast (c2e3473). Round 4 CONFIRMED. Next: same
recipe for foes.idx (scan_mobs still 2383ms), then harvest this plan
doc. load_world 11.9s remains a separate open issue.

Desktop verification on 31 July 2026 (post-review: `gear.idx` segmented per
wear slot for bounded seek reads; gear summary is a drill-in picker; detail
rows keep up to two alternate sources; mob rows mark extra spawn areas):
generated indexes reproduced deterministically, Python sources passed the
ASCII/BOM check, and all 1,495 tests passed.

## Decision

PrimeSUD has no command that recommends both level-appropriate opponents and
equipment upgrades. Existing commands cover separate parts of the workflow:

| Command | What it answers | Missing piece |
|:--|:--|:--|
| `consider <mob>` | Relative level of a mob in the current room | No world-wide discovery |
| `areas [low high]` | Areas within a level range | No mob or loot detail |
| `where <mob>` | Matching live mobs in the current loaded area | No unloaded areas or suitability ranking |
| `path <area or mob>` | Route to one chosen target | No target selection |
| `compare` | Gear score comparison for owned items | No acquisition sources |
| `wear best` | Best legal layout from owned items | No external upgrades |
| `hunt <mob>` | Tracking toward a named target | No recommendations |

Add a PrimeSUD-only `recommend` command:

```text
recommend
recommend mobs
recommend gear
recommend gear <slot>
```

Bare `recommend` opens a two-entry picker for mobs or gear. The command is
advisory: it does not move the player, load a target area, buy anything, start
combat, or change equipment.

The feature can preserve lazy loading. Build recommendation metadata offline,
keep it in `.idx` files, read only the required index on command use, retain
only the small displayed result set, and discard the raw data. Runtime code
must never iterate `MOB_DEFS`, `ITEM_DEFS`, or `ROOM_DEFS`.

## Goals

- Recommend reset-backed mobs near the player's level that are intended to be
  fightable.
- Recommend strict gear-score upgrades for each wear category.
- Identify a static acquisition source:
  - loot carried or worn by a suitable mob;
  - ordinary shop stock;
  - floor-reset items;
  - items reset inside a floor container;
  - nested items carried by a suitable mob, represented as that mob's loot.
- Use the same scoring rules as `compare` and `wear best`.
- Account for player level, alignment, weapon skill, strength, owned gear, and
  recorded experience with a mob where those data already exist.
- Keep output useful on the 64-column calculator display.
- Cause zero area loads and leave the loaded-area set unchanged.
- Keep generated metadata off heap until the player invokes the command.

## Non-goals

- No combat simulator or promise that a fight is safe.
- No automatic travel, buying, looting, or combat.
- No exhaustive route calculation for every recommendation.
- No prediction of whether a reset-backed instance is alive at this moment.
- No parsing or execution analysis of mob/object/room programs.
- No recommendation of random body-part drops, spell-created items, debug
  loads, or other non-static creation paths.
- No quest-point/trivia reward recommendations in the first version. Quest
  equipment rescales per player and is not ordinary reset/shop stock.
- No optimization for gold, experience per minute, drop probability, or travel
  time until gameplay shows a need.
- No new persistent player state.

## Repository assessment

### Lazy-loading boundary

`world.ROOM_DEFS`, `world.MOB_DEFS`, and `world.ITEM_DEFS` are `LazyDict`
instances. A keyed lookup may load one area; iteration loads all areas.
Recommendation code therefore cannot discover candidates from those mappings.

Existing world-wide features establish the correct pattern:

- `areas` reads generated static tables.
- unloaded mob lookup reads `mobs.idx`;
- `locate object` reads `objs.idx` and only hydrates candidate areas because
  it must report live locations;
- `path` reads the mob index, then loads at most two candidate areas to resolve
  one chosen mob's live room.

`recommend` needs only static possibilities, not live locations. It can stop at
the index and load no area at all.

### Existing indices

Current generated files are:

```text
mobs.idx  58,377 bytes, 1,003 mob-template rows
objs.idx  46,615 bytes, 1,357 object-template rows
```

Current schemas:

```text
mobs.idx: vnum|home_tag|level|keywords|short_descr|spawn_tags
objs.idx: home_tag|vnum|keywords|spawn_tags
```

`mobs.idx` already has the identity, level, display name, and reset-owning area
tags needed for basic mob discovery. It does not distinguish a fightable spawn
from a shopkeeper, trainer, pet, safe-room mob, or another service NPC.

`objs.idx` supports keyword lookup and candidate-area hydration. It does not
contain wear slot, required level, gear-score inputs, alignment restrictions,
display name, price, carrier, shopkeeper, room, or container provenance.
Extending it with all recommendation data would bloat every unrelated
`locate object` and `debug vnum` scan. Use a separate gear index.

### Static content audit

Audit of all shipped generated area files on 31 July 2026:

```text
Mob templates                                      1,003
Object templates                                   1,357
Wearable templates                                   986
Wearables with at least one static reset source      910
Wearables without a static reset source                76
Unique wearable/source relationships               1,202
```

Static source coverage:

| Source | Reset form | Unique wearable items | Reset occurrences |
|:--|:--|--:|--:|
| Mob loot | `M` followed by `E`/`G` | 724 | 1,829 |
| Shop stock | shopkeeper `M` followed by `E`/`G` | 155 | 175 |
| Floor | `O` | 35 | 42 |
| Container | `P` inside an `O`/`E`/`G`-reset object | 39 | 40 |

Counts overlap because some items have several source kinds. There are 43
wearables with more than one kind of static source.

The 1,202 relationship count keys on (item, source kind, effective source
VNUM), with a floor item's room VNUM acting as its source VNUM. The shipped
index keys on the finer documented (item, kind, source VNUM, room, tag)
relationship, so repeated reset sites -- mostly the same mob/item pair
recurring across rooms -- emit additional rows: 1,890 emitted rows, or 1,193
under the audit key after filtering. Nine non-fightable loot relationships
are removed from the audited 1,202; four carried-container relationships are
represented as level-filtered loot from their holder rather than unactionable
container-only sources. The generator models the device pipeline -- world's
per-room reset partitioning followed by reset_room's room-scoped
last-mob/last-spawned walk -- including a floor container and `P` reset in the
same room separated by an intervening `M`.

This is enough coverage for a useful first version. The 76 resetless wearables
include special creation/reward cases and should remain absent until each
source has explicit, reliable acquisition metadata.

### Gear-score constraints

`inventory.gear_score(player, obj)` is already the canonical score. Most score
inputs are static template data:

- all four armor values;
- stat bonuses and flag affects;
- resistance/immunity/vulnerability affects;
- implemented weapon procs;
- weapon dice and type.

Weapon score is player-specific because it uses current proficiency. Current
gear may also have instance armor/dice overrides or runtime affects. A single
score baked into an index would therefore disagree with `compare`.

Static reset/shop objects are created in their base template state. Their exact
score can be represented compactly as:

```text
static_score
weapon_base
weapon_type
sharp
```

`static_score` includes armor, modifiers, affects, and fixed weapon-proc value.
For weapons, runtime code adds the existing proficiency-scaled base and sharp
terms. Refactor this calculation into a small shared helper used by both
`gear_score()` and the recommendation index scanner. Do not duplicate the
formula in the generator or command.

### Acquisition semantics

The reset stream provides exact static provenance:

- `M` establishes the current mob reset.
- following `E` and `G` entries place gear on that mob;
- if that mob template has `shop`, reset handling marks those objects as
  shop inventory instead of death loot;
- `O` places an object on a room floor;
- `P` places an object inside an earlier reset container in the same room.

NPC death transfers non-shop inventory and equipment into the corpse, so
ordinary `E`/`G` relationships are valid loot recommendations. Shop inventory
is deliberately omitted from corpses and is valid only as a purchase source.
When `P` fills an object carried by a fightable mob, its nested item is also
represented as loot from that holder, preserving holder level and identity.

Reset metadata describes potential availability. A mob may currently be dead,
an item may already have been taken, or reset limits may suppress an instance.
Output and help text must say "known source", not "currently available."

## Proposed player experience

### Bare command

```text
Recommend:
  1) Mobs to fight
  2) Gear upgrades
```

Use the existing blocking picker. A cancelled picker does nothing.

### Mob summary

Example layout:

```text
[Lv  Record] Mob                         Area
 14    3/0!  a dwarven guard             Dwarven Kingdom
 15       -  a cave troll                Moria
 16     0/1  the black knight            High Tower
```

`Record` is mob kills / mob deaths, matching the stored mob-perspective
counters: `3/0` means the mob has killed the player three times and never
died. In the solo world these usually describe the player's encounters,
though NPC-on-NPC combat can also affect them. `!` marks an unfavorable
stored record (the mob is ahead). No record prints `-`.

Show at most ten rows through `tpage`. One row represents one mob template.
When a template has multiple viable spawn tags, prefer the current area, then
the earliest tag in `_AREA_FILES` order; a `+n` suffix after the area name
marks n additional spawn areas.

Do not calculate or print a speedwalk for every row. That would add cost and,
for exact mob locations, force area loads. The footer should say:

```text
Use path <mob> or path <area> after choosing.
```

### Gear summary

`recommend gear` prints at most one best strict external upgrade per wear
category:

```text
Slot       Gain Item                     Known source
head        +90 a jeweled war helm       loot: cave troll
body       +140 black dragon plate       shop: armorer
wield       +55 a silver longsword       loot: dwarven guard
```

The summary renders through the blocking picker (one option per category, at
most sixteen): choosing a row drills into that slot's detail, and the resolved
`recommend gear <slot>` string is returned for command-history replay; a
cancelled picker records the summary itself (`recommend gear`), since that
was the content shown. Omit categories with no known strict upgrade.
If every category is omitted:

```text
No known static gear upgrades for you.
```

`recommend gear <slot>` prints up to ten candidates for one category, ordered
by score gain, then source suitability, then VNUM. Accepted category names are
the existing wear flags:

```text
light finger neck body head legs feet hands arms about waist wrist
wield shield hold float
```

Do not expose concrete paired slots such as `finger_l`; `finger`, `neck`, and
`wrist` are the player-facing categories already used by wear logic.

For detail rows, show source area and price when applicable, plus up to two
ranked alternate sources per item so multi-source items stay visible.
Alternates that would render identically to the primary or to each other
(same kind, source, and area -- rooms are not shown) collapse to their
best-ranked row:

```text
head +90  a jeweled war helm
  loot from a cave troll (L14), Moria
  also buy from the armorer, Midgaard: 12,500 silver

body +70  polished field plate
  buy from the armorer, Midgaard: 12,500 silver
```

### Meaning of "upgrade"

Compare against the best compatible item the player already owns, not merely
the currently equipped item. This avoids recommending a hunt for something
already beaten by an unequipped inventory item.

- Single slots use the best legal owned score.
- Paired finger/neck/wrist categories compare against the weaker of the two
  best legal owned items; an empty position has score zero.
- Candidates must beat the baseline strictly. Ties remain omitted, matching
  `wear best`.
- Current owned-item scores use normal instance-aware `gear_score()`.
- Indexed candidate scores use the shared component helper.
- Level and anti-alignment rules match `_can_wear_best`.
- A wield candidate too heavy for the player's current strength is omitted.

Hand items have layout interactions that one item score cannot fully express:
two-handed weapons displace shields, secondary weapons exclude shield/hold,
and strength-granting equipment can change weight legality. First version
reports strict per-item score upgrades and labels hand rows as candidates.
`wear best` remains the final authority after acquisition. Do not copy the
large hand-layout enumerator into recommendation code. Generalize it only if
playtesting shows materially misleading hand recommendations.

## Mob recommendation rules

### Level band

Start with:

```text
player level - 2 <= mob level <= player level + 1
```

This matches the useful `consider` bands: two levels lower is "easy," while
one lower through one higher is "the perfect match."

If fewer than five candidates survive, widen only the lower boundary, one
level at a time, down to `player level - 5`. Never widen above `player + 1`;
an information command should not silently recommend a stronger fight merely
to fill the page.

Clamp the lower bound to level 1.

### Build-time fightability

Append one field to `mobs.idx`:

```text
vnum|home_tag|level|keywords|short_descr|spawn_tags|fight_tags
```

`fight_tags` is the ordered subset of `spawn_tags` containing at least one
static `M` reset site suitable for recommendation.

A reset site is not suitable when any of these is true:

- room is `safe`, `private`, `solitary`, or `pet_shop`;
- mob is a shopkeeper;
- merged mob flags mark trainer, practice mob, healer, changer, gain mob, pet,
  or charmed mob;
- both weapon and magic immunity make the mob unsuitable as a general target.

Merge race defaults and template flag removals the same way `create_mobile`
does before applying this filter. Preserve reset-owner tag order from
`_AREA_FILES`.

The filter is intentionally stricter than "can the kill command technically
start?" Service NPCs and inaccessible/special-purpose rooms are poor
recommendations even if one unusual code path permits combat.

Existing `mobs.idx` consumers must parse the new trailing field without
changing the meaning of field 5 (`spawn_tags`). Update synthetic index fixtures
in tests. Older six-field rows should remain accepted, treating
`fight_tags` as empty outside recommendation code.

### Runtime filters

After reading `mobs.idx`:

- require non-empty `fight_tags`;
- apply the level band;
- exclude the player's active deliver/find-mob quest target, which combat
  protects from killing;
- keep kill-quest and global-quest targets eligible;
- skip malformed rows rather than crashing.

No `MOB_DEFS`, `ROOM_DEFS`, or live-character lookup is needed.

### Ranking

Use deterministic, explainable ranking:

1. favorable or unseen stored record before unfavorable record;
2. current-area source before another area;
3. smallest absolute level difference;
4. lower mob level before higher on an equal difference;
5. existing index/VNUM order.

Do not create a synthetic combat-power score initially. Authored mob level is
the game's existing `consider` model, while current player combat power varies
by class, skills, spells, stance, gear, consumables, and tactics. A new scalar
would look more precise without being more trustworthy.

If real play finds repeated same-level outliers, add a displayed build-time
threat marker based on HP/damage/armor/special flags. Do not use it to make
hard promises or hide candidates until validated.

## Gear index

### File

Generate a new `src/gear.idx` from the same all-area pass already performed by
`tools/build_mob_index.py`.

One flat row represents one unique item/source relationship:

```text
item_vnum|slot|item_level|static_score|weapon_base|weapon_type|sharp|
weight|item_flags|item_name|source_kind|source_vnum|source_level|
room_vnum|source_name|tag|price
```

The physical file keeps each record on one line; the wrapped schema above is
for documentation only. Rows are grouped into one contiguous segment per wear
slot in fixed `_GEAR_SLOTS` order, after a comment header and one directory
line of comma-separated per-slot segment byte lengths (the `help.dat` +
`help.idx` pattern, folded into a single file). Runtime seeks and reads only
the segments a command needs, so peak transient heap is the largest needed
segment (~56 KB for wield today), never the whole ~178 KB file.

Field meanings:

| Field | Meaning |
|:--|:--|
| `slot` | Wear category used by `_wear_flag` |
| `static_score` | Player-independent portion of canonical gear score |
| `weapon_base` | Canonical dice coefficient; zero for non-weapons |
| `weapon_type` | Key used by `WEAPON_GSN_MAP`; empty for non-weapons |
| `sharp` | `1` when sharp's second skill-scaled term applies |
| `item_flags` | Compact comma list: anti-align and `two_hands` only |
| `source_kind` | `loot`, `shop`, `floor`, or `container` |
| `source_vnum` | Carrier/shopkeeper/container VNUM; zero for floor |
| `source_level` | Carrier level for loot; otherwise zero |
| `room_vnum` | Reset room, for diagnostics and future detail |
| `source_name` | Flattened mob, shopkeeper, room, or container display name |
| `tag` | Reset-owning/hosting area tag |
| `price` | Normal shop buy price in silver; zero for non-shop sources |

Flatten whitespace in names and reject `|` at generation time, matching the
existing index builders.

Flat rows repeat item scoring metadata across multiple sources. That costs
file bytes but keeps runtime simple: scan once, score and rank one row, retain
only the best few results, and build no all-item/all-source object graph on the
calculator. Off-heap file size is cheaper than a large parsed structure.

### Included sources

Include:

- `E`/`G` items attached to an ordinary fightable mob reset;
- `E`/`G` stock attached to a shopkeeper;
- wearable `O` floor objects;
- wearable `P` objects inside an `O`-placed floor container;
- wearable `P` objects inside an `E`/`G` object carried by a fightable mob,
  represented as loot from that mob.

Deduplicate identical `(item, source kind, source VNUM, room, tag)`
relationships.

For loot, require the exact preceding `M` reset site to pass the fightability
filter. Do not infer loot merely because the same mob template is fightable in
another room.

For shops, compute the fresh stock price with base object value, `profit_buy`,
and the existing wand/staff charge adjustment where applicable, matching
`get_cost()`. Price is informational; unaffordable gear may still be a future
upgrade, but affordable shop sources rank first among equal-score sources.

For `P` inside an `O`-placed container, retain container VNUM/name and hosting
room VNUM/tag. For `P` inside a mob-carried `E`/`G` object, emit the holder's
ordinary loot source VNUM, level, name, room, and tag; the holder is the
actionable acquisition bottleneck.

### Excluded sources

Do not index:

- resetless templates with no known acquisition path;
- starter outfit, because the player already owns it when relevant;
- quest/trivia shops and dynamically rescaled quest gear;
- mobprog `oload` and scripted give rewards;
- spell-created objects;
- death-cry body parts;
- random or runtime-enchanted variants;
- pending saved objects in unloaded rooms.

Pending and player-owned objects affect the current baseline through normal
runtime state; they are not promises of a repeatable external source.

### Runtime scan

`recommend gear`:

1. Scores the player's legal owned items and builds compact per-category
   baselines.
2. Reads the small directory line, then seek + one bounded read per needed
   slot segment -- all sixteen sequentially for the summary, one for
   `recommend gear <slot>`. The whole file is never resident at once.
3. Walks each segment's rows with a newline cursor rather than
   `data.split("\n")`, avoiding a second list containing every line.
4. Applies item eligibility and source suitability.
5. Retains only the best summary row per category, or top ten rows for one
   requested category.
6. Returns the compact results so the raw file buffer becomes unreachable.
7. Renders through `tpage`.

Do not retain a parsed cache between commands. Recommendations are occasional,
while a resident cache would permanently consume heap. Add an explicit
post-scan `gc.collect()` only if device measurement shows the raw buffer is not
reclaimed soon enough; do not assume it is needed from desktop behavior.

### Source suitability and ranking

Loot sources are eligible only when carrier level fits the same mob-level
window used by `recommend mobs`.

Shop, floor, and floor-container sources are not filtered by mob level. Their
area name is shown so the player can judge travel risk. Mob-carried nested
items are loot and use the normal carrier-level filter. Area level ranges may
be used as a tie-breaker but must not hide a legal upgrade.

For one item with several sources, choose:

1. source in the current area;
2. affordable shop;
3. floor/container;
4. loot with the smallest carrier/player level difference;
5. unaffordable shop;
6. stable source kind, area order, and VNUM tie-breaks.

Runner-up sources are not discarded: each retained item keeps up to two
lower-ranked alternates for its detail rows.

Across different items, order first by descending score gain. The command is
an upgrade finder, not an acquisition-cost optimizer.

## Lazy-loading and memory guarantees

The implementation must satisfy all of these:

- `recommend mobs` reads only `mobs.idx` and resident player/static tables.
- `recommend gear` reads only `gear.idx`, resident player inventory/equipment,
  and resident static tables.
- Neither mode performs `MOB_DEFS[...]`, `ITEM_DEFS[...]`, or
  `ROOM_DEFS[...]` for an indexed candidate.
- Neither mode calls `_ensure_area`, `_ensure_area_by_tag`,
  `_find_unloaded_mob`, `path`, or `locate object`.
- Neither mode changes `world._LOADED_AREAS`.
- Neither mode creates item or mob instances for candidates.
- Parsed candidate data is command-local and discarded after rendering.
- Missing index files produce a short unavailable message, not an area sweep.
- Malformed individual rows are skipped.

The generator may load every generated area file on desktop. It already does
so for `mobs.idx` and `objs.idx`; this work remains part of build/preflight,
never calculator runtime.

## Implementation shape

### Runtime

Add `src/recommend.py` containing:

- index constants;
- compact row parsing;
- mob filters/ranking/rendering;
- owned-gear baseline calculation;
- indexed candidate scoring;
- source ranking/rendering;
- `do_recommend(player, args)`.

Keep feature logic out of `info.py`; it is large already, and recommendation
has its own generated schema and tests.

Append `recommend` to the PrimeSUD extension section of `_CMD_TABLE` in
`src/commands.py`, at minimum position `resting`. Add its import normally. No
alias is needed. Because command lookup is first-prefix, `rec` remains
`recite`; `reco` is the shortest unambiguous prefix.

Add one description row to `src/commands.txt`.

### Shared scoring

Make the smallest backward-compatible change in `src/inventory.py`:

- extract the base-template component calculation and the player-specific
  weapon component calculation from `gear_score`;
- keep `gear_score(player, obj)` as the public instance-aware entry point;
- let the index generator obtain canonical components from a template;
- let `recommend.py` combine indexed components with current player skill.

All existing `compare` and `wear best` tests must retain the same scores.

Do not move general inventory logic into the new command module.

### Generation

Extend `tools/build_mob_index.py` rather than add another all-area loader:

- preserve current two-pass cross-area-template handling;
- compute ordered fightable tags;
- append `fight_tags` to `mobs.idx`;
- emit `gear.idx`;
- print row counts and file sizes;
- keep deterministic ordering.

Update the label in `tools/regen_areas.py` from "mob and object indexes" to
"mob, object, and gear indexes." `build_dist.py` already copies non-Python
source files and runs `regen_areas.py` in preflight, so no new build step is
needed.

### Documentation

On implementation:

- add a help entry to canonical `src/help.txt`;
- rebuild `src/help.idx`;
- add the command description to `src/commands.txt`;
- document picker/output/scoring limits in `docs/PRIME_UX.md`;
- add a concise generated-index/lazy-loading decision to `DESIGN.md`;
- add the player-facing feature to `FEATURES.md`.

Do not add `recommend` to `docs/COMMANDS.md`; that table documents the 348
upstream 1stMud commands, while PrimeSUD extensions live after it.

## Tests

Add `tests/test_recommend.py`.

### Mob tests

- Bare command opens the Mobs/Gear picker.
- Six-field legacy fixture does not crash.
- Empty `fight_tags` never recommends a mob.
- Base level window is `-2/+1`.
- Lower edge widens to at most `-5` only when fewer than five results exist.
- Upper edge never widens.
- Service/protected sites are absent from generated fight tags.
- Cross-area M resets use hosting/reset-owner tags.
- Current-area and stored-record ranking is deterministic.
- Deliver/find-mob quest targets are excluded; kill targets remain eligible.
- Malformed rows are skipped.
- Missing index prints an unavailable message.

### Gear tests

- Indexed armor/static score equals `gear_score()` for a fresh object.
- Indexed weapon score equals `gear_score()` at proficiency 0, 50, and 100,
  including sharp and each implemented proc.
- Runtime-enhanced owned gear is scored from its instance and can suppress a
  weaker indexed candidate.
- Required level, anti-alignment, and wield weight filters match wear rules.
- Ties are omitted.
- Paired slots compare against the weaker owned position.
- Loot outside the mob level band is omitted.
- Shop/floor/container sources remain eligible without a carrier-level check.
- Current-area and affordability source tie-breaks work.
- Duplicate reset relationships collapse.
- Slot detail returns at most ten rows.
- Hand rows are labeled as candidates rather than promised layouts.
- Missing/malformed gear index degrades safely.

### Lazy-loading tests

For both modes:

- replace `_ensure_area_by_tag` with a function that raises;
- record `world._LOADED_AREAS` before and after;
- make candidate VNUMs absent from every resident definition;
- assert output succeeds and loaded areas remain identical.

This is the central regression guard.

### Generator/real-world tests

- Real generated index contains every supported static wearable/source
  relationship.
- Every emitted item and source VNUM resolves during desktop generation.
- `E`/`G` follows the correct preceding `M`.
- Shopkeeper E/G rows become `shop`, never `loot`.
- `P` rows require a same-room reset container; mob-carried contents become
  holder loot with the holder's level.
- Output ordering is deterministic.
- Names contain no delimiter/newline leakage.
- Regenerating produces no git diff.

### Required checks

```text
python tools/build_mob_index.py
python tools/build_help_idx.py
python tools/check_ascii_py.py
python -m pytest -q -p no:cacheprovider
```

Run pytest elevated from the start on managed Windows, per `AGENTS.md`.

### Device check

Desktop tests cannot establish calculator heap and latency. Measure once on
G1 hardware with a representative mid-game save:

- elapsed time for `recommend mobs`;
- elapsed time for `recommend gear`;
- free heap before command, after scan, and after return/normal GC;
- loaded-area count before and after;
- repeated invocation to confirm no retained growth.

Do not add a resident cache unless repeated measured index parsing is a real
UX problem and retained heap is demonstrably affordable.

## Risks and mitigations

| Risk | Mitigation |
|:--|:--|
| Same-level mobs vary greatly | Use level as an honest heuristic; show personal record; add threat marker only after evidence |
| Static source currently absent | Say "known source"; do not claim live availability |
| Generated index drifts | Build in normal regen/preflight; deterministic real-world test |
| Rich gear index creates transient heap pressure | Separate file, one read, cursor scan, retain top rows only, device measurement |
| Weapon recommendation differs by class/skill | Store components, calculate with current proficiency through shared helper |
| Owned enchanted/quest gear is undervalued | Score owned items from live instances |
| Hand layout interactions mislead | Label hand items candidates; leave final layout to `wear best` |
| Scripted reward coverage seems incomplete | State exclusions; add explicit source kinds only when reliable |
| Added `mobs.idx` field breaks consumers | Preserve existing positions; update parsers and all synthetic fixtures |
| Recommendation accidentally loads world | Dedicated failing lazy-load tests and loaded-area-set assertions |

## Implementation order

1. Refactor gear scoring into shared component helpers without behavior change.
2. Extend `build_mob_index.py`; generate `fight_tags` and `gear.idx`.
3. Add generator and score-parity tests.
4. Add `recommend.py` mob mode and lazy-load tests.
5. Add gear baselines, index scan, source ranking, and tests.
6. Register command and picker.
7. Add help, command description, `PRIME_UX`, `DESIGN`, and `FEATURES` entries.
8. Run generators, ASCII check, and full elevated pytest suite.
9. Measure both modes on G1; simplify or segment `gear.idx` only if measured
   heap/latency requires it.

## Acceptance criteria

Feature is complete when:

- `recommend`, `recommend mobs`, `recommend gear`, and
  `recommend gear <slot>` work;
- mob recommendations are fightable reset-backed templates in the defined
  level policy;
- gear recommendations are strict canonical-score upgrades over the player's
  best owned compatible items;
- loot recommendations come only from suitable carrier resets;
- ordinary shop, floor, and container sources are represented;
- player-specific weapon skill changes indexed weapon ranking correctly;
- command output fits the 64-column UI and pages normally;
- no recommendation path loads or unloads an area;
- missing/corrupt index data fails softly;
- generated files reproduce deterministically;
- ASCII check and full test suite pass;
- hardware check shows no retained heap growth across repeated commands.

## Deferred extensions

Add only after the first version proves useful:

- validated HP/damage/armor threat markers;
- travel-distance ranking from the static border graph;
- exact current-live availability;
- exact combined hand-layout evaluation for hypothetical gear;
- quest/trivia reward recommendations with dynamic rescaling and currency;
- mobprog/scripted acquisition metadata;
- filters such as `recommend gear affordable` or `recommend mobs <range>`.

These are independent additions. None is required to preserve lazy loading or
deliver the core command.
