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

# ── Room VNUMs -----------------------------------------------------------------
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

# ── Mob template VNUMs ---------------------------------------------------------
M_ACOLYTE_OF_ZUMP                  = 3700
M_BLOB                             = 3701
M_MONSTER                          = 3702
M_WIMPY_MONSTER                    = 3703
M_AGGRESSIVE_MONSTER               = 3704
M_WIMPY_AGGRESSIVE_MONSTER         = 3705
M_BIG_CREATURE                     = 3706
M_ADEPT_OF_SATIN                   = 3707
M_ADEPT_OF_ALANDER                 = 3708
M_RABBIT                           = 3709
M_LIZARD                           = 3710
M_BOAR                             = 3711
M_FOX                              = 3712
M_SNAIL                            = 3713
M_BEAST                            = 3714
M_BEAR                             = 3715
M_WOLF                             = 3716
M_ADEPT_OF_SELENE                  = 3717
M_ADEPT_OF_FUREY                   = 3718
M_PRIEST_OF_CIRCE                  = 3719
M_DIPLOMA_BEAST                    = 3720

# ── Item template VNUMs --------------------------------------------------------
I_SUB_ISSUE_MACE                   = 3700
I_SUB_ISSUE_DAGGER                 = 3701
I_SUB_ISSUE_SWORD                  = 3702
I_SUB_ISSUE_VEST                   = 3703
I_SUB_ISSUE_SHIELD                 = 3704
I_SUB_ISSUE_CLOAK                  = 3705
I_SUB_ISSUE_HELMET                 = 3706
I_PAIR_OF_SUB_ISSUE_LEGGINGS       = 3707
I_PAIR_OF_SUB_ISSUE_BOOTS          = 3708
I_PAIR_OF_SUB_ISSUE_GLOVES         = 3709
I_PAIR_OF_SUB_ISSUE_SLEEVES        = 3710
I_SUB_ISSUE_CAPE                   = 3711
I_SUB_ISSUE_BELT                   = 3712
I_SUB_ISSUE_BRACER                 = 3713
I_KEY                              = 3714
I_MUD_SCHOOL_DIPLOMA               = 3715
I_WAR_BANNER                       = 3716
I_SUB_ISSUE_SPEAR                  = 3717
I_SUB_ISSUE_STAFF                  = 3718
I_SUB_ISSUE_AXE                    = 3719
I_SUB_ISSUE_FLAIL                  = 3720
I_SUB_ISSUE_WHIP                   = 3721
I_SUB_ISSUE_GLAIVE                 = 3722

