from hpprime import eval as ppleval
from util import free_mem
from colors import color_len

from world import ROOMS, ITEM_TEMPLATES, MOB_TEMPLATES, SKILLS, SKILL_TABLE, GSN_CURE_LIGHT
from picker import pick_from
from player import get_hitroll, get_damroll, get_AC, get_curr_stat, get_obj_list, get_char_room, save_char, is_name, PLR_AUTOMAP, PLR_DEFAULTS
from combat import set_fighting, stop_fighting, _get_thac0, WaitState, check_improve, do_kick
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


def _wrap_paragraphs(text, width):
    """Word-wrap text, preserving blank-line paragraph breaks from .are descriptions."""
    lines = []
    for para in text.split('\n\n'):
        flat = ' '.join(para.split('\n'))
        if lines:
            lines.append('')
        lines.extend(_wrap(flat, width))
    return lines


# (abbrev, full_name, reverse) — single source for all direction lookups
_DIRS = (("n","north","s"), ("e","east","w"), ("s","south","n"),
         ("w","west","e"), ("u","up","d"), ("d","down","u"))
_EXIT_ORDER  = tuple(d[0] for d in _DIRS)
_EXIT_NAMES  = {d[0]: d[1] for d in _DIRS}
_REV_DIR     = {d[0]: d[2] for d in _DIRS}
_DIR_ALIASES = {k: d[0] for d in _DIRS for k in (d[0], d[1])}


def _exit_to(exit_val):
    """Return destination vnum from a plain-vnum or dict exit."""
    return exit_val["to"] if isinstance(exit_val, dict) else exit_val

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

# ── Commands (cf. 1stMud do_* in interp.c / fight.c) ─────────────────────────

_FLAG_TABLE = (
    (PLR_AUTOMAP, "automap", "Map in room descriptions"),
)


def do_automap(tr, player, args, room_state, mob_instances):
    player["flags"] = player.get("flags", PLR_DEFAULTS) ^ PLR_AUTOMAP
    if player["flags"] & PLR_AUTOMAP:
        tr.print("You now see an automap in room descriptions.")
    else:
        tr.print("You no longer see automap room descriptions.")


def do_autolist(tr, player, args, room_state, mob_instances):
    tr.print(" Command    Status  Description")
    tr.print(" " + "-" * (TERMINAL_COLS - 2))
    flags = player.get("flags", PLR_DEFAULTS)
    for bit, name, desc in _FLAG_TABLE:
        status = "ON" if flags & bit else "OFF"
        tr.print(" {G" + name + " " * (10 - len(name)) +
                 " {W" + status + " " * (6 - len(status)) +
                 "{w " + desc + "{x")


def _look_item(tr, player, args, room_state):
    """Show an item's description from inventory, room, or equipped slots (cf. 1stMud do_look in act_info.c)."""
    target = " ".join(args)
    rs = room_state[player["room"]]
    equipped = [v for v in player["equip"].values() if v is not None]
    vnum = (get_obj_list(target, player["inv"], ITEM_TEMPLATES)
            or get_obj_list(target, rs["items"], ITEM_TEMPLATES)
            or get_obj_list(target, equipped, ITEM_TEMPLATES))
    if vnum is None:
        tr.print("You don't see that here.")
        return
    tpl = ITEM_TEMPLATES[vnum]
    for line in _wrap_paragraphs(tpl.get("description", tpl["short_descr"]), TERMINAL_COLS):
        tr.print(line)
    for ed in tpl.get("extra_descs", []):
        if is_name(target, ed.get("keywords", "")):
            for line in _wrap_paragraphs(ed.get("desc", ""), TERMINAL_COLS):
                tr.print(line)


