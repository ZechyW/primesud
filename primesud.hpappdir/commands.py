from world import ROOMS, ITEM_TEMPLATES, MOB_TEMPLATES, SKILLS, SK_ATTACK
from player import get_curr_stat, get_obj_list, get_char_room, save_char
from combat import set_fighting, do_flee, use_skill


# ── Commands (cf. 1stMud do_* in interp.c / fight.c) ─────────────────────────

def do_look(tr, player, args, room_state, mob_instances, _long=True):
    room = ROOMS[player["room"]]
    tr.print("[ {} ]".format(room["name"]))
    tr.print(room["long"] if _long else room["short"])
    rs = room_state[player["room"]]
    exits = " ".join(room["exits"].keys()).upper()
    tr.print("Exits: {}".format(exits) if exits else "Exits: none")
    if rs["items"]:
        names = ", ".join(ITEM_TEMPLATES[v]["name"] for v in rs["items"])
        tr.print("Items: {}".format(names))
    live_mobs = [i for i in rs["mobs"] if mob_instances[i]["state"] != "dead"]
    if live_mobs:
        names = ", ".join(MOB_TEMPLATES[mob_instances[i]["tpl"]]["name"] for i in live_mobs)
        tr.print("Mobs:  {}".format(names))


def do_move(tr, player, direction, room_state, mob_instances):
    exits = ROOMS[player["room"]]["exits"]
    if direction not in exits:
        tr.print("No exit to the {}.".format(direction))
        return
    player["room"] = exits[direction]
    tr.print("")
    do_look(tr, player, [], room_state, mob_instances, _long=False)


def do_get(tr, player, args, room_state, mob_instances):
    if not args:
        tr.print("Get what?")
        return
    rs = room_state[player["room"]]
    vnum = get_obj_list(" ".join(args), rs["items"], ITEM_TEMPLATES)
    if vnum is None:
        tr.print("Nothing here called that.")
        return
    rs["items"].remove(vnum)
    player["inv"].append(vnum)
    tr.print("You take the {}.".format(ITEM_TEMPLATES[vnum]["name"]))


def do_drop(tr, player, args, room_state, mob_instances):
    if not args:
        tr.print("Drop what?")
        return
    vnum = get_obj_list(" ".join(args), player["inv"], ITEM_TEMPLATES)
    if vnum is None:
        tr.print("You're not carrying that.")
        return
    player["inv"].remove(vnum)
    room_state[player["room"]]["items"].append(vnum)
    tr.print("You drop the {}.".format(ITEM_TEMPLATES[vnum]["name"]))


def do_inventory(tr, player, args, room_state, mob_instances):
    if not player["inv"]:
        tr.print("You carry nothing.")
        return
    counts = {}
    for v in player["inv"]:
        counts[v] = counts.get(v, 0) + 1
    for v, n in counts.items():
        name = ITEM_TEMPLATES[v]["name"]
        tr.print("  {} x{}".format(name, n) if n > 1 else "  {}".format(name))


def do_wear(tr, player, args, room_state, mob_instances):
    if not args:
        tr.print("Equip what?")
        return
    vnum = get_obj_list(" ".join(args), player["inv"], ITEM_TEMPLATES)
    if vnum is None:
        tr.print("You're not carrying that.")
        return
    tpl = ITEM_TEMPLATES[vnum]
    slot = tpl.get("slot")
    if slot is None:
        tr.print("That can't be equipped.")
        return
    if player["equip"][slot] is not None:
        player["inv"].append(player["equip"][slot])
    player["inv"].remove(vnum)
    player["equip"][slot] = vnum
    tr.print("You equip the {}.".format(tpl["name"]))


def do_remove(tr, player, args, room_state, mob_instances):
    if not args:
        tr.print("Remove which slot?")
        return
    slot = args[0].lower()
    if slot not in player["equip"]:
        tr.print("No such slot.")
        return
    vnum = player["equip"][slot]
    if vnum is None:
        tr.print("Nothing equipped there.")
        return
    player["inv"].append(vnum)
    player["equip"][slot] = None
    tr.print("You unequip the {}.".format(ITEM_TEMPLATES[vnum]["name"]))


def do_quaff(tr, player, args, room_state, mob_instances):
    if not args:
        tr.print("Use what?")
        return
    vnum = get_obj_list(" ".join(args), player["inv"], ITEM_TEMPLATES)
    if vnum is None:
        tr.print("You're not carrying that.")
        return
    tpl = ITEM_TEMPLATES[vnum]
    if tpl["type"] != "consumable":
        tr.print("You can't use that.")
        return
    player["inv"].remove(vnum)
    if "use_hp" in tpl:
        gained = min(tpl["use_hp"], player["hp_max"] - player["hp"])
        player["hp"] += gained
        tr.print("You drink the {}. +{} HP. ({}/{})".format(
            tpl["name"], gained, player["hp"], player["hp_max"]))


