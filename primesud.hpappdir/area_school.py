# fmt: off
# Area: Mud School
# Builders: None
# VNUM ranges: Rooms 3700-3799
# Credits: Hatchet


AREA = {
    "name":     'Mud School',
    "builders": 'None',
    "vnums":    (3700, 3799),
    "credits":  'Hatchet',
    "levels":   (1, 5),
    "version":  4,
}

# ── Room VNUMs ─────────────────────────────────────────────────────────────────
R_ENTRANCE_TO_MUD_SCHOOL           = 3700
R_ROOM_IN_MUD_SCHOOL               = 3701
R_CENTER_ROOM                      = 3702
R_ROOM_IN_MUD_SCHOOL_3703          = 3703
R_ROOM_IN_MUD_SCHOOL_3704          = 3704
R_ROOM_IN_MUD_SCHOOL_3705          = 3705
R_ROOM_IN_MUD_SCHOOL_3707          = 3707
R_ROOM_IN_MUD_SCHOOL_3708          = 3708
R_ROOM_IN_MUD_SCHOOL_3709          = 3709
R_BLOB_CAGE                        = 3710
R_ROOM_IN_MUD_SCHOOL_3711          = 3711
R_CAGE_ROOM                        = 3712
R_CAGE                             = 3713
R_CAGE_3714                        = 3714
R_CAGE_3715                        = 3715
R_CAGE_3716                        = 3716
R_ROOM_IN_MUD_SCHOOL_3717          = 3717
R_STORE_IN_MUD_SCHOOL              = 3718
R_ROOM_IN_MUD_SCHOOL_3719          = 3719
R_DARKENED_ROOM                    = 3720
R_END_OF_MUD_SCHOOL                = 3721
R_SOUTH_WALL_OF_ARENA              = 3722
R_SOUTH_WALL_OF_ARENA_3723         = 3723
R_SOUTH_WEST_CORNER_OF_ARENA       = 3724
R_SOUTH_WALL_OF_ARENA_3725         = 3725
R_SOUTH_EAST_CORNER_OF_ARENA       = 3726
R_WEST_WALL_OF_ARENA               = 3727
R_ARENA                            = 3728
R_ARENA_3729                       = 3729
R_ARENA_3730                       = 3730
R_EAST_WALL_OF_ARENA               = 3731
R_WEST_WALL_OF_ARENA_3732          = 3732
R_ARENA_3733                       = 3733
R_CENTER_OF_ARENA                  = 3734
R_ARENA_3735                       = 3735
R_EAST_WALL_OF_ARENA_3736          = 3736
R_WEST_WALL_OF_ARENA_3737          = 3737
R_ARENA_3738                       = 3738
R_ARENA_3739                       = 3739
R_ARENA_3740                       = 3740
R_EAST_WALL_OF_ARENA_3741          = 3741
R_NORTH_WEST_CORNER_OF_ARENA       = 3742
R_NORTH_WALL_OF_ARENA              = 3743
R_NORTH_WALL_OF_ARENA_3744         = 3744
R_NORTH_WALL_OF_ARENA_3745         = 3745
R_NORTH_EAST_CORNER_OF_ARENA       = 3746
R_CENTER_OF_THE_DUNGEON            = 3748
R_NORTH_WEST_CORNER_OF_THE_DUNGEON = 3749
R_NORTH_WALL_OF_THE_DUNGEON        = 3750
R_NORTH_EAST_CORNER_OF_THE_DUNGEON = 3751
R_WEST_WALL_OF_THE_DUNGEON         = 3752
R_EAST_WALL_OF_THE_DUNGEON         = 3753
R_SOUTH_WEST_CORNER_OF_THE_DUNGEON = 3754
R_SOUTH_WALL_OF_THE_DUNGEON        = 3755
R_SOUTH_EAST_CORNER_OF_THE_DUNGEON = 3756
R_ROOM_IN_MUD_SCHOOL_3757          = 3757
R_FUREY_S_TRAINING_ROOM            = 3758
R_ZUMP_S_GUILD_ROOM                = 3759
R_SAFE_ROOM                        = 3760

# ── Mob template VNUMs ─────────────────────────────────────────────────────────
M_ACOLYTE_CLERIC                   = 3700
M_BLOB                             = 3701
M_MONSTER                          = 3702
M_MONSTER_WIMPY                    = 3703
M_MONSTER_AGGRESSIVE               = 3704
M_MONSTER_WIMPY_AGGRESSIVE         = 3705
M_BIG_CREATURE                     = 3706
M_ADEPT_CLERIC                     = 3707
M_ADEPT                            = 3708
M_RABBIT                           = 3709
M_LIZARD                           = 3710
M_BOAR                             = 3711
M_FOX                              = 3712
M_SNAIL                            = 3713
M_BEAST                            = 3714
M_BEAR                             = 3715
M_WOLF                             = 3716
M_ADEPT_CLERIC_3717                = 3717
M_ADEPT_CLERIC_3718                = 3718
M_PRIEST_CLERIC                    = 3719
M_DIPLOMA_BEAST                    = 3720

# ── Item template VNUMs ────────────────────────────────────────────────────────
I_MACE_SUB_MERC                    = 3700
I_DAGGER_SUB_MERC                  = 3701
I_SWORD_SUB_MERC                   = 3702
I_VEST_SUB_MERC                    = 3703
I_SHIELD_SUB_MERC                  = 3704
I_CLOAK_SUB_MERC                   = 3705
I_HELMET_SUB_MERC                  = 3706
I_LEGGINGS_SUB_MERC                = 3707
I_BOOTS_SUB_MERC                   = 3708
I_GLOVES_SUB_MERC                  = 3709
I_SLEEVES_SUB_MERC                 = 3710
I_CAPE_SUB_MERC                    = 3711
I_BELT_SUB_MERC                    = 3712
I_BRACER_SUB_MERC                  = 3713
I_KEY                              = 3714
I_DIPLOMA                          = 3715
I_BANNER_WAR_MERC                  = 3716
I_SPEAR_SUB_MERC                   = 3717
I_STAFF_SUB_MERC                   = 3718
I_AXE_SUB_MERC                     = 3719
I_FLAIL_SUB_MERC                   = 3720
I_WHIP_SUB_MERC                    = 3721
I_GLAIVE_SUB_MERC                  = 3722

