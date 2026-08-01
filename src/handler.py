"""Character state, affects, equipment, visibility, and name-match helpers (cf. 1stMud handler.c)."""

from classes import is_prime_stat
from colors import upper
from config import (LEVEL_IMMORTAL, MAX_STATS,
                    STR_APP_TOHIT, STR_APP_TODAM, DEX_APP_DEF,
                    STR_APP_WIELD, POS_ORDER,
                    SEX_VALUES)
from races import race_lookup, RACE_TABLE
from skills_table import GSN_SNEAK
from terminal import tprint
from urandom import randint
import world
from world import MOB_DEFS, ROOM_DEFS, item_tpl, item_tpl_get
from game_time import time_info, SUN_SET, SUN_DARK
from debug import DBG  # [PRIMESUD] "holylight" debug toggle = 1stMud PLR_HOLYLIGHT
from util import int_str, sstr

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
# [PRIMESUD] TO_ALL carries ROM 2.4 semantics -- "everyone in ch's room,
# including ch" -- not 1stMud's BIT_E. In ROM, TO_ALL is the plain enum value 4
# (merc.h:487) and act_new loops only ch->in_room->people, skipping no one
# (comm.c:2184). 1stMud redefined it as BIT_E, a mud-wide descriptor broadcast
# that also excludes ch (bits.h:121, comm.c:2288), but converted none of the
# call sites it inherited from ROM -- effects.c x8, magic.c x8, music.c x2,
# special.c x3, update.c x1, an identical one-for-one set. All of them were
# written against the room-scoped meaning, so the redefinition is an
# unconverted port regression, not intent: it leaks room chatter mud-wide
# (hood.are gang taunts reaching every player) and silently drops messages
# whose only recipient was ch (player-cast continual light, poison weapon,
# remove curse print nothing). Every PrimeSUD TO_ALL site is one of those
# inherited call sites, so the constant restores ROM's meaning here rather
# than each site spelling out TO_ROOM | TO_CHAR. See docs/FIXES.md.
# BIT_E (16) is consequently unused.
TO_ALL     = TO_ROOM | TO_CHAR
TO_DAMAGE  = 32   # BIT_F
TO_ZONE    = 64   # BIT_G
TO_SOCIALS = 128  # BIT_H

# -- Player flag bits (cf. 1stMud PLR_* in bits.h) -----------------------------
# Defined here (not player.py) because player.py imports handler; player.py
# re-exports them, so import from either.
PLR_AUTOMAP = 1
PLR_AUTOSKILL = 2   # [PRIMESUD] autoskill combat automation
PLR_AUTOASSIST = 4   # BIT_C
PLR_AUTOEXIT = 8     # BIT_D
PLR_AUTOLOOT = 16    # BIT_E
PLR_AUTOSAC = 32     # BIT_F
PLR_AUTOGOLD = 64    # BIT_G
PLR_AUTOSPLIT = 128  # BIT_H
PLR_AUTODAMAGE = 1024  # BIT_K
# cf. 1stMud pload_default in save.c: all auto* flags on for new players
PLR_DEFAULTS = (PLR_AUTOMAP | PLR_AUTOASSIST | PLR_AUTOEXIT | PLR_AUTOLOOT
                | PLR_AUTOSAC | PLR_AUTOGOLD | PLR_AUTOSPLIT | PLR_AUTODAMAGE)

