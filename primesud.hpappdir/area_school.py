# fmt: off
# Area: Mud School (starter area)
# VNUM ranges: Rooms 1000–1199, Mobs 2000–2099, Items 3000–3099, Skills 4000–4099

from world_consts import GSN_KICK, GSN_PARRY

AREA = {"name": "Mud School", "vnums": (1000, 1199), "levels": (1, 5)}

# ── Room VNUMs ────────────────────────────────────────────────────────────────
R_VILLAGE_SQUARE   = 1000
R_DUNGEON_ENTRANCE = 1001
R_DUNGEON_HALL     = 1002
R_TRAINING_ROOM    = 1003
# Arena 5×5 grid: VNUM = 1100 + row*5 + col (row 0=south, col 0=west)
R_ARENA_ENTRY      = 1102   # row 0 col 2 — south-centre, entrance from Training Room
R_ARENA_SW         = 1100   # row 0 col 0 — snails
R_ARENA_SE         = 1104   # row 0 col 4 — foxes
R_ARENA_CENTER     = 1112   # row 2 col 2 — rabbits; down → dungeon
R_ARENA_NW         = 1120   # row 4 col 0 — lizards
R_ARENA_NE         = 1124   # row 4 col 4 — boars
R_ARENA_SAFE       = 1125   # safe room (up from all arena cells)
R_DUNGEON_C        = 1126   # dungeon centre — up → R_ARENA_CENTER
R_DUNGEON_NW       = 1127   # beast
R_DUNGEON_N        = 1128
R_DUNGEON_NE       = 1129   # bears
R_DUNGEON_W        = 1130
R_DUNGEON_E        = 1131
R_DUNGEON_SW       = 1132   # wolves
R_DUNGEON_S        = 1133
R_DUNGEON_SE       = 1134

# ── Mob template VNUMs ────────────────────────────────────────────────────────
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

# ── Item template VNUMs ───────────────────────────────────────────────────────
I_SWORD_IRON = 3000
I_POTION_HP  = 3001
I_DAGGER     = 3002

# ── Rooms ─────────────────────────────────────────────────────────────────────
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

# Arena 5×5 grid (generated)
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
        ROOMS[_v] = {"name": _arena_name(_r, _c), "short": "You are in the Arena.", "long": _AL, "exits": _ex}

ROOMS[R_ARENA_SAFE] = {
    "name":  "A Safe Room",
    "short": "You are in a safe room, away from the Arena.",
    "long":  ("You are in a safe room, away from all the mean rabbits and snails "
              "of the Arena.  You can rest here, and go down to return to the Arena."),
    "exits": {"d": R_ARENA_ENTRY},
}

for _v, _name, _ex in (
    (R_DUNGEON_C,  "The Center of the Dungeon",             {"n": R_DUNGEON_N,  "e": R_DUNGEON_E,  "s": R_DUNGEON_S,  "w": R_DUNGEON_W,  "u": R_ARENA_CENTER}),
    (R_DUNGEON_NW, "The North West Corner of the Dungeon",  {"e": R_DUNGEON_N,  "s": R_DUNGEON_W}),
    (R_DUNGEON_N,  "The North Wall of the Dungeon",         {"e": R_DUNGEON_NE, "s": R_DUNGEON_C,  "w": R_DUNGEON_NW}),
    (R_DUNGEON_NE, "The North East Corner of the Dungeon",  {"s": R_DUNGEON_E,  "w": R_DUNGEON_N}),
    (R_DUNGEON_W,  "The West Wall of the Dungeon",          {"n": R_DUNGEON_NW, "e": R_DUNGEON_C,  "s": R_DUNGEON_SW}),
    (R_DUNGEON_E,  "The East Wall of the Dungeon",          {"n": R_DUNGEON_NE, "s": R_DUNGEON_SE, "w": R_DUNGEON_C}),
    (R_DUNGEON_SW, "The South West Corner of the Dungeon",  {"n": R_DUNGEON_W,  "e": R_DUNGEON_S}),
    (R_DUNGEON_S,  "The South Wall of the Dungeon",         {"n": R_DUNGEON_C,  "e": R_DUNGEON_SE, "w": R_DUNGEON_SW}),
    (R_DUNGEON_SE, "The South East Corner of the Dungeon",  {"n": R_DUNGEON_E,  "w": R_DUNGEON_S}),
):
    _dl = _DL_C if _v == R_DUNGEON_C else _DL
    _ds = ("You are in the center of the dungeon." if _v == R_DUNGEON_C
           else "You are against a wall in the dungeon.")
    ROOMS[_v] = {"name": _name, "short": _ds, "long": _dl, "exits": _ex}

