"""Combat rounds, damage resolution, skills, and fight state."""

from actor import (get_hitroll, get_damroll, get_armor, get_curr_stat, act,
                   is_awake, can_see, affect_to_char)
from colors import upper
from area_limbo import (
    I_CORPSE,
    I_COIN_SILVER_GCASH,
    I_COIN_GOLD_GCASH,
    I_COINS_SILVER_GCASH,
    I_COINS_GOLD_GCASH,
    I_COINS_SILVER_GOLD_GCASH,
)
from config import (
    PULSE_VIOLENCE,
    POS_ORDER,
    CON_APP_HITP,
    WIS_APP_PRACTICE,
    INT_APP_LEARN,
    CLASS_HP_MIN,
    CLASS_HP_MAX,
    THAC0_00,
    THAC0_MIN,
    THAC0_PLATEAU,
    ATTACK_TABLE,
    TYPE_HIT,
    TYPE_UNDEFINED,
    DAM_NONE,
    DAM_BASH,
    DAM_PIERCE,
    DAM_SLASH,
    DAM_FIRE,
    DAM_COLD,
    DAM_LIGHTNING,
    DAM_ACID,
    DAM_POISON,
    DAM_NEGATIVE,
    DAM_HOLY,
    DAM_ENERGY,
    DAM_MENTAL,
    DAM_DISEASE,
    DAM_DROWNING,
    DAM_LIGHT,
    DAM_SOUND,
    DAM_CHARM,
    AC_PIERCE,
    AC_BASH,
    AC_SLASH,
    AC_EXOTIC,
)
from item import get_char_room, create_object, item_extra_flags, set_item_extra_flag
from picker import pick_from
from player import save_world
from terminal import tprint
from urandom import randint
from skills_table import (
    SKILL_TABLE, SKILLS, WEAPON_GSN_MAP,
    GSN_BACKSTAB, GSN_BASH, GSN_BERSERK, GSN_DIRT, GSN_DISARM,
    GSN_DODGE, GSN_HAND_TO_HAND, GSN_KICK, GSN_PARRY,
    GSN_RESCUE, GSN_SHIELD_BLOCK, GSN_SECOND_ATTACK, GSN_THIRD_ATTACK,
    GSN_TRIP,
)
import world
from world import ITEM_DEFS, MOB_DEFS, ROOM_DEFS


# -- Violence update (called every PULSE_VIOLENCE) -----------------------------

def violence_update(tr, player):
    """One combat pulse: all chars with a fight target attack (cf. 1stMud violence_update in fight.c).

    Args:
        tr: Terminal for printing combat messages.
        player (dict): Player state dict.

    Returns:
        bool or None: True if player died this pulse; None otherwise.
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
            multi_hit(tr, ch, victim)
        else:
            stop_fighting(ch, both=False)

        # 1stMud: victim = ch->fighting; if victim == NULL: continue
        if ch["fighting"] is None:
            continue

        # [PRIMESUD] player death check; 1stMud handles inside damage()
        if player.get("pos") == "dead":
            return True

        # 1stMud: check_assist(ch, victim)
        check_assist(tr, ch, victim)

        # TODO: mob TRIG_FIGHT / TRIG_HPCNT triggers not ported
        # TODO: obj worn-item TRIG_FIGHT triggers not ported
        # TODO: room TRIG_FIGHT trigger not ported

    return None


def check_assist(tr, ch, victim):
    """Let idle room chars join combat (cf. 1stMud check_assist in fight.c).

    Three cases mirror 1stMud exactly:
    - ch is player, rch is mob with assist_players: rch jumps in against victim.
    - ch is player, rch is player: autoassist / charm (no-op in single-player).
    - ch is mob (not charmed), rch is mob: assist_all / group / race / align / vnum;
      50% trigger chance; target picked from victim's group (single-player: victim).

    Args:
        tr: Terminal for printing combat messages.
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
                multi_hit(tr, rch, victim)
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

        # Pick random target from victim's group (cf. 1stMud target selection loop).
        # [PRIMESUD] Single-player: victim's group = victim only; target is always victim.
        tprint("{} screams and attacks!".format(rch_tpl["short_descr"]))
        multi_hit(tr, rch, victim)


# -- Helpers -------------------------------------------------------------------

def _same_align(tpl_a, tpl_b):
    """True if both templates share the same alignment band (good/neutral/evil).

    Args:
        tpl_a (dict): First mob template.
        tpl_b (dict): Second mob template.

    Returns:
        bool: True if both are in the same alignment band.
    """
    # cf. 1stMud IsGood/IsEvil/IsNeutral (>= 350, <= -350, between) in merc.h
    a = tpl_a.get("alignment", 0)
    b = tpl_b.get("alignment", 0)
    if a >= 350 and b >= 350:
        return True
    if a <= -350 and b <= -350:
        return True
    if -350 < a < 350 and -350 < b < 350:
        return True
    return False


def _dice(num, size):
    """Roll num dice of size sides and return the sum.

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


def _get_thac0(level):
    """Base THAC0 for a given level (classless curve, before hitroll/skill adj).

    Natural THAC0 plateaus at THAC0_PLATEAU; above that only hitroll/AC move
    the needle.  [PRIMESUD] Classless -- 1stMud uses per-class curves; see DESIGN.md.

    Args:
        level (int): Character level.

    Returns:
        int: Base THAC0, clamped to minimum -5 after soft-cap.
    """
    eff = min(level, THAC0_PLATEAU)
    # cf. 1stMud interpolate(level, thac0_00, thac0_32) in fight.c
    # Written as subtraction so the product is always positive, matching C truncation.
    t = THAC0_00 - (THAC0_00 - THAC0_MIN) * eff // THAC0_PLATEAU
    if t < 0:
        t = t // 2
    if t < -5:
        t = -5 + (t + 5) // 2
    return t


_XP_BASE = {
    -9: 1, -8: 2, -7: 5, -6: 9, -5: 11, -4: 22, -3: 33, -2: 50,
    -1: 66, 0: 83, 1: 99, 2: 121, 3: 143, 4: 165,
}


def _xp_for_kill(player_level, mob_level):
    """XP awarded for killing a mob, based on level difference (cf. 1stMud xp_compute in fight.c).

    Args:
        player_level (int): Player's current level.
        mob_level (int): Defeated mob's level.

    Returns:
        int: XP gain, randomised +/-25% around the base value.
    """
    lr = mob_level - player_level
    if lr <= -10:
        base = 0
    elif lr > 4:
        base = 160 + 20 * (lr - 4)
    else:
        base = _XP_BASE[lr]
    if player_level < 6:
        base = 10 * base // (player_level + 4)
    if base <= 0:
        return 0
    return randint(base * 3 // 4, base * 5 // 4)


def _get_weapon_sn(ch, slot="wield"):
    """Return (sn, tpl_or_None) for the weapon in the given equip slot (cf. get_weapon_sn in handler.c).

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
    """Map damage class to 1stMud armor bucket."""
    if dam_class == DAM_PIERCE:
        return AC_PIERCE
    if dam_class == DAM_SLASH:
        return AC_SLASH
    if dam_class == DAM_BASH or dam_class == DAM_NONE:
        return AC_BASH
    return AC_EXOTIC


