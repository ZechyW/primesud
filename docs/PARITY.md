# 1stMud Parity Sweep (engine 1.0 gate)

Audit of 2026-07-19: does PrimeSUD port everything it should from 1stMud 4.5.3
(all systems and mechanics except multiplayer-only ones)? Method: mechanical
command-table diff, then per-C-file system audits (10 subagent reports,
headline claims spot-checked against source). This doc is the release-gate
checklist for the engine 1.0 parity tag; strike items as they are resolved.

## Command parity

All 348 `commands.dat` commands are accounted for in `src/commands.py`
(147 active since the 20/07/2026 parity ports below, 201 commented with
reasons); PrimeSUD-only additions are
`autoskill`, `debug`, `macro` (all `[PRIMESUD]`). Nothing was forgotten;
the only risk class is *wrong* exclusions, audited below.

### Confirmed excluded (no action)

- **Multiplayer comms/social**: gossip(`.`), gtell(`;`), immtalk(`:`), afk,
  answer, barter, board/note/unread/subscribe, btalk, buddy, censor,
  channels, clantalk, count, deaf, description, donate, grats, gossip,
  ignore, info, music (channel half), nogocial, nosayverbs, nofollow,
  noloot, nosummon, ooc, pmote, question, quiet, quote, replay, report,
  shout, smote, sooc, split, think, timezone, whisper, who, whois, whowas,
  wizlist, worship (deity system unported, DESIGN.md). Several have
  prior-art drop reasoning in code (magic.py nosummon, quest.py pretitles).
- **Clan/PK family**: cinfo, claninfo, clanlist, clanrecall, clanadmin,
  clist, join, promote, roster, pk, pkshow, guild, tax — no clan system.
- **MP systems**: arena, auction, bid, war, rent (literal "no rent" stub),
  bug (writes report for nonexistent staff), qpgive, tpgive, home
  (needs runtime OLC room creation; architecturally blocked), donate.
- **Client/network infra**: client, color, colour, compress, imp, msp, mxp,
  portal, pueblo, password, screen, strkey, sendstats, webpass.
- **Server admin/moderation** (imm): allow, ban, announce, bonus, copyover,
  crash, deny, disable, disconnect, echo/gecho/pecho/zecho, freeze, log,
  newlock, nochannels, noemote, noshout, notell, pardon, pload/punload,
  poofin/poofout, prefix, protect, reboot, rename, shutdown, snoop,
  sockets, system, teleport, transfer, trust, violate, wizinvis, wizlock,
  wiznet, imotd, incognito, invis, changes, wizhelp.
- **OLC editors** (static data pipeline supersedes): aedit, alist, areaset,
  asave, avedam, cedit, chanedit, cledit, cmdcheck, cmdedit, coledit,
  dedit, edit, gredit, hedit, helpcheck, medit, mpedit, mudedit, oedit,
  opedit, raedit, redit, resets, rpedit, sedit, skcheck, skedit, songedit.
- **Already in debug toolkit**: advance, at*, goto, holylight, load, memory,
  mwhere, owhere, peace, purge, restore, set, slay, stat (\*`at` covered by
  two `debug goto` calls).
- **Resolved unclear**: autoprompt (status bar supersedes, info.py:126),
  combine (combined display already hardcoded, close info.py:131 TODO),
  delete (calculator file manager covers it), ring (no doorbell exit data
  in any ported area), story (no stock help entry — original-content
  decision, not a port), prompt/gprompt (status bar supersedes — close
  info.py:129-130 TODOs as superseded, mirroring autoprompt), typo
  (staff-report mechanism; note-to-self repurpose would be a new
  [PRIMESUD] feature, not parity), mob (raw mobprog injection; engine
  covered by test_mobprog.py), showstats (needs new stat tracking; see
  mobdeaths/mobkills candidate).

### Port-candidates (player-facing; need go/no-go)

