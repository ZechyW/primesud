# ── Display ───────────────────────────────────────────────────────────────────
DARK_MODE     = True
BG_COLOR      = 0x3000
TAB_SIZE      = 8
TERMINAL_COLS = 64   # character columns (std5x10green font, 320 px wide)
TERMINAL_ROWS = 24   # character rows    (std5x10green font, 240 px high, excl. status bar)

# ── Timing — pulse system (1stMud convention) ─────────────────────────────────
PULSE_PER_SECOND = 4                          # base pulse rate
MS_PER_PULSE     = 1000 // PULSE_PER_SECOND   # 250 ms per pulse
PULSE_VIOLENCE   = 3  * PULSE_PER_SECOND      # 12  pulses — combat round (3 s)
PULSE_TICK       = 30 * PULSE_PER_SECOND      # 120 pulses — world tick (30 s)
PULSE_AREA       = 120 * PULSE_PER_SECOND     # 480 pulses — area reset (2 min)
POLL_MS          = 10                          # keyboard polling interval (ms)
AUTOSAVE_TICKS   = 4                           # autosave every N world ticks (4 × 30 s = 120 s)
DEATH_MSG_DELAY  = 1                           # seconds between death flavour lines

# ── Regeneration (scaled for 30 s world tick) ─────────────────────────────────
# HP per tick = con * HP_REGEN_NUM // HP_REGEN_DENOM  → con=10 gives 12 HP/30 s
HP_REGEN_NUM   = 6
HP_REGEN_DENOM = 5
MP_REGEN_NUM   = 6
MP_REGEN_DENOM = 5

# ── Automap ───────────────────────────────────────────────────────────────────
MAP_HALF_W   = 6   # grid half-width  in room-steps (full grid = 2*W+1 = 13 cols)
MAP_HALF_H   = 6   # grid half-height in room-steps (full grid = 2*H+1 =  9 rows)
MAP_MAX_DEPTH = 3  # recursion depth for exit tracing

# ── Persistence ───────────────────────────────────────────────────────────────
SAVE_FILE = "primesud.sav"

# ── Key command shortcuts [PRIMESUD] ──────────────────────────────────────────
# Maps HP Prime physical key bit-index → command string.
# Nav keys auto-submit immediately in the game loop; others populate the buffer.
# Adjust indices here if they differ on a specific hardware revision.
KEY_COMMANDS = {  # [PRIMESUD]
    1:  "nw",  # ↖ NW
    2:  "n",   # ↑ N    (d-pad Up)
    3:  "ne",  # ↗ NE
    6:  "u",   # up
    7:  "w",   # ← W    (d-pad Left)
    8:  "e",   # → E    (d-pad Right)
    9:  "d",   # down
    11: "sw",  # ↙ SW
    12: "s",   # ↓ S    (d-pad Down)
    13: "se",  # ↘ SE
}
NAV_KEYS = {"n", "s", "e", "w", "ne", "nw", "se", "sw", "u", "d"}  # [PRIMESUD] all KEY_COMMANDS directions auto-submit

# ── Default digit macros [PRIMESUD] ───────────────────────────────────────────
# Maps digit key "0"-"9" → command string. Edit to taste.
DEFAULT_MACROS = {  # [PRIMESUD]
    "7": "kill",
    "5": "look",
    "1": "score",
    "0": "macro"
}
