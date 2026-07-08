# EXPLORED_PLAN.md -- Explore tracking port from 1stMud (explored.c)

> 1stMud sources: `reference/1stMud4.5.3/src/`. Depends on: nothing;
> independent of the other plans.
> On completion: update DESIGN.md "Explore tracking" row to Ported +
> harvest decision 2 (main-loop mark seam, no char_to_room choke point)
> into "Adjusted from 1stMud"; strike TODO.md `group` note if touched;
> delete this file.

Per-room "have I been here" bitmask with `do_explored` command and the
score-sheet line. DESIGN.md already lists this as "Planned; placeholder in
`do_score`". Solo completionist hook; later reward hooks (trivia/QP for
area completion) can build on it but are out of scope.

## 1stMud semantics

- Bit set in `char_to_room` (handler.c:1360) -- i.e. on *every* room entry,
  by vnum, players only.
- `roomcount(ch)` (explored.c:58) = total bits set;
  `areacount(ch, area)` (explored.c:96) = bits set within the area's vnum
  range; `arearooms(area)` (explored.c:115) = rooms existing in the range,
  excluding ROOM_NOEXPLORE (no loaded PrimeSUD room carries `noexplore` --
  verified 08/07/2026 -- so "explorable" == "exists").
- `do_explored` (explored.c:201): no arg -> world total + current-area
  stats, 4 lines with exact formats
  (`"ROM has {G%d{x explorable rooms."` -- render "ROM" as the realm name
  per the existing quest.py precedent for `{n`);
  `reset` -> zero the mask, `"Your explored rooms were set to 0."`;
  `list` -> two-column area list sorted by percent desc,
  `"{D[{Y%3.0f{y%%{D]{x %s"`, paged.
- Score line (act_info.c:1841): `Explored : N rooms (x.xx% of the world)`
  region -- re-read exact CTAG colours when implementing (docs/REFERENCE.md
  CTAG table).
- Persistence: RLE runs of alternating 0/1 counts (write_rle/read_rle,
  explored.c:134-191).

## Decisions

1. **Storage: `bytearray`, bit index = room vnum.** Size =
   `(max_vnum >> 3) + 1` from the static `_VNUM_RANGES` table (max vnum in
   loaded set is < 10000 -> ~1.25 KB; acceptable heap). Lives on the player
   dict as a non-serialized runtime object plus a serialized form (below).
2. **Mark seam: main-loop room-change check, not per-teleport call sites.**
   PrimeSUD has no `char_to_room` choke point -- room assignment happens in
   movement.py:245/485/1291, magic.py:383/1783/2325, combat.py:2525/3301,
   training.py:351, debug.py:142, game_state.py:417. Instead keep
   `player["_last_marked_room"]`-style cached vnum and, once per command
   dispatch (and once per update tick, to catch mob-initiated drags like
   summon), set the bit when it differs. One helper `mark_explored(player)`
   in a small new module or info.py. `[PRIMESUD]` note explaining the
   deviation. Debug `goto` marks too (1stMud char_to_room does).
3. **Static per-area room counts at generation time.** `arearooms` must not
   load areas. Extend `tools/gen_area_adj.py` to emit
   `AREA_ROOM_COUNTS = {tag: n_rooms}` into world.py alongside
   AREA_LEVELS; world total = sum of values (1stMud `top_explored`).
   Re-run the generator; commit regenerated world.py tables.
   `areacount` needs only the static vnum range + the bitmask -- zero-load.
4. **Save format: RLE string, str()+concat only** (PRIME_STRING_FORMAT_BUG
   applies -- this string is persisted). Same alternating-run scheme as
   1stMud (`"0 12 3 40 ... -1"` style); decode on load into the bytearray.
   SAVE_VERSION bump; absent field -> empty mask (old saves start fresh --
   acceptable, dev phase).
5. **`do_explored` percent formatting:** no floats on HP Prime if avoidable
   -- compute integer permille and render `NN.NN%` via divmod string
   assembly for the two-decimal world/area lines, plain integer percent for
   the `list` column. UI-transient strings, so `%` formatting is fine
   (colour-delimiter caveat in CLAUDE.md).
6. **Rooms that stop existing** (update_explored pruning, explored.c:73):
   skip -- area set is static per build; stale bits only matter if vnum
   ranges get reused, which the converter forbids.

## Touch points

- `tools/gen_area_adj.py` + regenerated `world.py` static tables
  (AREA_ROOM_COUNTS).
- New helper + mark calls: main command loop (primesud.py or commands.py
  dispatch -- find the single per-command point) and update.py tick.
- `info.py`: `do_explored` (new), `do_score` explored line (replace
  placeholder).
- `commands.py`: uncomment row #179 (`explored`, "sleeping").
- `game_state.py`: serialize/deserialize (decision 4), SAVE_VERSION bump.
- `debug.py`: optional `explored` debug key showing count.

## Verification

- Unit: RLE round-trip (empty, all-set, alternating runs); areacount
  against a hand-set mask; permille formatting edge cases (0%, 100%,
  rounding).
- PC shim: walk 3 rooms -> `explored` shows 3; `explored list` sorts;
  save/load round-trips the mask; `explored reset` zeroes.
- Heap sanity on device: confirm bytearray + RLE string don't spike
  (gc.mem_free before/after load, per docs/BUILTINS.md practice).
- `python tools/check_ascii_py.py`.
