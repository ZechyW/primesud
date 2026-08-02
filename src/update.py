"""World-state update loops (cf. 1stMud update.c)."""

import terminal
import world
from combat import update_mob_timers, violence_update
from config import (
    PULSE_VIOLENCE,
    PULSE_MOBILE,
    PULSE_MUSIC,
    PULSE_REGEN,
    PULSE_TICK,
    PULSE_AREA,
    TICK_SECS,
)
from debug import DBG, dbg  # [PRIMESUD]
from economy import bank_update
from explored import mark_explored  # [PRIMESUD]
from game_time import time_update
from gquest import gquest_update
from handler import unequip_char, chprintln
from item import (item_affect_remove, set_item_extra_flag, item_wear_flags,
                  item_type as _item_type)
from mob import mobile_update, aggr_update, area_update, weather_update
from music import song_update
from player import regen_update, tick_update
from quest import quest_update
from stances import first_stance_tip  # [PRIMESUD]
from urandom import randint
from util import count_str
from world import ROOM_DEFS, item_tpl

# -- Return flags for update_handler (cf. 1stMud update.c) --------------------
UPD_VIOLENCE = 1
UPD_TICK     = 2
UPD_REGEN    = 4

# -- Countdown timers (cf. 1stMud static locals in update_handler) -------------
def _gcd(a, b):
    # [PRIMESUD] inline Euclid: math.gcd/arith.gcd unverified on-device
    while b:
        a, b = b, a % b
    return a


def _stagger_offsets(periods):
    """Initial phase offsets so no two countdown timers share a pulse. [PRIMESUD]

    1stMud inits all timers to 0, so every timer fires together each
    LCM-of-periods pulses and the worst pulse pays the sum of all
    updaters.  Countdown reload preserves phase, so one-time offsets
    hold forever.  Two timers collide iff their offsets are congruent
    mod gcd(period_i, period_j); greedy picks each timer's smallest
    non-congruent offset.  Most-frequent-first ordering keeps offsets
    small (first-fire delay under 2s).  Note init 0 fires pulse 1,
    same as init 1, so candidates start at 1.

    Args:
        periods: timer periods in pulses, most frequent first.

    Returns:
        List of offsets, same order as periods.  If the periods admit
        no perfect stagger the colliding timer takes its least-bad
        offset (tests guard the perfect case for shipped config).
    """
    offsets = []
    for p in periods:
        best, best_hits = 1, len(periods)
        for o in range(1, p + 1):
            hits = 0
            for q, oq in zip(periods, offsets):
                g = _gcd(p, q)
                if o % g == oq % g:
                    hits += 1
            if hits < best_hits:
                best, best_hits = o, hits
            if hits == 0:
                break
        offsets.append(best)
    return offsets


(_pulse_violence, _pulse_mobile, _pulse_music, _pulse_regen,
 _pulse_tick, _pulse_area) = _stagger_offsets(
    (PULSE_VIOLENCE, PULSE_MOBILE, PULSE_MUSIC, PULSE_REGEN,
     PULSE_TICK, PULSE_AREA))
_regen_phase    = 0


def session_update(player):
    """Track this sitting's play time; announce each hour crossed. [PRIMESUD]

    The Prime exposes no battery level to PPL or Python (no ADC access, no PPL
    command), so elapsed play time is the only handle a player has on how much
    battery a sitting has burned.  "_session" is deliberately unsaved -- it is
    absent from game_state's save whitelist, so a reload starts a new sitting,
    which is what a battery-relevant figure should do.

    Args:
        player (dict): Player state dict.
    """
    was = player.get("_session", 0)
    player["_session"] = was + TICK_SECS
    hrs = player["_session"] // 3600
    if hrs != was // 3600:
        chprintln(player, "{c[You have been playing for "
                  + count_str(hrs, "hour") + " this session.]{x")