# ── Mob templates ──────────────────────────────────────────────────────────────
# hp_dice / mana_dice / damage: (num_dice, die_size, bonus)
# AC: avg(pierce,bash,slash,exotic) / 10 per REFERENCE.md  # TODO: verify scale
# hitroll: from level line; no separate damroll in .are (dam_dice bonus is it)
# loot: left empty — populate from RESETS E/G lines if needed
MOBILES = {
    M_ACOLYTE_CLERIC: {
        "keywords":    'acolyte cleric',
        "short_descr": 'the acolyte of Zump',
        "long_descr":  'An acolyte of Zump welcomes you to mud school.',
        "description": "He's big and bad.  Don't mess with him.",
        "race":        'Human',
        "act_flags": {"sentinel": True, "stay_area": True, "cleric": True, "warrior": True, "nopurge": True},
        "aff_flags": {"detect_evil": True, "sanctuary": True},
        "alignment": 1000,
        "level":     30,
        "hitroll":   10,
        "hp_dice":   (1, 1, 999),
        "mana_dice": (1, 1, 999),
        "damage":    (2, 4, 30),  "dam_type": 'beating',
        "AC":        -2,
        "off_flags": {"area_attack": True, "bash": True, "disarm": True, "dodge": True, "fast": True, "kick": True, "parry": True, "trip": True},
        "imm_flags": {"summon": True, "charm": True, "magic": True, "weapon": True},
        "sex":  'male',
        "gold": 0,
        "size": 'medium',
        "loot": [],  # TODO: from RESETS E/G
    },
    M_BLOB: {
        "keywords":    'blob',
        "short_descr": 'the blob',
        "long_descr":  'The blob is here, waiting to eat you up.',
        "description": "He is big, he is bad.  You don't want to fight him when he isn't chained up.\nPerhaps now would be a good time to flee from him!!!  If you don't flee, you\nwould really suffer the consequences.",
        "race":        'Unique',
        "act_flags": {"sentinel": True, "stay_area": True},
        "aff_flags": {"detect_evil": True},
        "alignment": 0,
        "level":     5,
        "hitroll":   -5,
        "hp_dice":   (1, 1, 49),
        "mana_dice": (1, 1, 99),
        "damage":    (1, 1, 0),  "dam_type": 'digestion',
        "AC":        -2,
        "off_flags": {"area_attack": True, "trip": True},
        "imm_flags": {"summon": True, "charm": True},
        "res_flags": {"magic": True, "weapon": True},
        "sex":  'either',
        "gold": 0,
        "size": 'large',
        "loot": [],  # TODO: from RESETS E/G
    },
    M_MONSTER: {
        "keywords":    'monster',
        "short_descr": 'the monster',
        "long_descr":  'There is a monster leashed here.',
        "description": 'He looks mean, but you feel comfortable that you can kill him, especially since\nhe is leashed up, and you are not.',
        "race":        'School monster',
        "act_flags": {"sentinel": True, "noalign": True},
        "alignment": 0,
        "level":     1,
        "hitroll":   0,
        "hp_dice":   (1, 1, 7),
        "mana_dice": (1, 1, 99),
        "damage":    (1, 3, 0),  "dam_type": 'claw',
        "AC":        1,
        "imm_flags": {"summon": True, "charm": True},
        "vuln_flags": {"magic": True},
        "sex":  'either',
        "gold": 10,
        "size": 'medium',
        "loot": [],  # TODO: from RESETS E/G
    },
    M_MONSTER_WIMPY: {
        "keywords":    'monster wimpy',
        "short_descr": 'the wimpy monster',
        "long_descr":  'There is a wimpy monster leashed here.',
        "description": 'He looks wimpy.  You feel comfortable that you can kill him, especially since\nhe is leashed up, and you are not.',
        "race":        'School monster',
        "act_flags": {"sentinel": True, "wimpy": True, "noalign": True},
        "alignment": 0,
        "level":     1,
        "hitroll":   0,
        "hp_dice":   (1, 1, 7),
        "mana_dice": (1, 1, 99),
        "damage":    (1, 2, 0),  "dam_type": 'claw',
        "AC":        1,
        "off_flags": {"crush": True},
        "imm_flags": {"summon": True, "charm": True},
        "vuln_flags": {"magic": True},
        "sex":  'either',
        "gold": 10,
        "size": 'medium',
        "loot": [],  # TODO: from RESETS E/G
    },
    M_MONSTER_AGGRESSIVE: {
        "keywords":    'monster aggressive',
        "short_descr": 'the aggressive monster',
        "long_descr":  'There is an aggressive monster leashed here.',
        "description": 'He looks mean, but you feel comfortable that you can kill him, especially since\nhe is leashed up, and you are not.',
        "race":        'School monster',
        "act_flags": {"sentinel": True, "aggressive": True, "noalign": True},
        "alignment": 0,
        "level":     1,
        "hitroll":   0,
        "hp_dice":   (1, 1, 7),
        "mana_dice": (1, 1, 99),
        "damage":    (1, 4, 0),  "dam_type": 'claw',
        "AC":        1,
        "off_flags": {"disarm": True, "parry": True},
        "imm_flags": {"summon": True, "charm": True},
        "vuln_flags": {"magic": True},
        "sex":  'either',
        "gold": 10,
        "size": 'medium',
        "loot": [],  # TODO: from RESETS E/G
    },
    M_MONSTER_WIMPY_AGGRESSIVE: {
        "keywords":    'monster wimpy aggressive',
        "short_descr": 'the wimpy aggressive monster',
        "long_descr":  'There is a wimpy aggressive monster leashed here.',
        "description": 'He looks mean, but you feel comfortable that you can kill him, especially since\nhe is leashed up, and you are not.',
        "race":        'School monster',
        "act_flags": {"sentinel": True, "aggressive": True, "wimpy": True, "noalign": True},
        "alignment": 0,
        "level":     1,
        "hitroll":   0,
        "hp_dice":   (1, 1, 7),
        "mana_dice": (1, 1, 99),
        "damage":    (1, 3, 0),  "dam_type": 'claw',
        "AC":        1,
        "off_flags": {"kick_dirt": True},
        "imm_flags": {"summon": True, "charm": True},
        "vuln_flags": {"magic": True},
        "sex":  'either',
        "gold": 10,
        "size": 'medium',
        "loot": [],  # TODO: from RESETS E/G
    },
    M_BIG_CREATURE: {
        "keywords":    'big creature',
        "short_descr": 'the big creature',
        "long_descr":  'There is a big creature hulking over your form.',
        "description": 'He looks mean, and you just might have a small problem killing him, but he\nlooks like a great prize!!!',
        "race":        'School monster',
        "act_flags": {"sentinel": True, "noalign": True},
        "aff_flags": {"infrared": True, "dark_vision": True},
        "alignment": 0,
        "level":     2,
        "hitroll":   1,
        "hp_dice":   (2, 2, 20),
        "mana_dice": (1, 1, 99),
        "damage":    (1, 4, 1),  "dam_type": 'claw',
        "AC":        0,
        "off_flags": {"dodge": True, "trip": True},
        "imm_flags": {"summon": True, "charm": True},
        "vuln_flags": {"magic": True},
        "sex":  'either',
        "gold": 25,
        "size": 'medium',
        "loot": [],  # TODO: from RESETS E/G
    },
    M_ADEPT_CLERIC: {
        "keywords":    'adept cleric',
        "short_descr": 'the adept of Satin',
        "long_descr":  'An adept of the mighty goddess Satin is here, contemplating your progress.',
        "description": "She is big and bad.  Don't mess with her.",
        "race":        'Human',
        "act_flags": {"sentinel": True, "stay_area": True, "cleric": True, "warrior": True, "nopurge": True},
        "aff_flags": {"detect_evil": True, "sanctuary": True},
        "alignment": 1000,
        "level":     30,
        "hitroll":   10,
        "hp_dice":   (1, 1, 999),
        "mana_dice": (1, 1, 999),
        "damage":    (2, 4, 30),  "dam_type": 'beating',
        "AC":        -2,
        "off_flags": {"area_attack": True, "bash": True, "disarm": True, "dodge": True, "fast": True, "kick": True, "parry": True, "trip": True},
        "imm_flags": {"summon": True, "charm": True, "magic": True, "weapon": True},
        "sex":  'female',
        "gold": 0,
        "size": 'medium',
        "loot": [],  # TODO: from RESETS E/G
    },
    M_ADEPT: {
        "keywords":    'adept',
        "short_descr": 'the adept of Alander',
        "long_descr":  'An adept of Alander is here, smiling at you.',
        "description": "He is big and bad.  Don't mess with him.",
        "race":        'Human',
        "act_flags": {"sentinel": True, "stay_area": True, "cleric": True, "warrior": True, "nopurge": True},
        "aff_flags": {"detect_evil": True, "sanctuary": True},
        "alignment": 1000,
        "level":     30,
        "hitroll":   10,
        "hp_dice":   (1, 1, 999),
        "mana_dice": (1, 1, 999),
        "damage":    (2, 4, 30),  "dam_type": 'beating',
        "AC":        -2,
        "off_flags": {"area_attack": True, "bash": True, "disarm": True, "dodge": True, "fast": True, "kick": True, "parry": True, "trip": True},
        "imm_flags": {"summon": True, "charm": True, "magic": True, "weapon": True},
        "sex":  'male',
        "gold": 0,
        "size": 'medium',
        "loot": [],  # TODO: from RESETS E/G
    },
    M_RABBIT: {
        "keywords":    'rabbit',
        "short_descr": 'the rabbit',
        "long_descr":  'A rabbit is bouncing around here.',
        "description": 'The rabbit smiles at you, completely harmless!',
        "race":        'Rabbit',
        "act_flags": {"stay_area": True, "wimpy": True, "noalign": True},
        "alignment": 100,
        "level":     1,
        "hitroll":   0,
        "hp_dice":   (1, 1, 10),
        "mana_dice": (1, 1, 99),
        "damage":    (1, 3, 0),  "dam_type": 'bite',
        "AC":        1,
        "off_flags": {"dodge": True, "fast": True},
        "sex":  'either',
        "gold": 0,
        "size": 'tiny',
        "loot": [],  # TODO: from RESETS E/G
    },
    M_LIZARD: {
        "keywords":    'lizard',
        "short_descr": 'the lizard',
        "long_descr":  'A lizard slithers up to you.',
        "description": 'It smiles at you, and tries to eat your leg.',
        "race":        'Lizard',
        "act_flags": {"stay_area": True, "noalign": True},
        "alignment": -100,
        "level":     2,
        "hitroll":   0,
        "hp_dice":   (2, 2, 20),
        "mana_dice": (1, 1, 99),
        "damage":    (1, 4, 1),  "dam_type": 'bite',
        "AC":        0,
        "off_flags": {"assist_race": True},
        "res_flags": {"poison": True},
        "vuln_flags": {"cold": True},
        "sex":  'either',
        "gold": 0,
        "size": 'small',
        "loot": [],  # TODO: from RESETS E/G
    },
    M_BOAR: {
        "keywords":    'boar',
        "short_descr": 'the boar',
        "long_descr":  'A boar tries to run you over.',
        "description": 'It grunts at you.',
        "race":        'Pig',
        "act_flags": {"stay_area": True, "noalign": True},
        "alignment": 0,
        "level":     3,
        "hitroll":   1,
        "hp_dice":   (3, 3, 30),
        "mana_dice": (1, 1, 99),
        "damage":    (1, 6, 1),  "dam_type": 'charge',
        "AC":        0,
        "off_flags": {"bash": True, "berserk": True, "dodge": True, "assist_race": True},
        "sex":  'either',
        "gold": 0,
        "size": 'medium',
        "loot": [],  # TODO: from RESETS E/G
    },
    M_FOX: {
        "keywords":    'fox',
        "short_descr": 'the fox',
        "long_descr":  'A fox is here staring at you.',
        "description": "It's fur might be worth money.",
        "race":        'Fox',
        "act_flags": {"stay_area": True, "wimpy": True, "noalign": True},
        "aff_flags": {"dark_vision": True},
        "alignment": 100,
        "level":     1,
        "hitroll":   1,
        "hp_dice":   (1, 1, 12),
        "mana_dice": (1, 1, 99),
        "damage":    (1, 3, 1),  "dam_type": 'bite',
        "AC":        0,
        "off_flags": {"dodge": True, "fast": True, "trip": True, "assist_race": True},
        "sex":  'either',
        "gold": 0,
        "size": 'small',
        "loot": [],  # TODO: from RESETS E/G
    },
    M_SNAIL: {
        "keywords":    'snail',
        "short_descr": 'the snail',
        "long_descr":  'A snail is trying to get out of your way.',
        "description": "You don't see much but slime about it.",
        "race":        'Unique',
        "act_flags": {"stay_area": True, "noalign": True},
        "alignment": 0,
        "level":     0,
        "hitroll":   0,
        "hp_dice":   (1, 1, 0),
        "mana_dice": (1, 1, 99),
        "damage":    (1, 1, 0),  "dam_type": 'digestion',
        "AC":        1,
        "sex":  'either',
        "gold": 0,
        "size": 'tiny',
        "loot": [],  # TODO: from RESETS E/G
    },
    M_BEAST: {
        "keywords":    'beast',
        "short_descr": 'the beast',
        "long_descr":  'A beast tries to feed off of you.',
        "description": "It looks mean.  You'd better run.",
        "race":        'School monster',
        "act_flags": {"aggressive": True, "warrior": True, "noalign": True},
        "aff_flags": {"dark_vision": True},
        "alignment": 0,
        "level":     5,
        "hitroll":   1,
        "hp_dice":   (5, 5, 55),
        "mana_dice": (1, 1, 99),
        "damage":    (1, 6, 3),  "dam_type": 'bite',
        "AC":        0,
        "off_flags": {"disarm": True, "parry": True, "tail": True},
        "imm_flags": {"summon": True, "charm": True},
        "res_flags": {"fire": True, "cold": True},
        "vuln_flags": {"magic": True},
        "sex":  'either',
        "gold": 50,
        "size": 'large',
        "loot": [],  # TODO: from RESETS E/G
    },
    M_BEAR: {
        "keywords":    'bear',
        "short_descr": 'the bear',
        "long_descr":  'A bear is here growling at you.',
        "description": 'The bear must be bigger than you!  It wants to rip your head off.',
        "race":        'Bear',
        "act_flags": {"stay_area": True, "noalign": True},
        "alignment": 0,
        "level":     4,
        "hitroll":   1,
        "hp_dice":   (4, 4, 44),
        "mana_dice": (1, 1, 99),
        "damage":    (1, 6, 2),  "dam_type": 'claw',
        "AC":        0,
        "off_flags": {"bash": True, "berserk": True, "disarm": True, "crush": True, "assist_race": True},
        "res_flags": {"bash": True, "cold": True},
        "sex":  'either',
        "gold": 0,
        "size": 'large',
        "loot": [],  # TODO: from RESETS E/G
    },
    M_WOLF: {
        "keywords":    'wolf',
        "short_descr": 'the wolf',
        "long_descr":  'A wolf is here snarling at you.',
        "description": "The wolf doesn't want to be bothered.",
        "race":        'Wolf',
        "act_flags": {"stay_area": True, "noalign": True},
        "aff_flags": {"dark_vision": True},
        "alignment": 0,
        "level":     4,
        "hitroll":   0,
        "hp_dice":   (4, 4, 44),
        "mana_dice": (1, 1, 99),
        "damage":    (1, 6, 2),  "dam_type": 'bite',
        "AC":        0,
        "off_flags": {"dodge": True, "fast": True, "trip": True, "assist_race": True},
        "sex":  'either',
        "gold": 0,
        "size": 'medium',
        "loot": [],  # TODO: from RESETS E/G
    },
    M_ADEPT_CLERIC_3717: {
        "keywords":    'adept cleric',
        "short_descr": 'the adept of Selene',
        "long_descr":  'An adept of Selene is here, grinning and selling you things.',
        "description": "He is big and bad.  Don't mess with him.",
        "race":        'Human',
        "act_flags": {"sentinel": True, "scavenger": True, "cleric": True, "warrior": True, "nopurge": True},
        "aff_flags": {"detect_evil": True, "sanctuary": True},
        "alignment": 1000,
        "level":     30,
        "hitroll":   10,
        "hp_dice":   (1, 1, 999),
        "mana_dice": (1, 1, 999),
        "damage":    (2, 4, 30),  "dam_type": 'beating',
        "AC":        -2,
        "off_flags": {"area_attack": True, "bash": True, "disarm": True, "dodge": True, "fast": True, "kick": True, "parry": True, "trip": True},
        "imm_flags": {"summon": True, "charm": True, "magic": True, "weapon": True},
        "sex":  'male',
        "gold": 0,
        "size": 'medium',
        "loot": [],  # TODO: from RESETS E/G
    },
    M_ADEPT_CLERIC_3718: {
        "keywords":    'adept cleric',
        "short_descr": 'the adept of Furey',
        "long_descr":  'An adept of Furey is here, training young students.',
        "description": "He is big and bad.  Don't mess with him.",
        "race":        'Human',
        "act_flags": {"sentinel": True, "scavenger": True, "train": True, "cleric": True, "warrior": True, "nopurge": True},
        "aff_flags": {"detect_evil": True, "sanctuary": True},
        "alignment": 1000,
        "level":     30,
        "hitroll":   10,
        "hp_dice":   (1, 1, 999),
        "mana_dice": (1, 1, 999),
        "damage":    (2, 4, 30),  "dam_type": 'beating',
        "AC":        -2,
        "off_flags": {"area_attack": True, "bash": True, "disarm": True, "dodge": True, "fast": True, "kick": True, "parry": True, "trip": True},
        "imm_flags": {"summon": True, "charm": True, "magic": True, "weapon": True},
        "sex":  'male',
        "gold": 0,
        "size": 'medium',
        "loot": [],  # TODO: from RESETS E/G
    },
    M_PRIEST_CLERIC: {
        "keywords":    'priest cleric',
        "short_descr": 'the priest of Circe',
        "long_descr":  'The priest of Circe is ready to help you practice.',
        "description": "He is big and bad.  Don't mess with him.",
        "race":        'Human',
        "act_flags": {"sentinel": True, "scavenger": True, "practice": True, "cleric": True, "warrior": True, "nopurge": True},
        "aff_flags": {"detect_evil": True, "sanctuary": True},
        "alignment": 1000,
        "level":     30,
        "hitroll":   10,
        "hp_dice":   (1, 1, 999),
        "mana_dice": (1, 1, 999),
        "damage":    (2, 4, 30),  "dam_type": 'beating',
        "AC":        -2,
        "off_flags": {"area_attack": True, "bash": True, "disarm": True, "dodge": True, "fast": True, "kick": True, "parry": True, "trip": True},
        "imm_flags": {"summon": True, "charm": True, "magic": True, "weapon": True},
        "sex":  'male',
        "gold": 0,
        "size": 'medium',
        "loot": [],  # TODO: from RESETS E/G
    },
    M_DIPLOMA_BEAST: {
        "keywords":    'diploma beast',
        "short_descr": 'the diploma beast',
        "long_descr":  'The hideous diploma beast is here, holding your graduation present!',
        "description": 'This horrible creature is your final test for mud school.  Kill him, and the\ndiploma is yours.',
        "race":        'School monster',
        "act_flags": {"sentinel": True, "noalign": True},
        "aff_flags": {"infrared": True},
        "alignment": 0,
        "level":     3,
        "hitroll":   1,
        "hp_dice":   (2, 4, 30),
        "mana_dice": (1, 1, 99),
        "damage":    (1, 6, 1),  "dam_type": 'claw',
        "AC":        0,
        "off_flags": {"disarm": True, "dodge": True, "trip": True},
        "imm_flags": {"summon": True, "charm": True},
        "vuln_flags": {"magic": True},
        "sex":  'either',
        "gold": 30,
        "size": 'medium',
        "loot": [],  # TODO: from RESETS E/G
    },
}

