"""Debug channel toggles for playtesting. [PRIMESUD]"""

import terminal
import world
from classes import exp_per_level
from config import MAX_LEVEL
from pager import tpage
from skills_table import (GSN_PLAGUE, GSN_POISON, GSN_BLINDNESS, GSN_CURSE,
                          GSN_SLEEP)
from util import num_str, pad_left, pad_right, sstr

# Game-module imports (combat, handler, item, info, mob, game_state) stay
# function-local throughout this file: handler/info/mob/update import debug
# at top for the DBG toggle and dbg(), so top-level backrefs would cycle.

# Active debug channels.  Callers must guard with `if "x" in DBG:` BEFORE
# building the message string -- concat costs even when discarded, and some
# call sites are in per-mob per-pulse loops.
DBG = set()

_CHANNELS = ("spawn", "move", "tick", "reset", "save", "time", "prog", "fidx")


def dbg(msg):
    """Print one debug line in dark grey. [PRIMESUD]"""
    terminal.tr.print("{D[dbg] " + msg + "{x")


def _val(v):
    """Stringify one dict value, truncated to keep the screen usable. [PRIMESUD]"""
    s = sstr(v)
    if len(s) > 160:
        s = s[:157] + "..."
    return s


def _dump(title, d):
    """Print a dict as sorted key/value lines (cf. 1stMud show_struct in tables.c). [PRIMESUD]"""
    terminal.tr.print("{D-- " + title + " --{x")
    for k in sorted(d.keys()):
        terminal.tr.print("{D" + k + ":{x " + _val(d[k]))


def _debug_stat(player, args):
    """Dump internal entity dicts (cf. 1stMud do_stat in act_wiz.c). [PRIMESUD]

    1stMud's do_stat renders structs via show_struct/data tables; PrimeSUD
    entities are plain dicts, so we dump the dict itself -- same information,
    no per-field porting.
    """
    from handler import get_char_room
    from item import get_obj_here, obj_vnum

    if not args:
        terminal.tr.print("debug stat player | mob <name|vnum> | obj <name|vnum> | room [vnum] | area [tag]")
        return
    what = args[0]
    target = args[1] if len(args) > 1 else None
    if "player".startswith(what):
        _dump("player", player)
    elif "mob".startswith(what) or "char".startswith(what):
        if target is None:
            terminal.tr.print("Stat which mob?")
        elif target.isdigit():
            tpl = world.MOB_DEFS.get(int(target))
            if tpl is None:
                terminal.tr.print("No mob template " + target + ".")
            else:
                _dump("mob tpl " + target, tpl)
        else:
            mob_id = get_char_room(target, world.rooms[player["room"]]["mobs"], world.chars)
            if mob_id is None:
                terminal.tr.print("No such mob here.")
            else:
                _dump("mob inst " + num_str(mob_id), world.chars[mob_id])
    elif "obj".startswith(what):
        if target is None:
            terminal.tr.print("Stat which object?")
        elif target.isdigit():
            tpl = world.ITEM_DEFS.get(int(target))
            if tpl is None:
                terminal.tr.print("No item template " + target + ".")
            else:
                _dump("obj tpl " + target, tpl)
        else:
            obj = get_obj_here(player, target)
            if obj is None:
                terminal.tr.print("No such object here.")
            elif isinstance(obj, dict):
                _dump("obj inst (tpl " + num_str(obj_vnum(obj)) + ")", obj)
            else:
                # Plain-vnum room item: no instance state, show template.
                _dump("obj tpl " + num_str(obj), world.ITEM_DEFS[obj])
    elif "room".startswith(what):
        vnum = int(target) if target is not None and target.isdigit() else player["room"]
        rdef = world.ROOM_DEFS.get(vnum)
        if rdef is None:
            terminal.tr.print("No room " + num_str(vnum) + ".")
            return
        _dump("room def " + num_str(vnum), rdef)
        rs = world.rooms.get(vnum)
        if rs is not None:
            _dump("room state " + num_str(vnum), rs)
    elif "area".startswith(what):
        tag = target if target is not None else world.ROOM_DEFS[player["room"]].get("area")
        found = False
        for area in world.areas:
            if area.get("tag") == tag:
                _dump("area state " + tag, area)
                found = True
                break
        if not found:
            terminal.tr.print("No area '" + tag + "'.")
    else:
        terminal.tr.print("Stat what? (player, mob, obj, room, area)")


def _debug_goto(player, args):
    """Teleport to a room vnum or a named mob's room (cf. 1stMud do_goto in act_wiz.c). [PRIMESUD]

    Private-room / bamfin / bamfout / invis_level checks not ported
    (single-player).  Pet moves along, as in perform_recall.
    """
    from handler import is_name
    from info import do_look
    from combat import stop_fighting

    if not args:
        terminal.tr.print("Goto where?")
        return
    location = None
    if args[0].isdigit():
        vnum = int(args[0])
        if vnum in world.ROOM_DEFS:
            location = vnum
    else:
        # cf. 1stMud find_location: fall back to a char's room by name
        frag = " ".join(args)
        for mid in sorted(world.chars):
            inst = world.chars[mid]
            if inst.get("is_npc") \
                    and is_name(frag, world.MOB_DEFS[inst["tpl"]].get("keywords", "")):
                location = inst["room"]
                break
    if location is None:
        terminal.tr.print("No such location.")
        return
    if player["fighting"] is not None:
        stop_fighting(player, both=True)
    from_vnum = player["room"]
    player["room"] = location
    # cf. perform_recall: pet moves with its master
    pet = world.chars.get(player["pet"]) if player.get("pet") is not None else None
    if (pet is not None and pet.get("room") == from_vnum
            and from_vnum in world.rooms and location in world.rooms):
        if pet["id"] in world.rooms[from_vnum]["mobs"]:
            world.rooms[from_vnum]["mobs"].remove(pet["id"])
        pet["room"] = location
        world.rooms[location]["mobs"].append(pet["id"])
    # cf. 1stMud do_goto act_wiz.c:927: do_look "auto" -- COMM_BRIEF gate
    do_look(player, ["auto"])