# ── Rooms ----------------------------------------------------------------------
ROOMS = {
    R_ENTRANCE_TO_MUD_SCHOOL: {
        "name":  'Entrance to Mud School',
        "short": 'This is the entrance to the Merc Mud School.',
        "long":  "This is the entrance to the Merc Mud School.  Go north to go through mud\nschool.  If you have been here before and want to go directly to the arena,\ngo south.\n\nA sign warns 'You may not pass these doors once you have passed level 5.'",
        "exits": {
            "n": R_ROOM_IN_MUD_SCHOOL_3757,
            "s": R_NORTH_WALL_OF_ARENA_3744,  # door: {"isdoor": True, "closed": True}
            "d": 3001,
        },
        "flags": {"no_mob": True, "indoors": True},
    },
    R_ROOM_IN_MUD_SCHOOL: {
        "name":  'A Room in Mud School',
        "short": 'You are in a square white room.',
        "long":  'You are in a square white room.  The walls are all blank, with no windows.\nLight fluoresces off the ceiling in soft white tones.  Of course, there is a\nsign on the wall.  The exits are west and south.  A small plaque is on the\nwall.',
        "exits": {
            "s": R_ROOM_IN_MUD_SCHOOL_3757,
            "w": R_CENTER_ROOM,
        },
        "flags": {"no_mob": True, "indoors": True, "_unknown_bits": [17]},
    },
    R_CENTER_ROOM: {
        "name":  'The Center Room',
        "short": 'You are in a square white room.',
        "long":  'You are in a square white room.  The walls are all blank, with no windows.\nLight fluoresces off the ceiling in soft white tones.  Of course, there is a\nsign on the wall.  Exits lead in ALL directions.',
        "exits": {
            "n": R_ROOM_IN_MUD_SCHOOL_3703,
            "e": R_ROOM_IN_MUD_SCHOOL,
            "s": R_ROOM_IN_MUD_SCHOOL_3705,
            "w": R_ROOM_IN_MUD_SCHOOL_3704,
            "u": R_ROOM_IN_MUD_SCHOOL_3708,
            "d": R_ROOM_IN_MUD_SCHOOL_3707,
        },
        "flags": {"no_mob": True, "indoors": True, "_unknown_bits": [17]},
    },
    R_ROOM_IN_MUD_SCHOOL_3703: {
        "name":  'A Room in Mud School',
        "short": 'You are in a square white room.',
        "long":  'You are in a square white room.  The walls are all blank, with no windows.\nLight fluoresces off the ceiling in soft white tones.  Of course, there is a\nsign on the wall.  Exits lead north and south.',
        "exits": {
            "n": R_ROOM_IN_MUD_SCHOOL_3709,
            "s": R_CENTER_ROOM,
        },
        "flags": {"no_mob": True, "indoors": True, "_unknown_bits": [17]},
    },
    R_ROOM_IN_MUD_SCHOOL_3704: {
        "name":  'A Room in Mud School',
        "short": 'You are in a square white room.',
        "long":  'You are in a square white room.  The walls are all blank, with no windows.\nLight fluoresces off the ceiling in soft white tones.  Of course, there is a\nsign on the wall.  The only exit is east.',
        "exits": {
            "e": R_CENTER_ROOM,
        },
        "flags": {"no_mob": True, "indoors": True, "_unknown_bits": [17]},
    },
    R_ROOM_IN_MUD_SCHOOL_3705: {
        "name":  'A Room in Mud School',
        "short": 'You are in a square white room.',
        "long":  'You are in a square white room.  The walls are all blank, with no windows.\nLight fluoresces off the ceiling in soft white tones.  Of course, there is a\nsign on the wall.  The only exit is north.',
        "exits": {
            "n": R_CENTER_ROOM,
        },
        "flags": {"no_mob": True, "indoors": True, "_unknown_bits": [17]},
    },
    R_ROOM_IN_MUD_SCHOOL_3707: {
        "name":  'A Room in Mud School',
        "short": 'You are in a square white room.',
        "long":  'You are in a square white room.  The walls are all blank, with no windows.\nLight fluoresces off the ceiling in soft white tones.  Of course, there is a\nsign on the wall.  The only exit is up.',
        "exits": {
            "u": R_CENTER_ROOM,
        },
        "flags": {"no_mob": True, "indoors": True, "_unknown_bits": [17]},
    },
    R_ROOM_IN_MUD_SCHOOL_3708: {
        "name":  'A Room in Mud School',
        "short": 'You are in a square white room.',
        "long":  'You are in a square white room.  The walls are all blank, with no windows.\nLight fluoresces off the ceiling in soft white tones.  Of course, there is a\nsign on the wall.  The only exit is down.',
        "exits": {
            "d": R_CENTER_ROOM,
        },
        "flags": {"no_mob": True, "indoors": True, "_unknown_bits": [17]},
    },
    R_ROOM_IN_MUD_SCHOOL_3709: {
        "name":  'A Room in Mud School',
        "short": 'You are in a square white room.',
        "long":  'You are in a square white room.  The walls are all blank, with no windows.\nLight fluoresces off the ceiling in soft white tones.  Of course, there is a\nsign on the wall.  Exits reach west and down.',
        "exits": {
            "w": R_ROOM_IN_MUD_SCHOOL_3711,
            "d": R_BLOB_CAGE,
        },
        "flags": {"no_mob": True, "indoors": True, "_unknown_bits": [17]},
    },
    R_BLOB_CAGE: {
        "name":  'The Blob Cage',
        "short": 'You are in a smelly cage.',
        "long":  'You are in a smelly cage.  Strangely, the walls are still clean!\nYou see a sign here.  The only exit is up.',
        "exits": {
            "u": R_ROOM_IN_MUD_SCHOOL_3709,
        },
        "flags": {"indoors": True, "_unknown_bits": [17]},
    },
    R_ROOM_IN_MUD_SCHOOL_3711: {
        "name":  'A Room in Mud School',
        "short": 'You are in a square white room.',
        "long":  'You are in a square white room.  The walls are all blank, with no windows.\nLight fluoresces off the ceiling in soft white tones.  Of course, there is a\nsign on the wall.',
        "exits": {
            "e": R_ROOM_IN_MUD_SCHOOL_3709,
            "d": R_CAGE_ROOM,
        },
        "flags": {"no_mob": True, "indoors": True, "_unknown_bits": [17]},
    },
    R_CAGE_ROOM: {
        "name":  'The Cage Room',
        "short": 'You are in the cage room.',
        "long":  'You are in the cage room.  All around are 4 cages.  Light fluoresces off the\nceiling in soft white tones.  Of course, there is a big sign on the wall.\nExits lead into the cardinal directions plus down.',
        "exits": {
            "n": R_CAGE,
            "e": R_CAGE_3716,
            "s": R_CAGE_3715,
            "w": R_CAGE_3714,
            "d": R_ROOM_IN_MUD_SCHOOL_3717,
        },
        "flags": {"no_mob": True, "indoors": True, "_unknown_bits": [17]},
    },
    R_CAGE: {
        "name":  'A Cage',
        "short": 'You are in a cage.',
        "long":  'You are in a cage.  Blood and gore are everywhere.  The keepers must be lax\nin the upkeep here!  There is a sign on the wall.  The only exit is south.',
        "exits": {
            "s": R_CAGE_ROOM,
        },
        "flags": {"indoors": True, "_unknown_bits": [17]},
    },
    R_CAGE_3714: {
        "name":  'A Cage',
        "short": 'You are in a cage.',
        "long":  'You are in a cage.  Blood and gore are everywhere.  The keepers must be lax\nin the upkeep here!  There is a sign on the wall.  The only exit is east.',
        "exits": {
            "e": R_CAGE_ROOM,
        },
        "flags": {"indoors": True, "_unknown_bits": [17]},
    },
    R_CAGE_3715: {
        "name":  'A Cage',
        "short": 'You are in a cage.',
        "long":  'You are in a cage.  Blood and gore are everywhere.  The keepers must be lax\nin the upkeep here!  There is a sign on the wall.  The only exit is north.',
        "exits": {
            "n": R_CAGE_ROOM,
        },
        "flags": {"indoors": True, "_unknown_bits": [17]},
    },
    R_CAGE_3716: {
        "name":  'A Cage',
        "short": 'You are in a cage.',
        "long":  'You are in a cage.  Blood and gore are everywhere.  The keepers must be lax\nin the upkeep here!  There is a sign on the wall.  The only exit is west.',
        "exits": {
            "w": R_CAGE_ROOM,
        },
        "flags": {"indoors": True, "_unknown_bits": [17]},
    },
    R_ROOM_IN_MUD_SCHOOL_3717: {
        "name":  'A Room in Mud School',
        "short": 'You are in a square white room.',
        "long":  'You are in a square white room.  The walls are all blank, with no windows.\nLight fluoresces off the ceiling in soft white tones.  Of course, there is a\nsign on the wall.  Find your own exit here.',
        "exits": {
            "e": R_ROOM_IN_MUD_SCHOOL_3719,  # door: {"isdoor": True, "closed": True}
            "s": R_STORE_IN_MUD_SCHOOL,
            "u": R_CAGE_ROOM,
        },
        "flags": {"no_mob": True, "indoors": True, "_unknown_bits": [17]},
    },
    R_STORE_IN_MUD_SCHOOL: {
        "name":  'The Store in Mud School',
        "short": 'You are in a cramped room.',
        "long":  'You are in a cramped room.  Stacked neatly on shelves everywhere are items\nand packages.  Light fluoresces off the ceiling in soft white tones.  Of\ncourse, there is a sign on the wall.  The only exit is north.',
        "exits": {
            "n": R_ROOM_IN_MUD_SCHOOL_3717,
        },
        "flags": {"indoors": True, "_unknown_bits": [17]},
    },
    R_ROOM_IN_MUD_SCHOOL_3719: {
        "name":  'A Room in Mud School',
        "short": 'You are in a square white room.',
        "long":  'You are in a square white room.  The walls are all blank, with no windows.\nLight fluoresces off the ceiling in soft white tones.  Of course, there is a\nsign on the wall.  The exits are north and west, with a door to the east.',
        "exits": {
            "n": R_DARKENED_ROOM,
            "e": R_END_OF_MUD_SCHOOL,  # door: {"isdoor": True, "closed": True, "locked": True, "pickproof": True}
            "w": R_ROOM_IN_MUD_SCHOOL_3717,  # door: {"isdoor": True, "closed": True}
        },
        "flags": {"no_mob": True, "indoors": True, "_unknown_bits": [17]},
    },
    R_DARKENED_ROOM: {
        "name":  'The Darkened Room',
        "short": 'This room was purposefully darkened so that you would need to hold on to...',
        "long":  'This room was purposefully darkened so that you would need to hold on to a\nlight source to go through.  The walls are, of course, blank, and white.\nThe only exit is south.',
        "exits": {
            "s": R_ROOM_IN_MUD_SCHOOL_3719,
        },
        "flags": {"dark": True, "indoors": True, "_unknown_bits": [17]},
    },
    R_END_OF_MUD_SCHOOL: {
        "name":  'The End of Mud School!',
        "short": 'This is a very bright room, with a marble pedestal in the center.',
        "long":  'This is a very bright room, with a marble pedestal in the center.  Behind\nthe pedestal stands a person cloaked in Silver.  Tapestries flow from every\nwall, and you feel very happy to be here right now.  There is a big sign here.\nThe only exit is on the other side of the gate north of you.',
        "exits": {
            "n": R_SOUTH_WALL_OF_ARENA,  # door: {"isdoor": True, "closed": True}
        },
        "flags": {"indoors": True, "_unknown_bits": [17]},
    },
    R_SOUTH_WALL_OF_ARENA: {
        "name":  'South Wall of Arena',
        "short": 'You are in the Arena.',
        "long":  'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
        "exits": {
            "n": R_ARENA_3729,
            "e": R_SOUTH_WALL_OF_ARENA_3725,
            "w": R_SOUTH_WALL_OF_ARENA_3723,
            "u": R_SAFE_ROOM,
        },
        "flags": {"indoors": True},
    },
    R_SOUTH_WALL_OF_ARENA_3723: {
        "name":  'South Wall of Arena',
        "short": 'You are in the Arena.',
        "long":  'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
        "exits": {
            "n": R_ARENA,
            "e": R_SOUTH_WALL_OF_ARENA,
            "w": R_SOUTH_WEST_CORNER_OF_ARENA,
            "u": R_SAFE_ROOM,
        },
        "flags": {"indoors": True},
    },
    R_SOUTH_WEST_CORNER_OF_ARENA: {
        "name":  'South West Corner of Arena',
        "short": 'You are in the Arena.',
        "long":  'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
        "exits": {
            "n": R_WEST_WALL_OF_ARENA,
            "e": R_SOUTH_WALL_OF_ARENA_3723,
            "u": R_SAFE_ROOM,
        },
        "flags": {"indoors": True},
    },
    R_SOUTH_WALL_OF_ARENA_3725: {
        "name":  'South Wall of Arena',
        "short": 'You are in the Arena.',
        "long":  'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
        "exits": {
            "n": R_ARENA_3730,
            "e": R_SOUTH_EAST_CORNER_OF_ARENA,
            "w": R_SOUTH_WALL_OF_ARENA,
            "u": R_SAFE_ROOM,
        },
        "flags": {"indoors": True},
    },
    R_SOUTH_EAST_CORNER_OF_ARENA: {
        "name":  'South East Corner of Arena',
        "short": 'You are in the Arena.',
        "long":  'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
        "exits": {
            "n": R_EAST_WALL_OF_ARENA,
            "w": R_SOUTH_WALL_OF_ARENA_3725,
            "u": R_SAFE_ROOM,
        },
        "flags": {"indoors": True},
    },
    R_WEST_WALL_OF_ARENA: {
        "name":  'West Wall of Arena',
        "short": 'You are in the Arena.',
        "long":  'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
        "exits": {
            "n": R_WEST_WALL_OF_ARENA_3732,
            "e": R_ARENA,
            "s": R_SOUTH_WEST_CORNER_OF_ARENA,
            "u": R_SAFE_ROOM,
        },
        "flags": {"indoors": True},
    },
    R_ARENA: {
        "name":  'Arena',
        "short": 'You are in the Arena.',
        "long":  'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
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
        "name":  'Arena',
        "short": 'You are in the Arena.',
        "long":  'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
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
        "name":  'Arena',
        "short": 'You are in the Arena.',
        "long":  'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
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
        "name":  'East Wall of Arena',
        "short": 'You are in the Arena.',
        "long":  'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
        "exits": {
            "n": R_EAST_WALL_OF_ARENA_3736,
            "s": R_SOUTH_EAST_CORNER_OF_ARENA,
            "w": R_ARENA_3730,
            "u": R_SAFE_ROOM,
        },
        "flags": {"indoors": True},
    },
    R_WEST_WALL_OF_ARENA_3732: {
        "name":  'West Wall of Arena',
        "short": 'You are in the Arena.',
        "long":  'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
        "exits": {
            "n": R_WEST_WALL_OF_ARENA_3737,
            "e": R_ARENA_3733,
            "s": R_WEST_WALL_OF_ARENA,
            "u": R_SAFE_ROOM,
        },
        "flags": {"indoors": True},
    },
    R_ARENA_3733: {
        "name":  'Arena',
        "short": 'You are in the Arena.',
        "long":  'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
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
        "name":  'Center of Arena',
        "short": 'You are in the Arena.',
        "long":  'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.  There is a BIG SIGN here.',
        "exits": {
            "n": R_ARENA_3739,
            "e": R_ARENA_3735,
            "s": R_ARENA_3729,
            "w": R_ARENA_3733,
            "u": R_SAFE_ROOM,
            "d": R_CENTER_OF_THE_DUNGEON,  # door: {"isdoor": True, "closed": True}
        },
        "flags": {"indoors": True},
    },
    R_ARENA_3735: {
        "name":  'Arena',
        "short": 'You are in the Arena.',
        "long":  'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
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
        "name":  'East Wall of Arena',
        "short": 'You are in the Arena.',
        "long":  'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
        "exits": {
            "n": R_EAST_WALL_OF_ARENA_3741,
            "s": R_EAST_WALL_OF_ARENA,
            "w": R_ARENA_3735,
            "u": R_SAFE_ROOM,
        },
        "flags": {"indoors": True},
    },
    R_WEST_WALL_OF_ARENA_3737: {
        "name":  'West Wall of Arena',
        "short": 'You are in the Arena.',
        "long":  'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
        "exits": {
            "n": R_NORTH_WEST_CORNER_OF_ARENA,
            "e": R_ARENA_3738,
            "s": R_WEST_WALL_OF_ARENA_3732,
            "u": R_SAFE_ROOM,
        },
        "flags": {"indoors": True},
    },
    R_ARENA_3738: {
        "name":  'Arena',
        "short": 'You are in the Arena.',
        "long":  'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
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
        "name":  'Arena',
        "short": 'You are in the Arena.',
        "long":  'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
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
        "name":  'Arena',
        "short": 'You are in the Arena.',
        "long":  'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
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
        "name":  'East Wall of Arena',
        "short": 'You are in the Arena.',
        "long":  'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
        "exits": {
            "n": R_NORTH_EAST_CORNER_OF_ARENA,
            "s": R_EAST_WALL_OF_ARENA_3736,
            "w": R_ARENA_3740,
            "u": R_SAFE_ROOM,
        },
        "flags": {"indoors": True},
    },
    R_NORTH_WEST_CORNER_OF_ARENA: {
        "name":  'North West Corner of Arena',
        "short": 'You are in the Arena.',
        "long":  'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
        "exits": {
            "e": R_NORTH_WALL_OF_ARENA,
            "s": R_WEST_WALL_OF_ARENA_3737,
            "u": R_SAFE_ROOM,
        },
        "flags": {"indoors": True},
    },
    R_NORTH_WALL_OF_ARENA: {
        "name":  'North Wall of Arena',
        "short": 'You are in the Arena.',
        "long":  'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  You can barely see the ceiling.  You feel as if you are being watched\nby some divine being.',
        "exits": {
            "e": R_NORTH_WALL_OF_ARENA_3744,
            "s": R_ARENA_3738,
            "w": R_NORTH_WEST_CORNER_OF_ARENA,
            "u": R_SAFE_ROOM,
        },
        "flags": {"indoors": True},
    },
    R_NORTH_WALL_OF_ARENA_3744: {
        "name":  'North Wall of Arena',
        "short": 'You are in the Arena.',
        "long":  'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
        "exits": {
            "e": R_NORTH_WALL_OF_ARENA_3745,
            "s": R_ARENA_3739,
            "w": R_NORTH_WALL_OF_ARENA,
            "u": R_SAFE_ROOM,
        },
        "flags": {"indoors": True},
    },
    R_NORTH_WALL_OF_ARENA_3745: {
        "name":  'North Wall of Arena',
        "short": 'You are in the Arena.',
        "long":  'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
        "exits": {
            "e": R_NORTH_EAST_CORNER_OF_ARENA,
            "s": R_ARENA_3740,
            "w": R_NORTH_WALL_OF_ARENA_3744,
            "u": R_SAFE_ROOM,
        },
        "flags": {"indoors": True},
    },
    R_NORTH_EAST_CORNER_OF_ARENA: {
        "name":  'North East Corner of Arena',
        "short": 'You are in the Arena.',
        "long":  'You are in the Arena.  Remember, if you wish to get out of this Arena, just\ngo up.  Ceilings can barely be seen in this huge Arena.  You feel as if you are\nbeing watched by some divine being.',
        "exits": {
            "s": R_EAST_WALL_OF_ARENA_3741,
            "w": R_NORTH_WALL_OF_ARENA_3745,
            "u": R_SAFE_ROOM,
        },
        "flags": {"indoors": True},
    },
    R_CENTER_OF_THE_DUNGEON: {
        "name":  'The Center of the Dungeon',
        "short": 'You are in the center of a large room.',
        "long":  'You are in the center of a large room.  A faint light from above shows that\nthe floors are all covered with slime.  A feeling of dread comes over you as\nyou notice that this is NOT a great place to go.  Exits go in all directions.\nOf special note is the one that brings you back up!!!',
        "exits": {
            "n": R_NORTH_WALL_OF_THE_DUNGEON,
            "e": R_EAST_WALL_OF_THE_DUNGEON,
            "s": R_SOUTH_WALL_OF_THE_DUNGEON,
            "w": R_WEST_WALL_OF_THE_DUNGEON,
            "u": R_CENTER_OF_ARENA,  # door: {"isdoor": True, "closed": True}
        },
        "flags": {"indoors": True},
    },
    R_NORTH_WEST_CORNER_OF_THE_DUNGEON: {
        "name":  'The North West Corner of the Dungeon',
        "short": 'You are against a wall in the dungeon.',
        "long":  'You are against a wall in the dungeon.  It is quite dark here.  The lack of\nany windows in the area explains the smell around you.',
        "exits": {
            "e": R_NORTH_WALL_OF_THE_DUNGEON,
            "s": R_WEST_WALL_OF_THE_DUNGEON,
        },
        "flags": {"dark": True, "indoors": True},
    },
    R_NORTH_WALL_OF_THE_DUNGEON: {
        "name":  'The North Wall of the Dungeon',
        "short": 'You are against a wall in the dungeon.',
        "long":  'You are against a wall in the dungeon.  It is quite dark here.  The lack of\nany windows in the area explains the smell around you.',
        "exits": {
            "e": R_NORTH_EAST_CORNER_OF_THE_DUNGEON,
            "s": R_CENTER_OF_THE_DUNGEON,
            "w": R_NORTH_WEST_CORNER_OF_THE_DUNGEON,
        },
        "flags": {"dark": True, "indoors": True},
    },
    R_NORTH_EAST_CORNER_OF_THE_DUNGEON: {
        "name":  'The North East Corner of the Dungeon',
        "short": 'You are against a wall in the dungeon.',
        "long":  'You are against a wall in the dungeon.  It is quite dark here.  The lack of\nany windows in the area explains the smell around you.',
        "exits": {
            "s": R_EAST_WALL_OF_THE_DUNGEON,
            "w": R_NORTH_WALL_OF_THE_DUNGEON,
        },
        "flags": {"dark": True, "indoors": True},
    },
    R_WEST_WALL_OF_THE_DUNGEON: {
        "name":  'The West Wall of the Dungeon',
        "short": 'You are against a wall in the dungeon.',
        "long":  'You are against a wall in the dungeon.  It is quite dark here.  The lack of\nany windows in the area explains the smell around you.',
        "exits": {
            "n": R_NORTH_WEST_CORNER_OF_THE_DUNGEON,
            "e": R_CENTER_OF_THE_DUNGEON,
            "s": R_SOUTH_WEST_CORNER_OF_THE_DUNGEON,
        },
        "flags": {"dark": True, "indoors": True},
    },
    R_EAST_WALL_OF_THE_DUNGEON: {
        "name":  'The East Wall of the Dungeon',
        "short": 'You are against a wall in the dungeon.',
        "long":  'You are against a wall in the dungeon.  It is quite dark here.  The lack of\nany windows in the area explains the smell around you.',
        "exits": {
            "n": R_NORTH_EAST_CORNER_OF_THE_DUNGEON,
            "s": R_SOUTH_EAST_CORNER_OF_THE_DUNGEON,
            "w": R_CENTER_OF_THE_DUNGEON,
        },
        "flags": {"dark": True, "indoors": True},
    },
    R_SOUTH_WEST_CORNER_OF_THE_DUNGEON: {
        "name":  'The South West Corner of the Dungeon',
        "short": 'You are against a wall in the dungeon.',
        "long":  'You are against a wall in the dungeon.  It is quite dark here.  The lack of\nany windows in the area explains the smell around you.',
        "exits": {
            "n": R_WEST_WALL_OF_THE_DUNGEON,
            "e": R_SOUTH_WALL_OF_THE_DUNGEON,
        },
        "flags": {"dark": True, "indoors": True},
    },
    R_SOUTH_WALL_OF_THE_DUNGEON: {
        "name":  'The South Wall of the Dungeon',
        "short": 'You are against a wall in the dungeon.',
        "long":  'You are against a wall in the dungeon.  It is quite dark here.  The lack of\nany windows in the area explains the smell around you.',
        "exits": {
            "n": R_CENTER_OF_THE_DUNGEON,
            "e": R_SOUTH_EAST_CORNER_OF_THE_DUNGEON,
            "w": R_SOUTH_WEST_CORNER_OF_THE_DUNGEON,
        },
        "flags": {"dark": True, "indoors": True},
    },
    R_SOUTH_EAST_CORNER_OF_THE_DUNGEON: {
        "name":  'The South East Corner of the Dungeon',
        "short": 'You are against a wall in the dungeon.',
        "long":  'You are against a wall in the dungeon.  It is quite dark here.  The lack of\nany windows in the area explains the smell around you.',
        "exits": {
            "n": R_EAST_WALL_OF_THE_DUNGEON,
            "w": R_SOUTH_WALL_OF_THE_DUNGEON,
        },
        "flags": {"dark": True, "indoors": True},
    },
    R_ROOM_IN_MUD_SCHOOL_3757: {
        "name":  'A Room in Mud School',
        "short": 'You are in a room in Mud School.',
        "long":  "You are in a room in Mud School.  Paintings of the heroic graduates of mud\nschool adorn the walls. To the west is Furey's Training Room, and to the east\nis Zump's Guild Room.  North of you is the next Station of Mud School.\nThere is a sign on the wall (type 'LOOK SIGN' to read it).",
        "exits": {
            "n": R_ROOM_IN_MUD_SCHOOL,
            "e": R_ZUMP_S_GUILD_ROOM,
            "s": R_ENTRANCE_TO_MUD_SCHOOL,
            "w": R_FUREY_S_TRAINING_ROOM,
        },
        "flags": {"no_mob": True, "indoors": True, "_unknown_bits": [17]},
        "sector": 1,
    },
    R_FUREY_S_TRAINING_ROOM: {
        "name":  "Furey's Training Room",
        "short": "You are in Furey's Training Room.",
        "long":  "You are in Furey's Training Room.  Around you are all sorts of physical\nand mental training tools.  The whole room is filled with magic, holiness,\nand sweat.  There is a sign on the wall.",
        "exits": {
            "e": R_ROOM_IN_MUD_SCHOOL_3757,
        },
        "flags": {"no_mob": True, "indoors": True, "_unknown_bits": [17]},
        "sector": 1,
    },
    R_ZUMP_S_GUILD_ROOM: {
        "name":  "Zump's Guild Room",
        "short": 'You are in a room filled with weapons, books, and many combat dummies, s...',
        "long":  'You are in a room filled with weapons, books, and many combat dummies, some\ncut and stabbed many times, others burnt to a crisp.  The room is filled with\nsweat and an aura of magic.  There is a sign on the wall.',
        "exits": {
            "w": R_ROOM_IN_MUD_SCHOOL_3757,
        },
        "flags": {"no_mob": True, "indoors": True, "_unknown_bits": [17]},
        "sector": 1,
    },
    R_SAFE_ROOM: {
        "name":  'A Safe Room',
        "short": 'You are in a safe room, away from all the mean rabbits and snails of the...',
        "long":  'You are in a safe room, away from all the mean rabbits and snails of the Arena.\nYou can rest here, and go up to go back to the Temple of Midgaard.',
        "exits": {
            "u": 3001,
        },
        "flags": {"no_mob": True, "indoors": True},
    },
}