# -- Comm bits (cf. 1stMud COMM_* in bits.h) -----------------------------------
# 1stMud keeps these on a separate ch->comm bitfield; PrimeSUD has only one
# player "flags" field (already persisted -- see game_state._serialize_world),
# so they share it with the PLR_* bits above rather than adding a parallel
# field. New bits, not a continuation of the PLR_* numbering.
COMM_BRIEF = 2048         # 1stMud BIT_M
COMM_COMPACT = 4096       # 1stMud BIT_L
COMM_SHOW_AFFECTS = 8192  # 1stMud BIT_Q
# None of the three are on by default (cf. 1stMud save.c:691 pload_default:
# ch->comm = COMM_COMBINE | COMM_PROMPT -- neither COMBINE nor PROMPT is
# ported, and brief/compact/show_affects aren't in that default set anyway).

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
    [DEVIATION] affect_list (list) replaces the affect linked list.
    """
    return {
        # -- Identity (cf. .name, .id, .level, .sex, .race, .alignment, .size)
        "name":        "",
        "id":          0,
        "is_npc":      False,
        "level":       1,
        "sex":         "neutral",
        "true_sex":    "neutral",  # cf. 1stMud pcdata->true_sex; baseline for reset_char
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
        # -- Followers (cf. .master, .leader, .pet) -- stored as char ids
        "master":      None,
        "leader":      None,
        "pet":         None,
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
        # [PRIMESUD] No stat rolling; fixed base stats (1stMud rolls in nanny.c)
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
        # -- Stances (cf. .stance[MAX_STANCE]; slots 0-10 trained %, 11 current
        #    stance id, 12 autodrop stance id -- zeroed as in 1stMud new_char)
        "stance":      [0] * 13,
        # -- Inventory / equipment (cf. .carrying, worn slots)
        "inv":         [],
        "equip":       {},
    }
    # Not ported: comm, wiznet, war, gquest, mprog_*,
    # reply, desc, was_in_room, gen_data, hunting, trust,
    # invis/incog_level, logon, prompt/gprompt, group, rank, Class[],
    # deity, material, dam_type, start_pos, default_pos, info_settings, color_prefix
    # timer: connection idle counter (ticks since last input) -- no-op in single-player



def _item_armor_runtime(tpl, obj=None):
    """Return armor tuple from item instance override or template, or None. [PRIMESUD]

    Instance "armor" supports quest gear that rescales with level
    (cf. 1stMud update_questobj writing obj->value[0..3]).
    """
    if isinstance(obj, dict) and "armor" in obj:
        return obj["armor"]
    armor = tpl.get("armor")
    if armor is None:
        return None
    return armor


# -- Stat application helpers --------------------------------------------------

# Maps stat name -> index position in a race's stats/max_stats tuples
# (cf. 1stMud pc_race_table[].max_stats[] index order in const.c).
# Dict, not tuple.index() -- get_curr_stat runs in combat loops.
_STAT_IDX = {"str": 0, "dex": 1, "int": 2, "wis": 3, "con": 4}


def get_curr_stat(char, stat):
    """Effective stat value: base + affect modifiers (cf. 1stMud get_curr_stat in handler.c).

    Args:
        char (dict): Character state dict (player or mob instance).
        stat (str): Stat name -- one of "str", "dex", "int", "wis", "con".

    Returns:
        int: Clamped stat value in [3, max] where max depends on race and class.
    """
    v = char.get("perm_stat", {}).get(stat, 10) + char.get("mod_stat", {}).get(stat, 0)
    if char.get("is_npc") or char.get("level", 1) > LEVEL_IMMORTAL:
        return max(3, min(MAX_STATS, v))
    _race = race_lookup(char.get("race", "Human")) or RACE_TABLE["Human"]
    _max = _race.get("max_stats", (18, 18, 18, 18, 18))
    cap = _max[_STAT_IDX.get(stat, 0)] + 4
    if is_prime_stat(char, stat):
        cap += 2
    if char.get("race", "Human") == "Human":
        cap += 1
    cap = min(cap, MAX_STATS)
    return max(3, min(cap, v))


def get_max_train(ch, stat):
    """Maximum trainable value for a stat (cf. 1stMud get_max_train in handler.c).

    For PCs: race.max_stats[stat] + prime bonus (human +3, else +2),
    capped at MAX_STATS. NPCs and immortals get flat MAX_STATS.

    Args:
        ch (dict): Character state dict.
        stat (str): Stat name -- one of "str", "dex", "int", "wis", "con".

    Returns:
        int: Maximum trainable stat value.
    """
    if ch.get("is_npc") or ch.get("level", 1) > LEVEL_IMMORTAL:
        return MAX_STATS
    _race = race_lookup(ch.get("race", "Human")) or RACE_TABLE["Human"]
    _max = _race.get("max_stats", (18, 18, 18, 18, 18))
    cap = _max[_STAT_IDX.get(stat, 0)]
    if is_prime_stat(ch, stat):
        if ch.get("race", "Human") == "Human":
            cap += 3
        else:
            cap += 2
    # [PRIMESUD] prestige tier perk: +1 trainable cap per tier (see
    # finish_tier_reset in training.py), still clamped at MAX_STATS.
    cap += ch.get("tier", 0)
    return min(cap, MAX_STATS)


# [PRIMESUD] Recursion guard for affect_modify's wield-drop branch. Mirrors
# 1stMud's `static int depth` in affect_modify (handler.c:1034). Needed here
# because our wield-drop calls unequip_char, which reverses the weapon's own
# stat_bonuses via _apply_item_modifiers -> affect_modify; a +str weapon would
# otherwise re-enter this branch (equip["wield"] still set) and drop twice.
_affect_depth = 0


def affect_modify(char, af, add):
    """Apply or remove an affect's bitvector and stat modifier

    Handles bitvector set/clear based on af["where"] (to_affects, to_immune,
    to_resist, to_vuln) and stat mod based on af["location"].

    (cf. 1stMud affect_modify in handler.c).
    [Verified: 23/06/2026; wield-drop added and re-verified 06/07/2026]

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
        # [PRIMESUD] 1stMud adds mod unclamped (APPLY_SEX, handler.c:975) and
        # lets reset_char repair out-of-range values; sex is a string here, so
        # clamp to the valid range instead.
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

    # -- Wield-drop if now too weak to hold weapon (cf. 1stMud affect_modify
    # handler.c:1030-1045). [PRIMESUD] unequip_char re-enters affect_modify
    # (reverses the weapon's stat_bonuses), so _affect_depth guards against a
    # +str weapon dropping twice -- same role as 1stMud's static depth counter.
    global _affect_depth
    wield = char.get("equip", {}).get("wield")
    if (_affect_depth == 0 and not char.get("is_npc") and wield is not None
            and item_tpl(wield).get("weight", 0)
                > STR_APP_WIELD[get_curr_stat(char, "str")] * 10):
        _affect_depth += 1
        act("You drop $p.", char, wield, None, TO_CHAR)
        act("$n drops $p.", char, wield, None, TO_ROOM)
        unequip_char(char, "wield")
        char["inv"].remove(wield)
        world.rooms[char["room"]]["items"].append(wield)
        _affect_depth -= 1


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
    """Re-set a bitvector if any remaining affect still provides it (cf. 1stMud affect_check in handler.c:1063-1148).

    Called after affect_remove clears a bit. Scans char affect_list, then
    each equipped item's runtime affect_list, then (for non-enchanted items)
    the item template's flag_affects; if any still carry the same
    where+bitvector, re-sets the flag and returns immediately (cf. 1stMud:
    runtime obj->affect_first checked before pIndexData->affect_first,
    per item, with an early return on first match).

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
        if obj is None:
            continue
        for paf in obj.get("affect_list", []):
            if paf.get("where", "to_affects") == where and paf.get("bitvector") == vector:
                char.setdefault(key, {})[vector] = True
                return
        # Template flag_affects -- non-enchanted only (cf. 1stMud handler.c:1121-1146)
        if not obj.get("enchanted"):
            tpl = item_tpl(obj)
            for paf in tpl_flag_affects(tpl):
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


# Converter "flag_affects" where -> runtime affect dict "where" (cf. 1stMud
# db2.c load_objects 'F' case: fWhere selects TO_AFFECTS/TO_IMMUNE/TO_RESIST/TO_VULN)
_FLAG_AFFECT_WHERE = {
    "affects": "to_affects",
    "immune": "to_immune",
    "resist": "to_resist",
    "vuln": "to_vuln",
}


def tpl_flag_affects(tpl):
    """Expand a template's "flag_affects" tuple into runtime affect dicts. [PRIMESUD]

    Converter-emitted "flag_affects" entries are (where, loc_name, mod, bits)
    tuples (cf. 1stMud pObjIndex affect_first, db2.c 'F' case), where "bits"
    is a dict of flag names (possibly with a "_unknown_bits" list of
    undefined bit ints, which is skipped). Each entry corresponds to a
    single 1stMud AffectData node -- one modifier applied once, even though
    its bitvector may carry several bits. To keep that semantics after
    expanding to one dict per bit, the modifier is only attached to the
    first (sorted) bit in the entry; the rest get modifier 0.

    Args:
        tpl (dict): Item template, as emitted by the area converter.

    Returns:
        list: Runtime affect dicts {"where", "location", "modifier", "bitvector"}.
    """
    result = []
    for where, loc_name, mod, bits in tpl.get("flag_affects", ()):
        mapped_where = _FLAG_AFFECT_WHERE.get(where, where)
        first = True
        for bit_name in sorted(bits):
            if bit_name == "_unknown_bits":
                continue
            result.append({"where": mapped_where, "location": loc_name,
                           "modifier": mod if first else 0,
                           "bitvector": bit_name})
            first = False
    return result


def _apply_item_modifiers(char, obj, tpl, add):
    """Apply stat bonuses and runtime object affects for equipped item (cf. 1stMud equip_char/unequip_char in handler.c).

    stat_bonuses maps to 1stMud .are "A" lines (TO_OBJECT, location+modifier only).
    flag_affects maps to 1stMud .are "F" lines (TO_AFFECTS/TO_IMMUNE/TO_RESIST/TO_VULN).
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
        # Template flag_affects -- non-enchanted only (cf. 1stMud pIndexData->affect_first)
        for af in tpl_flag_affects(tpl):
            affect_modify(char, af, add)
            if not add:
                affect_check(char, af.get("where", ""), af.get("bitvector", ""))
    # Runtime object affects (cf. 1stMud obj->affect_first)
    for af in obj.get("affect_list", []):
        affect_modify(char, af, add)
        if not add:
            affect_check(char, af.get("where", ""), af.get("bitvector", ""))


