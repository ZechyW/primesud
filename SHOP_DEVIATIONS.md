# Shop System -- Deviations from 1stMud

## Stubbed / Not Ported

1. **No time system (open/close hours)** -- `find_keeper` hour checks stubbed (shop.py:63-70). All shops always open. Needs `time_info` ported first.

2. **No pet shop** -- `ROOM_PET_SHOP` flag not implemented. `do_buy` and `do_list` skip entire pet-shop branch (cf. 1stMud act_obj.c:2494-2580, 2712-2747).

3. **No carry weight/count limits** -- `can_carry_n()` / `can_carry_w()` / `get_obj_number()` / `get_obj_weight()` don't exist. Buying ignores encumbrance (shop.py:249).

4. **No `can_drop_obj` (nodrop flag)** -- Sell/value skip nodrop check. Items with nodrop extra_flag can be sold (shop.py:361, 431).

5. **No `ch->reply` tracking** -- 1stMud sets `ch->reply = keeper` after keeper tells so player can `reply`. Reply command not ported.

6. **Timer system passive** -- `do_sell` sets `obj["timer"]` and `"had_timer"` flag, `do_buy` clears them, matching 1stMud. But no tick system actively decrements item timers, so sold-back items never decay from keeper inventory.

7. **`do_appraise` not ported** -- 1stMud cmd #340, alternate for `do_value` that also identifies. Not a standard ROM command; skipped.

## Implementation Differences

8. **`do_say` simulated via `act`** -- 1stMud uses `do_function(keeper, &do_say, text)` for keeper speech. PrimeSUD uses `act("$n says '$T'", keeper, None, text, TO_ROOM)` -- equivalent output but bypasses say command pipeline.

9. **No Shop-Loss Bias level override** -- 1stMud overrides object level for shop items during reset (scrolls/potions -> level 53, wands/staves -> spell level). PrimeSUD `create_object` takes no level parameter; items use template level as-is (mob.py:203-207).

10. **`ITEM_INVENTORY` not set on E resets** -- 1stMud sets on both G and E reset items for shopkeeper mobs. PrimeSUD only sets on G resets. E items go to equip immediately and aren't sellable -- no practical difference.

## Data Issues

11. **Numeric `buy_types` in area data** -- Some shop entries have numeric strings (`'6'`, `'7'`, `'30'`) in `buy_types` instead of type names. QuickMUD converter artifacts; never match any item type. Affected shops:
    - Weaponsmith (area_midgaard.py): `'6'`, `'7'` alongside `'weapon'`
    - Jeweller (area_midgaard.py): `'30'` alongside `'treasure'`, `'gem'`, `'jewelry'`