def do_look(tr, player, args, room_state, mob_instances):
    """Display the current room or examine an item (cf. 1stMud do_look in act_info.c).

    Args:
        tr: Terminal renderer.
        player (dict): Player state dict.
        args (list): Parsed command arguments; non-empty triggers item look.
        room_state (dict): Per-room mutable state.
        mob_instances (dict): Live mob instance dicts keyed by mob ID.
    """
    if args:
        # TODO: extend to room extra_descs, mob descriptions, and item extra_descs on other targets
        _look_item(tr, player, args, room_state)
        return
    room = ROOMS[player["room"]]
    rs = room_state[player["room"]]
    automap_on = player.get("flags", PLR_DEFAULTS) & PLR_AUTOMAP
    text_w = TERMINAL_COLS - COMPACT_W - 1 if automap_on else TERMINAL_COLS

    tr.print("{Y" + room["name"] + "{x")

    text = []
    text.extend(_wrap_paragraphs(room["desc"], text_w))
    
    if automap_on:
        map_lines = build_compact_lines(player, ROOMS)
        n = max(len(map_lines), len(text))
        for i in range(n):
            ml = map_lines[i] if i < len(map_lines) else ' ' * COMPACT_W
            tl = text[i] if i < len(text) else ''
            tr.print(ml + ' ' + tl)
    else:
        for tl in text:
            tr.print(tl)

    exits = " ".join(
        _EXIT_NAMES.get(d, d) for d in _EXIT_ORDER
        if d in room["exits"] and not (isinstance(room["exits"][d], dict) and room["exits"][d].get("closed"))
    )
    exit_string = "[Exits: {}]".format(exits) if exits else "[Exits: none]"
    tr.print("{g" + exit_string + "{x")
    tr.print("")
    live_mobs = rs["mobs"]
    if rs["items"]:
        names = ", ".join(ITEM_TEMPLATES[v]["short_descr"] for v in rs["items"])
        tr.print("Items: {}".format(names))
    if live_mobs:
        names = ", ".join(MOB_TEMPLATES[mob_instances[i]["tpl"]]["short_descr"] for i in live_mobs)
        tr.print("Mobs:  {}".format(names))


def do_move(tr, player, direction, room_state, mob_instances):
    if player["fighting"] is not None:
        tr.print("No way! You are fighting!")
        return
    exits = ROOMS[player["room"]]["exits"]
    if direction not in exits:
        tr.print("Alas, you cannot go that way.")
        return
    exit_val = exits[direction]
    if isinstance(exit_val, dict) and exit_val.get("closed"):
        tr.print("The door is closed.")
        return
    dest = _exit_to(exit_val)
    if dest not in ROOMS:
        tr.print("That way is not yet open.")
        return
    player["room"] = dest
    do_look(tr, player, [], room_state, mob_instances)


def do_open(tr, player, args, room_state, mob_instances):
    """Open a door in a given direction (cf. 1stMud do_open in act_move.c)."""
    exits = ROOMS[player["room"]]["exits"]
    if args:
        direction = _DIR_ALIASES.get(args[0].lower())
        if direction is None:
            tr.print("Open what?")
            return
    else:
        candidates = [d for d in _EXIT_ORDER
                      if isinstance(exits.get(d), dict)
                      and exits[d].get("isdoor") and exits[d].get("closed")]
        if not candidates:
            tr.print("There are no doors to open here.")
            return
        idx = pick_from(tr, "Open which door?",
                        [_EXIT_NAMES[d] for d in candidates])
        if idx < 0:
            return
        direction = candidates[idx]
    exit_val = exits.get(direction)
    if not isinstance(exit_val, dict) or not exit_val.get("isdoor"):
        tr.print("You can't do that.")
        return
    if not exit_val.get("closed"):
        tr.print("It's already open.")
        return
    if exit_val.get("locked"):
        tr.print("It's locked.")
        return
    exit_val["closed"] = False
    tr.print("Ok.")
    dest = exit_val["to"]
    rev = _REV_DIR.get(direction)
    if rev and dest in ROOMS:
        rev_exit = ROOMS[dest]["exits"].get(rev)
        if isinstance(rev_exit, dict) and _exit_to(rev_exit) == player["room"]:
            rev_exit["closed"] = False