# ── Mob templates ─────────────────────────────────────────────────────────────
# perm_stat: base attributes (str/dex/int/wis/con)
# hitroll/damroll: base combat bonuses (before stat application)
# AC: base armour class (100 = unarmored; negative = better)
# damage: (num_dice, die_size, bonus) — natural attack
MOBILES = {
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
        "off_flags": {"kick": True},
        "skills": {GSN_KICK: 75},
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
    M_SNAIL: {
        "name": "Snail",
        "desc": "A tiny snail oozes slowly across the ground.",
        "level": 0,
        "hp_dice": (1, 1, 0),
        "perm_stat": {"str": 4, "dex": 4, "int": 1, "wis": 1, "con": 4},
        "hitroll": 0, "damroll": 0, "AC": 100,
        "damage": (1, 1, 0),
        "gold": 0, "loot": [],
        "respawn": 20000,
    },
    M_RABBIT: {
        "name": "Rabbit",
        "desc": "A fluffy rabbit hops around, completely harmless.",
        "level": 1,
        "hp_dice": (1, 1, 10),
        "perm_stat": {"str": 6, "dex": 14, "int": 3, "wis": 3, "con": 6},
        "hitroll": 0, "damroll": 0, "AC": 100,
        "damage": (1, 3, 0),
        "gold": 0, "loot": [],
        "respawn": 30000,
    },
    M_FOX: {
        "name": "Fox",
        "desc": "A slender fox with sharp eyes watches you warily.",
        "level": 1,
        "hp_dice": (1, 1, 12),
        "perm_stat": {"str": 8, "dex": 12, "int": 6, "wis": 6, "con": 8},
        "hitroll": 0, "damroll": 1, "AC": 80,
        "damage": (1, 3, 1),
        "gold": 0, "loot": [],
        "respawn": 30000,
    },
    M_LIZARD: {
        "name": "Lizard",
        "desc": "A large lizard slithers toward you.",
        "level": 2,
        "hp_dice": (2, 2, 20),
        "perm_stat": {"str": 10, "dex": 10, "int": 3, "wis": 3, "con": 10},
        "hitroll": 0, "damroll": 0, "AC": 80,
        "damage": (1, 4, 1),
        "gold": 0, "loot": [],
        "respawn": 60000,
    },
    M_BOAR: {
        "name": "Boar",
        "desc": "A stocky boar snorts and paws the ground.",
        "level": 3,
        "hp_dice": (3, 3, 30),
        "perm_stat": {"str": 13, "dex": 8, "int": 3, "wis": 3, "con": 13},
        "hitroll": 0, "damroll": 1, "AC": 70,
        "damage": (1, 6, 1),
        "gold": 0, "loot": [],
        "respawn": 90000,
    },
    M_BEAR: {
        "name": "Bear",
        "desc": "A large bear rears up and growls at you.",
        "level": 4,
        "hp_dice": (4, 4, 44),
        "perm_stat": {"str": 16, "dex": 8, "int": 5, "wis": 5, "con": 16},
        "hitroll": 0, "damroll": 1, "AC": 60,
        "damage": (1, 6, 2),
        "gold": 0, "loot": [],
        "respawn": 120000,
        "off_flags": {"kick": True},
        "skills": {GSN_KICK: 75},
    },
    M_WOLF: {
        "name": "Wolf",
        "desc": "A grey wolf snarls, hackles raised.",
        "level": 4,
        "hp_dice": (4, 4, 44),
        "perm_stat": {"str": 13, "dex": 13, "int": 6, "wis": 6, "con": 13},
        "hitroll": 0, "damroll": 0, "AC": 70,
        "damage": (1, 6, 2),
        "gold": 0, "loot": [],
        "respawn": 120000,
        "off_flags": {"kick": True},
        "skills": {GSN_KICK: 75},
    },
    M_BEAST: {
        "name": "Beast",
        "desc": "A hulking creature lunges toward you.",
        "level": 5,
        "hp_dice": (5, 5, 55),
        "perm_stat": {"str": 17, "dex": 11, "int": 5, "wis": 5, "con": 17},
        "hitroll": 0, "damroll": 1, "AC": 50,
        "damage": (1, 6, 3),
        "gold": 0, "loot": [],
        "respawn": 180000,
        "off_flags": {"kick": True},
        "skills": {GSN_KICK: 75},
    },
}