def unequip_char(char, slot):
    """Remove obj from slot, reverse stat_bonuses, return to inventory (cf. 1stMud unequip_char in handler.c).

    Clears the equip slot before reversing modifiers (cf. 1stMud
    `obj->wear_loc = WEAR_NONE` at handler.c:1598, set before the
    affect_modify/affect_check loop) so affect_check's equipped-item scan
    does not see the very item being removed and immediately re-set the
    bit it just cleared.
    """
    obj = char["equip"][slot]
    tpl = item_tpl(obj)
    armor = _item_armor_runtime(tpl, obj)
    if armor is not None:
        a = char.get("armor") or (100, 100, 100, 100)
        char["armor"] = (a[0]+armor[0], a[1]+armor[1], a[2]+armor[2], a[3]+armor[3])
    char["equip"][slot] = None
    _apply_item_modifiers(char, obj, tpl, False)
    char["inv"].append(obj)


def equip_char(char, obj, slot):
    """Seat obj in slot and apply stat_bonuses (cf. 1stMud equip_char in handler.c)."""
    tpl = item_tpl(obj)
    char["inv"].remove(obj)
    char["equip"][slot] = obj
    armor = _item_armor_runtime(tpl, obj)
    if armor is not None:
        a = char.get("armor") or (100, 100, 100, 100)
        char["armor"] = (a[0]-armor[0], a[1]-armor[1], a[2]-armor[2], a[3]-armor[3])
    _apply_item_modifiers(char, obj, tpl, True)


