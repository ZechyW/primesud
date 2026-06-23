"""Inventory, equipment, item-use, and starter-outfit commands."""

from urandom import randint

import world
from skills_table import SKILLS, WEAPON_GSN_MAP
from world import ITEM_DEFS, MOB_DEFS
from picker import pick_from
from actor import get_curr_stat, is_name, affect_modify, equip_char, unequip_char
from item import (get_obj_list, obj_vnum, create_object, item_extra_flags,
                  item_wear_flags)
from combat import _get_weapon_skill, WaitState, check_improve, get_skill
from config import STR_APP_WIELD, PULSE_VIOLENCE
from skills_table import GSN_SCROLLS, GSN_STAVES, GSN_WANDS
from magic import cast_item_spells, validate_item_spell_payload
from area_school import (I_BANNER_WAR_MERC,
                         I_MACE_SUB_MERC, I_DAGGER_SUB_MERC, I_SWORD_SUB_MERC,
                         I_VEST_SUB_MERC, I_SHIELD_SUB_MERC,
                         I_SPEAR_SUB_MERC, I_AXE_SUB_MERC, I_FLAIL_SUB_MERC,
                         I_WHIP_SUB_MERC, I_GLAIVE_SUB_MERC)


_CONTAINER_TYPES = ("npc_corpse", "pc_corpse", "container")


def _apply_money_pickup(tr, player, obj, tpl):
    """Credit player with coin value; return True so caller skips inv append (cf. 1stMud get_obj).

    Args:
        tr: Terminal renderer.
        player (dict): Player state.
        obj (dict): Coin item instance.
        tpl (dict): Item template.

    Returns:
        bool: True if item was money and was consumed.
    """
    if tpl.get("type") != "money":
        return False
    s = obj.get("silver", 0)
    g = obj.get("gold", 0)
    player["silver"] += s
    player["gold"] += g
    if s > 0 and g > 0:
        tr.print("You pocket " + str(s) + " silver and " + str(g) + " gold coins.")
    elif g > 0:
        tr.print("You pocket " + str(g) + " gold coin" + ("s." if g != 1 else "."))
    else:
        tr.print("You pocket " + str(s) + " silver coin" + ("s." if s != 1 else "."))
    return True


def _loot_container_picker(tr, player, container):
    contents = container.get("contents", [])
    if not contents:
        tr.print("It is empty.")
        return
    names = []
    for cobj in contents:
        ctpl = ITEM_DEFS[obj_vnum(cobj)]
        names.append(cobj.get("short_descr") or ctpl["short_descr"])
    if len(contents) > 1:
        names.append("All")
    cidx = pick_from(tr, "Take what?", names)
    if cidx < 0:
        return
    if cidx == len(contents):
        for cobj in list(contents):
            ctpl = ITEM_DEFS[obj_vnum(cobj)]
            container["contents"].remove(cobj)
            if not _apply_money_pickup(tr, player, cobj, ctpl):
                player["inv"].append(cobj)
                tr.print("You get {}.".format(cobj.get("short_descr") or ctpl["short_descr"]))
        return
    cobj = contents[cidx]
    ctpl = ITEM_DEFS[obj_vnum(cobj)]
    container["contents"].remove(cobj)
    if not _apply_money_pickup(tr, player, cobj, ctpl):
        player["inv"].append(cobj)
        tr.print("You get {}.".format(cobj.get("short_descr") or ctpl["short_descr"]))


