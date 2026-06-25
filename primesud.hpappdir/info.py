"""Information and room-view command handlers."""

import world
from actor import get_hitroll, get_damroll, get_armor, get_curr_stat, is_name
from automap import build_compact_lines, build_full_lines, COMPACT_W
from colors import color_len, upper, draw_line
from combat import _get_thac0
from config import (TERMINAL_COLS, EXIT_ORDER, EXIT_NAMES, SECTOR_COLORS,
                    MAX_MORTAL_LEVEL,
                    AC_PIERCE, AC_BASH, AC_SLASH, AC_EXOTIC)
from item import get_obj_list, obj_vnum, item_extra_flags
from player import PLR_AUTOMAP, PLR_DEFAULTS
from skill_utils import can_use_skill_spell, is_spell, is_runtime_spell, skill_level, \
    spell_mana
from skills_table import SKILL_TABLE, SKILLS
from terminal import tprint
from util import free_mem, gc_collect
from world import ROOM_DEFS, ITEM_DEFS, MOB_DEFS


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
    # TODO: PLR_AUTODAMAGE "autodamage" - damage amounts in combat
    # TODO: PLR_AUTOASSIST "autoassist" - auto-assist group members
    # TODO: PLR_AUTOEXIT "autoexit" - exits in room descriptions
    # TODO: PLR_AUTOGOLD "autogold" - auto-loot gold from corpses
    # TODO: PLR_AUTOLOOT "autoloot" - auto-loot objects from corpses
    # TODO: PLR_AUTOSAC "autosac" - auto-sacrifice corpses
    # TODO: PLR_AUTOSPLIT "autosplit" - auto-split gold in group
    # TODO: PLR_AUTOPROMPT "autoprompt" - selective prompt display
    # TODO: COMM_COMPACT "compact" - compact output (comm flags)
    # TODO: COMM_PROMPT "prompt" - prompt display (comm flags)
    # TODO: COMM_GPROMPT "gprompt" - group prompt (comm flags)
    # TODO: COMM_COMBINE "combine" - combine duplicate objects (comm flags)
    # TODO: PLR_CANLOOT "noloot" - prevent corpse looting (inverted flag)
    # TODO: PLR_NOSUMMON "nosummon" - block summoning
    # TODO: PLR_NOFOLLOW "nofollow" - block following
    # TODO: COMM_NOPRETITLE "nopretitles" - hide pretitles (comm flags)
)


def do_automap(player, args):
    player["flags"] = player.get("flags", PLR_DEFAULTS) ^ PLR_AUTOMAP
    if player["flags"] & PLR_AUTOMAP:
        tprint("You now see an automap in room descriptions.")
    else:
        tprint("You no longer see automap room descriptions.")


def do_autolist(player, args):
    """Display toggle settings (cf. 1stMud do_autolist in act_info.c)."""
    tprint(" %-9s %-6s{w %s" % ("Command", "Status", "Description"))
    tprint(draw_line())
    flags = player.get("flags", PLR_DEFAULTS)
    for bit, name, desc in _FLAG_TABLE:
        status = "ON" if flags & bit else "OFF"
        tprint("{G%-11s {W%-6s{w %s{x" % (name, status, desc))
    tprint(draw_line())


_CONTAINER_TYPES = ("npc_corpse", "pc_corpse", "container")


def _look_in(player, args):
    """Show contents of a container in room or inventory (cf. 1stMud do_look 'in' case in act_info.c)."""
    if not args:
        tprint("Look in what?")
        return
    keyword = " ".join(args)
    rs = world.rooms[player["room"]]
    obj = get_obj_list(keyword, rs["items"], ITEM_DEFS)
    if obj is None:
        obj = get_obj_list(keyword, player["inv"], ITEM_DEFS)
    if obj is None:
        tprint("You do not see that here.")
        return
    tpl = ITEM_DEFS[obj_vnum(obj)]
    if tpl.get("type") not in _CONTAINER_TYPES:
        tprint("That is not a container.")
        return
    obj_name = (isinstance(obj, dict) and obj.get("short_descr")) or tpl["short_descr"]
    tprint("{} holds:".format(obj_name))
    contents = isinstance(obj, dict) and obj.get("contents", [])
    if not contents:
        tprint("  Nothing.")
        return
    for cobj in contents:
        ctpl = ITEM_DEFS[obj_vnum(cobj)]
        tprint("  " + (cobj.get("short_descr") or ctpl["short_descr"]))


def _look_item(player, args):
    """Show an item's description from inventory, room, or equipped slots (cf. 1stMud do_look in act_info.c)."""
    target = " ".join(args)
    rs = world.rooms[player["room"]]
    equipped = [obj for obj in player["equip"].values() if obj is not None]
    result = (get_obj_list(target, player["inv"], ITEM_DEFS)
              or get_obj_list(target, rs["items"], ITEM_DEFS)
              or get_obj_list(target, equipped, ITEM_DEFS))
    if result is None:
        tprint("You don't see that here.")
        return
    vnum = obj_vnum(result)
    tpl = ITEM_DEFS[vnum]
    inst_desc = isinstance(result, dict) and result.get("description")
    for line in _wrap_paragraphs(inst_desc or tpl.get("description", tpl["short_descr"]), TERMINAL_COLS):
        tprint(line)
    for ed in tpl.get("extra_descs", []):
        if is_name(target, ed.get("keywords", "")):
            for line in _wrap_paragraphs(ed.get("desc", ""), TERMINAL_COLS):
                tprint(line)


