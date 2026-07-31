"""Training, practice, and remort command handlers."""

import world
from classes import (CLASS_TABLE, MAX_REMORT, calc_max_level,
                     char_classes, class_lookup, class_name,
                     exp_per_level, is_class, lvl_bonus, skill_adept_cap)
from handler import (get_curr_stat, get_max_train, act, chprintln,
                   TO_CHAR, TO_ROOM, affect_remove, unequip_char)
from util import count_str, num_str, pad_right
from config import (INT_APP_LEARN, MAX_MORTAL_LEVEL, REMORT_POWER_DIV,
                    R_STARTING_ROOM, TERMINAL_COLS)
from info import print_practice_table
from inventory import do_outfit
from picker import pick_from
from comm import do_say
from game_state import save_world
from gquest import gquester
from magic import _skill_lookup
from mob import scale_pet
from player import group_add_basics_and_defaults, reset_char
from quest import is_quester
from races import RACE_TABLE, PC_RACE_ORDER
from groups import GROUP_TABLE, gn_add, group_lookup, group_rating
from skill_utils import (can_use_skill_spell, find_skill_spell, skill_level,
                         skill_rating)
from skills_table import SKILL_TABLE, SKILLS, WEAPON_GSN_MAP, GSN_RECALL
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
        stat_opts = [(k, lng) for k, lng in _TRAIN_STATS if player["perm_stat"][k] < get_max_train(player, k)]
        vital_opts = [("max_hit", "hp"), ("max_mana", "mana")]
        all_opts = stat_opts + vital_opts
        # [PRIMESUD] Picker UI -- 1stMud prints "You can train: ..." then falls through
        # [PRIMESUD] Singular/plural fix -- 1stMud always prints "sessions"
        chprintln(player, "You have "
                  + count_str(player["train"], "training session") + ".")
        names = []
        for k, lng in all_opts:
            if k in ("max_hit", "max_mana"):
                names.append(lng + " (max: " + num_str(player[k]) + ")")
            else:
                names.append(lng + " (" + num_str(player["perm_stat"][k]) + "/" + num_str(get_max_train(player, k)) + ")")
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
                if player["perm_stat"][k] < get_max_train(player, k):
                    buf = buf + " " + lng[:3]
            buf = buf + " hp mana."
            chprintln(player, buf)
            return
        if chosen_key not in ("max_hit", "max_mana") and player["perm_stat"][chosen_key] >= get_max_train(player, chosen_key):
            act("Your $T is already at maximum.", player, None, chosen_lng, TO_CHAR)
            return

    if player["train"] < 1:
        chprintln(player, "You don't have enough training sessions.")
        return
    player["train"] -= 1
    if chosen_key == "max_hit":
        player["perm_hit"] += 10
        player["max_hit"] += 10
        player["hit"] = min(player["max_hit"], player["hit"] + 10)
        act("Your durability increases!", player, None, None, TO_CHAR)
        act("$n's durability increases!", player, None, None, TO_ROOM)
    elif chosen_key == "max_mana":
        player["perm_mana"] += 10
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
        chprintln(player, "You have "
                  + count_str(player["practice"], "practice session") + " left.")
        if teacher is None or player["practice"] < 1:
            return
        # [PRIMESUD] Picker UI for practicing skills
        learned = player["learned"]
        # [PRIMESUD] skill_adept_cap: SKILL_ADEPT + prestige tier bonus
        _adept = skill_adept_cap(player)
        practicable = [(sn, learned[sn]) for sn, sk in SKILL_TABLE
                       if (sn in learned
                           and 0 < learned[sn] < _adept
                           and can_use_skill_spell(player, sn)
                           and skill_rating(player, sn) > 0)]
        if not practicable:
            return
        # [PRIMESUD] Put skills closest to mastery first in the picker.
        practicable.sort(key=lambda entry: -entry[1])
        names = [SKILLS[vnum]["name"] + " (" + num_str(pct) + "%)" for vnum, pct in practicable]
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
        # [PRIMESUD] skill_adept_cap: SKILL_ADEPT + prestige tier bonus
        if player["learned"][sk_vnum] >= skill_adept_cap(player):
            chprintln(player, "You are already learned at "
                      + SKILLS[sk_vnum]["name"] + ".")
            return

    int_val = get_curr_stat(player, "int")
    sk_rating = skill_rating(player, sk_vnum)
    if sk_rating == 0:
        chprintln(player, "You can't practice that.")
        return
    gain = INT_APP_LEARN[int_val] // sk_rating
    player["practice"] -= 1
    # [PRIMESUD] skill_adept_cap: SKILL_ADEPT + prestige tier bonus
    _adept = skill_adept_cap(player)
    new_pct = min(_adept, player["learned"][sk_vnum] + gain)
    player["learned"][sk_vnum] = new_pct
    if new_pct >= _adept:
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


