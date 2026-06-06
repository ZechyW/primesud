###################################
## PrimeSud — World Data         ##
## Rooms, items, mobs, skills    ##
###################################

# ── VNUM ranges ──────────────────
# 1000–1999  Rooms
# 2000–2999  Mob templates
# 3000–3999  Item templates
# 4000–4999  Skills

# ── Room VNUMs ───────────────────
R_VILLAGE_SQUARE   = 1000
R_DUNGEON_ENTRANCE = 1001
R_DUNGEON_HALL     = 1002
R_TRAINING_ROOM    = 1003

# ── Mob template VNUMs ───────────
M_RAT    = 2000
M_GOBLIN = 2001
M_DUMMY  = 2002
M_SNAIL  = 2003
M_RABBIT = 2004
M_FOX    = 2005
M_LIZARD = 2006
M_BOAR   = 2007
M_BEAR   = 2008
M_WOLF   = 2009
M_BEAST  = 2010

# ── Arena/Dungeon Room VNUMs ──────
# Arena 5×5 grid: VNUM = 1100 + row*5 + col (row 0=south, col 0=west)
R_ARENA_ENTRY  = 1102  # row 0 col 2 — south-centre, entrance from Training Room
R_ARENA_SW     = 1100  # row 0 col 0 — snails
R_ARENA_SE     = 1104  # row 0 col 4 — foxes
R_ARENA_CENTER = 1112  # row 2 col 2 — rabbits; down → dungeon
R_ARENA_NW     = 1120  # row 4 col 0 — lizards
R_ARENA_NE     = 1124  # row 4 col 4 — boars
R_ARENA_SAFE   = 1125  # safe room (up from all arena cells)
R_DUNGEON_C    = 1126  # dungeon centre — up → R_ARENA_CENTER
R_DUNGEON_NW   = 1127  # beast
R_DUNGEON_N    = 1128
R_DUNGEON_NE   = 1129  # bears
R_DUNGEON_W    = 1130
R_DUNGEON_E    = 1131
R_DUNGEON_SW   = 1132  # wolves
R_DUNGEON_S    = 1133
R_DUNGEON_SE   = 1134

# ── Item template VNUMs ──────────
I_SWORD_IRON  = 3000
I_POTION_HP   = 3001
I_DAGGER      = 3002

# ── Skill VNUMs ──────────────────
# Internal / auto-attack
SK_ATTACK       = 4000

# Active skills (manually triggered)
SK_SLASH        = 4001
SK_HEAL         = 4002
SK_WEAKEN       = 4003

# Weapon proficiencies (passive — affect one_hit damage/accuracy)
SK_UNARMED      = 4010
SK_SWORD        = 4011
SK_DAGGER       = 4012

# Passive combat skills
SK_SECOND_ATTACK = 4020
SK_THIRD_ATTACK  = 4021
SK_DODGE         = 4022
SK_PARRY         = 4023
SK_SHIELD_BLOCK  = 4024
SK_ENHANCED_DMG  = 4025

# ── Stat application tables (ROM 2.4 values, index by stat 0–25) ──────────────
# str_app: tohit (THAC0 bonus, negative = better), todam (damage roll bonus)
STR_APP_TOHIT = (-5,-5,-3,-3,-2,-2,-1,-1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 3, 3, 4, 4, 5, 6, 7)
STR_APP_TODAM = (-4,-4,-2,-1,-1,-1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 4, 4, 5, 5, 6, 7, 8)
# dex_app: defensive AC modifier (negative = better)
DEX_APP_DEF   = (60,50,40,35,30,25,20,15,10, 5, 0, 0, 0, 0, 0,-1,-2,-3,-4,-5,-6,-7,-8,-9,-10,-11)
# con_app: bonus HP gained per level-up
CON_APP_HITP  = (-4,-3,-2,-2,-1,-1,-1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 2, 3, 3, 4, 4, 5, 6, 7, 8)
# wis_app: bonus practices gained per level-up (1stMud wis_app[].practice)
WIS_APP_PRACTICE = (0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,2,2,2,3,3,3,3,4,4,4,5)

# ── Classless HP die (Cleric/Paladin range) ───────────────────────────────────
CLASS_HP_MIN = 7
CLASS_HP_MAX = 10

