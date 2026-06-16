# PrimeSUD — Area File Reference

Area files are Python modules (`area_<name>.py`) in `primesud.hpappdir/`. They replace
the text-based `.are` files used by 1stMud — parsing text at runtime would be
memory-intensive and slow on the HP Prime. The structure mirrors 1stMud's sections but
uses plain Python dicts and tuples.

> **Do not edit area files directly.** They are generated from `.are` source files by
> `tools/are_to_primesud.py`. Edit the converter and regenerate instead.

`world.py` loads every area module and merges `ROOMS`, `MOBILES`, `OBJECTS`, and
`RESETS` into the game-wide tables. `SKILL_TABLE` and `SKILLS` live in `world.py`
directly — skills are global, not per-area.

Cross-area VNUM constants that game logic needs to hardcode (e.g. respawn room, skill
IDs) go in `world_consts.py`. Area files may define their own local constants for
internal cross-referencing only.

---

## Module layout

Sections appear in this fixed order:

```
# fmt: off          ← must be first line; keeps aligned dicts from being reformatted
# Area: <name>
# Builders: <names>
# VNUM ranges: Rooms XXXX-XXXX, Mobs XXXX-XXXX, Items XXXX-XXXX

AREA = { ... }      ← area metadata

# ── Room VNUMs ──
R_FOO = 1234
...

# ── Mob template VNUMs ──
M_FOO = 1234
...

# ── Item template VNUMs ──
I_FOO = 1234
...

# ── Rooms ──
ROOMS = { ... }

# ── Mob templates ──
MOBILES = { ... }

# ── Item templates ──
OBJECTS = { ... }

# ── Resets ──
RESETS = ( ... )
```

---

## `AREA` — metadata dict

```python
AREA = {
    "name":     "Mud School",
    "builders": "None",
    "vnums":    (3700, 3799),   # inclusive VNUM range claimed by this area
    "credits":  "Hatchet",
    "levels":   (1, 5),         # recommended level range
    "version":  4,              # .are file version (informational)
}
```

All fields are optional except `name` and `vnums`. `world.py` uses `vnums` to detect
VNUM collisions at load time.

---

## VNUM constants

Each section declares named constants before its dict so the dicts can reference other
rooms/mobs/items by name rather than bare integers.

| Prefix | Meaning            | Example                       |
|--------|--------------------|-------------------------------|
| `R_`   | Room VNUM          | `R_VILLAGE_SQUARE = 1000`     |
| `M_`   | Mob template VNUM  | `M_GOBLIN = 2001`             |
| `I_`   | Item template VNUM | `I_IRON_SWORD = 3000`         |

Within an area file, always reference by constant name, never by raw integer. Raw
integers are acceptable only for exits that point to rooms in other areas (those VNUMs
belong to `world_consts.py` or are self-evident from context).

---

## `ROOMS`

```python
ROOMS = {
    R_VILLAGE_SQUARE: {
        "name":   "Village Square",
        "desc":   "Long multi-line description...",
        "exits":  {"n": R_MARKET, "s": R_DUNGEON_ENTRANCE},
        "flags":  {"no_mob": True, "indoors": True},
        "sector": 1,
    },
    ...
}
```

| Key      | Type           | Required | Notes |
|----------|----------------|----------|-------|
| `name`   | str            | yes      | Shown in the room header line |
| `desc`   | str            | yes      | Room description; use `\n` for line breaks |
| `exits`  | dict           | yes      | Direction string → destination VNUM. Valid directions: `"n"`, `"e"`, `"s"`, `"w"`, `"u"`, `"d"` |
| `flags`  | dict           | no       | Boolean room flags (see below) |
| `sector` | int            | no       | Terrain type; defaults to `0` if omitted |

### Room flags

| Flag            | Meaning |
|-----------------|---------|
| `no_mob`        | Mobs will not wander into this room |
| `indoors`       | Room is inside a building |
| `dark`          | Room is unlit; player needs a light source |
| `safe`          | No combat allowed |
| `_unknown_bits` | List of uninterpreted bit positions from the original `.are` conversion; preserve, don't add new ones |

### Doors

Use a dict instead of a plain integer for exits that have a door. Only include keys whose value is `True` — the converter never emits `False` entries:

```python
"exits": {
    "e": {"to": R_LOCKED_ROOM, "isdoor": True, "closed": True, "locked": True},
},
```

