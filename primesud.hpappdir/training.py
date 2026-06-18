from world import MOB_TEMPLATES, SKILLS
from picker import pick_from
from actor import get_curr_stat
from config import INT_APP_LEARN, MAX_STATS


_TRAIN_STATS = [
    ("str", "strength"),
    ("dex", "dexterity"),
    ("int", "intelligence"),
    ("wis", "wisdom"),
    ("con", "constitution"),
]

_PRACTICE_CAP = 75  # matches 1stMud skill_adept for all classes


def _print_skills(tr, player):
    for sk_vnum, pct in sorted(player["learned"].items()):
        sk = SKILLS.get(sk_vnum)
        if sk is None:
            continue
        if sk.get("spell_fun", "spell_null") != "spell_null":
            tr.print("  cast {} {}% (MP:{})".format(
                sk["name"], pct, sk.get("min_mana", 0)))
        else:
            tr.print("  {} {}%".format(sk["name"], pct))


def do_train(tr, player, args, world):
    """Permanently raise a stat or vital by spending a train point (cf. 1stMud do_train in act_move.c).

    Requires a mob with act_flags["train"] in the room.  Stats cap at MAX_STATS;
    hp and mana training raise hp_max/mp_max by 10 with no cap.

    Args:
        tr: Terminal instance.
        player (dict): Player state dict.
        args (list): Parsed command words; optional stat/vital name.
        world (dict): Game world state (keys: rooms, mobs, areas).
    """
    rs = world["rooms"][player["room"]]
    trainer = None
    for mid in rs["mobs"]:
        inst = world["mobs"][mid]
        if MOB_TEMPLATES[inst["tpl"]].get("act_flags", {}).get("train"):
            trainer = mid
            break
    if trainer is None:
        tr.print("You can't do that here.")
        return

    if not args:
        if player["train"] < 1:
            tr.print("You don't have any training sessions.")
            return
        stat_opts = [(k, lng) for k, lng in _TRAIN_STATS if player[k] < MAX_STATS]
        vital_opts = [("hp_max", "hp"), ("mp_max", "mana")]
        all_opts = stat_opts + vital_opts
        tr.print("You have {} training session{}.".format(
            player["train"], "" if player["train"] == 1 else "s"))
        names = []
        for k, lng in all_opts:
            if k in ("hp_max", "mp_max"):
                names.append("{} (max: {})".format(lng, player[k]))
            else:
                names.append("{} ({}/{})".format(lng, player[k], MAX_STATS))
        idx = pick_from(tr, "Train which?", names)
        if idx < 0:
            return
        chosen_key, chosen_lng = all_opts[idx]
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
            tr.print("Your {} is already at maximum.".format(chosen_lng))
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
        tr.print("Your {} increases!".format(chosen_lng))


def do_practice(tr, player, args, world):
    """Improve a skill percentage using a practice point (cf. 1stMud do_practice in act_info.c).

    Without an argument and no teacher: lists skills + practice count (1stMud parity).
    Without an argument and teacher present: picker of under-cap skills [PRIMESUD].
    With a skill name: requires a mob with act_flags["practice"] in the room.

    Args:
        tr: Terminal instance.
        player (dict): Player state dict.
        args (list): Parsed command words; optional skill name.
        world (dict): Game world state (keys: rooms, mobs, areas).
    """
    rs = world["rooms"][player["room"]]
    teacher = None
    for mid in rs["mobs"]:
        inst = world["mobs"][mid]
        if MOB_TEMPLATES[inst["tpl"]].get("act_flags", {}).get("practice"):
            teacher = mid
            break

    if not args:
        if teacher is None:
            _print_skills(tr, player)
            tr.print("You have {} practice session{}.".format(
                player["practice"], "" if player["practice"] == 1 else "s"))
            return
        if player["practice"] < 1:
            tr.print("You have no practice sessions left.")
            return
        practicable = [(vnum, pct) for vnum, pct in player["learned"].items()
                       if 0 < pct < _PRACTICE_CAP and SKILLS.get(vnum)]
        if not practicable:
            tr.print("You have nothing left to practice.")
            return
        tr.print("You have {} practice session{}.".format(
            player["practice"], "" if player["practice"] == 1 else "s"))
        names = ["{} ({}%)".format(SKILLS[vnum]["name"], pct) for vnum, pct in practicable]
        idx = pick_from(tr, "Practice which skill?", names)
        if idx < 0:
            return
        sk_vnum, _ = practicable[idx]
    else:
        if teacher is None:
            tr.print("You can't do that here.")
            return
        if player["practice"] < 1:
            tr.print("You have no practice sessions left.")
            return
        arg = " ".join(args)
        sk_vnum = None
        for vnum in player["learned"]:
            sk = SKILLS.get(vnum)
            if sk and sk["name"].startswith(arg):
                sk_vnum = vnum
                break
        if sk_vnum is None:
            tr.print("You don't know that skill.")
            return
        if player["learned"][sk_vnum] >= _PRACTICE_CAP:
            tr.print("You are already learned at {}.".format(SKILLS[sk_vnum]["name"]))
            return
        if player["learned"][sk_vnum] < 1:
            tr.print("You can't practice that.")
            return

    int_val = get_curr_stat(player, "int")
    sk_rating = SKILLS[sk_vnum].get("rating", 1)
    if sk_rating == 0:
        tr.print("You can't practice that.")
        return
    gain = INT_APP_LEARN[int_val] // sk_rating
    player["practice"] -= 1
    new_pct = min(_PRACTICE_CAP, player["learned"][sk_vnum] + gain)
    player["learned"][sk_vnum] = new_pct
    if new_pct >= _PRACTICE_CAP:
        tr.print("You are now learned at {}.".format(SKILLS[sk_vnum]["name"]))
    else:
        tr.print("You practice {}.".format(SKILLS[sk_vnum]["name"]))
