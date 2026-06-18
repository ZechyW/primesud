from util import free_mem, gc_collect
from colors import color_len

from world import ROOMS, ITEM_TEMPLATES, MOB_TEMPLATES, SKILLS, WEAPON_GSN_MAP
from picker import pick_from
from actor import get_hitroll, get_damroll, get_AC, get_curr_stat, is_name
from item import get_obj_list, get_char_room, obj_vnum, item_extra_flags
from player import save_char, PLR_AUTOMAP, PLR_DEFAULTS
from combat import set_fighting, stop_fighting, _get_thac0, do_kick
from inventory import (do_get, do_drop, do_inventory, do_wear, do_remove,
                       do_equipment, do_second, do_quaff, do_outfit)
from movement import _exit_to, do_move, do_open, do_close, do_recall
from magic import do_cast
from automap import build_compact_lines, build_full_lines, COMPACT_W
from config import (DEFAULT_MACROS, DEFAULT_FNKEY_MACROS, FNKEY_SENTINELS, FNKEY_NAMES,
                    TERMINAL_COLS, EXIT_ORDER, EXIT_NAMES, INT_APP_LEARN, MAX_STATS, SECTOR_COLORS)

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


def _wrap_paragraphs(text, width):
    """Word-wrap text, preserving blank-line paragraph breaks from .are descriptions."""
    lines = []
    for para in text.split('\n\n'):
        flat = ' '.join(para.split())  # [PRIMESUD] collapse whitespace runs (cf. erase_new_lines in automap.c)
        if lines:
            lines.append('')
        lines.extend(_wrap(flat, width))
    return lines

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

# -- Commands (cf. 1stMud do_* in interp.c / fight.c) -------------------------

_FLAG_TABLE = (
    (PLR_AUTOMAP, "automap", "Map in room descriptions"),
)


def do_automap(tr, player, args, world):
    player["flags"] = player.get("flags", PLR_DEFAULTS) ^ PLR_AUTOMAP
    if player["flags"] & PLR_AUTOMAP:
        tr.print("You now see an automap in room descriptions.")
    else:
        tr.print("You no longer see automap room descriptions.")


def do_autolist(tr, player, args, world):
    tr.print(" Command    Status  Description")
    tr.print(" " + "-" * (TERMINAL_COLS - 2))
    flags = player.get("flags", PLR_DEFAULTS)
    for bit, name, desc in _FLAG_TABLE:
        status = "ON" if flags & bit else "OFF"
        tr.print(" {G" + name + " " * (10 - len(name)) +
                 " {W" + status + " " * (6 - len(status)) +
                 "{w " + desc + "{x")


def _look_item(tr, player, args, world):
    """Show an item's description from inventory, room, or equipped slots (cf. 1stMud do_look in act_info.c)."""
    target = " ".join(args)
    rs = world["rooms"][player["room"]]
    equipped = [obj for obj in player["equip"].values() if obj is not None]
    result = (get_obj_list(target, player["inv"], ITEM_TEMPLATES)
              or get_obj_list(target, rs["items"], ITEM_TEMPLATES)
              or get_obj_list(target, equipped, ITEM_TEMPLATES))
    if result is None:
        tr.print("You don't see that here.")
        return
    vnum = obj_vnum(result)
    tpl = ITEM_TEMPLATES[vnum]
    for line in _wrap_paragraphs(tpl.get("description", tpl["short_descr"]), TERMINAL_COLS):
        tr.print(line)
    for ed in tpl.get("extra_descs", []):
        if is_name(target, ed.get("keywords", "")):
            for line in _wrap_paragraphs(ed.get("desc", ""), TERMINAL_COLS):
                tr.print(line)


