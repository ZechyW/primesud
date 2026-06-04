from urandom import randint
from hpprime import eval as ppleval

from config import COMBAT_TICK_MS, DEATH_MSG_DELAY, POLL_MS
from world import ITEM_TEMPLATES, MOB_TEMPLATES, SKILLS, SK_ATTACK, R_VILLAGE_SQUARE
from player import player_stat, show_status, show_prompt


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
    return max(0, raw + variance)


def _show_combat_options(tr, player, combatants, mob_instances, target_id):
    for mob_id in combatants:
        inst = mob_instances[mob_id]
        tpl = MOB_TEMPLATES[inst["tpl"]]
        mark = "*" if mob_id == target_id else " "
        tr.print("{}[{}] HP:{}/{}".format(mark, tpl["name"], inst["hp"], tpl["hp_max"]))
    tr.print("")
    for idx, sk_vnum in enumerate(player["skills"]):
        sk = SKILLS[sk_vnum]
        tr.print("{}. {} (MP:{})".format(idx + 1, sk["name"], sk["mp_cost"]))
    tr.print("{}. Flee".format(len(player["skills"]) + 1))
    tr.print("")


def _apply_skill(tr, player, sk_vnum, target_id, mob_instances, mob_mods):
    sk = SKILLS[sk_vnum]
    inst = mob_instances[target_id]
    tpl = MOB_TEMPLATES[inst["tpl"]]
    mods = mob_mods[target_id]
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


def enter_combat(tr, player, mob_id, mob_instances, room_state):
    rs = room_state[player["room"]]
    combatants = [i for i in rs["mobs"] if mob_instances[i]["state"] != "dead"]
    for mob_id in combatants:
        mob_instances[mob_id]["state"] = "aggro"
        tr.print("--- {} attacks! ---".format(MOB_TEMPLATES[mob_instances[mob_id]["tpl"]]["name"]))

    now = int(ppleval("Ticks"))
    stagger = COMBAT_TICK_MS // max(len(combatants), 1)
    mob_timers = {mob_id: now + i * stagger for i, mob_id in enumerate(combatants)}
    mob_mods = {mob_id: {} for mob_id in combatants}

    tr.print("")
    combat = {
        "combatants": combatants,
        "mob_mods": mob_mods,
        "mob_timers": mob_timers,
        "target_id": mob_id,
        "player_atk_timer": now,
        "buf": "",
    }
    # TODO: Do we really need to show this automatically?  Maybe only if the player presses enter with no command.
    # _show_combat_options(tr, player, combatants, mob_instances, mob_id)
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
                    for mob_id in combatants:
                        mob_instances[mob_id]["state"] = "idle"
                    return "fled"
                tr.print("You couldn't escape!")
                _show_combat_options(tr, player, combatants, mob_instances, combat["target_id"])
            elif 1 <= val <= n_skills:
                sk_vnum = player["skills"][val - 1]
                if player["mp"] < SKILLS[sk_vnum]["mp_cost"]:
                    tr.print("Not enough MP!")
                else:
                    player["mp"] -= SKILLS[sk_vnum]["mp_cost"]
                    _apply_skill(tr, player, sk_vnum, combat["target_id"], mob_instances, mob_mods)
                    if mob_instances[combat["target_id"]]["hp"] == 0:
                        inst = mob_instances[combat["target_id"]]
                        tpl = MOB_TEMPLATES[inst["tpl"]]
                        result = _handle_victory(tr, player, combat["target_id"], inst, tpl, room_state)
                        combatants.remove(combat["target_id"])
                        mob_mods.pop(combat["target_id"], None)
                        mob_timers.pop(combat["target_id"], None)
                        if not combatants:
                            return result
                        combat["target_id"] = combatants[0]
                    _show_combat_options(tr, player, combatants, mob_instances, combat["target_id"])
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
        inst = mob_instances[combat["target_id"]]
        tpl = MOB_TEMPLATES[inst["tpl"]]
        mods = mob_mods[combat["target_id"]]
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
        if inst["hp"] > 0:
            bonus = _try_special_move(tr, player, inst, tpl)
            if bonus:
                inst["hp"] = max(0, inst["hp"] - bonus)
        if inst["hp"] == 0:
            result = _handle_victory(tr, player, combat["target_id"], inst, tpl, room_state)
            combatants.remove(combat["target_id"])
            mob_mods.pop(combat["target_id"], None)
            mob_timers.pop(combat["target_id"], None)
            if not combatants:
                return result
            combat["target_id"] = combatants[0]
            _show_combat_options(tr, player, combatants, mob_instances, combat["target_id"])
            attacked = False

    # Per-mob attacks
    for mob_id in list(combatants):
        if now - mob_timers[mob_id] >= COMBAT_TICK_MS:
            mob_timers[mob_id] = now
            inst = mob_instances[mob_id]
            tpl = MOB_TEMPLATES[inst["tpl"]]
            mods = mob_mods[mob_id]
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
        inst = mob_instances[combat["target_id"]]
        tpl = MOB_TEMPLATES[inst["tpl"]]
        tr.print(_mob_condition(inst, tpl))
        tr.print("")
        show_prompt(tr, player, combat["buf"])

    return None


def _handle_victory(tr, player, mob_id, inst, tpl, room_state):
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