def do_close(tr, player, args, room_state, mob_instances):
    """Close a door in a given direction (cf. 1stMud do_close in act_move.c)."""
    exits = ROOMS[player["room"]]["exits"]
    if args:
        direction = _DIR_ALIASES.get(args[0].lower())
        if direction is None:
            tr.print("Close what?")
            return
    else:
        candidates = [d for d in _EXIT_ORDER
                      if isinstance(exits.get(d), dict)
                      and exits[d].get("isdoor") and not exits[d].get("closed")]
        if not candidates:
            tr.print("There are no open doors to close here.")
            return
        idx = pick_from(tr, "Close which door?",
                        [_EXIT_NAMES[d] for d in candidates])
        if idx < 0:
            return
        direction = candidates[idx]
    exit_val = exits.get(direction)
    if not isinstance(exit_val, dict) or not exit_val.get("isdoor"):
        tr.print("You can't do that.")
        return
    if exit_val.get("closed"):
        tr.print("It's already closed.")
        return
    if exit_val.get("noclose"):
        tr.print("You can't do that.")
        return
    exit_val["closed"] = True
    tr.print("Ok.")
    dest = exit_val["to"]
    rev = _REV_DIR.get(direction)
    if rev and dest in ROOMS:
        rev_exit = ROOMS[dest]["exits"].get(rev)
        if isinstance(rev_exit, dict) and _exit_to(rev_exit) == player["room"]:
            rev_exit["closed"] = True


def do_get(tr, player, args, room_state, mob_instances):
    if not args:
        tr.print("Get what?")
        return
    rs = room_state[player["room"]]
    arg = " ".join(args)
    if arg == "all" or arg.startswith("all."):
        filter_kw = arg[4:] if arg.startswith("all.") else None
        for vnum in list(rs["items"]):
            tpl = ITEM_TEMPLATES[vnum]
            if filter_kw and not is_name(filter_kw, tpl.get("keywords", "")):
                continue
            if "take" not in tpl.get("wear_flags", {}):
                tr.print("You can't take the {}.".format(tpl["short_descr"]))
                continue
            rs["items"].remove(vnum)
            player["inv"].append(vnum)
            tr.print("You take the {}.".format(tpl["short_descr"]))
        return
    vnum = get_obj_list(arg, rs["items"], ITEM_TEMPLATES)
    if vnum is None:
        tr.print("Nothing here called that.")
        return
    tpl = ITEM_TEMPLATES[vnum]
    if "take" not in tpl.get("wear_flags", {}):
        tr.print("You can't take that.")
        return
    rs["items"].remove(vnum)
    player["inv"].append(vnum)
    tr.print("You take the {}.".format(tpl["short_descr"]))


def do_drop(tr, player, args, room_state, mob_instances):
    if not args:
        tr.print("Drop what?")
        return
    arg = " ".join(args)
    if arg == "all" or arg.startswith("all."):
        filter_kw = arg[4:] if arg.startswith("all.") else None
        for vnum in list(player["inv"]):
            tpl = ITEM_TEMPLATES[vnum]
            if filter_kw and not is_name(filter_kw, tpl.get("keywords", "")):
                continue
            player["inv"].remove(vnum)
            room_state[player["room"]]["items"].append(vnum)
            tr.print("You drop the {}.".format(tpl["short_descr"]))
        return
    vnum = get_obj_list(arg, player["inv"], ITEM_TEMPLATES)
    if vnum is None:
        tr.print("You're not carrying that.")
        return
    player["inv"].remove(vnum)
    room_state[player["room"]]["items"].append(vnum)
    tr.print("You drop the {}.".format(ITEM_TEMPLATES[vnum]["short_descr"]))


def _obj_flags(tpl):
    """Build coloured flag prefix string for item display (cf. 1stMud format_obj_to_char in act_info.c)."""
    ef = tpl.get("extra_flags", {})
    parts = []
    if ef.get("glow"):   parts.append("{Y(Glowing){x ")
    if ef.get("hum"):    parts.append("{C(Humming){x ")
    if ef.get("magic"):  parts.append("{M(Magical){x ")
    if ef.get("invis"):  parts.append("{c(Invis){x ")
    if ef.get("evil"):   parts.append("{R(Red Aura){x ")
    if ef.get("bless"):  parts.append("{B(Blue Aura){x ")
    return "".join(parts)


def do_inventory(tr, player, args, room_state, mob_instances):
    max_carry = min(37, 17 + player["level"])
    tr.print("{{YYou are carrying {{W{}/{}{{Y items:{{x".format(len(player["inv"]), max_carry))
    if not player["inv"]:
        return
    counts = {}
    for v in player["inv"]:
        counts[v] = counts.get(v, 0) + 1
    for v, n in counts.items():
        tpl = ITEM_TEMPLATES[v]
        flags = _obj_flags(tpl)
        name = tpl["short_descr"]
        tr.print("  {}{} x{}".format(flags, name, n) if n > 1 else "  {}{}".format(flags, name))