def do_look(tr, player, args, world):
    """Display the current room or examine an item (cf. 1stMud do_look in act_info.c).

    Args:
        tr: Terminal renderer.
        player (dict): Player state dict.
        args (list): Parsed command arguments; non-empty triggers item look.
        world (dict): Game world state (keys: rooms, mobs, areas).
    """
    if args:
        # TODO: extend to room extra_descs, mob descriptions, and item extra_descs on other targets
        _look_item(tr, player, args, world)
        return
    room = ROOMS[player["room"]]
    rs = world["rooms"][player["room"]]
    automap_on = player.get("flags", PLR_DEFAULTS) & PLR_AUTOMAP
    text_w = TERMINAL_COLS - COMPACT_W - 1 if automap_on else TERMINAL_COLS

    tr.print("{Y" + room["name"] + "{x")

    color = SECTOR_COLORS.get(room.get("sector", "inside"), "")
    desc_lines = _wrap_paragraphs(room["desc"], text_w)

    if automap_on:
        map_lines = build_compact_lines(player, ROOMS)
        n = max(len(map_lines), len(desc_lines))
        for i in range(n):
            ml = map_lines[i] if i < len(map_lines) else ' ' * COMPACT_W
            tl = desc_lines[i] if i < len(desc_lines) else ''
            tr.print(ml + ' ' + color + tl)
    else:
        for tl in desc_lines:
            tr.print(color + tl)

    exits = " ".join(
        EXIT_NAMES.get(d, d) for d in EXIT_ORDER
        if d in room["exits"] and not (isinstance(room["exits"][d], dict) and room["exits"][d].get("closed"))
    )
    exit_string = "[Exits: {}]".format(exits) if exits else "[Exits: none]"
    tr.print("{g" + exit_string + "{x")
    live_mobs = rs["mobs"]
    # Items: build a display string per instance (flags + desc), stack by exact string match
    # (cf. 1stMud format_obj_to_char + show_list_to_char in act_info.c)
    seen = {}
    order = []
    for obj in rs["items"]:
        tpl = ITEM_TEMPLATES[obj_vnum(obj)]
        flags = item_extra_flags(obj, tpl)
        flag_str = ""
        if flags.get("invis"):  flag_str += "({cInvis{x) "
        if flags.get("glow"):   flag_str += "({YGlowing{x) "
        if flags.get("hum"):    flag_str += "({CHumming{x) "
        if flags.get("magic"):  flag_str += "({MMagical{x) "
        line = flag_str + "{Y" + (tpl.get("description") or tpl["short_descr"]) + "{x"
        if line in seen:
            seen[line] += 1
        else:
            seen[line] = 1
            order.append(line)
    for line in order:
        n = seen[line]
        stack_prefix = "(%2d) " % n if n > 1 else "     "
        tr.print(stack_prefix + line)
    # Mobs: one per line, long_descr at idle or constructed position string (cf. 1stMud show_char_to_char_0 in act_info.c)
    for mob_id in live_mobs:
        inst = world["mobs"][mob_id]
        tpl = MOB_TEMPLATES[inst["tpl"]]
        # Build AFF prefix string (cf. 1stMud show_char_to_char_0, act_info.c:191-214)
        # Source: tpl["aff_flags"] (baseline, like pIndexData->affected_by).
        # Dynamic spell AFF bits from inst["affects"] are not yet tracked here.
        aff = tpl.get("aff_flags", {})
        prefix = ""
        if aff.get("invisible"):    prefix += "({cInvis{x) "
        if aff.get("hide"):         prefix += "({DHide{x) "
        if aff.get("charm"):        prefix += "({MCharmed{x) "
        if aff.get("pass_door"):    prefix += "({cTranslucent{x) "
        if aff.get("faerie_fire"):  prefix += "({MPink Aura{x) "
        mob_align = tpl.get("alignment", 0)
        p_aff = player.get("aff_flags", {})
        if mob_align <= -350 and p_aff.get("detect_evil"):  prefix += "({RRed Aura{x) "
        if mob_align >= 350 and p_aff.get("detect_good"):   prefix += "({YGolden Aura{x) "
        if aff.get("sanctuary"):    prefix += "({WWhite Aura{x) "
        if inst["state"] == "idle":
            line = tpl.get("long_descr") or tpl["short_descr"]
        else:
            name = tpl["short_descr"]
            name = name[0].upper() + name[1:] if name else name
            if inst["fighting"] is player:
                line = "%s is here, fighting YOU!" % name
            else:
                line = "%s is here, fighting someone." % name
        tr.print("%s{M%s{x" % (prefix, line))


_SCORE_INNER = TERMINAL_COLS - 2
_SCORE_LEFT  = (TERMINAL_COLS - 7) // 2
_SCORE_RIGHT = TERMINAL_COLS - 7 - _SCORE_LEFT
_SCORE_SEP_OUTER = "{W+" + "-" * _SCORE_INNER + "+{x"
_SCORE_SEP_INNER = "{W+" + "-" * (_SCORE_LEFT + 2) + "+" + "-" * (_SCORE_RIGHT + 2) + "+{x"

