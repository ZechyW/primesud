"""Information and room-view command handlers."""

from util import free_mem, gc_collect
from colors import color_len, upper

from skills_table import SKILL_TABLE, SKILLS
from world import ROOM_DEFS, ITEM_DEFS, MOB_DEFS
from actor import get_hitroll, get_damroll, get_armor, get_curr_stat, is_name
from item import get_obj_list, obj_vnum, item_extra_flags
from player import PLR_AUTOMAP, PLR_DEFAULTS
from combat import _get_thac0
from automap import build_compact_lines, build_full_lines, COMPACT_W
from config import (TERMINAL_COLS, EXIT_ORDER, EXIT_NAMES, SECTOR_COLORS, MAX_MORTAL_LEVEL,
                    AC_PIERCE, AC_BASH, AC_SLASH, AC_EXOTIC)
from skill_utils import can_use_skill_spell, is_spell, is_runtime_spell, skill_level, spell_mana


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


_CONTAINER_TYPES = ("npc_corpse", "pc_corpse", "container")


def _look_in(tr, player, args, world):
    """Show contents of a container in room or inventory (cf. 1stMud do_look 'in' case in act_info.c)."""
    if not args:
        tr.print("Look in what?")
        return
    keyword = " ".join(args)
    rs = world.rooms[player["room"]]
    obj = get_obj_list(keyword, rs["items"], ITEM_DEFS)
    if obj is None:
        obj = get_obj_list(keyword, player["inv"], ITEM_DEFS)
    if obj is None:
        tr.print("You do not see that here.")
        return
    tpl = ITEM_DEFS[obj_vnum(obj)]
    if tpl.get("type") not in _CONTAINER_TYPES:
        tr.print("That is not a container.")
        return
    obj_name = (isinstance(obj, dict) and obj.get("short_descr")) or tpl["short_descr"]
    tr.print("{} holds:".format(obj_name))
    contents = isinstance(obj, dict) and obj.get("contents", [])
    if not contents:
        tr.print("  Nothing.")
        return
    for cobj in contents:
        ctpl = ITEM_DEFS[obj_vnum(cobj)]
        tr.print("  " + (cobj.get("short_descr") or ctpl["short_descr"]))


def _look_item(tr, player, args, world):
    """Show an item's description from inventory, room, or equipped slots (cf. 1stMud do_look in act_info.c)."""
    target = " ".join(args)
    rs = world.rooms[player["room"]]
    equipped = [obj for obj in player["equip"].values() if obj is not None]
    result = (get_obj_list(target, player["inv"], ITEM_DEFS)
              or get_obj_list(target, rs["items"], ITEM_DEFS)
              or get_obj_list(target, equipped, ITEM_DEFS))
    if result is None:
        tr.print("You don't see that here.")
        return
    vnum = obj_vnum(result)
    tpl = ITEM_DEFS[vnum]
    inst_desc = isinstance(result, dict) and result.get("description")
    for line in _wrap_paragraphs(inst_desc or tpl.get("description", tpl["short_descr"]), TERMINAL_COLS):
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
        if args[0] in ("in", "i"):
            _look_in(tr, player, args[1:], world)
            return
        # TODO: extend to room extra_descs, mob descriptions, and item extra_descs on other targets
        _look_item(tr, player, args, world)
        return
    room = ROOM_DEFS[player["room"]]
    rs = world.rooms[player["room"]]
    automap_on = player.get("flags", PLR_DEFAULTS) & PLR_AUTOMAP
    text_w = TERMINAL_COLS - COMPACT_W - 1 if automap_on else TERMINAL_COLS

    tr.print("{Y" + room["name"] + "{x")

    color = SECTOR_COLORS.get(room.get("sector", "inside"), "")
    desc_lines = _wrap_paragraphs(room["desc"], text_w)

    if automap_on:
        map_lines = build_compact_lines(player, ROOM_DEFS)
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
        tpl = ITEM_DEFS[obj_vnum(obj)]
        flags = item_extra_flags(obj, tpl)
        flag_str = ""
        if flags.get("invis"):  flag_str += "({cInvis{x) "
        if flags.get("glow"):   flag_str += "({YGlowing{x) "
        if flags.get("hum"):    flag_str += "({CHumming{x) "
        if flags.get("magic"):  flag_str += "({MMagical{x) "
        inst_desc = isinstance(obj, dict) and obj.get("description")
        line = flag_str + "{Y" + (inst_desc or tpl.get("description") or tpl["short_descr"]) + "{x"
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
        inst = world.chars[mob_id]
        tpl = MOB_DEFS[inst["tpl"]]
        # Build AFF prefix string (cf. 1stMud show_char_to_char_0, act_info.c:191-214)
        # Race defaults merged into inst at create_mobile; dynamic spell AFF bits
        # from inst["affects"] are not yet tracked here.
        aff = inst.get("aff_flags", {})
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
        if inst["fighting"] is None:
            line = tpl.get("long_descr") or tpl["short_descr"]
        else:
            name = tpl["short_descr"]
            name = upper(name) if name else name
            if inst["fighting"] == player["id"]:
                line = "%s is here, fighting YOU!" % name
            else:
                line = "%s is here, fighting someone." % name
        tr.print("%s{M%s{x" % (prefix, line))