# ── THAC0 constants (classless, balanced midpoint) ────────────────────────────
THAC0_00 = 20   # THAC0 at level 1  (higher = worse to-hit)
THAC0_32 = -2   # THAC0 at level 32 (lower  = better to-hit)

# ── Room definitions ─────────────
ROOMS = {
    R_VILLAGE_SQUARE: {
        "name":  "Village Square",
        "short": "A crumbling square. A well stands at the centre.",
        "long":  "The village square is mostly rubble. A well stands at the centre, "
                 "dry and long forgotten. A path leads north to the market ruins, "
                 "and a dark stairway descends south into the dungeon.",
        "exits": {"n": R_TRAINING_ROOM, "s": R_DUNGEON_ENTRANCE},
    },
    R_DUNGEON_ENTRANCE: {
        "name":  "Dungeon Entrance",
        "short": "A narrow stone archway. The smell of damp earth fills the air.",
        "long":  "Rough-hewn stone walls surround a narrow archway. Torchlight "
                 "flickers from somewhere deeper within. The village square lies back "
                 "to the north.",
        "exits": {"n": R_VILLAGE_SQUARE, "s": R_DUNGEON_HALL},
    },
    R_DUNGEON_HALL: {
        "name":  "Dungeon Hall",
        "short": "A broad hall. Bones litter the floor.",
        "long":  "A broad hall stretches before you, its ceiling lost in shadow. "
                 "Bones crunch underfoot. The entrance passage is back to the north.",
        "exits": {"n": R_DUNGEON_ENTRANCE},
    },
    R_TRAINING_ROOM: {
        "name":  "Training Yard",
        "short": "A sandy yard. A battered training dummy stands in the centre.",
        "long":  "A small sandy yard fenced off from the square. A battered wooden "
                 "training dummy stands bolted to a post in the centre, its surface "
                 "scarred from countless blows.",
        "exits": {"s": R_VILLAGE_SQUARE, "n": R_ARENA_ENTRY},
    },
}

# ── Arena and dungeon rooms (generated) ──────────────────────────────────────
def _arena_name(r, c):
    if r == 0:
        if c == 0:   return "South West Corner of Arena"
        elif c == 4: return "South East Corner of Arena"
        else:        return "South Wall of Arena"
    elif r == 4:
        if c == 0:   return "North West Corner of Arena"
        elif c == 4: return "North East Corner of Arena"
        else:        return "North Wall of Arena"
    elif c == 0:     return "West Wall of Arena"
    elif c == 4:     return "East Wall of Arena"
    elif r == 2 and c == 2: return "Center of Arena"
    else:            return "Arena"

_AL = ("You are in the Arena.  Remember, if you wish to get out of this Arena, just "
       "go up.  Ceilings can barely be seen in this huge Arena.  You feel as if you "
       "are being watched by some divine being.")
_DL_C = ("You are in the center of a large room.  A faint light from above shows that "
         "the floors are all covered with slime.  A feeling of dread comes over you as "
         "you notice that this is NOT a great place to go.  Exits go in all directions.  "
         "Of special note is the one that brings you back up!!!")
_DL = ("You are against a wall in the dungeon.  It is quite dark here.  "
       "The lack of any windows in the area explains the smell around you.")

for _r in range(5):
    for _c in range(5):
        _v = 1100 + _r * 5 + _c
        _ex = {}
        if _r < 4: _ex["n"] = 1100 + (_r + 1) * 5 + _c
        if _r > 0: _ex["s"] = 1100 + (_r - 1) * 5 + _c
        if _c < 4: _ex["e"] = 1100 + _r * 5 + (_c + 1)
        if _c > 0: _ex["w"] = 1100 + _r * 5 + (_c - 1)
        _ex["u"] = R_ARENA_SAFE
        if _r == 0 and _c == 2:
            _ex["s"] = R_TRAINING_ROOM
        if _r == 2 and _c == 2:
            _ex["d"] = R_DUNGEON_C
        _n = _arena_name(_r, _c)
        ROOMS[_v] = {"name": _n, "short": "You are in the Arena.", "long": _AL, "exits": _ex}

