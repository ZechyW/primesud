# fmt: off
# Area: Mob Factory
# Source: QuickMUD/ROM 2.4
# VNUM ranges: 9400-9499
# Credits: { 5 15} PinkF   Mob Factory


AREA = {
    "name":     'Mob Factory',
    "builders": '{ 5 15} PinkF   Mob Factory',
    "vnums":    (9400, 9499),
    "credits":  '{ 5 15} PinkF   Mob Factory',
    "levels":   (5, 15),
}

# -- Room VNUMs -----------------------------------------------------------------
R_ENTRANCE_TO_THE_MOB_FACTORY      = 9400
R_MOB_FACTORY_STORAGE_AREA         = 9401
R_MOB_FACTORY_STORAGE_AREA_9402    = 9402
R_FOREMAN_S_OFFICE                 = 9403
R_FOREMAN_S_BATHROOM               = 9404
R_MOB_FACTORY_STORAGE_AREA_9405    = 9405
R_MOB_FACTORY_STORAGE_AREA_9406    = 9406
R_ENTRANCE_HALLWAY_TO_MOB_FACTORY  = 9407
R_MOB_FACTORY_CAFETERIA            = 9408
R_MOB_FACTORY_CAFETERIA_9409       = 9409
R_MOB_FACTORY_INSPECTION_ROOM      = 9410
R_MOB_FACTORY_INSPECTION_ROOM_9411 = 9411
R_ENTRANCE_HALLWAY_TO_MOB_FACTORY_9412 = 9412
R_MOB_FACTORY_REJECT_ROOM          = 9413
R_MOB_FACTORY_REJECT_ROOM_9414     = 9414
R_PRIMARY_ASSEMBLY_LINE            = 9415
R_PRIMARY_ASSEMBLY_LINE_9416       = 9416
R_PRIMARY_ASSEMBLY_LINE_9417       = 9417
R_PRIMARY_ASSEMBLY_LINE_9418       = 9418
R_PRIMARY_ASSEMBLY_LINE_9419       = 9419
R_SECONDARY_ASSEMBLY_LINE          = 9420
R_SECONDARY_ASSEMBLY_LINE_9421     = 9421
R_SECONDARY_ASSEMBLY_LINE_9422     = 9422
R_SECONDARY_ASSEMBLY_LINE_9423     = 9423
R_SECONDARY_ASSEMBLY_LINE_9424     = 9424

# -- Mob template VNUMs ---------------------------------------------------------
M_OLDSTYLE_FIDO_MUTANT_DOG         = 9401
M_OLDSTYLE_FOREMAN_FLOYD           = 9402
M_OLDSTYLE_CITYGUARD_GUARD_HEAD    = 9403
M_OLDSTYLE_REVOLVING_DRUNK         = 9404
M_OLDSTYLE_TOXIC_SLIME             = 9405
M_OLDSTYLE_WORKER                  = 9406
M_OLDSTYLE_WORKER_9407             = 9407

# -- Item template VNUMs --------------------------------------------------------