def _debug_load(player, args):
    """Spawn a mob or object by vnum (cf. 1stMud do_load/do_mload/do_oload in act_wiz.c). [PRIMESUD]

    oload's optional level argument not ported -- PrimeSUD create_object
    has no level parameter.
    """

    if len(args) < 2 or not args[1].isdigit():
        terminal.tr.print("debug load mob|obj <vnum>")
        return
    what = args[0]
    vnum = int(args[1])
    if "mob".startswith(what) or "char".startswith(what):
        if vnum not in world.MOB_DEFS:
            terminal.tr.print("No mob has that vnum.")
            return
        from mob import create_mobile
        inst = create_mobile(vnum)
        inst["room"] = player["room"]
        inst["home_area"] = world.ROOM_DEFS[player["room"]].get("area")
        next_id = max(world.chars, default=1) + 1
        inst["id"] = next_id
        world.chars[next_id] = inst
        world.rooms[player["room"]]["mobs"].append(next_id)
        terminal.tr.print("Ok.")
    elif "obj".startswith(what):
        if vnum not in world.ITEM_DEFS:
            terminal.tr.print("No object has that vnum.")
            return
        from item import create_object
        obj = create_object(vnum)
        # cf. do_oload: CanWear(obj, ITEM_TAKE) -> inventory, else room
        if world.ITEM_DEFS[vnum].get("wear_flags", {}).get("take"):
            player["inv"].append(obj)
        else:
            world.rooms[player["room"]]["items"].append(obj)
        terminal.tr.print("Ok.")
    else:
        terminal.tr.print("debug load mob|obj <vnum>")


def _debug_purge(player, args):
    """Purge current room of NPCs and objects (cf. 1stMud do_purge in act_wiz.c). [PRIMESUD]

    nopurge mobs/objects survive, as in 1stMud.  [PRIMESUD] the player's
    pet also survives (1stMud purges it) -- debug convenience.
    Purge-by-target-name variant not ported.
    """
    from combat import _extract_char
    from item import obj_vnum, item_extra_flags

    rvnum = player["room"]
    for mid in list(world.rooms[rvnum]["mobs"]):
        inst = world.chars.get(mid)
        if inst is None:
            continue
        if inst.get("act_flags", {}).get("nopurge"):
            continue
        if mid == player.get("pet"):
            continue
        _extract_char(inst, pull=True)
    items = world.rooms[rvnum]["items"]
    items[:] = [obj for obj in items
                if item_extra_flags(obj, world.item_tpl(obj)).get("nopurge")]
    terminal.tr.print("Ok.")


def _debug_restore(player, args):
    """Restore hp/mana/move and strip maladies room-wide (cf. 1stMud do_restore in act_wiz.c). [PRIMESUD]

    Always the no-arg "room" form; "all" / by-name variants not ported
    (single-player).
    """
    from handler import affect_strip
    from combat import update_pos

    targets = [player] + [world.chars[mid]
                          for mid in world.rooms[player["room"]]["mobs"]
                          if mid in world.chars]
    for vch in targets:
        for sn in (GSN_PLAGUE, GSN_POISON, GSN_BLINDNESS, GSN_SLEEP, GSN_CURSE):
            affect_strip(vch, sn)
        vch["hit"] = vch["max_hit"]
        vch["mana"] = vch["max_mana"]
        vch["move"] = vch["max_move"]
        update_pos(vch)
    terminal.tr.print("Room restored.")


def _debug_peace(player, args):
    """Stop all fighting in the room, strip aggressive flag (cf. 1stMud do_peace in act_wiz.c). [PRIMESUD]"""
    from combat import stop_fighting

    if player["fighting"] is not None:
        stop_fighting(player, both=True)
    for mid in world.rooms[player["room"]]["mobs"]:
        inst = world.chars.get(mid)
        if inst is None:
            continue
        if inst["fighting"] is not None:
            stop_fighting(inst, both=True)
        # cf. RemBit(rch->act, ACT_AGGRESSIVE)
        inst.get("act_flags", {}).pop("aggressive", None)
    terminal.tr.print("Ok.")


def _debug_mwhere(player, args):
    """List spawned mobs matching name (cf. 1stMud do_mwhere in act_wiz.c). [PRIMESUD]

    Only instances in loaded areas are listed.  No-arg player listing not
    ported (single-player).
    """
    from handler import is_name

    if not args:
        terminal.tr.print("Find whom?")
        return
    frag = " ".join(args)
    count = 0
    for mid in sorted(world.chars):
        inst = world.chars[mid]
        if not inst.get("is_npc"):
            continue
        tpl = world.MOB_DEFS[inst["tpl"]]
        if not is_name(frag, tpl.get("keywords", "")):
            continue
        count += 1
        terminal.tr.print(
            pad_left(num_str(count), 3) + ") [" + pad_left(num_str(inst["tpl"]), 5)
            + "] " + pad_right(tpl["short_descr"][:20], 20) + " ["
            + pad_left(num_str(inst["room"]), 5) + "] "
            + world.ROOM_DEFS.get(inst["room"], {}).get("name", "?"))
    if count == 0:
        terminal.tr.print("You didn't find any " + frag + ".")


