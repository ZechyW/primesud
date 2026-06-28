# fmt: off
# Area: Graveyard
# Source: QuickMUD/ROM 2.4
# VNUM ranges: 3600-3699
# Credits: { 5 10} Alfa    Graveyard


AREA = {
    "name":     'Graveyard',
    "builders": '{ 5 10} Alfa    Graveyard',
    "vnums":    (3600, 3699),
    "credits":  '{ 5 10} Alfa    Graveyard',
    "levels":   (5, 10),
}

# -- Room VNUMs -----------------------------------------------------------------
R_GRAVEL_ROAD_IN_THE_GRAVEYARD     = 3600
R_GRAVEL_ROAD_IN_THE_GRAVEYARD_3601 = 3601
R_GRAVEL_ROAD_IN_THE_GRAVEYARD_3602 = 3602
R_GRAVEL_ROAD_IN_THE_GRAVEYARD_3603 = 3603
R_IN_FRONT_OF_THE_CHAPEL           = 3604
R_GRAVEL_PATH_ON_THE_GRAVEYARD     = 3606
R_IN_A_DUSTY_TOMB                  = 3607
R_GRAVEL_PATH_ON_THE_GRAVEYARD_3608 = 3608
R_IN_A_DUSTY_TOMB_3609             = 3609
R_GRAVEL_PATH_ON_THE_GRAVEYARD_3610 = 3610
R_IN_A_DUSTY_TOMB_3611             = 3611
R_GRAVEL_PATH_ON_THE_GRAVEYARD_3612 = 3612
R_IN_A_SHED_ON_THE_GRAVEYARD       = 3613
R_GRAVEL_PATH_ON_THE_GRAVEYARD_3614 = 3614
R_IN_A_DUSTY_TOMB_3615             = 3615
R_GRAVEL_PATH_ON_THE_GRAVEYARD_3616 = 3616
R_IN_A_DUSTY_TOMB_3617             = 3617
R_GRAVEL_PATH_ON_THE_GRAVEYARD_3618 = 3618
R_IN_A_DUSTY_TOMB_3619             = 3619
R_GRAVEL_PATH_ON_THE_GRAVEYARD_3638 = 3638
R_IN_A_DUSTY_TOMB_3639             = 3639
R_GRAVEL_PATH_ON_THE_GRAVEYARD_3640 = 3640
R_IN_A_DUSTY_TOMB_3641             = 3641
R_GRAVEL_PATH_ON_THE_GRAVEYARD_3642 = 3642
R_IN_A_DUSTY_TOMB_3643             = 3643
R_GRAVEL_PATH_ON_THE_GRAVEYARD_3644 = 3644
R_IN_A_DUSTY_TOMB_3645             = 3645
R_GRAVEL_PATH_ON_THE_GRAVEYARD_3646 = 3646
R_IN_A_DUSTY_TOMB_3647             = 3647
R_GRAVEL_PATH_ON_THE_GRAVEYARD_3648 = 3648
R_IN_A_DUSTY_TOMB_3649             = 3649
R_GRAVEL_PATH_ON_THE_GRAVEYARD_3650 = 3650
R_IN_A_DUSTY_TOMB_3651             = 3651

# -- Mob template VNUMs ---------------------------------------------------------
M_OLDSTYLE_HENRY_GARDENER          = 3600
M_OLDSTYLE_ZOMBIE                  = 3601
M_OLDSTYLE_GHOUL                   = 3602
M_OLDSTYLE_SKELETON                = 3603
M_OLDSTYLE_SKELETON_3604           = 3604
M_OLDSTYLE_ZOMBIE_3605             = 3605

# -- Item template VNUMs --------------------------------------------------------
I_CANDLESTICK                      = 3600
I_BRANDY_BOTTLE                    = 3601
I_BRANDY_BOTTLE_3602               = 3602
I_WHEELBARROW                      = 3603
I_SHOVEL                           = 3604
I_RAKE                             = 3605
I_SKELETON                         = 3610
I_AMETHYST_GEM                     = 3611
I_PENDANT_SILVER                   = 3612
I_DAGGER_SILVER                    = 3613

