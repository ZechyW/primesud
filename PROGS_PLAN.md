# PROGS_PLAN -- full mobprog/objprog/roomprog engine

Goal: full 1stMud 4.5.3 prog parity -- obj/room prog engines with ALL
triggers, commands, and ifchecks (not vocabulary no-ops), plus completion of
the mobprog engine (23 remaining ifchecks, 3 stubbed group/mass mp-commands)
-- so future custom areas can use full prog functionality without engine
changes. Decision 2026-07-20 (supersedes the earlier engine-wide obj/room
prog exclusion; PARITY.md port-candidate row).

Delete this document when all phases land (durable decisions harvest into
DESIGN.md first, per CLAUDE.md).

## Upstream surface (verified against 1stMud source, 2026-07-20)

Trigger sets (tables.c:514-600):

| origin | triggers |
|---|---|
| mob (16, all ported) | act bribe death entry fight give greet grall kill hpcnt random speech exit exall delay surr |
| obj (12) | act fight give greet grall random speech exall delay drop get sit |
| room (9) | act fight drop greet grall random speech exall delay |

Interpreter (programs.c): `program_flow` is tri-modal -- exactly one of
(mob, obj, room) non-NULL. Separate `cmd_eval_mob/_obj/_room` (421/762/1101)
and `expand_arg_mob`/`expand_arg_other` (1433/1664). Obj/room progs may ONLY
issue `obj <cmd>` / `room <cmd>` lines; a raw command line in a non-mobprog
is a bug() skip (programs.c:2782-2828).

Command tables (prog_cmds.c:77-130):

- obj_cmd_table (24): gecho zecho echo echoaround echoat mload oload purge
  goto transfer gtransfer otransfer force gforce vforce damage remember
  forget delay cancel call remove attrib peace
- room_cmd_table (23): asound gecho zecho echo echoaround echoat mload oload
  purge transfer gtransfer otransfer force gforce vforce damage remember
  forget delay cancel call remove peace

Area format (1stMud): obj trailer `O <trig> <progvnum> <phrase>~` inside
#OBJECTS (db2.c:422-440); room trailer `R <trig> <progvnum> <phrase>~` inside
#ROOMS (db.c:1018-1036); code sections `#OBJPROGS`/`#ROOMPROGS`, same shape
as #MOBPROGS (db2.c:1163-1244).

Fire sites to mirror:

