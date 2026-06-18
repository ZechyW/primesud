from world import ITEM_TEMPLATES, WEAPON_GSN_MAP
from picker import pick_from
from actor import get_curr_stat, is_name, affect_modify, unequip_char, equip_char
from item import (get_obj_list, obj_vnum, create_object, item_extra_flags,
                  item_wear_flags)
from combat import _get_weapon_skill
from config import STR_APP_WIELD
from area_school import (I_BANNER_WAR_MERC,
                         I_MACE_SUB_MERC, I_DAGGER_SUB_MERC, I_SWORD_SUB_MERC,
                         I_VEST_SUB_MERC, I_SHIELD_SUB_MERC,
                         I_SPEAR_SUB_MERC, I_AXE_SUB_MERC, I_FLAIL_SUB_MERC)


def do_get(tr, player, args, world):
    rs = world["rooms"][player["room"]]
    if not args:
        takeable = [obj for obj in reversed(rs["items"])
                    if "take" in item_wear_flags(obj, ITEM_TEMPLATES[obj_vnum(obj)])]
        if not takeable:
            tr.print("There is nothing here to pick up.")
            return
        names = [ITEM_TEMPLATES[obj_vnum(obj)]["short_descr"] for obj in takeable]
        idx = pick_from(tr, "Pick up what?", names)
        if idx < 0:
            return
        obj = takeable[idx]
        tpl = ITEM_TEMPLATES[obj_vnum(obj)]
        rs["items"].remove(obj)
        player["inv"].append(obj)
        tr.print("You get {}.".format(tpl["short_descr"]))
        return
    arg = " ".join(args)
    if arg == "all" or arg.startswith("all."):
        filter_kw = arg[4:] if arg.startswith("all.") else None
        found = False
        for obj in list(rs["items"]):
            tpl = ITEM_TEMPLATES[obj_vnum(obj)]
            if filter_kw and not is_name(filter_kw, tpl.get("keywords", "")):
                continue
            found = True
            if "take" not in item_wear_flags(obj, tpl):
                tr.print("You can't take that.")
                continue
            rs["items"].remove(obj)
            player["inv"].append(obj)
            tr.print("You get {}.".format(tpl["short_descr"]))
        if not found:
            if filter_kw:
                tr.print("I see no {} here.".format(filter_kw))
            else:
                tr.print("I see nothing here.")
        return
    obj = get_obj_list(arg, rs["items"], ITEM_TEMPLATES)
    if obj is None:
        tr.print("I see no {} here.".format(arg))
        return
    tpl = ITEM_TEMPLATES[obj_vnum(obj)]
    if "take" not in item_wear_flags(obj, tpl):
        tr.print("You can't take that.")
        return
    rs["items"].remove(obj)
    player["inv"].append(obj)
    tr.print("You get {}.".format(tpl["short_descr"]))


def do_drop(tr, player, args, world):
    if not args:
        if not player["inv"]:
            tr.print("You are not carrying anything.")
            return
        names = [ITEM_TEMPLATES[obj["vnum"]]["short_descr"] for obj in player["inv"]]
        idx = pick_from(tr, "Drop what?", names)
        if idx < 0:
            return
        obj = player["inv"][idx]
        tpl = ITEM_TEMPLATES[obj["vnum"]]
        player["inv"].remove(obj)
        world["rooms"][player["room"]]["items"].append(obj)
        tr.print("You drop {}.".format(tpl["short_descr"]))
        return
    arg = " ".join(args)
    if arg == "all" or arg.startswith("all."):
        filter_kw = arg[4:] if arg.startswith("all.") else None
        found = False
        for obj in list(player["inv"]):
            tpl = ITEM_TEMPLATES[obj["vnum"]]
            if filter_kw and not is_name(filter_kw, tpl.get("keywords", "")):
                continue
            found = True
            player["inv"].remove(obj)
            world["rooms"][player["room"]]["items"].append(obj)
            tr.print("You drop {}.".format(tpl["short_descr"]))
        if not found:
            if filter_kw:
                tr.print("You are not carrying any {}.".format(filter_kw))
            else:
                tr.print("You are not carrying anything.")
        return
    obj = get_obj_list(arg, player["inv"], ITEM_TEMPLATES)
    if obj is None:
        tr.print("You do not have that item.")
        return
    tpl = ITEM_TEMPLATES[obj["vnum"]]
    player["inv"].remove(obj)
    world["rooms"][player["room"]]["items"].append(obj)
    tr.print("You drop {}.".format(tpl["short_descr"]))


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


