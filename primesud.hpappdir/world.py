###################################
## PrimeSud — World Loader       ##
## Merges all area data and      ##
## defines global skill table.   ##
###################################

# fmt: off
# ── Cross-area room VNUMs (cf. 1stMud gsn_* / room vnums in index.h) ──────────
R_STARTING_ROOM  = 3700   # player respawn/starting room (currently Village Square)

# ── Skills ────────────────────────────────────────────────────────────────────
GSN_KICK         = 4001
GSN_CURE_LIGHT   = 4002
GSN_HAND_TO_HAND = 4010
GSN_PARRY        = 4020
# fmt: on

from area_school import (
    ROOMS    as _school_rooms,
    MOBILES  as MOB_TEMPLATES,
    OBJECTS  as ITEM_TEMPLATES,
    RESETS,
)

# Tag every room with its area name (cf. room->area pointer in 1stMud db.c).
# world.py is the authority — area modules carry no tag of their own.
ROOMS = {}
for _vnum, _room in _school_rooms.items():
    _room["area"] = "mud_school"
    ROOMS[_vnum] = _room

# ── Skills (cf. 1stMud skill_table; ordered list for prefix-match tiebreaking) ─
# type:     "active"  — manually triggered physical skill; beats apply
#           "spell"   — cast via 'cast <prefix>'; mana/beats/heal_dice apply
#           "weapon"  — proficiency checked in one_hit
#           "passive" — checked automatically each round
# beats: skill lag in pulses (PULSE_VIOLENCE = 12 = one full combat round)
#
# Improvement tuning (cf. 1stMud check_improve in skills.c):
#   rating     — intrinsic difficulty of the skill (minimum non-zero class cost
#                from skills.dat; higher = harder to improve)
#   multiplier — training context (1 for spells/kick, 5 for weapon prof, 6 for
#                harder passives); higher = fewer improvement rolls per use
#   Gate formula: chance = 10*INT_learn / (multiplier * rating * 4) + level
#   Roll 1..1000 — improvement only proceeds when roll <= chance.
SKILL_TABLE = [
    (GSN_KICK,         {"name": "kick",         "type": "active",
                        "beats": 12, "mana": 0, "rating": 3, "multiplier": 1,
                        "target": "char_offensive"}),
    (GSN_CURE_LIGHT,   {"name": "cure light",   "type": "spell",
                        "beats": 12, "mana": 10, "rating": 1, "multiplier": 1,
                        "target": "char_defensive", "msg_off": "!Cure Light!",
                        "effect": "heal", "heal_dice": (1, 8, 1), "level_div": 4}),
    (GSN_HAND_TO_HAND, {"name": "hand to hand", "type": "weapon",
                        "rating": 4, "multiplier": 5}),
    (GSN_PARRY,        {"name": "parry",        "type": "passive",
                        "rating": 4, "multiplier": 6}),
]

SKILLS = {vnum: data for vnum, data in SKILL_TABLE}