def do_get(tr, player, args):
    rs = world.rooms[player["room"]]
    if not args:
        loose = [obj for obj in reversed(rs["items"])
                 if ITEM_DEFS[obj_vnum(obj)].get("type") not in _CONTAINER_TYPES
                 and "take" in item_wear_flags(obj, ITEM_DEFS[obj_vnum(obj)])]
        conts = [obj for obj in rs["items"]
                 if ITEM_DEFS[obj_vnum(obj)].get("type") in _CONTAINER_TYPES]
        if not loose and not conts:
            tr.print("There is nothing here to pick up.")
            return
        names = []
        for obj in loose:
            tpl = ITEM_DEFS[obj_vnum(obj)]
            names.append((isinstance(obj, dict) and obj.get("short_descr")) or tpl["short_descr"])
        has_all = len(loose) > 1
        if has_all:
            names.append("All")
        cont_start = len(names)
        for obj in conts:
            tpl = ITEM_DEFS[obj_vnum(obj)]
            names.append(
                ((isinstance(obj, dict) and obj.get("short_descr")) or tpl["short_descr"])
                + " {W[loot]{x")
        idx = pick_from(tr, "Pick up what?", names)
        if idx < 0:
            return
        if idx < len(loose):
            obj = loose[idx]
            tpl = ITEM_DEFS[obj_vnum(obj)]
            rs["items"].remove(obj)
            if _apply_money_pickup(tr, player, obj, tpl):
                return
            player["inv"].append(obj)
            tr.print("You get {}.".format(
                (isinstance(obj, dict) and obj.get("short_descr")) or tpl["short_descr"]))
            return "get " + tpl.get("keywords", tpl["short_descr"]).split()[0]
        if has_all and idx == len(loose):
            for obj in list(loose):
                tpl = ITEM_DEFS[obj_vnum(obj)]
                rs["items"].remove(obj)
                if not _apply_money_pickup(tr, player, obj, tpl):
                    player["inv"].append(obj)
                    tr.print("You get {}.".format(
                        (isinstance(obj, dict) and obj.get("short_descr")) or tpl["short_descr"]))
            return
        _loot_container_picker(tr, player, conts[idx - cont_start])
        return
    arg = " ".join(args)
    if arg == "all" or arg.startswith("all."):
        filter_kw = arg[4:] if arg.startswith("all.") else None
        found = False
        for obj in list(rs["items"]):
            tpl = ITEM_DEFS[obj_vnum(obj)]
            if tpl.get("type") in _CONTAINER_TYPES:  # [PRIMESUD] skip containers; use "get all <container>"
                continue
            if filter_kw and not is_name(filter_kw, tpl.get("keywords", "")):
                continue
            found = True
            if "take" not in item_wear_flags(obj, tpl):
                tr.print("You can't take that.")
                continue
            rs["items"].remove(obj)
            if not _apply_money_pickup(tr, player, obj, tpl):
                player["inv"].append(obj)
                tr.print("You get {}.".format(tpl["short_descr"]))
        if not found:
            if filter_kw:
                tr.print("I see no {} here.".format(filter_kw))
            else:
                tr.print("I see nothing here.")
        return
    if len(args) >= 2:
        cont_arg = " ".join(args[1:])
        cont_obj = get_obj_list(cont_arg, rs["items"], ITEM_DEFS)
        if cont_obj is None:
            cont_obj = get_obj_list(cont_arg, player["inv"], ITEM_DEFS)
        if (cont_obj is not None and isinstance(cont_obj, dict)
                and ITEM_DEFS[obj_vnum(cont_obj)].get("type") in _CONTAINER_TYPES):
            item_arg = args[0]
            cont_tpl = ITEM_DEFS[obj_vnum(cont_obj)]
            contents = cont_obj.get("contents", [])
            if item_arg == "all":
                if not contents:
                    tr.print("It is empty.")
                else:
                    for cobj in list(contents):
                        ctpl = ITEM_DEFS[obj_vnum(cobj)]
                        cont_obj["contents"].remove(cobj)
                        if not _apply_money_pickup(tr, player, cobj, ctpl):
                            player["inv"].append(cobj)
                            tr.print("You get {}.".format(cobj.get("short_descr") or ctpl["short_descr"]))
                return
            cobj = get_obj_list(item_arg, contents, ITEM_DEFS)
            if cobj is None:
                tr.print("I see nothing like that in the {}.".format(
                    cont_obj.get("short_descr") or cont_tpl["short_descr"]))
                return
            ctpl = ITEM_DEFS[obj_vnum(cobj)]
            cont_obj["contents"].remove(cobj)
            if not _apply_money_pickup(tr, player, cobj, ctpl):
                player["inv"].append(cobj)
                tr.print("You get {}.".format(cobj.get("short_descr") or ctpl["short_descr"]))
            return
    obj = get_obj_list(arg, rs["items"], ITEM_DEFS)
    if obj is None:
        tr.print("I see no {} here.".format(arg))
        return
    tpl = ITEM_DEFS[obj_vnum(obj)]
    if "take" not in item_wear_flags(obj, tpl):
        tr.print("You can't take that.")
        return
    rs["items"].remove(obj)
    if not _apply_money_pickup(tr, player, obj, tpl):
        player["inv"].append(obj)
        tr.print("You get {}.".format((isinstance(obj, dict) and obj.get("short_descr")) or tpl["short_descr"]))


