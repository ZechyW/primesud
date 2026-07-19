"""In-game world time system (cf. 1stMud time_info in weather.c / update.c)."""

from urandom import randint

# -- Constants (cf. 1stMud defines.h) ------------------------------------------
HOURS_IN_DAY = 24
DAYS_IN_MONTH = 30
MONTHS_IN_YEAR = 17
DAYS_IN_WEEK = 7

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


def time_update(tr, player):
    """Advance game clock by one hour and echo time-of-day changes
    (cf. 1stMud time_update in weather.c:648-681).

    Called once per PULSE_TICK from update_handler.

    Args:
        tr: Terminal for the time-of-day echo.
        player (dict): Player state dict.
    """
    time_info["hour"] += 1
    hour = time_info["hour"]

    if hour == 5:
        time_info["sunlight"] = SUN_RISE
    elif hour == 6:
        time_info["sunlight"] = SUN_LIGHT
    elif hour == 19:
        time_info["sunlight"] = SUN_SET
    elif hour == 20:
        time_info["sunlight"] = SUN_DARK

    # cf. 1stMud time_update switch(++hour): echo cases are 5, 6, 12, 19, 20
    if hour in (5, 6, 12, 19, 20):
        _echo_time_of_day(tr, player, hour)

    if time_info["hour"] >= HOURS_IN_DAY:
        time_info["hour"] = 0
        time_info["day"] += 1

    if time_info["day"] >= DAYS_IN_MONTH:
        time_info["day"] = 0
        time_info["month"] += 1

    if time_info["month"] >= MONTHS_IN_YEAR:
        time_info["month"] = 0
        time_info["year"] += 1


# -- Time-of-day echoes (cf. 1stMud get_time_echo in weather.c:413-516) --------
_DAY_BEGUN_MSGS = [
    "The day has begun.",
    "The day has begun.",
    "The sky slowly begins to glow.",
    "The sun slowly embarks upon a new day.",
]

_SUNRISE_MSGS = [
    "The sun rises in the east.",
    "The sun rises in the east.",
    "The hazy sun rises over the horizon.",
    "Day breaks as the sun lifts into the sky.",
]

_NOON_MSGS = [
    "The intensity of the sun heralds the noon hour.",
    "The sun's bright rays beat down upon your shoulders.",
]

_SUNSET_MSGS = [
    "The sun slowly disappears in the west.",
    "The reddish sun sets past the horizon.",
    "The sky turns a reddish orange as the sun ends its journey.",
    "The sun's radiance dims as it sinks in the sky.",
]

_NIGHT_CLOUDY_MSGS = [
    "The night begins.",
    "Twilight descends around you.",
]

_NIGHT_CLEAR_MSGS = [
    "The moon's gentle glow diffuses through the night sky.",
    "The night sky gleams with glittering starlight.",
]


def _echo_time_of_day(tr, player, hour):
    """Print a time-of-day echo to the player (cf. 1stMud get_time_echo in
    weather.c:413-516, called from time_update's hour switch). [PRIMESUD]

    1stMud sends the echo to every awake, outdoor descriptor; PrimeSUD is
    single-player, so this only ever addresses ``player``, and only when
    outdoors and awake (cf. mob.py weather_update's ``outdoor_awake`` check,
    reused here in the same shape).

    Args:
        tr: Terminal for the echo.
        player (dict): Player state dict.
        hour (int): The just-advanced hour -- one of 5, 6, 12, 19, 20.
    """
    from handler import is_awake
    import world
    from world import ROOM_DEFS

    proom = ROOM_DEFS[player["room"]] if player["room"] in ROOM_DEFS._data else None
    if (proom is None or proom.get("flags", {}).get("indoors")
            or not is_awake(player)):
        return

    ptag = proom.get("area")
    w = None
    for area in world.areas:
        if area.get("tag") == ptag:
            w = area.get("weather")
            break
    if w is None:
        return

    pindex = _weather_index(w.get("precip", 0))
    n = randint(0, 3)  # cf. 1stMud number_bits(2)

    if hour == 5:
        msg, color = _DAY_BEGUN_MSGS[n], "{Y"
    elif hour == 6:
        msg, color = _SUNRISE_MSGS[n], "{y"
    elif hour == 12:
        if pindex > 0:
            msg, color = "It's noon.", "{W"
        else:
            msg, color = _NOON_MSGS[n % 2], "{W"
    elif hour == 19:
        msg, color = _SUNSET_MSGS[n], "{R"
    else:  # hour == 20
        if pindex > 0:
            msg, color = _NIGHT_CLOUDY_MSGS[n % 2], "{b"
        else:
            msg, color = _NIGHT_CLEAR_MSGS[n % 2], "{b"

    tr.print(color + msg + "{x")


