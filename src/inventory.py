"""Inventory, equipment, item-use, and starter-outfit commands."""

import world
from handler import (get_curr_stat, is_name, equip_char, unequip_char, act,
                     get_char_room, can_see, can_see_obj, is_awake,
                     affect_strip, affect_join, chprintln, chprintlnf,
                     is_good, is_evil, is_neutral,
                     TO_CHAR, TO_ROOM, TO_VICT, TO_NOTVICT)
from world import (OBJ_VNUM_SCHOOL_BANNER,
                   OBJ_VNUM_SCHOOL_MACE, OBJ_VNUM_SCHOOL_DAGGER, OBJ_VNUM_SCHOOL_SWORD,
                   OBJ_VNUM_SCHOOL_VEST, OBJ_VNUM_SCHOOL_SHIELD,
                   OBJ_VNUM_SCHOOL_STAFF, OBJ_VNUM_SCHOOL_AXE, OBJ_VNUM_SCHOOL_FLAIL,
                   OBJ_VNUM_SCHOOL_WHIP, OBJ_VNUM_SCHOOL_POLEARM)
from combat import (_get_weapon_skill, is_safe, multi_hit, number_fuzzy,
                    create_money, _get_size)
from comm import do_yell
from debug import DBG  # [PRIMESUD] debug vnum visibility toggle
from skill_utils import WaitState, check_improve, get_skill
from config import (STR_APP_WIELD, PULSE_VIOLENCE, WEAR_LABELS,
                    MAX_LEVEL, MAX_MORTAL_LEVEL, TYPE_UNDEFINED,
                    ATTACK_TABLE, DAM_BASH, SIZE_RANK)
from item import (get_obj_list, get_obj_here, obj_vnum, create_object,
                  item_extra_flags, item_wear_flags, apply_money_pickup,
                  can_drop_obj, can_carry_n, can_carry_w, get_obj_weight,
                  get_carry_weight,
                  item_weapon_flags, item_affect_to_obj,
                  item_container_flags, set_item_container_flag,
                  CONTAINER_TYPES,
                  item_type as _item_type,
                  promote_obj as _promote_obj,
                  liquid_left as _liquid_left,
                  liquid_total as _liquid_total,
                  liquid_type as _liquid_type,
                  set_liquid as _set_liquid,
                  liq_sip as _liq_sip)
from magic import (_skill_lookup, cast_item_spells, validate_item_spell_payload,
                   _new_affect, _skill_lookup)
from picker import pick_from
from quest import (quest_obj_check, is_quester, QUEST_DELIVER,
                   QUEST_RETURN_DELIVER, _giver_name)
from skills_table import (GSN_SCROLLS, GSN_STAVES, GSN_WANDS, GSN_STEAL,
                          GSN_SNEAK, GSN_ENVENOM, GSN_POISON)
from skills_table import SKILLS, WEAPON_GSN_MAP
from terminal import tprint
from urandom import randint
from world import ITEM_DEFS, MOB_DEFS

_CONTAINER_TYPES = CONTAINER_TYPES  # [PRIMESUD] shared definition now lives in item.py




def _loot_container_picker(player, container):
    """Present picker UI to loot items from a container. [PRIMESUD]

    cf. 1stMud do_get CONT_CLOSED check (act_obj.c:280) -- closed containers
    can't be looted, checked before the no-arg [loot] picker shown here.
    """
    cont_tpl = ITEM_DEFS[obj_vnum(container)]
    if item_container_flags(container, cont_tpl).get("closed"):
        kw = cont_tpl.get("keywords", cont_tpl["short_descr"])
        act("The $d is closed.", player, None, kw, TO_CHAR)
        return
    contents = container.get("contents", [])
    if not contents:
        chprintln(player, "It is empty.")
        return
    # cf. 1stMud get_obj_list can_see_obj gate: dark/invis contents are hidden
    visible = [c for c in contents if can_see_obj(player, c)]
    if not visible:
        chprintln(player, "It is empty.")
        return
    names = []
    for cobj in visible:
        ctpl = ITEM_DEFS[obj_vnum(cobj)]
        names.append(cobj.get("short_descr") or ctpl["short_descr"])
    if len(visible) > 1:
        names.append("All")
    cidx = pick_from("Take what?", names)
    if cidx < 0:
        return
    if cidx == len(visible):
        for cobj in list(visible):
            ctpl = ITEM_DEFS[obj_vnum(cobj)]
            if not _check_carry_get(player, cobj, ctpl):
                continue
            container["contents"].remove(cobj)
            chprintln(player, "You get {}.".format(cobj.get("short_descr") or ctpl["short_descr"]))
            if not apply_money_pickup(player, cobj, ctpl):
                player["inv"].append(cobj)
                quest_obj_check(player, cobj)  # cf. 1stMud get_obj quest hook
        return
    cobj = visible[cidx]
    ctpl = ITEM_DEFS[obj_vnum(cobj)]
    if not _check_carry_get(player, cobj, ctpl):
        return
    container["contents"].remove(cobj)
    chprintln(player, "You get {}.".format(cobj.get("short_descr") or ctpl["short_descr"]))
    if not apply_money_pickup(player, cobj, ctpl):
        player["inv"].append(cobj)
        quest_obj_check(player, cobj)  # cf. 1stMud get_obj quest hook


def _obj_number(obj):
    """Return obj's contribution (plus contents) to the carry-item count
    (cf. 1stMud get_obj_number in handler.c).

    Containers, corpses, money, gems, and jewelry contribute 0 themselves;
    everything else contributes 1.  [PRIMESUD] gem/jewelry types added to
    the zero-count set alongside PrimeSUD's corpse split of ITEM_CONTAINER.
    """
    tpl = ITEM_DEFS[obj_vnum(obj)]
    n = 0 if tpl.get("type") in _CONTAINER_TYPES + ("money", "gem", "jewelry") else 1
    if isinstance(obj, dict):
        for c in obj.get("contents", []):
            n += _obj_number(c)
    return n


def _check_carry_get(player, obj, tpl, from_carried=False):
    """Block pickup if it would exceed carry count/weight limits
    (cf. 1stMud get_obj carry_n/carry_w checks in act_obj.c).

    Args:
        player (dict): Player state dict.
        obj: Item instance dict (or plain vnum) about to be picked up.
        tpl (dict): obj's item template.
        from_carried (bool): True if obj comes from a container the player
            already carries -- skips the weight check, since obj's weight
            already counts (cf. 1stMud act_obj.c get_obj:
            `!obj->in_obj || obj->in_obj->carried_by != ch`).

    Returns:
        bool: True if obj may be picked up.
    """
    kw = tpl.get("keywords", tpl["short_descr"])
    carried = player["inv"] + [e for e in player["equip"].values() if e is not None]
    carry_n = sum(_obj_number(o) for o in carried)
    if carry_n + _obj_number(obj) > can_carry_n(player):
        act("$d: you can't carry that many items.", player, None, kw, TO_CHAR)
        return False
    if (not from_carried
            and get_carry_weight(player) + get_obj_weight(obj) > can_carry_w(player)):
        act("$d: you can't carry that much weight.", player, None, kw, TO_CHAR)
        return False
    return True


