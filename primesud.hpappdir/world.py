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
SK_ATTACK = 4000
SK_SLASH  = 4001
SK_HEAL   = 4002
SK_WEAKEN = 4003

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
ITEM_TEMPLATES = {
    I_SWORD_IRON: {
        "name": "Iron Sword",
        "desc": "A serviceable iron sword, nicked but solid.",
        "type": "weapon", "slot": "weapon",
        "weight": 4, "stats": {"atk": 5}, "value": 20,
    },
    I_DAGGER: {
        "name": "Dagger",
        "desc": "A short blade, easy to conceal.",
        "type": "weapon", "slot": "weapon",
        "weight": 1, "stats": {"atk": 2}, "value": 8,
    },
    I_POTION_HP: {
        "name": "Health Potion",
        "desc": "A small vial of red liquid. Restores HP when drunk.",
        "type": "consumable", "slot": None,
        "weight": 1, "stats": {}, "use_hp": 25, "value": 15,
    },
}

# ── Mob templates ────────────────
MOB_TEMPLATES = {
    M_RAT: {
        "name": "Giant Rat",
        "desc": "A rat the size of a terrier, teeth bared.",
        "hp_max": 8, "atk": 3, "def": 0,
        "xp": 10, "gold": 1,
        "loot": [(I_POTION_HP, 15)],   # (item VNUM, drop chance %)
        "ai": "aggressive",
        "respawn": 30000,              # ms until respawn after death (0 = no respawn)
    },
    M_GOBLIN: {
        "name": "Goblin",
        "desc": "A snarling creature clutching a rusty knife.",
        "hp_max": 18, "atk": 6, "def": 2,
        "xp": 30, "gold": 5,
        "loot": [(I_DAGGER, 20), (I_POTION_HP, 25)],
        "ai": "aggressive",
        "respawn": 60000,
    },
    M_DUMMY: {
        "name": "Training Dummy",
        "desc": "A battered wooden dummy bolted to a post.",
        "hp_max": 500, "atk": 0, "def": 0,
        "xp": 0, "gold": 0,
        "loot": [],
        "ai": "passive",
        "respawn": 5000,
    },
}

# Initial mob instance table.
# Copied into mutable mob_instances at game start.
MOB_INIT = {
    1: {"tpl": M_RAT,    "hp": 8,   "room": R_DUNGEON_ENTRANCE, "state": "idle", "respawn_at": 0},
    2: {"tpl": M_GOBLIN, "hp": 18,  "room": R_DUNGEON_HALL,     "state": "idle", "respawn_at": 0},
    3: {"tpl": M_RAT,    "hp": 8,   "room": R_DUNGEON_HALL,     "state": "idle", "respawn_at": 0},
    4: {"tpl": M_DUMMY,  "hp": 500, "room": R_TRAINING_ROOM,    "state": "idle", "respawn_at": 0},
}

# ── Skills ───────────────────────
SKILLS = {
    SK_ATTACK: {"name": "Attack", "mp_cost": 0,  "effect": "damage", "target": "enemy", "power": 10},
    SK_SLASH:  {"name": "Slash",  "mp_cost": 4,  "effect": "damage", "target": "enemy", "power": 18},
    SK_HEAL:   {"name": "Heal",   "mp_cost": 6,  "effect": "heal",   "target": "self",  "power": 25},
    SK_WEAKEN: {"name": "Weaken", "mp_cost": 5,  "effect": "debuff", "target": "enemy",
                "stat": "atk", "amount": 3, "turns": 2},
}
