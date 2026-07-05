# TODO

Loose ends that don't belong in a specific plan file.

## Combat

- **PC race aff/imm/res/vuln/stats not applied** — 1stMud's race-assignment
  path (nanny.c:533ff / save.c:723ff) also ORs race `aff`/`imm`/`res`/`vuln`
  into the char and sets `perm_stat`/`size` from race, like `mob.py` does for
  mobs. `player.py create_char` only merges `form`/`parts` (05/07/2026);
  elf infravision, dwarf poison/disease resist etc. are inert for PCs.
  Low-stakes while only "Human" is selectable (no race chargen yet).

## Items

- **`do_put` accepts corpses** — `_CONTAINER_TYPES` includes
  `npc_corpse`/`pc_corpse`, but 1stMud `do_put` requires strict
  ITEM_CONTAINER (corpses are separate item types): lootable, not stashable.
- **`do_pick` doors only** — containers now honour `locked`/`pickproof`
  (05/07/2026), but lockpicking still has no container branch, so a
  locked+pickproof-with-no-key container is permanently sealed.
- **Template-only type lookups remain in `do_envenom` and `do_quaff`** —
  instance `type` overrides (e.g. death_cry's trash downgrade) now gate
  `do_eat` via `_item_type`, but envenom/quaff still read the template only.

(do_eat instance type/poisoned overrides, container closed/locked flags, and
do_put's can_drop_obj check landed 05/07/2026 -- see inventory.py _item_type/
_is_poisoned_food, item.py container_flags helpers, movement.py
_open_container et al.)

## Magic

(elemental `effects.c` port and non-caster cast-level scaling landed
05/07/2026 -- nothing outstanding)

## Classes

- Full multiclassing (allowing remorts on the same char into all available classes), possibly tiering (start back with 1 class, but with perm bonuses, e.g. to starting skill proficiencies/stats/etc.)

## Commands

- Genuinely still-deferred commands (commented-out rows in
  `commands.py:_CMD_TABLE`): `gossip`, `shout`, `alias`/`unalias`, `group`,
  `bank`, `auction`, `path`, `play`, immortal commands. Port when/if a solo
  gameplay hook appears.

## Area data

- **Deferred runtime hooks for converter-emitted fields** — the 2026-07
  converter audit brought both converters (`are_to_primesud.py`,
  `are_to_primesud_quickmud.py`) to a common lossless schema; these emitted
  fields are captured in the `.dat` files but not yet consumed at runtime:
  - E/G reset `limit` (raw arg2; >50 means legacy 6, <=0 unlimited) — resets
    currently spawn without count enforcement
  - object `condition` (spawn wear-state), `light_hours` (light burnout),
    `no_sac`, `flag_affects` (F-line affect/immune/resist/vuln grants),
    container `container_max_item_weight` / `container_weight_mult`,
    food/drink `poisoned`
  - mob `default_pos` (spawn `start_pos` IS consumed -- `mob.py` sets
    initial position -- but nothing returns idle mobs to `default_pos`),
    `group`, `material`, `mob_triggers`
  - room `heal_rate`/`mana_rate`, `owner`
- **`_unknown_bits` in quest.are** — stock 1stMud data sets ACT bits 11/31 and
  AFF bits 34/36 that are undefined even in 1stMud's own `bits.h`; preserved
  losslessly under `_unknown_bits`, no runtime meaning.

## Tests

- **`conftest.py` `fresh_world` doesn't restore lazy-load state** — it clears
  `world._LOADED_AREAS`/`_TAG_TO_FILE`/`_VNUM_RANGES` at setup and teardown
  without saving/restoring, so a later test that lazily loads a real vnum via
  `ITEM_DEFS[vnum]` can `KeyError` depending on run order.
  `test_carry_and_align.py` sidesteps it by pre-seeding money templates.

## Platform

- `tml.py` `read_key()` still uses `get_key()`, which has a firmware race that
  swallowed keystrokes in the non-blocking path (see comment near
  `tml_prime.py:poll_char`). If blocking input ever drops keystrokes, apply the
  same `keyboard()`-polling fix via a `tml_prime` override.
- **Validate on-device memory footprint** of `skills_table.py` (149 skills) +
  `groups.py` + `classes.py` — flagged when the table grew from 6 to 149
  entries; no HP Prime heap test on record.
