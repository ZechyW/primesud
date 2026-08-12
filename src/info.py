"""Information and room-view command handlers."""

import terminal
import world
from automap import build_compact_lines, build_full_lines, COMPACT_W
from classes import class_long, class_short
from colors import color_len, color_wrap_full, upper, draw_line
from combat import get_thac0
from config import (TERMINAL_COLS, EXIT_ORDER, EXIT_NAMES, POS_FROM_SHORT,
                    SECTOR_COLORS,
                    MAX_MORTAL_LEVEL, MAX_LEVEL, DIR_ALIASES,
                    AC_PIERCE, AC_BASH, AC_SLASH, AC_EXOTIC,
                    WEAR_LABELS, VERSION)
from debug import DBG, dbg  # [PRIMESUD]
from explored import roomcount, TOP_EXPLORED, _pct2
from game_time import (time_info, day_name, month_name, ordinal_string,
                       weather_report_line, DAYS_IN_WEEK, HOURS_IN_DAY)
from gquest import gq_is_player_target
from handler import (get_hitroll, get_damroll, get_armor, get_curr_stat, is_name,
                     get_char_room, mob_condition, is_good, is_evil, can_see,
                     can_see_obj, room_is_dark, check_blind,
                     act, chprintln, TO_CHAR,
                     number_argument as _number_argument, tpl_flag_affects,
                     PLR_AUTOMAP, PLR_AUTOSKILL, PLR_AUTOLOOT, PLR_AUTOSAC,
                     PLR_AUTOGOLD, PLR_AUTOSPLIT, PLR_AUTOASSIST, PLR_AUTOEXIT,
                     PLR_AUTODAMAGE, PLR_DEFAULTS,
                     COMM_BRIEF, COMM_COMPACT, COMM_SHOW_AFFECTS)
import keyidx  # [PRIMESUD] binary mob keyword/metadata index
from item import (get_obj_here, obj_vnum, item_extra_flags,
                  item_container_flags, liquid_color, liquid_left,
                  liquid_total, liquid_type, obj_short,
                  item_type as _item_type)
from music import do_play
from pager import hpan, tpage
from picker import pick_from, _MAX_OPTS as _PICKER_PAGE
from player import _EQUIP_SAVE_ORDER, set_title
from prime_platform import ticks  # [PRIMESUD] 'debug time' channel timings
from quest import is_quester
from races import RACE_TABLE, race_lookup
from skill_utils import can_use_skill_spell, is_spell, is_runtime_spell, skill_level, \
    spell_mana, get_skill, check_improve
from skills_table import SKILL_TABLE, SKILLS, GSN_PEEK
from urandom import randint
from util import count_str, free_mem, gc_collect, num_str, pad_left, pad_right, zpad
from world import ROOM_DEFS, MOB_DEFS, item_tpl


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
    # [PRIMESUD] Leading "." is the ROM builder no-format marker (protects
    # ASCII art like the vnum-3162 city maps from OLC's format command);
    # honour it here too: emit verbatim, marker line dropped. Upstream
    # chprints raw so the "." shows there; PrimeSUD's 64-col reflow is the
    # deviation that made the guard necessary.
    if text.startswith('.\n'):
        return text.split('\n')[1:]
    lines = []
    for para in text.split('\n\n'):
        flat = ' '.join(para.split())  # [PRIMESUD] collapse whitespace runs (cf. erase_new_lines in automap.c)
        if lines:
            lines.append('')
        lines.extend(_wrap(flat, width))
    return lines


def _print_desc(player, text, width):
    """Print a description, panning oversized verbatim art in place first. [PRIMESUD]

    Wide dot-marked ASCII art (the ROM no-format marker honoured by
    _wrap_paragraphs) is unreadable once hard-wrapped, so offer it to
    pager.hpan first; the column offset the player leaves it at decides
    which window is then printed as the scrollback record.  Narrow art,
    ordinary prose, and non-interactive terminals get offset 0 back and
    print exactly as before.
    """
    lines = _wrap_paragraphs(text, width)
    col = hpan(lines, width)
    if col:
        lines = [ln[col:col + width] for ln in lines]
    for line in lines:
        chprintln(player, line)


def _current_area_def(player):
    """Return current area metadata and tag. [PRIMESUD]"""
    tag = ROOM_DEFS[player["room"]].get("area")
    for area in world.AREA_DEFS:
        if area.get("tag") == tag:
            return area, tag
    return {}, tag


def do_where(player, args):
    """Show area info or matching mob locations (cf. 1stMud do_where in act_info.c).

    [PRIMESUD] No-arg form stops after area info. With an argument, searches
    all matching mobs in the current area for solo quest/gquest utility.
    """
    area, tag = _current_area_def(player)
    if not args:
        # [PRIMESUD] "Recomended" typo in 1stMud fixed; labels re-padded
        # by one to keep the colons aligned
        chprintln(player, "You are in zone   : " + area.get("name", tag))
        if area.get("lvl_comment"):
            chprintln(player, "Recommended Levels: [" + pad_right(area["lvl_comment"], 7) + "]")
        else:
            levels = area.get("levels", (0, 0))
            chprintln(player, "Recommended Levels: [" + zpad(levels[0], 3) + " " + zpad(levels[1], 3) + "]")
        chprintln(player, "Author            : [" + pad_right(area.get("credits", ""), 7) + "]")
        return

    target = args[0]
    rows = []
    # room_vnums exists only once the area is loaded, and the player being
    # in it guarantees that, so every lookup below hits loaded data
    for room_vnum in area.get("room_vnums", []):
        rs = world.rooms.get(room_vnum)
        if rs is None:
            continue
        room = ROOM_DEFS[room_vnum]
        for mob_id in rs.get("mobs", []):
            mob = world.chars.get(mob_id)
            if mob is None:
                continue
            aff = mob["affected_by"]
            if aff.get("hide") or aff.get("sneak") or not can_see(player, mob):
                continue
            tpl = MOB_DEFS[mob["tpl"]]
            if is_name(target, tpl.get("keywords", "")):
                rows.append((mob.get("name") or tpl["short_descr"], room["name"]))
    if not rows:
        act("You didn't find any $T.", player, None, target, TO_CHAR)
        return
    for name, room_name in rows:
        chprintln(player, pad_right(name[:28], 28) + " " + room_name)


_FLAG_TABLE = (
    (PLR_AUTOMAP, "automap", "Map in Room Descriptions"),
    (PLR_AUTODAMAGE, "autodamage", "Displays damage amounts in combat."),
    (PLR_AUTOASSIST, "autoassist", "Auto-assists group members in combat."),
    (PLR_AUTOEXIT, "autoexit", "Displays exits in room descriptions."),
    (PLR_AUTOGOLD, "autogold", "Auto-loots gold from corpses."),
    (PLR_AUTOLOOT, "autoloot", "Auto-loots objects from corpses."),
    (PLR_AUTOSAC, "autosac", "Auto-sacrifices corpses."),
    (PLR_AUTOSKILL, "autoskill", "Auto-attacks with skills and spells."),  # [PRIMESUD]
    (PLR_AUTOSPLIT, "autosplit", "Auto-splits gold between group members."),
    # PLR_AUTOPROMPT "autoprompt": [PRIMESUD] not ported -- the status bar
    # is the prompt and is always visible, so selective display is moot
    (COMM_COMPACT, "compact", "Compacts mud output."),
    # COMM_PROMPT/COMM_GPROMPT "prompt"/"gprompt": [PRIMESUD] not ported --
    # superseded by the always-visible status bar, same reasoning as
    # autoprompt above (closed 19/07/2026 parity sweep)
    # COMM_COMBINE "combine": [PRIMESUD] not ported -- inventory display is
    # already always-combined and a long-form toggle is moot on the 320x240
    # screen (closed 19/07/2026 parity sweep)
    # TODO: PLR_CANLOOT "noloot" - prevent corpse looting (inverted flag)
    # TODO: PLR_NOSUMMON "nosummon" - block summoning
    # TODO: PLR_NOFOLLOW "nofollow" - block following
    # TODO: COMM_NOPRETITLE "nopretitles" - hide pretitles (comm flags)
)


def do_automap(player, args):
    """Toggle automap display in room descriptions (cf. 1stMud `do_automap` in automap.c). [Verified: 04/07/2026]"""
    player["flags"] = player.get("flags", PLR_DEFAULTS) ^ PLR_AUTOMAP
    if player["flags"] & PLR_AUTOMAP:
        chprintln(player, "You now see an automap in room descriptions.")
    else:
        chprintln(player, "You no longer see automap room descriptions.")


def do_autoloot(player, args):
    """Toggle autoloot (cf. 1stMud do_autoloot in act_info.c). [Verified: 04/07/2026]"""
    player["flags"] = player.get("flags", PLR_DEFAULTS) ^ PLR_AUTOLOOT
    if player["flags"] & PLR_AUTOLOOT:
        chprintln(player, "You now loot objects from corpses automatically.")
    else:
        chprintln(player, "You no longer loot objects from corpses automatically.")


def do_autogold(player, args):
    """Toggle autogold (cf. 1stMud do_autogold in act_info.c). [Verified: 04/07/2026]"""
    player["flags"] = player.get("flags", PLR_DEFAULTS) ^ PLR_AUTOGOLD
    if player["flags"] & PLR_AUTOGOLD:
        chprintln(player, "You now loot gold from corpses automatically.")
    else:
        chprintln(player, "You no longer loot gold from corpses automatically.")


def do_autosac(player, args):
    """Toggle autosac (cf. 1stMud do_autosac in act_info.c). [Verified: 04/07/2026]"""
    player["flags"] = player.get("flags", PLR_DEFAULTS) ^ PLR_AUTOSAC
    if player["flags"] & PLR_AUTOSAC:
        chprintln(player, "You now sacrifice corpses automatically.")
    else:
        chprintln(player, "You no longer automatically sacrifice corpses.")


def do_autosplit(player, args):
    """Toggle autosplit (cf. 1stMud do_autosplit in act_info.c). [Verified: 04/07/2026]"""
    player["flags"] = player.get("flags", PLR_DEFAULTS) ^ PLR_AUTOSPLIT
    if player["flags"] & PLR_AUTOSPLIT:
        chprintln(player, "You now split gold with group members.")
    else:
        chprintln(player, "You no longer split gold with group members.")


def do_autoassist(player, args):
    """Toggle autoassist (cf. 1stMud do_autoassist in act_info.c). [Verified: 04/07/2026]"""
    player["flags"] = player.get("flags", PLR_DEFAULTS) ^ PLR_AUTOASSIST
    if player["flags"] & PLR_AUTOASSIST:
        chprintln(player, "You now assist group members in combat.")
    else:
        chprintln(player, "You no longer assist group members in combat.")


def do_autodamage(player, args):
    """Toggle autodamage (cf. 1stMud do_autodamage in act_info.c). [Verified: 04/07/2026]"""
    player["flags"] = player.get("flags", PLR_DEFAULTS) ^ PLR_AUTODAMAGE
    if player["flags"] & PLR_AUTODAMAGE:
        chprintln(player, "You now see damage amounts in combat.")
    else:
        chprintln(player, "You no longer see damage amounts in combat.")


def do_autoexit(player, args):
    """Toggle autoexit (cf. 1stMud do_autoexit in act_info.c). [Verified: 04/07/2026]"""
    player["flags"] = player.get("flags", PLR_DEFAULTS) ^ PLR_AUTOEXIT
    if player["flags"] & PLR_AUTOEXIT:
        chprintln(player, "Exits will now be displayed.")
    else:
        chprintln(player, "Exits will no longer be displayed.")


def do_brief(player, args):
    """Toggle room-description suppression on movement (cf. 1stMud do_brief in act_info.c).

    Brief mode only affects the "auto" look triggered by movement (see
    do_look's "auto" branch below); an explicit `look` always shows the full
    room description regardless of this flag (cf. act_info.c:1144).
    """
    player["flags"] = player.get("flags", PLR_DEFAULTS) ^ COMM_BRIEF
    if player["flags"] & COMM_BRIEF:
        chprintln(player, "You no longer see room descriptions.")
    else:
        chprintln(player, "You now see room descriptions.")


def do_compact(player, args):
    """Toggle compact mode (cf. 1stMud do_compact in act_info.c).

    [PRIMESUD] 1stMud's compact mode suppresses the blank line normally
    printed before an inline telnet prompt (comm.c:1467). PrimeSUD's prompt
    is a persistent status bar (never printed inline), so there is no
    equivalent blank-line seam to gate -- this toggle only flips the flag
    (visible via `autolist`) with no other behavioural effect.
    """
    player["flags"] = player.get("flags", PLR_DEFAULTS) ^ COMM_COMPACT
    if player["flags"] & COMM_COMPACT:
        chprintln(player, "Compact mode set.")
    else:
        chprintln(player, "Compact mode removed.")