All 12 S-effort rows resolved 20/07/2026 (commits `58e****`..`193****`):
**socials, sshow, brief, compact, title, show, version, play, heel,
backup, prime, grlist** ported per the evidence rows below (genname had
already resolved 19/07/2026 via the chargen picker + `rename`). Notable
adaptations, all `[PRIMESUD]`-commented at the code sites: `play loud`
collapses the mud-wide MUSIC channel to always-echo-to-the-solo-player
(music.py; music.dat ported verbatim to src/music.txt + seek-index);
`compact` flips its flag only (status-bar prompt has no blank-line seam);
brief/compact/show COMM_ bits share the persisted player flags int;
`backup` restore = rename primesud_backup.sav via the calculator file
manager (upstream has no player restore either); `prime`'s level-51 gate
is an explicit message (no per-command level field). Follow-up resolved
20/07/2026: all `do_look` call sites now pass "auto" where upstream does
(stand, recall, gate, debug goto, boot look), plus the [PRIMESUD]
flee-look for brief-mode consistency (commits 4b4****, 65d****, 7cb****).

`path` ported 20/07/2026 with intent parity for the upstream inverted mob
condition: area-first lookup, gate-style mob restrictions, live-room targets,
and `mobs.idx` fallback. Its room BFS is [PRIMESUD]-bounded to one lazily
loaded area corridor with no load-all fallback, followed by forced cache
eviction (path.py).

`slist` ported 20/07/2026: class views retain the upstream level-grouped,
two-column layout; skill/spell views show all six classes across two lines
to fit the Prime's 64-column screen.

Remaining open candidates:

| cmd | effort | evidence | value |
|---|---|---|---|
| index | M | act_info.c:2672 | help category index; needs category metadata in help.txt + build_help_idx.py |
| mobdeaths / mobkills | M | act_info.c:3909-4020 | solo bestiary stats; needs per-template counters. NB upstream naming inverted (fight.c:1941/1968: area->kills = PC deaths) |
| areadeaths / areakills | M | act_info.c:4139-4251 | per-area tallies; same new-counter plumbing |
| objprog/roomprog engine | L | programs.c; db2.c #OBJPROGS/#ROOMPROGS | reopened 20/07/2026 (was closed as excluded); scope upgraded same day to FULL engine (user decision): all obj/room triggers (12/9), op/rp command tables (24/23), cmd_eval_obj/_room ifcheck subsets, plus mobprog completion (23 remaining ifchecks, gtransfer/gforce/vforce). Phase 0 completed 20/07/2026: converter/world data plumbing and the 2 originally dropped Midgaard progs restored (obj 3005 `O DROP 100`, room 3054 `R GRALL 100`); no behavior yet. Phased plan: PROGS_PLAN.md |
| bank / balance | L | economy.c:36-140 | shares minigame; TODO.md already defers. Stock lore (midgaard.are vnum 3140 liquidation notice) says bank defunct + no death-gold-loss, so solo value dubious — lean drop |
| locate object: unloaded areas | M | magic.c:3523 (obj_first is world-global) | spell_locate_object scans loaded areas only (noted in its docstring 20/07/2026). objs.idx could name areas whose templates match, but live floor/carried state of unloaded areas sits in pending-save buffers — needs design before porting |

### Debug-toolkit candidates (imm commands with solo debug value)

All resolved 20/07/2026 as `debug` subcommands (debug.py):