| trigger | upstream site | PrimeSUD seam |
|---|---|---|
| get/drop (obj+room) | act_obj.c:166-168, 582-613 | inventory.py get/drop |
| give (obj; room call exists but rprog set lacks "give" -- unreachable, mirror anyway) | act_obj.c:852-857 | inventory.py give |
| sit (obj) | act_move.c:1043-1440 | movement.py sit/rest/sleep/stand-on-furniture seams that exist |
| exit/exall (all 3) | act_move.c:57-59, programs.c:2965 | movement.py move_char |
| greet/grall (all 3) | programs.c:3154-3212; fired from act_move.c:263-265, act_enter.c:209-211, prog transfers | movement.py:314/558 + _mp/_op/_rp transfer/goto |
| speech (mob, objs in room, objs carried, room) | act_comm.c:381-400 | comm.py do_say |
| act (obj/room recipients) | comm.c:2042-2071 | handler.py act(), MOBtrigger latch |
| fight + hpcnt (mob, then char's objs, then room -- keep order) | fight.c:94-111 | combat.py violence round |
| random/delay (obj) | update.c:827-834 | obj tick loop |
| random/delay (room) | db.c:1380-1387 | area/tick loop |

Shipped content: the original 1stMud->ROM-format hand-conversion of
areas/*.are DROPPED all obj/room prog data. Exactly two progs exist in stock
1stMud areas, both midgaard: obj 3005 `O DROP 100` ("Don't drop me!"), room
3054 `R GRALL 100` (sanctuary echo). Re-add to areas/midgaard.are in Phase 0.

## Mobprog completion gaps (mobprog.py, current)

23 unimplemented ifchecks (KNOWN_CHECKS accepted, evaluate False + dbg):
order, isimmort, off, imm, carries, wears, has, uses, clan, race, class,
objtype, objval0-4, grpsize, onquest, hunter, plr, skill, weight.

- All get real implementations except: clan (no clan system), hunter
  (dead-wired upstream -- nothing ever sets `->hunting`), plr (no
  player-flag system) -- these evaluate False *faithfully*, with comments.
- objval0-4 needs a reverse mapping: PrimeSUD stores typed fields (weapon
  dice, container caps, ...) not raw value[]. Add an accessor in item.py
  mirroring tools/are_to_primesud.py's per-type field mapping.

3 stubbed mp-commands (_mp_skip): gtransfer, gforce, vforce. All
solo-meaningful (group = player + pets/charmies; vforce = all mobs of a
vnum) -- implement per prog_cmds.c.

## Phases (each independently shippable; tests + `python -m pytest -q` + `python tools/check_ascii_py.py` per phase)

### Phase 0 -- data pipeline (completed 20/07/2026; no behaviour change)

- tools/are_to_primesud.py: parse `#OBJPROGS`/`#ROOMPROGS` sections, `O`
  trailer in #OBJECTS, `R` trailer in #ROOMS -- [PRIMESUD] dialect
  extensions to the QuickMUD format (precedent: repeated-G room trailer).
  Validate trigger words against the obj/room sets above (invalid ->
  hard error, cf. db2.c exit(1)). Emit OBJPROGS/ROOMPROGS dicts +
  per-obj `obj_triggers` / per-room `room_triggers` tuples (same shape as
  `mob_triggers`).
- world.py: OBJPROGS/ROOMPROGS globals -- load/evict/clear mirroring
  MOBPROGS (world.py:865, 491, 797, 891).
- areas/midgaard.are: re-add the two progs; regen via tools/regen_areas.sh
  path (converter + mobs.idx + ascii check).
- docs/AREA_FILES.md: document the dialect.

### Phase 1 -- interpreter tri-mode (completed 20/07/2026)

- mobprog.py program_flow/cmd_eval/expand_arg grow (mob|obj|room) origin
  exactly as programs.c: cmd_eval_obj/_room subsets, expand_arg_other
  $-code semantics, `obj`/`room` line keywords; raw command lines in
  obj/room progs bug-skip per upstream.
- obj_interpret/room_interpret + op/rp command tables. Share logic with
  existing _mp_* helpers where identical, parameterized by (origin room,
  display name); obj-only attrib, room-only asound, obj goto.
- State on instances: `oprog_delay`/`oprog_target` on obj dicts,
  `rprog_delay`/`rprog_target` on runtime room dicts. Transient by design
  -- save surface is player-only, world rebuilds each boot.

### Phase 2 -- fire seams

Hook every row of the fire-site table. Preserve upstream firing ORDER
(e.g. fight: mob prog, then objs, then room; exit before greet on move).
act() extension honours the MOBtrigger latch for obj/room recipients.

### Phase 3 -- mobprog completion (tri-mode aware)

- 23 ifchecks per gap list; each lands in the right cmd_eval_* subset(s).
- gtransfer/gforce/vforce.

### Phase 4 -- debug toolkit + docs

- debug pstat/pdump/prog channel cover obj/room progs (revisit note in
  PARITY.md programs rationale).
- PARITY.md: strike port-candidate row; fix programs-subcommand rationale
  bullet. DESIGN.md: obj/room-prog exclusion row removed/updated.
  FEATURES.md: one-liner (area-authoring surface). mobprog.py module
  docstring "obj/room progs are out of scope" updated.

## Risks

- mobprog.py size on-device: already ~1900 lines, tri-mode adds ~700. If
  heap/bytecode pressure shows on hardware, split op/rp command tables into
  a lazily-imported sibling module (same deferred-import pattern as the
  existing `from mobprog import ...` seams).
- Furniture-sit seam may not be fully ported; TRIG_SIT hooks only the seams
  that exist, with a comment naming the upstream sites.