REMORT_GOLD = 500000  # cf. 1stMud do_remort: check_worth(ch, 500000, VALUE_GOLD)


def do_remort(player, args):
    """Remort into an additional class at max level (cf. 1stMud do_remort in multiclass.c).

    Requirements: at own class guild with a trainer/gainer mob present, at
    calc_max_level, REMORT_GOLD gold.
    Two-step confirm as in 1stMud (type remort twice; remort <arg> cancels).
    [PRIMESUD] nanny.c re-creation flow replaced by race + sex + class
    pickers; no immortal backup/wiznet. Race is re-pickable on EVERY remort
    -- upstream's stay_race lock (one change, then forever) is deliberately
    not ported; single-player flexibility (see DESIGN.md).
    [PRIMESUD] At MAX_REMORT classes, 1stMud's "You can't remort any more!"
    refusal becomes a prestige tier reset instead (see finish_tier_reset).

    Args:
        player (dict): Player state dict.
        args (list): Any argument cancels a pending confirm.
    """
    rs = world.rooms[player["room"]]
    # "guild" tuple from G room trailers (areas/midgaard.are)
    allowed = rs.get("guild", ())
    member = False
    for cl in allowed:
        if is_class(player, cl):
            member = True
            break
    if not member:
        chprintln(player, "You must be at your class"
                  + ("(s)" if len(player["classes"]) > 1 else "") + " guild to do that.")
        return

    trainer = None
    for mid in rs["mobs"]:
        inst = world.chars[mid]
        acts = MOB_DEFS[inst["tpl"]].get("act_flags", {})
        if acts.get("train") or acts.get("gain"):
            trainer = mid
            break
    if trainer is None:
        chprintln(player, "You can't do that here.")
        return

    if player["level"] < calc_max_level(player):
        # [PRIMESUD] plain level number; 1stMud prints high_level_name ("HERO")
        chprintln(player, "You must be level " + num_str(calc_max_level(player)) + " to remort.")
        return

    # [PRIMESUD] At full class count the remort becomes a prestige tier
    # reset (1stMud refuses here: "You can't remort any more!").
    tier_reset = len(player["classes"]) >= MAX_REMORT

    if is_quester(player) or gquester(player):
        chprintln(player, "Don't you want to finish your quest first?")
        return

    if player["gold"] < REMORT_GOLD or player.get("quest_points", 0) < 500:
        chprintln(player, "You need 500,000 gold and 500 quest points to remort.")
        return

    if not player.get("confirm_remort"):
        if args:
            chprintln(player, "Just type remort.  No argument.")
            return
        # [PRIMESUD] no stay_race FOREVER warning -- race never locks here
        chprintln(player, "{RTyping {Gremort{R with an argument will undo remort"
                  " status.  Remorting is {Wnot reversable{R; make sure you know"
                  " what {Cclass{R and {Brace{R you want to remort into."
                  "  Type {Gremort{R again to confirm.{x")
        if tier_reset:
            # [PRIMESUD] extra warning: this one is a prestige tier reset
            chprintln(player, "{RThis remort will {Wraise your tier{R: you"
                      " restart with a {Wsingle{R class, keeping only mastered"
                      " skills and permanent tier bonuses.{x")
        player["confirm_remort"] = True
        return

    if args:
        chprintln(player, "Remort status removed.")
        player["confirm_remort"] = False
        return

    # [PRIMESUD] re-creation pickers instead of nanny CON_GET_NEW_RACE /
    # CON_GET_NEW_SEX / CON_GET_NEW_CLASS; Esc at any aborts (confirm stays
    # pending, type remort again). Race offered every remort -- upstream's
    # stay_race one-change lock deliberately not ported.
    race_labels = [rn + " - " + RACE_TABLE[rn]["summary"]
                   for rn in PC_RACE_ORDER]
    ridx = pick_from("What is your race?", race_labels)
    if ridx < 0:
        return
    new_race = PC_RACE_ORDER[ridx]

    sidx = pick_from("What is your sex?", ["Male", "Female", "Neutral"])
    if sidx < 0:
        return
    new_sex = ("male", "female", "neutral")[sidx]

    if tier_reset:
        # tier reset restarts with any single class, repeats allowed
        avail = list(range(len(CLASS_TABLE)))
    else:
        avail = [i for i in range(len(CLASS_TABLE)) if i not in player["classes"]]
    labels = [CLASS_TABLE[i]["names"][0] + " - " + CLASS_TABLE[i]["summary"]
              for i in avail]
    idx = pick_from("What is your next class?", labels)
    if idx < 0:
        return
    if tier_reset:
        finish_tier_reset(player, avail[idx], new_race, new_sex)
    else:
        finish_remort(player, avail[idx], new_race, new_sex)


