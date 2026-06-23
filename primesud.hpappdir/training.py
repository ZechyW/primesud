"""Training and practice command handlers."""

from skills_table import SKILL_TABLE, SKILLS
import world
from world import MOB_DEFS
from picker import pick_from
from actor import get_curr_stat
from config import INT_APP_LEARN, MAX_STATS, SKILL_ADEPT
from info import print_practice_table
from skill_utils import can_use_skill_spell, find_skill_spell, skill_rating


_TRAIN_STATS = [
    ("str", "strength"),
    ("dex", "dexterity"),
    ("int", "intelligence"),
    ("wis", "wisdom"),
    ("con", "constitution"),
]

def do_train(tr, player, args):
    """Permanently raise a stat or vital by spending a train point (cf. 1stMud do_train in act_move.c).

    Requires a mob with act_flags["train"] in the room.  Stats cap at MAX_STATS;
    hp and mana training raise hp_max/mp_max by 10 with no cap.

    Args:
        tr: Terminal instance.
        player (dict): Player state dict.
        args (list): Parsed command words; optional stat/vital name.
    """
    rs = world.rooms[player["room"]]
    trainer = None
    for mid in rs["mobs"]:
        inst = world.chars[mid]
        if MOB_DEFS[inst["tpl"]].get("act_flags", {}).get("train"):
            trainer = mid
            break
    if trainer is None:
        tr.print("You can't do that here.")
        return

    _from_picker = False
    if not args:
        if player["train"] < 1:
            tr.print("You don't have any training sessions.")
            return
        stat_opts = [(k, lng) for k, lng in _TRAIN_STATS if player[k] < MAX_STATS]
        vital_opts = [("hp_max", "hp"), ("mp_max", "mana")]
        all_opts = stat_opts + vital_opts
        tr.print("You have " + str(player["train"]) + " training session" + ("" if player["train"] == 1 else "s") + ".")
        names = []
        for k, lng in all_opts:
            if k in ("hp_max", "mp_max"):
                names.append(lng + " (max: " + str(player[k]) + ")")
            else:
                names.append(lng + " (" + str(player[k]) + "/" + str(MAX_STATS) + ")")
        idx = pick_from(tr, "Train which?", names)
        if idx < 0:
            return
        chosen_key, chosen_lng = all_opts[idx]
        _from_picker = True
    else:
        if player["train"] < 1:
            tr.print("You don't have any training sessions.")
            return
        arg = args[0]
        chosen_key = None
        chosen_lng = None
        for k, lng in _TRAIN_STATS + [("hp_max", "hp"), ("mp_max", "mana")]:
            if lng.startswith(arg):
                chosen_key = k
                chosen_lng = lng
                break
        if chosen_key is None:
            tr.print("Valid training: str, dex, int, wis, con, hp, mana.")
            return
        if chosen_key not in ("hp_max", "mp_max") and player[chosen_key] >= MAX_STATS:
            tr.print("Your " + chosen_lng + " is already at maximum.")
            return

    player["train"] -= 1
    if chosen_key == "hp_max":
        player["hp_max"] += 10
        player["hp"] = min(player["hp_max"], player["hp"] + 10)
        tr.print("Your durability increases!")
    elif chosen_key == "mp_max":
        player["mp_max"] += 10
        player["mp"] = min(player["mp_max"], player["mp"] + 10)
        tr.print("Your power increases!")
    else:
        player[chosen_key] += 1
        tr.print("Your " + chosen_lng + " increases!")
    return ("train " + chosen_lng) if _from_picker else None


def do_practice(tr, player, args):
    """Improve a skill percentage using a practice point (cf. 1stMud do_practice in act_info.c).

    Without an argument: lists skills + practice count.  If a teacher is present,
    also opens a picker of under-cap skills [PRIMESUD].
    With a skill name: requires a mob with act_flags["practice"] in the room.

    Args:
        tr: Terminal instance.
        player (dict): Player state dict.
        args (list): Parsed command words; optional skill name.
    """
    rs = world.rooms[player["room"]]
    teacher = None
    for mid in rs["mobs"]:
        inst = world.chars[mid]
        if MOB_DEFS[inst["tpl"]].get("act_flags", {}).get("practice"):
            teacher = mid
            break

    _from_picker = False
    if not args:
        print_practice_table(tr, player)
        tr.print("You have " + str(player["practice"]) + " practice sessions left.")
        if teacher is None or player["practice"] < 1:
            return
        learned = player["learned"]
        practicable = [(sn, learned[sn]) for sn, sk in SKILL_TABLE
                       if (sn in learned
                           and 0 < learned[sn] < SKILL_ADEPT
                           and can_use_skill_spell(player, sn)
                           and skill_rating(player, sn) > 0)]
        if not practicable:
            return
        names = [str(SKILLS[vnum]["name"]) + " (" + str(pct) + "%)" for vnum, pct in practicable]
        tr.print("")
        idx = pick_from(tr, "Practice which skill?", names)
        if idx < 0:
            return
        sk_vnum, _ = practicable[idx]
        _from_picker = True
    else:
        if teacher is None:
            tr.print("You can't do that here.")
            return
        if player["practice"] < 1:
            tr.print("You have no practice sessions left.")
            return
        arg = " ".join(args)
        sk_vnum = find_skill_spell(player, arg)
        if (sk_vnum is None or not can_use_skill_spell(player, sk_vnum)
                or player["learned"].get(sk_vnum, 0) < 1
                or skill_rating(player, sk_vnum) == 0):
            tr.print("You can't practice that.")
            return
        if player["learned"][sk_vnum] >= SKILL_ADEPT:
            tr.print("You are already learned at {}.".format(SKILLS[sk_vnum]["name"]))
            return

    int_val = get_curr_stat(player, "int")
    sk_rating = skill_rating(player, sk_vnum)
    if sk_rating == 0:
        tr.print("You can't practice that.")
        return
    gain = INT_APP_LEARN[int_val] // sk_rating
    player["practice"] -= 1
    new_pct = min(SKILL_ADEPT, player["learned"][sk_vnum] + gain)
    player["learned"][sk_vnum] = new_pct
    if new_pct >= SKILL_ADEPT:
        tr.print("You are now learned at {}.".format(SKILLS[sk_vnum]["name"]))
    else:
        tr.print("You practice {}.".format(SKILLS[sk_vnum]["name"]))
    return ("practice " + SKILLS[sk_vnum]["name"]) if _from_picker else None
