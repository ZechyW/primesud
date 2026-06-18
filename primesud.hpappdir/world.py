"""World catalogs loaded from area modules and global skill data."""

###################################
## PrimeSud -- World Loader       ##
## Merges all area data and      ##
## defines global skill table.   ##
###################################

# fmt: off
# -- Cross-area room VNUMs (cf. 1stMud gsn_* / room vnums in index.h) ----------
R_STARTING_ROOM  = 3700   # player respawn/starting room (Mud School entrance)
R_RECALL         = 3001   # default recall destination (cf. 1stMud ROOM_VNUM_TEMPLE)

# -- Skills --------------------------------------------------------------------
from skills_table import (
    SKILL_TABLE as _ST_RAW,
    GSN_KICK, GSN_HAND_TO_HAND, GSN_PARRY, GSN_RECALL,
    GSN_SWORD, GSN_AXE, GSN_DAGGER, GSN_FLAIL, GSN_MACE, GSN_POLEARM,
    GSN_SPEAR, GSN_WHIP, GSN_SHIELD_BLOCK,
    GSN_SECOND_ATTACK, GSN_THIRD_ATTACK,
)
import area_limbo
import area_school
import area_midgaard
import area_quest
import area_chapel

GSN_CURE_LIGHT = 27  # [PRIMESUD] no gsn_cure_light in 1stMud; sn 27 from skill_table
# fmt: on

# List of (module_name, area_tag) -- add/remove areas here only.
_AREA_LIST = [
    (area_limbo, "limbo"),
    (area_school, "mudschool"),  # Avoid underscores; HP Prime string formatting may mis-handle them.
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
RESETS = ()
AREA_DEFS = []

for _mod, _tag in _AREA_LIST:
    for _vnum, _room in _mod.ROOMS.items():
        ROOMS[_vnum] = _room
        ROOM_AREAS[_vnum] = _tag
    MOB_TEMPLATES.update(_mod.MOBILES)
    ITEM_TEMPLATES.update(_mod.OBJECTS)
    RESETS = RESETS + _mod.RESETS
    AREA_DEFS.append({"tag": _tag, "resets": _mod.RESETS})

AREA_DEFS = tuple(AREA_DEFS)

# Snapshot initial door closed/locked state for reset (cf. 1stMud reset_room door loop, db.c:1411)
DOOR_RESET = {}
for _vnum, _room in ROOMS.items():
    for _d, _ev in _room.get("exits", {}).items():
        if isinstance(_ev, dict) and _ev.get("isdoor"):
            if _vnum not in DOOR_RESET:
                DOOR_RESET[_vnum] = {}
            DOOR_RESET[_vnum][_d] = {"closed": bool(_ev.get("closed")), "locked": bool(_ev.get("locked"))}

# -- Skills (cf. 1stMud skill_table; ordered list for prefix-match tiebreaking) -
# Flatten per-class tuples: skill_level -> earliest any class learns it;
# rating -> best (lowest non-zero) rate; default=1 guards all-zero edge case.
def _flatten_skill(sn, data):
    d = {}
    d.update(data)
    d["skill_level"] = min(data["skill_level"])
    d["rating"] = min((v for v in data["rating"] if v > 0), default=1)
    return (sn, d)

SKILL_TABLE = [_flatten_skill(sn, data) for sn, data in _ST_RAW]

SKILLS = dict(SKILL_TABLE)

# Maps item weapon_type string -> GSN (cf. 1stMud weapon_table in const.c).
# Unknown weapon type -> -1 at call site (see _get_weapon_sn in combat.py).
WEAPON_GSN_MAP = {
    "sword":   GSN_SWORD,
    "axe":     GSN_AXE,
    "dagger":  GSN_DAGGER,
    "flail":   GSN_FLAIL,
    "mace":    GSN_MACE,
    "polearm": GSN_POLEARM,
    "spear":   GSN_SPEAR,
    "whip":    GSN_WHIP,
}
