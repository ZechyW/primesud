from urandom import randint
from hpprime import eval as ppleval

from config import DEATH_MSG_DELAY, PULSE_VIOLENCE
from world import (
    ITEM_TEMPLATES, MOB_TEMPLATES, SKILLS, ROOMS,
    R_VILLAGE_SQUARE,
    GSN_HAND_TO_HAND, GSN_KICK, GSN_PARRY,
    STR_APP_TODAM, DEX_APP_DEF, CON_APP_HITP, WIS_APP_PRACTICE,
    CLASS_HP_MIN, CLASS_HP_MAX,
    THAC0_00, THAC0_32,
)
from player import get_hitroll, get_damroll, get_AC, show_prompt


# ── Helpers ───────────────────────────────────────────────────────────────────

def _dice(num, size):
    total = 0
    for _ in range(num):
        total += randint(1, size)
    return total


def _interpolate(level, lo, hi):
    return lo + (hi - lo) * (level - 1) // 31


def _get_thac0(level):
    """Base THAC0 for a given level (classless curve, before hitroll/skill adj)."""
    t = _interpolate(level, THAC0_00, THAC0_32)
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
    """Return (sk_vnum, learned_pct, weapon_tpl_or_None) for current main weapon."""
    wvnum = player["equip"].get("weapon")
    if wvnum is not None:
        return GSN_HAND_TO_HAND, player["learned"].get(GSN_HAND_TO_HAND, 20), ITEM_TEMPLATES[wvnum]
    return GSN_HAND_TO_HAND, player["learned"].get(GSN_HAND_TO_HAND, 20), None


# ── Damage flavour ────────────────────────────────────────────────────────────

def _damage_verb(dmg):
    if dmg == 0:     return ("miss",                                 "misses")
    if dmg <= 4:     return ("scratch",                              "scratches")
    if dmg <= 8:     return ("graze",                                "grazes")
    if dmg <= 12:    return ("hit",                                  "hits")
    if dmg <= 16:    return ("injure",                               "injures")
    if dmg <= 20:    return ("wound",                                "wounds")
    if dmg <= 24:    return ("maul",                                 "mauls")
    if dmg <= 28:    return ("decimate",                             "decimates")
    if dmg <= 32:    return ("devastate",                            "devastates")
    if dmg <= 36:    return ("maim",                                 "maims")
    if dmg <= 40:    return ("MUTILATE",                             "MUTILATES")
    if dmg <= 44:    return ("DISEMBOWEL",                           "DISEMBOWELS")
    if dmg <= 48:    return ("DISMEMBER",                            "DISMEMBERS")
    if dmg <= 52:    return ("MASSACRE",                             "MASSACRES")
    if dmg <= 56:    return ("MANGLE",                               "MANGLES")
    if dmg <= 60:    return ("*** DEMOLISH ***",                     "*** DEMOLISHES ***")
    if dmg <= 75:    return ("*** DEVASTATE ***",                    "*** DEVASTATES ***")
    if dmg <= 100:   return ("=== OBLITERATE ===",                   "=== OBLITERATES ===")
    if dmg <= 125:   return (">>> ANNIHILATE <<<",                   ">>> ANNIHILATES <<<")
    if dmg <= 150:   return ("<<< ERADICATE >>>",                    "<<< ERADICATES >>>")
    if dmg <= 185:   return ("***** PULVERIZE *****",                "***** PULVERIZES *****")
    if dmg <= 220:   return ("-=- VAPORIZE -=-",                     "-=- VAPORIZES -=-")
    if dmg <= 275:   return ("<-==-> ATOMIZE <-==->",                "<-==-> ATOMIZES <-==->")
    if dmg <= 315:   return ("<-:-> ASPHYXIATE <-:->",               "<-:-> ASPHYXIATES <-:->")
    if dmg <= 390:   return ("<-*-> RAVAGE <-*->",                   "<-*-> RAVAGES <-*->")
    if dmg <= 435:   return ("<>*<> FISSURE <>*<>",                  "<>*<> FISSURES <>*<>")
    if dmg <= 500:   return ("<*><*> LIQUIDATE <*><*>",              "<*><*> LIQUIDATES <*><*>")
    if dmg <= 590:   return ("<*><*><*> EVAPORATE <*><*><*>",        "<*><*><*> EVAPORATES <*><*><*>")
    if dmg <= 650:   return ("<-=-> SUNDER <-=->",                   "<-=-> SUNDERS <-=->")
    if dmg <= 790:   return ("<=-=><=-=> TEAR INTO <=-=><=-=>",      "<=-=><=-=> TEARS INTO <=-=><=-=>")
    if dmg <= 880:   return ("<->*<=> WASTE <=>*<->",                "<->*<=> WASTES <=>*<->")
    if dmg <= 960:   return ("<-+-><-*-> CREMATE <-*-><-+->",        "<-+-><-*-> CREMATES <-*-><-+->")
    if dmg <= 1040:  return ("<*><*><*><*> ANNIHILATE <*><*><*><*>", "<*><*><*><*> ANNIHILATES <*><*><*><*>")
    if dmg <= 3000:  return ("inflict UNSPEAKABLE PAIN on",          "inflicts UNSPEAKABLE PAIN on")
    if dmg <= 6000:  return ("inflict UNTHINKABLE PAIN on",          "inflicts UNTHINKABLE PAIN on")
    if dmg <= 9000:  return ("inflict UNIMAGINABLE PAIN on",         "inflicts UNIMAGINABLE PAIN on")
    if dmg <= 12000: return ("inflict UNBELIEVABLE PAIN on",         "inflicts UNBELIEVABLE PAIN on")
    return ("do TOTALLY, UTTERLY, INCONCEIVABLE things to",
            "does TOTALLY, UTTERLY, INCONCEIVABLE things to")