# ── Mob templates --------------------------------------------------------------
# hp_dice / damage: (num_dice, die_size, bonus)
# AC: avg(pierce,bash,slash,exotic) / 10 per REFERENCE.md  # TODO: verify scale
# hitroll: from level line; no separate damroll in .are (dam_dice bonus is it)
# loot: left empty — populate from RESETS E/G lines if needed
MOBILES = {
    M_ACOLYTE_OF_ZUMP: {
        "name":    'Acolyte Of Zump',
        "desc":    'An acolyte of Zump welcomes you to mud school.',
        "level":   30,
        "hp_dice": (1, 1, 999),
        "hitroll": 10, "AC": -2,
        "damage":  (2, 4, 30),  # dam_type: 'beating'
        "gold":    0,
        "loot":    [],  # TODO: from RESETS E/G
        "act_flags": {"sentinel": True, "stay_area": True, "cleric": True, "warrior": True, "nopurge": True},
        "aff_flags": {"detect_evil": True, "sanctuary": True},
        "off_flags": {"area_attack": True, "bash": True, "disarm": True, "dodge": True, "fast": True, "kick": True, "parry": True, "trip": True},
        "imm_flags": {"summon": True, "charm": True, "magic": True, "weapon": True},
    },
    M_BLOB: {
        "name":    'Blob',
        "desc":    'The blob is here, waiting to eat you up.',
        "level":   5,
        "hp_dice": (1, 1, 49),
        "hitroll": -5, "AC": -2,
        "damage":  (1, 1, 0),  # dam_type: 'digestion'
        "gold":    0,
        "loot":    [],  # TODO: from RESETS E/G
        "act_flags": {"sentinel": True, "stay_area": True},
        "aff_flags": {"detect_evil": True},
        "off_flags": {"area_attack": True, "trip": True},
        "imm_flags": {"summon": True, "charm": True},
        "res_flags": {"magic": True, "weapon": True},
    },
    M_MONSTER: {
        "name":    'Monster',
        "desc":    'There is a monster leashed here.',
        "level":   1,
        "hp_dice": (1, 1, 7),
        "hitroll": 0, "AC": 1,
        "damage":  (1, 3, 0),  # dam_type: 'claw'
        "gold":    10,
        "loot":    [],  # TODO: from RESETS E/G
        "act_flags": {"sentinel": True, "noalign": True},
        "imm_flags": {"summon": True, "charm": True},
        "vuln_flags": {"magic": True},
    },
    M_WIMPY_MONSTER: {
        "name":    'Wimpy Monster',
        "desc":    'There is a wimpy monster leashed here.',
        "level":   1,
        "hp_dice": (1, 1, 7),
        "hitroll": 0, "AC": 1,
        "damage":  (1, 2, 0),  # dam_type: 'claw'
        "gold":    10,
        "loot":    [],  # TODO: from RESETS E/G
        "act_flags": {"sentinel": True, "wimpy": True, "noalign": True},
        "off_flags": {"crush": True},
        "imm_flags": {"summon": True, "charm": True},
        "vuln_flags": {"magic": True},
    },
    M_AGGRESSIVE_MONSTER: {
        "name":    'Aggressive Monster',
        "desc":    'There is an aggressive monster leashed here.',
        "level":   1,
        "hp_dice": (1, 1, 7),
        "hitroll": 0, "AC": 1,
        "damage":  (1, 4, 0),  # dam_type: 'claw'
        "gold":    10,
        "loot":    [],  # TODO: from RESETS E/G
        "act_flags": {"sentinel": True, "aggressive": True, "noalign": True},
        "off_flags": {"disarm": True, "parry": True},
        "imm_flags": {"summon": True, "charm": True},
        "vuln_flags": {"magic": True},
    },
    M_WIMPY_AGGRESSIVE_MONSTER: {
        "name":    'Wimpy Aggressive Monster',
        "desc":    'There is a wimpy aggressive monster leashed here.',
        "level":   1,
        "hp_dice": (1, 1, 7),
        "hitroll": 0, "AC": 1,
        "damage":  (1, 3, 0),  # dam_type: 'claw'
        "gold":    10,
        "loot":    [],  # TODO: from RESETS E/G
        "act_flags": {"sentinel": True, "aggressive": True, "wimpy": True, "noalign": True},
        "off_flags": {"kick_dirt": True},
        "imm_flags": {"summon": True, "charm": True},
        "vuln_flags": {"magic": True},
    },
    M_BIG_CREATURE: {
        "name":    'Big Creature',
        "desc":    'There is a big creature hulking over your form.',
        "level":   2,
        "hp_dice": (2, 2, 20),
        "hitroll": 1, "AC": 0,
        "damage":  (1, 4, 1),  # dam_type: 'claw'
        "gold":    25,
        "loot":    [],  # TODO: from RESETS E/G
        "act_flags": {"sentinel": True, "noalign": True},
        "aff_flags": {"infrared": True, "dark_vision": True},
        "off_flags": {"dodge": True, "trip": True},
        "imm_flags": {"summon": True, "charm": True},
        "vuln_flags": {"magic": True},
    },
    M_ADEPT_OF_SATIN: {
        "name":    'Adept Of Satin',
        "desc":    'An adept of the mighty goddess Satin is here, contemplating your progress.',
        "level":   30,
        "hp_dice": (1, 1, 999),
        "hitroll": 10, "AC": -2,
        "damage":  (2, 4, 30),  # dam_type: 'beating'
        "gold":    0,
        "loot":    [],  # TODO: from RESETS E/G
        "act_flags": {"sentinel": True, "stay_area": True, "cleric": True, "warrior": True, "nopurge": True},
        "aff_flags": {"detect_evil": True, "sanctuary": True},
        "off_flags": {"area_attack": True, "bash": True, "disarm": True, "dodge": True, "fast": True, "kick": True, "parry": True, "trip": True},
        "imm_flags": {"summon": True, "charm": True, "magic": True, "weapon": True},
    },
    M_ADEPT_OF_ALANDER: {
        "name":    'Adept Of Alander',
        "desc":    'An adept of Alander is here, smiling at you.',
        "level":   30,
        "hp_dice": (1, 1, 999),
        "hitroll": 10, "AC": -2,
        "damage":  (2, 4, 30),  # dam_type: 'beating'
        "gold":    0,
        "loot":    [],  # TODO: from RESETS E/G
        "act_flags": {"sentinel": True, "stay_area": True, "cleric": True, "warrior": True, "nopurge": True},
        "aff_flags": {"detect_evil": True, "sanctuary": True},
        "off_flags": {"area_attack": True, "bash": True, "disarm": True, "dodge": True, "fast": True, "kick": True, "parry": True, "trip": True},
        "imm_flags": {"summon": True, "charm": True, "magic": True, "weapon": True},
    },
    M_RABBIT: {
        "name":    'Rabbit',
        "desc":    'A rabbit is bouncing around here.',
        "level":   1,
        "hp_dice": (1, 1, 10),
        "hitroll": 0, "AC": 1,
        "damage":  (1, 3, 0),  # dam_type: 'bite'
        "gold":    0,
        "loot":    [],  # TODO: from RESETS E/G
        "act_flags": {"stay_area": True, "wimpy": True, "noalign": True},
        "off_flags": {"dodge": True, "fast": True},
    },
    M_LIZARD: {
        "name":    'Lizard',
        "desc":    'A lizard slithers up to you.',
        "level":   2,
        "hp_dice": (2, 2, 20),
        "hitroll": 0, "AC": 0,
        "damage":  (1, 4, 1),  # dam_type: 'bite'
        "gold":    0,
        "loot":    [],  # TODO: from RESETS E/G
        "act_flags": {"stay_area": True, "noalign": True},
        "off_flags": {"assist_race": True},
        "res_flags": {"poison": True},
        "vuln_flags": {"cold": True},
    },
    M_BOAR: {
        "name":    'Boar',
        "desc":    'A boar tries to run you over.',
        "level":   3,
        "hp_dice": (3, 3, 30),
        "hitroll": 1, "AC": 0,
        "damage":  (1, 6, 1),  # dam_type: 'charge'
        "gold":    0,
        "loot":    [],  # TODO: from RESETS E/G
        "act_flags": {"stay_area": True, "noalign": True},
        "off_flags": {"bash": True, "berserk": True, "dodge": True, "assist_race": True},
    },
    M_FOX: {
        "name":    'Fox',
        "desc":    'A fox is here staring at you.',
        "level":   1,
        "hp_dice": (1, 1, 12),
        "hitroll": 1, "AC": 0,
        "damage":  (1, 3, 1),  # dam_type: 'bite'
        "gold":    0,
        "loot":    [],  # TODO: from RESETS E/G
        "act_flags": {"stay_area": True, "wimpy": True, "noalign": True},
        "aff_flags": {"dark_vision": True},
        "off_flags": {"dodge": True, "fast": True, "trip": True, "assist_race": True},
    },
    M_SNAIL: {
        "name":    'Snail',
        "desc":    'A snail is trying to get out of your way.',
        "level":   0,
        "hp_dice": (1, 1, 0),
        "hitroll": 0, "AC": 1,
        "damage":  (1, 1, 0),  # dam_type: 'digestion'
        "gold":    0,
        "loot":    [],  # TODO: from RESETS E/G
        "act_flags": {"stay_area": True, "noalign": True},
    },
    M_BEAST: {
        "name":    'Beast',
        "desc":    'A beast tries to feed off of you.',
        "level":   5,
        "hp_dice": (5, 5, 55),
        "hitroll": 1, "AC": 0,
        "damage":  (1, 6, 3),  # dam_type: 'bite'
        "gold":    50,
        "loot":    [],  # TODO: from RESETS E/G
        "act_flags": {"aggressive": True, "warrior": True, "noalign": True},
        "aff_flags": {"dark_vision": True},
        "off_flags": {"disarm": True, "parry": True, "tail": True},
        "imm_flags": {"summon": True, "charm": True},
        "res_flags": {"fire": True, "cold": True},
        "vuln_flags": {"magic": True},
    },
    M_BEAR: {
        "name":    'Bear',
        "desc":    'A bear is here growling at you.',
        "level":   4,
        "hp_dice": (4, 4, 44),
        "hitroll": 1, "AC": 0,
        "damage":  (1, 6, 2),  # dam_type: 'claw'
        "gold":    0,
        "loot":    [],  # TODO: from RESETS E/G
        "act_flags": {"stay_area": True, "noalign": True},
        "off_flags": {"bash": True, "berserk": True, "disarm": True, "crush": True, "assist_race": True},
        "res_flags": {"bash": True, "cold": True},
    },
    M_WOLF: {
        "name":    'Wolf',
        "desc":    'A wolf is here snarling at you.',
        "level":   4,
        "hp_dice": (4, 4, 44),
        "hitroll": 0, "AC": 0,
        "damage":  (1, 6, 2),  # dam_type: 'bite'
        "gold":    0,
        "loot":    [],  # TODO: from RESETS E/G
        "act_flags": {"stay_area": True, "noalign": True},
        "aff_flags": {"dark_vision": True},
        "off_flags": {"dodge": True, "fast": True, "trip": True, "assist_race": True},
    },
    M_ADEPT_OF_SELENE: {
        "name":    'Adept Of Selene',
        "desc":    'An adept of Selene is here, grinning and selling you things.',
        "level":   30,
        "hp_dice": (1, 1, 999),
        "hitroll": 10, "AC": -2,
        "damage":  (2, 4, 30),  # dam_type: 'beating'
        "gold":    0,
        "loot":    [],  # TODO: from RESETS E/G
        "act_flags": {"sentinel": True, "scavenger": True, "cleric": True, "warrior": True, "nopurge": True},
        "aff_flags": {"detect_evil": True, "sanctuary": True},
        "off_flags": {"area_attack": True, "bash": True, "disarm": True, "dodge": True, "fast": True, "kick": True, "parry": True, "trip": True},
        "imm_flags": {"summon": True, "charm": True, "magic": True, "weapon": True},
    },
    M_ADEPT_OF_FUREY: {
        "name":    'Adept Of Furey',
        "desc":    'An adept of Furey is here, training young students.',
        "level":   30,
        "hp_dice": (1, 1, 999),
        "hitroll": 10, "AC": -2,
        "damage":  (2, 4, 30),  # dam_type: 'beating'
        "gold":    0,
        "loot":    [],  # TODO: from RESETS E/G
        "act_flags": {"sentinel": True, "scavenger": True, "train": True, "cleric": True, "warrior": True, "nopurge": True},
        "aff_flags": {"detect_evil": True, "sanctuary": True},
        "off_flags": {"area_attack": True, "bash": True, "disarm": True, "dodge": True, "fast": True, "kick": True, "parry": True, "trip": True},
        "imm_flags": {"summon": True, "charm": True, "magic": True, "weapon": True},
    },
    M_PRIEST_OF_CIRCE: {
        "name":    'Priest Of Circe',
        "desc":    'The priest of Circe is ready to help you practice.',
        "level":   30,
        "hp_dice": (1, 1, 999),
        "hitroll": 10, "AC": -2,
        "damage":  (2, 4, 30),  # dam_type: 'beating'
        "gold":    0,
        "loot":    [],  # TODO: from RESETS E/G
        "act_flags": {"sentinel": True, "scavenger": True, "practice": True, "cleric": True, "warrior": True, "nopurge": True},
        "aff_flags": {"detect_evil": True, "sanctuary": True},
        "off_flags": {"area_attack": True, "bash": True, "disarm": True, "dodge": True, "fast": True, "kick": True, "parry": True, "trip": True},
        "imm_flags": {"summon": True, "charm": True, "magic": True, "weapon": True},
    },
    M_DIPLOMA_BEAST: {
        "name":    'Diploma Beast',
        "desc":    'The hideous diploma beast is here, holding your graduation present!',
        "level":   3,
        "hp_dice": (2, 4, 30),
        "hitroll": 1, "AC": 0,
        "damage":  (1, 6, 1),  # dam_type: 'claw'
        "gold":    30,
        "loot":    [],  # TODO: from RESETS E/G
        "act_flags": {"sentinel": True, "noalign": True},
        "aff_flags": {"infrared": True},
        "off_flags": {"disarm": True, "dodge": True, "trip": True},
        "imm_flags": {"summon": True, "charm": True},
        "vuln_flags": {"magic": True},
    },
}

