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
- **Autoskill combat automation** -- `autoskill` fires one offensive debuff,
  spell, or skill per combat round through the normal handlers at full
  mana/lag/fizzle cost; rotation is player-editable via a navpad-driven
  blocking editor (`autoskill edit`). Survival (heal, quaff, flee) stays
  manual (autoskill.py; DESIGN.md "Autoskill combat automation").

## Reimagined for one player

There are no other players, no immortals, no clans -- and the design turns
that into features rather than holes.

- **Pickers replace typing** -- `kill`, `get`, `wear`, `cast`, `practice`,
  `train`, `examine`, `open`/`unlock`, remort, chargen: given no argument,
  each opens a numbered target menu instead of failing (docs/PRIME_UX.md).
- **Name picker and free rename** -- chargen offers six generated fantasy
  names (1stMud's namegen syllable pools) with reroll and typed-entry
  options, and `rename` changes your name anytime -- no roster, no
  consequences (namegen.py, game_state.py).
- **The `debug` command** -- one player-facing command consolidates ROM's
  immortal staff kit: stat, goto, load, purge, restore, slay, advance, set,
  mwhere/owhere, find, flag, force, spellup, clone, mobprog inspection
  (pstat/pdump + live fire trace), plus holylight and vnum-display toggles
  (debug.py).
- **Gquests just happen** -- auto-scheduled and auto-joined with a level band
  clamped to always include you; no 3-minute join window, no "not enough
  people" cancel (DESIGN.md "Gquest joining").
- **PvP machinery gone** -- killer/thief flags, kill-stealing guards, arena and
  war handling, outlaw punishment specs, pkill stats: none of it exists.
- **Comm channels collapsed** -- `tell` is room-local (`yell` keeps its
  upstream area scope); gossip, shout, auction, and the comm-flag toggles
  (QUIET/DEAF/NOTELL) aren't ported.
- **Quest anti-theft dropped** -- quest tokens carry no owner tag; nobody else
  could steal them (quest.py).
- **Trivia spends trimmed** -- `tpspend` omits corpse retrieval, TP transfer,
  pretitle, and the PK flag; the rest of the trivia economy is faithful.

## Built for the calculator

320x240 screen, 64-column text, tiny heap, ~20ms file operations, no floats
worth trusting -- the engineering layer.

- **Generated Python area files** -- areas ship as offline-converted Python
  source, not runtime-parsed `.are` text (DESIGN.md "Area files",
  docs/AREA_FILES.md).
- **Lazy world loading** -- the full stock QuickMUD world ships (48 areas,
  3124 rooms), but an area's rooms/mobs/objects load only on first touch;
  static metadata tables let `areas` and `where` answer with zero loads, and
  `run` pick a destination without loading, then load only the areas along
  the path (DESIGN.md "Lazy area loading").
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
  are buffered and replayed when the area loads (game_state.py, world.py).
- **Keypad UX** -- D-pad keys move directly, digit keys plus two function-key
  rows (sin..log, x2..comma) are rebindable command macros, Symb/Help step
  command history, Shift-minus or a touch swipe opens
  a 250-row scrollback, and a persistent status bar shows hp/mana/xp plus the
  live input buffer (docs/PRIME_UX.md).
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
  Ranger shares the Warrior's, and all four Midgaard guildmasters can `gain`
  (DESIGN.md "Guild rooms").
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
- Furniture mechanics -- every furniture object in stock content has all-zero
  values; nothing to sit on yet.
- Object and room mobprogs -- mob progs only; no stock content uses the rest.
- Item condition/wear -- parsed by the converter, unmodeled at runtime.
