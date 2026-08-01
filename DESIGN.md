# PrimeSUD - Design Decisions

Intentional deviations from 1stMud and design choices made for PrimeSUD. Read before porting a new mechanic to avoid re-litigating settled decisions. Features not listed here: assume 1stMud behaviour unless code says otherwise.

**Guiding principle:** PrimeSUD is single-player. Multiplayer mechanics are excluded unless they add meaningful solo gameplay value. Mechanics with no current content hook are deferred, not eliminated.

---

## HP Prime runtime

HP Prime Python appears to load all `.py` files in the app before `primesud.py` runs. Lazy `import` patterns may not reduce first-launch wait if the source file is still packaged. Prefer lazy runtime initialisation for heap stability: avoid duplicate merged catalogs, bulk mutable state, and all-world resets until data is actually needed.

Pickers force numeric keyboard mode on entry (`picker.py:_force_numeric_keys`) so stale alpha/shift-lock state doesn't eat digit selections.

**Rendering (settled 22/07/2026).** Multi-line command output is passed
unjoined as a list through `chprintln` -> `terminal.print_lines`, which
composes the batch (scroll folded in, history-ring capture included)
offscreen in `SCRATCH_GROB` and updates the screen in one blit -- the old
screen holds during the compose, then the transition is atomic (~2ms).
Single lines draw whole `print_xy` runs (`tml_prime` override). Both paths
iterate `seg.encode()` with int-keyed glyph-offset maps because on-device
profiling showed the cost driver is Python *allocation* (~0.5ms each at
full game heap, 14x the standalone cost), not the native draw calls
(`strblit2` ~10us, heap-flat). Rule of thumb for hot loops: one avoided
alloc buys ~49 blits -- no per-char str iteration, slices, or `%`
formatting. Numbers and method: docs/PERFORMANCE.md sec. Text rendering.

**Input responsiveness (settled 30/07/2026).** The game loop is
cooperative and single-threaded; the firmware key FIFO holds only 4
presses, so the real latency metric is the longest gap between
`_pump_keyboard` calls, not average pulse time. The settled architecture
(measured history: docs/PERFORMANCE.md sec. Input-lag phase benchmark):

- **Typing path:** prompt prefix cache (`player.py` `_PROMPT_CACHE`) +
  offscreen status compose (`terminal.py` `wrapped_set_status`) +
  colour-band font cache took a keystroke from ~210 to ~84 ms.
- **Violence rounds** drain the firmware FIFO between combatants
  (`combat.py` checkpoints) and render each round through one
  `begin_batch`/`end_batch`, so long rounds delay input but no longer
  drop it.
- **Active-fighter index** (`world.FIGHTERS`): `violence_update` scans
  only fighting/hunting char ids. `set_fighting`/`stop_fighting` are the
  ONLY sanctioned mutation chokepoints for `ch["fighting"]`; the scan is
  stale-tolerant (lazily discards evicted/cleared entries), so
  clear-to-None and char-deletion paths need no index bookkeeping. The
  measured win is small (~6-20 ms in-context; the ~100 ms estimate was a
  tight-loop artifact) but it is kept for O(fighters) scaling.
  Corollary recorded the hard way: "scan-shaped" cost estimates from
  standalone loops overstate in-context cost -- measure in-context first.
- **Autosave defers while fighting** (`primesud.py` `game_loop`): both
  triggers gate on `player["fighting"] is None` and merge into one save
  on the first non-fighting pulse, removing a guaranteed ~880 ms
  mid-combat stall. Safe because mob HP/fight state never persists and
  kill-saves already cover real progress.
- **Pulse timers are phase-staggered** (`update.py`, derived at runtime)
  so the six periodic updaters never share a pulse; the 30-second
  all-updater pile-up is gone by construction. Periods are unchanged.
- **Streaming reveal** (`terminal.py`): all output paths stream at
  `REVEAL_MS_PER_LINE` (25 ms/row, device-tuned) with shared cross-call
  cadence; any key latches pacing off instantly (key kept as input) and
  `set_status` re-arms it. Optional per-char streaming behind
  `REVEAL_MS_PER_CHAR` (default off). A deliberate feel feature, not a
  cost: benches including it must subtract the pacing budget or set the
  knob to 0. UX detail: docs/PRIME_UX.md sec. Streaming output reveal.
- Measured dead ends, do not revisit without new evidence:
  interpret-level batching (`look` render share ~nil) and
  `mobile_update` scan reduction (same disproved scan-shape reasoning).

