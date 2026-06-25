"""Shared actor stat, affect, equipment, and name-match helpers."""

from colors import upper
from config import (MAX_STATS, STR_APP_TOHIT, STR_APP_TODAM, DEX_APP_DEF,
                    POS_ORDER,
                    SEX_VALUES)
from terminal import tprint
from world import ITEM_DEFS

TO_CHAR = "char"
TO_VICT = "vict"
TO_ROOM = "room"
TO_NOTVICT = "notvict"
TO_ALL = "all"

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
        "hit":         20,  "max_hit":  20,
        "mana":        0,   "max_mana":  0,
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
    # Not ported: move/max_move, comm, wiznet, stance[], war, gquest, mprog_*,
    # master/leader/pet/reply, desc, was_in_room, gen_data, hunting, trust,
    # invis/incog_level, logon, prompt/gprompt, group, rank, Class[],
    # deity, material, dam_type, start_pos, default_pos, info_settings, color_prefix
    # timer: connection idle counter (ticks since last input) -- no-op in single-player



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
    # [PRIMESUD] APPLY_MOVE intentionally not ported -- no max_move stat
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
    """Return the runtime player character, if present."""
    import world
    return world.chars.get(1)


def _event_room(ch, victim):
    """Return the room where an action occurs."""
    if ch is not None:
        return ch.get("room")
    if victim is not None:
        return victim.get("room")
    return None


def _send_player_text(ch, txt):
    """Deliver direct output only when ch is the local player.

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
    if not text:
        return ""
    return text.split()[0]


def _char_name(ch):
    if ch is None:
        return ""
    return ch.get("name", "")


def _pers(ch, looker):
    """Return 1stMud-style visible character name for one recipient."""
    if ch is None:
        return "someone"
    if looker is not None and ch is looker:
        return "you"
    if looker is not None and not can_see(looker, ch):
        return "someone"
    return _char_name(ch) or "someone"


def _obj_keywords(obj):
    if not isinstance(obj, dict):
        return ""
    if "keywords" in obj:
        return obj["keywords"]
    if "vnum" in obj and obj["vnum"] in ITEM_DEFS:
        return ITEM_DEFS[obj["vnum"]].get("keywords", "")
    return ""


def _obj_short(obj):
    if not isinstance(obj, dict):
        return "something"
    if "short_descr" in obj:
        return obj["short_descr"]
    if "vnum" in obj and obj["vnum"] in ITEM_DEFS:
        return ITEM_DEFS[obj["vnum"]].get("short_descr", "something")
    return "something"


def _act_code(code, ch, arg1, arg2, to):
    victim = arg2 if isinstance(arg2, dict) and "room" in arg2 else None
    obj1 = arg1 if isinstance(arg1, dict) and "vnum" in arg1 else None
    obj2 = arg2 if isinstance(arg2, dict) and "vnum" in arg2 else None
    if code == "$":
        return "$"
    if code == "t":
        return arg1 if isinstance(arg1, str) else "<@@@>"
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
    if code == "o":
        return _first_word(_obj_keywords(obj1)) or "something"
    if code == "O":
        return _first_word(_obj_keywords(obj2)) or "something"
    if code == "p":
        return _obj_short(obj1)
    if code == "P":
        return _obj_short(obj2)
    if code == "d":
        return _first_word(arg2) if isinstance(arg2, str) and arg2 else "door"
    return "<@@@>"


def _perform_act_string(format, ch, arg1, arg2, to):
    out = []
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
        out.append(_act_code(format[i], ch, arg1, arg2, to))
        i += 1
    return upper("".join(out))


def _sendok(ch):
    return isinstance(ch, dict) and POS_ORDER[ch.get("pos", "standing")] >= POS_ORDER["resting"]


def _player_sees_type(player, ch, arg1, arg2, type):
    room = _event_room(ch, arg2 if isinstance(arg2, dict) and "room" in arg2 else None)
    same_room = room is not None and player.get("room") == room
    if type == TO_CHAR:
        return _sendok(ch) and ch is player
    if type == TO_VICT:
        return _sendok(arg2) and arg2 is player and arg2 is not ch
    if type == TO_ROOM:
        return same_room and _sendok(player) and player is not ch
    if type == TO_NOTVICT:
        return same_room and _sendok(player) and player is not ch and player is not arg2
    if type == TO_ALL:
        return _sendok(player)
    return False


def act(format, ch=None, arg1=None, arg2=None, type=TO_CHAR, **kwargs):
    """Route a 1stMud-style act message to the solo player when applicable.

    This keeps the 1stMud `act(format, ch, arg1, arg2, type)` call shape while
    only delivering the message the local player would actually see.

    Args:
        format (str): 1stMud act string with optional `$` tokens.
        ch (dict): Acting character.
        arg1: First substitution argument, usually object or string.
        arg2: Second substitution argument, usually victim or string.
        type (str): One of TO_CHAR/TO_VICT/TO_ROOM/TO_NOTVICT/TO_ALL.
    """
    # [PRIMESUD] Backward-compatible aliases so existing call sites can port
    # lazily to the 1stMud argument names.
    if arg1 is None and "obj" in kwargs:
        arg1 = kwargs["obj"]
    if arg2 is None and "victim" in kwargs:
        arg2 = kwargs["victim"]
    if type == TO_CHAR and "to" in kwargs:
        type = kwargs["to"]

    player = _player_char()
    if player is None:
        return

    if not _player_sees_type(player, ch, arg1, arg2, type):
        return

    tprint(_perform_act_string(format, ch, arg1, arg2, player))


def can_see_room(ch, room_vnum):
    """Room visibility check (cf. 1stMud can_see_room in handler.c).

    [PRIMESUD] Stub -- always True. 1stMud checks:
    - ROOM_ARENA: always visible
    - ROOM_IMP_ONLY: trust < MAX_LEVEL blocked
    - ROOM_GODS_ONLY: non-immortal blocked
    - ROOM_HEROES_ONLY: non-immortal blocked
    - ROOM_NEWBIES_ONLY: level > 5 and non-immortal blocked
    - area->clan: non-matching clan blocked
    - is_home_owner: always visible
    None of these systems exist in PrimeSUD yet.
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

