# fmt: off
"""Game configuration constants, key maps, and stat tables."""

VERSION = "1.0.0"  # [PRIMESUD] shown by do_version; upstream has no PrimeSUD-side equivalent

# -- Display ---------------------------------------------------------------------------
DARK_MODE     = True
FONT          = "scientifica5x10"
BG_COLOR      = 0
# or BG_COLOR 0x3000 for use with green font
TAB_SIZE      = 8
TERMINAL_COLS = 64   # character columns (5x10 font, 320 px wide)
TERMINAL_ROWS = 22   # character rows    (5x10 font, 240 px high, excl. status bar)
                     # All 22 are usable by one command's output -- no row is
                     # reserved for the cursor. See docs/PRIME_UX.md sec.
                     # Full-screen output budget before sizing a layout.
FONT_GROB     = 9    # grob tml blits font glyphs from (HP Prime default)
COLOR_GROB    = 8    # unmodified font copy; restored into FONT_GROB on colour reset
SCRATCH_GROB  = 5    # offscreen compose buffer for batched renders (6=save, 7=history)
COLORFONT_GROB = 4   # [PRIMESUD] per-colour font cache bands (one FONT_GROB-sized band per colour seen)

# -- Timing -- pulse system (1stMud convention) -----------------------------------------
PULSE_PER_SECOND = 4                          # base pulse rate
MS_PER_PULSE     = 1000 // PULSE_PER_SECOND   # 250 ms per pulse
PULSE_VIOLENCE   = 2  * PULSE_PER_SECOND      # combat round
PULSE_MOBILE     = 5  * PULSE_PER_SECOND      # mob wander
PULSE_MUSIC      = 6  * PULSE_PER_SECOND      # jukebox lyric line (cf. 1stMud PULSE_MUSIC)
PULSE_REGEN      = 5  * PULSE_PER_SECOND      # [PRIMESUD] smooth player hp/mana/move
PULSE_TICK       = 30 * PULSE_PER_SECOND      # world tick
REGEN_SECS       = PULSE_REGEN // PULSE_PER_SECOND
TICK_SECS        = PULSE_TICK // PULSE_PER_SECOND  # seconds elapsed per world tick
# PULSE_AREA     = 120 * PULSE_PER_SECOND     # area reset
PULSE_AREA       = 30 * PULSE_PER_SECOND      # Quicker age ticks for better UX
POLL_MS          = 10                         # keyboard polling interval (ms)
# [PRIMESUD] Max loaded areas before world.maybe_evict unloads far ones.
# The keep-set (current area + neighbours + pinned limbo + follower/combat
# areas) is immune, so the effective floor is ~12 around the Midgaard hub;
# lower this for smaller-heap devices only alongside a smaller world.
AREA_CACHE_MAX   = 12
# Build-only switch: tools/build_dist.py --area-bench overrides this in the
# transfer copy. Source/game builds stay on the normal startup path.
AREA_LOAD_BENCH  = False
AUTOSAVE_TICKS   = 4                          # autosave every N world ticks
DEATH_MSG_DELAY  = 3                          # seconds between death flavour lines
REVEAL_MS_PER_LINE = 25                       # [PRIMESUD] streaming output reveal, per text row; 0 disables
REVEAL_MS_PER_CHAR = 0                        # [PRIMESUD] additional left-to-right char streaming within each revealed row; 0 disables


# Quest/gquest durations are configured and balanced in real-world minutes
# (matching 1stMud, whose tick is 60s); timers store world ticks internally
# and convert at assignment/display via these helpers. [PRIMESUD]

