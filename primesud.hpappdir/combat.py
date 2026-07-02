"""Combat rounds, damage resolution, skills, and fight state."""

import world
from world import (
    I_CORPSE, I_CORPSE_11,
    I_COIN_SILVER_GCASH,
    I_COIN_GOLD_GCASH,
    I_COINS_SILVER_GCASH,
    I_COINS_GOLD_GCASH,
    I_COINS_SILVER_GOLD_GCASH,
)
from colors import upper
from config import (
    MAX_MORTAL_LEVEL,
    PULSE_VIOLENCE,
    POS_ORDER,
    R_STARTING_ROOM,
    DEATH_MSG_DELAY,
    CON_APP_HITP,
    WIS_APP_PRACTICE,
    ATTACK_TABLE,
    TYPE_HIT,
    TYPE_UNDEFINED,
    DAM_NONE,
    DAM_BASH,
    DAM_PIERCE,
    DAM_SLASH,
    AC_PIERCE,
    AC_BASH,
    AC_SLASH,
    AC_EXOTIC,
    IS_NORMAL,
    IS_IMMUNE,
    IS_RESISTANT,
    IS_VULNERABLE,
    IMMUNE_NONE,
    DAM_TO_FLAG,
    XP_BASE,
    SIZE_RANK,
)
import classes
from handler import (get_hitroll, get_damroll, get_armor, get_curr_stat, act,
                     is_awake, can_see, affect_to_char, affect_remove,
                     chprintln, chprintlnf, get_char_room,
                     TO_CHAR, TO_NOTVICT, TO_ROOM, TO_VICT,
                     is_good, is_evil, is_neutral)
from item import (create_object, item_extra_flags,
                  set_item_extra_flag, get_obj_list, obj_vnum,
                  apply_money_pickup)
from picker import pick_from
from player import PLR_AUTOLOOT, PLR_AUTOSAC, PLR_AUTOGOLD, PLR_DEFAULTS
from races import RACE_TABLE
from skill_utils import get_skill, check_improve, skill_level, WaitState, DazeState
from skills_table import (
    SKILL_TABLE, SKILLS, WEAPON_GSN_MAP,
    GSN_BACKSTAB, GSN_BASH, GSN_BERSERK, GSN_DIRT, GSN_DISARM,
    GSN_DODGE, GSN_HAND_TO_HAND, GSN_KICK, GSN_PARRY,
    GSN_RESCUE, GSN_SHIELD_BLOCK, GSN_SECOND_ATTACK, GSN_THIRD_ATTACK,
    GSN_TRIP,
)
from terminal import tprint
from urandom import randint
from util import wait
from world import ITEM_DEFS, MOB_DEFS, ROOM_DEFS


# -- Violence update (called every PULSE_VIOLENCE) -----------------------------

def violence_update(player):
    """One combat pulse: all chars with a fight target attack (cf. 1stMud violence_update in fight.c).
    [Verified: 02/07/2026] -- mobprog/objprog/roomprog TRIG_FIGHT and hunt_victim not ported (see TODOs).

    Args:
        player (dict): Player state dict.
    """
    chars = world.chars

    # Need to copy to list first as chars could get modified during iteration (on deaths)
    for ch in [chars[k] for k in sorted(chars)]:
        # 1stMud: IsNPC(ch) && ch->fighting == NULL && IsAwake(ch) && ch->hunting != NULL
        if ch["is_npc"] and ch["fighting"] is None and is_awake(ch) and ch.get("hunting") is not None:
            # TODO: hunt_victim not ported
            continue

        # 1stMud: victim = ch->fighting; if victim == NULL || ch->in_room == NULL: continue
        # [PRIMESUD] ch->in_room == NULL cannot occur; all chars store fighting as char ID
        if ch["fighting"] is None:
            continue
        victim = chars.get(ch["fighting"])
        if victim is None:
            # [PRIMESUD] 1stMud nulls stale fighting refs in extract_char; we have no
            # equivalent sweep, so detect and clean up lazily here.
            stop_fighting(ch, both=False)
            continue

        # 1stMud: if IsAwake(ch) && ch->in_room == victim->in_room: multi_hit else stop_fighting
        if is_awake(ch) and ch["room"] == victim["room"]:
            multi_hit(ch, victim)
        else:
            stop_fighting(ch, both=False)

        # 1stMud: victim = ch->fighting; if victim == NULL: continue
        if ch["fighting"] is None:
            continue

        # 1stMud: check_assist(ch, victim)
        check_assist(ch, victim)

        # TODO: mob TRIG_FIGHT / TRIG_HPCNT triggers not ported
        # TODO: obj worn-item TRIG_FIGHT triggers not ported
        # TODO: room TRIG_FIGHT trigger not ported


def check_assist(ch, victim):
    """Let idle room chars join combat (cf. 1stMud check_assist in fight.c).
    [Verified: 02/07/2026]

    Three cases mirror 1stMud exactly:
    - ch is player, rch is mob with assist_players: rch jumps in against victim.
    - ch is player, rch is player: autoassist / charm (no-op in single-player).
    - ch is mob (not charmed), rch is mob: assist_all / group / race / align / vnum;
      50% trigger chance; target picked from victim's group (single-player: victim).

    Args:
        ch (dict): Attacker (player or mob).
        victim (dict): Ch's current fight target.
    """
    chars = world.chars
    rs    = world.rooms[ch["room"]]
    if ch["is_npc"]:
        ch_tpl = MOB_DEFS[ch["tpl"]]

    for mob_id in list(rs["mobs"]):
        rch = chars.get(mob_id)
        if rch is None or not is_awake(rch) or rch["fighting"] is not None:
            continue

        rch_tpl = MOB_DEFS[rch["tpl"]]
        off = rch.get("off_flags", {})

        # Case 1 & 2: ch is player
        if not ch["is_npc"]:
            # Case 1: mob with assist_players aids player against victim
            if off.get("assist_players") and rch["level"] + 6 > victim["level"]:
                tprint("{} screams and attacks!".format(rch_tpl["short_descr"]))
                multi_hit(rch, victim)
            # Case 2: autoassist / charm -- not implemented; skip mob
            continue

        # Case 3: ch is mob (not charmed)
        ch_grp  = ch_tpl.get("group")
        rch_grp = rch_tpl.get("group")
        qualifies = (
            off.get("assist_all")
            or (rch_grp and rch_grp == ch_grp)
            or (off.get("assist_race") and rch_tpl.get("race") == ch_tpl.get("race"))
            or (off.get("assist_align") and _same_align(rch_tpl, ch_tpl))
            or (off.get("assist_vnum") and rch["tpl"] == ch["tpl"])
        )
        if not qualifies:
            continue

        # 50% chance to skip (cf. 1stMud number_bits(1) == 0)
        if randint(0, 1) == 0:
            continue

        # Pick random target from victim's group (cf. 1stMud target selection loop:
        # candidates require can_see(rch, vch)).
        # [PRIMESUD] Single-player: victim's group = victim only; target is always victim.
        if not can_see(rch, victim):
            continue
        tprint("{} screams and attacks!".format(rch_tpl["short_descr"]))
        multi_hit(rch, victim)


# -- Helpers -------------------------------------------------------------------

def _same_align(tpl_a, tpl_b):
    """True if both templates share the same alignment band (good/neutral/evil). [PRIMESUD]

    Args:
        tpl_a (dict): First mob template.
        tpl_b (dict): Second mob template.

    Returns:
        bool: True if both are in the same alignment band.
    """
    return ((is_good(tpl_a) and is_good(tpl_b))
            or (is_evil(tpl_a) and is_evil(tpl_b))
            or (is_neutral(tpl_a) and is_neutral(tpl_b)))


def _dice(num, size):
    """Roll num dice of size sides and return the sum (cf. 1stMud `dice` in db.c).
    [Verified: 02/07/2026]

    Args:
        num (int): Number of dice to roll.
        size (int): Number of sides per die.

    Returns:
        int: Sum of all dice rolls.
    """
    total = 0
    for _ in range(num):
        total += randint(1, size)
    return total


def _cdiv(a, b):
    """Integer division truncating toward zero (C semantics; Python // floors). [PRIMESUD]"""
    q = abs(a) // abs(b)
    return -q if (a < 0) != (b < 0) else q


def interpolate(level, value_00, value_32):
    """Linear interpolation between level-0 and level-32 values (cf. 1stMud interpolate in db.c)."""
    return value_00 + _cdiv(level * (value_32 - value_00), 32)


def get_thac0(ch):
    """Base THAC0 before hitroll/skill adjustments (cf. 1stMud one_hit in fight.c).
    [Verified: 02/07/2026]

    NPC curve from act class flags; player curve from the class table
    (worst thac0_00, best thac0_32 across held classes).

    Args:
        ch (dict): Attacker (player or mob instance).

    Returns:
        int: Base THAC0 after the negative soft-caps.
    """
    if ch["is_npc"]:
        act = ch.get("act_flags", {})
        thac0_00 = 20
        thac0_32 = -4
        if act.get("warrior"):
            thac0_32 = -10
        elif act.get("thief"):
            thac0_32 = -4
        elif act.get("cleric"):
            thac0_32 = 2
        elif act.get("mage"):
            thac0_32 = 6
    else:
        thac0_00 = classes.get_thac00(ch)
        thac0_32 = classes.get_thac32(ch)
    thac0 = interpolate(ch["level"], thac0_00, thac0_32)
    if thac0 < 0:
        thac0 = _cdiv(thac0, 2)
    if thac0 < -5:
        thac0 = -5 + _cdiv(thac0 + 5, 2)
    return thac0