def do_get(player, args):
    """Pick up items from the room or loot containers (cf. 1stMud `do_get` in act_obj.c).

    Closed containers block looting (CONT_CLOSED, act_obj.c:280) via both
    the no-arg [loot] picker (_loot_container_picker) and the explicit
    "get <item> <container>" form below.
    """
    rs = world.rooms[player["room"]]
    if not args:
        # cf. 1stMud get_obj_list can_see_obj gate: unseen (dark/invis/
        # vis_death) room items drop out of the picker
        loose = [obj for obj in reversed(rs["items"])
                 if ITEM_DEFS[obj_vnum(obj)].get("type") not in _CONTAINER_TYPES
                 and "take" in item_wear_flags(obj, ITEM_DEFS[obj_vnum(obj)])
                 and can_see_obj(player, obj)]
        conts = [obj for obj in rs["items"]
                 if ITEM_DEFS[obj_vnum(obj)].get("type") in _CONTAINER_TYPES
                 and can_see_obj(player, obj)]
        if not loose and not conts:
            chprintln(player, "There is nothing here to pick up.")
            return
        names = []
        for obj in loose:
            tpl = ITEM_DEFS[obj_vnum(obj)]
            names.append((isinstance(obj, dict) and obj.get("short_descr")) or tpl["short_descr"])
        has_all = len(loose) > 1
        if has_all:
            names.append("All")
        cont_start = len(names)
        for obj in conts:
            tpl = ITEM_DEFS[obj_vnum(obj)]
            names.append(
                ((isinstance(obj, dict) and obj.get("short_descr")) or tpl["short_descr"])
                + " {W[loot]{x")
        idx = pick_from("Pick up what?", names)
        if idx < 0:
            return
        if idx < len(loose):
            obj = loose[idx]
            tpl = ITEM_DEFS[obj_vnum(obj)]
            if not _check_carry_get(player, obj, tpl):
                return
            rs["items"].remove(obj)
            chprintln(player, "You get {}.".format(
                (isinstance(obj, dict) and obj.get("short_descr")) or tpl["short_descr"]))
            if apply_money_pickup(player, obj, tpl):
                return
            player["inv"].append(obj)
            quest_obj_check(player, obj)  # cf. 1stMud get_obj quest hook
            return "get " + tpl.get("keywords", tpl["short_descr"]).split()[0]
        if has_all and idx == len(loose):
            for obj in list(loose):
                tpl = ITEM_DEFS[obj_vnum(obj)]
                if not _check_carry_get(player, obj, tpl):
                    continue
                rs["items"].remove(obj)
                chprintln(player, "You get {}.".format(
                    (isinstance(obj, dict) and obj.get("short_descr")) or tpl["short_descr"]))
                if not apply_money_pickup(player, obj, tpl):
                    player["inv"].append(obj)
                    quest_obj_check(player, obj)  # cf. 1stMud get_obj quest hook
            return
        _loot_container_picker(player, conts[idx - cont_start])
        return
    arg = " ".join(args)
    if arg == "all" or arg.startswith("all."):
        filter_kw = arg[4:] if arg.startswith("all.") else None
        found = False
        for obj in list(rs["items"]):
            tpl = ITEM_DEFS[obj_vnum(obj)]
            if tpl.get("type") in _CONTAINER_TYPES:  # [PRIMESUD] skip containers; use "get all <container>"
                continue
            if filter_kw and not is_name(filter_kw, tpl.get("keywords", "")):
                continue
            if not can_see_obj(player, obj):  # cf. 1stMud do_get all loop, act_obj.c:230
                continue
            found = True
            if "take" not in item_wear_flags(obj, tpl):
                chprintln(player, "You can't take that.")
                continue
            if not _check_carry_get(player, obj, tpl):
                continue
            rs["items"].remove(obj)
            chprintln(player, "You get {}.".format(tpl["short_descr"]))
            if not apply_money_pickup(player, obj, tpl):
                player["inv"].append(obj)
                quest_obj_check(player, obj)  # cf. 1stMud get_obj quest hook
        if not found:
            if filter_kw:
                chprintln(player, "I see no {} here.".format(filter_kw))
            else:
                chprintln(player, "I see nothing here.")
        return
    if len(args) >= 2:
        cont_arg = " ".join(args[1:])
        cont_obj = get_obj_list(cont_arg, rs["items"], ITEM_DEFS, player)
        if cont_obj is None:
            cont_obj = get_obj_list(cont_arg, player["inv"], ITEM_DEFS, player)
        if (cont_obj is not None and isinstance(cont_obj, dict)
                and ITEM_DEFS[obj_vnum(cont_obj)].get("type") in _CONTAINER_TYPES):
            item_arg = args[0]
            cont_tpl = ITEM_DEFS[obj_vnum(cont_obj)]
            # cf. 1stMud do_get CONT_CLOSED check, act_obj.c:280
            if item_container_flags(cont_obj, cont_tpl).get("closed"):
                kw = cont_tpl.get("keywords", cont_tpl["short_descr"])
                act("The $d is closed.", player, None, kw, TO_CHAR)
                return
            contents = cont_obj.get("contents", [])
            cont_carried = cont_obj in player["inv"]
            if item_arg == "all":
                if not contents:
                    chprintln(player, "It is empty.")
                else:
                    for cobj in list(contents):
                        ctpl = ITEM_DEFS[obj_vnum(cobj)]
                        if not can_see_obj(player, cobj):  # cf. 1stMud do_get all-from-container loop, act_obj.c:311
                            continue
                        if not _check_carry_get(player, cobj, ctpl, cont_carried):
                            continue
                        cont_obj["contents"].remove(cobj)
                        chprintln(player, "You get {}.".format(cobj.get("short_descr") or ctpl["short_descr"]))
                        if not apply_money_pickup(player, cobj, ctpl):
                            player["inv"].append(cobj)
                            quest_obj_check(player, cobj)  # cf. 1stMud get_obj quest hook
                return
            cobj = get_obj_list(item_arg, contents, ITEM_DEFS, player)
            if cobj is None:
                chprintln(player, "I see nothing like that in the {}.".format(
                    cont_obj.get("short_descr") or cont_tpl["short_descr"]))
                return
            ctpl = ITEM_DEFS[obj_vnum(cobj)]
            if not _check_carry_get(player, cobj, ctpl, cont_carried):
                return
            cont_obj["contents"].remove(cobj)
            chprintln(player, "You get {}.".format(cobj.get("short_descr") or ctpl["short_descr"]))
            if not apply_money_pickup(player, cobj, ctpl):
                player["inv"].append(cobj)
                quest_obj_check(player, cobj)  # cf. 1stMud get_obj quest hook
            return
    obj = get_obj_list(arg, rs["items"], ITEM_DEFS, player)
    if obj is None:
        chprintln(player, "I see no {} here.".format(arg))
        return
    tpl = ITEM_DEFS[obj_vnum(obj)]
    if "take" not in item_wear_flags(obj, tpl):
        chprintln(player, "You can't take that.")
        return
    if not _check_carry_get(player, obj, tpl):
        return
    rs["items"].remove(obj)
    chprintln(player, "You get {}.".format((isinstance(obj, dict) and obj.get("short_descr")) or tpl["short_descr"]))
    if not apply_money_pickup(player, obj, tpl):
        player["inv"].append(obj)
        quest_obj_check(player, obj)  # cf. 1stMud get_obj quest hook


def _drop_coins(player, amount, coin):
    """Coin branch of do_drop (cf. 1stMud do_drop money path in act_obj.c:483).

    Merges the dropped coins with any existing money pile in the room,
    matching 1stMud's per-vnum coin-pile scan before recreating a single
    combined money object.

    Args:
        player (dict): Player state dict.
        amount (int): Coin count to drop.
        coin (str): "coins"/"coin"/"gold"/"silver" -- coin denomination word.
    """
    if amount <= 0 or coin not in ("coins", "coin", "gold", "silver"):
        chprintln(player, "Sorry, you can't do that.")
        return
    silver = coin != "gold"
    wallet = "silver" if silver else "gold"
    if player[wallet] < amount:
        chprintln(player, "You don't have that much %s." % wallet)
        return
    player[wallet] -= amount
    gold = 0 if silver else amount
    silver_amt = amount if silver else 0

    rs = world.rooms[player["room"]]
    for obj in list(rs["items"]):
        if not isinstance(obj, dict) or ITEM_DEFS[obj_vnum(obj)].get("type") != "money":
            continue
        rs["items"].remove(obj)
        silver_amt += obj.get("silver", 0)
        gold += obj.get("gold", 0)

    coin_obj = create_money(gold, silver_amt)
    if coin_obj is not None:
        rs["items"].append(coin_obj)
    act("$n drops some coins.", player, None, None, TO_ROOM)
    chprintln(player, "OK.")


def do_drop(player, args):
    """Drop items from inventory onto the ground (cf. 1stMud `do_drop` in act_obj.c).

    Args:
        player (dict): Player state dict.
        args (list): Parsed command arguments; ["<n>", "gold"/"silver"/"coin"/"coins", ...]
            drops coins (cf. 1stMud do_drop act_obj.c:483), otherwise an item keyword or "all".
    """
    if args and args[0].isdigit():
        _drop_coins(player, int(args[0]), args[1].lower() if len(args) > 1 else "")
        return
    if not args:
        if not player["inv"]:
            chprintln(player, "You are not carrying anything.")
            return
        # cf. 1stMud get_obj_carry can_see_obj gate: can't drop what you can't see
        visible = [obj for obj in player["inv"] if can_see_obj(player, obj)]
        if not visible:
            chprintln(player, "You are not carrying anything.")
            return
        names = [ITEM_DEFS[obj["vnum"]]["short_descr"] for obj in visible]
        idx = pick_from("Drop what?", names)
        if idx < 0:
            return
        obj = visible[idx]
        if not can_drop_obj(player, obj):
            chprintln(player, "You can't let go of it.")
            return
        tpl = ITEM_DEFS[obj["vnum"]]
        player["inv"].remove(obj)
        world.rooms[player["room"]]["items"].append(obj)
        chprintln(player, "You drop {}.".format(tpl["short_descr"]))
        if item_extra_flags(obj, tpl).get("melt_drop"):
            world.rooms[player["room"]]["items"].remove(obj)
            chprintln(player, "{} dissolves into smoke.".format(tpl["short_descr"]))
            return
        return "drop " + tpl.get("keywords", tpl["short_descr"]).split()[0]
    arg = " ".join(args)
    if arg == "all" or arg.startswith("all."):
        filter_kw = arg[4:] if arg.startswith("all.") else None
        found = False
        for obj in list(player["inv"]):
            tpl = ITEM_DEFS[obj["vnum"]]
            if filter_kw and not is_name(filter_kw, tpl.get("keywords", "")):
                continue
            if not can_see_obj(player, obj):  # cf. 1stMud do_drop all loop, act_obj.c:602
                continue
            if not can_drop_obj(player, obj):
                continue
            found = True
            player["inv"].remove(obj)
            world.rooms[player["room"]]["items"].append(obj)
            chprintln(player, "You drop {}.".format(tpl["short_descr"]))
            if item_extra_flags(obj, tpl).get("melt_drop"):
                world.rooms[player["room"]]["items"].remove(obj)
                chprintln(player, "{} dissolves into smoke.".format(tpl["short_descr"]))
        if not found:
            if filter_kw:
                chprintln(player, "You are not carrying any {}.".format(filter_kw))
            else:
                chprintln(player, "You are not carrying anything.")
        return
    obj = get_obj_list(arg, player["inv"], ITEM_DEFS, player)
    if obj is None:
        chprintln(player, "You do not have that item.")
        return
    if not can_drop_obj(player, obj):
        chprintln(player, "You can't let go of it.")
        return
    tpl = ITEM_DEFS[obj["vnum"]]
    player["inv"].remove(obj)
    world.rooms[player["room"]]["items"].append(obj)
    chprintln(player, "You drop {}.".format(tpl["short_descr"]))
    if item_extra_flags(obj, tpl).get("melt_drop"):
        world.rooms[player["room"]]["items"].remove(obj)
        chprintln(player, "{} dissolves into smoke.".format(tpl["short_descr"]))


