# Item & Equipment System

## Goal

Full-fidelity port of 1stMud's item and equipment pipeline to PrimeSUD.
Reference: `act_obj.c`, `act_info.c`, `handler.c` in `reference/1stMud4.5.3/src/`.
Intentional deviations are marked `[PRIMESUD]` and documented below.

## Slot design

14 named slots in `player["equip"]` (string keys, `None` = empty).
Key names match area_school `wear_flags` exactly.

    "equip": {
        "light": None,  "wield": None,  "hold":   None,
        "body":  None,  "head":  None,  "legs":   None,
        "feet":  None,  "hands": None,  "arms":   None,
        "shield":None,  "about": None,  "waist":  None,
        "neck":  None,  "wrist": None,
    }

**[PRIMESUD]** No dual slots (`neck2`, `wrist2`) — a second item of the same
type swaps the first out.

**`do_equipment` display order** mirrors 1stMud `where_name[]` (const.c:407).

## Implemented

| # | What | 1stMud ref | Deviation |
|---|------|-----------|-----------|
| 1 | 14-slot `equip` dict; `get_AC/get_hitroll/get_damroll` iterate `.values()` | `db.c`, `macro.h` | — |
| 2 | `_wear_one` + `do_wear`; level check, NOREMOVE guard, slot from first non-`"take"` `wear_flag`; `wear all`; `wield` alias | `wear_obj`, `do_wear` in `act_obj.c` | — |
| 3 | `_remove_one` + `do_remove` by item name (not slot name); `remove all`; `_WEAR_LABELS` + `do_equipment` | `remove_obj`, `do_remove`, `do_equipment` in `act_obj.c`/`act_info.c` | `do_remove` takes item name; 1stMud takes slot name |
| 4 | `_look_item` + `do_look` item branch; TODO left for mob/room `extra_descs` | `do_look` in `act_info.c` | Mob/room extra_descs not yet handled |
| 5 | `_WEAR_MSG` per-slot wear messages | `wear_obj` in `act_obj.c` | — |
| 6 | `get all` / `get all.<kw>` / `drop all` / `drop all.<kw>` | `do_get`, `do_drop` in `act_obj.c` | — |
| 7 | `get_obj_list` nth-match (`"2.sword"`) | `get_obj_list` in `handler.c`, `number_argument` in `interp.c` | — |
| 8 | `_obj_flags(tpl)` — `(Glowing)` / `(Humming)` / `(Magical)` etc. in `do_inventory` + `do_equipment` | `format_obj_to_char` in `act_info.c` | — |
| 9 | `do_inventory` carry-count header; max = `min(37, 17 + level)` | `do_inventory` in `act_info.c`, `can_carry_n` in `handler.c` | Weight omitted — no weight data in templates yet |

## Deferred

| Feature | 1stMud ref | Reason |
|---------|-----------|--------|
| Containers (`do_put`, `get X from Y`) | `do_put`, `do_get` in `act_obj.c` | Needs object graph (`in_obj` equivalent) |
| `do_give` | `act_obj.c` | Depends on NPC interaction system |
| `E`/`G` mob-equipment resets | `db.c` reset loop | Flagged in DESIGN.md as deferred |
| Dual wear slots (`neck2`, `wrist2`) | `const.c` `where_name[]` | [PRIMESUD] single-slot simplification |
| Weight in `do_inventory` / carry limit in `do_get` | `handler.c` `can_carry_w` | No weight data in area templates yet |
| Wield skill-level messages | `wear_obj` in `act_obj.c` | No weapon-type skill check yet |
| `drop <n> gold` | `do_drop` in `act_obj.c` | No currency system yet |
| ITEM_MELT_DROP on drop | `do_drop` in `act_obj.c` | No items use it yet |
| Alignment restrictions on wear | `wear_obj` in `act_obj.c` | No alignment stat yet |
| `do_donate` / `do_sacrifice` | `act_obj.c` | Shop system not yet designed |
| Mob/room `extra_descs` in `do_look` | `do_look` in `act_info.c` | TODO in `_look_item` |
