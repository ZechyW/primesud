from world import ROOMS, ITEM_TEMPLATES, MOB_TEMPLATES, SKILLS
from player import get_hitroll, get_damroll, get_AC, get_obj_list, get_char_room, save_char
from combat import set_fighting, stop_fighting, use_skill, _get_thac0
from automap import build_compact_lines, build_full_lines, COMPACT_W
from config import DEFAULT_MACROS, TERMINAL_COLS

from urandom import randint


def _wrap(text, width):
    lines = []
    # Use >= so a line of exactly `width` chars is split: the combined
    # map+text line would otherwise reach _cols and trigger tml's auto-advance
    # before the \n, producing a blank row (see _wrapped_print in primesud.py).
    while len(text) >= width:
        i = text.rfind(' ', 0, width)
        if i <= 0:
            i = width - 1
        lines.append(text[:i])
        text = text[i:].lstrip(' ')
    lines.append(text)
    return lines


_EXIT_ORDER = ("n", "ne", "e", "se", "s", "sw", "w", "nw", "u", "d")

# ── Commands (cf. 1stMud do_* in interp.c / fight.c) ─────────────────────────

def do_look(tr, player, args, room_state, mob_instances, _long=True):
    room = ROOMS[player["room"]]
    rs = room_state[player["room"]]
    text_w = TERMINAL_COLS - COMPACT_W - 1

    text = ["[ {} ]".format(room["name"])]
    text.append("")
    text.extend(_wrap(room["long"] if _long else room["short"], text_w))
    exits = " ".join(d for d in _EXIT_ORDER if d in room["exits"]).upper()
    text.append("[Exits: {}]".format(exits) if exits else "[Exits: none]")
    text.append("")
    live_mobs = [i for i in rs["mobs"] if mob_instances[i]["state"] != "dead"]
    if rs["items"]:
        names = ", ".join(ITEM_TEMPLATES[v]["name"] for v in rs["items"])
        text.append("Items: {}".format(names))
    if live_mobs:
        names = ", ".join(MOB_TEMPLATES[mob_instances[i]["tpl"]]["name"] for i in live_mobs)
        text.append("Mobs:  {}".format(names))

    map_lines = build_compact_lines(player, ROOMS)
    n = max(len(map_lines), len(text))
    for i in range(n):
        ml = map_lines[i] if i < len(map_lines) else ' ' * COMPACT_W
        tl = text[i] if i < len(text) else ''
        tr.print(ml + ' ' + tl)


def do_move(tr, player, direction, room_state, mob_instances):
    if player["fighting"] is not None:
        tr.print("No way! You are fighting!")
        return
    exits = ROOMS[player["room"]]["exits"]
    if direction not in exits:
        tr.print("Alas, you cannot go that way.")
        return
    player["room"] = exits[direction]
    do_look(tr, player, [], room_state, mob_instances, _long=False)


def do_get(tr, player, args, room_state, mob_instances):
    if not args:
        tr.print("Get what?")
        return
    rs = room_state[player["room"]]
    vnum = get_obj_list(" ".join(args), rs["items"], ITEM_TEMPLATES)
    if vnum is None:
        tr.print("Nothing here called that.")
        return
    rs["items"].remove(vnum)
    player["inv"].append(vnum)
    tr.print("You take the {}.".format(ITEM_TEMPLATES[vnum]["name"]))


def do_drop(tr, player, args, room_state, mob_instances):
    if not args:
        tr.print("Drop what?")
        return
    vnum = get_obj_list(" ".join(args), player["inv"], ITEM_TEMPLATES)
    if vnum is None:
        tr.print("You're not carrying that.")
        return
    player["inv"].remove(vnum)
    room_state[player["room"]]["items"].append(vnum)
    tr.print("You drop the {}.".format(ITEM_TEMPLATES[vnum]["name"]))


def do_inventory(tr, player, args, room_state, mob_instances):
    if not player["inv"]:
        tr.print("You carry nothing.")
        return
    counts = {}
    for v in player["inv"]:
        counts[v] = counts.get(v, 0) + 1
    for v, n in counts.items():
        name = ITEM_TEMPLATES[v]["name"]
        tr.print("  {} x{}".format(name, n) if n > 1 else "  {}".format(name))