# -- Mob templates --------------------------------------------------------------
# hp_dice / mana_dice / damage: (num_dice, die_size, bonus)
# armor: (pierce, bash, slash, exotic), raw .are units
# hitroll: from mob level line
MOBILES = {
    M_OLDSTYLE_HENRY_GARDENER: {
        "keywords":    'oldstyle henry gardener',
        "short_descr": 'Henry the Gardener',
        "long_descr":  'Henry the Gardener is sitting here, looking drunk.',
        "description": 'He is a tall but bulky man in his late fifties.  His features are worn with\ndecades of hard work and his somewhat crouched expression is one of deep\nsorrow and depression.  He is haunted by a memory of a lost paradise.',
        "race":        'human',
        "act_flags": {"stay_area": True},
        "alignment": 350,
        "level":     4,
        "hitroll":   0,
        "hp_dice":   (2, 7, 46),
        "mana_dice": (2, 9, 100),
        "damage":    (1, 5, 1),  "dam_type": 'none',
        "armor":     (6, 6, 6, 9),
        "off_flags": {"disarm": True, "dodge": True, "trip": True, "assist_vnum": True},
        "start_pos":   'sit',
        "default_pos": 'sit',
        "material": '0',
        "sex":    'male',
        "wealth": 2,
        "size":   'medium',
    },
    M_OLDSTYLE_ZOMBIE: {
        "keywords":    'oldstyle zombie',
        "short_descr": 'the rotting zombie',
        "long_descr":  'A rotting zombie is staggering towards you with outstretched hands.',
        "description": 'Maggots crawl all over its decaying body.',
        "race":        'human',
        "act_flags": {"sentinel": True, "aggressive": True},
        "affected_by": {"infrared": True},
        "alignment": -750,
        "level":     4,
        "hitroll":   0,
        "hp_dice":   (2, 7, 46),
        "mana_dice": (2, 9, 100),
        "damage":    (1, 5, 1),  "dam_type": 'none',
        "armor":     (6, 6, 6, 9),
        "off_flags": {"disarm": True, "dodge": True, "trip": True, "assist_vnum": True},
        "start_pos":   'stand',
        "default_pos": 'stand',
        "material": '0',
        "sex":    'male',
        "wealth": 2,
        "size":   'medium',
    },
    M_OLDSTYLE_GHOUL: {
        "keywords":    'oldstyle ghoul',
        "short_descr": 'the ghastly ghoul',
        "long_descr":  'A ghastly ghoul is here.',
        "description": 'It is a walking corpse with long fangs and long, sharp nails that most of\nresemble claws.  Its eyes are a dark yellow colour and glare hungrily at you.',
        "race":        'human',
        "act_flags": {"sentinel": True, "aggressive": True},
        "affected_by": {"infrared": True},
        "alignment": -750,
        "level":     6,
        "hitroll":   0,
        "hp_dice":   (2, 7, 71),
        "mana_dice": (3, 9, 100),
        "damage":    (1, 7, 1),  "dam_type": 'none',
        "armor":     (4, 4, 4, 9),
        "off_flags": {"disarm": True, "dodge": True, "trip": True, "assist_vnum": True},
        "start_pos":   'stand',
        "default_pos": 'stand',
        "material": '0',
        "sex":    'male',
        "wealth": 5,
        "size":   'medium',
    },
    M_OLDSTYLE_SKELETON: {
        "keywords":    'oldstyle skeleton',
        "short_descr": 'a dusty skeleton',
        "long_descr":  'A dusty skeleton lies here.',
        "description": 'The dusty bones are almost brown.  It must have been buried for a very long\ntime.',
        "race":        'human',
        "act_flags": {"sentinel": True, "aggressive": True},
        "affected_by": {"infrared": True},
        "alignment": -750,
        "level":     3,
        "hitroll":   0,
        "hp_dice":   (2, 6, 35),
        "mana_dice": (1, 9, 100),
        "damage":    (1, 6, 0),  "dam_type": 'none',
        "armor":     (7, 7, 7, 10),
        "off_flags": {"disarm": True, "dodge": True, "trip": True, "assist_vnum": True},
        "start_pos":   'stand',
        "default_pos": 'stand',
        "material": '0',
        "sex":    'male',
        "wealth": 0,
        "size":   'medium',
    },
    M_OLDSTYLE_SKELETON_3604: {
        "keywords":    'oldstyle skeleton',
        "short_descr": 'a dusty skeleton',
        "long_descr":  'A dusty skeleton lies here.',
        "description": 'The dusty bones are almost brown.  It must have been buried for a very long\ntime.',
        "race":        'human',
        "act_flags": {"aggressive": True},
        "affected_by": {"infrared": True},
        "alignment": -750,
        "level":     3,
        "hitroll":   0,
        "hp_dice":   (2, 6, 35),
        "mana_dice": (1, 9, 100),
        "damage":    (1, 6, 0),  "dam_type": 'none',
        "armor":     (7, 7, 7, 10),
        "off_flags": {"disarm": True, "dodge": True, "trip": True, "assist_vnum": True},
        "start_pos":   'stand',
        "default_pos": 'stand',
        "material": '0',
        "sex":    'male',
        "wealth": 0,
        "size":   'medium',
    },
    M_OLDSTYLE_ZOMBIE_3605: {
        "keywords":    'oldstyle zombie',
        "short_descr": 'the rotting zombie',
        "long_descr":  'A rotting zombie is staggering towards you with outstretched hands.',
        "description": 'Maggots crawl all over its decaying body.',
        "race":        'human',
        "act_flags": {"aggressive": True},
        "affected_by": {"infrared": True},
        "alignment": -750,
        "level":     4,
        "hitroll":   0,
        "hp_dice":   (2, 7, 46),
        "mana_dice": (2, 9, 100),
        "damage":    (1, 5, 1),  "dam_type": 'none',
        "armor":     (6, 6, 6, 9),
        "off_flags": {"disarm": True, "dodge": True, "trip": True, "assist_vnum": True},
        "start_pos":   'stand',
        "default_pos": 'stand',
        "material": '0',
        "sex":    'male',
        "wealth": 5,
        "size":   'medium',
    },
}

# -- Specials -------------------------------------------------------------------
# ("M", mob_vnum, spec_fun_name) -- assign special function to mob template
SPECIALS = (
    ("M", M_OLDSTYLE_ZOMBIE, 'spec_cast_undead'),
    ("M", M_OLDSTYLE_GHOUL, 'spec_cast_undead'),
    ("M", M_OLDSTYLE_SKELETON, 'spec_cast_undead'),
    ("M", M_OLDSTYLE_SKELETON_3604, 'spec_cast_undead'),
    ("M", M_OLDSTYLE_ZOMBIE_3605, 'spec_cast_undead'),
)