# -- Mob templates --------------------------------------------------------------
# hp_dice / mana_dice / damage: (num_dice, die_size, bonus)
# armor: (pierce, bash, slash, exotic), raw .are units
# hitroll: from mob level line
MOBILES = {
    M_OLDSTYLE_FIDO_MUTANT_DOG: {
        "keywords":    'oldstyle fido mutant dog',
        "short_descr": 'The mutant beastly fido',
        "long_descr":  'The mutant beastly fido is here, his eyes glowing green!',
        "description": 'You see a mutant beastly fido, glaring at you with green eyes!  You wonder if\nthis factory meets ASPCA guidlines....',
        "race":        'fido',
        "act_flags": {"aggressive": True, "stay_area": True, "wimpy": True},
        "affected_by": {"detect_invis": True},
        "alignment": -700,
        "level":     6,
        "hitroll":   0,
        "hp_dice":   (2, 7, 71),
        "mana_dice": (3, 9, 100),
        "damage":    (1, 7, 1),  "dam_type": 'none',
        "armor":     (4, 4, 4, 9),
        "off_flags": {"disarm": True, "trip": True},
        "start_pos":   'stand',
        "default_pos": 'stand',
        "material": '0',
        "sex":    'male',
        "wealth": 0,
        "size":   'medium',
    },
    M_OLDSTYLE_FOREMAN_FLOYD: {
        "keywords":    'oldstyle foreman floyd',
        "short_descr": 'Foreman Floyd',
        "long_descr":  "Foreman Floyd is here, making plans for the factory's future.",
        "description": 'You see Foreman Floyd of the Mob factory -- a sterling example of what comes\nof dedicated Mudding!  Rewarded for his years of dedication as a monster\nslayer, Floyd now creates the beasts for other adventurers to fight.',
        "race":        'human',
        "act_flags": {"sentinel": True, "stay_area": True},
        "affected_by": {"detect_invis": True, "detect_hidden": True, "sanctuary": True},
        "alignment": 2,
        "level":     12,
        "hitroll":   0,
        "hp_dice":   (2, 10, 150),
        "mana_dice": (6, 9, 100),
        "damage":    (1, 10, 3),  "dam_type": 'none',
        "armor":     (0, 0, 0, 8),
        "off_flags": {"disarm": True, "dodge": True, "trip": True, "assist_vnum": True},
        "start_pos":   'sit',
        "default_pos": 'stand',
        "material": '0',
        "sex":    'male',
        "wealth": 50,
        "size":   'medium',
    },
    M_OLDSTYLE_CITYGUARD_GUARD_HEAD: {
        "keywords":    'oldstyle cityguard guard head',
        "short_descr": 'The Cityguard head',
        "long_descr":  'The Cityguard head floats around aimlessly.',
        "description": 'You see a Cityguard head floating around without a care in the world.\nObviously, this one got past quality control!  Careful, those teeth look\nsharp...',
        "race":        'unique',
        "act_flags": {"stay_area": True},
        "affected_by": {"flying": True},
        "alignment": 0,
        "level":     9,
        "hitroll":   0,
        "hp_dice":   (2, 6, 110),
        "mana_dice": (4, 9, 100),
        "damage":    (1, 8, 2),  "dam_type": 'none',
        "armor":     (2, 2, 2, 8),
        "off_flags": {"disarm": True, "dodge": True, "trip": True, "assist_vnum": True},
        "start_pos":   'stand',
        "default_pos": 'stand',
        "form_flags": {"edible": True, "sentient": True, "mammal": True},
        "part_flags": {"head": True, "brains": True, "ear": True, "eye": True},
        "material": '0',
        "sex":    'none',
        "wealth": 0,
        "size":   'medium',
    },
    M_OLDSTYLE_REVOLVING_DRUNK: {
        "keywords":    'oldstyle revolving drunk',
        "short_descr": 'The revolving drunk',
        "long_descr":  'The Revolving drunk is here, spinning in place.',
        "description": 'You see and smell a drunk who looks much like other drunks...but he is spinning\nin place!  Someone should tell him that he is a REVOLTING drunk.',
        "race":        'human',
        "act_flags": {"scavenger": True, "stay_area": True, "wimpy": True},
        "alignment": 1,
        "level":     2,
        "hitroll":   0,
        "hp_dice":   (2, 7, 21),
        "mana_dice": (1, 9, 100),
        "damage":    (1, 5, 0),  "dam_type": 'none',
        "armor":     (8, 8, 8, 10),
        "off_flags": {"disarm": True, "dodge": True, "trip": True, "assist_vnum": True},
        "start_pos":   'stand',
        "default_pos": 'stand',
        "material": '0',
        "sex":    'male',
        "wealth": 2,
        "size":   'medium',
    },
    M_OLDSTYLE_TOXIC_SLIME: {
        "keywords":    'oldstyle toxic slime',
        "short_descr": 'The toxic slime',
        "long_descr":  'A pool of toxic slime lies on  the floor.',
        "description": 'Yick.  Looks like someone had digestion problems!  Either that, or the\nhydraulic fluid is leaking again.',
        "race":        'human',
        "act_flags": {"sentinel": True, "scavenger": True},
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
        "sex":    'none',
        "wealth": 0,
        "size":   'medium',
    },
    M_OLDSTYLE_WORKER: {
        "keywords":    'oldstyle worker',
        "short_descr": 'The factory worker',
        "long_descr":  'A Mob Factory worker is standing here, looking bored.',
        "description": 'The worker wears a bright orange pair of overalls, with the words "Mob\nFactory" written in a bright purple starburst.  Fashion plate, he\'s not.',
        "race":        'human',
        "act_flags": {"stay_area": True, "wimpy": True},
        "alignment": 100,
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
        "wealth": 2,
        "size":   'medium',
    },
    M_OLDSTYLE_WORKER_9407: {
        "keywords":    'oldstyle worker',
        "short_descr": 'The factory worker',
        "long_descr":  'A Mob Factory worker is here, asleep in a chair.',
        "description": "If Floyd walks in, you can bet there'll be trouble.  Guess she shouldn't have\nworked the late shift!",
        "race":        'human',
        "act_flags": {"sentinel": True, "wimpy": True},
        "alignment": 150,
        "level":     3,
        "hitroll":   0,
        "hp_dice":   (2, 6, 35),
        "mana_dice": (1, 9, 100),
        "damage":    (1, 6, 0),  "dam_type": 'none',
        "armor":     (7, 7, 7, 10),
        "off_flags": {"disarm": True, "dodge": True, "trip": True, "assist_vnum": True},
        "start_pos":   'sleep',
        "default_pos": 'sit',
        "material": '0',
        "sex":    'female',
        "wealth": 3,
        "size":   'medium',
    },
}