def do_look(player, args):
    """Display the current room or examine an item (cf. 1stMud do_look in act_info.c).

    Args:
        player (dict): Player state dict.
        args (list): Parsed command arguments; non-empty triggers item look.
    """
    if args:
        if args[0] in ("in", "i"):
            _look_in(player, args[1:])
            return
        # TODO: extend to room extra_descs, mob descriptions, and item extra_descs on other targets
        _look_item(player, args)
        return
    room = ROOM_DEFS[player["room"]]
    rs = world.rooms[player["room"]]
    automap_on = player.get("flags", PLR_DEFAULTS) & PLR_AUTOMAP
    text_w = TERMINAL_COLS - COMPACT_W - 1 if automap_on else TERMINAL_COLS

    tprint("{Y" + room["name"] + "{x")

    color = SECTOR_COLORS.get(room.get("sector", "inside"), "")
    desc_lines = _wrap_paragraphs(room["desc"], text_w)

    if automap_on:
        map_lines = build_compact_lines(player, ROOM_DEFS)
        n = max(len(map_lines), len(desc_lines))
        for i in range(n):
            ml = map_lines[i] if i < len(map_lines) else ' ' * COMPACT_W
            tl = desc_lines[i] if i < len(desc_lines) else ''
            tprint(ml + ' ' + color + tl)
    else:
        for tl in desc_lines:
            tprint(color + tl)

    exits = " ".join(
        EXIT_NAMES.get(d, d) for d in EXIT_ORDER
        if d in room["exits"] and not (isinstance(room["exits"][d], dict) and room["exits"][d].get("closed"))
    )
    exit_string = "[Exits: {}]".format(exits) if exits else "[Exits: none]"
    tprint("{g" + exit_string + "{x")
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
        tprint(stack_prefix + line)
    # Mobs: one per line, long_descr at idle or constructed position string (cf. 1stMud show_char_to_char_0 in act_info.c)
    for mob_id in live_mobs:
        inst = world.chars[mob_id]
        tpl = MOB_DEFS[inst["tpl"]]
        # Build AFF prefix string (cf. 1stMud show_char_to_char_0, act_info.c:191-214)
        # Race defaults merged into inst at create_mobile; dynamic spell AFF bits
        # from inst["affects"] are not yet tracked here.
        aff = inst.get("affected_by", {})
        prefix = ""
        if aff.get("invisible"):    prefix += "({cInvis{x) "
        if aff.get("hide"):         prefix += "({DHide{x) "
        if aff.get("charm"):        prefix += "({MCharmed{x) "
        if aff.get("pass_door"):    prefix += "({cTranslucent{x) "
        if aff.get("faerie_fire"):  prefix += "({MPink Aura{x) "
        mob_align = tpl.get("alignment", 0)
        p_aff = player.get("affected_by", {})
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
        tprint("%s{M%s{x" % (prefix, line))


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