# -- Rooms ----------------------------------------------------------------------
ROOMS = {
    R_GRAVEL_ROAD_IN_THE_GRAVEYARD: {
        "name": 'A Gravel Road in the Graveyard',
        "desc": 'You are on a well-kept gravel road that leads north-south through the\ngraveyard.  On both sides of the road grow dark evergreen trees.  An iron\ngrate is to the north and narrow gravel paths lead east and west.',
        "exits": {
            "n": {"to": 3124, "desc": 'Through the solid iron bars you see Elm Street.', "keyword": 'grate', "isdoor": True, "closed": True, "locked": True, "key": 3121},
            "e": {"to": R_GRAVEL_PATH_ON_THE_GRAVEYARD_3650, "desc": 'The gravel path leads eastwards between the dark evergreen trees.'},
            "s": {"to": R_GRAVEL_ROAD_IN_THE_GRAVEYARD_3601, "desc": 'The gravel road continues southwards.'},
            "w": {"to": R_GRAVEL_PATH_ON_THE_GRAVEYARD, "desc": 'The gravel path leads westwards between the dark evergreen trees.'},
        },
        "sector": 'field',
    },
    R_GRAVEL_ROAD_IN_THE_GRAVEYARD_3601: {
        "name": 'A Gravel Road in the Graveyard',
        "desc": 'You are on a well-kept gravel road that leads north-south through the\ngraveyard.  On both sides of the road grow dark evergreen trees.',
        "exits": {
            "n": {"to": R_GRAVEL_ROAD_IN_THE_GRAVEYARD, "desc": 'The gravel road continues northwards.'},
            "s": {"to": R_GRAVEL_ROAD_IN_THE_GRAVEYARD_3602, "desc": 'The gravel road continues southwards.'},
        },
        "sector": 'field',
    },
    R_GRAVEL_ROAD_IN_THE_GRAVEYARD_3602: {
        "name": 'A Gravel Road in the Graveyard',
        "desc": 'You are on a well-kept gravel road that leads north-south through the\ngraveyard.  On both sides of the road grow dark evergreen trees.',
        "exits": {
            "n": {"to": R_GRAVEL_ROAD_IN_THE_GRAVEYARD_3601, "desc": 'The gravel road continues northwards.'},
            "s": {"to": R_GRAVEL_ROAD_IN_THE_GRAVEYARD_3603, "desc": 'The gravel road continues southwards.'},
        },
        "sector": 'field',
    },
    R_GRAVEL_ROAD_IN_THE_GRAVEYARD_3603: {
        "name": 'A Gravel Road in the Graveyard',
        "desc": 'You are on a well-kept gravel road that leads north-south through the\ngraveyard.  On both sides of the road grow dark evergreen trees.',
        "exits": {
            "n": {"to": R_GRAVEL_ROAD_IN_THE_GRAVEYARD_3602, "desc": 'The gravel road continues northwards.'},
            "s": {"to": R_IN_FRONT_OF_THE_CHAPEL, "desc": 'The gravel road continues southwards to an open space before a small\nbuilding.'},
        },
        "sector": 'field',
    },
    R_IN_FRONT_OF_THE_CHAPEL: {
        "name": 'In front of the Chapel',
        "desc": 'You are on an open space before a small chapel.  A gravel road leads north\nthrough the graveyard and the chapel entrance is to the south.',
        "exits": {
            "n": {"to": R_GRAVEL_ROAD_IN_THE_GRAVEYARD_3603, "desc": 'The gravel road continues northwards.'},
            "e": {"to": R_GRAVEL_PATH_ON_THE_GRAVEYARD_3638, "desc": 'The gravel path leads eastwards between the dark evergreen trees.'},
            "s": {"to": 3405, "desc": 'The chapel door is made of dark wood.', "keyword": 'door', "isdoor": True, "closed": True},
            "w": {"to": R_GRAVEL_PATH_ON_THE_GRAVEYARD_3618, "desc": 'The gravel path leads westwards between the dark evergreen trees.'},
        },
        "sector": 'field',
    },
    R_GRAVEL_PATH_ON_THE_GRAVEYARD: {
        "name": 'A Gravel Path on the Graveyard',
        "desc": 'You are on a gravel path winding its way between dark evergreen trees on\nthe graveyard.  An old tomb is here.',
        "exits": {
            "e": {"to": R_GRAVEL_ROAD_IN_THE_GRAVEYARD, "desc": 'The gravel path continues eastwards towards a gravel road.'},
            "s": {"to": R_GRAVEL_PATH_ON_THE_GRAVEYARD_3608, "desc": 'The gravel path continues southwards.'},
            "d": {"to": R_IN_A_DUSTY_TOMB, "keyword": 'tomb stone', "isdoor": True, "closed": True},
        },
        "sector": 'field',
        "extra_descs": [('tomb stone', 'It is a large rectangular slab of dark grey stone that has been placed face\nup in the ground.  The name has been erased by the ravages of time.')],
    },
    R_IN_A_DUSTY_TOMB: {
        "name": 'In a dusty Tomb',
        "desc": 'You are in a dark burial chamber beneath a large tomb stone.\nThe only exit appears to be up.',
        "exits": {
            "u": {"to": R_GRAVEL_PATH_ON_THE_GRAVEYARD, "keyword": 'tomb stone', "isdoor": True, "closed": True},
        },
        "flags": {"dark": True, "indoors": True},
        "sector": 'city',
    },
    R_GRAVEL_PATH_ON_THE_GRAVEYARD_3608: {
        "name": 'A Gravel Path on the Graveyard',
        "desc": 'You are on a gravel path winding its way between dark evergreen trees on\nthe graveyard.  The path leads north and west.  An old tomb is here.',
        "exits": {
            "n": {"to": R_GRAVEL_PATH_ON_THE_GRAVEYARD, "desc": 'The gravel path continues northwards.'},
            "w": {"to": R_GRAVEL_PATH_ON_THE_GRAVEYARD_3610, "desc": 'The gravel path continues westwards.'},
            "d": {"to": R_IN_A_DUSTY_TOMB_3609, "keyword": 'tomb stone', "isdoor": True, "closed": True},
        },
        "sector": 'field',
        "extra_descs": [('tomb stone', 'It is a large rectangular slab of dark grey stone that has been placed face\nup in the ground.  The name has been erased by the ravages of time.')],
    },
    R_IN_A_DUSTY_TOMB_3609: {
        "name": 'In a dusty Tomb',
        "desc": 'You are in a dark burial chamber beneath a large tomb stone.\nThe only exit appears to be up.',
        "exits": {
            "u": {"to": R_GRAVEL_PATH_ON_THE_GRAVEYARD_3608, "keyword": 'tomb stone', "isdoor": True, "closed": True},
        },
        "flags": {"dark": True, "indoors": True},
        "sector": 'city',
    },
    R_GRAVEL_PATH_ON_THE_GRAVEYARD_3610: {
        "name": 'A Gravel Path on the Graveyard',
        "desc": 'You are on a gravel path winding its way between dark evergreen trees on\nthe graveyard.  The path leads east and south.  An old tomb is here.',
        "exits": {
            "e": {"to": R_GRAVEL_PATH_ON_THE_GRAVEYARD_3608, "desc": 'The gravel path continues eastwards.'},
            "s": {"to": R_GRAVEL_PATH_ON_THE_GRAVEYARD_3612, "desc": 'The gravel path continues southwards.'},
            "d": {"to": R_IN_A_DUSTY_TOMB_3611, "keyword": 'tomb stone', "isdoor": True, "closed": True},
        },
        "sector": 'field',
        "extra_descs": [('tomb stone', 'It is a large rectangular slab of dark grey stone that has been placed face\nup in the ground.  The name has been erased by the ravages of time.')],
    },
    R_IN_A_DUSTY_TOMB_3611: {
        "name": 'In a dusty Tomb',
        "desc": 'You are in a dark burial chamber beneath a large tomb stone.\nThe only exit appears to be up.',
        "exits": {
            "u": {"to": R_GRAVEL_PATH_ON_THE_GRAVEYARD_3610, "keyword": 'tomb stone', "isdoor": True, "closed": True},
        },
        "flags": {"dark": True, "indoors": True},
        "sector": 'city',
    },
    R_GRAVEL_PATH_ON_THE_GRAVEYARD_3612: {
        "name": 'A Gravel Path on the Graveyard',
        "desc": 'You are on a gravel path winding its way between dark evergreen trees on\nthe graveyard.  The path leads north and east.  A small shed is to the west.',
        "exits": {
            "n": {"to": R_GRAVEL_PATH_ON_THE_GRAVEYARD_3610, "desc": 'The gravel path continues northwards.'},
            "e": {"to": R_GRAVEL_PATH_ON_THE_GRAVEYARD_3614, "desc": 'The gravel path continues eastwards.'},
            "w": {"to": R_IN_A_SHED_ON_THE_GRAVEYARD, "desc": 'It is a small black-painted shed with a wooden door.', "keyword": 'door', "isdoor": True, "closed": True},
        },
        "sector": 'field',
    },
    R_IN_A_SHED_ON_THE_GRAVEYARD: {
        "name": 'In a shed on the Graveyard',
        "desc": 'You are in a small shed that looks as if it is used to store all sorts of\ngardening equipment.  The only exit appears to be through a door to the east.',
        "exits": {
            "e": {"to": R_GRAVEL_PATH_ON_THE_GRAVEYARD_3612, "keyword": 'door', "isdoor": True, "closed": True},
        },
        "flags": {"indoors": True},
        "sector": 'city',
    },
    R_GRAVEL_PATH_ON_THE_GRAVEYARD_3614: {
        "name": 'A Gravel Path on the Graveyard',
        "desc": 'You are on a gravel path winding its way between dark evergreen trees on\nthe graveyard.  The path leads south and west.  An old tomb is here.',
        "exits": {
            "s": {"to": R_GRAVEL_PATH_ON_THE_GRAVEYARD_3616, "desc": 'The gravel path continues southwards.'},
            "w": {"to": R_GRAVEL_PATH_ON_THE_GRAVEYARD_3612, "desc": 'The gravel path continues westwards.'},
            "d": {"to": R_IN_A_DUSTY_TOMB_3615, "keyword": 'tomb stone', "isdoor": True, "closed": True},
        },
        "sector": 'field',
        "extra_descs": [('tomb stone', 'It is a large rectangular slab of dark grey stone that has been placed face\nup in the ground.  The name has been erased by the ravages of time.')],
    },
    R_IN_A_DUSTY_TOMB_3615: {
        "name": 'In a dusty Tomb',
        "desc": 'You are in a dark burial chamber beneath a large tomb stone.\nThe only exit appears to be up.',
        "exits": {
            "u": {"to": R_GRAVEL_PATH_ON_THE_GRAVEYARD_3614, "keyword": 'tomb stone', "isdoor": True, "closed": True},
        },
        "flags": {"dark": True, "indoors": True},
        "sector": 'city',
    },
    R_GRAVEL_PATH_ON_THE_GRAVEYARD_3616: {
        "name": 'A Gravel Path on the Graveyard',
        "desc": 'You are on a gravel path winding its way between dark evergreen trees on\nthe graveyard.  The path leads north and south.  An old tomb is here.',
        "exits": {
            "n": {"to": R_GRAVEL_PATH_ON_THE_GRAVEYARD_3614, "desc": 'The gravel path continues northwards.'},
            "s": {"to": R_GRAVEL_PATH_ON_THE_GRAVEYARD_3618, "desc": 'The gravel path continues southwards.'},
            "d": {"to": R_IN_A_DUSTY_TOMB_3617, "keyword": 'tomb stone', "isdoor": True, "closed": True},
        },
        "sector": 'field',
        "extra_descs": [('tomb stone', 'It is a large rectangular slab of dark grey stone that has been placed face\nup in the ground.  The name has been erased by the ravages of time.')],
    },
    R_IN_A_DUSTY_TOMB_3617: {
        "name": 'In a dusty Tomb',
        "desc": 'You are in a dark burial chamber beneath a large tomb stone.\nThe only exit appears to be up.',
        "exits": {
            "u": {"to": R_GRAVEL_PATH_ON_THE_GRAVEYARD_3616, "keyword": 'tomb stone', "isdoor": True, "closed": True},
        },
        "flags": {"dark": True, "indoors": True},
        "sector": 'city',
    },
    R_GRAVEL_PATH_ON_THE_GRAVEYARD_3618: {
        "name": 'A Gravel Path on the Graveyard',
        "desc": 'You are on a gravel path winding its way between dark evergreen trees on\nthe graveyard.  The path leads north and east.  An old tomb is here.',
        "exits": {
            "n": {"to": R_GRAVEL_PATH_ON_THE_GRAVEYARD_3616, "desc": 'The gravel path continues northwards.'},
            "e": {"to": R_IN_FRONT_OF_THE_CHAPEL, "desc": 'The gravel path continues eastwards towards a building of some sort.'},
            "d": {"to": R_IN_A_DUSTY_TOMB_3619, "keyword": 'tomb stone', "isdoor": True, "closed": True},
        },
        "sector": 'field',
        "extra_descs": [('tomb stone', 'It is a large rectangular slab of dark grey stone that has been placed face\nup in the ground.  The name has been erased by the ravages of time.')],
    },
    R_IN_A_DUSTY_TOMB_3619: {
        "name": 'In a dusty Tomb',
        "desc": 'You are in a dark burial chamber beneath a large tomb stone.\nThe only exit appears to be up.',
        "exits": {
            "u": {"to": R_GRAVEL_PATH_ON_THE_GRAVEYARD_3618, "keyword": 'tomb stone', "isdoor": True, "closed": True},
        },
        "flags": {"dark": True, "indoors": True},
        "sector": 'city',
    },
    R_GRAVEL_PATH_ON_THE_GRAVEYARD_3638: {
        "name": 'A Gravel Path on the Graveyard',
        "desc": 'You are on a gravel path winding its way between dark evergreen trees on\nthe graveyard.  The path leads north and west.  An old tomb is here.',
        "exits": {
            "n": {"to": R_GRAVEL_PATH_ON_THE_GRAVEYARD_3640, "desc": 'The gravel path continues northwards.'},
            "w": {"to": R_IN_FRONT_OF_THE_CHAPEL, "desc": 'The gravel path continues westwards towards a building of some sort.'},
            "d": {"to": R_IN_A_DUSTY_TOMB_3639, "keyword": 'tomb stone', "isdoor": True, "closed": True},
        },
        "sector": 'field',
        "extra_descs": [('tomb stone', 'It is a large rectangular slab of dark grey stone that has been placed face\nup in the ground.  The name has been erased by the ravages of time.')],
    },
    R_IN_A_DUSTY_TOMB_3639: {
        "name": 'In a dusty Tomb',
        "desc": 'You are in a dark burial chamber beneath a large tomb stone.\nThe only exit appears to be up.',
        "exits": {
            "u": {"to": R_GRAVEL_PATH_ON_THE_GRAVEYARD_3638, "keyword": 'tomb stone', "isdoor": True, "closed": True},
        },
        "flags": {"dark": True, "indoors": True},
        "sector": 'city',
    },
    R_GRAVEL_PATH_ON_THE_GRAVEYARD_3640: {
        "name": 'A Gravel Path on the Graveyard',
        "desc": 'You are on a gravel path winding its way between dark evergreen trees on\nthe graveyard.  The path leads north and south.  An old tomb is here.',
        "exits": {
            "n": {"to": R_GRAVEL_PATH_ON_THE_GRAVEYARD_3642, "desc": 'The gravel path continues northwards.'},
            "s": {"to": R_GRAVEL_PATH_ON_THE_GRAVEYARD_3638, "desc": 'The gravel path continues southwards.'},
            "d": {"to": R_IN_A_DUSTY_TOMB_3641, "keyword": 'tomb stone', "isdoor": True, "closed": True},
        },
        "sector": 'field',
        "extra_descs": [('tomb stone', 'It is a large rectangular slab of dark grey stone that has been placed face\nup in the ground.  The name has been erased by the ravages of time.')],
    },
    R_IN_A_DUSTY_TOMB_3641: {
        "name": 'In a dusty Tomb',
        "desc": 'You are in a dark burial chamber beneath a large tomb stone.\nThe only exit appears to be up.',
        "exits": {
            "u": {"to": R_GRAVEL_PATH_ON_THE_GRAVEYARD_3640, "keyword": 'tomb stone', "isdoor": True, "closed": True},
        },
        "flags": {"dark": True, "indoors": True},
        "sector": 'city',
    },
    R_GRAVEL_PATH_ON_THE_GRAVEYARD_3642: {
        "name": 'A Gravel Path on the Graveyard',
        "desc": 'You are on a gravel path winding its way between dark evergreen trees on\nthe graveyard.  The path leads east and south.  An old tomb is here.',
        "exits": {
            "e": {"to": R_GRAVEL_PATH_ON_THE_GRAVEYARD_3644, "desc": 'The gravel path continues eastwards.'},
            "s": {"to": R_GRAVEL_PATH_ON_THE_GRAVEYARD_3640, "desc": 'The gravel path continues southwards.'},
            "d": {"to": R_IN_A_DUSTY_TOMB_3643, "keyword": 'tomb stone', "isdoor": True, "closed": True},
        },
        "sector": 'field',
        "extra_descs": [('tomb stone', 'It is a large rectangular slab of dark grey stone that has been placed face\nup in the ground.  The name has been erased by the ravages of time.')],
    },
    R_IN_A_DUSTY_TOMB_3643: {
        "name": 'In a dusty Tomb',
        "desc": 'You are in a dark burial chamber beneath a large tomb stone.\nThe only exit appears to be up.',
        "exits": {
            "u": {"to": R_GRAVEL_PATH_ON_THE_GRAVEYARD_3642, "keyword": 'tomb stone', "isdoor": True, "closed": True},
        },
        "flags": {"dark": True, "indoors": True},
        "sector": 'city',
    },
    R_GRAVEL_PATH_ON_THE_GRAVEYARD_3644: {
        "name": 'A Gravel Path on the Graveyard',
        "desc": 'You are on a gravel path winding its way between dark evergreen trees on\nthe graveyard.  The path leads north and west.  An old tomb is here.',
        "exits": {
            "n": {"to": R_GRAVEL_PATH_ON_THE_GRAVEYARD_3646, "desc": 'The gravel path continues northwards.'},
            "w": {"to": R_GRAVEL_PATH_ON_THE_GRAVEYARD_3642, "desc": 'The gravel path continues westwards.'},
            "d": {"to": R_IN_A_DUSTY_TOMB_3645, "keyword": 'tomb stone', "isdoor": True, "closed": True},
        },
        "sector": 'field',
        "extra_descs": [('tomb stone', 'It is a large rectangular slab of dark grey stone that has been placed face\nup in the ground.  The name has been erased by the ravages of time.')],
    },
    R_IN_A_DUSTY_TOMB_3645: {
        "name": 'In a dusty Tomb',
        "desc": 'You are in a dark burial chamber beneath a large tomb stone.\nThe only exit appears to be up.',
        "exits": {
            "u": {"to": R_GRAVEL_PATH_ON_THE_GRAVEYARD_3644, "keyword": 'tomb stone', "isdoor": True, "closed": True},
        },
        "flags": {"dark": True, "indoors": True},
        "sector": 'city',
    },
    R_GRAVEL_PATH_ON_THE_GRAVEYARD_3646: {
        "name": 'A Gravel Path on the Graveyard',
        "desc": 'You are on a gravel path winding its way between dark evergreen trees on\nthe graveyard.  The path leads south and west.  An old tomb is here.',
        "exits": {
            "s": {"to": R_GRAVEL_PATH_ON_THE_GRAVEYARD_3644, "desc": 'The gravel path continues southwards.'},
            "w": {"to": R_GRAVEL_PATH_ON_THE_GRAVEYARD_3648, "desc": 'The gravel path continues westwards.'},
            "d": {"to": R_IN_A_DUSTY_TOMB_3647, "keyword": 'tomb stone', "isdoor": True, "closed": True},
        },
        "sector": 'field',
        "extra_descs": [('tomb stone', 'It is a large rectangular slab of dark grey stone that has been placed face\nup in the ground.  The name has been erased by the ravages of time.')],
    },
    R_IN_A_DUSTY_TOMB_3647: {
        "name": 'In a dusty Tomb',
        "desc": 'You are in a dark burial chamber beneath a large tomb stone.\nThe only exit appears to be up.',
        "exits": {
            "u": {"to": R_GRAVEL_PATH_ON_THE_GRAVEYARD_3646, "keyword": 'tomb stone', "isdoor": True, "closed": True},
        },
        "flags": {"dark": True, "indoors": True},
        "sector": 'city',
    },
    R_GRAVEL_PATH_ON_THE_GRAVEYARD_3648: {
        "name": 'A Gravel Path on the Graveyard',
        "desc": 'You are on a gravel path winding its way between dark evergreen trees on\nthe graveyard.  The path leads north and east.  An old tomb is here.',
        "exits": {
            "n": {"to": R_GRAVEL_PATH_ON_THE_GRAVEYARD_3650, "desc": 'The gravel path continues northwards.'},
            "e": {"to": R_GRAVEL_PATH_ON_THE_GRAVEYARD_3646, "desc": 'The gravel path continues eastwards.'},
            "d": {"to": R_IN_A_DUSTY_TOMB_3649, "keyword": 'tomb stone', "isdoor": True, "closed": True},
        },
        "sector": 'field',
        "extra_descs": [('tomb stone', 'It is a large rectangular slab of dark grey stone that has been placed face\nup in the ground.  The name has been erased by the ravages of time.')],
    },
    R_IN_A_DUSTY_TOMB_3649: {
        "name": 'In a dusty Tomb',
        "desc": 'You are in a dark burial chamber beneath a large tomb stone.\nThe only exit appears to be up.',
        "exits": {
            "u": {"to": R_GRAVEL_PATH_ON_THE_GRAVEYARD_3648, "keyword": 'tomb stone', "isdoor": True, "closed": True},
        },
        "flags": {"dark": True, "indoors": True},
        "sector": 'city',
    },
    R_GRAVEL_PATH_ON_THE_GRAVEYARD_3650: {
        "name": 'A Gravel Path on the Graveyard',
        "desc": 'You are on a gravel path winding its way between dark evergreen trees on\nthe graveyard.  The path leads south and west.  An old tomb is here.',
        "exits": {
            "s": {"to": R_GRAVEL_PATH_ON_THE_GRAVEYARD_3648, "desc": 'The gravel path continues southwards.'},
            "w": {"to": R_GRAVEL_ROAD_IN_THE_GRAVEYARD, "desc": 'The gravel path continues westwards towards a gravel road.'},
            "d": {"to": R_IN_A_DUSTY_TOMB_3651, "keyword": 'tomb stone', "isdoor": True, "closed": True},
        },
        "sector": 'field',
        "extra_descs": [('tomb stone', 'It is a large rectangular slab of dark grey stone that has been placed face\nup in the ground.  The name has been erased by the ravages of time.')],
    },
    R_IN_A_DUSTY_TOMB_3651: {
        "name": 'In a dusty Tomb',
        "desc": 'You are in a dark burial chamber beneath a large tomb stone.\nThe only exit appears to be up.',
        "exits": {
            "u": {"to": R_GRAVEL_PATH_ON_THE_GRAVEYARD_3650, "keyword": 'tomb stone', "isdoor": True, "closed": True},
        },
        "flags": {"dark": True, "indoors": True},
        "sector": 'city',
    },
}