def _debug_owhere(player, args):
    """Locate objects by name (cf. 1stMud do_owhere in act_wiz.c). [PRIMESUD]

    Searches loaded rooms (one container level deep), player inventory,
    and equipment.  Level / visibility filters not ported.
    """
    from handler import is_name
    from item import obj_vnum

    if not args:
        terminal.tr.print("Find what?")
        return
    frag = " ".join(args)
    count = [0]

    def _sd(obj):
        return ((isinstance(obj, dict) and obj.get("short_descr"))
                or world.item_tpl(obj)["short_descr"])

    def _report(obj, where):
        tpl = world.item_tpl(obj)
        if is_name(frag, tpl.get("keywords", "")):
            count[0] += 1
            terminal.tr.print(pad_left(num_str(count[0]), 3) + ") " + _sd(obj)
                              + " is " + where)

    # Loaded room state only -- ._data avoids triggering a full world load
    for rvnum in sorted(world.rooms._data):
        for obj in world.rooms._data[rvnum]["items"]:
            _report(obj, "in room " + num_str(rvnum))
            if isinstance(obj, dict):
                for inner in obj.get("contents", []):
                    _report(inner, "in " + _sd(obj) + " [room " + num_str(rvnum) + "]")
    for obj in player["inv"]:
        _report(obj, "carried by you")
        if isinstance(obj, dict):
            for inner in obj.get("contents", []):
                _report(inner, "in " + _sd(obj) + " (carried)")
    for slot in player["equip"]:
        obj = player["equip"][slot]
        if obj is not None:
            _report(obj, "worn by you")
    if count[0] == 0:
        terminal.tr.print("Nothing like that in heaven or earth.")


def _debug_memory(player, args):
    """Show heap usage and world counts (cf. 1stMud do_memory in db2.c). [PRIMESUD]

    Heap figures via MicroPython gc.mem_alloc/mem_free; unavailable on
    desktop CPython, printed as n/a there.
    """
    import gc

    gc.collect()
    try:
        terminal.tr.print("Heap:  " + num_str(gc.mem_alloc()) + " used, "
                          + num_str(gc.mem_free()) + " free")
    except AttributeError:
        terminal.tr.print("Heap:  n/a (desktop)")
    # ._data lengths: len() on a LazyDict would force-load every area
    loaded = 0
    for a in world.AREA_DEFS:
        if world.is_area_loaded(a["tag"]):
            loaded += 1
    terminal.tr.print("Areas: " + num_str(loaded) + "/" + num_str(len(world.AREA_DEFS)) + " loaded")
    terminal.tr.print("Mobs:  " + num_str(len(world.MOB_DEFS._data)) + " tpl, "
                      + num_str(len(world.chars)) + " inst")
    terminal.tr.print("Objs:  " + num_str(len(world.ITEM_DEFS._data)) + " tpl")
    terminal.tr.print("Rooms: " + num_str(len(world.ROOM_DEFS._data)) + " def, "
                      + num_str(len(world.rooms._data)) + " active")