# -- Immunity check (cf. 1stMud check_immune in handler.c) ---------------------

IS_NORMAL     = 0
IS_IMMUNE     = 1
IS_RESISTANT  = 2
IS_VULNERABLE = 3
IMMUNE_NONE   = -1

# Maps dam_class -> flag name for specific-type immunity lookup.
# DAM_BASH/PIERCE/SLASH use "weapon" as the broad category; everything else
# uses "magic".  The specific flag name (e.g. "fire") overrides the broad one.
_DAM_TO_FLAG = {
    DAM_BASH:      "bash",
    DAM_PIERCE:    "pierce",
    DAM_SLASH:     "slash",
    DAM_FIRE:      "fire",
    DAM_COLD:      "cold",
    DAM_LIGHTNING: "lightning",
    DAM_ACID:      "acid",
    DAM_POISON:    "poison",
    DAM_NEGATIVE:  "negative",
    DAM_HOLY:      "holy",
    DAM_ENERGY:    "energy",
    DAM_MENTAL:    "mental",
    DAM_DISEASE:   "disease",
    DAM_DROWNING:  "drowning",
    DAM_LIGHT:     "light",
    DAM_CHARM:     "charm",
    DAM_SOUND:     "sound",
}


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
    flag = _DAM_TO_FLAG.get(dam_type)
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


def mob_condition(inst, tpl):
    """Return a condition description string for a mob.

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


# -- Wait state ----------------------------------------------------------------

def WaitState(ch, pulses):
    """Set skill lag: ch cannot act for `pulses` pulses (cf. 1stMud WaitState).

    Args:
        ch (dict): Character state dict (player or mob instance).
        pulses (int): Lag duration in combat pulses.
    """
    if pulses > ch.get("wait", 0):
        ch["wait"] = pulses


def DazeState(ch, pulses):
    """Set daze: skill checks penalised for `pulses` pulses (cf. 1stMud DazeState).

    Args:
        ch (dict): Character state dict (player or mob instance).
        pulses (int): Daze duration in raw pulses.
    """
    if pulses > ch.get("daze", 0):
        ch["daze"] = pulses


def update_mob_timers():
    """Bulk-decrement wait/daze for NPCs in current room (cf. 1stMud multi_hit NPC path)."""
    rs = world.rooms[world.chars[1]["room"]]
    for mid in rs["mobs"]:
        inst = world.chars[mid]
        inst["wait"] = max(0, inst.get("wait", 0) - PULSE_VIOLENCE)
        inst["daze"] = max(0, inst.get("daze", 0) - PULSE_VIOLENCE)


# -- Skill improvement ---------------------------------------------------------

def _int_learn(int_stat):
    """Skill improvement rate for an INT stat value (cf. 1stMud int_app[INT].learn).

    Args:
        int_stat (int): Character INT stat.

    Returns:
        int: Improvement rate (e.g. 25 at INT 13, 40 at INT 18).
    """
    return INT_APP_LEARN[int_stat]


def check_improve(tr, player, sk_vnum, success, multiplier):
    """Attempt to improve a skill after use (cf. 1stMud check_improve in skills.c).

    Args:
        tr: Terminal for printing improvement messages.
        player (dict): Player state dict.
        sk_vnum (int): Skill vnum to potentially improve.
        success (bool): True if skill was used correctly (harder to improve near 100);
            False if missed/failed (learn-from-mistakes, faster at low skill).
        multiplier (int): Training context difficulty (1=easy, 6=hard); passed per
            call site as in 1stMud rather than stored in the skill table.
    """
    current = player["learned"].get(sk_vnum, 0)
    if current <= 0 or current >= 100:
        return

    sk        = SKILLS[sk_vnum]
    sk_rating = sk.get("rating", 1)

    chance = 10 * _int_learn(get_curr_stat(player, "int"))
    chance //= max(1, multiplier * sk_rating * 4)
    chance += player["level"]

    if randint(1, 1000) > chance:
        return

    sk_name = sk["name"]
    if success:
        inner = min(95, max(5, 100 - current))
        if randint(1, 100) < inner:
            player["learned"][sk_vnum] += 1
            tprint("You have become better at {}!".format(sk_name))
            player["xp"] += 2 * sk_rating
    else:
        inner = min(30, max(5, current // 2))
        if randint(1, 100) < inner:
            gain = randint(1, 3)
            player["learned"][sk_vnum] = min(100, current + gain)
            tprint("You learn from your mistakes, and your {} improves.".format(sk_name))
            player["xp"] += 2 * sk_rating

    if player["learned"].get(sk_vnum) == 100:
        tprint("{GYou have mastered %s!{x" % sk_name)


# -- Skill lookup -------------------------------------------------------------

def get_skill(entity, sn, is_mob=False):
    """Effective skill score for a player or mob, with status penalties applied
    (cf. 1stMud get_skill in handler.c).

    Args:
        entity (dict): Player or mob instance dict.
        sn (int): Skill GSN constant, or -1 for generic level-based score.
        is_mob (bool): True if entity is a mob instance.

    Returns:
        int: Effective skill percentage, clamped 0-100.
    """
    if is_mob:
        lvl = entity["level"]
        skill = lvl if lvl <= 2 else lvl // 2 + lvl // 3
    else:
        skill = entity["learned"].get(sn, 0) if sn != -1 else entity["level"] * 5 // 2

    if entity.get("daze", 0) > 0:
        is_spell = sn >= 0 and SKILLS.get(sn, {}).get("spell_fun", "spell_null") != "spell_null"
        skill = skill // 2 if is_spell else skill * 2 // 3

    return max(0, min(100, skill))


# -- Defensive checks ----------------------------------------------------------

def check_parry(tr, ch, victim):
    """Check if victim parries ch's strike (cf. 1stMud check_parry in fight.c).

    Args:
        tr: Terminal for printing parry messages.
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

    if victim["is_npc"]:
        act(tr, "{} parries your attack.".format(MOB_DEFS[victim["tpl"]]["short_descr"]))
    else:
        act(tr, "You parry {}'s attack.".format(MOB_DEFS[ch["tpl"]]["short_descr"]))
        check_improve(tr, victim, GSN_PARRY, True, 6)
    return True