# -- Specials -------------------------------------------------------------------
# ("M", mob_vnum, spec_fun_name) -- assign special function to mob template
SPECIALS = (
)

# -- Rooms ----------------------------------------------------------------------
ROOMS = {
    R_ENTRANCE_TO_THE_MOB_FACTORY: {
        "name": 'Entrance to the Mob Factory',
        "desc": "You find that you have entered a strange factory. This factory doesn't\nmake cars or computers or something - it makes mobs! The sound of\nmachinery can be heard in the background; the grinding gears drive you\ncrazy! To the north you see the storage area, to the south the\nforeman's office, to the east the entrance hallway, and to the west the\nfamiliar paving of wall road.",
        "exits": {
            "n": R_MOB_FACTORY_STORAGE_AREA,
            "e": R_ENTRANCE_HALLWAY_TO_MOB_FACTORY,
            "s": R_FOREMAN_S_OFFICE,
            "w": 3047,
        },
        "flags": {"indoors": True},
        "sector": 'inside',
    },
    R_MOB_FACTORY_STORAGE_AREA: {
        "name": 'Mob Factory Storage Area',
        "desc": 'This is where the raw materials from which mobs are manufactured are\nstored. You see sacks of sawdust, cans of pink paint, a large box\ncontaining wigs and a bottle mysteriously labelled "solution x". Exits\nare more of storage to the east and north, and entrance to the mob\nfactory to the south.',
        "exits": {
            "n": R_MOB_FACTORY_STORAGE_AREA_9402,
            "e": R_MOB_FACTORY_STORAGE_AREA_9406,
            "s": R_ENTRANCE_TO_THE_MOB_FACTORY,
        },
        "flags": {"indoors": True},
        "sector": 'inside',
    },
    R_MOB_FACTORY_STORAGE_AREA_9402: {
        "name": 'Mob Factory Storage Area',
        "desc": 'This is where the raw materials from which mobs are manufactured are\nstored. You see sacks of sawdust, cans of pink paint, a large box\ncontaining wigs and a bottle mysteriously labelled "solution X". Exits\nare more of storage to the east and south.',
        "exits": {
            "e": R_MOB_FACTORY_STORAGE_AREA_9405,
            "s": R_MOB_FACTORY_STORAGE_AREA,
        },
        "flags": {"indoors": True},
        "sector": 'inside',
    },
    R_FOREMAN_S_OFFICE: {
        "name": "Foreman's Office",
        "desc": "This is the office of the mob factory foreman. The room is sparsely\nfurnished with a metal desk, a couple of chairs, a shelf with helmets\nof various sizes and a Sports Illustrated Swimsuit calendar on the west\nwall. Exits lead north to the mob factory entrance and south to the\nforeman's bathroom.",
        "exits": {
            "n": R_ENTRANCE_TO_THE_MOB_FACTORY,
            "s": R_FOREMAN_S_BATHROOM,
        },
        "flags": {"indoors": True},
        "sector": 'inside',
    },
    R_FOREMAN_S_BATHROOM: {
        "name": "Foreman's Bathroom",
        "desc": "This is the place where the foreman makes frequent visits. The smell\nhere is very strong and reminds you of bovine excrement! There is a\nshower to the back, and a urinal to the left. On the floor you can\nsee stains of a very suspicious nature. The only exit leads north to\nthe foreman's office.",
        "exits": {
            "n": R_FOREMAN_S_OFFICE,
        },
        "flags": {"indoors": True},
        "sector": 'inside',
    },
    R_MOB_FACTORY_STORAGE_AREA_9405: {
        "name": 'Mob Factory Storage Area',
        "desc": 'This is where the raw materials from which mobs are manufactured are\nstored. You see sacks of sawdust, cans of pink paint, a large box\ncontaining wigs and a bottle mysteriously labelled "solution X". Exits\nare more of storage to the west and south, and an inspection room to\nthe east.',
        "exits": {
            "e": R_MOB_FACTORY_INSPECTION_ROOM,
            "s": R_MOB_FACTORY_STORAGE_AREA_9406,
            "w": R_MOB_FACTORY_STORAGE_AREA_9402,
        },
        "flags": {"indoors": True},
        "sector": 'inside',
    },
    R_MOB_FACTORY_STORAGE_AREA_9406: {
        "name": 'Mob Factory Storage Area',
        "desc": 'This is where the raw materials from which mobs are manufactured are\nstored. You see sacks of sawdust, cans of pink paint, a large box\ncontaining wigs and a bottle mysteriously labelled "solution X". Exits\nare more of storage to the west and north, an inspection room to the\neast and the entrance hallway to the south.',
        "exits": {
            "n": R_MOB_FACTORY_STORAGE_AREA_9405,
            "e": R_MOB_FACTORY_INSPECTION_ROOM_9411,
            "s": R_ENTRANCE_HALLWAY_TO_MOB_FACTORY,
            "w": R_MOB_FACTORY_STORAGE_AREA,
        },
        "flags": {"indoors": True},
        "sector": 'inside',
    },
    R_ENTRANCE_HALLWAY_TO_MOB_FACTORY: {
        "name": 'Entrance Hallway to Mob Factory',
        "desc": 'You are standing in the entrance hallway of the mob factory. The sound\nof machinery gets louder now, and you can hear people shouting in the\ndistance. Every once in a while you get creepy feeling that a pair of\neyes is observing you...... Exits are north to the storage area, east\nto the entrance hallway, south to the cafeteria and west to the mob\nfactory entrance.',
        "exits": {
            "n": R_MOB_FACTORY_STORAGE_AREA_9406,
            "e": R_ENTRANCE_HALLWAY_TO_MOB_FACTORY_9412,
            "s": R_MOB_FACTORY_CAFETERIA,
            "w": R_ENTRANCE_TO_THE_MOB_FACTORY,
        },
        "flags": {"indoors": True},
        "sector": 'inside',
    },
    R_MOB_FACTORY_CAFETERIA: {
        "name": 'Mob Factory Cafeteria',
        "desc": "You find that you have entered the cafeteria of the mob factory. There\nare many workers eating at the numerous tables placed around the room.\nThe food doesn't look too appetising, but the factory workers don't\nseem to care. There are many places where food and drink have been\nspilled on the ground. Exits are north to the entrance hallway and\nsouth to the mob factory cafeteria.",
        "exits": {
            "n": R_ENTRANCE_HALLWAY_TO_MOB_FACTORY,
            "s": R_MOB_FACTORY_CAFETERIA_9409,
        },
        "flags": {"indoors": True},
        "sector": 'inside',
    },
    R_MOB_FACTORY_CAFETERIA_9409: {
        "name": 'Mob Factory Cafeteria',
        "desc": "You find that you have entered the cafeteria of the mob factory. There\nare many workers eating at the numerous tables placed around the room.\nThe food doesn't look too appetising, but the factory workers don't\nseem to care. There are many places where food and drink have been\nspilled on the ground. The only exit is north to the mob factory\ncafeteria.",
        "exits": {
            "n": R_MOB_FACTORY_CAFETERIA,
        },
        "flags": {"indoors": True},
        "sector": 'inside',
    },
    R_MOB_FACTORY_INSPECTION_ROOM: {
        "name": 'Mob Factory Inspection Room',
        "desc": 'You have entered the mob factory inspections room. This is where the\nmobs manufactured on the assembly lines are inspected for defects. A\nwhole team of inspectors from the Midgaard Inspections Bureau is\nstanding around, trying to look busy. Exits are south to the mob\nfactory inspection room, east to the primary assembly line and west to\nthe storage area.',
        "exits": {
            "e": R_PRIMARY_ASSEMBLY_LINE,
            "s": R_MOB_FACTORY_INSPECTION_ROOM_9411,
            "w": R_MOB_FACTORY_STORAGE_AREA_9405,
        },
        "flags": {"indoors": True},
        "sector": 'inside',
    },
    R_MOB_FACTORY_INSPECTION_ROOM_9411: {
        "name": 'Mob Factory Inspection Room',
        "desc": 'You have entered the mob factory inspections room. This is where the\nmobs manufactured on the assembly lines are inspected for defects. A\nwhole team of inspectors from the Midgaard Inspections Bureau is\nstanding around, trying to look busy. Exits are south to the mob\nfactory inspection room, east to the primary assembly line and west to\nthe storage area.',
        "exits": {
            "n": R_MOB_FACTORY_INSPECTION_ROOM,
            "e": R_PRIMARY_ASSEMBLY_LINE_9416,
            "s": R_ENTRANCE_HALLWAY_TO_MOB_FACTORY_9412,
            "w": R_MOB_FACTORY_STORAGE_AREA_9406,
        },
        "flags": {"indoors": True},
        "sector": 'inside',
    },
    R_ENTRANCE_HALLWAY_TO_MOB_FACTORY_9412: {
        "name": 'Entrance Hallway to Mob Factory',
        "desc": 'You are standing in the entrance hallway of the mob factory. The sound\nof machinery gets louder now, and you can hear people shouting in the\ndistance. Every once in a while you get creepy feeling that a pair of\neyes is observing you...... Exits are north to the inspection room,\neast to the primary assembly line, south to the reject room and west\nto the entrance hallway.',
        "exits": {
            "n": R_MOB_FACTORY_INSPECTION_ROOM_9411,
            "e": R_PRIMARY_ASSEMBLY_LINE_9417,
            "s": R_MOB_FACTORY_REJECT_ROOM,
            "w": R_ENTRANCE_HALLWAY_TO_MOB_FACTORY,
        },
        "flags": {"indoors": True},
        "sector": 'inside',
    },
    R_MOB_FACTORY_REJECT_ROOM: {
        "name": 'Mob Factory Reject Room',
        "desc": 'This is the factory reject room. All the mobs that are manufactured\nincorrectly or have some defect are placed here before subsequent\ndestruction. You shudder at the many deformed and grotesque shapes\npresent before you. Exits are south to the reject room and north to\nthe entrance hallway.',
        "exits": {
            "n": R_ENTRANCE_HALLWAY_TO_MOB_FACTORY_9412,
            "s": R_MOB_FACTORY_REJECT_ROOM_9414,
        },
        "flags": {"indoors": True},
        "sector": 'inside',
    },
    R_MOB_FACTORY_REJECT_ROOM_9414: {
        "name": 'Mob Factory Reject Room',
        "desc": 'This is the factory reject room. All the mobs that are manufactured\nincorrectly or have some defect are placed here before subsequent\ndestruction. You shudder at the many deformed and grotesque shapes\npresent before you. The only exit is north to the reject room.',
        "exits": {
            "n": R_MOB_FACTORY_REJECT_ROOM,
        },
        "flags": {"indoors": True},
        "sector": 'inside',
    },
    R_PRIMARY_ASSEMBLY_LINE: {
        "name": 'Primary Assembly Line',
        "desc": 'This is the primary assembly line of the mob factory. Here, all the\nmobs seen roaming around the city of Midgaard are manufactured from\nraw materials. There is a big conveyor belt present which makes a lot\nof noise! It seems that the workers are making drunks today. Exits are\neast to the secondary assembly line, south to the primary assembly\nline and west to the inspection room.',
        "exits": {
            "e": R_SECONDARY_ASSEMBLY_LINE,
            "s": R_PRIMARY_ASSEMBLY_LINE_9416,
            "w": R_MOB_FACTORY_INSPECTION_ROOM,
        },
        "flags": {"indoors": True},
        "sector": 'inside',
    },
    R_PRIMARY_ASSEMBLY_LINE_9416: {
        "name": 'Primary Assembly Line',
        "desc": 'This is the primary assembly line of the mob factory. Here, all the\nmobs seen roaming around the city of Midgaard are manufactured from\nraw materials. There is a big conveyor belt present which makes a lot\nof noise! It seems that the workers are making drunks today. Exits are\neast to the secondary assembly line, north and south to the primary\nassembly line and west to the inspection room.',
        "exits": {
            "n": R_PRIMARY_ASSEMBLY_LINE,
            "e": R_SECONDARY_ASSEMBLY_LINE_9421,
            "s": R_PRIMARY_ASSEMBLY_LINE_9417,
            "w": R_MOB_FACTORY_INSPECTION_ROOM_9411,
        },
        "flags": {"indoors": True},
        "sector": 'inside',
    },
    R_PRIMARY_ASSEMBLY_LINE_9417: {
        "name": 'Primary Assembly Line',
        "desc": 'This is the primary assembly line of the mob factory. Here, all the\nmobs seen roaming around the city of Midgaard are manufactured from\nraw materials. There is a big conveyor belt present which makes a lot\nof noise! It seems that the workers are making drunks today. Exits are\neast to the secondary assembly line, north and south to the primary\nassembly line and west to the entrance hallway.',
        "exits": {
            "n": R_PRIMARY_ASSEMBLY_LINE_9416,
            "e": R_SECONDARY_ASSEMBLY_LINE_9422,
            "s": R_PRIMARY_ASSEMBLY_LINE_9418,
            "w": R_ENTRANCE_HALLWAY_TO_MOB_FACTORY_9412,
        },
        "flags": {"indoors": True},
        "sector": 'inside',
    },
    R_PRIMARY_ASSEMBLY_LINE_9418: {
        "name": 'Primary Assembly Line',
        "desc": 'This is the primary assembly line of the mob factory. Here, all the\nmobs seen roaming around the city of Midgaard are manufactured from\nraw materials. There is a big conveyor belt present which makes a lot\nof noise! It seems that the workers are making drunks today. Exits are\neast to the secondary assembly line, north and south to the primary\nassembly line.',
        "exits": {
            "n": R_PRIMARY_ASSEMBLY_LINE_9417,
            "e": R_SECONDARY_ASSEMBLY_LINE_9423,
            "s": R_PRIMARY_ASSEMBLY_LINE_9419,
        },
        "flags": {"indoors": True},
        "sector": 'inside',
    },
    R_PRIMARY_ASSEMBLY_LINE_9419: {
        "name": 'Primary Assembly Line',
        "desc": 'This is the primary assembly line of the mob factory. Here, all the\nmobs seen roaming around the city of Midgaard are manufactured from\nraw materials. There is a big conveyor belt present which makes a lot\nof noise! It seems that the workers are making drunks today. Exits are\neast to the secondary assembly line and north to the primary\nassembly line.',
        "exits": {
            "n": R_PRIMARY_ASSEMBLY_LINE_9418,
            "e": R_SECONDARY_ASSEMBLY_LINE_9424,
        },
        "flags": {"indoors": True},
        "sector": 'inside',
    },
    R_SECONDARY_ASSEMBLY_LINE: {
        "name": 'Secondary Assembly Line',
        "desc": 'This is the secondary asembly line of the mob factory. You are\nsurprised to see cityguard heads come floating on the conveyor belt!\nThe very sight is sickening, but the workers seem to be quite\ncheerful about their work. Exits are south to the secondary assembly\nline and west to the primary assembly line.',
        "exits": {
            "s": R_SECONDARY_ASSEMBLY_LINE_9421,
            "w": R_PRIMARY_ASSEMBLY_LINE,
        },
        "flags": {"indoors": True},
        "sector": 'inside',
    },
    R_SECONDARY_ASSEMBLY_LINE_9421: {
        "name": 'Secondary Assembly Line',
        "desc": 'This is the secondary asembly line of the mob factory. You are\nsurprised to see cityguard heads come floating on the conveyor belt!\nThe very sight is sickening, but the workers seem to be quite\ncheerful about their work. Exits are north and south to the secondary\nassembly line and west to the primary assembly line.',
        "exits": {
            "n": R_SECONDARY_ASSEMBLY_LINE,
            "s": R_SECONDARY_ASSEMBLY_LINE_9422,
            "w": R_PRIMARY_ASSEMBLY_LINE_9416,
        },
        "flags": {"indoors": True},
        "sector": 'inside',
    },
    R_SECONDARY_ASSEMBLY_LINE_9422: {
        "name": 'Secondary Assembly Line',
        "desc": 'This is the secondary asembly line of the mob factory. You are\nsurprised to see cityguard heads come floating on the conveyor belt!\nThe very sight is sickening, but the workers seem to be quite\ncheerful about their work. Exits are north and south to the secondary\nassembly line and west to the primary assembly line.',
        "exits": {
            "n": R_SECONDARY_ASSEMBLY_LINE_9421,
            "s": R_SECONDARY_ASSEMBLY_LINE_9423,
            "w": R_PRIMARY_ASSEMBLY_LINE_9417,
        },
        "flags": {"indoors": True},
        "sector": 'inside',
    },
    R_SECONDARY_ASSEMBLY_LINE_9423: {
        "name": 'Secondary Assembly Line',
        "desc": 'This is the secondary asembly line of the mob factory. You are\nsurprised to see cityguard heads come floating on the conveyor belt!\nThe very sight is sickening, but the workers seem to be quite\ncheerful about their work. Exits are north and south to the secondary\nassembly line and west to the primary assembly line.',
        "exits": {
            "n": R_SECONDARY_ASSEMBLY_LINE_9422,
            "s": R_SECONDARY_ASSEMBLY_LINE_9424,
            "w": R_PRIMARY_ASSEMBLY_LINE_9418,
        },
        "flags": {"indoors": True},
        "sector": 'inside',
    },
    R_SECONDARY_ASSEMBLY_LINE_9424: {
        "name": 'Secondary Assembly Line',
        "desc": 'This is the secondary asembly line of the mob factory. You are\nsurprised to see cityguard heads come floating on the conveyor belt!\nThe very sight is sickening, but the workers seem to be quite\ncheerful about their work. Exits are north to the secondary\nassembly line and west to the primary assembly line.',
        "exits": {
            "n": R_SECONDARY_ASSEMBLY_LINE_9423,
            "w": R_PRIMARY_ASSEMBLY_LINE_9419,
        },
        "flags": {"indoors": True},
        "sector": 'inside',
    },
}

