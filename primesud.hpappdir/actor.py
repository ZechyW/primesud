from config import MAX_STATS, STR_APP_TOHIT, STR_APP_TODAM, DEX_APP_DEF
from world import ITEM_TEMPLATES


# -- Stat application helpers --------------------------------------------------

def get_curr_stat(char, stat):
    """Effective stat value: base + affect modifiers (cf. 1stMud get_curr_stat in handler.c).

    Args:
        char (dict): Character state dict (player or mob instance).
        stat (str): Stat name -- one of "str", "dex", "int", "wis", "con".

    Returns:
        int: Clamped stat value in [3, MAX_STATS].
    """
    v = char.get(stat, 10) + char.get("mod_stat", {}).get(stat, 0)
    return max(3, min(MAX_STATS, v))


def affect_modify(char, loc, modifier, add):
    """Apply or remove a stat modifier for one affect location (cf. 1stMud affect_modify in handler.c).

    Mutates hp_max, mp_max, AC, hitroll, damroll directly; accumulates
    str/dex/int/wis/con into char["mod_stat"] (cf. 1stMud mod_stat[] in handler.c).

    Args:
        char (dict): Character state dict (player or mob instance).
        loc (str): Affect location -- one of "str", "dex", "int", "wis", "con",
            "hp", "mp", "AC", "hitroll", "damroll".
        modifier (int): Raw modifier value (positive = bonus).
        add (bool): True to apply, False to remove.
    """
    if not add:
        modifier = -modifier
    if loc == "hp":
        char["hp_max"] = max(1, char["hp_max"] + modifier)
    elif loc == "mp":
        char["mp_max"] = max(1, char["mp_max"] + modifier)
    elif loc == "AC":
        char["AC"] += modifier
    elif loc == "hitroll":
        char["hitroll"] += modifier
    elif loc == "damroll":
        char["damroll"] += modifier
    elif loc in ("str", "dex", "int", "wis", "con"):
        ms = char.setdefault("mod_stat", {})
        ms[loc] = ms.get(loc, 0) + modifier


def affect_to_char(char, sn, loc, modifier, duration):
    """Apply a timed affect to a character (cf. 1stMud affect_to_char in handler.c).

    Stores the affect in char["affects"] keyed by sn (skill/spell number) and
    immediately applies the modifier via affect_modify.  Overwrites any existing
    affect with the same sn.

    Args:
        char (dict): Character state dict (player or mob instance).
        sn (int): Skill/spell number identifying this affect.
        loc (str): Affect location (see affect_modify).
        modifier (int): Stat modifier value.
        duration (int): Duration in ticks (>= 1).
    """
    existing = char["affects"].get(sn)
    if existing is not None:
        affect_modify(char, existing["loc"], existing["modifier"], False)
    char["affects"][sn] = {"loc": loc, "modifier": modifier, "duration": duration}
    affect_modify(char, loc, modifier, True)


def affect_remove(char, sn):
    """Remove an active affect from a character (cf. 1stMud affect_remove in handler.c).

    Unapplies the modifier via affect_modify then deletes the entry from
    char["affects"].  No-op if sn is not in the affects dict.

    Args:
        char (dict): Character state dict (player or mob instance).
        sn (int): Skill/spell number to remove.
    """
    aff = char["affects"].pop(sn, None)
    if aff is not None:
        affect_modify(char, aff["loc"], aff["modifier"], False)


def get_hitroll(char):
    """Effective hitroll: base + STR bonus + equipped weapon bonus (cf. 1stMud GetHitroll macro in macro.h).

    Args:
        char (dict): Character state dict (player or mob instance).

    Returns:
        int: Total hitroll modifier.
    """
    return char.get("hitroll", 0) + STR_APP_TOHIT[get_curr_stat(char, "str")]


def get_damroll(char):
    """Effective damroll: base + STR bonus + equipped weapon bonus (cf. 1stMud GetDamroll macro in macro.h).

    Args:
        char (dict): Character state dict (player or mob instance).

    Returns:
        int: Total damroll modifier.
    """
    return char.get("damroll", 0) + STR_APP_TODAM[get_curr_stat(char, "str")]


def get_AC(char):
    """Effective AC: base + DEX bonus + equipped armour bonus.

    Args:
        char (dict): Character state dict (player or mob instance).

    Returns:
        int: Total AC (lower is better; negative is excellent).
    """
    return char.get("AC", 100) + DEX_APP_DEF[get_curr_stat(char, "dex")]


def is_name(fragment, namelist):
    """True if every word in fragment prefix-matches a word in namelist (cf. 1stMud is_name).

    Args:
        fragment (str): Space-separated words typed by the player.
        namelist (str): Space-separated keywords from the mob/item template.

    Returns:
        bool: True if all fragment words prefix-match at least one keyword.
    """
    if not fragment or not namelist:
        return False
    keywords = namelist.lower().split()
    for part in fragment.lower().split():
        if not any(kw.startswith(part) for kw in keywords):
            return False
    return True


def unequip_char(char, slot):
    """Remove obj from slot, reverse stat_bonuses, return to inventory (cf. 1stMud unequip_char in handler.c)."""
    obj = char["equip"][slot]
    tpl = ITEM_TEMPLATES[obj["vnum"]]
    for loc, mod in tpl.get("stat_bonuses", {}).items():
        affect_modify(char, loc, mod, False)
    char["equip"][slot] = None
    char["inv"].append(obj)


def equip_char(char, obj, slot):
    """Seat obj in slot and apply stat_bonuses (cf. 1stMud equip_char in handler.c)."""
    tpl = ITEM_TEMPLATES[obj["vnum"]]
    char["inv"].remove(obj)
    char["equip"][slot] = obj
    for loc, mod in tpl.get("stat_bonuses", {}).items():
        affect_modify(char, loc, mod, True)