def do_prime(player, args):
    """Set your prime class among the classes you currently hold (cf. 1stMud
    do_prime in multiclass.c).

    Costs 5 trivia points. The prime class is a slot index into
    player["classes"] (classes.prime_class getter) -- this reassigns which
    held class is "prime" without reordering the classes list itself, same
    as upstream's ch->pcdata->prime_class = iSlot (multiclass.c:732). The
    only PrimeSUD consumer of the getter is classes.class_who() (the 2-4
    char classes tag in who-list/score); nothing else keys off list order,
    so this reassignment is safe (see docs/PARITY.md prime port-candidate
    note).

    [PRIMESUD] Upstream gates this at commands.dat level 51 (=
    MAX_MORTAL_LEVEL) via the interpreter's per-command dispatch level check
    (interp.c cmd_level_ok) -- below that level the command is invisible,
    producing the same random "Huh?" reply as an unrecognized command.
    PrimeSUD's command table has no per-command level field, so the gate is
    enforced here instead with an explicit denial message (matching
    do_remort's style above) rather than faking command-invisibility.

    Args:
        player (dict): Player state dict.
        args (list): [<class name>].
    """
    if player.get("level", 1) < MAX_MORTAL_LEVEL:
        chprintln(player, "You must be level " + num_str(MAX_MORTAL_LEVEL)
                  + " to set your prime class.")
        return

    if not args:
        chprintln(player, "Syntax: prime <class>")
        chprintln(player, "It costs {R5{x trivia points to change your prime class.")
        # 1stMud do_prime (multiclass.c:699-704) omits `return` here and
        # falls through into class_lookup("") -- every other cmd_syntax()
        # call in 1stMud returns immediately after, so this looks like a
        # copy-paste slip. Kept bug-faithful per CLAUDE.md "unsure -> keep
        # the bug, note it". The outcome matches upstream exactly: 1stMud's
        # class_lookup (handler.c:165) first-char check rejects "" (tolower
        # of NUL never equals a class initial), and classes.class_lookup("")
        # guards empty to -1 here, so both print "No such class!" after the
        # syntax banner.

    iclass = class_lookup(args[0]) if args else -1
    if iclass == -1:
        chprintln(player, "No such class!")
        return

    classes = char_classes(player)
    islot = classes.index(iclass) if iclass in classes else -1  # cf. 1stMud class_slot in multiclass.c
    if islot == -1:
        chprintln(player, "You aren't part " + class_name(player, iclass) + "!")
        return

    if islot == player.get("prime_class", 0):
        chprintln(player, "Your prime class is already " + class_name(player, iclass) + ".")
        return

    if player.get("trivia", 0) < 5:
        chprintln(player, "It costs {R5{x trivia points to change your prime class.")
        return

    player["prime_class"] = islot
    player["trivia"] -= 5
    # [PRIMESUD] upstream (multiclass.c:735) drops the "you": "and are {R5{x
    # trivia points lighter" -- grammar slip fixed per CLAUDE.md.
    chprintln(player,
              "Your prime class is now " + class_name(player, iclass)
              + ", and you are {R5{x trivia points lighter.")