**Save-path heap policy (settled 31/07/2026).** Serialization burns
~420 KB of transient garbage per save (~13x payload; zero retained -- one
collect reclaims ~100%). The serialize itself takes no collects; reclaim
happens via a threshold-gated collect at the save's tail
(`game_state._GC_FREE_FLOOR`), pinning the collect to the one site
bench-validated clean (12 collects over save-shaped garbage,
`debug/save_smoke-9/-10.log`) instead of a random mid-gameplay
auto-collect. Explicit collects remain banned before/inside churn rich in
raw `str(int)`/formatter transients per docs/PRIME_FIRMWARE_BUGS.md.
Measurements: docs/PERFORMANCE.md sec. Save-path heap churn.

**Save compatibility policy (settled 01/08/2026).** Bump `SAVE_VERSION`,
never migrate in core. The version gate plus backup prompt
(`game_state.py` load path, `primesud.py` boot prompt) is the whole
compat story: a mismatched save is backed up and rejected, never
converted. If a player-save migration is ever worth doing, it ships as a
standalone tool outside the core codebase.

---

## Not ported

| Feature | Reason |
|---|---|
| Move / MV | Ported (row was stale, corrected 11/07/2026): sector-based `movement_loss` costs deducted in move_char (movement.py), flying/water halving/doubling, regen, train/restore paths |
| Race system | Ported: RACE_TABLE in races.py, race defaults merged at mob/player creation, check_immune in combat, race-aware stat caps (get_curr_stat/get_max_train in handler.py). Chargen: name, race, sex, class, alignment, weapon. Racial skills granted at creation. Creation-point group customisation not ported |
| Class system | Ported: CLASS_TABLE (7 classes) in classes.py, remort/multiclass, chargen class picker, per-class THAC0 and HP/mana gain, skill groups + `gain`. Six classes come from 1stMud; Swordsman is [PRIMESUD]. Creation-point group customisation at chargen not ported |
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
| Per-mob kill/death stats | Ported 21/07/2026 with sparse per-template/per-area maps in the global save. 1stMud writes counters back to `.are`; PrimeSUD generated area files stay immutable. |
| MOBprograms | Full 1stMud tri-mode prog engine (mob 10/07/2026; obj/room + completion 20-21/07/2026, `mobprog.py`). `program_flow` takes exactly one origin: mob dict, obj context, or room vnum. An obj origin is a mutable ctx dict `{"obj", "room", "carrier"}` supplied by the fire site (PrimeSUD objects carry no location back-pointer; `obj goto`/`otransfer` update it in place). Obj/room progs may only issue control + `obj <cmd>`/`room <cmd>` lines (raw command lines bug-skip, cf. programs.c:2782); their lookups use NULL-viewer semantics (no visibility filter, no self-exclusion). Per-instance state `oprog_delay`/`oprog_target` (obj dicts) and `rprog_delay`/`rprog_target` (runtime room dicts) is transient by design -- save surface is player-only. All ifchecks implemented; `clan` + `hunter` are faithful-False (no clan system; upstream never sets `->hunting`), `objval0-4` go through `item.prog_obj_value` (instance `values` tuple from `obj attrib` wins; weapon damage-type / liquid-type index spaces return 0 -- word-keyed in PrimeSUD). Group/mass commands (`gtransfer`/`gforce`/`vforce`) implemented for all three origins (mob variants exclude self, obj/room do not, per upstream). Fire seams mirror upstream order (get/drop/give obj-then-room-then-mob; move exit then greet, mob-obj-room; fight mob, worn objs, room-once-per-pulse). The `act()` obj/room TRIG_ACT block is deliberately NOT gated on the `MOBtrigger` latch and fires once per TO_ROOM/TO_NOTVICT recipient with the unrendered format, exactly as `perform_act` (comm.c:2044); recursion is bounded by the global program_flow call-depth counter. The mob-recipient act path keeps the [PRIMESUD] stricter latch (held off for the whole dispatch). Obj random/delay pulse is intent-parity: upstream's block hides behind the decay-timer gate (update.c:819), contradicting its own `obj delay`/`cancel` command surface and the room analogue (db.c:1380) -- ported per-tick; room pulse sweeps only the player's (non-empty) area. Obj `sit` trigger has no seam -- furniture is unported (movement.py position commands). Mob-to-mob speech recursion stays bounded by 1stMud's own guard (speech fires only for a player speaker). Demo content: Mud School acolyte greet/bribe/give prog [PRIMESUD]; midgaard obj 3005 drop + room 3054 grall (restored 1stMud originals). Area dialect: docs/AREA_FILES.md |
| quifael.are | Dropped from the shipped world (20/07/2026): builder Quifael's 6-room personal house -- 0 mobs/objects/resets, and unreachable in normal play (its front door exits one-way into Midgaard Park Road; no exit leads back in). Kept in `reference/quickmud` only |
| Furniture mechanics | sit/rest/sleep AT/ON/IN targets, occupancy (`count_users`), and value[3]/value[4] regen multipliers omitted -- no usable content: 12 of 13 stock furniture objects carry `0 0 0 0 0`; the sole nonzero carrier is wearable red dragon claws vnum 7306, mis-typed as furniture with value[0]=9 but no position flags, so it cannot be used as furniture. do_sit/do_rest/do_sleep/do_stand ignore the furniture keyword. Inns already regen faster via room heal_rate 110. Revisit alongside authored furniture content; full source map in git history (REGEN_PLAN.md decision 3) |
| Raw object `values` fallback | Settled without a generic port (22/07/2026). The converter retains nonzero raw value[0..4] tuples for object types without a dedicated schema, and `prog_obj_value` already exposes them to `objval0-4` plus instance overrides from `obj attrib`. Shipped content has 53 such templates (30 keys, 11 maps, 4 gems, 3 warp stones, 2 corpses, 2 treasures, and the mis-typed furniture above); no stock objprog reads them and no missing shipped mechanic consumes their type-specific meanings. Keep the lossless data/prog surface; add a reader only with an independently justified item mechanic or authored content. |
| Room `save_objs` flag | Settled without a flag-specific port (22/07/2026). 1stMud uses `ROOM_SAVE_OBJS` to select rooms whose floor contents survive restart. PrimeSUD's save model already persists floor objects in every room, including the static player home, so reading the flag would add no behavior. |
| Object condition/wear | Settled non-port (22/07/2026). The converter retains the `.are` condition letter losslessly, but 1stMud `create_object` never copies `pObjIndex->condition`: `new_obj` copies zero-initialized `obj_zero`, so normal instances begin at 0. No in-game wear, break, or repair path consumes it; remaining paths mutate, persist, or display the state. PrimeSUD has no gameplay reader, so do not add runtime condition state unless authored condition gameplay arrives. |
| Mob material runtime state | Settled without a runtime field (22/07/2026; death-cry parity corrected 23/07/2026). Templates retain material losslessly. 1stMud's only in-scope gameplay read is `death_cry` testing `ch->material == NULL`: PCs leave it NULL, while NPC creation always assigns a string. PrimeSUD matches that behavior directly from `is_npc` -- roll 1 gives PCs the blood message and falls through to the guts case for NPCs. |
| `fix_exits` boot pass | Settled non-port (22/07/2026). Full shipped-world audit found zero dangling exits; the only missing automatic `ROOM_NO_MOB` is hidden New Thalos pet-stock room 9706, whose zero exits already prevent wandering. Movement rejects an unresolved destination, while a global runtime pass would defeat lazy loading. Revisit only if authored area data introduces a dangling exit. |

