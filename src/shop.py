"""Shop system: buy, sell, list, and value commands (cf. 1stMud do_buy/do_sell/do_list/do_value in act_obj.c)."""

import world
from world import ITEM_DEFS, MOB_DEFS, ROOM_DEFS
from handler import (act, chprintln, is_name, can_see, can_see_obj,
                   get_char_room, TO_CHAR, TO_VICT, TO_ROOM)
from skill_utils import get_skill, check_improve
from comm import do_function, do_say
from game_time import time_info
from magic import spell_identify
from mob import spawn_pet
from item import (get_obj_list, obj_vnum, create_object, item_extra_flags,
                  ensure_item_extra_flags, can_drop_obj, can_carry_n,
                  can_carry_w, get_obj_weight)
from skills_table import GSN_HAGGLE
from urandom import randint
from util import num_str, pad_left


# -- Money helpers (cf. 1stMud check_worth/deduct_cost/add_cost in handler.c) --

def check_worth(ch, cost):
    """True if ch has enough gold+silver for cost in silver units (cf. 1stMud `check_worth` in handler.c: VALUE_DEFAULT branch)."""
    return ch["gold"] * 100 + ch["silver"] >= cost


def deduct_cost(ch, cost):
    """Remove cost (silver units) from ch, converting gold<->silver as needed (cf. 1stMud `deduct_cost` in handler.c: VALUE_DEFAULT branch)."""
    total = ch["gold"] * 100 + ch["silver"] - cost
    ch["gold"] = total // 100
    ch["silver"] = total % 100


def add_cost(ch, cost):
    """Add cost (silver units) to ch's money (cf. 1stMud `add_cost` in handler.c: VALUE_DEFAULT branch)."""
    total = ch["gold"] * 100 + ch["silver"] + cost
    ch["gold"] = total // 100
    ch["silver"] = total % 100


# -- Shop helpers (cf. 1stMud act_obj.c) --------------------------------------

def find_keeper(player):
    """Find NPC shopkeeper in player's room, check visibility (cf. 1stMud find_keeper in act_obj.c).

    Returns:
        tuple: (keeper_inst, keeper_id) or (None, None) if no usable shopkeeper.
    """
    rs = world.rooms[player["room"]]
    keeper = None
    keeper_id = None
    for mid in rs["mobs"]:
        inst = world.chars[mid]
        if inst["is_npc"] and MOB_DEFS[inst["tpl"]].get("shop"):
            keeper = inst
            keeper_id = mid
            break

    if keeper is None:
        chprintln(player, "You can't do that here.")
        return None, None

    shop = MOB_DEFS[keeper["tpl"]]["shop"]
    if time_info["hour"] < shop.get("open_hour", 0):
        do_function(keeper, do_say, "Sorry, I am closed. Come back later.")
        return None, None
    if time_info["hour"] > shop.get("close_hour", 23):
        do_function(keeper, do_say, "Sorry, I am closed. Come back tomorrow.")
        return None, None

    if not can_see(keeper, player):
        do_function(keeper, do_say, "I don't trade with folks I can't see.")
        return None, None

    return keeper, keeper_id


def get_cost(keeper, obj, buy):
    """Calculate item cost adjusted by shop profit margins (cf. 1stMud get_cost in act_obj.c).

    Args:
        keeper (dict): Shopkeeper mob instance.
        obj: Item instance dict, or None.
        buy (bool): True for buy price (player pays), False for sell price.

    Returns:
        int: Price in silver units, 0 if shop won't deal in this item.
    """
    shop = MOB_DEFS[keeper["tpl"]].get("shop")
    if shop is None or obj is None:
        return 0

    tpl = ITEM_DEFS[obj_vnum(obj)]
    cost_base = obj.get("cost", tpl.get("value", 0))

    if buy:
        cost = cost_base * shop["profit_buy"] // 100
    else:
        cost = 0
        item_type = tpl.get("type", "")
        for bt in shop["buy_types"]:
            if item_type == bt:
                cost = cost_base * shop["profit_sell"] // 100
                break

        if not item_extra_flags(obj, tpl).get("sell_extract"):
            for inv_obj in keeper["inv"]:
                if obj_vnum(inv_obj) == obj_vnum(obj):
                    inv_tpl = ITEM_DEFS[obj_vnum(inv_obj)]
                    inv_sd = inv_obj.get("short_descr") or inv_tpl["short_descr"]
                    obj_sd = obj.get("short_descr") or tpl["short_descr"]
                    if inv_sd == obj_sd:
                        if item_extra_flags(inv_obj, inv_tpl).get("inventory"):
                            cost //= 2
                        else:
                            cost = cost * 3 // 4

    # Wand/staff charge adjustment (cf. 1stMud get_cost value[1]/value[2] check)
    if tpl.get("type") in ("staff", "wand"):
        max_ch = obj.get("max_charges", tpl.get("max_charges", 0))
        cur_ch = obj.get("charges", tpl.get("charges", 0))
        if max_ch == 0:
            cost //= 4
        else:
            cost = cost * cur_ch // max_ch

    return cost