_WEAR_MSG = {
    "light":  "You light {} and hold it.",
    "wield":  "You wield {}.",
    "hold":   "You hold {} in your hand.",
    "body":   "You wear {} on your torso.",
    "head":   "You wear {} on your head.",
    "legs":   "You wear {} on your legs.",
    "feet":   "You wear {} on your feet.",
    "hands":  "You wear {} on your hands.",
    "arms":   "You wear {} on your arms.",
    "shield": "You wear {} as a shield.",
    "about":  "You wear {} about your torso.",
    "waist":  "You wear {} about your waist.",
    "neck":   "You wear {} around your neck.",
    "wrist":  "You wear {} around your wrist.",
}


def _wear_one(tr, player, vnum, tpl, slot):
    """Equip one item into slot, enforcing level and curse checks (cf. 1stMud wear_obj in act_obj.c)."""
    if player["level"] < tpl.get("level", 1):
        tr.print("You are too weak to use the {}.".format(tpl["short_descr"]))
        return
    cur = player["equip"][slot]
    if cur is not None:
        cur_tpl = ITEM_TEMPLATES[cur]
        if cur_tpl.get("extra_flags", {}).get("noremove"):
            tr.print("You can't remove the {}, it's cursed.".format(cur_tpl["short_descr"]))
            return
        player["inv"].append(cur)
    player["inv"].remove(vnum)
    player["equip"][slot] = vnum
    tr.print(_WEAR_MSG[slot].format(tpl["short_descr"]))


def do_wear(tr, player, args, room_state, mob_instances):
    """Equip an item from inventory, or wear all wearable items (cf. 1stMud do_wear in act_obj.c).

    Args:
        tr: Terminal renderer.
        player (dict): Player state dict.
        args (list): Parsed command arguments; first token may be "all".
        room_state (dict): Per-room mutable state (unused).
        mob_instances (dict): Live mob instances (unused).
    """
    if not args:
        tr.print("Wear what?")
        return
    if args[0] == "all":
        for vnum in list(player["inv"]):
            tpl = ITEM_TEMPLATES[vnum]
            slot = next((f for f in tpl.get("wear_flags", {}) if f != "take"), None)
            if slot is None or slot not in player["equip"]:
                continue
            _wear_one(tr, player, vnum, tpl, slot)
        return
    vnum = get_obj_list(" ".join(args), player["inv"], ITEM_TEMPLATES)
    if vnum is None:
        tr.print("You're not carrying that.")
        return
    tpl = ITEM_TEMPLATES[vnum]
    slot = next((f for f in tpl.get("wear_flags", {}) if f != "take"), None)
    if slot is None or slot not in player["equip"]:
        tr.print("You can't wear that.")
        return
    _wear_one(tr, player, vnum, tpl, slot)


def _remove_one(tr, player, slot, vnum):
    """Unequip one item, checking for curse (cf. 1stMud remove_obj in act_obj.c)."""
    tpl = ITEM_TEMPLATES[vnum]
    if tpl.get("extra_flags", {}).get("noremove"):
        tr.print("You can't remove the {}, it's cursed.".format(tpl["short_descr"]))
        return
    player["equip"][slot] = None
    player["inv"].append(vnum)
    tr.print("You remove the {}.".format(tpl["short_descr"]))


def do_remove(tr, player, args, room_state, mob_instances):
    """Remove a worn item by name and return it to inventory (cf. 1stMud do_remove in act_obj.c).

    Args:
        tr: Terminal renderer.
        player (dict): Player state dict.
        args (list): Parsed command arguments; first token may be "all".
        room_state (dict): Per-room mutable state (unused).
        mob_instances (dict): Live mob instances (unused).
    """
    if not args:
        tr.print("Remove what?")
        return
    if args[0] == "all":
        for slot, vnum in list(player["equip"].items()):
            if vnum is not None:
                _remove_one(tr, player, slot, vnum)
        return
    target = " ".join(args)
    for slot, vnum in player["equip"].items():
        if vnum is not None and is_name(target, ITEM_TEMPLATES[vnum].get("keywords", "")):
            _remove_one(tr, player, slot, vnum)
            return
    tr.print("You aren't wearing that.")