_SCORE_INNER = TERMINAL_COLS - 2
_SCORE_LEFT  = (TERMINAL_COLS - 7) // 2
_SCORE_RIGHT = TERMINAL_COLS - 7 - _SCORE_LEFT
_SCORE_SEP_OUTER = "{W+" + "-" * _SCORE_INNER + "+{x"
_SCORE_SEP_INNER = "{W+" + "-" * (_SCORE_LEFT + 2) + "+" + "-" * (_SCORE_RIGHT + 2) + "+{x"
# full-width AC bar: (_SCORE_INNER-2) content chars minus 6(label)+2(': ')+5(val)+2(' [')+1(']')
# Minus 2 chars for precise colour segment lengths
_AC_BAR_W = _SCORE_INNER - 18 - 2
_PERCENT_BAR_COLORS = ('r', 'R', 'y', 'Y', 'g', 'G', 'W')


def _make_percent_bar(val, max_val, length):
    """Colour-gradient fill bar of | chars (cf. 1stMud make_percent_bar in act_info.c).

    Args:
        val (int): Filled amount (0..max_val). Values <= 0 render empty bar.
        max_val (int): Scale maximum.
        length (int): Bar width in visible characters.

    Returns:
        str: String of exactly `length` visible chars with embedded {X color codes.
    """
    cm = len(_PERCENT_BAR_COLORS) - 1
    mod = max_val // length
    count = 0
    cp = 0
    parts = []
    for i in range(length):
        if i % cm == 0:
            parts.append('{' + _PERCENT_BAR_COLORS[cp])
            cp += 1
            if cp > cm:
                cp = 0
        if val > count:
            parts.append('|')
        else:
            parts.append(' ')
        count += mod
    return ''.join(parts)


