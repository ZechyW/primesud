"""Debug channel toggles for playtesting. [PRIMESUD]"""

import terminal

# Active debug channels.  Callers must guard with `if "x" in DBG:` BEFORE
# building the message string -- concat costs even when discarded, and some
# call sites are in per-mob per-pulse loops.
DBG = set()

_CHANNELS = ("spawn", "move", "tick", "reset", "vnum", "save", "time")


def dbg(msg):
    """Print one debug line in dark grey. [PRIMESUD]"""
    terminal.tr.print("{D[dbg] " + msg + "{x")


def _val(v):
    """Stringify one dict value, truncated to keep the screen usable. [PRIMESUD]"""
    s = str(v)
    if len(s) > 160:
        s = s[:157] + "..."
    return s


def _dump(title, d):
    """Print a dict as sorted key/value lines (cf. 1stMud show_struct in tables.c). [PRIMESUD]"""
    terminal.tr.print("{D-- " + title + " --{x")
    for k in sorted(d.keys()):
        terminal.tr.print("{D" + str(k) + ":{x " + _val(d[k]))


def _debug_stat(player, args):
    """Dump internal entity dicts (cf. 1stMud do_stat in act_wiz.c). [PRIMESUD]

    1stMud's do_stat renders structs via show_struct/data tables; PrimeSUD
    entities are plain dicts, so we dump the dict itself -- same information,
    no per-field porting.
    """
    import world
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
                _dump("mob inst " + str(mob_id), world.chars[mob_id])
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
                _dump("obj inst (tpl " + str(obj_vnum(obj)) + ")", obj)
            else:
                # Plain-vnum room item: no instance state, show template.
                _dump("obj tpl " + str(obj), world.ITEM_DEFS[obj])
    elif "room".startswith(what):
        vnum = int(target) if target is not None and target.isdigit() else player["room"]
        rdef = world.ROOM_DEFS.get(vnum)
        if rdef is None:
            terminal.tr.print("No room " + str(vnum) + ".")
            return
        _dump("room def " + str(vnum), rdef)
        rs = world.rooms.get(vnum)
        if rs is not None:
            _dump("room state " + str(vnum), rs)
    elif "area".startswith(what):
        tag = target if target is not None else world.ROOM_DEFS[player["room"]].get("area")
        found = False
        for area in world.areas:
            if area.get("tag") == tag:
                _dump("area state " + str(tag), area)
                found = True
                break
        if not found:
            terminal.tr.print("No area '" + str(tag) + "'.")
    else:
        terminal.tr.print("Stat what? (player, mob, obj, room, area)")


def _debug_goto(player, args):
    """Teleport to a room vnum or a named mob's room (cf. 1stMud do_goto in act_wiz.c). [PRIMESUD]

    Private-room / bamfin / bamfout / invis_level checks not ported
    (single-player).  Pet moves along, as in perform_recall.
    """
    import world
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
    do_look(player, [])


def _debug_load(player, args):
    """Spawn a mob or object by vnum (cf. 1stMud do_load/do_mload/do_oload in act_wiz.c). [PRIMESUD]

    oload's optional level argument not ported -- PrimeSUD create_object
    has no level parameter.
    """
    import world

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
    import world
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
                if item_extra_flags(obj, world.ITEM_DEFS[obj_vnum(obj)]).get("nopurge")]
    terminal.tr.print("Ok.")


def _debug_restore(player, args):
    """Restore hp/mana/move and strip maladies room-wide (cf. 1stMud do_restore in act_wiz.c). [PRIMESUD]

    Always the no-arg "room" form; "all" / by-name variants not ported
    (single-player).
    """
    import world
    from handler import affect_strip
    from combat import update_pos
    from skills_table import (GSN_PLAGUE, GSN_POISON, GSN_BLINDNESS,
                              GSN_SLEEP, GSN_CURSE)

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
    import world
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
    import world
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
        terminal.tr.print("%3d) [%5d] %-20s [%5d] %s" % (
            count, inst["tpl"], tpl["short_descr"][:20], inst["room"],
            world.ROOM_DEFS.get(inst["room"], {}).get("name", "?")))
    if count == 0:
        terminal.tr.print("You didn't find any " + frag + ".")


