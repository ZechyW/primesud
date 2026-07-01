"""Character state, affects, equipment, visibility, and name-match helpers (cf. 1stMud handler.c)."""

from colors import upper
from config import (MAX_STATS, STR_APP_TOHIT, STR_APP_TODAM, DEX_APP_DEF,
                    POS_ORDER,
                    SEX_VALUES)
from terminal import tprint
from world import ITEM_DEFS, MOB_DEFS

# -- Alignment helpers (cf. 1stMud IsGood/IsEvil/IsNeutral in macro.h) ----------------

def is_good(ch):
    """Check if character is good-aligned (cf. 1stMud `IsGood` in macro.h)."""
    return ch.get("alignment", 0) >= 350

def is_evil(ch):
    """Check if character is evil-aligned (cf. 1stMud `IsEvil` in macro.h)."""
    return ch.get("alignment", 0) <= -350

def is_neutral(ch):
    """Check if character is neutral-aligned (cf. 1stMud `IsNeutral` in macro.h)."""
    return not is_good(ch) and not is_evil(ch)


# -- act() type bitmask (cf. 1stMud TO_* in bits.h) ---------------------------------
TO_ROOM    = 1    # BIT_A
TO_NOTVICT = 2    # BIT_B
TO_VICT    = 4    # BIT_C
TO_CHAR    = 8    # BIT_D
TO_ALL     = 16   # BIT_E
TO_DAMAGE  = 32   # BIT_F
TO_ZONE    = 64   # BIT_G
TO_SOCIALS = 128  # BIT_H

AFF_TO_WHERE = {
    "to_affects": "affected_by",
    "to_immune": "imm_flags",
    "to_resist": "res_flags",
    "to_vuln": "vuln_flags",
}


def _char_base():
    """Return a fresh shared char state dict (cf. 1stMud char_data in structs.h:560).

    Both create_char (player.py) and create_mobile (mob.py) start from this base.
    Player-only fields (pcdata: xp_next, practice, learned, flags, played) and
    mob-only fields (tpl) are overlaid by their respective constructors.

    [DEVIATION] act_flags holds ACT_* bits; PLR_* player flags live in player-only
    "flags" key.  1stMud uses a single act bitfield for both.
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
        # -- Resources (cf. .hit/.max_hit, .mana/.max_mana, .move/.max_move, .gold, .silver, .exp)
        "hit":         20,  "max_hit":  20,
        "mana":        0,   "max_mana":  0,
        "move":        100, "max_move": 100,
        "gold":        0,
        "silver":      0,
        "xp":          0,
        # -- Combat (cf. .saving_throw, .hitroll, .damroll, .armor[], .perm_stat[], .mod_stat[])
        "saving_throw": 0,
        "hitroll":     0,
        "damroll":     0,
        "armor":       (100, 100, 100, 100),
        "perm_stat":   {"str": 13, "dex": 13, "int": 13, "wis": 13, "con": 13},
        "mod_stat":    {},
        # -- Flags (cf. .act, .imm_flags, .res_flags, .vuln_flags, .affected_by,
        #           .off_flags, .form, .parts)
        "act_flags":   {},
        "imm_flags":   {},
        "res_flags":   {},
        "vuln_flags":  {},
        "affected_by": {},
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
    # Not ported: comm, wiznet, stance[], war, gquest, mprog_*,
    # master/leader/pet/reply, desc, was_in_room, gen_data, hunting, trust,
    # invis/incog_level, logon, prompt/gprompt, group, rank, Class[],
    # deity, material, dam_type, start_pos, default_pos, info_settings, color_prefix
    # timer: connection idle counter (ticks since last input) -- no-op in single-player



def _item_armor_runtime(tpl):
    """Return armor tuple from item template, or None if absent. [PRIMESUD]"""
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
    v = char.get("perm_stat", {}).get(stat, 10) + char.get("mod_stat", {}).get(stat, 0)
    return max(3, min(MAX_STATS, v))


def affect_modify(char, af, add):
    """Apply or remove an affect's bitvector and stat modifier

    Handles bitvector set/clear based on af["where"] (to_affects, to_immune,
    to_resist, to_vuln) and stat mod based on af["location"].

    (cf. 1stMud affect_modify in handler.c).
    [Verified: 23/06/2026]

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
    if loc in ("str", "dex", "int", "wis", "con"):
        ms = char.setdefault("mod_stat", {})
        ms[loc] = ms.get(loc, 0) + mod
    elif loc == "sex":
        cur = SEX_VALUES.index(char["sex"]) if char.get("sex") in SEX_VALUES else 0
        char["sex"] = SEX_VALUES[max(0, min(2, cur + mod))]
    elif loc == "mana":
        char["max_mana"] = max(1, char["max_mana"] + mod)
    elif loc == "move":
        char["max_move"] = max(1, char["max_move"] + mod)
    elif loc == "hit":
        char["max_hit"] = max(1, char["max_hit"] + mod)
    elif loc == "ac":
        a = char.get("armor") or (100, 100, 100, 100)
        char["armor"] = (a[0]+mod, a[1]+mod, a[2]+mod, a[3]+mod)
    elif loc == "hitroll":
        char["hitroll"] += mod
    elif loc == "damroll":
        char["damroll"] += mod
    elif loc in ("saves", "saving_rod", "saving_petri", "saving_breath", "saving_spell"):
        char["saving_throw"] = char.get("saving_throw", 0) + mod
    # TODO: port wield-drop check (cf. 1stMud affect_modify lines 1030-1045):
    # after any stat change, if STR too low for wielded weapon, drop it to room.
    # Needs obj_from_char/obj_to_room. Skip until room/item plumbing is ready.


