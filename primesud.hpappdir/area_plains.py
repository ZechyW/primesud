# fmt: off
# Area: Plains
# Source: QuickMUD/ROM 2.4
# VNUM ranges: 300-399
# Credits: { 1 20} Copper  Plains of the North


AREA = {
    "name":     'Plains',
    "builders": '{ 1 20} Copper  Plains of the North',
    "vnums":    (300, 399),
    "credits":  '{ 1 20} Copper  Plains of the North',
    "levels":   (1, 20),
}

# -- Room VNUMs -----------------------------------------------------------------
R_PATH_IN_THE_PLAINS               = 300
R_PATH_IN_THE_PLAINS_301           = 301
R_PATH_IN_THE_PLAINS_302           = 302
R_PATH_IN_THE_PLAINS_303           = 303
R_PATH_IN_THE_PLAINS_304           = 304
R_PATH_IN_THE_PLAINS_305           = 305
R_PATH_IN_THE_FOOTHILLS            = 306
R_PATH_IN_THE_FOOTHILLS_307        = 307
R_PATH_IN_THE_FOOTHILLS_308        = 308
R_PATH_IN_THE_FOOTHILLS_309        = 309
R_PATH_IN_THE_FOOTHILLS_310        = 310
R_PATH_IN_THE_FOOTHILLS_311        = 311
R_PATH_INTERSECTION                = 312
R_ROAD_TO_OFCOL                    = 313
R_OUTSIDE_OFCOL                    = 314
R_GALLOW_HILL                      = 315
R_GRASSY_PLAINS                    = 316
R_GRASSY_PLAINS_317                = 317
R_GRASSY_PLAINS_318                = 318
R_GRASSY_PLAINS_319                = 319
R_GRASSY_PLAINS_320                = 320
R_GRASSY_PLAINS_321                = 321
R_GRASSY_FOOTHILLS                 = 322
R_STEEP_FOOTHILLS                  = 323
R_STEEP_FOOTHILLS_324              = 324
R_STEEP_FOOTHILLS_325              = 325
R_POOL_IN_THE_FOOTHILLS            = 326
R_FOOTHILLS                        = 327
R_IN_FRONT_OF_HUT_IN_FOOTHILLS     = 330
R_HERMIT_S_HUT                     = 331
R_ANCIENT_PATH                     = 332
R_ANCIENT_PATH_333                 = 333
R_ANCIENT_PATH_334                 = 334
R_ANCIENT_PATH_335                 = 335
R_WOODEN_BRIDGE                    = 336
R_ANCIENT_PATH_337                 = 337
R_GRASSY_PLAINS_338                = 338
R_STONES_OF_G_HARNE                = 339
R_DARK_SMELLY_TUNNELS              = 340
R_DEAD_END_OF_TUNNEL               = 341
R_DARK_SMELLY_TUNNELS_342          = 342
R_DARK_SMELLY_TUNNELS_343          = 343
R_HALL_OF_G_HARNE                  = 344
R_STEEP_SLOPE                      = 345

# -- Mob template VNUMs ---------------------------------------------------------
M_OLDSTYLE_DRUID_ARUNCUS           = 300
M_OLDSTYLE_HERMIT_SORBUS           = 301
M_OLDSTYLE_CITIZEN                 = 303
M_OLDSTYLE_CITIZEN_304             = 304
M_OLDSTYLE_WORM_SHUDDE_M_ELL       = 305
M_OLDSTYLE_LUXAN_SHOPKEEPER        = 306
M_OLDSTYLE_KEEPER_INNKEEPER        = 308
M_OLDSTYLE_RABBIT                  = 309
M_OLDSTYLE_DRAGON_PET              = 350

# -- Item template VNUMs --------------------------------------------------------
I_HERBS_HERB_TIMIAN                = 300
I_HERBS_HERB_GYVEL                 = 301
I_PLANT_IVY                        = 302
I_BLOOD_JAR                        = 303
I_WILD_FLOWERS                     = 304
I_AMULET                           = 307
I_STAFF_STICK                      = 308
I_RABBIT_ROAST_WABBIT              = 309
I_TEMPLATE_SCROLL                  = 310
I_POTION_CLEAR                     = 311
I_SCROLL_JHYFRDOW                  = 312

