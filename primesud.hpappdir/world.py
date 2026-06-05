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
        "exits": {"s": R_VILLAGE_SQUARE},
    },
}

# Initial item and mob placement per room.
# Copied into mutable room_state at game start — do not mutate these directly.
ROOM_INIT = {
    R_VILLAGE_SQUARE:   {"items": [],          "mobs": []},
    R_DUNGEON_ENTRANCE: {"items": [I_DAGGER],  "mobs": [1]},
    R_DUNGEON_HALL:     {"items": [],          "mobs": [2, 3]},
    R_TRAINING_ROOM:    {"items": [],          "mobs": [4]},
}

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
        "hp_max": 8,
        "perm_stat": {"str": 8, "dex": 12, "int": 2, "wis": 2, "con": 8},
        "hitroll": 0, "damroll": 0, "AC": 100,
        "damage": (1, 3, 0),
        "xp": 10, "gold": 1,
        "loot": [(I_POTION_HP, 15)],
        "ai": "aggressive",
        "respawn": 30000,
    },
    M_GOBLIN: {
        "name": "Goblin",
        "desc": "A snarling creature clutching a rusty knife.",
        "level": 3,
        "hp_max": 18,
        "perm_stat": {"str": 11, "dex": 11, "int": 8, "wis": 6, "con": 10},
        "hitroll": 0, "damroll": 1, "AC": 70,
        "damage": (1, 5, 1),
        "xp": 30, "gold": 5,
        "loot": [(I_DAGGER, 20), (I_POTION_HP, 25)],
        "ai": "aggressive",
        "respawn": 60000,
    },
    M_DUMMY: {
        "name": "Training Dummy",
        "desc": "A battered wooden dummy bolted to a post.",
        "level": 1,
        "hp_max": 500,
        "perm_stat": {"str": 10, "dex": 10, "int": 10, "wis": 10, "con": 10},
        "hitroll": -100, "damroll": 0, "AC": 100,
        "damage": (1, 1, 0),
        "xp": 0, "gold": 0,
        "loot": [],
        "ai": "passive",
        "respawn": 5000,
    },
}

# Initial mob placement.
# reset_area() initialises full instance data from MOB_TEMPLATES.
MOB_INIT = {
    1: {"tpl": M_RAT,    "room": R_DUNGEON_ENTRANCE},
    2: {"tpl": M_GOBLIN, "room": R_DUNGEON_HALL},
    3: {"tpl": M_RAT,    "room": R_DUNGEON_HALL},
    4: {"tpl": M_DUMMY,  "room": R_TRAINING_ROOM},
}

# ── Skills ───────────────────────
# type:
#   "internal"  — auto-attack, not manually triggered
#   "active"    — manually triggered; has mp_cost and beats (skill lag in pulses)
#   "weapon"    — weapon proficiency; affects damage/accuracy in one_hit
#   "passive"   — passive combat skill; checked automatically each round
#
# beats: skill lag in pulses (PULSE_VIOLENCE = 12 = one full combat round)
SKILLS = {
    SK_ATTACK: {
        "name": "attack", "type": "internal",
    },
    SK_SLASH: {
        "name": "slash", "type": "active",
        "effect": "weapon_strike", "bonus_damroll": 5,
        "mp_cost": 4, "beats": 12,
    },
    SK_HEAL: {
        "name": "heal", "type": "active",
        "effect": "heal", "power": 25,
        "mp_cost": 6, "beats": 12,
    },
    SK_WEAKEN: {
        "name": "weaken", "type": "active",
        "effect": "debuff", "stat": "hitroll", "amount": 3, "turns": 2,
        "mp_cost": 5, "beats": 12,
    },
    SK_UNARMED: {"name": "unarmed",  "type": "weapon"},
    SK_SWORD:   {"name": "sword",    "type": "weapon"},
    SK_DAGGER:  {"name": "dagger",   "type": "weapon"},
    SK_SECOND_ATTACK: {"name": "second attack",   "type": "passive"},
    SK_THIRD_ATTACK:  {"name": "third attack",    "type": "passive"},
    SK_DODGE:         {"name": "dodge",           "type": "passive"},
    SK_PARRY:         {"name": "parry",           "type": "passive"},
    SK_SHIELD_BLOCK:  {"name": "shield block",    "type": "passive"},
    SK_ENHANCED_DMG:  {"name": "enhanced damage", "type": "passive"},
}