_WEAR_LABELS = (
    ("light",  "{g<{Wused as light{g>{x      "),
    ("wield",  "{g<{Wwielded{g>{x           "),
    ("hold",   "{g<{Wheld{g>{x              "),
    ("body",   "{g<{Wworn on body{g>{x      "),
    ("head",   "{g<{Wworn on head{g>{x      "),
    ("legs",   "{g<{Wworn on legs{g>{x      "),
    ("feet",   "{g<{Wworn on feet{g>{x      "),
    ("hands",  "{g<{Wworn on hands{g>{x     "),
    ("arms",   "{g<{Wworn on arms{g>{x      "),
    ("shield", "{g<{Wworn as shield{g>{x    "),
    ("about",  "{g<{Wworn about body{g>{x   "),
    ("waist",  "{g<{Wworn about waist{g>{x  "),
    ("neck",   "{g<{Wworn around neck{g>{x  "),
    ("wrist",  "{g<{Wworn around wrist{g>{x "),
)


def do_equipment(tr, player, args, room_state, mob_instances):
    """List all equipment slots and what is worn in each (cf. 1stMud do_equipment in act_info.c).

    Args:
        tr: Terminal renderer.
        player (dict): Player state dict.
        args (list): Parsed command arguments (unused).
        room_state (dict): Per-room mutable state (unused).
        mob_instances (dict): Live mob instances (unused).
    """
    tr.print("You are wearing:")
    for slot, label in _WEAR_LABELS:
        vnum = player["equip"].get(slot)
        if vnum is not None:
            tpl = ITEM_TEMPLATES[vnum]
            tr.print(label + _obj_flags(tpl) + "{Y" + tpl["short_descr"] + "{x")
        else:
            tr.print(label + "nothing")


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
            tpl["short_descr"], gained, player["hp"], player["hp_max"]))


_SCORE_INNER = TERMINAL_COLS - 2
_SCORE_LEFT  = (TERMINAL_COLS - 7) // 2
_SCORE_RIGHT = TERMINAL_COLS - 7 - _SCORE_LEFT
_SCORE_SEP_OUTER = "{W+" + "-" * _SCORE_INNER + "+{x"
_SCORE_SEP_INNER = "{W+" + "-" * (_SCORE_LEFT + 2) + "+" + "-" * (_SCORE_RIGHT + 2) + "+{x"

def do_score(tr, player, args, room_state, mob_instances):
    """Display the character score sheet (cf. 1stMud dlm_score in act_info.c)."""
    # two-column box mirroring 1stMud dlm_score layout (see DESIGN.md)
    def _row(l, r):
        lpad = ' ' * (_SCORE_LEFT  - color_len(l))
        rpad = ' ' * (_SCORE_RIGHT - color_len(r))
        return "{W|{x " + l + lpad + " {W|{x " + r + rpad + " {W|{x"
    def _stat(name, val):
        # [perm/curr] — identical until affect system is added
        return '{c' + '{:<13}'.format(name) + ': [{w' + '{:2d}/{:2d}'.format(val, val) + '{c]{x'
    def _val(name, v, bright=False):
        nc = '{C' if bright else '{c'
        # values stay as dim white
        vc = '{w'
        return nc + '{:<13}'.format(name) + ': [' + vc + '{:>11}'.format(v) + nc + ' ]{x'

    def _free_mem():
        return "{G(Mem. free: " + str(free_mem()) + "){x"

    p = player
    thac0 = _get_thac0(p['level'])
    mem_str = _free_mem()
    name_raw = p.get('name', '???')
    name_col = "{c" + name_raw + "{x" + ' ' * (_SCORE_LEFT - len(name_raw))
    mem_col  = ' ' * (_SCORE_RIGHT - color_len(mem_str)) + mem_str

    session_secs = (int(ppleval("Ticks")) - p.get('_logon_ms', 0)) // 1000
    total_played = p.get('played', 0) + session_secs
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


def do_skills(tr, player, args, room_state, mob_instances):
    for sk_vnum, pct in sorted(player["learned"].items()):
        sk = SKILLS.get(sk_vnum)
        if sk is None:
            continue
        sk_type = sk.get("type", "")
        if sk_type == "spell":
            tr.print("  cast {} {}% (MP:{})".format(
                sk["name"], pct, sk.get("mana", 0)))
        elif sk_type == "active":
            tr.print("  {} {}%".format(sk["name"], pct))
        elif sk_type in ("weapon", "passive"):
            tr.print("  {} {}%".format(sk["name"], pct))