def check_shield_block(tr, ch, victim):
    """Check if victim blocks ch's strike with shield (cf. 1stMud check_shield_block in fight.c).

    Args:
        tr: Terminal for printing block messages.
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

    if victim["is_npc"]:
        act(tr, "{} blocks your attack with a shield.".format(MOB_DEFS[victim["tpl"]]["short_descr"]))
    else:
        act(tr, "You block {}'s attack with your shield.".format(MOB_DEFS[ch["tpl"]]["short_descr"]))
        check_improve(tr, victim, GSN_SHIELD_BLOCK, True, 6)
    return True


def check_dodge(tr, ch, victim):
    """Check if victim dodges ch's strike (cf. 1stMud check_dodge in fight.c).

    Args:
        tr: Terminal for printing dodge messages.
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

    if victim["is_npc"]:
        act(tr, "{} dodges your attack.".format(MOB_DEFS[victim["tpl"]]["short_descr"]))
    else:
        act(tr, "You dodge {}'s attack.".format(MOB_DEFS[ch["tpl"]]["short_descr"]))
        check_improve(tr, victim, GSN_DODGE, True, 6)
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


def dam_message(tr, ch, victim, dam, dt, immune, attack_noun=None):
    """Print damage message from ch's attack on victim (cf. 1stMud dam_message in fight.c).

    Single-player: only the player sees messages, as attacker (ch=player) or victim (ch=mob).

    # [PRIMESUD] attack_noun passed explicitly; 1stMud resolves it internally via
    # attack_table[dt - TYPE_HIT].noun, but PrimeSUD uses string-keyed dam_type
    # (from area files) rather than integer offsets, so dt alone is insufficient.

    Args:
        tr: Terminal for printing messages.
        ch (dict): Attacker (player or mob instance).
        victim (dict): Defender (player or mob instance).
        dam (int): Final damage dealt (0 = miss).
        dt (int): Damage type; dt >= TYPE_HIT means physical attack.
        immune (bool): True if victim was fully immune (dam forced to 0 by immunity).
        attack_noun (str or None): Attack display noun (e.g. "slash", "kick"); None = unarmed.
    """
    vs, vp = _damage_verb(dam)
    punct  = _damage_punct(dam)

    if not ch["is_npc"]:
        # 1stMud dam_message: ch is player; message goes to ch (TO_CHAR perspective)
        victim_name = MOB_DEFS[victim["tpl"]]["short_descr"]
        if immune:
            # 1stMud: "... but $N is unaffected." (immune suffix)
            if attack_noun:
                act(tr, "{GYour %s doesn't affect {G%s.{x" % (attack_noun, victim_name))
            else:
                act(tr, "{GYour attack doesn't affect {G%s.{x" % victim_name)
        elif dam == 0:
            # 1stMud: miss message without damage bracket
            if attack_noun:
                act(tr, "{GYour %s misses {G%s.{x" % (attack_noun, victim_name))
            else:
                act(tr, "{GYou miss {G%s.{x" % victim_name)
        elif attack_noun:
            act(tr, "{GYour %s %s {G%s%s {W[{R%d{W]{x" % (attack_noun, vp, victim_name, punct, dam))
        else:
            act(tr, "{GYou %s {G%s%s {W[{R%d{W]{x" % (vs, victim_name, punct, dam))
    else:
        # 1stMud dam_message: ch is mob; message goes to victim (TO_VICT) when victim is player
        ch_name = MOB_DEFS[ch["tpl"]]["short_descr"]
        if immune:
            act(tr, "{RYour body is unaffected by %s's attack.{x" % ch_name)
        elif dam == 0:
            # 1stMud: miss message without damage bracket
            if attack_noun:
                act(tr, "{R%s's %s misses {Ryou.{x" % (ch_name, attack_noun))
            else:
                act(tr, "{R%s misses {Ryou.{x" % ch_name)
        elif attack_noun:
            act(tr, "{R%s's %s %s {Ryou%s {W[{R%d{W]{x" % (ch_name, attack_noun, vp, punct, dam))
        else:
            act(tr, "{R%s %s {Ryou%s {W[{R%d{W]{x" % (ch_name, vp, punct, dam))


