# fmt: off
# Area: Limbo
# Builders: None
# VNUM ranges: Rooms 1-99
# Credits: Diku


AREA = {
    "name":     'Limbo',
    "builders": 'None',
    "vnums":    (1, 99),
    "credits":  'Diku',
    "levels":   (1, 10),
    "version":  4,
}

# ── Room VNUMs ─────────────────────────────────────────────────────────────────
R_VOID                             = 1
R_LIMBO                            = 2
R_MORGUE                           = 3

# ── Mob template VNUMs ─────────────────────────────────────────────────────────
M_DUMMY_MOB                        = 30

# ── Item template VNUMs ────────────────────────────────────────────────────────
I_COIN_SILVER_GCASH                = 1
I_COIN_GOLD_GCASH                  = 2
I_COINS_GOLD_GCASH                 = 3
I_COINS_SILVER_GCASH               = 4
I_COINS_SILVER_GOLD_GCASH          = 5
I_CORPSE                           = 10
I_CORPSE_11                        = 11
I_HEAD                             = 12
I_HEART                            = 13
I_ARM                              = 14
I_LEG                              = 15
I_GUTS_ENTRAILS                    = 16
I_BRAINS_BRAIN                     = 17
I_MUSHROOM                         = 20
I_BALL_LIGHT                       = 21
I_SPRING                           = 22
I_DISC_DISK_FLOATING_BLACK         = 23
I_GATE_PORTAL                      = 25
I_DUMMY_OBJECT                     = 30

# ── Mob templates ──────────────────────────────────────────────────────────────
# hp_dice / mana_dice / damage: (num_dice, die_size, bonus)
# AC: avg(pierce,bash,slash,exotic) / 10 per REFERENCE.md  # TODO: verify scale
# hitroll: from level line; no separate damroll in .are (dam_dice bonus is it)
MOBILES = {
    M_DUMMY_MOB: {
        "keywords":    'dummy mob',
        "short_descr": 'a dummy mobile',
        "long_descr":  'A dummy mobile is here.',
        "description": '',
        "race":        'Human',
        "act_flags": {"sentinel": True},
        "alignment": 0,
        "level":     60,
        "hitroll":   59,
        "hp_dice":   (85, 71, 1073),
        "mana_dice": (62, 8, 61),
        "damage":    (7, 12, 48),  "dam_type": 'none',
        "AC":        -5,
        "sex":  'either',
        "gold": 0,
        "size": 'medium',
    },
}

# ── Rooms ──────────────────────────────────────────────────────────────────────
ROOMS = {
    R_VOID: {
        "name": 'The Void',
        "desc": 'You are floating in nothing.',
        "exits": {
        },
        "flags": {"no_mob": True, "indoors": True},
        "sector": 'city',
    },
    R_LIMBO: {
        "name": 'Limbo',
        "desc": 'You are floating in a formless void, detached from all sensation of physical\nmatter, surrounded by swirling glowing light, which fades into the relative\ndarkness around you without any trace of edges or shadow.\n   There is a "No Tipping" notice pinned to the darkness.',
        "exits": {
            "u": 3001,
        },
        "flags": {"indoors": True},
        "sector": 'city',
    },
    R_MORGUE: {
        "name": 'The Morgue',
        "desc": 'Here lies marble tabletops holding coffins and empty bodies.',
        "exits": {
            "u": 3054,
        },
        "flags": {"indoors": True, "safe": True, "law": True, "save_objs": True},
        "sector": 'inside',
    },
}

