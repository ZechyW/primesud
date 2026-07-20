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
| Move / MV | Ported (row was stale, corrected 11/07/2026): sector-based `movement_loss` costs deducted in move_char (movement.py), flying/water halving/doubling, regen, train/restore paths |
| Race system | Ported: RACE_TABLE in races.py, race defaults merged at mob/player creation, check_immune in combat, race-aware stat caps (get_curr_stat/get_max_train in handler.py). Chargen: name, race, sex, class, alignment, weapon. Racial skills granted at creation. Creation-point group customisation not ported |
| Class system | Ported: CLASS_TABLE (6 classes) in classes.py, remort/multiclass, chargen class picker, per-class THAC0 and HP/mana gain, skill groups + `gain`. Creation-point group customisation at chargen not ported |
| Stat rolling | Per-race base stats from RACE_TABLE; no chargen reroll |
| Saving throws | `saving_throw = 0` baseline with `saves_spell`/`saves_dispel`/`check_dispel`; race/class modifiers and equipment bonuses deferred |
| Deity / worship | Multiplayer-social; no solo hook. (Alignment itself IS ported: chargen choice, kill/spell drift, is_good/is_evil gates -- row split 19/07/2026, was stale as "Alignment / deity") |
| Outlaw / crime (PLR_OUTLAW) | Multiplayer-only: both upstream set-sites are PvP (steal from a player, act_obj.c:2284; PK murder via check_killer, fight.c:1511) -- flag unreachable solo, so it is not modeled. spec_executioner stays inert; spec_guard/spec_thief outlaw branches skipped (2026-07-19 parity sweep). Candidate crime-system hook for the content track |
| Clan / rank | Multiplayer |
| Hunger / thirst / drunk | No solo gameplay hook identified; liq_table proof/full/thirst/food values dropped with it. Eat/drink/fill/pour ARE kept as RP flavour plus the real poison/food-pill mechanics; full 36-liquid table (colour + sip size) ported 19/07/2026 (item.py LIQ_TABLE) |
| Age / hours played | HP Prime has no reliable RTC; offline catch-up regen at login (save.c:1176) likewise N/A |
| Explore tracking | Ported (08/07/2026): per-room bitmask, `explored` command, `do_score` line (`explored.py`) |
| Trivia economy | Ported (08/07/2026 audit): earn via gquest kills/quest bonus/trivia pill, spend via `do_tpspend` (quest.py). Skipped options documented in do_tpspend docstring: corpse retrieval, transfer, pretitle, PK flag |
| Pkills / pdeaths | Single-player |
| Per-mob kill/death stats | 1stMud writes back to `.are` on shutdown; PrimeSUD areas are static Python files |
| MOBprograms | Full 1stMud tri-mode prog engine (mob 10/07/2026; obj/room + completion 20-21/07/2026, `mobprog.py`). `program_flow` takes exactly one origin: mob dict, obj context, or room vnum. An obj origin is a mutable ctx dict `{"obj", "room", "carrier"}` supplied by the fire site (PrimeSUD objects carry no location back-pointer; `obj goto`/`otransfer` update it in place). Obj/room progs may only issue control + `obj <cmd>`/`room <cmd>` lines (raw command lines bug-skip, cf. programs.c:2782); their lookups use NULL-viewer semantics (no visibility filter, no self-exclusion). Per-instance state `oprog_delay`/`oprog_target` (obj dicts) and `rprog_delay`/`rprog_target` (runtime room dicts) is transient by design -- save surface is player-only. All ifchecks implemented; `clan` + `hunter` are faithful-False (no clan system; upstream never sets `->hunting`), `objval0-4` go through `item.prog_obj_value` (instance `values` tuple from `obj attrib` wins; weapon damage-type / liquid-type index spaces return 0 -- word-keyed in PrimeSUD). Group/mass commands (`gtransfer`/`gforce`/`vforce`) implemented for all three origins (mob variants exclude self, obj/room do not, per upstream). Fire seams mirror upstream order (get/drop/give obj-then-room-then-mob; move exit then greet, mob-obj-room; fight mob, worn objs, room-once-per-pulse). The `act()` obj/room TRIG_ACT block is deliberately NOT gated on the `MOBtrigger` latch and fires once per TO_ROOM/TO_NOTVICT recipient with the unrendered format, exactly as `perform_act` (comm.c:2044); recursion is bounded by the global program_flow call-depth counter. The mob-recipient act path keeps the [PRIMESUD] stricter latch (held off for the whole dispatch). Obj random/delay pulse is intent-parity: upstream's block hides behind the decay-timer gate (update.c:819), contradicting its own `obj delay`/`cancel` command surface and the room analogue (db.c:1380) -- ported per-tick; room pulse sweeps only the player's (non-empty) area. Obj `sit` trigger has no seam -- furniture is unported (movement.py position commands). Mob-to-mob speech recursion stays bounded by 1stMud's own guard (speech fires only for a player speaker). Demo content: Mud School acolyte prog [PRIMESUD]; midgaard obj 3005 drop + room 3054 grall (restored 1stMud originals). Area dialect: docs/AREA_FILES.md |
| quifael.are | Dropped from the shipped world (20/07/2026): builder Quifael's 6-room personal house -- 0 mobs/objects/resets, and unreachable in normal play (its front door exits one-way into Midgaard Park Road; no exit leads back in). Kept in `reference/quickmud` only. World is 48 areas / 3124 rooms |
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
| Input queued during lag | Raw input accumulates unparsed in `d->inbuf` while `wait > 0` (comm.c:868-872 skips `read_from_buffer`); afterwards a strict FIFO, one command per pulse -- five spammed `trip`s all execute in order and a panicked `flee` typed mid-lag waits behind every one of them | Single-slot queue (`_pending_cmd`, primesud.py): latest submission during lag overwrites any earlier one and fires on the first post-lag pulse | Latest-wins makes the panic case work: `flee` (or its digit macro) replaces queued spam instead of joining the back of a fatal queue. Cost -- multi-command buffering during lag is lost; multi-step movement already has `run_buf` (cancelled on combat/keyboard input in both codebases). The `autoskill` engine yields any round with a queued command either way |

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

