# Parity Sweep -- 1stMud 4.5.3 C vs PrimeSUD Python

Sweep of every top-level function in act_obj.c, handler.c and update.c
135 rows closed -- faithful (none), deliberately deviated (known),
no single-player counterpart (unmapped), or resolved by the 2026-09-05
fix pass (`[fixed]`/`[resolved]`) -- are condensed to one-liners. The
7 OPEN port-drift rows keep their full evidence under "Open port-drift rows".

## Taxonomy
- **upstream-bug** -- the C contradicts its own stated intent. Correct fix would
  port the intent, tag `[PRIMESUD]`, log to `docs/FIXES.md`.
- **port-drift** -- the Python diverges from C fidelity (unintended).
- **none** -- faithful port, no meaningful difference.
- **known** -- the deviation is already documented (`docs/FIXES.md` entry or a
  `[PRIMESUD]` marker in `src/`) and intentional.
- **unmapped** -- no clear Python counterpart found.
- **ambiguous** -- counterpart found but classification is uncertain.
- **[fixed]/[resolved]** -- a follow-up change resolved a previously open
  port-drift row (the 2026-09-05 fix pass); `[resolved]` additionally means
  the row was reclassified to `known` (deviation deliberately kept, tagged
  `[PRIMESUD]`).

On-device adaptations that legitimately explain a Python difference are **not**
drift (classify none/known): no `%`/`.format()` (concatenation/`chprintf`),
`util.num_str()`/`int_str()` instead of `str(int)`, byte iteration via
`s.encode()`, single-player simplifications, the 64-column screen wrap.

## Coverage
- act_obj.c: 33 functions
- handler.c: 96 functions
- update.c: 13 functions
- Total rows: 142 (33 + 96 + 13); 135 closed (condensed below), 7 open (full detail at the bottom)

---

## act_obj.c (reference/1stMud4.5.3/src/act_obj.c)