# ── Item templates -------------------------------------------------------------
OBJECTS = {
    I_SUB_ISSUE_MACE: {
        "name": 'Sub Issue Mace',
        "desc": 'You see a mace of great but cheap craftsmanship.  Imprinted on the side is: Merc Industries',
        "type": 'weapon', "slot": 'weapon',
        "weight": 60, "value": 250,
        "dice": (1, 6, 0), "weapon_type": 'mace',
        "hitroll": 1, "damroll": 0,
        "extra_flags": {"melt_drop": True},
    },
    I_SUB_ISSUE_DAGGER: {
        "name": 'Sub Issue Dagger',
        "desc": 'You see a dagger of great but cheap craftsmanship.  Imprinted on the side is: Merc Industries',
        "type": 'weapon', "slot": 'weapon',
        "weight": 10, "value": 210,
        "dice": (1, 4, 0), "weapon_type": 'dagger',
        "hitroll": 1, "damroll": 0,
        "extra_flags": {"melt_drop": True},
    },
    I_SUB_ISSUE_SWORD: {
        "name": 'Sub Issue Sword',
        "desc": 'You see a sword of great but cheap craftsmanship.  Imprinted on the side is: Merc Industries',
        "type": 'weapon', "slot": 'weapon',
        "weight": 30, "value": 360,
        "dice": (1, 6, 0), "weapon_type": 'sword',
        "hitroll": 1, "damroll": 0,
        "extra_flags": {"melt_drop": True},
    },
    I_SUB_ISSUE_VEST: {
        "name": 'Sub Issue Vest',
        "desc": 'You see a vest of great but cheap craftsmanship.  Stamped on the side is: Merc Industries',
        "type": 'armor', "slot": 'body',
        "weight": 50, "value": 144,
        "AC": 0,
        "extra_flags": {"melt_drop": True},
    },
    I_SUB_ISSUE_SHIELD: {
        "name": 'Sub Issue Shield',
        "desc": 'You see a shield of great but cheap craftsmanship.  Imprinted on the side is: Merc Industries',
        "type": 'armor', "slot": 'shield',
        "weight": 30, "value": 108,
        "AC": 0,
        "extra_flags": {"melt_drop": True},
    },
    I_SUB_ISSUE_CLOAK: {
        "name": 'Sub Issue Cloak',
        "desc": 'You see a cloak of great but cheap craftsmanship.  Imprinted on the side is: Merc Industries',
        "type": 'armor', "slot": 'neck',
        "weight": 40, "value": 72,
        "AC": 0,
        "extra_flags": {"melt_drop": True},
    },
    I_SUB_ISSUE_HELMET: {
        "name": 'Sub Issue Helmet',
        "desc": 'You see a helmet of great but cheap craftsmanship.  Imprinted on the side is: Merc Industries',
        "type": 'armor', "slot": 'head',
        "weight": 30, "value": 72,
        "AC": 0,
        "extra_flags": {"melt_drop": True},
    },
    I_PAIR_OF_SUB_ISSUE_LEGGINGS: {
        "name": 'Pair Of Sub Issue Leggings',
        "desc": 'You see leggings of great but cheap craftsmanship.  Imprinted on the side is: Merc Industries',
        "type": 'armor', "slot": 'legs',
        "weight": 30, "value": 72,
        "AC": 0,
        "extra_flags": {"melt_drop": True},
    },
    I_PAIR_OF_SUB_ISSUE_BOOTS: {
        "name": 'Pair Of Sub Issue Boots',
        "desc": 'You see boots of great but cheap craftsmanship.  Imprinted on the side is: Merc Industries',
        "type": 'armor', "slot": 'feet',
        "weight": 30, "value": 72,
        "AC": 0,
        "extra_flags": {"melt_drop": True},
    },
    I_PAIR_OF_SUB_ISSUE_GLOVES: {
        "name": 'Pair Of Sub Issue Gloves',
        "desc": 'You see gloves of great but cheap craftsmanship.  Imprinted on the side is: Merc Industries',
        "type": 'armor', "slot": 'hands',
        "weight": 10, "value": 72,
        "AC": 0,
        "extra_flags": {"melt_drop": True},
    },
    I_PAIR_OF_SUB_ISSUE_SLEEVES: {
        "name": 'Pair Of Sub Issue Sleeves',
        "desc": 'You see sleeves of great but cheap craftsmanship.  Imprinted on the side is: Merc Industries',
        "type": 'armor', "slot": 'arms',
        "weight": 20, "value": 72,
        "AC": 0,
        "extra_flags": {"melt_drop": True},
    },
    I_SUB_ISSUE_CAPE: {
        "name": 'Sub Issue Cape',
        "desc": 'You see a cape of great but cheap craftsmanship.  Imprinted on the side is: Merc Industries',
        "type": 'armor', "slot": 'about',
        "weight": 20, "value": 72,
        "AC": 0,
        "extra_flags": {"melt_drop": True},
    },
    I_SUB_ISSUE_BELT: {
        "name": 'Sub Issue Belt',
        "desc": 'You see a belt of great but cheap craftsmanship.  Imprinted on the side is: Merc Industries',
        "type": 'armor', "slot": 'waist',
        "weight": 10, "value": 72,
        "AC": 0,
        "extra_flags": {"melt_drop": True},
    },
    I_SUB_ISSUE_BRACER: {
        "name": 'Sub Issue Bracer',
        "desc": 'You see a bracer of great but cheap craftsmanship.  Imprinted on the side is: Merc Industries',
        "type": 'armor', "slot": 'wrist',
        "weight": 10, "value": 48,
        "AC": 0,
        "extra_flags": {"melt_drop": True},
    },
    I_KEY: {
        "name": 'Key',
        "desc": 'You see a very important key here!',
        "type": 'key', "slot": None,
        "weight": 10, "value": 0,
        "extra_flags": {"_unknown_bits": [15]},
    },
    I_MUD_SCHOOL_DIPLOMA: {
        "name": 'Mud School Diploma',
        "desc": 'This document shows that you have graduated from Mud School. It also has magical effects on your abilities if you hold it!  Merc Industries',
        "type": 'treasure', "slot": 'hold',
        "weight": 10, "value": 1140,
        "extra_flags": {"magic": True, "melt_drop": True},
    },
    I_WAR_BANNER: {
        "name": 'War Banner',
        "desc": 'This is the official Merc war banner to see you through the darkest realm!',
        "type": 'light', "slot": None,
        "weight": 20, "value": 380,
        "extra_flags": {"glow": True, "magic": True},
    },
    I_SUB_ISSUE_SPEAR: {
        "name": 'Sub Issue Spear',
        "desc": 'You see a spear of great but cheap craftsmanship.  Imprinted on the side is: Merc Industries',
        "type": 'weapon', "slot": 'weapon',
        "weight": 50, "value": 111,
        "dice": (1, 6, 0), "weapon_type": 'staff',
        "hitroll": 1, "damroll": 0,
        "extra_flags": {"melt_drop": True},
    },
    I_SUB_ISSUE_STAFF: {
        "name": 'Sub Issue Staff',
        "desc": 'You see a staff of great but cheap craftsmanship.  Imprinted on the side is: Merc Industries',
        "type": 'weapon', "slot": 'weapon',
        "weight": 40, "value": 290,
        "dice": (1, 5, 0), "weapon_type": 'staff',
        "hitroll": 2, "damroll": 1,
        "extra_flags": {"melt_drop": True},
    },
    I_SUB_ISSUE_AXE: {
        "name": 'Sub Issue Axe',
        "desc": 'You see an axe of great but cheap craftsmanship.  Imprinted on the side is: Merc Industries',
        "type": 'weapon', "slot": 'weapon',
        "weight": 50, "value": 350,
        "dice": (1, 6, 0), "weapon_type": 'axe',
        "hitroll": 1, "damroll": 0,
        "extra_flags": {"melt_drop": True},
    },
    I_SUB_ISSUE_FLAIL: {
        "name": 'Sub Issue Flail',
        "desc": 'You see a flail of great but cheap craftsmanship.  Imprinted on the side is: Merc Industries',
        "type": 'weapon', "slot": 'weapon',
        "weight": 50, "value": 310,
        "dice": (1, 5, 0), "weapon_type": 'flail',
        "hitroll": 0, "damroll": 1,
        "extra_flags": {"melt_drop": True},
    },
    I_SUB_ISSUE_WHIP: {
        "name": 'Sub Issue Whip',
        "desc": 'You see a whip of great but cheap craftsmanship.  Imprinted on the side is: Merc Industries',
        "type": 'weapon', "slot": 'weapon',
        "weight": 20, "value": 330,
        "dice": (2, 2, 0), "weapon_type": 'whip',
        "hitroll": 2, "damroll": 0,
        "extra_flags": {"melt_drop": True},
    },
    I_SUB_ISSUE_GLAIVE: {
        "name": 'Sub Issue Glaive',
        "desc": 'You see a glaive of great but cheap craftsmanship.  Imprinted on the side is: Merc Industries',
        "type": 'weapon', "slot": 'weapon',
        "weight": 80, "value": 183,
        "dice": (1, 7, 0), "weapon_type": 'polearm',
        "hitroll": 0, "damroll": 1,
        "extra_flags": {"melt_drop": True},
    },
}

