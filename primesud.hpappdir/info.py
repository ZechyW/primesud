"""Information and room-view command handlers."""

import world
from handler import (get_hitroll, get_damroll, get_armor, get_curr_stat, is_name,
                   get_char_room, mob_condition, is_good, is_evil, can_see,
                   number_argument as _number_argument)
from automap import build_compact_lines, build_full_lines, COMPACT_W
from classes import class_long, class_short
from colors import color_len, upper, draw_line
from combat import get_thac0
from config import (TERMINAL_COLS, EXIT_ORDER, EXIT_NAMES, POS_FROM_SHORT, SECTOR_COLORS,
                    MAX_MORTAL_LEVEL, MAX_LEVEL, DIR_ALIASES,
                    AC_PIERCE, AC_BASH, AC_SLASH, AC_EXOTIC,
                    WEAR_LABELS)
from item import get_obj_list, get_obj_here, obj_vnum, item_extra_flags
from picker import pick_from
from player import (PLR_AUTOMAP, PLR_AUTOLOOT, PLR_AUTOSAC, PLR_AUTOGOLD,
                    PLR_AUTOSPLIT, PLR_DEFAULTS)
from skill_utils import can_use_skill_spell, is_spell, is_runtime_spell, skill_level, \
    spell_mana
from skills_table import SKILL_TABLE, SKILLS
from terminal import tprint
from util import free_mem, gc_collect
from world import ROOM_DEFS, ITEM_DEFS, MOB_DEFS
from debug import DBG  # [PRIMESUD]


def _wrap(text, width):
    """Word-wrap a single line of text to the given width. [PRIMESUD]"""
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
    """Word-wrap text, preserving blank-line paragraph breaks from .are descriptions. [PRIMESUD]"""
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
    (PLR_AUTOGOLD, "autogold", "Automatically loots gold from corpses."),
    (PLR_AUTOLOOT, "autoloot", "Automatically loots objects from corpses."),
    (PLR_AUTOSAC, "autosac", "Automatically sacrifices corpses."),
    (PLR_AUTOSPLIT, "autosplit", "Automatically splits gold with group members."),
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
    """Toggle automap display in room descriptions (cf. 1stMud `do_automap` in automap.c)."""
    player["flags"] = player.get("flags", PLR_DEFAULTS) ^ PLR_AUTOMAP
    if player["flags"] & PLR_AUTOMAP:
        tprint("You now see an automap in room descriptions.")
    else:
        tprint("You no longer see automap room descriptions.")


def do_autoloot(player, args):
    """Toggle autoloot (cf. 1stMud do_autoloot in act_info.c)."""
    player["flags"] = player.get("flags", PLR_DEFAULTS) ^ PLR_AUTOLOOT
    if player["flags"] & PLR_AUTOLOOT:
        tprint("You now loot objects from corpses automatically.")
    else:
        tprint("You no longer loot objects from corpses automatically.")


def do_autogold(player, args):
    """Toggle autogold (cf. 1stMud do_autogold in act_info.c)."""
    player["flags"] = player.get("flags", PLR_DEFAULTS) ^ PLR_AUTOGOLD
    if player["flags"] & PLR_AUTOGOLD:
        tprint("You now loot gold from corpses automatically.")
    else:
        tprint("You no longer loot gold from corpses automatically.")


def do_autosac(player, args):
    """Toggle autosac (cf. 1stMud do_autosac in act_info.c)."""
    player["flags"] = player.get("flags", PLR_DEFAULTS) ^ PLR_AUTOSAC
    if player["flags"] & PLR_AUTOSAC:
        tprint("You now sacrifice corpses automatically.")
    else:
        tprint("You no longer automatically sacrifice corpses.")


def do_autosplit(player, args):
    """Toggle autosplit (cf. 1stMud do_autosplit in act_info.c)."""
    player["flags"] = player.get("flags", PLR_DEFAULTS) ^ PLR_AUTOSPLIT
    if player["flags"] & PLR_AUTOSPLIT:
        tprint("You now split gold with group members.")
    else:
        tprint("You no longer split gold with group members.")


