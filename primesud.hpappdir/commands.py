from world import ROOMS, MOB_TEMPLATES
from picker import pick_from
from item import get_char_room
from player import save_char
from combat import set_fighting, stop_fighting, do_kick
from inventory import (do_get, do_drop, do_inventory, do_wear, do_remove,
                       do_equipment, do_second, do_quaff, do_outfit)
from movement import _exit_to, do_move, do_open, do_close, do_recall
from magic import do_cast
from training import do_train, do_practice
from info import (do_look, do_score, do_skills, do_help, do_affects,
                  do_credits, do_map, do_automap, do_autolist)
from config import (DEFAULT_MACROS, DEFAULT_FNKEY_MACROS, FNKEY_SENTINELS, FNKEY_NAMES,
                    TERMINAL_COLS)

from urandom import randint


# Position system (cf. 1stMud position_t enum in defines.h; gaps 1-3 omitted [PRIMESUD])
_POS_ORDER = {
    "dead": 0, "sleeping": 4, "resting": 5,
    "sitting": 6, "fighting": 7, "standing": 8,
}

_POS_MSG = {
    "dead":     "Lie still; you are DEAD.",
    "sleeping": "In your dreams, or what?",
    "resting":  "Nah... You feel too relaxed...",
    "sitting":  "Better stand up first.",
    "fighting": "No way!  You are still fighting!",
}

def do_kill(tr, player, args, world):
    if player["fighting"] is not None:
        tr.print("You are already fighting!")
        return
    rs = world["rooms"][player["room"]]
    live = rs["mobs"]
    if not live:
        tr.print("Kill whom?")
        return
    if args:
        mob_id = get_char_room(" ".join(args), live, world["mobs"])
        if mob_id is None:
            tr.print("They aren't here.")
            return
    else:
        names = [MOB_TEMPLATES[world["mobs"][i]["tpl"]]["short_descr"] for i in live]
        idx = pick_from(tr, "Kill whom?", names)
        if idx < 0:
            return
        mob_id = live[idx]
    set_fighting(tr, player, mob_id, world["mobs"])


def do_flee(tr, player, args, world):
    if player["fighting"] is None:
        tr.print("You're not fighting anyone.")
        return
    exits = list(ROOMS[player["room"]]["exits"].items())
    if not exits:
        tr.print("There is nowhere to run!")
        return
    # Try exits in random order (up to 6 attempts, cf. 1stMud)
    attempts = list(range(len(exits)))
    for _ in range(min(6, len(exits))):
        idx = randint(0, len(attempts) - 1)
        direction, exit_val = exits[attempts.pop(idx)]
        if isinstance(exit_val, dict) and exit_val.get("closed"):
            continue
        dest = _exit_to(exit_val)
        if dest not in ROOMS:
            continue
        player["room"] = dest
        stop_fighting(player, world["mobs"])
        tr.print("You flee {}!".format(direction))
        player["xp"] = max(0, player["xp"] - 10)
        tr.print("You lost 10 exp.")
        do_look(tr, player, [], world)
        return
    tr.print("There is nowhere to run!")


def do_save(tr, player, args, world):
    try:
        save_char(player, world)
        tr.print("Saved.")
    except Exception as e:
        tr.print("Save failed: {}".format(e))


def do_quit(tr, player, args, world):
    return "quit"


# -- Direction map -------------------------------------------------------------

_DIRECTION_MAP = {
    "n": "n", "north":     "n",
    "s": "s", "south":     "s",
    "e": "e", "east":      "e",
    "w": "w", "west":      "w",

    "u": "u", "up":   "u",
    "d": "d", "down": "d",
}

_MACRO_SUBST = dict(DEFAULT_MACROS)   # [PRIMESUD] user-configurable macros -- no 1stMud equivalent
_MACRO_SUBST.update(DEFAULT_FNKEY_MACROS)

_CELL_W         = (TERMINAL_COLS - 4) // 3  # width of each of the 3 display columns
_MACRO_SEP      = "+" + ("-" * _CELL_W + "+") * 3
_MACRO_SEP_STRONG = "+" + ("=" * _CELL_W + "+") * 3

_FNKEY_ORDER   = sorted(FNKEY_NAMES.keys())
_FNKEY_BY_NAME = {v: k for k, v in FNKEY_NAMES.items()}  # 'x2' -> '\x12' etc.

_fns = [(s, FNKEY_NAMES[s]) for s in _FNKEY_ORDER]
while len(_fns) % 3:
    _fns.append(None)
_MACRO_TABLE = [_fns[i:i+3] for i in range(0, len(_fns), 3)] + [
    None,
    [("7","7"), ("8","8"), ("9","9")],
    [("4","4"), ("5","5"), ("6","6")],
    [("1","1"), ("2","2"), ("3","3")],
    [("0","0"), None,      None     ],
]
del _fns