def do_inventory(tr, player, args, world):
    max_carry = min(37, 17 + player["level"])
    tr.print("{YYou are carrying {W%d/%d{Y items:{x" % (len(player["inv"]), max_carry))
    if not player["inv"]:
        return
    counts = {}
    for obj in player["inv"]:
        v = obj["vnum"]
        counts[v] = counts.get(v, 0) + 1
    for v, n in counts.items():
        tpl = ITEM_TEMPLATES[v]
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
    tpl = ITEM_TEMPLATES[obj["vnum"]]
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
    tpl = ITEM_TEMPLATES[obj["vnum"]]
    if player["level"] < tpl.get("level", 1):
        tr.print("You must be level {} to use this object.".format(tpl.get("level", 1)))
        return

    if tpl.get("type") == "light":
        if not remove_obj(tr, player, "light", fReplace):
            return
        tr.print(_WEAR_MSG["light"].format(tpl["short_descr"]))
        equip_char(player, obj, "light")
        return

    flag = next((f for f in item_wear_flags(obj, tpl) if f != "take"), None)
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


def do_wear(tr, player, args, world):
    """Equip an item from inventory, or wear all wearable items (cf. 1stMud do_wear in act_obj.c).

    Args:
        tr: Terminal renderer.
        player (dict): Player state dict.
        args (list): Parsed command arguments; first token may be "all".
        world (dict): Game world state (keys: rooms, mobs, areas); unused.
    """
    if not args:
        equippable = []
        for obj in player["inv"]:
            tpl = ITEM_TEMPLATES[obj["vnum"]]
            slot = "light" if tpl.get("type") == "light" else next(
                (f for f in item_wear_flags(obj, tpl) if f != "take"), None)
            if slot is not None and (slot in player["equip"] or slot in _DUAL_SLOTS):
                equippable.append((obj, tpl, slot))
        if not equippable:
            tr.print("You have nothing wearable.")
            return
        names = [tpl["short_descr"] for _, tpl, _ in equippable]
        idx = pick_from(tr, "Wear what?", names)
        if idx < 0:
            return
        obj, tpl, slot = equippable[idx]
        wear_obj(tr, player, obj, True)
        return
    if args[0] == "all":
        for obj in list(player["inv"]):
            wear_obj(tr, player, obj, False)
        return
    obj = get_obj_list(" ".join(args), player["inv"], ITEM_TEMPLATES)
    if obj is None:
        tr.print("You do not have that item.")
        return
    wear_obj(tr, player, obj, True)


def do_remove(tr, player, args, world):
    """Remove a worn item by name and return it to inventory (cf. 1stMud do_remove in act_obj.c).

    Args:
        tr: Terminal renderer.
        player (dict): Player state dict.
        args (list): Parsed command arguments; first token may be "all".
        world (dict): Game world state (keys: rooms, mobs, areas); unused.
    """
    if not args:
        worn = [(slot, obj) for slot, obj in player["equip"].items() if obj is not None]
        if not worn:
            tr.print("You aren't wearing anything.")
            return
        names = [ITEM_TEMPLATES[obj["vnum"]]["short_descr"] for _, obj in worn]
        idx = pick_from(tr, "Remove what?", names)
        if idx < 0:
            return
        slot, obj = worn[idx]
        remove_obj(tr, player, slot, True)
        return
    if args[0] == "all":
        for slot, obj in list(player["equip"].items()):
            if obj is not None:
                remove_obj(tr, player, slot, True)
        return
    target = " ".join(args)
    for slot, obj in player["equip"].items():
        if obj is not None and is_name(target, ITEM_TEMPLATES[obj["vnum"]].get("keywords", "")):
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


