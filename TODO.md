# TODO

Loose ends that don't belong in a specific plan file.

## Combat

(nothing outstanding)

## Items

(nothing outstanding)

## Magic

(nothing outstanding)

## Classes

(nothing outstanding -- prestige tiering shipped 11/07/2026, see DESIGN.md
"Multiclass prestige tiering")

## Commands

- Genuinely still-deferred commands (commented-out rows in
  `commands.py:_CMD_TABLE`): `gossip`, `shout`, `bank`, `auction`, `path`,
  `play`, immortal commands. Port when/if a solo gameplay hook appears.
  (`alias`/`unalias` and socials ported 10/07/2026.)

## Area data

- **New Thalos remote pet-shop stock room** -- QuickMUD special-cases shop
  room 9621 to list/buy pets from room 9706 instead of the normal `vnum + 1`.
  Both rooms and the eagle/lion/tiger cross-area resets are present, but
  PrimeSUD has not ported that mapping (`shop.py`), so Nabil's stock is
  currently inaccessible.

- **Deferred runtime hooks for converter-emitted fields** — the 2026-07
  converter audit brought `are_to_primesud.py` (the single ROM 2.4
  converter; formerly `are_to_primesud_quickmud.py`, renamed after the
  1stMud-format converter was deleted) to a lossless schema. Re-audited
  2026-07-10: `no_sac`, container `container_max_item_weight` /
  `container_weight_mult`, food/drink `poisoned`, mob `group` (assist),
  room `heal_rate`/`mana_rate` (regen), and `light_hours` are all consumed
  now; room `owner` is settled (can_see_room always-permissive, see
  DESIGN.md). Still unconsumed:
  - object `condition` (spawn wear-state) — item condition/wear not
    modeled at all (see quest.py reward note)
  - mob `material` — only in-scope 1stMud consumer is the death_cry
    case-1 guard (`material == 0` falls through to guts); no-op for stock
    data since every stock mob is material `'0'`. Cheap fidelity fix via
    `MOB_DEFS[tpl].get("material")` if ever wanted — see comment at
    `combat.py:_DEATH_CRY_CASES`
  - object `values` raw value[0..4] fallback for item types with no
    dedicated decode (furniture max-occupants/position flags, key linked
    vnum, map, portal, jukebox, ...) — emitted only when nonzero
    (2026-07-05 audit); runtime reads via `obj.get("values", ...)` when a
    consumer (e.g. furniture occupancy, see DESIGN.md furniture row) gets
    ported
- **No `fix_exits` equivalent at world load** — QuickMUD's post-boot pass
  (db.c fix_exits) nulls exits whose destination room doesn't exist and
  auto-sets `no_mob` on rooms with zero resolvable exits. The per-file
  converter architecturally can't do this (cross-area vnums); the runtime
  has no such pass either. Currently zero behavioral impact (audited: the
  only affected stock room, newthalos 9706, is unreachable anyway), but a
  future area with a dangling exit would surface it. Belongs in world.py
  after-load if ever needed.
- **Room flag `save_objs` (bit 22, 1stMud extension) has no runtime reader** —
  carried by the Limbo Morgue room (vnum 3, `areas/limbo.are`); investigate
  how 1stMud uses it (room contents persisting across reboot/reset) before
  porting.

## Tests

(nothing outstanding)

## Platform

- **Validate fling-scroll tuning on physical Prime** — touch scrollback now
  uses row-step fling easing with touch-cancel/release guard
  (`tml_prime.py`, 06/07/2026). Re-tune thresholds/decay on device if it
  still feels jumpy or too eager.
- **On-calculator checklist from the 08/07 planning queue** (consolidated
  final audit 10/07/2026; one walk of the world covers all, ordered by area):
  - *Mud School*: acolyte demo prog end to end (`say help`, give any item,
    delay follow-up); prog-room idle CPU/heap vs an empty room
    (`gc.mem_free`, act-heavy room); school banner light burnout pacing
    (flicker at <=5 hours, both goes-out messages)
  - *Midgaard*: idle tick cost with the full area loaded (regen + weather +
    mobprog pulse); weather message cadence over several ticks; buy + name a
    pet at the pet shop, `group` rendering on the 64-col screen
  - *Any dark room (e.g. caves/sewers)*: automap rendering while dark;
    "It is pitch black ... " + glowing red eyes on the physical screen;
    light a torch and re-look
  - *Anywhere*: `explored`/`score` permille after the walk; `gc.mem_free`
    before/after the ~2KB explored-mask alloc and a save/load round-trip
- **Far-area eviction: device validation (13/07/2026)** -- eviction shipped
  (DESIGN.md "Far-area eviction") after `debug heapmap` measured 5875 kB /
  948 kB free for the full world and an idle session MemoryError'd in
  `reset_room`. Validate on hardware: long wander crossing >12 areas, then
  `gc.mem_free` + `debug heapmap` preloaded markers to confirm far areas
  actually unloaded; revisit an evicted area and spot-check dropped floor
  items/mob positions survived. The 1 MB stock-heap device remains
  unsupported (keep-set floor ~12 areas exceeds it).