def _macro_cell(key, label=None):
    """Return padded display lines for one cell; key=None -> blank."""
    def pad(s):
        return s + " " * (_CELL_W - len(s))
    if key is None:
        return [" " * _CELL_W]
    if label is None:
        label = key
    label = " " * (3 - len(label)) + label
    cmd = _MACRO_SUBST.get(key)
    if cmd is None:
        return [pad(" {}:".format(label))]
    indent = len(label) + 3
    content_w = _CELL_W - indent
    lines = []
    rest = cmd
    while rest:
        prefix = " {}: ".format(label) if not lines else " " * indent
        lines.append(pad(prefix + rest[:content_w]))
        rest = rest[content_w:]
    return lines


def _macro_row(entries):
    """Render one 3-cell row; each entry is (key, label) or None for blank."""
    cells = [_macro_cell(*(e if e is not None else (None, None))) for e in entries]
    height = max(len(c) for c in cells)
    for c in cells:
        while len(c) < height:
            c.append(" " * _CELL_W)
    for ki, e in enumerate(entries):
        if e is not None:
            label = e[1]
            pad_len = max(3, len(label))
            s = cells[ki][0]
            cells[ki][0] = s[:1 + pad_len - len(label)] + "{R" + label + "{x" + s[1 + pad_len:]
    return ["|{}|{}|{}|".format(cells[0][i], cells[1][i], cells[2][i])
            for i in range(height)]

def do_macro(tr, player, args, world):  # [PRIMESUD]
    if not args:
        next_sep = _MACRO_SEP
        for row in _MACRO_TABLE:
            if row is None:
                next_sep = _MACRO_SEP_STRONG
            else:
                tr.print(next_sep)
                for line in _macro_row(row):
                    tr.print(line)
                next_sep = _MACRO_SEP
        tr.print(next_sep)
        return None
    if args[0] == "default":
        _MACRO_SUBST.clear()
        _MACRO_SUBST.update(DEFAULT_MACROS)
        _MACRO_SUBST.update(DEFAULT_FNKEY_MACROS)
        tr.print("Macros reset to defaults.")
        return None
    key = args[0].lower()
    sentinel = _FNKEY_BY_NAME.get(key)
    if sentinel is not None:
        target = sentinel
        label = key
    elif len(key) == 1 and key in "0123456789":
        target = key
        label = key
    else:
        tr.print("Key must be a digit 0-9 or one of: {}.".format(
            " ".join(sorted(_FNKEY_BY_NAME))))
        return None
    if len(args) == 1:
        if target in _MACRO_SUBST:
            del _MACRO_SUBST[target]
            tr.print("Macro {} cleared.".format(label))
        else:
            tr.print("No macro on {}.".format(label))
    else:
        cmd = " ".join(args[1:])
        _MACRO_SUBST[target] = cmd
        tr.print("{R%s{x mapped to '%s'." % (label, cmd))
    return None

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
    ("autolist",  do_autolist,  "dead",     False),   # #63
    ("outfit",    do_outfit,    "resting",  False),   # #80
    ("close",     do_close,     "resting",  False),   # #113
    ("drop",      do_drop,      "resting",  False),   # #115
    ("open",      do_open,      "resting",  False),   # #124
    ("second",    do_second,    "resting",  False),   # #128
    ("quaff",     do_quaff,     "resting",  False),   # #129
    ("remove",    do_remove,    "resting",  False),   # #131
    ("take",      do_get,       "resting",  False),   # #133
    ("wear",      do_wear,      "resting",  False),   # #138
    ("flee",      do_flee,      "fighting", False),   # #147
    ("kick",      do_kick,      "fighting", False),   # #148
    ("automap",   do_automap,   "sleeping", False),   # #154
    ("quit",      do_quit,      "dead",     True),    # #162 noprefix
    ("recall",    do_recall,    "fighting", False),   # #163
    ("/",         do_recall,    "fighting", False),   # #164
    ("save",      do_save,      "dead",     False),   # #166
    ("train",     do_train,     "resting",  False),   # #171
    ("macro",     do_macro,     "dead",     False),   # [PRIMESUD]
    ("map",       do_map,       "resting",  False),   # #291
]


# -- Interpreter ---------------------------------------------------------------

def interpret(raw, tr, player, world):
    parts = raw.strip().lower().split()
    if not parts:
        return None
    tr.print("")
    verb = parts[0]
    args = parts[1:]

    direction = _DIRECTION_MAP.get(verb)
    if direction is not None:
        do_move(tr, player, direction, world)
        return None

    pos = player.get("pos", "standing")
    for name, fn, min_pos, noprefix in _CMD_TABLE:
        if noprefix:
            if verb != name:
                continue
        elif not name.startswith(verb):
            continue
        if _POS_ORDER[pos] < _POS_ORDER[min_pos]:
            tr.print(_POS_MSG.get(pos, ""))
            return None
        return fn(tr, player, args, world)

    tr.print("Unknown command. ? for help.")
    return None
