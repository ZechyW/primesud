from world import SKILLS, SKILL_TABLE
from picker import pick_from
from combat import WaitState, check_improve

from urandom import randint


def _spell_heal(tr, player, sk):
    num, size, bonus = sk["heal_dice"]
    roll = bonus + player["level"] // sk.get("level_div", 1)
    for _ in range(num):
        roll += randint(1, size)
    gained = min(roll, player["hp_max"] - player["hp"])
    player["hp"] += gained
    tr.print("You feel better! +{} HP. ({}/{})".format(
        gained, player["hp"], player["hp_max"]))


def do_cast(tr, player, args, world):
    if not args:
        known = [(vnum, sk) for vnum, sk in SKILL_TABLE
                 if sk.get("spell_fun", "spell_null") != "spell_null"
                 and player["learned"].get(vnum, 0) > 0]
        if not known:
            tr.print("You know no spells.")
            return None
        names = [sk["name"] for _, sk in known]
        idx = pick_from(tr, "Cast which spell?", names)
        if idx < 0:
            return None
        sk_vnum = known[idx][0]
    else:
        spell_key = args[0]
        sk_vnum = None
        for vnum, sk in SKILL_TABLE:
            if sk.get("spell_fun", "spell_null") == "spell_null":
                continue
            name = sk["name"]
            if name == spell_key or name.startswith(spell_key):
                sk_vnum = vnum
                break
        if sk_vnum is None or player["learned"].get(sk_vnum, 0) == 0:
            tr.print("You don't know any spell called that.")
            return None
    sk = SKILLS[sk_vnum]
    if player.get("wait", 0) > 0:
        tr.print("You are still recovering.")
        return None
    mana = sk.get("min_mana", 0)
    if player["mp"] < mana:
        tr.print("You don't have enough mana.")
        return None
    player["mp"] -= mana
    WaitState(player, sk.get("beats", 0))
    effect = sk.get("effect", "")
    if effect == "heal":
        _spell_heal(tr, player, sk)
    check_improve(tr, player, sk_vnum, True, 1)
    return None