def do_drop(tr, player, args):
    if not args:
        if not player["inv"]:
            tr.print("You are not carrying anything.")
            return
        names = [ITEM_DEFS[obj["vnum"]]["short_descr"] for obj in player["inv"]]
        idx = pick_from(tr, "Drop what?", names)
        if idx < 0:
            return
        obj = player["inv"][idx]
        tpl = ITEM_DEFS[obj["vnum"]]
        player["inv"].remove(obj)
        world.rooms[player["room"]]["items"].append(obj)
        tr.print("You drop {}.".format(tpl["short_descr"]))
        if item_extra_flags(obj, tpl).get("melt_drop"):
            world.rooms[player["room"]]["items"].remove(obj)
            tr.print("{} dissolves into smoke.".format(tpl["short_descr"]))
            return
        return "drop " + tpl.get("keywords", tpl["short_descr"]).split()[0]
    arg = " ".join(args)
    if arg == "all" or arg.startswith("all."):
        filter_kw = arg[4:] if arg.startswith("all.") else None
        found = False
        for obj in list(player["inv"]):
            tpl = ITEM_DEFS[obj["vnum"]]
            if filter_kw and not is_name(filter_kw, tpl.get("keywords", "")):
                continue
            found = True
            player["inv"].remove(obj)
            world.rooms[player["room"]]["items"].append(obj)
            tr.print("You drop {}.".format(tpl["short_descr"]))
            if item_extra_flags(obj, tpl).get("melt_drop"):
                world.rooms[player["room"]]["items"].remove(obj)
                tr.print("{} dissolves into smoke.".format(tpl["short_descr"]))
        if not found:
            if filter_kw:
                tr.print("You are not carrying any {}.".format(filter_kw))
            else:
                tr.print("You are not carrying anything.")
        return
    obj = get_obj_list(arg, player["inv"], ITEM_DEFS)
    if obj is None:
        tr.print("You do not have that item.")
        return
    tpl = ITEM_DEFS[obj["vnum"]]
    player["inv"].remove(obj)
    world.rooms[player["room"]]["items"].append(obj)
    tr.print("You drop {}.".format(tpl["short_descr"]))
    if item_extra_flags(obj, tpl).get("melt_drop"):
        world.rooms[player["room"]]["items"].remove(obj)
        tr.print("{} dissolves into smoke.".format(tpl["short_descr"]))


def do_put(tr, player, args):
    """Put an item from inventory into a container (cf. 1stMud do_put in act_obj.c).

    Args:
        tr: Terminal renderer.
        player (dict): Player state dict.
        args (list): Parsed command arguments; first is item, rest is container (skips "in"/"on").
    """
    if len(args) < 2:
        tr.print("Put what in what?")
        return
    item_arg = args[0]
    rest = args[1:]
    if rest and rest[0] in ("in", "on"):
        rest = rest[1:]
    if not rest:
        tr.print("Put what in what?")
        return
    cont_arg = " ".join(rest)
    rs = world.rooms[player["room"]]
    cont_obj = get_obj_list(cont_arg, rs["items"], ITEM_DEFS)
    if cont_obj is None:
        cont_obj = get_obj_list(cont_arg, player["inv"], ITEM_DEFS)
    if cont_obj is None:
        tr.print("I see no {} here.".format(cont_arg))
        return
    cont_tpl = ITEM_DEFS[obj_vnum(cont_obj)]
    if cont_tpl.get("type") not in _CONTAINER_TYPES:
        tr.print("That's not a container.")
        return
    obj = get_obj_list(item_arg, player["inv"], ITEM_DEFS)
    if obj is None:
        tr.print("You do not have that item.")
        return
    if obj is cont_obj:
        tr.print("You can't fold it into itself.")
        return
    tpl = ITEM_DEFS[obj_vnum(obj)]
    player["inv"].remove(obj)
    cont_obj.setdefault("contents", []).append(obj)
    cont_name = (isinstance(cont_obj, dict) and cont_obj.get("short_descr")) or cont_tpl["short_descr"]
    tr.print("You put {} in {}.".format(tpl["short_descr"], cont_name))


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


def do_inventory(tr, player, args):
    max_carry = min(37, 17 + player["level"])
    tr.print("{YYou are carrying {W%d/%d{Y items:{x" % (len(player["inv"]), max_carry))
    if not player["inv"]:
        return
    counts = {}
    for obj in player["inv"]:
        v = obj["vnum"]
        counts[v] = counts.get(v, 0) + 1
    for v, n in counts.items():
        tpl = ITEM_DEFS[v]
        flags = _obj_flags(tpl)
        name = tpl["short_descr"]
        tr.print("  {}{} x{}".format(flags, name, n) if n > 1 else "  {}{}".format(flags, name))


_WEAR_MSG = {
    "light":    "You light {} and hold it.",
    "finger_l": "You wear {} on your left finger.",
    "finger_r": "You wear {} on your right finger.",
    "neck_1":   "You wear {} around your neck.",
    "neck_2":   "You wear {} around your neck.",
    "body":     "You wear {} on your torso.",
    "head":     "You wear {} on your head.",
    "legs":     "You wear {} on your legs.",
    "feet":     "You wear {} on your feet.",
    "hands":    "You wear {} on your hands.",
    "arms":     "You wear {} on your arms.",
    "shield":   "You wear {} as a shield.",
    "about":    "You wear {} about your torso.",
    "waist":    "You wear {} about your waist.",
    "wrist_l":  "You wear {} around your left wrist.",
    "wrist_r":  "You wear {} around your right wrist.",
    "wield":    "You wield {}.",
    "hold":     "You hold {} in your hand.",
    "float":    "You release {} and it floats next to you.",
}