def xp_compute(gch, victim, total_levels):
    """Compute XP for gch from killing victim in a group of total_levels
    (cf. 1stMud xp_compute in fight.c).
    [Verified: 02/07/2026] -- time_per_level penalty skipped (no play-time tracking).

    Includes alignment-based XP modifiers and alignment drift on the killer.

    Args:
        gch (dict): Group member receiving XP (player).
        victim (dict): Defeated mob instance.
        total_levels (int): Sum of effective levels in the group
            (PCs at full level, NPCs at level/2).

    Returns:
        int: XP gain for this group member.
    """
    level_range = victim["level"] - gch["level"]

    # -- Base XP from level difference (cf. 1stMud xp_compute switch)
    if level_range <= -10:
        base_exp = 0
    elif level_range > 4:
        base_exp = 160 + 20 * (level_range - 4)
    else:
        base_exp = XP_BASE[level_range]

    # -- Alignment drift (cf. 1stMud xp_compute alignment section)
    victim_align = victim.get("alignment", 0)
    gch_align = gch.get("alignment", 0)
    victim_act = victim.get("act_flags", {})

    align = victim_align - gch_align

    if not victim_act.get("noalign"):
        if align > 500:
            change = (align - 500) * base_exp // 500 * gch["level"] // total_levels
            change = max(1, change)
            gch["alignment"] = max(-1000, gch_align - change)
        elif align < -500:
            change = (-align - 500) * base_exp // 500 * gch["level"] // total_levels
            change = max(1, change)
            gch["alignment"] = min(1000, gch_align + change)
        else:
            # C division truncates toward zero; Python // floors. gch_align may
            # be negative here, so compute on the magnitude and re-apply sign.
            change = abs(gch_align) * base_exp // 500 * gch["level"] // total_levels
            if gch_align < 0:
                change = -change
            gch["alignment"] -= change

    # -- Alignment XP modifiers (cf. 1stMud xp_compute alignment XP section)
    gch_align = gch.get("alignment", 0)
    if victim_act.get("noalign"):
        xp = base_exp
    elif gch_align > 500:
        if victim_align < -750:
            xp = base_exp * 4 // 3
        elif victim_align < -500:
            xp = base_exp * 5 // 4
        elif victim_align > 750:
            xp = base_exp // 4
        elif victim_align > 500:
            xp = base_exp // 2
        elif victim_align > 250:
            xp = base_exp * 3 // 4
        else:
            xp = base_exp
    elif gch_align < -500:
        if victim_align > 750:
            xp = base_exp * 5 // 4
        elif victim_align > 500:
            xp = base_exp * 11 // 10
        elif victim_align < -750:
            xp = base_exp // 2
        elif victim_align < -500:
            xp = base_exp * 3 // 4
        elif victim_align < -250:
            xp = base_exp * 9 // 10
        else:
            xp = base_exp
    elif gch_align > 200:
        if victim_align < -500:
            xp = base_exp * 6 // 5
        elif victim_align > 750:
            xp = base_exp // 2
        elif victim_align > 0:
            xp = base_exp * 3 // 4
        else:
            xp = base_exp
    elif gch_align < -200:
        if victim_align > 500:
            xp = base_exp * 6 // 5
        elif victim_align < -750:
            xp = base_exp // 2
        elif victim_align < 0:
            xp = base_exp * 3 // 4
        else:
            xp = base_exp
    else:
        if victim_align > 500 or victim_align < -500:
            xp = base_exp * 4 // 3
        elif -200 < victim_align < 200:
            xp = base_exp // 2
        else:
            xp = base_exp

    # -- Low-level scaling (cf. 1stMud xp_compute)
    if gch["level"] < 6:
        xp = 10 * xp // (gch["level"] + 4)

    # -- High-level scaling (cf. 1stMud xp_compute)
    if gch["level"] > 35:
        xp = 15 * xp // (gch["level"] - 25)

    # -- Time-per-level penalty
    # [PRIMESUD] skip time_per_level (no play-time tracking ported)

    # -- Randomize +/-25% (cf. 1stMud xp_compute: number_range(xp*3/4, xp*5/4))
    xp = randint(xp * 3 // 4, xp * 5 // 4)

    # -- Group scaling (cf. 1stMud xp_compute: xp * gch->level / total_levels)
    xp = xp * gch["level"] // max(1, total_levels - 1)

    return xp


def _get_weapon_sn(ch, slot="wield"):
    """Return (sn, tpl_or_None) for the weapon in the given equip slot (cf. get_weapon_sn in handler.c).
    [Verified: 02/07/2026] -- 1stMud maps a wielded non-weapon to hand_to_hand; PrimeSUD's
    slot system only seats weapons in wield/secondary, so the case cannot occur.

    Args:
        ch (dict): Player or mob instance dict.
        slot (str): Equip slot key ('wield' or 'secondary').

    Returns:
        tuple: (sn (int), weapon_tpl (dict or None)).
            sn=GSN_HAND_TO_HAND when unarmed; sn=-1 for unknown weapon type.
    """
    wobj = ch["equip"].get(slot)
    if wobj is None:
        return GSN_HAND_TO_HAND, None
    tpl = ITEM_DEFS[wobj["vnum"]]
    sn = WEAPON_GSN_MAP.get(tpl.get("weapon_type", ""), -1)
    return sn, tpl


def _get_weapon_skill(ch, sn):
    """Return weapon skill% for ch and sn (cf. get_weapon_skill in handler.c).
    [Verified: 02/07/2026] -- 1stMud clamps Range(0,skill,100); learned is capped
    at 100 by check_improve and NPC formulas are non-negative, so min() suffices.

    Args:
        ch (dict): Player or mob instance dict.
        sn (int): Skill GSN; -1 = unknown weapon type.

    Returns:
        int: Skill percentage (0-100), capped.
            NPC: level-scaled formula. Player: learned dict lookup.
    """
    if ch.get("is_npc"):
        if sn == -1:
            skill = 3 * ch["level"]
        elif sn == GSN_HAND_TO_HAND:
            skill = 40 + 2 * ch["level"]
        else:
            skill = 40 + 5 * ch["level"] // 2
        return min(skill, 100)
    if sn == -1:
        return min(3 * ch["level"], 100)
    return ch["learned"].get(sn, 0)


# -- Damage flavour ------------------------------------------------------------

def _damage_verb(dmg):
    """Return verb pair for a damage amount (cf. 1stMud dam_message in fight.c).

    Args:
        dmg (int): Damage dealt (0 = miss).

    Returns:
        tuple: (first_person_verb (str), third_person_verb (str)).
    """
    # fmt: off
    if dmg == 0:     return ("miss",                                              "misses")
    if dmg <= 4:     return ("scratch",                                           "scratches")
    if dmg <= 8:     return ("graze",                                             "grazes")
    if dmg <= 12:    return ("hit",                                               "hits")
    if dmg <= 16:    return ("injure",                                            "injures")
    if dmg <= 20:    return ("wound",                                             "wounds")
    if dmg <= 24:    return ("maul",                                              "mauls")
    if dmg <= 28:    return ("decimate",                                          "decimates")
    if dmg <= 32:    return ("devastate",                                         "devastates")
    if dmg <= 36:    return ("maim",                                              "maims")
    if dmg <= 40:    return ("MUTILATE",                                          "MUTILATES")
    if dmg <= 44:    return ("DISEMBOWEL",                                        "DISEMBOWELS")
    if dmg <= 48:    return ("DISMEMBER",                                         "DISMEMBERS")
    if dmg <= 52:    return ("MASSACRE",                                          "MASSACRES")
    if dmg <= 56:    return ("MANGLE",                                            "MANGLES")
    if dmg <= 60:    return ("{b*** {BDEMOLISH {b***{x",                          "{b*** {BDEMOLISHES {b***{x")
    if dmg <= 75:    return ("{m*** {MDEVASTATE {m***{x",                         "{m*** {MDEVASTATES {m***{x")
    if dmg <= 100:   return ("{c=== {COBLITERATE {c==={x",                        "{c=== {COBLITERATES {c==={x")
    if dmg <= 125:   return ("{R>>> {YANNIHILATE {R<<<{x",                        "{R>>> {YANNIHILATES {R<<<{x")
    if dmg <= 150:   return ("{Y<<< {RERADICATE {Y>>>{x",                         "{Y<<< {RERADICATES {Y>>>{x")
    if dmg <= 185:   return ("{W***** {CPULVERIZE {W*****{x",                     "{W***** {CPULVERIZES {W*****{x")
    if dmg <= 220:   return ("{B-=- VAPORIZE -=-{x",                              "{B-=- VAPORIZES -=-{x")
    if dmg <= 275:   return ("{M<-==-> {CATOMIZE {M<-==->{x",                     "{M<-==-> {CATOMIZES {M<-==->{x")
    if dmg <= 315:   return ("{C<{W-:-{C>{W ASPHYXIATE {C<{W-:-{C>{x",            "{C<{W-:-{C>{W ASPHYXIATES {C<{W-:-{C>{x")
    if dmg <= 390:   return ("{W<-*-> {CRAVAGE {W<-*->{x",                        "{W<-*-> {CRAVAGES {W<-*->{x")
    if dmg <= 435:   return ("{M<>*<> {CFISSURE {M<>*<>{x",                       "{M<>*<> {CFISSURES {M<>*<>{x")
    if dmg <= 500:   return ("{Y<*>{R<*> {bLIQUIDATE {R<*>{Y<*>{x",               "{Y<*>{R<*> {bLIQUIDATES {R<*>{Y<*>{x")
    if dmg <= 590:   return ("{b<*>{Y<*>{R<*>{G EVAPORATE {R<*>{Y<*>{b<*>{x",     "{b<*>{Y<*>{R<*>{G EVAPORATES {R<*>{Y<*>{b<*>{x")
    if dmg <= 650:   return ("{Y<-=-> {RSUNDER {Y<-=->{x",                        "{Y<-=-> {RSUNDERS {Y<-=->{x")
    if dmg <= 790:   return ("{W<=-=><=-=> {GTEAR INTO {W<=-=><=-=>{x",           "{W<=-=><=-=> {GTEARS INTO {W<=-=><=-=>{x")
    if dmg <= 880:   return ("{Y<->*<=> {bWASTE {Y<=>*<->{x",                     "{Y<->*<=> {bWASTES {Y<=>*<->{x")
    if dmg <= 960:   return ("{R<-+-><-*-> {WCREMATE {R<-*-><-+->{x",             "{R<-+-><-*-> {WCREMATES {R<-*-><-+->{x")
    if dmg <= 1040:  return ("{M<*><*>{R<*><*> ANNIHILATE <*><*>{M<*><*>{x",      "{M<*><*>{R<*><*> ANNIHILATES <*><*>{M<*><*>{x")
    if dmg <= 3000:  return ("{rinflict {RUNSPEAKABLE PAIN{r on{x",               "{rinflicts {RUNSPEAKABLE PAIN{r on{x")
    if dmg <= 6000:  return ("{rinflict {RUNTHINKABLE PAIN{r on{x",               "{rinflicts {RUNTHINKABLE PAIN{r on{x")
    if dmg <= 9000:  return ("{rinflict {RUNIMAGINABLE PAIN{r on{x",              "{rinflicts {RUNIMAGINABLE PAIN{r on{x")
    if dmg <= 12000: return ("{rinflict {RUNBELIEVABLE PAIN{r on{x",              "{rinflicts {RUNBELIEVABLE PAIN{r on{x")
    return ("do {mTOTALLY{x, {mUTTERLY{x, {mINCONCEIVABLE{x things to",           "does {mTOTALLY{x, {mUTTERLY{x, {mINCONCEIVABLE{x things to")
    # fmt: on


def _damage_punct(dmg):
    """Return punctuation string matching damage severity (cf. 1stMud dam_message in fight.c).

    Args:
        dmg (int): Damage dealt.

    Returns:
        str: One of '.', '!', '!!', '!!!', '!!!!'.
    """
    if dmg <= 250:  return "."
    if dmg <= 1000: return "!"
    if dmg <= 3000: return "!!"
    if dmg <= 5000: return "!!!"
    return "!!!!"


def _attack_info(dam_type):
    """Resolve display noun and damage class for a dam_type key (cf. 1stMud attack_table in const.c).

    Args:
        dam_type (str): Attack type name from area file (e.g. 'bite', 'divine').

    Returns:
        tuple: (noun (str), dam_class (int)).
    """
    noun, dc = ATTACK_TABLE.get(dam_type, ("hit", DAM_BASH))
    if dc == DAM_NONE:
        dc = DAM_BASH
    return noun, dc


def _ac_type_for_damage_class(dam_class):
    """Map damage class to 1stMud armor bucket. [PRIMESUD]"""
    if dam_class == DAM_PIERCE:
        return AC_PIERCE
    if dam_class == DAM_SLASH:
        return AC_SLASH
    if dam_class == DAM_BASH or dam_class == DAM_NONE:
        return AC_BASH
    return AC_EXOTIC


# -- Immunity check (cf. 1stMud check_immune in handler.c) ---------------------

def check_immune(ch, dam_type):
    """Determine immunity/resistance/vulnerability of ch to a damage class
    (cf. 1stMud check_immune in handler.c).

    Two-pass check: first determine broad-category default (weapon or magic),
    then override with specific damage-type flag if present.

    Args:
        ch (dict): Victim (mob instance or player dict).
        dam_type (int): DAM_* damage class constant.

    Returns:
        int: One of IS_NORMAL, IS_IMMUNE, IS_RESISTANT, IS_VULNERABLE.
    """
    if dam_type == DAM_NONE:
        return IMMUNE_NONE

    # [not ported] 1stMud reads ch->imm_flags etc. directly; PrimeSUD stores
    # merged flags on mob instances (race defaults OR'd in at create_mobile).
    # Player imm/res/vuln flags will come from equipment affects when ported.
    imm  = ch.get("imm_flags", {})
    res  = ch.get("res_flags", {})
    vuln = ch.get("vuln_flags", {})

    # -- Pass 1: broad category default (cf. 1stMud check_immune first switch)
    if dam_type in (DAM_BASH, DAM_PIERCE, DAM_SLASH):
        broad = "weapon"
    else:
        broad = "magic"

    if imm.get(broad):
        default = IS_IMMUNE
    elif res.get(broad):
        default = IS_RESISTANT
    elif vuln.get(broad):
        default = IS_VULNERABLE
    else:
        default = IS_NORMAL

    # -- Pass 2: specific damage-type flag (cf. 1stMud check_immune second switch)
    flag = DAM_TO_FLAG.get(dam_type)
    if flag is None:
        return default

    immune = IMMUNE_NONE
    if imm.get(flag):
        immune = IS_IMMUNE
    elif res.get(flag) and immune != IS_IMMUNE:
        immune = IS_RESISTANT
    elif vuln.get(flag):
        if immune == IS_IMMUNE:
            immune = IS_RESISTANT
        elif immune == IS_RESISTANT:
            immune = IS_NORMAL
        else:
            immune = IS_VULNERABLE

    if immune == IMMUNE_NONE:
        return default
    return immune


def update_mob_timers():
    """Bulk-decrement wait/daze for NPCs in current room (cf. 1stMud multi_hit NPC path)."""
    rs = world.rooms[world.chars[1]["room"]]
    for mid in rs["mobs"]:
        inst = world.chars[mid]
        inst["wait"] = max(0, inst.get("wait", 0) - PULSE_VIOLENCE)
        inst["daze"] = max(0, inst.get("daze", 0) - PULSE_VIOLENCE)


# -- Defensive checks ----------------------------------------------------------

def check_parry(ch, victim):
    """Check if victim parries ch's strike (cf. 1stMud check_parry in fight.c).

    Args:
        ch (dict): Attacker (player or mob instance).
        victim (dict): Defender (player or mob instance).

    Returns:
        bool: True if the attack was parried.
    """
    if victim["is_npc"]:
        skill = get_skill(victim, GSN_PARRY, is_mob=True)
        skill //= 2
        # Mob has no wield slot -- halve again (cf. 1stMud check_parry: !WEAR_WIELD && IsNPC -> chance/=2)
        skill //= 2
        lv_delta = victim["level"] - ch["level"]
    else:
        if victim["equip"].get("wield") is None:
            return False
        skill    = get_skill(victim, GSN_PARRY)
        skill //= 2
        lv_delta = victim["level"] - ch["level"]

    # 1stMud: if (!can_see(ch, victim)) chance /= 2;
    if not can_see(ch, victim):
        skill //= 2

    chance = skill + lv_delta
    if randint(1, 100) >= chance:
        return False

    act("$N parries your attack.", ch, None, victim, TO_CHAR)
    act("You parry $n's attack.", ch, None, victim, TO_VICT)
    if not victim["is_npc"]:
        check_improve(victim, GSN_PARRY, True, 6)
    return True


def check_shield_block(ch, victim):
    """Check if victim blocks ch's strike with shield (cf. 1stMud check_shield_block in fight.c).

    Args:
        ch (dict): Attacker (player or mob instance).
        victim (dict): Defender (player or mob instance).

    Returns:
        bool: True if the attack was blocked.
    """
    # 1stMud: chance = get_skill(victim, gsn_shield_block) / 5 + 3;
    if victim["is_npc"]:
        chance = get_skill(victim, GSN_SHIELD_BLOCK, is_mob=True) // 5 + 3
    else:
        chance = get_skill(victim, GSN_SHIELD_BLOCK) // 5 + 3

    # 1stMud: if (get_eq_char(victim, WEAR_SHIELD) == NULL) return false;
    if victim["equip"].get("shield") is None:
        return False

    # 1stMud: if (number_percent() >= chance + victim->level - ch->level) return false;
    if randint(1, 100) >= chance + victim["level"] - ch["level"]:
        return False

    act("$N blocks your attack with a shield.", ch, None, victim, TO_CHAR)
    act("You block $n's attack with your shield.", ch, None, victim, TO_VICT)
    if not victim["is_npc"]:
        check_improve(victim, GSN_SHIELD_BLOCK, True, 6)
    return True


def check_dodge(ch, victim):
    """Check if victim dodges ch's strike (cf. 1stMud check_dodge in fight.c).

    Args:
        ch (dict): Attacker (player or mob instance).
        victim (dict): Defender (player or mob instance).

    Returns:
        bool: True if the attack was dodged.
    """
    if victim["is_npc"]:
        skill = get_skill(victim, GSN_DODGE, is_mob=True)
    else:
        skill = get_skill(victim, GSN_DODGE)

    chance = skill // 2

    # 1stMud: if (!can_see(victim, ch)) chance /= 2;
    if not can_see(victim, ch):
        chance //= 2

    if randint(1, 100) >= chance + victim["level"] - ch["level"]:
        return False

    act("$N dodges your attack.", ch, None, victim, TO_CHAR)
    act("You dodge $n's attack.", ch, None, victim, TO_VICT)
    if not victim["is_npc"]:
        check_improve(victim, GSN_DODGE, True, 6)
    return True


# -- Core damage resolution ----------------------------------------------------

def update_pos(ch):
    """Set ch's position from current HP
    (cf. 1stMud update_pos in fight.c).
    [Verified: 23/06/2026]

    Args:
        ch (dict): Character state dict.
    """
    hp = ch["hit"]

    if hp > 0:
        if POS_ORDER[ch["pos"]] <= POS_ORDER["stunned"]:
            ch["pos"] = "standing"
        return

    if ch["is_npc"] and hp < 1:
        ch["pos"] = "dead"
        return

    if hp <= -11:
        ch["pos"] = "dead"
    elif hp <= -6:
        ch["pos"] = "mortal"
    elif hp <= -3:
        ch["pos"] = "incap"
    else:
        ch["pos"] = "stunned"


def _randomize_damage(dam, roll):
    """Apply +/-50% variance to damage (cf. 1stMud randomize_damage in fight.c).

    Args:
        dam (int): Pre-variance damage.
        roll (int): Random 1-100 value.

    Returns:
        int: Adjusted damage.
    """
    return dam * (roll + 50) // 100


def is_safe(ch, victim):
    """Check if ch is prevented from attacking victim (cf. 1stMud is_safe in fight.c).

    Returns True (and prints a message) if the attack should be blocked.
    Unlike is_safe_spell, this prints feedback explaining why.

    Args:
        ch (dict): Attacker (player or mob instance).
        victim (dict): Potential target.

    Returns:
        bool: True means target is protected -- abort the attack.
    """
    if victim.get("fighting") == ch.get("id") or victim is ch:
        return False

    # [PRIMESUD] immortal check skipped -- single-player, no immortals

    if victim["is_npc"]:
        # [PRIMESUD] ROOM_SAFE not ported -- room_flags not on rooms yet
        # if room has "safe" flag: chprintln(ch, "Not in this room."); return True

        if MOB_DEFS[victim["tpl"]].get("shop"):
            chprintln(ch, "The shopkeeper wouldn't like that.")
            return True

        act_f = victim.get("act_flags", {})
        if (act_f.get("train") or act_f.get("practice")
                or act_f.get("healer") or act_f.get("changer")):
            # 1stmud: "I don't think $g would approve." -- $g = deity, not ported
            chprintln(ch, "I don't think the gods would approve.")
            return True

        if not ch["is_npc"]:
            # [PRIMESUD] ACT_PET not ported -- no pet flag on mobs yet
            # if act_f.get("pet"):
            #     act("But $N looks so cute and cuddly...", ch, arg2=victim)
            #     return True

            if (victim.get("affected_by", {}).get("charm")
                    and ch.get("id") != victim.get("master")):
                chprintln(ch, "You don't own that monster.")
                return True

            # [PRIMESUD] quest deliver/findmob target check not ported
    # [PRIMESUD] PvP checks skipped -- single-player
    return False


def is_safe_spell(ch, victim, area):
    """Silent safety check for spell targeting (cf. 1stMud is_safe_spell in fight.c).

    Returns True if victim should NOT be hit. Unlike is_safe, prints no
    messages.

    Args:
        ch (dict): Caster.
        victim (dict): Potential target.
        area (bool): True for area-effect spells.

    Returns:
        bool: True means target is protected.
    """
    if victim is ch and area:
        return True
    if victim.get("fighting") == ch.get("id") or victim is ch:
        return False
    if victim["is_npc"]:
        # [PRIMESUD] ROOM_SAFE not ported -- room_flags not on rooms yet
        if MOB_DEFS[victim["tpl"]].get("shop"):
            return True
        act = victim.get("act_flags", {})
        if (act.get("train") or act.get("practice")
                or act.get("healer") or act.get("changer")):
            return True
        if not ch["is_npc"]:
            # [PRIMESUD] ACT_PET not ported
            if (victim.get("affected_by", {}).get("charm")
                    and (area or ch.get("id") != victim.get("master"))):
                return True
            # 1stmud: victim fighting someone not in ch's group -> safe
            # [PRIMESUD] is_same_group not ported
        else:
            # NPC caster, area: skip if victim not grouped with ch's target
            # [PRIMESUD] is_same_group not ported
            pass
    # [PRIMESUD] PvP checks skipped -- single-player
    return False


def dam_message(ch, victim, dam, dt, immune, attack_noun=None):
    """Print damage message from ch's attack on victim (cf. 1stMud dam_message in fight.c).

    Single-player: only the player sees messages, as attacker (ch=player) or victim (ch=mob).

    # [PRIMESUD] attack_noun passed explicitly; 1stMud resolves it internally via
    # attack_table[dt - TYPE_HIT].noun, but PrimeSUD uses string-keyed dam_type
    # (from area files) rather than integer offsets, so dt alone is insufficient.

    Args:
        ch (dict): Attacker (player or mob instance).
        victim (dict): Defender (player or mob instance).
        dam (int): Final damage dealt (0 = miss).
        dt (int): Damage type; dt >= TYPE_HIT means physical attack.
        immune (bool): True if victim was fully immune (dam forced to 0 by immunity).
        attack_noun (str or None): Attack display noun (e.g. "slash", "kick"); None = unarmed.
    """
    vs, vp = _damage_verb(dam)
    punct  = _damage_punct(dam)

    # 1stMud dam_message: TO_CHAR goes to attacker, TO_VICT goes to defender
    # (cf. fight.c:2610-2693). Routing replaces is_npc branching.
    if immune:
        if attack_noun:
            act("{GYour %s doesn't affect {G$N.{x" % attack_noun, ch, None, victim, TO_CHAR)
            act("{R$n's %s is powerless against you.{x" % attack_noun, ch, None, victim, TO_VICT)
        else:
            act("{GYour attack doesn't affect {G$N.{x", ch, None, victim, TO_CHAR)
            act("{RYour body is unaffected by $n's attack.{x", ch, None, victim, TO_VICT)
    elif dam == 0:
        if attack_noun:
            act("{GYour %s misses {G$N.{x" % attack_noun, ch, None, victim, TO_CHAR)
            act("{R$n's %s misses {Ryou.{x" % attack_noun, ch, None, victim, TO_VICT)
        else:
            act("{GYou miss {G$N.{x", ch, None, victim, TO_CHAR)
            act("{R$n misses {Ryou.{x", ch, None, victim, TO_VICT)
    elif attack_noun:
        act("{GYour %s %s {G$N%s {W[{R%d{W]{x" % (attack_noun, vp, punct, dam), ch, None, victim, TO_CHAR)
        act("{R$n's %s %s {Ryou%s {W[{R%d{W]{x" % (attack_noun, vp, punct, dam), ch, None, victim, TO_VICT)
    else:
        act("{GYou %s {G$N%s {W[{R%d{W]{x" % (vs, punct, dam), ch, None, victim, TO_CHAR)
        act("{R$n %s {Ryou%s {W[{R%d{W]{x" % (vp, punct, dam), ch, None, victim, TO_VICT)


def damage(ch, victim, dam, dt, dam_type, show, attack_noun=None):
    """Apply damage to victim from ch; handle combat state, immunity, and death
    (cf. 1stMud damage in fight.c).

    dt >= TYPE_HIT = physical attack (dodge/parry checks apply).
    dt < TYPE_HIT  = skill/spell (no defensive checks).

    Args:
        ch (dict): Attacker (player or mob instance).
        victim (dict): Defender (player or mob instance).
        dam (int): Raw damage before soft-caps and modifiers.
        dt (int): Damage type ID; TYPE_HIT for weapon, skill sn for spells/skills.
        dam_type (int): DAM_* class for immunity checks.
        show (bool): Print dam_message if True (position messages always shown).
        attack_noun (str or None): [PRIMESUD] Attack display noun for dam_message.

    Returns:
        bool: True if damage applied (including kill); False on miss/dodge/parry/immune/dead.
    """
    if victim.get("pos") == "dead":
        return False

    # 1stmud: Anti-cheat check here
    if dam > 10000 and dt >= TYPE_HIT:
        dam = 10000

    # Damage soft caps
    if dam > 35:
        dam = (dam - 35) // 2 + 35
    if dam > 80:
        dam = (dam - 80) // 2 + 80

    # Global damage multipliers
    # [PRIMESUD] skip pcdam/mobdam multipliers (mud_info not ported)

    if victim is not ch:
        if is_safe(ch, victim):
            return False
        # [PRIMESUD] check_killer not ported -- pvp

        if POS_ORDER[victim["pos"]] > POS_ORDER["stunned"]:
            if victim["fighting"] is None:
                set_fighting(victim, ch)
                # 1stMud: if (IsNPC(victim) && HasTriggerMob(victim,TRIG_KILL)) p_percent_trigger(...)
                # [PRIMESUD] skip TRIG_KILL (not ported) - mobprogs
            # 1stMud: if (victim->timer <= 4) victim->position = POS_FIGHTING;
            # [PRIMESUD] timer is connection idle counter -- always 0 in single-player, so always true
            victim["pos"] = "fighting"

        # 1stMud: if (victim->position > POS_STUNNED) {
        #             if (ch->fighting == NULL) set_fighting(ch, victim); }
        if POS_ORDER[victim["pos"]] > POS_ORDER["stunned"]:
            if ch["fighting"] is None:
                set_fighting(ch, victim)

        # 1stMud: if (victim->master == ch) stop_follower(victim);
        # [PRIMESUD] skip stop_follower (no charm/follower system ported)

    # 1stMud: if (IsAffected(ch, AFF_INVISIBLE)) { affect_strip(ch, gsn_invis); ... act("$n fades in"); }
    # [PRIMESUD] skip invis strip (not ported)

    # 1stMud: if (dam > 1 && !IsNPC(victim) && victim->pcdata->condition[COND_DRUNK] > 10)
    #             dam = 9 * dam / 10;
    # [PRIMESUD] skip drunk damage reduction (condition system not ported)

    # 1stMud: if (dam > 1 && IsAffected(victim, AFF_SANCTUARY)) dam /= 2;
    if dam > 1 and victim.get("affected_by", {}).get("sanctuary"):
        dam //= 2

    # 1stMud: if (dam > 1 && ((IsAffected(victim, AFF_PROTECT_EVIL) && IsEvil(ch)) || ...))
    #             dam -= dam / 4;
    # [PRIMESUD] skip protect_evil/good (affects not ported)

    # 1stMud: if (mud_info.bonus.status == BONUS_DAM) dam *= mud_info.bonus.mod;
    # [PRIMESUD] skip bonus damage event (not ported)

    # 1stMud: if (dt >= TYPE_HIT && ch != victim) { check_dodge; check_parry; check_shield_block; ... }
    immune = False
    if dt >= TYPE_HIT and ch is not victim:
        # 1stMud: if (check_dodge(ch, victim)) return false;
        if check_dodge(ch, victim):
            return False
        # 1stMud: if (check_parry(ch, victim)) return false;
        if check_parry(ch, victim):
            return False
        # 1stMud: if (check_shield_block(ch, victim)) return false;
        if check_shield_block(ch, victim):
            return False
        # 1stMud: if (IsAffected(victim,AFF_FORCE_SHIELD) && check_force_shield(...)) return false;
        # 1stMud: if (IsAffected(victim,AFF_STATIC_SHIELD) && check_static_shield(...)) return false;
        # [PRIMESUD] skip force/static shields (not ported)

    # 1stMud: if (IsAffected(victim, AFF_FLAME_SHIELD) && dam_type <= 3) check_flame_shield(ch, victim);
    # [PRIMESUD] skip flame_shield (not ported)

    # 1stMud: switch (check_immune(victim, dam_type)) {
    #             case IS_IMMUNE:    immune=true; dam=0; break;
    #             case IS_RESISTANT: dam -= dam/3; break;
    #             case IS_VULNERABLE: dam += dam/2; break; }
    imm_result = check_immune(victim, dam_type)
    if imm_result == IS_IMMUNE:
        immune = True
        dam = 0
    elif imm_result == IS_RESISTANT:
        dam -= dam // 3
    elif imm_result == IS_VULNERABLE:
        dam += dam // 2

    # 1stMud: randomize_damage(ch, dam, dice(1,100));
    # [PRIMESUD] 1stMud discards return value (bug); we apply it. See FIXES.md.
    dam = _randomize_damage(dam, randint(1, 100))

    # 1stMud: if (show) dam_message(ch, victim, dam, dt, immune);
    if show:
        # [PRIMESUD] Auto-resolve attack_noun from skill table for spells.
        # 1stMud does this inside dam_message via skill_table[dt].noun_damage,
        # but we pass it explicitly because PrimeSUD uses string-keyed dam_type.
        if attack_noun is None and dt < TYPE_HIT and dt in SKILLS:
            sk = SKILLS[dt]
            attack_noun = sk.get("noun_damage") or sk["name"]
        dam_message(ch, victim, dam, dt, immune, attack_noun)

    # 1stMud: if (dam == 0) return false;
    if dam == 0:
        return False

    # 1stMud: victim->hit -= dam;
    victim["hit"] -= dam

    # 1stMud: if (!IsNPC(victim) && victim->level >= LEVEL_IMMORTAL && victim->hit < 1)
    #             victim->hit = 1;
    # [PRIMESUD] skip immortal HP floor (no immortal players)

    # 1stMud: update_pos(victim);
    update_pos(victim)

    # 1stMud: switch (victim->position) { case POS_MORTAL: ... case POS_DEAD: ... default: ... }
    # pos captured before stop_fighting (called below) can reset it to "standing".
    pos = victim.get("pos", "standing")

    if pos == "mortal":
        act("$n is mortally wounded, and will die soon, if not aided.", victim, type=TO_ROOM)
        if not victim["is_npc"]:
            tprint("You are mortally wounded, and will die soon, if not aided.")
    elif pos == "incap":
        act("$n is incapacitated and will slowly die, if not aided.", victim, type=TO_ROOM)
        if not victim["is_npc"]:
            tprint("You are incapacitated and will slowly die, if not aided.")
    elif pos == "stunned":
        act("$n is stunned, but will probably recover.", victim, type=TO_ROOM)
        if not victim["is_npc"]:
            tprint("You are stunned, but will probably recover.")
    elif pos == "dead":
        act("$n is DEAD!!", victim, type=TO_ROOM)
        # [PRIMESUD] player death message printed by game loop (primesud.py) to avoid duplicate
    else:
        # 1stMud: default:
        #   if (dam > victim->max_hit/4) chprintln(victim, "That really did HURT!")
        #   if (victim->hit < victim->max_hit/4) chprintln(victim, "You sure are BLEEDING!")
        if not victim["is_npc"]:
            max_hit = victim.get("max_hit", 1)
            if dam > max_hit // 4:
                tprint("That really did HURT!")
            if victim["hit"] < max_hit // 4:
                tprint("You sure are BLEEDING!")

    # 1stMud: if (!IsAwake(victim)) stop_fighting(victim, false);
    if not is_awake(victim):
        stop_fighting(victim, both=False)

    # 1stMud: if (victim->position == POS_DEAD) { ... raw_kill(victim, ch) ... }
    if pos == "dead":
        # 1stMud: if (IS_IN_ARENA...) check_arena; if (InWar...) check_war;
        # [PRIMESUD] skip arena and war (not ported)

        # 1stMud: group_gain(ch, victim)
        group_gain(ch, victim)

        # 1stMud: if (!IsNPC(victim)) { logf(...); if (!IsQuester...) gain_exp(loss); }
        # [PRIMESUD] skip player death exp loss (not ported)

        # 1stMud: new_wiznet / announce
        # [PRIMESUD] skip wiznet/announce (not ported)

        # 1stMud: if (IsNPC(victim) && HasTriggerMob(victim, TRIG_DEATH)) p_percent_trigger(...)
        # [PRIMESUD] skip TRIG_DEATH (not ported)

        # 1stMud: update_death(victim, ch)
        # [PRIMESUD] skip update_death (not ported)

        # 1stMud: raw_kill(victim, ch)
        corpse = raw_kill(victim, ch)

        if victim.get("is_npc"):
            _advance_target(ch, world.chars, world.rooms)

        # 1stMud: if (ch != victim && !IsNPC(ch) && ...) outlaw flag removal
        # [PRIMESUD] skip outlaw flag removal (not ported)

        # 1stMud: if (!IsNPC(ch) && (corpse = get_obj_list...) ... autoloot/autogold/autosac
        # [PRIMESUD] use corpse returned by raw_kill instead of searching by
        # name -- 1stMud searches and gets oldest corpse when multiples exist.
        if not ch.get("is_npc"):
            flags = ch.get("flags", PLR_DEFAULTS)
            if (corpse is not None and isinstance(corpse, dict)
                    and ITEM_DEFS[obj_vnum(corpse)].get("type") == "npc_corpse"):
                contents = corpse.get("contents", [])

                # 1stMud: if (PLR_AUTOLOOT && corpse->content_first) do_get("all corpse")
                if flags & PLR_AUTOLOOT and contents:
                    for cobj in list(contents):
                        ctpl = ITEM_DEFS[obj_vnum(cobj)]
                        corpse["contents"].remove(cobj)
                        tprint("You get {}.".format(cobj.get("short_descr") or ctpl["short_descr"]))
                        if not apply_money_pickup(ch, cobj, ctpl):
                            ch["inv"].append(cobj)

                # 1stMud: if (PLR_AUTOGOLD && content_first && !PLR_AUTOLOOT) get gold only
                if (flags & PLR_AUTOGOLD and corpse.get("contents")
                        and not (flags & PLR_AUTOLOOT)):
                    for cobj in list(corpse["contents"]):
                        ctpl = ITEM_DEFS[obj_vnum(cobj)]
                        if ctpl.get("type") == "money":
                            corpse["contents"].remove(cobj)
                            tprint("You get {}.".format(cobj.get("short_descr") or ctpl["short_descr"]))
                            apply_money_pickup(ch, cobj, ctpl)

                # 1stMud: if (PLR_AUTOSAC) { if (autoloot && still has contents) skip; else sacrifice }
                if flags & PLR_AUTOSAC:
                    if flags & PLR_AUTOLOOT and corpse.get("contents"):
                        pass
                    else:
                        silver = max(1, corpse.get("level", 0) * 3)
                        if silver == 1:
                            tprint("Your deity gives you one silver coin for your sacrifice.")
                        else:
                            tprint("Your deity gives you " + str(silver) + " silver coins for your sacrifice.")
                        ch["silver"] = ch.get("silver", 0) + silver
                        short = corpse.get("short_descr", "a corpse")
                        tprint("You sacrifice " + short + " to your deity.")
                        world.rooms[ch["room"]]["items"].remove(corpse)

        return True

    # 1stMud: if (victim == ch) return true;
    if victim is ch:
        return True

    # 1stMud: if (!IsNPC(victim) && victim->desc == NULL) { ... perform_recall ... }
    # [PRIMESUD] skip linkdead recall (no multiplayer)

    # 1stMud: if (IsNPC(victim) && dam > 0 && victim->wait < PULSE_VIOLENCE/2) {
    #             if (ACT_WIMPY && number_bits(2)==0 && hit < max_hit/5) do_flee;
    #             elif (AFF_CHARM && master && master->in_room != victim->in_room) do_flee; }
    if victim["is_npc"] and dam > 0 and victim.get("wait", 0) < PULSE_VIOLENCE // 2:
        act_flags = victim.get("act_flags", {})
        if (act_flags.get("wimpy") and randint(0, 3) == 0
                and victim["hit"] < victim.get("max_hit", 1) // 5):
            do_flee(victim, [])
        # [PRIMESUD] charmed mob flee requires master tracking (not yet ported)

    # 1stMud: player wimpy auto-flee
    if (not victim.get("is_npc") and victim["hit"] > 0
            and victim["hit"] <= victim.get("wimpy", 0)
            and victim.get("wait", 0) < PULSE_VIOLENCE // 2):
        do_flee(victim, [])

    # 1stMud: tail_chain();
    # [PRIMESUD] skip tail_chain (event queue not ported)

    return True


# -- Core attack: one_hit ------------------------------------------------------

def one_hit(ch, victim, dt=TYPE_UNDEFINED, bonus_damroll=0, secondary=False):
    """One attack from ch against victim (cf. 1stMud one_hit in fight.c).

    Args:
        ch (dict): Attacker (player or mob instance).
        victim (dict): Defender (player or mob instance).
        dt (int): Damage type; TYPE_UNDEFINED = resolve from weapon/mob,
            skill GSN (e.g. GSN_BACKSTAB) = skill-driven attack.
        bonus_damroll (int): Extra damage roll bonus (e.g. from skills).
        secondary (bool): True = secondary weapon (cf. 1stMud bool secondary).

    Returns:
        bool: True if damage was applied.
    """
    # Weapon / skill (cf. 1stMud one_hit: skill = 20 + get_weapon_skill, fight.c)
    slot = "secondary" if secondary else "wield"
    if secondary and ch["equip"].get(slot) is None:
        return False
    sk_vnum, wtpl = _get_weapon_sn(ch, slot)
    skill = 20 + _get_weapon_skill(ch, sk_vnum)

    # THAC0 -- mob attackers add affect-based hitroll bonus
    extra_hr = ch.get("affects", {}).get("m_hitroll", 0) if ch["is_npc"] else 0
    thac0 = get_thac0(ch)
    thac0 -= (get_hitroll(ch) + extra_hr) * skill // 100
    thac0 += 5 * (100 - skill) // 100

    # Backstab THAC0 bonus (cf. 1stMud one_hit fight.c:654-655)
    if dt == GSN_BACKSTAB:
        thac0 -= 10 * (100 - get_skill(ch, GSN_BACKSTAB, ch["is_npc"]))

    # Attack noun and damage class
    if ch["is_npc"]:
        ch_tpl   = MOB_DEFS[ch["tpl"]]
        dam_type = ch_tpl.get("dam_type", "none")
    else:
        dam_type = wtpl["dam_type"] if wtpl is not None else "none"
        ch_tpl   = None
    attack_noun, dam_class = _attack_info(dam_type)
    # Skill-driven attack: override noun from skill table (cf. 1stMud dt < TYPE_HIT branch)
    if dt != TYPE_UNDEFINED and dt < TYPE_HIT:
        noun = SKILLS[dt]["noun_damage"]
    else:
        # None = unarmed (no noun in dam_message); mirrors 1stMud !armed display branch
        noun = None if dam_type == "none" else attack_noun
    victim_ac = get_armor(victim, _ac_type_for_damage_class(dam_class)) // 10
    if victim_ac < -15:  # soft cap (cf. 1stMud one_hit fight.c)
        victim_ac = -((-victim_ac - 15) // 5) - 15

    # 1stMud: if (number_range(0,19) < thac0 - victim_ac)
    #             return damage(ch, victim, 0, dt, DAM_NONE, true);
    # Resolve dt for damage() calls: skill GSN stays as-is, otherwise TYPE_HIT
    effective_dt = dt if (dt != TYPE_UNDEFINED and dt < TYPE_HIT) else TYPE_HIT
    roll = randint(0, 19)
    if roll == 0 or (roll != 19 and roll < thac0 - victim_ac):
        damage(ch, victim, 0, effective_dt, DAM_NONE, show=True, attack_noun=noun)
        return False

    # Damage calculation (cf. 1stMud one_hit)
    if ch["is_npc"]:
        num, size, _ = ch_tpl["damage"]
        dam = _dice(num, size)
    elif wtpl is not None:
        num, size, bonus = wtpl.get("dice", (1, 4, 0))
        dam = (_dice(num, size) + bonus) * skill // 100
    else:
        # Unarmed formula (cf. 1stMud)
        lo = max(1, 1 + 4 * skill // 100)
        hi = max(lo, 2 * ch["level"] * skill // 300)
        dam = randint(lo, hi)

    # Position bonus: sleeping victim takes double, non-fighting victim takes 1.5x (cf. 1stMud one_hit in fight.c)
    vpos = POS_ORDER[victim["pos"]]
    if not is_awake(victim):
        dam *= 2
    elif vpos < POS_ORDER["fighting"]:
        dam = dam * 3 // 2

    # Backstab damage multiplier (cf. 1stMud one_hit fight.c:762-768)
    if dt == GSN_BACKSTAB and wtpl is not None:
        if wtpl.get("weapon_type") != "dagger":
            dam *= 2 + ch["level"] // 10
        else:
            dam *= 2 + ch["level"] // 8

    dam += (get_damroll(ch) + bonus_damroll) * min(100, skill) // 100
    dam = max(1, dam)

    # 1stMud: return damage(ch, victim, dam, dt, dam_type, true);
    # Soft caps, immunity, dodge/parry all handled inside damage().
    hit = damage(ch, victim, dam, effective_dt, dam_class, show=True, attack_noun=noun)

    if hit and not ch["is_npc"] and sk_vnum != -1:
        check_improve(ch, sk_vnum, True, 5)

    return hit


def do_kick(ch, args):
    """Kick for player or mob (cf. 1stMud do_kick in fight.c).

    Args:
        ch (dict): Acting character (player or mob instance).
        args (list): Command arguments (unused).
    """
    if ch["is_npc"]:
        target_id = ch["fighting"]
        if target_id is None:
            return None
        target = world.chars[target_id]
    else:
        if GSN_KICK not in ch["learned"]:
            tprint("You better leave the martial arts to fighters.")
            return None
        if ch["fighting"] is None:
            tprint("You aren't fighting anyone.")
            return None
        target_id = ch["fighting"]
        target    = world.chars[target_id]

    if ch["is_npc"]:
        skill_pct = ch["level"] if ch["level"] <= 2 else ch["level"] // 2 + ch["level"] // 3
    else:
        skill_pct = ch["learned"].get(GSN_KICK, 0)
    WaitState(ch, SKILLS[GSN_KICK]["beats"])

    if skill_pct > randint(1, 100):
        dam = randint(1, max(1, ch["level"]))
        # 1stMud: damage(ch, victim, dam, gsn_kick, DAM_BASH, true)
        damage(ch, target, dam, GSN_KICK, DAM_BASH, show=True, attack_noun="kick")
        if not ch["is_npc"]:
            check_improve(ch, GSN_KICK, True, 1)
    else:
        # 1stMud: damage(ch, victim, 0, gsn_kick, DAM_BASH, true)
        damage(ch, target, 0, GSN_KICK, DAM_BASH, show=True, attack_noun="kick")
        if not ch["is_npc"]:
            check_improve(ch, GSN_KICK, False, 1)
    return None


def do_backstab(ch, args):
    """Backstab a target from behind (cf. 1stMud do_backstab in fight.c).

    Args:
        ch (dict): Acting character (player or mob instance).
        args (list): Command arguments -- target keyword.
    """
    # [PRIMESUD] explicit gate; 1stMud lets it through but get_skill returns 0 -> guaranteed miss + lag
    if not ch["is_npc"] and GSN_BACKSTAB not in ch["learned"]:
        tprint("You don't know how to backstab.")
        return None

    if not args:
        tprint("Backstab whom?")
        return None

    if ch["fighting"] is not None:
        tprint("You're facing the wrong end.")
        return None

    rs = world.rooms[ch["room"]]
    target_id = get_char_room(" ".join(args), rs["mobs"], world.chars)
    if target_id is None:
        tprint("They aren't here.")
        return None

    victim = world.chars[target_id]
    if victim is ch:
        tprint("How can you sneak up on yourself?")
        return None

    if is_safe(ch, victim):
        return None
    # [PRIMESUD] kill-stealing check not ported (single-player)

    if ch["equip"].get("wield") is None:
        tprint("You need to wield a weapon to backstab.")
        return None

    if victim["hit"] < victim["max_hit"] // 3:
        act("$N is hurt and suspicious ... you can't sneak up.", ch, None, victim, TO_CHAR)
        return None

    # [PRIMESUD] check_killer not ported
    WaitState(ch, SKILLS[GSN_BACKSTAB]["beats"])
    skill_pct = get_skill(ch, GSN_BACKSTAB, ch["is_npc"])
    if randint(1, 100) <= skill_pct or (skill_pct >= 2 and not is_awake(victim)):
        check_improve(ch, GSN_BACKSTAB, True, 1)
        multi_hit(ch, victim, dt=GSN_BACKSTAB)
    else:
        check_improve(ch, GSN_BACKSTAB, False, 1)
        damage(ch, victim, 0, GSN_BACKSTAB, DAM_NONE, show=True, attack_noun="backstab")
    return None


def do_kill(player, args):
    """Initiate melee combat with a target (cf. 1stMud do_kill in fight.c).

    Args:
        player (dict): Player state dict.
        args (list): Target keyword; [PRIMESUD] picker shown if omitted.
    """
    rs = world.rooms[player["room"]]
    live = rs["mobs"]
    if args:
        mob_id = get_char_room(" ".join(args), live, world.chars)
        if mob_id is None:
            tprint("They aren't here.")
            return
    elif not live:
        tprint("Kill whom?")
        return
    else:
        # [PRIMESUD] picker menu when no args (1stMud prints "Kill whom?" and stops)
        names = [MOB_DEFS[world.chars[i]["tpl"]]["short_descr"] for i in live]
        idx = pick_from("Kill whom?", names)
        if idx < 0:
            return
        mob_id = live[idx]

    victim = world.chars[mob_id]

    # 1stMud: if (victim == ch) { "You hit yourself. Ouch!"; multi_hit(ch,ch,...); return; }
    # [PRIMESUD] player can't target self (mob_id lookup is mob-only)

    if is_safe(player, victim):
        return
    # [PRIMESUD] kill-stealing check not ported (single-player)
    # [PRIMESUD] charm master check not ported

    if player.get("pos") == "fighting":
        tprint("You do the best you can!")
        return

    WaitState(player, PULSE_VIOLENCE)
    # [PRIMESUD] check_killer not ported
    multi_hit(player, victim)
    if not args:
        return "kill " + MOB_DEFS[victim["tpl"]].get("keywords", "").split()[0]


def mob_hit(ch, victim, dt=TYPE_UNDEFINED):
    """Full attack sequence for one mob per combat round (cf. 1stMud mob_hit in fight.c).

    Args:
        ch (dict): Attacking mob instance dict.
        victim (dict): Player state dict.
        dt (int): Damage type passed from multi_hit (e.g. GSN_BACKSTAB).
    """
    one_hit(ch, victim, dt=dt)
    if victim.get("pos") == "dead":
        return

    # [PRIMESUD] haste/OFF_FAST extra hit not yet ported

    # Backstab = single hit only (cf. 1stMud mob_hit fight.c:475)
    if dt == GSN_BACKSTAB:
        return

    # Second and third attacks (cf. 1stMud get_skill NPC branch in handler.c + multi_hit in fight.c)
    # NPC get_skill: level>2 -> level//2 + level//3, else -> level; chance = skill//2; fires if roll < chance
    lvl = ch["level"]
    npc_skill = (lvl // 2 + lvl // 3) if lvl > 2 else lvl
    if randint(1, 100) < npc_skill // 2:
        one_hit(ch, victim)
        if victim.get("pos") == "dead":
            return

    if randint(1, 100) < npc_skill // 4:
        one_hit(ch, victim)
        if victim.get("pos") == "dead":
            return

    # [PRIMESUD] OFF_BACKSTAB mob special not yet ported

    # 1stMud: if (ch->wait > 0) return; -- blocks mob specials
    if ch.get("wait", 0) > 0:
        return

    # Off-flag specials (cf. 1stMud mob_hit random switch)
    if ch["off_flags"].get("kick") and randint(0, 8) == 3:
        do_kick(ch, [])


# -- Special unarmed moves [PRIMESUD] (cf. 1stMud special_move for inspiration) -

_SPECIAL_MOVES = [
    (
        "{RYou pull your hands into your waist then snap them into %s's stomach.{x",
        "{R%s doubles over in agony, and falls to the ground gasping for breath.{x",
    ),
    (
        "{RYou spin in a low circle, catching %s behind its ankle.{x",
        "{R%s crashes to the ground, stunned.{x",
    ),
    (
        "{RYou roll between %s's legs and flip to your feet.{x",
        "{RYou spin around and smash your elbow into the back of %s's head.{x",
        "{R%s falls to the ground, stunned.{x",
    ),
    (
        "{RYou somersault over %s's head and land lightly on your toes.{x",
        "{RYou roll back onto your shoulders and kick both feet into %s's back.{x",
        "{R%s falls to the ground, stunned.{x",
        "{RYou flip back up to your feet.{x",
    ),
    (
        "{RYou grab %s by the waist and hoist it above your head.{x",
        "{R%s crashes to the ground, stunned.{x",
    ),
    (
        "{RYou grab %s by the head and slam its face into your knee.{x",
        "{R%s crashes to the ground, stunned.{x",
        "{RYou flip back up to your feet.{x",
    ),
    (
        "{RYou duck under %s's attack and pound your fist into its stomach.{x",
        "{R%s doubles over in agony.{x",
    ),
]


def _try_special_move(player, target_inst):
    """Unarmed-only bonus attack with flavour (cf. 1stMud special_move).

    Args:
        player (dict): Player state dict.
        target_inst (dict): Target mob instance dict.

    Returns:
        int: Damage dealt (0 if not triggered or player has a weapon).
    """
    if player["equip"].get("wield") is not None:
        return 0
    chance = 20 + (get_curr_stat(player, "dex") - 10) * 3
    if randint(1, 100) > chance:
        return 0
    tpl  = MOB_DEFS[target_inst["tpl"]]
    name = tpl["short_descr"]
    move = _SPECIAL_MOVES[randint(0, len(_SPECIAL_MOVES) - 1)]
    for line in move[:-1]:
        tprint(line % name if "%s" in line else line)
    # Damage: same unarmed formula as one_hit (cf. 1stMud: skill = 20 + get_weapon_skill)
    skill = 20 + _get_weapon_skill(player, GSN_HAND_TO_HAND)
    lo  = max(1, 1 + 4 * skill // 100)
    hi  = max(lo, 2 * player["level"] * skill // 300)
    dam = max(1, randint(lo, hi))
    last = move[-1] % name if "%s" in move[-1] else move[-1]
    tprint("%s {W[{R%d{W]{x" % (last, dam))
    check_improve(player, GSN_HAND_TO_HAND, True, 5)
    # show=False: flavor text above already shows dam count; damage() still handles death/state
    damage(player, target_inst, dam, GSN_HAND_TO_HAND, DAM_BASH, show=False)
    return dam


# -- Multi-hit (player's full attack sequence) ---------------------------------

def multi_hit(ch, victim, dt=TYPE_UNDEFINED):
    """Full attack sequence for one combat round (cf. 1stMud multi_hit in fight.c).

    Args:
        ch (dict): Attacker (player or mob instance).
        victim (dict): Defender (player or mob instance).
        dt (int): Damage type; TYPE_UNDEFINED for normal round,
            skill GSN (e.g. GSN_BACKSTAB) for skill-initiated attacks.

    Returns:
        bool: True if the victim was killed this round.
    """
    if ch["is_npc"]:
        mob_hit(ch, victim, dt=dt)
        return victim.get("pos") == "dead"

    # Primary
    one_hit(ch, victim, dt=dt)
    if victim.get("pos") == "dead":
        return True

    # Offhand weapon (cf. 1stMud multi_hit WEAR_SECONDARY in fight.c)
    # Specifically, ensures that secondary item is a weapon before allowing hit
    secondary_obj = ch["equip"].get("secondary")
    if secondary_obj is not None and ITEM_DEFS[secondary_obj["vnum"]].get("type") == "weapon":
        one_hit(ch, victim, dt=dt, secondary=True)
        if victim.get("pos") == "dead":
            return True

    # [PRIMESUD] haste extra hit not yet ported (cf. 1stMud fight.c:387-388)

    # Backstab = single hit only (cf. 1stMud multi_hit fight.c:390)
    if dt == GSN_BACKSTAB:
        return False

    # Second attack: skill/2 chance; third: skill/4 chance (cf. 1stMud multi_hit in fight.c)
    if randint(1, 100) < ch["learned"].get(GSN_SECOND_ATTACK, 0) // 2:
        one_hit(ch, victim)
        check_improve(ch, GSN_SECOND_ATTACK, True, 5)
        if victim.get("pos") == "dead":
            return True
    if randint(1, 100) < ch["learned"].get(GSN_THIRD_ATTACK, 0) // 4:
        one_hit(ch, victim)
        check_improve(ch, GSN_THIRD_ATTACK, True, 6)
        if victim.get("pos") == "dead":
            return True

    # 1stMud: if (ch->wait > 0) return; -- blocks specials for players too
    if ch.get("wait", 0) > 0:
        return False

    # [PRIMESUD] Unarmed special move -- no 1stMud equivalent
    if ch["equip"].get("wield") is None:
        _try_special_move(ch, victim)
        if victim.get("pos") == "dead":
            return True

    return False


# -- Combat state --------------------------------------------------------------

def set_fighting(ch, victim):
    """Engage ch in combat against victim (cf. 1stMud set_fighting in fight.c)."""
    ch["fighting"] = victim["id"]
    ch["pos"] = "fighting"


def stop_fighting(ch, both=False):
    """
    Given character stops fighting its target.
    Optionally make all other characters stop fighting it.
    (cf. 1stMud stop_fighting in fight.c).

    Args:
        ch (dict): Character that stops fighting its target.
        both (bool): If true, all other characters stop fighting `ch`.
    """
    for char in world.chars.values():
        if char == ch or (both and char["fighting"] == ch["id"]):
            char["fighting"] = None
            # [PRIMESUD] original .are files allow for mobs to have default positions
            # specified, but we haven't ported this yet.
            char["pos"] = "standing"
            update_pos(char)
            # TODO: Stance is reset here.


def _advance_target(player, mob_instances, room_state):
    """Switch player's combat target to the next aggro mob in the room. [PRIMESUD]

    Args:
        player (dict): Player state dict.
        mob_instances (dict): Mob instance mapping mob ID -> mob instance dict.
        room_state (dict): Room state mapping room ID -> room state dict.
    """
    rs      = room_state[player["room"]]
    next_id = None
    for mid in rs["mobs"]:
        if mob_instances[mid]["fighting"] is not None:
            next_id = mid
            break
    if next_id is not None:
        player["fighting"] = next_id
    else:
        stop_fighting(player, both=False)


# -- Death / Victory -----------------------------------------------------------

# [PRIMESUD] uniform distribution over all variants; 1stMud uses number_bits(4)
# with per-mob part flags, giving ~50% chance of the fallback "death cry" line.
_DEATH_CRIES = [
    "$n hits the ground ... DEAD.",
    "$n splatters blood on your armor.",
    "$n spills $s guts all over the floor.",
    "$n's heart is torn from $s chest.",
    "$n's severed head plops on the ground.",
    "$n's arm is sliced from $s dead body.",
    "$n's leg is sliced from $s dead body.",
    "$n's head is shattered, and $s brains splash all over you.",
    "You hear $n's death cry.",
]


def _death_cry(ch):
    """Random death flavour message (cf. 1stMud death_cry in fight.c).

    Args:
        ch (dict): Dying character (player or mob instance).
    """
    act(_DEATH_CRIES[randint(0, len(_DEATH_CRIES) - 1)], ch, type=TO_ROOM)


def create_money(gold, silver):
    """Create a coin item for the given gold/silver amounts (cf. 1stMud create_money in handler.c).

    Args:
        gold (int): Gold coin count.
        silver (int): Silver coin count.

    Returns:
        dict: Coin item instance, or None if both are zero.
    """
    if gold <= 0 and silver <= 0:
        return None
    gold = max(0, gold)
    silver = max(0, silver)
    if gold == 0 and silver == 1:
        obj = create_object(I_COIN_SILVER_GCASH)
        obj["silver"] = 1
        obj["gold"] = 0
        obj["cost"] = 1
        return obj
    if gold == 1 and silver == 0:
        obj = create_object(I_COIN_GOLD_GCASH)
        obj["silver"] = 0
        obj["gold"] = 1
        obj["cost"] = 100
        return obj
    if silver == 0:
        obj = create_object(I_COINS_GOLD_GCASH)
        obj["short_descr"] = str(gold) + " gold coins"
        obj["silver"] = 0
        obj["gold"] = gold
        obj["cost"] = gold * 100
        return obj
    if gold == 0:
        obj = create_object(I_COINS_SILVER_GCASH)
        obj["short_descr"] = str(silver) + " silver coins"
        obj["silver"] = silver
        obj["gold"] = 0
        obj["cost"] = silver
        return obj
    obj = create_object(I_COINS_SILVER_GOLD_GCASH)
    obj["short_descr"] = str(silver) + " silver coins and " + str(gold) + " gold coins"
    obj["silver"] = silver
    obj["gold"] = gold
    obj["cost"] = gold * 100 + silver
    return obj


def make_corpse(ch):
    """Create corpse for ch and place in room (cf. 1stMud make_corpse in fight.c).

    NPC: corpse contains mob loot (gold + equipment).
    PC: [PRIMESUD] empty corpse for dramatic effect; player keeps items on respawn.

    Args:
        ch (dict): Dying character (player or mob instance).

    Returns:
        dict: The corpse object. [PRIMESUD] 1stMud make_corpse is void;
            we return it so autoloot can use it directly instead of searching
            by name (which picks the oldest corpse when multiple exist).
    """
    # 1stMud: if (IsSet(ch->in_room->room_flags, ROOM_ARENA)) return;
    # [PRIMESUD] skip arena check (not ported)

    if ch.get("is_npc"):
        # 1stMud: name = ch->short_descr;
        name = MOB_DEFS[ch["tpl"]]["short_descr"]
        # 1stMud: corpse = create_object(get_obj_index(OBJ_VNUM_CORPSE_NPC), 0);
        corpse = create_object(I_CORPSE)
        # 1stMud: corpse->timer = number_range(3, 6);
        corpse["timer"] = randint(3, 6)
        corpse["contents"] = []
        # 1stMud: if (ch->gold > 0) { obj_to_obj(create_money(...), corpse); ... }
        coin = create_money(ch.get("gold", 0), ch.get("silver", 0))
        if coin is not None:
            corpse["contents"].append(coin)
        # 1stMud: corpse->cost = 0;  (default in PrimeSUD)

        # 1stMud: for (obj = ch->carrying_first ...) obj_to_obj(obj, corpse)
        for obj in list(ch.get("equip", {}).values()) + list(ch.get("inv", [])):
            if obj is None:
                continue
            obj_tpl = ITEM_DEFS[obj["vnum"]]
            flags = item_extra_flags(obj, obj_tpl)
            # 1stMud: if (IsSet(obj->extra_flags, ITEM_INVENTORY)) extract_obj(obj)
            if flags.get("inventory"):
                continue
            # 1stMud: if (IsSet(obj->extra_flags, ITEM_ROT_DEATH) && !floating)
            if flags.get("rot_death"):
                obj["timer"] = randint(5, 10)
                set_item_extra_flag(obj, obj_tpl, "rot_death", False)
            # 1stMud: RemBit(obj->extra_flags, ITEM_VIS_DEATH)
            if item_extra_flags(obj, obj_tpl).get("vis_death"):
                set_item_extra_flag(obj, obj_tpl, "vis_death", False)
            # 1stMud: floating item handling (WEAR_FLOAT scatter/evaporate)
            # [PRIMESUD] skip floating items (not ported)
            corpse["contents"].append(obj)
    else:
        # 1stMud: name = ch->name;
        name = ch.get("name", "someone")
        # 1stMud: corpse = create_object(get_obj_index(OBJ_VNUM_CORPSE_PC), 0);
        corpse = create_object(I_CORPSE_11)
        # 1stMud: corpse->timer = number_range(25, 40);
        corpse["timer"] = randint(25, 40)
        # 1stMud: corpse->owner = str_dup(ch->name);
        corpse["owner"] = ch.get("name", "someone")
        # 1stMud: RemBit(ch->act, PLR_CANLOOT);
        # [PRIMESUD] skip PLR_CANLOOT (not ported)
        # 1stMud: if (is_clan(ch)) { gold/2 into corpse; }
        # [PRIMESUD] skip clan gold split (no clans)
        # 1stMud: item transfer loop (obj_to_obj for all carrying)
        # [PRIMESUD] skip -- player keeps all items on respawn

    # 1stMud: corpse->level = ch->level;
    corpse["level"] = ch.get("level", 1)
    # 1stMud: sprintf(buf, corpse->short_descr, name);
    corpse["short_descr"] = "The corpse of " + name
    # 1stMud: sprintf(buf, corpse->description, name);
    corpse["description"] = "The corpse of " + name + " is lying here."
    # 1stMud: obj_to_room(corpse, ch->in_room);
    world.rooms[ch["room"]]["items"].append(corpse)
    return corpse


def raw_kill(victim, killer):
    """Kill victim: stop fight, death cry, corpse, extract/respawn (cf. 1stMud raw_kill in fight.c).

    Args:
        victim (dict): Dying character (player or mob instance).
        killer (dict or None): Character that landed the killing blow, or None.

    Returns:
        dict: The corpse object created by make_corpse. [PRIMESUD]
    """
    stop_fighting(victim, both=True)
    victim.pop("run_buf", None)  # [PRIMESUD] 1stMud omits this (latent bug: run_buf survives death)
    _death_cry(victim)
    corpse = make_corpse(victim)

    if victim.get("is_npc"):
        # 1stMud: extract_char(victim, true) -- remove NPC from world
        _extract_char(victim, pull=True)
        # [PRIMESUD] save after every kill (1stmud only saves on level up)
        world.save_pending = True
        return corpse

    # 1stMud: extract_char(victim, false) -- teleport PC to altar
    _extract_char(victim, pull=False)
    # 1stMud: strip all affects
    for af in list(victim.get("affect_list", [])):
        affect_remove(victim, af)
    # 1stMud: victim->affected_by = victim->race->aff
    race_data = RACE_TABLE.get(victim.get("race", "Human"), {})
    victim["affected_by"] = dict(race_data.get("aff", {}))
    # 1stMud: for (i = 0; i < MAX_AC; i++) victim->armor[i] = 100
    victim["armor"] = (100, 100, 100, 100)
    # 1stMud: victim->position = POS_RESTING
    victim["pos"] = "resting"
    # 1stMud: victim->hit = Max(1, victim->hit) (etc.)
    victim["hit"] = max(1, victim["hit"])
    victim["mana"] = max(1, victim["mana"])
    victim["move"] = max(1, victim.get("move", 100))

    # [PRIMESUD] respawn flavour text (1stmud has no equivalent)
    tprint("You have been KILLED!!")
    tprint("Your lifeforce ebbs away...")
    wait(DEATH_MSG_DELAY)
    tprint("A distant warmth draws you back.")
    wait(DEATH_MSG_DELAY)
    tprint("You come to your senses. Alive, but barely.")
    tprint("")
    from info import do_look  # lazy import to avoid circular dependency
    do_look(victim, [])

    # [PRIMESUD] save after every kill (1stmud only saves on level up)
    world.save_pending = True
    return corpse


def _extract_char(ch, pull=True):
    """Remove character from room/world (cf. 1stMud extract_char in handler.c).

    Args:
        ch (dict): Character to extract.
        pull (bool): True = fully remove (NPC death), False = teleport to altar (PC death).
    """
    # 1stMud: nuke_pets, die_follower, etc.
    # [PRIMESUD] skip pets/followers (not ported)

    # 1stMud: stop_fighting(ch, true) -- redundant with raw_kill but harmless
    stop_fighting(ch, both=True)

    if pull:
        # NPC: remove from room and world
        room_mobs = world.rooms[ch["room"]]["mobs"]
        if ch["id"] in room_mobs:
            room_mobs.remove(ch["id"])
        del world.chars[ch["id"]]
    else:
        # PC: teleport to altar (R_STARTING_ROOM)
        # 1stMud: char_from_room(ch); char_to_room(ch, ROOM_VNUM_ALTAR)
        ch["room"] = R_STARTING_ROOM


def advance_level(player):
    """Roll HP/MP gains, grant practice and train (cf. 1stMud advance_level in update.c).

    Level increment and XP deduction happen in gain_exp before this is called,
    matching 1stMud's flow.

    Args:
        player (dict): Player state dict.
    """

    con  = get_curr_stat(player, "con")
    wis  = get_curr_stat(player, "wis")
    int_ = get_curr_stat(player, "int")

    # HP: (con_app.hitp + get_hp_gain) * 9/10, min 2  (cf. 1stMud advance_level in update.c;
    # get_hp_gain in multiclass.c rolls the best class die + per-class fuzz)
    add_hp = max(2, (CON_APP_HITP[con] + classes.get_hp_gain(player)) * 9 // 10)

    # MP: number_range(2, (2*INT + WIS)//5), halved for non-casters, * 9/10, min 2
    # (cf. 1stMud advance_level in update.c: if (!has_spells(ch)) add_mana /= 2)
    mp_hi  = max(2, (2 * int_ + wis) // 5)
    add_mp = randint(2, mp_hi)
    if not classes.has_spells(player):
        add_mp //= 2
    add_mp = max(2, add_mp * 9 // 10)

    # MV: number_range(1, (CON+DEX)//6) * 9/10, min 6  (cf. 1stMud advance_level in update.c)
    dex = get_curr_stat(player, "dex")
    mv_hi = max(1, (con + dex) // 6)
    add_mv = max(6, randint(1, mv_hi) * 9 // 10)

    add_prac = WIS_APP_PRACTICE[wis]

    player["perm_hit"]  += add_hp
    player["perm_mana"] += add_mp
    player["perm_move"] += add_mv
    player["max_hit"]   += add_hp
    player["max_mana"]  += add_mp
    player["max_move"]  += add_mv
    player["hit"]        = player["max_hit"]  # [PRIMESUD] 1stMud only adds to max; full heal for UX
    player["mana"]       = player["max_mana"]
    player["move"]       = player["max_move"]  # [PRIMESUD] full restore for UX
    player["practice"] += add_prac
    player["train"]    += 1

    chprintlnf(player, "You gain %d hit %s, %d mana, %d move, and %d %s.",
        add_hp,  "point" if add_hp  == 1 else "points",
        add_mp,
        add_mv,
        add_prac, "practice" if add_prac == 1 else "practices")
    learned = player.get("learned", {})
    for _sn, data in SKILL_TABLE:
        # cf. 1stMud advance_level: skill_level(ch, sn) == ch->level (class-aware)
        if skill_level(player, _sn) == player["level"]:
            kind = "spell" if data.get("spell_fun", "spell_null") != "spell_null" else "skill"
            # 1stMud: learned==1 -> "learn" (go practice it), >1 -> "use" (already practiced)
            verb = "learn" if learned.get(_sn, 0) <= 1 else "use"
            chprintlnf(player, "{MYou can now %s the {W%s{M %s.{x",
                verb, data["name"], kind)


def gain_exp(ch, gain):
    """Add XP to ch and level up as needed (cf. 1stMud gain_exp in update.c).

    Args:
        ch (dict): Player state dict.
        gain (int): XP to add (may be negative for death penalty).
    """
    # cf. 1stMud gain_exp: cap at calc_max_level (HERO + remort count)
    if ch.get("is_npc") or ch.get("level", 1) >= classes.calc_max_level(ch):
        return
    # 1stMud: ch->exp = Max(exp_per_level(...), ch->exp + gain)
    # [PRIMESUD] floor at 0 (no creation-point system)
    ch["xp"] = max(0, ch["xp"] + gain)
    while (ch.get("level", 1) < classes.calc_max_level(ch)
           and ch["xp"] >= ch["xp_next"]):
        chprintln(ch, "You raise a level!!")
        ch["level"] += 1
        ch["xp"]    -= ch["xp_next"]
        advance_level(ch)


def is_same_group(ach, bch):
    """True if ach and bch share a group leader (cf. 1stMud is_same_group in act_comm.c).

    Resolves leader pointers: if a char has a leader, use the leader for
    comparison.  Without followers/pets ported, every char is its own leader,
    so this returns True only when ach is bch.

    Args:
        ach (dict): First character.
        bch (dict): Second character.

    Returns:
        bool: True if both share the same (resolved) leader.
    """
    if ach is None or bch is None:
        return False
    # 1stMud: if (ach->leader != NULL) ach = ach->leader;
    a_leader = ach.get("leader")
    if a_leader is not None:
        ach = world.chars.get(a_leader, ach)
    b_leader = bch.get("leader")
    if b_leader is not None:
        bch = world.chars.get(b_leader, bch)
    return ach is bch


# -- Group level limit (cf. 1stMud mud_info.group_lvl_limit, default 20) -------
GROUP_LVL_LIMIT = 20


def group_gain(ch, victim):
    """Award XP to ch's group for killing victim (cf. 1stMud group_gain in fight.c).

    Iterates all characters in the same room that share ch's group.  NPCs
    (pets) contribute to the group level pool (at half level) but do not
    receive XP.  Each PC member receives XP proportional to their share of
    the total group levels.

    Args:
        ch (dict): Killer (player or mob).
        victim (dict): Defeated character.
    """
    if victim is ch:
        return

    chars = world.chars
    rs = world.rooms[ch["room"]]

    # -- Count members and group levels (cf. 1stMud group_gain pass 1)
    members = 0
    group_levels = 0
    # Collect group chars from room: player + room mobs
    room_chars = []
    player = chars.get(1)
    if player is not None and player["room"] == ch["room"]:
        room_chars.append(player)
    for mid in rs["mobs"]:
        mob = chars.get(mid)
        if mob is not None:
            room_chars.append(mob)

    for gch in room_chars:
        if is_same_group(gch, ch):
            members += 1
            group_levels += gch["level"] // 2 if gch["is_npc"] else gch["level"]

    if members == 0:
        members = 1
        group_levels = ch["level"]

    # -- Find highest level in group (cf. 1stMud group_gain pass 2)
    highest_level = 0
    for gch in room_chars:
        if is_same_group(gch, ch) and gch["level"] > highest_level:
            highest_level = gch["level"]

    # -- Award XP to each PC group member (cf. 1stMud group_gain pass 3)
    for gch in room_chars:
        if not is_same_group(gch, ch) or gch["is_npc"]:
            continue

        # 1stMud: level range check (group_lvl_limit)
        if (highest_level - gch["level"] >= GROUP_LVL_LIMIT
                or highest_level - gch["level"] <= -GROUP_LVL_LIMIT):
            tprint("Your powers are useless to such an advanced group of adventurers.")
            # 1stMud: if IsNPC(gch) && gch->master: act to master
            # [PRIMESUD] skip (gch is always a PC here)
            continue

        xp = xp_compute(gch, victim, group_levels)

        # 1stMud: if (mud_info.bonus.status == BONUS_XP) ...
        # [PRIMESUD] skip bonus XP event (not ported)
        tprint("You receive %s experience %s." % (
            str(xp), "point" if xp == 1 else "points"))
        gain_exp(gch, xp)

        # 1stMud: quest mob check (IsQuester && quest.mob == victim)
        # [PRIMESUD] quest completion handled separately in quest system


def _get_size(ch):
    """Return numeric size rank for ch (cf. 1stMud ch->size)."""
    if ch["is_npc"]:
        return SIZE_RANK.get(MOB_DEFS[ch["tpl"]].get("size", "medium"), 2)
    return SIZE_RANK.get(ch.get("size", "medium"), 2)


def _number_fuzzy(n):
    """Return n-1, n, or n+1 at random (cf. 1stMud number_fuzzy in db.c)."""
    return n + randint(-1, 1)


def _exit_to(exit_val):
    """Return destination vnum from a plain-vnum or dict exit. [PRIMESUD]"""
    return exit_val["to"] if isinstance(exit_val, dict) else exit_val


# -- Do_Fun ports from fight.c ------------------------------------------------

def do_murder(ch, args):
    """Attack a target with a yell for help (cf. 1stMud do_murder in fight.c).

    In ROM/Merc MUDs, ``kill`` was the normal PvE command while ``murder``
    was for attacking players -- hence the victim yell and the charm/pet
    guard (charmed mobs can't murder).  By 1stMud both run check_killer,
    so the practical difference is just the yell broadcast and the noprefix
    flag (can't trigger by abbreviation).

    Args:
        ch (dict): Acting character.
        args (list): Target keyword.
    """
    if not args:
        tprint("Murder whom?")
        return None

    # [PRIMESUD] charm/pet check skipped (not ported)

    rs = world.rooms[ch["room"]]
    mob_id = get_char_room(" ".join(args), rs["mobs"], world.chars)
    if mob_id is None:
        tprint("They aren't here.")
        return None

    victim = world.chars[mob_id]
    if victim is ch:
        tprint("Suicide is a mortal sin.")
        return None

    if is_safe(ch, victim):
        return None
    # [PRIMESUD] kill-stealing check not ported (single-player)
    # [PRIMESUD] charm master check not ported

    if ch.get("pos") == "fighting":
        tprint("You do the best you can!")
        return None

    WaitState(ch, PULSE_VIOLENCE)

    # 1stMud: victim yells for help
    victim_name = MOB_DEFS[victim["tpl"]]["short_descr"] if victim["is_npc"] else "someone"
    ch_name = ch.get("name", "someone")
    tprint("{} screams 'Help! I am being attacked by {}!'".format(
        upper(victim_name), ch_name))

    # [PRIMESUD] check_killer not ported
    multi_hit(ch, victim)
    return None


def do_suicide(ch, args):
    """Confirm-gated suicide (cf. 1stMud do_suicide in fight.c).

    Args:
        ch (dict): Acting character.
        args (list): Unused.
    """
    if ch["fighting"] is not None:
        tprint("You too busy!")
        return None

    # [PRIMESUD] ROOM_ARENA / ROOM_SAFE check not ported

    if not ch.get("confirm_suicide"):
        tprint("The gods disapprove of the taking of your own life.")
        tprint("If you REALLY want to commit suicide, type 'suicide' again. :(")
        ch["confirm_suicide"] = True
    else:
        act("$n uses a small knife to slit $s own throat!", ch, type=TO_ROOM)
        act("You use a small knife to slit your own throat!", ch, type=TO_CHAR)
        ch["confirm_suicide"] = False
        raw_kill(ch, None)
    return None


def do_berserk(ch, args):
    """Go berserk for combat bonuses (cf. 1stMud do_berserk in fight.c).

    Args:
        ch (dict): Acting character.
        args (list): Unused.
    """
    skill = get_skill(ch, GSN_BERSERK, ch["is_npc"])
    if skill == 0:
        tprint("You turn red in the face, but nothing happens.")
        return None

    if ch.get("affected_by", {}).get("berserk"):
        tprint("You get a little madder.")
        return None

    # 1stMud: check for frenzy spell too
    if ch.get("affected_by", {}).get("calm"):
        tprint("You're feeling to mellow to berserk.")
        return None

    if ch.get("mana", 0) < 50:
        tprint("You can't get up enough energy.")
        return None

    chance = skill
    if ch.get("pos") == "fighting":
        chance += 10

    hp_pct = 100 * ch["hit"] // max(1, ch.get("max_hit", 1))
    chance += 25 - hp_pct // 2

    if randint(1, 100) < chance:
        WaitState(ch, PULSE_VIOLENCE)
        ch["mana"] -= 50
        ch["move"] = ch.get("move", 0) // 2

        ch["hit"] += ch["level"] * 2
        ch["hit"] = min(ch["hit"], ch.get("max_hit", ch["hit"]))

        tprint("Your pulse races as you are consumed by rage!")
        check_improve(ch, GSN_BERSERK, True, 2)

        dur = _number_fuzzy(ch["level"] // 8)
        mod_hr_dr = max(1, ch["level"] // 5)
        mod_ac = max(10, 10 * (ch["level"] // 5))

        af_base = {
            "where": "to_affects",
            "type": GSN_BERSERK,
            "level": ch["level"],
            "duration": dur,
            "bitvector": "berserk",
        }
        af_hr = dict(af_base)
        af_hr["location"] = "hitroll"
        af_hr["modifier"] = mod_hr_dr
        affect_to_char(ch, af_hr)

        af_dr = dict(af_base)
        af_dr["location"] = "damroll"
        af_dr["modifier"] = mod_hr_dr
        affect_to_char(ch, af_dr)

        af_ac = dict(af_base)
        af_ac["location"] = "ac"
        af_ac["modifier"] = mod_ac
        affect_to_char(ch, af_ac)
    else:
        WaitState(ch, 3 * PULSE_VIOLENCE)
        ch["mana"] -= 25
        ch["move"] = ch.get("move", 0) // 2
        tprint("Your pulse speeds up, but nothing happens.")
        check_improve(ch, GSN_BERSERK, False, 2)
    return None


def do_bash(ch, args):
    """Shield bash a target (cf. 1stMud do_bash in fight.c).

    Args:
        ch (dict): Acting character.
        args (list): Optional target keyword.
    """
    chance = get_skill(ch, GSN_BASH, ch["is_npc"])
    if chance == 0:
        tprint("Bashing? What's that?")
        return None

    if not args:
        victim_id = ch["fighting"]
        if victim_id is None:
            tprint("But you aren't fighting anyone!")
            return None
        victim = world.chars[victim_id]
    else:
        rs = world.rooms[ch["room"]]
        victim_id = get_char_room(" ".join(args), rs["mobs"], world.chars)
        if victim_id is None:
            chprintln(ch, "They aren't here.")
            return None
        victim = world.chars[victim_id]

    if POS_ORDER[victim.get("pos", "standing")] < POS_ORDER["fighting"]:
        act("You'll have to let $M get back up first.", ch, None, victim,
            TO_CHAR)
        return None

    if victim is ch:
        chprintln(ch, "You try to bash your brains out, but fail.")
        return None

    if is_safe(ch, victim):
        return None
    # [PRIMESUD] kill-stealing check not ported (single-player)
    # [PRIMESUD] charm master check not ported

    # 1stMud: carry_weight adjustments; [PRIMESUD] carry_weight not ported
    ch_size = _get_size(ch)
    v_size = _get_size(victim)
    if ch_size < v_size:
        chance += (ch_size - v_size) * 15
    else:
        chance += (ch_size - v_size) * 10

    chance += get_curr_stat(ch, "str")
    chance -= (get_curr_stat(victim, "dex") * 4) // 3
    chance -= get_armor(victim, AC_BASH) // 25

    # 1stMud: haste bonus/penalty; [PRIMESUD] haste not fully ported
    if ch.get("affected_by", {}).get("haste"):
        chance += 10
    if victim.get("affected_by", {}).get("haste"):
        chance -= 30

    chance += ch["level"] - victim["level"]

    if not victim["is_npc"]:
        dodge_sk = get_skill(victim, GSN_DODGE)
        if chance < dodge_sk:
            chance -= 3 * (dodge_sk - chance)

    if randint(1, 100) < chance:
        act("$n sends you sprawling with a powerful bash!", ch, None, victim,
            TO_VICT)
        act("You slam into $N, and send $M flying!", ch, None, victim,
            TO_CHAR)
        act("$n sends $N sprawling with a powerful bash.", ch, None, victim,
            TO_NOTVICT)
        check_improve(ch, GSN_BASH, True, 1)

        DazeState(victim, 3 * PULSE_VIOLENCE)
        WaitState(ch, SKILLS[GSN_BASH]["beats"])
        victim["pos"] = "resting"
        dam = randint(2, 2 + 2 * ch_size + chance // 20)
        damage(ch, victim, dam, GSN_BASH, DAM_BASH, show=False)
    else:
        damage(ch, victim, 0, GSN_BASH, DAM_BASH, show=False)
        act("You fall flat on your face!", ch, None, victim, TO_CHAR)
        act("$n falls flat on $s face.", ch, None, victim, TO_NOTVICT)
        act("You evade $n's bash, causing $m to fall flat on $s face.", ch,
            None, victim, TO_VICT)
        check_improve(ch, GSN_BASH, False, 1)
        ch["pos"] = "resting"
        WaitState(ch, SKILLS[GSN_BASH]["beats"] * 3 // 2)

    # [PRIMESUD] check_killer not ported
    return None


def do_dirt(ch, args):
    """Kick dirt in opponent's eyes (cf. 1stMud do_dirt in fight.c).

    Args:
        ch (dict): Acting character.
        args (list): Optional target keyword.
    """
    chance = get_skill(ch, GSN_DIRT, ch["is_npc"])
    if chance == 0:
        tprint("You get your feet dirty.")
        return None

    if not args:
        victim_id = ch["fighting"]
        if victim_id is None:
            tprint("But you aren't in combat!")
            return None
        victim = world.chars[victim_id]
    else:
        rs = world.rooms[ch["room"]]
        victim_id = get_char_room(" ".join(args), rs["mobs"], world.chars)
        if victim_id is None:
            tprint("They aren't here.")
            return None
        victim = world.chars[victim_id]

    if victim.get("affected_by", {}).get("blind"):
        act("$E's already been blinded.", ch, None, victim, TO_CHAR)
        return None

    if victim is ch:
        chprintln(ch, "Very funny.")
        return None

    if is_safe(ch, victim):
        return None
    # [PRIMESUD] kill-stealing check not ported (single-player)
    # [PRIMESUD] charm master check not ported

    chance += get_curr_stat(ch, "dex")
    chance -= 2 * get_curr_stat(victim, "dex")

    if ch.get("affected_by", {}).get("haste"):
        chance += 10
    if victim.get("affected_by", {}).get("haste"):
        chance -= 25

    chance += (ch["level"] - victim["level"]) * 2

    if chance % 5 == 0:
        chance += 1

    # Sector-type modifier (cf. 1stMud switch on sector_type)
    room_def = ROOM_DEFS.get(ch["room"], {})
    sector = room_def.get("sector", "field")
    if sector == "inside":
        chance -= 20
    elif sector == "city":
        chance -= 10
    elif sector == "field" or sector == "path":
        chance += 5
    elif sector == "mountain" or sector == "swamp":
        chance -= 10
    elif sector in ("water_swim", "water_noswim", "air"):
        chance = 0
    elif sector == "desert":
        chance += 10

    if chance == 0:
        tprint("There isn't any dirt to kick.")
        return None

    if randint(1, 100) < chance:
        act("$n is blinded by the dirt in $s eyes!", victim, None, None,
            TO_ROOM)
        act("$n kicks dirt in your eyes!", ch, None, victim, TO_VICT)
        damage(ch, victim, randint(2, 5), GSN_DIRT, DAM_NONE, show=False)
        chprintln(victim, "You can't see a thing!")
        check_improve(ch, GSN_DIRT, True, 2)
        WaitState(ch, SKILLS[GSN_DIRT]["beats"])

        af = {
            "where": "to_affects",
            "type": GSN_DIRT,
            "level": ch["level"],
            "duration": 0,
            "location": "hitroll",
            "modifier": -4,
            "bitvector": "blind",
        }
        affect_to_char(victim, af)
    else:
        damage(ch, victim, 0, GSN_DIRT, DAM_NONE, show=True)
        check_improve(ch, GSN_DIRT, False, 2)
        WaitState(ch, SKILLS[GSN_DIRT]["beats"])

    # [PRIMESUD] check_killer not ported
    return None


def do_trip(ch, args):
    """Trip an opponent (cf. 1stMud do_trip in fight.c).

    Args:
        ch (dict): Acting character.
        args (list): Optional target keyword.
    """
    chance = get_skill(ch, GSN_TRIP, ch["is_npc"])
    if chance == 0:
        tprint("Tripping?  What's that?")
        return None

    if not args:
        victim_id = ch["fighting"]
        if victim_id is None:
            tprint("But you aren't fighting anyone!")
            return None
        victim = world.chars[victim_id]
    else:
        rs = world.rooms[ch["room"]]
        victim_id = get_char_room(" ".join(args), rs["mobs"], world.chars)
        if victim_id is None:
            tprint("They aren't here.")
            return None
        victim = world.chars[victim_id]

    if is_safe(ch, victim):
        return None
    # [PRIMESUD] kill-stealing check not ported (single-player)

    if victim.get("affected_by", {}).get("flying"):
        tprint("Their feet aren't on the ground.")
        return None

    if POS_ORDER[victim.get("pos", "standing")] < POS_ORDER["fighting"]:
        tprint("They are already down.")
        return None

    if victim is ch:
        tprint("You fall flat on your face!")
        WaitState(ch, 2 * SKILLS[GSN_TRIP]["beats"])
        return None

    # [PRIMESUD] charm master check not ported

    ch_size = _get_size(ch)
    v_size = _get_size(victim)
    if ch_size < v_size:
        chance += (ch_size - v_size) * 10

    chance += get_curr_stat(ch, "dex")
    chance -= get_curr_stat(victim, "dex") * 3 // 2

    if ch.get("affected_by", {}).get("haste"):
        chance += 10
    if victim.get("affected_by", {}).get("haste"):
        chance -= 20

    chance += (ch["level"] - victim["level"]) * 2

    if randint(1, 100) < chance:
        act("You trip $N and $E goes down!", ch, None, victim, TO_CHAR)
        act("$n trips you and you go down!", ch, None, victim, TO_VICT)
        check_improve(ch, GSN_TRIP, True, 1)

        DazeState(victim, 2 * PULSE_VIOLENCE)
        WaitState(ch, SKILLS[GSN_TRIP]["beats"])
        victim["pos"] = "resting"
        dam = randint(2, 2 + 2 * v_size)
        damage(ch, victim, dam, GSN_TRIP, DAM_BASH, show=True)
        # TODO: stance trip (if ValidStance && chance-5 check) not ported
    else:
        damage(ch, victim, 0, GSN_TRIP, DAM_BASH, show=True)
        WaitState(ch, SKILLS[GSN_TRIP]["beats"] * 2 // 3)
        check_improve(ch, GSN_TRIP, False, 1)

    # [PRIMESUD] check_killer not ported
    return None


def do_flee(ch, args):
    """Attempt to flee from combat (cf. 1stMud do_flee in fight.c).

    Works for both players and NPCs.

    Args:
        ch (dict): Acting character.
        args (list): Unused.
    """
    from info import do_look  # lazy import to avoid circular dependency

    if ch["fighting"] is None:
        if ch.get("pos") == "fighting":
            ch["pos"] = "standing"
        if not ch.get("is_npc"):
            tprint("You aren't fighting anyone.")
        return None

    # [PRIMESUD] arena check not ported

    was_in = ch["room"]
    exits = ROOM_DEFS[was_in].get("exits", {})
    exit_keys = list(exits.keys())
    is_npc = ch.get("is_npc", False)

    for _attempt in range(6):
        if not exit_keys:
            break
        door = exit_keys[randint(0, len(exit_keys) - 1)]
        exit_val = exits[door]

        if isinstance(exit_val, dict) and exit_val.get("closed"):
            continue

        # 1stMud: daze blocks flee through this exit
        if ch.get("daze", 0) > 0 and randint(0, ch["daze"]) != 0:
            continue

        dest = _exit_to(exit_val)
        if dest not in ROOM_DEFS:
            continue

        # NPCs can't flee into NO_MOB rooms
        if is_npc and ROOM_DEFS[dest].get("flags", {}).get("no_mob"):
            continue

        ch["room"] = dest
        if is_npc:
            ch_id = ch["id"]
            old_mobs = world.rooms.get(was_in, {}).get("mobs", [])
            if ch_id in old_mobs:
                old_mobs.remove(ch_id)
            world.rooms[dest]["mobs"].append(ch_id)

        stop_fighting(ch, both=True)

        if not is_npc:
            tprint("You flee from combat!")
            # 1stMud: class 2 (thief) sneak check; [PRIMESUD] classless
            tprint("You lost 10 exp.")
            ch["xp"] = max(0, ch["xp"] - 10)
            do_look(ch, [])
        return None

    if not is_npc:
        tprint("PANIC! You couldn't escape!")
    return None


def do_rescue(ch, args):
    """Rescue another character from combat (cf. 1stMud do_rescue in fight.c).

    [PRIMESUD] Single-player: rescuing NPCs is blocked by 1stMud (!IsNPC(ch) &&
    IsNPC(victim) -> "Doesn't need your help!"). Ported for fidelity but largely
    a no-op in single-player.

    Args:
        ch (dict): Acting character.
        args (list): Target keyword.
    """
    if not args:
        tprint("Rescue whom?")
        return None

    rs = world.rooms[ch["room"]]
    victim_id = get_char_room(" ".join(args), rs["mobs"], world.chars)
    if victim_id is None:
        tprint("They aren't here.")
        return None
    victim = world.chars[victim_id]

    if victim is ch:
        tprint("What about fleeing instead?")
        return None

    # 1stMud: if (!IsNPC(ch) && IsNPC(victim)) "Doesn't need your help!"
    if not ch["is_npc"] and victim["is_npc"]:
        tprint("Doesn't need your help!")
        return None

    if ch["fighting"] == victim_id:
        tprint("Too late.")
        return None

    fch_id = victim["fighting"]
    if fch_id is None:
        tprint("That person is not fighting right now.")
        return None
    fch = world.chars.get(fch_id)
    if fch is None:
        tprint("That person is not fighting right now.")
        return None

    # [PRIMESUD] kill-stealing check not ported (single-player)

    WaitState(ch, SKILLS[GSN_RESCUE]["beats"])
    skill_pct = get_skill(ch, GSN_RESCUE, ch["is_npc"])
    if randint(1, 100) > skill_pct:
        tprint("You fail the rescue.")
        check_improve(ch, GSN_RESCUE, False, 1)
        return None

    act("You rescue $N!", ch, None, victim, TO_CHAR)
    act("$n rescues you!", ch, None, victim, TO_VICT)
    check_improve(ch, GSN_RESCUE, True, 1)

    stop_fighting(fch, both=False)
    stop_fighting(victim, both=False)

    # [PRIMESUD] check_killer not ported
    set_fighting(ch, fch)
    set_fighting(fch, ch)
    return None


def disarm(ch, victim):
    """Remove victim's weapon (cf. 1stMud disarm in fight.c).

    Args:
        ch (dict): Attacker.
        victim (dict): Defender whose weapon is removed.
    """
    wobj = victim["equip"].get("wield")
    if wobj is None:
        return

    obj_tpl = ITEM_DEFS[wobj["vnum"]]
    flags = item_extra_flags(wobj, obj_tpl)
    if flags.get("noremove"):
        act("$S weapon won't budge!", ch, None, victim, TO_CHAR)
        act("$n tries to disarm you, but your weapon won't budge!", ch, None, victim, TO_VICT)
        return

    act("You disarm $N!", ch, None, victim, TO_CHAR)
    act("$n DISARMS you and sends your weapon flying!", ch, None, victim, TO_VICT)

    del victim["equip"]["wield"]

    if flags.get("nodrop") or flags.get("inventory"):
        # Item stays with victim (goes to inventory)
        victim["inv"].append(wobj)
    else:
        # Item falls to room floor
        world.rooms[victim["room"]]["items"].append(wobj)
        # 1stMud: if IsNPC && wait==0 && can_see_obj, mob picks it back up
        if victim["is_npc"] and victim.get("wait", 0) == 0:
            victim["equip"]["wield"] = wobj
            world.rooms[victim["room"]]["items"].remove(wobj)


def do_disarm(ch, args):
    """Attempt to disarm opponent's weapon (cf. 1stMud do_disarm in fight.c).

    Args:
        ch (dict): Acting character.
        args (list): Unused.
    """
    chance = get_skill(ch, GSN_DISARM, ch["is_npc"])
    if chance == 0:
        tprint("You don't know how to disarm opponents.")
        return None

    hth = 0
    if ch["equip"].get("wield") is None:
        hth = get_skill(ch, GSN_HAND_TO_HAND, ch["is_npc"])
        if hth == 0:
            tprint("You must wield a weapon to disarm.")
            return None

    victim_id = ch["fighting"]
    if victim_id is None:
        tprint("You aren't fighting anyone.")
        return None
    victim = world.chars[victim_id]

    if victim["equip"].get("wield") is None:
        tprint("Your opponent is not wielding a weapon.")
        return None

    ch_weapon_sn, _ = _get_weapon_sn(ch)
    vict_weapon_sn, _ = _get_weapon_sn(victim)
    ch_weapon = _get_weapon_skill(ch, ch_weapon_sn)
    vict_weapon = _get_weapon_skill(victim, vict_weapon_sn)
    ch_vict_weapon = _get_weapon_skill(ch, vict_weapon_sn)

    if ch["equip"].get("wield") is None:
        chance = chance * hth // 150
    else:
        chance = chance * ch_weapon // 100

    chance += (ch_vict_weapon // 2 - vict_weapon) // 2

    chance += get_curr_stat(ch, "dex")
    chance -= 2 * get_curr_stat(victim, "str")

    chance += (ch["level"] - victim["level"]) * 2

    WaitState(ch, SKILLS[GSN_DISARM]["beats"])
    if randint(1, 100) < chance:
        disarm(ch, victim)
        check_improve(ch, GSN_DISARM, True, 1)
    else:
        tprint("You fail to disarm your opponent.")
        check_improve(ch, GSN_DISARM, False, 1)

    # [PRIMESUD] check_killer not ported
    return None


def do_surrender(ch, args):
    """Surrender to current opponent (cf. 1stMud do_surrender in fight.c).

    Args:
        ch (dict): Acting character.
        args (list): Unused.
    """
    mob_id = ch["fighting"]
    if mob_id is None:
        tprint("But you're not fighting!")
        return None

    mob = world.chars.get(mob_id)
    if mob is None:
        stop_fighting(ch, both=False)
        tprint("But you're not fighting!")
        return None

    act("You surrender to $N!", ch, None, mob, TO_CHAR)

    stop_fighting(ch, both=True)

    # 1stMud: if (!IsNPC(ch) && IsNPC(mob) && no TRIG_SURR) mob resumes attack
    if not ch["is_npc"] and mob["is_npc"]:
        # [PRIMESUD] TRIG_SURR not ported; mob always ignores surrender
        act("$N seems to ignore your cowardly act!", ch, None, mob, TO_CHAR)
        multi_hit(mob, ch)
    return None


def do_slay(ch, args):
    """Immortal instant-kill (cf. 1stMud do_slay in fight.c).

    [PRIMESUD] No immortal system, but ported for completeness. Could be
    used as a debug/GM command.

    Args:
        ch (dict): Acting character.
        args (list): Target keyword.
    """
    if not args:
        tprint("Slay whom?")
        return None

    rs = world.rooms[ch["room"]]
    mob_id = get_char_room(" ".join(args), rs["mobs"], world.chars)
    if mob_id is None:
        tprint("They aren't here.")
        return None

    victim = world.chars[mob_id]
    if victim is ch:
        tprint("Suicide is a mortal sin.")
        return None

    # 1stMud: trust-level check; [PRIMESUD] no trust system
    act("You slay $M in cold blood!", ch, None, victim, TO_CHAR)
    raw_kill(victim, ch)
    return None


def do_sskill(ch, args):
    """Display fighting stance skills (cf. 1stMud do_sskill in fight.c).

    TODO: Stance system not ported. Placeholder prints a message.

    Args:
        ch (dict): Acting character.
        args (list): Unused.
    """
    # TODO: stance_table, GetStance, stance_name not ported
    tprint("Fighting stances are not yet available.")
    return None


def do_stance(ch, args):
    """Set or toggle fighting stance (cf. 1stMud do_stance in fight.c).

    TODO: Stance system not ported. Placeholder prints a message.

    Args:
        ch (dict): Acting character.
        args (list): Optional stance name.
    """
    # TODO: stance_table, GetStance, SetStance, can_use_stance not ported
    tprint("Fighting stances are not yet available.")
    return None


def do_autostance(ch, args):
    """Set auto-stance on combat start (cf. 1stMud do_autostance in fight.c).

    TODO: Stance system not ported. Placeholder prints a message.

    Args:
        ch (dict): Acting character.
        args (list): Optional stance name or 'none'.
    """
    # TODO: stance_table, GetStance, SetStance, STANCE_AUTODROP not ported
    tprint("Fighting stances are not yet available.")
    return None
