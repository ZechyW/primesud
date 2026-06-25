"""Training and practice command handlers."""

import world
from actor import (get_curr_stat, act, chprintln, chprintlnf,
                   TO_CHAR, TO_ROOM)
from config import INT_APP_LEARN, MAX_STATS, SKILL_ADEPT
from info import print_practice_table
from picker import pick_from
from skill_utils import can_use_skill_spell, find_skill_spell, skill_rating
from skills_table import SKILL_TABLE, SKILLS
from world import MOB_DEFS

_TRAIN_STATS = [
    ("str", "strength"),
    ("dex", "dexterity"),
    ("int", "intelligence"),
    ("wis", "wisdom"),
    ("con", "constitution"),
]

def do_train(player, args):
    """Permanently raise a stat or vital by spending a train point (cf. 1stMud do_train in act_move.c).

    Requires a mob with act_flags["train"] in the room.  Stats cap at MAX_STATS;
    hp and mana training raise max_hit/max_mana by 10 with no cap.

    Args:
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
        chprintln(player, "You can't do that here.")
        return

    _from_picker = False
    if not args:
        if player["train"] < 1:
            chprintln(player, "You don't have enough training sessions.")
            return
        stat_opts = [(k, lng) for k, lng in _TRAIN_STATS if player["perm_stat"][k] < MAX_STATS]
        vital_opts = [("max_hit", "hp"), ("max_mana", "mana")]
        all_opts = stat_opts + vital_opts
        # [PRIMESUD] Picker UI -- 1stMud prints "You can train: ..." then falls through
        # [PRIMESUD] Singular/plural fix -- 1stMud always prints "sessions"
        chprintlnf(player, "You have %d training session%s.",
                    player["train"],
                    "" if player["train"] == 1 else "s")
        names = []
        for k, lng in all_opts:
            if k in ("max_hit", "max_mana"):
                names.append(lng + " (max: " + str(player[k]) + ")")
            else:
                names.append(lng + " (" + str(player["perm_stat"][k]) + "/" + str(MAX_STATS) + ")")
        idx = pick_from("Train which?", names)
        if idx < 0:
            return
        chosen_key, chosen_lng = all_opts[idx]
        _from_picker = True
    else:
        if player["train"] < 1:
            chprintln(player, "You don't have enough training sessions.")
            return
        arg = args[0]
        chosen_key = None
        chosen_lng = None
        for k, lng in _TRAIN_STATS + [("max_hit", "hp"), ("max_mana", "mana")]:
            if lng.startswith(arg):
                chosen_key = k
                chosen_lng = lng
                break
        if chosen_key is None:
            buf = "You can train:"
            for k, lng in _TRAIN_STATS:
                if player["perm_stat"][k] < MAX_STATS:
                    buf = buf + " " + lng[:3]
            buf = buf + " hp mana."
            chprintln(player, buf)
            return
        if chosen_key not in ("max_hit", "max_mana") and player["perm_stat"][chosen_key] >= MAX_STATS:
            act("Your $T is already at maximum.", player, None, chosen_lng, TO_CHAR)
            return

    if player["train"] < 1:
        chprintln(player, "You don't have enough training sessions.")
        return
    player["train"] -= 1
    if chosen_key == "max_hit":
        player["max_hit"] += 10
        player["hit"] = min(player["max_hit"], player["hit"] + 10)
        act("Your durability increases!", player, None, None, TO_CHAR)
        act("$n's durability increases!", player, None, None, TO_ROOM)
    elif chosen_key == "max_mana":
        player["max_mana"] += 10
        player["mana"] = min(player["max_mana"], player["mana"] + 10)
        act("Your power increases!", player, None, None, TO_CHAR)
        act("$n's power increases!", player, None, None, TO_ROOM)
    else:
        player["perm_stat"][chosen_key] += 1
        act("Your $T increases!", player, None, chosen_lng, TO_CHAR)
        act("$n's $T increases!", player, None, chosen_lng, TO_ROOM)
    return ("train " + chosen_lng) if _from_picker else None


def do_practice(player, args):
    """Improve a skill percentage using a practice point (cf. 1stMud do_practice in act_info.c).

    Without an argument: lists skills + practice count.  If a teacher is present,
    also opens a picker of under-cap skills [PRIMESUD].
    With a skill name: requires a mob with act_flags["practice"] in the room.

    Args:
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
        print_practice_table(player)
        # [PRIMESUD] Singular/plural fix -- 1stMud always prints "sessions"
        chprintlnf(player, "You have %d practice session%s left.",
                    player["practice"],
                    "" if player["practice"] == 1 else "s")
        if teacher is None or player["practice"] < 1:
            return
        # [PRIMESUD] Picker UI for practicing skills
        learned = player["learned"]
        practicable = [(sn, learned[sn]) for sn, sk in SKILL_TABLE
                       if (sn in learned
                           and 0 < learned[sn] < SKILL_ADEPT
                           and can_use_skill_spell(player, sn)
                           and skill_rating(player, sn) > 0)]
        if not practicable:
            return
        names = [str(SKILLS[vnum]["name"]) + " (" + str(pct) + "%)" for vnum, pct in practicable]
        chprintln(player, "")
        idx = pick_from("Practice which skill?", names)
        if idx < 0:
            return
        sk_vnum, _ = practicable[idx]
        _from_picker = True
    else:
        if teacher is None:
            chprintln(player, "You can't do that here.")
            return
        if player["practice"] < 1:
            chprintln(player, "You have no practice sessions left.")
            return
        arg = " ".join(args)
        sk_vnum = find_skill_spell(player, arg)
        if (sk_vnum is None or not can_use_skill_spell(player, sk_vnum)
                or player["learned"].get(sk_vnum, 0) < 1
                or skill_rating(player, sk_vnum) == 0):
            chprintln(player, "You can't practice that.")
            return
        if player["learned"][sk_vnum] >= SKILL_ADEPT:
            chprintlnf(player, "You are already learned at %s.",
                        SKILLS[sk_vnum]["name"])
            return

    int_val = get_curr_stat(player, "int")
    sk_rating = skill_rating(player, sk_vnum)
    if sk_rating == 0:
        chprintln(player, "You can't practice that.")
        return
    gain = INT_APP_LEARN[int_val] // sk_rating
    player["practice"] -= 1
    new_pct = min(SKILL_ADEPT, player["learned"][sk_vnum] + gain)
    player["learned"][sk_vnum] = new_pct
    if new_pct >= SKILL_ADEPT:
        act("You are now learned at $T.", player, None,
            SKILLS[sk_vnum]["name"], TO_CHAR)
        act("$n is now learned at $T.", player, None,
            SKILLS[sk_vnum]["name"], TO_ROOM)
    else:
        act("You practice $T.", player, None,
            SKILLS[sk_vnum]["name"], TO_CHAR)
        act("$n practices $T.", player, None,
            SKILLS[sk_vnum]["name"], TO_ROOM)
    return ("practice " + SKILLS[sk_vnum]["name"]) if _from_picker else None