_DUAL_SLOTS = {
    "finger": ("finger_l", "finger_r"),
    "neck":   ("neck_1",   "neck_2"),
    "wrist":  ("wrist_l",  "wrist_r"),
}

_WIELD_SKILL_MSG = (
    (100, "{} feels like a part of you!"),
    ( 85, "You feel quite confident with {}."),
    ( 70, "You are skilled with {}."),
    ( 50, "Your skill with {} is adequate."),
    ( 25, "{} feels a little clumsy in your hands."),
    (  1, "You fumble and almost drop {}."),
    (  0, "You don't even know which end is up on {}."),
)


def remove_obj(tr, player, slot, fReplace):
    """Unequip slot if occupied, honouring curse and fReplace flag (cf. 1stMud remove_obj in act_obj.c).

    Args:
        tr: Terminal renderer.
        player (dict): Player state dict.
        slot (str): Equipment slot key.
        fReplace (bool): If False, refuse silently when slot is occupied.

    Returns:
        bool: True if slot is free (or was successfully freed), False otherwise.
    """
    obj = player["equip"].get(slot)
    if obj is None:
        return True
    if not fReplace:
        return False
    tpl = ITEM_DEFS[obj["vnum"]]
    if item_extra_flags(obj, tpl).get("noremove"):
        tr.print("You can't remove {}.".format(tpl["short_descr"]))
        return False
    tr.print("You stop using {}.".format(tpl["short_descr"]))
    unequip_char(player, slot)
    return True


def wear_obj(tr, player, obj, fReplace):
    """Equip obj, selecting slot from wear flags (cf. 1stMud wear_obj in act_obj.c).

    Args:
        tr: Terminal renderer.
        player (dict): Player state dict.
        obj (dict): Item instance from inventory.
        fReplace (bool): Auto-remove current occupant if True; skip silently if False.
    """
    tpl = ITEM_DEFS[obj["vnum"]]
    if player["level"] < tpl.get("level", 1):
        tr.print("You must be level {} to use this object.".format(tpl.get("level", 1)))
        return

    if tpl.get("type") == "light":
        if not remove_obj(tr, player, "light", fReplace):
            return
        tr.print(_WEAR_MSG["light"].format(tpl["short_descr"]))
        equip_char(player, obj, "light")
        return

    try:
        flag = next(f for f in item_wear_flags(obj, tpl) if f != "take")
    except StopIteration:
        flag = None
    if flag is None:
        if fReplace:
            tr.print("You can't wear, wield, or hold that.")
        return

    if flag in _DUAL_SLOTS:
        slot_a, slot_b = _DUAL_SLOTS[flag]
        if (player["equip"].get(slot_a) is not None
                and player["equip"].get(slot_b) is not None):
            if not remove_obj(tr, player, slot_a, fReplace) \
                    and not remove_obj(tr, player, slot_b, fReplace):
                return
        if player["equip"].get(slot_a) is None:
            slot = slot_a
        elif player["equip"].get(slot_b) is None:
            slot = slot_b
        else:
            return
    else:
        slot = flag
        if slot not in player["equip"]:
            if fReplace:
                tr.print("You can't wear, wield, or hold that.")
            return
        if not remove_obj(tr, player, slot, fReplace):
            return

    if slot == "wield":
        wield_limit = STR_APP_WIELD[get_curr_stat(player, "str")]
        if tpl.get("weight", 0) > wield_limit * 10:
            tr.print("It is too heavy for you to wield.")
            return

    tr.print(_WEAR_MSG[slot].format(tpl["short_descr"]))
    equip_char(player, obj, slot)

    if slot == "wield":
        sn = WEAPON_GSN_MAP.get(tpl.get("weapon_type", ""), -1)
        skill = _get_weapon_skill(player, sn)
        msg = _WIELD_SKILL_MSG[-1][1]
        for threshold, m in _WIELD_SKILL_MSG[:-1]:
            if skill > threshold:
                msg = m
                break
        tr.print(msg.format(tpl["short_descr"]))