# -- Item templates -------------------------------------------------------------
OBJECTS = {
    I_CANDLESTICK: {
        "keywords":    'candlestick',
        "short_descr": 'a candlestick',
        "description": 'A pewter candlestick is standing here.',
        "material":    'oldstyle',
        "type": 'light',
        "wear_flags": {"take": True, "hold": True},
        "level": 0, "weight": 50, "value": 10,
        "extra_descs": [('candlestick', 'It is a rather old-looking three-armed candlestick made from pewter.  Its\ncandles are a yellowish white colour.')],
    },
    I_BRANDY_BOTTLE: {
        "keywords":    'brandy bottle',
        "short_descr": 'a brandy bottle',
        "description": 'A brandy bottle is lying here.',
        "material":    'oldstyle',
        "type": 'drink',
        "wear_flags": {"take": True},
        "liquid_total": 32, "liquid_left": 32,
        "liquid_type": 'whisky',
        "level": 0, "weight": 20, "value": 100,
        "extra_descs": [('brandy bottle', "The bottle is a special 'Dragon Blood' brandy bottle.  Its neck is shaped\nlike a small dragon's head.  Bottles like these are often worth a small\namount money, even when empty.")],
    },
    I_BRANDY_BOTTLE_3602: {
        "keywords":    'brandy bottle',
        "short_descr": 'a brandy bottle',
        "description": 'A brandy bottle is lying here.',
        "material":    'oldstyle',
        "type": 'drink',
        "wear_flags": {"take": True},
        "liquid_total": 32, "liquid_left": 0,
        "liquid_type": 'whisky',
        "level": 0, "weight": 20, "value": 100,
        "extra_descs": [('brandy bottle', "The bottle is a special 'Dragon Blood' brandy bottle.  Its neck is shaped\nlike a small dragon's head.  Bottles like these are often worth some money,\neven when empty.")],
    },
    I_WHEELBARROW: {
        "keywords":    'wheelbarrow',
        "short_descr": 'a wheelbarrow',
        "description": 'A green-painted wheelbarrow is standing here.',
        "material":    'oldstyle',
        "type": 'boat',
        "wear_flags": {"take": True},
        "level": 0, "weight": 1000, "value": 50,
        "extra_descs": [('wheelbarrow', 'It is a heavy wheelbarrow made from solid oaken planks that have been painted\na dark, green colour.')],
    },
    I_SHOVEL: {
        "keywords":    'shovel',
        "short_descr": 'a shovel',
        "description": 'A shovel is lying here.',
        "material":    'oldstyle',
        "type": 'weapon',
        "wear_flags": {"take": True, "wield": True},
        "weapon_type": 'mace', "dam_type": 'pound', "dice": (1, 5, 0),
        "weapon_flags": {},
        "level": 0, "weight": 80, "value": 169,
        "extra_descs": [('shovel', 'It is a large metal shovel with a solid wooden handle.')],
    },
    I_RAKE: {
        "keywords":    'rake',
        "short_descr": 'a rake',
        "description": 'A rake is lying here.',
        "material":    'oldstyle',
        "type": 'weapon',
        "wear_flags": {"take": True, "wield": True},
        "weapon_type": 'mace', "dam_type": 'claw', "dice": (1, 4, 0),
        "weapon_flags": {},
        "level": 0, "weight": 80, "value": 140,
        "extra_descs": [('rake', 'It is a large metal rake with a solid wooden handle.')],
    },
    I_SKELETON: {
        "keywords":    'skeleton',
        "short_descr": 'a dusty skeleton',
        "description": 'A dusty skeleton lies here.',
        "material":    'oldstyle',
        "type": 'furniture',
        "wear_flags": {"take": True},
        "level": 0, "weight": 150, "value": 0,
        "extra_descs": [('skeleton', 'The dusty bones are almost brown.  It must have been buried for a very long\ntime.\nA dusty skeleton is in an excellent condition.')],
    },
    I_AMETHYST_GEM: {
        "keywords":    'amethyst gem',
        "short_descr": 'a amethyst',
        "description": 'A large, beautifully polished amethyst has been left here.',
        "material":    'oldstyle',
        "type": 'warp_stone',
        "wear_flags": {"take": True, "hold": True},
        "extra_flags": {"nolocate": True},
        "level": 0, "weight": 10, "value": 2500,
        "extra_descs": [('amethyst', 'It has a very deep purple colour.')],
    },
    I_PENDANT_SILVER: {
        "keywords":    'pendant silver',
        "short_descr": 'a silver pendant',
        "description": 'A silver pendant has been left here.',
        "material":    'oldstyle',
        "type": 'jewelry',
        "wear_flags": {"take": True, "neck": True},
        "stat_bonuses": {'str': 1, 'ac': -1},
        "level": 7, "weight": 10, "value": 800,
        "extra_descs": [('pendant silver', "It resembles Thor's hammer and appears to be made of solid silver.")],
    },
    I_DAGGER_SILVER: {
        "keywords":    'dagger silver',
        "short_descr": 'a silver dagger',
        "description": 'A long silver dagger is lying here.',
        "material":    'oldstyle',
        "type": 'weapon',
        "wear_flags": {"take": True, "wield": True},
        "weapon_type": 'dagger', "dam_type": 'pierce', "dice": (2, 4, 0),
        "weapon_flags": {},
        "stat_bonuses": {'damroll': 1},
        "level": 6, "weight": 10, "value": 430,
        "extra_descs": [('dagger silver', 'It has a long, sharp blade that is made entirely from silver.  A small rune\nhas been engraved on the blade next to the hilt.')],
    },
}

