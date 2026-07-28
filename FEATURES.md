# PrimeSUD -- What's Different

PrimeSUD is a single-player port of 1stMud 4.5.3 (a ROM 2.4 derivative) to the
HP Prime graphing calculator. The default is fidelity: anything not listed
here plays like 1stMud. This file is the curated index of what *doesn't* --
the things that make PrimeSUD PrimeSUD -- for the curious ROM/1stMud player.
Each entry is one line; depth lives in DESIGN.md, docs/FIXES.md, and the
`[PRIMESUD]` tags at the code sites.

---

## New systems

Things with no upstream equivalent.

- **Prestige tiers** -- at the remort class cap, `remort` becomes a repeatable
  *tier reset* instead of 1stMud's "You can't remort any more!": restart
  near-fresh with one class and permanent per-tier perks (kept masteries,
  +tier stats/pools, skill floors, raised practice ceiling). Full spec in
  DESIGN.md "Multiclass prestige tiering".
- **Growing and evolving pets** -- pets scale with player levels, survive
  remorts, and optionally evolve through area-authored forms on tier resets
  (DESIGN.md "Multiclass prestige tiering").
- **Race and sex re-pick on every remort** -- remorting re-runs the race/sex/
  class creation prompts; upstream's `stay_race` "that race FOREVER" lock is
  deliberately not ported (DESIGN.md).
- **Area speedwalk** -- `run` with no argument opens a picker of known areas
  and auto-walks a computed path there, pathfinding over a static area graph
  (movement.py, info.py).
- **Automatic door handling** -- walking into a closed door opens it (unlocking
  with a carried key if needed) and re-closes/re-locks it behind you and your
  followers (movement.py).
- **Stance onboarding** -- new characters start out of stance; the first fight
  triggers a one-time cinematic stance pick plus a follow-up tutorial hint
  (stances.py).
- **Gquest countdowns** -- global quests self-schedule on a real-minute timer
  and announce "a global quest will begin in about N minutes" beforehand
  (gquest.py).
- **Obj/room progs in the QuickMUD area format** -- the full 1stMud prog
  engine (mob, object, and room programs: every trigger, `obj`/`room`
  command table, and ifcheck) is authorable straight in the `.are` files
  via `O`/`R` trailers plus `#OBJPROGS`/`#ROOMPROGS` sections, a [PRIMESUD]
  dialect extension to the QuickMUD format 1stMud never had (docs/
  AREA_FILES.md; DESIGN.md "MOBprograms").
- **Autoskill combat automation** -- `autoskill` fires one offensive debuff,
  spell, or skill per combat round through the normal handlers at full
  mana/lag/fizzle cost; rotation is player-editable via a navpad-driven
  blocking editor (`autoskill edit`). Survival (heal, quaff, flee) stays
  manual (autoskill.py; DESIGN.md "Autoskill combat automation").

## Reimagined for one player

There are no other players, no immortals, no clans -- and the design turns
that into features rather than holes.

- **Pickers replace typing** -- `kill`, `get`, `give`, `wear`, `cast`, `practice`,
  `train`, `buy`, `sell`, `examine`, `open`/`unlock`, remort, chargen: given no
  argument, each opens a numbered target menu instead of failing
  (docs/PRIME_UX.md).
- **Contextual quest hub** -- bare `quest` shows status away from questmasters;
  at one, it offers valid quest actions and nested reward-shop pickers, while
  completed quests auto-complete instead of accepting an accidental quit
  (docs/PRIME_UX.md).
- **Gear score and `wear best`** -- compatible equipment shares one combat-aware
  score used by `compare`; `wear best` equips strict per-slot upgrades and picks
  the best legal hand layout (shield, two-handed, dual wield) by combined score
  (docs/PRIME_UX.md).
- **Browsable help** -- bare `help` opens a category-then-entry browser driven
  by digits and Enter, reaching all 288 entries without alpha-shifting a
  keyword, and `help <letter>` picks from its matches instead of printing a
  list you can only act on by retyping; Enter on the default option still
  gives upstream's one-page summary. Categories are rebalanced for menu use --
  upstream's 50-entry `unknown` bucket is split, and helps for systems
  PrimeSUD doesn't port (OLC, clans, deities, immortal powers) sit at level 51
  instead of cluttering the browser and `index` (docs/PRIME_UX.md).