def do_wear(tr, player, args):
    """Equip an item from inventory, or wear all wearable items (cf. 1stMud do_wear in act_obj.c).

    Args:
        tr: Terminal renderer.
        player (dict): Player state dict.
        args (list): Parsed command arguments; first token may be "all".
    """
    if not args:
        equippable = []
        for obj in player["inv"]:
            tpl = ITEM_DEFS[obj["vnum"]]
            if tpl.get("type") == "light":
                slot = "light"
            else:
                try:
                    slot = next(f for f in item_wear_flags(obj, tpl)
                                if f != "take")
                except StopIteration:
                    slot = None
            if slot is not None and (slot in player["equip"] or slot in _DUAL_SLOTS):
                equippable.append((obj, tpl, slot))
        if not equippable:
            tr.print("You have nothing wearable.")
            return
        names = [tpl["short_descr"] for _, tpl, _ in equippable]
        if len(equippable) > 1:
            names.append("All")
        idx = pick_from(tr, "Wear what?", names)
        if idx < 0:
            return
        if idx == len(equippable):
            for obj, _, _ in list(equippable):
                wear_obj(tr, player, obj, False)
            return
        obj, tpl, slot = equippable[idx]
        wear_obj(tr, player, obj, True)
        return "wear " + tpl.get("keywords", tpl["short_descr"]).split()[0]
    if args[0] == "all":
        for obj in list(player["inv"]):
            wear_obj(tr, player, obj, False)
        return
    obj = get_obj_list(" ".join(args), player["inv"], ITEM_DEFS)
    if obj is None:
        tr.print("You do not have that item.")
        return
    wear_obj(tr, player, obj, True)


def do_remove(tr, player, args):
    """Remove a worn item by name and return it to inventory (cf. 1stMud do_remove in act_obj.c).

    Args:
        tr: Terminal renderer.
        player (dict): Player state dict.
        args (list): Parsed command arguments; first token may be "all".
    """
    if not args:
        worn = [(slot, obj) for slot, obj in player["equip"].items() if obj is not None]
        if not worn:
            tr.print("You aren't wearing anything.")
            return
        names = [ITEM_DEFS[obj["vnum"]]["short_descr"] for _, obj in worn]
        if len(worn) > 1:
            names.append("All")
        idx = pick_from(tr, "Remove what?", names)
        if idx < 0:
            return
        if idx == len(worn):
            for slot, obj in list(worn):
                remove_obj(tr, player, slot, True)
            return
        slot, obj = worn[idx]
        remove_obj(tr, player, slot, True)
        return "remove " + ITEM_DEFS[obj["vnum"]].get("keywords", ITEM_DEFS[obj["vnum"]]["short_descr"]).split()[0]
    if args[0] == "all":
        for slot, obj in list(player["equip"].items()):
            if obj is not None:
                remove_obj(tr, player, slot, True)
        return
    target = " ".join(args)
    for slot, obj in player["equip"].items():
        if obj is not None and is_name(target, ITEM_DEFS[obj["vnum"]].get("keywords", "")):
            remove_obj(tr, player, slot, True)
            return
    tr.print("You do not have that item.")


_WEAR_LABELS = (
    ("light",     "{g<{Wused as light{g>{x     "),
    ("finger_l",  "{g<{Wworn on finger{g>{x    "),
    ("finger_r",  "{g<{Wworn on finger{g>{x    "),
    ("neck_1",    "{g<{Wworn around neck{g>{x  "),
    ("neck_2",    "{g<{Wworn around neck{g>{x  "),
    ("body",      "{g<{Wworn on torso{g>{x     "),
    ("head",      "{g<{Wworn on head{g>{x      "),
    ("legs",      "{g<{Wworn on legs{g>{x      "),
    ("feet",      "{g<{Wworn on feet{g>{x      "),
    ("hands",     "{g<{Wworn on hands{g>{x     "),
    ("arms",      "{g<{Wworn on arms{g>{x      "),
    ("shield",    "{g<{Wworn as shield{g>{x    "),
    ("about",     "{g<{Wworn about body{g>{x   "),
    ("waist",     "{g<{Wworn about waist{g>{x  "),
    ("wrist_l",   "{g<{Wworn around wrist{g>{x "),
    ("wrist_r",   "{g<{Wworn around wrist{g>{x "),
    ("wield",     "{g<{Wwielded{g>{x           "),
    ("hold",      "{g<{Wheld{g>{x              "),
    ("float",     "{g<{Wfloating nearby{g>{x   "),
    ("secondary", "{g<{Wsecondary weapon{g>{x  "),
)


def do_equipment(tr, player, args):
    """List all equipment slots and what is worn in each (cf. 1stMud do_equipment in act_info.c).

    Args:
        tr: Terminal renderer.
        player (dict): Player state dict.
        args (list): Parsed command arguments (unused).
    """
    tr.print("You are wearing:")
    for slot, label in _WEAR_LABELS:
        obj = player["equip"].get(slot)
        if obj is not None:
            tpl = ITEM_DEFS[obj["vnum"]]
            tr.print(label + _obj_flags(tpl) + "{Y" + tpl["short_descr"] + "{x")
        else:
            tr.print(label + "nothing")


