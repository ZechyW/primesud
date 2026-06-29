"""Mutable world catalog and state loaded from area modules."""

import area_chapel
import area_grave
import area_haon
import area_immort
import area_limbo
import area_midgaard
import area_mobfact
import area_ofcol2
import area_plains
import area_quest
import area_school
import area_shire

# List of (module_name, area_tag) -- add/remove areas here only.
_AREA_LIST = [
    (area_chapel, "chapel"),
    (area_grave, "grave"),
    (area_haon, "haon"),
    (area_immort, "immort"),
    (area_limbo, "limbo"),
    (area_midgaard, "midgaard"),
    (area_mobfact, "mobfact"),
    (area_ofcol2, "ofcol2"),
    (area_plains, "plains"),
    (area_quest, "quest"),
    (area_school, "mud_school"),
    (area_shire, "shire"),
]

# -- Static definitions (populated by init_world, constant after) -----------
ROOM_DEFS = {}
MOB_DEFS = {}
ITEM_DEFS = {}
AREA_DEFS = []
DOOR_DEFS = {}
_WORLD_READY = False

# -- Mutable runtime state (mutated by reset_area / game functions) ---------
rooms = {}
chars = {}
areas = []
save_pending = False


def init_world():
    """Initialise merged world catalogs on first use."""
    global _WORLD_READY
    if _WORLD_READY:
        return

    ROOM_DEFS.clear()
    MOB_DEFS.clear()
    ITEM_DEFS.clear()
    del AREA_DEFS[:]
    DOOR_DEFS.clear()

    for _mod, _tag in _AREA_LIST:
        for _vnum, _room in _mod.ROOMS.items():
            _room["area"] = _tag
            ROOM_DEFS[_vnum] = _room
        MOB_DEFS.update(_mod.MOBILES)
        for _entry in getattr(_mod, "SPECIALS", ()):
            if _entry[0] == "M" and _entry[1] in MOB_DEFS:
                MOB_DEFS[_entry[1]]["spec_fun"] = _entry[2]
        ITEM_DEFS.update(_mod.OBJECTS)
        for _entry in getattr(_mod, "SHOPS", ()):
            _keeper = _entry["keeper"]
            if _keeper in MOB_DEFS:
                MOB_DEFS[_keeper]["shop"] = _entry
        _adef = {"tag": _tag, "resets": _mod.RESETS}
        _adef.update(_mod.AREA)
        AREA_DEFS.append(_adef)

    # Snapshot initial door closed/locked state for reset (cf. 1stMud reset_room door loop, db.c:1411)
    for _vnum, _room in ROOM_DEFS.items():
        for _d, _ev in _room.get("exits", {}).items():
            if isinstance(_ev, dict) and _ev.get("isdoor"):
                if _vnum not in DOOR_DEFS:
                    DOOR_DEFS[_vnum] = {}
                DOOR_DEFS[_vnum][_d] = {
                    "closed": bool(_ev.get("closed")),
                    "locked": bool(_ev.get("locked")),
                }

    _WORLD_READY = True