def damage(tr, ch, victim, dam, dt, dam_type, show, attack_noun=None):
    """Apply damage to victim from ch; handle combat state, immunity, and death
    (cf. 1stMud damage in fight.c).

    dt >= TYPE_HIT = physical attack (dodge/parry checks apply).
    dt < TYPE_HIT  = skill/spell (no defensive checks).

    Args:
        tr: Terminal for printing messages.
        ch (dict): Attacker (player or mob instance).
        victim (dict): Defender (player or mob instance).
        dam (int): Raw damage before soft-caps and modifiers.
        dt (int): Damage type ID; TYPE_HIT for weapon, skill sn for spells/skills.
        dam_type (int): DAM_* class for immunity checks.
        show (bool): Print dam_message if True (position messages always shown).
        attack_noun (str or None): Attack display noun for dam_message.

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
        # 1stMud: if (is_safe(ch, victim)) return false;
        # [PRIMESUD] skip is_safe (not ported) - safe rooms, service mobs, pet/charm, quest target

        # 1stMud: check_killer(ch, victim);
        # [PRIMESUD] skip check_killer (not ported) - pvp

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
        if check_dodge(tr, ch, victim):
            return False
        # 1stMud: if (check_parry(ch, victim)) return false;
        if check_parry(tr, ch, victim):
            return False
        # 1stMud: if (check_shield_block(ch, victim)) return false;
        if check_shield_block(tr, ch, victim):
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
        dam_message(tr, ch, victim, dam, dt, immune, attack_noun)

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
    victim_name = MOB_DEFS[victim["tpl"]]["short_descr"] if victim["is_npc"] else None

    if pos == "mortal":
        # 1stMud: act("$n is mortally wounded, and will die soon, if not aided.", victim, TO_ROOM)
        #         chprintln(victim, "You are mortally wounded, and will die soon, if not aided.")
        if victim["is_npc"]:
            act(tr, "{} is mortally wounded, and will die soon, if not aided.".format(victim_name))
        else:
            tprint("You are mortally wounded, and will die soon, if not aided.")
    elif pos == "incap":
        # 1stMud: act("$n is incapacitated and will slowly die, if not aided.", victim, TO_ROOM)
        #         chprintln(victim, "You are incapacitated and will slowly die, if not aided.")
        if victim["is_npc"]:
            act(tr, "{} is incapacitated and will slowly die, if not aided.".format(victim_name))
        else:
            tprint("You are incapacitated and will slowly die, if not aided.")
    elif pos == "stunned":
        # 1stMud: act("$n is stunned, but will probably recover.", victim, TO_ROOM)
        #         chprintln(victim, "You are stunned, but will probably recover.")
        if victim["is_npc"]:
            act(tr, "{} is stunned, but will probably recover.".format(victim_name))
        else:
            tprint("You are stunned, but will probably recover.")
    elif pos == "dead":
        # 1stMud: act("$n is DEAD!!", victim, 0, 0, TO_ROOM)
        if victim["is_npc"]:
            act(tr, "{} is DEAD!!".format(victim_name))
        # 1stMud: chprintln(victim, "You have been KILLED!!")
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
        # [PRIMESUD] skip group_gain (single-player; XP handled in raw_kill via _xp_for_kill)

        # 1stMud: if (!IsNPC(victim)) { logf(...); if (!IsQuester...) gain_exp(loss); }
        # [PRIMESUD] skip player death exp loss (not ported)

        # 1stMud: new_wiznet / announce
        # [PRIMESUD] skip wiznet/announce (not ported)

        # 1stMud: if (IsNPC(victim) && HasTriggerMob(victim, TRIG_DEATH)) p_percent_trigger(...)
        # [PRIMESUD] skip TRIG_DEATH (not ported)

        # 1stMud: update_death(victim, ch)
        # [PRIMESUD] skip update_death (not ported)

        # 1stMud: raw_kill(victim, ch)
        if victim["is_npc"]:
            raw_kill(tr, ch, victim["id"], victim, MOB_DEFS[victim["tpl"]])
            _advance_target(ch, world.chars, world.rooms)
        # [PRIMESUD] player death: game loop in primesud.py handles death message and respawn

        # 1stMud: if (ch != victim && !IsNPC(ch) && ...) outlaw flag removal
        # [PRIMESUD] skip outlaw flag removal (not ported)

        # 1stMud: if (!IsNPC(ch) && (corpse = get_obj_list...) ... autoloot/autogold/autosac
        # [PRIMESUD] TODO: autoloot/autogold/autosac not ported

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
        act = victim.get("act_flags", {})
        if (act.get("wimpy") and randint(0, 3) == 0
                and victim["hit"] < victim.get("max_hit", 1) // 5):
            do_flee(tr, victim, [])
        # [PRIMESUD] charmed mob flee requires master tracking (not yet ported)

    # 1stMud: player wimpy auto-flee
    if (not victim.get("is_npc") and victim["hit"] > 0
            and victim["hit"] <= victim.get("wimpy", 0)
            and victim.get("wait", 0) < PULSE_VIOLENCE // 2):
        do_flee(tr, victim, [])

    # 1stMud: tail_chain();
    # [PRIMESUD] skip tail_chain (event queue not ported)

    return True


# -- Core attack: one_hit ------------------------------------------------------

def one_hit(tr, ch, victim, dt=TYPE_UNDEFINED, bonus_damroll=0, secondary=False):
    """One attack from ch against victim (cf. 1stMud one_hit in fight.c).

    Args:
        tr: Terminal for printing combat messages.
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
    thac0 = _get_thac0(ch["level"])
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
        damage(tr, ch, victim, 0, effective_dt, DAM_NONE, show=True, attack_noun=noun)
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
    hit = damage(tr, ch, victim, dam, effective_dt, dam_class, show=True,
                 attack_noun=noun)

    if hit and not ch["is_npc"] and sk_vnum != -1:
        check_improve(tr, ch, sk_vnum, True, 5)

    return hit


def do_kick(tr, ch, args):
    """Kick for player or mob (cf. 1stMud do_kick in fight.c).

    Args:
        tr: Terminal for printing messages.
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
        damage(tr, ch, target, dam, GSN_KICK, DAM_BASH, show=True,
               attack_noun="kick")
        if not ch["is_npc"]:
            check_improve(tr, ch, GSN_KICK, True, 1)
    else:
        # 1stMud: damage(ch, victim, 0, gsn_kick, DAM_BASH, true)
        damage(tr, ch, target, 0, GSN_KICK, DAM_BASH, show=True,
               attack_noun="kick")
        if not ch["is_npc"]:
            check_improve(tr, ch, GSN_KICK, False, 1)
    return None


def do_backstab(tr, ch, args):
    """Backstab a target from behind (cf. 1stMud do_backstab in fight.c).

    Args:
        tr: Terminal for printing messages.
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

    # [PRIMESUD] is_safe not ported
    # [PRIMESUD] kill-stealing check not ported (single-player)

    if ch["equip"].get("wield") is None:
        tprint("You need to wield a weapon to backstab.")
        return None

    if victim["hit"] < victim["max_hit"] // 3:
        act(tr, "%s is hurt and suspicious ... you can't sneak up." % upper(MOB_DEFS[victim["tpl"]]["short_descr"]))
        return None

    # [PRIMESUD] check_killer not ported
    WaitState(ch, SKILLS[GSN_BACKSTAB]["beats"])
    skill_pct = get_skill(ch, GSN_BACKSTAB, ch["is_npc"])
    if randint(1, 100) <= skill_pct or (skill_pct >= 2 and not is_awake(victim)):
        check_improve(tr, ch, GSN_BACKSTAB, True, 1)
        multi_hit(tr, ch, victim, dt=GSN_BACKSTAB)
    else:
        check_improve(tr, ch, GSN_BACKSTAB, False, 1)
        damage(tr, ch, victim, 0, GSN_BACKSTAB, DAM_NONE, show=True,
               attack_noun="backstab")
    return None