def do_equipment(tr, player, args, world):
    """List all equipment slots and what is worn in each (cf. 1stMud do_equipment in act_info.c).

    Args:
        tr: Terminal renderer.
        player (dict): Player state dict.
        args (list): Parsed command arguments (unused).
        world (dict): Game world state (keys: rooms, mobs, areas); unused.
    """
    tr.print("You are wearing:")
    for slot, label in _WEAR_LABELS:
        obj = player["equip"].get(slot)
        if obj is not None:
            tpl = ITEM_TEMPLATES[obj["vnum"]]
            tr.print(label + _obj_flags(tpl) + "{Y" + tpl["short_descr"] + "{x")
        else:
            tr.print(label + "nothing")


def do_second(tr, player, args, world):
    """Wield a weapon in the off-hand (cf. 1stMud do_second in act_obj.c)."""
    if not args:
        tr.print("Wear which weapon in your off-hand?")
        return
    obj = get_obj_list(" ".join(args), player["inv"], ITEM_TEMPLATES)
    if obj is None:
        tr.print("You have no such thing in your backpack.")
        return
    if (player["equip"].get("shield") is not None
            or player["equip"].get("hold") is not None):
        tr.print("You cannot use a secondary weapon while using a shield or holding an item")
        return
    tpl = ITEM_TEMPLATES[obj["vnum"]]
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
    primary_tpl = ITEM_TEMPLATES[player["equip"]["wield"]["vnum"]]
    if tpl.get("weight", 0) * 2 > primary_tpl.get("weight", 0):
        tr.print("Your secondary weapon has to be considerably lighter than the primary one.")
        return
    if not remove_obj(tr, player, "secondary", True):
        return
    tr.print("You wield {} in your off-hand.".format(tpl["short_descr"]))
    equip_char(player, obj, "secondary")


def do_quaff(tr, player, args, world):
    if not args:
        tr.print("Use what?")
        return
    obj = get_obj_list(" ".join(args), player["inv"], ITEM_TEMPLATES)
    if obj is None:
        tr.print("You're not carrying that.")
        return
    tpl = ITEM_TEMPLATES[obj["vnum"]]
    if tpl["type"] != "consumable":
        tr.print("You can't use that.")
        return
    player["inv"].remove(obj)
    if "use_hp" in tpl:
        gained = min(tpl["use_hp"], player["hp_max"] - player["hp"])
        player["hp"] += gained
        tr.print("You drink the {}. +{} HP. ({}/{})".format(
            tpl["short_descr"], gained, player["hp"], player["hp_max"]))


# Weapon choices for do_outfit; sword is the default/tie-winner (cf. 1stMud weapon_table in const.c).
_WEAPON_OUTFIT_CHOICES = [
    ("mace",   I_MACE_SUB_MERC),
    ("dagger", I_DAGGER_SUB_MERC),
    ("spear",  I_SPEAR_SUB_MERC),
    ("axe",    I_AXE_SUB_MERC),
    ("flail",  I_FLAIL_SUB_MERC),
]


def do_outfit(tr, player, args, world):
    """Equip a new character with Mud School starter gear (cf. 1stMud do_outfit in act_wiz.c).

    Fills only empty slots; skips any slot already occupied.  Weapon type is
    chosen by highest skill in player["learned"], defaulting to sword on ties
    (mirrors 1stMud weapon_table loop).  Also called at character creation
    (primesud.py new_game) with no level restriction concern since level=1.

    Deviations from 1stMud:
      - No NPC guard (no NPCs in PrimeSUD).
      - obj->cost = 0 applied to weapon too (1stMud omits it for the weapon).
      - equip_char skipped; direct slot assignment + affect_modify (same net state).

    Args:
        tr: Terminal renderer.
        player (dict): Player instance dict.
        args (str): Unused.
        world: Unused.
    """
    if player["level"] > 5:
        tr.print("Find it yourself!")
        return

    def _equip(slot, vnum):
        if player["equip"].get(slot) is not None:
            return
        obj = create_object(vnum)
        obj["cost"] = 0   # cf. 1stMud do_outfit: obj->cost = 0
        player["equip"][slot] = obj
        for loc, mod in ITEM_TEMPLATES[vnum].get("stat_bonuses", {}).items():
            affect_modify(player, loc, mod, True)

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
    if not (wobj and ITEM_TEMPLATES[wobj["vnum"]].get("weapon_flags", {}).get("two_hands")):
        _equip("shield", I_SHIELD_SUB_MERC)

    tr.print("You have been equipped by the gods.")