def _get_obj_keeper(player, keeper, arg):
    """Find item in keeper's inventory by name, skipping duplicate runs (cf. 1stMud get_obj_keeper in act_obj.c).

    Args:
        player (dict): Player character.
        keeper (dict): Shopkeeper mob instance.
        arg (str): Item name, optionally prefixed with "N." ordinal.

    Uses N.name syntax. Consecutive items with same vnum and short_descr
    count as one entry for ordinal purposes.
    """
    if '.' in arg:
        prefix, rest = arg.split('.', 1)
        try:
            number = int(prefix)
            arg = rest
        except ValueError:
            number = 1
    else:
        number = 1

    count = 0
    i = 0
    inv = keeper["inv"]
    while i < len(inv):
        obj = inv[i]
        vnum = obj_vnum(obj)
        tpl = ITEM_DEFS[vnum]
        if can_see_obj(keeper, obj) and can_see_obj(player, obj):
            if is_name(arg, tpl.get("keywords", "")):
                count += 1
                if count == number:
                    return obj
                obj_sd = obj.get("short_descr") or tpl["short_descr"]
                while i + 1 < len(inv):
                    nxt = inv[i + 1]
                    if obj_vnum(nxt) != vnum:
                        break
                    nxt_tpl = ITEM_DEFS[obj_vnum(nxt)]
                    nxt_sd = nxt.get("short_descr") or nxt_tpl["short_descr"]
                    if obj_sd != nxt_sd:
                        break
                    i += 1
        i += 1
    return None


def _mult_argument(argument):
    """Parse '5*sword' into (5, 'sword'); plain 'sword' returns (1, 'sword') (cf. 1stMud `mult_argument` in interp.c)."""
    star = argument.find('*')
    if star < 0:
        return 1, argument
    try:
        return int(argument[:star]), argument[star + 1:]
    except ValueError:
        return 1, argument


# -- Commands ------------------------------------------------------------------

def _buy_pet(player, args):
    """Buy a pet from a pet shop (cf. 1stMud do_buy ROOM_PET_SHOP branch in act_obj.c).

    Pets live in the room after the shop room (vnum + 1), except New Thalos
    (9621), whose stock room is 9706.
    """

    # hack to make new thalos pets work (cf. 1stMud/QuickMUD vnum 9621 -> 9706)
    if player["room"] == 9621:
        next_vnum = 9706
    else:
        next_vnum = player["room"] + 1
    if next_vnum not in ROOM_DEFS or next_vnum not in world.rooms:
        # 1stMud: bugf("Do_buy: bad pet shop at vnum %ld.")
        chprintln(player, "Sorry, you can't buy that here.")
        return

    pet_id = get_char_room(args[0], world.rooms[next_vnum]["mobs"], world.chars)
    stock = world.chars.get(pet_id) if pet_id is not None else None
    if stock is None or not stock.get("act_flags", {}).get("pet"):
        chprintln(player, "Sorry, you can't buy that here.")
        return

    if player.get("pet") is not None:
        chprintln(player, "You already own a pet.")
        return

    cost = 10 * stock["level"] * stock["level"]

    if not check_worth(player, cost):
        chprintln(player, "You can't afford it.")
        return

    if player["level"] < stock["level"]:
        chprintln(player, "You're not powerful enough to master this pet.")
        return

    roll = randint(1, 100)
    if roll < get_skill(player, GSN_HAGGLE):
        cost -= cost // 2 * roll // 100
        chprintln(player, "You haggle the price down to " + str(cost) + " coins.")
        check_improve(player, GSN_HAGGLE, True, 4)

    deduct_cost(player, cost)

    # cf. 1stMud: pet = create_mobile(pet->pIndexData) + ACT_PET/AFF_CHARM/
    # name/neck tag/add_follower/leader/pet linkage
    name_arg = args[1] if len(args) > 1 else None
    pet = spawn_pet(stock["tpl"], player, name_arg=name_arg)
    chprintln(player, "Enjoy your pet.")
    act("$n bought $N as a pet.", player, None, pet, TO_ROOM)


