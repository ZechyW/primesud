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

# List of (module_name, area_tag) — add/remove areas here only.
_AREA_LIST = [
    ("area_limbo",    "limbo"),
    ("area_school",   "mud_school"),
    ("area_midgaard", "midgaard"),
    ("area_quest",    "quest"),
    ("area_chapel",   "chapel"),
]

# Tag every room with its area name (cf. room->area pointer in 1stMud db.c).
# world.py is the authority — area modules carry no tag of their own.
ROOMS = {}
MOB_TEMPLATES = {}
ITEM_TEMPLATES = {}
RESETS = ()
AREA_DEFS = []

for _mod_name, _tag in _AREA_LIST:
    _mod = __import__(_mod_name)
    for _vnum, _room in _mod.ROOMS.items():
        _room["area"] = _tag
        ROOMS[_vnum] = _room
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
