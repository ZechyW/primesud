# Shop System -- Deviations from 1stMud

## Stubbed / Not Ported

1. ~~**No time system (open/close hours)**~~ **RESOLVED** -- `game_time.py` ports `time_info` + `time_update`. `find_keeper` now checks `open_hour`/`close_hour` against `time_info["hour"]`.

2. ~~**No pet shop**~~ **RESOLVED** -- pet-shop branch of `do_buy`/`do_list` ported (`pet_shop` room flag; stock lives in room vnum + 1). Deviations: 1stMud's vnum 9621 -> 9706 special case not ported (area absent); pet `comm` flags (NOTELL etc.) not ported; pet persistence saves `p.pet=tpl|hp|max_hp|name` plus timed affects (`p.pet.affects`); other write_pet fields (exp, gold, inventory, comm bits) respawn from the template since PrimeSUD pets cannot accumulate them.

3. ~~**No carry weight/count limits**~~ **RESOLVED** -- `can_carry_n()` / `can_carry_w()` / `get_obj_weight()` ported in `item.py`. `do_buy` checks both before purchase.

4. ~~**No `can_drop_obj` (nodrop flag)**~~ **RESOLVED** -- `can_drop_obj()` in `item.py`. Wired into `do_sell`, `do_value`, `do_drop`.

5. ~~**No `ch->reply` tracking**~~ **RESOLVED** -- `player["reply"] = keeper` set at all keeper-tells-you sites. `do_reply` ported in `comm.py`, registered as command #106.

6. ~~**Timer system passive**~~ **RESOLVED** -- `obj_update` now ticks down NPC inventory timers. Sold-back items decay from keeper inventory.

7. ~~**`do_appraise` not ported**~~ **RESOLVED** -- `do_appraise` in `shop.py` calls `spell_identify` on keeper inventory items. Registered as command #340.