def _apply_remort_race(player, race_name):
    """Apply the remort race pick (cf. 1stMud HANDLE_CON_GET_NEW_RACE in nanny.c).

    Perm stats reset to the race base (nanny.c:527 -- trained stats and the
    chargen prime +3 are lost, as upstream), race-derived fields re-derive,
    and racial skills are granted at 1%.
    [PRIMESUD] Deviations: upstream's stay_race lock (a different race is
    forever) not ported -- race is re-pickable every remort; +tier re-added
    to the reset stats so the tier stat perk survives; flag dicts replaced
    rather than OR'd with the old race's (nanny.c:529-532) -- they re-derive
    from the race name on load, so OR'd leftovers could never survive a
    save anyway; creation points not ported.

    Args:
        player (dict): Player state dict.
        race_name (str): Chosen PC race name (RACE_TABLE key).
    """
    if race_name != player["race"]:
        # cf. nanny.c:546 "You are now a %s." ([PRIMESUD] article fixed;
        # printed only on an actual change, upstream echoes every pick)
        art = "an" if race_name[0] in "AEIOU" else "a"
        chprintln(player, "{cYou are now " + art + " {W" + race_name + "{c.{x")
    player["race"] = race_name
    race = RACE_TABLE[race_name]
    stats = race.get("stats", (13, 13, 13, 13, 13))
    tier = player.get("tier", 0)
    names = ("str", "dex", "int", "wis", "con")
    for i in range(5):
        player["perm_stat"][names[i]] = stats[i]
    for st in names:
        player["perm_stat"][st] = min(player["perm_stat"][st] + tier,
                                      get_max_train(player, st))
    # race-derived fields, as create_char / load_game re-derivation
    player["size"] = race.get("size", "medium")
    player["affected_by"] = dict(race.get("aff", {}))
    player["imm_flags"] = dict(race.get("imm", {}))
    player["res_flags"] = dict(race.get("res", {}))
    player["vuln_flags"] = dict(race.get("vuln", {}))
    player["form_flags"] = dict(race.get("form", {}))
    player["part_flags"] = dict(race.get("parts", {}))
    # racial skills at 1% (cf. nanny.c:536-541 group_add loop)
    for rsk_name in race.get("skills", ()):
        sn = _skill_lookup(rsk_name)
        if sn is not None and player["learned"].get(sn, 0) == 0:
            player["learned"][sn] = 1


