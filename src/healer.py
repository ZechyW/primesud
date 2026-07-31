"""Healer NPC services (cf. 1stMud healer.c)."""

import world
from combat import dice
from handler import act, chprintln, TO_CHAR, TO_ROOM
from config import PULSE_VIOLENCE
from skill_utils import WaitState
from magic import SPELL_FUNS, TARGET_CHAR, _skill_lookup
from skills_table import SKILLS
from shop import check_worth, deduct_cost, add_cost
from util import num_str, pad_left

# (name, descr, spell name for _skill_lookup or None=mana, words, cost in gold)
# cf. 1stMud healer_table in healer.c
_HEALER_TABLE = (
    ("light",     "cure light wounds",    "cure light",     "judicandus dies",     10),
    ("serious",   "cure serious wounds",  "cure serious",   "judicandus gzfuajg",  16),
    ("critical",  "cure critical wounds", "cure critical",  "judicandus qfuhuqar", 25),
    ("heal",      "healing spell",        "heal",           "pzar",                50),
    ("blindness", "cure blindness",       "cure blindness", "judicandus noselacri", 20),
    ("disease",   "cure disease",         "cure disease",   "judicandus eugzagz",  15),
    ("poison",    "cure poison",          "cure poison",    "judicandus sausabru", 25),
    ("uncurse",   "remove a curse",       "remove curse",   "candussido judifgz",  50),
    ("refresh",   "restore movement",     "refresh",        "candusima",            5),
    ("mana",      "restore mana",         None,             "energizer",           10),
)


def do_heal(player, args):
    """Buy a healing spell from a healer NPC in the room (cf. 1stMud do_heal in healer.c)."""

    mob = None
    for mid in world.rooms[player["room"]]["mobs"]:
        inst = world.chars.get(mid)
        if inst is not None and inst.get("act_flags", {}).get("healer"):
            mob = inst
            break

    if mob is None:
        chprintln(player, "You can't do that here.")
        return

    if not args:
        act("$N says 'I offer the following spells:'", player, None, mob, TO_CHAR)
        for name, descr, _spell, _words, cost in _HEALER_TABLE:
            chprintln(player, "  " + pad_left(name, 12) + ": " + pad_left(descr, 24)
                      + " " + num_str(cost) + " gold")
        chprintln(player, "  Type heal <type> to be healed.")
        return

    entry = None
    for row in _HEALER_TABLE:
        if row[0].startswith(args[0]):
            entry = row
            break

    if entry is None:
        act("$N says 'Type 'heal' for a list of spells.'", player, None, mob, TO_CHAR)
        return

    name, descr, spell_name, words, cost = entry
    # cf. check_worth(ch, cost, VALUE_GOLD): costs are gold; wallet in silver units
    if not check_worth(player, cost * 100):
        act("$N says 'You do not have enough gold for my services.'",
            player, None, mob, TO_CHAR)
        return

    WaitState(player, PULSE_VIOLENCE)

    deduct_cost(player, cost * 100)
    add_cost(mob, cost * 100)
    act("$n utters the words '$T'.", mob, None, words, TO_ROOM)

    if spell_name is None:
        player["mana"] = min(player["mana"] + dice(2, 8) + mob["level"] // 3,
                             player["max_mana"])
        chprintln(player, "A warm glow passes through you.")
        return

    sn = _skill_lookup(spell_name)
    if sn is None:
        return
    fun = SPELL_FUNS.get(SKILLS[sn].get("spell_fun", ""))
    if fun is None:
        return
    # cf. TARGET_CHAR spell call: (*spell)(sn, mob->level, mob, ch, TARGET_CHAR)
    mob["_target_name"] = ""
    fun(sn, mob["level"], mob, player, TARGET_CHAR)
    if "_target_name" in mob:
        del mob["_target_name"]