def do_autolist(player, args):
    """Display toggle settings (cf. 1stMud do_autolist in act_info.c)."""
    tprint(" %-9s %-6s{w %s" % ("Command", "Status", "Description"))
    tprint(draw_line())
    flags = player.get("flags", PLR_DEFAULTS)
    for bit, name, desc in _FLAG_TABLE:
        status = "ON" if flags & bit else "OFF"
        tprint("{G%-11s {W%-6s{w %s{x" % (name, status, desc))
    tprint(draw_line())


def do_wimpy(player, args):
    """Set the hp threshold below which the player auto-flees in combat (cf. 1stMud do_wimpy in act_info.c).

    Args:
        player (dict): Player state dict.
        args (list): Parsed command words; optional hp value (default max_hit/5).
    """
    if not args:
        wimpy = player["max_hit"] // 5
    else:
        try:
            wimpy = int(args[0])
        except ValueError:
            wimpy = 0  # cf. atoi() -- non-numeric input yields 0
    if wimpy < 0:
        tprint("Your courage exceeds your wisdom.")
        return
    if wimpy > player["max_hit"] // 2:
        tprint("Such cowardice ill becomes you.")
        return
    player["wimpy"] = wimpy
    tprint("Wimpy set to %d hit points." % wimpy)


def _get_ed(name, extra_descs):
    """Find first extra description matching name (cf. 1stMud get_ed in db.c)."""
    for keywords, desc in extra_descs:
        if is_name(name, keywords):
            return desc
    return None


def _show_char_to_char_1(player, mob_id):
    """Show mob description, health condition, and equipment (cf. 1stMud show_char_to_char_1 in act_info.c)."""
    inst = world.chars[mob_id]
    tpl = MOB_DEFS[inst["tpl"]]
    # Instance description overrides template (cf. 1stMud per-char description;
    # set when buying a pet: neck-tag line appended)
    desc = inst.get("description") or tpl.get("description")
    if desc:
        for line in _wrap_paragraphs(desc, TERMINAL_COLS):
            tprint(line)
    else:
        tprint("You see nothing special about them.")
    tprint(mob_condition(inst, tpl))
    found = False
    for slot, label in WEAR_LABELS:
        obj = inst["equip"].get(slot)
        if obj is not None:
            if not found:
                tprint("")
                tprint(upper(tpl["short_descr"]) + " is using:")
                found = True
            ctpl = ITEM_DEFS[obj_vnum(obj)]
            tprint(label + ctpl["short_descr"])


_CONTAINER_TYPES = ("npc_corpse", "pc_corpse", "container")


def _look_in(player, args):
    """Show contents of a container in room or inventory (cf. 1stMud do_look 'in' case in act_info.c)."""
    if not args:
        tprint("Look in what?")
        return
    keyword = " ".join(args)
    rs = world.rooms[player["room"]]
    obj = get_obj_list(keyword, player["inv"], ITEM_DEFS)
    if obj is None:
        obj = get_obj_list(keyword, rs["items"], ITEM_DEFS)
    if obj is None:
        tprint("You do not see that here.")
        return
    tpl = ITEM_DEFS[obj_vnum(obj)]
    if tpl.get("type") not in _CONTAINER_TYPES:
        tprint("That is not a container.")
        return
    _show_container(obj, tpl)


def _show_container(obj, tpl):
    """Print container contents (cf. 1stMud do_look 'in' case in act_info.c)."""
    obj_name = (isinstance(obj, dict) and obj.get("short_descr")) or tpl["short_descr"]
    tprint("{} holds:".format(obj_name))
    contents = isinstance(obj, dict) and obj.get("contents", [])
    if not contents:
        tprint("  Nothing.")
        return
    for cobj in contents:
        ctpl = ITEM_DEFS[obj_vnum(cobj)]
        tprint("  " + (cobj.get("short_descr") or ctpl["short_descr"]))


