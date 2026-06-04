from urandom import randint
from hpprime import eval as ppleval

from config import COMBAT_TICK_MS, DEATH_MSG_DELAY, POLL_MS
from world import ITEM_TEMPLATES, MOB_TEMPLATES, SKILLS, SK_ATTACK, R_VILLAGE_SQUARE
from player import player_stat, show_status, show_prompt


# ── Combat ────────────────────────────────────────────────────────────────────

def _handle_death(tr, player):
    tr.print("Your lifeforce ebbs away...")
    ppleval("WAIT({})".format(DEATH_MSG_DELAY))
    tr.print("A distant warmth draws you back.")
    ppleval("WAIT({})".format(DEATH_MSG_DELAY))
    player["room"] = R_VILLAGE_SQUARE
    player["hp"] = 1
    player["mp"] = 1
    tr.print("You come to your senses. Alive, but barely.")
    tr.print("")


def calc_damage(atk, def_, power, mod_atk=0, mod_def=0):
    raw = power + max(0, (atk + mod_atk) - (def_ + mod_def))
    band = raw // 5
    variance = randint(-band, band) if band else 0
    return max(1, raw + variance)


def _show_combat_options(tr, player, combatants, mob_instances, target_iid):
    for iid in combatants:
        inst = mob_instances[iid]
        tpl = MOB_TEMPLATES[inst["tpl"]]
        mark = "*" if iid == target_iid else " "
        tr.print("{}[{}] HP:{}/{}".format(mark, tpl["name"], inst["hp"], tpl["hp_max"]))
    tr.print("")
    for idx, sk_vnum in enumerate(player["skills"]):
        sk = SKILLS[sk_vnum]
        tr.print("{}. {} (MP:{})".format(idx + 1, sk["name"], sk["mp_cost"]))
    tr.print("{}. Flee".format(len(player["skills"]) + 1))
    tr.print("")