def do_wear(tr, player, args, room_state, mob_instances):
    if not args:
        tr.print("Equip what?")
        return
    vnum = get_obj_list(" ".join(args), player["inv"], ITEM_TEMPLATES)
    if vnum is None:
        tr.print("You're not carrying that.")
        return
    tpl = ITEM_TEMPLATES[vnum]
    slot = tpl.get("slot")
    if slot is None:
        tr.print("That can't be equipped.")
        return
    if player["equip"][slot] is not None:
        player["inv"].append(player["equip"][slot])
    player["inv"].remove(vnum)
    player["equip"][slot] = vnum
    tr.print("You equip the {}.".format(tpl["name"]))


def do_remove(tr, player, args, room_state, mob_instances):
    if not args:
        tr.print("Remove which slot?")
        return
    slot = args[0].lower()
    if slot not in player["equip"]:
        tr.print("No such slot.")
        return
    vnum = player["equip"][slot]
    if vnum is None:
        tr.print("Nothing equipped there.")
        return
    player["inv"].append(vnum)
    player["equip"][slot] = None
    tr.print("You unequip the {}.".format(ITEM_TEMPLATES[vnum]["name"]))


def do_quaff(tr, player, args, room_state, mob_instances):
    if not args:
        tr.print("Use what?")
        return
    vnum = get_obj_list(" ".join(args), player["inv"], ITEM_TEMPLATES)
    if vnum is None:
        tr.print("You're not carrying that.")
        return
    tpl = ITEM_TEMPLATES[vnum]
    if tpl["type"] != "consumable":
        tr.print("You can't use that.")
        return
    player["inv"].remove(vnum)
    if "use_hp" in tpl:
        gained = min(tpl["use_hp"], player["hp_max"] - player["hp"])
        player["hp"] += gained
        tr.print("You drink the {}. +{} HP. ({}/{})".format(
            tpl["name"], gained, player["hp"], player["hp_max"]))


_SCORE_INNER     = TERMINAL_COLS - 2
_SCORE_LEFT      = (TERMINAL_COLS - 7) // 2
_SCORE_RIGHT     = TERMINAL_COLS - 7 - _SCORE_LEFT
_SCORE_SEP_OUTER = "+" + "-" * _SCORE_INNER + "+"
_SCORE_SEP_INNER = "+" + "-" * (_SCORE_LEFT + 2) + "+" + "-" * (_SCORE_RIGHT + 2) + "+"
_SCORE_ROW_FMT   = "| {{:<{}}} | {{:<{}}} |".format(_SCORE_LEFT, _SCORE_RIGHT)
_SCORE_NAME_FMT  = "|{{:^{}}}|".format(_SCORE_INNER)

def do_score(tr, player, args, room_state, mob_instances):
    # two-column box mirroring 1stMud dlm_score layout (see DESIGN.md)
    def _row(l, r):
        return _SCORE_ROW_FMT.format(l, r)
    def _stat(name, val):
        # [perm/curr] — identical until affect system is added
        return '{:<13}: [{:2d}/{:2d}]'.format(name, val, val)
    def _val(name, v):
        return '{:<13}: [{:>11} ]'.format(name, v)

    p = player
    thac0 = _get_thac0(p['level'])
    lines = [
        _SCORE_SEP_OUTER,
        _SCORE_NAME_FMT.format(p.get('name', '???')),
        _SCORE_SEP_INNER,
        _row(_stat('Strength',     p['str']), _val('Level',     p['level'])),
        _row(_stat('Intelligence', p['int']), _val('Thac0',     thac0)),
        _row(_stat('Wisdom',       p['wis']), _val('Practices', p.get('practice', 0))),
        _row(_stat('Dexterity',    p['dex']), _val('Trains',    p.get('train', 0))),
        _row(_stat('Constitution', p['con']), ''),
        _SCORE_SEP_INNER,
        _row('Hit    : [{:5d}/{:5d}]'.format(p['hp'],  p['hp_max']),
             _val('Hitroll', get_hitroll(p))),
        _row('Mana   : [{:5d}/{:5d}]'.format(p['mp'],  p['mp_max']),
             _val('Damroll', get_damroll(p))),
        _row('Exp    : [{:>10} ]'.format(p['xp']),
             _val('AC',      get_AC(p))),
        _row('To Lvl : [{:>10} ]'.format(p['xp_next'] - p['xp']), ''),
        _SCORE_SEP_OUTER,
    ]
    for line in lines:
        tr.print(line)