- **Name picker and free rename** -- chargen offers six generated fantasy
  names (1stMud's namegen syllable pools) with reroll and typed-entry
  options, and `rename` changes your name anytime -- no roster, no
  consequences (namegen.py, game_state.py).
- **The `debug` command** -- one player-facing command consolidates ROM's
  immortal staff kit: stat, goto, load, purge, restore, slay, advance, set,
  mwhere/owhere, vnum, flag, force, spellup, clone, mobprog inspection
  (pstat/pdump + live fire trace), plus holylight (imm sight with vnum
  overlay, as upstream) (debug.py).
- **Gquests just happen** -- auto-scheduled and auto-joined with a level band
  clamped to always include you; no 3-minute join window, no "not enough
  people" cancel (DESIGN.md "Gquest joining").
- **PvP machinery gone** -- killer/thief flags, kill-stealing guards, arena and
  war handling, outlaw punishment specs, pkill stats: none of it exists.
- **Comm channels collapsed** -- `tell` is room-local (`yell` keeps its
  upstream area scope); gossip, shout, auction, and the comm-flag toggles
  (QUIET/DEAF/NOTELL) aren't ported.
- **`play loud` sings to you anywhere** -- the mud-wide MUSIC channel
  collapses to the solo player: loud jukebox songs follow you from room to
  room, non-loud ones stay with the jukebox (music.py).
- **Quest anti-theft dropped** -- quest tokens carry no owner tag; nobody else
  could steal them (quest.py).
- **Trivia spends trimmed** -- `tpspend` omits corpse retrieval, TP transfer,
  pretitle, and the PK flag; the rest of the trivia economy is faithful.
- **Solo banking** -- banked gold, shares, and the fluctuating market remain;
  player transfers and clan-bank branches are removed (economy.py).
- **Tutorial-ready purse** -- new players start with 100 silver alongside
  1stMud's 10 gold, enough to follow the Mud School acolyte's donation lesson.
- **One personal estate** -- buy the stock Player Estates home, rename and
  describe it, recall there, and decorate it with persistent floor items;
  runtime OLC rooms and multiplayer ownership are unnecessary (DESIGN.md).

## Built for the calculator

320x240 screen, 64-column text, tiny heap, ~20ms file operations, no floats
worth trusting -- the engineering layer.

- **Generated Python area files** -- areas ship as offline-converted Python
  source, not runtime-parsed `.are` text (DESIGN.md "Area files",
  docs/AREA_FILES.md).
- **Lazy world loading** -- the full stock QuickMUD world ships, but an
  area's rooms/mobs/objects load only on first touch;
  static metadata tables let `areas` and `where` answer with zero loads, and
  `run` route to a destination with zero loads (border graph), areas loading
  lazily as the run walks into them (DESIGN.md "Lazy area loading").
- **Bounded world paths** -- `path <area or mob>` reports a speedwalk without
  moving; mob lookup uses the off-heap index and exact live room, while route
  search Dijkstras a precomputed border graph (`paths.idx`) for exact
  shortest routes with zero area loads at routing time (DESIGN.md "Lazy
  area loading").  Mob targets resolve deterministically -- 1stMud's random
  saving-throw gate is dropped (docs/FIXES.md).
- **World-wide object location** -- `locate object` searches plausible
  unloaded areas one at a time through the object index, then releases each
  transient load (DESIGN.md "Lazy area loading").
- **Far-area eviction** -- when more than a dozen areas are loaded, the
  least-recently-visited are unloaded again, buffering mob positions and
  floor items exactly like a save; areas holding your pet, followers, or
  combatants are never evicted (DESIGN.md "Far-area eviction").
- **Minimal item instances** -- an object instance carries only its vnum and
  the fields that have diverged; everything else reads through to the
  template, and saves serialize just the divergent fields as compact tokens
  -- the core memory/save-size strategy (item.py).
- **Save system** -- autosave to the calculator's HVar store every ~2 minutes
  and after every kill; compact line format; saved deltas for unloaded areas
  are buffered and replayed when the area loads; `backup` writes a manual
  second slot, restored by renaming the file in the calculator's file
  manager (game_state.py, world.py).
- **Keypad UX** -- D-pad keys move directly, digit/decimal keys plus two
  function-key rows (x^y..log, x2..comma) are rebindable command macros,
  Symb/Help step command history, Shift-minus or a touch swipe opens a 250-row
  scrollback, and a persistent status bar shows hp/mana/xp plus the live input
  buffer (docs/PRIME_UX.md).
- **Session clock in place of a battery gauge** -- the Prime exposes no battery
  level to PPL or Python, so `time` reports how long the current sitting has
  run and an hourly notice announces it unprompted (update.py, info.py).
- **Firmware workarounds** -- a hand-rolled key queue drains the 4-deep GETKEY
  FIFO around a keystroke-swallowing firmware race; the terminal subclass
  rebuilds inherited dict attributes the G2 firmware corrupts (tml_prime.py).
- **File I/O discipline** -- help lookups seek into a prebuilt index instead of
  reading 150KB of help text; socials live off-heap in an indexed file
  (info.py, socials.py).
- **Drift-free counters** -- room light and per-template object counts are
  recomputed on demand instead of incrementally maintained, so the many
  extraction paths can't desync them into the save (DESIGN.md).
- **Integer-only math** -- weather simulation and the remort `lvl_bonus`
  formula are exact integer reimplementations of upstream float code.

## Balance and quality of life

Deliberate gameplay tweaks; each is a settled decision in DESIGN.md or a
`[PRIMESUD]`-tagged site.

- **Kinder start** -- 50 hp at creation (stock: 20; mana/move stay at the
  stock 100); flat 1000 XP per level replaces the creation-point-scaled
  curve.
- **No movement lag** -- plain walking never triggers the `[Recovering...]`
  gate; move as fast as you can type, and `run` advances every pulse
  (skill/combat lag unchanged).
- **Level-up heals** -- gaining a level fully restores hp/mana/move; no more
  "levelled at 1 HP mid-fight".
- **Remort power knob** -- the stock remort grant (~6000 hp) is divided by
  `REMORT_POWER_DIV` (default 12, ~500 hp); set 1 for stock (config.py).
- **Remort kindness floors** -- the weapon-40%/recall-50% floors are applied
  *after* the skill reset, so they survive it (upstream's ordering wipes
  them back to 1%).
- **Death is a setback, not a robbery** -- you respawn at the starting room
  with 1 hp and all your gear after a short narration; no corpse run, no XP
  penalty (docs/PRIME_UX.md "Auto-respawn on death").
- **Forgiving quest targets** -- kill/find/deliver quests match any live
  instance of the target template, surviving resets and reloads, instead of
  tracking one specific spawn (quest.py).
- **Faster pulses** -- combat rounds and regen ticks come quicker, mob wander
  slower (DESIGN.md "Pulse timing").
- **Every class can remort in town** -- Paladin shares the Cleric guilds,
  Ranger and Swordsman share the Warrior's, and all four Midgaard guildmasters can `gain`
  (DESIGN.md "Guild rooms").
- **Swordsman / Sword Saint** -- a PrimeSUD-only single-sword duelist with
  flowing form, passive riposte, driving form, and tone-matched cosmetic
  combat flourishes (DESIGN.md "Swordsman / Sword Saint").
- **Combat flow** -- after a kill you auto-retarget a mob already fighting
  you; fleeing auto-looks at the destination; backstab without ranks refuses
  instead of burning a lagged round.
- **Floor lights illuminate** -- a dropped torch or conjured light ball lights
  the room; stock ROM only counts worn lights (DESIGN.md "Room light
  counter").
- **No hunger or thirst** -- condition tracking isn't implemented; conjured
  food decays after a day so it doesn't pile up instead.
- **Per-word spell abbreviation** -- `cast`, `practice`, and `train` match
  skill names word by word (`c 'cu li'`, even `c 'c l w'`, finds cure light
  wounds); upstream only prefix-matches the whole string (skill_utils.py).

## Upstream bugs fixed

docs/FIXES.md carries full write-ups (upstream code excerpts and all) of the
1stMud/ROM bugs PrimeSUD corrects. Highlights:

- The +/-50% damage variance roll upstream computes and then discards.
- Seven attack spells rolling `(level | 50)` -- bitwise OR, a typo for `+` --
  flattening their damage across all 50 levels.
- Ventriloquate, a complete no-op upstream thanks to an inverted name check.
- Non-weapons in the offhand slot rolling their raw value fields as damage
  dice (a container could hit for thousands).
- Autoloot targeting the *oldest* corpse in the room, not your fresh kill.
- `do_wake` standing the waker instead of the sleeper (ROM 2.4).
- The pick-lock lag exploit: skill roll and lag applied before checking the
  door exists (movement.py).
- Silver-only mobs dropping no coins (`gold > 0` gate) (combat.py).
- Remort zeroing the skills of a player who *kept* their race (inverted
  `stay_race` condition).

## Deliberately not ported

Recorded decisions, not gaps (DESIGN.md "Not ported" has the reasons):

- Immortals, clans, arenas, player-killing -- multiplayer by definition.
- Creation points -- no chargen point budgeting; groups/skills come from
  class defaults plus `gain`.
- Stat rolling -- stats come from the race table (plus prime-stat bonus).
- Hunger/thirst, alignment deities, age tracking (no real-time clock).
- Saving-throw race/class/equipment modifiers -- flat 0 baseline for now.
- Furniture mechanics -- no usable stock furniture content; the sole nonzero
  tuple belongs to mis-typed wearable red dragon claws with no position flags.
- Item condition/wear -- retained as source metadata, but not modeled at
  runtime; 1stMud itself does not copy template condition to spawned objects.
