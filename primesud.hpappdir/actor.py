"""Shared actor stat, affect, equipment, and name-match helpers."""

from config import (MAX_STATS, STR_APP_TOHIT, STR_APP_TODAM, DEX_APP_DEF,
                    AC_PIERCE, AC_BASH, AC_SLASH, AC_EXOTIC, POS_ORDER)
from world import ITEM_DEFS
from colors import upper

AFF_TO_WHERE = {
    "to_affects": "affected_by",
    "to_immune": "imm_flags",
    "to_resist": "res_flags",
    "to_vuln": "vuln_flags",
}

_AC_LOC_MAP = {
    "ac_pierce": AC_PIERCE,
    "ac_bash": AC_BASH,
    "ac_slash": AC_SLASH,
    "ac_exotic": AC_EXOTIC,
}


def _char_base():
    """Return a fresh shared char state dict (cf. 1stMud char_data in structs.h:560).

    Both create_char (player.py) and create_mobile (mob.py) start from this base.
    Player-only fields (pcdata: xp_next, practice, learned, flags, played) and
    mob-only fields (tpl) are overlaid by their respective constructors.

    [DEVIATION] act_flags holds ACT_* bits; PLR_* player flags live in player-only
    "flags" key.  1stMud uses a single act bitfield for both.
    [DEVIATION] move/max_move not ported -- no stamina system yet.
    [DEVIATION] is_npc bool replaces NULL pcdata pointer check.
    [DEVIATION] room/fighting stored as vnum/id, not pointers.
    [DEVIATION] affect_list (list) + affects (dict) replace affect linked list;
    affects dict is a [PRIMESUD] O(1) shortcut derived from affect_list.
    """
    return {
        # -- Identity (cf. .name, .id, .level, .sex, .race, .alignment, .size)
        "name":        "",
        "id":          0,
        "is_npc":      False,
        "level":       1,
        "sex":         "neutral",
        "race":        "Human",
        "alignment":   0,
        "size":        "medium",
        # -- Position / timing (cf. .position, .wait, .daze, .fighting, .wimpy)
        "room":        None,
        "pos":         "standing",
        "wait":        0,
        "daze":        0,
        "fighting":    None,
        "wimpy":       0,
        # -- Resources (cf. .hit/.max_hit, .mana/.max_mana, .gold, .silver, .exp)
        "hp":          20,  "hp_max":  20,
        "mp":          0,   "mp_max":  0,
        "gold":        0,
        "silver":      0,
        "xp":          0,
        # -- Combat (cf. .saving_throw, .hitroll, .damroll, .armor[], .perm_stat[], .mod_stat[])
        "saving_throw": 0,
        "hitroll":     0,
        "damroll":     0,
        "armor":       (100, 100, 100, 100),
        "str":         13,  "dex": 13,  "int": 13,
        "wis":         13,  "con": 13,
        "mod_stat":    {},
        # -- Flags (cf. .act, .imm_flags, .res_flags, .vuln_flags, .affected_by,
        #           .off_flags, .form, .parts)
        "act_flags":   {},
        "imm_flags":   {},
        "res_flags":   {},
        "vuln_flags":  {},
        "affected_by":   {},
        "off_flags":   {},
        "form_flags":  {},
        "part_flags":  {},
        # -- Affects (cf. .affect linked list)
        "affect_list": [],
        "affects":     {},
        # -- Inventory / equipment (cf. .carrying, worn slots)
        "inv":         [],
        "equip":       {},
    }
    # Not ported: move/max_move, comm, wiznet, stance[], war, gquest, mprog_*,
    # master/leader/pet/reply, desc, was_in_room, gen_data, hunting, trust,
    # invis/incog_level, logon, prompt/gprompt, group, rank, Class[],
    # deity, material, dam_type, start_pos, default_pos, info_settings, color_prefix
    # timer: connection idle counter (ticks since last input) -- no-op in single-player


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


def affect_modify(char, af, add):
    """Apply or remove an affect's bitvector and stat modifier (cf. 1stMud affect_modify in handler.c).

    Handles bitvector set/clear based on af["where"] (to_affects, to_immune,
    to_resist, to_vuln) and stat mod based on af["location"].

    Args:
        char (dict): Character state dict (player or mob instance).
        af (dict): Affect dict with where, location, modifier, bitvector.
        add (bool): True to apply, False to remove.
    """
    # -- Bitvector set/clear (cf. 1stMud affect_modify lines 910-948)
    bit = af.get("bitvector", "")
    if bit:
        where = af.get("where", "to_affects")
        key = AFF_TO_WHERE.get(where)
        if key:
            if add:
                char.setdefault(key, {})[bit] = True
            else:
                char.get(key, {}).pop(bit, None)

    # -- Stat modifier (cf. 1stMud affect_modify lines 952-1028)
    mod = af.get("modifier", 0)
    if not mod:
        return
    if not add:
        mod = -mod
    loc = af.get("location", "none")
    if loc == "hit":
        char["hp_max"] = max(1, char["hp_max"] + mod)
    elif loc in ("mp", "mana"):
        char["mp_max"] = max(1, char["mp_max"] + mod)
    elif loc == "ac":
        _add_armor(char, (mod, mod, mod, mod))
    elif loc in _AC_LOC_MAP:
        armor = _armor_list(char)
        armor[_AC_LOC_MAP[loc]] += mod
        _set_armor(char, armor)
    elif loc == "hitroll":
        char["hitroll"] += mod
    elif loc == "damroll":
        char["damroll"] += mod
    elif loc == "saving_throw":
        char["saving_throw"] = char.get("saving_throw", 0) + mod
    elif loc in ("str", "dex", "int", "wis", "con"):
        ms = char.setdefault("mod_stat", {})
        ms[loc] = ms.get(loc, 0) + mod


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
    """Copy affect and apply to character (cf. 1stMud affect_to_char in handler.c).

    Args:
        char (dict): Character state dict (player or mob instance).
        af (dict): Affect with type, level, duration, location, modifier, bitvector, where.
    """
    cur = dict(af)
    char.setdefault("affect_list", []).append(cur)
    affect_modify(char, cur, True)


