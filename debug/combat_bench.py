"""Combat/input-lag phase benchmark: synthetic, real terminal, real heap. [PRIMESUD]

Companion probe to COMBAT_LAG.md (repo root). Measures the coarse phase
costs that document names as suspects -- status/prompt rendering, room
render via interpret, and combat pulse cost at three shapes (single mob,
busy room, autoskill-on) -- plus update_handler() at three pulse shapes
(violence only, all six periodic pulses aligned on one call, near-idle).
No human input: every scenario drives the same APIs the real game loop
calls, with fixed synthetic timing loops instead of a keyboard/GETKEY poll.

Unlike snapshot_gates.py, this probe does NOT stub terminal.tr: rendering
cost is a prime suspect in the lag investigation, so status/print calls
must hit the real tml_prime blit path. terminal.init_terminal() is called
immediately after `import terminal`, before any other game import, so nothing
prints to an uninitialised terminal.

Setup mirrors save_smoke.py/snapshot_gates.py: copy the REAL primesud.sav
into this debug appdir first (Connectivity Kit) -- it is only read.
SAVE_VAR is redirected to "smoketest" before world.init_world()/load_world()
so create_char()'s reset_lazy and the load never touch the real save slot;
SAVE_FILE is redirected to combat_bench.sav after load_world() so nothing
this probe does (no scenario here calls save_world(), but the redirect is
cheap insurance) can touch the real save file either.

Ship the full game closure (src/*.py + src/*.txt + src/*.idx) EXCEPT
src/primesud.py (its module level launches the game). Only ONE
self-running .py may be in the appdir (Prime auto-imports all): this probe
OR snapshot_gates.py OR save_smoke.py, never more than one at a time.
Results printed and written to combat_bench.log.

Scenarios (run in this order -- typing/status/interpret first so their
numbers are clean-heap; combat scenarios run after and reflect heap churn
from spawned mobs):
  1  boot              -- load_world() timing (like snapshot_gates)
  2  typing_prompt     -- show_prompt() over ~40 type+backspace calls
  3  status_raw        -- terminal.tr.set_status() alone, prefix precomputed
  4  interpret_look     -- commands.interpret("look", player) x5
  5  combat_basic      -- 1 mob, 10 violence_update() rounds
  6  combat_busy       -- 4 mobs vs. player, 10 rounds
  7  combat_autoskill  -- 1 mob, PLR_AUTOSKILL on, 10 rounds; if the loaded
                        save's real rotation has no included entries, SIMULATES
                        one (injects learned pct for 2-3 class/level-eligible
                        candidates, restored after) before giving up (or
                        skip+reason if even the simulated rotation is empty)
  8  pulse_violence_only -- update_handler() x10, only violence pulse due
  9  pulse_aligned     -- update_handler() x3, ALL six pulses due each call
  10 pulse_idle        -- update_handler() x5, only regen due (near no-op)
  11 set_color_ab      -- pixon font repaint vs COLORFONT-band blit, x10
                        each (runs first, right after boot: it repaints the
                        live FONT_GROB and must end with font + colour state
                        back at the defaults before anything else renders)
  12 interpret_look_batched -- scenario 4 with output batched (render-share A/B)
  13 scan_skeleton     -- violence snapshot+scan replica, no combat, x10
  14 combat_basic_batched -- scenario 5 with output batched (render-share A/B)
"""
import gc

import terminal

terminal.init_terminal()

from prime_platform import ticks, hvars_set  # noqa: E402
from hpprime import dimgrob, getpix, grobh, grobw, pixon, strblit2  # noqa: E402
from util import int_str, num_str  # noqa: E402
from config import R_STARTING_ROOM, FONT_GROB, COLOR_GROB  # noqa: E402
from handler import PLR_AUTOSKILL, PLR_DEFAULTS  # noqa: E402
import world  # noqa: E402
import game_state  # noqa: E402
import mobprog  # noqa: E402
from player import create_char, show_prompt  # noqa: E402
import combat  # noqa: E402
import update  # noqa: E402
import commands  # noqa: E402
import autoskill  # noqa: E402

LOG = "combat_bench.log"

_out = []