ROOMS[R_ARENA_SAFE] = {
    "name":  "A Safe Room",
    "short": "You are in a safe room, away from the Arena.",
    "long":  ("You are in a safe room, away from all the mean rabbits and snails "
              "of the Arena.  You can rest here, and go down to return to the Arena."),
    "exits": {"d": R_ARENA_ENTRY},
}

for _v, _name, _ex in (
    (R_DUNGEON_C,  "The Center of the Dungeon",        {"n": R_DUNGEON_N,  "e": R_DUNGEON_E,  "s": R_DUNGEON_S,  "w": R_DUNGEON_W,  "u": R_ARENA_CENTER}),
    (R_DUNGEON_NW, "The North West Corner of the Dungeon", {"e": R_DUNGEON_N,  "s": R_DUNGEON_W}),
    (R_DUNGEON_N,  "The North Wall of the Dungeon",    {"e": R_DUNGEON_NE, "s": R_DUNGEON_C,  "w": R_DUNGEON_NW}),
    (R_DUNGEON_NE, "The North East Corner of the Dungeon", {"s": R_DUNGEON_E,  "w": R_DUNGEON_N}),
    (R_DUNGEON_W,  "The West Wall of the Dungeon",     {"n": R_DUNGEON_NW, "e": R_DUNGEON_C,  "s": R_DUNGEON_SW}),
    (R_DUNGEON_E,  "The East Wall of the Dungeon",     {"n": R_DUNGEON_NE, "s": R_DUNGEON_SE, "w": R_DUNGEON_C}),
    (R_DUNGEON_SW, "The South West Corner of the Dungeon", {"n": R_DUNGEON_W,  "e": R_DUNGEON_S}),
    (R_DUNGEON_S,  "The South Wall of the Dungeon",    {"n": R_DUNGEON_C,  "e": R_DUNGEON_SE, "w": R_DUNGEON_SW}),
    (R_DUNGEON_SE, "The South East Corner of the Dungeon", {"n": R_DUNGEON_E,  "w": R_DUNGEON_S}),
):
    _dl = _DL_C if _v == R_DUNGEON_C else _DL
    _ds = ("You are in the center of the dungeon." if _v == R_DUNGEON_C
           else "You are against a wall in the dungeon.")
    ROOMS[_v] = {"name": _name, "short": _ds, "long": _dl, "exits": _ex}

# Initial item and mob placement per room.
# Copied into mutable room_state at game start — do not mutate these directly.
ROOM_INIT = {
    R_VILLAGE_SQUARE:   {"items": [],          "mobs": []},
    R_DUNGEON_ENTRANCE: {"items": [I_DAGGER],  "mobs": [1]},
    R_DUNGEON_HALL:     {"items": [],          "mobs": [2, 3]},
    R_TRAINING_ROOM:    {"items": [],          "mobs": [4]},
}

for _v in range(1100, 1135):
    ROOM_INIT[_v] = {"items": [], "mobs": []}
ROOM_INIT[R_ARENA_SW]["mobs"]     = [5, 6, 7, 8, 9]
ROOM_INIT[R_ARENA_SE]["mobs"]     = [10, 11, 12]
ROOM_INIT[R_ARENA_CENTER]["mobs"] = [13, 14, 15, 16]
ROOM_INIT[R_ARENA_NW]["mobs"]     = [17, 18, 19]
ROOM_INIT[R_ARENA_NE]["mobs"]     = [20, 21, 22]
ROOM_INIT[R_DUNGEON_NW]["mobs"]   = [23]
ROOM_INIT[R_DUNGEON_NE]["mobs"]   = [24, 25]
ROOM_INIT[R_DUNGEON_SW]["mobs"]   = [26, 27]

# ── Item templates ───────────────
# Weapons: dice=(num,size,bonus) — damage roll; weapon_type — proficiency link
# Armour:  AC — contribution to worn AC (negative = better)
ITEM_TEMPLATES = {
    I_SWORD_IRON: {
        "name": "Iron Sword",
        "desc": "A serviceable iron sword, nicked but solid.",
        "type": "weapon", "slot": "weapon",
        "weight": 4,
        "dice": (1, 6, 1), "weapon_type": "sword",
        "hitroll": 1, "damroll": 1,
        "value": 20,
    },
    I_DAGGER: {
        "name": "Dagger",
        "desc": "A short blade, easy to conceal.",
        "type": "weapon", "slot": "weapon",
        "weight": 1,
        "dice": (1, 4, 0), "weapon_type": "dagger",
        "hitroll": 0, "damroll": 0,
        "value": 8,
    },
    I_POTION_HP: {
        "name": "Health Potion",
        "desc": "A small vial of red liquid. Restores HP when drunk.",
        "type": "consumable", "slot": None,
        "weight": 1, "use_hp": 25, "value": 15,
    },
}