# -- Calendar names (cf. 1stMud day_name / month_name in const.c) --------------
day_name = [
    "the Moon", "the Bull", "Deception", "Thunder", "Freedom",
    "the Great Gods", "the Sun",
]

month_name = [
    "Winter", "the Winter Wolf", "the Frost Giant", "the Old Forces",
    "the Grand Struggle", "the Spring", "Nature", "Futility", "the Dragon",
    "the Sun", "the Heat", "the Battle", "the Dark Shades", "the Shadows",
    "the Long Shadows", "the Ancient Darkness", "the Great Evil",
]


def ordinal_string(n):
    """Return the ordinal form of n, e.g. 1 -> 'first', 21 -> '21st' (cf. 1stMud ordinal_string in handler.c:2893).

    Matches 1stMud verbatim, including its lack of an 11th/12th/13th special
    case (11 -> '11st'); days run 1..30 so this only shows on 11/12/13.
    """
    if n == 1 or n == 0:
        return "first"
    if n == 2:
        return "second"
    if n == 3:
        return "third"
    if n % 10 == 1:
        return str(n) + "st"
    if n % 10 == 2:
        return str(n) + "nd"
    if n % 10 == 3:
        return str(n) + "rd"
    return str(n) + "th"


# -- Weather (cf. 1stMud weather.c; mud_info defaults in data_table.c) ----------
# [PRIMESUD] Full per-area temp/precip/wind vector model, ported from weather.c.
# Every loaded area file carries "Climate 2 2 2", so PrimeSUD bakes a neutral
# climate for all areas instead of reading climate data from area files. With
# climate 2 the (climate-2)*unit climate-pull term is zero, which collapses
# adjust_vectors to integer arithmetic -- no floats on-device.
WEATH_UNIT = 10       # mud_info.weath_unit
RAND_FACTOR = 2       # mud_info.rand_factor
MAX_VECTOR = 30       # mud_info.max_vector (weath_unit * 3), vector clamp
WEATH_LIMIT = 30      # 3 * weath_unit, clamp on temp/precip/wind values


def _trunc_div(a, b):
    """Integer division truncating toward zero, matching C '/' semantics. [PRIMESUD]"""
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


def _weather_index(val):
    """Map a weather variable (-30..30) to a 0..5 severity index (cf. 1stMud (val + 3*unit - 1)/unit)."""
    idx = _trunc_div(val + 3 * WEATH_UNIT - 1, WEATH_UNIT)
    if idx < 0:
        return 0
    if idx > 5:
        return 5
    return idx


def init_weather():
    """Seed a fresh area weather state (cf. 1stMud init_area_weather in weather.c, climate 2 2 2). [PRIMESUD]"""
    w = {}
    for k in ("temp", "precip", "wind"):
        w[k] = randint(-WEATH_UNIT, WEATH_UNIT)          # + climate*0
        w[k + "_vector"] = randint(-RAND_FACTOR, RAND_FACTOR)
    return w


def advance_weather(w):
    """Advance one area's weather by its vectors, clamped (cf. 1stMud weather_update body in weather.c). [PRIMESUD]"""
    for k in ("temp", "precip", "wind"):
        v = w.get(k, 0) + w.get(k + "_vector", 0)
        if v < -WEATH_LIMIT:
            v = -WEATH_LIMIT
        elif v > WEATH_LIMIT:
            v = WEATH_LIMIT
        w[k] = v


def adjust_vectors(w):
    """Drift an area's weather vectors toward its climate (cf. 1stMud adjust_vectors in weather.c). [PRIMESUD]

    Climate is a neutral 2, so the climate-pull term reduces to -val/unit
    (truncated toward zero) and all arithmetic stays integer.
    """
    for k in ("temp", "precip", "wind"):
        d = randint(-RAND_FACTOR, RAND_FACTOR) + _trunc_div(-w.get(k, 0), WEATH_UNIT)
        v = w.get(k + "_vector", 0) + d
        if v < -MAX_VECTOR:
            v = -MAX_VECTOR
        elif v > MAX_VECTOR:
            v = MAX_VECTOR
        w[k + "_vector"] = v