def log(msg):
    print(msg)
    _out.append(msg)
    try:
        with open(LOG, "w") as f:
            f.write("\n".join(_out) + "\n")
    except Exception:
        pass


def free():
    return gc.mem_free() if hasattr(gc, "mem_free") else 0


def _log_stats(label, n, total, mx, mn, rounds):
    """Log one scenario's aggregate timing, plus a per-round list when
    n <= 12 (kept as a fixed small list per CLAUDE.md pitfall 9, never
    unbounded). [PRIMESUD]"""
    msg = (label + ": n=" + int_str(n) + " total=" + int_str(total)
           + "ms max=" + int_str(mx) + "ms min=" + int_str(mn) + "ms")
    if rounds:
        parts = []
        for r in rounds:
            parts.append(int_str(r))
        msg += " rounds=[" + ",".join(parts) + "]"
    log(msg)


def _timed_rounds(label, n, restore_fn, call_fn):
    """Run call_fn() n times, calling restore_fn() (untimed) before each
    round, and log aggregate + (n<=12) per-round timings. [PRIMESUD]"""
    total = 0
    mx = 0
    mn = 999999999
    keep_rounds = n <= 12
    rounds = [] if keep_rounds else None
    for _ in range(n):
        if restore_fn is not None:
            restore_fn()
        t0 = ticks()
        call_fn()
        dt = ticks() - t0
        total += dt
        if dt > mx:
            mx = dt
        if dt < mn:
            mn = dt
        if keep_rounds:
            rounds.append(dt)
    _log_stats(label, n, total, mx, mn, rounds)


# -- Mob selection ---------------------------------------------------------

def _pick_mob():
    """Pick a low-level mob vnum with no off_flags and no spec_fun ("no
    specials") from whatever areas load_world() already pulled in; falls
    back to loading further areas (like snapshot_gates._pick_item_area)
    if none of those areas define a plain mob. [PRIMESUD]

    Returns:
        int: A mob template vnum, or -1 if the world defines no mobs at all.
    """
    best = -1
    best_level = None
    for v, tpl in world.MOB_DEFS._data.items():
        if tpl.get("spec_fun") or tpl.get("off_flags"):
            continue
        lvl = tpl.get("level", 1)
        if best_level is None or lvl < best_level or (lvl == best_level and v < best):
            best = v
            best_level = lvl
    if best >= 0:
        return best
    for entry in world._AREA_FILES:
        tag = entry[1]
        if tag in world._LOADED_AREAS:
            continue
        world._ensure_area_by_tag(tag)
        for v, tpl in world.MOB_DEFS._data.items():
            if not tpl.get("spec_fun") and not tpl.get("off_flags"):
                return v
    for v in world.MOB_DEFS._data:
        return v
    return -1


# -- Combat engage/restore/disengage ----------------------------------------

def _engage(player, mobs):
    """One-time combat entry (cf. combat.set_fighting side effects: sleep
    strip, stance autodrop, Swordsman form default) for player vs. mobs[0],
    and each mob vs. player. [PRIMESUD]"""
    for m in mobs:
        combat.set_fighting(m, player)
    combat.set_fighting(player, mobs[0])


def _restore_round(player, mobs):
    """Reset hit/wait/daze/pos to full before a timed round, and repair
    fighting links if a previous round's damage killed and extracted a
    combatant. Repair is needed because resetting hit to max_hit happens
    BEFORE violence_update runs each round, but one round can still deal
    more than max_hit in damage (multiple hits, crits) and kill mid-round --
    without this, a scenario could silently stop measuring real combat
    partway through its round count. [PRIMESUD]"""
    room = player["room"]
    room_mobs = world.rooms[room]["mobs"]
    for m in mobs:
        if m["id"] not in world.chars:
            world.chars[m["id"]] = m
        if m["id"] not in room_mobs:
            room_mobs.append(m["id"])
        m["room"] = room
        m["fighting"] = player["id"]
        world.FIGHTERS.add(m["id"])  # [PRIMESUD] direct write -- keep index in sync
        m["pos"] = "fighting"
        m["hit"] = m["max_hit"]
        m["wait"] = 0
        m["daze"] = 0
    player["fighting"] = mobs[0]["id"]
    world.FIGHTERS.add(player["id"])  # [PRIMESUD] direct write -- keep index in sync
    player["pos"] = "fighting"
    player["hit"] = player["max_hit"]
    # Mana/move too: autoskill casts every round, and draining to zero
    # mid-scenario would silently turn later rounds into plain melee
    # (combat_bench-2.log rounds decayed 1225ms -> ~300ms exactly this way).
    player["mana"] = player["max_mana"]
    player["move"] = player["max_move"]
    player["wait"] = 0