def _look_scan_items(target, number, count, items):
    """Scan an item list for extra_desc or name match (cf. 1stMud `do_look` in act_info.c: item scan loop).

    Returns:
        tuple: (found, count) where found is True if the Nth match was displayed.
    """
    for obj in items:
        vnum = obj_vnum(obj)
        tpl = ITEM_DEFS[vnum]
        pdesc = _get_ed(target, tpl.get("extra_descs", []))
        if pdesc is not None:
            count += 1
            if count == number:
                for line in _wrap_paragraphs(pdesc, TERMINAL_COLS):
                    tprint(line)
                return True, count
            continue
        if is_name(target, tpl.get("keywords", "")):
            count += 1
            if count == number:
                inst_desc = isinstance(obj, dict) and obj.get("description")
                for line in _wrap_paragraphs(
                        inst_desc or tpl.get("description", tpl["short_descr"]),
                        TERMINAL_COLS):
                    tprint(line)
                return True, count
    return False, count


def do_exits(player, args):
    """List obvious exits with destination room names (cf. 1stMud do_exits in act_info.c).

    Args:
        player (dict): Player state dict.
        args (list): Parsed command arguments (unused).
    """
    # [PRIMESUD] "auto" form not ported (autoexit uses its own line in do_look);
    # check_blind / can_see_room stubbed; immortal room-vnum suffix not ported
    tprint("Obvious exits:")
    found = False
    exits = world.rooms[player["room"]]["exits"]
    for d in EXIT_ORDER:
        ev = exits.get(d)
        if ev is None:
            continue
        if isinstance(ev, dict):
            if ev.get("closed"):
                continue
            to = ev["to"]
        else:
            to = ev
        if to not in world.rooms:
            continue
        found = True
        # [PRIMESUD] room_is_dark not ported -- 1stMud shows "Too dark to tell"
        name = EXIT_NAMES.get(d, d)
        tprint("%-5s - %s" % (upper(name), world.rooms[to]["name"]))
    if not found:
        tprint("None.")


# Position display strings (cf. 1stMud show_char_to_char_0 in act_info.c)
# [PRIMESUD] furniture ("sleeping on X") variants not ported
_POS_LINES = {
    "dead":     " is DEAD!!",
    "mortal":   " is mortally wounded.",
    "incap":    " is incapacitated.",
    "stunned":  " is lying here stunned.",
    "sleeping": " is sleeping here.",
    "resting":  " is resting here.",
    "sitting":  " is sitting here.",
    "standing": " is here.",
}


