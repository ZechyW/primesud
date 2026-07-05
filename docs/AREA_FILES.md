# PrimeSUD — Area File Reference

Area files are generated `.txt` files (`area_<name>.txt`) in `src/`, holding plain
Python source that `world.py` `exec()`s at load time. `.txt` rather than `.py` so
build/transfer tooling doesn't mistake them for binary; the content is Python dicts
and tuples, same as any other module. They replace the text-based `.are` files used
by 1stMud/ROM — parsing text at runtime would be memory-intensive and slow on the
HP Prime. The structure mirrors ROM 2.4's `#SECTION` layout.

> **Do not edit area files directly.** They are generated from ROM 2.4 (QuickMUD-dialect)
> `.are` source files in `areas/` by `tools/are_to_primesud.py`. Edit the
> `.are` source or the converter and regenerate via `tools/regen_areas.sh` instead.
> `areas/*.are` are editable working copies; pristine upstream originals remain under
> `reference/`.

`world.py` loads every area module and merges `ROOMS`, `MOBILES`, `OBJECTS`, and
`RESETS` into the game-wide tables. `SKILL_TABLE` and `SKILLS` live in `world.py`
directly — skills are global, not per-area.

Cross-area VNUM constants that game logic needs to hardcode (e.g. respawn room, skill
IDs) go in `world_consts.py`.

**No named VNUM constants in generated files.** Room/mob/item VNUMs appear as raw
integers everywhere — dict keys, `exits`, `RESETS` — not as `R_FOO`/`M_FOO`/`I_FOO`
names. Cross-reference VNUMs by reading the `.are` source or the area's
`# VNUM ranges` header comment.