# Weapon type → proficiency skill VNUM
WEAPON_TYPE_SKILL = {
    "sword":  SK_SWORD,
    "dagger": SK_DAGGER,
}

# ── Mob templates ────────────────
# perm_stat: base attributes (str/dex/int/wis/con)
# hitroll/damroll: base combat bonuses (before stat application)
# AC: base armour class (100 = unarmored; negative = better)
# damage: (num_dice, die_size, bonus) — natural attack
MOB_TEMPLATES = {
    M_RAT: {
        "name": "Giant Rat",
        "desc": "A rat the size of a terrier, teeth bared.",
        "level": 1,
        "hp_dice": (1, 6, 2),
        "perm_stat": {"str": 8, "dex": 12, "int": 2, "wis": 2, "con": 8},
        "hitroll": 0, "damroll": 0, "AC": 100,
        "damage": (1, 3, 0),
        "gold": 1,
        "loot": [(I_POTION_HP, 15)],
        "respawn": 30000,
    },
    M_GOBLIN: {
        "name": "Goblin",
        "desc": "A snarling creature clutching a rusty knife.",
        "level": 3,
        "hp_dice": (2, 8, 2),
        "perm_stat": {"str": 11, "dex": 11, "int": 8, "wis": 6, "con": 10},
        "hitroll": 0, "damroll": 1, "AC": 70,
        "damage": (1, 5, 1),
        "gold": 5,
        "loot": [(I_DAGGER, 20), (I_POTION_HP, 25)],
        "respawn": 60000,
    },
    M_DUMMY: {
        "name": "Training Dummy",
        "desc": "A battered wooden dummy bolted to a post.",
        "level": 1,
        "hp_dice": (1, 1, 499),
        "perm_stat": {"str": 10, "dex": 10, "int": 10, "wis": 10, "con": 10},
        "hitroll": -100, "damroll": 0, "AC": 100,
        "damage": (1, 1, 0),
        "gold": 0,
        "loot": [],
        "passive": True,  # [PRIMESUD] does not counter-attack
        "respawn": 5000,
    },
}