def affect_remove(char, af):
    """Remove one active affect from a character (cf. 1stMud affect_remove in handler.c)."""
    affects = char.get("affect_list", [])
    if af not in affects:
        return
    affect_modify(char, af, False)
    where = af.get("where", "to_affects")
    vector = af.get("bitvector", "")
    affects.remove(af)
    affect_check(char, where, vector)


def affect_check(char, where, vector):
    """Re-set a bitvector if any remaining affect still provides it (cf. 1stMud affect_check in handler.c).

    Called after affect_remove clears a bit. Scans char affect_list and
    equipped item affects; if any still carry the same where+bitvector,
    re-sets the flag.

    Args:
        char (dict): Character state dict.
        where (str): Affect target -- "to_affects", "to_immune", "to_resist", "to_vuln".
        vector (str): Bitvector name (e.g. "sanctuary", "haste").
    """
    if where == "to_object" or where == "to_weapon" or not vector:
        return

    key = AFF_TO_WHERE.get(where)
    if not key:
        return

    # Check char affects (cf. 1stMud: scan ch->affect_first)
    for paf in char.get("affect_list", []):
        if paf.get("where", "to_affects") == where and paf.get("bitvector") == vector:
            char.setdefault(key, {})[vector] = True
            return

    # Check equipped item affects (cf. 1stMud: scan ch->carrying_first where wear_loc != -1)
    for obj in char.get("equip", {}).values():
        for paf in obj.get("affect_list", []):
            if paf.get("where", "to_affects") == where and paf.get("bitvector") == vector:
                char.setdefault(key, {})[vector] = True
                return


def affect_strip(char, sn):
    """Remove all affects of type sn (cf. 1stMud affect_strip in handler.c)."""
    for af in list(char.get("affect_list", [])):
        if af.get("type") == sn:
            affect_remove(char, af)


def is_awake(ch):
    """True if ch can act: position > sleeping (cf. 1stMud IsAwake macro in macro.h)."""
    return POS_ORDER[ch["pos"]] > POS_ORDER["sleeping"]


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
    """Effective bucket AC: base + DEX bonus + equipped armor bonus.

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

    stat_bonuses maps to 1stMud .are "A" lines (TO_OBJECT, location+modifier only).
    Does NOT handle base armor values -- those are subtracted/added
    directly in equip_char/unequip_char (cf. 1stMud handler.c).
    """
    # Template stat bonuses (cf. 1stMud pIndexData->affect_first, "A" lines)
    for loc, mod in tpl.get("stat_bonuses", {}).items():
        affect_modify(char, {"where": "to_object", "location": loc,
                             "modifier": mod, "bitvector": ""}, add)
    # Runtime object affects (cf. 1stMud obj->affect_first)
    for af in obj.get("affect_list", []):
        affect_modify(char, af, add)


def unequip_char(char, slot):
    """Remove obj from slot, reverse stat_bonuses, return to inventory (cf. 1stMud unequip_char in handler.c)."""
    obj = char["equip"][slot]
    tpl = ITEM_DEFS[obj["vnum"]]
    armor = _item_armor_runtime(tpl)
    if armor is not None:
        _add_armor(char, armor)
    _apply_item_modifiers(char, obj, tpl, False)
    char["equip"][slot] = None
    char["inv"].append(obj)


def equip_char(char, obj, slot):
    """Seat obj in slot and apply stat_bonuses (cf. 1stMud equip_char in handler.c)."""
    tpl = ITEM_DEFS[obj["vnum"]]
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
    tr.print(upper(msg))


def can_see(ch, victim):
    """Check if ch can see victim (cf. 1stMud can_see in handler.c).

    Stub -- always returns True. Real checks (AFF_BLIND, room_is_dark,
    AFF_INVISIBLE, AFF_SNEAK, AFF_HIDE) to be added when those systems
    are ported.

    Args:
        ch (dict): Observer (player or mob instance).
        victim (dict): Target (player or mob instance).

    Returns:
        bool: True if ch can see victim.
    """
    # [PRIMESUD] stub: fill in when AFF_BLIND/INVISIBLE/SNEAK/HIDE/dark rooms ported
    if ch is victim:
        return True
    return True

