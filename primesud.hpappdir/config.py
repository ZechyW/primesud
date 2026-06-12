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
PULSE_AREA       = 120 * PULSE_PER_SECOND     # 480 pulses — area reset (2 min)
POLL_MS          = 10                          # keyboard polling interval (ms)
AUTOSAVE_TICKS   = 4                           # autosave every N world ticks (4 × 30 s)
DEATH_MSG_DELAY  = 1                           # seconds between death flavour lines

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
    "5": "look",
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