def mins_to_ticks(m):
    """Real minutes -> world ticks, at least 1. [PRIMESUD]"""
    return max(1, m * 60 // TICK_SECS)


def ticks_to_mins(t):
    """World ticks -> whole real minutes for display (ceil). [PRIMESUD]"""
    if t <= 0:
        return 0
    return (t * TICK_SECS + 59) // 60


def on_minute(t):
    """True when a tick count sits on a whole-minute boundary. [PRIMESUD]"""
    return (t * TICK_SECS) % 60 == 0


# -- Global quests [PRIMESUD] ---------------------------------------------------------
# Real-world minutes (see mins_to_ticks above).
GQUEST_INITIAL_DELAY = 30     # first auto gquest of a new game
GQUEST_AUTO_DELAY_MIN = 30    # random delay between auto gquests
GQUEST_AUTO_DELAY_MAX = 60

# -- Automap ---------------------------------------------------------------------------
MAP_HALF_W      = 5   # compact automap half-width  (full grid = 2*W+1 = 11 cols)
MAP_HALF_H      = 6   # compact automap half-height (full grid = 2*H+1 = 13 rows)
FULL_MAP_HALF_W = 9   # 'map' command half-width    (full grid = 2*W+1 = 11 cols)
FULL_MAP_HALF_H = 8   # 'map' command half-height   (full grid = 2*H+1 = 15 rows, 17 total w/ borders)
COMPACT_MAP_DEPTH = 2  # exit-tracing hops for compact map (cf. 1stMud fSmall: depth starts at 2)
FULL_MAP_DEPTH    = 4  # exit-tracing hops for full map   (cf. 1stMud !fSmall: depth starts at 0)

# Sector display (cf. 1stMud sector_color_table in automap.c; jungle has no entry -> "")
# game code uses room.get("sector", "inside") so hand-authored rooms default to "inside"
SECTOR_COLORS = {
    "inside":   "{w",  "city":     "{W",  "field":    "{G",  "forest": "{g",
    "hills":    "{y",  "mountain": "{w",  "water_swim": "{B",  "water_noswim": "{b",
    "ice":      "{C",  "air":      "{C",  "desert":   "{y",  "road":   "{m",
    "path":     "{M",  "swamp":    "{G",  "jungle":   "",    "cave":   "{w",
    "none":     "{w",
}
SECTOR_SYMBOLS = {
    "inside":   'o',   "city":     'o',   "field":    '*',   "forest": '*',
    "hills":    '!',   "mountain": '@',   "water_swim": '=',   "water_noswim": '=',
    "ice":      'O',   "air":      '~',   "desert":   '+',   "road":   ':',
    "path":     ':',   "swamp":    '&',   "jungle":   '?',   "cave":   '#',
    "none":     '?',
}

# -- Scrollback [PRIMESUD] -------------------------------------------------------------
SCROLLBACK_SIZE = 250  # rows to keep in history (0 = disabled)
SCROLL_STEP     = 7   # rows scrolled per Shift+- / Shift++ keypress

# -- Touch input [PRIMESUD] ------------------------------------------------------------
SWIPE_THRESHOLD   = 20  # min Y-pixel delta on lift to enter scrollback
TOUCH_SCROLL_STEP = 3   # rows scrolled per char_height of drag inside scrollback
FLING_FRAME_MS    = 16  # fling integration cadence inside touch scrollback
FLING_MIN_VELOCITY = 120  # min fling speed in px/sec after lift
FLING_DECAY_NUM   = 7   # fling velocity decay numerator per frame
FLING_DECAY_DEN   = 8   # fling velocity decay denominator per frame
FLING_SMOOTH_NUM  = 3   # velocity EMA: old-sample weight (new-sample weight = 1)

# -- Command history [PRIMESUD] --------------------------------------------------------
CMD_HISTORY_MAX = 50  # maximum number of submitted commands to remember

# -- Persistence -----------------------------------------------------------------------
SAVE_VAR = "primesud_save"

# -- Directions -----------------------------------------------------------------------
_DIRS       = (("n","north","s"), ("e","east","w"), ("s","south","n"),
               ("w","west","e"),  ("u","up","d"),   ("d","down","u"))
EXIT_ORDER  = tuple(d[0] for d in _DIRS)
EXIT_NAMES  = {d[0]: d[1] for d in _DIRS}
REV_DIR     = {d[0]: d[2] for d in _DIRS}
DIR_ALIASES = {k: d[0] for d in _DIRS for k in (d[0], d[1])}

# -- Key command shortcuts [PRIMESUD] --------------------------------------------------
# Maps HP Prime physical key bit-index -> (command, auto_submit).
# auto_submit=True: execute immediately; False: load into input buffer.
# Adjust indices here if they differ on a specific hardware revision.
KEY_COMMANDS = {  # [PRIMESUD]
    2:  ("n",  True),   # Nav-pad Up
    6:  ("u",  True),   # Plot
    7:  ("w",  True),   # Nav-pad Left
    8:  ("e",  True),   # Nav-pad Right
    9:  ("d",  True),   # View
    12: ("s",  True),   # Nav-pad Down
}

# -- Default digit/decimal macros [PRIMESUD] -------------------------------------------
# Maps digit keys "0"-"9" and "." -> command strings. Edit to taste.
DEFAULT_MACROS = {  # [PRIMESUD]
    "7": "kill",
    "8": "flee",
    "9": "cast",
    "4": "buy",
    "5": "sell",
    "6": "get",
    "1": "score",
    "2": "practice",
    "3": "drop",
    "0": "macro",
    ".": "help"
}

# -- Function-row macro keys [PRIMESUD] ---------------------------------------
# Sentinels must match _FN_* in tml_prime.py. One row per key: sentinel ->
# (display_name, default_command); None leaves a configurable key unbound.
# display_name is used as the save-file key (save_char/load_char in player.py); must not contain '~' (line
# separator) or '=' (key/value separator) or save parsing will break.
FNKEY_TABLE = {
    14: ('sin', 'look'),      # sin key -- index 21
    15: ('cos', 'rest'),      # cos key -- index 22
    16: ('tan', 'stand'),     # tan key -- index 23
    17: ('ln',  'quest'),     # ln  key -- index 24; bare quest = contextual hub
    18: ('log', 'gquest'),    # log key -- index 25; bare gquest = contextual hub
    19: ('x2',  'inventory'), # x2  key -- index 26
    20: ('pm',  'equip'),     # +/- key -- index 27
    21: ('()',  'wear'),      # ()  key -- index 28
    22: (',',   'remove'),    # ,   key -- index 29
    23: ('xy',  'run'),       # x^y key -- index 20
    24: ('eex', 'consider'),  # EEX key -- index 31
    25: ('vars', 'path'),     # Vars      key -- index 14
    26: ('tool', 'examine'),  # Toolbox   key -- index 15
    27: ('tmpl', 'where'),    # Templates key -- index 16
    28: ('math', 'train'),    # Math sym  key -- index 17
    29: ('abc', 'recommend'), # a b/c     key -- index 18
}
FNKEY_SENTINELS      = frozenset(FNKEY_TABLE)
FNKEY_NAMES          = {k: v[0] for k, v in FNKEY_TABLE.items()}
DEFAULT_FNKEY_MACROS = {k: v[1] for k, v in FNKEY_TABLE.items() if v[1] is not None}

# -- Sector types (cf. 1stMud sector_t enum in defines.h) -----------------------------
SECT_INSIDE       = 'inside'
SECT_CITY         = 'city'
SECT_FIELD        = 'field'
SECT_FOREST       = 'forest'
SECT_HILLS        = 'hills'
SECT_MOUNTAIN     = 'mountain'
SECT_WATER_SWIM   = 'water_swim'
SECT_WATER_NOSWIM = 'water_noswim'
SECT_ICE          = 'ice'
SECT_AIR          = 'air'
SECT_DESERT       = 'desert'
SECT_ROAD         = 'road'
SECT_PATH         = 'path'
SECT_SWAMP        = 'swamp'
SECT_JUNGLE       = 'jungle'

# movement_loss[sector] -- movement point cost per sector (cf. 1stMud const.c)
MOVEMENT_LOSS = {
    'inside': 1, 'city': 2, 'field': 2, 'forest': 3, 'hills': 4,
    'mountain': 6, 'water_swim': 4, 'water_noswim': 1, 'ice': 6,
    'air': 10, 'desert': 6, 'road': 1, 'path': 1, 'swamp': 6, 'jungle': 4,
}

# -- Cross-area room VNUMs (cf. 1stMud room vnums in index.h) -------------------------
R_STARTING_ROOM  = 3700   # player respawn/starting room (Mud School entrance)
R_RECALL         = 3001   # default recall destination (cf. 1stMud ROOM_VNUM_TEMPLE)

# -- Stat cap (cf. 1stMud #define MAX_STATS 30 in defines.h) ------------------------------
MAX_STATS = 30

# -- Stat application tables (1stMud ROM values, index by stat 0-MAX_STATS) ---------------
# str_app: tohit (hitroll bonus, positive = better to-hit), todam (damage roll bonus),
#          carry (max carry weight in lbs; cf. 1stMud str_app[].carry in const.c),
#          wield (max weapon weight for wielding, in lbs; cf. 1stMud str_app[].wield in const.c)
STR_APP_TOHIT    = (-5,-5,-3,-3,-2,-2,-1,-1, 0, 0, 0, 0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8)
STR_APP_TODAM    = (-4,-4,-2,-1,-1,-1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 2, 3, 3, 4, 5, 6, 6, 7, 8, 9,10,11,12,13,14)
STR_APP_CARRY    = (  0, 3, 3,10,25,55,80,90,100,100,115,115,130,130,140,150,165,180,200,225,250,300,350,400,450,500,550,600,650,700,750)
STR_APP_WIELD    = ( 0, 1, 2, 3, 4, 5, 6, 7, 8, 9,10,11,12,13,14,15,16,22,25,30,35,40,45,50,55,60,65,70,75,80,85)
# dex_app: defensive AC modifier added to ch->armor[] before /10 division in combat (negative = better)
DEX_APP_DEF      = (60,50,50,40,30,20,10, 0, 0, 0, 0, 0, 0, 0, 0,-10,-15,-20,-30,-40,-50,-60,-75,-90,-105,-120,-130,-140,-155,-175,-190)
# con_app: bonus HP gained per level-up; shock = resurrection survival % (cf. 1stMud con_app[].shock)
CON_APP_HITP     = (-4,-3,-2,-2,-1,-1,-1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 2, 3, 3, 4, 4, 5, 6, 7, 8, 9,10,11,12,13)
CON_APP_SHOCK    = (20,25,30,35,40,45,50,55,60,65,70,75,80,85,88,90,95,97,99,99,99,99,99,99,99,99,100,102,104,107,110)
# wis_app: bonus practices gained per level-up (1stMud wis_app[].practice)
WIS_APP_PRACTICE = (0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,2,2,2,3,3,3,3,4,4,4,5,5,5,6,6,6)
# int_app: skill improvement rate used in check_improve and do_practice (1stMud int_app[].learn)
INT_APP_LEARN    = (3,5,7,8,9,10,11,12,13,15,17,19,22,25,28,31,34,37,40,44,49,55,60,70,80,85,90,95,100,105,110)

# -- Level caps ------------------------------------------------------------------------
# 1stMud 4.5.3 defines MAX_LEVEL=60, LEVEL_IMMORTAL=52,
# MAX_MORTAL_LEVEL=51, MAX_REMORT=2, and LEVEL_HERO=49.
# calc_max_level() caps mortals at HERO plus remort count: 49-51.
MAX_LEVEL = 60  # Levels 52-60 would be immortal levels in 1stmud
MAX_MORTAL_LEVEL = 51  # 1stMud do_skills/do_spells display/filter cap.
LEVEL_IMMORTAL = 52  # skill_level() sentinel for skills no held class learns.
LEVEL_HERO = 49  # calc_max_level base: mortals cap at HERO + remort count.

# Class-count cap (cf. 1stMud MAX_REMORT in defines.h). Stock = 2 (1 remort).
# [PRIMESUD] At len(classes) == MAX_REMORT, do_remort in training.py offers a
# prestige tier reset (finish_tier_reset) instead of 1stMud's refusal. classes.py's
# calc_max_level() combines this with LEVEL_HERO/MAX_MORTAL_LEVEL above, so a
# different remort count needs ALL of the following changed together:
#  - MAX_REMORT here (how many classes/remorts are allowed)
#  - MAX_MORTAL_LEVEL above (hard ceiling; currently 51 == LEVEL_HERO + 2 remorts)
#  - CLASS_TABLE["names"] tuples in classes.py need one entry per remort tier
#    (currently 2: base + 1 remort); short of that, extra remorts silently
#    reuse the last tier's name instead of erroring.
#  - MAX_LEVEL above if the extra levels should also apply elsewhere (gquest
#    level bounds, debug setlevel, corpse-gold split, info.py display clamps).
MAX_REMORT = 2

# [PRIMESUD] Remort power divisor. Stock 1stMud finish_remort grants
# 100*lvl_bonus hp/mana/move, 5*lvl_bonus trains, 7*lvl_bonus practices --
# ~6000 hp / 300 trains / 420 practices at first remort, absurd against
# PrimeSUD's flatter economy (fresh char: 50 hp / 3 trains / 5 practices).
# All three grants are divided by this; 12 lands ~500 hp / 25 / 35.
# Set to 1 for stock 1stMud behaviour.
REMORT_POWER_DIV = 12

# -- Practice cap ----------------------------------------------------------------------
SKILL_ADEPT = 75  # 1stMud class_table[].skill_adept; all shipped classes use 75
# [PRIMESUD] Effective practice ceiling is skill_adept_cap() in classes.py:
# SKILL_ADEPT + 5 per prestige tier, max 95.

# -- Stat training cap -----------------------------------------------------------------
# race.max_stats[stat] + 2 (or +3 for human prime stats), capped at MAX_STATS;
# see get_max_train() in handler.py.

# -- Position order (cf. 1stMud position_t enum in defines.h) -------------------------
POS_ORDER = {
    "dead": 0, "mortal": 1, "incap": 2, "stunned": 3,
    "sleeping": 4, "resting": 5, "sitting": 6, "fighting": 7, "standing": 8,
}

# start_pos/default_pos short forms in area data -> position keys
# (cf. 1stMud position_table in tables.c)
POS_FROM_SHORT = {"stand": "standing", "sit": "sitting",
                  "rest": "resting", "sleep": "sleeping"}

# -- damage() dt threshold (cf. 1stMud TYPE_HIT / TYPE_UNDEFINED in defines.h) ----------
# dt >= TYPE_HIT = physical weapon attack (dodge/parry apply); dt < TYPE_HIT = skill/spell.
TYPE_HIT       = 1000
TYPE_UNDEFINED = -1

# -- Sex (cf. 1stMud sex_t enum in defines.h: SEX_NEUTRAL=0, SEX_MALE=1, SEX_FEMALE=2) -
SEX_VALUES = ("neutral", "male", "female")

# -- Armor class buckets (cf. 1stMud AC_* in merc.h) -----------------------------------
AC_PIERCE = 0
AC_BASH   = 1
AC_SLASH  = 2
AC_EXOTIC = 3

# -- Damage classes (cf. 1stMud dam_class enum in merc.h) ------------------------------
# Three related tables, three jobs:
#   DAM_*        -- the damage class itself: what KIND of harm is dealt. Passed
#                   through damage() / saves_spell() / check_immune().
#   DAM_TO_FLAG  -- damage class -> imm/res/vuln flag name on a character, used
#                   by check_immune. Classes with no entry (DAM_OTHER, DAM_HARM)
#                   only get the broad-category check: bash/pierce/slash count
#                   as "weapon", everything else as "magic".
#   ATTACK_TABLE -- area-file attack key -> (display noun, damage class): how a
#                   mob/weapon attack reads in combat messages and which damage
#                   class it deals (cf. attack_table in const.c).
DAM_NONE      = -1   # "none" / TYPE_HIT bare attack -- falls back to DAM_BASH
DAM_BASH      =  0
DAM_PIERCE    =  1
DAM_SLASH     =  2
DAM_FIRE      =  3
DAM_COLD      =  4
DAM_LIGHTNING =  5
DAM_ACID      =  6
DAM_POISON    =  7
DAM_NEGATIVE  =  8
DAM_HOLY      =  9
DAM_ENERGY    = 10
DAM_MENTAL    = 11
DAM_DISEASE   = 12
DAM_DROWNING  = 13
DAM_LIGHT     = 14
DAM_SOUND     = 15
DAM_OTHER     = 16
DAM_HARM      = 17
DAM_CHARM     = 18

# -- Damage-class to immunity flag mapping (cf. 1stMud check_immune in handler.c) ------
DAM_TO_FLAG = {
    DAM_BASH:      "bash",
    DAM_PIERCE:    "pierce",
    DAM_SLASH:     "slash",
    DAM_FIRE:      "fire",
    DAM_COLD:      "cold",
    DAM_LIGHTNING: "lightning",
    DAM_ACID:      "acid",
    DAM_POISON:    "poison",
    DAM_NEGATIVE:  "negative",
    DAM_HOLY:      "holy",
    DAM_ENERGY:    "energy",
    DAM_MENTAL:    "mental",
    DAM_DISEASE:   "disease",
    DAM_DROWNING:  "drowning",
    DAM_LIGHT:     "light",
    DAM_CHARM:     "charm",
    DAM_SOUND:     "sound",
}

# -- Attack table (cf. 1stMud attack_table in const.c) ---------------------------------
# Maps dam_type area-file key -> (display noun, dam_class).
# Noun differs from key for: divine, peckb, shbite, flbite, frbite, acbite, drain.
# dam_class used for AC-type selection (pierce/slash/bash/exotic) and future res/imm.
ATTACK_TABLE = {
    "none":      ("hit",           DAM_NONE),
    "slice":     ("slice",         DAM_SLASH),
    "stab":      ("stab",          DAM_PIERCE),
    "slash":     ("slash",         DAM_SLASH),
    "whip":      ("whip",          DAM_SLASH),
    "claw":      ("claw",          DAM_SLASH),
    "blast":     ("blast",         DAM_BASH),
    "pound":     ("pound",         DAM_BASH),
    "crush":     ("crush",         DAM_BASH),
    "grep":      ("grep",          DAM_SLASH),
    "bite":      ("bite",          DAM_PIERCE),
    "pierce":    ("pierce",        DAM_PIERCE),
    "suction":   ("suction",       DAM_BASH),
    "beating":   ("beating",       DAM_BASH),
    "digestion": ("digestion",     DAM_ACID),
    "charge":    ("charge",        DAM_BASH),
    "slap":      ("slap",          DAM_BASH),
    "punch":     ("punch",         DAM_BASH),
    "wrath":     ("wrath",         DAM_ENERGY),
    "magic":     ("magic",         DAM_ENERGY),
    "divine":    ("divine power",  DAM_HOLY),
    "cleave":    ("cleave",        DAM_SLASH),
    "scratch":   ("scratch",       DAM_PIERCE),
    "peck":      ("peck",          DAM_PIERCE),
    "peckb":     ("peck",          DAM_BASH),
    "chop":      ("chop",          DAM_SLASH),
    "sting":     ("sting",         DAM_PIERCE),
    "smash":     ("smash",         DAM_BASH),
    "shbite":    ("shocking bite", DAM_LIGHTNING),
    "flbite":    ("flaming bite",  DAM_FIRE),
    "frbite":    ("freezing bite", DAM_COLD),
    "acbite":    ("acidic bite",   DAM_ACID),
    "chomp":     ("chomp",         DAM_PIERCE),
    "drain":     ("life drain",    DAM_NEGATIVE),
    "thrust":    ("thrust",        DAM_PIERCE),
    "slime":     ("slime",         DAM_ACID),
    "shock":     ("shock",         DAM_LIGHTNING),
    "thwack":    ("thwack",        DAM_BASH),
    "flame":     ("flame",         DAM_FIRE),
    "chill":     ("chill",         DAM_COLD),
    "code":      ("code",          DAM_OTHER),
    "radiation": ("radiation",     DAM_POISON),
}

# -- Immunity constants (cf. 1stMud check_immune in handler.c) -------------------------
IS_NORMAL     = 0
IS_IMMUNE     = 1
IS_RESISTANT  = 2
IS_VULNERABLE = 3
IMMUNE_NONE   = -1

# -- XP base table by level difference (cf. 1stMud xp_compute in fight.c) -------------
XP_BASE = {
    -9: 1, -8: 2, -7: 5, -6: 9, -5: 11, -4: 22, -3: 33, -2: 50,
    -1: 66, 0: 83, 1: 99, 2: 121, 3: 143, 4: 165,
}

# -- Size rank (cf. 1stMud SIZE_* in merc.h) -------------------------------------------
SIZE_RANK = {"tiny": 0, "small": 1, "medium": 2, "large": 3, "huge": 4, "giant": 5}

# -- Wear-slot display labels (cf. 1stMud wear_loc_names in act_info.c) ----------------
WEAR_LABELS = (
    ("light",     "{g<{Wused as light{g>{x     "),
    ("finger_l",  "{g<{Wworn on finger{g>{x    "),
    ("finger_r",  "{g<{Wworn on finger{g>{x    "),
    ("neck_1",    "{g<{Wworn around neck{g>{x  "),
    ("neck_2",    "{g<{Wworn around neck{g>{x  "),
    ("body",      "{g<{Wworn on torso{g>{x     "),
    ("head",      "{g<{Wworn on head{g>{x      "),
    ("legs",      "{g<{Wworn on legs{g>{x      "),
    ("feet",      "{g<{Wworn on feet{g>{x      "),
    ("hands",     "{g<{Wworn on hands{g>{x     "),
    ("arms",      "{g<{Wworn on arms{g>{x      "),
    ("shield",    "{g<{Wworn as shield{g>{x    "),
    ("about",     "{g<{Wworn about body{g>{x   "),
    ("waist",     "{g<{Wworn about waist{g>{x  "),
    ("wrist_l",   "{g<{Wworn around wrist{g>{x "),
    ("wrist_r",   "{g<{Wworn around wrist{g>{x "),
    ("wield",     "{g<{Wwielded{g>{x           "),
    ("hold",      "{g<{Wheld{g>{x              "),
    ("float",     "{g<{Wfloating nearby{g>{x   "),
    ("secondary", "{g<{Wsecondary weapon{g>{x  "),
)