| C function | C lines | Verdict | Note |
|---|---|---|---|
| can_loot | 43-71 | unmapped | single-player: no other PC owns a corpse; effectively always-true |
| get_obj | 73-179 | none | single-player/scope omissions (donate-room gate, can_loot, "using" check, autosplit) |
| do_get | 181-330 | [fixed] | bare "from" strip fixed 2026-09-05 (inventory.py:260-263, cf. act_obj.c:193-194) |
| do_drop | 468-636 | none | no-arg shows a [PRIMESUD] picker |
| do_give | 638-860 | none | documented [PRIMESUD]: changer-from-thin-air, quest_mob vnum, socials-to-act, wallet absorption |
| do_envenom | 862-973 | none |  |
| do_fill | 975-1041 | none |  |
| do_pour | 1043-1167 | none | pour-for-a-character unported (no multi-char targets) |
| do_drink | 1169-1288 | none | [PRIMESUD] condition tracking (THIRST/FULL/DRUNK) omitted |
| do_eat | 1290-1374 | none | [PRIMESUD] COND_FULL/HUNGER omitted; pill payload validation + death_cry override added |
| remove_obj | 1376-1396 | none | docstring says "curse" but C also checks only ITEM_NOREMOVE -- no behavioral drift |
| wear_obj | 1398-1702 | known | [PRIMESUD]: 16 CanWear branches -> table pick; _zap_anti_align relocated; "wear best" machinery; two-hand vs shield auto-removes shield (C hard-refuses) |
| do_wear | 1704-1741 | none | no-arg [PRIMESUD] picker; `wear best` added |
| do_sacrifice | 1780-1889 | none | [PRIMESUD] can_see gate on the "all" loop; silver clamped to 1 for cost-0 items |
| do_quaff | 1891-1938 | none | C ROOM_ARENA block unported (PvP construct) |
| do_recite | 1940-2002 | none | [PRIMESUD] validate_item_spell_payload |
| do_brandish | 2004-2089 | none | single-player target simplification; Python handles obj_char_defensive/offensive targets C would bugf |
| do_zap | 2091-2180 | none | [PRIMESUD] validate_item_spell_payload |
| do_steal | 2182-2355 | known | [PRIMESUD]: arena, PvP level-gap, clan gate, outlaw+wiznet, carry-weight unported -- victims always NPCs; sex==2 vs "female" paper-bag yell |
| find_keeper | 2357-2397 | none |  |
| get_obj_keeper | 2399-2425 | none | [PRIMESUD] item_tpl for evicted foreign-area stock; no wear_loc gate (keeper stock never worn) |
| get_cost | 2427-2480 | none | per-match compounding of the same-item discount kept |
| do_buy | 2482-2707 | none | pet-shop branch delegated; [PRIMESUD] no-arg stock picker; haggle base uses template value (equivalent for fresh stock) |
| do_list | 2709-2810 | none | [PRIMESUD] no MXPTAG tags; item_tpl for evicted foreign stock |
| do_sell | 2812-2904 | none | [PRIMESUD] no-arg picker + "sell all" + multi-word join (repo-wide convention; C single-item); bare "gold" |
| do_value | 2906-2959 | none | bare "gold" (C's unconditional plural misprints at 1) |
| do_appraise | 2961-2992 | none | omits C's redundant second "You aren't in a shop." |
| do_second | 2994-3059 | [fixed] | verdict corrected: faithful; [PRIMESUD] anti-align zap in do_second not inline (C equip_char does it) |
| donate_object | 3061-3093 | known | unported; inert without do_donate |
| do_donate | 3095-3176 | known | unported; command commented out (commands.py:376) |
| do_ring | 3178-3229 | known | unported; deliberate scope omission |

---

## handler.c (reference/1stMud4.5.3/src/handler.c)

| C function | C lines | Verdict | Note |
|---|---|---|---|
| is_friend | 40-81 | unmapped | multiplayer group/clan/assist test |
| count_users | 83-97 | unmapped | multiplayer multi-seat furniture |
| weapon_lookup | 99-111 | none | name->GSN dict (skills_table.py), no table iteration |
| weapon_class | 113-125 | none | name->classnum dict (item.py) |
| weapon_name | 127-135 | unmapped | no reverse weapon_t->name helper; type shown from stored data word |
| attack_lookup | 137-149 | none | dam_type-keyed (noun, dam_class) dict (config.py) |
| wiznet_lookup | 151-163 | unmapped | GM wiznet not ported |
| class_lookup | 165-177 | none | prefix-match preserved; Py adds empty-name guard (safety) |
| check_immune | 179-288 | none | two-pass structure faithful; equipment-derived imm/res/vuln not yet ported [not ported] |
| is_clan | 290-293 | unmapped | clan not ported |
| is_true_clan | 295-299 | unmapped | clan not ported |
| is_same_clan | 301-307 | unmapped | clan not ported |
| is_old_mob | 309-316 | unmapped | all converted mobs new-format; olevel stays 0 |
| get_weapon_sn | 361-401 | none |  |
| get_weapon_skill | 403-425 | none | clamp safe: NPC formulas non-negative, learned capped by check_improve |
| reset_char | 427-738 | known | [PRIMESUD] perm-recovery block + last_level omitted (no legacy saves) |
| get_trust | 740-752 | unmapped | trust intentionally not ported |
| get_age | 754-758 | none | formula identical; Py "played" already includes session time |
| get_curr_stat | 760-781 | none | race data verified identical |
| get_max_train | 783-799 | known | [PRIMESUD] +1 trainable cap per prestige tier |
| can_carry_n | 801-810 | [fixed] | [resolved] ACT_PET flat-100 cap deliberately dropped ([PRIMESUD]; anti-mule, N/A single-player); immortal branch N/A |
| can_carry_w | 812-821 | [fixed] | [resolved] ACT_PET flat-1000-tenths cap deliberately dropped, same reasoning; immortal branch N/A |
| is_name | 823-857 | none | per-word prefix matching identical to C's effective semantics (inverted str_prefix polarity) |
| is_exact_name | 859-874 | [fixed] | verdict corrected: inlined at the sole live caller (explored.py:233) |
| affect_enchant | 876-901 | none | shared helper is a refactor of C's copy loop; per-affect level written but never read |
| affect_modify | 903-1048 | known | [PRIMESUD] sex clamp + _affect_depth guard; minor max(1,...) / mod==0 early returns |
| affect_find | 1050-1061 | none |  |
| affect_check | 1063-1148 | none |  |
| affect_to_char | 1150-1163 | none |  |
| affect_to_obj | 1165-1191 | none | missing TO_WEAPON type guard unreachable (affects only created on weapons) |
| affect_remove | 1193-1214 | none | C bug() on empty list vs Py no-op guard -- defensive, not observable |
| affect_strip | 1256-1269 | none |  |
| is_affected | 1271-1282 | none |  |
| affect_join | 1284-1304 | none | debuff-only use, matches C call sites |
| char_from_room | 1306-1330 | known | [PRIMESUD] on-demand room_light (incl. intentional floor-light addition) |
| obj_from_char | 1471-1491 | none |  |
| apply_ac | 1493-1520 | none | data-driven gating behaviorally equal; quest rescaled AC preserved via instance override |
| get_eq_char | 1522-1536 | [fixed] | verdict corrected: inlined O(1) slot-dict lookup at call sites |
| equip_char | 1538-1581 | known | [PRIMESUD] anti-align zap moved to _zap_anti_align; APPLY_SPELL_AFFECT not ported |
| unequip_char | 1583-1652 | known | AC add + clear slot before reversing affects (ordering documented); Py re-appends to inv (net state equal) |
| count_obj_list | 1654-1667 | [fixed] | inlined into reset_room ("O" has_one scan, "P" vnum count); global obj_counts map is a separate [PRIMESUD] restructure |
| obj_from_room | 1669-1689 | none | sit-on-furniture not ported (ch->on clear N/A) |
| obj_to_room | 1691-1704 | known | [PRIMESUD] ITEM_AUCTIONED + donation-room cost zeroing skipped (unported) |
| obj_to_obj | 1706-1732 | [fixed] | resolved 2026-09-05 via the shared get_obj_weight WeightMult fix |
| obj_from_obj | 1734-1761 | [fixed] | resolved 2026-09-05, same shared fix |
| extract_obj | 1763-1802 | [fixed] | [PRIMESUD] auction reset omitted, contents destroyed with item (callers spill first); quest re-pickup staleness tracked open under obj_to_char |
| extract_char | 1804-1884 | known | pull path + death item-strip (ITEM_QUEST/AUCTIONED kept) |
| get_char_room | 1886-1918 | known | [PRIMESUD] self/me handled by callers, not here |
| get_char_world | 1920-1942 | known | three [PRIMESUD] helpers (NULL-viewer, own-room-first, debug) |
| get_char_vnum | 1944-1960 | known | [PRIMESUD] spec_fun room scan instead of vnum world scan (same intent: find the registar) |
| get_pc_world | 1962-1981 | unmapped | dead C code (no callers); scans player_first (multiplayer) |
| get_obj_type | 1983-1994 | unmapped | sole caller db.c:1553 (reset obj-count limit); Py reset simplified |
| get_obj_list | 1996-2015 | none | [PRIMESUD] item_tpl keyword resolution (restructure, behavior preserved) |
| get_obj_carry | 2017-2038 | [fixed] | inlined into get_obj_here (single concatenated get_obj_list call) |
| get_obj_wear | 2040-2061 | [fixed] | inlined into get_obj_here; sole live caller passes character=true |
| get_obj_here | 2063-2102 | known | [PRIMESUD] cumulative N counter across room+inv+equip legs (upstream leaves the Nth match unaddressable across lists) |
| get_obj_world | 2104-2125 | known | [PRIMESUD] no global object list (lazy loading), one-container-level depth |
| deduct_cost | 2127-2169 | none | identical in the reachable domain; C clamp branch dead both sides |
| add_cost | 2171-2197 | none | identical silver path; gold branch vacuous single-player |
| cost_str | 2199-2215 | unmapped | sole caller do_tax (imm, unported); shop display inlines the split |
| create_money | 2217-2267 | known | [PRIMESUD] None instead of bug-clamp on bad input; weight not tracked; plural descr fix |
| get_obj_number | 2269-2283 | known | [PRIMESUD] corpses count as 0 (CONTAINER_TYPES adds npc/pc_corpse; C counts them as 1) |
| get_obj_weight | 2285-2295 | [fixed] | resolved 2026-09-05: contents scaled by container_weight_mult/100 (item.py:709-718) + paired do_put switch to get_true_weight |
| get_true_weight | 2297-2306 | unmapped | inlined in do_put; capacity check equivalent |
| room_is_dark | 2308-2324 | none |  |
| is_room_owner | 2326-2335 | unmapped | private-room check not ported (multiplayer only) |
| room_is_private | 2337-2360 | unmapped | call sites test static flags, dropping occupancy/owner/IMP_ONLY gates |
| can_see_room | 2362-2389 | known | [PRIMESUD] always-True stub (multiplayer/immortal-only restrictions) |
| can_see | 2391-2454 | known | [PRIMESUD] invis_level/incog/arena dropped; HOLYLIGHT -> debug toggle; quest/gquest by template vnum |
| can_see_obj | 2456-2484 | known | [PRIMESUD] HOLYLIGHT -> debug toggle; quest obj by template vnum |
| can_drop_obj | 2486-2499 | none | ITEM_AUCTIONED not ported; immortal override dead code |
| is_full_name | 2501-2513 | unmapped | note board (not ported) |
| emptystring | 2515-2524 | unmapped | OLC editor only |
| str_time | 2526-2563 | unmapped | do_time inlines the game calendar; no wall-clock/timezone |
| calc_max_level | 2565-2571 | none | immortal branch dead code |
| high_level_name | 2573-2602 | unmapped | immortal tiers not ported; HERO forms inlined at level-up |
| file_exists | 2604-2618 | unmapped | multiplayer file I/O |
| exists_player | 2620-2626 | unmapped | I3 inter-MUD (known non-port) |
| is_player_name | 2628-2644 | unmapped | player-file system |
| is_exact_player_name | 2646-2659 | unmapped | wizard do_name; no pfiles |
| get_player_name | 2661-2677 | unmapped | dead C code (zero call sites) |
| is_donate_room | 2679-2684 | unmapped | donate unported |
| timestr | 2686-2802 | unmapped | PK/admin/OLC callers only |
| getarg | 2804-2836 | unmapped | I3 channel filter (Py one_argument ports interp.c, a different fn) |
| hasname | 2838-2854 | unmapped | I3 channel filter |
| flagname | 2856-2869 | unmapped | I3 channel filter |
| unflagname | 2871-2889 | unmapped | I3 channel filter |
| ordinal_string | 2891-2914 | none | faithful incl. the 11st/12th/13th quirk |
| has_whitespace | 2916-2924 | unmapped | email subsystem |
| wild_match | 2926-3005 | unmapped | I3/ban; deliberate ROM quirk: the missing break before case '?' is a fall-through, do not "fix" |
| is_invalid_email | 3008-3059 | unmapped | email subsystem |

---

## update.c (reference/1stMud4.5.3/src/update.c)

| C function | C lines | Verdict | Note |
|---|---|---|---|
| advance_level | 51-125 | known | [PRIMESUD] full heal/restore; last_level not ported; verb fix = documented upstream bug (FIXES.md) |
| gain_exp | 127-159 | known | [PRIMESUD] per-level xp model; Py starts at level 1 (C's level-0 first-gain quirk gone) |
| hit_gain | 161-241 | known | condition-gated /2 regen halves unported (condition system) |
| mana_gain | 243-322 | known | Py classes.has_spells fixes the upstream class-index bug (FIXES.md); condition halves unported |
| move_gain | 324-373 | known | condition halves unported; mob branch not ported (mobs carry no move pool) |
| gain_condition | 375-407 | unmapped | the whole condition system (DRUNK/FULL/THIRST/HUNGER) is not ported |
| mobile_update | 409-513 | known | NPC tick split: affect duration -> regen -> aggr -> wander |
| obj_update | 768-929 | known | core faithful; expiry msg_obj announce unimplemented (FIXES.md:616-618) |
| aggr_update | 931-995 | none | gate-for-gate match |
| bank_update | 997-1009 | known | [PRIMESUD] 4x-faster cadence (PULSE_AREA 30s vs 120s) |
| bonus_update | 1011-1044 | unmapped | admin bonus event system |
| update_handler | 1046-1114 | known | [PRIMESUD] timer stagger offsets; char_update split into tick + PULSE_REGEN |
| char_update | 515-767 | [fixed] | affect level decay fixed 2026-09-05 (player.py:628-630, cf. update.c:650-651); condition system [PRIMESUD] |

---

## Open port-drift rows

Full evidence, copied verbatim from the sweep. Original line numbers in
parentheses. Severity note appended per row.

| Row | Function | C lines | One-liner | Severity |
|---|---|---|---|---|
| 37 | do_put | 332-466 | `put all in <container>` bulk loop missing (single item only) | convenience, not correctness |
| 48 | do_remove | 1743-1778 | `remove all.<name>` class subform missing | low, rare subform |
| 87 | get_skill | 318-359 | get_skill(mob,-1) reorder: C level*5/2 vs Py level-based | low, rare |
| 106 | affect_remove_obj | 1216-1254 | worn-item wearer handling dropped -- item curse/bless saving_throw +/-1 never reverts | persistent, observable |
| 111 | char_to_room | 1332-1415 | entry-time plague contagion (1/64) not ported; only the 1/16 tick vector | infection route, if a carrier present |
| 112 | link_obj_to_char | 1417-1455 | shopkeeper dup-merge + level-sorted insert missing | visible, any shop sell |
| 113 | obj_to_char | 1457-1469 | quest item not rescaled on re-pickup | rare edge |

### do_put (original row 37)

C supports `put all in <container>` via a bulk loop over carrying (act_obj.c:431-462); Python handles a single item only (inventory.py:526 get_obj_list), so `put all in X` returns "You do not have that item." Secondary: C resolves the container via get_obj_here (includes worn, handler.c); Python searches room+inv only (inventory.py:511-513); capacity guard is [PRIMESUD] (inventory.py:552-556).

Severity: convenience -- a bulk-form convenience, not a correctness bug; C's bulk loop (act_obj.c:431-462) would need a carrying iteration that Py's single-item path lacks.

### do_remove (original row 48)

Single-item (get_obj_wear -> remove_obj fReplace=true, inventory.py:1693-1699 vs C:1770-1776) and plain "all" (loop remove_obj, inventory.py:1688-1692 vs C:1756-1768) faithful. C also matches "all.<name>" via str_prefix("all.", arg) + is_name(&arg[4]) (C:1756,1764) to remove all of a class; Python has no such suffix (inventory.py:1688 checks args[0]=="all" only), so `remove all.finger` fails as a single-item lookup. Low impact (rare subform). No-arg shows a [PRIMESUD] picker (inventory.py:1668-1687) instead of "Remove what?" (C:1752).

Severity: low -- the `all.<name>` subform is rare; the row itself rates it low impact.

### get_skill (original row 87)

Reorder: C checks sn==-1 first for all chars (handler.c:322) then IsNPC (handler.c:331); Py checks is_mob first (skill_utils.py:212) then sn==-1 (skill_utils.py:215), so mob+sn==-1 gives C=level*5/2 vs Py=level-based (level 10: 25 vs 8). Only affects get_skill(mob,-1). Also: drunk skill reduction (handler.c:355-356, 9/10 when COND_DRUNK>10) omitted - documented condition-system non-port (combat.py:1318-1320 [PRIMESUD]); bad-sn bugf diagnostic dropped (handler.c:326-330, Py returns 0 via .get default, no log); Py adds sn>=0 guard on daze (handler.c:349 indexes skill_table[sn]=OOB for sn==-1).

Severity: low -- only `get_skill(mob, -1)` (unknown weapon on a mob) differs; player path is faithful.

### affect_remove_obj (original row 106)

Py omits C's worn-item wearer handling: affect_modify(carried_by,paf,false) (1227-1228) and affect_check on the wearer (1251-1252); Py docstring scopes the function to the flag-bit switch only (cites C 1233-1245). Observable: item curse (magic.py:1209 to_object "saves" +1, duration 2*level; 1211-1215 caster saving_throw +1, cf. C magic.c:1657-1669) and item bless (magic.py:1077,1079-1083, cf. magic.c:758-759) set a caster saving_throw offset at cast; on expiry (update.py:231-232, cf. update.c:815) or dispel (magic.py:1071,1203, cf. magic.c:734,1643) C reverts the wearer's saving_throw - in single-player caster==wearer==player - while Py never reverts: the only other saving_throw writers are the char-affect path (handler.py:314) and reset (player.py:234), so the +/-1 persists permanently. Not listed in docs/FIXES.md.

Severity: persistent, observable -- item curse/bless saving_throw +/-1 set at cast is never reverted on expiry or dispel; the only other writers are the char-affect path and reset, so the offset persists.

### char_to_room (original row 111)

Entry-time plague contagion not ported: C 1371-1412 infects a disease-free entering PC at 1/64 (number_bits(6), 1404); Py only has the tick vector 1/16 (player.py:388-393, cf. update.c:705-717) and no [PRIMESUD] note. Rest faithful or N/A: explored bits (explored.py; chokepoint commands.py:645), area empty/age/nplayer single-player N/A (mob.py:546 [PRIMESUD], mobprog.py:877-878, mob.py:827+), portal_map N/A (binary GUI-client protocol, client.c:1018-1039), act_sound absent (no "sound" key in any area file), room light increment -> on-demand room_light (handler.py:1212+, documented).

Severity: infection route -- C 1371-1412 infects a disease-free entering PC at 1/64; Py only has the 1/16 tick vector (player.py:388-393).

### link_obj_to_char (original row 112)

Shopkeeper duplicate-merge missing: C 1427-1454 merges same pIndexData + short_descr in a keeper's inventory (existing ITEM_INVENTORY -> extract_obj destroys sold dup, 1433-1437; else copies cost, 1438) and inserts level-sorted (1440-1450). Py sell always keeper["inv"].append(obj) (shop.py:577) and reset appends (mob.py:542): a sold duplicate of keeper stock with the inventory flag survives instead of being extracted (C: item vanishes, only silver credited), and "list" order is reset-order not level-order. Simple player path (C 1421-1424) is trivially ported.

Severity: visible -- a sold duplicate of keeper stock lingers in the keeper's inv instead of being extracted, and list order is reset-order not level-order.

### obj_to_char (original row 113)

C 1465-1466 rescales ITEM_QUEST items via update_questobj on every PC pickup; Py do_get paths only call quest_obj_check (retrieve/return state flip, quest.py:810+) -- update_questobj fires only at questman grant (quest.py:1035, comment "cf. 1stMud obj_to_char quest hook") and level-up (combat.py:2968). Edge: a dropped quest item re-picked-up after a level change keeps stale level/condition. carry_number/carry_weight on-demand (item.py:713-722) is structural-equal; update_corpses (C 1467-1468) N/A (no corpse registry).

Severity: rare edge -- a dropped quest item re-picked-up after a level change keeps stale level/condition; update_questobj fires only at questman grant and level-up. (Also referenced from the closed extract_obj row.)

