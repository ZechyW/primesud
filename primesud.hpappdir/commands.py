"""Command dispatcher, command table, and position gates (cf. 1stMud interpret in interp.c)."""

from combat import (do_kill, do_kick, do_backstab, do_murder, do_suicide,
                    do_berserk, do_bash, do_dirt, do_trip, do_flee,
                    do_rescue, do_disarm, do_surrender, do_slay,
                    do_sskill, do_stance, do_autostance)
from config import POS_ORDER
from info import (do_look, do_examine, do_read, do_score, do_skills, do_spells,
                  do_help, do_affects, do_credits, do_map, do_automap,
                  do_autolist, do_autoloot, do_autogold, do_autosac,
                  do_autosplit)
from inventory import (do_get, do_drop, do_inventory, do_wear, do_remove,
                       do_equipment, do_second, do_quaff, do_recite,
                       do_brandish, do_zap, do_eat, do_outfit, do_put,
                       do_sacrifice)
from macros import do_macro
from magic import do_cast
from movement import (do_north, do_east, do_south, do_west, do_up, do_down,
                      do_open, do_close, do_recall)
from scan import do_scan
from system_cmds import do_save, do_quit, do_debug
from terminal import tprint
from training import do_train, do_practice
from urandom import randint

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

# -- Command table -------------------------------------------------------------
# Entries in 1stMud load order (cf. COMMANDS.md); [PRIMESUD] shortcuts interleaved.
# Schema: (name, fn, min_pos, noprefix)

_CMD_TABLE = [
    ("north",     do_north,     "standing", False),    # #1
    ("east",      do_east,      "standing", False),    # #2
    ("south",     do_south,     "standing", False),    # #3
    ("west",      do_west,      "standing", False),    # #4
    ("up",        do_up,        "standing", False),    # #5
    ("down",      do_down,      "standing", False),    # #6
    ("cast",      do_cast,      "fighting", False),   # #8
    ("get",       do_get,       "resting",  False),   # #13
    ("hit",       do_kill,      "fighting", False),   # #17
    ("inventory", do_inventory, "dead",     False),   # #18
    ("kill",      do_kill,      "fighting", False),   # #19
    ("look",      do_look,      "resting",  False),   # #20
    ("practice",  do_practice,  "sleeping", False),   # #24
    ("wield",     do_wear,      "resting",  False),   # #31
    ("affects",   do_affects,   "dead",     False),   # #33
    ("credits",   do_credits,   "dead",     False),   # #41
    ("equipment", do_equipment, "dead",     False),   # #42
    ("examine",   do_examine,   "resting",  False),   # #43
    ("help",      do_help,      "dead",     False),   # #44
    ("read",      do_read,      "resting",  False),   # #46
    ("score",     do_score,     "dead",     False),   # #49
    ("skills",    do_skills,    "dead",     False),   # #50
    ("spells",    do_spells,    "dead",     False),   # #53
    ("autolist",  do_autolist,  "dead",     False),   # #63
    ("autogold",  do_autogold,  "dead",     False),   # #66
    ("autoloot",  do_autoloot,  "dead",     False),   # #67
    ("autosac",   do_autosac,   "dead",     False),   # #68
    ("autosplit", do_autosplit, "dead",     False),   # #69
    ("outfit",    do_outfit,    "resting",  False),   # #80
    ("brandish",  do_brandish,  "resting",  False),   # #112
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
    ("zap",       do_zap,       "resting",  False),   # #139
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

# {? = random colour in 1stMud; we use {R as fallback until random colour ported
_HUH_MESSAGES = [
    "{RHuh?{x",
    "{RPardon?{x",
    "{RWhat is command '%s'?{x",
    "{RInput error.{x",
    "{RTry again.{x",
    "{RI do not understand.{x",
    "{RType commands for a list of commands.{x",
]


def one_argument(argument):
    """Extract one argument from *argument*, returning (word, rest) (cf. 1stMud one_argument in interp.c).

    Handles single/double-quote grouping.  Both the extracted word and the
    remainder are lowercased to match 1stMud's ``tolower`` inside
    ``one_argument``.
    """
    i = 0
    argument = argument.strip().lower()
    length = len(argument)
    while i < length and argument[i].isspace():
        i += 1
    if i >= length:
        return ("", "")
    end = " "
    if argument[i] == "'" or argument[i] == '"':
        end = argument[i]
        i += 1
    start = i
    if end == " ":
        while i < length and not argument[i].isspace():
            i += 1
    else:
        while i < length and argument[i] != end:
            i += 1
    word = argument[start:i]
    if i < length and argument[i] == end:
        i += 1
    rest = argument[i:].strip()
    return (word, rest)


def split_args(argument):
    """Split *argument* into a list via repeated one_argument calls (cf. 1stMud)."""
    args = []
    while argument:
        word, argument = one_argument(argument)
        if word:
            args.append(word)
    return args


def interpret(raw, player):
    """Main command interpreter (cf. 1stMud interpret in interp.c).

    Flow mirrors 1stMud: strip input, remove AFF_HIDE, extract command word
    (handling non-alpha first chars), look up command, check position, execute.
    """
    argument = raw.strip()
    if not argument:
        return None
    tprint("")

    # RemBit(ch->affected_by, AFF_HIDE)
    aff = player.get("affected_by")
    if aff:
        aff.pop("hide", None)

    # -- PLR_FREEZE: not applicable in single-player

    # Non-alpha/digit first char is a single-char command (e.g. '/')
    ch0 = argument[0]
    if not ch0.isalpha() and not ch0.isdigit():
        command = ch0.lower()
        argument = argument[1:].strip().lower()
    else:
        command, argument = one_argument(argument)

    # -- Look up command in table (cf. command_hash scan)
    cmd = None
    for entry in _CMD_TABLE:
        name, fn, min_pos, noprefix = entry
        if noprefix:
            if command != name:
                continue
        else:
            if not name.startswith(command):
                continue
            # cmd_level_ok: not applicable in single-player
        cmd = entry
        break

    # -- No match: check_social fallback, then huh message
    if not cmd:
        # check_social: not yet ported
        msg = _HUH_MESSAGES[randint(0, len(_HUH_MESSAGES) - 1)]
        if "%s" in msg:
            tprint(msg % command)
        else:
            tprint(msg)
        return None

    # -- check_disabled: not yet ported

    name, fn, min_pos, noprefix = cmd

    # -- Position gate (cf. switch on ch->position)
    pos = player.get("pos", "standing")
    if POS_ORDER[pos] < POS_ORDER[min_pos]:
        tprint(_POS_MSG.get(pos, ""))
        return None

    args = split_args(argument)
    return fn(player, args)
