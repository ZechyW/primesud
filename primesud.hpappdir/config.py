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

# ── Persistence ───────────────────────────────────────────────────────────────
SAVE_FILE = "primesud.sav"