def do_score(tr, player, args, world):
    """Display the character score sheet (cf. 1stMud dlm_score in act_info.c)."""
    # two-column box mirroring 1stMud dlm_score layout (see DESIGN.md)
    def _row(l, r):
        lpad = ' ' * (_SCORE_LEFT  - color_len(l))
        rpad = ' ' * (_SCORE_RIGHT - color_len(r))
        return "{W|{x " + l + lpad + " {W|{x " + r + rpad + " {W|{x"
    def _stat(name, val):
        # [perm/curr] -- identical until affect system is added
        return '{c' + '{:<13}'.format(name) + ': [{w' + '{:2d}/{:2d}'.format(val, val) + '{c]{x'
    def _val(name, v, bright=False):
        nc = '{C' if bright else '{c'
        # values stay as dim white
        vc = '{w'
        return nc + '{:<13}'.format(name) + ': [' + vc + '{:>11}'.format(v) + nc + ' ]{x'

    def _free_mem():
        # Since memory is mentioned here, also use `score` as a point to do gc
        gc_collect()
        return "{G(Mem. free: " + str(free_mem()) + "){x"

    p = player
    thac0 = _get_thac0(p['level'])
    mem_str = _free_mem()
    name_raw = p.get('name', '???')
    name_col = "{c" + name_raw + "{x" + ' ' * (_SCORE_LEFT - len(name_raw))
    mem_col  = ' ' * (_SCORE_RIGHT - color_len(mem_str)) + mem_str

    total_played = p.get('played', 0)
    hours = total_played // 3600            # cf. 1stMud act_info.c: played/HOUR
    age   = 17 + total_played // 72000      # cf. 1stMud act_info.c: 17 + played/(20*HOUR)

    lines = [
        _SCORE_SEP_OUTER,
        "{W|{x " + name_col + "   " + mem_col + " {W|{x",
        _SCORE_SEP_INNER,
        _row(_stat('Strength',     get_curr_stat(p, 'str')), _val('Level',     p['level'])),
        _row(_stat('Intelligence', get_curr_stat(p, 'int')), _val('Thac0',     thac0)),
        _row(_stat('Wisdom',       get_curr_stat(p, 'wis')), _val('Practices', p.get('practice', 0))),
        _row(_stat('Dexterity',    get_curr_stat(p, 'dex')), _val('Trains',    p.get('train', 0))),
        _row(_stat('Constitution', get_curr_stat(p, 'con')), ''),
        _SCORE_SEP_INNER,
        _row('{CHit      : [{R' + '{:5d}'.format(p['hp'])     + '{C/{R' + '{:5d}'.format(p['hp_max']) + '{C]{x',
             _val('Hitroll', get_hitroll(p),  bright=True)),
        _row('{CMana     : [{M' + '{:5d}'.format(p['mp'])     + '{C/{M' + '{:5d}'.format(p['mp_max']) + '{C]{x',
             _val('Damroll', get_damroll(p), bright=True)),
        _row('{CExp      : [{w' + '{:>10}'.format(p['xp'])    + '{C ]{x',
             _val('AC',      get_AC(p),      bright=True)),
        _row('{CTo Lvl   : [{w' + '{:>10}'.format(p['xp_next'] - p['xp']) + '{C ]{x',
             _val('Hours',   hours,          bright=True)),
        _row('{CPosition : [{w' + '{:>10}'.format(p['pos'])    + '{C ]{x',
             _val('Age',      age,                  bright=True)),
        _SCORE_SEP_OUTER,
    ]
    for line in lines:
        tr.print(line)


def do_skills(tr, player, args, world):
    for sk_vnum, pct in sorted(player["learned"].items()):
        sk = SKILLS.get(sk_vnum)
        if sk is None:
            continue
        if sk.get("spell_fun", "spell_null") != "spell_null":
            tr.print("  cast {} {}% (MP:{})".format(
                sk["name"], pct, sk.get("min_mana", 0)))
        else:
            tr.print("  {} {}%".format(sk["name"], pct))


def do_help(tr, player, args, world):
    tr.print("Move: 2/8=n/s  4/6=w/e  7/9=u/d (or n/s/e/w/u/d)")
    tr.print("5=look  i=inv  wear  remove  quaff  st=stats  sk=skills")
    tr.print("k/kill=fight  kick  cast <spell>  flee  save  credits  q=quit")


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


def do_map(tr, player, args, world):
    """Print a full-size automap of rooms reachable from the current room (cf. 1stMud do_map in automap.c).

    Args:
        tr: Terminal renderer.
        player (dict): Player state dict.
    """
    # [TODO blind] 1stMud checks check_blind(ch) here and refuses if AFF_BLIND -- add when blindness is implemented
    for line in build_full_lines(player, ROOMS):
        tr.print(line)