def finish_remort(player, new_class, new_race=None, new_sex=None):
    """Apply the remort: level 1 restart with an added class
    (cf. 1stMud finish_remort in multiclass.c).

    Args:
        player (dict): Player state dict (at max level, requirements checked).
        new_class (int): Class index to append.
        new_race (str or None): Race pick from the remort prompts; None
            keeps the current race untouched.
        new_sex (str or None): Sex pick ("male"/"female"/"neutral"); None
            keeps the current sex.
    """

    # cf. 1stMud: nanny appends the new class (CON_GET_NEW_CLASS) before
    # finish_remort computes b, and the level reset happens after -- so
    # b sees the new class count at the old level.
    player["classes"].append(new_class)
    b = lvl_bonus(player)

    for af in list(player.get("affect_list", [])):
        affect_remove(player, af)
    for slot in player["equip"]:
        if player["equip"][slot] is not None:
            unequip_char(player, slot)

    player["level"] = 1
    player["xp"] = 0
    player["gold"] -= REMORT_GOLD
    player["quest_points"] = player.get("quest_points", 0) - 500  # cf. 1stMud finish_remort
    if new_race is not None:
        _apply_remort_race(player, new_race)  # before xp_next: race class_mult
    if new_sex is not None:
        # cf. nanny.c CON_GET_NEW_SEX (remort re-asks sex like creation)
        player["sex"] = player["true_sex"] = new_sex
    # 1stMud assigns mana=max_move / move=max_mana (swapped) -- harmless
    # upstream since all three are 100*b; PrimeSUD assigns straight.
    # [PRIMESUD] Stock grants (100*b vitals, 5*b trains, 7*b practices,
    # ~6000/300/420 at first remort) scaled down by REMORT_POWER_DIV
    # (config.py) -- ~500/25/35 at the default 12; 1 restores stock.
    player["max_hit"]  = player["perm_hit"]  = 100 * b // REMORT_POWER_DIV
    player["max_mana"] = player["perm_mana"] = 100 * b // REMORT_POWER_DIV
    player["max_move"] = player["perm_move"] = 100 * b // REMORT_POWER_DIV
    player["hit"]  = player["max_hit"]
    player["mana"] = player["max_mana"]
    player["move"] = player["max_move"]
    player["wimpy"] = player["max_hit"] // 5
    player["train"] = 5 * b // REMORT_POWER_DIV
    player["practice"] = 7 * b // REMORT_POWER_DIV
    player["xp_next"] = exp_per_level(player)  # class_mult may change with new class
    reset_char(player)

    # [PRIMESUD] Pets share their owner's prestige reset instead of being purged.
    scale_pet(player, reset=True)

    # cf. 1stMud finish_remort learned loop: in-progress (<100) skills reset
    # to 1%, mastered (100) skills kept. [PRIMESUD] upstream zeroes kept-race
    # skills here (multiclass.c:217, inverted condition -- see docs/FIXES.md);
    # race skills reset to 1% like everything else (new-race skills were
    # granted in _apply_remort_race).
    learned = player["learned"]
    for sn in list(learned):
        if 0 < learned[sn] < 100:
            learned[sn] = 1
    # cf. 1stMud nanny remort flow: re-grants "rom basics" + base + default
    # groups for ALL held classes (CON_ROLL_STATS 'y' + add_default_groups).
    group_add_basics_and_defaults(player)
    # [PRIMESUD] Upstream sets weapon 40 / recall 50 BEFORE the reset loop,
    # so a 1stMud remort actually restarts them at 1%. Kinder here: set
    # after, matching fresh-char feel (see CLASS_PLAN.md Phase D).
    wgsn = WEAPON_GSN_MAP[CLASS_TABLE[new_class]["weapon"]]
    if learned.get(wgsn, 0) < 40:
        learned[wgsn] = 40
    if learned.get(GSN_RECALL, 0) < 50:
        learned[GSN_RECALL] = 50

    player["confirm_remort"] = False
    player["room"] = R_STARTING_ROOM  # cf. 1stMud char_to_room(ROOM_VNUM_SCHOOL)
    chprintln(player,
              "You are brought back to reality, and you feel quite different now...")
    do_outfit(player, "")
    save_world(quiet=True)