def do_buy(player, args):
    """Purchase items from a shopkeeper or pet shop (cf. 1stMud do_buy in act_obj.c)."""
    if not args:
        chprintln(player, "Buy what?")
        return

    # -- Pet shop (cf. 1stMud ROOM_PET_SHOP branch)
    if ROOM_DEFS[player["room"]].get("flags", {}).get("pet_shop"):
        _buy_pet(player, args)
        return

    keeper, keeper_id = find_keeper(player)
    if keeper is None:
        return

    number, arg = _mult_argument(" ".join(args))
    obj = _get_obj_keeper(player, keeper, arg)
    cost = get_cost(keeper, obj, True)

    if number < 1 or number > 99:
        act("$n tells you 'Get real!", keeper, None, player, TO_VICT)
        return

    if cost <= 0 or obj is None or not can_see_obj(player, obj):
        act("$n tells you 'I don't sell that -- try 'list''.", keeper, None, player, TO_VICT)
        player["reply"] = keeper["id"]
        return

    tpl = ITEM_DEFS[obj_vnum(obj)]
    flags = item_extra_flags(obj, tpl)

    if not flags.get("inventory"):
        count = 0
        obj_sd = obj.get("short_descr") or tpl["short_descr"]
        for inv_obj in keeper["inv"]:
            if obj_vnum(inv_obj) == obj_vnum(obj):
                inv_tpl = ITEM_DEFS[obj_vnum(inv_obj)]
                inv_sd = inv_obj.get("short_descr") or inv_tpl["short_descr"]
                if obj_sd == inv_sd:
                    count += 1
        if count < number:
            act("$n tells you 'I don't have that many in stock.", keeper, None, player, TO_VICT)
            player["reply"] = keeper["id"]
            return

    if not check_worth(player, cost * number):
        if number > 1:
            act("$n tells you 'You can't afford to buy that many.", keeper, None, player, TO_VICT)
        else:
            act("$n tells you 'You can't afford to buy $p'.", keeper, obj, player, TO_VICT)
        player["reply"] = keeper["id"]
        return

    if tpl.get("level", 0) > player["level"]:
        act("$n tells you 'You can't use $p yet'.", keeper, obj, player, TO_VICT)
        player["reply"] = keeper["id"]
        return

    carry_n = len(player["inv"]) + sum(1 for e in player["equip"].values() if e is not None)
    if carry_n + number > can_carry_n(player):
        chprintln(player, "You can't carry that many items.")
        return

    carry_w = sum(get_obj_weight(o) for o in player["inv"])
    carry_w += sum(get_obj_weight(e) for e in player["equip"].values() if e is not None)
    if get_obj_weight(obj) * number + carry_w > can_carry_w(player):
        chprintln(player, "You can't carry that much weight.")
        return

    # Haggle (cf. 1stMud do_buy haggle block)
    roll = randint(1, 100)
    if not flags.get("sell_extract") and roll < get_skill(player, GSN_HAGGLE):
        cost -= tpl.get("value", 0) // 2 * roll // 100
        act("You haggle with $N.", player, None, keeper, TO_CHAR)
        check_improve(player, GSN_HAGGLE, True, 4)

    if number > 1:
        act("$n buys $p[" + str(number) + "].", player, obj, None, TO_ROOM)
        act("You buy $p for " + str(cost * number) + " silver.", player, obj, None, TO_CHAR)
    else:
        act("$n buys $p.", player, obj, None, TO_ROOM)
        act("You buy $p for " + str(cost) + " silver.", player, obj, None, TO_CHAR)

    deduct_cost(player, cost * number)
    add_cost(keeper, cost * number)

    for _ in range(number):
        if flags.get("inventory"):
            t_obj = create_object(obj_vnum(obj))
        else:
            t_obj = obj
            keeper["inv"].remove(t_obj)
            obj = _get_obj_keeper(player, keeper, arg)

        # Clear shop-assigned timer on bought items (cf. 1stMud ITEM_HAD_TIMER logic)
        if t_obj.get("timer", 0) > 0:
            ef = t_obj.get("extra_flags", {})
            if not ef.get("had_timer"):
                t_obj["timer"] = 0
            ef.pop("had_timer", None)

        player["inv"].append(t_obj)
        if cost < t_obj.get("cost", 0):
            t_obj["cost"] = cost