MOB_TEMPLATES[M_SNAIL] = {
    "name": "Snail",
    "desc": "A tiny snail oozes slowly across the ground.",
    "level": 0,
    "hp_dice": (1, 1, 0),
    "perm_stat": {"str": 4, "dex": 4, "int": 1, "wis": 1, "con": 4},
    "hitroll": 0, "damroll": 0, "AC": 100,
    "damage": (1, 1, 0),
    "gold": 0, "loot": [],
    "respawn": 20000,
}
MOB_TEMPLATES[M_RABBIT] = {
    "name": "Rabbit",
    "desc": "A fluffy rabbit hops around, completely harmless.",
    "level": 1,
    "hp_dice": (1, 1, 10),
    "perm_stat": {"str": 6, "dex": 14, "int": 3, "wis": 3, "con": 6},
    "hitroll": 0, "damroll": 0, "AC": 100,
    "damage": (1, 3, 0),
    "gold": 0, "loot": [],
    "respawn": 30000,
}
MOB_TEMPLATES[M_FOX] = {
    "name": "Fox",
    "desc": "A slender fox with sharp eyes watches you warily.",
    "level": 1,
    "hp_dice": (1, 1, 12),
    "perm_stat": {"str": 8, "dex": 12, "int": 6, "wis": 6, "con": 8},
    "hitroll": 0, "damroll": 1, "AC": 80,
    "damage": (1, 3, 1),
    "gold": 0, "loot": [],
    "respawn": 30000,
}
MOB_TEMPLATES[M_LIZARD] = {
    "name": "Lizard",
    "desc": "A large lizard slithers toward you.",
    "level": 2,
    "hp_dice": (2, 2, 20),
    "perm_stat": {"str": 10, "dex": 10, "int": 3, "wis": 3, "con": 10},
    "hitroll": 0, "damroll": 0, "AC": 80,
    "damage": (1, 4, 1),
    "gold": 0, "loot": [],
    "respawn": 60000,
}
MOB_TEMPLATES[M_BOAR] = {
    "name": "Boar",
    "desc": "A stocky boar snorts and paws the ground.",
    "level": 3,
    "hp_dice": (3, 3, 30),
    "perm_stat": {"str": 13, "dex": 8, "int": 3, "wis": 3, "con": 13},
    "hitroll": 0, "damroll": 1, "AC": 70,
    "damage": (1, 6, 1),
    "gold": 0, "loot": [],
    "respawn": 90000,
}
MOB_TEMPLATES[M_BEAR] = {
    "name": "Bear",
    "desc": "A large bear rears up and growls at you.",
    "level": 4,
    "hp_dice": (4, 4, 44),
    "perm_stat": {"str": 16, "dex": 8, "int": 5, "wis": 5, "con": 16},
    "hitroll": 0, "damroll": 1, "AC": 60,
    "damage": (1, 6, 2),
    "gold": 0, "loot": [],
    "respawn": 120000,
}
MOB_TEMPLATES[M_WOLF] = {
    "name": "Wolf",
    "desc": "A grey wolf snarls, hackles raised.",
    "level": 4,
    "hp_dice": (4, 4, 44),
    "perm_stat": {"str": 13, "dex": 13, "int": 6, "wis": 6, "con": 13},
    "hitroll": 0, "damroll": 0, "AC": 70,
    "damage": (1, 6, 2),
    "gold": 0, "loot": [],
    "respawn": 120000,
}
MOB_TEMPLATES[M_BEAST] = {
    "name": "Beast",
    "desc": "A hulking creature lunges toward you.",
    "level": 5,
    "hp_dice": (5, 5, 55),
    "perm_stat": {"str": 17, "dex": 11, "int": 5, "wis": 5, "con": 17},
    "hitroll": 0, "damroll": 1, "AC": 50,
    "damage": (1, 6, 3),
    "gold": 0, "loot": [],
    "respawn": 180000,
}

# Initial mob placement.
# reset_area() initialises full instance data from MOB_TEMPLATES.
MOB_INIT = {
    1: {"tpl": M_RAT,    "room": R_DUNGEON_ENTRANCE},
    2: {"tpl": M_GOBLIN, "room": R_DUNGEON_HALL},
    3: {"tpl": M_RAT,    "room": R_DUNGEON_HALL},
    4: {"tpl": M_DUMMY,  "room": R_TRAINING_ROOM},
}

MOB_INIT[5]  = {"tpl": M_SNAIL,  "room": R_ARENA_SW}
MOB_INIT[6]  = {"tpl": M_SNAIL,  "room": R_ARENA_SW}
MOB_INIT[7]  = {"tpl": M_SNAIL,  "room": R_ARENA_SW}
MOB_INIT[8]  = {"tpl": M_SNAIL,  "room": R_ARENA_SW}
MOB_INIT[9]  = {"tpl": M_SNAIL,  "room": R_ARENA_SW}
MOB_INIT[10] = {"tpl": M_FOX,    "room": R_ARENA_SE}
MOB_INIT[11] = {"tpl": M_FOX,    "room": R_ARENA_SE}
MOB_INIT[12] = {"tpl": M_FOX,    "room": R_ARENA_SE}
MOB_INIT[13] = {"tpl": M_RABBIT, "room": R_ARENA_CENTER}
MOB_INIT[14] = {"tpl": M_RABBIT, "room": R_ARENA_CENTER}
MOB_INIT[15] = {"tpl": M_RABBIT, "room": R_ARENA_CENTER}
MOB_INIT[16] = {"tpl": M_RABBIT, "room": R_ARENA_CENTER}
MOB_INIT[17] = {"tpl": M_LIZARD, "room": R_ARENA_NW}
MOB_INIT[18] = {"tpl": M_LIZARD, "room": R_ARENA_NW}
MOB_INIT[19] = {"tpl": M_LIZARD, "room": R_ARENA_NW}
MOB_INIT[20] = {"tpl": M_BOAR,   "room": R_ARENA_NE}
MOB_INIT[21] = {"tpl": M_BOAR,   "room": R_ARENA_NE}
MOB_INIT[22] = {"tpl": M_BOAR,   "room": R_ARENA_NE}
MOB_INIT[23] = {"tpl": M_BEAST,  "room": R_DUNGEON_NW}
MOB_INIT[24] = {"tpl": M_BEAR,   "room": R_DUNGEON_NE}
MOB_INIT[25] = {"tpl": M_BEAR,   "room": R_DUNGEON_NE}
MOB_INIT[26] = {"tpl": M_WOLF,   "room": R_DUNGEON_SW}
MOB_INIT[27] = {"tpl": M_WOLF,   "room": R_DUNGEON_SW}