def get_weather_echo(w):
    """Return (message, color) for a weather change this tick, or ('', '') (cf. 1stMud get_weather_echo in weather.c). [PRIMESUD]"""
    n = randint(0, 3)
    temp = w.get("temp", 0)
    precip = w.get("precip", 0)
    dT = w.get("temp_vector", 0)
    dP = w.get("precip_vector", 0)
    tindex = _weather_index(temp)
    pindex = _weather_index(precip)
    U = WEATH_UNIT

    if pindex == 0:
        if precip - dP > -2 * U:
            return ["The clouds disappear.",
                    "The clouds disappear.",
                    "The sky begins to break through the clouds.",
                    "The clouds are slowly evaporating."][n], "{W"
    elif pindex == 1:
        if precip - dP <= -2 * U:
            return ["The sky is getting cloudy.",
                    "The sky is getting cloudy.",
                    "Light clouds cast a haze over the sky.",
                    "Billows of clouds spread through the sky."][n], "{D"
    elif pindex == 2:
        if precip - dP > 0:
            if tindex > 1:
                return ["The rain stops.",
                        "The rain stops.",
                        "The rainstorm tapers off.",
                        "The rain's intensity breaks."][n], "{C"
            return ["The snow stops.",
                    "The snow stops.",
                    "The snow showers taper off.",
                    "The snow flakes disappear from the sky."][n], "{W"
    elif pindex == 3:
        if precip - dP <= 0:
            if tindex > 1:
                return ["It starts to rain.",
                        "It starts to rain.",
                        "A droplet of rain falls upon you.",
                        "The rain begins to patter."][n], "{C"
            return ["It starts to snow.",
                    "It starts to snow.",
                    "Crystal flakes begin to fall from the sky.",
                    "Snow flakes drift down from the clouds."][n], "{W"
        elif tindex < 2 and temp - dT > -U:
            return ["The temperature drops and the rain becomes a light snow.",
                    "The temperature drops and the rain becomes a light snow.",
                    "Flurries form as the rain freezes.",
                    "Large snow flakes begin to fall with the rain."][n], "{W"
        elif tindex > 1 and temp - dT <= -U:
            return ["The snow flurries are gradually replaced by pockets of rain.",
                    "The snow flurries are gradually replaced by pockets of rain.",
                    "The falling snow turns to a cold drizzle.",
                    "The snow turns to rain as the air warms."][n], "{C"
    elif pindex == 4:
        if precip - dP > 2 * U:
            if tindex > 1:
                return ["The lightning has stopped.",
                        "The lightning has stopped.",
                        "The sky settles, and the thunder surrenders.",
                        "The lightning bursts fade as the storm weakens."][n], "{D"
        elif tindex < 2 and temp - dT > -U:
            return ["The cold rain turns to snow.",
                    "The cold rain turns to snow.",
                    "Snow flakes begin to fall amidst the rain.",
                    "The driving rain begins to freeze."][n], "{W"
        elif tindex > 1 and temp - dT <= -U:
            return ["The snow becomes a freezing rain.",
                    "The snow becomes a freezing rain.",
                    "A cold rain beats down on you as the snow begins to melt.",
                    "The snow is slowly replaced by a heavy rain."][n], "{C"
    elif pindex == 5:
        if precip - dP <= 2 * U:
            if tindex > 1:
                return ["Lightning flashes in the sky.",
                        "Lightning flashes in the sky.",
                        "A flash of lightning splits the sky.",
                        "The sky flashes, and the ground trembles with thunder."][n], "{Y"
        elif tindex > 1 and temp - dT <= -U:
            return ["The sky rumbles with thunder as the snow changes to rain.",
                    "The sky rumbles with thunder as the snow changes to rain.",
                    "The falling turns to freezing rain amidst flashes of lightning.",
                    "The falling snow begins to melt as thunder crashes overhead."][n], "{W"
        elif tindex < 2 and temp - dT > -U:
            return ["The lightning stops as the rainstorm becomes a blinding blizzard.",
                    "The lightning stops as the rainstorm becomes a blinding blizzard.",
                    "The thunder dies off as the pounding rain turns to heavy snow.",
                    "The cold rain turns to snow and the lightning stops."][n], "{C"
    return "", ""


