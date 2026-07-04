# TODO

Loose ends that don't belong in a specific plan file.

## Combat

- **Body-part drops via `death_cry`** (was CORPSE_PLAN Phase 4) — race `part_flags`
  now populated on every mob instance (`mob.py` merges race `parts`); body-part
  objects exist in `area_limbo.py` (`I_HEAD`, `I_HEART`, ...). `_death_cry`
  (`combat.py`) is still uniform-random text only: no part-flag gating, no
  body-part object creation, no adjacent-room cry broadcast. Prereq (race data)
  is satisfied; implement per 1stMud `death_cry` in `fight.c`. Fold in the
  deferred sub-items: poison food from mob `form` flags.

## Items

- **Weight/count limits not enforced in `do_get`/`do_put`** — `can_carry_w` /
  `get_obj_weight` / `can_carry_n` exist and are enforced in `do_give` and
  `do_buy`, but `do_get` and `do_put` (`inventory.py`) never call them.
- **Alignment-restricted wear not enforced** — `anti_good`/`anti_evil`/
  `anti_neutral` extra_flags are parsed from area data and drive the post-kill
  equipment zap (`combat.py`), but `wear_obj` (`inventory.py`) never blocks
  wearing an anti-aligned item.
- `drop <n> gold` / `drop <n> silver` unimplemented (no coin-drop path in
  `inventory.py`).
- **Mob `extra_descs` not checked in `do_look`** — room/item extra_descs work
  via `_get_ed`; the mob branch (`info.py`) short-circuits before any
  extra_desc lookup.

## Magic

- **Elemental object/room side-effects from `effects.c` not ported** —
  `acid_effect`/`fire_effect`/`cold_effect`/`shock_effect`/`poison_effect`
  (item destruction, blind/daze chances). Breath, damage, and weapon-proc
  spells apply raw damage only; see inline `# TODO [PRIMESUD]` markers in
  `magic.py` and `combat.py:_weapon_procs`.
- **Revisit spell cast level scaling** — `do_cast` still passes full
  `player["level"]` regardless of class (tagged `# [PRIMESUD] classless` in
  `magic.py`). Classes exist now; 1stMud casts non-casters at `3 * level / 4`.

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
  - mob `start_pos`/`default_pos` (long-form strings; `config.py`
    `POS_FROM_SHORT` only has short keys, so non-"standing" values silently
    fall back to standing), `group`, `material`, `mob_triggers`
  - room `heal_rate`/`mana_rate`, `owner`
- **`_unknown_bits` in quest.are** — stock 1stMud data sets ACT bits 11/31 and
  AFF bits 34/36 that are undefined even in 1stMud's own `bits.h`; preserved
  losslessly under `_unknown_bits`, no runtime meaning.

## Platform

- `tml.py` `read_key()` still uses `get_key()`, which has a firmware race that
  swallowed keystrokes in the non-blocking path (see comment near
  `tml_prime.py:poll_char`). If blocking input ever drops keystrokes, apply the
  same `keyboard()`-polling fix via a `tml_prime` override.
- **Validate on-device memory footprint** of `skills_table.py` (149 skills) +
  `groups.py` + `classes.py` — flagged when the table grew from 6 to 149
  entries; no HP Prime heap test on record.