def do_kill(tr, player, args):
    """Initiate melee combat with a target (cf. 1stMud do_kill in fight.c).

    Args:
        tr: Terminal (unused, kept for interpret() signature).
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
        idx = pick_from(tr, "Kill whom?", names)
        if idx < 0:
            return
        mob_id = live[idx]

    victim = world.chars[mob_id]

    # 1stMud: if (victim == ch) { "You hit yourself. Ouch!"; multi_hit(ch,ch,...); return; }
    # [PRIMESUD] player can't target self (mob_id lookup is mob-only)

    # [PRIMESUD] is_safe not ported
    # [PRIMESUD] kill-stealing check not ported (single-player)
    # [PRIMESUD] charm master check not ported

    if player.get("pos") == "fighting":
        tprint("You do the best you can!")
        return

    WaitState(player, PULSE_VIOLENCE)
    # [PRIMESUD] check_killer not ported
    multi_hit(tr, player, victim)
    if not args:
        return "kill " + MOB_DEFS[victim["tpl"]].get("keywords", "").split()[0]


def mob_hit(tr, ch, victim, dt=TYPE_UNDEFINED):
    """Full attack sequence for one mob per combat round (cf. 1stMud mob_hit in fight.c).

    Args:
        tr: Terminal for printing combat messages.
        ch (dict): Attacking mob instance dict.
        victim (dict): Player state dict.
        dt (int): Damage type passed from multi_hit (e.g. GSN_BACKSTAB).
    """
    one_hit(tr, ch, victim, dt=dt)
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
        one_hit(tr, ch, victim)
        if victim.get("pos") == "dead":
            return

    if randint(1, 100) < npc_skill // 4:
        one_hit(tr, ch, victim)
        if victim.get("pos") == "dead":
            return

    # [PRIMESUD] OFF_BACKSTAB mob special not yet ported

    # 1stMud: if (ch->wait > 0) return; -- blocks mob specials
    if ch.get("wait", 0) > 0:
        return

    # Off-flag specials (cf. 1stMud mob_hit random switch)
    if ch["off_flags"].get("kick") and randint(0, 8) == 3:
        do_kick(tr, ch, [])


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


def _try_special_move(tr, player, target_inst):
    """Unarmed-only bonus attack with flavour (cf. 1stMud special_move).

    Args:
        tr: Terminal for printing combat messages.
        player (dict): Player state dict.
        target_inst (dict): Target mob instance dict.

    Returns:
        int: Damage dealt (0 if not triggered or player has a weapon).
    """
    if player["equip"].get("wield") is not None:
        return 0
    chance = 20 + (player["dex"] - 10) * 3
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
    check_improve(tr, player, GSN_HAND_TO_HAND, True, 5)
    # show=False: flavor text above already shows dam count; damage() still handles death/state
    damage(tr, player, target_inst, dam, GSN_HAND_TO_HAND, DAM_BASH, show=False)
    return dam


# -- Multi-hit (player's full attack sequence) ---------------------------------

def multi_hit(tr, ch, victim, dt=TYPE_UNDEFINED):
    """Full attack sequence for one combat round (cf. 1stMud multi_hit in fight.c).

    Args:
        tr: Terminal for printing combat messages.
        ch (dict): Attacker (player or mob instance).
        victim (dict): Defender (player or mob instance).
        dt (int): Damage type; TYPE_UNDEFINED for normal round,
            skill GSN (e.g. GSN_BACKSTAB) for skill-initiated attacks.

    Returns:
        bool: True if the victim was killed this round.
    """
    if ch["is_npc"]:
        mob_hit(tr, ch, victim, dt=dt)
        return victim.get("pos") == "dead"

    # Primary
    one_hit(tr, ch, victim, dt=dt)
    if victim.get("pos") == "dead":
        return True

    # Offhand weapon (cf. 1stMud multi_hit WEAR_SECONDARY in fight.c)
    # Specifically, ensures that secondary item is a weapon before allowing hit
    secondary_obj = ch["equip"].get("secondary")
    if secondary_obj is not None and ITEM_DEFS[secondary_obj["vnum"]].get("type") == "weapon":
        one_hit(tr, ch, victim, dt=dt, secondary=True)
        if victim.get("pos") == "dead":
            return True

    # [PRIMESUD] haste extra hit not yet ported (cf. 1stMud fight.c:387-388)

    # Backstab = single hit only (cf. 1stMud multi_hit fight.c:390)
    if dt == GSN_BACKSTAB:
        return False

    # Second attack: skill/2 chance; third: skill/4 chance (cf. 1stMud multi_hit in fight.c)
    if randint(1, 100) < ch["learned"].get(GSN_SECOND_ATTACK, 0) // 2:
        one_hit(tr, ch, victim)
        check_improve(tr, ch, GSN_SECOND_ATTACK, True, 5)
        if victim.get("pos") == "dead":
            return True
    if randint(1, 100) < ch["learned"].get(GSN_THIRD_ATTACK, 0) // 4:
        one_hit(tr, ch, victim)
        check_improve(tr, ch, GSN_THIRD_ATTACK, True, 6)
        if victim.get("pos") == "dead":
            return True

    # 1stMud: if (ch->wait > 0) return; -- blocks specials for players too
    if ch.get("wait", 0) > 0:
        return False

    # [PRIMESUD] Unarmed special move -- no 1stMud equivalent
    if ch["equip"].get("wield") is None:
        _try_special_move(tr, ch, victim)
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
    """Switch player's combat target to the next aggro mob in the room.

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
    "{} hits the ground ... DEAD.",
    "{} splatters blood on your armor.",
    "{} spills its guts all over the floor.",
    "{}'s heart is torn from its chest.",
    "{}'s severed head plops on the ground.",
    "{}'s arm is sliced from its dead body.",
    "{}'s leg is sliced from its dead body.",
    "{}'s head is shattered, and its brains splash all over you.",
    "You hear {}'s death cry.",
]