# -- Resets ---------------------------------------------------------------------
# ("M", mob_vnum, global_limit, room_vnum, room_limit) -- spawn mob up to limits
# ("O", item_vnum, room_vnum)                          -- place one item copy in room
# ("E", item_vnum, slot_name)                          -- equip item on last M mob
# ("G", item_vnum)                                     -- give item to last M mob inventory
# ("P", item_vnum, limit, container_vnum, max)         -- [PRIMESUD] deferred: no containers
# ("R", room_vnum, num_dirs)                           -- [PRIMESUD] deferred: unused in current areas
# D resets are baked into room exit flags at conversion time
RESETS = (
    ("O", I_SKELETON, R_IN_A_DUSTY_TOMB),
    ("M", M_OLDSTYLE_SKELETON, 4, R_IN_A_DUSTY_TOMB_3609, 1),
    ("M", M_OLDSTYLE_SKELETON, 4, R_IN_A_DUSTY_TOMB_3611, 1),
    ("O", I_DAGGER_SILVER, R_IN_A_DUSTY_TOMB_3611),
    ("M", M_OLDSTYLE_HENRY_GARDENER, 1, R_IN_A_SHED_ON_THE_GRAVEYARD, 1),
    ("G", I_BRANDY_BOTTLE),
    ("O", I_BRANDY_BOTTLE_3602, R_IN_A_SHED_ON_THE_GRAVEYARD),
    ("O", I_WHEELBARROW, R_IN_A_SHED_ON_THE_GRAVEYARD),
    ("O", I_SHOVEL, R_IN_A_SHED_ON_THE_GRAVEYARD),
    ("O", I_RAKE, R_IN_A_SHED_ON_THE_GRAVEYARD),
    ("O", I_SKELETON, R_IN_A_DUSTY_TOMB_3615),
    ("M", M_OLDSTYLE_GHOUL, 1, R_IN_A_DUSTY_TOMB_3617, 1),
    ("G", I_PENDANT_SILVER),
    ("O", I_SKELETON, R_IN_A_DUSTY_TOMB_3619),
    ("M", M_OLDSTYLE_SKELETON, 4, R_IN_A_DUSTY_TOMB_3639, 1),
    ("O", I_SKELETON, R_IN_A_DUSTY_TOMB_3641),
    ("O", I_WHEELBARROW, R_IN_A_DUSTY_TOMB_3643),
    ("M", M_OLDSTYLE_ZOMBIE, 1, R_IN_A_DUSTY_TOMB_3645, 1),
    ("G", I_AMETHYST_GEM),
    ("O", I_SKELETON, R_IN_A_DUSTY_TOMB_3647),
    ("M", M_OLDSTYLE_SKELETON, 4, R_IN_A_DUSTY_TOMB_3649, 1),
    ("M", M_OLDSTYLE_SKELETON_3604, 4, R_GRAVEL_PATH_ON_THE_GRAVEYARD, 1),
    ("M", M_OLDSTYLE_SKELETON_3604, 4, R_IN_FRONT_OF_THE_CHAPEL, 1),
    ("M", M_OLDSTYLE_SKELETON_3604, 4, R_GRAVEL_PATH_ON_THE_GRAVEYARD_3612, 1),
    ("M", M_OLDSTYLE_SKELETON_3604, 4, R_GRAVEL_PATH_ON_THE_GRAVEYARD_3640, 1),
    ("M", M_OLDSTYLE_ZOMBIE_3605, 3, R_IN_A_DUSTY_TOMB_3651, 1),
    ("M", M_OLDSTYLE_ZOMBIE_3605, 3, R_GRAVEL_PATH_ON_THE_GRAVEYARD_3644, 1),
    ("M", M_OLDSTYLE_ZOMBIE_3605, 3, R_GRAVEL_PATH_ON_THE_GRAVEYARD_3638, 1),
)

# -- Shops ---------------------------------------------------------------------
# keeper_vnum: mob that runs the shop
# buy_types: item type names the shop will purchase
# profit_buy/profit_sell: percentage markup/markdown
SHOPS = (
)

# -- Helps ---------------------------------------------------------------------
HELPS = (
)

# -- Socials -------------------------------------------------------------------
SOCIALS = (
)

# -- MobProgs ------------------------------------------------------------------
# (vnum, code) -- mob program code blocks, referenced by mob triggers
MOBPROGS = {
}