def do_score(tr, player, args, world):
    """Display the character score sheet (cf. 1stMud dlm_score in act_info.c)."""
    # two-column box mirroring 1stMud dlm_score layout, with bright/normal colours
    # alternating between horizontal segments.
    def _row(l, r):
        lpad = ' ' * (_SCORE_LEFT  - color_len(l))
        rpad = ' ' * (_SCORE_RIGHT - color_len(r))
        return "{W|{x " + l + lpad + " {W|{x " + r + rpad + " {W|{x"
    def _stat(name, val):
        # [perm/curr] -- identical until affect system is added
        return '{c' + '{:<13}'.format(name) + ': [{w' + '{:2d}/{:2d}'.format(val, val) + '{c]{x'
    def _val_l(name, v, bright=False):
        nc = '{C' if bright else '{c'
        # values stay as dim white
        vc = '{w'
        return nc + '{:<13}'.format(name) + ': [' + vc + '{:>10}'.format(v) + nc + ' ]{x'
    def _val_r(name, v, bright=False):
        nc = '{C' if bright else '{c'
        # values stay as dim white
        vc = '{w'
        return nc + '{:<13}'.format(name) + ': [' + vc + '{:>11}'.format(v) + nc + ' ]{x'

    def _ac_row(label, val):
        bar = _make_percent_bar(-val, 1000, _AC_BAR_W)
        content = '{c' + '{:<6}'.format(label) + ' {W:  {w' + '{:5d}'.format(val) + ' {c[' + bar + '{c]'
        return '{W|{x ' + content + ' {W|{x'

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
        _row(
            _stat("Strength", get_curr_stat(p, "str")),
            _val_r("Level", p["level"])
        ),
        _row(
            _stat("Intelligence", get_curr_stat(p, "int")),
            _val_r("Thac0", thac0)
        ),
        _row(
            _stat("Wisdom", get_curr_stat(p, "wis")),
            _val_r("Practices", p.get("practice", 0)),
        ),
        _row(
            _stat("Dexterity", get_curr_stat(p, "dex")),
            _val_r("Trains", p.get("train", 0)),
        ),
        _row(
            _stat("Constitution", get_curr_stat(p, "con")),
            ""
        ),
        _SCORE_SEP_INNER,
        _row(
            "{CHit          : [{R"
            + "{:5d}".format(p["hp"])
            + "{C/{R"
            + "{:5d}".format(p["hp_max"])
            + "{C]{x",
            _val_r("Hitroll", get_hitroll(p), bright=True),
        ),
        _row(
            "{CMana         : [{M"
            + "{:5d}".format(p["mp"])
            + "{C/{M"
            + "{:5d}".format(p["mp_max"])
            + "{C]{x",
            _val_r("Damroll", get_damroll(p), bright=True),
        ),
        _row(
            _val_l("Exp", p["xp"], bright=True),
            _val_r("Age", age, bright=True)
        ),
        _row(
            _val_l("To Lvl", p["xp_next"] - p["xp"], bright=True),
            _val_r("Hours", hours, bright=True),
        ),
        _row(
            _val_l("Silver", p["silver"], bright=True),
            _val_r("Position", p["pos"], bright=True),
        ),
        _row(
            _val_l("Gold", p["gold"], bright=True),
            ""
        ),
        _SCORE_SEP_OUTER,
        _ac_row("Pierce", get_armor(p, AC_PIERCE)),
        _ac_row("Bash", get_armor(p, AC_BASH)),
        _ac_row("Slash", get_armor(p, AC_SLASH)),
        _ac_row("Exotic", get_armor(p, AC_EXOTIC)),
        _SCORE_SEP_OUTER,
    ]
    for line in lines:
        tr.print(line)


def _parse_skill_range(tr, args):
    if not args:
        return (False, 1, MAX_MORTAL_LEVEL, True)
    f_all = True
    if args[0].startswith("all"):
        return (f_all, 1, MAX_MORTAL_LEVEL, True)
    try:
        max_lev = int(args[0])
    except ValueError:
        tr.print("Arguments must be numerical or all.")
        return (False, 1, MAX_MORTAL_LEVEL, False)
    if max_lev < 1 or max_lev > MAX_MORTAL_LEVEL:
        tr.print("Levels must be between 1 and {}.".format(MAX_MORTAL_LEVEL))
        return (False, 1, MAX_MORTAL_LEVEL, False)
    min_lev = 1
    if len(args) > 1:
        try:
            min_lev = max_lev
            max_lev = int(args[1])
        except ValueError:
            tr.print("Arguments must be numerical or all.")
            return (False, 1, MAX_MORTAL_LEVEL, False)
        if max_lev < 1 or max_lev > MAX_MORTAL_LEVEL:
            tr.print("Levels must be between 1 and {}.".format(MAX_MORTAL_LEVEL))
            return (False, 1, MAX_MORTAL_LEVEL, False)
        if min_lev > max_lev:
            tr.print("That would be silly.")
            return (False, 1, MAX_MORTAL_LEVEL, False)
    return (f_all, min_lev, max_lev, True)


def _pad_color(s, width):
    return s + " " * max(0, width - color_len(s))