def _death_cry(tr, tpl):
    """Random death flavour message (cf. 1stMud death_cry in fight.c)."""
    act(tr, _DEATH_CRIES[randint(0, len(_DEATH_CRIES) - 1)].format(tpl["short_descr"]))


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


def make_corpse(inst, tpl):
    """Create an NPC corpse containing mob loot and place it in the room (cf. 1stMud make_corpse in fight.c)."""
    corpse = create_object(I_CORPSE)
    corpse["timer"] = randint(3, 6)
    mob_short = tpl["short_descr"]
    corpse["short_descr"] = "The corpse of " + mob_short
    corpse["description"] = "The corpse of " + mob_short + " is lying here."
    corpse["contents"] = []

    coin = create_money(inst.get("gold", 0), inst.get("silver", 0))
    if coin is not None:
        corpse["contents"].append(coin)

    for obj in list(inst.get("equip", {}).values()) + list(inst.get("inv", [])):
        if obj is None:
            continue
        obj_tpl = ITEM_DEFS[obj["vnum"]]
        flags = item_extra_flags(obj, obj_tpl)
        if flags.get("inventory"):
            continue
        if flags.get("rot_death"):
            obj["timer"] = randint(5, 10)
            set_item_extra_flag(obj, obj_tpl, "rot_death", False)
        if item_extra_flags(obj, obj_tpl).get("vis_death"):
            set_item_extra_flag(obj, obj_tpl, "vis_death", False)
        corpse["contents"].append(obj)

    world.rooms[inst["room"]]["items"].append(corpse)


def raw_kill(tr, player, mob_id, inst, tpl):
    """Handle mob death: award XP, level-up if needed, drop loot, extract mob (cf. 1stMud raw_kill in fight.c).

    Args:
        tr: Terminal for printing kill/loot messages.
        player (dict): Player state dict.
        mob_id (int): ID of the killed mob instance.
        inst (dict): Mob instance dict.
        tpl (dict): Mob template dict.
    """
    xp = _xp_for_kill(player["level"], inst["level"])
    player["xp"] += xp
    tprint("You receive {} experience {}.".format(
        xp, "point" if xp == 1 else "points"))

    while player["xp"] >= player["xp_next"]:
        advance_level(tr, player)

    _death_cry(tr, tpl)

    make_corpse(inst, tpl)

    # [PRIMESUD] save after every kill (1stmud only saves on level up)
    save_world(quiet=True)

    world.rooms[inst["room"]]["mobs"].remove(mob_id)
    del world.chars[mob_id]
    tprint("")