def finish_tier_reset(player, new_class, new_race=None, new_sex=None):
    """Apply a prestige tier reset: restart with a single class and permanent
    tier perks. [PRIMESUD] -- no 1stMud equivalent; mirrors finish_remort's
    sequence but restarts near-fresh instead of the 100*lvl_bonus power dump.

    Perks per tier: +50 hp/mana/move base, +1 train/practice grants, +1 all
    perm stats (get_max_train cap rises with tier), non-mastered skills floor
    at 10*tier instead of 1%, practice ceiling +5 (skill_adept_cap), mastered
    skills kept (dormant until a learning class is held again -- skill_level
    semantics unchanged). See DESIGN.md multiclass tiering.

    Args:
        player (dict): Player state dict (at max level/classes, gates checked).
        new_class (int): Class index to restart with (repeats allowed).
        new_race (str or None): Race pick from the remort prompts; None
            keeps the current race untouched.
        new_sex (str or None): Sex pick ("male"/"female"/"neutral"); None
            keeps the current sex.
    """

    tier = player.get("tier", 0) + 1
    player["tier"] = tier

    for af in list(player.get("affect_list", [])):
        affect_remove(player, af)
    for slot in player["equip"]:
        if player["equip"][slot] is not None:
            unequip_char(player, slot)

    player["classes"] = [new_class]
    player["prime_class"] = 0
    player["level"] = 1
    player["xp"] = 0
    player["gold"] -= REMORT_GOLD
    player["quest_points"] = player.get("quest_points", 0) - 500
    # near-fresh pools: create_char baselines (50/100/100) + 50 per tier
    player["max_hit"]  = player["perm_hit"]  = 50 + 50 * tier
    player["max_mana"] = player["perm_mana"] = 100 + 50 * tier
    player["max_move"] = player["perm_move"] = 100 + 50 * tier
    player["hit"]  = player["max_hit"]
    player["mana"] = player["max_mana"]
    player["move"] = player["max_move"]
    player["wimpy"] = player["max_hit"] // 5
    player["train"] = 5 + tier
    player["practice"] = 7 + tier
    if new_race is not None:
        # stats reset to race base + tier: the tier stat perk lives in
        # _apply_remort_race's +tier (race prompt runs on every remort)
        _apply_remort_race(player, new_race)
    else:
        # direct-call fallback (do_remort always passes a race): +1 all perm
        # stats, capped at the (tier-raised) trainable maximum
        for st in ("str", "dex", "int", "wis", "con"):
            if player["perm_stat"][st] < get_max_train(player, st):
                player["perm_stat"][st] += 1
    if new_sex is not None:
        # cf. nanny.c CON_GET_NEW_SEX (remort re-asks sex like creation)
        player["sex"] = player["true_sex"] = new_sex
    player["xp_next"] = exp_per_level(player)  # class_mult follows the new class
    reset_char(player)

    # [PRIMESUD] One optional evolution step per tier; unlinked pets still scale.
    scale_pet(player, evolve=True, reset=True)

    # mastered (100) skills kept as in finish_remort; in-progress skills
    # floor at 10*tier instead of 1
    learned = player["learned"]
    floor = 10 * tier
    for sn in list(learned):
        if 0 < learned[sn] < 100:
            learned[sn] = max(1, min(learned[sn], floor))
    group_add_basics_and_defaults(player)
    # same weapon-40 / recall-50 kindness floors as finish_remort
    wgsn = WEAPON_GSN_MAP[CLASS_TABLE[new_class]["weapon"]]
    if learned.get(wgsn, 0) < 40:
        learned[wgsn] = 40
    if learned.get(GSN_RECALL, 0) < 50:
        learned[GSN_RECALL] = 50

    player["confirm_remort"] = False
    player["room"] = R_STARTING_ROOM
    chprintln(player,
              "The world unravels and reforms around you; you begin anew,"
              " yet something of your old self remains...")
    do_outfit(player, "")
    save_world(quiet=True)


def _print_two_col(player, items):
    """Print items two per line, half-width columns (cf. print_practice_table
    in info.py). [PRIMESUD]"""
    half = TERMINAL_COLS // 2
    for i in range(0, len(items), 2):
        line = items[i]
        if i + 1 < len(items):
            line = line + " " * (half - len(line)) + items[i + 1]
        chprintln(player, line)