def do_save(tr, player, args, world):
    try:
        save_char(player, world)
        tr.print("Saved.")
    except Exception as e:
        tr.print("Save failed: {}".format(e))


def do_credits(tr, player, args, world):
    tr.print("{WPrimeSUD{x -- a single-user dungeon for the HP Prime")
    tr.print("Port by ZechyW.  Not for commercial distribution.")
    tr.print("")
    tr.print("{W1stMud ROM Derivative{x")
    tr.print("  {c(c) 2001-2003 Ryan Jennings (Markanth){x")
    tr.print("  markanth@firstmud.com")
    tr.print("")
    tr.print("{WROM 2.4 beta{x")
    tr.print("  {c(c) 1993-1998 Russ Taylor{x")
    tr.print("  rtaylor@hypercube.org")
    tr.print("")
    tr.print("{WMerc 2.1{x")
    tr.print("  {c(c) 1992-1993 Michael Chastain  mec@shell.portal.com{x")
    tr.print("            Michael Quan       michael@uclink.berkeley.edu")
    tr.print("            Mitchell Tse       hatchet@uclink.berkeley.edu")
    tr.print("")
    tr.print("{WDikuMud{x -- creators of the original game")
    tr.print("  {c(c) 1990-1991 Sebastian Hammer       quinn@freja.diku.dk{x")
    tr.print("            Michael Seifert        seifert@freja.diku.dk")
    tr.print("            Hans Henrik Staerfeldt bombman@freja.diku.dk")
    tr.print("            Tom Madsen             noop@freja.diku.dk")
    tr.print("            Katja Nyboe            katz@freja.diku.dk")
    tr.print("  DIKU, Computer Science Institute, Copenhagen University")


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

_TRAIN_STATS = [
    ("str", "strength"),
    ("dex", "dexterity"),
    ("int", "intelligence"),
    ("wis", "wisdom"),
    ("con", "constitution"),
]


def do_train(tr, player, args, world):
    """Permanently raise a stat or vital by spending a train point (cf. 1stMud do_train in act_move.c).

    Requires a mob with act_flags["train"] in the room.  Stats cap at MAX_STATS;
    hp and mana training raise hp_max/mp_max by 10 with no cap.

    Args:
        tr: Terminal instance.
        player (dict): Player state dict.
        args (list): Parsed command words; optional stat/vital name.
        world (dict): Game world state (keys: rooms, mobs, areas).
    """
    rs = world["rooms"][player["room"]]
    trainer = None
    for mid in rs["mobs"]:
        inst = world["mobs"][mid]
        if MOB_TEMPLATES[inst["tpl"]].get("act_flags", {}).get("train"):
            trainer = mid
            break
    if trainer is None:
        tr.print("You can't do that here.")
        return

    if not args:
        if player["train"] < 1:
            tr.print("You don't have any training sessions.")
            return
        stat_opts = [(k, lng) for k, lng in _TRAIN_STATS if player[k] < MAX_STATS]
        vital_opts = [("hp_max", "hp"), ("mp_max", "mana")]
        all_opts = stat_opts + vital_opts
        tr.print("You have {} training session{}.".format(
            player["train"], "" if player["train"] == 1 else "s"))
        names = []
        for k, lng in all_opts:
            if k in ("hp_max", "mp_max"):
                names.append("{} (max: {})".format(lng, player[k]))
            else:
                names.append("{} ({}/{})".format(lng, player[k], MAX_STATS))
        idx = pick_from(tr, "Train which?", names)
        if idx < 0:
            return
        chosen_key, chosen_lng = all_opts[idx]
    else:
        if player["train"] < 1:
            tr.print("You don't have any training sessions.")
            return
        arg = args[0]
        chosen_key = None
        chosen_lng = None
        for k, lng in _TRAIN_STATS + [("hp_max", "hp"), ("mp_max", "mana")]:
            if lng.startswith(arg):
                chosen_key = k
                chosen_lng = lng
                break
        if chosen_key is None:
            tr.print("Valid training: str, dex, int, wis, con, hp, mana.")
            return
        if chosen_key not in ("hp_max", "mp_max") and player[chosen_key] >= MAX_STATS:
            tr.print("Your {} is already at maximum.".format(chosen_lng))
            return

    player["train"] -= 1
    if chosen_key == "hp_max":
        player["hp_max"] += 10
        player["hp"] = min(player["hp_max"], player["hp"] + 10)
        tr.print("Your durability increases!")
    elif chosen_key == "mp_max":
        player["mp_max"] += 10
        player["mp"] = min(player["mp_max"], player["mp"] + 10)
        tr.print("Your power increases!")
    else:
        player[chosen_key] += 1
        tr.print("Your {} increases!".format(chosen_lng))


