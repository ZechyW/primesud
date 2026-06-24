"""Command dispatcher, command table, and position gates."""

from combat import (do_kill, do_kick, do_backstab, do_murder, do_suicide,
                    do_berserk, do_bash, do_dirt, do_trip, do_flee,
                    do_rescue, do_disarm, do_surrender, do_slay,
                    do_sskill, do_stance, do_autostance)
from inventory import (do_get, do_drop, do_inventory, do_wear, do_remove,
                       do_equipment, do_second, do_quaff, do_recite,
                       do_brandish, do_zap, do_eat, do_outfit, do_put,
                       do_sacrifice)
from movement import do_move, do_open, do_close, do_recall
from magic import do_cast
from scan import do_scan
from training import do_train, do_practice
from info import (do_look, do_score, do_skills, do_spells, do_help, do_affects,
                  do_credits, do_map, do_automap, do_autolist)
from macros import do_macro
from system_cmds import do_save, do_quit, do_debug
from config import POS_ORDER

_POS_MSG = {
    "dead":     "Lie still; you are DEAD.",
    "mortal":   "You are hurt far too bad for that.",
    "incap":    "You are hurt far too bad for that.",
    "stunned":  "You are too stunned to do that.",
    "sleeping": "In your dreams, or what?",
    "resting":  "Nah... You feel too relaxed...",
    "sitting":  "Better stand up first.",
    "fighting": "No way!  You are still fighting!",
}

# -- Direction map -------------------------------------------------------------

_DIRECTION_MAP = {
    "n": "n", "north":     "n",
    "s": "s", "south":     "s",
    "e": "e", "east":      "e",
    "w": "w", "west":      "w",

    "u": "u", "up":   "u",
    "d": "d", "down": "d",
}

# -- Command table -------------------------------------------------------------
# Entries in 1stMud load order (cf. COMMANDS.md); [PRIMESUD] shortcuts interleaved.
# Schema: (name, fn, min_pos, noprefix)

_CMD_TABLE = [
    ("cast",      do_cast,      "fighting", False),   # #8
    ("get",       do_get,       "resting",  False),   # #13
    ("inventory", do_inventory, "dead",     False),   # #18
    ("kill",      do_kill,      "fighting", False),   # #19
    ("look",      do_look,      "resting",  False),   # #20
    ("practice",  do_practice,  "sleeping", False),   # #24
    ("wield",     do_wear,      "resting",  False),   # #31
    ("affects",   do_affects,   "dead",     False),   # #33
    ("credits",   do_credits,   "dead",     False),   # #41
    ("equipment", do_equipment, "dead",     False),   # #42
    ("help",      do_help,      "dead",     False),   # #44
    ("score",     do_score,     "dead",     False),   # #49
    ("skills",    do_skills,    "dead",     False),   # #50
    ("spells",    do_spells,    "dead",     False),   # #53
    ("autolist",  do_autolist,  "dead",     False),   # #63
    ("outfit",    do_outfit,    "resting",  False),   # #80
    ("brandish",  do_brandish,  "fighting", False),   # #112
    ("close",     do_close,     "resting",  False),   # #113
    ("drop",      do_drop,      "resting",  False),   # #115
    ("eat",       do_eat,       "resting",  False),   # #116
    ("open",      do_open,      "resting",  False),   # #124
    ("put",       do_put,       "resting",  False),   # #127
    ("second",    do_second,    "resting",  False),   # #128
    ("quaff",     do_quaff,     "resting",  False),   # #129
    ("recite",    do_recite,    "resting",  False),   # #130
    ("remove",    do_remove,    "resting",  False),   # #131
    ("take",      do_get,       "resting",  False),   # #133
    ("sacrifice", do_sacrifice, "resting",  False),   # #134
    ("junk",      do_sacrifice, "resting",  False),   # #135
    ("tap",       do_sacrifice, "resting",  False),   # #136
    ("wear",      do_wear,      "resting",  False),   # #138
    ("zap",       do_zap,       "fighting", False),   # #139
    ("backstab",  do_backstab,  "fighting", False),   # #141
    ("bash",      do_bash,      "fighting", False),   # #142
    ("bs",        do_backstab,  "fighting", False),   # #143
    ("berserk",   do_berserk,   "fighting", False),   # #144
    ("dirt",      do_dirt,      "fighting", False),   # #145
    ("disarm",    do_disarm,    "fighting", False),   # #146
    ("flee",      do_flee,      "fighting", False),   # #147
    ("kick",      do_kick,      "fighting", False),   # #148
    ("murder",    do_murder,    "fighting", True),     # #149 noprefix
    ("rescue",    do_rescue,    "fighting", False),   # #150
    ("surrender", do_surrender, "fighting", False),   # #151
    ("trip",      do_trip,      "fighting", False),   # #152
    ("automap",   do_automap,   "sleeping", False),   # #154
    ("quit",      do_quit,      "dead",     True),    # #162 noprefix
    ("recall",    do_recall,    "fighting", False),   # #163
    ("/",         do_recall,    "fighting", False),   # #164
    ("save",      do_save,      "dead",     False),   # #166
    ("train",     do_train,     "resting",  False),   # #171
    ("slay",      do_slay,      "dead",     True),     # #209 noprefix (imm cmd)
    ("scan",      do_scan,      "resting",  False),   # #253
    ("map",       do_map,       "resting",  False),   # #291
    ("sskill",    do_sskill,    "sleeping", False),   # #304
    ("stance",    do_stance,    "standing", False),   # #305
    ("autostance", do_autostance, "sleeping", False), # #306
    ("suicide",   do_suicide,   "resting",  True),     # #344 noprefix
    ("macro",     do_macro,     "dead",     False),   # [PRIMESUD] #349
    ("debug",     do_debug,     "dead",     False),   # [PRIMESUD] #350
]


# -- Interpreter ---------------------------------------------------------------

def _split_args(raw):
    """Split command input like 1stMud one_argument quoting."""
    args = []
    i = 0
    raw = raw.strip().lower()
    length = len(raw)
    while i < length:
        while i < length and raw[i].isspace():
            i += 1
        if i >= length:
            break
        end = " "
        if raw[i] == "'" or raw[i] == '"':
            end = raw[i]
            i += 1
        start = i
        if end == " ":
            while i < length and not raw[i].isspace():
                i += 1
        else:
            while i < length and raw[i] != end:
                i += 1
        args.append(raw[start:i])
        if i < length and raw[i] == end:
            i += 1
    return args


def interpret(raw, tr, player):
    parts = _split_args(raw)
    if not parts:
        return None
    tr.print("")
    verb = parts[0]
    args = parts[1:]

    direction = _DIRECTION_MAP.get(verb)
    if direction is not None:
        do_move(tr, player, direction)
        return None

    pos = player.get("pos", "standing")
    for name, fn, min_pos, noprefix in _CMD_TABLE:
        if noprefix:
            if verb != name:
                continue
        elif not name.startswith(verb):
            continue
        if POS_ORDER[pos] < POS_ORDER[min_pos]:
            tr.print(_POS_MSG.get(pos, ""))
            return None
        return fn(tr, player, args)

    tr.print("Unknown command. ? for help.")
    return None