def do_gain(player, args):
    """Buy skill groups or non-spell skills with trains at a gain trainer
    (cf. 1stMud do_gain in skills.c).

    gain list / gain convert (10 practices -> 1 train; leading count
    multiplies, "gain 3 convert") / gain <group> / gain <skill>. Spells
    can only be gained via their group.
    [PRIMESUD] "gain points" not ported -- no creation-point economy
    (see groups.py).

    Args:
        player (dict): Player state dict.
        args (list): Parsed command words.
    """
    rs = world.rooms[player["room"]]
    trainer = None
    for mid in rs["mobs"]:
        inst = world.chars[mid]
        if MOB_DEFS[inst["tpl"]].get("act_flags", {}).get("gain"):
            trainer = inst
            break
    if trainer is None:
        chprintln(player, "You can't do that here.")
        return

    # cf. 1stMud mult_argument: optional leading count
    mult = 1
    if args and args[0].isdigit():
        mult = max(1, int(args[0]))
        args = args[1:]

    if not args:
        do_say(trainer, "Pardon me?")
        return

    arg = " ".join(args)

    if "list".startswith(args[0]):
        # [PRIMESUD] two columns per line (practice-table style); 1stMud
        # prints 3-column tables
        known = player["groups"]
        learned = player["learned"]
        half = TERMINAL_COLS // 2
        hdr = "Group              Cost"
        chprintln(player, "{w" + hdr + " " * (half - len(hdr)) + hdr + "{x")
        items = []
        for gn in range(len(GROUP_TABLE)):
            val = group_rating(player, gn)
            if gn not in known and val > 0:
                items.append(pad_right(GROUP_TABLE[gn][0], 18) + " " + num_str(val))
        _print_two_col(player, items)
        chprintln(player, "")
        hdr = "Skill              Cost Lev"
        chprintln(player, "{w" + hdr + " " * (half - len(hdr)) + hdr + "{x")
        items = []
        for sn, sk in SKILL_TABLE:
            val = skill_rating(player, sn)
            if (learned.get(sn, 0) == 0 and val > 0
                    and sk["spell_fun"] == 'spell_null'):
                items.append(pad_right(sk["name"], 18) + " " + pad_right(num_str(val), 4)
                             + " " + num_str(skill_level(player, sn)))
        _print_two_col(player, items)
        # cf. 1stMud intstr(ch->train, "train")
        chprintln(player, "You have "
                  + count_str(player["train"], "train") + " left.")
        return

    if "convert".startswith(args[0]):
        if player["practice"] < 10 * mult:
            act("$N tells you 'You are not yet ready.'", player, None,
                trainer, TO_CHAR)
            return
        act("$N helps you apply your practice to training", player, None,
            trainer, TO_CHAR)
        player["practice"] -= 10 * mult
        player["train"] += mult
        return

    # [not ported] 1stMud "gain points" refunds creation points -- no
    # creation-point economy in PrimeSUD (see groups.py).

    gn = group_lookup(arg)
    if gn >= 0:
        if gn in player["groups"]:
            act("$N tells you 'You already know that group!'", player, None,
                trainer, TO_CHAR)
            return
        val = group_rating(player, gn)
        if val < 1:
            act("$N tells you 'That group is beyond your powers.'", player,
                None, trainer, TO_CHAR)
            return
        if player["train"] < val:
            act("$N tells you 'You are not yet ready for that group.'",
                player, None, trainer, TO_CHAR)
            return
        gn_add(player, gn)
        act("$N trains you in the art of $t", player, GROUP_TABLE[gn][0],
            trainer, TO_CHAR)
        player["train"] -= val
        return

    sn = find_skill_spell(player, arg)
    if sn is not None:
        if SKILLS[sn]["spell_fun"] != 'spell_null':
            act("$N tells you 'You must learn the full group.'", player,
                None, trainer, TO_CHAR)
            return
        if player["learned"].get(sn, 0):
            act("$N tells you 'You already know that skill!'", player, None,
                trainer, TO_CHAR)
            return
        val = skill_rating(player, sn)
        if val < 1:
            act("$N tells you 'That skill is beyond your powers.'", player,
                None, trainer, TO_CHAR)
            return
        if player["train"] < val:
            act("$N tells you 'You are not yet ready for that skill.'",
                player, None, trainer, TO_CHAR)
            return
        player["learned"][sn] = 1
        act("$N trains you in the art of $t", player, SKILLS[sn]["name"],
            trainer, TO_CHAR)
        player["train"] -= val
        return

    act("$N tells you 'I do not understand...'", player, None, trainer,
        TO_CHAR)