---

## Adjusted from 1stMud

| Feature | 1stMud | PrimeSUD | Reason |
|---|---|---|---|
| EXP per level | `exp_per_level()` -- scales with creation points and race/class mult | Flat 1000 XP / level | Equivalent at 40 creation points, human baseline |
| Level-up heal | Adds gains to `max_hit`/`max_mana`; current HP/MP unchanged | Fully restores current HP and MP | Eliminates "levelled at 1 HP mid-fight" |
| Remort progression | `finish_remort` grants `100*lvl_bonus` hp/mana/move, `5*lvl_bonus` trains, `7*lvl_bonus` practices -- ~6000/300/420 at first remort | Same `lvl_bonus` formula, all three grants divided by `REMORT_POWER_DIV` (config.py, default 12) -- ~500 hp / 25 trains / 35 practices; `1` restores stock | Revisited 11/07/2026 (was "accepted, revisit after playtest"): 6000 hp against PrimeSUD's 50-hp creation baseline trivialised everything; ~500 keeps the power-fantasy bump without breaking content. Single knob keeps vitals/trains/practices proportional |
| Guild rooms | Single class per guild room; midgaard has no paladin/ranger/swordsman guilds | Paladin shares the Cleric guild rooms; Ranger and Swordsman share the Warrior's; all four midgaard GMs are gain-capable (`areas/midgaard.are` room `G` trailers + mob `act_flags`; see docs/AREA_FILES.md "Deviations from stock QuickMUD") | Every class must be gain/remort-capable within the loaded-area set |
| Pulse timing | `PULSE_VIOLENCE = 3xPPS`, `PULSE_MOBILE = 4xPPS`, `PULSE_TICK = 45xPPS` | `PULSE_VIOLENCE = 2xPPS`, `PULSE_MOBILE = 5xPPS`, player `PULSE_REGEN = 5xPPS`, world/mob `PULSE_TICK = 30xPPS`; fractional carry preserves the 30-second player recovery total | Faster combat and smoother player recovery without rounding loss; slower mob wander; mob regen retains world-tick cost |
| Gquest joining | 3-min GQUEST_WAITING window to gather joiners via `gquest join`; cancels with "Not enough people" if none join; ends running quest when last player leaves | No window -- quest starts running at announcement with the player auto-joined (same gates as manual join: no regular quest, level in range); auto-quest level band clamped to always include the player; runs until time expires; `gquest quit`/`join` still allow opt-out/rejoin (e.g. join after wrapping up a regular quest) | Single player -- window was dead time (kills don't credit until RUNNING), "not enough players" can't be a failure mode, joining has no penalty, and an unjoinable quest is dead content |
| World-reset object counts | Incremental `pObjIndex->count` bumped at create/extract | Recomputed once per reset pass (`mob._object_count_map`) from the loaded world -- room floor items + one level of container `contents` + every char's inventory/equipment -- then incremented locally as the pass spawns | Sacrifice/quaff/decay/burnout extraction paths would drift a persistent counter and force it into the save file; lazy loading makes the computed count correct-by-construction (unloaded areas hold no instances) |
| P-reset container target | `get_obj_type` scans the global object list for the most recent container instance; a carried container (`in_room == NULL`) is valid only while `last` holds (db.c:1554) | Most-recent instance found in the *resetting room* only: floor items first, then -- gated on `last_spawned`, mirroring db.c:1554 -- the room's mobs' inventory and equipment | Stock P always targets a container O-placed or E/G-given in the resetting room (all areas verified 31/07/2026; the converter's fix_exits-style checks keep it that way), so the room scope is behaviour-identical to upstream while keeping lazy loading intact. Floor-only until 31/07/2026, which silently dropped 19 mob-carried fills (mahntor key ring, hitower pouches, moria corpse+map, chapel head, gnome basket) -- see docs/FIXES.md |
| R-reset exit shuffle | Fisher-Yates over the live exit array, doors included | Same shuffle over the first N of the fixed `n,e,s,w,u,d` order, but skipped entirely if any affected exit is a door | Door reset state is keyed by (room, direction) in `DOOR_DEFS`; shuffling a door would desync it. Stock shuffled carriers (daycare maze, limbo) carry no doors on shuffled exits. Automap/`do_run` read the mutated static exits, diverging from ROOM_DEFS exactly as 1stMud mutates its live exits |
| Room light counter | `room->light` bumped incrementally in `char_to_room`/`equip_char` | Computed on demand: `room_light(vnum)` counts lit lights worn by the room's occupants **and lying on its floor** | The many extraction/removal paths would drift a persistent counter and force it into the save. Floor lights also illuminate ([PRIMESUD], unlike stock ROM/1stMud which count only worn lights -- `room->light` is never touched by `obj_to_room`): a dropped torch or a cast continual-light ball lighting the room is the intuitive behaviour. Lights inside containers do not count |
| `can_see_room` | Gates immortal / clan / owner room flags | Always permissive | Single-player: no immortals or clans, and the only room-flag carrier (`area_immort`) is already unreachable |
| Player housing | `pestates.are` entrance allocates up to five rooms, keys, exits, and ownership through runtime OLC; multiplayer invite/evict; area files rewritten | One static Player Estates home: stock purchase price/key/locked door, `home key`/`recall`/`name`/`describe`, persistent dropped decorations | Single player needs one home; fixed room data avoids dynamic world-definition persistence while preserving housing's solo value |
| Explore-bit mark point | `StrSetBit` in `char_to_room` (handler.c:1360) -- one choke point on every room entry | `mark_explored(player)` called once per command dispatch (`commands.interpret`) and once per update tick (`update.update_handler`), setting the bit when the player's room differs from a cached `_last_marked_room` | PrimeSUD has no `char_to_room` choke point -- room assignment is scattered across movement/magic/combat/training/debug/load. The command seam catches player moves; the tick seam catches mob-initiated drags (summon). Per-area room counts baked at generation time (`AREA_ROOM_COUNTS`) so `arearooms`/score never load an area |
| Weather model | Per-area temp/precip/wind vector sim seeded from each area's climate | Same engine, climate baked to a neutral `2 2 2` for every area; integer-only, and the change echo is computed for the player's area alone | Loaded area files all carry `Climate 2 2 2`, so climate 2 zeroes the climate-pull term (no floats on-device), and 1stMud never displays a non-player area's echo |
| `do_time` | Calendar line plus boot/copyover/timezone/connected/creation lines | Calendar line + hours played only | The server/multiplayer state has no single-player equivalent |
| `do_group` roster | One `[%2d %s] %-16s %4ld/%4ld hp ... %5d xp` line per member (~70 chars) | Two lines per member: `[%2d %-4s] <name>` then an indented, column-aligned `hp/mana/mv/xp` stats line | The single line overflows the 64-col screen and wraps mid-value; the split fields stay vertically aligned down the list |
| Movement lag | `move_char` applies `WAIT_STATE(ch, 1)` -- one pulse of recovery per step, so fast walking queues input behind the lag gate | No movement WaitState: steps cost movement points only, and `run` advances one step per pulse | Single-player pacing: nothing competes for pulses, so the `[Recovering...]` gate on plain walking was pure friction. Skill/combat lag unchanged |
| Input queued during lag | Raw input accumulates unparsed in `d->inbuf` while `wait > 0` (comm.c:868-872 skips `read_from_buffer`); afterwards a strict FIFO, one command per pulse -- five spammed `trip`s all execute in order and a panicked `flee` typed mid-lag waits behind every one of them | Single-slot queue (`_pending_cmd`, primesud.py): latest submission during lag overwrites any earlier one and fires on the first post-lag pulse | Latest-wins makes the panic case work: `flee` (or its digit macro) replaces queued spam instead of joining the back of a fatal queue. Cost -- multi-command buffering during lag is lost; multi-step movement already has `run_buf` (cancelled on combat/keyboard input in both codebases). The `autoskill` engine yields any round with a queued command either way |

---

## Swordsman / Sword Saint [PRIMESUD]

Added 23/07/2026 as the first post-1.0 content class. Swordsman is a
DEX-primary, non-caster single-sword duelist: sword is rating 1, dagger is an
optional level-5 sidearm, and other weapon skills are unavailable. THAC0 and
HP sit between Thief and Warrior. Swordsman shares the Warrior guild rooms.

Three unique skills condense classical Chinese sword forms without adding a
second stance system:

- `flow` / flowing form (level 12): one sword hit with +4 THAC0 accuracy,
  90% damage, and 12-beat lag.
- riposte (level 30): after a successful sword parry, `skill // 4` percent
  chance for one immediate normal sword hit; ripostes cannot chain.
- `drive` / driving form (level 42): one sword hit at 140% damage with
  24-beat lag.

All three skills add a small DEX bonus to their activation or proc chance:
one percentage point per two DEX above 13, capped at +5. Riposte improvement
is checked on both successful procs and failed eligible proc rolls.

Each active skill chooses from a tone-specific message pool. Cosmetic
combat flourishes use the last active form's flowing/driving pool. Form
choice defaults to flowing before first use, persists across fights and
target changes, and is not saved. Flourishes have no mechanical effect.

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
Display: `score` Level cell `(T<tier>)` suffix (only when tier > 0),
`class_who` `*<tier>` suffix.
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
- **Flat player-editable rotation** (`autoskill on|off|edit|list|reset`; see
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

Single ROM 2.4 (QuickMUD-dialect) pipeline: `areas/*.are` are editable working copies (pristine upstream originals kept under `reference/`), converted by the sole `tools/are_to_primesud.py`. The old 1stMud-format converter is retired; 1stMud-only areas (`limbo`, `quest`, `pestates`) were converted once to ROM 2.4 so every area shares one format and one converter. `#SPECIALS`/`#SHOPS` are baked into each mob's `MOBILES` entry (`spec_fun`/`shop` keys) at conversion time rather than merged at load; a special/shop referencing a mob vnum outside its own file is a hard conversion error. A handful of 1stMud flag-bit extensions absent from stock QuickMUD `merc.h` (item `extra_flags` bits 17/26, room flag bits 4/5/20-22) are treated as canonical since the runtime is 1stMud-ported. Generated data files (`area_*.txt`, `help.txt`) use `.txt` rather than `.dat` so tooling doesn't mistake them for binary; generated index files (`help.idx`, `socials.idx`, `mobs.idx`) use `.idx` (also plain text). `mobs.idx` stores one compact row per template (`vnum|home_tag|level|keywords|short_descr|spawn_tags`): counters/debug use metadata without area loads, while ordered reset-owning `spawn_tags` preserve unloaded-mob lookup priority. `objs.idx` likewise stores every object template as `home_tag|vnum|keywords|spawn_tags`; `debug vnum` uses the first three fields and `locate object` uses ordered `O`/`E`/`G`/`P` reset-owning tags. The converter fails loudly (`ValueError`) on any construct it doesn't handle -- unknown sections (`#AREADATA`, `#MOBOLD`/`#OBJOLD`), unrecognized trailer/reset/special letters, truncated payloads, `spec_fun` names missing from `src/special.py` `SPEC_TABLE` -- mirroring QuickMUD's own `bug()`+`exit(1)` loader; verified 2026-07-05 against all 53 stock QuickMUD areas (52 convert clean; `hood.are` correctly rejected for unimplemented specs).

---

## Lazy area loading

**Recommendation indexes (settled 31/07/2026).** `mobs.idx` appends ordered
`fight_tags` to its existing template/spawn fields; older six-field rows remain
valid for non-recommendation consumers. `gear.idx` stores canonical-score
components plus one row per static loot, ordinary-shop, floor, or floor-
container source, grouped into per-wear-slot segments behind a byte-length
directory line so runtime seeks and reads only needed segments (largest ~56 KB,
never the whole ~178 KB file -- cf. the `help.dat` bulk-read ceiling in
docs/PERFORMANCE.md). `recommend` scans only these files and resident
player/static tables, retains bounded displayed results, creates no candidate
instances, loads no area, and keeps no parsed cache.

`world.py`'s `ROOM_DEFS`/`MOB_DEFS`/`ITEM_DEFS` are `LazyDict`s: any `[vnum]`/`.get(vnum)`/`vnum in ...` access loads that vnum's whole area file. This is cheap per-area but easy to trip accidentally -- any code that walks "all areas" (e.g. picking a destination, listing the world) ends up loading every area on the map, which is slow and heap-hungry on the calculator. `world._AREA_FILES`/`AREA_LEVELS`/`AREA_BUILDERS`/`_AREA_ADJ` are static tables (filename/tag/display-name/vnum-range, level range, builder, directed area-graph adjacency) generated by `tools/gen_area_adj.py` so area-level metadata and routing can be consulted without touching `ROOM_DEFS`. `world._vnum_to_tag(vnum)` (static-range lookup) and `world._ensure_area_by_tag(tag)` are the zero-load / single-area-load primitives built on top.

`do_areas` (`src/info.py`) renders entirely from those static tables -- no area load, ever. 1stMud's stock `do_areas` (db.c) appends a per-area `path_to_area()` directions column by default, but the same function also implements an alternate layout gated by `MudFlag(DISABLE_AREA_DIRECTIONS)` that drops the column entirely (`"%s{W[{B%-7s{W] {r%s {C%s{x"`, no trailing `(dirs)`). PrimeSUD always renders that alternate layout: computing directions for every area (even lazily) still touches enough of the room graph that most areas end up loaded, defeating the purpose. The leading marker column (1stMud: clan-restriction `*`, not ported -- no clans) is repurposed to flag the player's current area instead, since there's no directions column left to say "You are here."

`do_run` with no args (`src/movement.py`) picks a destination area from the same static area list (zero loads to build the picker), then routes via `info.find_path_to_area` -- since 20/07/2026 a thin wrapper over the same border-graph `_route` that powers `path` (next paragraph): exact shortest route, zero area loads at routing time. Areas along the walk load lazily as the run enters them, and per-pulse far-area eviction trims behind. This replaced the staged corridor pathfinder (area-adjacency chain -> chain load -> restricted room BFS -> load-all `find_area_paths` fallback), which silently produced 3-4x overlong walks through partitioned areas and loaded the whole ~5.9MB world whenever its restricted BFS dead-ended; `find_area_paths` and `_area_chain` were deleted with it. `world._AREA_ADJ` remains in use by the eviction keep-set.

`path <area or mob>` (`src/path.py`) reports the same compressed route without moving. Area names take precedence, matching 1stMud. Loaded mobs use their live room; an absent mob is resolved through `mobs.idx` and the existing two-candidate area-load cap, so wandering and restored mob positions stay authoritative without adding spawn-room data to the index. Routing runs over a precomputed **border graph** (`src/paths.idx`, built offline by `tools/build_path_index.py`): S records give the shortest intra-area walk from each entry room to each exit room of an area, X records give every cross-area exit. `_route` Dijkstras over that graph (integer weights, O(V^2) linear-min -- `heapq` availability on-device unverified) plus two live BFS legs inside already-loaded areas: player room -> source-area exits (source area is always loaded) and, for mob targets, target-area entries -> the mob's room (that area was loaded by the mob lookup). Zero area loads at routing time, and routes are exact shortest paths -- the earlier corridor-restricted BFS over the static area-adjacency chain assumed any entry of an area reaches any exit, which real (internally partitioned) areas break constantly: measured on full data, 536/2256 area pairs got no route despite one existing and 30% of exact-room targets were unreachable. Step counts match an unrestricted full-world BFS (asserted against real data in `tests/test_path_realworld.py`); the chosen equal-length route may differ from upstream's. The index freezes one layout of randomized-exit rooms (`R` resets); routes through such rooms can drift until the index is rebuilt. The upstream mob condition is inverted (`!= NULL` followed by failure clauses joined with `||`); PrimeSUD ports its clear gate-style intent instead: safe/private/solitary/no-recall rooms, quest/gquest mobs, targets 3+ levels higher, summon immunity, and a successful save all hide the destination. Arena/clan/area-access checks remain inapplicable until those systems exist. Because `path` does not move, it force-runs the normal far-area eviction check after the query.

`locate object` preserves 1stMud's world-global search without loading the full
world at once. It scans resident state first, then uses `objs.idx` reset-owning
tags plus nested `_pending_room_items` tokens to hydrate only plausible areas,
one candidate at a time. Each load and any cascade-loaded areas are scanned
once through the normal visibility/name/`nolocate`/chance/level filters, then
unloaded in `finally`; no later candidate loads once `max_found = 2 * level`
accepted results exist. Result order is deterministic resident/index order,
not 1stMud's process-local object allocation order.

---

## Far-area eviction [PRIMESUD]

Lazy loading alone is one-way: a long session that wanders the full world exhausts the device's 8 MB heap and dies mid-`reset_room` (confirmed on hardware 13/07/2026). `world.maybe_evict(player)` -- called every pulse from `update_handler`; fast path is one int compare on the player's room -- unloads far areas whenever more than `AREA_CACHE_MAX` (config.py, default 12) are loaded, least-recently-visited first. Non-moving remote lookups such as `path` (whose mob lookup may load candidate areas; routing itself loads none) pass `force=True` to enforce the same cap immediately.

**Keep-set** (never evicted): the player's current area, its static `_AREA_ADJ` neighbours (so `look`/`scan`/automap at a boundary don't thrash), pinned areas (`_PINNED = ("limbo",)` -- corpse/coin/portal templates spawn on every kill), and both the template-owning and hosting areas of any follower (`master` set) or combatant (fighting the player or fought by them). The cap therefore floors at ~12 around the Midgaard hub; shrinking it below the keep-set size just disables eviction.

**Eviction = synthetic save** (`world._unload_area`): mob positions and floor items are written to `_pending_mob_saves`/`_pending_room_items` in the exact shapes the save system already uses, so reload replays them through `_apply_pending_deltas` identically to a game load, and an intervening autosave re-serializes them verbatim. Dropped without recording, matching existing save/load semantics: live door state (baseline rebuilt from the area file), mob hp/inventory (fresh from template), and foreign-template wanderers standing in evicted rooms (respawn at home on their area's next reset). Deleted mobs' dangling `fighting` refs are cleared. `area_update` skips evicted areas via the existing missing-`room_vnums` guard, so their age accrues and they reset naturally on reload.

**Reset ownership invariant [PRIMESUD]:** every `M`/`O`/`R`/`D` reset must target a room defined in the same `.are` file. The converter fails loudly when an area tries to push state into another area's room. An area may still pull foreign mob/object templates into its own rooms; their definitions cascade-load through `MOB_DEFS`/`ITEM_DEFS`. Stock's only room-crossing cluster (`arachnos` placing spiders in Haon Dor room 6134) was moved to `haon.are`, while its templates remain in `arachnos.are`.

## Item template snapshots [PRIMESUD]

Eviction's counterpart for items: gear that outlives its template-owning area (player inventory/equipment, foreign floor drops, deferred room tokens, surviving NPC/shop stock) must keep answering template reads without dragging the owner area back onto the heap -- including across save/load, where a first post-login inventory scan otherwise stalls seconds per souvenir area (New Thalos alone ~10s). Settled design (29/07/2026; full rationale in git history: SNAPSHOT_PLAN.md):

- **Shared registry, not per-instance copies.** `world.ITEM_SNAPSHOTS = {vnum: (validated_revision, template_dict, objprog_dict)}` -- one entry per VNUM regardless of instance count; instances carry no marker (the VNUM is the key). Rejected alternatives: flattening template fields onto instances (blurs template/instance provenance, bloats saves, pins rebalanced stats) and inverting the 14 `item_*` accessor signatures (all-caller churn for the same effect).
- **One lookup seam.** `item_tpl`/`item_tpl_get` resolve resident `ITEM_DEFS._data` -> current-revision registry entry -> intentional lazy load -> orphan fallback. Resident data always wins, so a loaded area's current templates supersede any snapshot; loading an area prunes registry entries it makes resident. Genuine instance overrides keep winning through the instance-first accessors.
- **Eviction materializes; save persists.** `_materialize_item_snapshots` runs after dying NPCs are deleted (survivor walk needs no dead-set plumbing) and collects distinct owned vnums from survivor inv/equip, foreign loaded rooms, and `_pending_room_items` (dict-free token vnum walker). Saves write one deduplicated `it.<vnum>=<revision>|<record>` line per required vnum (player gear always; foreign-owner room/pending items), additive to the v10 format -- no `SAVE_VERSION` bump; malformed lines are individually skipped cache misses. A cold mark/sweep at save prunes unreferenced entries; no incremental refcounts (a missed mutation path would leak or over-free).
- **Typed codec, no eval/repr/JSON.** `_snap_encode`/`_snap_decode`: self-delimiting one-char type tags over None/bool/int/str/list/tuple/dict, sorted dict keys for determinism. Unsafe bytes (`~ " \n \r \`) are REPLACED by two-char escapes -- `load_world` splits the payload with a naive `split("~")` that ignores backslashes, so prefixing is not enough (14 real templates carry quotes, 213 newlines). The PPL string literal in `hvars_set` DOES interpret backslash escapes -- and fails the whole eval silently on unknown ones (device-confirmed 29/07/2026, `debug/hvar_cap-2.log`) -- so `hvars_set` doubles backslashes in transit and the codec's two-char sequences round-trip unchanged. The all-area round-trip test is the drift guard: a new unsupported value type in area data fails loudly.
- **Save-path caches.** `_PENDING_VNUM_CACHE` (per-room pending-token vnum scans, validated by raw-string identity -- pending strings are replaced wholesale, never mutated), `_SNAP_ENC_CACHE` (vnum -> encoded `it.` line, valid while the stamped revision matches; prefilled from raw save bytes at load), and `_PENDING_MOB_CACHE` (tpl vnum -> serialized `m=` part string, validated by room-list identity; prefilled from the raw save entry at load). Round 2 (30/07/2026, targets from the fine-grained segment split in debug/save_smoke-5.log): `_PENDING_ROOM_LINE_CACHE` (rvnum -> finished `r.<vnum>.items` passthrough line, raw-string identity), `_MOB_STAT_LINE_CACHE`/`_AREA_STAT_LINE_CACHE` (`s.m.`/`s.a.` lines keyed by (kills, deaths) VALUE pair -- the stat lists mutate in place, so identity cannot detect changes), and the RLE explored-mask encode cached on the player (`_rle_cache`, dropped only when a mask bit actually changes; `mark_explored` checks the bit first, so revisits never invalidate). All world caches owned by world.py, cleared in `reset_lazy`; `load_world` prewarms the pending-token cache so the one-time scan cost lands on the load screen, not the first autosave. Device-measured on G1: full-world save 11.7s -> 1.6s -> 0.88s -> 0.37s steady all-pending / 0.83s with 3 areas resident, where live-data serialization (room items + NPC positions) dominates (debug/save_smoke-1..-7.log, 29-30/07/2026).
- **Staleness = one global digest.** Generated `CONTENT_REVISION` (sha256 prefix over all OBJECTS+OBJPROGS via the codec itself, `tools/gen_area_adj.py`). Mismatch means one corrective area load, then refreshed on next save -- exactly pre-snapshot behavior after a content update. Per-area digests deliberately rejected until content updates are frequent enough to matter. Removed-vnum orphans: the stale entry answers, gets restamped once, and lives until mark/sweep drops it -- no retry ladder.
- **Object programs ride along.** Each entry captures only the `OBJPROGS` sources its template's `obj_triggers` reference; `mobprog._run_oprog` falls back to the snapshot's program map when the resident table misses.
- **Device-validated on G1 (30/07/2026, debug/snapshot_gates-1.log).** Heap flat across travel/eviction cycles, stale revision costs exactly one corrective owner load, snapshot obj prog fires with the owner unloaded (numbers in docs/PERFORMANCE.md sec. Save path). If save size ever bites, the first lever is field-name tags inside the snapshot codec -- never silently dropping `description`/`extra_descs`.