def do_look(player, args):
    """Display the current room, examine a target, or look in a direction (cf. 1stMud do_look in act_info.c).

    Args:
        player (dict): Player state dict.
        args (list): Parsed command arguments; non-empty triggers targeted look.
    """
    if args:
        if args[0] in ("in", "i", "on"):
            _look_in(player, args[1:])
            return

        arg1 = args[0]
        number, target = _number_argument(arg1)
        rs = world.rooms[player["room"]]

        mob_id = get_char_room(arg1, rs["mobs"], world.chars, player)
        if mob_id is not None:
            _show_char_to_char_1(player, mob_id)
            return

        count = 0
        # Inventory + equipped (cf. 1stMud carrying_first which includes worn)
        equipped = [o for o in player["equip"].values() if o is not None]
        found, count = _look_scan_items(target, number, count,
                                        player["inv"] + equipped)
        if found:
            return
        # Room items
        found, count = _look_scan_items(target, number, count, rs["items"])
        if found:
            return

        # Room extra_descs (cf. 1stMud do_look line 1309)
        room = ROOM_DEFS[player["room"]]
        pdesc = _get_ed(target, room.get("extra_descs", []))
        if pdesc is not None:
            count += 1
            if count == number:
                for line in _wrap_paragraphs(pdesc, TERMINAL_COLS):
                    tprint(line)
                return

        if count > 0 and count != number:
            if count == 1:
                tprint("You only see one %s here." % target)
            else:
                tprint("You only see %d of those here." % count)
            return

        # Direction look (cf. 1stMud do_look lines 1330-1362)
        door = DIR_ALIASES.get(arg1)
        if door is None:
            tprint("You do not see that here.")
            return
        exits = room["exits"]
        if door not in exits:
            tprint("Nothing special there.")
            return
        ex = exits[door]
        if isinstance(ex, dict):
            ex_desc = ex.get("desc")
            if ex_desc:
                for line in _wrap_paragraphs(ex_desc, TERMINAL_COLS):
                    tprint(line)
            else:
                tprint("Nothing special there.")
            kw = ex.get("keyword", "")
            if kw and kw[0] != ' ':
                if ex.get("closed"):
                    tprint("The %s is closed." % kw)
                elif ex.get("isdoor"):
                    tprint("The %s is open." % kw)
        else:
            tprint("Nothing special there.")
        return
    room = ROOM_DEFS[player["room"]]
    rs = world.rooms[player["room"]]
    automap_on = player.get("flags", PLR_DEFAULTS) & PLR_AUTOMAP
    text_w = TERMINAL_COLS - COMPACT_W - 1 if automap_on else TERMINAL_COLS

    show_vnums = "vnum" in DBG  # [PRIMESUD] debug vnum visibility toggle
    if show_vnums:
        tprint("{Y" + room["name"] + " {D[" + str(player["room"]) + "]{x")
    else:
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
        if show_vnums:  # [PRIMESUD]
            line += " {D[" + str(obj_vnum(obj)) + "]{x"
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
        # cf. 1stMud show_char_to_char: skip chars the viewer can't see
        if not can_see(player, inst):
            continue
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
        p_aff = player.get("affected_by", {})
        if is_evil(inst) and p_aff.get("detect_evil"):   prefix += "({RRed Aura{x) "
        if is_good(inst) and p_aff.get("detect_good"):   prefix += "({YGolden Aura{x) "
        if aff.get("sanctuary"):    prefix += "({WWhite Aura{x) "
        # cf. 1stMud: long_descr only when mob is at its start_pos
        pos = inst.get("pos", "standing")
        start_pos = POS_FROM_SHORT.get(tpl.get("start_pos", "stand"), "standing")
        if pos == start_pos and inst["fighting"] is None and tpl.get("long_descr"):
            line = tpl["long_descr"]
        else:
            name = tpl["short_descr"]
            name = upper(name) if name else name
            if inst["fighting"] is not None or pos == "fighting":
                if inst["fighting"] == player["id"]:
                    line = "%s is here, fighting YOU!" % name
                else:
                    # [PRIMESUD] 1stMud shows the target's name; mobs only
                    # fight the player or each other's ids -- resolve if present
                    tgt = world.chars.get(inst["fighting"])
                    if tgt is None:
                        line = "%s is here, fighting thin air??" % name
                    else:
                        line = "%s is here, fighting %s." % (
                            name, MOB_DEFS[tgt["tpl"]]["short_descr"])
            else:
                line = name + _POS_LINES.get(pos, " is here.")
        if show_vnums:  # [PRIMESUD] template vnum; instance id via debug stat mob
            line += " {D[" + str(inst["tpl"]) + "]"
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
    thac0 = get_thac0(p)
    # full names if they fit the value cell, 4-char forms otherwise (multiclass)
    cls_name = class_long(p)
    if len(cls_name) > 11:
        cls_name = class_short(p)
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
            _val_r("Class", cls_name),
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
            "{CMovement     : [{G"
            + "{:5d}".format(p.get("move", 100))
            + "{C/{G"
            + "{:5d}".format(p.get("max_move", 100))
            + "{C]{x",
            "",
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
    """Parse level range arguments for spell/skill list commands. [PRIMESUD]"""
    if not args:
        return (False, 1, MAX_MORTAL_LEVEL, True)
    f_all = True
    # cf. 1stMud !str_prefix(argument, "all"): arg is prefix of "all"
    if "all".startswith(args[0]):
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
    """Right-pad a colour-coded string to the given visible width. [PRIMESUD]"""
    return s + " " * max(0, width - color_len(s))


