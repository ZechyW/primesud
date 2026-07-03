"""World-state update loops (cf. 1stMud update.c)."""

import world
from world import ITEM_DEFS, ROOM_DEFS
from item import obj_vnum, item_affect_remove
from urandom import randint
import terminal
from config import (
    PULSE_VIOLENCE,
    PULSE_MOBILE,
    PULSE_TICK,
    PULSE_AREA,
    TICK_SECS,
)
from combat import update_mob_timers, violence_update
from game_time import time_update
from mob import mobile_update, aggr_update, area_update
from player import tick_update
from debug import DBG, dbg  # [PRIMESUD]

# -- Return flags for update_handler (cf. 1stMud update.c) --------------------
UPD_VIOLENCE = 1
UPD_TICK     = 2

# -- Countdown timers (cf. 1stMud static locals in update_handler) -------------
_pulse_area     = 0
_pulse_mobile   = 0
_pulse_violence = 0
_pulse_tick     = 0


def update_handler():
    """Dispatch periodic game-state updates (cf. 1stMud update_handler in update.c).

    Called once per pulse from game_loop.  Uses countdown timers matching 1stMud's
    static locals.  Returns bitmask of UPD_* flags so caller can handle
    PrimeSUD-specific display.
    """
    global _pulse_area, _pulse_mobile, _pulse_violence, _pulse_tick

    tr = terminal.tr
    player = world.chars[1]
    fired = 0

    _pulse_area -= 1
    if _pulse_area <= 0:
        _pulse_area = PULSE_AREA
        if "tick" in DBG:  # [PRIMESUD]
            dbg("pulse area")
        area_update(tr, player)

    # pulse_music -- not yet ported

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
        if player["fighting"] is not None:
            # [PRIMESUD] blank separator before combat round output
            # (display concern; blank-before-block matches interpret)
            tr.print("")
        violence_update(player)
        fired |= UPD_VIOLENCE

    _pulse_tick -= 1
    if _pulse_tick <= 0:
        _pulse_tick = PULSE_TICK
        if "tick" in DBG:  # [PRIMESUD]
            dbg("pulse tick")
        # weather_update()  # not yet ported
        time_update()
        player["played"] = player.get("played", 0) + TICK_SECS
        tick_update(tr, player, ROOM_DEFS[player["room"]])
        obj_update(tr, player)
        # quest_update()    # not yet ported
        fired |= UPD_TICK

    # cf. 1stMud aggr_update runs every pulse; gated to
    # PULSE_VIOLENCE here for HP Prime performance.
    if fired & UPD_VIOLENCE and player["fighting"] is None:
        aggr_update(tr, player)

    return fired


def _obj_affect_update(obj):
    """Tick object affects: decrement duration, fade level, remove expired (cf. 1stMud obj_update in update.c, lines 781-816)."""
    affects = obj.get("affect_list")
    if not affects:
        return
    tpl = ITEM_DEFS[obj_vnum(obj)]
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
    tpl = ITEM_DEFS[obj_vnum(obj)]
    itype = tpl.get("type", "")
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
    expired), then timer countdown and decay handling.

    Args:
        tr: Terminal for decay messages.
        player (dict): Player state.
    """
    # -- Room items --
    for rvnum, room in world.rooms.items():
        for obj in list(room.get("items", [])):
            _tick_contents(obj.get("contents", []))
            _obj_affect_update(obj)
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
                    room["items"].append(inner)
                room["items"].remove(obj)

    # -- NPC inventories (cf. 1stMud obj->carried_by != NULL, IsNPC path) --
    for cid, ch in world.chars.items():
        if not ch.get("is_npc"):
            continue
        for obj in list(ch.get("inv", [])):
            _tick_contents(obj.get("contents", []))
            _obj_affect_update(obj)
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
    for obj in list(player.get("inv", [])):
        _tick_contents(obj.get("contents", []))
        _obj_affect_update(obj)
        timer = obj.get("timer", -1)
        if timer <= 0:
            continue
        timer -= 1
        obj["timer"] = timer
        if timer == 0:
            tr.print(_decay_message(obj))
            # PC corpse or floating item: spill contents to player inv
            # (cf. 1stMud update.c:908-915, obj_to_char path)
            tpl = ITEM_DEFS[obj_vnum(obj)]
            itype = tpl.get("type", "")
            if itype == "pc_corpse" or tpl.get("wear_flags", {}).get("float"):
                for inner in obj.get("contents", []):
                    player["inv"].append(inner)
            player["inv"].remove(obj)

    for slot, obj in list((player.get("equip") or {}).items()):
        if obj is None:
            continue
        _tick_contents(obj.get("contents", []))
        _obj_affect_update(obj)
        timer = obj.get("timer", -1)
        if timer <= 0:
            continue
        timer -= 1
        obj["timer"] = timer
        if timer == 0:
            from handler import unequip_char
            tr.print(_decay_message(obj))
            # Floating equipped container: spill contents to room
            # (cf. 1stMud update.c:910-913)
            tpl = ITEM_DEFS[obj_vnum(obj)]
            if tpl.get("wear_flags", {}).get("float"):
                room = world.rooms.get(player["room"])
                if room:
                    for inner in obj.get("contents", []):
                        room["items"].append(inner)
            unequip_char(player, slot)
            player["inv"].remove(obj)