# -- Item templates -------------------------------------------------------------
OBJECTS = {
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
    ("M", M_OLDSTYLE_TOXIC_SLIME, 7, R_MOB_FACTORY_STORAGE_AREA, 1),
    ("M", M_OLDSTYLE_FIDO_MUTANT_DOG, 5, R_MOB_FACTORY_STORAGE_AREA_9402, 1),
    ("M", M_OLDSTYLE_FOREMAN_FLOYD, 1, R_FOREMAN_S_OFFICE, 1),
    ("M", M_OLDSTYLE_TOXIC_SLIME, 7, R_FOREMAN_S_BATHROOM, 1),
    ("M", M_OLDSTYLE_CITYGUARD_GUARD_HEAD, 7, R_MOB_FACTORY_STORAGE_AREA_9406, 1),
    ("M", M_OLDSTYLE_TOXIC_SLIME, 7, R_MOB_FACTORY_CAFETERIA, 1),
    ("M", M_OLDSTYLE_FIDO_MUTANT_DOG, 5, R_MOB_FACTORY_CAFETERIA, 1),
    ("M", M_OLDSTYLE_TOXIC_SLIME, 7, R_MOB_FACTORY_CAFETERIA_9409, 1),
    ("M", M_OLDSTYLE_WORKER_9407, 3, R_MOB_FACTORY_INSPECTION_ROOM, 1),
    ("M", M_OLDSTYLE_REVOLVING_DRUNK, 4, R_MOB_FACTORY_INSPECTION_ROOM, 2),
    ("M", M_OLDSTYLE_CITYGUARD_GUARD_HEAD, 7, R_MOB_FACTORY_INSPECTION_ROOM, 1),
    ("M", M_OLDSTYLE_WORKER_9407, 3, R_MOB_FACTORY_INSPECTION_ROOM_9411, 1),
    ("M", M_OLDSTYLE_FIDO_MUTANT_DOG, 5, R_MOB_FACTORY_INSPECTION_ROOM_9411, 1),
    ("M", M_OLDSTYLE_REVOLVING_DRUNK, 4, R_MOB_FACTORY_REJECT_ROOM, 2),
    ("M", M_OLDSTYLE_CITYGUARD_GUARD_HEAD, 7, R_MOB_FACTORY_REJECT_ROOM_9414, 1),
    ("M", M_OLDSTYLE_TOXIC_SLIME, 7, R_PRIMARY_ASSEMBLY_LINE, 1),
    ("M", M_OLDSTYLE_WORKER, 8, R_PRIMARY_ASSEMBLY_LINE, 1),
    ("M", M_OLDSTYLE_WORKER, 8, R_PRIMARY_ASSEMBLY_LINE_9416, 1),
    ("M", M_OLDSTYLE_WORKER, 8, R_PRIMARY_ASSEMBLY_LINE_9417, 1),
    ("M", M_OLDSTYLE_WORKER, 8, R_PRIMARY_ASSEMBLY_LINE_9418, 1),
    ("M", M_OLDSTYLE_FIDO_MUTANT_DOG, 5, R_PRIMARY_ASSEMBLY_LINE_9418, 1),
    ("M", M_OLDSTYLE_WORKER, 8, R_PRIMARY_ASSEMBLY_LINE_9419, 1),
    ("M", M_OLDSTYLE_WORKER, 8, R_SECONDARY_ASSEMBLY_LINE, 1),
    ("M", M_OLDSTYLE_WORKER_9407, 3, R_SECONDARY_ASSEMBLY_LINE, 1),
    ("M", M_OLDSTYLE_TOXIC_SLIME, 7, R_SECONDARY_ASSEMBLY_LINE_9421, 1),
    ("M", M_OLDSTYLE_CITYGUARD_GUARD_HEAD, 7, R_SECONDARY_ASSEMBLY_LINE_9421, 1),
    ("M", M_OLDSTYLE_FIDO_MUTANT_DOG, 5, R_SECONDARY_ASSEMBLY_LINE_9422, 1),
    ("M", M_OLDSTYLE_CITYGUARD_GUARD_HEAD, 7, R_SECONDARY_ASSEMBLY_LINE_9422, 1),
    ("M", M_OLDSTYLE_WORKER, 8, R_SECONDARY_ASSEMBLY_LINE_9423, 1),
    ("M", M_OLDSTYLE_CITYGUARD_GUARD_HEAD, 7, R_SECONDARY_ASSEMBLY_LINE_9423, 1),
    ("M", M_OLDSTYLE_CITYGUARD_GUARD_HEAD, 7, R_SECONDARY_ASSEMBLY_LINE_9424, 1),
    ("M", M_OLDSTYLE_WORKER, 8, R_SECONDARY_ASSEMBLY_LINE_9424, 1),
    ("M", M_OLDSTYLE_TOXIC_SLIME, 7, R_SECONDARY_ASSEMBLY_LINE_9424, 1),
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