def do_help(tr, player, args, room_state, mob_instances):
    tr.print("Move: 2/8=n/s  4/6=w/e  7/9=u/d (or n/s/e/w/u/d)")
    tr.print("5=look  i=inv  wear  remove  quaff  st=stats  sk=skills")
    tr.print("k/kill=fight  kick  cast <spell>  flee  save  credits  q=quit")


def do_kill(tr, player, args, room_state, mob_instances):
    if player["fighting"] is not None:
        tr.print("You are already fighting!")
        return
    rs = room_state[player["room"]]
    live = rs["mobs"]
    if not live:
        tr.print("No enemies here.")
        return
    if args:
        mob_id = get_char_room(" ".join(args), live, mob_instances)
        if mob_id is None:
            tr.print("No such enemy.")
            return
    else:
        names = [MOB_TEMPLATES[mob_instances[i]["tpl"]]["short_descr"] for i in live]
        idx = pick_from(tr, "Kill whom?", names)
        if idx < 0:
            return
        mob_id = live[idx]
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
        direction, exit_val = exits[attempts.pop(idx)]
        if isinstance(exit_val, dict) and exit_val.get("closed"):
            continue
        dest = _exit_to(exit_val)
        if dest not in ROOMS:
            continue
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


def do_credits(tr, player, args, room_state, mob_instances):
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


def do_quit(tr, player, args, room_state, mob_instances):
    return "quit"


# ── Skill / spell dispatch ────────────────────────────────────────────────────

def do_cast(tr, player, args, room_state, mob_instances):
    if not args:
        tr.print("Cast which spell?")
        return None
    spell_key = args[0]
    sk_vnum = None
    for vnum, sk in SKILL_TABLE:
        if sk.get("type") != "spell":
            continue
        name = sk["name"]
        if name == spell_key or name.startswith(spell_key):
            sk_vnum = vnum
            break
    if sk_vnum is None or player["learned"].get(sk_vnum, 0) == 0:
        tr.print("You don't know any spell called that.")
        return None
    sk = SKILLS[sk_vnum]
    if player.get("wait", 0) > 0:
        tr.print("You are still recovering.")
        return None
    mana = sk.get("mana", 0)
    if player["mp"] < mana:
        tr.print("You don't have enough mana.")
        return None
    player["mp"] -= mana
    WaitState(player, sk.get("beats", 0))
    effect = sk.get("effect", "")
    if effect == "heal":
        num, size, bonus = sk["heal_dice"]
        roll = bonus + player["level"] // sk.get("level_div", 1)
        for _ in range(num):
            roll += randint(1, size)
        gained = min(roll, player["hp_max"] - player["hp"])
        player["hp"] += gained
        tr.print("You feel better! +{} HP. ({}/{})".format(
            gained, player["hp"], player["hp_max"]))
    check_improve(tr, player, sk_vnum, True)
    return None


# ── Direction map ─────────────────────────────────────────────────────────────

