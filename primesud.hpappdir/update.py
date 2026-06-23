"""World-state update loops (cf. 1stMud update.c)."""

import world
from world import ITEM_DEFS
from item import obj_vnum


def affect_update(player):
    """Tick timed affects down on all characters (cf. 1stMud affect_update in update.c).

    Args:
        player (dict): Player state dict.
    """
    for inst in world.chars.values():
        affects = inst["affects"]
        for key in list(affects.keys()):
            if key.endswith("_t"):
                affects[key] -= 1
                if affects[key] <= 0:
                    base = key[:-2]
                    affects.pop(key, None)
                    affects.pop(base, None)


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