def do_skills(tr, player, args, room_state, mob_instances):
    for sk_vnum, pct in sorted(player["learned"].items()):
        sk = SKILLS.get(sk_vnum)
        if sk is None:
            continue
        sk_type = sk.get("type", "")
        if sk_type == "active":
            tr.print("  {} {}% (MP:{})".format(
                sk["name"], pct, sk.get("mp_cost", 0)))
        elif sk_type in ("weapon", "passive"):
            tr.print("  {} {}%".format(sk["name"], pct))


def do_help(tr, player, args, room_state, mob_instances):
    tr.print("Move: 7 8 9 / 4 5 6 / 1 2 3 (or n/s/e/w/ne/...)")
    tr.print("5=look  i=inv  equip  unequip  u=use  st=stats")
    tr.print("sk=skills  l=look  k/kill=fight  flee  save  q=quit")


def do_kill(tr, player, args, room_state, mob_instances):
    if player["fighting"] is not None:
        tr.print("You are already fighting!")
        return
    rs = room_state[player["room"]]
    live = [i for i in rs["mobs"] if mob_instances[i]["state"] != "dead"]
    if not live:
        tr.print("No enemies here.")
        return
    if args:
        mob_id = get_char_room(" ".join(args), live, mob_instances)
        if mob_id is None:
            tr.print("No such enemy.")
            return
    else:
        mob_id = live[0]
    set_fighting(tr, player, mob_id, mob_instances, room_state)


def do_flee(tr, player, args, room_state, mob_instances):
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
        direction, dest = exits[attempts.pop(idx)]
        player["room"] = dest
        stop_fighting(player, mob_instances)
        tr.print("You flee {}!".format(direction))
        do_look(tr, player, [], room_state, mob_instances)
        return
    tr.print("There is nowhere to run!")


def do_map(tr, player, args, room_state, mob_instances):
    for line in build_full_lines(player, ROOMS):
        tr.print(line)


def do_save(tr, player, args, room_state, mob_instances):
    ok = save_char(player, room_state, mob_instances)
    tr.print("Saved." if ok else "Save failed.")


def do_quit(tr, player, args, room_state, mob_instances):
    return "quit"


# ── Direction map ─────────────────────────────────────────────────────────────

_DIRECTION_MAP = {
    "n": "n", "north":     "n",
    "s": "s", "south":     "s",
    "e": "e", "east":      "e",
    "w": "w", "west":      "w",

    "ne": "ne", "northeast": "ne",
    "nw": "nw", "northwest": "nw",
    "se": "se", "southeast": "se",
    "sw": "sw", "southwest": "sw",

    "u": "u", "up":   "u",
    "d": "d", "down": "d",
}

_MACRO_SUBST = dict(DEFAULT_MACROS)  # [PRIMESUD] user-configurable digit macros — no 1stMud equivalent

_MACRO_ROWS = [("7", "8", "9"), ("4", "5", "6"), ("1", "2", "3")]
_CELL_W     = (TERMINAL_COLS - 4) // 3  # 4 for the four | separators
_CMD_INDENT = 4                          # len(" K: ")
_MACRO_SEP  = "+" + ("-" * _CELL_W + "+") * 3