# ── Item templates ────────────────────────────────────────────────────────────
# Weapons: dice=(num,size,bonus) — damage roll; weapon_type — proficiency link
# Armour:  AC — contribution to worn AC (negative = better)
OBJECTS = {
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

# ── Resets ────────────────────────────────────────────────────────────────────
# Sequential spawn/placement script run by reset_area() (cf. 1stMud #RESETS).
# ("M", mob_template_vnum, room_vnum) — place one mob instance
# ("O", item_template_vnum, room_vnum) — place one item copy in room
# Processing order determines mob instance IDs (first M gets ID 1, etc.).
RESETS = (
    # Core area mobs (IDs 1–4)
    ("M", M_RAT,    R_DUNGEON_ENTRANCE),
    ("M", M_GOBLIN, R_DUNGEON_HALL),
    ("M", M_RAT,    R_DUNGEON_HALL),
    ("M", M_DUMMY,  R_TRAINING_ROOM),
    # Arena: south-west — snails (IDs 5–9)
    ("M", M_SNAIL,  R_ARENA_SW),
    ("M", M_SNAIL,  R_ARENA_SW),
    ("M", M_SNAIL,  R_ARENA_SW),
    ("M", M_SNAIL,  R_ARENA_SW),
    ("M", M_SNAIL,  R_ARENA_SW),
    # Arena: south-east — foxes (IDs 10–12)
    ("M", M_FOX,    R_ARENA_SE),
    ("M", M_FOX,    R_ARENA_SE),
    ("M", M_FOX,    R_ARENA_SE),
    # Arena: center — rabbits (IDs 13–16)
    ("M", M_RABBIT, R_ARENA_CENTER),
    ("M", M_RABBIT, R_ARENA_CENTER),
    ("M", M_RABBIT, R_ARENA_CENTER),
    ("M", M_RABBIT, R_ARENA_CENTER),
    # Arena: north-west — lizards (IDs 17–19)
    ("M", M_LIZARD, R_ARENA_NW),
    ("M", M_LIZARD, R_ARENA_NW),
    ("M", M_LIZARD, R_ARENA_NW),
    # Arena: north-east — boars (IDs 20–22)
    ("M", M_BOAR,   R_ARENA_NE),
    ("M", M_BOAR,   R_ARENA_NE),
    ("M", M_BOAR,   R_ARENA_NE),
    # Dungeon mobs (IDs 23–27)
    ("M", M_BEAST,  R_DUNGEON_NW),
    ("M", M_BEAR,   R_DUNGEON_NE),
    ("M", M_BEAR,   R_DUNGEON_NE),
    ("M", M_WOLF,   R_DUNGEON_SW),
    ("M", M_WOLF,   R_DUNGEON_SW),
    # Items
    ("O", I_DAGGER, R_DUNGEON_ENTRANCE),
)
