###################################
## PrimeSud — World Loader       ##
## Merges all area data and      ##
## defines global skill table.   ##
###################################

# fmt: off
# ── Cross-area room VNUMs (cf. 1stMud gsn_* / room vnums in index.h) ──────────
R_STARTING_ROOM  = 3700   # player respawn/starting room (Mud School entrance)
R_RECALL         = 3001   # default recall destination (cf. 1stMud ROOM_VNUM_TEMPLE)

# ── Skills ────────────────────────────────────────────────────────────────────
GSN_KICK         = 4001
GSN_CURE_LIGHT   = 4002
GSN_HAND_TO_HAND = 4010
GSN_PARRY        = 4020
GSN_RECALL       = 4030
# fmt: on

from area_limbo import (
    ROOMS    as _limbo_rooms,
    MOBILES  as _limbo_mobs,
    OBJECTS  as _limbo_items,
    RESETS   as _limbo_resets,
)
from area_school import (
    ROOMS    as _school_rooms,
    MOBILES  as _school_mobs,
    OBJECTS  as _school_items,
    RESETS   as _school_resets,
)
from area_midgaard import (
    ROOMS    as _midgaard_rooms,
    MOBILES  as _midgaard_mobs,
    OBJECTS  as _midgaard_items,
    RESETS   as _midgaard_resets,
)
from area_quest import (
    ROOMS    as _quest_rooms,
    MOBILES  as _quest_mobs,
    OBJECTS  as _quest_items,
    RESETS   as _quest_resets,
)

# Tag every room with its area name (cf. room->area pointer in 1stMud db.c).
# world.py is the authority — area modules carry no tag of their own.
ROOMS = {}
for _vnum, _room in _limbo_rooms.items():
    _room["area"] = "limbo"
    ROOMS[_vnum] = _room
for _vnum, _room in _school_rooms.items():
    _room["area"] = "mud_school"
    ROOMS[_vnum] = _room
for _vnum, _room in _midgaard_rooms.items():
    _room["area"] = "midgaard"
    ROOMS[_vnum] = _room
for _vnum, _room in _quest_rooms.items():
    _room["area"] = "quest"
    ROOMS[_vnum] = _room

# Snapshot initial door closed/locked state for reset (cf. 1stMud reset_room door loop, db.c:1411)
DOOR_RESET = {}
for _vnum, _room in ROOMS.items():
    for _d, _ev in _room.get("exits", {}).items():
        if isinstance(_ev, dict) and _ev.get("isdoor"):
            if _vnum not in DOOR_RESET:
                DOOR_RESET[_vnum] = {}
            DOOR_RESET[_vnum][_d] = {"closed": bool(_ev.get("closed")), "locked": bool(_ev.get("locked"))}

MOB_TEMPLATES = {}; MOB_TEMPLATES.update(_limbo_mobs);   MOB_TEMPLATES.update(_school_mobs);  MOB_TEMPLATES.update(_midgaard_mobs);  MOB_TEMPLATES.update(_quest_mobs)
ITEM_TEMPLATES = {}; ITEM_TEMPLATES.update(_limbo_items); ITEM_TEMPLATES.update(_school_items); ITEM_TEMPLATES.update(_midgaard_items); ITEM_TEMPLATES.update(_quest_items)
RESETS          = _limbo_resets + _school_resets + _midgaard_resets + _quest_resets

AREA_DEFS = (
    {"tag": "limbo",     "resets": _limbo_resets},
    {"tag": "mud_school", "resets": _school_resets},
    {"tag": "midgaard",   "resets": _midgaard_resets},
    {"tag": "quest",      "resets": _quest_resets},
)

# ── Skills (cf. 1stMud skill_table; ordered list for prefix-match tiebreaking) ─
# type:     "active"  — manually triggered physical skill; beats apply
#           "spell"   — cast via 'cast <prefix>'; mana/beats/heal_dice apply
#           "weapon"  — proficiency checked in one_hit
#           "passive" — checked automatically each round
# beats: skill lag in pulses (PULSE_VIOLENCE = 12 = one full combat round)
#
# Improvement tuning (cf. 1stMud check_improve in skills.c):
#   rating — intrinsic difficulty of the skill (minimum non-zero class cost
#             from skills.dat; higher = harder to improve)
#   Gate formula: chance = 10*INT_learn / (multiplier * rating * 4) + level
#   multiplier is passed per call site in check_improve(), not stored here.
#   Roll 1..1000 — improvement only proceeds when roll <= chance.
SKILL_TABLE = [
    (GSN_KICK,         {"name": "kick",         "type": "active",  "min_level": 1,
                        "beats": 12, "mana": 0, "rating": 3,
                        "target": "char_offensive"}),
    (GSN_CURE_LIGHT,   {"name": "cure light",   "type": "spell",   "min_level": 1,
                        "beats": 12, "mana": 10, "rating": 1,
                        "target": "char_defensive", "msg_off": "!Cure Light!",
                        "effect": "heal", "heal_dice": (1, 8, 1), "level_div": 4}),
    (GSN_HAND_TO_HAND, {"name": "hand to hand", "type": "weapon",  "min_level": 1,
                        "rating": 4}),
    (GSN_PARRY,        {"name": "parry",        "type": "passive", "min_level": 1,
                        "rating": 4}),
    (GSN_RECALL,       {"name": "recall",       "type": "active",  "min_level": 1,
                        "beats": 0, "mana": 0, "rating": 4, "target": "none"}),
]

SKILLS = {vnum: data for vnum, data in SKILL_TABLE}
