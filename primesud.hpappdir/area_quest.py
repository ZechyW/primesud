# fmt: off
# Area: Quest
# Builders: None
# VNUM ranges: Rooms 200-249
# Credits: 1stMud


AREA = {
    "name":     'Quest',
    "builders": 'None',
    "vnums":    (200, 249),
    "credits":  '1stMud',
    "levels":   (1, 10),
    "version":  4,
}

# -- Room VNUMs -----------------------------------------------------------------
R_QUESTORS_LOUNGE                  = 200
R_REGISTAR_S_OFFICE                = 201
R_TRIVIA_SHOP                      = 202

# -- Mob template VNUMs ---------------------------------------------------------
M_EDURIN_QUESTMASTER_QUESTOR       = 200
M_TRIVIA_SHOPKEEPER                = 201
M_200_REGISTRAR_GQUEST             = 202

# -- Item template VNUMs --------------------------------------------------------
I_TRIVIA_PILL                      = 200
I_QUEST_AURA_SANCTUARY             = 201
I_SWORD_QUEST_ANCIENT              = 203
I_BREASTPLATE_QUEST_ANCIENT        = 204
I_BOOTS_QUEST_ANCIENT              = 205
I_GLOVES_QUEST_PROTECTION          = 206
I_FLAME_QUEST_ANCIENTS             = 207
I_QUEST_HELM_TRUE_SIGHT            = 208
I_BAG_QUEST_ANCIENT                = 209
I_SHIELD_QUEST_ANCIENT             = 210
I_QUEST_RING_REGENERATION          = 211
I_QUEST_RING_INVISIBILITY          = 212
I_DRAGON_EYE                       = 214
I_EAGLE_CLAW                       = 215
I_RABBIT_FOOT                      = 216
I_WOLF_TOOTH                       = 217

# -- Mob templates --------------------------------------------------------------
# hp_dice / mana_dice / damage: (num_dice, die_size, bonus)
# AC: avg(pierce,bash,slash,exotic), raw .are units; create_mobile applies x10
# hitroll: from level line; no separate damroll in .are (dam_dice bonus is it)
MOBILES = {
    M_EDURIN_QUESTMASTER_QUESTOR: {
        "keywords":    'Edurin Questmaster Questor',
        "short_descr": 'Edurin',
        "long_descr":  'Edurin the Questmaster is sitting at a table here.',
        "description": '',
        "race":        'Elf',
        "act_flags": {"sentinel": True, "stay_area": True, "thief": True, "nopurge": True, "_unknown_bits": [11, 31]},
        "aff_flags": {"detect_invis": True, "detect_hidden": True, "sanctuary": True, "infrared": True},
        "alignment": 0,
        "level":     205,
        "hitroll":   218,
        "hp_dice":   (396, 337, 17149),
        "mana_dice": (285, 13, 97),
        "damage":    (32, 14, 278),  "dam_type": 'smash',
        "AC":        -358,
        "imm_flags": {"summon": True, "magic": True, "weapon": True},
        "res_flags": {"charm": True},
        "vuln_flags": {"iron": True},
        "sex":  'male',
        "gold": 422,
        "size": 'medium',
    },
    M_TRIVIA_SHOPKEEPER: {
        "keywords":    'trivia shopkeeper',
        "short_descr": 'The Trivia Shopkeeper',
        "long_descr":  'The trivia shopkeeper is here, handing out prizes.',
        "description": '',
        "race":        'Unique',
        "act_flags": {"sentinel": True, "stay_area": True, "_unknown_bits": [31]},
        "aff_flags": {"detect_invis": True, "detect_hidden": True, "sanctuary": True, "infrared": True},
        "alignment": 0,
        "level":     92,
        "hitroll":   80,
        "hp_dice":   (130, 114, 1899),
        "mana_dice": (96, 10, 95),
        "damage":    (11, 13, 94),  "dam_type": 'smash',
        "AC":        -93,
        "imm_flags": {"magic": True, "weapon": True},
        "res_flags": {"charm": True},
        "vuln_flags": {"iron": True},
        "sex":  'male',
        "gold": 122,
        "size": 'medium',
    },
    M_200_REGISTRAR_GQUEST: {
        "keywords":    '#200\n\n\nRegistrar gquest',
        "short_descr": 'The Registrar',
        "long_descr":  'A busy looking man is here, writing in a ledger.',
        "description": '',
        "race":        'Elf',
        "act_flags": {"sentinel": True, "stay_area": True, "thief": True, "nopurge": True, "_unknown_bits": [11, 31]},
        "aff_flags": {"detect_invis": True, "detect_hidden": True, "sanctuary": True, "infrared": True},
        "alignment": 0,
        "level":     205,
        "hitroll":   218,
        "hp_dice":   (396, 337, 17149),
        "mana_dice": (285, 13, 97),
        "damage":    (32, 14, 278),  "dam_type": 'smash',
        "AC":        -358,
        "imm_flags": {"summon": True, "magic": True, "weapon": True},
        "res_flags": {"charm": True},
        "vuln_flags": {"iron": True},
        "sex":  'male',
        "gold": 422,
        "size": 'medium',
    },
}