def _print_level_lists(player, args, want_spells):
    """Print spells or skills grouped by level. [PRIMESUD]"""
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
                    item = "{c" + _pad_color(sk["name"], 16) + " n/a      "
                else:
                    item = "{c" + _pad_color(sk["name"], 16) + " {W%3d mana  " % spell_mana(player, sn)
            elif player.get("level", 1) < level:
                item = "{c" + _pad_color(sk["name"], 16) + " n/a      "
            else:
                item = "{c" + _pad_color(sk["name"], 16) + " {W%3d%%      " % learned.get(sn, 0)
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
            # [PRIMESUD] 1stMud's 29-wide columns overflow 64 cols (68 vis);
            # 16-wide names + stripped tail keep two columns under the wrap.
            tprint(line.rstrip() + "{x")


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


HELP_FILE = "help.dat"  # [PRIMESUD] generated by tools/help_to_primesud.py


def _help_is_name(sstr, namelist):
    """True if every word of sstr prefix-matches a keyword in namelist (cf. 1stMud is_name in handler.c).

    Unlike handler.is_name, tokenizes namelist with quote grouping (so
    'ACID BLAST' is one keyword) and also accepts the whole input string
    as a prefix of any single keyword, matching the upstream algorithm
    used for help lookups.
    """
    from commands import split_args  # late import: commands imports info
    parts = split_args(sstr)
    names = split_args(namelist)
    if not parts or not names:
        return False
    full = sstr.strip().lower()
    for part in parts:
        matched = False
        for name in names:
            if name.startswith(full):
                return True
            if name.startswith(part):
                matched = True
                break
        if not matched:
            return False
    return True


def do_help(player, args):
    """Show a help entry, keyword list, or see-also list (cf. 1stMud do_help in act_info.c).

    [PRIMESUD] Scans HELP_FILE line-by-line instead of an in-memory help
    list -- the full help text (~150KB) will not fit the HP Prime heap.
    Record format: '#<level>|<keywords>' header line, then text lines.
    """
    argall = " ".join(args) if args else "summary"
    number, target = _number_argument(argall)
    trust = player.get("level", 1)
    listing = len(target) == 1  # single-letter arg lists matching keywords
    sep = draw_line("{c-{C-")
    found = False
    printing = False
    count = 0
    matches = []  # list-mode keywords
    related = []  # "See Also" keywords after the shown entry
    f = open(HELP_FILE)
    while True:
        line = f.readline()
        if not line:
            break
        if line[0] == "#":
            if printing:
                tprint(sep)
                printing = False
            level_s, keyword = line[1:].rstrip("\n").split("|", 1)
            if int(level_s) > trust:
                continue
            if not _help_is_name(target, keyword):
                continue
            if listing:
                matches.append(keyword)
                found = True
            else:
                count += 1
                if count == number:
                    tprint(sep)
                    tprint("Help Keywords : %s" % keyword)
                    tprint(sep)
                    printing = True
                    found = True
                elif found:
                    related.append(keyword)
        elif printing:
            tprint(line.rstrip("\n"))
    f.close()
    if printing:
        tprint(sep)
    if matches:
        # [PRIMESUD] 1stMud prints 3 columns; 2 columns fit the 64-col screen
        tprint("Help files that start with the letter '%s'." % target[0].upper())
        tprint(sep)
        half = TERMINAL_COLS // 2
        cells = []
        for i, kw in enumerate(matches):
            cells.append(("%3d) %s" % (i + 1, kw))[:half - 1])
        for i in range(0, len(cells), 2):
            line = cells[i]
            if i + 1 < len(cells):
                line = line + " " * (half - len(line)) + cells[i + 1]
            tprint(line)
        tprint(sep)
        tprint("%d total help files." % len(matches))
    elif not found:
        tprint("No help found for %s. Try using just the first letter." % target)
        # new_wiznet missing-help log: no immortals in single-user [PRIMESUD]
    elif related:
        tprint("See Also : %s." % ", ".join(related))
        tprint(sep)


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
    """Display game credits and acknowledgements (cf. 1stMud `do_credits` in act_info.c)."""
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


def _convert_level(arg):
    """Parse level string to int (cf. 1stMud convert_level in db.c)."""
    if not arg:
        return 0
    if arg.isdigit():
        return int(arg)
    if arg == "imm":
        return MAX_LEVEL
    if arg in ("hero", "hro"):
        return MAX_MORTAL_LEVEL
    return 0


