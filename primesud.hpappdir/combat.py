from urandom import randint
from hpprime import eval as ppleval

from config import DEATH_MSG_DELAY
from world import ITEM_TEMPLATES, MOB_TEMPLATES, SKILLS, SK_ATTACK, R_VILLAGE_SQUARE
from player import get_curr_stat, show_status, show_prompt


# ── Special unarmed moves (adapted from 1stMud fight.c) ──────────────────────

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


def _try_special_move(tr, player, inst, tpl):
    if player["equip"].get("weapon") is not None:
        return 0
    chance = 20 + (player["dex"] - 10) * 3
    if randint(1, 100) > chance:
        return 0
    name = tpl["name"]
    move = _SPECIAL_MOVES[randint(0, len(_SPECIAL_MOVES) - 1)]
    for line in move[:-1]:
        tr.print(line.format(name))
    bonus = calc_damage(player["str"], tpl["def"], 8)
    tr.print("{} [{}]".format(move[-1].format(name), bonus))
    return bonus


# ── Damage ────────────────────────────────────────────────────────────────────

def calc_damage(atk, def_, power, mod_atk=0, mod_def=0):
    raw = power + max(0, (atk + mod_atk) - (def_ + mod_def))
    band = raw // 5
    variance = randint(-band, band) if band else 0
    return max(0, raw + variance)


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


# ── Combat state (cf. 1stMud set_fighting / stop_fighting) ───────────────────

def set_fighting(tr, player, mob_id, mob_instances, room_state):
    """Enter combat: mark all room mobs aggro, set player target."""
    rs = room_state[player["room"]]
    for mid in rs["mobs"]:
        inst = mob_instances[mid]
        if inst["state"] != "dead":
            inst["state"] = "aggro"
            if mid == mob_id:
                tr.print("--- {} attacks! ---".format(MOB_TEMPLATES[inst["tpl"]]["name"]))
            else:
                tr.print("--- {} joins the fight! ---".format(MOB_TEMPLATES[inst["tpl"]]["name"]))
    tr.print("")
    player["fighting"] = mob_id


def stop_fighting(player, mob_instances):
    """End combat: reset all aggro mobs to idle, clear player target."""
    for inst in mob_instances.values():
        if inst["state"] == "aggro":
            inst["state"] = "idle"
            inst["affects"] = {}
    player["fighting"] = None


# ── Skills ────────────────────────────────────────────────────────────────────

def _apply_skill(tr, player, sk_vnum, target_id, mob_instances):
    sk = SKILLS[sk_vnum]
    inst = mob_instances[target_id]
    tpl = MOB_TEMPLATES[inst["tpl"]]
    affects = inst["affects"]
    effect = sk["effect"]
    if effect == "damage":
        dmg = calc_damage(
            get_curr_stat(player, "atk"), tpl["def"], sk["power"],
            mod_atk=affects.get("p_atk", 0),
            mod_def=affects.get("m_def", 0),
        )
        inst["hp"] = max(0, inst["hp"] - dmg)
        vs, vp = _damage_verb(dmg)
        punct = _damage_punct(dmg)
        tr.print("Your {} {} {}{} [{}]".format(sk["name"], vp, tpl["name"], punct, dmg))
    elif effect == "heal":
        gained = min(sk["power"], player["hp_max"] - player["hp"])
        player["hp"] += gained
        tr.print("{}: +{} HP. ({}/{})".format(
            sk["name"], gained, player["hp"], player["hp_max"]))
    elif effect == "debuff":
        key = "m_" + sk["stat"]
        affects[key] = affects.get(key, 0) - sk["amount"]
        affects[key + "_t"] = sk["turns"]
        tr.print("{} weakens {}!".format(sk["name"], tpl["name"]))


def use_skill(tr, player, sk_vnum, mob_instances, room_state):
    """Use a skill against the current target, handling kill if it occurs."""
    target_id = player["fighting"]
    _apply_skill(tr, player, sk_vnum, target_id, mob_instances)
    if mob_instances[target_id]["hp"] == 0:
        inst = mob_instances[target_id]
        tpl = MOB_TEMPLATES[inst["tpl"]]
        raw_kill(tr, player, target_id, inst, tpl, room_state)
        _advance_target(player, mob_instances, room_state)