def do_second(tr, player, args):
    """Wield a weapon in the off-hand (cf. 1stMud do_second in act_obj.c)."""
    if not args:
        tr.print("Wear which weapon in your off-hand?")
        return
    obj = get_obj_list(" ".join(args), player["inv"], ITEM_DEFS)
    if obj is None:
        tr.print("You have no such thing in your backpack.")
        return
    if (player["equip"].get("shield") is not None
            or player["equip"].get("hold") is not None):
        tr.print("You cannot use a secondary weapon while using a shield or holding an item")
        return
    tpl = ITEM_DEFS[obj["vnum"]]
    if player["level"] < tpl.get("level", 1):
        tr.print("You must be level {} to use this object.".format(tpl.get("level", 1)))
        return
    if player["equip"].get("wield") is None:
        tr.print("You need to wield a primary weapon, before using a secondary one!")
        return
    wield_limit = STR_APP_WIELD[get_curr_stat(player, "str")]
    if tpl.get("weight", 0) > wield_limit // 2:
        tr.print("This weapon is too heavy to be used as a secondary weapon by you.")
        return
    primary_tpl = ITEM_DEFS[player["equip"]["wield"]["vnum"]]
    if tpl.get("weight", 0) * 2 > primary_tpl.get("weight", 0):
        tr.print("Your secondary weapon has to be considerably lighter than the primary one.")
        return
    if not remove_obj(tr, player, "secondary", True):
        return
    tr.print("You wield {} in your off-hand.".format(tpl["short_descr"]))
    equip_char(player, obj, "secondary")


def do_quaff(tr, player, args):
    """Quaff a potion (cf. 1stMud do_quaff in act_obj.c)."""
    if not args:
        tr.print("Quaff what?")
        return
    obj = get_obj_list(" ".join(args), player["inv"], ITEM_DEFS)
    if obj is None:
        tr.print("You do not have that potion.")
        return
    tpl = ITEM_DEFS[obj["vnum"]]
    if tpl["type"] != "potion":
        tr.print("You can quaff only potions.")
        return
    if player["level"] < tpl.get("level", 1):
        tr.print("This liquid is too powerful for you to drink.")
        return
    if validate_item_spell_payload(tr, obj) is None:
        return
    tr.print("You quaff {}.".format(tpl["short_descr"]))
    cast_item_spells(tr, player, obj, player, None)
    player["inv"].remove(obj)


def do_eat(tr, player, args):
    """Eat food or pill (cf. 1stMud do_eat in act_obj.c)."""
    if not args:
        tr.print("Eat what?")
        return
    obj = get_obj_list(" ".join(args), player["inv"], ITEM_DEFS)
    if obj is None:
        tr.print("You do not have that item.")
        return
    tpl = ITEM_DEFS[obj["vnum"]]
    if tpl["type"] not in ("food", "pill"):
        tr.print("That's not edible.")
        return
    if tpl["type"] == "pill" and validate_item_spell_payload(tr, obj) is None:
        return
    tr.print("You eat {}.".format(tpl["short_descr"]))
    if tpl["type"] == "pill":
        cast_item_spells(tr, player, obj, player, None)
    player["inv"].remove(obj)


def _find_here_obj(player, target_name):
    obj = get_obj_list(target_name, player["inv"], ITEM_DEFS)
    if obj is not None:
        return obj
    obj = get_obj_list(target_name, world.rooms[player["room"]]["items"], ITEM_DEFS)
    if obj is not None:
        return obj
    equipped = [it for it in player["equip"].values() if it is not None]
    return get_obj_list(target_name, equipped, ITEM_DEFS)


def _find_here_char_or_obj(player, target_name):
    for mob_id in world.rooms[player["room"]]["mobs"]:
        mob = world.chars[mob_id]
        if is_name(target_name, MOB_DEFS[mob["tpl"]].get("keywords", "")):
            return (mob, None)
    obj = _find_here_obj(player, target_name)
    return (None, obj)


def _destroy_equipped(player, slot):
    if player["equip"].get(slot) is None:
        return
    unequip_char(player, slot)
    player["inv"].pop()


def do_recite(tr, player, args):
    """Recite a scroll (cf. 1stMud do_recite in act_obj.c)."""
    arg1 = args[0] if args else ""
    arg2 = " ".join(args[1:]) if len(args) > 1 else ""
    scroll = get_obj_list(arg1, player["inv"], ITEM_DEFS)
    if scroll is None:
        tr.print("You do not have that scroll.")
        return
    tpl = ITEM_DEFS[scroll["vnum"]]
    if tpl["type"] != "scroll":
        tr.print("You can recite only scrolls.")
        return
    if player["level"] < tpl.get("level", 1):
        tr.print("This scroll is too complex for you to comprehend.")
        return
    parsed = validate_item_spell_payload(tr, scroll)
    if parsed is None:
        return
    victim = player
    obj = None
    if arg2:
        victim, obj = _find_here_char_or_obj(player, arg2)
        if victim is None and obj is None:
            tr.print("You can't find it.")
            return
    tr.print("You recite {}.".format(tpl["short_descr"]))
    if randint(1, 100) >= 20 + get_skill(player, GSN_SCROLLS) * 4 // 5:
        tr.print("You mispronounce a syllable.")
        check_improve(tr, player, GSN_SCROLLS, False, 2)
    else:
        cast_item_spells(tr, player, scroll, victim, obj)
        check_improve(tr, player, GSN_SCROLLS, True, 2)
    player["inv"].remove(scroll)