def do_score(player, args):
    """Display the character score sheet (cf. 1stMud dlm_score in act_info.c)."""
    # two-column box mirroring 1stMud dlm_score layout, with bright/normal colours
    # alternating between horizontal segments.
    def _row(l, r):
        lpad = ' ' * (_SCORE_LEFT  - color_len(l))
        rpad = ' ' * (_SCORE_RIGHT - color_len(r))
        return "{W|{x " + l + lpad + " {W|{x " + r + rpad + " {W|{x"
    def _stat(name, perm, curr):
        return '{c' + '{:<13}'.format(name) + ': [{w' + '{:2d}/{:2d}'.format(perm, curr) + '{c]{x'
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
    ps = p["perm_stat"]
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
            _stat("Strength", ps["str"], get_curr_stat(p, "str")),
            _val_r("Level", p["level"])
        ),
        _row(
            _stat("Intelligence", ps["int"], get_curr_stat(p, "int")),
            _val_r("Thac0", thac0)
        ),
        _row(
            _stat("Wisdom", ps["wis"], get_curr_stat(p, "wis")),
            _val_r("Practices", p.get("practice", 0)),
        ),
        _row(
            _stat("Dexterity", ps["dex"], get_curr_stat(p, "dex")),
            _val_r("Trains", p.get("train", 0)),
        ),
        _row(
            _stat("Constitution", ps["con"], get_curr_stat(p, "con")),
            ""
        ),
        _SCORE_SEP_INNER,
        _row(
            "{CHit          : [{R"
            + "{:5d}".format(p["hit"])
            + "{C/{R"
            + "{:5d}".format(p["max_hit"])
            + "{C]{x",
            _val_r("Hitroll", get_hitroll(p), bright=True),
        ),
        _row(
            "{CMana         : [{M"
            + "{:5d}".format(p["mana"])
            + "{C/{M"
            + "{:5d}".format(p["max_mana"])
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
        tprint(line)


def _parse_skill_range(args):
    if not args:
        return (False, 1, MAX_MORTAL_LEVEL, True)
    f_all = True
    if args[0].startswith("all"):
        return (f_all, 1, MAX_MORTAL_LEVEL, True)
    try:
        max_lev = int(args[0])
    except ValueError:
        tprint("Arguments must be numerical or all.")
        return (False, 1, MAX_MORTAL_LEVEL, False)
    if max_lev < 1 or max_lev > MAX_MORTAL_LEVEL:
        tprint("Levels must be between 1 and {}.".format(MAX_MORTAL_LEVEL))
        return (False, 1, MAX_MORTAL_LEVEL, False)
    min_lev = 1
    if len(args) > 1:
        try:
            min_lev = max_lev
            max_lev = int(args[1])
        except ValueError:
            tprint("Arguments must be numerical or all.")
            return (False, 1, MAX_MORTAL_LEVEL, False)
        if max_lev < 1 or max_lev > MAX_MORTAL_LEVEL:
            tprint("Levels must be between 1 and {}.".format(MAX_MORTAL_LEVEL))
            return (False, 1, MAX_MORTAL_LEVEL, False)
        if min_lev > max_lev:
            tprint("That would be silly.")
            return (False, 1, MAX_MORTAL_LEVEL, False)
    return (f_all, min_lev, max_lev, True)


def _pad_color(s, width):
    return s + " " * max(0, width - color_len(s))


def _print_level_lists(player, args, want_spells):
    f_all, min_lev, max_lev, ok = _parse_skill_range(args)
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
        tprint("{cNo " + ("spells" if want_spells else "skills") + " found.{x")
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
            tprint(line + "{x")


def print_practice_table(player):
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
        tprint(line)


def do_skills(player, args):
    """List known skills by level (cf. 1stMud do_skills in skills.c)."""
    _print_level_lists(player, args, False)


def do_spells(player, args):
    """List known spells by level (cf. 1stMud do_spells in skills.c)."""
    _print_level_lists(player, args, True)


def do_help(player, args):
    tprint("Move: 2/8=n/s  4/6=w/e  7/9=u/d (or n/s/e/w/u/d)")
    tprint("5=look  i=inv  wear  remove  eat  quaff  recite  zap")
    tprint("brandish  st=stats  sk=skills  k/kill=fight  kick")
    tprint("cast <spell>  flee  save  credits  q=quit")


def do_map(player, args):
    """Print a full-size automap of rooms reachable from the current room (cf. 1stMud do_map in automap.c).

    Args:
        player (dict): Player state dict.
    """
    # [TODO blind] 1stMud checks check_blind(ch) here and refuses if AFF_BLIND -- add when blindness is implemented
    for line in build_full_lines(player, ROOM_DEFS):
        tprint(line)


def do_affects(player, args):
    """List all active player affects with name, location, modifier, duration (cf. 1stMud do_affects in act_info.c).

    Args:
        player (dict): Player state dict.
        args (list): Unused.
    """
    affects = player.get("affect_list", [])
    if not affects:
        tprint("You are not affected by any spells.")
        return
    tprint("You are affected by:")
    for aff in affects:
        sn = aff.get("type")
        sk = SKILLS.get(sn)
        name = sk["name"] if sk else "unknown"
        mod = aff["modifier"]
        dur = aff["duration"]
        dur_str = "permanent" if dur < 0 else "{} tick{}".format(dur, "" if dur == 1 else "s")
        tprint("  {}: modifies {} by {:+d} for {}".format(
            name, aff["location"], mod, dur_str))


def do_credits(player, args):
    tprint("{WPrimeSUD{x -- a single-user dungeon for the HP Prime")
    tprint("Port by ZechyW.  Not for commercial distribution.")
    tprint("")
    tprint("{W1stMud ROM Derivative{x")
    tprint("  {c(c) 2001-2003 Ryan Jennings (Markanth){x")
    tprint("  markanth@firstmud.com")
    tprint("")
    tprint("{WROM 2.4 beta{x")
    tprint("  {c(c) 1993-1998 Russ Taylor{x")
    tprint("  rtaylor@hypercube.org")
    tprint("")
    tprint("{WMerc 2.1{x")
    tprint("  {c(c) 1992-1993 Michael Chastain  mec@shell.portal.com{x")
    tprint("            Michael Quan       michael@uclink.berkeley.edu")
    tprint("            Mitchell Tse       hatchet@uclink.berkeley.edu")
    tprint("")
    tprint("{WDikuMud{x -- creators of the original game")
    tprint("  {c(c) 1990-1991 Sebastian Hammer       quinn@freja.diku.dk{x")
    tprint("            Michael Seifert        seifert@freja.diku.dk")
    tprint("            Hans Henrik Staerfeldt bombman@freja.diku.dk")
    tprint("            Tom Madsen             noop@freja.diku.dk")
    tprint("            Katja Nyboe            katz@freja.diku.dk")
    tprint("  DIKU, Computer Science Institute, Copenhagen University")
