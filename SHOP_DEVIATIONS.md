# Shop System -- Deviations from 1stMud

## Stubbed / Not Ported

1. ~~**No time system (open/close hours)**~~ **RESOLVED** -- `game_time.py` ports `time_info` + `time_update`. `find_keeper` now checks `open_hour`/`close_hour` against `time_info["hour"]`.

2. **No pet shop** -- `ROOM_PET_SHOP` flag not implemented. `do_buy` and `do_list` skip entire pet-shop branch (cf. 1stMud act_obj.c:2494-2580, 2712-2747). Needs follower/charm system ported first.

3. ~~**No carry weight/count limits**~~ **RESOLVED** -- `can_carry_n()` / `can_carry_w()` / `get_obj_weight()` ported in `item.py`. `do_buy` checks both before purchase.

4. ~~**No `can_drop_obj` (nodrop flag)**~~ **RESOLVED** -- `can_drop_obj()` in `item.py`. Wired into `do_sell`, `do_value`, `do_drop`.

5. ~~**No `ch->reply` tracking**~~ **RESOLVED** -- `player["reply"] = keeper` set at all keeper-tells-you sites. `do_reply` ported in `comm.py`, registered as command #106.

6. ~~**Timer system passive**~~ **RESOLVED** -- `obj_update` now ticks down NPC inventory timers. Sold-back items decay from keeper inventory.

7. ~~**`do_appraise` not ported**~~ **RESOLVED** -- `do_appraise` in `shop.py` calls `spell_identify` on keeper inventory items. Registered as command #340.