def is_affected(char, sn):
    """Return True if char has a spell affect type.

    (cf. 1stMud is_affected in handler.c)
    [Verified: 23/06/2026]
    """
    return affect_find(char, sn) is not None


def affect_find(char, sn):
    """Return first affect of type sn, or None.

    (cf. 1stMud affect_find in handler.c)
    [Verified: 23/06/2026]
    """
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


def affect_join(char, af):
    """Merge-or-create affect (cf. 1stMud affect_join in handler.c).

    If char already has an affect with matching type, merge: average the
    levels, sum the durations and modifiers, remove old, then apply merged.
    Otherwise just apply as new.

    1stMud intentionally does NOT use this for buff spells (armor, haste,
    shield, etc.) -- those guard with is_affected and refuse to reapply.
    affect_join is used only for debuffs that should worsen on repeated
    hits: chill_touch, poison, plague, sleep.

    Args:
        char (dict): Character state dict.
        af (dict): New affect to merge or create.
    """
    for old in char.get("affect_list", []):
        if old.get("type") == af.get("type"):
            af = dict(af)
            af["level"] = (af["level"] + old.get("level", 0)) // 2
            af["duration"] = af.get("duration", 0) + old.get("duration", 0)
            af["modifier"] = af.get("modifier", 0) + old.get("modifier", 0)
            affect_remove(char, old)
            break
    affect_to_char(char, af)


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
    """Effective bucket AC: base + DEX bonus + equipped armor bonus. [PRIMESUD]

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
    """Apply stat bonuses and runtime object affects for equipped item (cf. 1stMud equip_char/unequip_char in handler.c).

    stat_bonuses maps to 1stMud .are "A" lines (TO_OBJECT, location+modifier only).
    Skips template affects for enchanted items (cf. 1stMud handler.c enchanted check).
    Does NOT handle base armor values -- those are subtracted/added
    directly in equip_char/unequip_char (cf. 1stMud handler.c).

    [PRIMESUD] Does not handle APPLY_SPELL_AFFECT (1stMud equip_char calls
    affect_to_char for those; unequip_char has matching removal). Port when
    area data includes spell-affect-on-equip items.
    """
    # Template stat bonuses -- non-enchanted only (cf. 1stMud pIndexData->affect_first)
    if not obj.get("enchanted"):
        for loc, mod in tpl.get("stat_bonuses", {}).items():
            _af = {"where": "to_object", "location": loc,
                   "modifier": mod, "bitvector": ""}
            affect_modify(char, _af, add)
            if not add:
                affect_check(char, _af.get("where", ""), _af.get("bitvector", ""))
    # Runtime object affects (cf. 1stMud obj->affect_first)
    for af in obj.get("affect_list", []):
        affect_modify(char, af, add)
        if not add:
            affect_check(char, af.get("where", ""), af.get("bitvector", ""))


def unequip_char(char, slot):
    """Remove obj from slot, reverse stat_bonuses, return to inventory (cf. 1stMud unequip_char in handler.c)."""
    obj = char["equip"][slot]
    tpl = ITEM_DEFS[obj["vnum"]]
    armor = _item_armor_runtime(tpl)
    if armor is not None:
        a = char.get("armor") or (100, 100, 100, 100)
        char["armor"] = (a[0]+armor[0], a[1]+armor[1], a[2]+armor[2], a[3]+armor[3])
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
        a = char.get("armor") or (100, 100, 100, 100)
        char["armor"] = (a[0]-armor[0], a[1]-armor[1], a[2]-armor[2], a[3]-armor[3])
    _apply_item_modifiers(char, obj, tpl, True)


def _player_char():
    """Return the runtime player character, if present. [PRIMESUD]"""
    import world
    return world.chars.get(1)



def _send_player_text(ch, txt):
    """Deliver direct output only when ch is the local player. [PRIMESUD]

    Returns:
        int: 1 if output was sent, else 0.
    """
    player = _player_char()
    if player is not None and ch is player:
        tprint(txt)
        return 1
    return 0


def chprint(ch, txt):
    """Direct-send text without formatting (cf. 1stMud chprint in character.h)."""
    if txt is None:
        return 0
    return _send_player_text(ch, txt)


def chprintln(ch, txt):
    """Direct-send one line (cf. 1stMud chprintln in character.h)."""
    if txt is None:
        txt = ""
    return _send_player_text(ch, txt)


def chprintf(ch, fmt, *args):
    """Printf-style direct-send without forced line break (cf. 1stMud chprintf in character.h)."""
    if not fmt:
        return 0
    if args:
        fmt = fmt % args
    return _send_player_text(ch, fmt)


def chprintlnf(ch, fmt, *args):
    """Printf-style direct-send with line semantics (cf. 1stMud chprintlnf in character.h)."""
    if not fmt:
        return _send_player_text(ch, "")
    if args:
        fmt = fmt % args
    return _send_player_text(ch, fmt)


_HE_SHE = {
    "male": "he",
    "female": "she",
    "either": "it",
    "neutral": "it",
}

_HIM_HER = {
    "male": "him",
    "female": "her",
    "either": "it",
    "neutral": "it",
}

_HIS_HER = {
    "male": "his",
    "female": "her",
    "either": "its",
    "neutral": "its",
}


def _first_word(text):
    """Return first whitespace-delimited word of text. [PRIMESUD]"""
    if not text:
        return ""
    return text.split()[0]


def _char_name(ch):
    """Return character name string, or empty string if None. [PRIMESUD]"""
    if ch is None:
        return ""
    return ch.get("name", "")


def _pers(ch, looker):
    """Return visible character name (cf. 1stMud Pers macro in macro.h).

    1stMud: can_see(looker, ch) ? GetName(ch) : IsImmortal(ch) ? "an Immortal" : "someone"
    [PRIMESUD] Immortal branch not ported -- always "someone" when not visible.
    [PRIMESUD] Pretitle not ported.
    """
    if ch is None:
        return "someone"
    if looker is not None and not can_see(looker, ch):
        return "someone"
    return _char_name(ch) or "someone"


def _obj_keywords(obj):
    """Return object keywords from instance or template fallback. [PRIMESUD]"""
    if not isinstance(obj, dict):
        return ""
    if "keywords" in obj:
        return obj["keywords"]
    if "vnum" in obj and obj["vnum"] in ITEM_DEFS:
        return ITEM_DEFS[obj["vnum"]].get("keywords", "")
    return ""


def _obj_short(obj):
    """Return object short description from instance or template fallback. [PRIMESUD]"""
    if not isinstance(obj, dict):
        return "something"
    if "short_descr" in obj:
        return obj["short_descr"]
    if "vnum" in obj and obj["vnum"] in ITEM_DEFS:
        return ITEM_DEFS[obj["vnum"]].get("short_descr", "something")
    return "something"


def _act_code(code, ch, arg1, arg2, to, type):
    """Resolve one $-code (cf. 1stMud perform_act switch in comm.c)."""
    victim = arg2 if isinstance(arg2, dict) and "room" in arg2 else None
    obj1 = arg1 if isinstance(arg1, dict) and "vnum" in arg1 else None
    obj2 = arg2 if isinstance(arg2, dict) and "vnum" in arg2 else None
    if code == "$":
        return "$"
    if code == "t":
        if not isinstance(arg1, str):
            return "<@@@>"
        # 1stMud: TO_DAMAGE suppresses $t for NPC viewers / players without PLR_AUTODAMAGE
        if type & TO_DAMAGE:
            if to is not None and to.get("is_npc"):
                return ""
            # [PRIMESUD] PLR_AUTODAMAGE not ported -- player always sees damage text
        return arg1
    if code == "T":
        return arg2 if isinstance(arg2, str) else "<@@@>"
    if code == "n":
        return _pers(ch, to)
    if code == "N":
        return _pers(victim, to)
    if code == "e":
        return _HE_SHE.get((ch or {}).get("sex", "neutral"), "it")
    if code == "E":
        return _HE_SHE.get((victim or {}).get("sex", "neutral"), "it")
    if code == "m":
        return _HIM_HER.get((ch or {}).get("sex", "neutral"), "it")
    if code == "M":
        return _HIM_HER.get((victim or {}).get("sex", "neutral"), "it")
    if code == "s":
        return _HIS_HER.get((ch or {}).get("sex", "neutral"), "its")
    if code == "S":
        return _HIS_HER.get((victim or {}).get("sex", "neutral"), "its")
    if code == "g":
        # [PRIMESUD] deity not ported -- ch->deity->name
        if type == TO_CHAR:
            return "your deity"
        return _HIS_HER.get((ch or {}).get("sex", "neutral"), "its") + " deity"
    if code == "G":
        # [PRIMESUD] deity not ported -- vch->deity->name
        return _HIS_HER.get((victim or {}).get("sex", "neutral"), "its") + " deity"
    if code == "c":
        # [PRIMESUD] clan not ported -- CharClan(ch)->name
        if type == TO_CHAR:
            return "your clan"
        return _HIS_HER.get((ch or {}).get("sex", "neutral"), "its") + " clan"
    if code == "C":
        # [PRIMESUD] clan not ported -- CharClan(vch)->name
        return _HIS_HER.get((victim or {}).get("sex", "neutral"), "its") + " clan"
    if code == "o":
        if to is not None and obj1 is not None:
            if can_see_obj(to, obj1):
                return _first_word(_obj_keywords(obj1)) or "something"
        return "something"
    if code == "O":
        if to is not None and obj2 is not None:
            if can_see_obj(to, obj2):
                return _first_word(_obj_keywords(obj2)) or "something"
        return "something"
    if code == "p":
        if to is not None and obj1 is not None:
            if can_see_obj(to, obj1):
                return _obj_short(obj1)
        return "something"
    if code == "P":
        if to is not None and obj2 is not None:
            if can_see_obj(to, obj2):
                return _obj_short(obj2)
        return "something"
    if code == "d":
        if arg2 is None or (isinstance(arg2, str) and not arg2):
            return "door"
        if isinstance(arg2, str):
            return _first_word(arg2)
        return "door"
    return "<@@@>"


def _perform_act(format, ch, arg1, arg2, type, to):
    """Format and deliver one act message (cf. 1stMud perform_act in comm.c).

    Substitutes $-codes, appends {x color reset, capitalizes first visible
    char (skipping color codes), then sends to the terminal.

    Args:
        format (str): Act format string with $-codes.
        ch (dict): Subject character.
        arg1: Object argument (object dict or string).
        arg2: Target argument (victim dict, object dict, or string).
        type (int): Bitmask of TO_* flags.
        to (dict): Recipient character (always the player in PrimeSUD).
    """
    out = []
    # [PRIMESUD] TO_SOCIALS color prefix not ported -- needs CTAG(_SOCIALS)
    i = 0
    while i < len(format):
        if format[i] != "$":
            out.append(format[i])
            i += 1
            continue
        i += 1
        if i >= len(format):
            out.append("<@@@>")
            break
        code = format[i]
        if arg2 is None and code.isupper() and code != "$":
            out.append(" <@@@> ")
        else:
            out.append(_act_code(code, ch, arg1, arg2, to, type))
        i += 1
    out.append("{x")
    tprint(upper("".join(out)))


def _sendok(ch, min_pos="resting"):
    """True if ch is awake enough to receive act messages (cf. 1stMud SENDOK in comm.c).

    1stMud also checks IsNPC || (desc && connected == CON_PLAYING); in
    single-player PrimeSUD the player is always connected and NPCs are
    never message recipients, so only the position check matters.
    """
    return isinstance(ch, dict) and POS_ORDER.get(ch.get("pos", "standing"), 0) >= POS_ORDER.get(min_pos, 0)


def _act_room(ch, arg1, arg2):
    """Derive event room from ch, falling back to arg1/arg2 (cf. 1stMud act_new room logic in comm.c)."""
    if isinstance(ch, dict) and ch.get("room") is not None:
        return ch["room"]
    if isinstance(arg1, dict) and arg1.get("room") is not None:
        return arg1["room"]
    if isinstance(arg2, dict) and arg2.get("room") is not None:
        return arg2["room"]
    return None


def act_new(format, ch, arg1, arg2, type, min_pos):
    """Route act message to the solo player (cf. 1stMud act_new in comm.c).

    Full bitmask routing adapted for single-player: checks each TO_* bit
    independently and delivers via _perform_act if the player qualifies.

    Args:
        format (str): Act format string with $-codes.
        ch (dict): Subject character.
        arg1: Object argument (object dict or string).
        arg2: Target argument (victim dict, object dict, or string).
        type (int): Bitmask of TO_* flags.
        min_pos (str): Minimum position to receive message (default "resting").
    """
    if not format:
        return

    player = _player_char()
    if player is None:
        return

    # TO_CHAR: send to ch (cf. 1stMud: if ch && SENDOK -> perform_act to ch)
    if type & TO_CHAR:
        if ch is player and _sendok(ch, min_pos):
            _perform_act(format, ch, arg1, arg2, type, ch)
            return

    # TO_VICT: send to arg2 if arg2 != ch (cf. 1stMud: if to && SENDOK && to != ch)
    if type & TO_VICT:
        vict = arg2 if isinstance(arg2, dict) and "room" in arg2 else None
        if vict is player and vict is not ch and _sendok(vict, min_pos):
            _perform_act(format, ch, arg1, arg2, type, vict)
            return

    # TO_ALL / TO_ZONE: iterate all descriptors; player != ch
    # (cf. 1stMud: for each desc, vch != ch, TO_ALL or same area)
    if type & (TO_ALL | TO_ZONE):
        if player is not ch and _sendok(player, min_pos):
            if type & TO_ALL:
                _perform_act(format, ch, arg1, arg2, type, player)
                return
            # TO_ZONE: same area check
            if isinstance(ch, dict) and ch.get("room") is not None:
                from world import ROOM_DEFS
                ch_area = ROOM_DEFS.get(ch["room"], {}).get("area")
                pl_area = ROOM_DEFS.get(player.get("room"), {}).get("area")
                if ch_area is not None and ch_area == pl_area:
                    _perform_act(format, ch, arg1, arg2, type, player)
                    return

    # TO_ROOM / TO_NOTVICT: same room, player != ch (and != arg2 for NOTVICT)
    # (cf. 1stMud: find room from ch/obj1/obj2, iterate room->person_first)
    if type & (TO_ROOM | TO_NOTVICT):
        room = _act_room(ch, arg1, arg2)
        if room is not None and player.get("room") == room:
            if _sendok(player, min_pos) and player is not ch:
                if type & TO_ROOM:
                    _perform_act(format, ch, arg1, arg2, type, player)
                    return
                if player is not arg2:
                    _perform_act(format, ch, arg1, arg2, type, player)
                    return


def act(format, ch, arg1=None, arg2=None, type=TO_CHAR):
    """1stMud act() entry point (cf. act macro in macro.h).

    Wraps act_new with min_pos=POS_RESTING, matching
    `#define act(format,ch,arg1,arg2,type) act_new((format),(ch),(arg1),(arg2),(type),POS_RESTING)`

    Args:
        format (str): Act format string with $-codes.
        ch (dict): Subject character (required, as in 1stMud).
        arg1: Object argument (object dict or string).
        arg2: Target argument (victim dict, object dict, or string).
        type (int): Bitmask of TO_* flags.
    """
    if not format:
        return
    act_new(format, ch, arg1, arg2, type, "resting")


def can_see_room(ch, room_vnum):
    """Room visibility check (cf. 1stMud can_see_room in handler.c).

    [PRIMESUD] Stub -- always True. 1stMud checks:
    - ROOM_ARENA: always visible
    - ROOM_IMP_ONLY: trust < MAX_LEVEL blocked
    - ROOM_GODS_ONLY: non-immortal blocked
    - ROOM_HEROES_ONLY: non-immortal blocked
    - ROOM_NEWBIES_ONLY: level > 5 and non-immortal blocked
    - area->clan: non-matching clan blocked
    - room->owner: non-owner blocked (room also treated as private)
    - is_home_owner: always visible
    Clan/owner not ported: PrimeSUD is single-player, so multi-player
    access restrictions serve no purpose. Room flags (IMP_ONLY etc.)
    not ported yet either.
    """
    return True


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


def can_see_obj(ch, obj):
    """Check if ch can see obj (cf. 1stMud can_see_obj in handler.c).

    [PRIMESUD] Stub -- always returns True. Real checks (AFF_BLIND,
    ITEM_VIS_DEATH, ITEM_INVIS, ITEM_GLOW/room_is_dark) to be added
    when those systems are ported.

    Args:
        ch (dict): Observer (player or mob instance).
        obj (dict): Target object instance.

    Returns:
        bool: True if ch can see obj.
    """
    # [PRIMESUD] stub: fill in when item visibility flags ported
    return True


def get_char_room(fragment, inst_ids, mob_instances):
    """Find the first mob in inst_ids whose keywords match fragment (cf. 1stMud get_char_room in handler.c).

    Args:
        fragment (str): Player-typed name fragment.
        inst_ids (list): Ordered list of mob instance IDs to search.
        mob_instances (dict): Mob instance mapping mob ID -> mob instance dict.

    Returns:
        int or None: First matching mob instance ID, or None if not found.
    """
    for mob_id in inst_ids:
        if is_name(fragment, MOB_DEFS[mob_instances[mob_id]["tpl"]].get("keywords", "")):
            return mob_id
    return None


def mob_condition(inst, tpl):
    """Return a condition description string for a mob. [PRIMESUD]

    Args:
        inst (dict): Mob instance state dict.
        tpl (dict): Mob template dict.

    Returns:
        str: Human-readable condition sentence.
    """
    _hm = inst.get("max_hit", 1)
    pct = inst["hit"] * 100 // _hm if _hm > 0 else -1
    name = tpl["short_descr"]
    if pct >= 100: wound = name + " is in excellent condition."
    elif pct >= 90:  wound = name + " has a few scratches."
    elif pct >= 75:  wound = name + " has some small wounds and bruises."
    elif pct >= 50:  wound = name + " has quite a few wounds."
    elif pct >= 30:  wound = name + " has some big nasty wounds and scratches."
    elif pct >= 15:  wound = name + " looks pretty hurt."
    elif pct >= 0:   wound = name + " is in awful condition."
    else:            wound = name + " is bleeding to death."
    return upper(wound)