def do_list(player, args):
    """Display shopkeeper's or pet shop's stock (cf. 1stMud do_list in act_obj.c)."""
    # -- Pet shop (cf. 1stMud ROOM_PET_SHOP branch)
    if ROOM_DEFS[player["room"]].get("flags", {}).get("pet_shop"):
        # hack to make new thalos pets work (cf. 1stMud/QuickMUD vnum 9621 -> 9706)
        if player["room"] == 9621:
            next_vnum = 9706
        else:
            next_vnum = player["room"] + 1
        if next_vnum not in ROOM_DEFS or next_vnum not in world.rooms:
            # 1stMud: bugf("Do_list: bad pet shop at vnum %ld.")
            chprintln(player, "You can't do that here.")
            return
        found = False
        for pid in world.rooms[next_vnum]["mobs"]:
            pet = world.chars.get(pid)
            if pet is not None and pet.get("act_flags", {}).get("pet"):
                if not found:
                    found = True
                    chprintln(player, "Pets for sale:")
                chprintln(player, "[" + pad_left(num_str(pet["level"]), 2) + "] "
                          + pad_left(num_str(10 * pet["level"] * pet["level"]), 8) + " - "
                          + MOB_DEFS[pet["tpl"]]["short_descr"])
        if not found:
            chprintln(player, "Sorry, we're out of pets right now.")
        return

    keeper, keeper_id = find_keeper(player)
    if keeper is None:
        return

    arg = args[0] if args else ""

    found = False
    i = 0
    inv = keeper["inv"]
    while i < len(inv):
        obj = inv[i]
        vnum = obj_vnum(obj)
        tpl = ITEM_DEFS[vnum]
        cost = get_cost(keeper, obj, True)

        if can_see_obj(player, obj) and cost > 0:
            if not arg or is_name(arg, tpl.get("keywords", "")):
                if not found:
                    found = True
                    chprintln(player, "[Lv Price Qty] Item")

                flags = item_extra_flags(obj, tpl)
                short = obj.get("short_descr") or tpl["short_descr"]

                if flags.get("inventory"):
                    chprintln(player, "[" + pad_left(num_str(tpl.get("level", 0)), 2) + " "
                              + pad_left(num_str(cost), 5) + " -- ] " + short)
                else:
                    count = 1
                    while i + 1 < len(inv):
                        nxt = inv[i + 1]
                        if obj_vnum(nxt) != vnum:
                            break
                        nxt_tpl = ITEM_DEFS[obj_vnum(nxt)]
                        nxt_sd = nxt.get("short_descr") or nxt_tpl["short_descr"]
                        if short != nxt_sd:
                            break
                        count += 1
                        i += 1
                    chprintln(player, "[" + pad_left(num_str(tpl.get("level", 0)), 2) + " "
                              + pad_left(num_str(cost), 5) + " " + pad_left(num_str(count), 2)
                              + " ] " + short)
        i += 1

    if not found:
        chprintln(player, "You can't buy anything here.")


