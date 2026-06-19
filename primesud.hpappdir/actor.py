"""Shared actor stat, affect, equipment, and name-match helpers."""

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
    elif loc == "saving_throw":
        char["saving_throw"] = char.get("saving_throw", 0) + modifier
    elif loc in ("str", "dex", "int", "wis", "con"):
        ms = char.setdefault("mod_stat", {})
        ms[loc] = ms.get(loc, 0) + modifier


def is_affected(char, sn):
    """Return True if char has a spell affect type (cf. 1stMud is_affected in handler.c)."""
    return affect_find(char, sn) is not None


def affect_find(char, sn):
    """Return first affect of type sn, or None (cf. 1stMud affect_find in handler.c)."""
    for af in char.get("affect_list", []):
        if af.get("type") == sn:
            return af
    return None


def affect_to_char(char, af):
    """Apply a 1stMud-style timed affect to a character (cf. 1stMud affect_to_char in handler.c).

    Args:
        char (dict): Character state dict (player or mob instance).
        af (dict): Affect with type, level, duration, location, modifier, bitvector.
    """
    cur = dict(af)
    char.setdefault("affect_list", []).append(cur)
    affect_modify(char, cur.get("location", "none"), cur.get("modifier", 0), True)
    bit = cur.get("bitvector", "")
    if bit:
        char.setdefault("aff_flags", {})[bit] = True


def affect_remove(char, af):
    """Remove one active affect from a character (cf. 1stMud affect_remove in handler.c)."""
    affects = char.get("affect_list", [])
    if af in affects:
        affects.remove(af)
    affect_modify(char, af.get("location", "none"), af.get("modifier", 0), False)
    _rebuild_aff_flags(char)


def affect_strip(char, sn):
    """Remove all affects of type sn (cf. 1stMud affect_strip in handler.c)."""
    for af in list(char.get("affect_list", [])):
        if af.get("type") == sn:
            affect_remove(char, af)


def _rebuild_aff_flags(char):
    flags = {}
    for af in char.get("affect_list", []):
        bit = af.get("bitvector", "")
        if bit:
            flags[bit] = True
    if flags:
        char["aff_flags"] = flags
    elif "aff_flags" in char:
        char["aff_flags"] = {}


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


def _apply_item_modifiers(char, obj, tpl, add):
    """Apply template bonuses and runtime object affects for equipped item."""
    for loc, mod in tpl.get("stat_bonuses", {}).items():
        affect_modify(char, loc, mod, add)
    for af in obj.get("affect_list", []):
        loc = af.get("location", "none")
        mod = af.get("modifier", 0)
        if loc != "none" and mod != 0:
            affect_modify(char, loc, mod, add)


def unequip_char(char, slot):
    """Remove obj from slot, reverse stat_bonuses, return to inventory (cf. 1stMud unequip_char in handler.c)."""
    obj = char["equip"][slot]
    tpl = ITEM_TEMPLATES[obj["vnum"]]
    _apply_item_modifiers(char, obj, tpl, False)
    char["equip"][slot] = None
    char["inv"].append(obj)


def equip_char(char, obj, slot):
    """Seat obj in slot and apply stat_bonuses (cf. 1stMud equip_char in handler.c)."""
    tpl = ITEM_TEMPLATES[obj["vnum"]]
    char["inv"].remove(obj)
    char["equip"][slot] = obj
    _apply_item_modifiers(char, obj, tpl, True)