def _print_area_levels(levels):
    """Format area level range for display (cf. 1stMud print_area_levels in db.c)."""
    lo, hi = levels
    if lo >= MAX_MORTAL_LEVEL and hi >= MAX_MORTAL_LEVEL:
        return " HERO+ "
    lo_s = "HRO" if lo >= MAX_MORTAL_LEVEL else "%03d" % lo
    hi_s = "HRO" if hi >= MAX_MORTAL_LEVEL else "%03d" % hi
    return lo_s + " " + hi_s


def _extract_builder(credits):
    """Extract builder name from area credits line (cf. 1stMud convert_area_credits in db2.c)."""
    idx = credits.find("} ")
    if idx >= 0:
        parts = credits[idx + 2:].split()
        if parts:
            return parts[0]
    return credits[:7] if credits else ""


def _compress_path(parent, source, target):
    """Trace BFS parent chain and compress directions (cf. 1stMud path_to_area in act_enter.c)."""
    path = []
    v = target
    while v != source:
        pv, d = parent[v]
        path.append(d)
        v = pv
    path.reverse()
    if not path:
        return ""
    parts = []
    count = 1
    for i in range(1, len(path)):
        if path[i] == path[i - 1]:
            count += 1
        else:
            if count > 1:
                parts.append(str(count))
            parts.append(path[i - 1])
            count = 1
    if count > 1:
        parts.append(str(count))
    parts.append(path[-1])
    return "".join(parts)


def find_area_paths(ch):
    """Single BFS from player room to all areas (cf. 1stMud path_to_area in act_enter.c).

    Returns:
        dict: Mapping of area_tag -> compressed direction string.
    """
    source = ch.get("room")
    if source is None:
        return {}
    source_room = ROOM_DEFS.get(source)
    if source_room is None:
        return {}
    source_area = source_room.get("area")
    found = {}
    dist = {source: 0}
    parent = {}
    queue = [source]
    qi = 0
    while qi < len(queue):
        cur = queue[qi]
        qi += 1
        room = ROOM_DEFS.get(cur)
        if room is None:
            continue
        for d in EXIT_ORDER:
            ev = room.get("exits", {}).get(d)
            if ev is None:
                continue
            to_vnum = ev.get("to") if isinstance(ev, dict) else ev
            if to_vnum is None or to_vnum in dist:
                continue
            to_room = ROOM_DEFS.get(to_vnum)
            if to_room is None:
                continue
            dist[to_vnum] = dist[cur] + 1
            parent[to_vnum] = (cur, d)
            tag = to_room.get("area")
            if tag and tag != source_area and tag not in found:
                found[tag] = _compress_path(parent, source, to_vnum)
            queue.append(to_vnum)
    return found