def _debug_heapmap(player, args):
    """Load every area one by one, printing per-area heap cost. [PRIMESUD]

    Measures the true incremental footprint of each area (defs + live
    room/mob state from its reset) via gc.mem_alloc deltas. Loads in
    _AREA_FILES order (ascending file size). Areas already loaded report
    0 and are marked with '*'. Desktop CPython has no mem_alloc; deltas
    print as n/a there but the load-all still runs.
    """
    import gc

    def _alloc():
        gc.collect()
        try:
            return gc.mem_alloc()
        except AttributeError:
            return None

    start = _alloc()
    total = 0
    terminal.tr.print("{Warea             kB   cum-kB{x")
    # Suppress per-area "[Loading area: ...]" notices between table rows
    world._LOADING_ALL = True
    try:
        for _, tag, name, _, _ in world._AREA_FILES:
            pre_loaded = world.is_area_loaded(tag)
            before = _alloc()
            if not pre_loaded:
                world._ensure_area_by_tag(tag)
            after = _alloc()
            if before is None or after is None:
                terminal.tr.print(pad_right(tag, 14) + "  n/a")
                continue
            delta = after - before
            total += delta
            terminal.tr.print(
                pad_right(tag, 14) + " " + pad_left(num_str(delta // 1024), 5)
                + " " + pad_left(num_str(total // 1024), 8)
                + (" *" if pre_loaded else ""))
    finally:
        world._LOADING_ALL = False
    if start is not None:
        terminal.tr.print("Free: " + num_str(gc.mem_free()))
    terminal.tr.print("(* = already loaded before heapmap)")


def _debug_slay(player, args):
    """Instant-kill a mob in the room (cf. 1stMud do_slay in fight.c). [PRIMESUD]

    Thin wrapper: the port lives in combat.do_slay; 1stMud's top-level imm
    command slot (#209) is retired in favour of 'debug slay'.
    """
    from combat import do_slay
    do_slay(player, args)


def _find_char_world(player, name):
    """Find player or loaded mob by name/vnum (cf. 1stMud get_char_world). [PRIMESUD]"""
    from handler import is_name

    if name in ("self", "me") or name == player.get("name", "").lower():
        return player
    if name.isdigit():
        mid = int(name)
        return world.chars.get(mid)
    for mid in sorted(world.chars):
        inst = world.chars[mid]
        if not inst.get("is_npc"):
            if name == inst.get("name", "").lower():
                return inst
            continue
        tpl = world.MOB_DEFS[inst["tpl"]]
        if is_name(name, tpl.get("keywords", "")):
            return inst
    return None


def _debug_advance(player, args):
    """Raise/lower the player to a level (cf. 1stMud do_advance in act_wiz.c). [PRIMESUD]"""
    from combat import advance_level
    from game_state import save_world

    if len(args) < 2 or not _is_int(args[1]):
        terminal.tr.print("Syntax: advance <char> <level>")
        return
    victim = _find_char_world(player, args[0])
    if victim is None:
        terminal.tr.print("That player is not here.")
        return
    if victim.get("is_npc"):
        terminal.tr.print("Not on NPC's.")
        return
    level = int(args[1])
    if level < 1 or level > MAX_LEVEL:
        terminal.tr.print("Level must be 1 to " + num_str(MAX_LEVEL) + ".")
        return

    if level <= victim["level"]:
        temp_prac = victim["practice"]
        terminal.tr.print("Lowering a player's level!")
        terminal.tr.print("**** OOOOHHHHHHHHHH  NNNNOOOO ****")
        victim["level"] = 1
        victim["xp"] = 0
        victim["max_hit"] = victim["perm_hit"] = 10
        victim["max_mana"] = victim["perm_mana"] = 100
        victim["max_move"] = victim["perm_move"] = 100
        victim["practice"] = 0
        victim["hit"] = victim["max_hit"]
        victim["mana"] = victim["max_mana"]
        victim["move"] = victim["max_move"]
        advance_level(victim)
        victim["practice"] = temp_prac
    else:
        terminal.tr.print("Raising a player's level!")
        terminal.tr.print("**** OOOOHHHHHHHHHH  YYYYEEEESSS ****")

    while victim["level"] < level:
        victim["level"] += 1
        advance_level(victim)
    victim["xp"] = 0
    victim["xp_next"] = exp_per_level(victim)
    terminal.tr.print("You are now level " + num_str(victim["level"]) + ".")
    save_world(quiet=True)


# 1stMud field name -> PrimeSUD dict key (cf. char_data_table/pcdata_data_table/
# obj_data_table in data_table.c; prefix-matched like set_struct, no aliases).
_SET_CHAR_KEYS = {
    "name": "name",
    "level": "level",
    "hit": "hit",
    "max_hit": "max_hit",
    "mana": "mana",
    "max_mana": "max_mana",
    "move": "move",
    "max_move": "max_move",
    "gold": "gold",
    "silver": "silver",
    "practice": "practice",
    "train": "train",
    "alignment": "alignment",
    "wimpy": "wimpy",
    "exp": "xp",
    "xp_next": "xp_next",  # [PRIMESUD] per-level xp model threshold
}

_SET_PC_KEYS = {
    "played": "played",
    "trivia": "trivia",
    "quest.points": "quest_points",
    "quest.time": "quest_time",
}

_SET_OBJ_KEYS = {
    "owner": "owner",
    "name": "keywords",  # 1stMud obj->name = keyword string
    "short_descr": "short_descr",
    "description": "description",
    "weight": "weight",
    "cost": "cost",
    "level": "level",
    "condition": "condition",
    "timer": "timer",
    "material": "material",
}


def _set_keys(keys):
    out = []
    for k in sorted(keys):
        out.append(k)
    terminal.tr.print(" ".join(out))


def _is_int(s):
    """True if s is a valid int literal (at most one leading '-'). [PRIMESUD]"""
    if s.startswith("-"):
        s = s[1:]
    return s.isdigit()


def _set_value(target, key, value):
    # Existing field type wins: digits into a str field stay a string
    # (e.g. "set char self name 123" must not make name an int).
    cur = target.get(key)
    if isinstance(cur, str):
        target[key] = value
    elif isinstance(cur, int):
        if not _is_int(value):
            terminal.tr.print("Value must be numeric.")
            return False
        target[key] = int(value)
    elif _is_int(value):  # absent field: guess type from the value
        target[key] = int(value)
    else:
        target[key] = value
    return True


def _debug_set_struct(table_name, target, keys, args):
    if len(args) < 2:
        _set_keys(keys)
        terminal.tr.print("Syntax: set " + table_name + " <name> <option> <value>")
        return
    field = args[0]
    value = " ".join(args[1:])
    key = None
    for candidate in sorted(keys):
        if candidate.startswith(field):
            key = keys[candidate]
            break
    if key is None:
        _set_keys(keys)
        return
    if _set_value(target, key, value):
        terminal.tr.print("Ok.")


def _set_help():
    """Print do_set syntax lines (cf. 1stMud do_set_help in act_wiz.c). [PRIMESUD]"""
    terminal.tr.print("Syntax: set char <name> <option> <value>")
    terminal.tr.print("Syntax: set player <name> <option> <value>")
    terminal.tr.print("Syntax: set object <name> <option> <value>")


def _debug_set(player, args):
    """Set live character/player/object fields (cf. 1stMud do_set in act_wiz.c). [PRIMESUD]"""
    if not args:
        _set_help()
        return
    what = args[0]
    if "character".startswith(what) or "mobile".startswith(what):
        if len(args) < 2:
            _set_keys(_SET_CHAR_KEYS)
            terminal.tr.print("Syntax: set char <name> <option> <value>")
            return
        victim = _find_char_world(player, args[1])
        if victim is None:
            terminal.tr.print("There is no such character.")
            return
        _debug_set_struct("char", victim, _SET_CHAR_KEYS, args[2:])
        return
    if "player".startswith(what):
        if len(args) < 2:
            _set_keys(_SET_PC_KEYS)
            terminal.tr.print("Syntax: set player <name> <option> <value>")
            return
        victim = _find_char_world(player, args[1])
        if victim is None or victim.get("is_npc"):
            terminal.tr.print("There is no such player.")
            return
        _debug_set_struct("player", victim, _SET_PC_KEYS, args[2:])
        return
    if "object".startswith(what):
        if len(args) < 2:
            _set_keys(_SET_OBJ_KEYS)
            terminal.tr.print("Syntax: set object <name> <option> <value>")
            return
        from item import get_obj_here, promote_obj
        obj = get_obj_here(player, args[1])
        if obj is None:
            terminal.tr.print("There is no such object.")
            return
        obj = promote_obj(player, obj)
        _debug_set_struct("object", obj, _SET_OBJ_KEYS, args[2:])
        return
    _set_help()


def _debug_holylight(player, args):
    """Toggle imm sight (cf. 1stMud do_holylight in act_wiz.c:2941).

    Not a log channel: flips gameplay visibility. Stored in DBG so the
    handler.py sight predicates (can_see, can_see_obj, check_blind) and the
    do_look pitch-black gate can short-circuit on "holylight" in DBG, the
    PLR_HOLYLIGHT equivalent. Excluded from "debug all".

    Also gates the vnum display overlay: room vnum in the look title as
    upstream (act_info.c:1136-1139); mob vnums in the room list and obj
    vnums in inventory/equipment are a [PRIMESUD] superset (upstream imms
    use stat for those).
    """
    if "holylight" in DBG:
        DBG.discard("holylight")
        terminal.tr.print("Holy light mode off.")
    else:
        DBG.add("holylight")
        terminal.tr.print("Holy light mode on.")


# Keyword index files (built by tools/build_mob_index.py). Module constants
# so desktop tests can point them at synthetic files.
MOBS_IDX = "mobs.idx"
OBJS_IDX = "objs.idx"


def _find_idx(frag, idx_file, lines, mob=False):
    """Append "[vnum] keywords (tag, unloaded)" rows for unloaded-area matches. [PRIMESUD]

    One f.read() per call (looped readline() ~20ms/call on-device); nothing
    is retained, so no area load and no lasting heap cost. Missing index
    file (desktop dev runs) degrades to loaded-area results only.
    """
    from handler import is_name

    try:
        with open(idx_file) as f:
            data = f.read()
    except OSError:
        return
    for line in data.split("\n"):
        if not line or line[0] == "#":
            continue
        parts = line.split("|", 5 if mob else 3)
        if len(parts) < (6 if mob else 3):
            continue
        tag, vnum, keywords = ((parts[1], parts[0], parts[3]) if mob
                               else (parts[0], parts[1], parts[2]))
        if tag in world._LOADED_AREAS:
            continue
        if is_name(frag, keywords):
            lines.append("[" + pad_left(vnum, 5) + "] " + keywords + " ("
                        + tag + ", unloaded)")


def _debug_vnum(player, args):
    """Find mob/obj template vnums by name, world-wide (cf. 1stMud do_vnum /
    do_mfind / do_ofind in act_wiz.c). [PRIMESUD]

    Loaded areas answer from MOB_DEFS/ITEM_DEFS in memory (short_descr
    shown); unloaded areas via the keyword indices mobs.idx / objs.idx
    (keywords shown), so no area load is forced.
    do_vnum's skill branch (do_slookup) not ported -- PrimeSUD skills are
    name-keyed (skills_table.py), there is no sn to look up.
    """
    from handler import is_name

    if not args:
        terminal.tr.print("debug vnum [mob|obj] <name>")
        return
    # cf. do_vnum: exact type word, else fall through searching both
    if args[0] in ("mob", "char"):
        if len(args) < 2:  # cf. do_mfind NullStr gate
            terminal.tr.print("Find whom?")
            return
        kinds = ("mob",)
        frag = " ".join(args[1:])
    elif args[0] == "obj":
        if len(args) < 2:  # cf. do_ofind NullStr gate
            terminal.tr.print("Find what?")
            return
        kinds = ("obj",)
        frag = " ".join(args[1:])
    else:
        kinds = ("mob", "obj")
        frag = " ".join(args)
    lines = []
    for kind in kinds:
        defs = world.MOB_DEFS if kind == "mob" else world.ITEM_DEFS
        start = len(lines)
        # ._data scan: loaded areas only, never triggers a load
        for vnum in sorted(defs._data):
            if is_name(frag, defs._data[vnum].get("keywords", "")):
                lines.append("[" + pad_left(num_str(vnum), 5) + "] "
                            + defs._data[vnum].get("short_descr", ""))
        _find_idx(frag, MOBS_IDX if kind == "mob" else OBJS_IDX, lines,
                  kind == "mob")
        if len(lines) == start:
            lines.append("No " + ("mobiles" if kind == "mob" else "objects")
                        + " by that name.")
    tpage(lines)


# Field-name prefix -> instance dict key (cf. do_flag's arg3 chain, flags.c:96).
# plr/comm not ported: player PLR_* bits are an int bitmask (player.py
# "flags", managed by the auto* commands), and there is no comm system.
# [PRIMESUD] "off" is intent-parity: flags.c:61 help advertises it but the
# dispatch chain has no off branch, so upstream can never edit off_flags.
_FLAG_CHAR_FIELDS = (
    ("act", "act_flags"), ("affected", "affected_by"), ("off", "off_flags"),
    ("immunity", "imm_flags"), ("resist", "res_flags"), ("vuln", "vuln_flags"),
    ("form", "form_flags"), ("parts", "part_flags"),
)
# NPC-only fields (cf. flags.c NPC guards on act/form/parts; off is
# [PRIMESUD]-grouped here -- mob offense bits are meaningless on a player,
# whose act bits live in the int bitmask, not act_flags).
_FLAG_NPC_ONLY = ("act_flags", "off_flags", "form_flags", "part_flags")


def _debug_flag(player, args):
    """Toggle/add/remove/set flag bits on a live char or object (cf. 1stMud
    do_flag in flags.c). [PRIMESUD]

    PrimeSUD flags are dicts of True bits, so a "bit" is a dict key. Flag
    names are not validated against a table (there is none at runtime); an
    unknown name creates an inert key, so the resulting flag set is echoed
    to make typos visible.
    """
    if len(args) < 4:
        terminal.tr.print("debug flag mob|char <name> <field> [+|-|=] <flags>")
        terminal.tr.print("debug flag obj <name> <field> [+|-|=] <flags>")
        terminal.tr.print("  char fields: act aff off imm res vuln form parts")
        terminal.tr.print("  obj fields: extra wear")
        terminal.tr.print("  +: add flag, -: remove flag, = set equal to")
        terminal.tr.print("  otherwise flag toggles the flags listed.")
        return
    what, name, field = args[0], args[1], args[2]
    target = None
    if "mobile".startswith(what) or "character".startswith(what):
        victim = _find_char_world(player, name)
        if victim is None:
            terminal.tr.print("You can't find them.")
            return
        for prefix, key in _FLAG_CHAR_FIELDS:
            if prefix.startswith(field):
                if key in _FLAG_NPC_ONLY and not victim.get("is_npc"):
                    # cf. flags.c "Use plr for PCs." / "can't be set on PCs";
                    # player PLR_* bits live in the auto* commands
                    terminal.tr.print("Can't be set on PCs.")
                    return
                target = victim.setdefault(key, {})
                break
    elif "object".startswith(what):
        from item import get_obj_here, promote_obj, ensure_item_extra_flags
        obj = get_obj_here(player, name)
        if obj is None:
            terminal.tr.print("You can't find that object.")
            return
        obj = promote_obj(player, obj)
        tpl = world.item_tpl(obj)
        if "extra".startswith(field):
            target = ensure_item_extra_flags(obj, tpl)
        elif "wear".startswith(field):
            if "wear_flags" not in obj:  # instance override, cf. item_wear_flags
                obj["wear_flags"] = dict(tpl.get("wear_flags", {}))
            target = obj["wear_flags"]
    else:
        _debug_flag(player, [])
        return
    if target is None:
        terminal.tr.print("That's not an acceptable flag.")
        return
    words = args[3:]
    op = ""
    if words[0][0] in "+-=":
        op = words[0][0]
        words = ([words[0][1:]] if len(words[0]) > 1 else []) + words[1:]
        if not words:
            terminal.tr.print("Which flags do you wish to change?")
            return
    if op == "=":
        target.clear()
    for word in words:
        w = word.lower()
        if op in ("+", "="):
            target[w] = True
        elif op == "-":
            target.pop(w, None)
        elif w in target:
            del target[w]
        else:
            target[w] = True
    terminal.tr.print(" ".join(sorted(target)) if target else "(none)")


def _debug_force(player, args):
    """Make a character run a command (cf. 1stMud do_force in act_wiz.c). [PRIMESUD]

    all/players/gods sweeps and trust gates not ported (single-player).
    The "force <vic> delete|mob" refusal is moot: neither is in the player
    command table ("mob" prog commands dispatch only inside mobprogs).
    The "$n forces you to ..." act line is skipped -- NPC-directed output
    is discarded in PrimeSUD.
    """
    from commands import interpret

    if len(args) < 2:
        terminal.tr.print("Force whom to do what?")
        return
    victim = _find_char_world(player, args[0])
    if victim is None:
        terminal.tr.print("They aren't here.")
        return
    if victim is player:
        terminal.tr.print("Aye aye, right away!")
        return
    interpret(" ".join(args[1:]), victim)
    terminal.tr.print("Ok.")


# Buff spells in qspell_table order (act_wiz.c:3219), by skill name.
_QSPELLS = ("bless", "giant strength", "haste", "frenzy", "shield", "armor",
            "sanctuary", "detect hidden", "detect invis", "stone skin",
            "bark skin", "forceshield", "staticshield", "flameshield")


def _debug_spellup(player, args):
    """Cast every qspell buff on a character (cf. 1stMud do_spellup in act_wiz.c). [PRIMESUD]

    all/room variants not ported (single-player); no-arg defaults to self.
    Cast at MAX_LEVEL (the imm get_trust equivalent); already-affected
    spells are skipped, as upstream.
    """
    from handler import is_affected
    from magic import SPELL_FUNS, TARGET_CHAR, _skill_lookup
    from skills_table import SKILLS

    victim = _find_char_world(player, args[0]) if args else player
    if victim is None:
        terminal.tr.print("They aren't here.")
        return
    for name in _QSPELLS:
        sn = _skill_lookup(name)
        if sn is None or is_affected(victim, sn):
            continue
        fun = SPELL_FUNS.get(SKILLS[sn].get("spell_fun", ""))
        if fun is not None:
            fun(sn, MAX_LEVEL, player, victim, TARGET_CHAR)
    terminal.tr.print("OK.")


def _deep_copy(v):
    """Recursive dict/list copy for instance dicts (no copy module on-device). [PRIMESUD]"""
    if isinstance(v, dict):
        out = {}
        for k in v:
            out[k] = _deep_copy(v[k])
        return out
    if isinstance(v, list):
        return [_deep_copy(x) for x in v]
    return v  # scalars and tuples (immutable) share safely


def _debug_clone(player, args):
    """Duplicate a room mob or an object here with its live state (cf. 1stMud
    do_clone in act_wiz.c). [PRIMESUD]

    Trust/level gates (obj_check) not ported (imm trust N/A solo).
    Container contents clone along via the deep copy, cf. recursive_clone.
    """
    from handler import get_char_room
    from item import get_obj_here, promote_obj

    if not args:
        terminal.tr.print("Clone what?")
        return
    name = " ".join(args)
    mob_id = get_char_room(name, world.rooms[player["room"]]["mobs"], world.chars)
    if mob_id is not None:
        inst = _deep_copy(world.chars[mob_id])
        next_id = max(world.chars, default=1) + 1
        inst["id"] = next_id
        inst["fighting"] = None
        world.chars[next_id] = inst
        world.rooms[player["room"]]["mobs"].append(next_id)
        terminal.tr.print("You clone "
                          + world.MOB_DEFS[inst["tpl"]].get("short_descr", "it") + ".")
        return
    obj = get_obj_here(player, name)
    if obj is None:
        terminal.tr.print("You don't see that here.")
        return
    obj = promote_obj(player, obj)
    clone = _deep_copy(obj)
    # cf. do_clone: carried source -> to char, else to room
    carried = (any(o is obj for o in player["inv"])
               or any(player["equip"][s] is obj for s in player["equip"]))
    if carried:
        player["inv"].append(clone)
    else:
        world.rooms[player["room"]]["items"].append(clone)
    terminal.tr.print("You clone "
                      + (obj.get("short_descr")
                         or world.item_tpl(obj).get("short_descr", "it")) + ".")


def _pstat_trigs(trigs):
    """Shared pstat trigger-table printer. [PRIMESUD]"""
    if not trigs:
        terminal.tr.print("[No programs set]")
        return
    i = 0
    for t in trigs:
        i += 1
        terminal.tr.print(
            "[" + pad_left(num_str(i), 2) + "] Trigger [" + pad_right(t[0], 8)
            + "] Program [" + pad_left(num_str(t[1]), 4) + "] Phrase [" + t[2] + "]")


def _debug_pstat(player, args):
    """Show prog triggers and live prog state for a mob, obj, or room
    (cf. 1stMud do_pstat in programs.c). [PRIMESUD]

    ``pstat <mob|vnum>`` (mob form, default), ``pstat room [vnum]``,
    ``pstat obj <name|vnum>``.  The room form defaults to the current room;
    the obj name form finds a world instance (live oprog delay/target), the
    vnum forms show the template's trigger table only.
    """
    from handler import get_char_room

    if not args:
        terminal.tr.print("debug pstat <mob|vnum> | room [vnum] | obj <name|vnum>")
        return
    sub = args[0].lower()
    rest = args[1:]
    if "room".startswith(sub):
        if not rest:
            vnum = player["room"]
        elif rest[0].isdigit():
            vnum = int(rest[0])
        else:
            terminal.tr.print("You must provide a number.")
            return
        tpl = world.ROOM_DEFS._data.get(vnum)
        if tpl is None:
            terminal.tr.print("No such room.")
            return
        terminal.tr.print("Room #" + pad_right(num_str(vnum), 6) + " ["
                          + tpl.get("name", "") + "]")
        rs = world.rooms._data.get(vnum) or {}
        tgt = rs.get("rprog_target")
        terminal.tr.print("Delay   " + pad_right(num_str(rs.get("rprog_delay", 0)), 6)
                          + " [" + ("No target" if tgt is None else num_str(tgt)) + "]")
        _pstat_trigs(tpl.get("room_triggers"))
        return
    if "object".startswith(sub):
        if not rest:
            terminal.tr.print("No such object.")
            return
        obj = None
        if rest[0].isdigit():
            vnum = int(rest[0])
        else:
            import mobprog  # deferred: keep mobprog off the boot path
            obj = mobprog._get_obj_world(player, rest[0])
            if obj is None or not isinstance(obj, dict):
                terminal.tr.print("No such object.")
                return
            vnum = obj["vnum"]
        tpl = world.ITEM_DEFS.get(vnum)
        if tpl is None:
            terminal.tr.print("No such object.")
            return
        terminal.tr.print("Object #" + pad_right(num_str(vnum), 6) + " ["
                          + tpl.get("short_descr", "") + "]")
        tgt = obj.get("oprog_target") if obj is not None else None
        terminal.tr.print("Delay   " + pad_right(num_str((obj or {}).get("oprog_delay", 0)), 6)
                          + " [" + ("No target" if tgt is None else num_str(tgt)) + "]")
        _pstat_trigs(tpl.get("obj_triggers"))
        return
    if "mobile".startswith(sub) and rest:
        args = rest  # explicit mob form: shift to the default handling below
    inst = None
    if args[0].isdigit():
        vnum = int(args[0])
    else:
        mob_id = get_char_room(args[0], world.rooms[player["room"]]["mobs"], world.chars)
        if mob_id is None:
            terminal.tr.print("No such creature.")
            return
        inst = world.chars[mob_id]
        vnum = inst["tpl"]
    tpl = world.MOB_DEFS.get(vnum)
    if tpl is None:
        terminal.tr.print("No mob template " + num_str(vnum) + ".")
        return
    terminal.tr.print("Mobile #" + pad_right(num_str(vnum), 6) + " ["
                      + tpl.get("short_descr", "") + "]")
    if inst is not None:
        tgt = inst.get("mprog_target")
        terminal.tr.print("Delay   " + pad_right(num_str(inst.get("mprog_delay", 0)), 6)
                          + " [" + ("No target" if tgt is None else num_str(tgt)) + "]")
    _pstat_trigs(tpl.get("mob_triggers"))


def _debug_pdump(player, args):
    """Page a program's source by vnum (cf. 1stMud do_pdump in programs.c). [PRIMESUD]

    Upstream keeps one global prog list shared by all three origins; here the
    vnum is looked up across MOBPROGS, OBJPROGS, and ROOMPROGS.  Progs merge
    in as their area loads, so an unloaded area's progs are not visible yet.
    """
    if not args or not args[0].isdigit():
        terminal.tr.print("debug pdump <vnum>")
        return
    v = int(args[0])
    code = (world.MOBPROGS.get(v) or world.OBJPROGS.get(v)
            or world.ROOMPROGS.get(v))
    if code is None:
        terminal.tr.print("No such program.")
        return
    tpage(code.split("\n"))


_SUBCMDS = (
    ("stat",    _debug_stat,    "dump player/mob/obj/room/area dict"),
    ("slay",    _debug_slay,    "instant-kill a mob in the room"),
    ("advance", _debug_advance, "raise/lower player to a level"),
    ("set",     _debug_set,     "edit char/player/object fields"),
    ("goto",    _debug_goto,    "teleport to room vnum or named mob"),
    ("load",    _debug_load,    "spawn mob or object by vnum"),
    ("purge",   _debug_purge,   "remove NPCs and objects in room"),
    ("restore", _debug_restore, "heal and strip maladies room-wide"),
    ("peace",   _debug_peace,   "stop all fighting in the room"),
    ("mwhere",  _debug_mwhere,  "list spawned mobs matching name"),
    ("owhere",  _debug_owhere,  "locate objects by name"),
    ("memory",  _debug_memory,  "show heap usage and world counts"),
    ("heapmap", _debug_heapmap, "load all areas, per-area heap cost"),
    ("holylight", _debug_holylight, "toggle imm sight + vnum overlay"),
    ("vnum",    _debug_vnum,    "name->vnum lookup world-wide (mob/obj)"),
    ("flag",    _debug_flag,    "toggle bit-flags on char or object"),
    ("force",   _debug_force,   "make a character run a command"),
    ("spellup", _debug_spellup, "cast all qspell buffs on a char"),
    ("clone",   _debug_clone,   "duplicate mob/object with live state"),
    ("pstat",   _debug_pstat,   "list mob/obj/room prog triggers"),
    ("pdump",   _debug_pdump,   "print a program's source by vnum"),
)


def do_debug(player, args):
    """Toggle debug channels or run imm-style debug subcommands. [PRIMESUD]"""
    if not args:
        # [PRIMESUD] help listing styled after do_commands (channels + subcommands)
        lines = ["Debug channels (debug <name> toggles, debug all):"]
        for name in _CHANNELS:
            state = "{Gon{x" if name in DBG else "{Doff{x"
            lines.append("  " + name + ": " + state)
        lines.append("Subcommands:")
        for sub in _SUBCMDS:
            desc = sub[2]
            # cf. 1stMud score "Holy Light: on/off" (act_info.c:2127) --
            # the toggle's state must be visible somewhere
            if sub[0] == "holylight":
                desc += ": " + ("{Gon{x" if "holylight" in DBG else "{Doff{x")
            lines.append("{G" + pad_right(sub[0], 9) + "{x " + desc)
        tpage(lines)
        return
    name = args[0]
    # Exact channel name always wins (e.g. "move" vs mwhere/memory prefix)
    if name in _CHANNELS:
        pass  # fall through to channel toggle below
    else:
        for sub in _SUBCMDS:
            if sub[0].startswith(name):
                sub[1](player, args[1:])
                return
    if "all".startswith(name):
        if DBG.issuperset(_CHANNELS):
            # difference_update, not clear: holylight is a mode toggle
            # (debug holylight), not a log channel -- "all" leaves it alone
            DBG.difference_update(_CHANNELS)
            terminal.tr.print("All debug channels off.")
        else:
            DBG.update(_CHANNELS)
            terminal.tr.print("All debug channels on.")
        return
    match = None
    for c in _CHANNELS:
        if c.startswith(name):
            match = c
            break
    if match is None:
        terminal.tr.print("No such debug channel: " + name)
        return
    if match in DBG:
        DBG.discard(match)
        terminal.tr.print("Debug channel '" + match + "' off.")
    else:
        DBG.add(match)
        terminal.tr.print("Debug channel '" + match + "' on.")