def _player_char():
    """Return the runtime player character, if present. [PRIMESUD]"""
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
    """Direct-send one line (cf. 1stMud chprintln in character.h).

    [PRIMESUD] txt may also be a list of lines -- passed through unjoined and
    batch-rendered by terminal.print_lines (avoids the device join-over-
    formatted-strings bug, see PRIME_FIRMWARE_BUGS.md).
    """
    if txt is None:
        txt = ""
    return _send_player_text(ch, txt)


def _safe_fmt(fmt, args):
    """Format fmt with args by manual parse + concat, never the firmware
    formatter. [PRIMESUD]

    The `%` operator and `.format()` are banned on-device (CLAUDE.md
    pitfall 8); this keeps the 1stMud printf-style chprintf/chprintlnf API
    usable. Supports %s, %c, %d, %% with optional `-` (left-justify),
    `0` (zero-pad, %d only) and width. Anything else raises ValueError.

    Raises:
        ValueError: On an unsupported conversion character.
    """
    out = []
    ai = 0
    i = 0
    n = len(fmt)
    while i < n:
        if fmt[i] != "%":
            j = fmt.find("%", i)
            if j < 0:
                out.append(fmt[i:])
                break
            out.append(fmt[i:j])
            i = j
            continue
        i += 1
        if i >= n:
            out.append("%")
            break
        c = fmt[i]
        if c == "%":
            out.append("%")
            i += 1
            continue
        left = False
        zero = False
        if c == "-":
            left = True
            i += 1
            c = fmt[i]
        if c == "0":
            zero = True
            i += 1
            c = fmt[i]
        width = 0
        while "0" <= c <= "9":
            width = width * 10 + (ord(c) - 48)
            i += 1
            c = fmt[i]
        arg = args[ai]
        ai += 1
        if c == "d":
            s = int_str(arg) if type(arg) is int else str(arg)  # str-ok
        elif c == "c":
            s = chr(arg) if type(arg) is int else (arg if type(arg) is str else str(arg))  # str-ok
        elif c == "s":
            s = arg if type(arg) is str else sstr(arg)
        else:
            raise ValueError("unsupported format: %" + c)
        if width > len(s):
            if zero and c == "d":
                if s[0] == "-":
                    s = "-" + "0" * (width - len(s)) + s[1:]
                else:
                    s = "0" * (width - len(s)) + s
            elif left:
                s = s + " " * (width - len(s))
            else:
                s = " " * (width - len(s)) + s
        out.append(s)
        i += 1
    return "".join(out)


def chprintf(ch, fmt, *args):
    """Printf-style direct-send without forced line break (cf. 1stMud chprintf in character.h).

    [PRIMESUD] Formats via _safe_fmt (manual concat), not the banned
    firmware `%` operator -- see CLAUDE.md pitfall 8.
    """
    if not fmt:
        return 0
    if args:
        fmt = _safe_fmt(fmt, args)
    return _send_player_text(ch, fmt)


def chprintlnf(ch, fmt, *args):
    """Printf-style direct-send with line semantics (cf. 1stMud chprintlnf in character.h).

    [PRIMESUD] Formats via _safe_fmt (manual concat), not the banned
    firmware `%` operator -- see CLAUDE.md pitfall 8.
    """
    if not fmt:
        return _send_player_text(ch, "")
    if args:
        fmt = _safe_fmt(fmt, args)
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
    if "vnum" in obj:
        # [PRIMESUD] item_tpl_get, not `vnum in ITEM_DEFS`: the membership
        # test itself loads the owning area for snapshotted foreign gear.
        tpl = item_tpl_get(obj)
        if tpl is not None:
            return tpl.get("keywords", "")
    return ""