# ── Skills ───────────────────────
# type:
#   "internal"  — auto-attack, not manually triggered
#   "active"    — manually triggered; has mp_cost and beats (skill lag in pulses)
#   "weapon"    — weapon proficiency; affects damage/accuracy in one_hit
#   "passive"   — passive combat skill; checked automatically each round
#
# beats: skill lag in pulses (PULSE_VIOLENCE = 12 = one full combat round)
#
# Improvement tuning (cf. 1stMud check_improve in skills.c):
#   rating     — intrinsic difficulty of the skill (1stMud: per-class cost from
#                skills.dat; here we use the minimum non-zero class value so a
#                classless player trains at the rate of the most natural class).
#                Higher = harder to improve. Multiplied into the improvement gate.
#   multiplier — context in which the skill is trained (1stMud: passed by each
#                check_improve call site in fight.c). Encodes how demanding the
#                training opportunity is: 1 for always-succeeding active skills,
#                5 for normal weapon/attack use, 6 for harder passive skills.
#                Higher = fewer improvement rolls per use.
#   Gate formula: chance = 10*INT_learn / (multiplier * rating * 4) + level
#   Roll 1..1000 — improvement only proceeds when roll <= chance.
SKILLS = {
    SK_ATTACK: {
        "name": "attack", "type": "internal",
    },
    # Active skills: rating/multiplier kept low — player-triggered, always succeed
    SK_SLASH: {
        "name": "slash", "type": "active",
        "effect": "weapon_strike", "bonus_damroll": 5,
        "mp_cost": 4, "beats": 12,
        "rating": 1, "multiplier": 1,
    },
    SK_HEAL: {
        "name": "heal", "type": "active",
        "effect": "heal", "power": 25,
        "mp_cost": 6, "beats": 12,
        "rating": 1, "multiplier": 1,
    },
    SK_WEAKEN: {
        "name": "weaken", "type": "active",
        "effect": "debuff", "stat": "hitroll", "amount": 3, "turns": 2,
        "mp_cost": 5, "beats": 12,
        "rating": 1, "multiplier": 1,
    },
    # Weapon proficiencies: multiplier=5 (cf. fight.c one_hit), rating from skills.dat minimum
    SK_UNARMED: {"name": "unarmed",  "type": "weapon", "rating": 4, "multiplier": 5},
    SK_SWORD:   {"name": "sword",    "type": "weapon", "rating": 2, "multiplier": 5},
    SK_DAGGER:  {"name": "dagger",   "type": "weapon", "rating": 2, "multiplier": 5},
    # Passive skills: multipliers and ratings from fight.c / skills.dat
    SK_SECOND_ATTACK: {"name": "second attack",   "type": "passive", "rating": 3, "multiplier": 5},
    SK_THIRD_ATTACK:  {"name": "third attack",    "type": "passive", "rating": 4, "multiplier": 6},
    SK_DODGE:         {"name": "dodge",           "type": "passive", "rating": 4, "multiplier": 6},
    SK_PARRY:         {"name": "parry",           "type": "passive", "rating": 4, "multiplier": 6},
    SK_SHIELD_BLOCK:  {"name": "shield block",    "type": "passive", "rating": 2, "multiplier": 6},
    SK_ENHANCED_DMG:  {"name": "enhanced damage", "type": "passive", "rating": 3, "multiplier": 6},
}