_DIRECTION_MAP = {
    "n": "n", "north":     "n",
    "s": "s", "south":     "s",
    "e": "e", "east":      "e",
    "w": "w", "west":      "w",

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

_TRAIN_STATS = [
    ("str", "strength"),
    ("dex", "dexterity"),
    ("int", "intelligence"),
    ("wis", "wisdom"),
    ("con", "constitution"),
]


def do_train(tr, player, args, room_state, mob_instances):
    """Permanently raise a stat by 1 using a train point (cf. 1stMud do_train in act_move.c).

    Requires a mob with act_flags["train"] in the room.  Stats cap at 25;
    each improvement costs 1 train point.

    Args:
        tr: Terminal instance.
        player (dict): Player state dict.
        args (list): Parsed command words; optional stat name.
        room_state (dict): Per-room mutable state.
        mob_instances (dict): Live mob instance dicts.
    """
    rs = room_state[player["room"]]
    trainer = None
    for mid in rs["mobs"]:
        inst = mob_instances[mid]
        if MOB_TEMPLATES[inst["tpl"]].get("act_flags", {}).get("train"):
            trainer = mid
            break
    if trainer is None:
        tr.print("You can't do that here.")
        return

    if not args:
        tr.print("You have {} training session{}.".format(
            player["train"], "" if player["train"] == 1 else "s"))
        available = [lng for key, lng in _TRAIN_STATS if player[key] < 25]
        if available:
            tr.print("You can train: {}.".format(", ".join(available)))
        else:
            tr.print("All your stats are at maximum.")
        return

    arg = args[0]
    stat_key = None
    stat_lng = None
    for key, lng in _TRAIN_STATS:
        if key.startswith(arg) or lng.startswith(arg):
            stat_key = key
            stat_lng = lng
            break

    if stat_key is None:
        tr.print("Valid stats: str, dex, int, wis, con.")
        return

    if player[stat_key] >= 25:
        tr.print("Your {} is already at maximum.".format(stat_lng))
        return

    if player["train"] < 1:
        tr.print("You don't have any training sessions.")
        return

    player["train"] -= 1
    player[stat_key] += 1
    tr.print("Your {} increases!".format(stat_lng))


def do_affects(tr, player, args, room_state, mob_instances):
    """List all active player affects with name, location, modifier, duration (cf. 1stMud do_affects in act_info.c).

    Args:
        tr: Terminal instance.
        player (dict): Player state dict.
        args (list): Unused.
        room_state (dict): Unused.
        mob_instances (dict): Unused.
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


def do_practice(tr, player, args, room_state, mob_instances):
    """Improve a skill percentage using a practice point (cf. 1stMud do_practice in act_info.c).

    Without an argument shows current skills and practice count.  With a skill
    name, requires a mob with act_flags["practice"] in the room; costs 1
    practice point; gain = INT_learn (max(1, int//3)), capped at 75%.

    Args:
        tr: Terminal instance.
        player (dict): Player state dict.
        args (list): Parsed command words; optional skill name.
        room_state (dict): Per-room mutable state.
        mob_instances (dict): Live mob instance dicts.
    """
    if not args:
        do_skills(tr, player, [], room_state, mob_instances)
        tr.print("You have {} practice session{}.".format(
            player["practice"], "" if player["practice"] == 1 else "s"))
        return

    rs = room_state[player["room"]]
    teacher = None
    for mid in rs["mobs"]:
        inst = mob_instances[mid]
        if MOB_TEMPLATES[inst["tpl"]].get("act_flags", {}).get("practice"):
            teacher = mid
            break
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

    current = player["learned"][sk_vnum]
    if current >= _PRACTICE_CAP:
        tr.print("You are already learned at {}.".format(SKILLS[sk_vnum]["name"]))
        return

    gain = max(1, get_curr_stat(player, "int") // 3)
    player["practice"] -= 1
    new_pct = min(_PRACTICE_CAP, current + gain)
    player["learned"][sk_vnum] = new_pct

    if new_pct >= _PRACTICE_CAP:
        tr.print("You are now learned at {}.".format(SKILLS[sk_vnum]["name"]))
    else:
        tr.print("You practice {}.".format(SKILLS[sk_vnum]["name"]))


# ── Command table ─────────────────────────────────────────────────────────────
# Entries in 1stMud load order (cf. COMMANDS.md); [PRIMESUD] shortcuts interleaved.
# Schema: (name, fn, min_pos, noprefix)

_CMD_TABLE = [
    ("cast",      do_cast,      "fighting", False),   # #8
    ("get",       do_get,       "resting",  False),   # #13
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
    ("close",     do_close,     "resting",  False),   # #113
    ("drop",      do_drop,      "resting",  False),   # #115
    ("open",      do_open,      "resting",  False),   # #124
    ("quaff",     do_quaff,     "resting",  False),   # #129
    ("remove",    do_remove,    "resting",  False),   # #131
    ("take",      do_get,       "resting",  False),   # #133
    ("wear",      do_wear,      "resting",  False),   # #138
    ("flee",      do_flee,      "fighting", False),   # #147
    ("kick",      do_kick,      "fighting", False),   # #148
    ("automap",   do_automap,   "sleeping", False),   # #154
    ("quit",      do_quit,      "dead",     True),    # #162 noprefix
    ("save",      do_save,      "dead",     False),   # #166
    ("train",     do_train,     "resting",  False),   # #171
    ("macro",     do_macro,     "dead",     False),   # [PRIMESUD]
    ("map",       do_map,       "resting",  False),   # #291
]


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
        return fn(tr, player, args, room_state, mob_instances)

    tr.print("Unknown command. ? for help.")
    return None
