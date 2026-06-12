from urandom import randint

from config import (PULSE_VIOLENCE,
                    STR_APP_TODAM, DEX_APP_DEF, CON_APP_HITP, WIS_APP_PRACTICE,
                    CLASS_HP_MIN, CLASS_HP_MAX, THAC0_00, THAC0_MIN, THAC0_PLATEAU,
                    ATTACK_TABLE, DAM_NONE, DAM_BASH)
from world import (ITEM_TEMPLATES, MOB_TEMPLATES, SKILL_TABLE, SKILLS, ROOMS,
                   GSN_HAND_TO_HAND, GSN_KICK, GSN_PARRY)
from player import get_hitroll, get_damroll, get_AC, get_curr_stat, show_prompt, save_char


# ── Helpers ───────────────────────────────────────────────────────────────────

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
    the needle.  [PRIMESUD] 1stMud interpolates straight to level 32 (its cap).

    Args:
        level (int): Character level.

    Returns:
        int: Base THAC0, clamped to minimum -5 after soft-cap.
    """
    eff = min(level, THAC0_PLATEAU)
    # linearly interpolate THAC0 from THAC0_00 (level 1) to THAC0_MIN (level THAC0_PLATEAU)
    t = THAC0_00 + (THAC0_MIN - THAC0_00) * (eff - 1) // (THAC0_PLATEAU - 1)
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
        int: XP gain, randomised ±25% around the base value.
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


def _weapon_skill(player):
    """Return weapon skill info for the player's currently equipped weapon.

    Args:
        player (dict): Player state dict.

    Returns:
        tuple: (sk_vnum (int), learned_pct (int), weapon_tpl (dict or None)).
    """
    wvnum = player["equip"].get("wield")
    if wvnum is not None:
        return GSN_HAND_TO_HAND, player["learned"].get(GSN_HAND_TO_HAND, 20), ITEM_TEMPLATES[wvnum]
    return GSN_HAND_TO_HAND, player["learned"].get(GSN_HAND_TO_HAND, 20), None


# ── Damage flavour ────────────────────────────────────────────────────────────

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


def _mob_condition(inst, tpl):
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
    if pct >= 100: return "{} is in excellent condition.".format(name)
    if pct >= 90:  return "{} has a few scratches.".format(name)
    if pct >= 75:  return "{} has some small wounds and bruises.".format(name)
    if pct >= 50:  return "{} has quite a few wounds.".format(name)
    if pct >= 30:  return "{} has some big nasty wounds and scratches.".format(name)
    if pct >= 15:  return "{} looks pretty hurt.".format(name)
    if pct >= 0:   return "{} is in awful condition.".format(name)
    return "{} is bleeding to death.".format(name)


# ── Wait state ────────────────────────────────────────────────────────────────

def WaitState(ch, pulses):
    """Set skill lag: ch cannot act for `pulses` pulses (cf. 1stMud WaitState).

    Args:
        ch (dict): Character state dict (player or mob instance).
        pulses (int): Lag duration in combat pulses.
    """
    if pulses > ch.get("wait", 0):
        ch["wait"] = pulses


# ── Skill improvement ─────────────────────────────────────────────────────────

def _int_learn(int_stat):
    """Skill improvement rate for an INT stat value (cf. 1stMud int_app[INT].learn).

    Args:
        int_stat (int): Character INT stat.

    Returns:
        int: Improvement rate, range 1–9 over INT 3–25.
    """
    return max(1, int_stat // 3)


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
        tr.print("{{GYou have mastered {}!{{x".format(sk_name))


# ── Skill lookup ─────────────────────────────────────────────────────────────

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
        skill = skill * 2 // 3

    return max(0, min(100, skill))


# ── Defensive checks ──────────────────────────────────────────────────────────

def check_parry(tr, player, mob_inst, mob_is_attacker):
    """Check if the defender parries the attacker's strike (cf. 1stMud check_parry in fight.c).

    Args:
        tr: Terminal for printing parry messages.
        player (dict): Player state dict.
        mob_inst (dict): Mob instance dict (attacker or defender depending on mob_is_attacker).
        mob_is_attacker (bool): True = mob attacks player (player defends);
                                False = player attacks mob (mob defends).

    Returns:
        bool: True if the attack was parried.
    """
    tpl = MOB_TEMPLATES[mob_inst["tpl"]]

    if mob_is_attacker:
        if player["equip"].get("wield") is None:
            return False
        skill    = get_skill(player, GSN_PARRY)
        lv_delta = player["level"] - mob_inst["level"]
    else:
        skill = get_skill(mob_inst, GSN_PARRY, is_mob=True)
        if tpl.get("dam_type", "none") == "none":
            skill //= 2
        lv_delta = mob_inst["level"] - player["level"]

    chance = skill // 2 + lv_delta
    if randint(1, 100) > chance:
        return False

    if mob_is_attacker:
        tr.print("You parry {}'s attack.".format(tpl["short_descr"]))
        check_improve(tr, player, GSN_PARRY, True, 6)
    else:
        tr.print("{} parries your attack.".format(tpl["short_descr"]))
    return True


# ── Core attack: one_hit ──────────────────────────────────────────────────────

def one_hit(tr, player, target_inst, bonus_damroll=0, slot="weapon"):
    """One attack from player against target_inst (cf. 1stMud one_hit in fight.c).

    Args:
        tr: Terminal for printing combat messages.
        player (dict): Player state dict.
        target_inst (dict): Target mob instance dict.
        bonus_damroll (int): Extra damage roll bonus (e.g. from skills).
        slot (str): Equipment slot to attack with ('weapon' or 'offhand').

    Returns:
        int: Damage dealt (0 on miss).
    """
    tpl     = MOB_TEMPLATES[target_inst["tpl"]]
    affects = target_inst["affects"]

    # Weapon / skill
    if slot == "weapon":
        sk_vnum, skill, wtpl = _weapon_skill(player)
    else:
        wvnum = player["equip"].get(slot)
        if wvnum is None:
            return 0
        wtpl    = ITEM_TEMPLATES[wvnum]
        sk_vnum = GSN_HAND_TO_HAND
        skill   = player["learned"].get(GSN_HAND_TO_HAND, 20)

    # THAC0
    mob_hitroll_pen = affects.get("m_hitroll", 0)  # debuff on mob affects its attack, not ours
    thac0 = _get_thac0(player["level"])
    thac0 -= get_hitroll(player) * skill // 100
    thac0 += 5 * (100 - skill) // 100

    victim_ac = get_AC(target_inst) // 10

    # Resolve attack noun and damage class from the table
    _dt_key = wtpl["dam_type"] if wtpl is not None else "none"
    attack_noun, dam_class = _attack_info(_dt_key)
    armed = _dt_key != "none"

    # Hit check
    roll = randint(0, 19)
    if roll == 0 or (roll != 19 and roll < thac0 - victim_ac):
        vs, vp = _damage_verb(0)
        if armed:
            tr.print("Your {} {} {}.".format(attack_noun, vp, tpl["short_descr"]))
        else:
            tr.print("You {} {}.".format(vs, tpl["short_descr"]))
        return 0

    # Mob parry check
    if check_parry(tr, player, target_inst, mob_is_attacker=False):
        return 0

    # Damage
    if wtpl is not None:
        num, size, bonus = wtpl.get("dice", (1, 4, 0))
        dam = (_dice(num, size) + bonus) * skill // 100
    else:
        # Unarmed formula (cf. 1stMud)
        lo = max(1, 1 + 4 * skill // 100)
        hi = max(lo, 2 * player["level"] * skill // 300)
        dam = randint(lo, hi)

    # Damroll (scaled by weapon skill)
    dam += (get_damroll(player) + bonus_damroll) * min(100, skill) // 100

    # Soft damage caps (cf. 1stMud)
    if dam > 35:
        dam = (dam - 35) // 2 + 35
    if dam > 80:
        dam = (dam - 80) // 2 + 80

    dam = max(1, dam)
    target_inst["hp"] = max(0, target_inst["hp"] - dam)

    vs, vp = _damage_verb(dam)
    punct = _damage_punct(dam)
    if armed:
        tr.print("Your {} {} {}{} [{}]".format(attack_noun, vp, tpl["short_descr"], punct, dam))
    else:
        tr.print("You {} {}{} [{}]".format(vs, tpl["short_descr"], punct, dam))

    check_improve(tr, player, sk_vnum, True, 5)
    return dam


def _mob_one_hit(tr, mob_inst, player):
    """One attack from mob against player (cf. 1stMud one_hit in fight.c, NPC side).

    Args:
        tr: Terminal for printing combat messages.
        mob_inst (dict): Attacking mob instance dict.
        player (dict): Player state dict.

    Returns:
        int: Damage dealt (0 on miss or parry).
    """
    tpl     = MOB_TEMPLATES[mob_inst["tpl"]]
    affects = mob_inst["affects"]

    # Mobs fight at full natural skill (100)
    SKILL = 100

    mob_hitroll = get_hitroll(mob_inst) + affects.get("m_hitroll", 0)
    thac0 = _get_thac0(mob_inst["level"])
    thac0 -= mob_hitroll * SKILL // 100

    player_ac = get_AC(player) // 10

    attack_noun, dam_class = _attack_info(tpl.get("dam_type", "none"))

    roll = randint(0, 19)
    if roll == 0 or (roll != 19 and roll < thac0 - player_ac):
        tr.print("{}'s {} misses you.".format(tpl["short_descr"], attack_noun))
        return 0

    # Defensive checks (player skills)
    if check_parry(tr, player, mob_inst, mob_is_attacker=True):
        return 0

    # Damage
    num, size, bonus = tpl["damage"]
    dam = _dice(num, size) + bonus
    dam += get_damroll(mob_inst) * SKILL // 100

    if dam > 35:
        dam = (dam - 35) // 2 + 35
    if dam > 80:
        dam = (dam - 80) // 2 + 80

    dam = max(1, dam)
    player["hp"] = max(0, player["hp"] - dam)

    _, vp = _damage_verb(dam)
    punct = _damage_punct(dam)
    tr.print("{}'s {} {} you{} [{}]".format(tpl["short_descr"], attack_noun, vp, punct, dam))

    if dam > player["hp_max"] // 4:
        tr.print("That really did HURT!")
    if player["hp"] < player["hp_max"] // 4:
        tr.print("You sure are BLEEDING!")

    return dam


def do_kick(tr, ch, args, room_state, mob_instances):
    """Kick for player or mob (cf. 1stMud do_kick in fight.c).

    Args:
        tr: Terminal for printing messages.
        ch (dict): Acting character (player or mob instance).
        args (list): Command arguments (unused).
        room_state (dict): Room state mapping room ID → room state dict.
        mob_instances (dict): Mob instance mapping mob ID → mob instance dict.
    """
    if ch["is_npc"]:
        target = ch["fighting"]   # player dict, set by set_fighting
        if target is None:
            return None
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
        target    = mob_instances[target_id]

    if ch["is_npc"]:
        skill_pct = ch["level"] if ch["level"] <= 2 else ch["level"] // 2 + ch["level"] // 3
    else:
        skill_pct = ch["learned"].get(GSN_KICK, 0)
    WaitState(ch, SKILLS[GSN_KICK]["beats"])

    if skill_pct > randint(1, 100):
        dam = randint(1, max(1, ch["level"]))
        target["hp"] = max(0, target["hp"] - dam)
        _, vp  = _damage_verb(dam)
        punct  = _damage_punct(dam)
        if ch["is_npc"]:
            tr.print("{} kicks you{} [{}]".format(MOB_TEMPLATES[ch["tpl"]]["short_descr"], punct, dam))
        else:
            tpl = MOB_TEMPLATES[target["tpl"]]
            tr.print("Your kick {} {}{} [{}]".format(vp, tpl["short_descr"], punct, dam))
            check_improve(tr, ch, GSN_KICK, True, 1)
            if target["hp"] == 0:
                raw_kill(tr, ch, target_id, target, tpl, room_state, mob_instances)
                _advance_target(ch, mob_instances, room_state)
    else:
        if ch["is_npc"]:
            tr.print("{}'s kick misses you.".format(MOB_TEMPLATES[ch["tpl"]]["short_descr"]))
        else:
            tpl = MOB_TEMPLATES[target["tpl"]]
            tr.print("Your kick misses {}.".format(tpl["short_descr"]))
            check_improve(tr, ch, GSN_KICK, False, 1)
    return None


def mob_hit(tr, mob_inst, player, room_state, mob_instances):
    """Full attack sequence for one mob per combat round (cf. 1stMud mob_hit).

    Args:
        tr: Terminal for printing combat messages.
        mob_inst (dict): Attacking mob instance dict.
        player (dict): Player state dict.
        room_state (dict): Room state mapping room ID → room state dict.
        mob_instances (dict): Mob instance mapping mob ID → mob instance dict.
    """
    _mob_one_hit(tr, mob_inst, player)
    if player["hp"] == 0:
        return

    # Second and third attacks: level-derived chance (cf. 1stMud gsn_second/third_attack)
    skill = min(100, mob_inst["level"] * 12 + 20)
    if randint(1, 100) <= skill // 2:
        _mob_one_hit(tr, mob_inst, player)
        if player["hp"] == 0:
            return

    if randint(1, 100) <= skill // 4:
        _mob_one_hit(tr, mob_inst, player)
        if player["hp"] == 0:
            return

    # Off-flag specials (cf. 1stMud mob_hit random switch)
    if mob_inst["off_flags"].get("kick") and randint(0, 8) == 3:
        do_kick(tr, mob_inst, [], room_state, mob_instances)


# ── Special unarmed moves [PRIMESUD] (cf. 1stMud special_move for inspiration) ─

_SPECIAL_MOVES = [
    (
        "You pull your hands into your waist then snap them into {}'s stomach.",
        "{} doubles over in agony, and falls to the ground gasping for breath.",
    ),
    (
        "You spin in a low circle, catching {} behind its ankle.",
        "{} crashes to the ground, stunned.",
    ),
    (
        "You roll between {}'s legs and flip to your feet.",
        "You spin around and smash your elbow into the back of {}'s head.",
        "{} falls to the ground, stunned.",
    ),
    (
        "You somersault over {}'s head and land lightly on your toes.",
        "You roll back onto your shoulders and kick both feet into {}'s back.",
        "{} falls to the ground, stunned.",
        "You flip back up to your feet.",
    ),
    (
        "You grab {} by the waist and hoist it above your head.",
        "{} crashes to the ground, stunned.",
    ),
    (
        "You grab {} by the head and slam its face into your knee.",
        "{} crashes to the ground, stunned.",
    ),
    (
        "You duck under {}'s attack and pound your fist into its stomach.",
        "{} doubles over in agony.",
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
    tpl  = MOB_TEMPLATES[target_inst["tpl"]]
    name = tpl["short_descr"]
    move = _SPECIAL_MOVES[randint(0, len(_SPECIAL_MOVES) - 1)]
    for line in move[:-1]:
        tr.print(line.format(name))
    # Damage: same unarmed formula as one_hit
    skill = player["learned"].get(GSN_HAND_TO_HAND, 20)
    lo  = max(1, 1 + 4 * skill // 100)
    hi  = max(lo, 2 * player["level"] * skill // 300)
    dam = max(1, randint(lo, hi))
    target_inst["hp"] = max(0, target_inst["hp"] - dam)
    tr.print("{} [{}]".format(move[-1].format(name), dam))
    check_improve(tr, player, GSN_HAND_TO_HAND, True, 5)
    return dam


# ── Multi-hit (player's full attack sequence) ─────────────────────────────────

def multi_hit(tr, player, target_inst):
    """Full attack sequence for one combat round (cf. 1stMud multi_hit in fight.c).

    Args:
        tr: Terminal for printing combat messages.
        player (dict): Player state dict.
        target_inst (dict): Target mob instance dict.

    Returns:
        bool: True if the target was killed this round.
    """
    # Primary
    one_hit(tr, player, target_inst)
    if target_inst["hp"] == 0:
        return True

    # [PRIMESUD] Unarmed special move — no 1stMud equivalent
    if player["equip"].get("wield") is None:
        _try_special_move(tr, player, target_inst)
        if target_inst["hp"] == 0:
            return True

    # Offhand weapon
    offhand = player["equip"].get("offhand")
    if offhand is not None and ITEM_TEMPLATES[offhand].get("type") == "weapon":
        one_hit(tr, player, target_inst, slot="offhand")
        if target_inst["hp"] == 0:
            return True

    return False


# ── Combat state ──────────────────────────────────────────────────────────────

def set_fighting(tr, player, mob_id, mob_instances, room_state):
    """Enter combat: engage a single mob against the player (cf. 1stMud set_fighting in fight.c).

    Args:
        tr: Terminal for printing combat messages.
        player (dict): Player state dict.
        mob_id (int): ID of the mob to engage.
        mob_instances (dict): Mob instance mapping mob ID → mob instance dict.
        room_state (dict): Room state mapping room ID → room state dict.
    """
    inst = mob_instances[mob_id]
    tpl  = MOB_TEMPLATES[inst["tpl"]]
    inst["state"]    = "aggro"
    inst["fighting"] = player
    player["fighting"] = mob_id
    player["pos"]      = "fighting"


def check_assist(tr, player, attacked_id, mob_instances, room_state):
    """Let idle room mobs join combat against the player (cf. 1stMud check_assist in fight.c).

    Checks every idle mob in the room; those whose off_flags qualify jump in.
    Triggers: assist_all (always), assist_vnum (same template), assist_race
    (same race field), or matching non-zero group value.

    Args:
        tr: Terminal for printing combat messages.
        player (dict): Player state dict.
        attacked_id (int): ID of the mob the player is currently attacking.
        mob_instances (dict): Mob instance mapping mob ID → mob instance dict.
        room_state (dict): Room state mapping room ID → room state dict.
    """
    rs            = room_state[player["room"]]
    attacked_inst = mob_instances[attacked_id]
    attacked_tpl  = MOB_TEMPLATES[attacked_inst["tpl"]]

    for mid in rs["mobs"]:
        if mid == attacked_id:
            continue
        inst = mob_instances[mid]
        if inst["state"] == "aggro":
            continue
        tpl = MOB_TEMPLATES[inst["tpl"]]
        if tpl.get("passive"):
            continue

        off = tpl.get("off_flags", {})
        grp = tpl.get("group")
        if (off.get("assist_all")
                or (off.get("assist_vnum") and inst["tpl"] == attacked_inst["tpl"])
                or (off.get("assist_race")
                    and tpl.get("race") == attacked_tpl.get("race"))
                or (grp and grp == attacked_tpl.get("group"))):
            inst["state"]    = "aggro"
            inst["fighting"] = player
            tr.print("{} screams and attacks!".format(
                tpl["short_descr"]))


def stop_fighting(player, mob_instances):
    """End combat: reset aggro mobs to idle, clear player target (cf. 1stMud stop_fighting in fight.c).

    Args:
        player (dict): Player state dict.
        mob_instances (dict): Mob instance mapping mob ID → mob instance dict.
    """
    for inst in mob_instances.values():
        if inst["state"] == "aggro":
            inst["state"]    = "idle"
            inst["fighting"] = None
            inst["affects"]  = {}
    player["fighting"] = None
    player["pos"]      = "standing"


def _advance_target(player, mob_instances, room_state):
    """Switch player's combat target to the next aggro mob in the room.

    Args:
        player (dict): Player state dict.
        mob_instances (dict): Mob instance mapping mob ID → mob instance dict.
        room_state (dict): Room state mapping room ID → room state dict.
    """
    rs      = room_state[player["room"]]
    next_id = None
    for mid in rs["mobs"]:
        if mob_instances[mid]["state"] == "aggro":
            next_id = mid
            break
    if next_id is not None:
        player["fighting"] = next_id
    else:
        stop_fighting(player, mob_instances)


# ── Violence update (called every PULSE_VIOLENCE) ─────────────────────────────

def violence_update(tr, player, mob_instances, room_state):
    """One combat pulse: player attacks, then all aggro mobs counter-attack (cf. 1stMud violence_update in fight.c).

    Args:
        tr: Terminal for printing combat messages.
        player (dict): Player state dict.
        mob_instances (dict): Mob instance mapping mob ID → mob instance dict.
        room_state (dict): Room state mapping room ID → room state dict.

    Returns:
        bool or None: True if the player died this pulse (caller should show
            the respawn room); None otherwise.
    """
    target_id = player["fighting"]
    if target_id is None:
        return

    target = mob_instances.get(target_id)
    if target is None:
        stop_fighting(player, mob_instances)
        return

    tpl = MOB_TEMPLATES[target["tpl"]]

    # Decrement wait/daze for player and all room mobs
    player["wait"] = max(0, player["wait"] - PULSE_VIOLENCE)
    rs = room_state[player["room"]]
    for mid in rs["mobs"]:
        inst = mob_instances[mid]
        inst["wait"] = max(0, inst["wait"] - PULSE_VIOLENCE)
        inst["daze"] = max(0, inst["daze"] - PULSE_VIOLENCE)

    # Player's attack turn
    if player["wait"] <= 0:
        killed = multi_hit(tr, player, target)
        if killed:
            raw_kill(tr, player, target_id, target, tpl, room_state, mob_instances)
            _advance_target(player, mob_instances, room_state)
        else:
            check_assist(tr, player, target_id, mob_instances, room_state)

    # Mob counter-attacks
    for mob_id in list(rs["mobs"]):
        mob_inst = mob_instances[mob_id]
        if mob_inst["state"] != "aggro":
            continue
        if mob_inst["wait"] > 0:
            continue
        mob_tpl = MOB_TEMPLATES[mob_inst["tpl"]]
        if mob_tpl.get("passive"):
            continue

        mob_hit(tr, mob_inst, player, room_state, mob_instances)

        # Tick debuff timers
        affects = mob_inst["affects"]
        for key in list(affects.keys()):
            if key.endswith("_t"):
                affects[key] -= 1
                if affects[key] <= 0:
                    base = key[:-2]
                    affects.pop(key, None)
                    affects.pop(base, None)

        if player["hp"] == 0:
            stop_fighting(player, mob_instances)
            return True

    if player["fighting"] is not None:
        fid  = player["fighting"]
        finst = mob_instances[fid]
        tr.print(_mob_condition(finst, MOB_TEMPLATES[finst["tpl"]]))
        tr.print("")



# ── Death / Victory ───────────────────────────────────────────────────────────

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
    tr.print(_DEATH_CRIES[randint(0, len(_DEATH_CRIES) - 1)].format(tpl["short_descr"]))


def raw_kill(tr, player, mob_id, inst, tpl, room_state, mob_instances):
    """Handle mob death: award XP, level-up if needed, drop loot, extract mob (cf. 1stMud raw_kill in fight.c).

    Args:
        tr: Terminal for printing kill/loot messages.
        player (dict): Player state dict.
        mob_id (int): ID of the killed mob instance.
        inst (dict): Mob instance dict.
        tpl (dict): Mob template dict.
        room_state (dict): Room state mapping room ID → room state dict.
        mob_instances (dict): Mob instance mapping mob ID → instance dict.
    """
    xp = _xp_for_kill(player["level"], inst["level"])
    player["xp"] += xp
    tr.print("You receive {} experience {}.".format(
        xp, "point" if xp == 1 else "points"))

    while player["xp"] >= player["xp_next"]:
        advance_level(tr, player)

    _death_cry(tr, tpl)

    # [PRIMESUD] save after every kill (1stmud only saves on level up)
    save_char(player, room_state, mob_instances)

    for item_vnum, chance in tpl["loot"]:
        if randint(1, 100) <= chance:
            player["inv"].append(item_vnum)
            tr.print("Found: {}".format(ITEM_TEMPLATES[item_vnum]["short_descr"]))

    room_state[inst["room"]]["mobs"].remove(mob_id)
    del mob_instances[mob_id]
    tr.print("")


def advance_level(tr, player):
    """Advance player one level: roll HP/MP gains, grant practice and train.

    Args:
        tr: Terminal for printing level-up messages.
        player (dict): Player state dict.
    """
    player["level"] += 1
    player["xp"]    -= player["xp_next"]
    # xp_next stays 1000 (flat cost per level — 1stMud exp_per_level with 40 pts, human)

    con  = min(25, max(0, player["con"]))
    wis  = min(25, max(0, player["wis"]))
    int_ = min(25, max(0, player["int"]))

    # HP: (con_app.hitp + class_hp_roll) * 9/10, min 2  (1stMud advance_level)
    hp_roll = randint(CLASS_HP_MIN, CLASS_HP_MAX + 1)
    add_hp  = max(2, (CON_APP_HITP[con] + hp_roll) * 9 // 10)

    # MP: number_range(2, (2*INT + WIS)//5) * 9/10, min 2  (1stMud advance_level)
    mp_hi  = max(2, (2 * int_ + wis) // 5)
    add_mp = max(2, randint(2, mp_hi) * 9 // 10)

    add_prac = WIS_APP_PRACTICE[wis]

    player["hp_max"]   += add_hp
    player["mp_max"]   += add_mp
    player["hp"]        = player["hp_max"]
    player["mp"]        = player["mp_max"]
    player["practice"] += add_prac
    player["train"]    += 1

    tr.print("You raise a level!!")
    tr.print("You gain {} hit {}, {} mana, and {} {}.".format(
        add_hp,  "point" if add_hp  == 1 else "points",
        add_mp,
        add_prac, "practice" if add_prac == 1 else "practices"))
    for _sn, data in SKILL_TABLE:
        if data.get("min_level") == player["level"]:
            kind = "spell" if data["type"] == "spell" else "skill"
            tr.print("You can now use the {} {}.".format(data["name"], kind))