def _advance_target(player, mob_instances, room_state):
    """After killing current target: auto-engage next aggro mob or stop fighting."""
    rs = room_state[player["room"]]
    next_id = None
    for mid in rs["mobs"]:
        if mob_instances[mid]["state"] == "aggro":
            next_id = mid
            break
    if next_id is not None:
        player["fighting"] = next_id
    else:
        stop_fighting(player, mob_instances)


# ── Violence update (cf. 1stMud violence_update, called every PULSE_VIOLENCE) ─

def violence_update(tr, player, mob_instances, room_state):
    """Auto-attack round for player and all aggro mobs in the room."""
    target_id = player["fighting"]
    if target_id is None:
        return

    inst = mob_instances.get(target_id)
    if inst is None or inst["state"] == "dead":
        stop_fighting(player, mob_instances)
        return

    tpl = MOB_TEMPLATES[inst["tpl"]]
    affects = inst["affects"]
    sk = SKILLS[SK_ATTACK]

    # Player auto-attack
    dmg = calc_damage(
        get_curr_stat(player, "atk"), tpl["def"], sk["power"],
        mod_atk=affects.get("p_atk", 0),
        mod_def=affects.get("m_def", 0),
    )
    inst["hp"] = max(0, inst["hp"] - dmg)
    vs, vp = _damage_verb(dmg)
    punct = _damage_punct(dmg)
    tr.print("You {} {}{} [{}]".format(vs, tpl["name"], punct, dmg))

    if inst["hp"] > 0:
        bonus = _try_special_move(tr, player, inst, tpl)
        if bonus:
            inst["hp"] = max(0, inst["hp"] - bonus)

    if inst["hp"] == 0:
        raw_kill(tr, player, target_id, inst, tpl, room_state)
        _advance_target(player, mob_instances, room_state)
        return

    # All aggro mobs in room counter-attack
    rs = room_state[player["room"]]
    for mob_id in list(rs["mobs"]):
        mob_inst = mob_instances[mob_id]
        if mob_inst["state"] != "aggro":
            continue
        mob_tpl = MOB_TEMPLATES[mob_inst["tpl"]]
        mob_affects = mob_inst["affects"]
        mob_atk = mob_tpl["atk"] + mob_affects.get("m_atk", 0)
        dmg2 = calc_damage(mob_atk, get_curr_stat(player, "def"), mob_tpl["atk"])
        player["hp"] = max(0, player["hp"] - dmg2)
        vs2, vp2 = _damage_verb(dmg2)
        punct2 = _damage_punct(dmg2)
        tr.print("{} {} you{} [{}]".format(mob_tpl["name"], vp2, punct2, dmg2))
        for key in list(mob_affects.keys()):
            if key.endswith("_t"):
                mob_affects[key] -= 1
                if mob_affects[key] <= 0:
                    base = key[:-2]
                    mob_affects.pop(key, None)
                    mob_affects.pop(base, None)
        if player["hp"] == 0:
            char_death(tr, player)
            stop_fighting(player, mob_instances)
            return

    if player["fighting"] is not None:
        tr.print(_mob_condition(mob_instances[player["fighting"]],
                                MOB_TEMPLATES[mob_instances[player["fighting"]]["tpl"]]))
        tr.print("")


# ── Flee ──────────────────────────────────────────────────────────────────────

def do_flee(tr, player, args, mob_instances):
    if player["fighting"] is None:
        tr.print("You're not fighting anyone.")
        return
    flee_chance = 40 + (player["dex"] - 10) * 5
    if randint(1, 100) <= flee_chance:
        tr.print("You flee!")
        stop_fighting(player, mob_instances)
    else:
        tr.print("You couldn't escape!")


# ── Death / Victory ───────────────────────────────────────────────────────────

def char_death(tr, player):
    tr.print("Your lifeforce ebbs away...")
    ppleval("WAIT({})".format(DEATH_MSG_DELAY))
    tr.print("A distant warmth draws you back.")
    ppleval("WAIT({})".format(DEATH_MSG_DELAY))
    player["room"] = R_VILLAGE_SQUARE
    player["hp"] = 1
    player["mp"] = 1
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
    player["level"] += 1
    player["xp"] -= player["xp_next"]
    player["xp_next"] = player["xp_next"] * 3 // 2
    player["con"] += 1
    player["str"] += 1
    player["hp_max"] = 10 + player["con"] * 2
    player["mp_max"] = 5 + player["int"]
    player["hp"] = player["hp_max"]
    player["mp"] = player["mp_max"]
    tr.print("*** Level up! Now level {}. ***".format(player["level"]))