| Key            | Meaning |
|----------------|---------|
| `to`           | Destination VNUM (always present in dict form) |
| `isdoor`       | Required for `open`/`close` to work |
| `closed`       | Door starts closed |
| `locked`       | Door starts locked (implies `closed`) |
| `pickproof`    | Cannot be picked |
| `nopass`       | Blocks `pass door` spell |
| `doorbell`     | Has a doorbell |
| `easy`/`hard`/`infuriating` | Pick difficulty |
| `noclose`      | Cannot be closed |
| `nolock`       | Cannot be locked |

The automap will not draw past a currently-closed door (matching 1stMud behaviour).

---

## `MOBILES`

```python
MOBILES = {
    M_GOBLIN: {
        "name":      "Goblin",
        "desc":      "A goblin crouches here, eyeing you hungrily.",
        "level":     3,
        "hp_dice":   (3, 3, 10),   # max HP = 3d3 + 10
        "hitroll":   1,
        "AC":        0,
        "damage":    (1, 4, 1),    # per hit: 1d4 + 1
        "gold":      15,
        "act_flags": {"aggressive": True, "stay_area": True},
        "aff_flags": {"infrared": True},
        "off_flags": {"dodge": True, "trip": True},
        "imm_flags": {"charm": True},
        "res_flags": {"poison": True},
        "vuln_flags": {"magic": True},
    },
    ...
}
```

| Key         | Type  | Required | Notes |
|-------------|-------|----------|-------|
| `name`      | str   | yes      | Short name used in combat messages |
| `desc`      | str   | yes      | "A foo is here." line shown in room |
| `level`     | int   | yes      | Used to derive THAC0 and stat scaling |
| `hp_dice`   | tuple | yes      | `(num_dice, die_size, bonus)` — max HP |
| `hitroll`   | int   | yes      | Added to attack roll |
| `AC`        | int   | yes      | Armour class; lower is better (negative = very hard to hit) |
| `damage`    | tuple | yes      | `(num_dice, die_size, bonus)` per hit |
| `dam_type`  | str   | yes      | Attack noun for combat messages (e.g. `'claw'`, `'bite'`, `'beating'`); also the damage category for future resistance checks |
| `gold`      | int   | yes      | Gold carried (unused until economy is implemented) |
| `act_flags` | dict  | no       | Behaviour flags (see below) |
| `aff_flags` | dict  | no       | Permanent affect flags |
| `off_flags` | dict  | no       | Combat offence flags |
| `imm_flags` | dict  | no       | Damage immunities |
| `res_flags` | dict  | no       | Damage resistances (half damage) |
| `vuln_flags`| dict  | no       | Damage vulnerabilities (double damage) |

### `act_flags`

| Flag          | Meaning |
|---------------|---------|
| `sentinel`    | Does not wander |
| `aggressive`  | Attacks players on sight |
| `wimpy`       | Flees when HP drops low |
| `stay_area`   | Will not follow players out of the area |
| `scavenger`   | Picks up items from the ground |
| `train`       | Mob is a trainer (for `train` command) |
| `practice`    | Mob is a practitioner (for `practice` command) |
| `nopurge`     | Survives area purge |
| `noalign`     | No alignment (informational; alignment not implemented) |
| `cleric`      | Has cleric skills (informational) |
| `warrior`     | Has warrior skills (informational) |

### `off_flags` (combat)

Common values: `area_attack`, `bash`, `berserk`, `crush`, `disarm`, `dodge`, `fast`,
`kick`, `kick_dirt`, `parry`, `tail`, `trip`, `assist_race`.

### `aff_flags` (affects)

Common values: `detect_evil`, `infrared`, `dark_vision`, `sanctuary`.

---

## `OBJECTS`

```python
OBJECTS = {
    I_IRON_SWORD: {
        "name":        "Iron Sword",
        "desc":        "A plain iron sword lies here.",
        "type":        "weapon",
        "slot":        "weapon",
        "weight":      30,
        "value":       200,
        "dice":        (1, 6, 0),    # weapon only: damage dice
        "weapon_type": "sword",      # weapon only
        "hitroll":     1,            # weapon only
        "damroll":     0,            # weapon only
        "extra_flags": {"melt_drop": True},
    },
    I_LEATHER_VEST: {
        "name":   "Leather Vest",
        "desc":   "A worn leather vest lies here.",
        "type":   "armor",
        "slot":   "body",
        "weight": 40,
        "value":  100,
        "AC":     1,                 # armor only: AC bonus
        "extra_flags": {},
    },
    ...
}
```

