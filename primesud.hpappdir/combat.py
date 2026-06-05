from urandom import randint
from hpprime import eval as ppleval

from config import DEATH_MSG_DELAY, PULSE_VIOLENCE
from world import (
    ITEM_TEMPLATES, MOB_TEMPLATES, SKILLS, ROOMS,
    R_VILLAGE_SQUARE,
    SK_UNARMED, SK_SECOND_ATTACK, SK_THIRD_ATTACK,
    SK_DODGE, SK_PARRY, SK_SHIELD_BLOCK, SK_ENHANCED_DMG,
    WEAPON_TYPE_SKILL,
    STR_APP_TODAM, DEX_APP_DEF, CON_APP_HITP,
    THAC0_00, THAC0_32,
)
from player import get_hitroll, get_damroll, get_AC, show_status, show_prompt


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


def _weapon_skill(player):
    """Return (sk_vnum, learned_pct, weapon_tpl_or_None) for current main weapon."""
    wvnum = player["equip"].get("weapon")
    if wvnum is not None:
        wtpl  = ITEM_TEMPLATES[wvnum]
        sk_vn = WEAPON_TYPE_SKILL.get(wtpl.get("weapon_type", ""), SK_UNARMED)
        return sk_vn, player["learned"].get(sk_vn, 20), wtpl
    return SK_UNARMED, player["learned"].get(SK_UNARMED, 20), None


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
    pct = inst["hp"] * 100 // tpl["hp_max"] if tpl["hp_max"] > 0 else -1
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

def _try_improve(player, sk_vnum, chance=10):
    """chance% probability of gaining 1 skill point (capped at 100)."""
    current = player["learned"].get(sk_vnum, 0)
    if 0 < current < 100 and randint(1, 100) <= chance:
        player["learned"][sk_vnum] = current + 1


# ── Defensive checks (player defending against mob attack) ────────────────────

def check_dodge(tr, player, mob_inst):
    skill = player["learned"].get(SK_DODGE, 0)
    if skill > 0 and randint(1, 100) <= skill // 2:
        tpl = MOB_TEMPLATES[mob_inst["tpl"]]
        tr.print("You dodge {}'s attack.".format(tpl["name"]))
        _try_improve(player, SK_DODGE)
        return True
    return False


def check_parry(tr, player, mob_inst):
    if player["equip"].get("weapon") is None:
        return False
    skill = player["learned"].get(SK_PARRY, 0)
    if skill > 0 and randint(1, 100) <= skill // 2:
        tpl = MOB_TEMPLATES[mob_inst["tpl"]]
        tr.print("You parry {}'s attack.".format(tpl["name"]))
        _try_improve(player, SK_PARRY)
        return True
    return False


def check_shield_block(tr, player, mob_inst):
    offhand = player["equip"].get("offhand")
    if offhand is None or ITEM_TEMPLATES[offhand].get("type") != "shield":
        return False
    skill = player["learned"].get(SK_SHIELD_BLOCK, 0)
    if skill > 0 and randint(1, 100) <= skill // 2:
        tpl = MOB_TEMPLATES[mob_inst["tpl"]]
        tr.print("You block {}'s attack.".format(tpl["name"]))
        _try_improve(player, SK_SHIELD_BLOCK)
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
        wtpl  = ITEM_TEMPLATES[wvnum]
        sk_vn = WEAPON_TYPE_SKILL.get(wtpl.get("weapon_type", ""), SK_UNARMED)
        sk_vnum, skill = sk_vn, player["learned"].get(sk_vn, 20)

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

    # Enhanced damage passive
    enh = player["learned"].get(SK_ENHANCED_DMG, 0)
    if enh > 0 and randint(1, 100) <= enh:
        dam += 2 * dam * randint(1, 100) // 300

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
    vs, _ = _damage_verb(dam)
    punct = _damage_punct(dam)
    tr.print("Your {} {} {}{} [{}]".format(weapon_name, vs, tpl["name"], punct, dam))

    _try_improve(player, sk_vnum)
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
    if check_dodge(tr, player, mob_inst):
        return 0
    if check_parry(tr, player, mob_inst):
        return 0
    if check_shield_block(tr, player, mob_inst):
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