def do_brandish(tr, player, args):
    """Brandish a held staff (cf. 1stMud do_brandish in act_obj.c)."""
    staff = player["equip"].get("hold")
    if staff is None:
        tr.print("You hold nothing in your hand.")
        return
    tpl = ITEM_DEFS[staff["vnum"]]
    if tpl["type"] != "staff":
        tr.print("You can brandish only with a staff.")
        return
    parsed = validate_item_spell_payload(tr, staff)
    if parsed is None:
        return
    _level, payload = parsed
    sn_target = None
    if payload:
        from magic import _skill_lookup
        sn_target = _skill_lookup(payload[0])
    WaitState(player, 2 * PULSE_VIOLENCE)
    if staff.get("charges", tpl.get("charges", tpl.get("max_charges", 0))) > 0:
        tr.print("You brandish {}.".format(tpl["short_descr"]))
        if player["level"] < tpl.get("level", 1) or randint(1, 100) >= 20 + get_skill(player, GSN_STAVES) * 4 // 5:
            tr.print("You fail to invoke {}.".format(tpl["short_descr"]))
            check_improve(tr, player, GSN_STAVES, False, 2)
        else:
            target_type = None
            if sn_target is not None:
                target_type = SKILLS[sn_target].get("target")
            if target_type in ("ignore", "char_self", "char_defensive", "obj_char_defensive"):
                cast_item_spells(tr, player, staff, player, None)
                check_improve(tr, player, GSN_STAVES, True, 2)
            elif target_type in ("char_offensive", "obj_char_offensive"):
                for mob_id in list(world.rooms[player["room"]]["mobs"]):
                    if mob_id in world.chars:
                        cast_item_spells(tr, player, staff, world.chars[mob_id], None)
                        check_improve(tr, player, GSN_STAVES, True, 2)
            else:
                tr.print("[DEV] " + tpl["short_descr"] + ": unsupported staff target")
                return
    staff["charges"] = staff.get("charges", tpl.get("charges", tpl.get("max_charges", 0))) - 1
    if staff["charges"] <= 0:
        tr.print("Your {} blazes bright and is gone.".format(tpl["short_descr"]))
        _destroy_equipped(player, "hold")


def do_zap(tr, player, args):
    """Zap with a held wand (cf. 1stMud do_zap in act_obj.c)."""
    arg = " ".join(args)
    if not arg and player.get("fighting") is None:
        tr.print("Zap whom or what?")
        return
    wand = player["equip"].get("hold")
    if wand is None:
        tr.print("You hold nothing in your hand.")
        return
    tpl = ITEM_DEFS[wand["vnum"]]
    if tpl["type"] != "wand":
        tr.print("You can zap only with a wand.")
        return
    if validate_item_spell_payload(tr, wand) is None:
        return
    victim = None
    obj = None
    if not arg:
        victim = world.chars.get(player.get("fighting"))
        if victim is None:
            tr.print("Zap whom or what?")
            return
    else:
        victim, obj = _find_here_char_or_obj(player, arg)
        if victim is None and obj is None:
            tr.print("You can't find it.")
            return
    WaitState(player, 2 * PULSE_VIOLENCE)
    if wand.get("charges", tpl.get("charges", tpl.get("max_charges", 0))) > 0:
        if victim is not None:
            tr.print("You zap " + MOB_DEFS[victim["tpl"]]["short_descr"] + " with " + tpl["short_descr"] + ".")
        else:
            tr.print("You zap " + ITEM_DEFS[obj["vnum"]]["short_descr"] + " with " + tpl["short_descr"] + ".")
        if player["level"] < tpl.get("level", 1) or randint(1, 100) >= 20 + get_skill(player, GSN_WANDS) * 4 // 5:
            tr.print("Your efforts with {} produce only smoke and sparks.".format(tpl["short_descr"]))
            check_improve(tr, player, GSN_WANDS, False, 2)
        else:
            cast_item_spells(tr, player, wand, victim, obj)
            check_improve(tr, player, GSN_WANDS, True, 2)
    wand["charges"] = wand.get("charges", tpl.get("charges", tpl.get("max_charges", 0))) - 1
    if wand["charges"] <= 0:
        tr.print("Your {} explodes into fragments.".format(tpl["short_descr"]))
        _destroy_equipped(player, "hold")