# ── Rooms ──────────────────────────────────────────────────────────────────────
ROOMS = {
    R_ENTRANCE_TO_MUD_SCHOOL: {
        "name": 'Entrance to Mud School',
        "desc": "This is the entrance to the Merc Mud School.  Go north to go through mud\nschool.  If you have been here before and want to go directly to the arena,\ngo south.\n\nA sign warns 'You may not pass these doors once you have passed level 5.'",
        "exits": {
            "n": R_ROOM_IN_MUD_SCHOOL_3757,
            "s": {"to": R_NORTH_WALL_OF_ARENA_3744, "isdoor": True, "closed": True},
            "d": 3001,
        },
        "flags": {"no_mob": True, "indoors": True},
    },
    R_ROOM_IN_MUD_SCHOOL: {
        "name": 'A Room in Mud School',
        "desc": 'You are in a square white room.  The walls are all blank, with no windows.\nLight fluoresces off the ceiling in soft white tones.  Of course, there is a\nsign on the wall.  The exits are west and south.  A small plaque is on the\nwall.',
        "exits": {
            "s": R_ROOM_IN_MUD_SCHOOL_3757,
            "w": R_CENTER_ROOM,
        },
        "flags": {"no_mob": True, "indoors": True, "newbies_only": True},
    },
    R_CENTER_ROOM: {
        "name": 'The Center Room',
        "desc": 'You are in a square white room.  The walls are all blank, with no windows.\nLight fluoresces off the ceiling in soft white tones.  Of course, there is a\nsign on the wall.  Exits lead in ALL directions.',
        "exits": {
            "n": R_ROOM_IN_MUD_SCHOOL_3703,
            "e": R_ROOM_IN_MUD_SCHOOL,
            "s": R_ROOM_IN_MUD_SCHOOL_3705,
            "w": R_ROOM_IN_MUD_SCHOOL_3704,
            "u": R_ROOM_IN_MUD_SCHOOL_3708,
            "d": R_ROOM_IN_MUD_SCHOOL_3707,
        },
        "flags": {"no_mob": True, "indoors": True, "newbies_only": True},
    },
    R_ROOM_IN_MUD_SCHOOL_3703: {
        "name": 'A Room in Mud School',
        "desc": 'You are in a square white room.  The walls are all blank, with no windows.\nLight fluoresces off the ceiling in soft white tones.  Of course, there is a\nsign on the wall.  Exits lead north and south.',
        "exits": {
            "n": R_ROOM_IN_MUD_SCHOOL_3709,
            "s": R_CENTER_ROOM,
        },
        "flags": {"no_mob": True, "indoors": True, "newbies_only": True},
    },
    R_ROOM_IN_MUD_SCHOOL_3704: {
        "name": 'A Room in Mud School',
        "desc": 'You are in a square white room.  The walls are all blank, with no windows.\nLight fluoresces off the ceiling in soft white tones.  Of course, there is a\nsign on the wall.  The only exit is east.',
        "exits": {
            "e": R_CENTER_ROOM,
        },
        "flags": {"no_mob": True, "indoors": True, "newbies_only": True},
    },
    R_ROOM_IN_MUD_SCHOOL_3705: {
        "name": 'A Room in Mud School',
        "desc": 'You are in a square white room.  The walls are all blank, with no windows.\nLight fluoresces off the ceiling in soft white tones.  Of course, there is a\nsign on the wall.  The only exit is north.',
        "exits": {
            "n": R_CENTER_ROOM,
        },
        "flags": {"no_mob": True, "indoors": True, "newbies_only": True},
    },
    R_ROOM_IN_MUD_SCHOOL_3707: {
        "name": 'A Room in Mud School',
        "desc": 'You are in a square white room.  The walls are all blank, with no windows.\nLight fluoresces off the ceiling in soft white tones.  Of course, there is a\nsign on the wall.  The only exit is up.',
        "exits": {
            "u": R_CENTER_ROOM,
        },
        "flags": {"no_mob": True, "indoors": True, "newbies_only": True},
    },
    R_ROOM_IN_MUD_SCHOOL_3708: {
        "name": 'A Room in Mud School',
        "desc": 'You are in a square white room.  The walls are all blank, with no windows.\nLight fluoresces off the ceiling in soft white tones.  Of course, there is a\nsign on the wall.  The only exit is down.',
        "exits": {
            "d": R_CENTER_ROOM,
        },
        "flags": {"no_mob": True, "indoors": True, "newbies_only": True},
    },
    R_ROOM_IN_MUD_SCHOOL_3709: {
        "name": 'A Room in Mud School',
        "desc": 'You are in a square white room.  The walls are all blank, with no windows.\nLight fluoresces off the ceiling in soft white tones.  Of course, there is a\nsign on the wall.  Exits reach west and down.',
        "exits": {
            "w": R_ROOM_IN_MUD_SCHOOL_3711,
            "d": R_BLOB_CAGE,
        },
        "flags": {"no_mob": True, "indoors": True, "newbies_only": True},
    },
    R_BLOB_CAGE: {
        "name": 'The Blob Cage',
        "desc": 'You are in a smelly cage.  Strangely, the walls are still clean!\nYou see a sign here.  The only exit is up.',
        "exits": {
            "u": R_ROOM_IN_MUD_SCHOOL_3709,
        },
        "flags": {"indoors": True, "newbies_only": True},
    },
    R_ROOM_IN_MUD_SCHOOL_3711: {
        "name": 'A Room in Mud School',
        "desc": 'You are in a square white room.  The walls are all blank, with no windows.\nLight fluoresces off the ceiling in soft white tones.  Of course, there is a\nsign on the wall.',
        "exits": {
            "e": R_ROOM_IN_MUD_SCHOOL_3709,
            "d": R_CAGE_ROOM,
        },
        "flags": {"no_mob": True, "indoors": True, "newbies_only": True},
    },
    R_CAGE_ROOM: {
        "name": 'The Cage Room',
        "desc": 'You are in the cage room.  All around are 4 cages.  Light fluoresces off the\nceiling in soft white tones.  Of course, there is a big sign on the wall.\nExits lead into the cardinal directions plus down.',
        "exits": {
            "n": R_CAGE,
            "e": R_CAGE_3716,
            "s": R_CAGE_3715,
            "w": R_CAGE_3714,
            "d": R_ROOM_IN_MUD_SCHOOL_3717,
        },
        "flags": {"no_mob": True, "indoors": True, "newbies_only": True},
    },
    R_CAGE: {
        "name": 'A Cage',
        "desc": 'You are in a cage.  Blood and gore are everywhere.  The keepers must be lax\nin the upkeep here!  There is a sign on the wall.  The only exit is south.',
        "exits": {
            "s": R_CAGE_ROOM,
        },
        "flags": {"indoors": True, "newbies_only": True},
    },
    R_CAGE_3714: {
        "name": 'A Cage',
        "desc": 'You are in a cage.  Blood and gore are everywhere.  The keepers must be lax\nin the upkeep here!  There is a sign on the wall.  The only exit is east.',
        "exits": {
            "e": R_CAGE_ROOM,
        },
        "flags": {"indoors": True, "newbies_only": True},
    },
    R_CAGE_3715: {
        "name": 'A Cage',
        "desc": 'You are in a cage.  Blood and gore are everywhere.  The keepers must be lax\nin the upkeep here!  There is a sign on the wall.  The only exit is north.',
        "exits": {
            "n": R_CAGE_ROOM,
        },
        "flags": {"indoors": True, "newbies_only": True},
    },
    R_CAGE_3716: {
        "name": 'A Cage',
        "desc": 'You are in a cage.  Blood and gore are everywhere.  The keepers must be lax\nin the upkeep here!  There is a sign on the wall.  The only exit is west.',
        "exits": {
            "w": R_CAGE_ROOM,
        },
        "flags": {"indoors": True, "newbies_only": True},
    },
    R_ROOM_IN_MUD_SCHOOL_3717: {
        "name": 'A Room in Mud School',
        "desc": 'You are in a square white room.  The walls are all blank, with no windows.\nLight fluoresces off the ceiling in soft white tones.  Of course, there is a\nsign on the wall.  Find your own exit here.',
        "exits": {
            "e": {"to": R_ROOM_IN_MUD_SCHOOL_3719, "isdoor": True, "closed": True},
            "s": R_STORE_IN_MUD_SCHOOL,
            "u": R_CAGE_ROOM,
        },
        "flags": {"no_mob": True, "indoors": True, "newbies_only": True},
    },
    R_STORE_IN_MUD_SCHOOL: {
        "name": 'The Store in Mud School',
        "desc": 'You are in a cramped room.  Stacked neatly on shelves everywhere are items\nand packages.  Light fluoresces off the ceiling in soft white tones.  Of\ncourse, there is a sign on the wall.  The only exit is north.',
        "exits": {
            "n": R_ROOM_IN_MUD_SCHOOL_3717,
        },
        "flags": {"indoors": True, "newbies_only": True},
    },
    R_ROOM_IN_MUD_SCHOOL_3719: {
        "name": 'A Room in Mud School',
        "desc": 'You are in a square white room.  The walls are all blank, with no windows.\nLight fluoresces off the ceiling in soft white tones.  Of course, there is a\nsign on the wall.  The exits are north and west, with a door to the east.',
        "exits": {
            "n": R_DARKENED_ROOM,
            "e": {"to": R_END_OF_MUD_SCHOOL, "isdoor": True, "closed": True, "locked": True, "pickproof": True},
            "w": {"to": R_ROOM_IN_MUD_SCHOOL_3717, "isdoor": True, "closed": True},
        },
        "flags": {"no_mob": True, "indoors": True, "newbies_only": True},
    },
    R_DARKENED_ROOM: {
        "name": 'The Darkened Room',
        "desc": 'This room was purposefully darkened so that you would need to hold on to a\nlight source to go through.  The walls are, of course, blank, and white.\nThe only exit is south.',
        "exits": {
            "s": R_ROOM_IN_MUD_SCHOOL_3719,
        },
        "flags": {"dark": True, "indoors": True, "newbies_only": True},
    },
    R_END_OF_MUD_SCHOOL: {
        "name": 'The End of Mud School!',
        "desc": 'This is a very bright room, with a marble pedestal in the center.  Behind\nthe pedestal stands a person cloaked in Silver.  Tapestries flow from every\nwall, and you feel very happy to be here right now.  There is a big sign here.\nThe only exit is on the other side of the gate north of you.',
        "exits": {
            "n": {"to": R_SOUTH_WALL_OF_ARENA, "isdoor": True, "closed": True},
        },
        "flags": {"indoors": True, "newbies_only": True},
    },
    R_SOUTH_WALL_OF_ARENA: {
        "name": 'South Wall of Arena',
        "desc": 'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
        "exits": {
            "n": R_ARENA_3729,
            "e": R_SOUTH_WALL_OF_ARENA_3725,
            "w": R_SOUTH_WALL_OF_ARENA_3723,
            "u": R_SAFE_ROOM,
        },
        "flags": {"indoors": True},
    },
    R_SOUTH_WALL_OF_ARENA_3723: {
        "name": 'South Wall of Arena',
        "desc": 'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
        "exits": {
            "n": R_ARENA,
            "e": R_SOUTH_WALL_OF_ARENA,
            "w": R_SOUTH_WEST_CORNER_OF_ARENA,
            "u": R_SAFE_ROOM,
        },
        "flags": {"indoors": True},
    },
    R_SOUTH_WEST_CORNER_OF_ARENA: {
        "name": 'South West Corner of Arena',
        "desc": 'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
        "exits": {
            "n": R_WEST_WALL_OF_ARENA,
            "e": R_SOUTH_WALL_OF_ARENA_3723,
            "u": R_SAFE_ROOM,
        },
        "flags": {"indoors": True},
    },
    R_SOUTH_WALL_OF_ARENA_3725: {
        "name": 'South Wall of Arena',
        "desc": 'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
        "exits": {
            "n": R_ARENA_3730,
            "e": R_SOUTH_EAST_CORNER_OF_ARENA,
            "w": R_SOUTH_WALL_OF_ARENA,
            "u": R_SAFE_ROOM,
        },
        "flags": {"indoors": True},
    },
    R_SOUTH_EAST_CORNER_OF_ARENA: {
        "name": 'South East Corner of Arena',
        "desc": 'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
        "exits": {
            "n": R_EAST_WALL_OF_ARENA,
            "w": R_SOUTH_WALL_OF_ARENA_3725,
            "u": R_SAFE_ROOM,
        },
        "flags": {"indoors": True},
    },
    R_WEST_WALL_OF_ARENA: {
        "name": 'West Wall of Arena',
        "desc": 'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
        "exits": {
            "n": R_WEST_WALL_OF_ARENA_3732,
            "e": R_ARENA,
            "s": R_SOUTH_WEST_CORNER_OF_ARENA,
            "u": R_SAFE_ROOM,
        },
        "flags": {"indoors": True},
    },
    R_ARENA: {
        "name": 'Arena',
        "desc": 'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
        "exits": {
            "n": R_ARENA_3733,
            "e": R_ARENA_3729,
            "s": R_SOUTH_WALL_OF_ARENA_3723,
            "w": R_WEST_WALL_OF_ARENA,
            "u": R_SAFE_ROOM,
        },
        "flags": {"indoors": True},
    },
    R_ARENA_3729: {
        "name": 'Arena',
        "desc": 'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
        "exits": {
            "n": R_CENTER_OF_ARENA,
            "e": R_ARENA_3730,
            "s": R_SOUTH_WALL_OF_ARENA,
            "w": R_ARENA,
            "u": R_SAFE_ROOM,
        },
        "flags": {"indoors": True},
    },
    R_ARENA_3730: {
        "name": 'Arena',
        "desc": 'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
        "exits": {
            "n": R_ARENA_3735,
            "e": R_EAST_WALL_OF_ARENA,
            "s": R_SOUTH_WALL_OF_ARENA_3725,
            "w": R_ARENA_3729,
            "u": R_SAFE_ROOM,
        },
        "flags": {"indoors": True},
    },
    R_EAST_WALL_OF_ARENA: {
        "name": 'East Wall of Arena',
        "desc": 'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
        "exits": {
            "n": R_EAST_WALL_OF_ARENA_3736,
            "s": R_SOUTH_EAST_CORNER_OF_ARENA,
            "w": R_ARENA_3730,
            "u": R_SAFE_ROOM,
        },
        "flags": {"indoors": True},
    },
    R_WEST_WALL_OF_ARENA_3732: {
        "name": 'West Wall of Arena',
        "desc": 'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
        "exits": {
            "n": R_WEST_WALL_OF_ARENA_3737,
            "e": R_ARENA_3733,
            "s": R_WEST_WALL_OF_ARENA,
            "u": R_SAFE_ROOM,
        },
        "flags": {"indoors": True},
    },
    R_ARENA_3733: {
        "name": 'Arena',
        "desc": 'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
        "exits": {
            "n": R_ARENA_3738,
            "e": R_CENTER_OF_ARENA,
            "s": R_ARENA,
            "w": R_WEST_WALL_OF_ARENA_3732,
            "u": R_SAFE_ROOM,
        },
        "flags": {"indoors": True},
    },
    R_CENTER_OF_ARENA: {
        "name": 'Center of Arena',
        "desc": 'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.  There is a BIG SIGN here.',
        "exits": {
            "n": R_ARENA_3739,
            "e": R_ARENA_3735,
            "s": R_ARENA_3729,
            "w": R_ARENA_3733,
            "u": R_SAFE_ROOM,
            "d": {"to": R_CENTER_OF_THE_DUNGEON, "isdoor": True, "closed": True},
        },
        "flags": {"indoors": True},
    },
    R_ARENA_3735: {
        "name": 'Arena',
        "desc": 'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
        "exits": {
            "n": R_ARENA_3740,
            "e": R_EAST_WALL_OF_ARENA_3736,
            "s": R_ARENA_3730,
            "w": R_CENTER_OF_ARENA,
            "u": R_SAFE_ROOM,
        },
        "flags": {"indoors": True},
    },
    R_EAST_WALL_OF_ARENA_3736: {
        "name": 'East Wall of Arena',
        "desc": 'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
        "exits": {
            "n": R_EAST_WALL_OF_ARENA_3741,
            "s": R_EAST_WALL_OF_ARENA,
            "w": R_ARENA_3735,
            "u": R_SAFE_ROOM,
        },
        "flags": {"indoors": True},
    },
    R_WEST_WALL_OF_ARENA_3737: {
        "name": 'West Wall of Arena',
        "desc": 'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
        "exits": {
            "n": R_NORTH_WEST_CORNER_OF_ARENA,
            "e": R_ARENA_3738,
            "s": R_WEST_WALL_OF_ARENA_3732,
            "u": R_SAFE_ROOM,
        },
        "flags": {"indoors": True},
    },
    R_ARENA_3738: {
        "name": 'Arena',
        "desc": 'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
        "exits": {
            "n": R_NORTH_WALL_OF_ARENA,
            "e": R_ARENA_3739,
            "s": R_ARENA_3733,
            "w": R_WEST_WALL_OF_ARENA_3737,
            "u": R_SAFE_ROOM,
        },
        "flags": {"indoors": True},
    },
    R_ARENA_3739: {
        "name": 'Arena',
        "desc": 'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
        "exits": {
            "n": R_NORTH_WALL_OF_ARENA_3744,
            "e": R_ARENA_3740,
            "s": R_CENTER_OF_ARENA,
            "w": R_ARENA_3738,
            "u": R_SAFE_ROOM,
        },
        "flags": {"indoors": True},
    },
    R_ARENA_3740: {
        "name": 'Arena',
        "desc": 'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
        "exits": {
            "n": R_NORTH_WALL_OF_ARENA_3745,
            "e": R_EAST_WALL_OF_ARENA_3741,
            "s": R_ARENA_3735,
            "w": R_ARENA_3739,
            "u": R_SAFE_ROOM,
        },
        "flags": {"indoors": True},
    },
    R_EAST_WALL_OF_ARENA_3741: {
        "name": 'East Wall of Arena',
        "desc": 'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
        "exits": {
            "n": R_NORTH_EAST_CORNER_OF_ARENA,
            "s": R_EAST_WALL_OF_ARENA_3736,
            "w": R_ARENA_3740,
            "u": R_SAFE_ROOM,
        },
        "flags": {"indoors": True},
    },
    R_NORTH_WEST_CORNER_OF_ARENA: {
        "name": 'North West Corner of Arena',
        "desc": 'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
        "exits": {
            "e": R_NORTH_WALL_OF_ARENA,
            "s": R_WEST_WALL_OF_ARENA_3737,
            "u": R_SAFE_ROOM,
        },
        "flags": {"indoors": True},
    },
    R_NORTH_WALL_OF_ARENA: {
        "name": 'North Wall of Arena',
        "desc": 'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  You can barely see the ceiling.  You feel as if you are being watched\nby some divine being.',
        "exits": {
            "e": R_NORTH_WALL_OF_ARENA_3744,
            "s": R_ARENA_3738,
            "w": R_NORTH_WEST_CORNER_OF_ARENA,
            "u": R_SAFE_ROOM,
        },
        "flags": {"indoors": True},
    },
    R_NORTH_WALL_OF_ARENA_3744: {
        "name": 'North Wall of Arena',
        "desc": 'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
        "exits": {
            "e": R_NORTH_WALL_OF_ARENA_3745,
            "s": R_ARENA_3739,
            "w": R_NORTH_WALL_OF_ARENA,
            "u": R_SAFE_ROOM,
        },
        "flags": {"indoors": True},
    },
    R_NORTH_WALL_OF_ARENA_3745: {
        "name": 'North Wall of Arena',
        "desc": 'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
        "exits": {
            "e": R_NORTH_EAST_CORNER_OF_ARENA,
            "s": R_ARENA_3740,
            "w": R_NORTH_WALL_OF_ARENA_3744,
            "u": R_SAFE_ROOM,
        },
        "flags": {"indoors": True},
    },
    R_NORTH_EAST_CORNER_OF_ARENA: {
        "name": 'North East Corner of Arena',
        "desc": 'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
        "exits": {
            "s": R_EAST_WALL_OF_ARENA_3741,
            "w": R_NORTH_WALL_OF_ARENA_3745,
            "u": R_SAFE_ROOM,
        },
        "flags": {"indoors": True},
    },
    R_CENTER_OF_THE_DUNGEON: {
        "name": 'The Center of the Dungeon',
        "desc": 'You are in the center of a large room.  A faint light from above shows that\nthe floors are all covered with slime.  A feeling of dread comes over you as\nyou notice that this is NOT a great place to go.  Exits go in all directions.\nOf special note is the one that brings you back up!!!',
        "exits": {
            "n": R_NORTH_WALL_OF_THE_DUNGEON,
            "e": R_EAST_WALL_OF_THE_DUNGEON,
            "s": R_SOUTH_WALL_OF_THE_DUNGEON,
            "w": R_WEST_WALL_OF_THE_DUNGEON,
            "u": {"to": R_CENTER_OF_ARENA, "isdoor": True, "closed": True},
        },
        "flags": {"indoors": True},
    },
    R_NORTH_WEST_CORNER_OF_THE_DUNGEON: {
        "name": 'The North West Corner of the Dungeon',
        "desc": 'You are against a wall in the dungeon.  It is quite dark here.  The lack of\nany windows in the area explains the smell around you.',
        "exits": {
            "e": R_NORTH_WALL_OF_THE_DUNGEON,
            "s": R_WEST_WALL_OF_THE_DUNGEON,
        },
        "flags": {"dark": True, "indoors": True},
    },
    R_NORTH_WALL_OF_THE_DUNGEON: {
        "name": 'The North Wall of the Dungeon',
        "desc": 'You are against a wall in the dungeon.  It is quite dark here.  The lack of\nany windows in the area explains the smell around you.',
        "exits": {
            "e": R_NORTH_EAST_CORNER_OF_THE_DUNGEON,
            "s": R_CENTER_OF_THE_DUNGEON,
            "w": R_NORTH_WEST_CORNER_OF_THE_DUNGEON,
        },
        "flags": {"dark": True, "indoors": True},
    },
    R_NORTH_EAST_CORNER_OF_THE_DUNGEON: {
        "name": 'The North East Corner of the Dungeon',
        "desc": 'You are against a wall in the dungeon.  It is quite dark here.  The lack of\nany windows in the area explains the smell around you.',
        "exits": {
            "s": R_EAST_WALL_OF_THE_DUNGEON,
            "w": R_NORTH_WALL_OF_THE_DUNGEON,
        },
        "flags": {"dark": True, "indoors": True},
    },
    R_WEST_WALL_OF_THE_DUNGEON: {
        "name": 'The West Wall of the Dungeon',
        "desc": 'You are against a wall in the dungeon.  It is quite dark here.  The lack of\nany windows in the area explains the smell around you.',
        "exits": {
            "n": R_NORTH_WEST_CORNER_OF_THE_DUNGEON,
            "e": R_CENTER_OF_THE_DUNGEON,
            "s": R_SOUTH_WEST_CORNER_OF_THE_DUNGEON,
        },
        "flags": {"dark": True, "indoors": True},
    },
    R_EAST_WALL_OF_THE_DUNGEON: {
        "name": 'The East Wall of the Dungeon',
        "desc": 'You are against a wall in the dungeon.  It is quite dark here.  The lack of\nany windows in the area explains the smell around you.',
        "exits": {
            "n": R_NORTH_EAST_CORNER_OF_THE_DUNGEON,
            "s": R_SOUTH_EAST_CORNER_OF_THE_DUNGEON,
            "w": R_CENTER_OF_THE_DUNGEON,
        },
        "flags": {"dark": True, "indoors": True},
    },
    R_SOUTH_WEST_CORNER_OF_THE_DUNGEON: {
        "name": 'The South West Corner of the Dungeon',
        "desc": 'You are against a wall in the dungeon.  It is quite dark here.  The lack of\nany windows in the area explains the smell around you.',
        "exits": {
            "n": R_WEST_WALL_OF_THE_DUNGEON,
            "e": R_SOUTH_WALL_OF_THE_DUNGEON,
        },
        "flags": {"dark": True, "indoors": True},
    },
    R_SOUTH_WALL_OF_THE_DUNGEON: {
        "name": 'The South Wall of the Dungeon',
        "desc": 'You are against a wall in the dungeon.  It is quite dark here.  The lack of\nany windows in the area explains the smell around you.',
        "exits": {
            "n": R_CENTER_OF_THE_DUNGEON,
            "e": R_SOUTH_EAST_CORNER_OF_THE_DUNGEON,
            "w": R_SOUTH_WEST_CORNER_OF_THE_DUNGEON,
        },
        "flags": {"dark": True, "indoors": True},
    },
    R_SOUTH_EAST_CORNER_OF_THE_DUNGEON: {
        "name": 'The South East Corner of the Dungeon',
        "desc": 'You are against a wall in the dungeon.  It is quite dark here.  The lack of\nany windows in the area explains the smell around you.',
        "exits": {
            "n": R_EAST_WALL_OF_THE_DUNGEON,
            "w": R_SOUTH_WALL_OF_THE_DUNGEON,
        },
        "flags": {"dark": True, "indoors": True},
    },
    R_ROOM_IN_MUD_SCHOOL_3757: {
        "name": 'A Room in Mud School',
        "desc": "You are in a room in Mud School.  Paintings of the heroic graduates of mud\nschool adorn the walls. To the west is Furey's Training Room, and to the east\nis Zump's Guild Room.  North of you is the next Station of Mud School.\nThere is a sign on the wall (type 'LOOK SIGN' to read it).",
        "exits": {
            "n": R_ROOM_IN_MUD_SCHOOL,
            "e": R_ZUMP_S_GUILD_ROOM,
            "s": R_ENTRANCE_TO_MUD_SCHOOL,
            "w": R_FUREY_S_TRAINING_ROOM,
        },
        "flags": {"no_mob": True, "indoors": True, "newbies_only": True},
        "sector": 1,
    },
    R_FUREY_S_TRAINING_ROOM: {
        "name": "Furey's Training Room",
        "desc": "You are in Furey's Training Room.  Around you are all sorts of physical\nand mental training tools.  The whole room is filled with magic, holiness,\nand sweat.  There is a sign on the wall.",
        "exits": {
            "e": R_ROOM_IN_MUD_SCHOOL_3757,
        },
        "flags": {"no_mob": True, "indoors": True, "newbies_only": True},
        "sector": 1,
    },
    R_ZUMP_S_GUILD_ROOM: {
        "name": "Zump's Guild Room",
        "desc": 'You are in a room filled with weapons, books, and many combat dummies, some\ncut and stabbed many times, others burnt to a crisp.  The room is filled with\nsweat and an aura of magic.  There is a sign on the wall.',
        "exits": {
            "w": R_ROOM_IN_MUD_SCHOOL_3757,
        },
        "flags": {"no_mob": True, "indoors": True, "newbies_only": True},
        "sector": 1,
    },
    R_SAFE_ROOM: {
        "name": 'A Safe Room',
        "desc": 'You are in a safe room, away from all the mean rabbits and snails of the Arena.\nYou can rest here, and go up to go back to the Temple of Midgaard.',
        "exits": {
            "u": 3001,
        },
        "flags": {"no_mob": True, "indoors": True},
    },
}