# ── Item templates ─────────────────────────────────────────────────────────────
OBJECTS = {
    I_COIN_SILVER_GCASH: {
        "keywords":    'coin silver gcash',
        "short_descr": 'A silver coin',
        "description": 'One miserable silver coin.',
        "material":    'silver',
        "type": 'money',
        "wear_flags": {"take": True},
        "level": 0, "weight": 10, "value": 0,
    },
    I_COIN_GOLD_GCASH: {
        "keywords":    'coin gold gcash',
        "short_descr": 'A gold coin',
        "description": 'One valuable gold coin.',
        "material":    'gold',
        "type": 'money',
        "wear_flags": {"take": True},
        "level": 0, "weight": 10, "value": 0,
    },
    I_COINS_GOLD_GCASH: {
        "keywords":    'coins gold gcash',
        "short_descr": '%d gold coins',
        "description": 'A pile of gold coins.',
        "material":    'gold',
        "type": 'money',
        "wear_flags": {"take": True},
        "level": 0, "weight": 10, "value": 0,
    },
    I_COINS_SILVER_GCASH: {
        "keywords":    'coins silver gcash',
        "short_descr": '%d silver coins',
        "description": 'A pile of silver coins.',
        "material":    'silver',
        "type": 'money',
        "wear_flags": {"take": True},
        "level": 0, "weight": 10, "value": 0,
    },
    I_COINS_SILVER_GOLD_GCASH: {
        "keywords":    'coins silver gold gcash',
        "short_descr": '%d silver coins and %d gold coins',
        "description": 'A pile of coins.',
        "material":    'gold',
        "type": 'money',
        "wear_flags": {"take": True},
        "level": 0, "weight": 10, "value": 0,
    },
    I_CORPSE: {
        "keywords":    'corpse',
        "short_descr": 'The corpse of %s',
        "description": 'The corpse of %s is lying here.',
        "material":    'meat',
        "type": 'npc_corpse',
        "wear_flags": {"take": True},
        "level": 0, "weight": 1000, "value": 0,
    },
    I_CORPSE_11: {
        "keywords":    'corpse',
        "short_descr": 'The corpse of %s',
        "description": 'The corpse of %s is lying here.',
        "material":    'meat',
        "type": 'pc_corpse',
        "wear_flags": {"take": True},
        "extra_flags": {"nopurge": True},
        "level": 0, "weight": 1000, "value": 0,
    },
    I_HEAD: {
        "keywords":    'head',
        "short_descr": 'The head of %s',
        "description": 'The severed head of %s is lying here.',
        "material":    'meat',
        "type": 'trash',
        "wear_flags": {"take": True},
        "level": 0, "weight": 50, "value": 0,
    },
    I_HEART: {
        "keywords":    'heart',
        "short_descr": 'The heart of %s',
        "description": 'The torn-out heart of %s is lying here.',
        "material":    'meat',
        "type": 'food',
        "wear_flags": {"take": True},
        "level": 0, "weight": 20, "value": 0,
    },
    I_ARM: {
        "keywords":    'arm',
        "short_descr": 'The arm of %s',
        "description": 'The sliced-off arm of %s is lying here.',
        "material":    'meat',
        "type": 'food',
        "wear_flags": {"take": True},
        "level": 0, "weight": 50, "value": 0,
    },
    I_LEG: {
        "keywords":    'leg',
        "short_descr": 'The leg of %s',
        "description": 'The sliced-off leg of %s is lying here.',
        "material":    'meat',
        "type": 'food',
        "wear_flags": {"take": True},
        "level": 0, "weight": 50, "value": 0,
    },
    I_GUTS_ENTRAILS: {
        "keywords":    'guts entrails',
        "short_descr": 'The guts of %s',
        "description": "A steaming pile of %s's entrails is lying here.",
        "material":    'meat',
        "type": 'food',
        "wear_flags": {"take": True},
        "level": 0, "weight": 20, "value": 0,
    },
    I_BRAINS_BRAIN: {
        "keywords":    'brains brain',
        "short_descr": 'The brains of %s',
        "description": 'The splattered brains of %s are lying here.',
        "material":    'meat',
        "type": 'food',
        "wear_flags": {"take": True},
        "level": 0, "weight": 20, "value": 0,
    },
    I_MUSHROOM: {
        "keywords":    'mushroom',
        "short_descr": 'A Magic Mushroom',
        "description": 'A delicious magic mushroom is here.',
        "material":    'food',
        "type": 'food',
        "wear_flags": {"take": True},
        "level": 0, "weight": 10, "value": 0,
    },
    I_BALL_LIGHT: {
        "keywords":    'ball light',
        "short_descr": 'A bright ball of light',
        "description": 'A bright ball of light shimmers in the air.',
        "material":    'energy',
        "type": 'light',
        "wear_flags": {"take": True},
        "extra_flags": {"glow": True},
        "level": 0, "weight": 0, "value": 0,
    },
    I_SPRING: {
        "keywords":    'spring',
        "short_descr": 'A magical spring',
        "description": 'A magical spring flows from the ground here.',
        "material":    'water',
        "type": 'fountain',
        "wear_flags": {},
        "extra_flags": {"magic": True},
        "level": 0, "weight": 0, "value": 0,
    },
    I_DISC_DISK_FLOATING_BLACK: {
        "keywords":    'disc disk floating black',
        "short_descr": 'A floating disc',
        "description": 'A floating black disc hangs in the air.',
        "material":    'energy',
        "type": 'container',
        "wear_flags": {"take": True, "float": True},
        "extra_flags": {"magic": True, "noremove": True, "rot_death": True, "melt_drop": True, "burn_proof": True, "nouncurse": True},
        "level": 0, "weight": 0, "value": 0,
    },
    I_GATE_PORTAL: {
        "keywords":    'gate portal',
        "short_descr": 'A shimmering gate',
        "description": 'A shimmering black gate rises from the ground, leading to parts unknown.',
        "material":    'shadow',
        "type": 'portal',
        "wear_flags": {},
        "extra_flags": {"magic": True, "nopurge": True, "nolocate": True},
        "level": 0, "weight": 0, "value": 0,
    },
    I_DUMMY_OBJECT: {
        "keywords":    'dummy object',
        "short_descr": 'A dummy object',
        "description": 'Dummy object is used for loading non-existent objects',
        "material":    '',
        "type": 'trash',
        "wear_flags": {},
        "level": 0, "weight": 0, "value": 0,
    },
}

# ── Resets ─────────────────────────────────────────────────────────────────────
# ("M", mob_vnum, global_limit, room_vnum, room_limit) — spawn mob up to limits
# ("O", item_vnum, room_vnum)                          — place one item copy in room
# ("E", item_vnum, slot_name)                          — equip item on last M mob
# ("G", item_vnum)                                     — give item to last M mob inventory
# ("P", item_vnum, limit, container_vnum, max)         — [PRIMESUD] deferred: no containers
# ("R", room_vnum, num_dirs)                           — [PRIMESUD] deferred: unused in current areas
# F and D .are resets are baked into room exit flags at conversion time
RESETS = (
    ("O", 3415, R_MORGUE),
    ("R", R_MORGUE, 1),
)
