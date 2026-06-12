# fmt: off
# ── Display ───────────────────────────────────────────────────────────────────────────
DARK_MODE     = True
FONT          = "std5x10"
BG_COLOR      = 0
# or BG_COLOR 0x3000 for use with green font
TAB_SIZE      = 8
TERMINAL_COLS = 64   # character columns (std5x10 font, 320 px wide)
TERMINAL_ROWS = 22   # character rows    (std5x10 font, 240 px high, excl. status bar)
FONT_GROB     = 9    # grob tml blits font glyphs from (HP Prime default)
COLOR_GROB    = 8    # unmodified font copy; restored into FONT_GROB on colour reset

# ── Timing — pulse system (1stMud convention) ─────────────────────────────────────────
PULSE_PER_SECOND = 4                          # base pulse rate
MS_PER_PULSE     = 1000 // PULSE_PER_SECOND   # 250 ms per pulse
PULSE_VIOLENCE   = 3  * PULSE_PER_SECOND      # 12  pulses — combat round (3 s)
PULSE_MOBILE     = 4  * PULSE_PER_SECOND      # 16  pulses — mob wander (4 s)
PULSE_TICK       = 30 * PULSE_PER_SECOND      # 120 pulses — world tick (30 s)
# PULSE_AREA     = 120 * PULSE_PER_SECOND     # 480 pulses — area reset (2 min)
PULSE_AREA       = 30 * PULSE_PER_SECOND      # Quicker (30s) age ticks for better UX
POLL_MS          = 10                         # keyboard polling interval (ms)
AUTOSAVE_TICKS   = 4                          # autosave every N world ticks (4 × 30 s)
DEATH_MSG_DELAY  = 1                          # seconds between death flavour lines

# ── Automap ───────────────────────────────────────────────────────────────────────────
MAP_HALF_W    = 5   # grid half-width  in room-steps (full grid = 2*W+1 = 13 cols)
MAP_HALF_H    = 6   # grid half-height in room-steps (full grid = 2*H+1 =  9 rows)
MAP_MAX_DEPTH = 2   # recursion depth for exit tracing

# ── Persistence ───────────────────────────────────────────────────────────────────────
SAVE_VAR = "primesud_save"

# ── Key command shortcuts [PRIMESUD] ──────────────────────────────────────────────────
# Maps HP Prime physical key bit-index → (command, auto_submit).
# auto_submit=True: execute immediately; False: load into input buffer.
# Adjust indices here if they differ on a specific hardware revision.
KEY_COMMANDS = {  # [PRIMESUD]
    2:  ("n",  True),   # ↑ N    (d-pad Up)
    6:  ("u",  True),   # up
    7:  ("w",  True),   # ← W    (d-pad Left)
    8:  ("e",  True),   # → E    (d-pad Right)
    9:  ("d",  True),   # down
    12: ("s",  True),   # ↓ S    (d-pad Down)
}

# ── Default digit macros [PRIMESUD] ───────────────────────────────────────────────────
# Maps digit key "0"-"9" → command string. Edit to taste.
DEFAULT_MACROS = {  # [PRIMESUD]
    "7": "kill",
    "8": "flee",
    "4": "look",
    "5": "open",
    "1": "score",
    "0": "macro"
}

# ── Stat application tables (ROM 2.4 values, index by stat 0–25) ──────────────────────
# str_app: tohit (THAC0 bonus, negative = better), todam (damage roll bonus)
STR_APP_TOHIT    = (-5,-5,-3,-3,-2,-2,-1,-1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 3, 3, 4, 4, 5, 6, 7)
STR_APP_TODAM    = (-4,-4,-2,-1,-1,-1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 4, 4, 5, 5, 6, 7, 8)
# dex_app: defensive AC modifier (negative = better)
DEX_APP_DEF      = (60,50,40,35,30,25,20,15,10, 5, 0, 0, 0, 0, 0,-1,-2,-3,-4,-5,-6,-7,-8,-9,-10,-11)
# con_app: bonus HP gained per level-up
CON_APP_HITP     = (-4,-3,-2,-2,-1,-1,-1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 2, 3, 3, 4, 4, 5, 6, 7, 8)
# wis_app: bonus practices gained per level-up (1stMud wis_app[].practice)
WIS_APP_PRACTICE = (0,0,0,0,0,1,1,1,1,1,1,1,1,1,1,2,2,2,3,3,3,3,4,4,4,5)

# ── Classless HP die (Cleric/Paladin range) ───────────────────────────────────────────
CLASS_HP_MIN = 7
CLASS_HP_MAX = 10

# ── Level cap ─────────────────────────────────────────────────────────────────────────
MAX_LEVEL = 50  # [PRIMESUD] 1stMud caps at 32

# ── THAC0 constants (classless, balanced midpoint) ────────────────────────────────────
THAC0_PLATEAU = 32   # level at which natural THAC0 stops improving
THAC0_00      = 20   # THAC0 at level 1              (higher = worse to-hit)
THAC0_MIN     = -2   # THAC0 at level THAC0_PLATEAU  (lower  = better to-hit)

# ── Damage classes (cf. 1stMud dam_class enum in merc.h) ──────────────────────────────
DAM_NONE      = -1   # "none" / TYPE_HIT bare attack — falls back to DAM_BASH
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

# ── Attack table (cf. 1stMud attack_table in const.c) ─────────────────────────────────
# Maps dam_type area-file key → (display noun, dam_class).
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