# ── Item templates ─────────────────────────────────────────────────────────────
OBJECTS = {
    I_MACE_SUB_MERC: {
        "keywords":    'mace sub merc',
        "short_descr": 'A sub issue mace',
        "description": 'You see a sub issue mace here.',
        "material":    'bronze',
        "type": 'weapon',
        "wear_flags": {"take": True, "wield": True},
        "extra_flags": {"melt_drop": True},
        "weapon_type": 'mace', "dam_type": 'pound', "dice": (1, 6, 0),
        "weapon_flags": {},
        "stat_bonuses": {'hitroll': 1},
        "level": 1, "weight": 60, "value": 250,
        "extra_descs": [('mace', 'You see a mace of great but cheap craftsmanship.  Imprinted on the side is:\nMerc Industries')],
    },
    I_DAGGER_SUB_MERC: {
        "keywords":    'dagger sub merc',
        "short_descr": 'A sub issue dagger',
        "description": 'You see a sub issue dagger here.',
        "material":    'bronze',
        "type": 'weapon',
        "wear_flags": {"take": True, "wield": True},
        "extra_flags": {"melt_drop": True},
        "weapon_type": 'dagger', "dam_type": 'pierce', "dice": (1, 4, 0),
        "weapon_flags": {},
        "stat_bonuses": {'hitroll': 1},
        "level": 0, "weight": 10, "value": 210,
        "extra_descs": [('dagger', 'You see a dagger of great but cheap craftsmanship.  Imprinted on the side is:\nMerc Industries')],
    },
    I_SWORD_SUB_MERC: {
        "keywords":    'sword sub merc',
        "short_descr": 'A sub issue sword',
        "description": 'You see a sub issue sword here.',
        "material":    'bronze',
        "type": 'weapon',
        "wear_flags": {"take": True, "wield": True},
        "extra_flags": {"melt_drop": True},
        "weapon_type": 'sword', "dam_type": 'slash', "dice": (1, 6, 0),
        "weapon_flags": {},
        "stat_bonuses": {'hitroll': 1},
        "level": 1, "weight": 30, "value": 360,
        "extra_descs": [('sword', 'You see a sword of great but cheap craftsmanship.  Imprinted on the side is:\nMerc Industries')],
    },
    I_VEST_SUB_MERC: {
        "keywords":    'vest sub merc',
        "short_descr": 'A sub issue vest',
        "description": 'You see a sub issue vest here.',
        "material":    'leather',
        "type": 'armor',
        "wear_flags": {"take": True, "body": True},
        "extra_flags": {"melt_drop": True},
        "AC": 0,
        "level": 0, "weight": 50, "value": 144,
        "extra_descs": [('vest', 'You see a vest of great but cheap craftsmanship.  Stamped on the side is:\nMerc Industries')],
    },
    I_SHIELD_SUB_MERC: {
        "keywords":    'shield sub merc',
        "short_descr": 'A sub issue shield',
        "description": 'You see a sub issue shield here.',
        "material":    'wood',
        "type": 'armor',
        "wear_flags": {"take": True, "shield": True},
        "extra_flags": {"melt_drop": True},
        "AC": 0,
        "level": 0, "weight": 30, "value": 108,
        "extra_descs": [('shield', 'You see a shield of great but cheap craftsmanship.  Imprinted on the side is:\nMerc Industries')],
    },
    I_CLOAK_SUB_MERC: {
        "keywords":    'cloak sub merc',
        "short_descr": 'A sub issue cloak',
        "description": 'You see a sub issue cloak here.',
        "material":    'cloth',
        "type": 'armor',
        "wear_flags": {"take": True, "neck": True},
        "extra_flags": {"melt_drop": True},
        "AC": 0,
        "level": 0, "weight": 40, "value": 72,
        "extra_descs": [('cloak', 'You see a cloak of great but cheap craftsmanship.  Imprinted on the side is:\nMerc Industries')],
    },
    I_HELMET_SUB_MERC: {
        "keywords":    'helmet sub merc',
        "short_descr": 'A sub issue helmet',
        "description": 'You see a sub issue helmet here.',
        "material":    'leather',
        "type": 'armor',
        "wear_flags": {"take": True, "head": True},
        "extra_flags": {"melt_drop": True},
        "AC": 0,
        "level": 0, "weight": 30, "value": 72,
        "extra_descs": [('helmet', 'You see a helmet of great but cheap craftsmanship.  Imprinted on the side is:\nMerc Industries')],
    },
    I_LEGGINGS_SUB_MERC: {
        "keywords":    'leggings sub merc',
        "short_descr": 'A pair of sub issue leggings',
        "description": 'You see a pair of sub issue leggings here.',
        "material":    'leather',
        "type": 'armor',
        "wear_flags": {"take": True, "legs": True},
        "extra_flags": {"melt_drop": True},
        "AC": 0,
        "level": 0, "weight": 30, "value": 72,
        "extra_descs": [('leggings', 'You see leggings of great but cheap craftsmanship.  Imprinted on the side is:\nMerc Industries')],
    },
    I_BOOTS_SUB_MERC: {
        "keywords":    'boots sub merc',
        "short_descr": 'A pair of sub issue boots',
        "description": 'You see a pair of sub issue boots here.',
        "material":    'leather',
        "type": 'armor',
        "wear_flags": {"take": True, "feet": True},
        "extra_flags": {"melt_drop": True},
        "AC": 0,
        "level": 0, "weight": 30, "value": 72,
        "extra_descs": [('boots', 'You see boots of great but cheap craftsmanship.  Imprinted on the side is:\nMerc Industries')],
    },
    I_GLOVES_SUB_MERC: {
        "keywords":    'gloves sub merc',
        "short_descr": 'A pair of sub issue gloves',
        "description": 'You see a pair of sub issue gloves here.',
        "material":    'leather',
        "type": 'armor',
        "wear_flags": {"take": True, "hands": True},
        "extra_flags": {"melt_drop": True},
        "AC": 0,
        "level": 0, "weight": 10, "value": 72,
        "extra_descs": [('gloves', 'You see gloves of great but cheap craftsmanship.  Imprinted on the side is:\nMerc Industries')],
    },
    I_SLEEVES_SUB_MERC: {
        "keywords":    'sleeves sub merc',
        "short_descr": 'A pair of sub issue sleeves',
        "description": 'You see a pair of sub issue sleeves here.',
        "material":    'leather',
        "type": 'armor',
        "wear_flags": {"take": True, "arms": True},
        "extra_flags": {"melt_drop": True},
        "AC": 0,
        "level": 0, "weight": 20, "value": 72,
        "extra_descs": [('sleeves', 'You see sleeves of great but cheap craftsmanship.  Imprinted on the side is:\nMerc Industries')],
    },
    I_CAPE_SUB_MERC: {
        "keywords":    'cape sub merc',
        "short_descr": 'A sub issue cape',
        "description": 'You see a sub issue cape here.',
        "material":    'cloth',
        "type": 'armor',
        "wear_flags": {"take": True, "about": True},
        "extra_flags": {"melt_drop": True},
        "AC": 0,
        "level": 0, "weight": 20, "value": 72,
        "extra_descs": [('cape', 'You see a cape of great but cheap craftsmanship.  Imprinted on the side is:\nMerc Industries')],
    },
    I_BELT_SUB_MERC: {
        "keywords":    'belt sub merc',
        "short_descr": 'A sub issue belt',
        "description": 'You see a sub issue belt here.',
        "material":    'leather',
        "type": 'armor',
        "wear_flags": {"take": True, "waist": True},
        "extra_flags": {"melt_drop": True},
        "AC": 0,
        "level": 0, "weight": 10, "value": 72,
        "extra_descs": [('belt', 'You see a belt of great but cheap craftsmanship.  Imprinted on the side is:\nMerc Industries')],
    },
    I_BRACER_SUB_MERC: {
        "keywords":    'bracer sub merc',
        "short_descr": 'A sub issue bracer',
        "description": 'You see a sub issue bracer here.',
        "material":    'bronze',
        "type": 'armor',
        "wear_flags": {"take": True, "wrist": True},
        "extra_flags": {"melt_drop": True},
        "AC": 0,
        "level": 0, "weight": 10, "value": 48,
        "extra_descs": [('bracer', 'You see a bracer of great but cheap craftsmanship.  Imprinted on the side is:\nMerc Industries')],
    },
    I_KEY: {
        "keywords":    'key',
        "short_descr": 'A key',
        "description": 'You see a very important key here!',
        "material":    'brass',
        "type": 'key',
        "wear_flags": {"take": True},
        "extra_flags": {"_unknown_bits": [15]},
        "level": 0, "weight": 10, "value": 0,
    },
    I_DIPLOMA: {
        "keywords":    'diploma',
        "short_descr": 'A mud school diploma',
        "description": 'You see a mud school diploma here.',
        "material":    'vellum',
        "type": 'treasure',
        "wear_flags": {"take": True, "hold": True},
        "extra_flags": {"magic": True, "melt_drop": True},
        "stat_bonuses": {'con': 1, 'wis': 1},
        "level": 0, "weight": 10, "value": 1140,
        "extra_descs": [('diploma', 'This document shows that you have graduated from Mud School.\nIt also has magical effects on your abilities if you hold it!\n\nMerc Industries')],
    },
    I_BANNER_WAR_MERC: {
        "keywords":    'banner war merc',
        "short_descr": 'A war banner',
        "description": 'A war banner is on the floor here.',
        "material":    'cloth',
        "type": 'light',
        "wear_flags": {"take": True},
        "extra_flags": {"glow": True, "magic": True},
        "stat_bonuses": {'AC': -1},
        "level": 0, "weight": 20, "value": 380,
        "extra_descs": [('banner', 'This is the official Merc war banner to see you through the darkest realm!')],
    },
    I_SPEAR_SUB_MERC: {
        "keywords":    'spear sub merc',
        "short_descr": 'A sub issue spear',
        "description": 'You see a sub issue spear here.',
        "material":    'wood',
        "type": 'weapon',
        "wear_flags": {"take": True, "wield": True},
        "extra_flags": {"melt_drop": True},
        "weapon_type": 'staff', "dam_type": 'thrust', "dice": (1, 6, 0),
        "weapon_flags": {},
        "stat_bonuses": {'hitroll': 1},
        "level": 1, "weight": 50, "value": 111,
        "extra_descs": [('spear', 'You see a spear of great but cheap craftsmanship.  Imprinted on the side is:\nMerc Industries')],
    },
    I_STAFF_SUB_MERC: {
        "keywords":    'staff sub merc',
        "short_descr": 'A sub issue staff',
        "description": 'You see a sub issue staff here.',
        "material":    'wood',
        "type": 'weapon',
        "wear_flags": {"take": True, "wield": True},
        "extra_flags": {"melt_drop": True},
        "weapon_type": 'staff', "dam_type": 'pound', "dice": (1, 5, 0),
        "weapon_flags": {"two_hands": True},
        "stat_bonuses": {'damroll': 1, 'hitroll': 2},
        "level": 1, "weight": 40, "value": 290,
        "extra_descs": [('staff', 'You see a staff of great but cheap craftsmanship.  Imprinted on the side is:\nMerc Industries')],
    },
    I_AXE_SUB_MERC: {
        "keywords":    'axe sub merc',
        "short_descr": 'A sub issue axe',
        "description": 'You see a sub issue axe here.',
        "material":    'bronze',
        "type": 'weapon',
        "wear_flags": {"take": True, "wield": True},
        "extra_flags": {"melt_drop": True},
        "weapon_type": 'axe', "dam_type": 'chop', "dice": (1, 6, 0),
        "weapon_flags": {},
        "stat_bonuses": {'hitroll': 1},
        "level": 1, "weight": 50, "value": 350,
        "extra_descs": [('axe', 'You see an axe of great but cheap craftsmanship.  Imprinted on the side is:\nMerc Industries')],
    },
    I_FLAIL_SUB_MERC: {
        "keywords":    'flail sub merc',
        "short_descr": 'A sub issue flail',
        "description": 'You see a sub issue flail here.',
        "material":    'bronze',
        "type": 'weapon',
        "wear_flags": {"take": True, "wield": True},
        "extra_flags": {"melt_drop": True},
        "weapon_type": 'flail', "dam_type": 'crush', "dice": (1, 5, 0),
        "weapon_flags": {},
        "stat_bonuses": {'damroll': 1},
        "level": 1, "weight": 50, "value": 310,
        "extra_descs": [('flail', 'You see a flail of great but cheap craftsmanship.  Imprinted on the side is:\nMerc Industries')],
    },
    I_WHIP_SUB_MERC: {
        "keywords":    'whip sub merc',
        "short_descr": 'A sub issue whip',
        "description": 'You see a sub issue whip here.',
        "material":    'leather',
        "type": 'weapon',
        "wear_flags": {"take": True, "wield": True},
        "extra_flags": {"melt_drop": True},
        "weapon_type": 'whip', "dam_type": 'whip', "dice": (2, 2, 0),
        "weapon_flags": {},
        "stat_bonuses": {'hitroll': 2},
        "level": 1, "weight": 20, "value": 330,
        "extra_descs": [('whip', 'You see a whip of great but cheap craftsmanship.  Imprinted on the side is:\nMerc Industries')],
    },
    I_GLAIVE_SUB_MERC: {
        "keywords":    'glaive sub merc',
        "short_descr": 'A sub issue glaive',
        "description": 'You see a sub issue glaive here.',
        "material":    'wood',
        "type": 'weapon',
        "wear_flags": {"take": True, "wield": True},
        "extra_flags": {"melt_drop": True},
        "weapon_type": 'polearm', "dam_type": 'slash', "dice": (1, 7, 0),
        "weapon_flags": {"two_hands": True},
        "stat_bonuses": {'damroll': 1},
        "level": 1, "weight": 80, "value": 183,
        "extra_descs": [('glaive', 'You see a glaive of great but cheap craftsmanship.  Imprinted on the side is:\nMerc Industries')],
    },
}

