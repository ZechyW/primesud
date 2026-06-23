"""Combat rounds, damage resolution, skills, and fight state."""

from actor import get_hitroll, get_damroll, get_armor, get_curr_stat, act, is_awake
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
from urandom import randint
from skills_table import (
    SKILL_TABLE, SKILLS, WEAPON_GSN_MAP,
    GSN_HAND_TO_HAND, GSN_KICK, GSN_PARRY, GSN_DODGE,
    GSN_SECOND_ATTACK, GSN_THIRD_ATTACK,
)
import world
from world import ITEM_DEFS, MOB_DEFS


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
    for ch in list(chars.values()):
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
            stop_fighting(ch, chars, both=False)
            continue

        # 1stMud: if IsAwake(ch) && ch->in_room == victim->in_room: multi_hit else stop_fighting
        if is_awake(ch) and ch["room"] == victim["room"]:
            multi_hit(tr, ch, victim)
        else:
            stop_fighting(ch, chars, both=False)

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
                tr.print("{} screams and attacks!".format(rch_tpl["short_descr"]))
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
        tr.print("{} screams and attacks!".format(rch_tpl["short_descr"]))
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
    _hm = inst.get("hp_max", 1)
    pct = inst["hp"] * 100 // _hm if _hm > 0 else -1
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
            tr.print("You have become better at {}!".format(sk_name))
            player["xp"] += 2 * sk_rating
    else:
        inner = min(30, max(5, current // 2))
        if randint(1, 100) < inner:
            gain = randint(1, 3)
            player["learned"][sk_vnum] = min(100, current + gain)
            tr.print("You learn from your mistakes, and your {} improves.".format(sk_name))
            player["xp"] += 2 * sk_rating

    if player["learned"].get(sk_vnum) == 100:
        tr.print("{GYou have mastered %s!{x" % sk_name)


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

    chance = skill + lv_delta
    if randint(1, 100) >= chance:
        return False

    if victim["is_npc"]:
        act(tr, "{} parries your attack.".format(MOB_DEFS[victim["tpl"]]["short_descr"]))
    else:
        act(tr, "You parry {}'s attack.".format(MOB_DEFS[ch["tpl"]]["short_descr"]))
        check_improve(tr, victim, GSN_PARRY, True, 6)
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

    chance = skill // 2 + victim["level"] - ch["level"]
    if randint(1, 100) >= chance:
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
    [Verified against 1stmud: 23/06/2026]

    Args:
        ch (dict): Character state dict.
    """
    hp = ch["hp"]

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


def dam_message(tr, ch, victim, dam, dt, immune, attack_noun=None):
    """Print damage message from ch's attack on victim (cf. 1stMud dam_message in fight.c).

    Single-player: only the player sees messages, as attacker (ch=player) or victim (ch=mob).

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
        # [PRIMESUD] skip shield_block (not ported)
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
    # [PRIMESUD] skip randomize_damage (minor variance; not ported)

    # 1stMud: if (show) dam_message(ch, victim, dam, dt, immune);
    if show:
        dam_message(tr, ch, victim, dam, dt, immune, attack_noun)

    # 1stMud: if (dam == 0) return false;
    if dam == 0:
        return False

    # 1stMud: victim->hit -= dam;
    victim["hp"] -= dam

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
            tr.print("You are mortally wounded, and will die soon, if not aided.")
    elif pos == "incap":
        # 1stMud: act("$n is incapacitated and will slowly die, if not aided.", victim, TO_ROOM)
        #         chprintln(victim, "You are incapacitated and will slowly die, if not aided.")
        if victim["is_npc"]:
            act(tr, "{} is incapacitated and will slowly die, if not aided.".format(victim_name))
        else:
            tr.print("You are incapacitated and will slowly die, if not aided.")
    elif pos == "stunned":
        # 1stMud: act("$n is stunned, but will probably recover.", victim, TO_ROOM)
        #         chprintln(victim, "You are stunned, but will probably recover.")
        if victim["is_npc"]:
            act(tr, "{} is stunned, but will probably recover.".format(victim_name))
        else:
            tr.print("You are stunned, but will probably recover.")
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
            hp_max = victim.get("hp_max", 1)
            if dam > hp_max // 4:
                tr.print("That really did HURT!")
            if victim["hp"] < hp_max // 4:
                tr.print("You sure are BLEEDING!")

    # 1stMud: if (!IsAwake(victim)) stop_fighting(victim, false);
    if not is_awake(victim):
        stop_fighting(victim, world.chars, both=False)
        # stop_fighting resets pos to "standing"; re-correct from HP
        update_pos(victim)

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
        off = victim.get("off_flags", {})
        if (off.get("wimpy") and randint(0, 3) == 0
                and victim["hp"] < victim.get("hp_max", 1) // 5):
            # TODO: mob flee not ported (do_flee in movement.py is player-only)
            pass
        elif (victim.get("affected_by", {}).get("charm")
              and victim.get("master") is not None):
            # TODO: charmed mob flee not ported
            pass

    # 1stMud: if (!IsNPC(victim) && victim->hit > 0 && victim->hit <= victim->wimpy
    #             && victim->wait < PULSE_VIOLENCE/2) do_function(victim, &do_flee, "");
    # TODO: player wimpy flee not ported (wimpy threshold not in player dict)

    # 1stMud: tail_chain();
    # [PRIMESUD] skip tail_chain (event queue not ported)

    return True


# -- Core attack: one_hit ------------------------------------------------------

def one_hit(tr, ch, victim, bonus_damroll=0, secondary=False):
    """One attack from ch against victim (cf. 1stMud one_hit in fight.c).

    Args:
        tr: Terminal for printing combat messages.
        ch (dict): Attacker (player or mob instance).
        victim (dict): Defender (player or mob instance).
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

    # Attack noun and damage class
    if ch["is_npc"]:
        ch_tpl   = MOB_DEFS[ch["tpl"]]
        dam_type = ch_tpl.get("dam_type", "none")
    else:
        dam_type = wtpl["dam_type"] if wtpl is not None else "none"
        ch_tpl   = None
    attack_noun, dam_class = _attack_info(dam_type)
    # None = unarmed (no noun in dam_message); mirrors 1stMud !armed display branch
    noun = None if dam_type == "none" else attack_noun
    victim_ac = get_armor(victim, _ac_type_for_damage_class(dam_class)) // 10
    if victim_ac < -15:  # soft cap (cf. 1stMud one_hit fight.c)
        victim_ac = -((-victim_ac - 15) // 5) - 15

    # 1stMud: if (number_range(0,19) < thac0 - victim_ac)
    #             return damage(ch, victim, 0, dt, DAM_NONE, true);
    roll = randint(0, 19)
    if roll == 0 or (roll != 19 and roll < thac0 - victim_ac):
        damage(tr, ch, victim, 0, TYPE_HIT, DAM_NONE, show=True, attack_noun=noun)
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

    dam += (get_damroll(ch) + bonus_damroll) * min(100, skill) // 100
    dam = max(1, dam)

    # Position bonus: sleeping victim takes double, non-fighting victim takes 1.5x (cf. 1stMud one_hit in fight.c)
    vpos = POS_ORDER[victim["pos"]]
    if not is_awake(victim):
        dam *= 2
    elif vpos < POS_ORDER["fighting"]:
        dam = dam * 3 // 2

    # 1stMud: return damage(ch, victim, dam, dt, dam_type, true);
    # Soft caps, immunity, dodge/parry all handled inside damage().
    hit = damage(tr, ch, victim, dam, TYPE_HIT, dam_class, show=True,
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
            tr.print("You better leave the martial arts to fighters.")
            return None
        if ch["fighting"] is None:
            tr.print("You aren't fighting anyone.")
            return None
        if ch.get("wait", 0) > 0:
            tr.print("You are still recovering.")
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


def do_kill(tr, player, args):
    if player["fighting"] is not None:
        tr.print("You are already fighting!")
        return
    rs = world.rooms[player["room"]]
    live = rs["mobs"]
    if not live:
        tr.print("Kill whom?")
        return
    if args:
        mob_id = get_char_room(" ".join(args), live, world.chars)
        if mob_id is None:
            tr.print("They aren't here.")
            return
    else:
        names = [MOB_DEFS[world.chars[i]["tpl"]]["short_descr"] for i in live]
        idx = pick_from(tr, "Kill whom?", names)
        if idx < 0:
            return
        mob_id = live[idx]
    multi_hit(tr, player, world.chars[mob_id])
    if not args:
        return "kill " + MOB_DEFS[world.chars[mob_id]["tpl"]].get("keywords", "").split()[0]


def mob_hit(tr, ch, victim):
    """Full attack sequence for one mob per combat round (cf. 1stMud mob_hit in fight.c).

    Args:
        tr: Terminal for printing combat messages.
        ch (dict): Attacking mob instance dict.
        victim (dict): Player state dict.
    """
    one_hit(tr, ch, victim)
    if victim.get("pos") == "dead":
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
        tr.print(line % name if "%s" in line else line)
    # Damage: same unarmed formula as one_hit (cf. 1stMud: skill = 20 + get_weapon_skill)
    skill = 20 + _get_weapon_skill(player, GSN_HAND_TO_HAND)
    lo  = max(1, 1 + 4 * skill // 100)
    hi  = max(lo, 2 * player["level"] * skill // 300)
    dam = max(1, randint(lo, hi))
    last = move[-1] % name if "%s" in move[-1] else move[-1]
    tr.print("%s {W[{R%d{W]{x" % (last, dam))
    check_improve(tr, player, GSN_HAND_TO_HAND, True, 5)
    # show=False: flavor text above already shows dam count; damage() still handles death/state
    damage(tr, player, target_inst, dam, GSN_HAND_TO_HAND, DAM_BASH, show=False)
    return dam


# -- Multi-hit (player's full attack sequence) ---------------------------------

def multi_hit(tr, ch, victim):
    """Full attack sequence for one combat round (cf. 1stMud multi_hit in fight.c).

    Args:
        tr: Terminal for printing combat messages.
        ch (dict): Attacker (player or mob instance).
        victim (dict): Defender (player or mob instance).

    Returns:
        bool: True if the victim was killed this round.
    """
    if ch["is_npc"]:
        mob_hit(tr, ch, victim)
        return victim.get("pos") == "dead"

    # Primary
    one_hit(tr, ch, victim)
    if victim.get("pos") == "dead":
        return True

    # Offhand weapon (cf. 1stMud multi_hit WEAR_SECONDARY in fight.c)
    # Specifically, ensures that secondary item is a weapon before allowing hit
    secondary_obj = ch["equip"].get("secondary")
    if secondary_obj is not None and ITEM_DEFS[secondary_obj["vnum"]].get("type") == "weapon":
        one_hit(tr, ch, victim, secondary=True)
        if victim.get("pos") == "dead":
            return True

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


def stop_fighting(ch, chars, both=False):
    """
    Given character stops fighting its target.
    Optionally make all other characters stop fighting it.
    (cf. 1stMud stop_fighting in fight.c).
    [Verified against 1stmud: 22/06/2026]

    Args:
        ch (dict): Character that stops fighting its target.
        chars (dict): Pass through current world chars state.
        both (bool): If true, all other characters stop fighting `ch`.
    """
    for char in chars.values():
        if char == ch or (both and char["fighting"] == ch["id"]):
            char["fighting"] = None
            # [PRIMESUD] original .are files allow for mobs to have default positions
            # specified, but we haven't ported this yet.
            char["pos"] = "standing"
            # TODO: update_pos is called here in 1stMud, correcting dead/stunned pos.
            #       damage() calls update_pos after stop_fighting to compensate.
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
        stop_fighting(player, mob_instances, both=False)


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
    tr.print("You receive {} experience {}.".format(
        xp, "point" if xp == 1 else "points"))

    while player["xp"] >= player["xp_next"]:
        advance_level(tr, player)

    _death_cry(tr, tpl)

    make_corpse(inst, tpl)

    # [PRIMESUD] save after every kill (1stmud only saves on level up)
    save_world(tr, quiet=True)

    world.rooms[inst["room"]]["mobs"].remove(mob_id)
    del world.chars[mob_id]
    tr.print("")


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

    player["hp_max"]   += add_hp
    player["mp_max"]   += add_mp
    player["hp"]        = player["hp_max"]  # [PRIMESUD] 1stMud only adds to max; full heal for UX
    player["mp"]        = player["mp_max"]
    player["practice"] += add_prac
    player["train"]    += 1

    tr.print("You raise a level!!")
    tr.print("You gain {} hit {}, {} mana, and {} {}.".format(
        add_hp,  "point" if add_hp  == 1 else "points",
        add_mp,
        add_prac, "practice" if add_prac == 1 else "practices"))
    for _sn, data in SKILL_TABLE:
        if data.get("skill_level") == player["level"]:
            kind = "spell" if data.get("spell_fun", "spell_null") != "spell_null" else "skill"
            tr.print("You can now use the {} {}.".format(data["name"], kind))