| cmd | evidence | resolution (20/07/2026) |
|---|---|---|
| vnum | act_wiz.c:988 | PORTED as `debug vnum [mob\|obj] <name>` (the old vnum display channel folded into holylight, matching upstream's PLR_HOLYLIGHT room-vnum gate, act_info.c:1136; mob/obj vnum overlay kept as [PRIMESUD] superset). Loaded areas answer from defs in memory; unloaded areas via keyword indices (mobs.idx + new objs.idx, built by tools/build_mob_index.py) -- no area load forced. Skill branch (do_slookup) N/A: skills are name-keyed |
| flag | flags.c:35 | PORTED as `debug flag`; dict-key bits, +/-/=/toggle as upstream; plr/comm fields N/A (no player-flag/comm systems); no flag-name table at runtime, so result set is echoed instead of validated |
| force | act_wiz.c:2720 | PORTED as `debug force <char> <cmd>`; all/players/gods sweeps + trust gates N/A solo |
| switch/return | act_wiz.c:1609,1680 | CLOSED covered-by-force: upstream switch swaps the descriptor into the mob to issue commands as it; PrimeSUD has no descriptor layer and the whole command surface assumes the player dict. `debug force <mob> <cmd>` gives the same test lever (mob's own say doesn't fire speech triggers upstream either -- NPC gate) |
| spellup | act_wiz.c:3238 | PORTED as `debug spellup [<char>]` (default self); full 14-spell qspell_table at MAX_LEVEL; all/room variants N/A solo |
| clone | act_wiz.c:1742 | PORTED as `debug clone <name>`; deep-copies the live instance dict (contents clone along, cf. recursive_clone); obj_check trust gates N/A solo |
| programs | programs.c:2315 | PORTED lightweight: `debug pstat` (trigger listing), `debug pdump` (prog source), `debug prog` channel (live fire trace). trace/reset/info not 1:1 -- see below |

`programs` deliberately not 1:1 (three of five subcommands service infra
PrimeSUD doesn't have, by design):

- `trace`: a 500-entry timestamped ring buffer, valuable on a multiplayer
  server where progs fire from other players' actions while the imm is
  elsewhere. Solo, every prog fires from the player's own action in the
  player's room -- the `debug prog` channel prints the same fact live, with
  zero retained heap and no wall-clock source (no utime on-device).
- `reset`: exists because 1stMud's global C callstack can wedge after a
  mid-prog longjmp/crash. mobprog.py decrements `_call_depth` in a
  try/finally, so it cannot wedge -- nothing to reset.
- `info`: abort history + the buggy_prog disable machinery (persist a
  forensic text, keep the prog disabled) that protects a 24/7 server from
  a buggy prog re-firing forever. PrimeSUD aborts print via dbg() at the
  moment they happen and the fix is editing the area file; the disable
  state would be dead weight.
- Obj/room progs were excluded engine-wide at audit time (reopened
  20/07/2026 as a port-candidate; revisit pstat/pdump coverage if that
  lands), so 2/3 of every 1:1 listing loop would have been N/A.

## Systems parity

### Verified clean (value-level where applicable)

Race/class/attr-apply/group/movement-loss/attack/weapon tables match
byte-for-byte in all sampled rows (races.py, classes.py, config.py,
groups.py, skills_table.py). Core handler mechanics (affects, check_immune,
carry caps, visibility, equip/unequip + align zap, extract/raw_kill),
chargen pipeline, full save surface (incl. nested containers, pets, quest
state, RLE explored map), reset engine M/O/P/E/G/R incl. limit decoding,
create_mobile stat/wealth rolls, weather engine, effects (acid/fire/cold/
poison/shock), obj decay/corpse spill, aggr_update, spec_funs (25/26;
spec_warmaster N/A — its only user is the unshipped war PK area), hunt
(incl. dormant-upstream hunt_victim), mobprog engine (16/16 triggers,
27/30 mob commands, 33/56 ifchecks — all unimplemented ones unused by any
shipped content and recognized as vocabulary so they no-op rather than
abort; the 3 stubbed commands (gtransfer/gforce/vforce) are solo-meaningful
after all — completion scoped in PROGS_PLAN.md).

### Confirmed gaps (fidelity; spot-checked against source)

All resolved or closed 19/07/2026:

| # | gap | evidence | resolution (19/07/2026) |
|---|---|---|---|
| G1 | Two-hand weapon / shield mutual exclusion missing | act_obj.c:1589-1637 | FIXED: wear/wield/shield checks in inventory.py wear_obj, incl. shield-vs-dual-wield direction |
| G2 | Regen position gate missing; incap/mortal bleed-out missing | update.c:538,739-746 | FIXED: tick_update gates regen at >= stunned; bleed-out ported (player.py) |
| G3 | Poison/plague periodic tick damage + plague room contagion missing | update.c:670-746 | FIXED: _char_disease_tick in player.py, exact else-if chain; mob<->player contagion live |
| G4 | Sunset off-by-one: SUN_SET at hour 18, upstream 19 | weather.c:483 | FIXED: game_time.py hour 19 |
| G5 | Time-of-day echo broadcasts missing | weather.c:413-516 | FIXED: _echo_time_of_day, all variants + colours, outdoors+awake gate |
| G6 | Shopkeeper wealth top-up missing | update.c:435-442 | FIXED: mob.py mobile_update, exact gate + divisors |
| G7 | PLR_OUTLAW unmodeled | special.c:851-969 | CLOSED no-flag (user decision): both set-sites are PvP-only, unreachable solo — DESIGN.md row added; guard/thief non-outlaw halves were already ported; executioner stays inert with corrected comment |
| G8 | spec_fido stub with stale reason | special.c:885-913 | FIXED: eats NPC corpses, spills contents |
| G9 | spec_mayor gate walk + spec_nasty opener not ported | special.c:998-1098, 372-427 | FIXED: full mayor FSM (paths/messages verbatim, latch-before-fight ordering per upstream); nasty backstab/murder opener via victim= param |
| G10 | Chargen name suggestions (nanny.c/namegen.c) never ported | nanny.c:116-190 | FIXED: namegen.py (syllable pools verbatim) + chargen name picker (6 suggestions / reroll / typed entry) + [PRIMESUD] `rename` command (picker when no arg) |
| G11 | checkcorpse login warning missing | save.c:2284-2308 | CLOSED N/A: save surface is player-only (game_state.py _serialize_world), world rebuilds each boot — a player corpse cannot exist at login |
| G12 | Liquid table partial, color dropped, no look-in branch | const.c:332-378 | FIXED: full 36-liquid LIQ_TABLE (item.py) + look-in ITEM_DRINK_CON branch (info.py); conditions stay dropped per DESIGN.md |
| G13 | TRIG_SURR mobprog trigger not ported | fight.c:3639-3661 | FIXED: do_surrender fires "surr" trigger + missing TO_NOTVICT act line |

### Doc/comment fixes (no gameplay change) — all applied 19/07/2026

- DESIGN.md: "Alignment / deity" row split (alignment is live; only deity
  unported); outlaw/crime N/A row added; hunger/thirst row extended with
  eat/drink-as-RP-flavour + LIQ_TABLE note; offline catch-up regen
  (save.c:1176) recorded N/A; mobprog row's stale "except surr" fixed.
- docs/AREA_FILES.md: three stale "not yet implemented" notes fixed
  (shops, socials, mobprogs — all shipped).
- TODO.md: save_objs question closed (player-home floor persistence only,
  homes.c:313 — N/A); `play` re-bucketed out of the MP-only list.
- info.py: prompt/gprompt TODOs closed as superseded (status bar), combine
  TODO closed as moot; compact TODO kept (port-candidate).
- commands.py: imm band comment reworded (ordinal band; `prime` noted as
  mortal -- its ordinal, misrecorded here as #203, was corrected to #317
  when `prime` was ported 20/07/2026).

### Closed questions (verified, no action)

- Mob `random` level-variance field: 1stMud v4-area-format-only
  (db2.c:101-105, gated `version >= 4`); the ROM/QuickMUD format the
  converter ingests has no such field, so future stock-ROM imports cannot
  carry it, and all shipped 1stMud sources have zero values. Converter now
  hard-errors on over-long mob stat lines (20/07/2026) so a hand-converted
  v4 line cannot silently mis-parse. If a v4 area is ever imported, apply
  spawn variance per db.c:1788-1791.
- Upstream stock areas contain no mobprogs (school.are's are [PRIMESUD]
  demo additions); midgaard has 1 objprog + 1 roomprog — obj/room prog
  engine reopened 20/07/2026 as a port-candidate (see table above).
- missing.c is libc portability shims; zero game logic.
- hunt_victim: absent from ROM 2.4/quickmud entirely (no hunt.c, no
  ACT_HUNTER); 1stMud wires calls (fight.c:72, update.c:423) but nothing
  ever sets `->hunting` (NULL assignments only, incl. the programs.c:551
  ifcheck — always false) — dead-wired, cannot fire. PrimeSUD's dormant
  port is faithful; not a gap.
- economy.c contains no dynamic shop-pricing simulation; no shop parity
  gap implied.
