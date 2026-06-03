from world import ROOMS, ITEM_TEMPLATES, MOB_TEMPLATES, SKILLS, R_VILLAGE_SQUARE
from player import player_stat, resolve_name, resolve_mob_name, save_game
from combat import combat_loop


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_look(tr, player, room_state, mob_instances, long=False):
    tr.print("")
    room = ROOMS[player["room"]]
    tr.print("[ {} ]".format(room["name"]))
    tr.print(room["long"] if long else room["short"])
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


def cmd_move(tr, player, direction, room_state, mob_instances):
    exits = ROOMS[player["room"]]["exits"]
    if direction not in exits:
        tr.print("No exit to the {}.".format(direction))
        return
    player["room"] = exits[direction]
    cmd_look(tr, player, room_state, mob_instances)


def cmd_take(tr, player, args, room_state):
    if not args:
        tr.print("Take what?")
        return
    rs = room_state[player["room"]]
    vnum = resolve_name(" ".join(args), rs["items"], ITEM_TEMPLATES)
    if vnum is None:
        tr.print("Nothing here called that.")
        return
    rs["items"].remove(vnum)
    player["inv"].append(vnum)
    tr.print("You take the {}.".format(ITEM_TEMPLATES[vnum]["name"]))


def cmd_drop(tr, player, args, room_state):
    if not args:
        tr.print("Drop what?")
        return
    vnum = resolve_name(" ".join(args), player["inv"], ITEM_TEMPLATES)
    if vnum is None:
        tr.print("You're not carrying that.")
        return
    player["inv"].remove(vnum)
    room_state[player["room"]]["items"].append(vnum)
    tr.print("You drop the {}.".format(ITEM_TEMPLATES[vnum]["name"]))


def cmd_inv(tr, player):
    if not player["inv"]:
        tr.print("You carry nothing.")
        return
    counts = {}
    for v in player["inv"]:
        counts[v] = counts.get(v, 0) + 1
    for v, n in counts.items():
        name = ITEM_TEMPLATES[v]["name"]
        tr.print("  {} x{}".format(name, n) if n > 1 else "  {}".format(name))


def cmd_equip(tr, player, args):
    if not args:
        tr.print("Equip what?")
        return
    vnum = resolve_name(" ".join(args), player["inv"], ITEM_TEMPLATES)
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


def cmd_unequip(tr, player, args):
    if not args:
        tr.print("Unequip which slot?")
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


def cmd_use(tr, player, args):
    if not args:
        tr.print("Use what?")
        return
    vnum = resolve_name(" ".join(args), player["inv"], ITEM_TEMPLATES)
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


def cmd_stats(tr, player):
    tr.print("Level {} ({}/{} XP)".format(player["level"], player["xp"], player["xp_next"]))
    tr.print("HP:{}/{} MP:{}/{}".format(player["hp"], player["hp_max"], player["mp"], player["mp_max"]))
    tr.print("STR:{} DEX:{} INT:{} CON:{}".format(
        player["str"], player["dex"], player["int"], player["con"]))
    tr.print("ATK:{} DEF:{}".format(player_stat(player, "atk"), player_stat(player, "def")))
    equipped = {s: ITEM_TEMPLATES[v]["name"] for s, v in player["equip"].items() if v is not None}
    if equipped:
        tr.print("")
        for slot, name in equipped.items():
            tr.print("  {}: {}".format(slot, name))


def cmd_skills(tr, player):
    for sk_vnum in player["skills"]:
        sk = SKILLS[sk_vnum]
        tr.print("  {} (MP:{})".format(sk["name"], sk["mp_cost"]))


def cmd_help(tr):
    tr.print("Move: 7 8 9 / 4 5 6 / 1 2 3 (or n/s/e/w/ne/...)")
    tr.print("5=look  i=inv  equip  unequip  u=use  st=stats")
    tr.print("k=skills  l=look  f=fight  save  q=quit")


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


def _dispatch_command(raw, tr, player, room_state, mob_instances):
    parts = raw.strip().lower().split()
    if not parts:
        return None
    verb = parts[0]
    args = parts[1:]

    if verb == "5":
        cmd_look(tr, player, room_state, mob_instances, long=True)
        return None

    if verb in _DIRECTION_MAP:
        cmd_move(tr, player, _DIRECTION_MAP[verb], room_state, mob_instances)
        return None

    if verb in ("i", "inv"):
        cmd_inv(tr, player)
    elif verb in ("st", "stats"):
        cmd_stats(tr, player)
    elif verb in ("k", "skills"):
        cmd_skills(tr, player)
    elif verb in ("l", "look"):
        cmd_look(tr, player, room_state, mob_instances, long=True)
    elif verb == "take":
        cmd_take(tr, player, args, room_state)
    elif verb == "drop":
        cmd_drop(tr, player, args, room_state)
    elif verb == "equip":
        cmd_equip(tr, player, args)
    elif verb == "unequip":
        cmd_unequip(tr, player, args)
    elif verb == "use":
        cmd_use(tr, player, args)
    elif verb in ("f", "fight"):
        _cmd_fight(tr, player, args, room_state, mob_instances)
    elif verb == "save":
        ok = save_game(player, room_state, mob_instances)
        tr.print("Saved." if ok else "Save failed.")
    elif verb in ("h", "help", "?"):
        cmd_help(tr)
    elif verb in ("q", "quit"):
        return "quit"
    else:
        tr.print("Unknown command. ? for help.")
    return None


def _cmd_fight(tr, player, args, room_state, mob_instances):
    rs = room_state[player["room"]]
    live = [i for i in rs["mobs"] if mob_instances[i]["state"] != "dead"]
    if not live:
        tr.print("No enemies here.")
        return
    if args:
        mob_iid = resolve_mob_name(" ".join(args), live, mob_instances)
        if mob_iid is None:
            tr.print("No such enemy.")
            return
    else:
        mob_iid = live[0]

    result = combat_loop(tr, player, mob_iid, mob_instances, room_state)
    if result == "dead":
        tr.print("Game over.")
        player["hp"] = player["hp_max"]
        player["mp"] = player["mp_max"]
        player["room"] = R_VILLAGE_SQUARE
        cmd_look(tr, player, room_state, mob_instances)
    elif result == "victory":
        cmd_look(tr, player, room_state, mob_instances)