# do_weather message tables (cf. 1stMud preciptemp_msg/windtemp_msg/precip_msg/
# wind_msg in const.c). Indexed [precip|wind][temp], 0..5.
# [PRIMESUD] 1stMud spelling slips fixed: "searing" -> "searing" (x3),
# "oppresive" -> "oppressive", "rythmically" -> "rhythmically",
# "ciculates" -> "circulates". Everything else is verbatim.
preciptemp_msg = [
    ["Frigid temperatures settle over the land",
     "It is bitterly cold",
     "The weather is crisp and dry",
     "A comfortable warmth sets in",
     "A dry heat warms the land",
     "Seething heat bakes the land"],
    ["A few flurries drift from the high clouds",
     "Frozen drops of rain fall from the sky",
     "An occasional raindrop falls to the ground",
     "Mild drops of rain seep from the clouds",
     "It is very warm, and the sky is overcast",
     "High humidity intensifies the searing heat"],
    ["A brief snow squall dusts the earth",
     "A light flurry dusts the ground",
     "Light snow drifts down from the heavens",
     "A light drizzle mars an otherwise perfect day",
     "A few drops of rain fall to the warm ground",
     "A light rain falls through the sweltering sky"],
    ["Snowfall covers the frigid earth",
     "Light snow falls to the ground",
     "A brief shower moistens the crisp air",
     "A pleasant rain falls from the heavens",
     "The warm air is heavy with rain",
     "A refreshing shower eases the oppressive heat"],
    ["Sleet falls in sheets through the frosty air",
     "Snow falls quickly, piling upon the cold earth",
     "Rain pelts the ground on this crisp day",
     "Rain drums the ground rhythmically",
     "A warm rain drums the ground loudly",
     "Tropical rain showers pelt the searing ground"],
    ["A downpour of frozen rain covers the land in ice",
     "A blizzard blankets everything in pristine white",
     "Torrents of rain fall from a cool sky",
     "A drenching downpour obscures the temperate day",
     "Warm rain pours from the sky",
     "A torrent of rain soaks the heated earth"],
]

windtemp_msg = [
    ["The frigid air is completely still",
     "A cold temperature hangs over the area",
     "The crisp air is eerily calm",
     "The warm air is still",
     "No wind makes the day uncomfortably warm",
     "The stagnant heat is sweltering"],
    ["A light breeze makes the frigid air seem colder",
     "A stirring of the air intensifies the cold",
     "A touch of wind makes the day cool",
     "It is a temperate day, with a slight breeze",
     "It is very warm, the air stirs slightly",
     "A faint breeze stirs the feverish air"],
    ["A breeze gives the frigid air bite",
     "A breeze swirls the cold air",
     "A lively breeze cools the area",
     "It is a temperate day, with a pleasant breeze",
     "Very warm breezes buffet the area",
     "A breeze circulates the sweltering air"],
    ["Stiff gusts add cold to the frigid air",
     "The cold air is agitated by gusts of wind",
     "Wind blows in from the north, cooling the area",
     "Gusty winds mix the temperate air",
     "Brief gusts of wind punctuate the warm day",
     "Wind attempts to cut the sweltering heat"],
    ["The frigid air whirls in gusts of wind",
     "A strong, cold wind blows in from the north",
     "Strong wind makes the cool air nip",
     "It is a pleasant day, with gusty winds",
     "Warm, gusty winds move through the area",
     "Blustering winds punctuate the searing heat"],
    ["A frigid gale sets bones shivering",
     "Howling gusts of wind cut the cold air",
     "An angry wind whips the air into a frenzy",
     "Fierce winds tear through the tepid air",
     "Gale-like winds whip up the warm air",
     "Monsoon winds tear the feverish air"],
]

precip_msg = [
    "there is not a cloud in the sky",
    "pristine white clouds are in the sky",
    "thick, grey clouds mask the sun",
]

wind_msg = [
    "there is not a breath of wind in the air",
    "a slight breeze stirs the air",
    "a breeze wafts through the area",
    "brief gusts of wind punctuate the air",
    "angry gusts of wind blow",
    "howling winds whip the air into a frenzy",
]


def weather_report_line(w):
    """Return the do_weather combo string for an area's weather (cf. 1stMud do_weather in act_info.c). [PRIMESUD]"""
    t = _weather_index(w.get("temp", 0))
    p = _weather_index(w.get("precip", 0))
    wi = _weather_index(w.get("wind", 0))
    if p >= 3:
        combo = preciptemp_msg[p][t]
        single = wind_msg[wi]
    else:
        combo = windtemp_msg[wi][t]
        single = precip_msg[p]
    return combo + " and " + single + "."