def do_show(player, args):
    """Toggle affects display in the score sheet (cf. 1stMud do_show in act_info.c)."""
    player["flags"] = player.get("flags", PLR_DEFAULTS) ^ COMM_SHOW_AFFECTS
    if player["flags"] & COMM_SHOW_AFFECTS:
        chprintln(player, "Affects will now be shown in score.")
    else:
        chprintln(player, "Affects will no longer be shown in score.")


def do_autolist(player, args):
    """Display toggle settings (cf. 1stMud do_autolist in act_info.c). [Verified: 04/07/2026]"""
    chprintln(player, " " + pad_right("Command", 9) + " " + pad_right("Status", 6) + "{w " + "Description")
    chprintln(player, draw_line())
    flags = player.get("flags", PLR_DEFAULTS)
    for bit, name, desc in _FLAG_TABLE:
        status = "ON" if flags & bit else "OFF"
        chprintln(player, "{G" + pad_right(name, 11) + " {W" + pad_right(status, 6) + "{w " + desc + "{x")
    chprintln(player, draw_line())


def do_clear(player, args):
    """Clear the screen (cf. 1stMud do_clear in act_info.c).

    1stMud clear_screen sends VT100 erase codes; [PRIMESUD] the tml layer
    clears the LCD directly.
    """
    terminal.tr.clear()


def show_greeting():
    """Clear the screen and show the title screen with credits. [PRIMESUD]

    Blocks on tr.input until Enter is pressed.  Called at startup
    (primesud.py).
    """
    tr = terminal.tr
    tr.clear()

    mem_part = "{G(Mem. free: " + free_mem() + ")"
    pad = 64 - 23 - len(mem_part) - 1
    # [PRIMESUD] single list batch: one colour-grouped render (terminal
    # print_lines) instead of 20 per-line print calls
    tr.print([
        '{C 8888888b.          d8b' + ' ' * pad + mem_part + '{x',
        "{C 888   Y88b         Y8P                                       {x",
        "{C 888    888                                                   {x",
        "{C 888   d88P 888d888 888 88888b.d88b.   .d88b.                 {x",
        '{C 8888888P"  888P"   888 888 "888 "88b d8P  Y8b                {x',
        "{C 888        888     888 888  888  888 88888888                {x",
        "{C 888        888     888 888  888  888 Y8b.                    {x",
        '{C 888        888     888 888  888  888  "Y8888                 {x',
        "{C                             .d8888b.  888     888 8888888b.  {x",
        '{C                            d88P  Y88b 888     888 888  "Y88b {x',
        "{C                            Y88b.      888     888 888    888 {x",
        '{C                             "Y888b.   888     888 888    888 {x',
        '{C                                "Y88b. 888     888 888    888 {x',
        '{C                                  "888 888     888 888    888 {x',
        "{C                            Y88b  d88P Y88b. .d88P 888  .d88P {x",
        '{C                             "Y8888P"   "Y88888P"  8888888P"  {x',
        "{c      Original DikuMUD by Hans Staerfeldt, Katja Nyboe,       {x",
        "{c      Tom Madsen, Michael Seifert, and Sebastian Hammer       {x",
        "{c      Based on MERC 2.1 code by Hatchet, Furey, and Kahn      {x",
        "{c      ROM 2.4 copyright (c) 1993-1998 Russ Taylor.            {x",
        "{c      1stMud Server copyright (c) 2001-2004, Markanth.        {x",
    ])
    tr.input("                    [Press Enter to start]                     ",
        alpha=False,
    )

    tr.print()


def do_motd(player, args):
    """Show the message of the day help entry (cf. 1stMud do_motd in act_info.c)."""
    do_help(player, ["motd"])


def do_version(player, args):
    """Show the server version and build info (cf. 1stMud do_version in act_info.c).

    [PRIMESUD] Upstream prints "<mudname> is running <mudstring>." plus a
    "Compiled at <date> at <time>." line from C preprocessor macros;
    PrimeSUD has no build/compile step (interpreted on-device, cf.
    docs/PARITY.md), so the version line is adapted to name PrimeSUD's own
    VERSION and 1stMud/ROM lineage, and the compile-timestamp line is
    dropped (no equivalent exists).

    Args:
        player (dict): Player state dict.
        args (list): Parsed command arguments (unused).
    """
    chprintln(player, "PrimeSUD is running PrimeSUD " + VERSION + ", based on 1stMud 4.5.3 / ROM 2.4 beta.")