Owned pets share the player's progression instead of keeping NPC XP: they
rescale whenever the player levels, survive ordinary remorts at the player's
new level 1, and gain five effective scaling levels per prestige tier.  A tier
reset follows at most one optional mob-template `E <vnum>` evolution link;
invalid and missing targets leave the current form intact.  Evolution
adopts the target template's form and combat attributes while preserving the
custom name and ownership.  Temporary pet affects are cleared on either reset.
Midgaard supplies puppy -> beagle -> rottweiler -> wolf and kitten -> lion
chains; the tiger and other unlinked pets still receive stat scaling.  Pet
saves retain template VNUM, current/max HP, custom name, and timed affects;
max HP is re-derived from owner level/tier on load (the saved field remains
for old-save compatibility), while inventory, money, XP, and comm flags are
not persisted.  This intentionally deviates from 1stMud, which purges pets
during remort.

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

## Autoskill combat automation [PRIMESUD]

Settled 18/07/2026; no 1stMud equivalent. `autoskill` fires one offensive
action per combat round on the player's behalf -- debuffs, offensive spells,
physical skills -- through the normal `do_cast`/`do_bash`/... handlers, so
mana, `WaitState` lag, fizzle, `check_improve`, and retaliation all run at
full normal cost. The engine acts only when `player["wait"] == 0`
(self-throttles to a fast typist's cadence) and yields the round whenever a
manual command is queued (`_cmd_queued`, set by the game loop).

Decisions and why:

- **Offense only -- no survival automation.** No auto-heal (with PrimeSUD's
  lenient death penalty it would make the player effectively unkillable
  while mana lasts), no auto-quaff, no flee logic; `wimpy` stays the safety
  net.
- **No buffs.** Only haste/berserk are even castable at `pos=fighting`, and
  buffs have a different lifecycle (cast, watch duration, recast on drop) --
  they belong in a possible future `autobuff` command that also covers
  non-combat buffs so they don't drop unnoticed.
- **Flat player-editable rotation** (`autoskill edit|list|reset`; see
  docs/PRIME_UX.md "Autoskill rotation editor"). Default order: debuffs
  (blindness, weaken, curse) -> offensive spells by class level descending
  -> bash/trip/dirt/disarm/kick. First eligible entry fires; eligibility
  re-checks each round (debuff not already on victim, mana reserve, cheap
  mirrors of each skill handler's static early-outs).
- **Learned floor 75 shapes defaults only.** Below-75 spells default to
  excluded (fizzle costs half mana plus a lag round), but an explicitly
  kept entry fires regardless -- explicit inclusion is informed consent;
  the floor protects the autopilot, not the player's judgement.
- **25% max-mana reserve** on auto casts so the player can always still
  choose to heal manually.
- Custom rotation persists as one save line (`p.autoskill_rot`, comma
  list, `!` prefix = excluded); absent key = pure heuristic. Newly learned
  spells auto-append to a custom rotation at the end in heuristic order,
  so saved lists never go stale.

---

## Area files

Generated `.txt` files (`area_<name>.txt`, Python source) instead of parsed `.are` files -- runtime text parsing too memory-intensive. See **[docs/AREA_FILES.md](docs/AREA_FILES.md)** for full format reference.

Single ROM 2.4 (QuickMUD-dialect) pipeline: `areas/*.are` are editable working copies (pristine upstream originals kept under `reference/`), converted by the sole `tools/are_to_primesud.py`. The old 1stMud-format converter is retired; 1stMud-only areas (`limbo`, `quest`) were converted once to ROM 2.4 so every area shares one format and one converter. `#SPECIALS`/`#SHOPS` are baked into each mob's `MOBILES` entry (`spec_fun`/`shop` keys) at conversion time rather than merged at load; a special/shop referencing a mob vnum outside its own file is a hard conversion error. A handful of 1stMud flag-bit extensions absent from stock QuickMUD `merc.h` (item `extra_flags` bits 17/26, room flag bits 4/5/20-22) are treated as canonical since the runtime is 1stMud-ported. Generated data files (`area_*.txt`, `help.txt`) use `.txt` rather than `.dat` so tooling doesn't mistake them for binary; generated index files (`help.idx`, `socials.idx`, `mobs.idx`) use `.idx` (also plain text). The converter fails loudly (`ValueError`) on any construct it doesn't handle -- unknown sections (`#AREADATA`, `#MOBOLD`/`#OBJOLD`), unrecognized trailer/reset/special letters, truncated payloads, `spec_fun` names missing from `src/special.py` `SPEC_TABLE` -- mirroring QuickMUD's own `bug()`+`exit(1)` loader; verified 2026-07-05 against all 53 stock QuickMUD areas (52 convert clean; `hood.are` correctly rejected for unimplemented specs).

---

## Lazy area loading

`world.py`'s `ROOM_DEFS`/`MOB_DEFS`/`ITEM_DEFS` are `LazyDict`s: any `[vnum]`/`.get(vnum)`/`vnum in ...` access loads that vnum's whole area file. This is cheap per-area but easy to trip accidentally -- any code that walks "all areas" (e.g. picking a destination, listing the world) ends up loading every area on the map, which is slow and heap-hungry on the calculator. `world._AREA_FILES`/`AREA_LEVELS`/`AREA_BUILDERS`/`_AREA_ADJ` are static tables (filename/tag/display-name/vnum-range, level range, builder, directed area-graph adjacency) generated by `tools/gen_area_adj.py` so area-level metadata and routing can be consulted without touching `ROOM_DEFS`. `world._vnum_to_tag(vnum)` (static-range lookup) and `world._ensure_area_by_tag(tag)` are the zero-load / single-area-load primitives built on top.

`do_areas` (`src/info.py`) renders entirely from those static tables -- no area load, ever. 1stMud's stock `do_areas` (db.c) appends a per-area `path_to_area()` directions column by default, but the same function also implements an alternate layout gated by `MudFlag(DISABLE_AREA_DIRECTIONS)` that drops the column entirely (`"%s{W[{B%-7s{W] {r%s {C%s{x"`, no trailing `(dirs)`). PrimeSUD always renders that alternate layout: computing directions for every area (even lazily) still touches enough of the room graph that most areas end up loaded, defeating the purpose. The leading marker column (1stMud: clan-restriction `*`, not ported -- no clans) is repurposed to flag the player's current area instead, since there's no directions column left to say "You are here."

`do_run` with no args (`src/movement.py`) picks a destination area from the same static area list (zero loads to build the picker), then routes via `info.find_path_to_area` -- since 20/07/2026 a thin wrapper over the same border-graph `_route` that powers `path` (next paragraph): exact shortest route, zero area loads at routing time. Areas along the walk load lazily as the run enters them, and per-pulse far-area eviction trims behind. This replaced the staged corridor pathfinder (area-adjacency chain -> chain load -> restricted room BFS -> load-all `find_area_paths` fallback), which silently produced 3-4x overlong walks through partitioned areas and loaded the whole ~5.9MB world whenever its restricted BFS dead-ended; `find_area_paths` and `_area_chain` were deleted with it. `world._AREA_ADJ` remains in use by the eviction keep-set.

`path <area or mob>` (`src/path.py`) reports the same compressed route without moving. Area names take precedence, matching 1stMud. Loaded mobs use their live room; an absent mob is resolved through `mobs.idx` and the existing two-candidate area-load cap, so wandering and restored mob positions stay authoritative without adding spawn-room data to the index. Routing runs over a precomputed **border graph** (`src/paths.idx`, built offline by `tools/build_path_index.py`): S records give the shortest intra-area walk from each entry room to each exit room of an area, X records give every cross-area exit. `_route` Dijkstras over that graph (integer weights, O(V^2) linear-min -- `heapq` availability on-device unverified) plus two live BFS legs inside already-loaded areas: player room -> source-area exits (source area is always loaded) and, for mob targets, target-area entries -> the mob's room (that area was loaded by the mob lookup). Zero area loads at routing time, and routes are exact shortest paths -- the earlier corridor-restricted BFS over the static area-adjacency chain assumed any entry of an area reaches any exit, which real (internally partitioned) areas break constantly: measured on full data, 536/2256 area pairs got no route despite one existing and 30% of exact-room targets were unreachable. Step counts match an unrestricted full-world BFS (asserted against real data in `tests/test_path_realworld.py`); the chosen equal-length route may differ from upstream's. The index freezes one layout of randomized-exit rooms (`R` resets); routes through such rooms can drift until the index is rebuilt. The upstream mob condition is inverted (`!= NULL` followed by failure clauses joined with `||`); PrimeSUD ports its clear gate-style intent instead: safe/private/solitary/no-recall rooms, quest/gquest mobs, targets 3+ levels higher, summon immunity, and a successful save all hide the destination. Arena/clan/area-access checks remain inapplicable until those systems exist. Because `path` does not move, it force-runs the normal far-area eviction check after the query.

---

## Far-area eviction [PRIMESUD]

Lazy loading alone is one-way: a long session that wanders the full world (48 areas, 3124 rooms) accretes ~5.9 MB of area data and dies mid-`reset_room` on the device's 8 MB heap (confirmed on hardware 13/07/2026). `world.maybe_evict(player)` -- called every pulse from `update_handler`; fast path is one int compare on the player's room -- unloads far areas whenever more than `AREA_CACHE_MAX` (config.py, default 12) are loaded, least-recently-visited first. Non-moving remote lookups such as `path` (whose mob lookup may load candidate areas; routing itself loads none) pass `force=True` to enforce the same cap immediately.

**Keep-set** (never evicted): the player's current area, its static `_AREA_ADJ` neighbours (so `look`/`scan`/automap at a boundary don't thrash), pinned areas (`_PINNED = ("limbo",)` -- corpse/coin/portal templates spawn on every kill), and both the template-owning and hosting areas of any follower (`master` set) or combatant (fighting the player or fought by them). The cap therefore floors at ~12 around the Midgaard hub; shrinking it below the keep-set size just disables eviction.

**Eviction = synthetic save** (`world._unload_area`): mob positions and floor items are written to `_pending_mob_saves`/`_pending_room_items` in the exact shapes the save system already uses, so reload replays them through `_apply_pending_deltas` identically to a game load, and an intervening autosave re-serializes them verbatim. Dropped without recording, matching existing save/load semantics: live door state (baseline rebuilt from the area file), mob hp/inventory (fresh from template), and foreign-template wanderers standing in evicted rooms (respawn at home on their area's next reset). Deleted mobs' dangling `fighting` refs are cleared. `area_update` skips evicted areas via the existing missing-`room_vnums` guard, so their age accrues and they reset naturally on reload.

**Cross-area resets** (owner area A places mobs/objects in target area B) survive eviction via disjoint responsibility: at A's load, A appends its cross-entries only into B-rooms *already resident* (and resets them); for unloaded targets it just triggers B's load, and B's `_load_area` pulls cross-entries targeting it from every loaded area's `AREA_DEFS` resets. Appending on both paths would duplicate resets -- the split is load-order-proof (A-first, B-first, cascade, evict+reload of either). `_unload_area(A)` removes A's cross-entries from resident foreign room defs so A's reload can't double-append.

No shipped area uses this path (audited 13/07/2026). Stock data had exactly one cross-area reset cluster -- `arachnos` spawning the Queen Spider and three poisonous spiders (plus G-gear) into Haon Dor room 6134 -- and since `areas/*.are` are our editable working copies, those placement entries were moved into `haon.are`, the room's owning area (`[PRIMESUD]` comments at both sites; templates stay defined in arachnos and cascade-load on demand). The machinery above remains as a tested guardrail for any future cross-area reset. Resets that merely *spawn a foreign template in the owner's own room* are not cross-area -- the entry partitions normally and the template cascade-loads via the `MOB_DEFS`/`ITEM_DEFS` LazyDicts.
