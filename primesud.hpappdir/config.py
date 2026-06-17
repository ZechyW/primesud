# fmt: off
# -- Display ---------------------------------------------------------------------------
DARK_MODE     = True
FONT          = "std5x10"
BG_COLOR      = 0
# or BG_COLOR 0x3000 for use with green font
TAB_SIZE      = 8
TERMINAL_COLS = 64   # character columns (std5x10 font, 320 px wide)
TERMINAL_ROWS = 22   # character rows    (std5x10 font, 240 px high, excl. status bar)
FONT_GROB     = 9    # grob tml blits font glyphs from (HP Prime default)
COLOR_GROB    = 8    # unmodified font copy; restored into FONT_GROB on colour reset

# -- Timing -- pulse system (1stMud convention) -----------------------------------------
PULSE_PER_SECOND = 4                          # base pulse rate
MS_PER_PULSE     = 1000 // PULSE_PER_SECOND   # 250 ms per pulse
PULSE_VIOLENCE   = 2  * PULSE_PER_SECOND      # combat round
PULSE_MOBILE     = 5  * PULSE_PER_SECOND      # mob wander
PULSE_TICK       = 30 * PULSE_PER_SECOND      # world tick
TICK_SECS        = PULSE_TICK // PULSE_PER_SECOND  # seconds elapsed per world tick
# PULSE_AREA     = 120 * PULSE_PER_SECOND     # area reset
PULSE_AREA       = 15 * PULSE_PER_SECOND      # Quicker age ticks for better UX
POLL_MS          = 10                         # keyboard polling interval (ms)
AUTOSAVE_TICKS   = 4                          # autosave every N world ticks
DEATH_MSG_DELAY  = 1                          # seconds between death flavour lines

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
    "hills":    "{y",  "mountain": "{w",  "swim":     "{B",  "noswim": "{b",
    "ice":      "{C",  "air":      "{C",  "desert":   "{y",  "road":   "{m",
    "path":     "{M",  "swamp":    "{G",  "jungle":   "",    "cave":   "{w",
    "none":     "{w",
}
SECTOR_SYMBOLS = {
    "inside":   'o',   "city":     'o',   "field":    '*',   "forest": '*',
    "hills":    '!',   "mountain": '@',   "swim":     '=',   "noswim": '=',
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

# -- Default digit macros [PRIMESUD] ---------------------------------------------------
# Maps digit key "0"-"9" -> command string. Edit to taste.
DEFAULT_MACROS = {  # [PRIMESUD]
    "7": "kill",
    "8": "flee",
    "4": "open",
    "5": "get",
    "6": "drop",
    "1": "score",
    "2": "practice",
    "3": "train",
    "0": "macro"
}

# -- Function-row macro keys [PRIMESUD] ---------------------------------------
# Sentinels must match _FN_* in tml_prime.py. One row per key: sentinel -> (display_name, default_command).
# display_name is used as the save-file key (save_char/load_char in player.py); must not contain '~' (line
# separator) or '=' (key/value separator) or save parsing will break.
FNKEY_TABLE = {
    '\x12': ('x2', 'inventory'),      # x2 key -- index 26
    '\x13': ('pm', 'equip'),  # +/- key -- index 27
    '\x14': ('()', 'wear'),       # ()  key -- index 28
    '\x15': (',',  'remove'),     # ,   key -- index 29
}
FNKEY_SENTINELS      = frozenset(FNKEY_TABLE)
FNKEY_NAMES          = {k: v[0] for k, v in FNKEY_TABLE.items()}
DEFAULT_FNKEY_MACROS = {k: v[1] for k, v in FNKEY_TABLE.items()}

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

# -- Classless HP die (Cleric/Paladin range) -------------------------------------------
CLASS_HP_MIN = 7
CLASS_HP_MAX = 10

# -- Level cap -------------------------------------------------------------------------
MAX_LEVEL = 50  # [PRIMESUD] 1stMud caps at 32

# -- Stat training cap -----------------------------------------------------------------
# Revisit when races are added: 1stMud uses race.max_stats[stat] + 2 (or +3 for human
# prime stats) via get_max_train() in handler.c; flat MAX_STATS until then.

# -- THAC0 constants (classless, balanced midpoint) ------------------------------------
THAC0_PLATEAU = 32   # level at which natural THAC0 stops improving
THAC0_00      = 20   # THAC0 at level 1              (higher = worse to-hit)
THAC0_MIN     = -2   # THAC0 at level THAC0_PLATEAU  (lower  = better to-hit)

# -- Damage classes (cf. 1stMud dam_class enum in merc.h) ------------------------------
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
DAM_OTHER     = 11

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
