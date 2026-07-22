# TODO

Loose ends that don't belong in a specific plan file.

## Roadmap (18/07/2026)

Two-track release plan:

1. **Engine 1.0 first**: sweep that all general 1stMud systems/mechanics are
   ported (minus multiplayer-only ones -- see DESIGN.md for settled
   non-ports) and finalised; close the open items below and the
   on-calculator checklist, then tag a main release (`v1.0.0`).
2. **Content track after**: new-content additions (new classes, areas,
   quests -- e.g. SWORDSMAN_PLAN.md) land only after the 1.0 tag, released
   as content versions on top of the stable engine. Keeps "1stMud parity"
   auditable separately from "PrimeSUD original content".

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
  `commands.py:_CMD_TABLE`): `gossip`, `shout`, `auction`,
  immortal commands. Port when/if a solo gameplay hook appears.
  (`alias`/`unalias` and social actions ported 10/07/2026; the 20/07/2026
  S-effort batch ported `play`, `socials`, `sshow`, `brief`, `compact`,
  `show`, `title`, `version`, `heel`, `grlist`, `backup`, `prime`; later
  parity work ported `path`, `bank`, and `balance` -- see docs/PARITY.md.)

## Housing

(nothing outstanding -- static single-player estate shipped 22/07/2026;
see DESIGN.md "Player housing")

## Area data

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
  resolved 22/07/2026: PrimeSUD already persists floor objects in every room,
  including the static player home, so a flag-specific reader would add no
  behavior.

## Tests

(nothing outstanding)

## Platform

(nothing outstanding -- full on-device walk completed 22/07/2026:
batched/offscreen rendering, minifier flags + startup preload, mobs.idx
heap headroom, path/run border graph, autoskill, Mud School progs,
Midgaard ticks, dark rooms, eviction wander, and fling-scroll all
validated on hardware; checklist text in git history. The 1 MB
stock-heap device remains unsupported -- keep-set floor ~12 areas
exceeds it.)
