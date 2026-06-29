"""In-game world time system (cf. 1stMud time_info in weather.c / update.c)."""

# -- Constants (cf. 1stMud defines.h) ------------------------------------------
HOURS_IN_DAY = 24
DAYS_IN_MONTH = 30
MONTHS_IN_YEAR = 17

SUN_DARK = 0
SUN_RISE = 1
SUN_LIGHT = 2
SUN_SET = 3

# -- Global time state (cf. 1stMud time_info struct) ---------------------------
time_info = {
    "hour": 8,
    "day": 0,
    "month": 0,
    "year": 0,
    "sunlight": SUN_LIGHT,
}


def time_update():
    """Advance game clock by one hour (cf. 1stMud time_update in weather.c).

    Called once per PULSE_TICK from update_handler.
    """
    time_info["hour"] += 1

    if time_info["hour"] == 5:
        time_info["sunlight"] = SUN_RISE
    elif time_info["hour"] == 6:
        time_info["sunlight"] = SUN_LIGHT
    elif time_info["hour"] == 18:
        time_info["sunlight"] = SUN_SET
    elif time_info["hour"] == 20:
        time_info["sunlight"] = SUN_DARK

    if time_info["hour"] >= HOURS_IN_DAY:
        time_info["hour"] = 0
        time_info["day"] += 1

    if time_info["day"] >= DAYS_IN_MONTH:
        time_info["day"] = 0
        time_info["month"] += 1

    if time_info["month"] >= MONTHS_IN_YEAR:
        time_info["month"] = 0
        time_info["year"] += 1