def do_wimpy(player, args):
    """Set the hp threshold below which the player auto-flees in combat (cf. 1stMud do_wimpy in act_info.c).

    [Verified: 04/07/2026]

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
        chprintln(player, "Your courage exceeds your wisdom.")
        return
    if wimpy > player["max_hit"] // 2:
        chprintln(player, "Such cowardice ill becomes you.")
        return
    player["wimpy"] = wimpy
    chprintln(player, "Wimpy set to " + num_str(wimpy) + " hit points.")


def _get_ed(name, extra_descs):
    """Find first extra description matching name (cf. 1stMud get_ed in db.c). [Verified: 03/07/2026]"""
    for keywords, desc in extra_descs:
        if is_name(name, keywords):
            return desc
    return None


def _show_char_to_char_1(player, mob_id):
    """Show mob description, health condition, equipment, and peek (cf. 1stMud show_char_to_char_1 in act_info.c).

    [Verified: 04/07/2026] -- "$n looks at ..." room/vict acts not ported
    (no other players to notify; mobs ignore them).
    """
    inst = world.chars[mob_id]
    tpl = MOB_DEFS[inst["tpl"]]
    # Instance description overrides template (cf. 1stMud per-char description;
    # set when buying a pet: neck-tag line appended)
    desc = inst.get("description") or tpl.get("description")
    if desc:
        for line in _wrap_paragraphs(desc, TERMINAL_COLS):
            chprintln(player, line)
    else:
        act("You see nothing special about $M.", player, None, inst, TO_CHAR)
    chprintln(player, mob_condition(inst, tpl))
    found = False
    for slot, label in WEAR_LABELS:
        obj = inst["equip"].get(slot)
        if obj is not None:
            if not found:
                chprintln(player, "")
                chprintln(player, upper(inst.get("name") or tpl["short_descr"]) + " is using:")
                found = True
            ctpl = item_tpl(obj)
            chprintln(player, label + obj_short(obj, ctpl))
    # cf. 1stMud peek check (act_info.c:459-465)
    if randint(1, 100) < get_skill(player, GSN_PEEK):
        chprintln(player, "")
        chprintln(player, "You peek at the inventory:")
        check_improve(player, GSN_PEEK, True, 4)
        inv = inst["inv"]
        if not inv:
            chprintln(player, "     Nothing.")
        else:
            # short-descr stacking (cf. 1stMud show_list_to_char fShort=true)
            seen = {}
            order = []
            for obj in inv:
                s = obj_short(obj, item_tpl(obj))
                if s in seen:
                    seen[s] += 1
                else:
                    seen[s] = 1
                    order.append(s)
            for s in order:
                n = seen[s]
                chprintln(player, ("(" + pad_left(num_str(n), 2) + ") " if n > 1 else "     ") + s)


_CONTAINER_TYPES = ("npc_corpse", "pc_corpse", "container")


def _look_in(player, args):
    """Show contents of a container in room or inventory (cf. 1stMud do_look 'in' case in act_info.c).

    [Verified: 19/07/2026]
    """
    if not args:
        chprintln(player, "Look in what?")
        return
    keyword = " ".join(args)
    obj = get_obj_here(player, keyword)  # room, then inventory/equipped
    if obj is None:
        chprintln(player, "You do not see that here.")
        return
    tpl = item_tpl(obj)
    if _item_type(obj, tpl) == "drink":
        # cf. 1stMud do_look 'in' ITEM_DRINK_CON case, act_info.c:1205-1220
        left = liquid_left(obj, tpl)
        if left <= 0:
            chprintln(player, "It is empty.")
            return
        total = liquid_total(obj, tpl)
        if left < total // 4:
            frac = "less than half-"
        elif left < 3 * total // 4:
            frac = "about half-"
        else:
            frac = "more than half-"
        # [PRIMESUD] double space after "with" matches upstream's format
        # string exactly
        chprintln(player, "It's " + frac + "filled with  a "
                  + liquid_color(liquid_type(obj, tpl)) + " liquid.")
        return
    if _item_type(obj, tpl) not in _CONTAINER_TYPES:
        chprintln(player, "That is not a container.")
        return
    # cf. 1stMud do_look 'in' CONT_CLOSED check, act_info.c:1225 (containers
    # and corpses alike)
    if item_container_flags(obj, tpl).get("closed"):
        chprintln(player, "It is closed.")
        return
    _show_container(player, obj, tpl)


def _show_container(player, obj, tpl):
    """Print container contents (cf. 1stMud do_look 'in' case in act_info.c). [Verified: 10/07/2026]"""
    chprintln(player, obj_short(obj, tpl) + " holds:")
    contents = isinstance(obj, dict) and obj.get("contents", [])
    # cf. show_list_to_char's can_see_obj filter (invisible contents hidden)
    visible = [c for c in contents or [] if can_see_obj(player, c)]
    if not visible:
        chprintln(player, "  Nothing.")
        return
    for cobj in visible:
        ctpl = item_tpl(cobj)
        chprintln(player, "  " + (cobj.get("short_descr") or ctpl["short_descr"]))


def _look_scan_items(player, target, number, count, items):
    """Scan an item list for extra_desc or name match (cf. 1stMud `do_look` in act_info.c: item scan loop).

    [Verified: 29/07/2026]

    Returns:
        tuple: (found, count) where found is True if the Nth match was displayed.
    """
    for obj in items:
        # cf. act_info.c:1234/1263 -- both look-item loops gate on can_see_obj
        if not can_see_obj(player, obj):
            continue
        # [PRIMESUD] item_tpl, not ITEM_DEFS[vnum]: the bare subscript loads
        # the owning area for snapshotted foreign gear.
        tpl = item_tpl(obj)
        # Check instance extra_descs first (cf. 1stMud obj->ed_first, act_info.c:1248)
        if isinstance(obj, dict):
            pdesc = _get_ed(target, obj.get("extra_descs", []))
            if pdesc is not None:
                count += 1
                if count == number:
                    _print_desc(player, pdesc, TERMINAL_COLS)
                    return True, count
                continue
        # Then check template extra_descs (cf. 1stMud obj->pIndexData->ed_first, act_info.c:1259)
        pdesc = _get_ed(target, tpl.get("extra_descs", []))
        if pdesc is not None:
            count += 1
            if count == number:
                _print_desc(player, pdesc, TERMINAL_COLS)
                return True, count
            continue
        if is_name(target, tpl.get("keywords", "")):
            count += 1
            if count == number:
                inst_desc = isinstance(obj, dict) and obj.get("description")
                _print_desc(player,
                            inst_desc or tpl.get("description", tpl["short_descr"]),
                            TERMINAL_COLS)
                return True, count
    return False, count


def _count_mob_matches(player, target, mob_ids):
    """Count mobs in mob_ids visible to player whose keywords match target. [PRIMESUD]

    Mirrors get_char_room's per-mob predicate (instance keywords overriding the
    template, can_see gate) so do_look's `N.` counter can span mobs and objects
    as one sequence -- see docs/FIXES.md, do_look N.-prefix counter.

    Returns:
        int: Number of visible matching mobs.
    """
    count = 0
    for mob_id in mob_ids:
        inst = world.chars[mob_id]
        if not can_see(player, inst):
            continue
        kw = inst.get("keywords") or MOB_DEFS[inst["tpl"]].get("keywords", "")
        if is_name(target, kw):
            count += 1
    return count


def do_exits(player, args):
    """List obvious exits with destination room names (cf. 1stMud do_exits in act_info.c).

    [Verified: 08/07/2026]

    Args:
        player (dict): Player state dict.
        args (list): Parsed command arguments (unused).
    """
    # [PRIMESUD] "auto" form not ported (autoexit uses its own line in do_look);
    # can_see_room stubbed; immortal room-vnum suffix not ported
    if not check_blind(player):   # cf. 1stMud do_exits act_info.c:1446
        return
    chprintln(player, "Obvious exits:")
    found = False
    exits = ROOM_DEFS[player["room"]]["exits"]
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
        if to not in ROOM_DEFS:
            continue
        found = True
        name = EXIT_NAMES.get(d, d)
        # cf. 1stMud do_exits act_info.c:1476 -- a dark destination hides its
        # name (independent of the viewer's infrared, matching the source)
        dest = "Too dark to tell" if room_is_dark(to) else ROOM_DEFS[to]["name"]
        chprintln(player, pad_right(upper(name), 5) + " - " + dest)
    if not found:
        chprintln(player, "None.")


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


def _show_char_to_char(player, mob_ids, out=None):
    """List room chars to player; red-eyes fallback in the dark (cf. 1stMud show_char_to_char in act_info.c:470).

    Each char the viewer can_see renders a full line (show_char_to_char_0); a
    char the viewer cannot see but who carries AFF_INFRARED in a dark room
    betrays "glowing red eyes" instead. Infrared thus reveals living things,
    never the room description -- both the pitch-black branch and the normal
    room render call this, matching 1stMud's single shared function.

    Args:
        player (dict): Observer.
        mob_ids (list): Room's live mob instance ids.
        out (list): [PRIMESUD] optional accumulator for batched room output.
    """
    emit = out.append if out is not None else lambda line: chprintln(player, line)
    p_aff = player["affected_by"]
    # [PRIMESUD] mob vnum overlay under holylight (upstream imms use stat)
    show_vnums = "holylight" in DBG
    dark = (player["room"] in ROOM_DEFS._data and room_is_dark(player["room"]))
    for mob_id in mob_ids:
        inst = world.chars.get(mob_id)
        if inst is None:
            continue
        # cf. 1stMud show_char_to_char (act_info.c:481): can_see -> full line;
        # else a dark-room char with AFF_INFRARED shows glowing eyes
        if not can_see(player, inst):
            if dark and inst["affected_by"].get("infrared"):
                emit("You see glowing red eyes watching YOU!")
            continue
        tpl = MOB_DEFS[inst["tpl"]]
        # Build AFF prefix string (cf. 1stMud show_char_to_char_0, act_info.c:191-214)
        # Race defaults merged into inst at create_mobile; spell AFF bits land
        # in "affected_by" via affect_modify, so both show here.
        aff = inst["affected_by"]
        prefix = ""
        if aff.get("invisible"):    prefix += "({cInvis{x) "
        if aff.get("hide"):         prefix += "({DHide{x) "
        if aff.get("charm"):        prefix += "({MCharmed{x) "
        if aff.get("pass_door"):    prefix += "({cTranslucent{x) "
        if aff.get("faerie_fire"):  prefix += "({MPink Aura{x) "
        if is_evil(inst) and p_aff.get("detect_evil"):   prefix += "({RRed Aura{x) "
        if is_good(inst) and p_aff.get("detect_good"):   prefix += "({YGolden Aura{x) "
        if aff.get("sanctuary"):    prefix += "({WWhite Aura{x) "
        # cf. 1stMud act_info.c:219 quest target marker; [PRIMESUD] vnum match
        if is_quester(player) and inst["tpl"] == player.get("quest_mob", 0):
            prefix += "{r[{RTARGET{r] {x"
        # cf. 1stMud act_info.c:223 gquest target marker
        if gq_is_player_target(inst["tpl"]):
            prefix += "{Y({RGquest{Y) {x"
        # cf. 1stMud: long_descr only when mob is at its start_pos
        pos = inst.get("pos", "standing")
        start_pos = POS_FROM_SHORT.get(tpl.get("start_pos", "stand"), "standing")
        if pos == start_pos and inst["fighting"] is None and tpl.get("long_descr"):
            line = tpl["long_descr"]
        else:
            # [PRIMESUD] instance name wins -- pets rename on evolve
            name = inst.get("name") or tpl["short_descr"]
            name = upper(name) if name else name
            if inst["fighting"] is not None or pos == "fighting":
                if inst["fighting"] == player["id"]:
                    line = name + " is here, fighting YOU!"
                else:
                    # [PRIMESUD] 1stMud shows the target's name; mobs only
                    # fight the player or each other's ids -- resolve if present
                    tgt = world.chars.get(inst["fighting"])
                    if tgt is None:
                        line = name + " is here, fighting thin air??"
                    else:
                        line = (name + " is here, fighting "
                                + (tgt.get("name") or MOB_DEFS[tgt["tpl"]]["short_descr"]) + ".")
            else:
                line = name + _POS_LINES.get(pos, " is here.")
        if show_vnums:  # [PRIMESUD] template vnum; instance id via debug stat mob
            line += " {D[" + num_str(inst["tpl"]) + "]"
        emit(prefix + "{M" + line + "{x")


def do_look(player, args):
    """Display the current room, examine a target, or look in a direction (cf. 1stMud do_look in act_info.c).

    Position ("stars"/sleeping) gates are handled by the command table; the
    check_blind and pitch-black darkness gates below run before argument
    parsing, so they apply to every look form (cf. act_info.c:1112-1121). The
    pitch-black gate ignores infrared (matching the source): infrared reveals
    living things via _show_char_to_char, not the room description.

    [Verified: 20/07/2026] -- the PLR_HOLYLIGHT leg of the act_info.c:1115
    condition maps to the [PRIMESUD] debug channel.

    [PRIMESUD] Room output accumulated into a list and sent as one batched
    print (21/07/2026) -- perf deviation, 1stMud sends per line; player-visible
    output unchanged. The list is passed through unjoined (see pitfall 8 /
    PRIME_FIRMWARE_BUGS.md: no join over %-formatted lines).

    Args:
        player (dict): Player state dict.
        args (list): Parsed command arguments; non-empty triggers targeted
            look, except the single sentinel "auto" (cf. 1stMud
            do_function(ch, &do_look, "auto") from move_char) which requests
            the brief-mode-gated room display used after movement.
    """
    # cf. 1stMud do_look act_info.c:1112 -- both gates precede argument parsing
    if not check_blind(player):
        return
    # cf. 1stMud do_look act_info.c:1128 -- "auto" (movement) shows the room
    # description unless COMM_BRIEF is set; explicit `look` (empty args)
    # always shows it. Falls through to the same full-room-display branch
    # as bare `look` below; only desc_lines' visibility differs.
    show_desc = True
    if args and args[0] == "auto":
        show_desc = not (player.get("flags", PLR_DEFAULTS) & COMM_BRIEF)
        args = []
    # cf. 1stMud act_info.c:1114 -- infrared does NOT lift this gate: it reveals
    # living things (via show_char_to_char, which can_see-passes for an infrared
    # viewer), never the room name/desc/items. room_is_dark itself ignores
    # infrared, so a dark room stays "pitch black" for infrared and unlit alike.
    # PLR_HOLYLIGHT in the source condition maps to the [PRIMESUD] debug toggle.
    if ("holylight" not in DBG
            and player["room"] in ROOM_DEFS._data and room_is_dark(player["room"])):
        chprintln(player, "It is pitch black ... ")
        _show_char_to_char(player, world.rooms[player["room"]]["mobs"])
        return
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

        # [PRIMESUD] Seed the counter with the room's visible mob matches so
        # `N.` indexes one unified mob -> object -> extra-desc sequence.
        # Upstream restarts at 0 here, leaving objects behind a same-keyword
        # mob unaddressable (docs/FIXES.md: do_look N.-prefix counter).
        count = _count_mob_matches(player, target, rs["mobs"])
        # Inventory + equipped (cf. 1stMud carrying_first which includes worn)
        equipped = [o for o in player["equip"].values() if o is not None]
        found, count = _look_scan_items(player, target, number, count,
                                        player["inv"] + equipped)
        if found:
            return
        # Room items
        found, count = _look_scan_items(player, target, number, count, rs["items"])
        if found:
            return

        # Room extra_descs (cf. 1stMud do_look line 1309)
        room = ROOM_DEFS[player["room"]]
        pdesc = _get_ed(target, room.get("extra_descs", []))
        if pdesc is not None:
            count += 1
            if count == number:
                _print_desc(player, pdesc, TERMINAL_COLS)
                return

        if count > 0 and count != number:
            if count == 1:
                chprintln(player, "You only see one " + target + " here.")
            else:
                chprintln(player, "You only see " + num_str(count) + " of those here.")
            return

        # Direction look (cf. 1stMud do_look lines 1330-1362)
        door = DIR_ALIASES.get(arg1)
        if door is None:
            chprintln(player, "You do not see that here.")
            return
        exits = room["exits"]
        if door not in exits:
            chprintln(player, "Nothing special there.")
            return
        ex = exits[door]
        if isinstance(ex, dict):
            # EX_DOORBELL "perhaps you should ring it?" line not ported
            ex_desc = ex.get("desc")
            if ex_desc:
                for line in _wrap_paragraphs(ex_desc, TERMINAL_COLS):
                    chprintln(player, line)
            else:
                chprintln(player, "Nothing special there.")
            kw = ex.get("keyword", "")
            if kw and kw[0] != ' ':
                kw = kw.split()[0]  # 1stMud act "$d": first word of keyword
                if ex.get("closed"):
                    chprintln(player, "The " + kw + " is closed.")
                elif ex.get("isdoor"):
                    chprintln(player, "The " + kw + " is open.")
        else:
            chprintln(player, "Nothing special there.")
        return
    room = ROOM_DEFS[player["room"]]
    rs = world.rooms[player["room"]]
    automap_on = player.get("flags", PLR_DEFAULTS) & PLR_AUTOMAP
    text_w = TERMINAL_COLS - COMPACT_W - 1 if automap_on else TERMINAL_COLS

    # Room vnum in title under holylight, cf. 1stMud PLR_HOLYLIGHT gate
    # (act_info.c:1136-1139)
    show_vnums = "holylight" in DBG
    out = []
    if show_vnums:
        out.append("{Y" + room["name"] + " {D[" + num_str(player["room"]) + "]{x")
    else:
        out.append("{Y" + room["name"] + "{x")

    # cf. 1stMud act_info.c:1144-1171 -- the description (and, nested inside
    # the same gate upstream, the automap draw) is skipped entirely under
    # COMM_BRIEF; exits/items/mobs below are not gated (act_info.c:1173-1180).
    if show_desc:
        color = SECTOR_COLORS.get(room.get("sector", "inside"), "")
        desc_lines = _wrap_paragraphs(room["desc"], text_w)

        if automap_on:
            # _data, not the LazyDict: mapping must not lazy-load neighbour
            # areas (see _map_exits docstring). [PRIMESUD]
            map_lines = build_compact_lines(player, ROOM_DEFS._data)
            n = max(len(map_lines), len(desc_lines))
            for i in range(n):
                ml = map_lines[i] if i < len(map_lines) else ' ' * COMPACT_W
                tl = desc_lines[i] if i < len(desc_lines) else ''
                out.append(ml + ' ' + color + tl)
        else:
            for tl in desc_lines:
                out.append(color + tl)

    # cf. 1stMud do_look: exits only shown with PLR_AUTOEXIT (do_exits "auto")
    if player.get("flags", PLR_DEFAULTS) & PLR_AUTOEXIT:
        exits = " ".join(
            EXIT_NAMES.get(d, d) for d in EXIT_ORDER
            if d in room["exits"] and not (isinstance(room["exits"][d], dict)
                and (room["exits"][d].get("closed")
                     or room["exits"][d].get("to") is None))
        )
        exit_string = "[Exits: " + exits + "]" if exits else "[Exits: none]"
        out.append("{g" + exit_string + "{x")
    live_mobs = rs["mobs"]
    # Items: build a display string per instance (flags + desc), stack by exact string match
    # (cf. 1stMud format_obj_to_char + show_list_to_char in act_info.c)
    seen = {}
    order = []
    p_aff = player["affected_by"]
    for obj in rs["items"]:
        # cf. 1stMud show_list_to_char: skip items the viewer can't see
        if not can_see_obj(player, obj):
            continue
        tpl = item_tpl(obj)
        flags = item_extra_flags(obj, tpl)
        # cf. 1stMud format_obj_to_char flag order (act_info.c:53-64)
        flag_str = ""
        if flags.get("invis"):  flag_str += "({cInvis{x) "
        if p_aff.get("detect_evil") and flags.get("evil"):
            flag_str += "({RRed Aura{x) "
        if p_aff.get("detect_good") and flags.get("bless"):
            flag_str += "({BBlue Aura{x) "
        if p_aff.get("detect_magic") and flags.get("magic"):
            flag_str += "({MMagical{x) "
        if flags.get("glow"):   flag_str += "({YGlowing{x) "
        if flags.get("hum"):    flag_str += "({CHumming{x) "
        # cf. 1stMud act_info.c:66 quest obj marker; [PRIMESUD] vnum match
        if is_quester(player) and obj_vnum(obj) == player.get("quest_obj", 0):
            flag_str += "{r[{RTARGET{r] {x"
        inst_desc = isinstance(obj, dict) and obj.get("description")
        line = flag_str + "{Y" + (inst_desc or tpl.get("description") or tpl["short_descr"]) + "{x"
        if show_vnums:  # [PRIMESUD]
            line += " {D[" + num_str(obj_vnum(obj)) + "]{x"
        if line in seen:
            seen[line] += 1
        else:
            seen[line] = 1
            order.append(line)
    for line in order:
        n = seen[line]
        stack_prefix = "(" + pad_left(num_str(n), 2) + ") " if n > 1 else "     "
        out.append(stack_prefix + line)
    # Mobs: one per line (cf. 1stMud show_char_to_char in act_info.c)
    _show_char_to_char(player, live_mobs, out)
    # [PRIMESUD] list sent unjoined: terminal batch-renders it, and joining
    # %-formatted lines trips the device heap bug (PRIME_FIRMWARE_BUGS.md)
    chprintln(player, out)


_SCORE_INNER = TERMINAL_COLS - 2
_SCORE_LEFT  = (TERMINAL_COLS - 7) // 2
_SCORE_RIGHT = TERMINAL_COLS - 7 - _SCORE_LEFT
_SCORE_SEP_OUTER = "{W+" + "-" * _SCORE_INNER + "+{x"
_SCORE_SEP_INNER = "{W+" + "-" * (_SCORE_LEFT + 2) + "+" + "-" * (_SCORE_RIGHT + 2) + "+{x"
# paired AC bar: cell width minus 6(label)+2(': ')+5(val)+2(' [')+1(']')
_AC_BAR_L = _SCORE_LEFT - 16
_AC_BAR_R = _SCORE_RIGHT - 16
_PERCENT_BAR_COLORS = ('r', 'R', 'y', 'Y', 'g', 'G', 'W')


def _make_percent_bar(val, max_val, length):
    """Colour-gradient fill bar of | chars (cf. 1stMud make_percent_bar in act_info.c).

    [Verified: 03/07/2026]

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
    """Display the character score sheet (cf. 1stMud dlm_score in act_info.c).

    [Verified: 21/07/2026] -- data fields (age, hours, thac0, AC bars)
    verified; box layout adapted for the 64-col, 22-row screen (AC bars
    paired 2-per-row, values/AC separator dropped) and a Tier cell added
    [PRIMESUD].
    """
    # two-column box mirroring 1stMud dlm_score layout, with bright/normal colours
    # alternating between horizontal segments.
    def _row(l, r):
        lpad = ' ' * (_SCORE_LEFT  - color_len(l))
        rpad = ' ' * (_SCORE_RIGHT - color_len(r))
        return "{W|{x " + l + lpad + " {W|{x " + r + rpad + " {W|{x"
    def _stat(name, perm, curr):
        return ('{c' + pad_right(name, 13) + ': [{w'
                + pad_left(num_str(perm), 2) + '/' + pad_left(num_str(curr), 2) + '{c]{x')
    def _val_l(name, v, bright=False):
        nc = '{C' if bright else '{c'
        # values stay as dim white
        vc = '{w'
        vs = v if isinstance(v, str) else num_str(v)
        return nc + pad_right(name, 13) + ': [' + vc + pad_left(vs, 10) + nc + ' ]{x'
    def _val_r(name, v, bright=False):
        nc = '{C' if bright else '{c'
        # values stay as dim white
        vc = '{w'
        vs = v if isinstance(v, str) else num_str(v)
        return nc + pad_right(name, 13) + ': [' + vc + pad_left(vs, 11) + nc + ' ]{x'

    def _ac_cell(label, val, bar_w=_AC_BAR_L):
        # [PRIMESUD] two bars per row so the score box fits the 22-row screen
        bar = _make_percent_bar(-val, 1000, bar_w)
        return ('{c' + pad_right(label, 6) + '{W: {w' + pad_left(num_str(val), 5)
                + ' {c[' + bar + '{c]{x')

    def _free_mem():
        # Since memory is mentioned here, also use `score` as a point to do gc
        gc_collect()
        return "{G(Mem. free: " + free_mem() + "){x"

    p = player
    ps = p["perm_stat"]
    thac0 = get_thac0(p)
    # full names if they fit the value cell, 4-char forms otherwise (multiclass)
    cls_name = class_long(p)
    if len(cls_name) > 11:
        cls_name = class_short(p)
    mem_str = _free_mem()
    name_raw = p.get('name', '???')
    # cf. 1stMud dlm_score header "<name><title>" (ch->name + ch->pcdata->title;
    # the title already carries its own leading space -- see set_title).
    # Falls back to the bare name if the combination would not fit the header.
    title_raw = name_raw + p.get("title", "")
    _hdr_w = _SCORE_LEFT + 3 + _SCORE_RIGHT
    if len(title_raw) + color_len(mem_str) + 1 > _hdr_w:
        title_raw = name_raw
    name_col = "{c" + title_raw + "{x"
    mem_col  = ' ' * (_hdr_w - len(title_raw) - color_len(mem_str)) + mem_str

    # cf. 1stMud act_info.c:1841 "Explored : %.0f of %d rooms (%.2f%% of the
    # world)" -- rendered as a centered full-width box row [PRIMESUD].
    _rcnt = roomcount(p)
    _expl_txt = ("{cExplored : {w" + num_str(_rcnt) + "{c of {w" + num_str(TOP_EXPLORED)
                 + "{c rooms ({w" + _pct2(_rcnt, TOP_EXPLORED)
                 + "%{c of the world){x")
    _ev = color_len(_expl_txt)
    _elp = max(0, (_SCORE_INNER - _ev) // 2)
    _erp = max(0, _SCORE_INNER - _ev - _elp)
    expl_row = "{W|{x" + " " * _elp + _expl_txt + " " * _erp + "{W|{x"

    total_played = p.get('played', 0)
    hours = total_played // 3600            # cf. 1stMud act_info.c: played/HOUR
    age   = 17 + total_played // 72000      # cf. 1stMud act_info.c: 17 + played/(20*HOUR)
    level = p["level"]
    tier = p.get("tier", 0)
    if tier:
        level = num_str(level) + " (T" + num_str(tier) + ")"

    lines = [
        _SCORE_SEP_OUTER,
        "{W|{x " + name_col + mem_col + " {W|{x",
        _SCORE_SEP_INNER,
        _row(
            _stat("Strength", ps["str"], get_curr_stat(p, "str")),
            _val_r("Level", level)
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
            + pad_left(num_str(p["hit"]), 5)
            + "{C/{R"
            + pad_left(num_str(p["max_hit"]), 5)
            + "{C]{x",
            _val_r("Hitroll", get_hitroll(p), bright=True),
        ),
        _row(
            "{CMana         : [{M"
            + pad_left(num_str(p["mana"]), 5)
            + "{C/{M"
            + pad_left(num_str(p["max_mana"]), 5)
            + "{C]{x",
            _val_r("Damroll", get_damroll(p), bright=True),
        ),
        _row(
            "{CMovement     : [{G"
            + pad_left(num_str(p.get("move", 100)), 5)
            + "{C/{G"
            + pad_left(num_str(p.get("max_move", 100)), 5)
            + "{C]{x",
            # cf. 1stMud dlm_score "Quest Points" cell
            _val_r("Quest Points", p.get("quest_points", 0), bright=True),
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
            _val_l("Gold", p["gold"], bright=True),
            _val_r("Position", p["pos"], bright=True),
        ),
        _row(
            _val_l("Silver", p["silver"], bright=True),
            _val_r("Alignment", p.get("alignment", 0), bright=True),
        ),
        _row(_ac_cell("Pierce", get_armor(p, AC_PIERCE)),
             _ac_cell("Bash", get_armor(p, AC_BASH), _AC_BAR_R)),
        _row(_ac_cell("Slash", get_armor(p, AC_SLASH)),
             _ac_cell("Exotic", get_armor(p, AC_EXOTIC), _AC_BAR_R)),
        _SCORE_SEP_OUTER,
        expl_row,
        _SCORE_SEP_OUTER,
    ]
    if p.get("gold_bank", 0) or p.get("shares", 0):
        # [PRIMESUD] Full-width row fits max values and displays the intended
        # share price; upstream passes shares twice where share_value is meant.
        _shares = p.get("shares", 0)
        _bank_txt = ("{CBank: {w" + num_str(p.get("gold_bank", 0))
                     + " gold {C| Shares: {w" + num_str(_shares) + " {C("
                     + num_str(_shares * world.share_value) + " gold @ "
                     + num_str(world.share_value) + "){x")
        _bv = color_len(_bank_txt)
        _blp = max(0, (_SCORE_INNER - _bv) // 2)
        _brp = max(0, _SCORE_INNER - _bv - _blp)
        lines.insert(-1, "{W|{x" + " " * _blp + _bank_txt
                     + " " * _brp + "{W|{x")
    # [PRIMESUD] list sent unjoined: batch-rendered by terminal.print_lines
    chprintln(player, lines)

    # cf. 1stMud act_info.c:2182 -- COMM_SHOW_AFFECTS appends do_affects.
    if p.get("flags", PLR_DEFAULTS) & COMM_SHOW_AFFECTS:
        do_affects(player, [])


def do_title(player, argument):
    """Set the player's score title (cf. 1stMud do_title in act_info.c).

    Args:
        player (dict): Player state dict.
        argument (str): Raw command tail -- the title text, case and spacing
            preserved (cf. 1stMud do_fun(ch, argument), not a lowercased
            token list).
    """
    if not argument:
        chprintln(player, "Change your title to what?")
        return
    title = argument[:45]  # cf. 1stMud act_info.c:3531 -- 45-char cap
    # [PRIMESUD] save-payload safety (game_state.py _serialize_world): '~' is
    # the save-line separator and '"' would break the PPL string literal --
    # neither is guarded upstream (raw C string), but both would corrupt the
    # next save here.
    if "~" in title or '"' in title:
        chprintln(player, "Titles may not contain '~' or '\"'.")
        return
    set_title(player, title)
    chprintln(player, "Ok.")


def do_worth(player, args):
    """Show gold, silver, experience and quest/trivia points (cf. 1stMud do_worth in act_info.c).

    [Verified: 04/07/2026] -- IsNPC branch not applicable (single player);
    "exp to level" uses the per-level xp model (xp_next - xp) in place of
    1stMud's (level+1)*exp_per_level - exp [PRIMESUD].
    """
    chprintln(player, "You have " + num_str(player["gold"]) + " gold, " + num_str(player["silver"])
           + " silver, and " + num_str(player["xp"]) + " experience ("
           + num_str(player["xp_next"] - player["xp"]) + " exp to level).")
    chprintln(player, "You have earned " + count_str(player.get("quest_points", 0), "questpoint")
           + " and " + count_str(player.get("trivia", 0), "trivia point") + ".")


def do_time(player, args):
    """Show the game calendar and time played (cf. 1stMud do_time in act_info.c:2348).

    [PRIMESUD] Only the calendar line and played-time line are ported; 1stMud's
    server/multiplayer lines (boot/copyover time, timezones, connected-at,
    creation percentage) have no single-player equivalent and are omitted.
    A session-time line is added (no 1stMud equivalent).
    """
    hour = time_info["hour"]
    half = HOURS_IN_DAY // 2
    hour12 = half if hour % half == 0 else hour % half
    ampm = "pm" if hour >= half else "am"
    # [PRIMESUD] 1stMud's format string carries a leftover "%d%s" from ROM's
    # (day+1, suffix) pair but passes only ordinal_string(day+1); the stray %d
    # is a slip -- rendered here as a single ordinal ("first", "21st", ...).
    chprintln(player,
              "It is " + num_str(hour12) + " o'clock " + ampm
              + ", Day of " + day_name[(time_info["day"] + 1) % DAYS_IN_WEEK]
              + ", " + ordinal_string(time_info["day"] + 1)
              + " the Month of " + month_name[time_info["month"]]
              + ", year " + num_str(time_info["year"]) + ".")
    # cf. 1stMud (pcdata->played + elapsed) / HOUR . ((.../36) % 100);
    # PrimeSUD tracks played in real seconds (update.py), HOUR = 3600.
    played = player.get("played", 0)
    cents = (played // 36) % 100
    cs = num_str(cents) if cents >= 10 else "0" + num_str(cents)
    chprintln(player, "You have played approximately "
              + num_str(played // 3600) + "." + cs + " hours.")
    # [PRIMESUD] Current sitting, tracked unsaved in update.py.  No battery
    # level is readable on the Prime, so this is the player's only gauge of
    # how long the calculator has been awake.
    session = player.get("_session", 0)
    sh = session // 3600
    chprintln(player, "This session: "
              + ((count_str(sh, "hour") + ", ") if sh else "")
              + count_str((session % 3600) // 60, "minute") + ".")


def do_weather(player, args):
    """Report the current weather to an outdoor player (cf. 1stMud do_weather in act_info.c:2470)."""
    room = ROOM_DEFS[player["room"]]
    # IsOutside (cf. 1stMud macro.h): a room not flagged indoors.
    if room.get("flags", {}).get("indoors"):
        chprintln(player, "You can't see the sky from here.")
        return
    tag = room.get("area")
    weather = None
    for a in world.areas:
        if a.get("tag") == tag:
            weather = a.get("weather")
            break
    if weather is None:
        chprintln(player, "You can't see the sky from here.")
        return
    chprintln(player, "{B" + weather_report_line(weather) + "{x")


def _parse_skill_range(player, args):
    """Parse level range arguments for spell/skill list commands. [PRIMESUD]"""
    if not args:
        return (False, 1, MAX_MORTAL_LEVEL, True)
    # cf. 1stMud do_spells/do_skills: ANY argument sets fAll (numeric ranges
    # list entries above the char's level as "n/a" rather than hiding them)
    f_all = True
    # cf. 1stMud !str_prefix(argument, "all"): arg is prefix of "all"
    if "all".startswith(args[0]):
        return (f_all, 1, MAX_MORTAL_LEVEL, True)
    try:
        max_lev = int(args[0])
    except ValueError:
        chprintln(player, "Arguments must be numerical or all.")
        return (False, 1, MAX_MORTAL_LEVEL, False)
    if max_lev < 1 or max_lev > MAX_MORTAL_LEVEL:
        chprintln(player, "Levels must be between 1 and " + num_str(MAX_MORTAL_LEVEL) + ".")
        return (False, 1, MAX_MORTAL_LEVEL, False)
    min_lev = 1
    if len(args) > 1:
        try:
            min_lev = max_lev
            max_lev = int(args[1])
        except ValueError:
            chprintln(player, "Arguments must be numerical or all.")
            return (False, 1, MAX_MORTAL_LEVEL, False)
        if max_lev < 1 or max_lev > MAX_MORTAL_LEVEL:
            chprintln(player, "Levels must be between 1 and " + num_str(MAX_MORTAL_LEVEL) + ".")
            return (False, 1, MAX_MORTAL_LEVEL, False)
        if min_lev > max_lev:
            chprintln(player, "That would be silly.")
            return (False, 1, MAX_MORTAL_LEVEL, False)
    return (f_all, min_lev, max_lev, True)


def _pad_color(s, width):
    """Right-pad a colour-coded string to the given visible width. [PRIMESUD]"""
    return s + " " * max(0, width - color_len(s))


def _print_level_lists(player, args, want_spells):
    """Print spells or skills grouped by level. [PRIMESUD]"""
    f_all, min_lev, max_lev, ok = _parse_skill_range(player, args)
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
                    item = ("{c" + _pad_color(sk["name"], 16) + " {W"
                            + pad_left(num_str(spell_mana(player, sn)), 3) + " mana  ")
            elif player.get("level", 1) < level:
                item = "{c" + _pad_color(sk["name"], 16) + " n/a      "
            else:
                item = ("{c" + _pad_color(sk["name"], 16) + " {W"
                        + pad_left(num_str(learned.get(sn, 0)), 3) + "%      ")
            if level not in rows:
                rows[level] = []
            rows[level].append(item)
    if not found:
        # 1stMud: do_spells prints plain, do_skills colored
        if want_spells:
            chprintln(player, "No spells found.")
        else:
            chprintln(player, "{cNo skills found.{x")
        return
    # [PRIMESUD] output accumulated and sent as one unjoined list --
    # batch-rendered by terminal.print_lines
    out = []
    for level in range(MAX_MORTAL_LEVEL + 1):
        items = rows.get(level)
        if not items:
            continue
        for i in range(0, len(items), 2):
            prefix = ("{cLevel {W" + pad_left(num_str(level), 2) + "{c: "
                      if i == 0 else "{x          ")
            line = prefix + items[i]
            if i + 1 < len(items):
                line += items[i + 1]
            # [PRIMESUD] 1stMud's 29-wide columns overflow 64 cols (68 vis);
            # 16-wide names + stripped tail keep two columns under the wrap.
            out.append(line.rstrip() + "{x")
    chprintln(player, out)


def print_practice_table(player):
    """Print learned practice percentages (cf. 1stMud do_practice in act_info.c). [Verified: 04/07/2026]"""
    items = []
    half = TERMINAL_COLS // 2
    name_w = 18
    learned = player.get("learned", {})
    for sn, sk in SKILL_TABLE:
        pct = learned.get(sn, 0)
        if can_use_skill_spell(player, sn) and pct > 0:
            items.append(pad_right(sk["name"][:name_w], name_w) + " " + pad_left(num_str(pct), 3) + "%")
    # [PRIMESUD] list sent unjoined: batch-rendered by terminal.print_lines
    out = []
    for i in range(0, len(items), 2):
        line = items[i]
        if i + 1 < len(items):
            line = line + " " * (half - len(line)) + items[i + 1]
        out.append(line)
    chprintln(player, out)


def do_skills(player, args):
    """List known skills by level (cf. 1stMud do_skills in skills.c). [Verified: 03/07/2026]"""
    _print_level_lists(player, args, False)


def do_spells(player, args):
    """List known spells by level (cf. 1stMud do_spells in skills.c). [Verified: 03/07/2026]"""
    _print_level_lists(player, args, True)


HELP_FILE = "help.txt"  # [PRIMESUD] canonical source; idx via tools/build_help_idx.py
HELP_INDEX = "help.idx"  # '<level>|<category>|<offset>|<keywords>' per entry
# [PRIMESUD] Upstream ships 8 categories, half of them unusable as menu rows:
# a 50-entry "unknown" dumping ground, two single-entry categories, and 23 olc
# helps for an unported editor. Rebalanced into browsable groups. Eight are
# mortal-visible; every entry in deities, immortal, olc, clan and unknown sits
# at level 51 in help.txt -- out of reach of any player level, since none of
# those systems is ported, but still readable if one ever lands. Tuple order
# is the listing order, and a category missing from it is silently dropped
# from both menus.
HELP_CATEGORIES = ("creation", "deities", "commands", "skills", "spells",
                   "combat", "world", "interface", "credits",
                   "immortal", "olc", "clan", "unknown")


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


def _help_body(offset):
    """Read and screen-wrap one help body at its prebuilt byte offset. [PRIMESUD]

    Flush-left source lines form reflowable paragraphs. Blank lines retain
    paragraph spacing; blocks containing indentation or ``Syntax:`` retain
    their source line breaks. ``.nf``/``.fi`` delimit explicit fixed-layout
    blocks for flush-left tables and ASCII art.
    """
    body = []
    block = []
    fixed = False

    def flush_block():
        if not block:
            return
        hard_lines = fixed
        if not hard_lines:
            for text in block:
                i = 0
                while i + 1 < len(text) and text[i] == "{":
                    i += 2  # indentation may hide behind colour codes
                if (i < len(text) and (text[i] == " " or text[i] == "\t")) \
                        or text.startswith("Syntax:"):
                    hard_lines = True
                    break
        if hard_lines:
            for text in block:
                body.extend(color_wrap_full(text, TERMINAL_COLS))
        else:
            body.extend(color_wrap_full(" ".join(text.strip() for text in block),
                                        TERMINAL_COLS))
        del block[:]

    with open(HELP_FILE) as f:
        f.seek(offset)
        # [PRIMESUD] chunked read to the '#' terminator line; looped
        # readline() costs ~20ms/call on-device (docs/PERFORMANCE.md).
        text = ""
        while True:
            chunk = f.read(2048)
            text += chunk
            end = text.find("\n#")
            if end >= 0:
                text = text[:end]
                break
            if len(chunk) < 2048:
                # EOF: drop the file's final newline, not a blank body line
                if text[-1:] == "\n":
                    text = text[:-1]
                break
    if text[:1] == "#":
        text = ""  # empty body: offset sits on the next entry's header
    for line in (text.split("\n") if text else ()):
        if line == ".nf":
            flush_block()
            fixed = True
        elif line == ".fi":
            flush_block()
            fixed = False
        elif not line:
            flush_block()
            body.append("")
        else:
            block.append(line)
    flush_block()
    return body


def do_index(player, args):
    """Browse help entries by category (cf. 1stMud do_index in act_info.c).

    [PRIMESUD] Scans the off-heap help index and uses two columns for the
    Prime's 64-column screen. The category listing is level-filtered and
    gap-free: upstream counts every entry regardless of level, so a mortal was
    offered `olc (23 helps)` and got an empty page from `index olc`. Both
    `index <n>` and `index <name>` resolve against that same filtered list, so
    neither can reach a category the listing withheld.
    [Verified: 25/07/2026]
    """
    trust = player.get("level", 1)
    if not args:
        lines = ["Help Category not found. Valid args are:"]
        for i, (category, count) in enumerate(_help_visible_categories(trust)):
            lines.append(pad_left(num_str(i + 1), 2) + ") " + category + " (" + num_str(count) + " helps)")
        tpage(lines)
        return

    arg = args[0].lower()
    category = None
    if arg.isdigit():
        visible = _help_visible_categories(trust)
        category_number = int(arg) - 1
        if 0 <= category_number < len(visible):
            category = visible[category_number][0]
    else:
        # [PRIMESUD] Matched against the visible categories, not all of
        # HELP_CATEGORIES: naming a level-51 category is "Unknown category."
        # here, the same denial `help olc` already gives for its entries.
        for name, _count in _help_visible_categories(trust):
            if name.startswith(arg):
                category = name
                break
    if category is None:
        chprintln(player, "Unknown category.")
        return

    number = None
    if len(args) > 1:
        # [PRIMESUD] Category-local misses use the clearer not-found message;
        # upstream instead treats numbers >= global top_help as bad syntax.
        if not args[1].isdigit() or int(args[1]) < 1:
            chprintln(player, "Syntax: index <category> <help number>")
            return
        number = int(args[1])

    with open(HELP_INDEX) as f:
        data = f.read()
    matches = []
    selected = None
    count = 0
    for line in data.split("\n"):
        if not line:
            continue
        level_s, entry_category, offset_s, keywords = line.split("|", 3)
        if int(level_s) > trust or entry_category != category:
            continue
        if number is None:
            matches.append(keywords)
        else:
            count += 1
            if number == count:
                selected = (keywords, int(offset_s))
                break
    data = None

    sep = draw_line("{c-{C-")
    if number is not None:
        if selected is None:
            chprintln(player, "That help not found in " + category + ".")
            return
        lines = [sep, "Help Keywords : " + selected[0],
                 "Help Category : " + category, sep]
        lines.extend(_help_body(selected[1]))
        lines.append(sep)
        tpage(lines)
        return

    lines = [sep, "[ " + category.upper() + " ]", sep]
    half = TERMINAL_COLS // 2
    cells = []
    for i, keywords in enumerate(matches):
        cells.append((pad_left(num_str(i + 1), 3) + ") " + keywords)[:half - 1])
    for i in range(0, len(cells), 2):
        line = cells[i]
        if i + 1 < len(cells):
            line += " " * (half - len(line)) + cells[i + 1]
        lines.append(line)
    # [PRIMESUD] Upstream's "No helps found in %s." is dropped: only a visible
    # category resolves now, and a visible category has entries by definition.
    lines.append(sep)
    tpage(lines)


def do_help(player, args):
    """Show a help entry, keyword list, or see-also list (cf. 1stMud do_help in act_info.c).

    [PRIMESUD] Scans HELP_INDEX (~9KB) instead of an in-memory help list or
    the full ~150KB HELP_FILE -- neither fits the HP Prime heap/time budget.
    Index format: '<level>|<category>|<offset>|<keywords>' per line; offset is
    the byte position of the entry's first text line in HELP_FILE.
    [Verified: 25/07/2026] -- [PRIMESUD] bare "help" opens a category
    browser instead of printing the summary outright.
    """
    if not args:
        # [PRIMESUD] Bare help browses by category rather than printing the
        # summary outright; its first menu option is that same summary.
        _help_browse(player)
        return
    argall = " ".join(args)
    number, target = _number_argument(argall)
    trust = player.get("level", 1)
    listing = len(target) == 1  # single-letter arg lists matching keywords
    sep = draw_line("{c-{C-")
    found = False
    count = 0
    matches = []  # list-mode keywords
    offsets = []  # list-mode body offsets, parallel to matches [PRIMESUD]
    related = []  # "See Also" keywords after the shown entry
    show = None   # (keyword, offset) of the entry to print
    t0 = ticks()  # [PRIMESUD] 'debug time' channel timings
    # [PRIMESUD] one f.read() beats 283 readline() calls ~100x on Prime FS.
    # Substring pre-filter: any _help_is_name match needs the first target
    # word to prefix some keyword, so its uppercase form must appear in the
    # index line -- skips split/int/is_name work on non-candidates.
    with open(HELP_INDEX) as f:
        data = f.read()
    words = target.split()
    q = words[0].strip("'\"").upper() if words else ""
    for line in data.split("\n"):
        if not line or q not in line:
            continue
        level_s, _category, off_s, keyword = line.split("|", 3)
        if int(level_s) > trust:
            continue
        if not _help_is_name(target, keyword):
            continue
        if listing:
            matches.append(keyword)
            offsets.append(int(off_s))  # [PRIMESUD] picker opens the body
            found = True
        else:
            count += 1
            if count == number:
                show = (keyword, int(off_s))
                found = True
            elif found:
                related.append(keyword)
    data = None  # [PRIMESUD] release 9KB index string promptly
    t1 = t2 = ticks()  # [PRIMESUD] idx scan done
    if show:
        # [PRIMESUD] read body before printing so 'debug time' can split
        # file-read cost from terminal-render cost
        body = _help_body(show[1])
        t2 = ticks()
        # [PRIMESUD] output accumulated and sent as one unjoined list --
        # batch-rendered by terminal.print_lines
        out = [sep, "Help Keywords : " + show[0], sep]
        out.extend(body)
        out.append(sep)
    else:
        out = []
    if matches:
        # [PRIMESUD] Replaces 1stMud's numbered 3-column list, which the
        # player could only act on by retyping 'help <n>.<word>' with enough
        # letters to leave list mode. The picker opens any match with a
        # digit and Enter instead. `show` is never set in list mode, so
        # nothing is pending in `out` here.
        _help_pick("Help files starting with '" + target[0].upper() + "'",
                   matches, offsets)
    elif not found:
        out.append("No help found for " + target + ". Try using just the first letter.")
        # new_wiznet missing-help log: no immortals in single-user [PRIMESUD]
    elif related:
        out.append("See Also : " + ", ".join(related) + ".")
        out.append(sep)
    if out:
        chprintln(player, out)
    if "time" in DBG:  # [PRIMESUD] 'debug time' channel
        t3 = ticks()
        dbg("help: idx=" + num_str(t1 - t0) + "ms read=" + num_str(t2 - t1) +
            "ms print=" + num_str(t3 - t2) + "ms")


# [PRIMESUD] Picker rows render as "  N) <label>", and row 1 of each page
# also carries a " (default)" marker -- 15 columns of furniture in the worst
# case. Keyword lists run to 101 chars, so they are elided to fit one row.
_HELP_LABEL_MAX = TERMINAL_COLS - 15


def _help_visible_categories(trust):
    """Return [(category, count)] for categories with entries visible at trust. [PRIMESUD]"""
    counts = [0] * len(HELP_CATEGORIES)
    with open(HELP_INDEX) as f:
        data = f.read()
    for line in data.split("\n"):
        if not line:
            continue
        level_s, category, _offset, _keywords = line.split("|", 3)
        if int(level_s) > trust or category not in HELP_CATEGORIES:
            continue
        counts[HELP_CATEGORIES.index(category)] += 1
    data = None  # [PRIMESUD] release the 9KB index string promptly
    out = []
    for i, name in enumerate(HELP_CATEGORIES):
        if counts[i]:
            out.append((name, counts[i]))
    return out


def _help_category_entries(trust, category):
    """Return (keywords, offsets) lists for one category, in do_index order. [PRIMESUD]

    Same filter and same order as do_index, so menu position N is also the
    number `index <category> N` takes.
    """
    with open(HELP_INDEX) as f:
        data = f.read()
    keywords = []
    offsets = []
    for line in data.split("\n"):
        if not line:
            continue
        level_s, entry_category, offset_s, entry_keywords = line.split("|", 3)
        if int(level_s) > trust or entry_category != category:
            continue
        keywords.append(entry_keywords)
        offsets.append(int(offset_s))
    data = None
    return keywords, offsets


def _help_pick(title, keywords, offsets, category=None):
    """Menu a keyword list, showing each pick until Esc. [PRIMESUD]

    Args:
        title (str): Picker header.
        keywords (list[str]): Full keyword lists, one per entry.
        offsets (list[int]): HELP_FILE body offsets, parallel to keywords.
        category (str): Shown as a "Help Category" header line; omitted
            when the caller's entries span categories.
    """
    labels = []
    for kw in keywords:
        # Short labels are appended as-is, so the common case shares the
        # existing string rather than allocating a copy.
        labels.append(kw if len(kw) <= _HELP_LABEL_MAX
                      else kw[:_HELP_LABEL_MAX - 3] + "...")
    sep = draw_line("{c-{C-")
    page = 0
    while True:
        idx = pick_from(title, labels, page)
        if idx < 0:
            return
        # Reopen where the player left off: without this, picking entry 63
        # drops them back on page 1 with six pages to walk again.
        page = idx // _PICKER_PAGE
        lines = [sep, "Help Keywords : " + keywords[idx]]
        if category is not None:
            lines.append("Help Category : " + category)
        lines.append(sep)
        lines.extend(_help_body(offsets[idx]))
        lines.append(sep)
        tpage(lines)


def _help_browse_category(player, category, trust):
    """Menu one category's entries, showing each pick until Esc. [PRIMESUD]"""
    keywords, offsets = _help_category_entries(trust, category)
    _help_pick("Help: " + category, keywords, offsets, category)


def _help_browse(player):
    """Browse help by category with digits and Enter only. [PRIMESUD]

    Typing a keyword on the calculator keypad means alpha-shifting every
    letter, so bare `help` opens a menu instead: category, then entry, then
    the entry body; Esc steps back out one level at a time. The first option
    is `summary`, so `help` followed by Enter still yields 1stMud's bare-help
    output.
    """
    trust = player.get("level", 1)
    categories = _help_visible_categories(trust)
    labels = ["summary (one-page command overview)"]
    for name, count in categories:
        labels.append(name + " (" + num_str(count) + " helps)")
    while True:
        choice = pick_from("Help: pick a category", labels)
        if choice < 0:
            return
        if choice == 0:
            do_help(player, ["summary"])
            continue
        _help_browse_category(player, categories[choice - 1][0], trust)


def do_map(player, args):
    """Print a full-size automap of rooms reachable from the current room (cf. 1stMud do_map in automap.c).

    Args:
        player (dict): Player state dict.
    """
    if not check_blind(player):   # cf. 1stMud do_map automap.c:567
        return
    # [PRIMESUD] list sent unjoined: batch-rendered by terminal.print_lines
    # _data: resident rooms only, no lazy-load (see _map_exits docstring). [PRIMESUD]
    chprintln(player, list(build_full_lines(player, ROOM_DEFS._data)))


def do_affects(player, args):
    """List all active player affects with name, location, modifier, duration (cf. 1stMud do_affects in act_info.c).

    [Verified: 06/07/2026]

    Args:
        player (dict): Player state dict.
        args (list): Unused.
    """
    found = False
    # [PRIMESUD] output accumulated and sent as one unjoined list --
    # batch-rendered by terminal.print_lines
    out = []
    affects = player["affect_list"]
    if affects:
        out.append("You are affected by the following spells:")
        # cf. 1stMud: modifier/duration detail only at trust >= 20
        show_detail = player.get("level", 1) >= 20
        last_type = None
        for aff in affects:
            sn = aff.get("type")
            if last_type is not None and sn == last_type:
                # consecutive same-type affects: indented continuation
                if not show_detail:
                    continue
                line = " " * 26
            else:
                sk = SKILLS.get(sn)
                name = sk["name"] if sk else "unknown"
                line = "{xSpell: {c" + _pad_color(name, 19) + "{x"
            if show_detail:
                dur = aff["duration"]
                line += (": modifies " + aff["location"]
                         + " by " + num_str(aff["modifier"]) + " ")
                if dur < 0:
                    line += "permanently"
                else:
                    line += "for " + num_str(dur) + " hours"
            out.append(line)
            last_type = sn
        found = True
        out.append("")
    # cf. 1stMud do_affects racial-ability section (act_info.c:2249-2264);
    # gated on the bits actually being set on the char (IsAffected).
    _race = race_lookup(player.get("race", "Human")) or RACE_TABLE["Human"]
    race_aff = _race.get("aff", {})
    affected_by = player["affected_by"]
    if race_aff and any(affected_by.get(f) for f in race_aff):
        out.append("You are affected by the following racial abilities:")
        for flag_name in sorted(race_aff):
            out.append("{xSpell: {c" + _pad_color(flag_name, 19) + "{x")
        found = True
        out.append("")
    # cf. 1stMud do_affects equipment-spells section (act_info.c:2265-2337):
    # gated on any active affected_by bit not accounted for by race->aff.
    active = set(f for f in affected_by if affected_by.get(f))
    if active and active != set(race_aff):
        printed = False
        for slot in _EQUIP_SAVE_ORDER:
            obj = player["equip"].get(slot)
            if obj is None:
                continue
            tpl = item_tpl(obj)
            short_descr = obj_short(obj, tpl)
            # Runtime object affects first (cf. 1stMud obj->affect_first)
            for paf in obj.get("affect_list", []):
                if paf.get("where", "to_affects") != "to_affects":
                    continue
                bit = paf.get("bitvector")
                if not bit or not affected_by.get(bit):
                    continue
                if not printed:
                    out.append("You are affected by the following equipment spells:")
                    printed = True
                out.append("{xSpell: {c" + _pad_color(bit, 19)
                           + ":{x " + short_descr)
            # Then template flag_affects, non-enchanted only (cf. 1stMud
            # obj->pIndexData->affect_first, gated on !obj->enchanted)
            if not obj.get("enchanted"):
                for paf in tpl_flag_affects(tpl):
                    if paf.get("where", "to_affects") != "to_affects":
                        continue
                    bit = paf.get("bitvector")
                    if not bit or not affected_by.get(bit):
                        continue
                    if not printed:
                        out.append("You are affected by the following equipment spells:")
                        printed = True
                    out.append("{xSpell: {c" + _pad_color(bit, 19)
                               + ":{x " + short_descr)
        # 1stMud sets found=true here unconditionally, even if nothing printed
        # (act_info.c:2333-2334) -- quirk preserved for fidelity.
        found = True
        if printed:
            out.append("")
    if not found:
        out.append("You are not affected by any spells.")
    chprintln(player, out)


def do_credits(player, args):
    """Display upstream credit help entries (cf. 1stMud `do_credits` in act_info.c). [Verified: 23/07/2026]"""
    do_help(player, ["diku", "credits"])
    do_help(player, ["ROM", "credits"])
    do_help(player, ["1stMud", "credits"])


def _convert_level(arg):
    """Parse level string to int (cf. 1stMud convert_level in db.c). [Verified: 03/07/2026]"""
    if not arg:
        return 0
    if arg.isdigit():
        return int(arg)
    # cf. 1stMud is_name("IMM", arg): "IMM" prefix-matches the typed arg
    if arg.startswith("imm"):
        return MAX_LEVEL  # 1stMud LEVEL_IMMORTAL; no imm tiers here
    if arg.startswith("hero") or arg.startswith("hro"):
        return MAX_MORTAL_LEVEL
    return 0


def _print_area_levels(levels, comment=None):
    """Format area level range for display (cf. 1stMud print_area_levels in db.c). [Verified: 08/07/2026]"""
    if comment:
        # Non-numeric credits token ("All", "None") shown verbatim,
        # centered in the 7-wide slot (1stMud: str_align(7, Center,
        # lvl_comment); caller's %-7s supplies the right fill).
        return " " * ((7 - len(comment)) // 2) + comment
    lo, hi = levels
    if lo >= MAX_MORTAL_LEVEL and hi >= MAX_MORTAL_LEVEL:
        return " HERO+ "
    lo_s = "HRO" if lo >= MAX_MORTAL_LEVEL else zpad(lo, 3)
    hi_s = "HRO" if hi >= MAX_MORTAL_LEVEL else zpad(hi, 3)
    return lo_s + " " + hi_s


def _area_level_str(tag):
    """Return an area's normalized display-level range. [PRIMESUD]"""
    levels = world.AREA_LEVELS.get(tag, (1, MAX_LEVEL))
    lo = max(1, min(levels[0], MAX_LEVEL))
    hi = max(1, min(levels[1], MAX_LEVEL))
    return _print_area_levels(
        (lo, hi), world.AREA_LVL_COMMENTS.get(tag))


def _sorted_area_files():
    """Return static areas with special ranges first, then level/name. [PRIMESUD]"""
    return sorted(
        world._AREA_FILES,
        key=lambda a: ((a[1] not in world.AREA_LVL_COMMENTS,)
                       + world.AREA_LEVELS.get(a[1], (1, MAX_LEVEL))
                       + (a[2].lower(),)))


def _extract_builder(credits):
    """Extract builder name from area credits line (cf. 1stMud convert_area_credits in db2.c). [Verified: 03/07/2026]"""
    idx = credits.find("} ")
    if idx >= 0:
        parts = credits[idx + 2:].split()
        if parts:
            return parts[0]
    return credits[:7] if credits else ""


def _compress_path(parent, source, target):
    """Trace BFS parent chain and compress directions (cf. 1stMud path_to_area in act_enter.c).

    [PRIMESUD] Emits "<count><dir>" runs (e.g. "3s2en") matching do_run's
    parser; 1stMud's own run-length prepending is inconsistent/buggy.
    [Verified: 03/07/2026]
    """
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
                parts.append(num_str(count))
            parts.append(path[i - 1])
            count = 1
    if count > 1:
        parts.append(num_str(count))
    parts.append(path[-1])
    return "".join(parts)


# Precomputed border-graph index (tools/build_path_index.py); cwd is src/
# both on-device and at runtime. Tests monkeypatch this to a tmp file.
PATH_INDEX_FILE = "paths.idx"


# Parsed-index cache keyed by filename: paths.idx is static per build, and
# on-device the per-call re-parse dominated _route at ~4s/call
# (debug/str_soak-1.log phase A). Filename keying keeps the test
# monkeypatches of PATH_INDEX_FILE working (each points at a unique tmp file).
_INDEX_CACHE = None  # (fname, segs, xedges, slivers)


def _parse_index():
    """Read paths.idx in one f.read() and byte-walk all record types. [PRIMESUD]

    Parses once per PATH_INDEX_FILE value and returns the cached data
    after that; callers treat it as read-only.

    [PRIMESUD] The walk indexes the raw bytes (unboxed ints, no per-line
    or per-field string objects) and accumulates digits arithmetically
    instead of split() + int() per line: on-device one small heap
    allocation costs ~0.5ms at full game heap, so split-based text
    parsing is allocation-bound, not data-bound (docs/PERFORMANCE.md
    secs. Recommend scans, Boot load phase split). Only genuine payloads
    allocate -- the S route string and the X direction character. The
    paths.idx text format is unchanged (tools/build_path_index.py).

    [PRIMESUD] A "*" X direction marks an exit out of a room whose exits
    an "R" reset reshuffles every reset; the stored direction becomes the
    room-target token "*<to_vnum>" ("take whichever live exit leads
    there"), which movement.run_buf_step resolves as it walks.  S dirs
    strings carry the same tokens inline and need no extra parsing (they
    are copied out verbatim).

    Returns:
        tuple: (segs, xedges, slivers) where segs maps entry vnum ->
            [(exit_vnum, dist, dirs), ...] intra-area segments, xedges
            maps exit vnum -> [(dir, to_vnum), ...] cross-area exits, and
            slivers is the set of border rooms stranded in a disconnected
            fragment of their own area.
    """
    global _INDEX_CACHE
    c = _INDEX_CACHE
    if c is not None and c[0] == PATH_INDEX_FILE:
        return c[1], c[2], c[3]
    segs = {}
    xedges = {}
    slivers = set()
    with open(PATH_INDEX_FILE, "rb") as f:
        data = f.read()
    if type(data) is str:
        # Device open(.., "rb").read() hands back str; MicroPython's
        # encode() is a raw byte cast, so this recovers the exact bytes
        # (docs/BUILTINS.md sec. File open() binary-mode semantics, same
        # guard as recommend._as_bytes).
        data = data.encode()
    dir_chars = {}  # byte -> 1-char str, interned across all X records
    n = len(data)
    i = 0
    while i < n:
        kind = data[i]
        if kind == 83:  # "S|entry|exit|dist|dirs"
            i += 2
            entry = 0
            while i < n and 47 < data[i] < 58:
                entry = entry * 10 + data[i] - 48
                i += 1
            i += 1  # skip "|"
            exit_vnum = 0
            while i < n and 47 < data[i] < 58:
                exit_vnum = exit_vnum * 10 + data[i] - 48
                i += 1
            i += 1
            dist = 0
            while i < n and 47 < data[i] < 58:
                dist = dist * 10 + data[i] - 48
                i += 1
            i += 1
            start = i
            while i < n and data[i] != 10 and data[i] != 13:
                i += 1
            row = (exit_vnum, dist, data[start:i].decode())
            seg = segs.get(entry)
            if seg is None:
                segs[entry] = [row]
            else:
                seg.append(row)
        elif kind == 88:  # "X|exit|dir|to"
            i += 2
            exit_vnum = 0
            while i < n and 47 < data[i] < 58:
                exit_vnum = exit_vnum * 10 + data[i] - 48
                i += 1
            i += 1  # skip "|"
            if i >= n:
                break
            b = data[i]
            i += 2  # skip the direction char and its "|"
            to_vnum = 0
            while i < n and 47 < data[i] < 58:
                to_vnum = to_vnum * 10 + data[i] - 48
                i += 1
            if b == 42:  # "*": exit out of a shuffled room -- see docstring
                direction = "*" + num_str(to_vnum)
            else:
                direction = dir_chars.get(b)
                if direction is None:
                    direction = chr(b)
                    dir_chars[b] = direction
            row = (direction, to_vnum)
            xedge = xedges.get(exit_vnum)
            if xedge is None:
                xedges[exit_vnum] = [row]
            else:
                xedge.append(row)
        elif kind == 86:  # "V|vnum"
            i += 2
            vnum = 0
            while i < n and 47 < data[i] < 58:
                vnum = vnum * 10 + data[i] - 48
                i += 1
            slivers.add(vnum)
        while i < n and data[i] != 10:  # comments/blanks land here too
            i += 1
        i += 1
    _INDEX_CACHE = (PATH_INDEX_FILE, segs, xedges, slivers)
    return segs, xedges, slivers


def _bfs_leg(start, tag):
    """BFS from start over one already-loaded area's rooms only. [PRIMESUD]

    Returns:
        tuple: (dist, parent) dicts; parent chains feed _compress_path.
    """
    dist = {start: 0}
    parent = {}
    queue = [start]
    qi = 0
    while qi < len(queue):
        cur = queue[qi]
        qi += 1
        room = ROOM_DEFS._data.get(cur)
        if room is None:
            continue
        for direction in EXIT_ORDER:
            exit_val = room.get("exits", {}).get(direction)
            if exit_val is None:
                continue
            to = exit_val.get("to") if isinstance(exit_val, dict) else exit_val
            if to is None or to in dist:
                continue
            to_room = ROOM_DEFS._data.get(to)
            if to_room is None or to_room.get("area") != tag:
                continue
            dist[to] = dist[cur] + 1
            parent[to] = (cur, direction)
            queue.append(to)
    return dist, parent


def _merge_runs(parts):
    """Concatenate compressed direction strings, merging boundary runs.

    "3n" + "2n" -> "5n"; format is count-then-dir with count omitted when
    1, matching _compress_path / do_run's parser. [PRIMESUD]

    [PRIMESUD] "*<vnum>" room-target tokens (paths.idx steps out of a
    shuffle-reset room) are atomic single steps: they never merge with
    anything, and a run count is never emitted straight after one, whose
    digits would fuse with the token's vnum ("*3054" + "3n" -> "*3054nnn").
    """
    runs = []  # [part, count] pairs; part is a dir char or a "*<vnum>" token
    for s in parts:
        i = 0
        n = len(s)
        while i < n:
            j = i
            while "0" <= s[j] <= "9":
                j += 1
            count = int(s[i:j]) if j > i else 1
            d = s[j]
            i = j + 1
            if d == "*":
                while i < n and "0" <= s[i] <= "9":
                    i += 1
                runs.append([s[j:i], 1])
                continue
            if runs and runs[-1][0] == d:
                runs[-1][1] += count
            else:
                runs.append([d, count])
    out = []
    prev_token = False
    for d, count in runs:
        if count == 1:
            out.append(d)
        elif prev_token:
            out.append(d * count)
        else:
            out.append(num_str(count))
            out.append(d)
        prev_token = d[0] == "*"
    return "".join(out)


def _route(player, target_tag, target_room=None):
    """Exact shortest route via the precomputed border graph. [PRIMESUD]

    Dijkstra over paths.idx segments plus two live BFS legs inside
    already-loaded areas (source area; target area for mob targets, loaded
    by the mob lookup). Loads no areas at routing time. Step count matches
    an unrestricted full-world BFS; the chosen equal-length route may
    differ from upstream's.

    Returns:
        tuple: ("", 0) no walk needed; (route, steps) compressed route;
            (None, 0) unreachable.
    """
    source = player.get("room")
    if source is None:
        return None, 0
    source_tag = ROOM_DEFS[source].get("area")
    if source_tag == target_tag:
        if target_room is None or source == target_room:
            return "", 0

    segs, xedges, slivers = _parse_index()
    START = -1
    GOAL = -2

    # Source leg: virtual start -> each source-area exit room; plus a
    # direct edge to the goal for a same-area mob target (the graph still
    # considers leave-and-re-enter routes alongside it).
    sdist, sparent = _bfs_leg(source, source_tag)
    start_edges = []
    for room in sdist:
        if room in xedges:
            start_edges.append(
                (room, sdist[room], _compress_path(sparent, source, room)))
    if target_room is not None and target_room in sdist:
        start_edges.append((GOAL, sdist[target_room],
                            _compress_path(sparent, source, target_room)))

    # Target leg (mob targets): each entry room of the target area -> the
    # mob's room, BFS inside the target area (loaded by the mob lookup).
    tgt_entry = {}
    if target_room is not None:
        entries = set()
        for xlist in xedges.values():
            for _direction, to in xlist:
                if world._vnum_to_tag(to) == target_tag:
                    entries.add(to)
        for entry in entries:
            tdist, tparent = _bfs_leg(entry, target_tag)
            if target_room in tdist:
                tgt_entry[entry] = (tdist[target_room],
                                    _compress_path(tparent, entry,
                                                   target_room))

    # Dijkstra, integer weights, O(V^2) linear-min (no heapq: device
    # availability unverified). Two passes at most: the first refuses to
    # land on a sliver room, the second (only run when a sliver was in fact
    # skipped and nothing else was reachable) accepts them.
    for skip_slivers in (True, False):
        dist = {START: 0}
        prev = {}
        settled = set()
        goal_node = None
        skipped = False
        while goal_node is None:
            u = None
            du = 0
            for node in dist:
                if node not in settled and (u is None or dist[node] < du):
                    u = node
                    du = dist[node]
            if u is None:
                break
            settled.add(u)
            if target_room is None:
                # Area target: done on first arrival inside the target area
                # (upstream path_to_area stops at the first such room).
                # [PRIMESUD] except for sliver rooms -- area-tagged border
                # rooms cut off from the rest of their own area (e.g. New
                # Thalos' river rooms 9772-9775), where upstream's rule
                # strands the walk outside the real area.
                if u >= 0 and world._vnum_to_tag(u) == target_tag:
                    if skip_slivers and u in slivers:
                        skipped = True
                    else:
                        goal_node = u
                        break
            elif u == GOAL:
                goal_node = u
                break
            if u == START:
                edges = start_edges
            else:
                edges = [(to, w, dirs) for to, w, dirs in segs.get(u, ())]
                for direction, to in xedges.get(u, ()):
                    edges.append((to, 1, direction))
                if target_room is not None and u in tgt_entry:
                    w, dirs = tgt_entry[u]
                    edges.append((GOAL, w, dirs))
            for to, w, dirs in edges:
                nd = du + w
                if to not in dist or nd < dist[to]:
                    dist[to] = nd
                    prev[to] = (u, dirs)
        if goal_node is not None or not skipped:
            break
    if goal_node is None:
        return None, 0

    parts = []
    node = goal_node
    while node != START:
        node, dirs = prev[node]
        parts.append(dirs)
    parts.reverse()
    return _merge_runs(parts), dist[goal_node]


def find_path_to_area(ch, target_tag):
    """Speedwalk to a target area via the border graph. [PRIMESUD]

    Thin wrapper over _route: exact shortest route, zero area loads at
    routing time. Replaces the earlier staged corridor pathfinder and its
    load-all find_area_paths fallback -- the corridor's area-level chains
    assumed any entry of an area reaches any exit, which internally
    partitioned areas break constantly (silent 3-4x overlong walks, or a
    full ~5.9MB world load when the restricted BFS dead-ended).

    Args:
        ch (dict): Player state dict.
        target_tag (str): Area tag to path to.

    Returns:
        str or None: Compressed speedwalk string (e.g. "3s2en"), or None
            if unreachable. Also None if ch is already in target_tag --
            callers exclude the current area from candidate lists anyway.
    """
    route, _steps = _route(ch, target_tag)
    return route or None


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
    """List areas with level ranges and builders (cf. 1stMud do_areas in db.c).

    [Verified: 04/07/2026] -- clan restriction marker ("{G*") and its
    legend line not ported (no clans); [PRIMESUD] sorted by special range,
    then level, then name (1stMud lists in area-file load order).

    [PRIMESUD] 1stMud's stock layout appends a per-area path_to_area()
    directions column; the codebase's own MudFlag(DISABLE_AREA_DIRECTIONS)
    config switch drops it for an alternate layout ("%s{W[{B%-7s{W] {r%s
    {C%s{x", no trailing "(dirs)" parenthetical) -- see 1stMud db.c
    do_areas(). PrimeSUD always renders that alternate layout: computing
    directions for every area (even lazily, one BFS per area or one
    combined BFS) means touching enough of the room graph that most
    areas end up loaded anyway, defeating the point of lazy loading.
    Renders purely from the static tables (world._AREA_FILES,
    world.AREA_LEVELS, world.AREA_BUILDERS) so listing areas never
    triggers an area load itself. The leading marker column (1stMud:
    clan-restriction "*") is repurposed [PRIMESUD] to flag the player's
    current area instead, since there is no directions column left to
    say "You are here."
    """
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

    chprintln(player, "")
    chprintln(player, "{W" + _center_fill("[ {RAREAS ON PRIMESUD{W ]") + "{x")

    # Current room is always loaded, so this is a zero-load lookup.
    source_area = ROOM_DEFS.get(player.get("room"), {}).get("area")

    # [PRIMESUD] "All"/"None" ranges first, then level range and name;
    # 1stMud lists in area-file load order.
    sorted_areas = _sorted_area_files()

    count = 0
    for _fname, tag, name, _vlo, _vhi in sorted_areas:
        levels = world.AREA_LEVELS.get(tag, (1, MAX_LEVEL))
        lo = max(1, min(levels[0], MAX_LEVEL))
        hi = max(1, min(levels[1], MAX_LEVEL))
        if lo >= lo_lv and hi <= hi_lv:
            lvl_str = _area_level_str(tag)
            builder = world.AREA_BUILDERS.get(tag, "")
            # [PRIMESUD] "here" marker, see docstring.
            here = "{G>{x" if tag == source_area else " "
            # [PRIMESUD] builder column 10 wide (upstream %-7s): "Andersen"
            # is 8 chars and shifted Pyramid/Astral names by one.
            chprintln(player, here + "{W[{B" + pad_right(lvl_str, 7)
                   + "{W] {r" + pad_right(builder, 10) + " {C" + name + "{x")
            count += 1

    if count == 0:
        chprintln(player, "{W" + _center_fill("[ {RNo areas meeting those criteria.{W ]") + "{x")
    else:
        chprintln(player, "{W" + _center_fill("[ {R" + num_str(count) + " areas found{W ]") + "{x")


MOB_INDEX_FILE = "mobs.bin"  # [PRIMESUD] prebuilt mob display metadata


def _mob_stats(player, stat_index):
    """Show mob-template stats (cf. 1stMud do_mobkills/do_mobdeaths in act_info.c).

    [PRIMESUD] Layout is condensed to 64 columns; immortal reset forms are
    omitted with the immortal admin surface.
    """
    title = "Most Dangerous Monsters" if stat_index == 0 else "Most Popular Mobs"
    label = "Kills" if stat_index == 0 else "Deaths"
    counts = {v: s[stat_index] for v, s in world.mob_stats.items()
              if s[stat_index] > 2}
    lines = ["{W[ {R" + title + "{W ]{x",
             "{GNum  Mob Name               Lvl Area                 " + label + "{x"]
    if not counts:
        lines.append("No Mobs listed yet.")
        tpage(lines)
        return
    metadata = {}
    # One walk of the binary index; record fields are read by offset
    # (layout in keyidx's docstring) so nothing allocates per template.
    index = keyidx.load(MOB_INDEX_FILE)
    if index is not None:
        data, meta = index
        kw_off = meta[1]
        strings_off = meta[2]
        tags = meta[4]
        pos = meta[0]
        while pos < kw_off:
            vnum = data[pos] | data[pos + 1] << 8
            if vnum in counts:
                name_off = strings_off + (data[pos + 7] | data[pos + 8] << 8)
                metadata[vnum] = (
                    data[name_off:name_off + data[pos + 9]].decode(),
                    data[pos + 2], tags[data[pos + 3]])
            pos += 11 + data[pos + 10]
    ranked = [(count, vnum) for vnum, count in counts.items()
              if vnum in metadata]
    ranked.sort(key=lambda x: (-x[0], x[1]))
    rank = 0
    for count, vnum in ranked[:50]:
        rank += 1
        short_descr, level, tag = metadata[vnum]
        lines.append(pad_left(num_str(rank), 3) + ") " + pad_right(short_descr[:22], 22)
                     + " " + pad_left(num_str(level), 3) + " "
                     + pad_right(world._TAG_TO_NAME.get(tag, tag)[:20], 20)
                     + " " + pad_left(num_str(count), 6))
    if not rank:
        lines.append("No Mobs listed yet.")
    tpage(lines)


def do_mobkills(player, args):
    """List mobs ranked by kills (cf. 1stMud do_mobkills in act_info.c)."""
    _mob_stats(player, 0)


def do_mobdeaths(player, args):
    """List mobs ranked by deaths (cf. 1stMud do_mobdeaths in act_info.c)."""
    _mob_stats(player, 1)


def _area_stats(stat_index):
    """Show area stats (cf. 1stMud do_areakills/do_areadeaths in act_info.c).

    [PRIMESUD] Layout is condensed to 64 columns; trusted reset forms are
    omitted with the immortal admin surface.
    """
    # [PRIMESUD] Upstream do_areakills has an inverted AREA_CLOSED gate that
    # hides every active area; use its clear listing intent, like do_areadeaths.
    label = "Kills" if stat_index == 0 else "Deaths"
    ranked = [(s[stat_index], tag) for tag, s in world.area_stats.items()
              if s[stat_index] > 0]
    ranked.sort(key=lambda x: (-x[0], x[1]))
    lines = ["{GNum  Area Name                 Levels   " + label + "{x"]
    for rank, entry in enumerate(ranked, 1):
        count, tag = entry
        levels = world.AREA_LEVELS.get(tag, (1, MAX_LEVEL))
        lvl = num_str(levels[0]) + "-" + num_str(levels[1])
        lines.append(pad_left(num_str(rank), 3) + ") "
                     + pad_right(world._TAG_TO_NAME.get(tag, tag)[:25], 25)
                     + " " + pad_left(lvl, 7) + " " + pad_left(num_str(count), 7))
    tpage(lines)


def do_areakills(player, args):
    """List areas ranked by kills (cf. 1stMud do_areakills in act_info.c)."""
    _area_stats(0)


def do_areadeaths(player, args):
    """List areas ranked by deaths (cf. 1stMud do_areadeaths in act_info.c)."""
    _area_stats(1)


def do_read(player, args):
    """Alias for do_look (cf. 1stMud do_read in act_info.c). [Verified: 03/07/2026]"""
    do_look(player, args)


def do_examine(player, args):
    """Examine an object: look at it, then show contents or coin count (cf. 1stMud do_examine in act_info.c).

    [Verified: 04/07/2026]

    Args:
        player (dict): Player state dict.
        args (list): Parsed command arguments.
    """
    if not args:
        # [PRIMESUD] picker menu when no args (1stMud prints "Examine what?" and
        # stops); hidden/invisible entries filtered like the get/drop pickers.
        # Order: mobs, room objects, the room's extra descriptions ({c, labelled
        # by their first keyword), any exit carrying a description ({g, labelled
        # by full direction name), then carried objects (inventory, then worn).
        # Room context comes first because it is what the player can only reach
        # from here and it would otherwise sit pages deep on the calculator's
        # short screen; carried gear stays reachable via inventory/equipment.
        rs = world.rooms[player["room"]]
        room = ROOM_DEFS[player["room"]]
        equipped = [o for o in player["equip"].values() if o is not None]
        mobs = [i for i in rs["mobs"] if can_see(player, world.chars[i])]
        robjs = [o for o in rs["items"] if can_see_obj(player, o)]
        cobjs = [o for o in (player["inv"] + equipped) if can_see_obj(player, o)]
        # [PRIMESUD] extra_descs and exit descs are room description text, so
        # they honour do_look's blind and pitch-black gates (holylight lifts
        # both), silently: the picker never prints the gate messages. Mob and
        # object entries need no gate -- can_see/can_see_obj already handle
        # blind and dark viewers.
        eds = []
        ex_dirs = []
        if "holylight" in DBG or (not player["affected_by"].get("blind")
                                  and not room_is_dark(player["room"])):
            for keywords, desc in room.get("extra_descs", []):
                words = keywords.split()
                if words:
                    eds.append((words[0], desc))
            room_exits = room["exits"]
            ex_dirs = [d for d in EXIT_ORDER
                       if isinstance(room_exits.get(d), dict) and room_exits[d].get("desc")]
        labels = [world.chars[i].get("name") or MOB_DEFS[world.chars[i]["tpl"]]["short_descr"]
                  for i in mobs]
        for o in robjs:
            labels.append(obj_short(o, item_tpl(o)))
        for first_kw, desc in eds:
            labels.append("{c" + first_kw + "{x")
        for d in ex_dirs:
            labels.append("{g" + EXIT_NAMES.get(d, d) + "{x")
        for o in cobjs:
            labels.append(obj_short(o, item_tpl(o)))
        if not labels:
            # [PRIMESUD] empty menu: say why, instead of upstream's bare
            # "Examine what?" missing-argument prompt (which reads like a
            # picker bug when the player asked for the menu). Blind and
            # pitch-black reuse do_look's gate lines; holylight lifts both.
            if "holylight" not in DBG and player["affected_by"].get("blind"):
                chprintln(player, "You can't see a thing!")
            elif "holylight" not in DBG and room_is_dark(player["room"]):
                chprintln(player, "It is pitch black ... ")
            else:
                chprintln(player, "There is nothing here to examine.")
            return
        idx = pick_from("Examine what?", labels)
        if idx < 0:
            return
        # [PRIMESUD] picker-resolved history strings use a SINGLE-WORD target
        # token here: typed examine/look consume one token only (1stMud
        # one_argument), unlike the inventory/shop pickers whose typed paths
        # join args and so replay the full keywords string.
        if idx < len(mobs):
            _show_char_to_char_1(player, mobs[idx])
            mtpl = MOB_DEFS[world.chars[mobs[idx]]["tpl"]]
            return "examine " + mtpl.get("keywords", mtpl["short_descr"]).split()[0]
        idx -= len(mobs)
        # [PRIMESUD] eds and exits sit BETWEEN the room and carried object
        # entries, so only indices past the room objects need un-shifting
        # before the shared object lookup below.
        if len(robjs) <= idx < len(robjs) + len(eds):
            # [PRIMESUD] delegate to do_look with an exact cumulative `N.` token
            # (see do_look's unified counter): room extra_descs are scanned
            # after every mob and object, and an earlier extra_desc matching
            # the same keyword takes one more slot ahead of this one.
            first_kw, desc = eds[idx - len(robjs)]
            n = _count_mob_matches(player, first_kw, rs["mobs"])
            found, n = _look_scan_items(player, first_kw, -1, n,
                                        player["inv"] + equipped + rs["items"])
            for kws, d in room.get("extra_descs", []):
                if d is desc:
                    break
                if is_name(first_kw, kws):
                    n += 1
            target = first_kw if n == 0 else num_str(n + 1) + "." + first_kw
            do_look(player, [target])
            return "examine " + target
        if len(robjs) + len(eds) <= idx < len(robjs) + len(eds) + len(ex_dirs):
            # exit description: reuse do_look's direction branch (desc + door state)
            d = ex_dirs[idx - len(robjs) - len(eds)]
            dir_name = EXIT_NAMES.get(d, d)
            do_look(player, [dir_name])
            return "examine " + dir_name
        if idx >= len(robjs):
            idx -= len(eds) + len(ex_dirs)
        obj = (robjs + cobjs)[idx]
        tpl = item_tpl(obj)
        # [PRIMESUD] route through do_look's typed scan with an exact cumulative
        # `N.` token instead of hand-rendering the description: the typed path
        # checks the object's extra_descs first (e.g. a letter's contents rather
        # than "...is taped to the wall.").  Scan order is inventory + worn,
        # then room items; bare-vnum ints make `is` stop at an earlier equal
        # vnum, which is harmless -- identical items render identically.
        kw = tpl.get("keywords", tpl["short_descr"]).split()[0]
        prefix_list = []
        for o in player["inv"] + equipped + rs["items"]:
            if o is obj:
                break
            prefix_list.append(o)
        n = _count_mob_matches(player, kw, rs["mobs"])
        found, n = _look_scan_items(player, kw, -1, n, prefix_list)
        target = kw if n == 0 else num_str(n + 1) + "." + kw
        do_look(player, [target])
        # extras come from the picked instance, not a re-resolution of `target`
        # (get_obj_here numbers each list separately, so a cumulative token can
        # miss); same rationale as _examine_extras' own [PRIMESUD] note.
        _examine_extras(player, obj)
        return "examine " + target
    arg = args[0]
    do_look(player, [arg])
    obj = get_obj_here(player, arg)
    if obj is not None:
        _examine_extras(player, obj)


def _examine_extras(player, obj):
    """Show money coin counts or container contents after looking at obj (cf. 1stMud do_examine in act_info.c).

    [PRIMESUD] Container contents shown from the resolved obj directly; 1stMud
    re-resolves via do_look "in <arg>", which can match a different object.
    [Verified: 31/07/2026]
    """
    tpl = item_tpl(obj)
    obj_type = _item_type(obj, tpl)
    if obj_type == "money":
        silver = obj.get("silver", tpl.get("silver", 0))
        gold = obj.get("gold", tpl.get("gold", 0))
        if silver == 0:
            if gold == 0:
                chprintln(player, "Odd...there's no coins in the pile.")
            elif gold == 1:
                chprintln(player, "Wow. One gold coin.")
            else:
                chprintln(player, "There are " + num_str(gold) + " gold coins in the pile.")
        elif gold == 0:
            if silver == 1:
                chprintln(player, "Wow. One silver coin.")
            else:
                chprintln(player, "There are " + num_str(silver) + " silver coins in the pile.")
        else:
            # [PRIMESUD] Singular/plural fix -- 1stMud prints "%ld gold and %ld
            # silver coins", so the noun only ever attached to the silver half.
            chprintln(player, "There are " + count_str(gold, "gold coin") + " and "
                      + count_str(silver, "silver coin") + " in the pile.")
    elif obj_type in _CONTAINER_TYPES:
        _show_container(player, obj, tpl)
    elif obj_type == "jukebox":
        # cf. 1stMud do_function(ch, &do_play, "list") -- re-resolves the
        # jukebox from scratch rather than reusing the already-matched obj,
        # same as upstream.
        do_play(player, ["list"])