# -- Mob templates --------------------------------------------------------------
# hp_dice / mana_dice / damage: (num_dice, die_size, bonus)
# armor: (pierce, bash, slash, exotic), raw .are units
# hitroll: from mob level line
MOBILES = {
    M_OLDSTYLE_DRUID_ARUNCUS: {
        "keywords":    'oldstyle druid Aruncus',
        "short_descr": 'Aruncus the Druid',
        "long_descr":  'Aruncus the Druid is walking around here, searching for herbs.',
        "description": 'Aruncus is a tall, skinny druid with a face marked by nature.\nHe seems to be in peace with himself and his surroundings.',
        "race":        'human',
        "act_flags": {"stay_area": True, "wimpy": True},
        "affected_by": {"detect_invis": True},
        "alignment": -500,
        "level":     13,
        "hitroll":   0,
        "hp_dice":   (2, 10, 170),
        "mana_dice": (6, 9, 100),
        "damage":    (2, 5, 3),  "dam_type": 'none',
        "armor":     (-1, -1, -1, 8),
        "off_flags": {"disarm": True, "dodge": True, "trip": True, "assist_vnum": True},
        "start_pos":   'stand',
        "default_pos": 'stand',
        "material": '0',
        "sex":    'male',
        "wealth": 25,
        "size":   'medium',
    },
    M_OLDSTYLE_HERMIT_SORBUS: {
        "keywords":    'oldstyle hermit sorbus',
        "short_descr": 'Sorbus the Hermit',
        "long_descr":  'Sorbus the Hermit is sitting here, roasting a rabbit.',
        "description": 'Sorbus bares the marks of a long, hard life in solitude.\nHe is dressed in simple clothing and looks like he has little\nor nothing to say.',
        "race":        'human',
        "act_flags": {"sentinel": True},
        "alignment": 0,
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
        "wealth": 0,
        "size":   'medium',
    },
    M_OLDSTYLE_CITIZEN: {
        "keywords":    'oldstyle citizen',
        "short_descr": 'the citizen',
        "long_descr":  'There is a citizen of Ofcol here glaring at you ... stranger!',
        "description": 'He seems like a nice person with no interest in harming you or others.\nHe wears normal, light clothing and has an anonymous face.',
        "race":        'human',
        "act_flags": {"scavenger": True, "stay_area": True},
        "alignment": 0,
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
        "wealth": 10,
        "size":   'medium',
    },
    M_OLDSTYLE_CITIZEN_304: {
        "keywords":    'oldstyle citizen',
        "short_descr": 'the citizen',
        "long_descr":  'There is a citizen of Ofcol here glaring at you ... stranger!',
        "description": 'She seems like a nice person with no interest in harming you or others.\nShe wears a minimum of clothing and has big ... eyes.',
        "race":        'human',
        "act_flags": {"scavenger": True, "stay_area": True},
        "alignment": 0,
        "level":     5,
        "hitroll":   0,
        "hp_dice":   (2, 6, 60),
        "mana_dice": (2, 9, 100),
        "damage":    (1, 6, 1),  "dam_type": 'none',
        "armor":     (5, 5, 5, 9),
        "off_flags": {"disarm": True, "dodge": True, "trip": True, "assist_vnum": True},
        "start_pos":   'stand',
        "default_pos": 'stand',
        "material": '0',
        "sex":    'female',
        "wealth": 5,
        "size":   'medium',
    },
    M_OLDSTYLE_WORM_SHUDDE_M_ELL: {
        "keywords":    "oldstyle worm Shudde-M'ell",
        "short_descr": "Shudde-M'ell",
        "long_descr":  "Shudde-M'ell the Giant worm of G'harne is guarding his treasure.",
        "description": "Shudde-M'ell is about 15 ft long and is surrounded by an evil stench,\nThe worm is the protector of the treasure of G'harne and has been so\nfor as long anyone can remember.",
        "race":        'human',
        "act_flags": {"sentinel": True, "aggressive": True},
        "affected_by": {"detect_invis": True},
        "alignment": -1000,
        "level":     24,
        "hitroll":   0,
        "hp_dice":   (5, 10, 500),
        "mana_dice": (12, 9, 100),
        "damage":    (2, 10, 6),  "dam_type": 'none',
        "armor":     (-6, -6, -6, 6),
        "off_flags": {"disarm": True, "dodge": True, "trip": True, "assist_vnum": True},
        "start_pos":   'stand',
        "default_pos": 'stand',
        "material": '0',
        "sex":    'male',
        "wealth": 683,
        "size":   'medium',
    },
    M_OLDSTYLE_LUXAN_SHOPKEEPER: {
        "keywords":    'oldstyle luxan shopkeeper',
        "short_descr": 'Luxan',
        "long_descr":  'Luxan the Shopkeeper is here, eager to sell you anything.',
        "description": 'Luxan is dressed in a strange jacket.\nHe looks like a mean trader from the outskirts of Midgaard.\nHis life is seems to be totally occupied with trading.\nHe looks very fit and capable of protecting his goods.',
        "race":        'human',
        "act_flags": {"sentinel": True, "scavenger": True},
        "alignment": 400,
        "level":     23,
        "hitroll":   0,
        "hp_dice":   (5, 10, 450),
        "mana_dice": (11, 9, 100),
        "damage":    (3, 6, 6),  "dam_type": 'none',
        "armor":     (-6, -6, -6, 6),
        "off_flags": {"disarm": True, "dodge": True, "trip": True, "assist_vnum": True},
        "start_pos":   'stand',
        "default_pos": 'stand',
        "material": '0',
        "sex":    'male',
        "wealth": 400,
        "size":   'medium',
    },
    M_OLDSTYLE_KEEPER_INNKEEPER: {
        "keywords":    'oldstyle keeper innkeeper',
        "short_descr": 'the Innkeeper',
        "long_descr":  'An Innkeeper is here waiting for your order.',
        "description": 'The Innkeeper looks skilled in brewing different beers and mixing the\nwierdest drinks known. He also looks very big.',
        "race":        'human',
        "act_flags": {"sentinel": True},
        "alignment": -100,
        "level":     23,
        "hitroll":   0,
        "hp_dice":   (5, 10, 450),
        "mana_dice": (11, 9, 100),
        "damage":    (3, 6, 6),  "dam_type": 'none',
        "armor":     (-6, -6, -6, 6),
        "off_flags": {"disarm": True, "dodge": True, "trip": True, "assist_vnum": True},
        "start_pos":   'stand',
        "default_pos": 'stand',
        "material": '0',
        "sex":    'male',
        "wealth": 5,
        "size":   'medium',
    },
    M_OLDSTYLE_RABBIT: {
        "keywords":    'oldstyle rabbit',
        "short_descr": 'the cute rabbit',
        "long_descr":  'A cute rabbit is here.',
        "description": 'It is a small, furry creature with long ears and big feet.',
        "race":        'rabbit',
        "act_flags": {"stay_area": True},
        "alignment": 0,
        "level":     1,
        "hitroll":   0,
        "hp_dice":   (2, 6, 10),
        "mana_dice": (0, 9, 100),
        "damage":    (1, 4, 0),  "dam_type": 'none',
        "armor":     (9, 9, 9, 10),
        "off_flags": {"disarm": True, "trip": True, "assist_race": True},
        "start_pos":   'stand',
        "default_pos": 'stand',
        "material": '0',
        "sex":    'none',
        "wealth": 0,
        "size":   'medium',
    },
    M_OLDSTYLE_DRAGON_PET: {
        "keywords":    'oldstyle dragon pet',
        "short_descr": 'the pet dragon',
        "long_descr":  "Ravan's pet dragon is bouncing around here flapping her cute wings.",
        "description": "Ravan's pet dragon is about 3 ft. tall with small pointy teeth.\nThe small wings are eagerly trying to lift her from the ground,\nbut so far they haven't succeeded.",
        "race":        'dragon',
        "act_flags": {"sentinel": True, "wimpy": True, "mage": True},
        "affected_by": {"detect_invis": True, "sanctuary": True},
        "alignment": 1000,
        "level":     10,
        "hitroll":   0,
        "hp_dice":   (2, 6, 110),
        "mana_dice": (10, 9, 100),
        "damage":    (1, 8, 1),  "dam_type": 'none',
        "armor":     (2, 2, 2, 6),
        "off_flags": {"dodge": True, "assist_race": True},
        "start_pos":   'stand',
        "default_pos": 'stand',
        "material": '0',
        "sex":    'female',
        "wealth": 0,
        "size":   'medium',
    },
}

# -- Specials -------------------------------------------------------------------
# ("M", mob_vnum, spec_fun_name) -- assign special function to mob template
SPECIALS = (
    ("M", M_OLDSTYLE_DRAGON_PET, 'spec_cast_mage'),
)