def _damage_punct(dmg):
    if dmg <= 250:  return "."
    if dmg <= 1000: return "!"
    if dmg <= 3000: return "!!"
    if dmg <= 5000: return "!!!"
    return "!!!!"


def _mob_condition(inst, tpl):
    _hm = inst.get("hp_max", 1)
    pct = inst["hp"] * 100 // _hm if _hm > 0 else -1
    name = tpl["name"]
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
    """Set skill lag: ch cannot act for `pulses` pulses (cf. 1stMud WaitState)."""
    if pulses > ch.get("wait", 0):
        ch["wait"] = pulses


# ── Skill improvement ─────────────────────────────────────────────────────────

def _int_learn(int_stat):
    # Approximates 1stMud int_app[INT].learn (range 1–9 over INT 3–25)
    return max(1, int_stat // 3)


def check_improve(tr, player, sk_vnum, success):
    # cf. 1stMud check_improve (skills.c). rating/multiplier per skill in world.py.
    # success=True: used correctly, chance of +1 (harder near 100).
    # success=False: missed/failed, learn-from-mistakes, faster at low skill.
    current = player["learned"].get(sk_vnum, 0)
    if current <= 0 or current >= 100:
        return

    sk        = SKILLS[sk_vnum]
    sk_rating = sk.get("rating", 1)
    sk_mult   = sk.get("multiplier", 1)

    chance = 10 * _int_learn(player.get("int", 10))
    chance //= max(1, sk_mult * sk_rating * 4)
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
        tr.print("You have mastered {}!".format(sk_name))


# ── Defensive checks (player defending against mob attack) ────────────────────

def check_parry(tr, player, mob_inst):
    if player["equip"].get("weapon") is None:
        return False
    skill = player["learned"].get(GSN_PARRY, 0)
    if skill > 0 and randint(1, 100) <= skill // 2:
        tpl = MOB_TEMPLATES[mob_inst["tpl"]]
        tr.print("You parry {}'s attack.".format(tpl["name"]))
        check_improve(tr, player, GSN_PARRY, True)
        return True
    return False


# ── Core attack: one_hit ──────────────────────────────────────────────────────

def one_hit(tr, player, target_inst, bonus_damroll=0, slot="weapon"):
    """One attack from player against target_inst. Returns damage dealt."""
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

    # Hit check
    roll = randint(0, 19)
    if roll == 0 or (roll != 19 and roll < thac0 - victim_ac):
        vs, _ = _damage_verb(0)
        tr.print("You {} {}.".format(vs, tpl["name"]))
        check_improve(tr, player, sk_vnum, False)
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

    weapon_name = wtpl["name"] if wtpl else "fist"
    vs, vp = _damage_verb(dam)
    punct = _damage_punct(dam)
    tr.print("Your {} {} {}{} [{}]".format(weapon_name, vp, tpl["name"], punct, dam))

    check_improve(tr, player, sk_vnum, True)
    return dam


def _mob_one_hit(tr, mob_inst, player):
    """One attack from mob against player. Returns damage dealt."""
    tpl     = MOB_TEMPLATES[mob_inst["tpl"]]
    affects = mob_inst["affects"]

    # Mobs fight at full natural skill (100)
    SKILL = 100

    mob_hitroll = get_hitroll(mob_inst) + affects.get("m_hitroll", 0)
    thac0 = _get_thac0(mob_inst["level"])
    thac0 -= mob_hitroll * SKILL // 100

    player_ac = get_AC(player) // 10

    roll = randint(0, 19)
    if roll == 0 or (roll != 19 and roll < thac0 - player_ac):
        _, vp = _damage_verb(0)
        tr.print("{} {} you.".format(tpl["name"], vp))
        return 0

    # Defensive checks (player skills)
    if check_parry(tr, player, mob_inst):
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
    tr.print("{} {} you{} [{}]".format(tpl["name"], vp, punct, dam))
    return dam


def do_kick(tr, ch, args, room_state, mob_instances):
    """Kick for player or mob (cf. 1stMud do_kick in fight.c)."""
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

    skill_pct = ch["learned"].get(GSN_KICK, 0)
    WaitState(ch, SKILLS[GSN_KICK]["beats"])

    if skill_pct > randint(1, 100):
        dam = randint(1, max(1, ch["level"]))
        target["hp"] = max(0, target["hp"] - dam)
        _, vp  = _damage_verb(dam)
        punct  = _damage_punct(dam)
        if ch["is_npc"]:
            tr.print("{} kicks you{} [{}]".format(ch["name"], punct, dam))
        else:
            tpl = MOB_TEMPLATES[target["tpl"]]
            tr.print("Your kick {} {}{} [{}]".format(vp, tpl["name"], punct, dam))
            check_improve(tr, ch, GSN_KICK, True)
            if target["hp"] == 0:
                raw_kill(tr, ch, target_id, target, tpl, room_state)
                _advance_target(ch, mob_instances, room_state)
    else:
        if ch["is_npc"]:
            tr.print("{}'s kick misses you.".format(ch["name"]))
        else:
            tpl = MOB_TEMPLATES[target["tpl"]]
            tr.print("Your kick misses {}.".format(tpl["name"]))
            check_improve(tr, ch, GSN_KICK, False)
    return None


def mob_hit(tr, mob_inst, player, room_state, mob_instances):
    """Full attack sequence for one mob per combat round (cf. 1stMud mob_hit)."""
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
    """Unarmed-only bonus attack with flavour (cf. 1stMud special_move)."""
    if player["equip"].get("weapon") is not None:
        return 0
    chance = 20 + (player["dex"] - 10) * 3
    if randint(1, 100) > chance:
        return 0
    tpl  = MOB_TEMPLATES[target_inst["tpl"]]
    name = tpl["name"]
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
    check_improve(tr, player, GSN_HAND_TO_HAND, True)
    return dam


# ── Multi-hit (player's full attack sequence) ─────────────────────────────────

def multi_hit(tr, player, target_inst):
    """Full attack sequence for one combat round. Returns True if target killed."""
    # Primary
    one_hit(tr, player, target_inst)
    if target_inst["hp"] == 0:
        return True

    # [PRIMESUD] Unarmed special move — no 1stMud equivalent
    if player["equip"].get("weapon") is None:
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
    """Enter combat: mark all non-passive room mobs aggro, set player target."""
    rs = room_state[player["room"]]
    for mid in rs["mobs"]:
        inst = mob_instances[mid]
        tpl  = MOB_TEMPLATES[inst["tpl"]]
        if inst["state"] != "dead" and not tpl.get("passive"):
            inst["state"]   = "aggro"
            inst["fighting"] = player
            if mid == mob_id:
                tr.print("--- {} attacks! ---".format(tpl["name"]))
            else:
                tr.print("--- {} joins the fight! ---".format(tpl["name"]))
    player["fighting"] = mob_id


def stop_fighting(player, mob_instances):
    """End combat: reset aggro mobs to idle, clear player target."""
    for inst in mob_instances.values():
        if inst["state"] == "aggro":
            inst["state"]    = "idle"
            inst["fighting"] = None
            inst["affects"]  = {}
    player["fighting"] = None


def _advance_target(player, mob_instances, room_state):
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
    target_id = player["fighting"]
    if target_id is None:
        return

    target = mob_instances.get(target_id)
    if target is None or target["state"] == "dead":
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
            raw_kill(tr, player, target_id, target, tpl, room_state)
            _advance_target(player, mob_instances, room_state)

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
            char_death(tr, player)
            stop_fighting(player, mob_instances)
            return

    if player["fighting"] is not None:
        fid  = player["fighting"]
        finst = mob_instances[fid]
        tr.print(_mob_condition(finst, MOB_TEMPLATES[finst["tpl"]]))
        tr.print("")



# ── Death / Victory ───────────────────────────────────────────────────────────

def char_death(tr, player):
    tr.print("Your lifeforce ebbs away...")
    ppleval("WAIT({})".format(DEATH_MSG_DELAY))
    tr.print("A distant warmth draws you back.")
    ppleval("WAIT({})".format(DEATH_MSG_DELAY))
    player["room"] = R_VILLAGE_SQUARE
    player["hp"]   = 1
    player["mp"]   = 1
    player["wait"] = 0
    player["daze"] = 0
    tr.print("You come to your senses. Alive, but barely.")
    tr.print("")


def raw_kill(tr, player, mob_id, inst, tpl, room_state):
    tr.print("{} is defeated!".format(tpl["name"]))
    xp = _xp_for_kill(player["level"], inst["level"])
    player["xp"] += xp
    tr.print("+{} XP".format(xp))

    while player["xp"] >= player["xp_next"]:
        advance_level(tr, player)

    for item_vnum, chance in tpl["loot"]:
        if randint(1, 100) <= chance:
            player["inv"].append(item_vnum)
            tr.print("Found: {}".format(ITEM_TEMPLATES[item_vnum]["name"]))

    inst["state"] = "dead"
    if tpl["respawn"] > 0:
        inst["respawn_at"] = int(ppleval("Ticks")) + tpl["respawn"]

    tr.print("")


def advance_level(tr, player):
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
