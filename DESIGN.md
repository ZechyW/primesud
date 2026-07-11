# PrimeSUD - Design Decisions

Intentional deviations from 1stMud and design choices made for PrimeSUD. Read before porting a new mechanic to avoid re-litigating settled decisions. Features not listed here: assume 1stMud behaviour unless code says otherwise.

**Guiding principle:** PrimeSUD is single-player. Multiplayer mechanics are excluded unless they add meaningful solo gameplay value. Mechanics with no current content hook are deferred, not eliminated.

---

## HP Prime runtime

HP Prime Python appears to load all `.py` files in the app before `primesud.py` runs. Lazy `import` patterns may not reduce first-launch wait if the source file is still packaged. Prefer lazy runtime initialisation for heap stability: avoid duplicate merged catalogs, bulk mutable state, and all-world resets until data is actually needed.

Pickers force numeric keyboard mode on entry (`picker.py:_force_numeric_keys`) so stale alpha/shift-lock state doesn't eat digit selections.

---

## Not ported

| Feature | Reason |
|---|---|
| Move / MV | No solo gameplay hook identified; omitted entirely |
| Race system | Ported: RACE_TABLE in races.py, race defaults merged at mob/player creation, check_immune in combat, race-aware stat caps (get_curr_stat/get_max_train in handler.py). Chargen: name, race, sex, class, alignment, weapon. Racial skills granted at creation. Creation-point group customisation not ported |
| Class system | Ported: CLASS_TABLE (6 classes) in classes.py, remort/multiclass, chargen class picker, per-class THAC0 and HP/mana gain, skill groups + `gain`. Creation-point group customisation at chargen not ported |
| Stat rolling | Per-race base stats from RACE_TABLE; no chargen reroll |
| Saving throws | `saving_throw = 0` baseline with `saves_spell`/`saves_dispel`/`check_dispel`; race/class modifiers and equipment bonuses deferred |
| Alignment / deity | No solo gameplay hook identified |
| Clan / rank | Multiplayer |
| Hunger / thirst | No solo gameplay hook identified |
| Age / hours played | HP Prime has no reliable RTC |
| Explore tracking | Ported (08/07/2026): per-room bitmask, `explored` command, `do_score` line (`explored.py`) |
| Trivia economy | Ported (08/07/2026 audit): earn via gquest kills/quest bonus/trivia pill, spend via `do_tpspend` (quest.py). Skipped options documented in do_tpspend docstring: corpse retrieval, transfer, pretitle, PK flag |
| Pkills / pdeaths | Single-player |
| Per-mob kill/death stats | 1stMud writes back to `.are` on shutdown; PrimeSUD areas are static Python files |
| MOBprograms | Ported (10/07/2026, `mobprog.py`): **MOB** progs only -- obj/room progs skipped (the converter emits neither). Trigger set is all converter words except `surr` (surrender mechanic unported) -- includes `act` (fired on NPC recipients of `act()` room text) and `exit`/`exall` (a room mob may react to / abort a player's departure). The `act` path carries a global `MOBtrigger` latch (mobprog.py): [PRIMESUD] it is held off for the whole act-trigger dispatch (stricter than 1stMud, which latches only emote/asound) so a prog's own act output cannot recursively fire further act triggers -- a hard recursion bound for the Prime's small stack. Mob-to-mob *speech* recursion is bounded separately by 1stMud's own guard: speech triggers fire only for a player speaker (`do_say` `!IsNPC` gate). mp-command set is the solo-relevant subset; the group/mass commands (`mpgtransfer`/`mpgforce`/`mpvforce`) are skipped as logged no-ops. Any non-control prog line dispatches through the real command interpreter as the mob (NPC-safe verbs only, per the `mobprog.py` prog-safety docstring). First demo content: the Mud School acolyte greet/give/delay prog (`area_school`, authored directly in `areas/school.are` as an `M` mob-trailer trigger set + `#MOBPROGS` section; see docs/AREA_FILES.md "Deviations from stock QuickMUD") |
| Furniture mechanics | sit/rest/sleep AT/ON/IN targets, occupancy (`count_users`), and value[3]/value[4] regen multipliers omitted -- no content: every furniture-typed object in the loaded areas (and all 16 across stock QuickMUD) carries `0 0 0 0 0` values. do_sit/do_rest/do_sleep/do_stand ignore the furniture keyword. Inns already regen faster via room heal_rate 110. Revisit alongside authored furniture content; full source map in git history (REGEN_PLAN.md decision 3) |

---

## Adjusted from 1stMud

| Feature | 1stMud | PrimeSUD | Reason |
|---|---|---|---|
| EXP per level | `exp_per_level()` -- scales with creation points and race/class mult | Flat 1000 XP / level | Equivalent at 40 creation points, human baseline |
| Level-up heal | Adds gains to `max_hit`/`max_mana`; current HP/MP unchanged | Fully restores current HP and MP | Eliminates "levelled at 1 HP mid-fight" |
| Remort progression | `finish_remort` grants `100*lvl_bonus` hp/mana/move, `5*lvl_bonus` trains, `7*lvl_bonus` practices -- ~6000/300/420 at first remort | Same `lvl_bonus` formula, all three grants divided by `REMORT_POWER_DIV` (config.py, default 12) -- ~500 hp / 25 trains / 35 practices; `1` restores stock | Revisited 11/07/2026 (was "accepted, revisit after playtest"): 6000 hp against PrimeSUD's 50-hp creation baseline trivialised everything; ~500 keeps the power-fantasy bump without breaking content. Single knob keeps vitals/trains/practices proportional |
| Guild rooms | Single class per guild room; midgaard has no paladin/ranger guilds | Paladin shares the Cleric guild rooms, Ranger shares the Warrior's; all four midgaard GMs are gain-capable (`areas/midgaard.are` room `G` trailers + mob `act_flags`; see docs/AREA_FILES.md "Deviations from stock QuickMUD") | Every class must be gain/remort-capable within the loaded-area set |
| Pulse timing | `PULSE_VIOLENCE = 3xPPS`, `PULSE_MOBILE = 4xPPS`, `PULSE_TICK = 45xPPS` | `2xPPS`, `5xPPS`, `30xPPS` | Faster combat/regen; slower mob wander |
| Gquest joining | 3-min GQUEST_WAITING window to gather joiners via `gquest join`; cancels with "Not enough people" if none join; ends running quest when last player leaves | No window -- quest starts running at announcement with the player auto-joined (same gates as manual join: no regular quest, level in range); auto-quest level band clamped to always include the player; runs until time expires; `gquest quit`/`join` still allow opt-out/rejoin (e.g. join after wrapping up a regular quest) | Single player -- window was dead time (kills don't credit until RUNNING), "not enough players" can't be a failure mode, joining has no penalty, and an unjoinable quest is dead content |
| World-reset object counts | Incremental `pObjIndex->count` bumped at create/extract | Recomputed once per reset pass (`mob._object_count_map`) from the loaded world -- room floor items + one level of container `contents` + every char's inventory/equipment -- then incremented locally as the pass spawns | Sacrifice/quaff/decay/burnout extraction paths would drift a persistent counter and force it into the save file; lazy loading makes the computed count correct-by-construction (unloaded areas hold no instances) |
| P-reset container target | `get_obj_type` scans the global object list for the most recent container instance | Most-recent instance of the container template found in the *resetting room's* floor items only | Converted stock P always fills a container O-placed in the same room; a global scan would fight lazy loading |
| R-reset exit shuffle | Fisher-Yates over the live exit array, doors included | Same shuffle over the first N of the fixed `n,e,s,w,u,d` order, but skipped entirely if any affected exit is a door | Door reset state is keyed by (room, direction) in `DOOR_DEFS`; shuffling a door would desync it. Stock shuffled carriers (daycare maze, limbo) carry no doors on shuffled exits. Automap/`do_run` read the mutated static exits, diverging from ROOM_DEFS exactly as 1stMud mutates its live exits |
| Room light counter | `room->light` bumped incrementally in `char_to_room`/`equip_char` | Computed on demand: `room_light(vnum)` counts lit lights worn by the room's occupants **and lying on its floor** | The many extraction/removal paths would drift a persistent counter and force it into the save. Floor lights also illuminate ([PRIMESUD], unlike stock ROM/1stMud which count only worn lights -- `room->light` is never touched by `obj_to_room`): a dropped torch or a cast continual-light ball lighting the room is the intuitive behaviour. Lights inside containers do not count |
| `can_see_room` | Gates immortal / clan / owner room flags | Always permissive | Single-player: no immortals or clans, and the only room-flag carrier (`area_immort`) is already unreachable |
| Explore-bit mark point | `StrSetBit` in `char_to_room` (handler.c:1360) -- one choke point on every room entry | `mark_explored(player)` called once per command dispatch (`commands.interpret`) and once per update tick (`update.update_handler`), setting the bit when the player's room differs from a cached `_last_marked_room` | PrimeSUD has no `char_to_room` choke point -- room assignment is scattered across movement/magic/combat/training/debug/load. The command seam catches player moves; the tick seam catches mob-initiated drags (summon). Per-area room counts baked at generation time (`AREA_ROOM_COUNTS`) so `arearooms`/score never load an area |
| Weather model | Per-area temp/precip/wind vector sim seeded from each area's climate | Same engine, climate baked to a neutral `2 2 2` for every area; integer-only, and the change echo is computed for the player's area alone | Loaded area files all carry `Climate 2 2 2`, so climate 2 zeroes the climate-pull term (no floats on-device), and 1stMud never displays a non-player area's echo |
| `do_time` | Calendar line plus boot/copyover/timezone/connected/creation lines | Calendar line + hours played only | The server/multiplayer state has no single-player equivalent |
| `do_group` roster | One `[%2d %s] %-16s %4ld/%4ld hp ... %5d xp` line per member (~70 chars) | Two lines per member: `[%2d %-4s] <name>` then an indented, column-aligned `hp/mana/mv/xp` stats line | The single line overflows the 64-col screen and wraps mid-value; the split fields stay vertically aligned down the list |

---

## Multiclass prestige tiering [PRIMESUD]

Settled 11/07/2026; no 1stMud equivalent (stock `MAX_REMORT=2` hard-refuses a
second remort). Within a tier, play is faithful 1stMud multiclass: start with
one class, remort at level 49 appends a second (with the stock `lvl_bonus`
power dump), cap 50. At `MAX_REMORT` classes and max level, `remort` becomes a
**tier reset** (`finish_tier_reset` in training.py) instead of refusing: same
gates/costs (guild + trainer, 500k gold + 500 qp, two-step confirm), class
picker over **all** classes (repeats allowed), then `classes=[pick]`,
`tier+=1`, level 1, back to school.

A reset restarts **near-fresh** -- hp `50+50*tier`, mana/move `100+50*tier`,
trains `5+tier`, practices `7+tier` -- with permanent perks per tier:

- **Mastered skills kept** (100% survives, as in stock remort) but **dormant
  until re-held**: `skill_level()` semantics unchanged, so a mastered skill
  from a dropped class is unusable until a class that learns it is held again.
- **+1 all perm stats** per reset; `get_max_train` cap `+tier` (clamped at
  MAX_STATS).
- **Proficiency floor**: non-mastered skills reset to `min(old, 10*tier)`
  instead of 1%.
- **Practice ceiling** `skill_adept_cap()` = `SKILL_ADEPT + 5*tier`, max 95
  (use-based `check_improve` still runs to 100 independently).

Level caps, `lvl_bonus`, and the `LEVEL_IMMORTAL` 52 sentinel are untouched.
Display: `score` Tier cell (only when tier > 0), `class_who` `*<tier>` suffix.
Save line `p.tier` (absent in old saves -> defaults 0, no version bump).

**Race + sex re-pick on remort** (added 11/07/2026, revised same day):
remorting is conceptually re-creating a new mortal char, so every remort --
stock or tier reset -- re-runs the race and sex pickers before the class
picker (cf. 1stMud nanny.c CON_GET_NEW_RACE/CON_GET_NEW_SEX). [PRIMESUD]
deviation: upstream locks race after one change (`stay_race`, "that race
FOREVER"); not ported -- race is re-pickable on every remort, more
flexibility for a single-player game. Any race prompt (even re-picking the
same race) resets perm stats to the race base as upstream (nanny.c:527),
losing trained stats and the chargen prime +3; `+tier` is re-added so the
tier stat perk survives ([PRIMESUD] -- this is also how the "+1 all perm
stats per tier" perk is realised, since the prompt always runs). Race flag
dicts are replaced, not OR'd with the old race's as nanny.c does -- they
re-derive from the race name on load, so OR'd leftovers could never survive
a save. New race skills granted at 1%; upstream's kept-race skill zeroing
corrected (see docs/FIXES.md). Creation points not ported.

---

## Area files

Generated `.txt` files (`area_<name>.txt`, Python source) instead of parsed `.are` files -- runtime text parsing too memory-intensive. See **[docs/AREA_FILES.md](docs/AREA_FILES.md)** for full format reference.

Single ROM 2.4 (QuickMUD-dialect) pipeline: `areas/*.are` are editable working copies (pristine upstream originals kept under `reference/`), converted by the sole `tools/are_to_primesud.py`. The old 1stMud-format converter is retired; 1stMud-only areas (`limbo`, `quest`) were converted once to ROM 2.4 so every area shares one format and one converter. `#SPECIALS`/`#SHOPS` are baked into each mob's `MOBILES` entry (`spec_fun`/`shop` keys) at conversion time rather than merged at load; a special/shop referencing a mob vnum outside its own file is a hard conversion error. A handful of 1stMud flag-bit extensions absent from stock QuickMUD `merc.h` (item `extra_flags` bits 17/26, room flag bits 4/5/20-22) are treated as canonical since the runtime is 1stMud-ported. Generated data files (`area_*.txt`, `help.txt`, `mob_index.txt`) use `.txt` rather than `.dat` so tooling doesn't mistake them for binary. The converter fails loudly (`ValueError`) on any construct it doesn't handle -- unknown sections (`#AREADATA`, `#MOBOLD`/`#OBJOLD`), unrecognized trailer/reset/special letters, truncated payloads, `spec_fun` names missing from `src/special.py` `SPEC_TABLE` -- mirroring QuickMUD's own `bug()`+`exit(1)` loader; verified 2026-07-05 against all 53 stock QuickMUD areas (52 convert clean; `hood.are` correctly rejected for unimplemented specs).

---

## Lazy area loading

`world.py`'s `ROOM_DEFS`/`MOB_DEFS`/`ITEM_DEFS` are `LazyDict`s: any `[vnum]`/`.get(vnum)`/`vnum in ...` access loads that vnum's whole area file. This is cheap per-area but easy to trip accidentally -- any code that walks "all areas" (e.g. picking a destination, listing the world) ends up loading every area on the map, which is slow and heap-hungry on the calculator. `world._AREA_FILES`/`AREA_LEVELS`/`AREA_BUILDERS`/`_AREA_ADJ` are static tables (filename/tag/display-name/vnum-range, level range, builder, directed area-graph adjacency) generated by `tools/gen_area_adj.py` so area-level metadata and routing can be consulted without touching `ROOM_DEFS`. `world._vnum_to_tag(vnum)` (static-range lookup) and `world._ensure_area_by_tag(tag)` are the zero-load / single-area-load primitives built on top.

`do_areas` (`src/info.py`) renders entirely from those static tables -- no area load, ever. 1stMud's stock `do_areas` (db.c) appends a per-area `path_to_area()` directions column by default, but the same function also implements an alternate layout gated by `MudFlag(DISABLE_AREA_DIRECTIONS)` that drops the column entirely (`"%s{W[{B%-7s{W] {r%s {C%s{x"`, no trailing `(dirs)`). PrimeSUD always renders that alternate layout: computing directions for every area (even lazily) still touches enough of the room graph that most areas end up loaded, defeating the purpose. The leading marker column (1stMud: clan-restriction `*`, not ported -- no clans) is repurposed to flag the player's current area instead, since there's no directions column left to say "You are here."

`do_run` with no args (`src/movement.py`) picks a destination area from the same static area list (zero loads to build the picker), then pathfinds lazily via `info.find_path_to_area`: (1) zero-load BFS over the static area-adjacency graph to find a chain of areas from here to there; (2) load just the areas on that chain; (3) a *restricted* room-level BFS from the player's room that filters every candidate destination room through `world._vnum_to_tag` (zero-load) before ever touching `ROOM_DEFS` for it, so it can't accidentally load an area outside the chain; (4) if that restricted search can't complete the chain at room granularity (e.g. a one-way exit means the graph edge isn't walkable in this direction), fall back to the old exhaustive `find_area_paths`, which loads every area but is guaranteed to find any reachable target. `find_area_paths`/`_compress_path` are unchanged and remain as that fallback.