def _disengage(player, mobs):
    """Stop combat and extract every spawned mob, leaving the mob harmlessly
    -- same removal path debug.py's _debug_purge uses for NPCs. [PRIMESUD]"""
    if player.get("fighting") is not None:
        combat.stop_fighting(player, both=True)
    for m in mobs:
        if m["id"] in world.chars:
            combat._extract_char(m, pull=True)


# -- Scenarios ---------------------------------------------------------------

AB_GROB = 3  # scratch for set_color_ab's two colour bands (4-9 in use, config.py)


def scenario_set_color_ab():
    """A/B the two set_color paint strategies against the live FONT_GROB:
    (A) the pre-cache pixon per-foreground-pixel repaint loop, (B) one
    native strblit2 from a pre-painted colour band (the COLORFONT_GROB
    approach, using AB_GROB so the live cache is untouched). Replicates
    terminal.install_color_print's own fg-pixel scan. Alternates two
    colours each iteration so neither path can early-out.

    Runs FIRST after boot: it repaints FONT_GROB behind the live
    terminal's back, so it must (and does) end by restoring the default
    font from COLOR_GROB -- at this point in the run nothing coloured has
    printed yet, so the terminal's tracked colour state (None) still
    matches the restored font."""
    font_w = grobw(FONT_GROB)
    font_h = grobh(FONT_GROB)
    cw = terminal.tr.char_width
    _w_x = (ord("W") - 32) * cw + cw // 2
    font_fg = getpix(FONT_GROB, _w_x, terminal.tr.char_height // 2)
    fg_rows = [
        [x for x in range(font_w) if getpix(FONT_GROB, x, y) == font_fg]
        for y in range(font_h)
    ]
    npix = 0
    for xs in fg_rows:
        npix += len(xs)
    log("set_color_ab: font " + int_str(font_w) + "x" + int_str(font_h)
        + " fg_pixels=" + int_str(npix))

    c_a = 0xFF0000  # {R red
    c_b = 0x6495ED  # {B cornflowerblue

    def _repaint(color):
        _po = pixon
        for y, xs in enumerate(fg_rows):
            for x in xs:
                _po(FONT_GROB, x, y, color)

    n = 10
    total = 0
    mx = 0
    mn = 999999999
    for i in range(n):
        color = c_a if i % 2 == 0 else c_b
        t0 = ticks()
        _repaint(color)
        dt = ticks() - t0
        total += dt
        if dt > mx:
            mx = dt
        if dt < mn:
            mn = dt
    _log_stats("set_color_ab(pixon)", n, total, mx, mn, None)

    # Pre-paint the two bands (untimed), like the lazy cache's first use.
    dimgrob(AB_GROB, font_w, font_h * 2, 0)
    _repaint(c_a)
    strblit2(AB_GROB, 0, 0, font_w, font_h, FONT_GROB, 0, 0, font_w, font_h)
    _repaint(c_b)
    strblit2(AB_GROB, 0, font_h, font_w, font_h, FONT_GROB, 0, 0, font_w, font_h)

    total = 0
    mx = 0
    mn = 999999999
    for i in range(n):
        band = i % 2
        t0 = ticks()
        strblit2(FONT_GROB, 0, 0, font_w, font_h,
                 AB_GROB, 0, band * font_h, font_w, font_h)
        dt = ticks() - t0
        total += dt
        if dt > mx:
            mx = dt
        if dt < mn:
            mn = dt
    _log_stats("set_color_ab(blit)", n, total, mx, mn, None)

    # Restore the default-colour font (same blit reset_color uses).
    strblit2(FONT_GROB, 0, 0, font_w, font_h,
             COLOR_GROB, 0, 0, font_w, font_h)


def scenario_typing_prompt(player):
    """show_prompt() over typing then backspacing a fixed string, ~40 calls."""
    text = "flee flee flee flee"
    buf = ""
    total = 0
    mx = 0
    mn = 999999999
    n = 0
    for ch in text:
        buf += ch
        t0 = ticks()
        show_prompt(player, buf)
        dt = ticks() - t0
        total += dt
        if dt > mx:
            mx = dt
        if dt < mn:
            mn = dt
        n += 1
    _log_stats("typing_prompt(type)", n, total, mx, mn, None)

    total = 0
    mx = 0
    mn = 999999999
    n = 0
    while buf:
        buf = buf[:-1]
        t0 = ticks()
        show_prompt(player, buf)
        dt = ticks() - t0
        total += dt
        if dt > mx:
            mx = dt
        if dt < mn:
            mn = dt
        n += 1
    _log_stats("typing_prompt(backspace)", n, total, mx, mn, None)


def scenario_status_raw(player):
    """terminal.tr.set_status() alone, with the prefix built once outside
    the timed loop -- isolates status-render cost from show_prompt's
    per-call prefix concatenation (COMBAT_LAG.md "Per-character prompt
    rendering")."""
    prefix = ("{R" + num_str(player["hit"]) + "/" + num_str(player["max_hit"])
              + "hp {M" + num_str(player["mana"]) + "/" + num_str(player["max_mana"])
              + "mn {B" + num_str(player["move"]) + "/" + num_str(player["max_move"])
              + "mv{x " + num_str(player["xp_next"] - player["xp"]) + "tnl>flee")
    total = 0
    mx = 0
    mn = 999999999
    n = 20
    for _ in range(n):
        t0 = ticks()
        terminal.tr.set_status(prefix)
        dt = ticks() - t0
        total += dt
        if dt > mx:
            mx = dt
        if dt < mn:
            mn = dt
    _log_stats("status_raw", n, total, mx, mn, None)


def scenario_interpret_look(player):
    """commands.interpret("look", player) x5 -- representative command +
    room-render path outside combat."""
    _timed_rounds("interpret_look", 5, None,
                  lambda: commands.interpret("look", player))


def scenario_scan_skeleton(player):
    """Isolate violence_update's full-world snapshot+scan cost: replicate
    its `[chars[k] for k in sorted(chars)]` snapshot and the cheap
    per-char field checks every non-fighting char pays, with no combat.
    If this alone is a large share of the ~360ms 1v1 round, the scan --
    not attacks or rendering -- is the optimisation target."""
    chars = world.chars

    def _scan():
        n_fight = 0
        for ch in [chars[k] for k in sorted(chars)]:
            if ch["is_npc"] and ch["fighting"] is None and is_awake_stub(ch) and ch.get("hunting") is not None:
                continue
            if ch["fighting"] is None:
                continue
            n_fight += 1
        return n_fight

    # combat.is_awake equivalent without importing private helpers here.
    def is_awake_stub(ch):
        return ch.get("pos") not in ("sleeping", "stunned", "incap", "mortal", "dead")

    _timed_rounds("scan_skeleton", 10, None, _scan)


def scenario_combat_basic_batched(player):
    """Same as combat_basic but with the round's output batched via
    tr.begin_batch()/end_batch() -- direct same-shape A/B of the
    violence-round output batching, without update_handler overhead."""
    vnum = _pick_mob()
    if vnum < 0:
        log("combat_basic_batched: SKIPPED -- no mob template available")
        return
    if not hasattr(terminal.tr, "begin_batch"):
        log("combat_basic_batched: SKIPPED -- no batch support")
        return
    mob = mobprog._spawn_mob_at(vnum, player["room"])
    _engage(player, [mob])

    def _round():
        terminal.tr.begin_batch()
        try:
            combat.violence_update(player)
        finally:
            terminal.tr.end_batch()

    _timed_rounds("combat_basic_batched", 10,
                  lambda: _restore_round(player, [mob]), _round)
    _disengage(player, [mob])


def scenario_interpret_look_batched(player):
    """interpret("look") with output batched -- A/B against
    interpret_look to size the render share of a multi-line command
    before committing to interpret-level batching (needs
    flush-before-blocking-input hooks in the game proper; this probe
    call is safe because "look" never blocks)."""
    if not hasattr(terminal.tr, "begin_batch"):
        log("interpret_look_batched: SKIPPED -- no batch support")
        return

    def _lk():
        terminal.tr.begin_batch()
        try:
            commands.interpret("look", player)
        finally:
            terminal.tr.end_batch()

    _timed_rounds("interpret_look_batched", 5, None, _lk)


def scenario_combat_basic(player):
    """1 mob, 10 timed violence_update() rounds."""
    vnum = _pick_mob()
    if vnum < 0:
        log("combat_basic: SKIPPED -- no mob template available")
        return
    mob = mobprog._spawn_mob_at(vnum, player["room"])
    log("combat_basic: mob vnum=" + int_str(vnum) + " level="
        + int_str(world.MOB_DEFS._data.get(vnum, {}).get("level", 1)))
    _engage(player, [mob])
    _timed_rounds("combat_basic", 10,
                  lambda: _restore_round(player, [mob]),
                  lambda: combat.violence_update(player))
    _disengage(player, [mob])


def scenario_combat_busy(player):
    """4 mobs vs. player (player targets the first), 10 timed rounds."""
    vnum = _pick_mob()
    if vnum < 0:
        log("combat_busy: SKIPPED -- no mob template available")
        return
    mobs = []
    for _ in range(4):
        mobs.append(mobprog._spawn_mob_at(vnum, player["room"]))
    log("combat_busy: mob vnum=" + int_str(vnum) + " count=" + int_str(len(mobs)))
    _engage(player, mobs)
    _timed_rounds("combat_busy", 10,
                  lambda: _restore_round(player, mobs),
                  lambda: combat.violence_update(player))
    _disengage(player, mobs)


def _simulate_autoskill_candidates(player, limit=3):
    """Find up to `limit` (sn, name, kind) entries this player's held
    class(es)/level make eligible, mirroring autoskill._build_candidates'
    own gates -- can_use_skill_spell (class/level), is_runtime_spell, spell
    target + min_pos, and the fixed physical-skill list -- but dropping the
    "already has nonzero learned pct" checks, since injecting that pct is
    exactly what the caller is about to do. Used only when the real loaded
    save's rotation has no included entries, to simulate a plausible
    autoskill loadout for this scenario instead of skipping it. [PRIMESUD]

    Returns:
        list: up to `limit` (sn, name, kind) tuples, kind in
            ('debuff', 'spell', 'skill'), that will become included once
            player["learned"][sn] is set to a nonzero pct.
    """
    found = []
    for sn in autoskill._DEBUFF_SNS:
        if sn is None:
            continue
        if (autoskill.can_use_skill_spell(player, sn)
                and autoskill.is_runtime_spell(sn)):
            found.append((sn, autoskill.SKILLS[sn]["name"], "debuff"))
            if len(found) >= limit:
                return found

    for sn, sk in autoskill.SKILL_TABLE:
        if sn in autoskill._DEBUFF_SET or sn in autoskill._SKILL_HANDLERS:
            continue
        if sk.get("target") not in ("char_offensive", "obj_char_offensive"):
            continue
        if autoskill.POS_ORDER["fighting"] < autoskill.POS_ORDER.get(sk.get("min_pos"), 0):
            continue
        if not (autoskill.can_use_skill_spell(player, sn)
                and autoskill.is_runtime_spell(sn)):
            continue
        found.append((sn, sk["name"], "spell"))
        if len(found) >= limit:
            return found

    for sn in (autoskill.GSN_BASH, autoskill.GSN_TRIP, autoskill.GSN_DIRT,
               autoskill.GSN_DISARM, autoskill.GSN_KICK):
        if autoskill.can_use_skill_spell(player, sn):
            found.append((sn, autoskill.SKILLS[sn]["name"], "skill"))
            if len(found) >= limit:
                return found

    return found


def scenario_combat_autoskill(player):
    """1 mob, PLR_AUTOSKILL enabled (player.py/autoskill.py's own enabling
    state: `player["flags"] |= PLR_AUTOSKILL`, cf. do_autoskill in
    autoskill.py). If the character's current rotation (autoskill.
    get_rotation, built from player["learned"] -- either the real loaded
    save's skills, or create_char()'s class/race defaults if no save was
    present) has no included entry, this SIMULATES a loadout instead of
    giving up straight away: it injects a learned pct into 2-3 candidates
    that _build_candidates would actually accept for this character's held
    class(es) and level (via _simulate_autoskill_candidates), rebuilds the
    rotation, and only skips (logging autoskill-skipped) if even that
    simulated rotation has no included entry. Every injected/overwritten
    field is restored to its pre-scenario value afterward, on both the
    timed and the skip path, so later scenarios see clean state."""
    vnum = _pick_mob()
    if vnum < 0:
        log("combat_autoskill: SKIPPED -- no mob template available")
        return
    mob = mobprog._spawn_mob_at(vnum, player["room"])
    prev_flags = player.get("flags", PLR_DEFAULTS)
    player["flags"] = prev_flags | PLR_AUTOSKILL
    rotation = autoskill.get_rotation(player)
    included = [r for r in rotation if r[3]]

    simulated = False
    saved_learned = None
    saved_rot = player.get("autoskill_rot")
    if not included:
        sim_cands = _simulate_autoskill_candidates(player)
        if sim_cands:
            saved_learned = {}
            for sn, name, kind in sim_cands:
                saved_learned[sn] = player["learned"].get(sn, 0)
                player["learned"][sn] = 75
            rotation = autoskill.get_rotation(player)
            included = [r for r in rotation if r[3]]
            simulated = True

    if not included:
        log("combat_autoskill: autoskill-skipped -- rotation has no "
            + "included entries for this character (learned skills/spells "
            + "empty, or every candidate excluded), and no class/level-"
            + "eligible skill or spell could be simulated either")
        if saved_learned is not None:
            for sn, orig in saved_learned.items():
                if orig:
                    player["learned"][sn] = orig
                else:
                    player["learned"].pop(sn, None)
            if saved_rot is None:
                player.pop("autoskill_rot", None)
            else:
                player["autoskill_rot"] = saved_rot
        player["flags"] = prev_flags
        combat._extract_char(mob, pull=True)
        return

    if simulated:
        names = []
        for r in included:
            names.append(r[1])
        log("combat_autoskill: SIMULATED rotation -- " + ", ".join(names))

    log("combat_autoskill: rotation head=" + included[0][1]
        + " (" + included[0][2] + ")")
    _engage(player, [mob])
    _timed_rounds("combat_autoskill", 10,
                  lambda: _restore_round(player, [mob]),
                  lambda: combat.violence_update(player))
    _disengage(player, [mob])

    if saved_learned is not None:
        for sn, orig in saved_learned.items():
            if orig:
                player["learned"][sn] = orig
            else:
                player["learned"].pop(sn, None)
        if saved_rot is None:
            player.pop("autoskill_rot", None)
        else:
            player["autoskill_rot"] = saved_rot
    player["flags"] = prev_flags


def scenario_pulse_violence_only(player):
    """update_handler() x10 with only the violence pulse forced due each
    round; area/mobile/music/regen/tick countdowns suppressed."""
    vnum = _pick_mob()
    if vnum < 0:
        log("pulse_violence_only: SKIPPED -- no mob template available")
        return
    mob = mobprog._spawn_mob_at(vnum, player["room"])
    _engage(player, [mob])
    update._pulse_area = 100000
    update._pulse_mobile = 100000
    update._pulse_music = 100000
    update._pulse_regen = 100000
    update._pulse_tick = 100000

    def _restore():
        _restore_round(player, [mob])
        update._pulse_violence = 1

    _timed_rounds("pulse_violence_only", 10, _restore,
                  lambda: update.update_handler())
    _disengage(player, [mob])


def scenario_pulse_aligned(player):
    """update_handler() x3, forcing ALL six pulses (area, music, mobile,
    violence, regen, tick) due on every call -- the 30-second alignment
    COMBAT_LAG.md flags as a combined-pulse hitch candidate. Each call is
    logged individually (not just aggregated) since one call is the whole
    scenario each time."""
    vnum = _pick_mob()
    if vnum < 0:
        log("pulse_aligned: SKIPPED -- no mob template available")
        return
    mob = mobprog._spawn_mob_at(vnum, player["room"])
    _engage(player, [mob])
    total = 0
    for i in range(3):
        _restore_round(player, [mob])
        update._pulse_area = 1
        update._pulse_mobile = 1
        update._pulse_music = 1
        update._pulse_violence = 1
        update._pulse_regen = 1
        update._pulse_tick = 1
        t0 = ticks()
        update.update_handler()
        dt = ticks() - t0
        total += dt
        log("pulse_aligned run " + int_str(i + 1) + ": " + int_str(dt) + "ms")
    log("pulse_aligned: n=3 total=" + int_str(total) + "ms")
    _disengage(player, [mob])


def scenario_pulse_idle(player):
    """update_handler() x5, no combat, only regen forced due each round --
    near-no-op baseline (maybe_evict + mark_explored + regen check only)."""
    if player.get("fighting") is not None:
        combat.stop_fighting(player, both=True)
    update._pulse_area = 100000
    update._pulse_mobile = 100000
    update._pulse_music = 100000
    update._pulse_violence = 100000
    update._pulse_tick = 100000

    def _restore():
        update._pulse_regen = 1

    _timed_rounds("pulse_idle", 5, _restore, lambda: update.update_handler())


def main():
    gc.collect()
    log("combat_bench: on-device phase benchmark")
    log("mem free start: " + int_str(free()))

    # Redirect the save slot before ANY game write can touch the real one.
    game_state.SAVE_VAR = "smoketest"

    world.init_world()  # before create_char: its reset_lazy clears chars

    player = create_char()
    player["_macros"] = {}
    player["room"] = R_STARTING_ROOM
    world.chars[1] = player

    t0 = ticks()
    src = game_state.load_world()
    dt = ticks() - t0
    log("boot: load_world " + int_str(dt) + "ms source=" + str(src))
    log("boot: chars=" + int_str(len(world.chars))
        + " areas=" + int_str(len(world._LOADED_AREAS)))
    game_state.SAVE_FILE = "combat_bench.sav"

    gc.collect()
    log("mem free after boot: " + int_str(free()))

    scenario_set_color_ab()
    gc.collect()
    log("mem free after set_color_ab: " + int_str(free()))

    scenario_typing_prompt(player)
    gc.collect()
    log("mem free after typing_prompt: " + int_str(free()))

    scenario_status_raw(player)
    gc.collect()
    log("mem free after status_raw: " + int_str(free()))

    scenario_interpret_look(player)
    gc.collect()
    log("mem free after interpret_look: " + int_str(free()))

    scenario_interpret_look_batched(player)
    gc.collect()
    log("mem free after interpret_look_batched: " + int_str(free()))

    scenario_scan_skeleton(player)
    gc.collect()
    log("mem free after scan_skeleton: " + int_str(free()))

    log("chars loaded: " + int_str(len(world.chars)))
    scenario_combat_basic(player)
    gc.collect()
    log("mem free after combat_basic: " + int_str(free()))

    log("chars loaded: " + int_str(len(world.chars)))
    scenario_combat_basic_batched(player)
    gc.collect()
    log("mem free after combat_basic_batched: " + int_str(free()))

    log("chars loaded: " + int_str(len(world.chars)))
    scenario_combat_busy(player)
    gc.collect()
    log("mem free after combat_busy: " + int_str(free()))

    log("chars loaded: " + int_str(len(world.chars)))
    scenario_combat_autoskill(player)
    gc.collect()
    log("mem free after combat_autoskill: " + int_str(free()))

    log("chars loaded: " + int_str(len(world.chars)))
    scenario_pulse_violence_only(player)
    gc.collect()
    log("mem free after pulse_violence_only: " + int_str(free()))

    log("chars loaded: " + int_str(len(world.chars)))
    scenario_pulse_aligned(player)
    gc.collect()
    log("mem free after pulse_aligned: " + int_str(free()))

    scenario_pulse_idle(player)
    gc.collect()
    log("mem free after pulse_idle: " + int_str(free()))

    try:
        hvars_set("smoketest", "0")
        hvars_set("smoketest_bak", "0")
    except Exception:
        pass
    log("Done. Results in " + LOG)


main()
