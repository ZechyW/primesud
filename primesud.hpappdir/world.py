"""Mutable world catalog and state loaded from area modules."""

import area_limbo
import area_school
import area_midgaard
import area_quest
import area_chapel

# List of (module_name, area_tag) -- add/remove areas here only.
_AREA_LIST = [
    (area_limbo, "limbo"),
    (area_school, "mud_school"),
    (area_midgaard, "midgaard"),
    (area_quest, "quest"),
    (area_chapel, "chapel"),
]

# Map each room to its area name (cf. room->area pointer in 1stMud db.c).
# world.py is the authority -- area modules carry no tag of their own.
ROOMS = {}
ROOM_AREAS = {}
MOB_TEMPLATES = {}
ITEM_TEMPLATES = {}
RESETS = []
AREA_DEFS = []
DOOR_RESET = {}
_WORLD_READY = False


def init_world():
    """Initialise merged world catalogs on first use."""
    global _WORLD_READY
    if _WORLD_READY:
        return

    ROOMS.clear()
    ROOM_AREAS.clear()
    MOB_TEMPLATES.clear()
    ITEM_TEMPLATES.clear()
    del RESETS[:]
    del AREA_DEFS[:]
    DOOR_RESET.clear()

    for _mod, _tag in _AREA_LIST:
        for _vnum, _room in _mod.ROOMS.items():
            ROOMS[_vnum] = _room
            ROOM_AREAS[_vnum] = _tag
        MOB_TEMPLATES.update(_mod.MOBILES)
        ITEM_TEMPLATES.update(_mod.OBJECTS)
        RESETS.extend(_mod.RESETS)
        AREA_DEFS.append({"tag": _tag, "resets": _mod.RESETS})

    # Snapshot initial door closed/locked state for reset (cf. 1stMud reset_room door loop, db.c:1411)
    for _vnum, _room in ROOMS.items():
        for _d, _ev in _room.get("exits", {}).items():
            if isinstance(_ev, dict) and _ev.get("isdoor"):
                if _vnum not in DOOR_RESET:
                    DOOR_RESET[_vnum] = {}
                DOOR_RESET[_vnum][_d] = {"closed": bool(_ev.get("closed")), "locked": bool(_ev.get("locked"))}

    _WORLD_READY = True