def _obj_short(obj):
    """Return object short description from instance or template fallback. [PRIMESUD]"""
    if not isinstance(obj, dict):
        return "something"
    if "short_descr" in obj:
        return obj["short_descr"]
    if "vnum" in obj:
        tpl = item_tpl_get(obj)
        if tpl is not None:
            return tpl.get("short_descr", "something")
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
            # missing "flags" defaults to all-on (-1) like PLR_DEFAULTS
            if to is not None and (to.get("is_npc")
                                   or not (to.get("flags", -1) & PLR_AUTODAMAGE)):
                return ""
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


def _render_act(format, ch, arg1, arg2, type, to):
    """Substitute $-codes for one recipient and return the rendered line (cf. 1stMud perform_act buf).

    Substitutes $-codes as seen by *to*, appends {x color reset, capitalizes
    the first visible char (skipping color codes).  Split out from
    _perform_act so act triggers can render the mob-recipient buffer without
    printing it ([PRIMESUD] Phase E). (cf. perform_act in comm.c)
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
    return upper("".join(out))


def _perform_act(format, ch, arg1, arg2, type, to):
    """Format and deliver one act message to the player (cf. 1stMud perform_act in comm.c).

    Args:
        format (str): Act format string with $-codes.
        ch (dict): Subject character.
        arg1: Object argument (object dict or string).
        arg2: Target argument (victim dict, object dict, or string).
        type (int): Bitmask of TO_* flags.
        to (dict): Recipient character (always the player in PrimeSUD).
    """
    tprint(_render_act(format, ch, arg1, arg2, type, to))


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
    _act_to_player(format, ch, arg1, arg2, type, min_pos)
    # [PRIMESUD] Phase E: fire TRIG_ACT on NPC recipients of this act.  1stMud
    # does this inside perform_act's per-recipient loop (comm.c:2041); the
    # PrimeSUD player-only delivery above never visits mobs, so it is a
    # separate room-mob pass here, gated by the MOBtrigger latch.
    _act_trigger_mobs(format, ch, arg1, arg2, type)
    # obj/room TRIG_ACT pass (cf. perform_act tail, comm.c:2044-2073) --
    # deliberately NOT gated by the MOBtrigger latch, matching upstream
    _act_trigger_objs_rooms(format, ch, arg1, arg2, type)


def _act_to_player(format, ch, arg1, arg2, type, min_pos):
    """Deliver an act message to the solo player, if the player qualifies. [PRIMESUD]

    The recipient-selection half of act_new (cf. act_new in comm.c); split out
    so act-trigger firing runs regardless of which delivery branch matched.
    """
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

    # TO_ZONE: iterate all descriptors in ch's area; player != ch
    # (cf. 1stMud: for each desc, vch != ch, same area).  [PRIMESUD] TO_ALL is
    # not handled here -- it is ROM's room-scoped constant (see its definition
    # above), so it routes through the TO_ROOM/TO_CHAR branches instead.
    if type & TO_ZONE:
        if player is not ch and _sendok(player, min_pos):
            if isinstance(ch, dict) and ch.get("room") is not None:
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


def _act_trigger_mobs(format, ch, arg1, arg2, type):
    """Fire TRIG_ACT on the NPC recipients of an act (cf. perform_act tail, comm.c:2041). [PRIMESUD]

    Mirrors act_new's recipient selection: TO_CHAR -> ch, TO_VICT -> the
    victim, TO_ROOM/TO_NOTVICT -> every room NPC except ch (and the victim for
    NOTVICT).  TO_ZONE reaches only descriptors (players) in 1stMud, so no mob
    recipients; TO_ALL is ROM's room-scoped TO_ROOM | TO_CHAR here (see its
    definition above), so its acts reach room NPCs through those bits --
    matching ROM, where act_new's room loop visits mobs and fires
    mp_act_trigger on them.  The trigger phrase is matched against the line as
    rendered for that mob.

    The MOBtrigger latch is held off for the whole dispatch -- [PRIMESUD]
    stricter than 1stMud (which latches only emote/asound): a prog fired here
    must not have its own act output recursively fire further act triggers, a
    hard recursion bound for the Prime's small stack.
    """
    import mobprog  # deferred: keep mobprog off the boot path
    if not mobprog.MOBtrigger:
        return
    has_trigger = mobprog.has_trigger
    vch = arg2 if isinstance(arg2, dict) and "room" in arg2 else None
    # Collect only the NPC recipients that actually carry an act trigger, so a
    # populated but trigger-less room costs one has_trigger check per mob and
    # never flips the latch or renders a buffer.
    recips = []
    if (type & TO_CHAR) and isinstance(ch, dict) and ch.get("is_npc") and has_trigger(ch, "act"):
        recips.append(ch)
    if (type & TO_VICT) and vch is not None and vch is not ch and vch.get("is_npc") and has_trigger(vch, "act"):
        recips.append(vch)
    if type & (TO_ROOM | TO_NOTVICT):
        room = _act_room(ch, arg1, arg2)
        rs = world.rooms._data.get(room) if room is not None else None
        if rs is not None:
            for mid in list(rs.get("mobs", [])):
                mob = world.chars.get(mid)
                if mob is None or mob is ch or not mob.get("is_npc"):
                    continue
                if (type & TO_NOTVICT) and mob is vch:
                    continue
                if has_trigger(mob, "act"):
                    recips.append(mob)
    if not recips:
        return
    saved = mobprog.MOBtrigger
    mobprog.MOBtrigger = False
    try:
        for mob in recips:
            # an earlier recipient's prog may have extracted a later one
            # (mppurge / mpdamage); skip a mob that is no longer resident.
            mid = mob.get("id")
            if mid is not None and world.chars.get(mid) is not mob:
                continue
            buf = _render_act(format, ch, arg1, arg2, type, mob)
            mobprog.act_trigger(buf, mob, ch, arg1, arg2, "act")
    finally:
        mobprog.MOBtrigger = saved


def _act_trigger_objs_rooms(format, ch, arg1, arg2, type):
    """Fire TRIG_ACT on room objs, carried objs, and the room (cf. perform_act
    tail, comm.c:2044-2073). [PRIMESUD]

    Upstream this block runs inside perform_act -- once per qualifying
    TO_ROOM/TO_NOTVICT recipient -- and is NOT gated on the MOBtrigger latch
    (only the mob-recipient branch is): an emote or a latched give still fires
    obj/room act triggers.  Recursion is bounded by mobprog's global
    program_flow call-depth counter.  The trigger text is the unrendered
    format string (upstream passes ``orig``).  As in _act_trigger_mobs, the
    SENDOK position gate on recipients is not mirrored.
    """
    if not (type & (TO_ROOM | TO_NOTVICT)):
        return
    # ponytail: no obj/room progs loaded -> skip the per-act room scan; a
    # per-room trigger cache is the upgrade path if this shows on-device
    if not world.OBJPROGS and not world.ROOMPROGS:
        return
    if not isinstance(ch, dict) or ch.get("room") is None:
        return
    rs = world.rooms._data.get(ch["room"])
    if rs is None:
        return
    vch = arg2 if isinstance(arg2, dict) and "room" in arg2 else None
    # one firing pass per qualifying recipient, as upstream's per-recipient
    # perform_act calls repeat the whole block
    persons = []
    player = _player_char()
    if player is not None and player.get("room") == ch["room"]:
        persons.append(player)
    for mid in list(rs.get("mobs", [])):
        m = world.chars.get(mid)
        if m is not None:
            persons.append(m)
    recips = 0
    for p in persons:
        if p is ch:
            continue
        if (type & TO_NOTVICT) and p is vch:
            continue
        recips += 1
    if recips == 0:
        return
    import mobprog  # deferred: keep mobprog off the boot path
    for _i in range(recips):
        mobprog.act_trigger_objs_room(format, ch)


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


def _is_lit_light(obj):
    """True if obj (instance dict or bare VNUM) is a lit light source. [PRIMESUD]

    Fuel is read from the instance, falling back to the template. Value[2]
    semantics (cf. 1stMud): 0 = dead, absent/negative = infinite, positive =
    hours left -- so a dead (0) light is not lit and everything else is.
    """
    tpl = item_tpl(obj)
    if tpl.get("type") != "light":
        return False
    fuel = obj.get("light_hours") if isinstance(obj, dict) else None
    if fuel is None:
        fuel = tpl.get("light_hours")
    return fuel is None or fuel != 0


def room_light(room_vnum):
    """Count lit light sources in a room -- worn by occupants or on the floor. [PRIMESUD]

    1stMud maintains ``room->light`` incrementally in char_to_room /
    equip_char (handler.c:1321/1578); PrimeSUD computes it on demand instead
    -- extraction/removal paths are many and a persistent counter would drift
    and need saving. Counts every character in the room (player and mobs both
    live in ``world.chars``) wearing a lit light-slot item, plus [PRIMESUD]
    any lit light lying on the room floor (``_is_lit_light``). Stock
    ROM/1stMud count only worn lights (``room->light`` is bumped in
    equip_char, never obj_to_room); the floor-light behaviour is an
    intentional PrimeSUD deviation -- a dropped torch or a cast
    continual-light ball illuminates the room. Items inside containers do not
    count. (cf. room->light in handler.c; DESIGN.md "Adjusted from 1stMud")

    Args:
        room_vnum (int): Room VNUM.

    Returns:
        int: Number of lit light sources in the room.
    """
    total = 0
    for ch in world.chars.values():
        if ch.get("room") != room_vnum:
            continue
        eq = ch.get("equip", {}).get("light")
        if eq is not None and _is_lit_light(eq):
            total += 1
    rs = world.rooms._data.get(room_vnum)  # runtime state only; no lazy-load
    if rs:
        for obj in rs.get("items", []):  # [PRIMESUD] floor lights
            if _is_lit_light(obj):
                total += 1
    return total


def room_is_dark(room_vnum):
    """True if a room is unlit (cf. 1stMud room_is_dark in handler.c:2308). [PRIMESUD]

    Order matches the source: a lit light source overrides everything; then a
    set ROOM_DARK flag forces dark; inside/city sectors are always lit;
    finally an outdoors room goes dark at SUN_SET / SUN_DARK.

    Args:
        room_vnum (int): Room VNUM.

    Returns:
        bool: True if the room is dark.
    """
    if room_light(room_vnum) > 0:
        return False
    rdef = ROOM_DEFS[room_vnum]
    if rdef.get("flags", {}).get("dark"):
        return True
    sector = rdef.get("sector", "inside")
    if sector == "inside" or sector == "city":
        return False
    if time_info["sunlight"] == SUN_SET or time_info["sunlight"] == SUN_DARK:
        return True
    return False


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

    Checks AFF_BLIND, quest/gquest target overrides, room darkness vs
    AFF_INFRARED, AFF_INVISIBLE vs detect_invis, AFF_SNEAK skill contest,
    and AFF_HIDE vs detect_hidden.
    PLR_HOLYLIGHT (handler.c:2403) maps to the [PRIMESUD] "debug holylight"
    toggle (imm sight for playtesting). [PRIMESUD] invis_level/incog/arena
    not ported.

    Args:
        ch (dict): Observer (player or mob instance).
        victim (dict): Target (player or mob instance).

    Returns:
        bool: True if ch can see victim.
    """
    if ch is victim:
        return True

    # cf. 1stMud PLR_HOLYLIGHT (handler.c:2403) -- [PRIMESUD] debug toggle
    if not ch.get("is_npc") and "holylight" in DBG:
        return True

    ch_aff = ch.get("affected_by", {})
    v_aff = victim.get("affected_by", {})

    if ch_aff.get("blind"):
        return False

    # cf. handler.c:2421-2426 -- a quester keeps sight of their quest-target
    # mob, and a gquester of any still-unkilled gquest target, through
    # darkness/invis/hide. [PRIMESUD] quest_mob is a template vnum, so any
    # live instance matches (same semantics as quest.py kill credit); plain
    # dict reads + a lazy gquest import keep handler decoupled from quest.
    if not ch.get("is_npc") and victim.get("is_npc"):
        tpl = victim.get("tpl", 0)
        if tpl:
            if ch.get("quest_status") and tpl == ch.get("quest_mob", 0):
                return True
            from gquest import gquest_info, GQUEST_RUNNING, gq_is_player_target  # deferred: gquest imports handler
            if (gquest_info["running"] == GQUEST_RUNNING
                    and gq_is_player_target(tpl)):
                return True

    # cf. 1stMud can_see dark gate (handler.c:2428): a dark room hides the
    # victim from a viewer without infrared. Observer room resolves from
    # ch["room"] for both players and mobs -- mob aggro routes through
    # can_see, so a dark room shields an unlit player from non-infrared
    # aggressors (1stMud-correct).
    # Membership tests _data (already-loaded rooms) not ROOM_DEFS: a plain
    # `in ROOM_DEFS` would fire LazyDict's on-demand area load. The observer is
    # always standing in a loaded room, so _data is sufficient and side-effect
    # free; an unknown/stray room vnum just skips the gate (treated as lit).
    ch_room = ch.get("room")
    if (ch_room in ROOM_DEFS._data and room_is_dark(ch_room)
            and not ch_aff.get("infrared")):
        return False

    if v_aff.get("invisible") and not ch_aff.get("detect_invis"):
        return False

    if (v_aff.get("sneak") and not ch_aff.get("detect_hidden")
            and victim.get("fighting") is None):
        from skill_utils import get_skill  # deferred: skill_utils imports handler
        chance = get_skill(victim, GSN_SNEAK,
                           is_mob=bool(victim.get("is_npc")))
        chance += get_curr_stat(victim, "dex") * 3 // 2
        chance -= get_curr_stat(ch, "int") * 2
        chance -= ch.get("level", 1) - victim.get("level", 1) * 3 // 2
        if randint(1, 100) < chance:
            return False

    if (v_aff.get("hide") and not ch_aff.get("detect_hidden")
            and victim.get("fighting") is None):
        return False

    return True