def update_handler():
    """Dispatch periodic game-state updates (cf. 1stMud update_handler in update.c).

    Called once per pulse from game_loop.  Uses countdown timers matching 1stMud's
    static locals.  Returns bitmask of UPD_* flags so caller can handle
    PrimeSUD-specific display.
    """
    global _pulse_area, _pulse_mobile, _pulse_music, _pulse_violence
    global _pulse_regen, _pulse_tick, _regen_phase

    tr = terminal.tr
    player = world.chars[1]
    fired = 0

    # [PRIMESUD] Far-area eviction; fast no-op unless the player moved.
    # Runs before area_update so resets happen after the heap is trimmed.
    world.maybe_evict(player)

    _pulse_area -= 1
    if _pulse_area <= 0:
        _pulse_area = PULSE_AREA
        if "tick" in DBG:  # [PRIMESUD]
            dbg("pulse area")
        area_update(tr, player)
        bank_update()

    _pulse_music -= 1
    if _pulse_music <= 0:
        _pulse_music = PULSE_MUSIC
        if "tick" in DBG:  # [PRIMESUD]
            dbg("pulse music")
        song_update()

    _pulse_mobile -= 1
    if _pulse_mobile <= 0:
        _pulse_mobile = PULSE_MOBILE
        if "tick" in DBG:  # [PRIMESUD]
            dbg("pulse mobile")
        mobile_update(tr, player)

    _pulse_violence -= 1
    if _pulse_violence <= 0:
        _pulse_violence = PULSE_VIOLENCE
        update_mob_timers()
        # [PRIMESUD] batch the round's separator + violence_update output
        # into one blit instead of dozens of per-line screen draws -- a
        # busy combat round measured ~1.07s on device, mostly per-line
        # wrapped_print (PERFORMANCE.md sec. Input-lag phase benchmark).
        # try/finally so an exception mid-round can never leave the
        # terminal stuck in batch mode. getattr guard: tests stub tr
        # without begin_batch/end_batch.
        _bb = getattr(tr, "begin_batch", None)
        if _bb:
            _bb()
            try:
                if player["fighting"] is not None:
                    # [PRIMESUD] blank separator before combat round output
                    # (display concern; blank-before-block matches interpret)
                    tr.print("")
                violence_update(player)
            finally:
                tr.end_batch()
        else:
            if player["fighting"] is not None:
                # [PRIMESUD] blank separator before combat round output
                # (display concern; blank-before-block matches interpret)
                tr.print("")
            violence_update(player)
        fired |= UPD_VIOLENCE

    _pulse_regen -= 1
    if _pulse_regen <= 0:
        _pulse_regen = PULSE_REGEN
        improve = _regen_phase == 0
        _regen_phase += 1
        if _regen_phase >= PULSE_TICK // PULSE_REGEN:
            _regen_phase = 0
        if regen_update(player, ROOM_DEFS[player["room"]], improve):
            fired |= UPD_REGEN

    _pulse_tick -= 1
    if _pulse_tick <= 0:
        _pulse_tick = PULSE_TICK
        if "tick" in DBG:  # [PRIMESUD]
            dbg("pulse tick")
        weather_update(tr, player)
        time_update(tr, player)
        player["played"] = player.get("played", 0) + TICK_SECS
        session_update(player)  # [PRIMESUD]
        tick_update(tr, player, ROOM_DEFS[player["room"]])
        obj_update(tr, player)
        quest_update()
        gquest_update()
        fired |= UPD_TICK

    # cf. 1stMud aggr_update runs every pulse; gated to
    # PULSE_VIOLENCE here for HP Prime performance.
    if fired & UPD_VIOLENCE and player["fighting"] is None:
        first_stance_tip(player)  # [PRIMESUD] one-time post-first-battle hint
        aggr_update(tr, player)

    # [PRIMESUD] mark seam for room changes that skip interpret's per-command
    # mark: speedwalk/run steps (run_buf_step fires each pulse just before this)
    # and mob-initiated drags (summon). Runs every pulse; cheap cached-vnum
    # compare. See explored.py module docstring.
    mark_explored(player)

    return fired


def _obj_affect_update(obj):
    """Tick object affects: decrement duration, fade level, remove expired (cf. 1stMud obj_update in update.c, lines 781-816)."""
    affects = obj.get("affect_list")
    if not affects:
        return
    tpl = item_tpl(obj)
    for af in list(affects):
        dur = af.get("duration", -1)
        if dur > 0:
            af["duration"] = dur - 1
            if randint(0, 4) == 0 and af.get("level", 0) > 0:
                af["level"] = af["level"] - 1
        elif dur == 0:
            item_affect_remove(obj, af, tpl)


def _decay_message(obj):
    """Return decay message string for a timer-expired object (cf. 1stMud obj_update switch in update.c)."""
    tpl = item_tpl(obj)
    itype = _item_type(obj, tpl) or ""
    short = obj.get("short_descr", tpl.get("short_descr", "something"))
    if itype == "fountain":
        return short + " dries up."
    if itype in ("npc_corpse", "pc_corpse"):
        return short + " decays into dust."
    if itype == "food":
        return short + " decomposes."
    if itype == "potion":
        return short + " has evaporated from disuse."
    if itype == "portal":
        return short + " fades out of existence."
    return short + " crumbles into dust."


def _tick_contents(obj_list):
    """Recursively tick affects and timers on nested contents (cf. 1stMud flat obj_first iteration).

    Items whose timer expires are removed from their parent list.
    Content spill is NOT done here -- only the top-level loops handle
    where spilled items land (room floor vs. player inv).
    """
    for obj in list(obj_list):
        _tick_contents(obj.get("contents", []))
        _obj_affect_update(obj)
        timer = obj.get("timer", -1)
        if timer <= 0:
            continue
        timer -= 1
        obj["timer"] = timer
        if timer == 0:
            obj_list.remove(obj)