# Weapon choices for do_outfit; order mirrors 1stMud weapon_table (const.c); sword is
# default/tie-winner and handled separately as the seed value.
_WEAPON_OUTFIT_CHOICES = [
    ("mace",    I_MACE_SUB_MERC),
    ("dagger",  I_DAGGER_SUB_MERC),
    ("spear",   I_SPEAR_SUB_MERC),
    ("axe",     I_AXE_SUB_MERC),
    ("flail",   I_FLAIL_SUB_MERC),
    ("whip",    I_WHIP_SUB_MERC),
    ("polearm", I_GLAIVE_SUB_MERC),
]


def do_outfit(tr, player, args):
    """Equip a new character with Mud School starter gear (cf. 1stMud do_outfit in act_wiz.c).

    Fills only empty slots; skips any slot already occupied.  Weapon type is
    chosen by highest skill in player["learned"], defaulting to sword on ties
    (mirrors 1stMud weapon_table loop).  Also called at character creation
    (game_state.py new_game) with no level restriction concern since level=1.

    Deviations from 1stMud:
      - No NPC guard (no NPCs in PrimeSUD).
      - obj->cost = 0 applied to weapon too (1stMud omits it for the weapon).

    Args:
        tr: Terminal renderer.
        player (dict): Player instance dict.
        args (str): Unused.
    """
    if player["level"] > 5:
        tr.print("Find it yourself!")
        return

    def _equip(slot, vnum):
        if player["equip"].get(slot) is not None:
            return
        obj = create_object(vnum)
        obj["cost"] = 0   # cf. 1stMud do_outfit: obj->cost = 0 (weapon excepted upstream)
        player["inv"].append(obj)  # obj_to_char equivalent
        equip_char(player, obj, slot)

    _equip("light", I_BANNER_WAR_MERC)
    _equip("body",  I_VEST_SUB_MERC)

    if player["equip"].get("wield") is None:
        wield_vnum = I_SWORD_SUB_MERC
        best_pct = player["learned"].get(WEAPON_GSN_MAP.get("sword", -1), 0)
        for wtype, vnum in _WEAPON_OUTFIT_CHOICES:
            pct = player["learned"].get(WEAPON_GSN_MAP.get(wtype, -1), 0)
            if pct > best_pct:
                best_pct = pct
                wield_vnum = vnum
        _equip("wield", wield_vnum)

    wobj = player["equip"].get("wield")
    if not (wobj and ITEM_DEFS[wobj["vnum"]].get("weapon_flags", {}).get("two_hands")):
        _equip("shield", I_SHIELD_SUB_MERC)

    tr.print("You have been equipped by the gods.")


def _sacrifice_one(tr, player, obj, rs):
    """Sacrifice a single room item for silver (inner helper for do_sacrifice).

    Args:
        tr: Terminal renderer.
        player (dict): Player state dict.
        obj: Item instance dict from rs["items"].
        rs (dict): Current room state dict.
    """
    tpl = ITEM_DEFS[obj_vnum(obj)]

    if tpl.get("type") == "pc_corpse" and obj.get("contents"):
        tr.print("Your deity wouldn't like that.")
        return

    wear = item_wear_flags(obj, tpl)
    extra = item_extra_flags(obj, tpl)
    if "take" not in wear or extra.get("no_sac"):
        short = obj.get("short_descr") or tpl["short_descr"]
        tr.print(short + " is not an acceptable sacrifice.")
        return

    silver = max(1, tpl.get("level", 0) * 3)
    if tpl.get("type") not in ("npc_corpse", "pc_corpse"):
        silver = min(silver, obj.get("cost", 0))
    silver = max(1, silver)

    if silver == 1:
        tr.print("Your deity gives you one silver coin for your sacrifice.")
    else:
        tr.print("Your deity gives you " + str(silver) + " silver coins for your sacrifice.")

    player["silver"] = player.get("silver", 0) + silver

    short = obj.get("short_descr") or tpl["short_descr"]
    tr.print("You sacrifice " + short + " to your deity.")
    rs["items"].remove(obj)


def do_sacrifice(tr, player, args):
    """Sacrifice a room item to the deity for silver (cf. 1stMud do_sacrifice in act_obj.c).

    Args:
        tr: Terminal renderer.
        player (dict): Player state dict.
        args (list): Parsed command arguments.
    """
    rs = world.rooms[player["room"]]

    if not args or " ".join(args) == player.get("name", "").lower():
        tr.print("Your deity appreciates your offer and may accept it later.")
        return

    arg = " ".join(args)

    if arg == "all":
        for obj in list(rs["items"]):
            _sacrifice_one(tr, player, obj, rs)
        return

    obj = get_obj_list(arg, rs["items"], ITEM_DEFS)
    if obj is None:
        tr.print("You can't find it.")
        return

    _sacrifice_one(tr, player, obj, rs)