# ── Special unarmed moves (primesud flavour, cf. 1stMud special_move) ────────

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
    skill = player["learned"].get(SK_UNARMED, 20)
    lo  = max(1, 1 + 4 * skill // 100)
    hi  = max(lo, 2 * player["level"] * skill // 300)
    dam = max(1, randint(lo, hi))
    target_inst["hp"] = max(0, target_inst["hp"] - dam)
    tr.print("{} [{}]".format(move[-1].format(name), dam))
    _try_improve(player, SK_UNARMED)
    return dam


# ── Multi-hit (player's full attack sequence) ─────────────────────────────────

def multi_hit(tr, player, target_inst):
    """Full attack sequence for one combat round. Returns True if target killed."""
    # Primary
    one_hit(tr, player, target_inst)
    if target_inst["hp"] == 0:
        return True

    # Unarmed special move (primesud flavour)
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

    # Second attack
    second = player["learned"].get(SK_SECOND_ATTACK, 0)
    if second > 0 and randint(1, 100) <= second // 2:
        one_hit(tr, player, target_inst)
        _try_improve(player, SK_SECOND_ATTACK, chance=5)
        if target_inst["hp"] == 0:
            return True

    # Third attack
    third = player["learned"].get(SK_THIRD_ATTACK, 0)
    if third > 0 and randint(1, 100) <= third // 4:
        one_hit(tr, player, target_inst)
        _try_improve(player, SK_THIRD_ATTACK, chance=6)
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
        if inst["state"] != "dead" and tpl.get("ai") != "passive":
            inst["state"] = "aggro"
            if mid == mob_id:
                tr.print("--- {} attacks! ---".format(tpl["name"]))
            else:
                tr.print("--- {} joins the fight! ---".format(tpl["name"]))
    tr.print("")
    player["fighting"] = mob_id


def stop_fighting(player, mob_instances):
    """End combat: reset aggro mobs to idle, clear player target."""
    for inst in mob_instances.values():
        if inst["state"] == "aggro":
            inst["state"] = "idle"
            inst["affects"] = {}
    player["fighting"] = None


# ── Skill application ─────────────────────────────────────────────────────────

def _apply_skill(tr, player, sk, target_inst):
    effect = sk.get("effect", "")
    tpl    = MOB_TEMPLATES[target_inst["tpl"]]

    if effect == "weapon_strike":
        one_hit(tr, player, target_inst, bonus_damroll=sk.get("bonus_damroll", 0))

    elif effect == "heal":
        gained = min(sk["power"], player["hp_max"] - player["hp"])
        player["hp"] += gained
        tr.print("{}: +{} HP. ({}/{})".format(
            sk["name"], gained, player["hp"], player["hp_max"]))

    elif effect == "debuff":
        key = "m_" + sk["stat"]
        affects = target_inst["affects"]
        affects[key]       = affects.get(key, 0) - sk["amount"]
        affects[key + "_t"] = sk["turns"]
        tr.print("{} weakens {}!".format(sk["name"], tpl["name"]))


def use_skill(tr, player, sk_vnum, mob_instances, room_state):
    """Use a skill against the current target."""
    sk        = SKILLS[sk_vnum]
    target_id = player["fighting"]
    target    = mob_instances[target_id]

    _apply_skill(tr, player, sk, target)
    WaitState(player, sk.get("beats", 0))

    if target["hp"] == 0:
        tpl = MOB_TEMPLATES[target["tpl"]]
        raw_kill(tr, player, target_id, target, tpl, room_state)
        _advance_target(player, mob_instances, room_state)


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
            return

    # Mob counter-attacks
    for mob_id in list(rs["mobs"]):
        mob_inst = mob_instances[mob_id]
        if mob_inst["state"] != "aggro":
            continue
        if mob_inst["wait"] > 0:
            continue
        mob_tpl = MOB_TEMPLATES[mob_inst["tpl"]]
        if mob_tpl.get("ai") == "passive":
            continue

        _mob_one_hit(tr, mob_inst, player)

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


# ── Flee ──────────────────────────────────────────────────────────────────────

def do_flee(tr, player, args, room_state, mob_instances):
    if player["fighting"] is None:
        tr.print("You're not fighting anyone.")
        return
    exits = list(ROOMS[player["room"]]["exits"].items())
    if not exits:
        tr.print("There is nowhere to run!")
        return
    # Try exits in random order (up to 6 attempts, cf. 1stMud)
    attempts = list(range(len(exits)))
    for _ in range(min(6, len(exits))):
        idx = randint(0, len(attempts) - 1)
        direction, dest = exits[attempts.pop(idx)]
        player["room"] = dest
        stop_fighting(player, mob_instances)
        tr.print("You flee {}!".format(direction))
        tr.print("[ {} ]".format(ROOMS[dest]["name"]))
        return
    tr.print("There is nowhere to run!")


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
    player["xp"] += tpl["xp"]
    tr.print("+{} XP".format(tpl["xp"]))

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
    show_status(tr, player)


def advance_level(tr, player):
    player["level"]   += 1
    player["xp"]      -= player["xp_next"]
    player["xp_next"]  = player["xp_next"] * 3 // 2

    con = min(25, max(0, player["con"]))
    hp_gain = max(1, CON_APP_HITP[con] + randint(1, 5))
    mp_gain = max(1, player["int"] // 5 + randint(1, 3))

    player["hp_max"] += hp_gain
    player["mp_max"] += mp_gain
    player["hp"]      = player["hp_max"]
    player["mp"]      = player["mp_max"]
    tr.print("*** Level up! Now level {}. (+{} HP, +{} MP) ***".format(
        player["level"], hp_gain, mp_gain))
