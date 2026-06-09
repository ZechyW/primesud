# fmt: off
# Cross-area VNUM constants — referenced by game logic, not just area data.
# When adding a new area, add any VNUMs that other modules need to hardcode here.
# Area files define their own local constants for internal use; only the ones
# that cross module boundaries belong here.

# ── Rooms ─────────────────────────────────────────────────────────────────────
R_VILLAGE_SQUARE = 1000   # player respawn point after death

# ── Skills (cf. 1stMud gsn_* in index.h) ─────────────────────────────────────
GSN_KICK         = 4001
GSN_CURE_LIGHT   = 4002
GSN_HAND_TO_HAND = 4010
GSN_PARRY        = 4020