def advance_level(tr, player):
    """Advance player one level: roll HP/MP gains, grant practice and train.

    Args:
        tr: Terminal for printing level-up messages.
        player (dict): Player state dict.
    """
    player["level"] += 1
    player["xp"]    -= player["xp_next"]
    # xp_next stays 1000 (flat cost per level -- 1stMud exp_per_level with 40 pts, human)

    con  = get_curr_stat(player, "con")
    wis  = get_curr_stat(player, "wis")
    int_ = get_curr_stat(player, "int")

    # HP: (con_app.hitp + class_hp_roll) * 9/10, min 2  (cf. 1stMud advance_level in update.c)
    # Two-step roll mirrors 1stMud get_hp_gain: number_range(hp_min,hp_max) -> number_range(result,result+1)
    hp_roll = randint(CLASS_HP_MIN, CLASS_HP_MAX)
    hp_roll = randint(hp_roll, hp_roll + 1)
    add_hp  = max(2, (CON_APP_HITP[con] + hp_roll) * 9 // 10)

    # MP: number_range(2, (2*INT + WIS)//5) * 9/10, min 2  (1stMud advance_level)
    mp_hi  = max(2, (2 * int_ + wis) // 5)
    add_mp = max(2, randint(2, mp_hi) * 9 // 10)

    add_prac = WIS_APP_PRACTICE[wis]

    player["max_hit"]   += add_hp
    player["max_mana"]   += add_mp
    player["hit"]        = player["max_hit"]  # [PRIMESUD] 1stMud only adds to max; full heal for UX
    player["mana"]        = player["max_mana"]
    player["practice"] += add_prac
    player["train"]    += 1

    tprint("You raise a level!!")
    tprint("You gain {} hit {}, {} mana, and {} {}.".format(
        add_hp,  "point" if add_hp  == 1 else "points",
        add_mp,
        add_prac, "practice" if add_prac == 1 else "practices"))
    for _sn, data in SKILL_TABLE:
        if data.get("skill_level") == player["level"]:
            kind = "spell" if data.get("spell_fun", "spell_null") != "spell_null" else "skill"
            tprint("You can now use the {} {}.".format(data["name"], kind))


# -- Size rank (cf. 1stMud SIZE_* in merc.h) ----------------------------------

_SIZE_RANK = {"tiny": 0, "small": 1, "medium": 2, "large": 3, "huge": 4, "giant": 5}


def _get_size(ch):
    """Return numeric size rank for ch (cf. 1stMud ch->size)."""
    if ch["is_npc"]:
        return _SIZE_RANK.get(MOB_DEFS[ch["tpl"]].get("size", "medium"), 2)
    return _SIZE_RANK.get(ch.get("size", "medium"), 2)


def _number_fuzzy(n):
    """Return n-1, n, or n+1 at random (cf. 1stMud number_fuzzy in db.c)."""
    return n + randint(-1, 1)


def _exit_to(exit_val):
    """Return destination vnum from a plain-vnum or dict exit."""
    return exit_val["to"] if isinstance(exit_val, dict) else exit_val


# -- Do_Fun ports from fight.c ------------------------------------------------

def do_murder(tr, ch, args):
    """Attack a target with a yell for help (cf. 1stMud do_murder in fight.c).

    In ROM/Merc MUDs, ``kill`` was the normal PvE command while ``murder``
    was for attacking players -- hence the victim yell and the charm/pet
    guard (charmed mobs can't murder).  By 1stMud both run check_killer,
    so the practical difference is just the yell broadcast and the noprefix
    flag (can't trigger by abbreviation).

    Args:
        tr: Terminal (unused, kept for interpret() signature).
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

    # [PRIMESUD] is_safe not ported
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
    multi_hit(tr, ch, victim)
    return None


def do_suicide(tr, ch, args):
    """Confirm-gated suicide (cf. 1stMud do_suicide in fight.c).

    Args:
        tr: Terminal (unused, kept for interpret() signature).
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
        act(tr, "You use a small knife to slit your own throat!")
        ch["confirm_suicide"] = False
        # [PRIMESUD] player death: set pos to dead, game loop handles respawn
        ch["hit"] = -11
        update_pos(ch)
    return None


def do_berserk(tr, ch, args):
    """Go berserk for combat bonuses (cf. 1stMud do_berserk in fight.c).

    Args:
        tr: Terminal (unused, kept for interpret() signature).
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
        # 1stMud: ch->move /= 2;  [PRIMESUD] move not ported

        ch["hit"] += ch["level"] * 2
        ch["hit"] = min(ch["hit"], ch.get("max_hit", ch["hit"]))

        tprint("Your pulse races as you are consumed by rage!")
        check_improve(tr, ch, GSN_BERSERK, True, 2)

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
        tprint("Your pulse speeds up, but nothing happens.")
        check_improve(tr, ch, GSN_BERSERK, False, 2)
    return None


def do_bash(tr, ch, args):
    """Shield bash a target (cf. 1stMud do_bash in fight.c).

    Args:
        tr: Terminal (unused, kept for interpret() signature).
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
            tprint("They aren't here.")
            return None
        victim = world.chars[victim_id]

    if POS_ORDER[victim.get("pos", "standing")] < POS_ORDER["fighting"]:
        tprint("You'll have to let them get back up first.")
        return None

    if victim is ch:
        tprint("You try to bash your brains out, but fail.")
        return None

    # [PRIMESUD] is_safe not ported
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
        victim_name = MOB_DEFS[victim["tpl"]]["short_descr"] if victim["is_npc"] else "you"
        if victim["is_npc"]:
            act(tr, "You slam into {}, and send them flying!".format(victim_name))
        else:
            tprint("{} sends you sprawling with a powerful bash!".format(
                MOB_DEFS[ch["tpl"]]["short_descr"] if ch["is_npc"] else ch.get("name", "Someone")))
        check_improve(tr, ch, GSN_BASH, True, 1)

        DazeState(victim, 3 * PULSE_VIOLENCE)
        WaitState(ch, SKILLS[GSN_BASH]["beats"])
        victim["pos"] = "resting"
        dam = randint(2, 2 + 2 * ch_size + chance // 20)
        damage(tr, ch, victim, dam, GSN_BASH, DAM_BASH, show=False)
    else:
        damage(tr, ch, victim, 0, GSN_BASH, DAM_BASH, show=False)
        tprint("You fall flat on your face!")
        check_improve(tr, ch, GSN_BASH, False, 1)
        ch["pos"] = "resting"
        WaitState(ch, SKILLS[GSN_BASH]["beats"] * 3 // 2)

    # [PRIMESUD] check_killer not ported
    return None


def do_dirt(tr, ch, args):
    """Kick dirt in opponent's eyes (cf. 1stMud do_dirt in fight.c).

    Args:
        tr: Terminal (unused, kept for interpret() signature).
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
        tprint("They're already been blinded.")
        return None

    if victim is ch:
        tprint("Very funny.")
        return None

    # [PRIMESUD] is_safe not ported
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
        victim_name = MOB_DEFS[victim["tpl"]]["short_descr"] if victim["is_npc"] else "you"
        if victim["is_npc"]:
            act(tr, "{} is blinded by the dirt in their eyes!".format(
                upper(MOB_DEFS[victim["tpl"]]["short_descr"])))
        else:
            tprint("{} kicks dirt in your eyes!".format(
                MOB_DEFS[ch["tpl"]]["short_descr"] if ch["is_npc"] else ch.get("name", "Someone")))
        damage(tr, ch, victim, randint(2, 5), GSN_DIRT, DAM_NONE, show=False)
        if victim["is_npc"]:
            pass  # mob blindness message not shown to player
        else:
            tprint("You can't see a thing!")
        check_improve(tr, ch, GSN_DIRT, True, 2)
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
        damage(tr, ch, victim, 0, GSN_DIRT, DAM_NONE, show=True)
        check_improve(tr, ch, GSN_DIRT, False, 2)
        WaitState(ch, SKILLS[GSN_DIRT]["beats"])

    # [PRIMESUD] check_killer not ported
    return None


def do_trip(tr, ch, args):
    """Trip an opponent (cf. 1stMud do_trip in fight.c).

    Args:
        tr: Terminal (unused, kept for interpret() signature).
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

    # [PRIMESUD] is_safe not ported
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
        victim_name = MOB_DEFS[victim["tpl"]]["short_descr"] if victim["is_npc"] else "you"
        if victim["is_npc"]:
            act(tr, "You trip {} and they go down!".format(victim_name))
        else:
            tprint("{} trips you and you go down!".format(
                MOB_DEFS[ch["tpl"]]["short_descr"] if ch["is_npc"] else ch.get("name", "Someone")))
        check_improve(tr, ch, GSN_TRIP, True, 1)

        DazeState(victim, 2 * PULSE_VIOLENCE)
        WaitState(ch, SKILLS[GSN_TRIP]["beats"])
        victim["pos"] = "resting"
        dam = randint(2, 2 + 2 * v_size)
        damage(tr, ch, victim, dam, GSN_TRIP, DAM_BASH, show=True)
        # TODO: stance trip (if ValidStance && chance-5 check) not ported
    else:
        damage(tr, ch, victim, 0, GSN_TRIP, DAM_BASH, show=True)
        WaitState(ch, SKILLS[GSN_TRIP]["beats"] * 2 // 3)
        check_improve(tr, ch, GSN_TRIP, False, 1)

    # [PRIMESUD] check_killer not ported
    return None


def do_flee(tr, ch, args):
    """Attempt to flee from combat (cf. 1stMud do_flee in fight.c).

    Works for both players and NPCs.

    Args:
        tr: Terminal (unused, kept for interpret() signature).
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
            do_look(tr, ch, [])
        return None

    if not is_npc:
        tprint("PANIC! You couldn't escape!")
    return None


def do_rescue(tr, ch, args):
    """Rescue another character from combat (cf. 1stMud do_rescue in fight.c).

    [PRIMESUD] Single-player: rescuing NPCs is blocked by 1stMud (!IsNPC(ch) &&
    IsNPC(victim) -> "Doesn't need your help!"). Ported for fidelity but largely
    a no-op in single-player.

    Args:
        tr: Terminal (unused, kept for interpret() signature).
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
        check_improve(tr, ch, GSN_RESCUE, False, 1)
        return None

    victim_name = MOB_DEFS[victim["tpl"]]["short_descr"] if victim["is_npc"] else victim.get("name", "someone")
    act(tr, "You rescue {}!".format(victim_name))
    check_improve(tr, ch, GSN_RESCUE, True, 1)

    stop_fighting(fch, both=False)
    stop_fighting(victim, both=False)

    # [PRIMESUD] check_killer not ported
    set_fighting(ch, fch)
    set_fighting(fch, ch)
    return None


def disarm(tr, ch, victim):
    """Remove victim's weapon (cf. 1stMud disarm in fight.c).

    Args:
        tr: Terminal (unused, kept for signature).
        ch (dict): Attacker.
        victim (dict): Defender whose weapon is removed.
    """
    wobj = victim["equip"].get("wield")
    if wobj is None:
        return

    obj_tpl = ITEM_DEFS[wobj["vnum"]]
    flags = item_extra_flags(wobj, obj_tpl)
    if flags.get("noremove"):
        act(tr, "Their weapon won't budge!")
        return

    if victim["is_npc"]:
        act(tr, "You disarm {}!".format(MOB_DEFS[victim["tpl"]]["short_descr"]))
    else:
        tprint("{} DISARMS you and sends your weapon flying!".format(
            MOB_DEFS[ch["tpl"]]["short_descr"] if ch["is_npc"] else ch.get("name", "Someone")))

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


def do_disarm(tr, ch, args):
    """Attempt to disarm opponent's weapon (cf. 1stMud do_disarm in fight.c).

    Args:
        tr: Terminal (unused, kept for interpret() signature).
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
        disarm(tr, ch, victim)
        check_improve(tr, ch, GSN_DISARM, True, 1)
    else:
        tprint("You fail to disarm your opponent.")
        check_improve(tr, ch, GSN_DISARM, False, 1)

    # [PRIMESUD] check_killer not ported
    return None


def do_surrender(tr, ch, args):
    """Surrender to current opponent (cf. 1stMud do_surrender in fight.c).

    Args:
        tr: Terminal (unused, kept for interpret() signature).
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

    mob_name = MOB_DEFS[mob["tpl"]]["short_descr"] if mob["is_npc"] else mob.get("name", "someone")
    act(tr, "You surrender to {}!".format(mob_name))

    stop_fighting(ch, both=True)

    # 1stMud: if (!IsNPC(ch) && IsNPC(mob) && no TRIG_SURR) mob resumes attack
    if not ch["is_npc"] and mob["is_npc"]:
        # [PRIMESUD] TRIG_SURR not ported; mob always ignores surrender
        act(tr, "{} seems to ignore your cowardly act!".format(upper(mob_name)))
        multi_hit(tr, mob, ch)
    return None


def do_slay(tr, ch, args):
    """Immortal instant-kill (cf. 1stMud do_slay in fight.c).

    [PRIMESUD] No immortal system, but ported for completeness. Could be
    used as a debug/GM command.

    Args:
        tr: Terminal (unused, kept for interpret() signature).
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
    act(tr, "You slay {} in cold blood!".format(
        MOB_DEFS[victim["tpl"]]["short_descr"] if victim["is_npc"] else victim.get("name", "them")))

    if victim["is_npc"]:
        raw_kill(tr, ch, mob_id, victim, MOB_DEFS[victim["tpl"]])
    else:
        # [PRIMESUD] player death: set pos to dead
        victim["hit"] = -11
        update_pos(victim)
    return None


def do_sskill(tr, ch, args):
    """Display fighting stance skills (cf. 1stMud do_sskill in fight.c).

    TODO: Stance system not ported. Placeholder prints a message.

    Args:
        tr: Terminal (unused, kept for interpret() signature).
        ch (dict): Acting character.
        args (list): Unused.
    """
    # TODO: stance_table, GetStance, stance_name not ported
    tprint("Fighting stances are not yet available.")
    return None


def do_stance(tr, ch, args):
    """Set or toggle fighting stance (cf. 1stMud do_stance in fight.c).

    TODO: Stance system not ported. Placeholder prints a message.

    Args:
        tr: Terminal (unused, kept for interpret() signature).
        ch (dict): Acting character.
        args (list): Optional stance name.
    """
    # TODO: stance_table, GetStance, SetStance, can_use_stance not ported
    tprint("Fighting stances are not yet available.")
    return None


def do_autostance(tr, ch, args):
    """Set auto-stance on combat start (cf. 1stMud do_autostance in fight.c).

    TODO: Stance system not ported. Placeholder prints a message.

    Args:
        tr: Terminal (unused, kept for interpret() signature).
        ch (dict): Acting character.
        args (list): Optional stance name or 'none'.
    """
    # TODO: stance_table, GetStance, SetStance, STANCE_AUTODROP not ported
    tprint("Fighting stances are not yet available.")
    return None