def obj_update(tr, player):
    """Tick object affects and item timers for all objects in game (cf. 1stMud obj_update in update.c).

    Iterates room items, NPC inventories, and player inventory/equipment.
    Recurses into container contents to match 1stMud's flat global object
    list iteration.  Affects tick first (duration--, 20%% level fade, remove
    expired), then the random/delay objprog pulse (cf. update.c:822-835;
    container contents are excluded, matching the upstream located-only gate
    -- see mobprog.pulse_obj for the intent-parity note), then timer
    countdown and decay handling.

    Args:
        tr: Terminal for decay messages.
        player (dict): Player state.
    """
    oprogs = bool(world.OBJPROGS)  # ponytail: no obj progs -> skip per-obj pulse
    if oprogs:
        import mobprog  # deferred: keep mobprog off the boot path
        ptag = ROOM_DEFS[player["room"]].get("area")  # non-empty area = the player's

    # -- Room items --
    for rvnum, room in world.rooms.items():
        for obj in list(room.get("items", [])):
            _tick_contents(obj.get("contents", []))
            _obj_affect_update(obj)
            if (oprogs and mobprog.pulse_obj(
                    obj, rvnum, None, ROOM_DEFS[rvnum].get("area") == ptag)
                    and obj not in room["items"]):
                continue  # the prog purged/moved it; nothing left to tick
            timer = obj.get("timer", -1)
            if timer <= 0:
                continue
            timer -= 1
            obj["timer"] = timer
            if timer == 0:
                if player["room"] == rvnum:
                    tr.print(_decay_message(obj))
                # Drop contents to room floor (cf. 1stMud obj_update in update.c)
                for inner in obj.get("contents", []):
                    if inner.get("timer", -1) <= 0:
                        # [PRIMESUD] no permanent world litter: unlike 1stMud,
                        # saves persist floor items, so timerless spill (gear,
                        # coins) would accumulate forever. The litter flag lets
                        # pickup (_get_triggers) clear the timer again; items
                        # with a canonical timer (potion/scroll/rot_death) are
                        # untouched.
                        inner["timer"] = randint(25, 40)
                        set_item_extra_flag(inner, item_tpl(inner), "litter",
                                            True)
                    room["items"].append(inner)
                room["items"].remove(obj)

    # -- NPC inventories (cf. 1stMud obj->carried_by != NULL, IsNPC path) --
    for cid, ch in world.chars.items():
        if not ch.get("is_npc"):
            continue
        for obj in list(ch["inv"]):
            _tick_contents(obj.get("contents", []))
            _obj_affect_update(obj)
            if (oprogs and mobprog.pulse_obj(obj, ch["room"], ch, True)
                    and obj not in ch["inv"]):
                continue
            timer = obj.get("timer", -1)
            if timer <= 0:
                continue
            timer -= 1
            obj["timer"] = timer
            if timer == 0:
                # Shopkeeper recoup (cf. 1stMud update.c:878)
                if ch.get("shop"):
                    ch["silver"] = ch.get("silver", 0) + obj.get("cost", 0) // 5
                ch["inv"].remove(obj)

    # -- Player inventory + equipment (cf. 1stMud obj->carried_by, !IsNPC path) --
    for obj in list(player["inv"]):
        _tick_contents(obj.get("contents", []))
        _obj_affect_update(obj)
        if (oprogs and mobprog.pulse_obj(obj, player["room"], player, True)
                and obj not in player["inv"]):
            continue
        timer = obj.get("timer", -1)
        if timer <= 0:
            continue
        timer -= 1
        obj["timer"] = timer
        if timer == 0:
            tr.print(_decay_message(obj))
            # PC corpse or floating item: spill contents to player inv
            # (cf. 1stMud update.c:908-915, obj_to_char path)
            tpl = item_tpl(obj)
            itype = _item_type(obj, tpl) or ""
            if itype == "pc_corpse" or item_wear_flags(obj, tpl).get("float"):
                for inner in obj.get("contents", []):
                    player["inv"].append(inner)
            player["inv"].remove(obj)

    for slot, obj in list(player["equip"].items()):
        if obj is None:
            continue
        _tick_contents(obj.get("contents", []))
        _obj_affect_update(obj)
        if (oprogs and mobprog.pulse_obj(obj, player["room"], player, True)
                and player["equip"].get(slot) is not obj):
            continue
        timer = obj.get("timer", -1)
        if timer <= 0:
            continue
        timer -= 1
        obj["timer"] = timer
        if timer == 0:
            tr.print(_decay_message(obj))
            # Floating equipped container: spill contents to room
            # (cf. 1stMud update.c:910-913)
            tpl = item_tpl(obj)
            if item_wear_flags(obj, tpl).get("float"):
                room = world.rooms.get(player["room"])
                if room:
                    for inner in obj.get("contents", []):
                        room["items"].append(inner)
            unequip_char(player, slot)
            player["inv"].remove(obj)