# ── Resets ─────────────────────────────────────────────────────────────────────
# ("M", mob_template_vnum, global_limit, room_vnum, room_limit)  — spawn mob instance up to limits
# ("O", item_template_vnum, room_vnum) — place one item copy in room
# E/G/P/R/D/F resets from .are are not yet handled — see # TODO lines
RESETS = (
    # TODO: F 0 3700 2 0 +YY
    # TODO: F 0 3717 1 0 +YY
    # TODO: F 0 3719 1 0 +YYYnnY
    # TODO: F 0 3719 3 0 +YY
    # TODO: F 0 3721 0 0 +YY
    # TODO: F 0 3734 5 0 +YY
    # TODO: F 0 3748 4 0 +YY
    ("M", M_ACOLYTE_CLERIC, 1, R_ROOM_IN_MUD_SCHOOL, 1),
    ("M", M_BLOB, 1, R_BLOB_CAGE, 1),
    ("M", M_ADEPT_CLERIC, 1, R_CAGE_ROOM, 1),
    ("M", M_MONSTER_AGGRESSIVE, 1, R_CAGE, 1),
    # TODO: E 0 3707 0 7
    # TODO: E 0 3712 0 13
    ("M", M_MONSTER_WIMPY_AGGRESSIVE, 1, R_CAGE_3714, 1),
    # TODO: E 0 3708 0 8
    # TODO: E 0 3713 0 14
    ("M", M_MONSTER_WIMPY, 1, R_CAGE_3715, 1),
    # TODO: E 0 3706 0 6
    # TODO: E 0 3711 0 12
    ("M", M_MONSTER, 1, R_CAGE_3716, 1),
    # TODO: E 0 3705 0 3
    # TODO: E 0 3705 0 4
    ("M", M_ADEPT_CLERIC_3717, 1, R_STORE_IN_MUD_SCHOOL, 1),
    # TODO: G 0 3138 0
    # TODO: G 0 3031 0
    ("M", M_BIG_CREATURE, 1, R_DARKENED_ROOM, 1),
    # TODO: E 0 3709 0 9
    # TODO: E 0 3710 0 10
    # TODO: E 0 3714 0 17
    # TODO: E 0 3713 0 14
    ("M", M_DIPLOMA_BEAST, 1, R_END_OF_MUD_SCHOOL, 1),
    # TODO: E 0 3715 0 17
    ("M", M_ADEPT, 1, R_END_OF_MUD_SCHOOL, 1),
    ("M", M_SNAIL, 5, R_SOUTH_WEST_CORNER_OF_ARENA, 5),
    ("M", M_FOX, 3, R_SOUTH_EAST_CORNER_OF_ARENA, 3),
    ("M", M_RABBIT, 4, R_CENTER_OF_ARENA, 4),
    ("M", M_LIZARD, 3, R_NORTH_WEST_CORNER_OF_ARENA, 3),
    ("M", M_BOAR, 3, R_NORTH_EAST_CORNER_OF_ARENA, 3),
    ("M", M_BEAST, 1, R_NORTH_WEST_CORNER_OF_THE_DUNGEON, 1),
    ("M", M_BEAR, 2, R_NORTH_EAST_CORNER_OF_THE_DUNGEON, 2),
    ("M", M_WOLF, 2, R_SOUTH_WEST_CORNER_OF_THE_DUNGEON, 2),
    ("M", M_ADEPT_CLERIC_3718, 1, R_FUREY_S_TRAINING_ROOM, 1),
    ("M", M_PRIEST_CLERIC, 1, R_ZUMP_S_GUILD_ROOM, 1),
)
