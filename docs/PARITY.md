# 1stMud Parity Sweep (engine 1.0 gate)

Audit of 2026-07-19: does PrimeSUD port everything it should from 1stMud 4.5.3
(all systems and mechanics except multiplayer-only ones)? Method: mechanical
command-table diff, then per-C-file system audits (10 subagent reports,
headline claims spot-checked against source). This doc is the release-gate
checklist for the engine 1.0 parity tag; strike items as they are resolved.

## Command parity

All 348 `commands.dat` commands are accounted for in `src/commands.py`
(133 active since the 19/07/2026 `rename` port, 215 commented with
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

| cmd | effort | evidence | value |
|---|---|---|---|
| socials | S | act_info.c:618 | list social names; socials.idx already sorted |
| sshow | S | act_info.c:640 | preview one social; pairs with socials |
| brief | S | act_info.c:853 | room-desc suppression; movement.py:262 admits gap; help.txt documents it |
| compact | S | act_info.c:860 | blank-line toggle; info.py:128 TODO already exists |
| title | S | act_info.c:3516 | score title; info.py:853 admits gap |
| show | S | act_info.c:866 | score appends affects (COMM_SHOW_AFFECTS) |
| version | S | act_info.c:3898 | no build string exists anywhere; debugging value |
| play | S | music.c:156-230 | Midgaard bar jukebox (midgaard.are:2375) ships today but is inert; info.py:1822 TODO. Channel half stays excluded |
| heel | S | act_enter.c:281 | call pet to room; pet system exists |
| genname | S | namegen.c:162 | ~~random name toy~~ superseded 19/07/2026: namegen.py ported, surfaced via chargen picker + `rename` (G10); list-60-names command itself not wanted |
| backup | S | act_comm.c:995 | manual second save slot; safety net for single flash save file |
| prime | S | multiclass.c:695 | mortal multiclass command mis-swept as imm: prime_class getter exists (classes.py:120), slot forced 0, no setter command. Real gap in shipped multiclass system |
| grlist | S | skills.c:1051 | read-only skill-group listing |
| slist | M | skills.c:956 | class x level skill reference table; multiclass planning value |
| path | M | act_enter.c:416 | route to mob/area; reuse hunt.py:50-92 BFS; pairs with automap |
| index | M | act_info.c:2672 | help category index; needs category metadata in help.txt + build_help_idx.py |
| mobdeaths / mobkills | M | act_info.c:3909-4020 | solo bestiary stats; needs per-template counters. NB upstream naming inverted (fight.c:1941/1968: area->kills = PC deaths) |
| areadeaths / areakills | M | act_info.c:4139-4251 | per-area tallies; same new-counter plumbing |
| bank / balance | L | economy.c:36-140 | shares minigame; TODO.md already defers. Stock lore (midgaard.are vnum 3140 liquidation notice) says bank defunct + no death-gold-loss, so solo value dubious — lean drop |

### Debug-toolkit candidates (imm commands with solo debug value)

| cmd | evidence | gap it fills |
|---|---|---|
| vnum | act_wiz.c:988 | name->vnum lookup world-wide (debug load needs known vnum; debug stat is in-room only) |
| flag | flags.c:35 | toggle bit-flags on live instance; debug set only does scalars |
| force | act_wiz.c:2720 | make any char run a command; test receiving side of skills/AI |
| switch/return | act_wiz.c:1609,1680 | puppet an NPC; test mob-only paths, speech triggers |
| spellup | act_wiz.c:3238 | instant full-buff test state (autobuff deferred) |
| clone | act_wiz.c:1742 | duplicate live instance with current state (minor) |
| programs | programs.c:2315 | mobprog trigger-fired visibility; lightweight equivalent, not 1:1 |

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
27/30 mob commands — 3 MP-only stubs, 33/56 ifchecks — all unimplemented
ones unused by any shipped content and recognized as vocabulary so they
no-op rather than abort).

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
- commands.py: imm band comment reworded (ordinal band, #203 `prime` is
  mortal).

### Closed questions (verified, no action)

- Mob `random` level-variance field: zero nonzero values in all stock
  areas; converter drop has no impact.
- Upstream stock areas contain no mobprogs (school.are's are [PRIMESUD]
  demo additions); midgaard has 1 objprog + 1 roomprog, both in the
  documented obj/room-prog exclusion.
- missing.c is libc portability shims; zero game logic.
- hunt_victim mob-chase AI is inert upstream too — not a gap.
- economy.c contains no dynamic shop-pricing simulation; no shop parity
  gap implied.