def can_see_obj(ch, obj):
    """Check if ch can see obj (cf. 1stMud can_see_obj in handler.c:2456).

    Check order matches the source: HOLYLIGHT (mapped to the [PRIMESUD]
    "debug holylight" toggle), quest-object override, ITEM_VIS_DEATH,
    blindness (potions exempt), a lit light source, ITEM_INVIS vs
    detect_invis, ITEM_GLOW, then a dark room vs dark_vision.

    Args:
        ch (dict): Observer (player or mob instance).
        obj (dict): Target object instance, or a plain VNUM int.

    Returns:
        bool: True if ch can see obj.
    """
    vnum = obj["vnum"] if isinstance(obj, dict) else obj
    # [PRIMESUD] item_tpl, not ITEM_DEFS[vnum]: snapshotted foreign gear must
    # not drag its owner area back in on every look/list/get scan.
    tpl = item_tpl(obj)
    if isinstance(obj, dict) and "extra_flags" in obj:
        flags = obj["extra_flags"]
    else:
        flags = tpl.get("extra_flags", {})
    if isinstance(obj, dict) and "type" in obj:
        otype = obj["type"]
    else:
        otype = tpl.get("type")

    # cf. 1stMud PLR_HOLYLIGHT (handler.c:2458) -- [PRIMESUD] debug toggle
    if not ch.get("is_npc") and "holylight" in DBG:
        return True

    ch_aff = ch.get("affected_by", {})

    # cf. handler.c:2461 -- a quester always sees their quest object (so a
    # retrieve token in a dark room stays visible). [PRIMESUD] matched by
    # template vnum, same semantics as quest.py quest_obj_check.
    if ch.get("quest_status") and vnum and vnum == ch.get("quest_obj", 0):
        return True

    if flags.get("vis_death"):
        return False

    if ch_aff.get("blind") and otype != "potion":
        return False

    # A lit light source is visible even in the dark. Value[2] semantics
    # (cf. 1stMud): 0 = dead (fall through), absent/negative = infinite,
    # positive = hours left.
    if otype == "light":
        fuel = obj.get("light_hours") if isinstance(obj, dict) else None
        if fuel is None:
            fuel = tpl.get("light_hours")
        if fuel is None or fuel != 0:
            return True

    if flags.get("invis") and not ch_aff.get("detect_invis"):
        return False

    if flags.get("glow"):
        return True

    ch_room = ch.get("room")  # _data, not ROOM_DEFS: avoid a lazy area load
    if (ch_room in ROOM_DEFS._data and room_is_dark(ch_room)
            and not ch_aff.get("dark_vision")):
        return False

    return True


