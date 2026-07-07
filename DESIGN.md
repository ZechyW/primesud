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
| Explore tracking | Planned; placeholder in `do_score` |
| Trivia economy | Counter and trivia pill retained for quest compatibility; shop/reward system later |
| Pkills / pdeaths | Single-player |
| Per-mob kill/death stats | 1stMud writes back to `.are` on shutdown; PrimeSUD areas are static Python files |

---

## Adjusted from 1stMud

| Feature | 1stMud | PrimeSUD | Reason |
|---|---|---|---|
| EXP per level | `exp_per_level()` -- scales with creation points and race/class mult | Flat 1000 XP / level | Equivalent at 40 creation points, human baseline |
| Level-up heal | Adds gains to `max_hit`/`max_mana`; current HP/MP unchanged | Fully restores current HP and MP | Eliminates "levelled at 1 HP mid-fight" |
| Remort progression | `lvl_bonus` multiplier against 1stMud's economy | Same formula against PrimeSUD's flatter economy (20 HP at creation) -- first remort lands ~6000 HP/mana/move, 300 trains, 420 practices | Accepted 03/07/2026 as an NG+-style feature; revisit after playtest |
| Guild rooms | Single class per guild room; midgaard has no paladin/ranger guilds | Paladin shares the Cleric guild rooms, Ranger shares the Warrior's; all four midgaard GMs are gain-capable (`patch_1stmud_deltas.py`) | Every class must be gain/remort-capable within the loaded-area set |
| Pulse timing | `PULSE_VIOLENCE = 3xPPS`, `PULSE_MOBILE = 4xPPS`, `PULSE_TICK = 45xPPS` | `2xPPS`, `5xPPS`, `30xPPS` | Faster combat/regen; slower mob wander |
| Gquest joining | 3-min GQUEST_WAITING window to gather joiners via `gquest join`; cancels with "Not enough people" if none join; ends running quest when last player leaves | No window -- quest starts running at announcement with the player auto-joined (same gates as manual join: no regular quest, level in range); auto-quest level band clamped to always include the player; runs until time expires; `gquest quit`/`join` still allow opt-out/rejoin (e.g. join after wrapping up a regular quest) | Single player -- window was dead time (kills don't credit until RUNNING), "not enough players" can't be a failure mode, joining has no penalty, and an unjoinable quest is dead content |

---

## Area files

Generated `.txt` files (`area_<name>.txt`, Python source) instead of parsed `.are` files -- runtime text parsing too memory-intensive. See **[docs/AREA_FILES.md](docs/AREA_FILES.md)** for full format reference.

Single ROM 2.4 (QuickMUD-dialect) pipeline: `areas/*.are` are editable working copies (pristine upstream originals kept under `reference/`), converted by the sole `tools/are_to_primesud.py`. The old 1stMud-format converter is retired; 1stMud-only areas (`limbo`, `quest`) were converted once to ROM 2.4 so every area shares one format and one converter. `#SPECIALS`/`#SHOPS` are baked into each mob's `MOBILES` entry (`spec_fun`/`shop` keys) at conversion time rather than merged at load; a special/shop referencing a mob vnum outside its own file is a hard conversion error. A handful of 1stMud flag-bit extensions absent from stock QuickMUD `merc.h` (item `extra_flags` bits 17/26, room flag bits 4/5/20-22) are treated as canonical since the runtime is 1stMud-ported. Generated data files (`area_*.txt`, `help.txt`, `mob_index.txt`) use `.txt` rather than `.dat` so tooling doesn't mistake them for binary. The converter fails loudly (`ValueError`) on any construct it doesn't handle -- unknown sections (`#AREADATA`, `#MOBOLD`/`#OBJOLD`), unrecognized trailer/reset/special letters, truncated payloads, `spec_fun` names missing from `src/special.py` `SPEC_TABLE` -- mirroring QuickMUD's own `bug()`+`exit(1)` loader; verified 2026-07-05 against all 53 stock QuickMUD areas (52 convert clean; `hood.are` correctly rejected for unimplemented specs).

---

## Lazy area loading

`world.py`'s `ROOM_DEFS`/`MOB_DEFS`/`ITEM_DEFS` are `LazyDict`s: any `[vnum]`/`.get(vnum)`/`vnum in ...` access loads that vnum's whole area file. This is cheap per-area but easy to trip accidentally -- any code that walks "all areas" (e.g. picking a destination, listing the world) ends up loading every area on the map, which is slow and heap-hungry on the calculator. `world._AREA_FILES`/`AREA_LEVELS`/`AREA_BUILDERS`/`_AREA_ADJ` are static tables (filename/tag/display-name/vnum-range, level range, builder, directed area-graph adjacency) generated by `tools/gen_area_adj.py` so area-level metadata and routing can be consulted without touching `ROOM_DEFS`. `world._vnum_to_tag(vnum)` (static-range lookup) and `world._ensure_area_by_tag(tag)` are the zero-load / single-area-load primitives built on top.

`do_areas` (`src/info.py`) renders entirely from those static tables -- no area load, ever. 1stMud's stock `do_areas` (db.c) appends a per-area `path_to_area()` directions column by default, but the same function also implements an alternate layout gated by `MudFlag(DISABLE_AREA_DIRECTIONS)` that drops the column entirely (`"%s{W[{B%-7s{W] {r%s {C%s{x"`, no trailing `(dirs)`). PrimeSUD always renders that alternate layout: computing directions for every area (even lazily) still touches enough of the room graph that most areas end up loaded, defeating the purpose. The leading marker column (1stMud: clan-restriction `*`, not ported -- no clans) is repurposed to flag the player's current area instead, since there's no directions column left to say "You are here."

`do_run` with no args (`src/movement.py`) picks a destination area from the same static area list (zero loads to build the picker), then pathfinds lazily via `info.find_path_to_area`: (1) zero-load BFS over the static area-adjacency graph to find a chain of areas from here to there; (2) load just the areas on that chain; (3) a *restricted* room-level BFS from the player's room that filters every candidate destination room through `world._vnum_to_tag` (zero-load) before ever touching `ROOM_DEFS` for it, so it can't accidentally load an area outside the chain; (4) if that restricted search can't complete the chain at room granularity (e.g. a one-way exit means the graph edge isn't walkable in this direction), fall back to the old exhaustive `find_area_paths`, which loads every area but is guaranteed to find any reachable target. `find_area_paths`/`_compress_path` are unchanged and remain as that fallback.
