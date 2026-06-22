"""Shared actor stat, affect, equipment, and name-match helpers."""

from config import (MAX_STATS, STR_APP_TOHIT, STR_APP_TODAM, DEX_APP_DEF,
                    AC_PIERCE, AC_BASH, AC_SLASH, AC_EXOTIC)
from world import ITEM_TEMPLATES
from colors import cap_first


_AC_LOC_MAP = {
    "ac_pierce": AC_PIERCE,
    "ac_bash": AC_BASH,
    "ac_slash": AC_SLASH,
    "ac_exotic": AC_EXOTIC,
}


def _armor_list(char):
    armor = char.get("armor")
    if armor is None:
        armor = (100, 100, 100, 100)
    return [armor[0], armor[1], armor[2], armor[3]]


def _set_armor(char, armor):
    char["armor"] = (armor[0], armor[1], armor[2], armor[3])


def _add_armor(char, armor_delta):
    armor = _armor_list(char)
    for i in range(4):
        armor[i] += armor_delta[i]
    _set_armor(char, armor)


def _item_armor_runtime(tpl):
    armor = tpl.get("armor")
    if armor is None:
        return None
    return armor


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

    Mutates hp_max, mp_max, armor, hitroll, damroll directly; accumulates
    str/dex/int/wis/con into char["mod_stat"] (cf. 1stMud mod_stat[] in handler.c).

    Args:
        char (dict): Character state dict (player or mob instance).
        loc (str): Affect location -- one of "str", "dex", "int", "wis", "con",
            "hit", "mp", "mana", "ac_pierce", "ac_bash", "ac_slash",
            "ac_exotic", "ac", "hitroll", "damroll".
        modifier (int): Raw modifier value (positive = bonus).
        add (bool): True to apply, False to remove.
    """
    if not add:
        modifier = -modifier
    if loc == "hit":
        char["hp_max"] = max(1, char["hp_max"] + modifier)
    elif loc in ("mp", "mana"):
        char["mp_max"] = max(1, char["mp_max"] + modifier)
    elif loc == "ac":
        _add_armor(char, (modifier, modifier, modifier, modifier))
    elif loc in _AC_LOC_MAP:
        armor = _armor_list(char)
        armor[_AC_LOC_MAP[loc]] += modifier
        _set_armor(char, armor)
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
    # Start from race+template baseline (cf. 1stMud: victim->affected_by = victim->race->aff)
    flags = dict(char.get("_base_aff", {}))
    for af in char.get("affect_list", []):
        bit = af.get("bitvector", "")
        if bit:
            flags[bit] = True
    char["aff_flags"] = flags


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


def get_armor(char, ac_type):
    """Effective bucket AC: base + DEX bonus + equipped armour bonus.

    Args:
        char (dict): Character state dict (player or mob instance).
        ac_type (int): One of AC_PIERCE/AC_BASH/AC_SLASH/AC_EXOTIC.

    Returns:
        int: Total AC bucket value in PrimeSUD runtime units.

    PrimeSUD stores actor armor in per-bucket combat units and later divides by
    10 in hit resolution, matching the current combat pipeline.
    """
    armor = char.get("armor", (100, 100, 100, 100))
    return armor[ac_type] + DEX_APP_DEF[get_curr_stat(char, "dex")]



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
    """Apply stat bonuses and runtime object affects for equipped item.

    Does NOT handle base armor values -- those are subtracted/added
    directly in equip_char/unequip_char (cf. 1stMud handler.c).
    """
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
    armor = _item_armor_runtime(tpl)
    if armor is not None:
        _add_armor(char, armor)
    _apply_item_modifiers(char, obj, tpl, False)
    char["equip"][slot] = None
    char["inv"].append(obj)


def equip_char(char, obj, slot):
    """Seat obj in slot and apply stat_bonuses (cf. 1stMud equip_char in handler.c)."""
    tpl = ITEM_TEMPLATES[obj["vnum"]]
    char["inv"].remove(obj)
    char["equip"][slot] = obj
    armor = _item_armor_runtime(tpl)
    if armor is not None:
        _add_armor(char, (-armor[0], -armor[1], -armor[2], -armor[3]))
    _apply_item_modifiers(char, obj, tpl, True)


def act(tr, msg):
    """Send an action-narration message, capitalising the first visible character.

    Reduced port of act_new/perform_act (cf. 1stMud comm.c). Full 1stMud act()
    also handles multi-recipient routing (TO_CHAR/TO_VICT/TO_ROOM/etc.) and
    visibility-aware $n/$N/$p token substitution via Pers(). Both are omitted:
    PrimeSUD is single-player so there is only ever one recipient, and token
    substitution is done inline with % / format(). The post-substitution
    skipcol+toupper in perform_act is preserved: mob short_descr values are
    stored lowercase and may appear at sentence start in narration strings.

    Args:
        tr: tml instance (print target).
        msg (str): Fully assembled narration string, may contain {X colour codes.
    """
    tr.print(cap_first(msg))

