# TODO

Loose ends that don't belong in a specific plan file.

## Active plan docs (08/07/2026)

Root-level `*_PLAN.md` files awaiting implementation; each carries its own
dependency + completion notes in its header. `MOBPROG` is the last plan
left (independent).
`RESETS`, `DARKNESS`, `EXPLORED`, and `PETS_GROUPS` are done (08/07/2026). `OPUS_HANDOFF.md` carries
ready-made session prompts for every stage. Strike this section when the
last plan is deleted.

## Combat

(nothing outstanding)

## Items

(nothing outstanding)

## Magic

(nothing outstanding)

## Classes

- Full multiclassing (allowing remorts on the same char into all available classes), possibly tiering (start back with 1 class, but with perm bonuses, e.g. to starting skill proficiencies/stats/etc.)

## Commands

- Genuinely still-deferred commands (commented-out rows in
  `commands.py:_CMD_TABLE`): `gossip`, `shout`, `alias`/`unalias`,
  `bank`, `auction`, `path`, `play`, immortal commands. Port when/if a solo
  gameplay hook appears.

## Area data

- **Deferred runtime hooks for converter-emitted fields** — the 2026-07
  converter audit brought `are_to_primesud.py` (the single ROM 2.4
  converter; formerly `are_to_primesud_quickmud.py`, renamed after the
  1stMud-format converter was deleted) to a lossless schema; these emitted
  fields are captured in the `.txt` files but not yet consumed at runtime:
  - object `condition` (spawn wear-state), `no_sac`, container
    `container_max_item_weight` / `container_weight_mult`, food/drink
    `poisoned` (`light_hours` now consumed -- see DARKNESS light burnout)
  - mob `default_pos` -- its only 1stMud runtime consumer is MOBPROG trigger
    gating (update.c:444-462); there is no "return to default position"
    mechanic, so `start_pos` (consumed at spawn) is enough until MOBPROG
    lands. `group`, `material`, `mob_triggers`
  - room `heal_rate`/`mana_rate`, `owner`
  - object `values` raw value[0..4] fallback for item types with no
    dedicated decode (furniture max-occupants/position flags, key linked
    vnum, map, portal, jukebox, ...) — emitted only when nonzero
    (2026-07-05 audit); runtime reads via `obj.get("values", ...)` when a
    consumer (e.g. furniture occupancy) gets ported
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
- **`_unknown_bits` in quest.are** — stock 1stMud data sets ACT bits 11/31 and
  AFF bits 34/36 that are undefined even in 1stMud's own `bits.h`; preserved
  losslessly under `_unknown_bits`, no runtime meaning.

## Tests

(nothing outstanding)

## Platform

- **Validate fling-scroll tuning on physical Prime** — touch scrollback now
  uses row-step fling easing with touch-cancel/release guard
  (`tml_prime.py`, 06/07/2026). Re-tune thresholds/decay on device if it
  still feels jumpy or too eager.
