# ── Display ───────────────────────────────────────────────────────────────────
DARK_MODE = True
BG_COLOR  = 0x3000
TAB_SIZE  = 8

# ── Timing — pulse system (1stMud convention) ─────────────────────────────────
PULSE_PER_SECOND = 4                          # base pulse rate
MS_PER_PULSE     = 1000 // PULSE_PER_SECOND   # 250 ms per pulse
PULSE_VIOLENCE   = 3  * PULSE_PER_SECOND      # 12  pulses — combat round (3 s)
PULSE_TICK       = 30 * PULSE_PER_SECOND      # 120 pulses — world tick (30 s)
PULSE_AREA       = 120 * PULSE_PER_SECOND     # 480 pulses — area reset (2 min)
POLL_MS          = 10                          # keyboard polling interval (ms)
AUTOSAVE_TICKS   = 2                           # autosave every N world ticks (2 × 30 s = 60 s)
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
    3:  "help",  # Help key
    2:  "n",     # Up    → north
    7:  "w",     # Left  → west
    8:  "e",     # Right → east
    12: "s",     # Down  → south
    14: "macro", # Menu key
}
NAV_KEYS = {"n", "s", "e", "w"}  # [PRIMESUD] subset of KEY_COMMANDS that auto-submit
