# TODO

Loose ends that don't belong in a specific plan file.

## Combat

- **Race not persisted** — `create_char` now derives racial
  aff/imm/res/vuln/stats/size/form/parts (06/07/2026), but `game_state.py`
  has no `p.race` save key, so the load path always re-derives from
  `_char_base`'s "Human". Harmless while only "Human" is selectable; when
  race chargen lands, persist race and re-derive after load (cf. 1stMud
  save.c:723ff re-deriving after fread).
- **Wield-drop on strength loss not ported** — `handler.py:220` TODO:
  1stMud affect_modify (handler.c:1030-1045) makes a char drop a wielded
  weapon when a stat-draining affect leaves them too weak to hold it
  (str_app wield limit). PrimeSUD affect_modify applies the stat change
  but never rechecks the wield.

## Items

(nothing outstanding)

## Magic

(nothing outstanding)

## Classes

- Full multiclassing (allowing remorts on the same char into all available classes), possibly tiering (start back with 1 class, but with perm bonuses, e.g. to starting skill proficiencies/stats/etc.)

## Commands

- Genuinely still-deferred commands (commented-out rows in
  `commands.py:_CMD_TABLE`): `gossip`, `shout`, `alias`/`unalias`, `group`,
  `bank`, `auction`, `path`, `play`, immortal commands. Port when/if a solo
  gameplay hook appears.

## Area data

- **Deferred runtime hooks for converter-emitted fields** — the 2026-07
  converter audit brought `are_to_primesud.py` (the single ROM 2.4
  converter; formerly `are_to_primesud_quickmud.py`, renamed after the
  1stMud-format converter was deleted) to a lossless schema; these emitted
  fields are captured in the `.txt` files but not yet consumed at runtime:
  - E/G reset `limit` (raw arg2; >50 means legacy 6, <=0 unlimited) — resets
    currently spawn without count enforcement
  - object `condition` (spawn wear-state), `light_hours` (light burnout),
    `no_sac`, container `container_max_item_weight` / `container_weight_mult`,
    food/drink `poisoned`
  - mob `default_pos` (spawn `start_pos` IS consumed -- `mob.py` sets
    initial position -- but nothing returns idle mobs to `default_pos`),
    `group`, `material`, `mob_triggers`
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
- **`flag_affects` on objects parsed+stored but no runtime consumer yet** —
  `.are` F-trailer affect/immune/resist/vuln grants (e.g. One Ring
  invisibility, `src/area_shire.txt` object 1105); see docs/AREA_FILES.md
  OBJECTS section.
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
