# ── Display ───────────────────────────────────────────────────────────────────
DARK_MODE = True
BG_COLOR  = 0x3000
TAB_SIZE  = 8

# ── Timing ────────────────────────────────────────────────────────────────────
WORLD_TICK_MS  = 5000
COMBAT_TICK_MS = 1000
POLL_MS        = 10    # main loop sleep interval; raise if hourglass appears
AUTOSAVE_TICKS   = 12  # autosave every N world ticks (= 60s at default WORLD_TICK_MS)
DEATH_MSG_DELAY  = 1   # seconds between death flavour lines

# ── Regeneration ──────────────────────────────────────────────────────────────
HP_REGEN_PER_CON = 5   # HP gained per tick = con // this
MP_REGEN_PER_INT = 5   # MP gained per tick = int // this

# ── Persistence ───────────────────────────────────────────────────────────────
SAVE_FILE = "primesud.sav"