# -- Rooms ----------------------------------------------------------------------
ROOMS = {
    R_PATH_IN_THE_PLAINS: {
        "name": 'Path in the plains',
        "desc": 'You are walking on a path situated in the rough plains.\nYou feel the strong winds blow through your hair as you study\nthe beautiful landscaping here. The path continues east, north\nand west leads to plains and you see the path towards the north\ngate of midgaard to the south.',
        "exits": {
            "n": {"to": R_GALLOW_HILL, "desc": 'You see the grassy plains.'},
            "e": {"to": R_PATH_IN_THE_PLAINS_301, "desc": 'You notice nothing special, except that the path in the plains continues.'},
            "s": {"to": 3904, "desc": 'Towards the south you notice the north gate of Midgaard.'},
            "w": {"to": R_GRASSY_PLAINS, "desc": 'You see the grassy plains.'},
        },
        "sector": 'field',
    },
    R_PATH_IN_THE_PLAINS_301: {
        "name": 'Path in the plains',
        "desc": 'You are walking on a path situated in the rough plains.\nYou feel the strong winds blow through your hair as you study\nthe beautiful landscaping here. The path continues east and west.',
        "exits": {
            "e": {"to": R_PATH_IN_THE_PLAINS_302, "desc": 'You notice nothing special, except that the path in the plains continues.'},
            "w": {"to": R_PATH_IN_THE_PLAINS, "desc": 'You notice nothing special, except that the path in the plains continues.'},
        },
        "sector": 'field',
    },
    R_PATH_IN_THE_PLAINS_302: {
        "name": 'Path in the plains',
        "desc": 'You are walking on a path situated in the rough plains.\nYou feel the strong winds blow through your hair as you study\nthe beautiful landscaping here. The path continues north and west.',
        "exits": {
            "n": {"to": R_PATH_IN_THE_PLAINS_303, "desc": 'You notice nothing special, except that the path in the plains continues.'},
            "w": {"to": R_PATH_IN_THE_PLAINS_301, "desc": 'You notice nothing special, except that the path in the plains continues.'},
        },
        "sector": 'field',
    },
    R_PATH_IN_THE_PLAINS_303: {
        "name": 'Path in the plains',
        "desc": 'You are walking on a path situated in the rough plains.\nYou feel the strong winds blow through your hair as you study\nthe beautiful landscaping here. The path leads north and south.\nTo the east and the west you have the grassy plains.',
        "exits": {
            "n": {"to": R_PATH_IN_THE_PLAINS_304, "desc": 'You notice nothing special, except that the path in the plains continues.'},
            "e": {"to": R_GRASSY_PLAINS_317, "desc": 'To the east you notice the grassy plains.'},
            "s": {"to": R_PATH_IN_THE_PLAINS_302, "desc": 'You notice nothing special, except that the path in the plains continues.'},
            "w": {"to": R_GALLOW_HILL, "desc": 'To the west you can see more of the beautiful grassy plains.'},
        },
        "sector": 'field',
    },
    R_PATH_IN_THE_PLAINS_304: {
        "name": 'Path in the plains',
        "desc": 'You are walking on a path situated in the rough plains.\nYou feel the strong winds blow through your hair as you study\nthe beautiful landscaping here. The Path leads north and south.',
        "exits": {
            "n": {"to": R_PATH_IN_THE_PLAINS_305, "desc": 'The path continues north as small foothills begins to appear.'},
            "s": {"to": R_PATH_IN_THE_PLAINS_303, "desc": 'The path leads south towards the town.'},
        },
        "sector": 'field',
    },
    R_PATH_IN_THE_PLAINS_305: {
        "name": 'Path in the plains',
        "desc": 'You are walking on a path situated in the rough plains.\nYou feel the strong winds blow through your hair as you watch the\nbeautiful landscaping here. To the east and west you see the grassy plains.\nThe path extends into small foothills to the north and also continues south.',
        "exits": {
            "n": {"to": R_PATH_IN_THE_FOOTHILLS, "desc": 'The path continues into the small foothills.'},
            "e": {"to": R_GRASSY_PLAINS_321, "desc": 'You see the grassy plains here.'},
            "s": {"to": R_PATH_IN_THE_PLAINS_304, "desc": 'The path continues towards Midgaard.'},
            "w": {"to": R_GRASSY_PLAINS_320, "desc": 'You see the grassy plains here.'},
        },
        "sector": 'field',
    },
    R_PATH_IN_THE_FOOTHILLS: {
        "name": 'Path in the foothills',
        "desc": 'You are on the path leading through the small foothills.\nThe wind blow through your hair as you study the beautiful\nlandscaping here. From the north you sense a certain freshness.\nThe path continues east and south. You smell freshness from north.',
        "exits": {
            "n": {"to": R_POOL_IN_THE_FOOTHILLS, "desc": 'You see grassy plains and perhaps some crystal clear water.'},
            "e": {"to": R_PATH_IN_THE_FOOTHILLS_307, "desc": 'The path continues towards east here.'},
            "s": {"to": R_PATH_IN_THE_PLAINS_305, "desc": 'The path in the plains wind through the small foothills.'},
        },
        "sector": 'field',
    },
    R_PATH_IN_THE_FOOTHILLS_307: {
        "name": 'Path in the foothills',
        "desc": 'You are walking on a path situated in the small foothills.\nThe winds are more than average here but it feels nice. You can follow\nthe path east or west.',
        "exits": {
            "e": {"to": R_PATH_IN_THE_FOOTHILLS_308, "desc": 'The path continues in the foothills'},
            "w": {"to": R_PATH_IN_THE_FOOTHILLS, "desc": 'To the west the path takes a bend southwards.'},
        },
        "sector": 'field',
    },
    R_PATH_IN_THE_FOOTHILLS_308: {
        "name": 'Path in the foothills',
        "desc": 'You are walking on a narrow path in the foothills.\nYou feel the strong winds blow through your hair as you study\nthe beautiful landscaping here. The path goes north and west.',
        "exits": {
            "n": {"to": R_PATH_IN_THE_FOOTHILLS_309, "desc": 'The narrow path through the foothills turns left here.'},
            "w": {"to": R_PATH_IN_THE_FOOTHILLS_307, "desc": 'To the west you can see the path continues.'},
        },
        "sector": 'field',
    },
    R_PATH_IN_THE_FOOTHILLS_309: {
        "name": 'Path in the foothills',
        "desc": 'You are walking on a path situated in foothills.\nTo the west you sense a certain freshness and the path continues\nsouth and east.',
        "exits": {
            "e": {"to": R_PATH_IN_THE_FOOTHILLS_310, "desc": 'You see the path continues in the foothills.'},
            "s": {"to": R_PATH_IN_THE_FOOTHILLS_308, "desc": 'You see the path continues in the foothills.'},
            "w": {"to": R_POOL_IN_THE_FOOTHILLS, "desc": 'You see grassy plains and perhaps some crystal clear water.'},
        },
        "sector": 'field',
    },
    R_PATH_IN_THE_FOOTHILLS_310: {
        "name": 'Path in the foothills',
        "desc": 'You are walking on a long path in the east-west direction.\nThe surroundings are green, vegetated foothills.\nYou are able to force your way through some dense plants to the north.',
        "exits": {
            "n": {"to": R_FOOTHILLS, "desc": "You can't really see much through the vegetation on the foothills."},
            "e": {"to": R_PATH_IN_THE_FOOTHILLS_311, "desc": 'To the east you notice that the path continues towards a T-intersection.'},
            "w": {"to": R_PATH_IN_THE_FOOTHILLS_309, "desc": 'You just see the path through the foothills.'},
        },
        "sector": 'field',
    },
    R_PATH_IN_THE_FOOTHILLS_311: {
        "name": 'Path in the foothills',
        "desc": 'You are walking on the long, narrow path through the foothills.\nTo your east you see a T-intersection and to the west the path\ncontinues far.',
        "exits": {
            "e": {"to": R_PATH_INTERSECTION, "desc": 'You can go to the T-intersection this way.'},
            "w": {"to": R_PATH_IN_THE_FOOTHILLS_310, "desc": 'You can see the long path through the plains.'},
        },
        "sector": 'field',
    },
    R_PATH_INTERSECTION: {
        "name": 'The path intersection',
        "desc": 'You are standing on an intersection between 3 paths.\nTo the west you can follow a long, narrow path through the foothills.\nTo the north a wide path leads to the Village of Ofcol and an\nancient path leads towards the south.',
        "exits": {
            "n": {"to": R_ROAD_TO_OFCOL, "desc": 'The wide road to Ofcol runs here.'},
            "s": {"to": R_ANCIENT_PATH, "desc": 'Here is a partially hidden, ancient looking path.'},
            "w": {"to": R_PATH_IN_THE_FOOTHILLS_311, "desc": 'You can see the long narrow path running through the foothills.'},
        },
        "sector": 'field',
    },
    R_ROAD_TO_OFCOL: {
        "name": 'Road to Ofcol',
        "desc": 'You are walking on a wide road with trail marks on it.  To the north\nyou see the village of Ofcol and to the south there is the T intersection.\nYou can enter the foothills west.  The foothills to your east are too\nsteep to climb.',
        "exits": {
            "n": {"to": R_OUTSIDE_OFCOL, "desc": 'The road continues towards Ofcol.'},
            "s": {"to": R_PATH_INTERSECTION, "desc": 'You can see the T-intersection in the souther direction.'},
            "w": {"to": R_FOOTHILLS, "desc": 'You think you can climb these foothills.'},
        },
        "sector": 'field',
    },
    R_OUTSIDE_OFCOL: {
        "name": 'Outside Ofcol',
        "desc": 'You are standing outside the village of Ofcol.\nThe village looks very small, but still a nice and safe place to stay.\nYou may enter the city to the north or journey towards the\nT-intersection in the southern direction.',
        "exits": {
            "n": {"to": 5550, "desc": 'You notice a sign saying : Stranger we welcome you to the\n                           peaceful city of Ofcol.'},
            "s": {"to": R_ROAD_TO_OFCOL, "desc": 'Here you see the road go towards the intersection.'},
        },
        "sector": 'field',
    },
    R_GALLOW_HILL: {
        "name": 'Gallow hill',
        "desc": 'You walk in the grassy plains. On this little hill you can see\ntwo gallows, with rotting human tissue hanging from the ropes.\nThere is a sign here.',
        "exits": {
            "n": {"to": R_GRASSY_PLAINS_320, "desc": 'The plains extend far to the north.'},
            "e": {"to": R_PATH_IN_THE_PLAINS_303, "desc": 'To the east you can see a small path in the plains.'},
            "s": {"to": R_PATH_IN_THE_PLAINS, "desc": 'To the south you can see a small path in the plains.'},
            "w": {"to": R_GRASSY_PLAINS_318, "desc": 'The plains extend far to the west.'},
        },
        "sector": 'hills',
        "extra_descs": [('sign', "The sign says:\n\n  Loyal citizens of Midgaard.  These are the earthly remains of the\n  two heretics 'Dim' and 'Gamma' of this world. Having forged them-\n  selves to immortality, they called upon themselves the anger of the\n  implementators.  Let this be a lesson too all .....\n\n                                    -- the Powers that Be.")],
    },
    R_GRASSY_PLAINS: {
        "name": 'Grassy plains',
        "desc": 'You walk in the grassy plains among the herbs which grow here. The wind is\nstrong and rough. Far to the north you can see the foothills and further on\nmountain peaks are visible.',
        "exits": {
            "n": {"to": R_GRASSY_PLAINS_318, "desc": 'The plains extend far to the north.'},
            "e": {"to": R_PATH_IN_THE_PLAINS, "desc": 'When you look to the east you notice at small path.'},
        },
        "sector": 'hills',
    },
    R_GRASSY_PLAINS_317: {
        "name": 'Grassy plains',
        "desc": 'You walk in the grassy plains among the herbs which grow here. The wind is\nstrong and rough. Far to the north you can see the foothills and further on\nmountain peaks are visible. City of Midgaard is to the south but so are some\nVERY steep slopes.',
        "exits": {
            "e": {"to": R_GRASSY_PLAINS_338, "desc": 'The plains extend far to the east.'},
            "s": {"to": R_STEEP_SLOPE, "desc": 'Some VERY steep slopes prevent you from going this way, it might kill you.'},
            "w": {"to": R_PATH_IN_THE_PLAINS_303, "desc": 'A small path is running through the plains.'},
        },
        "sector": 'hills',
    },
    R_GRASSY_PLAINS_318: {
        "name": 'Grassy plains',
        "desc": 'You walk in the beautiful grassy plains. The wind is strong and rough.\nFar to the north you can see the foothills and further on mountain peaks\nare visible.',
        "exits": {
            "n": {"to": R_GRASSY_PLAINS_319, "desc": 'The plains extend far to the north.'},
            "e": {"to": R_GALLOW_HILL, "desc": 'The plains extend far to the east.'},
            "s": {"to": R_GRASSY_PLAINS, "desc": 'The plains extend far to the south.'},
        },
        "sector": 'hills',
    },
    R_GRASSY_PLAINS_319: {
        "name": 'Grassy plains',
        "desc": 'You walk in the grassy plains among the herbs which grow here. The wind is\nstrong and rough. To the north you can see the foothills and just behind\nmountain peaks are visible.',
        "exits": {
            "n": {"to": R_IN_FRONT_OF_HUT_IN_FOOTHILLS, "desc": 'To the north, the plains extend into small foothills, behind a small hill\nyou notice something ...'},
            "e": {"to": R_GRASSY_PLAINS_320, "desc": 'The plains extend far to the east.'},
            "s": {"to": R_GRASSY_PLAINS_318, "desc": 'The plains extend far to the south.'},
        },
        "sector": 'hills',
    },
    R_GRASSY_PLAINS_320: {
        "name": 'Grassy plains',
        "desc": 'You walk in some grassy plains. The wind is strong and rough. To the\nnorth you can see the foothills and further on mountain peaks are visible.',
        "exits": {
            "n": {"to": R_GRASSY_FOOTHILLS, "desc": 'The plains extend into small foothills to the north.'},
            "e": {"to": R_PATH_IN_THE_PLAINS_305, "desc": 'East of here you see a winding path in the plains.'},
            "s": {"to": R_GALLOW_HILL, "desc": 'The plains extend far to the south.'},
            "w": {"to": R_GRASSY_PLAINS_319, "desc": 'The plains extend far to the west.'},
        },
        "sector": 'hills',
    },
    R_GRASSY_PLAINS_321: {
        "name": 'Grassy plains',
        "desc": 'You walk in the grassy plains. The wind is fairly strong.',
        "exits": {
            "s": {"to": R_GRASSY_PLAINS_338, "desc": 'The plains extend far to the south.'},
            "w": {"to": R_PATH_IN_THE_PLAINS_305, "desc": 'A small path is running through the plains.'},
        },
        "sector": 'hills',
    },
    R_GRASSY_FOOTHILLS: {
        "name": 'Grassy foothills',
        "desc": 'You walk in the grassy foothills north of the plains. The wind is rough.\nTo the north you can see foothills and just behind them mountain peaks\nare visible.',
        "exits": {
            "n": {"to": R_STEEP_FOOTHILLS_324, "desc": 'The small foothills extend into foothills far to the north.'},
            "s": {"to": R_GRASSY_PLAINS_320, "desc": 'The small foothills extend into plains far to the south.'},
            "w": {"to": R_IN_FRONT_OF_HUT_IN_FOOTHILLS, "desc": 'The small foothills extend far to the west.'},
        },
        "sector": 'hills',
    },
    R_STEEP_FOOTHILLS: {
        "name": 'The steep foothills',
        "desc": 'You walk in the steep foothills. It is rather hard to move here.\nTo the north you can see a grassy valley with wildflowers.',
        "exits": {
            "n": {"to": 7800, "desc": 'You see a path toward the valley.'},
            "e": {"to": R_STEEP_FOOTHILLS_324, "desc": 'The foothills extend far to the east.'},
            "s": {"to": R_IN_FRONT_OF_HUT_IN_FOOTHILLS, "desc": 'On the horizon you can see the City of Midgaard.'},
        },
        "sector": 'hills',
    },
    R_STEEP_FOOTHILLS_324: {
        "name": 'The steep foothills',
        "desc": 'You are walking in the steep foothills. It is rather hard to move here.\nTo the north you can see the mountains towering over you.  Pine trees\ngrow here.',
        "exits": {
            "n": {"to": 901, "desc": 'The path continues up the mountain.'},
            "e": {"to": R_STEEP_FOOTHILLS_325, "desc": 'The foothills extend far to the east.'},
            "s": {"to": R_GRASSY_FOOTHILLS, "desc": 'The foothills extend downwards to the south. In the horizon you can\nsee the City Of Midgaard.'},
            "w": {"to": R_STEEP_FOOTHILLS, "desc": 'The foothills extend far to the west.'},
        },
        "sector": 'hills',
        "extra_descs": [('pine tree trees pines', 'The all too quiet trees suggest that something roams these woods.'), ('mountains', 'The mountains seems dark and all most alive, as they contrast against\nthe sky.')],
    },
    R_STEEP_FOOTHILLS_325: {
        "name": 'The steep foothills',
        "desc": 'You are walking in the steep foothills. It is rather hard to move here.\nFurther to the north you can see the mountains towering over you.\nSeveral pinetrees grow here.',
        "exits": {
            "e": {"to": R_POOL_IN_THE_FOOTHILLS, "desc": 'The foothills extend into smaller hills far to the east.'},
            "w": {"to": R_STEEP_FOOTHILLS_324, "desc": 'The foothills extend far to the west.'},
        },
        "sector": 'hills',
    },
    R_POOL_IN_THE_FOOTHILLS: {
        "name": 'The pool in the foothills',
        "desc": 'You are standing by a pool in the small foothills. It is clear and cold.\nA steep slope rises up into the foothills to the north. Behind them ...\nthe mountains.',
        "exits": {
            "e": {"to": R_PATH_IN_THE_FOOTHILLS_309, "desc": 'To the east you notice a small path in the foothills.'},
            "s": {"to": R_PATH_IN_THE_FOOTHILLS, "desc": 'To the south a path winds its way south into the plains.'},
            "w": {"to": R_STEEP_FOOTHILLS_325, "desc": 'The foothills extend far to the west.'},
        },
        "sector": 'hills',
        "extra_descs": [('pool', "The pool is crystal clear, but as you look into it you notice that\nyou can't see the bottom of it ... it must be pretty deep.")],
    },
    R_FOOTHILLS: {
        "name": 'The foothills',
        "desc": 'You are walking in some foothills. It is rather hard to move here.\nFurther to the north you can see the mountains towering over you.\nSeveral pinetrees grow here.',
        "exits": {
            "e": {"to": R_ROAD_TO_OFCOL, "desc": 'To the east you notice a small path in the foothills.'},
            "s": {"to": R_PATH_IN_THE_FOOTHILLS_310, "desc": 'To the south a steep slope runs down to a small path in the foothills.'},
        },
        "sector": 'hills',
    },
    R_IN_FRONT_OF_HUT_IN_FOOTHILLS: {
        "name": 'In front of hut in foothills',
        "desc": 'You are standing in the foothills. To the west, well hidden among the small\nfoothills and pines, you see a small hut. To the north you can see\nthe foothills, and some pineforrest. Further on mountain peaks are visible.',
        "exits": {
            "n": {"to": R_STEEP_FOOTHILLS, "desc": 'The steep foothills seems hard to climb'},
            "e": {"to": R_GRASSY_FOOTHILLS, "desc": 'The foothills extend far to the east.'},
            "s": {"to": R_GRASSY_PLAINS_319, "desc": 'To the south the foothills extend into plains far to the south.'},
            "w": {"to": R_HERMIT_S_HUT, "desc": 'You see a small crumbled hut here, must be a hermit living here.', "keyword": 'door', "isdoor": True},
        },
        "sector": 'hills',
    },
    R_HERMIT_S_HUT: {
        "name": "Hermit's hut",
        "desc": "You are inside the hermit's hut. It is rather old, but serves it purpose.\nIt keeps its habitant from the rough winds and dangerous beasts of the\nplains and foothills. There is a small fireplace here.",
        "exits": {
            "e": {"to": R_IN_FRONT_OF_HUT_IN_FOOTHILLS, "desc": 'Through the door you can see the foothills.', "keyword": 'door', "isdoor": True},
        },
        "flags": {"indoors": True},
        "sector": 'inside',
        "extra_descs": [('fireplace', 'The hermit cooks here.')],
    },
    R_ANCIENT_PATH: {
        "name": 'The ancient path',
        "desc": 'You are moving on an ancient path. The path is slightly covered with\nleaves and twitches.\nTo the north you can see the T-crossing and the path continues south.',
        "exits": {
            "n": {"to": R_PATH_INTERSECTION, "desc": 'As you look to the north you see a T-intersection.'},
            "s": {"to": R_ANCIENT_PATH_333, "desc": 'The ancient path continues through the plains.'},
        },
        "sector": 'forest',
    },
    R_ANCIENT_PATH_333: {
        "name": 'The ancient path',
        "desc": 'You are standing on the ancient path which runs north and south.\nThe path is hardly visible here.',
        "exits": {
            "n": {"to": R_ANCIENT_PATH, "desc": 'You see the ancient path.'},
            "s": {"to": R_ANCIENT_PATH_334, "desc": 'You trace the path carefully and see no immediate dangers.'},
        },
        "sector": 'forest',
    },
    R_ANCIENT_PATH_334: {
        "name": 'The ancient path',
        "desc": 'You are standing on the ancient path which runs north and south.\nThe path is hardly visible here.',
        "exits": {
            "n": {"to": R_ANCIENT_PATH_333, "desc": 'You see the ancient path.'},
            "s": {"to": R_ANCIENT_PATH_335, "desc": 'You trace the path carefully and see no immediate dangers.'},
        },
        "sector": 'forest',
    },
    R_ANCIENT_PATH_335: {
        "name": 'The ancient path',
        "desc": 'The path runs north and east from here.  You notice some markers placed\nalong the side of the path.',
        "exits": {
            "n": {"to": R_ANCIENT_PATH_334, "desc": 'You see the ancient path winding its way north from here. Looks safe.'},
            "e": {"to": R_WOODEN_BRIDGE, "desc": 'Further ahead you see a bridge over a small creak.'},
        },
        "sector": 'forest',
        "extra_descs": [('markers', 'The markers seems like normal stones, but the way they are\narranged makes you think there is something special about them.')],
    },
    R_WOODEN_BRIDGE: {
        "name": 'The wooden bridge',
        "desc": "You have stepped upon a wooden bridge. It looks old but safe to cross.\nIt is made of a wood you haven't seen before.",
        "exits": {
            "e": {"to": R_ANCIENT_PATH_337, "desc": 'The path continues, further ahead you notice some rock formations.'},
            "w": {"to": R_ANCIENT_PATH_335, "desc": 'The ancient path leads west and turns north further ahead.'},
        },
        "sector": 'field',
        "extra_descs": [('rock formation formations', "The rock formations are made of 7 huge, monolith like stones, placed\nin a symbolic circle.\nYou notice it's possible to enter the ring.")],
    },
    R_ANCIENT_PATH_337: {
        "name": 'The ancient path',
        "desc": 'You find yourself located between the bridge and the rock formations.\nAs you approach the formations you begin to realize the true size of\nthem, about 15 feet tall and almost perfect rectangular shape.\nYou feel impressed with the awesome sight.',
        "exits": {
            "e": {"to": R_STONES_OF_G_HARNE, "desc": "To the east you enter the ring of stones. You wonder if it's safe."},
            "w": {"to": R_WOODEN_BRIDGE, "desc": 'To the west the ancient path leads across the wooden bridge.'},
        },
        "sector": 'forest',
        "extra_descs": [('rock formation formations', "The rock formations are made of seven huge monolith placed in a circle.\nYou notice it's possible to enter the ring.")],
    },
    R_GRASSY_PLAINS_338: {
        "name": 'Grassy plains',
        "desc": 'You walk in the grassy plains among the herbs which grow here. The wind is\nstrong and rough. Far to the north you can see the foothills and further on\nmountain peaks are visible.',
        "exits": {
            "n": {"to": R_GRASSY_PLAINS_321, "desc": 'The plains extend far to the north.'},
            "w": {"to": R_GRASSY_PLAINS_317, "desc": 'The plains extend far to the east.'},
        },
        "sector": 'hills',
    },
    R_STONES_OF_G_HARNE: {
        "name": "The Stones of G'harne",
        "desc": "You are in the center of 7, 15 ft tall monolith like black stones.\nIn the center of the ring formed by the monolith you can't help\nnoticing a big sacrifice altar. The ground is covered with dirt, but the\naltar shows no sign of such. West of here is the ancient path.",
        "exits": {
            "w": {"to": R_ANCIENT_PATH_337, "desc": 'You see the ancient path and the wooden bridge here.'},
            "d": {"to": R_DARK_SMELLY_TUNNELS, "desc": 'You see a tunnel down there.'},
        },
        "sector": 'field',
        "extra_descs": [('death rituals worms engraving picture', 'The pictures are depicting evil rituals.\nYou see druids pouring blood over herbs on an altar like this one.\nThere are people calling giant worms into existence with dark spells.'), ('altar sacrifice', "You move closer to examine the sacrifice altar of G'harne.\nThe altar is about 3 feet high, 10 feet long and 4 feet wide.\nIt has engraved pictures of death rituals and horrifying worms."), ("stones g'harne monolith", "The stones of G'harne tower fifteen feet over you.\nThe giant stones are made of a material you haven't seen before.\nIt resembles black marble, but somehow feels different.")],
    },
    R_DARK_SMELLY_TUNNELS: {
        "name": 'Dark smelly tunnels',
        "desc": "You are standing in a gloomy tunnel leading south and west, right under\nthe altar of G'harne.  The walls are covered with a smelly slime and small\nrotting pieces of a meat like substance, fills the air with an unbearable\nstench.  You might be able to force your way up into fresh air from here.",
        "exits": {
            "s": R_DEAD_END_OF_TUNNEL,
            "w": R_DARK_SMELLY_TUNNELS_342,
            "u": {"to": R_STONES_OF_G_HARNE, "desc": 'You welcome the sight of fresh air.'},
        },
        "flags": {"dark": True, "indoors": True, "_unknown_bits": [8]},
        "sector": 'inside',
        "extra_descs": [('meat rotting slime substance', 'You try to examine the substance closer, but must refrain from this\nas all you really want to do is puke.\nYou puke.')],
    },
    R_DEAD_END_OF_TUNNEL: {
        "name": 'Dead end of tunnel',
        "desc": "The tunnel comes to an abrupt end here. It simply looks like it\nhasn't been excavated further.  North of here the tunnel makes a turn east.",
        "exits": {
            "n": R_DARK_SMELLY_TUNNELS,
        },
        "flags": {"dark": True, "indoors": True, "_unknown_bits": [8]},
        "sector": 'inside',
    },
    R_DARK_SMELLY_TUNNELS_342: {
        "name": 'Dark smelly tunnels',
        "desc": 'You are standing in a gloomy tunnel leading east and west.\nThe walls are covered with a smelly slime and small rotting pieces of a\nmeat like substance, fills the air with an unbearable stench.',
        "exits": {
            "e": {"to": R_DARK_SMELLY_TUNNELS, "desc": 'The tunnel continues in this direction.'},
            "w": {"to": R_DARK_SMELLY_TUNNELS_343, "desc": 'The tunnel continues in this direction.'},
        },
        "flags": {"dark": True, "indoors": True, "_unknown_bits": [8]},
        "sector": 'inside',
        "extra_descs": [('meat rotting slime substance', 'You try to examine the substance closer, but must refrain from this\nas all you really want to do is puke.\nYou puke.')],
    },
    R_DARK_SMELLY_TUNNELS_343: {
        "name": 'Dark smelly tunnels',
        "desc": 'You are standing in a small smelly tunnel under the plains.\nThe smell is growing stronger to the west, so is the density of the\nslime and other undeterminable substances ...',
        "exits": {
            "e": {"to": R_DARK_SMELLY_TUNNELS_342, "desc": 'The unbearable stench is less intensive in this direction.'},
            "w": {"to": R_HALL_OF_G_HARNE, "desc": 'The tunnel seems to extend into some kind of cave.'},
        },
        "flags": {"_unknown_bits": [8]},
        "sector": 'inside',
        "extra_descs": [('slime substance', 'BWADR! ...')],
    },
    R_HALL_OF_G_HARNE: {
        "name": "The Hall of G'harne",
        "desc": "You stand in the hall of G'harne. The walls are dressed with strange\ncarving, symbolizing human sacrifice and people worshipping giant worms.\nDisgusting slime and gore are also very dominant in your view of this room.",
        "exits": {
            "e": {"to": R_DARK_SMELLY_TUNNELS_343, "desc": 'It looks like a good idea just to run in this direction.'},
        },
        "flags": {"dark": True, "indoors": True, "_unknown_bits": [8]},
        "sector": 'inside',
        "extra_descs": [('slime gore', 'You puke.')],
    },
    R_STEEP_SLOPE: {
        "name": 'Steep slope',
        "desc": "You try to climb down the slope.\n>\nYou slip!\nYou fall and tumble.\nYou hit your head HARD.\nYou die.\n\nYou've fallen, and you can't get up!",
        "exits": {
        },
        "flags": {"no_mob": True},
        "sector": 'field',
    },
}