def _print_level_lists(tr, player, args, want_spells):
    f_all, min_lev, max_lev, ok = _parse_skill_range(tr, args)
    if not ok:
        return
    rows = {}
    found = False
    learned = player.get("learned", {})
    for sn, sk in SKILL_TABLE:
        level = skill_level(player, sn)
        if (level < MAX_MORTAL_LEVEL + 1
                and (f_all or level <= player.get("level", 1))
                and min_lev <= level <= max_lev
                and is_spell(sn) == want_spells
                and (not want_spells or is_runtime_spell(sn))
                and learned.get(sn, 0) > 0):
            found = True
            if want_spells:
                if player.get("level", 1) < level:
                    item = "{c" + _pad_color(sk["name"], 18) + " n/a      "
                else:
                    item = "{c" + _pad_color(sk["name"], 18) + " {W%3d mana  " % spell_mana(player, sn)
            elif player.get("level", 1) < level:
                item = "{c" + _pad_color(sk["name"], 18) + " n/a      "
            else:
                item = "{c" + _pad_color(sk["name"], 18) + " {W%3d%%      " % learned.get(sn, 0)
            if level not in rows:
                rows[level] = []
            rows[level].append(item)
    if not found:
        tr.print("{cNo " + ("spells" if want_spells else "skills") + " found.{x")
        return
    for level in range(MAX_MORTAL_LEVEL + 1):
        items = rows.get(level)
        if not items:
            continue
        for i in range(0, len(items), 2):
            prefix = "{cLevel {W%2d{c: " % level if i == 0 else "{x          "
            line = prefix + items[i]
            if i + 1 < len(items):
                line += items[i + 1]
            tr.print(line + "{x")


def print_practice_table(tr, player):
    """Print learned practice percentages (cf. 1stMud do_practice in act_info.c)."""
    items = []
    half = TERMINAL_COLS // 2
    name_w = 18
    learned = player.get("learned", {})
    for sn, sk in SKILL_TABLE:
        pct = learned.get(sn, 0)
        if can_use_skill_spell(player, sn) and pct > 0:
            items.append("{:<{}} {:3d}%".format(sk["name"][:name_w], name_w, pct))
    for i in range(0, len(items), 2):
        line = items[i]
        if i + 1 < len(items):
            line = line + " " * (half - len(line)) + items[i + 1]
        tr.print(line)


def do_skills(tr, player, args, world):
    """List known skills by level (cf. 1stMud do_skills in skills.c)."""
    _print_level_lists(tr, player, args, False)


def do_spells(tr, player, args, world):
    """List known spells by level (cf. 1stMud do_spells in skills.c)."""
    _print_level_lists(tr, player, args, True)


def do_help(tr, player, args, world):
    tr.print("Move: 2/8=n/s  4/6=w/e  7/9=u/d (or n/s/e/w/u/d)")
    tr.print("5=look  i=inv  wear  remove  eat  quaff  recite  zap")
    tr.print("brandish  st=stats  sk=skills  k/kill=fight  kick")
    tr.print("cast <spell>  flee  save  credits  q=quit")


def do_map(tr, player, args, world):
    """Print a full-size automap of rooms reachable from the current room (cf. 1stMud do_map in automap.c).

    Args:
        tr: Terminal renderer.
        player (dict): Player state dict.
    """
    # [TODO blind] 1stMud checks check_blind(ch) here and refuses if AFF_BLIND -- add when blindness is implemented
    for line in build_full_lines(player, ROOM_DEFS):
        tr.print(line)


def do_affects(tr, player, args, world):
    """List all active player affects with name, location, modifier, duration (cf. 1stMud do_affects in act_info.c).

    Args:
        tr: Terminal instance.
        player (dict): Player state dict.
        args (list): Unused.
        world (dict): Game world state (keys: rooms, mobs, areas); unused.
    """
    affects = player.get("affect_list", [])
    if not affects:
        tr.print("You are not affected by any spells.")
        return
    tr.print("You are affected by:")
    for aff in affects:
        sn = aff.get("type")
        sk = SKILLS.get(sn)
        name = sk["name"] if sk else "unknown"
        mod = aff["modifier"]
        dur = aff["duration"]
        dur_str = "permanent" if dur < 0 else "{} tick{}".format(dur, "" if dur == 1 else "s")
        tr.print("  {}: modifies {} by {:+d} for {}".format(
            name, aff["location"], mod, dur_str))


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