def _debug_owhere(player, args):
    """Locate objects by name (cf. 1stMud do_owhere in act_wiz.c). [PRIMESUD]

    Searches loaded rooms (one container level deep), player inventory,
    and equipment.  Level / visibility filters not ported.
    """
    import world
    from handler import is_name
    from item import obj_vnum

    if not args:
        terminal.tr.print("Find what?")
        return
    frag = " ".join(args)
    count = [0]

    def _sd(obj):
        return ((isinstance(obj, dict) and obj.get("short_descr"))
                or world.ITEM_DEFS[obj_vnum(obj)]["short_descr"])

    def _report(obj, where):
        tpl = world.ITEM_DEFS[obj_vnum(obj)]
        if is_name(frag, tpl.get("keywords", "")):
            count[0] += 1
            terminal.tr.print("%3d) %s is %s" % (count[0], _sd(obj), where))

    # Loaded room state only -- ._data avoids triggering a full world load
    for rvnum in sorted(world.rooms._data):
        for obj in world.rooms._data[rvnum]["items"]:
            _report(obj, "in room " + str(rvnum))
            if isinstance(obj, dict):
                for inner in obj.get("contents", []):
                    _report(inner, "in " + str(_sd(obj)) + " [room " + str(rvnum) + "]")
    for obj in player["inv"]:
        _report(obj, "carried by you")
        if isinstance(obj, dict):
            for inner in obj.get("contents", []):
                _report(inner, "in " + str(_sd(obj)) + " (carried)")
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
    import world

    gc.collect()
    try:
        terminal.tr.print("Heap:  " + str(gc.mem_alloc()) + " used, "
                          + str(gc.mem_free()) + " free")
    except AttributeError:
        terminal.tr.print("Heap:  n/a (desktop)")
    # ._data lengths: len() on a LazyDict would force-load every area
    loaded = 0
    for a in world.AREA_DEFS:
        if world.is_area_loaded(a["tag"]):
            loaded += 1
    terminal.tr.print("Areas: " + str(loaded) + "/" + str(len(world.AREA_DEFS)) + " loaded")
    terminal.tr.print("Mobs:  " + str(len(world.MOB_DEFS._data)) + " tpl, "
                      + str(len(world.chars)) + " inst")
    terminal.tr.print("Objs:  " + str(len(world.ITEM_DEFS._data)) + " tpl")
    terminal.tr.print("Rooms: " + str(len(world.ROOM_DEFS._data)) + " def, "
                      + str(len(world.rooms._data)) + " active")


def _debug_slay(player, args):
    """Instant-kill a mob in the room (cf. 1stMud do_slay in fight.c). [PRIMESUD]

    Thin wrapper: the port lives in combat.do_slay; 1stMud's top-level imm
    command slot (#209) is retired in favour of 'debug slay'.
    """
    from combat import do_slay
    do_slay(player, args)


def _find_char_world(player, name):
    """Find player or loaded mob by name/vnum (cf. 1stMud get_char_world). [PRIMESUD]"""
    import world
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
    from config import MAX_LEVEL
    from classes import exp_per_level
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
        terminal.tr.print("Level must be 1 to " + str(MAX_LEVEL) + ".")
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
    terminal.tr.print("You are now level " + str(victim["level"]) + ".")
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
)


def do_debug(player, args):
    """Toggle debug channels or run imm-style debug subcommands. [PRIMESUD]"""
    if not args:
        # [PRIMESUD] help listing styled after do_commands (channels + subcommands)
        from pager import tpage
        lines = ["Debug channels (debug <name> toggles, debug all):"]
        for name in _CHANNELS:
            state = "{Gon{x" if name in DBG else "{Doff{x"
            lines.append("  " + name + ": " + state)
        lines.append("Subcommands:")
        for sub in _SUBCMDS:
            lines.append("{G%-8s{x %s" % (sub[0], sub[2]))
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
            DBG.clear()
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