# -- Item templates -------------------------------------------------------------
OBJECTS = {
    I_HERBS_HERB_TIMIAN: {
        "keywords":    'herbs herb timian',
        "short_descr": 'a small dusk of timian herbs',
        "description": 'Some herbs are lying here, small green leaves and tiny pink flowers.',
        "material":    'oldstyle',
        "type": 'food',
        "wear_flags": {"take": True},
        "food_hours": 1, "food_hunger": 1,
        "level": 0, "weight": 10, "value": 10,
        "extra_descs": [('herbs herb timian', 'This herb smells rather spicy; maybe you should try it?')],
    },
    I_HERBS_HERB_GYVEL: {
        "keywords":    'herbs herb gyvel',
        "short_descr": 'a small dusk of black gyvel',
        "description": 'Some black gyvel is lying here, dark green with black leaves and tiny\n\nblood red flowers.',
        "material":    'oldstyle',
        "type": 'food',
        "wear_flags": {"take": True},
        "food_hours": 1, "food_hunger": 1,
        "level": 0, "weight": 10, "value": 10,
        "extra_descs": [('herbs herb gyvel', 'This herb smells rather special, but is it poisonous?')],
    },
    I_PLANT_IVY: {
        "keywords":    'plant ivy',
        "short_descr": 'a small dusk of poison ivy',
        "description": 'Some poison ivy is growing here.',
        "material":    'oldstyle',
        "type": 'food',
        "wear_flags": {"take": True},
        "food_hours": 1, "food_hunger": 1,
        "level": 0, "weight": 10, "value": 0,
        "extra_descs": [('plant ivy', 'This plant has dark green juicy leaves.\nYou notice some small white thorns on it.')],
    },
    I_BLOOD_JAR: {
        "keywords":    'blood jar',
        "short_descr": 'a dark red jar',
        "description": 'A small jar in a dark, red colour.',
        "material":    'oldstyle',
        "type": 'drink',
        "wear_flags": {"take": True},
        "liquid_total": 2, "liquid_left": 2,
        "liquid_type": 'blood',
        "level": 0, "weight": 20, "value": 20,
        "extra_descs": [('blood jar', 'The jar is made of dry clay, covered with markings suggesting its\noccult origin.')],
    },
    I_WILD_FLOWERS: {
        "keywords":    'wild flowers',
        "short_descr": 'wild flowers',
        "description": 'A bunch of pretty wild flowers is here.',
        "material":    'oldstyle',
        "type": 'trash',
        "wear_flags": {"take": True, "head": True},
        "extra_flags": {"anti_evil": True},
        "level": 0, "weight": 10, "value": 0,
        "extra_descs": [('wild flowers', 'These wild flowers are really pretty.\nJust like the flowers you would wear in your hair.')],
    },
    I_AMULET: {
        "keywords":    'amulet',
        "short_descr": 'a strange amulet',
        "description": 'A strange looking amulet is lying here, half covered with dust.',
        "material":    'oldstyle',
        "type": 'jewelry',
        "wear_flags": {"take": True, "neck": True},
        "extra_flags": {"magic": True, "nodrop": True},
        "stat_bonuses": {'saves': 5},
        "level": 0, "weight": 10, "value": 1,
        "extra_descs": [('amulet', 'Judging from the signs inscripted in the amulet, you gather it must\nhave belonged to a druid.  It is weird looking with symbols from nature\ndominating it.')],
    },
    I_STAFF_STICK: {
        "keywords":    'staff stick',
        "short_descr": 'a druish staff',
        "description": 'A staff with druidic marks have been left here.',
        "material":    'oldstyle',
        "type": 'trash',
        "wear_flags": {"take": True, "hold": True},
        "level": 0, "weight": 40, "value": 10,
        "extra_descs": [('staff stick', 'Then staff is about 5 ft long, engraved with mythical signs and figures.\nOtherwise the staff seems of no real interest.')],
    },
    I_RABBIT_ROAST_WABBIT: {
        "keywords":    'rabbit roast wabbit',
        "short_descr": 'a rabbit roast',
        "description": 'You see a deliciously looking rabbit roast.',
        "material":    'oldstyle',
        "type": 'food',
        "wear_flags": {"take": True},
        "food_hours": 24, "food_hunger": 24,
        "level": 0, "weight": 50, "value": 0,
        "extra_descs": [('roast rabbit wabbit', "Well the rabbit looks rather dead.\nYou guess that this once was a ferocious rabbit who's life now has\nchanged to that of a tasty wabbit woast.")],
    },
    I_TEMPLATE_SCROLL: {
        "keywords":    'template scroll',
        "short_descr": 'a strange template',
        "description": 'A strange template made of an exotic green metal is placed here',
        "material":    'oldstyle',
        "type": 'scroll',
        "wear_flags": {"take": True, "hold": True},
        "extra_flags": {"magic": True},
        "spell_level": 15,
        "spells": ['sleep', 'blindness', 'fireball'],
        "level": 13, "weight": 10, "value": 1870,
        "extra_descs": [('template scroll metal', "The template is made of an exotic green metal and looks\ncenturies old.\nInscripted upon is the words 'Ep ep fi'hur G'harne\n                             G'harne fhtagn Shudde-M'ell hyas Negg'h'\nAnd beneath the inscription you see horrifying death scenes depicted.")],
    },
    I_POTION_CLEAR: {
        "keywords":    'potion clear',
        "short_descr": 'a clear potion',
        "description": 'A clear potion wrapped in leather is unnoticed placed here.',
        "material":    'oldstyle',
        "type": 'potion',
        "wear_flags": {"take": True},
        "extra_flags": {"magic": True},
        "spell_level": 20,
        "spells": ['detect evil', 'detect invis', 'detect magic'],
        "level": 0, "weight": 20, "value": 300,
        "extra_descs": [('leather', 'The leather wrapped around the potion is old and decayed, originating\nfrom an, to you, unknown creature.'), ('potion clear', 'As you examine the potion more, you notice the oddities of this\npotion. When you look through it you notice strange things...\nThe clear potion is certainly not of this world.')],
    },
    I_SCROLL_JHYFRDOW: {
        "keywords":    'scroll jhyfrdow',
        "short_descr": "a scroll titled 'jhyfrdow'",
        "description": 'An odd looking scroll is here.',
        "material":    'oldstyle',
        "type": 'scroll',
        "wear_flags": {"take": True},
        "spell_level": 18,
        "spells": ['protection evil'],
        "level": 2, "weight": 10, "value": 640,
        "extra_descs": [('ritual men drawings', 'The drawing pictures people gathered round giant stone formations,\nworshipping a giant worm like creature.\nIt seems they are sacrificing some of their own species.'), ('scroll jhyfrdow', "The scroll is titled 'jhyfrdow' and looks very old.\nAs you examine it closer you notice primitive drawings of\nmen doing some kind of a ritual.")],
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
    ("O", I_HERBS_HERB_TIMIAN, R_FOOTHILLS),
    ("O", I_HERBS_HERB_GYVEL, R_GRASSY_PLAINS_319),
    ("O", I_WILD_FLOWERS, R_GRASSY_PLAINS),
    ("O", I_WILD_FLOWERS, R_STEEP_FOOTHILLS),
    ("O", I_WILD_FLOWERS, R_GRASSY_PLAINS_338),
    ("M", M_OLDSTYLE_WORM_SHUDDE_M_ELL, 1, R_HALL_OF_G_HARNE, 1),
    ("G", I_TEMPLATE_SCROLL),
    ("G", I_POTION_CLEAR),
    ("M", M_OLDSTYLE_RABBIT, 10, R_STEEP_FOOTHILLS_324, 4),
    ("M", M_OLDSTYLE_RABBIT, 10, R_GRASSY_PLAINS_318, 4),
    ("M", M_OLDSTYLE_RABBIT, 10, R_ANCIENT_PATH_334, 4),
    ("M", M_OLDSTYLE_DRUID_ARUNCUS, 1, R_STEEP_FOOTHILLS, 1),
    ("E", I_STAFF_STICK, "hold"),
    ("E", I_AMULET, "neck_1"),
    ("G", I_SCROLL_JHYFRDOW),
    ("G", I_PLANT_IVY),
    ("M", M_OLDSTYLE_HERMIT_SORBUS, 1, R_HERMIT_S_HUT, 1),
    ("G", I_BLOOD_JAR),
    ("O", I_RABBIT_ROAST_WABBIT, R_HERMIT_S_HUT),
)

# -- Shops ---------------------------------------------------------------------
# keeper_vnum: mob that runs the shop
# buy_types: item type names the shop will purchase
# profit_buy/profit_sell: percentage markup/markdown
SHOPS = (
    {"keeper": M_OLDSTYLE_LUXAN_SHOPKEEPER, "buy_types": ['light', 'potion', 'clothing', 'food'], "profit_buy": 120, "profit_sell": 60, "open_hour": 0, "close_hour": 23},
    {"keeper": M_OLDSTYLE_KEEPER_INNKEEPER, "buy_types": [], "profit_buy": 110, "profit_sell": 100, "open_hour": 0, "close_hour": 23},
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