def do_put(player, args):
    """Put an item from inventory into a container (cf. 1stMud do_put in act_obj.c).

    Args:
        player (dict): Player state dict.
        args (list): Parsed command arguments; first is item, rest is container (skips "in"/"on").
    """
    if len(args) < 2:
        chprintln(player, "Put what in what?")
        return
    item_arg = args[0]
    rest = args[1:]
    if rest and rest[0] in ("in", "on"):
        rest = rest[1:]
    if not rest:
        chprintln(player, "Put what in what?")
        return
    cont_arg = " ".join(rest)
    rs = world.rooms[player["room"]]
    cont_obj = get_obj_list(cont_arg, rs["items"], ITEM_DEFS, player)
    if cont_obj is None:
        cont_obj = get_obj_list(cont_arg, player["inv"], ITEM_DEFS, player)
    if cont_obj is None:
        chprintln(player, "I see no {} here.".format(cont_arg))
        return
    cont_tpl = ITEM_DEFS[obj_vnum(cont_obj)]
    if _item_type(cont_obj, cont_tpl) != "container":
        chprintln(player, "That's not a container.")
        return
    # cf. 1stMud do_put CONT_CLOSED check, act_obj.c:370
    if item_container_flags(cont_obj, cont_tpl).get("closed"):
        kw = cont_tpl.get("keywords", cont_tpl["short_descr"])
        act("The $d is closed.", player, None, kw, TO_CHAR)
        return
    obj = get_obj_list(item_arg, player["inv"], ITEM_DEFS, player)
    if obj is None:
        chprintln(player, "You do not have that item.")
        return
    if obj is cont_obj:
        chprintln(player, "You can't fold it into itself.")
        return
    # cf. 1stMud do_put act_obj.c:391 -- nodrop items can't be stashed either
    if not can_drop_obj(player, obj):
        chprintln(player, "You can't let go of it.")
        return
    tpl = ITEM_DEFS[obj_vnum(obj)]
    # cf. 1stMud do_put act_obj.c:397 -- quest items only fit quest containers
    if (item_extra_flags(obj, tpl).get("quest")
            and not item_extra_flags(cont_obj, cont_tpl).get("quest")):
        chprintln(player, "You can't put a quest item in something.")
        return
    # cf. 1stMud do_put act_obj.c:403 -- nested weight-reducing containers barred
    if tpl.get("container_weight_mult", 100) != 100:
        chprintln(player, "You have a feeling that would be a bad idea.")
        return
    # cf. 1stMud do_put act_obj.c:409 -- container capacity checks; [PRIMESUD]
    # containers without converted container_max_weight/container_max_item_weight
    # (e.g. limbo's floating disc) carry no capacity limit
    max_weight = cont_tpl.get("container_max_weight")
    max_item_weight = cont_tpl.get("container_max_item_weight")
    if max_weight is not None and max_item_weight is not None:
        if (get_obj_weight(obj) + get_obj_weight(cont_obj) > max_weight * 10
                or get_obj_weight(obj) > max_item_weight * 10):
            chprintln(player, "It won't fit.")
            return
    player["inv"].remove(obj)
    cont_obj.setdefault("contents", []).append(obj)
    cont_name = (isinstance(cont_obj, dict) and cont_obj.get("short_descr")) or cont_tpl["short_descr"]
    chprintln(player, "You put {} in {}.".format(tpl["short_descr"], cont_name))