| Key           | Type       | Required    | Notes |
|---------------|------------|-------------|-------|
| `name`        | str        | yes         | Shown in inventory and equipment lists |
| `desc`        | str        | yes         | "You see a foo here." line in rooms |
| `type`        | str        | yes         | `weapon`, `armor`, `key`, `treasure`, `light`, … |
| `slot`        | str\|None  | yes         | Equipment slot; `None` for non-wearable items |
| `weight`      | int        | yes         | Item weight (currently informational) |
| `value`       | int        | yes         | Shop buy price (unused until economy implemented) |
| `dice`        | tuple      | weapons     | `(num_dice, die_size, bonus)` — damage roll |
| `weapon_type` | str        | weapons     | `sword`, `dagger`, `mace`, `axe`, `flail`, `whip`, `staff`, `polearm`, … |
| `dam_type`    | str        | weapons     | Attack noun for combat messages, matching `attack_table` (e.g. `'slash'`, `'pierce'`, `'pound'`) |
| `hitroll`     | int        | weapons     | Added to attack roll when wielded |
| `damroll`     | int        | weapons     | Added to damage roll when wielded |
| `AC`          | int        | armor       | AC bonus when worn |
| `extra_flags` | dict       | no          | Item flags (see below) |

### Equipment slots

`weapon`, `shield`, `body`, `head`, `legs`, `feet`, `hands`, `arms`, `neck`, `waist`,
`wrist`, `about`, `hold`

### `extra_flags`

| Flag         | Meaning |
|--------------|---------|
| `glow`       | Item glows (acts as light source) |
| `magic`      | Item is magical |
| `melt_drop`  | Item disappears when dropped (starter gear guard) |
| `_unknown_bits` | Uninterpreted bits from `.are` conversion |

---

## `RESETS`

```python
RESETS = (
    ("M", M_GOBLIN, 3, R_DUNGEON_HALL, 3),  # spawn goblin: global_limit=3, room_limit=3
    ("E", I_IRON_SWORD, "wield"),            # equip sword on last M mob
    ("G", I_GOLD_POUCH),                     # give pouch to last M mob's inventory
    ("O", I_IRON_SWORD, R_DUNGEON_HALL),     # place one item copy in room
    ...
)
```

| Command | Format                                                          | Meaning |
|---------|-----------------------------------------------------------------|---------|
| `"M"`   | `("M", mob_vnum, global_limit, room_vnum, room_limit)`         | Spawn mob up to both caps; sets mob context for E/G |
| `"O"`   | `("O", item_vnum, room_vnum)`                                  | Place one item copy in room; clears mob context |
| `"E"`   | `("E", item_vnum, slot_name)`                                  | Equip item on last M mob; skipped if last M was capped |
| `"G"`   | `("G", item_vnum)`                                             | Give item to last M mob's inventory; skipped if last M was capped |
| `"P"`   | `("P", item_vnum, limit, container_vnum, max)`                 | [PRIMESUD] deferred: no container system yet |
| `"R"`   | `("R", room_vnum, num_dirs)`                                   | [PRIMESUD] deferred: unused in current areas |

**F and D .are resets** are consumed at conversion time and baked into the room exits
dict — they do not appear in `RESETS`.  F completely overwrites a door's exit flags;
D sets its closed/locked state.  On every area reset, `reset_area()` restores all
door exits to the state encoded in the exits dict.

**Mob limits and dynamic allocation.** `reset_mobs(mob_instances, room_state, resets)`
in `player.py` processes each `"M"` entry and spawns at most one instance if both caps
allow it: `global_limit` (max live instances of that template across all rooms) and
`room_limit` (max live instances in that specific room). Dead mobs are removed from
`mob_instances` immediately on death — there are no `state="dead"` slots. On the area
tick, `reset_mobs` is called on the live `mob_instances` dict; missing mobs are
filled up to their limits one per reset cycle, matching 1stMud's `reset_room` 'M'
behaviour. `reset_area()` (game start / full wipe only) creates a fresh empty
`mob_instances` and calls `reset_mobs` to populate it.

---

## Conventions

- **`# fmt: off` is mandatory.** The aligned column style in VNUM constants and mob/item
  dicts would be destroyed by an auto-formatter. Do not remove it.
- **`_unknown_bits`** keys in flag dicts record uninterpreted bit positions from the
  original `.are` file. Preserve them; do not add new ones manually.
- **`# TODO` comments** mark `.are` features that weren't converted because the
  corresponding PrimeSUD system (doors, mob equipment, shops) is not yet implemented.
  Keep them verbatim from the source file so the original data isn't lost.