def do_sell(player, args):
    """Sell an item to a shopkeeper (cf. 1stMud do_sell in act_obj.c)."""
    if not args:
        chprintln(player, "Sell what?")
        return

    keeper, keeper_id = find_keeper(player)
    if keeper is None:
        return

    obj = get_obj_list(args[0], player["inv"], ITEM_DEFS, player)
    if obj is None:
        act("$n tells you 'You don't have that item'.", keeper, None, player, TO_VICT)
        player["reply"] = keeper["id"]
        return

    tpl = ITEM_DEFS[obj_vnum(obj)]
    flags = item_extra_flags(obj, tpl)

    if not can_drop_obj(player, obj):
        chprintln(player, "You can't let go of it.")
        return

    if flags.get("quest"):
        chprintln(player, "You should sell that to the questor instead!")
        return

    if not can_see_obj(keeper, obj):
        act("$n doesn't see what you are offering.", keeper, None, player, TO_VICT)
        return

    cost = get_cost(keeper, obj, False)
    if cost <= 0:
        act("$n looks uninterested in $p.", keeper, obj, player, TO_VICT)
        return

    if not check_worth(keeper, cost):
        act("$n tells you 'I'm afraid I don't have enough wealth to buy $p.", keeper, obj, player, TO_VICT)
        return

    act("$n sells $p.", player, obj, None, TO_ROOM)

    # Haggle (cf. 1stMud do_sell haggle block)
    roll = randint(1, 100)
    if not flags.get("sell_extract") and roll < get_skill(player, GSN_HAGGLE):
        chprintln(player, "You haggle with the shopkeeper.")
        cost += tpl.get("value", 0) // 2 * roll // 100
        cost = min(cost, 95 * get_cost(keeper, obj, True) // 100)
        cost = min(cost, keeper["silver"] + 100 * keeper["gold"])
        check_improve(player, GSN_HAGGLE, True, 4)

    silver_part = cost - (cost // 100) * 100
    gold_part = cost // 100
    msg = "You sell $p for " + str(silver_part) + " silver and " + str(gold_part) + " gold piece" + ("" if cost == 1 else "s") + "."
    act(msg, player, obj, None, TO_CHAR)
    add_cost(player, cost)
    deduct_cost(keeper, cost)

    if tpl.get("type") == "trash" or flags.get("sell_extract"):
        player["inv"].remove(obj)
    else:
        player["inv"].remove(obj)
        if obj.get("timer", 0):
            ensure_item_extra_flags(obj, tpl)["had_timer"] = True
        else:
            obj["timer"] = randint(50, 100)
        keeper["inv"].append(obj)


def do_value(player, args):
    """Appraise item value at a shop (cf. 1stMud do_value in act_obj.c)."""
    if not args:
        chprintln(player, "Value what?")
        return

    keeper, keeper_id = find_keeper(player)
    if keeper is None:
        return

    obj = get_obj_list(args[0], player["inv"], ITEM_DEFS, player)
    if obj is None:
        act("$n tells you 'You don't have that item'.", keeper, None, player, TO_VICT)
        player["reply"] = keeper["id"]
        return

    tpl = ITEM_DEFS[obj_vnum(obj)]

    if not can_see_obj(keeper, obj):
        act("$n doesn't see what you are offering.", keeper, None, player, TO_VICT)
        return

    if not can_drop_obj(player, obj):
        chprintln(player, "You can't let go of it.")
        return

    cost = get_cost(keeper, obj, False)
    if cost <= 0:
        act("$n looks uninterested in $p.", keeper, obj, player, TO_VICT)
        return

    silver_part = cost - (cost // 100) * 100
    gold_part = cost // 100
    msg = "$n tells you 'I'll give you " + str(silver_part) + " silver and " + str(gold_part) + " gold coins for $p'."
    act(msg, keeper, obj, player, TO_VICT)
    player["reply"] = keeper["id"]


def do_appraise(player, args):
    """Appraise an item in a shopkeeper's inventory -- value + identify (cf. 1stMud do_appraise in act_obj.c)."""
    if not args:
        chprintln(player, "Appraise what?")
        return

    keeper, keeper_id = find_keeper(player)
    if keeper is None:
        return

    obj = _get_obj_keeper(player, keeper, args[0])
    if obj is None:
        act("{c$n{c tells you '{CI don't have that item.{c'{x.", keeper, None, player, TO_VICT)
        player["reply"] = keeper["id"]
        return

    spell_identify(0, player["level"], player, obj, "obj")