def do_score(tr, player, args, room_state, mob_instances):
    tr.print("Level {} ({}/{} XP)".format(player["level"], player["xp"], player["xp_next"]))
    tr.print("HP:{}/{} MP:{}/{}".format(player["hp"], player["hp_max"], player["mp"], player["mp_max"]))
    tr.print("STR:{} DEX:{} INT:{} CON:{}".format(
        player["str"], player["dex"], player["int"], player["con"]))
    tr.print("ATK:{} DEF:{}".format(get_curr_stat(player, "atk"), get_curr_stat(player, "def")))
    equipped = {s: ITEM_TEMPLATES[v]["name"] for s, v in player["equip"].items() if v is not None}
    if equipped:
        tr.print("")
        for slot, name in equipped.items():
            tr.print("  {}: {}".format(slot, name))


def do_skills(tr, player, args, room_state, mob_instances):
    for sk_vnum in player["skills"]:
        sk = SKILLS[sk_vnum]
        tr.print("  {} (MP:{})".format(sk["name"], sk["mp_cost"]))


def do_help(tr, player, args, room_state, mob_instances):
    tr.print("Move: 7 8 9 / 4 5 6 / 1 2 3 (or n/s/e/w/ne/...)")
    tr.print("5=look  i=inv  equip  unequip  u=use  st=stats")
    tr.print("sk=skills  l=look  k/kill=fight  flee  save  q=quit")


def do_kill(tr, player, args, room_state, mob_instances):
    if player["fighting"] is not None:
        tr.print("You are already fighting!")
        return
    rs = room_state[player["room"]]
    live = [i for i in rs["mobs"] if mob_instances[i]["state"] != "dead"]
    if not live:
        tr.print("No enemies here.")
        return
    if args:
        mob_id = get_char_room(" ".join(args), live, mob_instances)
        if mob_id is None:
            tr.print("No such enemy.")
            return
    else:
        mob_id = live[0]
    set_fighting(tr, player, mob_id, mob_instances, room_state)


def do_save(tr, player, args, room_state, mob_instances):
    ok = save_char(player, room_state, mob_instances)
    tr.print("Saved." if ok else "Save failed.")


def do_quit(tr, player, args, room_state, mob_instances):
    return "quit"


# ── Direction map ─────────────────────────────────────────────────────────────

_DIRECTION_MAP = {
    "n": "n", "north": "n",
    "s": "s", "south": "s",
    "e": "e", "east": "e",
    "w": "w", "west": "w",
    "ne": "ne", "northeast": "ne",
    "nw": "nw", "northwest": "nw",
    "se": "se", "southeast": "se",
    "sw": "sw", "southwest": "sw",
    # Numpad digit shortcuts (1-9, matching compass layout)
    "7": "nw", "8": "n", "9": "ne",
    "4": "w",              "6": "e",
    "1": "sw", "2": "s",  "3": "se",
}

# Maps digit chars to the display text shown in the input buffer.
_DIGIT_SUBST = {
    "1": "sw", "2": "s",  "3": "se",
    "4": "w",              "6": "e",
    "7": "nw", "8": "n",  "9": "ne",
    "5": "look",
}

# ── Command table (cf. 1stMud cmd_table[] in interp.c) ───────────────────────

_CMD_TABLE = {
    "i":        do_inventory,
    "inv":      do_inventory,
    "l":        do_look,
    "look":     do_look,
    "st":       do_score,
    "stats":    do_score,
    "score":    do_score,
    "sk":       do_skills,
    "skills":   do_skills,
    "get":      do_get,
    "take":     do_get,
    "drop":     do_drop,
    "equip":    do_wear,
    "wear":     do_wear,
    "unequip":  do_remove,
    "remove":   do_remove,
    "u":        do_quaff,
    "use":      do_quaff,
    "quaff":    do_quaff,
    "k":        do_kill,
    "kill":     do_kill,
    "f":        do_kill,
    "fight":    do_kill,
    "flee":     do_flee,
    "fl":       do_flee,
    "save":     do_save,
    "h":        do_help,
    "help":     do_help,
    "?":        do_help,
    "q":        do_quit,
    "quit":     do_quit,
}


# ── Interpreter (cf. 1stMud interpret() in interp.c) ─────────────────────────

def interpret(raw, tr, player, room_state, mob_instances):
    parts = raw.strip().lower().split()
    if not parts:
        return None
    verb = parts[0]
    args = parts[1:]

    direction = _DIRECTION_MAP.get(verb)
    if direction is not None:
        do_move(tr, player, direction, room_state, mob_instances)
        return None

    fn = _CMD_TABLE.get(verb)
    if fn is not None:
        return fn(tr, player, args, room_state, mob_instances)

    # Skill name dispatch (excludes SK_ATTACK which is auto-attack only)
    for sk_vnum in player["skills"]:
        if sk_vnum == SK_ATTACK:
            continue
        if verb == SKILLS[sk_vnum]["name"].lower():
            if player["fighting"] is None:
                tr.print("You're not in combat.")
            elif player["mp"] < SKILLS[sk_vnum]["mp_cost"]:
                tr.print("Not enough MP!")
            else:
                player["mp"] -= SKILLS[sk_vnum]["mp_cost"]
                use_skill(tr, player, sk_vnum, mob_instances, room_state)
            return None

    tr.print("Unknown command. ? for help.")
    return None