# -- Rooms ----------------------------------------------------------------------
ROOMS = {
    R_QUESTORS_LOUNGE: {
        "name": 'The Questors Lounge',
        "desc": '',
        "exits": {
            "w": 3001,
        },
        "sector": 'inside',
    },
    R_REGISTAR_S_OFFICE: {
        "name": "The Registar's Office",
        "desc": '',
        "exits": {
            "e": 3001,
        },
        "sector": 'inside',
    },
    R_TRIVIA_SHOP: {
        "name": 'The Trivia Shop',
        "desc": '',
        "exits": {
            "n": 3303,
        },
        "sector": 'inside',
    },
}

# -- Item templates -------------------------------------------------------------
OBJECTS = {
    I_TRIVIA_PILL: {
        "keywords":    'trivia pill',
        "short_descr": 'A Trivia Pill',
        "description": 'A trivia pill is here!',
        "material":    'unknown',
        "type": 'pill',
        "wear_flags": {"take": True},
        "extra_flags": {"glow": True, "hum": True, "magic": True, "nonmetal": True, "nolocate": True, "burn_proof": True, "quest": True},
        "level": 0, "weight": 0, "value": 0,
    },
    I_QUEST_AURA_SANCTUARY: {
        "keywords":    'quest aura sanctuary',
        "short_descr": 'An Aura of the Ancients',
        "description": 'A red and yellow aura lies here.',
        "material":    'unknown',
        "type": 'jewelry',
        "wear_flags": {"take": True, "float": True},
        "extra_flags": {"glow": True, "hum": True, "magic": True, "nonmetal": True, "burn_proof": True, "quest": True},
        "stat_bonuses": {'AC': -100, 'hitroll': 50, 'damroll': 50},
        "level": 0, "weight": 1, "value": -1,
    },
    I_SWORD_QUEST_ANCIENT: {
        "keywords":    'Sword Quest Ancient',
        "short_descr": 'A Sword of the Ancients',
        "description": 'A red and yellow sword lies here.',
        "material":    'adamantite',
        "type": 'weapon',
        "wear_flags": {"take": True, "wield": True},
        "extra_flags": {"glow": True, "hum": True, "burn_proof": True, "quest": True},
        "weapon_type": 'sword', "dam_type": 'slice', "dice": (-1, -1, 0),
        "weapon_flags": {"flaming": True},
        "level": 0, "weight": 35, "value": -1,
    },
    I_BREASTPLATE_QUEST_ANCIENT: {
        "keywords":    'breastplate quest ancient',
        "short_descr": 'A BreastPlate of the Ancients',
        "description": 'Some red and yellow platemail was left here.',
        "material":    'unknown',
        "type": 'armor',
        "wear_flags": {"take": True, "body": True},
        "extra_flags": {"glow": True, "hum": True, "burn_proof": True, "quest": True},
        "AC": 0,
        "stat_bonuses": {'str': 1, 'dex': 1, 'wis': 1, 'int': 1},
        "level": 0, "weight": 20, "value": -1,
    },
    I_BOOTS_QUEST_ANCIENT: {
        "keywords":    'boots quest ancient',
        "short_descr": 'Boots of the Ancients',
        "description": 'Some red and yellow boots were left here.',
        "material":    'unknown',
        "type": 'armor',
        "wear_flags": {"take": True, "feet": True},
        "extra_flags": {"magic": True, "burn_proof": True, "quest": True},
        "AC": 0,
        "stat_bonuses": {'dex': 2},
        "level": 0, "weight": 8, "value": -1,
    },
    I_GLOVES_QUEST_PROTECTION: {
        "keywords":    'gloves quest protection',
        "short_descr": 'Gloves of Protection',
        "description": 'Some red and yellow gloves lie here.',
        "material":    'unknown',
        "type": 'armor',
        "wear_flags": {"take": True, "hands": True},
        "extra_flags": {"magic": True, "burn_proof": True, "quest": True},
        "AC": 0,
        "stat_bonuses": {'damroll': 50, 'hitroll': 50, 'con': 1, 'str': 1},
        "level": 0, "weight": 20, "value": -1,
    },
    I_FLAME_QUEST_ANCIENTS: {
        "keywords":    'flame quest ancients',
        "short_descr": 'Flame of the Ancients',
        "description": 'A red and yellow flame burns here.',
        "material":    'unknown',
        "type": 'light',
        "wear_flags": {"take": True, "hold": True},
        "extra_flags": {"glow": True, "burn_proof": True, "quest": True},
        "stat_bonuses": {'int': 1, 'wis': 1, 'mana': 100},
        "level": 0, "weight": 5, "value": -1,
    },
    I_QUEST_HELM_TRUE_SIGHT: {
        "keywords":    'quest helm true sight',
        "short_descr": 'A Helm of True Sight',
        "description": 'A red and yellow helm lies here.',
        "material":    'unknown',
        "type": 'armor',
        "wear_flags": {"take": True, "head": True},
        "extra_flags": {"glow": True, "hum": True, "magic": True, "burn_proof": True, "quest": True},
        "AC": 0,
        "level": 0, "weight": 10, "value": -1,
    },
    I_BAG_QUEST_ANCIENT: {
        "keywords":    'bag quest ancient',
        "short_descr": 'Bag of the Ancients',
        "description": 'A red and yellow bag lies here.',
        "material":    'unknown',
        "type": 'container',
        "wear_flags": {"take": True},
        "extra_flags": {"glow": True, "magic": True, "nonmetal": True, "quest": True},
        "stat_bonuses": {'AC': -100},
        "level": 0, "weight": 0, "value": -1,
    },
    I_SHIELD_QUEST_ANCIENT: {
        "keywords":    'shield quest ancient',
        "short_descr": 'A Shield of the Ancients',
        "description": 'A red and yellow shield lies here.',
        "material":    'unknown',
        "type": 'armor',
        "wear_flags": {"take": True, "shield": True},
        "extra_flags": {"magic": True, "burn_proof": True, "quest": True, "_unknown_bits": [27]},
        "AC": 0,
        "stat_bonuses": {'hp': 100},
        "level": 0, "weight": 20, "value": -1,
    },
    I_QUEST_RING_REGENERATION: {
        "keywords":    'quest ring regeneration',
        "short_descr": 'A Ring of Regeneration',
        "description": 'A red and yellow ring lies here.',
        "material":    'unknown',
        "type": 'jewelry',
        "wear_flags": {"take": True, "finger": True},
        "extra_flags": {"glow": True, "hum": True, "burn_proof": True, "quest": True},
        "level": 0, "weight": 3, "value": -1,
    },
    I_QUEST_RING_INVISIBILITY: {
        "keywords":    'quest ring invisibility',
        "short_descr": 'A Ring of Invisibility',
        "description": 'A red and yellow ring was left here.',
        "material":    'unknown',
        "type": 'jewelry',
        "wear_flags": {"take": True, "finger": True},
        "extra_flags": {"glow": True, "hum": True, "burn_proof": True, "quest": True},
        "level": 0, "weight": 2, "value": -1,
    },
    I_DRAGON_EYE: {
        "keywords":    'dragon eye',
        "short_descr": "A Dragon's Eye",
        "description": "A Dragon's Eye lies here.",
        "material":    'unknown',
        "type": 'trash',
        "wear_flags": {"take": True},
        "extra_flags": {"burn_proof": True},
        "level": 1, "weight": 0, "value": 0,
    },
    I_EAGLE_CLAW: {
        "keywords":    'eagle claw',
        "short_descr": "An Eagles' Claw",
        "description": "An Eagle's Claw lies here.",
        "material":    'unknown',
        "type": 'trash',
        "wear_flags": {"take": True},
        "extra_flags": {"burn_proof": True},
        "level": 0, "weight": 0, "value": 0,
    },
    I_RABBIT_FOOT: {
        "keywords":    'rabbit foot',
        "short_descr": "A Rabbit's Foot",
        "description": "A Rabbit's Foot lies here.",
        "material":    'unknown',
        "type": 'trash',
        "wear_flags": {"take": True},
        "extra_flags": {"burn_proof": True},
        "level": 0, "weight": 0, "value": 0,
    },
    I_WOLF_TOOTH: {
        "keywords":    'wolf tooth',
        "short_descr": 'A Wolves Tooth',
        "description": 'A Wolves Tooth lies here.',
        "material":    'unknown',
        "type": 'trash',
        "wear_flags": {"take": True},
        "extra_flags": {"burn_proof": True},
        "level": 0, "weight": 0, "value": 0,
    },
}

# -- Resets ---------------------------------------------------------------------
# ("M", mob_vnum, global_limit, room_vnum, room_limit) -- spawn mob up to limits
# ("O", item_vnum, room_vnum)                          -- place one item copy in room
# ("E", item_vnum, slot_name)                          -- equip item on last M mob
# ("G", item_vnum)                                     -- give item to last M mob inventory
# ("P", item_vnum, limit, container_vnum, max)         -- [PRIMESUD] deferred: no containers
# ("R", room_vnum, num_dirs)                           -- [PRIMESUD] deferred: unused in current areas
# F and D .are resets are baked into room exit flags at conversion time
RESETS = (
    ("M", M_EDURIN_QUESTMASTER_QUESTOR, 1, R_QUESTORS_LOUNGE, 1),
    ("M", M_200_REGISTRAR_GQUEST, 1, R_REGISTAR_S_OFFICE, 1),
    ("M", M_TRIVIA_SHOPKEEPER, 1, R_TRIVIA_SHOP, 1),
)
