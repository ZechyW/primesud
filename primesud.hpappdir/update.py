"""World-state update loops (cf. 1stMud update.c)."""

from world import ITEM_TEMPLATES
from item import obj_vnum


def affect_update(player, world):
    """Tick timed affects down on all characters (cf. 1stMud affect_update in update.c).

    Args:
        player (dict): Player state dict.
        world (dict): Game world state.
    """
    for inst in world["chars"].values():
        affects = inst["affects"]
        for key in list(affects.keys()):
            if key.endswith("_t"):
                affects[key] -= 1
                if affects[key] <= 0:
                    base = key[:-2]
                    affects.pop(key, None)
                    affects.pop(base, None)


def obj_update(tr, player, world):
    """Tick down item timers and remove decayed items from all rooms (cf. 1stMud obj_update in update.c).

    Args:
        tr: Terminal for decay messages.
        player (dict): Player state (used to check if player is in affected room).
        world (dict): World state with "rooms" mapping.
    """
    for rvnum, room in world["rooms"].items():
        for obj in list(room.get("items", [])):
            timer = obj.get("timer", -1)
            if timer <= 0:
                continue
            timer -= 1
            obj["timer"] = timer
            if timer == 0:
                tpl = ITEM_TEMPLATES[obj_vnum(obj)]
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
