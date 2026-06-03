from urandom import randint
from hpprime import eval as ppleval

from world import ITEM_TEMPLATES, MOB_TEMPLATES, SKILLS, SK_ATTACK
from player import player_stat, show_status, show_prompt, _poll_char


# ── Combat ────────────────────────────────────────────────────────────────────

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
    for idx, sk_vnum in enumerate(player["skills"]):
        sk = SKILLS[sk_vnum]
        tr.print("{}. {} (MP:{})".format(idx + 1, sk["name"], sk["mp_cost"]))
    tr.print("{}. Flee".format(len(player["skills"]) + 1))


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
        tr.print("{} hits {} for {} dmg! ({} HP)".format(
            sk["name"], tpl["name"], dmg, inst["hp"]))
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


def combat_loop(tr, player, mob_iid, mob_instances, room_state):
    """Non-blocking combat: auto-attacks tick every ~1s; skills fire on Enter."""
    COMBAT_TICK_MS = 1000

    rs = room_state[player["room"]]
    combatants = [i for i in rs["mobs"] if mob_instances[i]["state"] != "dead"]
    for iid in combatants:
        mob_instances[iid]["state"] = "aggro"
        tr.print("--- {} attacks! ---".format(MOB_TEMPLATES[mob_instances[iid]["tpl"]]["name"]))

    now = int(ppleval("Ticks"))
    stagger = COMBAT_TICK_MS // max(len(combatants), 1)
    mob_timers = {iid: now + i * stagger for i, iid in enumerate(combatants)}
    player_atk_timer = now
    target_iid = mob_iid
    mob_mods = {iid: {} for iid in combatants}

    _show_combat_options(tr, player, combatants, mob_instances, target_iid)
    combat_buf = ""
    show_prompt(tr, player, combat_buf)

    while combatants:
        char = _poll_char(tr)
        if char is not None:
            if char == '\n':
                val = None
                try:
                    val = int(combat_buf.strip())
                except Exception:
                    pass
                combat_buf = ""
                show_prompt(tr, player, combat_buf)
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
                        _show_combat_options(tr, player, combatants, mob_instances, target_iid)
                    elif 1 <= val <= n_skills:
                        sk_vnum = player["skills"][val - 1]
                        if player["mp"] < SKILLS[sk_vnum]["mp_cost"]:
                            tr.print("Not enough MP!")
                        else:
                            player["mp"] -= SKILLS[sk_vnum]["mp_cost"]
                            _apply_skill(tr, player, sk_vnum, target_iid, mob_instances, mob_mods)
                            if mob_instances[target_iid]["hp"] == 0:
                                inst = mob_instances[target_iid]
                                tpl = MOB_TEMPLATES[inst["tpl"]]
                                result = _handle_victory(tr, player, target_iid, inst, tpl, room_state)
                                combatants.remove(target_iid)
                                mob_mods.pop(target_iid, None)
                                mob_timers.pop(target_iid, None)
                                if not combatants:
                                    return result
                                target_iid = combatants[0]
                            _show_combat_options(tr, player, combatants, mob_instances, target_iid)
            elif char == '\b':
                combat_buf = combat_buf[:-1]
                show_prompt(tr, player, combat_buf)
            elif char == '\e':
                combat_buf = ""
                show_prompt(tr, player, combat_buf)
            elif char.isdigit() and len(combat_buf) < 2:
                combat_buf += char
                show_prompt(tr, player, combat_buf)

        now = int(ppleval("Ticks"))

        # Player auto-attack
        if now - player_atk_timer >= COMBAT_TICK_MS:
            player_atk_timer = now
            inst = mob_instances[target_iid]
            tpl = MOB_TEMPLATES[inst["tpl"]]
            mods = mob_mods[target_iid]
            sk = SKILLS[SK_ATTACK]
            dmg = calc_damage(
                player_stat(player, "atk"), tpl["def"], sk["power"],
                mod_atk=mods.get("p_atk", 0),
                mod_def=mods.get("m_def", 0),
            )
            inst["hp"] = max(0, inst["hp"] - dmg)
            tr.print("You hit {} for {}. ({} HP)".format(tpl["name"], dmg, inst["hp"]))
            show_prompt(tr, player, combat_buf)
            if inst["hp"] == 0:
                result = _handle_victory(tr, player, target_iid, inst, tpl, room_state)
                combatants.remove(target_iid)
                mob_mods.pop(target_iid, None)
                mob_timers.pop(target_iid, None)
                if not combatants:
                    return result
                target_iid = combatants[0]
                _show_combat_options(tr, player, combatants, mob_instances, target_iid)

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
                tr.print("{} hits you for {}! ({}/{})".format(
                    tpl["name"], dmg, player["hp"], player["hp_max"]))
                show_prompt(tr, player, combat_buf)
                for key in list(mods.keys()):
                    if key.endswith("_t"):
                        mods[key] -= 1
                        if mods[key] <= 0:
                            base = key[:-2]
                            mods.pop(key, None)
                            mods.pop(base, None)
                if player["hp"] == 0:
                    tr.print("You have died.")
                    return "dead"

        ppleval("WAIT(1/1e3)")


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