def _center_fill(text, width=0):
    """Center text with oO fill pattern (cf. 1stMud `do_areas` in db.c: center-fill with oO)."""
    if width <= 0:
        width = TERMINAL_COLS
    vis = color_len(text)
    pad = width - vis
    if pad <= 0:
        return text
    pl = pad // 2
    pr = pad - pl
    lf = ("oO" * (pl // 2 + 1))[:pl]
    rf = ("oO" * (pr // 2 + 1))[:pr]
    return lf + text + rf


def do_areas(player, args):
    """List areas with level ranges, authors, and directions (cf. 1stMud do_areas in db.c)."""
    lo_lv = 0
    hi_lv = 0
    if args:
        lo_lv = _convert_level(args[0])
        if len(args) >= 2:
            hi_lv = _convert_level(args[1])
    if lo_lv > 0:
        lo_lv = max(1, min(lo_lv, MAX_LEVEL))
    else:
        lo_lv = 0
    if hi_lv > 0:
        hi_lv = max(1, min(hi_lv, MAX_LEVEL))
    else:
        hi_lv = MAX_LEVEL

    tprint("")
    tprint("{W" + _center_fill("[ {RAREAS ON PRIMESUD{W ]") + "{x")
    tprint("{YLoading area paths...{x")

    paths = find_area_paths(player)
    source_area = ROOM_DEFS.get(player.get("room"), {}).get("area")

    sorted_areas = sorted(world.AREA_DEFS, key=lambda a: a.get("name", "").lower())

    count = 0
    for area in sorted_areas:
        levels = area.get("levels", (1, MAX_LEVEL))
        lo = max(1, min(levels[0], MAX_LEVEL))
        hi = max(1, min(levels[1], MAX_LEVEL))
        if lo >= lo_lv and hi <= hi_lv:
            lvl_str = _print_area_levels((lo, hi))
            builder = _extract_builder(area.get("credits", ""))
            name = area.get("name", area["tag"])
            tag = area["tag"]
            if tag == source_area:
                dirs = "You are here."
            else:
                dirs = paths.get(tag, "Not accessible.")
            tprint(" {W[{B%-7s{W] {r%-7s {C%-23s {W({M%s{W){x"
                   % (lvl_str, builder, name, dirs))
            count += 1

    if count == 0:
        tprint("{W" + _center_fill("[ {RNo areas meeting those criteria.{W ]") + "{x")
    else:
        tprint("{W" + _center_fill("[ {R" + str(count) + " areas found{W ]") + "{x")
        tprint("All directions are from your current position.")


def do_read(player, args):
    """Alias for do_look (cf. 1stMud do_read in act_info.c)."""
    do_look(player, args)


def do_examine(player, args):
    """Examine an object: look at it, then show contents or coin count (cf. 1stMud do_examine in act_info.c).

    Args:
        player (dict): Player state dict.
        args (list): Parsed command arguments.
    """
    if not args:
        # [PRIMESUD] picker menu when no args (1stMud prints "Examine what?" and stops)
        rs = world.rooms[player["room"]]
        equipped = [o for o in player["equip"].values() if o is not None]
        mobs = list(rs["mobs"])
        objs = list(rs["items"]) + player["inv"] + equipped
        labels = [MOB_DEFS[world.chars[i]["tpl"]]["short_descr"] for i in mobs]
        for o in objs:
            labels.append((isinstance(o, dict) and o.get("short_descr"))
                          or ITEM_DEFS[obj_vnum(o)]["short_descr"])
        if not labels:
            tprint("Examine what?")
            return
        idx = pick_from("Examine what?", labels)
        if idx < 0:
            return
        if idx < len(mobs):
            _show_char_to_char_1(player, mobs[idx])
            return
        obj = objs[idx - len(mobs)]
        tpl = ITEM_DEFS[obj_vnum(obj)]
        inst_desc = isinstance(obj, dict) and obj.get("description")
        for line in _wrap_paragraphs(inst_desc or tpl.get("description", tpl["short_descr"]),
                                     TERMINAL_COLS):
            tprint(line)
        _examine_extras(obj)
        return
    arg = args[0]
    do_look(player, [arg])
    obj = get_obj_here(player, arg)
    if obj is not None:
        _examine_extras(obj)


def _examine_extras(obj):
    """Show money coin counts or container contents after looking at obj (cf. 1stMud do_examine in act_info.c).

    [PRIMESUD] Container contents shown from the resolved obj directly; 1stMud
    re-resolves via do_look "in <arg>", which can match a different object.
    """
    tpl = ITEM_DEFS[obj_vnum(obj)]
    obj_type = tpl.get("type")
    if obj_type == "money":
        silver = obj.get("silver", 0)
        gold = obj.get("gold", 0)
        if silver == 0:
            if gold == 0:
                tprint("Odd...there's no coins in the pile.")
            elif gold == 1:
                tprint("Wow. One gold coin.")
            else:
                tprint("There are " + str(gold) + " gold coins in the pile.")
        elif gold == 0:
            if silver == 1:
                tprint("Wow. One silver coin.")
            else:
                tprint("There are " + str(silver) + " silver coins in the pile.")
        else:
            tprint("There are " + str(gold) + " gold and " + str(silver) + " silver coins in the pile.")
    elif obj_type in _CONTAINER_TYPES:
        _show_container(obj, tpl)
    # 1stMud: ITEM_JUKEBOX -> do_play "list" -- not yet ported
