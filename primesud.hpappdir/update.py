"""World-state update loops (cf. 1stMud update.c)."""

import world
from world import ITEM_DEFS, ROOM_DEFS
from item import obj_vnum
import terminal
from config import (
    PULSE_VIOLENCE,
    PULSE_MOBILE,
    PULSE_TICK,
    PULSE_AREA,
    TICK_SECS,
)
from combat import update_mob_timers, violence_update
from mob import mobile_update, aggr_update, area_update
from player import tick_update

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
        area_update(tr, player)

    # pulse_music -- not yet ported

    _pulse_mobile -= 1
    if _pulse_mobile <= 0:
        _pulse_mobile = PULSE_MOBILE
        mobile_update(tr, player)

    _pulse_violence -= 1
    if _pulse_violence <= 0:
        _pulse_violence = PULSE_VIOLENCE
        update_mob_timers()
        violence_update(player)
        fired |= UPD_VIOLENCE

    _pulse_tick -= 1
    if _pulse_tick <= 0:
        _pulse_tick = PULSE_TICK
        # weather_update()  # not yet ported
        # time_update()     # not yet ported
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


def obj_update(tr, player):
    """Tick down item timers and remove decayed items from all rooms (cf. 1stMud obj_update in update.c).

    Args:
        tr: Terminal for decay messages.
        player (dict): Player state (used to check if player is in affected room).
    """
    for rvnum, room in world.rooms.items():
        for obj in list(room.get("items", [])):
            timer = obj.get("timer", -1)
            if timer <= 0:
                continue
            timer -= 1
            obj["timer"] = timer
            if timer == 0:
                tpl = ITEM_DEFS[obj_vnum(obj)]
                itype = tpl.get("type", "")
                short = obj.get("short_descr", tpl.get("short_descr", "something"))
                if itype in ("npc_corpse", "pc_corpse"):
                    msg = short + " decays into dust."
                elif itype == "food":
                    msg = short + " decomposes."
                elif itype == "potion":
                    msg = short + " has evaporated from disuse."
                else:
                    msg = short + " crumbles into dust."
                if player["room"] == rvnum:
                    tr.print(msg)
                if "contents" in obj:
                    del obj["contents"]
                room["items"].remove(obj)