def _apply_skill(tr, player, sk_vnum, target_iid, mob_instances, mob_mods):
    sk = SKILLS[sk_vnum]
    inst = mob_instances[target_iid]
    tpl = MOB_TEMPLATES[inst["tpl"]]
    mods = mob_mods[target_iid]
    effect = sk["effect"]
    if effect == "damage":
        dmg = calc_damage(
            player_stat(player, "atk"), tpl["def"], sk["power"],
            mod_atk=mods.get("p_atk", 0),
            mod_def=mods.get("m_def", 0),
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
        mods[key] = mods.get(key, 0) - sk["amount"]
        mods[key + "_t"] = sk["turns"]
        tr.print("{} weakens {}!".format(sk["name"], tpl["name"]))


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


def enter_combat(tr, player, mob_iid, mob_instances, room_state):
    rs = room_state[player["room"]]
    combatants = [i for i in rs["mobs"] if mob_instances[i]["state"] != "dead"]
    for iid in combatants:
        mob_instances[iid]["state"] = "aggro"
        tr.print("--- {} attacks! ---".format(MOB_TEMPLATES[mob_instances[iid]["tpl"]]["name"]))

    now = int(ppleval("Ticks"))
    stagger = COMBAT_TICK_MS // max(len(combatants), 1)
    mob_timers = {iid: now + i * stagger for i, iid in enumerate(combatants)}
    mob_mods = {iid: {} for iid in combatants}

    tr.print("")
    combat = {
        "combatants": combatants,
        "mob_mods": mob_mods,
        "mob_timers": mob_timers,
        "target_iid": mob_iid,
        "player_atk_timer": now,
        "buf": "",
    }
    _show_combat_options(tr, player, combatants, mob_instances, mob_iid)
    show_prompt(tr, player, "")
    return combat


def handle_combat_input(tr, char, combat, player, mob_instances, room_state):
    combatants = combat["combatants"]
    mob_mods = combat["mob_mods"]
    mob_timers = combat["mob_timers"]

    if char == '\n':
        val = None
        try:
            val = int(combat["buf"].strip())
        except Exception:
            pass
        combat["buf"] = ""
        show_prompt(tr, player, combat["buf"])
        if val is not None:
            n_skills = len(player["skills"])
            if val == n_skills + 1:
                flee_chance = 40 + (player["dex"] - 10) * 5
                if randint(1, 100) <= flee_chance:
                    tr.print("You flee!")
                    for iid in combatants:
                        mob_instances[iid]["state"] = "idle"
                    return "fled"
                tr.print("You couldn't escape!")
                _show_combat_options(tr, player, combatants, mob_instances, combat["target_iid"])
            elif 1 <= val <= n_skills:
                sk_vnum = player["skills"][val - 1]
                if player["mp"] < SKILLS[sk_vnum]["mp_cost"]:
                    tr.print("Not enough MP!")
                else:
                    player["mp"] -= SKILLS[sk_vnum]["mp_cost"]
                    _apply_skill(tr, player, sk_vnum, combat["target_iid"], mob_instances, mob_mods)
                    if mob_instances[combat["target_iid"]]["hp"] == 0:
                        inst = mob_instances[combat["target_iid"]]
                        tpl = MOB_TEMPLATES[inst["tpl"]]
                        result = _handle_victory(tr, player, combat["target_iid"], inst, tpl, room_state)
                        combatants.remove(combat["target_iid"])
                        mob_mods.pop(combat["target_iid"], None)
                        mob_timers.pop(combat["target_iid"], None)
                        if not combatants:
                            return result
                        combat["target_iid"] = combatants[0]
                    _show_combat_options(tr, player, combatants, mob_instances, combat["target_iid"])
    elif char == '\b':
        combat["buf"] = combat["buf"][:-1]
        show_prompt(tr, player, combat["buf"])
    elif char == '\e':
        combat["buf"] = ""
        show_prompt(tr, player, combat["buf"])
    elif char.isdigit() and len(combat["buf"]) < 2:
        combat["buf"] += char
        show_prompt(tr, player, combat["buf"])
    return None


def tick_combat(tr, now, combat, player, mob_instances, room_state):
    combatants = combat["combatants"]
    mob_mods = combat["mob_mods"]
    mob_timers = combat["mob_timers"]
    attacked = False

    # Player auto-attack
    if now - combat["player_atk_timer"] >= COMBAT_TICK_MS:
        combat["player_atk_timer"] = now
        inst = mob_instances[combat["target_iid"]]
        tpl = MOB_TEMPLATES[inst["tpl"]]
        mods = mob_mods[combat["target_iid"]]
        sk = SKILLS[SK_ATTACK]
        dmg = calc_damage(
            player_stat(player, "atk"), tpl["def"], sk["power"],
            mod_atk=mods.get("p_atk", 0),
            mod_def=mods.get("m_def", 0),
        )
        inst["hp"] = max(0, inst["hp"] - dmg)
        vs, vp = _damage_verb(dmg)
        punct = _damage_punct(dmg)
        tr.print("You {} {}{} [{}]".format(vs, tpl["name"], punct, dmg))
        attacked = True
        if inst["hp"] == 0:
            result = _handle_victory(tr, player, combat["target_iid"], inst, tpl, room_state)
            combatants.remove(combat["target_iid"])
            mob_mods.pop(combat["target_iid"], None)
            mob_timers.pop(combat["target_iid"], None)
            if not combatants:
                return result
            combat["target_iid"] = combatants[0]
            _show_combat_options(tr, player, combatants, mob_instances, combat["target_iid"])
            attacked = False

    # Per-mob attacks
    for iid in list(combatants):
        if now - mob_timers[iid] >= COMBAT_TICK_MS:
            mob_timers[iid] = now
            inst = mob_instances[iid]
            tpl = MOB_TEMPLATES[inst["tpl"]]
            mods = mob_mods[iid]
            mob_atk = tpl["atk"] + mods.get("m_atk", 0)
            dmg = calc_damage(mob_atk, player_stat(player, "def"), tpl["atk"])
            player["hp"] = max(0, player["hp"] - dmg)
            vs, vp = _damage_verb(dmg)
            punct = _damage_punct(dmg)
            tr.print("{} {} you{} [{}]".format(tpl["name"], vp, punct, dmg))
            for key in list(mods.keys()):
                if key.endswith("_t"):
                    mods[key] -= 1
                    if mods[key] <= 0:
                        base = key[:-2]
                        mods.pop(key, None)
                        mods.pop(base, None)
            if player["hp"] == 0:
                _handle_death(tr, player)
                return "dead"

    if attacked:
        inst = mob_instances[combat["target_iid"]]
        tpl = MOB_TEMPLATES[inst["tpl"]]
        tr.print(_mob_condition(inst, tpl))
        tr.print("")
        show_prompt(tr, player, combat["buf"])

    return None


def _handle_victory(tr, player, mob_iid, inst, tpl, room_state):
    tr.print("{} is defeated!".format(tpl["name"]))
    player["xp"] += tpl["xp"]
    tr.print("+{} XP".format(tpl["xp"]))

    while player["xp"] >= player["xp_next"]:
        _level_up(tr, player)

    for item_vnum, chance in tpl["loot"]:
        if randint(1, 100) <= chance:
            player["inv"].append(item_vnum)
            tr.print("Found: {}".format(ITEM_TEMPLATES[item_vnum]["name"]))

    inst["state"] = "dead"
    room_state[inst["room"]]["mobs"]  # instance stays; removed from display via state check
    if tpl["respawn"] > 0:
        inst["respawn_at"] = int(ppleval("Ticks")) + tpl["respawn"]

    tr.print("")
    show_status(tr, player)
    return "victory"


def _level_up(tr, player):
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