**The converter fails loudly on anything it doesn't handle** (2026-07-05 audit,
mirroring QuickMUD's own `bug()`+`exit(1)` loader behavior): unknown `#SECTION`
names (including `#AREADATA` new-style headers and legacy `#MOBOLD`/`#OBJOLD`),
unrecognized trailer/command letters in rooms, resets, and specials, malformed
or truncated payloads, out-of-range exit/reset directions, and `spec_fun` names
not present in `src/special.py`'s `SPEC_TABLE` all raise `ValueError` rather
than silently dropping data. Trailer payloads split across physical lines
(legal under ROM's whitespace-skipping readers) are handled for object `A`/`F`
and mob `F` lines.

---

## Module layout

Sections appear in this fixed order:

```
# fmt: off              <- must be first line; keeps aligned dicts from being reformatted
# Area: <name>
# Source: QuickMUD/ROM 2.4
# VNUM ranges: <lo>-<hi>
# Credits: <text>

AREA = { ... }          <- area metadata

# -- Mob templates --
MOBILES = { ... }

# -- Rooms --
ROOMS = { ... }

# -- Item templates --
OBJECTS = { ... }

# -- Resets --
RESETS = ( ... )

# -- Helps --
HELPS = ( ... )

# -- Socials --
SOCIALS = ( ... )

# -- MobProgs --
MOBPROGS = { ... }
```

---

## `AREA` — metadata dict

```python
AREA = {
    "name":     "Shire",
    "builders": "None",           # QuickMUD old-style .are has no builder field
    "vnums":    (1100, 1199),     # inclusive VNUM range claimed by this area
    "credits":  "{ 5 35} Poohb   The Shire",
    "levels":   (5, 35),          # [PRIMESUD] heuristic parsed from credits text
}
```

All fields are always emitted. `world.py` uses `vnums` to detect VNUM collisions at
load time. `levels` is a converter heuristic, not derived data from ROM (old-style
`#AREA` headers carry no level range).

---

## `ROOMS`

```python
ROOMS = {
    1105: {
        "name":   "The General Store",
        "desc":   "You are inside the general store. ...",
        "exits":  {"s": {"to": 1104, "desc": "The only exit lies to the south."}},
        "flags":  {"indoors": True},
        "sector": "inside",
    },
    ...
}
```

| Key          | Type      | Required | Notes |
|--------------|-----------|----------|-------|
| `name`       | str       | yes      | Shown in the room header line |
| `desc`       | str       | yes      | Room description; `\n` for line breaks |
| `exits`      | dict      | yes      | Direction string -> destination (int, `None`, or door dict). Directions: `"n"`, `"e"`, `"s"`, `"w"`, `"u"`, `"d"` |
| `flags`      | dict      | no       | Boolean room flags (see below); omitted if none set |
| `sector`     | str       | no       | Terrain name (see `SECTOR_NAMES`); omitted if the source room line has no sector token. Runtime default when absent: `"inside"` (`room.get("sector", "inside")`) |
| `heal_rate`  | int       | no       | ROM `H` room trailer; percentage HP regen modifier |
| `mana_rate`  | int       | no       | ROM `M` room trailer; percentage mana regen modifier |
| `extra_descs`| list      | no       | `(keyword, desc)` tuples from `E` room trailers |
| `clan`       | str       | no       | ROM `C` room trailer (clan name) |
| `owner`      | str       | no       | ROM `O` room trailer (owner name) |

A destination of `None` means the exit exists (and is listed by `exits`/automap
data) but doesn't lead anywhere — ROM keeps such exits examinable but
untraversable rather than dropping them (`fix_exits` only nulls the destination
pointer).

### Room flags

Decoded from the ROM `room_flags` bitvector (see `ROOM_FLAGS` in the "Flag bits
reference" section below for the full bit map, including 1stMud extension bits).

| Flag            | Meaning |
|-----------------|---------|
| `dark`          | Room is unlit; player needs a light source |
| `no_mob`        | Mobs will not wander into this room |
| `indoors`       | Room is inside a building |
| `arena`         | 1stMud extension |
| `bank`          | 1stMud extension |
| `private`       | Limited to a small number of occupants |
| `safe`          | No combat allowed |
| `solitary`      | Only one occupant allowed |
| `pet_shop`      | Pet shop room |
| `no_recall`     | `recall` doesn't work here |
| `imp_only`      | Implementor-only |
| `gods_only`     | Immortal-only |
| `heroes_only`   | Hero-level-only |
| `newbies_only`  | Newbie-only |
| `law`           | Law-enforced (guards attack outlaws); also force-set on any room with VNUM in `[3000, 3400)` regardless of stored flags — a "horrible hack" ported verbatim from `db.c load_rooms` |
| `nowhere`       | Not a real location (informational) |
| `noexplore`     | 1stMud extension; excluded from explore-tracking |
| `noautomap`     | 1stMud extension; hidden from the automap |
| `save_objs`     | 1stMud extension; room contents persist across reboot/reset. No runtime reader yet [PRIMESUD] — carried by e.g. Limbo's Morgue room (vnum 3, `areas/limbo.are`) |
| `_unknown_bits` | List of uninterpreted bit positions from the original `.are` conversion; preserve, don't add new ones |

### Doors

Only include keys whose value is `True`/set — the converter never emits `False`
entries:

```python
"exits": {
    "e": {"to": 1234, "isdoor": True, "pickproof": True, "key": 3001,
          "desc": "A stout oak door blocks the way.", "keyword": "door"},
},
```

| Key         | Meaning |
|-------------|---------|
| `to`        | Destination VNUM, or `None` (see above). Always present in dict form |
| `desc`      | Extra look-description text for the exit direction (`D`-trailer desc string) |
| `keyword`   | Feature keyword matched by `look <keyword>`/`open <keyword>` etc. |
| `isdoor`    | Required for `open`/`close` to work |
| `pickproof` | Cannot be picked |
| `nopass`    | Blocks `pass door` spell |
| `key`       | VNUM of the key item that opens/locks this door (0/absent = no key) |
| `closed`    | Door starts closed — only set via a `D`-reset override (see RESETS) |
| `locked`    | Door starts locked, implies `closed` — only set via a `D`-reset override |

`easy`/`hard`/`infuriating` (pick difficulty), `doorbell`, `noclose`, `nolock` are
part of the emitter's schema (`emit()` checks for them) but the ROM 2.4 `.are`
lock encoding used by the current converter (`0`=open, `1`=door, `2`=+pickproof,
`3`=+nopass, `4`=+pickproof+nopass) has no source data for them, so no current
area file sets them.

The automap will not draw past a currently-closed door (matching 1stMud behaviour).

---

## `MOBILES`

```python
MOBILES = {
    1101: {
        "keywords":    "oldstyle ring keeper",
        "short_descr": "the Keeper of the Ring",
        "long_descr":  "The Keeper of the Ring is here, guarding his treasure jealously.",
        "description": "The Ring Keeper is a rather big but short halfling. ...",
        "race":        "Human",
        "act_flags":   {"sentinel": True, "stay_area": True, "thief": True},
        "affected_by": {"invisible": True, "detect_invis": True},
        "alignment":   0,
        "level":       20,
        "hitroll":     0,
        "hp_dice":     (3, 9, 308),     # max HP = 3d9 + 308
        "mana_dice":   (10, 9, 100),
        "damage":      (2, 7, 5),  "dam_type": "none",
        "armor":       (-4, -4, -4, 6),
        "off_flags":   {"backstab": True, "dodge": True},
        "start_pos":   "stand",
        "default_pos": "stand",
        "material":    "0",
        "sex":         "male",
        "wealth":      61,
        "size":        "medium",
        "spec_fun":    "spec_thief",
    },
    ...
}
```

| Key            | Type  | Required | Notes |
|----------------|-------|----------|-------|
| `keywords`     | str   | yes      | Space-separated match words for targeting the mob |
| `short_descr`  | str   | yes      | Name used in combat/inventory messages (e.g. "the Keeper of the Ring") |
| `long_descr`   | str   | yes      | "X is here" line shown when the mob is present in a room |
| `description`  | str   | yes      | Full paragraph shown on `look <mob>` |
| `race`         | str   | yes      | `RACE_TABLE` key (capitalized, e.g. `"Human"`); race defaults are merged in at mob creation |
| `act_flags`    | dict  | no       | Behaviour flags (see below); `is_npc` (bit 0) is always set and omitted from the dict |
| `affected_by`  | dict  | no       | Permanent affect flags |
| `alignment`    | int   | yes      | -1000..1000 |
| `group`        | int   | no       | ROM mob group number; omitted when `0` |
| `level`        | int   | yes      | Used to derive THAC0 and stat scaling |
| `hitroll`      | int   | yes      | Added to attack roll |
| `hp_dice`      | tuple | yes      | `(num_dice, die_size, bonus)` — max HP |
| `mana_dice`    | tuple | yes      | `(num_dice, die_size, bonus)` — max mana |
| `damage`       | tuple | yes      | `(num_dice, die_size, bonus)` per hit |
| `dam_type`     | str   | yes      | Attack noun for combat messages |
| `armor`        | tuple | yes      | `(pierce, bash, slash, exotic)` armor buckets from `.are`; lower is better |
| `off_flags`    | dict  | no       | Combat offence flags |
| `imm_flags`    | dict  | no       | Damage immunities |
| `res_flags`    | dict  | no       | Damage resistances (half damage) |
| `vuln_flags`   | dict  | no       | Damage vulnerabilities (double damage) |
| `start_pos`    | str   | yes      | Spawn position (e.g. `"stand"`, `"sleep"`) |
| `default_pos`  | str   | yes      | Position the mob returns to when idle. `start_pos` is consumed at spawn (`mob.py`); nothing currently returns idle mobs to `default_pos` [PRIMESUD deferred] |
| `form_flags`   | dict  | no       | Body form (e.g. `biped`, `animal`, `undead`) |
| `part_flags`   | dict  | no       | Body parts present (for dismemberment-style messages) |
| `material`     | str   | yes      | Body material; often `"0"` for old-style `.are` mobs |
| `sex`          | str   | yes      | `"male"`, `"female"`, `"neutral"` |
| `wealth`       | int   | yes      | Gold carried (unused until economy is implemented) |
| `size`         | str   | yes      | `"tiny"`..`"huge"` etc. |
| `mob_triggers` | tuple | no       | `(trig_type, mprog_vnum, trig_phrase)` — see MOBPROGS below; omitted if empty |
| `flag_removes` | tuple | no       | `(canonical_field, flag_names)` — `F`-trailer bit removals applied after race-merge at runtime (cf. `mob.py create_mobile`, ROM `db2.c` `REMOVE_BIT`) |
| `spec_fun`     | str   | no       | See SPECIALS below |
| `shop`         | dict  | no       | See SHOPS below |

### `act_flags`

| Flag          | Meaning |
|---------------|---------|
| `sentinel`    | Does not wander |
| `aggressive`  | Attacks players on sight |
| `wimpy`       | Flees when HP drops low |
| `stay_area`   | Will not follow players out of the area |
| `scavenger`   | Picks up items from the ground |
| `pet`         | Mob is a pet template |
| `train`       | Mob is a trainer (for `train` command) |
| `practice`    | Mob is a practitioner (for `practice` command) |
| `undead`      | Undead |
| `nopurge`     | Survives area purge |
| `noalign`     | No alignment (informational; alignment not implemented) |
| `outdoors`    | Only found outdoors (informational) |
| `indoors`     | Only found indoors (informational) |
| `cleric`      | Has cleric skills (informational) |
| `mage`        | Has mage skills (informational) |
| `thief`       | Has thief skills (informational) |
| `warrior`     | Has warrior skills (informational) |
| `healer`      | Healer shop-style mob |
| `gain`        | Mob is a class-gain trainer |
| `update_always` | Updated even when no players are in the room |
| `changer`     | Shapechanger |

### `off_flags` (combat)

Common values: `area_attack`, `backstab`, `bash`, `berserk`, `disarm`, `dodge`,
`fade`, `fast`, `kick`, `kick_dirt`, `parry`, `rescue`, `tail`, `trip`, `crush`,
`assist_all`, `assist_align`, `assist_race`, `assist_players`, `assist_guard`,
`assist_vnum`.

### `affected_by` (affects)

Common values: `blind`, `invisible`, `detect_evil`, `detect_invis`, `detect_magic`,
`detect_hidden`, `detect_good`, `sanctuary`, `faerie_fire`, `infrared`, `curse`,
`poison`, `protect_evil`, `protect_good`, `sneak`, `hide`, `sleep`, `charm`,
`flying`, `pass_door`, `haste`, `calm`, `plague`, `weaken`, `dark_vision`,
`berserk`, `swim`, `regeneration`, `slow`.

### `form_flags` / `part_flags`

Common `form_flags` values: `edible`, `poison`, `magical`, `animal`, `sentient`,
`undead`, `construct`, `biped`, `dragon`, `snake`. Common `part_flags` values:
`head`, `arms`, `legs`, `heart`, `hands`, `feet`, `claws`, `fangs`, `wings`, `tail`.

---

## `spec_fun` (baked from `.are` `#SPECIALS`)

```python
1113: {
    ...
    "spec_fun": "spec_cast_mage",
},
```

`#SPECIALS` entries are no longer emitted as a standalone `SPECIALS` tuple merged
at load time — the converter bakes each `("M", mob_vnum, spec_fun)` entry
directly into that mob's own `MOBILES[mob_vnum]["spec_fun"]` at conversion time.
Verified across all stock QuickMUD areas: specials never reference a mob vnum
outside their own file. **A `#SPECIALS` entry whose mob vnum isn't present in the
same file's `MOBILES` section is a hard conversion error** (`ValueError`), not a
silently dropped entry. PrimeSUD may ignore a `spec_fun` name until the matching
runtime behavior is ported.

---

## `OBJECTS`

```python
OBJECTS = {
    1105: {
        "keywords":    "one ring",
        "short_descr": "the One Ring",
        "description": "The One Ring is here.",
        "material":    "oldstyle",
        "type":        "jewelry",
        "wear_flags":  {"take": True, "finger": True},
        "extra_flags": {"magic": True},
        "stat_bonuses": {"str": -1},
        "flag_affects": (
            ("affects", "0", 0, {"invisible": True}),
        ),
        "level": 20, "weight": 30, "value": 1660,
    },
    1106: {
        "keywords":    "iron sword",
        "short_descr": "an iron sword",
        "description": "An iron sword lies here.",
        "material":    "iron",
        "type":        "weapon",
        "wear_flags":  {"take": True, "wield": True},
        "weapon_type": "sword", "dam_type": "slash", "dice": (1, 6, 0),
        "weapon_flags": {},
        "level": 5, "weight": 30, "value": 200,
    },
    ...
}
```

| Key            | Type       | Required     | Notes |
|----------------|------------|--------------|-------|
| `keywords`     | str        | yes          | Space-separated match words |
| `short_descr`  | str        | yes          | Shown in inventory/equipment lists |
| `description`  | str        | yes          | "You see a foo here." line in rooms |
| `material`     | str        | yes          | Freeform material string |
| `type`         | str        | yes          | `weapon`, `armor`, `light`, `container`, `drink`, `food`, `money`, `jewelry`, `treasure`, `trash`, `key`, ... (see `ITEM_TYPE_NUM`) |
| `wear_flags`   | dict       | yes          | Boolean equipment-slot/take flags (see below) |
| `no_sac`       | bool       | no           | Present (`True`) only when set; item cannot be sacrificed |
| `condition`    | int        | no           | Spawn wear-state (0-100); omitted when `100` (perfect, the default) |
| `extra_flags`  | dict       | no           | Item flags (see below); omitted if none set |
| `level`        | int        | yes          | |
| `weight`       | int        | yes          | Item weight (currently informational) |
| `value`        | int        | yes          | Shop buy price (unused until economy implemented) |
| `extra_descs`  | list       | no           | `(keyword, desc)` tuples; omitted if empty |
| `stat_bonuses` | dict       | no           | `{apply_loc_name: modifier}` from `.are` `A`-trailers |
| `flag_affects` | tuple      | no           | `.are` `F`-trailers — see below |

### Type-specific keys

| `type`                  | Keys |
|-------------------------|------|
| `weapon`                | `weapon_type`, `dam_type`, `dice` (num, die, bonus), `weapon_flags` (dict: `flaming`, `frost`, `vampiric`, `sharp`, `vorpal`, `two_hands`, `shocking`, `poison`) |
| `armor`                 | `armor`: `(pierce, bash, slash, exotic)` AC bonus when worn |
| `potion` / `pill` / `scroll` | `spell_level` (optional), `spells` (optional list of spell names) |
| `wand` / `staff`        | `spell_level`, `max_charges`/`charges`, `spell` (optional keys) |
| `light`                 | `light_hours` (optional) |
| `container`             | `container_max_weight` (optional), `container_flags` (dict: `closeable`, `pickproof`, `closed`, `locked`, `put_on`; optional), `container_key` (optional, >0 only), `container_max_item_weight`/`container_weight_mult` (optional pair; old-format containers default to `0`/`100`) |
| `drink` / `fountain`    | `liquid_total`/`liquid_left`/`liquid_type` (optional), `poisoned` (optional bool) |
| `food`                  | `food_hours`/`food_hunger` (optional), `poisoned` (optional bool) |
| `money`                 | `silver`/`gold` (optional pair) |
| any other type          | `values` (optional): raw `(value[0], ..., value[4])` tuple decoded per QuickMUD `db2.c`'s `default:` branch (all five via `fread_flag`). Covers `furniture` (max occupants, position flags), `key` (linked door/portal vnum), `map`, `portal`, `jukebox`, `warp_stone`, corpses, etc. Omitted when all five are zero; read via `obj.get("values", (0, 0, 0, 0, 0))`. No runtime consumer yet (see TODO.md). |

### `wear_flags` (equipment slots + take)

| Flag     | Meaning |
|----------|---------|
| `take`   | Item can be picked up (ROM `ITEM_TAKE`, bit 0) |
| `finger`, `neck`, `body`, `head`, `legs`, `feet`, `hands`, `arms`, `shield`, `about`, `waist`, `wrist`, `wield`, `hold`, `float` | Wearable in that slot |

### `extra_flags`

| Flag            | Meaning |
|-----------------|---------|
| `glow`          | Item glows (acts as light source) |
| `hum`           | Item hums |
| `dark`          | Item darkens surroundings |
| `lock`          | Lockable |
| `evil`/`bless`  | Alignment-detectable |
| `invis`         | Item is invisible |
| `magic`         | Item is magical |
| `nodrop`        | Cannot be dropped once held |
| `anti_good`/`anti_evil`/`anti_neutral` | Alignment-restricted |
| `noremove`      | Cannot be removed once worn |
| `inventory`     | Shows in `inventory` even if normally hidden |
| `nopurge`       | Survives area purge |
| `rot_death`/`vis_death` | Decays / stays visible on owner death |
| `auctioned`     | 1stMud extension (bit 17); no ROM `ITEM_*` define |
| `nonmetal`      | Not affected by metal-detection effects |
| `nolocate`      | Immune to `locate object` |
| `melt_drop`     | Item disappears when dropped (starter gear guard) |
| `had_timer`     | Had a decay timer at some point |
| `sell_extract`  | Removed from the game when sold |
| `burn_proof`    | Immune to fire damage to the item itself |
| `nouncurse`     | Cannot be uncursed |
| `quest`         | 1stMud extension (bit 26); gated on by `quest.py`/`shop.py`/`inventory.py`/`magic.py` |
| `_unknown_bits` | Uninterpreted bits from `.are` conversion |

### `flag_affects` (`.are` `F`-trailers)

```python
"flag_affects": (
    ("affects", "0", 0, {"invisible": True}),
),
```

Tuple of `(where, loc, modifier, flags)`:

| Field      | Meaning |
|------------|---------|
| `where`    | `"affects"` (grants an `affected_by` flag while worn/held) or `"immune"`/`"resist"`/`"vuln"` (grants a damage flag) |
| `loc`      | `APPLY_LOC` name for the affect location, or the raw numeric string if unrecognized (e.g. `"0"`) |
| `modifier` | Integer modifier value from the `.are` line |
| `flags`    | Decoded flag dict (`affected_by` names for `"affects"`, `RESIST_FLAGS` names otherwise) |

Parsed and stored losslessly (both one-line and two-line `F`-trailer layouts,
per `db2.c:536-569`'s whitespace-skipping reads); **no runtime consumer yet**
[PRIMESUD deferred]. Example: `src/area_shire.txt` object 1105 (the One Ring)
grants `invisible` while worn.

---

## `RESETS`

```python
RESETS = (
    ("M", 2001, 3, 1000, 3),   # spawn goblin: global_limit=3, room_limit=3
    ("E", 3000, "wield", 6),   # equip sword on last M mob, limit=6
    ("G", 3001, 0),            # give item to last M mob's inventory, unlimited
    ("O", 3000, 1000),         # place one item copy in room
    ...
)
```

| Command | Format                                                  | Meaning |
|---------|----------------------------------------------------------|---------|
| `"M"`   | `("M", mob_vnum, global_limit, room_vnum, room_limit)`   | Spawn mob up to both caps; sets mob context for E/G |
| `"O"`   | `("O", item_vnum, room_vnum)`                            | Place one item copy in room; clears mob context |
| `"E"`   | `("E", item_vnum, slot_name, limit)`                     | Equip item on last M mob; skipped if last M was capped |
| `"G"`   | `("G", item_vnum, limit)`                                | Give item to last M mob's inventory; skipped if last M was capped |
| `"P"`   | `("P", item_vnum, limit, container_vnum, max)`           | [PRIMESUD] deferred: no container system yet |
| `"R"`   | `("R", room_vnum, num_dirs)`                             | [PRIMESUD] deferred: not enforced by runtime yet |

**E/G `limit`** is the raw ROM reset-count field (cf. `db.c reset_room`): a value
`> 50` is a legacy encoding meaning limit 6; `-1` (or `0`, for E/G specifically)
means unlimited. Runtime enforcement of this limit is deferred [PRIMESUD].

**D resets** are consumed at conversion time and baked into the room exits dict —
they do not appear in `RESETS`. A `D` reset overwrites a door's `closed`/`locked`
state (case 0 = no change, 1 = set closed, 2 = set closed+locked). On every area
reset, `reset_area()` restores all door exits to the state encoded in the exits
dict.

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

## `shop` (baked from `.are` `#SHOPS`)

```python
1113: {
    ...
    "shop": {"keeper": 1113, "buy_types": ["drink"],
             "profit_buy": 150, "profit_sell": 50,
             "open_hour": 0, "close_hour": 23},
},
```

Like `spec_fun`, `#SHOPS` entries are no longer emitted as a standalone `SHOPS`
tuple merged at load time — the converter bakes each shop dict directly into its
keeper mob's own `MOBILES[keeper]["shop"]` at conversion time. Same hard-error
rule as `spec_fun`: a `#SHOPS` entry whose keeper vnum isn't present in the same
file's `MOBILES` section is a conversion error, not a silently dropped entry.

| Key           | Type    | Notes |
|---------------|---------|-------|
| `keeper`      | int     | Mob VNUM that runs the shop; redundant with the dict's own key but kept (matches what `world.py` used to assign) |
| `buy_types`   | list    | Item type names the shop will purchase (e.g. `"weapon"`, `"armor"`, `"drink"`). Empty list = sell-only |
| `profit_buy`  | int     | Percentage of item value the player pays when buying (100 = no markup) |
| `profit_sell` | int     | Percentage of item value the player receives when selling |
| `open_hour`   | int     | Game hour the shop opens (0-23) |
| `close_hour`  | int     | Game hour the shop closes (0-23) |

[PRIMESUD] deferred: buy/sell commands not yet implemented.

---

## `HELPS`

```python
HELPS = (
    {"level": 0, "keyword": "COLOUR COLOR ANSI",
     "text": "Syntax: colour    Toggles colour mode on/off\n..."},
    ...
)
```

| Key       | Type | Notes |
|-----------|------|-------|
| `level`   | int  | Minimum player level to see this help entry (0 = all) |
| `keyword` | str  | Space-separated keywords that match the `help` command argument |
| `text`    | str  | Full help text body |

---

## `SOCIALS`

```python
SOCIALS = (
    {"name": "smile",
     "char_no_arg": "You smile happily.",
     "others_no_arg": "$n smiles happily.",
     "char_found": "You smile at $M.",
     "others_found": "$n beams a smile at $N.",
     "vict_found": "$n smiles at you.",
     "char_not_found": "There's no one by that name around.",
     "char_auto": "You smile at yourself.",
     "others_auto": "$n smiles at $mself."},
    ...
)
```

| Key              | Type     | Notes |
|------------------|----------|-------|
| `name`           | str      | Social command name (e.g. `smile`, `bow`) |
| `char_no_arg`    | str\|None | Message to actor when used without a target |
| `others_no_arg`  | str\|None | Message to room when used without a target |
| `char_found`     | str\|None | Message to actor when target is found |
| `others_found`   | str\|None | Message to room when target is found |
| `vict_found`     | str\|None | Message to the target |
| `char_not_found` | str\|None | Message to actor when target is not found |
| `char_auto`      | str\|None | Message to actor when targeting self |
| `others_auto`    | str\|None | Message to room when actor targets self |

Message strings use ROM substitution tokens: `$n` = actor, `$N` = target, `$m`/`$M` =
him/her/it, `$s`/`$S` = his/her/its. `None` = no message for that case.

Socials are global (not per-area) in ROM. The converter preserves them per-file;
`world.py` merges all `SOCIALS` tuples into one table at load time.

[PRIMESUD] deferred: social commands not yet implemented.

---

## `MOBPROGS`

```python
MOBPROGS = {
    1234: "if rand(50)\n  say Hello!\nendif\n",
    ...
}
```

| Key  | Type | Notes |
|------|------|-------|
| vnum | int  | Mob program VNUM (dict key) |
| code | str  | Program source code (ROM mob_prog language) |

Mob templates reference programs via `mob_triggers` in their `MOBILES` entry:

```python
1200: {
    ...
    "mob_triggers": (
        ("greet", 1234, "100"),   # (trig_type, mprog_vnum, trig_phrase)
        ("speech", 1235, "help"),
    ),
},
```

| Trigger type | Fires when |
|--------------|------------|
| `act`        | An act() message matches the trigger phrase |
| `bribe`      | Player gives gold >= trigger phrase amount |
| `death`      | Mob dies |
| `entry`      | Mob enters a room |
| `fight`      | Each combat round |
| `give`       | Player gives an item to mob |
| `greet`      | Player enters mob's room (mob can see them) |
| `grall`      | Player enters mob's room (any visibility) |
| `hpcnt`      | Mob HP% drops below trigger phrase value |
| `kill`       | Player initiates combat with mob |
| `random`     | Random chance each tick (trigger phrase = percentage) |
| `speech`     | Player says text matching trigger phrase |
| `exit`       | Player leaves mob's room (specific direction) |
| `exall`      | Player leaves mob's room (any direction) |
| `delay`      | After a programmed delay |
| `surrender`  | Mob surrenders |

[PRIMESUD] deferred: mob_prog interpreter not yet implemented.

---

## Conventions

- **`# fmt: off` is mandatory.** The aligned column style in mob/item/room dicts
  would be destroyed by an auto-formatter. Do not remove it.
- **`_unknown_bits`** keys in flag dicts record uninterpreted bit positions from the
  original `.are` file. Preserve them; do not add new ones manually.

---

## Flag bits reference

Full ROM/1stMud bit-to-name maps used by `tools/are_to_primesud.py` to
decode `.are` bit-strings into the `act_flags` / `affected_by` / `off_flags` /
`imm_flags` / `res_flags` / `vuln_flags` / room `flags` / item `extra_flags` dicts
described above. Useful when auditing an area file's `.txt` output against its
`.are` source by hand. Bit 0 of `act_flags` (`is_npc`) is always set for mobiles
and is omitted from the converted dict.

### ACT_FLAGS (bit -> name)

```
1=sentinel  2=scavenger  5=aggressive  6=stay_area  7=wimpy
8=pet  9=train  10=practice  14=undead  16=cleric  17=mage
18=thief  19=warrior  20=noalign  21=nopurge  22=outdoors
24=indoors  26=healer  27=gain  28=update_always  29=changer
```

### AFFECTED_BY (bit -> name)

```
0=blind  1=invisible  2=detect_evil  3=detect_invis  4=detect_magic
5=detect_hidden  6=detect_good  7=sanctuary  8=faerie_fire  9=infrared
10=curse  12=poison  13=protect_evil  14=protect_good  15=sneak  16=hide
17=sleep  18=charm  19=flying  20=pass_door  21=haste  22=calm  23=plague
24=weaken  25=dark_vision  26=berserk  27=swim  28=regeneration  29=slow
```

### OFF_FLAGS (bit -> name)

```
0=area_attack  1=backstab  2=bash  3=berserk  4=disarm  5=dodge
6=fade  7=fast  8=kick  9=kick_dirt  10=parry  11=rescue  12=tail
13=trip  14=crush  15=assist_all  16=assist_align  17=assist_race
18=assist_players  19=assist_guard  20=assist_vnum
```

### RESIST_FLAGS (bit -> name; shared by imm_flags / res_flags / vuln_flags)

```
0=summon  1=charm  2=magic  3=weapon  4=bash  5=pierce  6=slash
7=fire  8=cold  9=lightning  10=acid  11=poison  12=negative  13=holy
14=energy  15=mental  16=disease  17=drowning  18=light  19=sound
23=wood  24=silver  25=iron
```

### ROOM_FLAGS (bit -> name)

Bits 4, 5, 20, 21, 22 are 1stMud extensions with no `ROOM_*` define in QuickMUD's
`merc.h`. PrimeSUD's runtime is 1stMud-ported, so 1stMud semantics are canonical;
QuickMUD stock areas never set these bits (verified across all shipped areas), so
decoding them is unambiguous. [PRIMESUD]

```
0=dark  2=no_mob  3=indoors  4=arena*  5=bank*  9=private  10=safe
11=solitary  12=pet_shop  13=no_recall  14=imp_only  15=gods_only
16=heroes_only  17=newbies_only  18=law  19=nowhere
20=noexplore*  21=noautomap*  22=save_objs*     (* = 1stMud extension)
```

### EXTRA_FLAGS (bit -> name; item `extra_flags`)

Bits 17 (`auctioned`) and 26 (`quest`) are 1stMud extensions with no `ITEM_*`
define in QuickMUD's `merc.h`. PrimeSUD's runtime is 1stMud-ported and
`quest.py`/`shop.py`/`inventory.py`/`magic.py` gate on `"quest"`, so 1stMud
semantics are canonical; QuickMUD stock areas never set these bits (verified
across all shipped areas). [PRIMESUD]

```
0=glow  1=hum  2=dark  3=lock  4=evil  5=invis  6=magic  7=nodrop
8=bless  9=anti_good  10=anti_evil  11=anti_neutral  12=noremove
13=inventory  14=nopurge  15=rot_death  16=vis_death  17=auctioned*
18=nonmetal  19=nolocate  20=melt_drop  21=had_timer  22=sell_extract
24=burn_proof  25=nouncurse  26=quest*          (* = 1stMud extension)
```

### AC interpretation

Raw `.are` AC values are per-bucket (`pierce, bash, slash, exotic`) and are
kept as-is by the converter -- see `armor` under ROOMS/MOBILES/OBJECTS above.
Runtime combat (`handler.get_armor`, `combat.py`) uses each bucket
independently rather than a single combined score: `mob.py` multiplies the
raw `.are` value by 10 on load, and `combat.py` divides back by 10 per
bucket when checking to-hit.

The formula below is **not** the runtime formula. It is a quick eyeball
conversion for reading a raw four-bucket `.are` AC line as a single
traditional descriptor (10 = unarmored, lower/negative = better armored)
while auditing a new area file:

`ac = (sum of 4 AC values) // 4 // 10` (Python floor division, rounds toward
negative infinity)

Examples:
- All 10s -> 40 // 4 = 10, 10 // 10 = **1**
- (8, 8, 8, 10) -> 34 // 4 = 8, 8 // 10 = **0**
- (7, 7, 7, 9) -> 30 // 4 = 7, 7 // 10 = **0**
- (6, 5, 6, 7) -> 24 // 4 = 6, 6 // 10 = **0**
- All -15 -> -60 // 4 = -15, -15 // 10 = **-2**