# ── Resets ---------------------------------------------------------------------
# ("M", mob_template_vnum, room_vnum)  — spawn one mob instance
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
    ("M", M_ACOLYTE_OF_ZUMP, R_ROOM_IN_MUD_SCHOOL),
    ("M", M_BLOB, R_BLOB_CAGE),
    ("M", M_ADEPT_OF_SATIN, R_CAGE_ROOM),
    ("M", M_AGGRESSIVE_MONSTER, R_CAGE),
    # TODO: E 0 3707 0 7
    # TODO: E 0 3712 0 13
    ("M", M_WIMPY_AGGRESSIVE_MONSTER, R_CAGE_3714),
    # TODO: E 0 3708 0 8
    # TODO: E 0 3713 0 14
    ("M", M_WIMPY_MONSTER, R_CAGE_3715),
    # TODO: E 0 3706 0 6
    # TODO: E 0 3711 0 12
    ("M", M_MONSTER, R_CAGE_3716),
    # TODO: E 0 3705 0 3
    # TODO: E 0 3705 0 4
    ("M", M_ADEPT_OF_SELENE, R_STORE_IN_MUD_SCHOOL),
    # TODO: G 0 3138 0
    # TODO: G 0 3031 0
    ("M", M_BIG_CREATURE, R_DARKENED_ROOM),
    # TODO: E 0 3709 0 9
    # TODO: E 0 3710 0 10
    # TODO: E 0 3714 0 17
    # TODO: E 0 3713 0 14
    ("M", M_DIPLOMA_BEAST, R_END_OF_MUD_SCHOOL),
    # TODO: E 0 3715 0 17
    ("M", M_ADEPT_OF_ALANDER, R_END_OF_MUD_SCHOOL),
    ("M", M_SNAIL, R_SOUTH_WEST_CORNER_OF_ARENA),
    ("M", M_FOX, R_SOUTH_EAST_CORNER_OF_ARENA),
    ("M", M_RABBIT, R_CENTER_OF_ARENA),
    ("M", M_LIZARD, R_NORTH_WEST_CORNER_OF_ARENA),
    ("M", M_BOAR, R_NORTH_EAST_CORNER_OF_ARENA),
    ("M", M_BEAST, R_NORTH_WEST_CORNER_OF_THE_DUNGEON),
    ("M", M_BEAR, R_NORTH_EAST_CORNER_OF_THE_DUNGEON),
    ("M", M_WOLF, R_SOUTH_WEST_CORNER_OF_THE_DUNGEON),
    ("M", M_ADEPT_OF_FUREY, R_FUREY_S_TRAINING_ROOM),
    ("M", M_PRIEST_OF_CIRCE, R_ZUMP_S_GUILD_ROOM),
)