def do_affects(tr, player, args, world):
    """List all active player affects with name, location, modifier, duration (cf. 1stMud do_affects in act_info.c).

    Args:
        tr: Terminal instance.
        player (dict): Player state dict.
        args (list): Unused.
        world (dict): Game world state (keys: rooms, mobs, areas); unused.
    """
    affects = player.get("affects", {})
    if not affects:
        tr.print("You are not affected by any spells.")
        return
    tr.print("You are affected by:")
    for sn, aff in affects.items():
        sk = SKILLS.get(sn)
        name = sk["name"] if sk else "unknown"
        mod = aff["modifier"]
        dur = aff["duration"]
        dur_str = "permanent" if dur < 0 else "{} tick{}".format(dur, "" if dur == 1 else "s")
        tr.print("  {}: modifies {} by {:+d} for {}".format(
            name, aff["loc"], mod, dur_str))


_PRACTICE_CAP = 75  # matches 1stMud skill_adept for all classes


def do_practice(tr, player, args, world):
    """Improve a skill percentage using a practice point (cf. 1stMud do_practice in act_info.c).

    Without an argument and no teacher: lists skills + practice count (1stMud parity).
    Without an argument and teacher present: picker of under-cap skills [PRIMESUD].
    With a skill name: requires a mob with act_flags["practice"] in the room.

    Args:
        tr: Terminal instance.
        player (dict): Player state dict.
        args (list): Parsed command words; optional skill name.
        world (dict): Game world state (keys: rooms, mobs, areas).
    """
    rs = world["rooms"][player["room"]]
    teacher = None
    for mid in rs["mobs"]:
        inst = world["mobs"][mid]
        if MOB_TEMPLATES[inst["tpl"]].get("act_flags", {}).get("practice"):
            teacher = mid
            break

    if not args:
        if teacher is None:
            do_skills(tr, player, [], world)
            tr.print("You have {} practice session{}.".format(
                player["practice"], "" if player["practice"] == 1 else "s"))
            return
        if player["practice"] < 1:
            tr.print("You have no practice sessions left.")
            return
        practicable = [(vnum, pct) for vnum, pct in player["learned"].items()
                       if 0 < pct < _PRACTICE_CAP and SKILLS.get(vnum)]
        if not practicable:
            tr.print("You have nothing left to practice.")
            return
        tr.print("You have {} practice session{}.".format(
            player["practice"], "" if player["practice"] == 1 else "s"))
        names = ["{} ({}%)".format(SKILLS[vnum]["name"], pct) for vnum, pct in practicable]
        idx = pick_from(tr, "Practice which skill?", names)
        if idx < 0:
            return
        sk_vnum, _ = practicable[idx]
    else:
        if teacher is None:
            tr.print("You can't do that here.")
            return
        if player["practice"] < 1:
            tr.print("You have no practice sessions left.")
            return
        arg = " ".join(args)
        sk_vnum = None
        for vnum in player["learned"]:
            sk = SKILLS.get(vnum)
            if sk and sk["name"].startswith(arg):
                sk_vnum = vnum
                break
        if sk_vnum is None:
            tr.print("You don't know that skill.")
            return
        if player["learned"][sk_vnum] >= _PRACTICE_CAP:
            tr.print("You are already learned at {}.".format(SKILLS[sk_vnum]["name"]))
            return
        if player["learned"][sk_vnum] < 1:
            tr.print("You can't practice that.")
            return

    int_val = get_curr_stat(player, "int")
    sk_rating = SKILLS[sk_vnum].get("rating", 1)
    if sk_rating == 0:
        tr.print("You can't practice that.")
        return
    gain = INT_APP_LEARN[int_val] // sk_rating
    player["practice"] -= 1
    new_pct = min(_PRACTICE_CAP, player["learned"][sk_vnum] + gain)
    player["learned"][sk_vnum] = new_pct
    if new_pct >= _PRACTICE_CAP:
        tr.print("You are now learned at {}.".format(SKILLS[sk_vnum]["name"]))
    else:
        tr.print("You practice {}.".format(SKILLS[sk_vnum]["name"]))


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
    world["look_fn"] = do_look
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