def _macro_cell(key):
    def pad(s):
        return s + " " * (_CELL_W - len(s))
    cmd = _MACRO_SUBST.get(key)
    if cmd is None:
        return [pad(" {}:".format(key))]
    content_w = _CELL_W - _CMD_INDENT
    lines = []
    rest = cmd
    while rest:
        prefix = " {}: ".format(key) if not lines else " " * _CMD_INDENT
        lines.append(pad(prefix + rest[:content_w]))
        rest = rest[content_w:]
    return lines

def _macro_row(keys):
    cells = [_macro_cell(k) for k in keys]
    height = max(len(c) for c in cells)
    for c in cells:
        while len(c) < height:
            c.append(" " * _CELL_W)
    for ki, key in enumerate(keys):
        s = cells[ki][0]
        cells[ki][0] = s[0] + "{R" + key + "{x" + s[2:]
    return ["|{}|{}|{}|".format(cells[0][i], cells[1][i], cells[2][i])
            for i in range(height)]

def do_macro(tr, player, args, room_state, mob_instances):  # [PRIMESUD]
    if not args:
        for keys in _MACRO_ROWS:
            tr.print(_MACRO_SEP)
            for line in _macro_row(keys):
                tr.print(line)
        # bottom row: 0 centred in the middle column
        blank = " " * _CELL_W
        tr.print(_MACRO_SEP)
        cell0 = _macro_cell("0")
        s = cell0[0]
        cell0[0] = s[0] + "{R0{x" + s[2:]
        for mid in cell0:
            tr.print("|{}|{}|{}|".format(blank, mid, blank))
        tr.print(_MACRO_SEP)
        return None
    key = args[0]
    if len(key) != 1 or key not in "0123456789":
        tr.print("Key must be a single digit 0-9.")
        return None
    if len(args) == 1:
        if key in _MACRO_SUBST:
            del _MACRO_SUBST[key]
            tr.print("Macro {} cleared.".format(key))
        else:
            tr.print("No macro on {}.".format(key))
    else:
        cmd = " ".join(args[1:])
        _MACRO_SUBST[key] = cmd
        tr.print("{} => {}".format(key, cmd))
    return None

# ── Command table ─────────────────────────────────────────────────────────────

_CMD_TABLE = {
    "i":       do_inventory,
    "inv":     do_inventory,
    "l":       do_look,
    "look":    do_look,
    "st":      do_score,
    "stats":   do_score,
    "score":   do_score,
    "sk":      do_skills,
    "skills":  do_skills,
    "get":     do_get,
    "take":    do_get,
    "drop":    do_drop,
    "wear":    do_wear,
    "remove":  do_remove,
    "quaff":   do_quaff,
    "k":       do_kill,
    "kill":    do_kill,
    "flee":    do_flee,
    "fl":      do_flee,
    "macro":   do_macro,
    "map":     do_map,
    "save":    do_save,
    "h":       do_help,
    "help":    do_help,
    "?":       do_help,
    "q":       do_quit,
    "quit":    do_quit,
}


# ── Interpreter ───────────────────────────────────────────────────────────────

def interpret(raw, tr, player, room_state, mob_instances):
    parts = raw.strip().lower().split()
    if not parts:
        return None
    tr.print("")
    verb = parts[0]
    args = parts[1:]

    direction = _DIRECTION_MAP.get(verb)
    if direction is not None:
        do_move(tr, player, direction, room_state, mob_instances)
        return None

    fn = _CMD_TABLE.get(verb)
    if fn is not None:
        return fn(tr, player, args, room_state, mob_instances)

    # Skill name dispatch — active skills only
    for sk_vnum, pct in player["learned"].items():
        sk = SKILLS.get(sk_vnum)
        if sk is None or sk.get("type") != "active":
            continue
        if verb != sk["name"].lower():
            continue
        if player["fighting"] is None:
            tr.print("You're not in combat.")
        elif player.get("wait", 0) > 0:
            tr.print("You are still recovering.")
        elif player["mp"] < sk.get("mp_cost", 0):
            tr.print("Not enough MP!")
        else:
            player["mp"] -= sk.get("mp_cost", 0)
            use_skill(tr, player, sk_vnum, mob_instances, room_state)
        return None

    tr.print("Unknown command. ? for help.")
    return None
