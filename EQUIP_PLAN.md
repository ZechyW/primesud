# Item & Equipment System

## Goal

Full-fidelity port of 1stMud's item and equipment pipeline to PrimeSUD.
Reference: `act_obj.c`, `act_info.c`, `handler.c` in `reference/1stMud4.5.3/src/`.
Intentional deviations are marked `[PRIMESUD]` and documented below.

## Slot design

20 named slots in `player["equip"]` (string keys, `None` = empty).
Key names match area_school `wear_flags` via `_DUAL_SLOTS` mapping.

    "equip": {
        "light":     None,  "finger_l":  None,  "finger_r":  None,
        "neck_1":    None,  "neck_2":    None,  "body":      None,
        "head":      None,  "legs":      None,  "feet":      None,
        "hands":     None,  "arms":      None,  "shield":    None,
        "about":     None,  "waist":     None,  "wrist_l":   None,
        "wrist_r":   None,  "wield":     None,  "hold":      None,
        "float":     None,  "secondary": None,
    }

Dual slots use `_DUAL_SLOTS` mapping (area flag -> left/right pair):
`finger` -> `finger_l`/`finger_r`, `neck` -> `neck_1`/`neck_2`,
`wrist` -> `wrist_l`/`wrist_r`. First empty slot fills; both full -> swap first.

**`do_equipment` display order** mirrors 1stMud `where_name[]` (const.c:407),
rendered via `WEAR_LABELS` in `config.py`.

## Implemented

| # | What | 1stMud ref | Deviation |
|---|------|-----------|-----------|
| 1 | 20-slot `equip` dict; `get_AC/get_hitroll/get_damroll` iterate `.values()` | `db.c`, `macro.h` | — |
| 2 | `_wear_one` + `do_wear`; level check, NOREMOVE guard, dual-slot fill; `wear all`; `wield` alias | `wear_obj`, `do_wear` in `act_obj.c` | — |
| 3 | `remove_obj` + `do_remove` by item name (not slot name); `remove all` | `remove_obj`, `do_remove` in `act_obj.c` | `do_remove` takes item name; 1stMud takes slot name |
| 4 | `_look_item` + `do_look` item branch; room/item `extra_descs` via `_get_ed` | `do_look` in `act_info.c` | Mob `extra_descs` not yet handled |
| 5 | `_WEAR_MSG` per-slot wear messages including dual slots | `wear_obj` in `act_obj.c` | — |
| 6 | `get all` / `get all.<kw>` / `drop all` / `drop all.<kw>` | `do_get`, `do_drop` in `act_obj.c` | — |
| 7 | `get_obj_list` nth-match (`"2.sword"`) via `_number_argument` | `get_obj_list` in `handler.c`, `number_argument` in `interp.c` | — |
| 8 | `_obj_flags(tpl)` -- `(Glowing)` / `(Humming)` / `(Magical)` etc. in `do_inventory` + `do_equipment` | `format_obj_to_char` in `act_info.c` | — |
| 9 | `do_inventory` carry-count header; `can_carry_n` = `20 + 2*dex + level` | `do_inventory` in `act_info.c`, `can_carry_n` in `handler.c` | — |
| 10 | Containers: `do_put`, `get X from Y`, `_loot_container_picker` | `do_put`, `do_get` in `act_obj.c` | `[PRIMESUD]` picker UI for no-arg loot |
| 11 | E/G mob-equipment resets via `equip_char` in `reset_room` | `db.c` reset loop | — |
| 12 | `do_sacrifice` / `junk` / `tap` aliases; silver reward, PC-corpse guard, `no_sac` check | `do_sacrifice` in `act_obj.c` | — |
| 13 | Room/item `extra_descs` in `do_look` via `_get_ed` | `do_look` in `act_info.c` | — |
| 14 | `ITEM_MELT_DROP` on drop -- dissolves into smoke | `do_drop` in `act_obj.c` | Also checked in `do_get` |
| 15 | Wield skill-level messages (`_WIELD_SKILL_MSG` + `_get_weapon_skill`) | `wear_obj` in `act_obj.c` | — |
| 16 | `do_second` -- off-hand weapon; weight checks vs primary | `do_second` in `act_obj.c` | — |
| 17 | `do_outfit` -- starter gear by best weapon skill | `do_outfit` in `act_wiz.c` | — |
| 18 | Item-use commands: `do_quaff`, `do_eat`, `do_recite`, `do_brandish`, `do_zap` | `act_obj.c` | — |
| 19 | `can_carry_w`, `get_obj_weight` (recursive, includes contents) | `handler.c` | Functions exist but not enforced in `do_get` (see deferred) |
| 20 | `equip_char` / `unequip_char` with `_apply_item_modifiers`, `affect_check` rebuild | `handler.c` | `APPLY_SPELL_AFFECT` not yet ported |
| 21 | Item serialization: `serialize_item_token` / `parse_item_token` with `lv:` level field | `save.c` | — |
| 22 | Item affect system: `item_affect_to_obj`, `item_affect_remove`, `item_affect_find` | `handler.c` | — |
| 23 | `_EQUIP_SAVE_ORDER` -- save/load preserves all 20 slots | `save.c` | — |

## Deferred

| Feature | 1stMud ref | Reason |
|---------|-----------|--------|
| `do_give` | `act_obj.c` | Commented out in commands.py (#119); depends on NPC interaction |
| Weight enforcement in `do_get` / `do_put` | `handler.c` `can_carry_w`, `get_obj_weight` | Functions exist; `do_get` doesn't call them yet |
| `drop <n> gold` / `drop <n> silver` | `do_drop` in `act_obj.c` | No currency-drop path yet |
| Alignment restrictions on wear (`anti_good` / `anti_evil` / `anti_neutral`) | `wear_obj` in `act_obj.c` | Flags parsed in area converter but not checked in `wear_obj` |
| `do_donate` | `act_obj.c` | Commented out in commands.py (#266); needs donation pit / shop system |
| Mob `extra_descs` in `do_look` | `do_look` in `act_info.c` | Room/item extra_descs done; mob missing |
| `APPLY_SPELL_AFFECT` on equip | `equip_char` in `handler.c` | Note in `_apply_item_modifiers`; port when area data includes such items |