def check_blind(ch):
    """True unless ch is blinded, printing the failure line (cf. 1stMud check_blind in act_info.c:495).

    HOLYLIGHT short-circuit (act_info.c:498) maps to the [PRIMESUD]
    "debug holylight" toggle.

    Args:
        ch (dict): Observer whose sight is being tested.

    Returns:
        bool: True if ch can see; False (after printing "You can't see a
        thing!") if blinded.
    """
    if not ch.get("is_npc") and "holylight" in DBG:
        return True
    if ch.get("affected_by", {}).get("blind"):
        chprintln(ch, "You can't see a thing!")
        return False
    return True


def number_argument(arg):
    """Parse '2.sword' into (2, 'sword'); plain 'sword' returns (1, 'sword') (cf. 1stMud number_argument in interp.c).

    Non-numeric prefix ('abc.sword') returns (0, 'sword') like C atoi, so
    nothing matches.
    """
    dot = arg.find('.')
    if dot < 0:
        return 1, arg
    try:
        return int(arg[:dot]), arg[dot + 1:]
    except ValueError:
        return 0, arg[dot + 1:]


def get_char_room(fragment, inst_ids, mob_instances, viewer=None):
    """Find the number-th mob in inst_ids whose keywords match fragment (cf. 1stMud get_char_room in handler.c).

    Supports '2.guard' counted syntax via number_argument.  'self' is not
    handled here since players are not mob instances; callers that allow
    self-targeting check it themselves. [PRIMESUD]

    Args:
        fragment (str): Player-typed name fragment, optionally 'N.name'.
        inst_ids (list): Ordered list of mob instance IDs to search.
        mob_instances (dict): Mob instance mapping mob ID -> mob instance dict.
        viewer (dict): Observer; unseen mobs are skipped (cf. 1stMud
            can_see check).  None skips the visibility filter.

    Returns:
        int or None: Matching mob instance ID, or None if not found.
    """
    number, arg = number_argument(fragment)
    count = 0
    for mob_id in inst_ids:
        inst = mob_instances[mob_id]
        if viewer is not None and not can_see(viewer, inst):
            continue
        # Instance keywords override template (cf. 1stMud per-char name;
        # set when a bought pet is given a custom name)
        kw = inst.get("keywords") or MOB_DEFS[inst["tpl"]].get("keywords", "")
        if not is_name(arg, kw):
            continue
        count += 1
        if count == number:
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