def _give_coins(player, amount, coin, rest):
    """Coin branch of do_give (cf. 1stMud do_give money path in act_obj.c:655).

    Fires TRIG_BRIBE on the recipient (see below). [PRIMESUD] The changer's
    change comes straight from thin air like 1stMud's till top-up.
    """
    if amount <= 0 or coin not in ("coins", "coin", "gold", "silver"):
        chprintln(player, "Sorry, you can't do that.")
        return
    silver = coin != "gold"
    if not rest:
        chprintln(player, "Give what to whom?")
        return
    rs = world.rooms[player["room"]]
    vid = get_char_room(" ".join(rest), rs["mobs"], world.chars, player)
    if vid is None:
        chprintln(player, "They aren't here.")
        return
    victim = world.chars[vid]
    wallet = "silver" if silver else "gold"
    if player[wallet] < amount:
        chprintln(player, "You haven't got that much.")
        return
    player[wallet] -= amount
    victim[wallet] = victim.get(wallet, 0) + amount
    act("$n gives you %d %s." % (amount, wallet), player, None, victim, TO_VICT)
    act("$n gives $N some coins.", player, None, victim, TO_NOTVICT)
    act("You give $N %d %s." % (amount, wallet), player, None, victim, TO_CHAR)

    # TRIG_BRIBE: amount normalised to silver (cf. p_bribe_trigger, act_obj.c:710)
    if victim.get("is_npc"):
        from mobprog import has_trigger, bribe_trigger  # deferred: keep mobprog off the boot path
        if has_trigger(victim, "bribe"):
            bribe_trigger(victim, player, amount if silver else amount * 100)

    # Money changer (cf. 1stMud ACT_IS_CHANGER branch)
    if victim.get("act_flags", {}).get("changer"):
        change = (95 * amount // 100 // 100) if silver else (95 * amount)
        if change < 1 and can_see(victim, player):
            act("$n tells you 'I'm sorry, you did not give me enough to change.'",
                victim, None, player, TO_VICT)
            # 1stMud: changer gives the original amount back via do_give
            victim[wallet] -= amount
            player[wallet] += amount
            act("$n gives you %d %s." % (amount, wallet), victim, None, player, TO_VICT)
        elif can_see(victim, player):
            out = "gold" if silver else "silver"
            player[out] += change
            act("$n gives you %d %s." % (change, out), victim, None, player, TO_VICT)
            if silver:
                rem = 95 * amount // 100 - change * 100
                if rem > 0:
                    player["silver"] += rem
                    act("$n gives you %d silver." % rem, victim, None, player, TO_VICT)
            act("$n tells you 'Thank you, come again.'", victim, None, player, TO_VICT)


def do_give(player, args):
    """Give coins or an item to a mob in the room (cf. 1stMud do_give in act_obj.c).

    Args:
        player (dict): Player state dict.
        args (list): [amount, coin-word, mob] for coins, or [item, mob].
    """
    if len(args) < 2:
        chprintln(player, "Give what to whom?")
        return
    arg1 = args[0]

    if arg1.isdigit():
        _give_coins(player, int(arg1), args[1].lower(), args[2:])
        return

    obj = get_obj_list(arg1, player["inv"], ITEM_DEFS, player)
    if obj is None:
        chprintln(player, "You do not have that item.")
        return
    # 1stMud: wear_loc check -- [PRIMESUD] inv never holds equipped items

    rs = world.rooms[player["room"]]
    vid = get_char_room(" ".join(args[1:]), rs["mobs"], world.chars, player)
    if vid is None:
        chprintln(player, "They aren't here.")
        return
    victim = world.chars[vid]
    tpl = ITEM_DEFS[obj_vnum(obj)]

    # Quest delivery (cf. 1stMud do_give act_obj.c:772)
    if (is_quester(player)
            and player.get("quest_status", 0) == QUEST_DELIVER
            and obj_vnum(obj) == player.get("quest_obj", 0)):
        if victim.get("tpl") == player.get("quest_mob", 0):  # [PRIMESUD] vnum match
            act("$n gives $p to $N.", player, obj, victim, TO_NOTVICT)
            act("$n gives you $p.", player, obj, victim, TO_VICT)
            act("You give $p to $N.", player, obj, victim, TO_CHAR)
            # [PRIMESUD] "{5+R" (blink) rendered as {R
            chprintln(player, "{RYou have almost completed your QUEST!{x")
            chprintlnf(player, "{RReturn to %s before your time runs out!{x",
                       _giver_name(player))
            player["quest_status"] = QUEST_RETURN_DELIVER
            player["inv"].remove(obj)  # cf. 1stMud extract_obj
            player["quest_obj"] = 0
            player["quest_mob"] = 0
            # 1stMud: interpret(victim, "thank <name>") -- [PRIMESUD] socials
            # not ported; equivalent act
            act("$N thanks you heartily.", player, None, victim, TO_CHAR)
        else:
            # [PRIMESUD] "who your ... deliver $p too" grammar fixed
            act("That isn't who you're supposed to deliver $p to.",
                player, obj, None, TO_CHAR)
        return

    if MOB_DEFS[victim["tpl"]].get("shop"):
        act("$N tells you 'Sorry, you'll have to sell that.'",
            player, None, victim, TO_CHAR)
        return

    if not can_drop_obj(player, obj):
        chprintln(player, "You can't let go of it.")
        return

    if (item_extra_flags(obj, tpl).get("quest")
            and player["level"] <= MAX_MORTAL_LEVEL):
        chprintln(player, "You can't give quest items.")
        return

    carry_n = len(victim["inv"]) + sum(1 for e in victim["equip"].values()
                                       if e is not None)
    if carry_n + 1 > can_carry_n(victim):
        act("$N has $S hands full.", player, None, victim, TO_CHAR)
        return

    # cf. 1stMud act_obj.c do_give: get_carry_weight includes coin weight
    if get_carry_weight(victim) + get_obj_weight(obj) > can_carry_w(victim):
        act("$N can't carry that much weight.", player, None, victim, TO_CHAR)
        return

    if not can_see_obj(victim, obj):
        act("$N can't see it.", player, None, victim, TO_CHAR)
        return

    player["inv"].remove(obj)
    victim["inv"].append(obj)
    # cf. do_give (act_obj.c:845): MOBtrigger off around the give announcement
    # so the "gives you" text can't fire the recipient's act trigger -- the
    # give trigger below is the intended reaction.  (1stMud does not latch the
    # coin/quest give paths, so those stay unlatched too.)
    import mobprog  # deferred: keep mobprog off the boot path
    saved = mobprog.MOBtrigger
    mobprog.MOBtrigger = False
    try:
        act("$n gives $p to $N.", player, obj, victim, TO_NOTVICT)
        act("$n gives you $p.", player, obj, victim, TO_VICT)
        act("You give $p to $N.", player, obj, victim, TO_CHAR)
    finally:
        mobprog.MOBtrigger = saved
    # TRIG_GIVE: mob reacts to the received object (cf. do_give, act_obj.c:856)
    if victim.get("is_npc"):
        from mobprog import has_trigger, give_trigger  # deferred: keep mobprog off the boot path
        if has_trigger(victim, "give"):
            give_trigger(victim, player, obj)


def _obj_flags(tpl):
    """Build coloured flag prefix string for item display (cf. 1stMud format_obj_to_char in act_info.c)."""
    ef = tpl.get("extra_flags", {})
    parts = []
    if ef.get("glow"):   parts.append("{Y(Glowing){x ")
    if ef.get("hum"):    parts.append("{C(Humming){x ")
    if ef.get("magic"):  parts.append("{M(Magical){x ")
    if ef.get("invis"):  parts.append("{c(Invis){x ")
    if ef.get("evil"):   parts.append("{R(Red Aura){x ")
    if ef.get("bless"):  parts.append("{B(Blue Aura){x ")
    return "".join(parts)


def do_inventory(player, args):
    """Display carried inventory with item counts (cf. 1stMud `do_inventory` in act_info.c)."""
    max_carry = can_carry_n(player)
    chprintln(player, "{YYou are carrying {W%d/%d{Y items:{x" % (len(player["inv"]), max_carry))
    if not player["inv"]:
        return
    counts = {}
    for obj in player["inv"]:
        v = obj["vnum"]
        counts[v] = counts.get(v, 0) + 1
    show_vnums = "vnum" in DBG
    for v, n in counts.items():
        tpl = ITEM_DEFS[v]
        flags = _obj_flags(tpl)
        name = tpl["short_descr"]
        # cf. 1stMud act_info.c:66 quest obj marker; [PRIMESUD] vnum match
        if is_quester(player) and v == player.get("quest_obj", 0):
            name = "{r[{RTARGET{r] {x" + name
        if show_vnums:  # [PRIMESUD]
            name += " {D[" + str(v) + "]{x"
        chprintln(player, "  {}{} x{}".format(flags, name, n) if n > 1 else "  {}{}".format(flags, name))


_WEAR_MSG = {
    "light":    "You light {} and hold it.",
    "finger_l": "You wear {} on your left finger.",
    "finger_r": "You wear {} on your right finger.",
    "neck_1":   "You wear {} around your neck.",
    "neck_2":   "You wear {} around your neck.",
    "body":     "You wear {} on your torso.",
    "head":     "You wear {} on your head.",
    "legs":     "You wear {} on your legs.",
    "feet":     "You wear {} on your feet.",
    "hands":    "You wear {} on your hands.",
    "arms":     "You wear {} on your arms.",
    "shield":   "You wear {} as a shield.",
    "about":    "You wear {} about your torso.",
    "waist":    "You wear {} about your waist.",
    "wrist_l":  "You wear {} around your left wrist.",
    "wrist_r":  "You wear {} around your right wrist.",
    "wield":    "You wield {}.",
    "hold":     "You hold {} in your hand.",
    "float":    "You release {} and it floats next to you.",
}

_DUAL_SLOTS = {
    "finger": ("finger_l", "finger_r"),
    "neck":   ("neck_1",   "neck_2"),
    "wrist":  ("wrist_l",  "wrist_r"),
}

_WIELD_SKILL_MSG = (
    (100, "{} feels like a part of you!"),
    ( 85, "You feel quite confident with {}."),
    ( 70, "You are skilled with {}."),
    ( 50, "Your skill with {} is adequate."),
    ( 25, "{} feels a little clumsy in your hands."),
    (  1, "You fumble and almost drop {}."),
    (  0, "You don't even know which end is up on {}."),
)


def remove_obj(player, slot, fReplace):
    """Unequip slot if occupied, honouring curse and fReplace flag (cf. 1stMud remove_obj in act_obj.c).

    Args:
        player (dict): Player state dict.
        slot (str): Equipment slot key.
        fReplace (bool): If False, refuse silently when slot is occupied.

    Returns:
        bool: True if slot is free (or was successfully freed), False otherwise.
    """
    obj = player["equip"].get(slot)
    if obj is None:
        return True
    if not fReplace:
        return False
    tpl = ITEM_DEFS[obj["vnum"]]
    if item_extra_flags(obj, tpl).get("noremove"):
        chprintln(player, "You can't remove {}.".format(tpl["short_descr"]))
        return False
    unequip_char(player, slot)
    act("$n stops using $p.", player, obj, None, TO_ROOM)
    act("You stop using $p.", player, obj, None, TO_CHAR)
    return True


def _zap_anti_align(player, obj, tpl):
    """Zap and drop obj if anti-aligned against player's alignment
    (cf. 1stMud equip_char anti-align check in handler.c). [PRIMESUD] ported
    here rather than in equip_char since PrimeSUD's equip_char (handler.py)
    has no alignment awareness; see combat.py's post-kill zap for the same
    flag names.

    Args:
        player (dict): Player state dict.
        obj (dict): Item instance about to be equipped.
        tpl (dict): obj's item template.

    Returns:
        bool: True if obj was zapped (dropped to the room, not equipped).
    """
    ef = item_extra_flags(obj, tpl)
    if not ((ef.get("anti_evil") and is_evil(player))
            or (ef.get("anti_good") and is_good(player))
            or (ef.get("anti_neutral") and is_neutral(player))):
        return False
    act("You are zapped by $p and drop it.", player, obj, None, TO_CHAR)
    act("$n is zapped by $p and drops it.", player, obj, None, TO_ROOM)
    player["inv"].remove(obj)
    world.rooms[player["room"]]["items"].append(obj)
    return True


def wear_obj(player, obj, fReplace):
    """Equip obj, selecting slot from wear flags (cf. 1stMud wear_obj in act_obj.c).

    Args:
        player (dict): Player state dict.
        obj (dict): Item instance from inventory.
        fReplace (bool): Auto-remove current occupant if True; skip silently if False.
    """
    tpl = ITEM_DEFS[obj["vnum"]]
    if player["level"] < tpl.get("level", 1):
        chprintln(player, "You must be level {} to use this object.".format(tpl.get("level", 1)))
        return

    if tpl.get("type") == "light":
        if not remove_obj(player, "light", fReplace):
            return
        chprintln(player, _WEAR_MSG["light"].format(tpl["short_descr"]))
        if _zap_anti_align(player, obj, tpl):
            return
        equip_char(player, obj, "light")
        return

    try:
        flag = next(f for f in item_wear_flags(obj, tpl) if f != "take")
    except StopIteration:
        flag = None
    if flag is None:
        if fReplace:
            chprintln(player, "You can't wear, wield, or hold that.")
        return

    if flag in _DUAL_SLOTS:
        slot_a, slot_b = _DUAL_SLOTS[flag]
        if (player["equip"].get(slot_a) is not None
                and player["equip"].get(slot_b) is not None):
            if not remove_obj(player, slot_a, fReplace) \
                    and not remove_obj(player, slot_b, fReplace):
                return
        if player["equip"].get(slot_a) is None:
            slot = slot_a
        elif player["equip"].get(slot_b) is None:
            slot = slot_b
        else:
            return
    else:
        slot = flag
        if slot not in player["equip"]:
            if fReplace:
                chprintln(player, "You can't wear, wield, or hold that.")
            return
        if not remove_obj(player, slot, fReplace):
            return

    if slot == "wield":
        wield_limit = STR_APP_WIELD[get_curr_stat(player, "str")]
        if tpl.get("weight", 0) > wield_limit * 10:
            chprintln(player, "It is too heavy for you to wield.")
            return
        # cf. 1stMud wear_obj wield-vs-shield two-hand check, act_obj.c:1631-1637
        if (_get_size(player) < SIZE_RANK["large"]
                and item_weapon_flags(obj, tpl).get("two_hands")
                and player["equip"].get("shield") is not None):
            chprintln(player, "You need two hands free for that weapon.")
            return
    elif slot == "shield":
        # cf. 1stMud wear_obj shield-vs-dual-wield check, act_obj.c:1593-1597
        if player["equip"].get("secondary") is not None:
            chprintln(player, "You cannot use a shield while using 2 weapons.")
            return
        # cf. 1stMud wear_obj shield-vs-two-hand-weapon check, act_obj.c:1602-1608
        wobj = player["equip"].get("wield")
        if wobj is not None:
            wtpl = ITEM_DEFS[wobj["vnum"]]
            if (_get_size(player) < SIZE_RANK["large"]
                    and item_weapon_flags(wobj, wtpl).get("two_hands")):
                chprintln(player, "Your hands are tied up with your weapon!")
                return

    chprintln(player, _WEAR_MSG[slot].format(tpl["short_descr"]))
    if _zap_anti_align(player, obj, tpl):
        return
    equip_char(player, obj, slot)

    if slot == "wield":
        sn = WEAPON_GSN_MAP.get(tpl.get("weapon_type", ""), -1)
        skill = _get_weapon_skill(player, sn)
        msg = _WIELD_SKILL_MSG[-1][1]
        for threshold, m in _WIELD_SKILL_MSG[:-1]:
            if skill > threshold:
                msg = m
                break
        chprintln(player, msg.format(tpl["short_descr"]))


def do_wear(player, args):
    """Equip an item from inventory, or wear all wearable items (cf. 1stMud do_wear in act_obj.c).

    Args:
        player (dict): Player state dict.
        args (list): Parsed command arguments; first token may be "all".
    """
    if not args:
        equippable = []
        for obj in player["inv"]:
            if not can_see_obj(player, obj):  # cf. 1stMud get_obj_carry can_see_obj gate
                continue
            tpl = ITEM_DEFS[obj["vnum"]]
            if tpl.get("type") == "light":
                slot = "light"
            else:
                try:
                    slot = next(f for f in item_wear_flags(obj, tpl)
                                if f != "take")
                except StopIteration:
                    slot = None
            if slot is not None and (slot in player["equip"] or slot in _DUAL_SLOTS):
                equippable.append((obj, tpl, slot))
        if not equippable:
            chprintln(player, "You have nothing wearable.")
            return
        names = [tpl["short_descr"] for _, tpl, _ in equippable]
        if len(equippable) > 1:
            names.append("All")
        idx = pick_from("Wear what?", names)
        if idx < 0:
            return
        if idx == len(equippable):
            for obj, _, _ in list(equippable):
                wear_obj(player, obj, False)
            return
        obj, tpl, slot = equippable[idx]
        wear_obj(player, obj, True)
        return "wear " + tpl.get("keywords", tpl["short_descr"]).split()[0]
    if args[0] == "all":
        for obj in list(player["inv"]):
            if not can_see_obj(player, obj):  # cf. 1stMud do_wear all loop, act_obj.c:1724
                continue
            wear_obj(player, obj, False)
        return
    obj = get_obj_list(" ".join(args), player["inv"], ITEM_DEFS, player)
    if obj is None:
        chprintln(player, "You do not have that item.")
        return
    wear_obj(player, obj, True)


def do_remove(player, args):
    """Remove a worn item by name and return it to inventory (cf. 1stMud do_remove in act_obj.c).

    Args:
        player (dict): Player state dict.
        args (list): Parsed command arguments; first token may be "all".
    """
    if not args:
        # cf. 1stMud get_obj_wear can_see_obj gate: can't remove what you can't see
        worn = [(slot, obj) for slot, obj in player["equip"].items()
                if obj is not None and can_see_obj(player, obj)]
        if not worn:
            chprintln(player, "You aren't wearing anything.")
            return
        names = [ITEM_DEFS[obj["vnum"]]["short_descr"] for _, obj in worn]
        if len(worn) > 1:
            names.append("All")
        idx = pick_from("Remove what?", names)
        if idx < 0:
            return
        if idx == len(worn):
            for slot, obj in list(worn):
                remove_obj(player, slot, True)
            return
        slot, obj = worn[idx]
        remove_obj(player, slot, True)
        return "remove " + ITEM_DEFS[obj["vnum"]].get("keywords", ITEM_DEFS[obj["vnum"]]["short_descr"]).split()[0]
    if args[0] == "all":
        for slot, obj in list(player["equip"].items()):
            if obj is not None and can_see_obj(player, obj):  # cf. 1stMud do_remove all loop, act_obj.c:1763
                remove_obj(player, slot, True)
        return
    target = " ".join(args)
    # cf. 1stMud get_obj_wear (handler.c:2052) -- worn lookup gates on can_see_obj
    for slot, obj in player["equip"].items():
        if (obj is not None and can_see_obj(player, obj)
                and is_name(target, ITEM_DEFS[obj["vnum"]].get("keywords", ""))):
            remove_obj(player, slot, True)
            return
    chprintln(player, "You do not have that item.")


def do_equipment(player, args):
    """List all equipment slots and what is worn in each (cf. 1stMud do_equipment in act_info.c).

    Args:
        player (dict): Player state dict.
        args (list): Parsed command arguments (unused).
    """
    chprintln(player, "You are wearing:")
    show_vnums = "vnum" in DBG
    for slot, label in WEAR_LABELS:
        obj = player["equip"].get(slot)
        if obj is not None:
            tpl = ITEM_DEFS[obj["vnum"]]
            line = label + _obj_flags(tpl) + "{Y" + tpl["short_descr"] + "{x"
            if show_vnums:  # [PRIMESUD]
                line += " {D[" + str(obj["vnum"]) + "]{x"
            chprintln(player, line)
        else:
            chprintln(player, label + "nothing")


def do_steal(player, args):
    """Steal coins or an item from a mob via the steal skill (cf. 1stMud do_steal in act_obj.c).

    [PRIMESUD] arena, PvP level-gap, clan-membership, outlaw-flag, and
    wiznet branches not ported -- victims are always NPCs; yell rendered
    as a plain line (channels not ported).

    Args:
        player (dict): Player state dict.
        args (list): [what, whom] -- "coins"/"gold"/"silver" or item keyword.
    """
    if len(args) < 2:
        chprintln(player, "Steal what from whom?")
        return

    rs = world.rooms[player["room"]]
    victim_id = get_char_room(" ".join(args[1:]), rs["mobs"], world.chars, player)
    if victim_id is None:
        chprintln(player, "They aren't here.")
        return
    victim = world.chars[victim_id]

    if is_safe(player, victim):
        return

    if victim.get("fighting") is not None:
        chprintln(player, "Kill stealing is not permitted.")
        chprintln(player, "You'd better not -- you might get hit.")
        return

    WaitState(player, SKILLS[GSN_STEAL]["beats"])
    percent = randint(1, 100)

    if not is_awake(victim):
        percent -= 10
    elif not can_see(victim, player):
        percent += 25
    else:
        percent += 50

    if percent > get_skill(player, GSN_STEAL):
        # Failure -- victim notices
        chprintln(player, "Oops.")
        affect_strip(player, GSN_SNEAK)
        player.get("affected_by", {}).pop("sneak", None)

        yells = (
            player["name"] + " is a lousy thief!",
            player["name"] + " couldn't rob "
            + ("her" if player.get("sex") == "female" else "his")
            + " way out of a paper bag!",
            player["name"] + " tried to rob me!",
            "Keep your hands out of there, " + player["name"] + "!",
        )
        if not is_awake(victim):
            victim["pos"] = "standing"  # cf. do_wake on victim
        if is_awake(victim):
            do_yell(victim, yells[randint(0, 3)])
        check_improve(player, GSN_STEAL, False, 2)
        multi_hit(victim, player, TYPE_UNDEFINED)
        return

    what = args[0]
    if what in ("coin", "coins", "gold", "silver"):
        gold = victim.get("gold", 0) * randint(1, player["level"]) // MAX_LEVEL
        silver = victim.get("silver", 0) * randint(1, player["level"]) // MAX_LEVEL
        if gold <= 0 and silver <= 0:
            chprintln(player, "You couldn't get any coins.")
            return
        player["gold"] += gold
        player["silver"] += silver
        victim["gold"] -= gold
        victim["silver"] -= silver
        if silver <= 0:
            chprintln(player, "Bingo!  You got %d gold coins." % gold)
        elif gold <= 0:
            chprintln(player, "Bingo!  You got %d silver coins." % silver)
        else:
            chprintln(player, "Bingo!  You got %d silver and %d gold coins." % (silver, gold))
        check_improve(player, GSN_STEAL, True, 2)
        return

    # cf. 1stMud act_obj.c:2324 -- thief is the viewer, not the victim
    obj = get_obj_list(what, victim.get("inv", []), ITEM_DEFS, player)
    if obj is None:
        chprintln(player, "You can't find it.")
        return

    tpl = ITEM_DEFS[obj_vnum(obj)]
    if (not can_drop_obj(player, obj)
            or item_extra_flags(obj, tpl).get("inventory")
            or tpl.get("level", 0) > player["level"]):
        chprintln(player, "You can't pry it away.")
        return

    if len(player["inv"]) + 1 > can_carry_n(player):
        chprintln(player, "You have your hands full.")
        return
    # [PRIMESUD] carry-weight check not ported (no weight tracking)

    victim["inv"].remove(obj)
    player["inv"].append(obj)
    act("You pocket $p.", player, obj, None)
    check_improve(player, GSN_STEAL, True, 2)
    chprintln(player, "Got it!")


def do_compare(player, args):
    """Compare a carried weapon or armor piece against another (cf. 1stMud do_compare in act_info.c).

    With one arg: compares against the worn item of the same type sharing
    a wear flag.  With two args: compares the two named carried items.

    Args:
        player (dict): Player state dict.
        args (list): One or two item keywords.
    """
    if not args:
        chprintln(player, "Compare what to what?")
        return

    carried = player["inv"] + [o for o in player["equip"].values() if o is not None]
    obj1 = get_obj_list(args[0], carried, ITEM_DEFS, player)
    if obj1 is None:
        chprintln(player, "You do not have that item.")
        return
    tpl1 = ITEM_DEFS[obj_vnum(obj1)]

    if len(args) < 2:
        obj2 = None
        wf1 = item_wear_flags(obj1, tpl1)
        for o in player["equip"].values():
            if o is None:
                continue
            tpl = ITEM_DEFS[obj_vnum(o)]
            if (tpl.get("type") == tpl1.get("type")
                    and any(f for f in item_wear_flags(o, tpl)
                            if f != "take" and wf1.get(f))):
                obj2 = o
                break
        if obj2 is None:
            chprintln(player, "You aren't wearing anything comparable.")
            return
    else:
        obj2 = get_obj_list(args[1], carried, ITEM_DEFS, player)
        if obj2 is None:
            chprintln(player, "You do not have that item.")
            return
    tpl2 = ITEM_DEFS[obj_vnum(obj2)]

    msg = None
    value1 = 0
    value2 = 0

    if obj1 is obj2:
        msg = "You compare $p to itself.  It looks about the same."
    elif tpl1.get("type") != tpl2.get("type"):
        msg = "You can't compare $p and $P."
    else:
        itype = tpl1.get("type")
        if itype == "armor":
            # 1stMud compares instance values (act_info.c:3331) -- quest gear scales
            a1 = obj1.get("armor") or tpl1.get("armor", (0, 0, 0, 0))
            a2 = obj2.get("armor") or tpl2.get("armor", (0, 0, 0, 0))
            value1 = a1[0] + a1[1] + a1[2]
            value2 = a2[0] + a2[1] + a2[2]
        elif itype == "weapon":
            # 1stMud new_format: (1 + dice_size) * dice_num, instance values (act_info.c:3337)
            # [PRIMESUD] old-format branch dropped -- converter emits dice for all weapons
            d1 = obj1.get("dice") or tpl1.get("dice", (0, 0, 0))
            d2 = obj2.get("dice") or tpl2.get("dice", (0, 0, 0))
            value1 = (1 + d1[1]) * d1[0]
            value2 = (1 + d2[1]) * d2[0]
        else:
            msg = "You can't compare $p and $P."

    if msg is None:
        if value1 == value2:
            msg = "$p and $P look about the same."
        elif value1 > value2:
            msg = "$p looks better than $P."
        else:
            msg = "$p looks worse than $P."

    act(msg, player, obj1, obj2)


def do_second(player, args):
    """Wield a weapon in the off-hand (cf. 1stMud do_second in act_obj.c)."""
    if not args:
        chprintln(player, "Wear which weapon in your off-hand?")
        return
    obj = get_obj_list(" ".join(args), player["inv"], ITEM_DEFS, player)
    if obj is None:
        chprintln(player, "You have no such thing in your backpack.")
        return
    if (player["equip"].get("shield") is not None
            or player["equip"].get("hold") is not None):
        chprintln(player, "You cannot use a secondary weapon while using a shield or holding an item")
        return
    tpl = ITEM_DEFS[obj["vnum"]]
    if player["level"] < tpl.get("level", 1):
        chprintln(player, "You must be level {} to use this object.".format(tpl.get("level", 1)))
        return
    if player["equip"].get("wield") is None:
        chprintln(player, "You need to wield a primary weapon, before using a secondary one!")
        return
    wield_limit = STR_APP_WIELD[get_curr_stat(player, "str")]
    if tpl.get("weight", 0) > wield_limit // 2:
        chprintln(player, "This weapon is too heavy to be used as a secondary weapon by you.")
        return
    primary_tpl = ITEM_DEFS[player["equip"]["wield"]["vnum"]]
    if tpl.get("weight", 0) * 2 > primary_tpl.get("weight", 0):
        chprintln(player, "Your secondary weapon has to be considerably lighter than the primary one.")
        return
    if not remove_obj(player, "secondary", True):
        return
    chprintln(player, "You wield {} in your off-hand.".format(tpl["short_descr"]))
    if _zap_anti_align(player, obj, tpl):
        return
    equip_char(player, obj, "secondary")


def do_quaff(player, args):
    """Quaff a potion (cf. 1stMud do_quaff in act_obj.c)."""
    if not args:
        chprintln(player, "Quaff what?")
        return
    obj = get_obj_list(" ".join(args), player["inv"], ITEM_DEFS, player)
    if obj is None:
        chprintln(player, "You do not have that potion.")
        return
    tpl = ITEM_DEFS[obj_vnum(obj)]
    if _item_type(obj, tpl) != "potion":
        chprintln(player, "You can quaff only potions.")
        return
    if player["level"] < tpl.get("level", 1):
        chprintln(player, "This liquid is too powerful for you to drink.")
        return
    if validate_item_spell_payload(obj) is None:
        return
    chprintln(player, "You quaff {}.".format(tpl["short_descr"]))
    cast_item_spells(player, obj, player, None)
    player["inv"].remove(obj)


def do_envenom(player, args):
    """Coat a weapon or food/drink with poison (cf. 1stMud do_envenom in act_obj.c).
    [Verified: 04/07/2026; tprint->chprintln output routing re-verified 04/07/2026;
    instance type override added and re-verified 06/07/2026; get_obj_list
    can_see_obj viewer gate added and re-verified 10/07/2026]

    Args:
        player (dict): Player state dict.
        args (list): Item name arguments.
    """
    if not args:
        chprintln(player, "Envenom what item?")
        return

    # 1stMud: get_obj_list(ch, argument, ch->carrying_first) -- carried + worn
    equipped = [o for o in player["equip"].values() if o is not None]
    obj = get_obj_list(" ".join(args), player["inv"] + equipped, ITEM_DEFS, player)
    if obj is None:
        chprintln(player, "You don't have that item.")
        return

    skill = get_skill(player, GSN_ENVENOM)
    if skill < 1:
        chprintln(player, "Are you crazy? You'd poison yourself!")
        return

    obj = _promote_obj(player, obj)
    tpl = ITEM_DEFS[obj_vnum(obj)]
    itype = _item_type(obj, tpl)

    if itype in ("food", "drink"):
        flags = item_extra_flags(obj, tpl)
        if flags.get("bless") or flags.get("burn_proof"):
            act("You fail to poison $p.", player, obj, None, TO_CHAR)
            return
        already = obj["poisoned"] if "poisoned" in obj else tpl.get("poisoned")
        if randint(1, 100) < skill:
            act("$n treats $p with deadly poison.", player, obj, None, TO_ROOM)
            act("You treat $p with deadly poison.", player, obj, None, TO_CHAR)
            if not already:
                obj["poisoned"] = True  # 1stMud: obj->value[3] = 1
                check_improve(player, GSN_ENVENOM, True, 4)
            WaitState(player, SKILLS[GSN_ENVENOM]["beats"])
            return
        act("You fail to poison $p.", player, obj, None, TO_CHAR)
        if not already:
            check_improve(player, GSN_ENVENOM, False, 4)
        WaitState(player, SKILLS[GSN_ENVENOM]["beats"])
        return

    if itype == "weapon":
        wf = item_weapon_flags(obj, tpl)
        flags = item_extra_flags(obj, tpl)
        if (wf.get("flaming") or wf.get("frost") or wf.get("vampiric")
                or wf.get("sharp") or wf.get("vorpal") or wf.get("shocking")
                or flags.get("bless") or flags.get("burn_proof")):
            act("You can't seem to envenom $p.", player, obj, None, TO_CHAR)
            return
        # 1stMud: value[3] < 0 or DAM_BASH attack -> edged weapons only
        _, dam_class = ATTACK_TABLE.get(tpl.get("dam_type", ""), ("", DAM_BASH))
        if dam_class == DAM_BASH:
            chprintln(player, "You can only envenom edged weapons.")
            return
        if wf.get("poison"):
            act("$p is already envenomed.", player, obj, None, TO_CHAR)
            return
        percent = randint(1, 100)
        if percent < skill:
            item_affect_to_obj(obj, {
                "where": "to_weapon", "type": GSN_POISON,
                "level": player["level"] * percent // 100,
                "duration": player["level"] // 2 * percent // 100,
                "location": "none", "modifier": 0, "bitvector": "poison",
            }, tpl)
            act("$n coats $p with deadly venom.", player, obj, None, TO_ROOM)
            act("You coat $p with venom.", player, obj, None, TO_CHAR)
            check_improve(player, GSN_ENVENOM, True, 3)
        else:
            act("You fail to envenom $p.", player, obj, None, TO_CHAR)
            check_improve(player, GSN_ENVENOM, False, 3)
        WaitState(player, SKILLS[GSN_ENVENOM]["beats"])
        return

    act("You can't poison $p.", player, obj, None, TO_CHAR)


def do_eat(player, args):
    """Eat food or pill; honour instance type override and poison
    (cf. 1stMud do_eat in act_obj.c).
    """
    if not args:
        chprintln(player, "Eat what?")
        return
    obj = get_obj_list(" ".join(args), player["inv"], ITEM_DEFS, player)
    if obj is None:
        chprintln(player, "You do not have that item.")
        return
    tpl = ITEM_DEFS[obj_vnum(obj)]
    # Check instance type override first (death_cry may set obj["type"]="trash")
    otype = _item_type(obj, tpl)
    if otype not in ("food", "pill"):
        chprintln(player, "That's not edible.")
        return
    if otype == "pill" and validate_item_spell_payload(obj) is None:
        return
    # Remove from inventory first, then promote to dict for act() rendering [PRIMESUD]
    player["inv"].remove(obj)
    # Promote plain vnum to dict so act() can render short_descr properly [PRIMESUD]
    if not isinstance(obj, dict):
        obj = create_object(obj_vnum(obj))
    # 1stMud: act("$n eats $p.", ch, obj, NULL, TO_ROOM/TO_CHAR)
    act("$n eats $p.", player, obj, None, TO_ROOM)
    act("You eat $p.", player, obj, None, TO_CHAR)
    if otype == "pill":
        cast_item_spells(player, obj, player, None)
    # 1stMud: poison check if obj->value[3] != 0
    elif _is_poisoned_food(obj, tpl):
        # 1stMud value[0] (food fullness hours) = converter's "food_hours";
        # the .dat "value" field is the item's gold cost, not value[0].
        food_amount = tpl.get("food_hours", 0)
        act("$n chokes and gags.", player, None, None, TO_ROOM)
        chprintln(player, "You choke and gag.")
        # 1stMud: af.level = number_fuzzy(obj->value[0]); af.duration = 2 * obj->value[0]
        affect_join(player, _new_affect(_skill_lookup("poison"),
                                        number_fuzzy(food_amount), food_amount * 2,
                                        None, 0, "poison"))


def _is_poisoned_drink(obj, tpl):
    """Return True if drink object/template is poisoned. [PRIMESUD]

    An explicit instance value wins over the template so a poisoned drink
    stays clean after `pour out` clears it (1stMud value[3] = 0).
    """
    if isinstance(obj, dict) and "poisoned" in obj:
        return obj["poisoned"]
    return tpl.get("poisoned")


def _is_poisoned_food(obj, tpl):
    """Return True if food object/template is poisoned. [PRIMESUD]

    An explicit instance value wins over the template so a poisoned food
    item can be cleared by instance override if needed.
    """
    if isinstance(obj, dict) and "poisoned" in obj:
        return obj["poisoned"]
    return tpl.get("poisoned")


def _first_room_fountain(player):
    """Return the first fountain in the current room (cf. 1stMud do_drink/do_fill fountain scan in act_obj.c)."""
    for obj in world.rooms[player["room"]]["items"]:
        if ITEM_DEFS[obj_vnum(obj)].get("type") == "fountain":
            return obj
    return None


def do_drink(player, args):
    """Drink from a fountain or drink container (cf. 1stMud do_drink in act_obj.c).

    [PRIMESUD] Drunk/hunger/thirst condition tracking (gain_condition and
    the COND_* checks) is intentionally omitted.
    """
    if not args:
        obj = _first_room_fountain(player)
        if obj is None:
            chprintln(player, "Drink what?")
            return
    else:
        obj = get_obj_here(player, " ".join(args))
        if obj is None:
            chprintln(player, "You can't find it.")
            return
    tpl = ITEM_DEFS[obj_vnum(obj)]
    otype = tpl.get("type")
    if otype == "fountain":
        liq = _liquid_type(obj, tpl)
        amount = _liq_sip(liq) * 3
    elif otype == "drink":
        if _liquid_left(obj, tpl) <= 0:
            chprintln(player, "It is already empty.")
            return
        liq = _liquid_type(obj, tpl)
        amount = min(_liq_sip(liq), _liquid_left(obj, tpl))
    else:
        chprintln(player, "You can't drink from that.")
        return
    # 1stMud: value[0] == 0 means an unlimited source (typical fountain);
    # those never mutate, so a transient instance renders act $p without
    # persisting to room items / save payload [PRIMESUD]
    if _liquid_total(obj, tpl) > 0:
        obj = _promote_obj(player, obj)
    elif not isinstance(obj, dict):
        obj = create_object(obj_vnum(obj))
    act("$n drinks $T from $p.", player, obj, liq, TO_ROOM)
    act("You drink $T from $p.", player, obj, liq, TO_CHAR)
    if _is_poisoned_drink(obj, tpl):
        # 1stMud applies the poison affect directly -- no saving throw
        act("$n chokes and gags.", player, None, None, TO_ROOM)
        chprintln(player, "You choke and gag.")
        affect_join(player, _new_affect(_skill_lookup("poison"),
                                        number_fuzzy(amount), amount * 3,
                                        None, 0, "poison"))
    if _liquid_total(obj, tpl) > 0:
        _set_liquid(obj, tpl, _liquid_left(obj, tpl) - amount, liq)


def do_fill(player, args):
    """Fill a drink container from a fountain (cf. 1stMud do_fill in act_obj.c)."""
    if not args:
        chprintln(player, "Fill what?")
        return
    obj = get_obj_list(" ".join(args), player["inv"], ITEM_DEFS, player)
    if obj is None:
        chprintln(player, "You do not have that item.")
        return
    fountain = _first_room_fountain(player)
    if fountain is None:
        chprintln(player, "There is no fountain here!")
        return
    tpl = ITEM_DEFS[obj_vnum(obj)]
    if tpl.get("type") != "drink":
        chprintln(player, "You can't fill that.")
        return
    ftpl = ITEM_DEFS[obj_vnum(fountain)]
    left = _liquid_left(obj, tpl)
    fliq = _liquid_type(fountain, ftpl)
    if left != 0 and _liquid_type(obj, tpl) != fliq:
        chprintln(player, "There is already another liquid in it.")
        return
    if left >= _liquid_total(obj, tpl):
        chprintln(player, "Your container is full.")
        return
    obj = _promote_obj(player, obj)
    # fountain is never mutated by fill; transient instance renders act $P
    # without persisting to room items / save payload [PRIMESUD]
    if not isinstance(fountain, dict):
        fountain = create_object(obj_vnum(fountain))
    act("You fill $p with %s from $P." % fliq, player, obj, fountain, TO_CHAR)
    act("$n fills $p with %s from $P." % fliq, player, obj, fountain, TO_ROOM)
    _set_liquid(obj, tpl, _liquid_total(obj, tpl), fliq)


def do_pour(player, args):
    """Pour liquid between drink containers or onto the ground (cf. 1stMud do_pour in act_obj.c).

    [PRIMESUD] Pouring for another character holding a container
    (get_char_room + WEAR_HOLD fallback) is not ported.
    """
    if len(args) < 2:
        chprintln(player, "Pour what into what?")
        return
    out = get_obj_list(args[0], player["inv"], ITEM_DEFS, player)
    if out is None:
        chprintln(player, "You don't have that item.")
        return
    tpl = ITEM_DEFS[obj_vnum(out)]
    if tpl.get("type") != "drink":
        chprintln(player, "That's not a drink container.")
        return
    liq = _liquid_type(out, tpl)
    argument = " ".join(args[1:])
    if argument == "out":
        if _liquid_left(out, tpl) == 0:
            chprintln(player, "It's already empty.")
            return
        out = _promote_obj(player, out)
        _set_liquid(out, tpl, 0, liq)
        out["poisoned"] = False  # 1stMud: value[3] = 0
        act("You invert $p, spilling %s all over the ground." % liq,
            player, out, None, TO_CHAR)
        act("$n inverts $p, spilling %s all over the ground." % liq,
            player, out, None, TO_ROOM)
        return
    # out must be promoted BEFORE the dest lookup: if both names match the
    # same plain-vnum element, the lookup then returns the promoted dict and
    # the `dest is out` self-pour check below stays sound (`is` on equal
    # ints is unreliable) [PRIMESUD]
    out = _promote_obj(player, out)
    dest = get_obj_here(player, argument)
    if dest is None:
        # [PRIMESUD] 1stMud falls back to pouring for a character holding
        # a container; no such targets exist in PrimeSUD
        chprintln(player, "Pour into what?")
        return
    dtpl = ITEM_DEFS[obj_vnum(dest)]
    if dtpl.get("type") != "drink":
        chprintln(player, "You can only pour into other drink containers.")
        return
    if dest is out:
        chprintln(player, "You cannot change the laws of physics!")
        return
    dleft = _liquid_left(dest, dtpl)
    if dleft != 0 and _liquid_type(dest, dtpl) != liq:
        chprintln(player, "They don't hold the same liquid.")
        return
    if _liquid_left(out, tpl) == 0:
        act("There's nothing in $p to pour.", player, out, None, TO_CHAR)
        return
    # promote only once a mutation or act $p render is certain [PRIMESUD]
    dest = _promote_obj(player, dest)
    if dleft >= _liquid_total(dest, dtpl):
        act("$p is already filled to the top.", player, dest, None, TO_CHAR)
        return
    amount = min(_liquid_left(out, tpl), _liquid_total(dest, dtpl) - dleft)
    _set_liquid(dest, dtpl, dleft + amount, liq)
    _set_liquid(out, tpl, _liquid_left(out, tpl) - amount, liq)
    act("You pour %s from $p into $P." % liq, player, out, dest, TO_CHAR)
    act("$n pours %s from $p into $P." % liq, player, out, dest, TO_ROOM)


def _find_here_char_or_obj(player, target_name):
    """Find a mob or object in the current room by name. [PRIMESUD]"""
    for mob_id in world.rooms[player["room"]]["mobs"]:
        mob = world.chars[mob_id]
        if is_name(target_name, MOB_DEFS[mob["tpl"]].get("keywords", "")):
            return (mob, None)
    obj = get_obj_here(player, target_name)
    return (None, obj)


def _destroy_equipped(player, slot):
    """Remove and discard an equipped item from a slot. [PRIMESUD]"""
    if player["equip"].get(slot) is None:
        return
    unequip_char(player, slot)
    player["inv"].pop()


def do_recite(player, args):
    """Recite a scroll (cf. 1stMud do_recite in act_obj.c)."""
    arg1 = args[0] if args else ""
    arg2 = " ".join(args[1:]) if len(args) > 1 else ""
    scroll = get_obj_list(arg1, player["inv"], ITEM_DEFS, player)
    if scroll is None:
        chprintln(player, "You do not have that scroll.")
        return
    tpl = ITEM_DEFS[scroll["vnum"]]
    if tpl["type"] != "scroll":
        chprintln(player, "You can recite only scrolls.")
        return
    if player["level"] < tpl.get("level", 1):
        chprintln(player, "This scroll is too complex for you to comprehend.")
        return
    parsed = validate_item_spell_payload(scroll)
    if parsed is None:
        return
    victim = player
    obj = None
    if arg2:
        victim, obj = _find_here_char_or_obj(player, arg2)
        if victim is None and obj is None:
            chprintln(player, "You can't find it.")
            return
    chprintln(player, "You recite {}.".format(tpl["short_descr"]))
    if randint(1, 100) >= 20 + get_skill(player, GSN_SCROLLS) * 4 // 5:
        chprintln(player, "You mispronounce a syllable.")
        check_improve(player, GSN_SCROLLS, False, 2)
    else:
        cast_item_spells(player, scroll, victim, obj)
        check_improve(player, GSN_SCROLLS, True, 2)
    player["inv"].remove(scroll)


def do_brandish(player, args):
    """Brandish a held staff (cf. 1stMud do_brandish in act_obj.c)."""
    staff = player["equip"].get("hold")
    if staff is None:
        chprintln(player, "You hold nothing in your hand.")
        return
    tpl = ITEM_DEFS[staff["vnum"]]
    if tpl["type"] != "staff":
        chprintln(player, "You can brandish only with a staff.")
        return
    parsed = validate_item_spell_payload(staff)
    if parsed is None:
        return
    _level, payload = parsed
    sn_target = None
    if payload:
        sn_target = _skill_lookup(payload[0])
    WaitState(player, 2 * PULSE_VIOLENCE)
    if staff.get("charges", tpl.get("charges", tpl.get("max_charges", 0))) > 0:
        chprintln(player, "You brandish {}.".format(tpl["short_descr"]))
        if player["level"] < tpl.get("level", 1) or randint(1, 100) >= 20 + get_skill(player, GSN_STAVES) * 4 // 5:
            chprintln(player, "You fail to invoke {}.".format(tpl["short_descr"]))
            check_improve(player, GSN_STAVES, False, 2)
        else:
            target_type = None
            if sn_target is not None:
                target_type = SKILLS[sn_target].get("target")
            if target_type in ("ignore", "char_self", "char_defensive", "obj_char_defensive"):
                cast_item_spells(player, staff, player, None)
                check_improve(player, GSN_STAVES, True, 2)
            elif target_type in ("char_offensive", "obj_char_offensive"):
                for mob_id in list(world.rooms[player["room"]]["mobs"]):
                    if mob_id in world.chars:
                        cast_item_spells(player, staff, world.chars[mob_id], None)
                        check_improve(player, GSN_STAVES, True, 2)
            else:
                tprint("[DEV] " + tpl["short_descr"] + ": unsupported staff target")
                return
    staff["charges"] = staff.get("charges", tpl.get("charges", tpl.get("max_charges", 0))) - 1
    if staff["charges"] <= 0:
        chprintln(player, "Your {} blazes bright and is gone.".format(tpl["short_descr"]))
        _destroy_equipped(player, "hold")


def do_zap(player, args):
    """Zap with a held wand (cf. 1stMud do_zap in act_obj.c)."""
    arg = " ".join(args)
    if not arg and player.get("fighting") is None:
        chprintln(player, "Zap whom or what?")
        return
    wand = player["equip"].get("hold")
    if wand is None:
        chprintln(player, "You hold nothing in your hand.")
        return
    tpl = ITEM_DEFS[wand["vnum"]]
    if tpl["type"] != "wand":
        chprintln(player, "You can zap only with a wand.")
        return
    if validate_item_spell_payload(wand) is None:
        return
    victim = None
    obj = None
    if not arg:
        victim = world.chars.get(player.get("fighting"))
        if victim is None:
            chprintln(player, "Zap whom or what?")
            return
    else:
        victim, obj = _find_here_char_or_obj(player, arg)
        if victim is None and obj is None:
            chprintln(player, "You can't find it.")
            return
    WaitState(player, 2 * PULSE_VIOLENCE)
    if wand.get("charges", tpl.get("charges", tpl.get("max_charges", 0))) > 0:
        if victim is not None:
            chprintln(player, "You zap " + MOB_DEFS[victim["tpl"]]["short_descr"] + " with " + tpl["short_descr"] + ".")
        else:
            chprintln(player, "You zap " + ITEM_DEFS[obj["vnum"]]["short_descr"] + " with " + tpl["short_descr"] + ".")
        if player["level"] < tpl.get("level", 1) or randint(1, 100) >= 20 + get_skill(player, GSN_WANDS) * 4 // 5:
            chprintln(player, "Your efforts with {} produce only smoke and sparks.".format(tpl["short_descr"]))
            check_improve(player, GSN_WANDS, False, 2)
        else:
            cast_item_spells(player, wand, victim, obj)
            check_improve(player, GSN_WANDS, True, 2)
    wand["charges"] = wand.get("charges", tpl.get("charges", tpl.get("max_charges", 0))) - 1
    if wand["charges"] <= 0:
        chprintln(player, "Your {} explodes into fragments.".format(tpl["short_descr"]))
        _destroy_equipped(player, "hold")


# Weapon choices for do_outfit; order mirrors 1stMud weapon_table (const.c); sword is
# default/tie-winner and handled separately as the seed value.
_WEAPON_OUTFIT_CHOICES = [
    ("mace",    OBJ_VNUM_SCHOOL_MACE),
    ("dagger",  OBJ_VNUM_SCHOOL_DAGGER),
    ("axe",     OBJ_VNUM_SCHOOL_AXE),
    ("staff",   OBJ_VNUM_SCHOOL_STAFF),  # weapon_table: "staff" -> SCHOOL_STAFF 3718, gsn_spear
    ("flail",   OBJ_VNUM_SCHOOL_FLAIL),
    ("whip",    OBJ_VNUM_SCHOOL_WHIP),
    ("polearm", OBJ_VNUM_SCHOOL_POLEARM),
]


def do_outfit(player, args):
    """Equip a new character with Mud School starter gear (cf. 1stMud do_outfit in act_wiz.c).

    Fills only empty slots; skips any slot already occupied.  Weapon type is
    chosen by highest skill in player["learned"], defaulting to sword on ties
    (mirrors 1stMud weapon_table loop).  Also called at character creation
    (game_state.py new_game) with no level restriction concern since level=1.

    Deviations from 1stMud:
      - No NPC guard (no NPCs in PrimeSUD).
      - obj->cost = 0 applied to weapon too (1stMud omits it for the weapon).

    Args:
        player (dict): Player instance dict.
        args (str): Unused.
    """
    if player["level"] > 5:
        chprintln(player, "Find it yourself!")
        return

    def _equip(slot, vnum):
        if player["equip"].get(slot) is not None:
            return
        obj = create_object(vnum)
        obj["cost"] = 0   # cf. 1stMud do_outfit: obj->cost = 0 (weapon excepted upstream)
        player["inv"].append(obj)  # obj_to_char equivalent
        equip_char(player, obj, slot)

    _equip("light", OBJ_VNUM_SCHOOL_BANNER)
    _equip("body",  OBJ_VNUM_SCHOOL_VEST)

    if player["equip"].get("wield") is None:
        wield_vnum = OBJ_VNUM_SCHOOL_SWORD
        best_pct = player["learned"].get(WEAPON_GSN_MAP.get("sword", -1), 0)
        for wtype, vnum in _WEAPON_OUTFIT_CHOICES:
            pct = player["learned"].get(WEAPON_GSN_MAP.get(wtype, -1), 0)
            if pct > best_pct:
                best_pct = pct
                wield_vnum = vnum
        _equip("wield", wield_vnum)

    wobj = player["equip"].get("wield")
    if not (wobj and ITEM_DEFS[wobj["vnum"]].get("weapon_flags", {}).get("two_hands")):
        _equip("shield", OBJ_VNUM_SCHOOL_SHIELD)

    chprintln(player, "You have been equipped by the gods.")


def _sacrifice_one(player, obj, rs):
    """Sacrifice a single room item for silver (inner helper for do_sacrifice). [PRIMESUD]

    Args:
        player (dict): Player state dict.
        obj: Item instance dict from rs["items"].
        rs (dict): Current room state dict.
    """
    tpl = ITEM_DEFS[obj_vnum(obj)]

    if tpl.get("type") == "pc_corpse" and obj.get("contents"):
        chprintln(player, "Your deity wouldn't like that.")
        return

    wear = item_wear_flags(obj, tpl)
    extra = item_extra_flags(obj, tpl)
    if "take" not in wear or extra.get("no_sac"):
        short = obj.get("short_descr") or tpl["short_descr"]
        chprintln(player, short + " is not an acceptable sacrifice.")
        return

    # 1stMud: silver = Max(1, obj->level * 3) -- instance level (set on corpses), not template
    silver = max(1, (obj.get("level") if isinstance(obj, dict) and obj.get("level") is not None
                     else tpl.get("level", 0)) * 3)
    if tpl.get("type") not in ("npc_corpse", "pc_corpse"):
        silver = min(silver, obj.get("cost", 0))
    silver = max(1, silver)

    if silver == 1:
        chprintln(player, "Your deity gives you one silver coin for your sacrifice.")
    else:
        chprintln(player, "Your deity gives you " + str(silver) + " silver coins for your sacrifice.")

    player["silver"] = player.get("silver", 0) + silver

    short = obj.get("short_descr") or tpl["short_descr"]
    chprintln(player, "You sacrifice " + short + " to your deity.")
    rs["items"].remove(obj)


def do_sacrifice(player, args):
    """Sacrifice a room item to the deity for silver (cf. 1stMud do_sacrifice in act_obj.c).

    Args:
        player (dict): Player state dict.
        args (list): Parsed command arguments.
    """
    rs = world.rooms[player["room"]]

    if not args or " ".join(args) == player.get("name", "").lower():
        chprintln(player, "Your deity appreciates your offer and may accept it later.")
        return

    arg = " ".join(args)

    if arg == "all":
        # cf. 1stMud do_sacrifice all (act_obj.c:1811) -- recurses per obj name,
        # so unseen objects fail the gated get_obj_list and are skipped
        for obj in list(rs["items"]):
            if can_see_obj(player, obj):
                _sacrifice_one(player, obj, rs)
        return

    obj = get_obj_list(arg, rs["items"], ITEM_DEFS, player)
    if obj is None:
        chprintln(player, "You can't find it.")
        return

    _sacrifice_one(player, obj, rs)
