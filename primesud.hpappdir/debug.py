"""Debug channel toggles for playtesting. [PRIMESUD]"""

import terminal

# Active debug channels.  Callers must guard with `if "x" in DBG:` BEFORE
# building the message string -- concat costs even when discarded, and some
# call sites are in per-mob per-pulse loops.
DBG = set()

_CHANNELS = ("spawn", "move", "tick", "reset", "vnum", "save")


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


def do_debug(player, args):
    """Toggle debug channels or dump entity data; no args lists channel states. [PRIMESUD]"""
    if not args:
        terminal.tr.print("Debug channels:")
        for name in _CHANNELS:
            state = "{Gon{x" if name in DBG else "{Doff{x"
            terminal.tr.print("  " + name + ": " + state)
        terminal.tr.print("Also: debug stat ...")
        return
    name = args[0]
    if "stat".startswith(name):
        _debug_stat(player, args[1:])
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
