"""Inventory, equipment, item-use, and starter-outfit commands."""

import terminal
import world
from combat import (_get_weapon_skill, is_safe, multi_hit, number_fuzzy,
                    create_money, _get_size)
from comm import do_yell
from config import (STR_APP_WIELD, PULSE_VIOLENCE, WEAR_LABELS,
                    MAX_LEVEL, MAX_MORTAL_LEVEL, TYPE_UNDEFINED,
                    ATTACK_TABLE, DAM_BASH, SIZE_RANK)
from debug import DBG  # [PRIMESUD] holylight vnum overlay
from handler import (get_curr_stat, is_name, equip_char, unequip_char, act,
                     get_char_room, can_see, can_see_obj, is_awake,
                     affect_strip, affect_join, chprintln,
                     _item_armor_runtime, tpl_flag_affects,
                     is_good, is_evil, is_neutral,
                     TO_CHAR, TO_ROOM, TO_VICT, TO_NOTVICT)
from item import (get_obj_list, get_obj_here, obj_vnum, create_object,
                  item_extra_flags, item_wear_flags, apply_money_pickup,
                  can_drop_obj, can_carry_n, can_carry_w, get_obj_weight,
                  get_carry_weight,
                  item_weapon_flags, item_affect_to_obj,
                  item_container_flags, CONTAINER_TYPES,
                  item_type as _item_type,
                  promote_obj as _promote_obj,
                  liquid_left as _liquid_left,
                  liquid_total as _liquid_total,
                  liquid_type as _liquid_type,
                  set_liquid as _set_liquid,
                  liq_sip as _liq_sip)
from magic import (cast_item_spells, validate_item_spell_payload,
                   _new_affect, _skill_lookup)
from picker import pick_from
from quest import (quest_obj_check, is_quester, QUEST_DELIVER,
                   QUEST_RETURN_DELIVER, _giver_name)
from skill_utils import WaitState, check_improve, get_skill
from skills_table import (GSN_SCROLLS, GSN_STAVES, GSN_WANDS, GSN_STEAL,
                          GSN_SNEAK, GSN_ENVENOM, GSN_POISON,
                          GSN_SHIELD_BLOCK)
from skills_table import SKILLS, WEAPON_GSN_MAP
from terminal import tprint
from urandom import randint
from util import int_str, num_str
from world import ITEM_DEFS, MOB_DEFS, item_tpl
from world import (OBJ_VNUM_SCHOOL_BANNER,
                   OBJ_VNUM_SCHOOL_MACE, OBJ_VNUM_SCHOOL_DAGGER, OBJ_VNUM_SCHOOL_SWORD,
                   OBJ_VNUM_SCHOOL_VEST, OBJ_VNUM_SCHOOL_SHIELD,
                   OBJ_VNUM_SCHOOL_STAFF, OBJ_VNUM_SCHOOL_AXE, OBJ_VNUM_SCHOOL_FLAIL,
                   OBJ_VNUM_SCHOOL_WHIP, OBJ_VNUM_SCHOOL_POLEARM)

_CONTAINER_TYPES = CONTAINER_TYPES  # [PRIMESUD] shared definition now lives in item.py




def _loot_container_picker(player, container):
    """Present picker UI to loot items from a container. [PRIMESUD]

    cf. 1stMud do_get CONT_CLOSED check (act_obj.c:280) -- closed containers
    can't be looted, checked before the no-arg [loot] picker shown here.

    Returns:
        str or None: Resolved "get ..." command for history replay, or None
            when nothing was taken.
    """
    cont_tpl = item_tpl(container)
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
        ctpl = item_tpl(cobj)
        names.append(cobj.get("short_descr") or ctpl["short_descr"])
    if len(visible) > 1:
        names.append("[all]")
    cidx = pick_from("Take what?", names)
    if cidx < 0:
        return
    cont_kw = cont_tpl.get("keywords", cont_tpl["short_descr"]).split()[0]
    if cidx == len(visible):
        for cobj in list(visible):
            ctpl = item_tpl(cobj)
            if not _check_carry_get(player, cobj, ctpl):
                continue
            container["contents"].remove(cobj)
            chprintln(player, "You get " + (cobj.get("short_descr") or ctpl["short_descr"]) + ".")
            if not apply_money_pickup(player, cobj, ctpl):
                player["inv"].append(cobj)
                _get_triggers(player, cobj)
                quest_obj_check(player, cobj)  # cf. 1stMud get_obj quest hook
        return "get all " + cont_kw
    cobj = visible[cidx]
    ctpl = item_tpl(cobj)
    if not _check_carry_get(player, cobj, ctpl):
        return
    container["contents"].remove(cobj)
    chprintln(player, "You get " + (cobj.get("short_descr") or ctpl["short_descr"]) + ".")
    if not apply_money_pickup(player, cobj, ctpl):
        player["inv"].append(cobj)
        _get_triggers(player, cobj)
        quest_obj_check(player, cobj)  # cf. 1stMud get_obj quest hook
    return "get " + ctpl.get("keywords", ctpl["short_descr"]).split()[0] + " " + cont_kw


def _obj_number(obj):
    """Return obj's contribution (plus contents) to the carry-item count
    (cf. 1stMud get_obj_number in handler.c).

    Containers, corpses, money, gems, and jewelry contribute 0 themselves;
    everything else contributes 1.  [PRIMESUD] gem/jewelry types added to
    the zero-count set alongside PrimeSUD's corpse split of ITEM_CONTAINER.
    """
    tpl = item_tpl(obj)
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


def _get_triggers(player, obj):
    """Obj then room TRIG_GET after a successful pickup (cf. get_obj,
    act_obj.c:165-168). [PRIMESUD] shared by every do_get pickup path."""
    # [PRIMESUD] litter decay is floor-only (see obj_update spill): picking
    # the item up makes it the player's for keeps, like a shop buy-back
    # clearing a had_timer stamp. Flag only ever set on the instance dict.
    ef = obj.get("extra_flags")
    if ef is not None and ef.pop("litter", None):
        obj.pop("timer", None)
    import mobprog  # deferred: keep mobprog off the boot path
    if mobprog.has_otrigger(obj, "get"):
        mobprog.ogive_trigger(
            {"obj": obj, "room": player["room"], "carrier": player},
            player, "get")
    if mobprog.has_rtrigger(player["room"], "get"):
        mobprog.rgive_trigger(player["room"], player, obj, "get")


def _drop_triggers(player, obj):
    """Obj then room TRIG_DROP after a drop (cf. do_drop, act_obj.c:581-584).
    [PRIMESUD] shared by every do_drop path."""
    import mobprog  # deferred: keep mobprog off the boot path
    if mobprog.has_otrigger(obj, "drop"):
        mobprog.ogive_trigger(
            {"obj": obj, "room": player["room"], "carrier": None},
            player, "drop")
    if mobprog.has_rtrigger(player["room"], "drop"):
        mobprog.rgive_trigger(player["room"], player, obj, "drop")


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
                 if item_tpl(obj).get("type") not in _CONTAINER_TYPES
                 and "take" in item_wear_flags(obj, item_tpl(obj))
                 and can_see_obj(player, obj)]
        conts = [obj for obj in rs["items"]
                 if item_tpl(obj).get("type") in _CONTAINER_TYPES
                 and can_see_obj(player, obj)]
        if not loose and not conts:
            chprintln(player, "There is nothing here to pick up.")
            return
        names = []
        for obj in loose:
            tpl = item_tpl(obj)
            names.append((isinstance(obj, dict) and obj.get("short_descr")) or tpl["short_descr"])
        has_all = len(loose) > 1
        if has_all:
            names.append("[all]")
        cont_start = len(names)
        for obj in conts:
            tpl = item_tpl(obj)
            names.append(
                ((isinstance(obj, dict) and obj.get("short_descr")) or tpl["short_descr"])
                + " {W[loot]{x")
        idx = pick_from("Pick up what?", names)
        if idx < 0:
            return
        if idx < len(loose):
            obj = loose[idx]
            tpl = item_tpl(obj)
            if not _check_carry_get(player, obj, tpl):
                return
            rs["items"].remove(obj)
            chprintln(player, "You get " + (
                (isinstance(obj, dict) and obj.get("short_descr")) or tpl["short_descr"]) + ".")
            if apply_money_pickup(player, obj, tpl):
                return
            player["inv"].append(obj)
            _get_triggers(player, obj)
            quest_obj_check(player, obj)  # cf. 1stMud get_obj quest hook
            return "get " + tpl.get("keywords", tpl["short_descr"]).split()[0]
        if has_all and idx == len(loose):
            for obj in list(loose):
                tpl = item_tpl(obj)
                if not _check_carry_get(player, obj, tpl):
                    continue
                rs["items"].remove(obj)
                chprintln(player, "You get " + (
                    (isinstance(obj, dict) and obj.get("short_descr")) or tpl["short_descr"]) + ".")
                if not apply_money_pickup(player, obj, tpl):
                    player["inv"].append(obj)
                    _get_triggers(player, obj)
                    quest_obj_check(player, obj)  # cf. 1stMud get_obj quest hook
            return "get all"
        return _loot_container_picker(player, conts[idx - cont_start])
    arg = " ".join(args)
    if arg == "all" or arg.startswith("all."):
        filter_kw = arg[4:] if arg.startswith("all.") else None
        found = False
        for obj in list(rs["items"]):
            tpl = item_tpl(obj)
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
            chprintln(player, "You get " + tpl["short_descr"] + ".")
            if not apply_money_pickup(player, obj, tpl):
                player["inv"].append(obj)
                _get_triggers(player, obj)
                quest_obj_check(player, obj)  # cf. 1stMud get_obj quest hook
        if not found:
            if filter_kw:
                chprintln(player, "I see no " + filter_kw + " here.")
            else:
                chprintln(player, "I see nothing here.")
        return
    if len(args) >= 2:
        cont_arg = " ".join(args[1:])
        cont_obj = get_obj_list(cont_arg, rs["items"], ITEM_DEFS, player)
        if cont_obj is None:
            cont_obj = get_obj_list(cont_arg, player["inv"], ITEM_DEFS, player)
        if (cont_obj is not None and isinstance(cont_obj, dict)
                and item_tpl(cont_obj).get("type") in _CONTAINER_TYPES):
            item_arg = args[0]
            cont_tpl = item_tpl(cont_obj)
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
                        ctpl = item_tpl(cobj)
                        if not can_see_obj(player, cobj):  # cf. 1stMud do_get all-from-container loop, act_obj.c:311
                            continue
                        if not _check_carry_get(player, cobj, ctpl, cont_carried):
                            continue
                        cont_obj["contents"].remove(cobj)
                        chprintln(player, "You get " + (cobj.get("short_descr") or ctpl["short_descr"]) + ".")
                        if not apply_money_pickup(player, cobj, ctpl):
                            player["inv"].append(cobj)
                            _get_triggers(player, cobj)
                            quest_obj_check(player, cobj)  # cf. 1stMud get_obj quest hook
                return
            cobj = get_obj_list(item_arg, contents, ITEM_DEFS, player)
            if cobj is None:
                chprintln(player, "I see nothing like that in the " + (
                    cont_obj.get("short_descr") or cont_tpl["short_descr"]) + ".")
                return
            ctpl = item_tpl(cobj)
            if not _check_carry_get(player, cobj, ctpl, cont_carried):
                return
            cont_obj["contents"].remove(cobj)
            chprintln(player, "You get " + (cobj.get("short_descr") or ctpl["short_descr"]) + ".")
            if not apply_money_pickup(player, cobj, ctpl):
                player["inv"].append(cobj)
                _get_triggers(player, cobj)
                quest_obj_check(player, cobj)  # cf. 1stMud get_obj quest hook
            return
    obj = get_obj_list(arg, rs["items"], ITEM_DEFS, player)
    if obj is None:
        chprintln(player, "I see no " + arg + " here.")
        return
    tpl = item_tpl(obj)
    if "take" not in item_wear_flags(obj, tpl):
        chprintln(player, "You can't take that.")
        return
    if not _check_carry_get(player, obj, tpl):
        return
    rs["items"].remove(obj)
    chprintln(player, "You get " + ((isinstance(obj, dict) and obj.get("short_descr")) or tpl["short_descr"]) + ".")
    if not apply_money_pickup(player, obj, tpl):
        player["inv"].append(obj)
        _get_triggers(player, obj)
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
        chprintln(player, "You don't have that much " + wallet + ".")
        return
    player[wallet] -= amount
    gold = 0 if silver else amount
    silver_amt = amount if silver else 0

    rs = world.rooms[player["room"]]
    for obj in list(rs["items"]):
        if not isinstance(obj, dict) or item_tpl(obj).get("type") != "money":
            continue
        rs["items"].remove(obj)
        tpl = item_tpl(obj)
        silver_amt += obj.get("silver", tpl.get("silver", 0))
        gold += obj.get("gold", tpl.get("gold", 0))

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
        names = [item_tpl(obj)["short_descr"] for obj in visible]
        if len(visible) > 1:
            names.append("[all]")
        idx = pick_from("Drop what?", names)
        if idx < 0:
            return
        if idx == len(visible):
            do_drop(player, ["all"])
            return
        obj = visible[idx]
        if not can_drop_obj(player, obj):
            chprintln(player, "You can't let go of it.")
            return
        tpl = item_tpl(obj)
        player["inv"].remove(obj)
        ritems = world.rooms[player["room"]]["items"]
        ritems.append(obj)
        chprintln(player, "You drop " + tpl["short_descr"] + ".")
        _drop_triggers(player, obj)
        # cf. act_obj.c:586 `if (obj && ...)`: a drop prog may have purged or
        # moved the obj -- melt only if it still lies here
        if obj in ritems and item_extra_flags(obj, tpl).get("melt_drop"):
            ritems.remove(obj)
            chprintln(player, tpl["short_descr"] + " dissolves into smoke.")
            return
        return "drop " + tpl.get("keywords", tpl["short_descr"]).split()[0]
    arg = " ".join(args)
    if arg == "all" or arg.startswith("all."):
        filter_kw = arg[4:] if arg.startswith("all.") else None
        found = False
        for obj in list(player["inv"]):
            tpl = item_tpl(obj)
            if filter_kw and not is_name(filter_kw, tpl.get("keywords", "")):
                continue
            if not can_see_obj(player, obj):  # cf. 1stMud do_drop all loop, act_obj.c:602
                continue
            if not can_drop_obj(player, obj):
                continue
            found = True
            player["inv"].remove(obj)
            ritems = world.rooms[player["room"]]["items"]
            ritems.append(obj)
            chprintln(player, "You drop " + tpl["short_descr"] + ".")
            _drop_triggers(player, obj)
            # cf. act_obj.c:616 `if (obj && ...)`: prog may have moved it
            if obj in ritems and item_extra_flags(obj, tpl).get("melt_drop"):
                ritems.remove(obj)
                chprintln(player, tpl["short_descr"] + " dissolves into smoke.")
        if not found:
            if filter_kw:
                chprintln(player, "You are not carrying any " + filter_kw + ".")
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
    tpl = item_tpl(obj)
    player["inv"].remove(obj)
    ritems = world.rooms[player["room"]]["items"]
    ritems.append(obj)
    chprintln(player, "You drop " + tpl["short_descr"] + ".")
    _drop_triggers(player, obj)
    # cf. act_obj.c:586 `if (obj && ...)`: prog may have moved it
    if obj in ritems and item_extra_flags(obj, tpl).get("melt_drop"):
        ritems.remove(obj)
        chprintln(player, tpl["short_descr"] + " dissolves into smoke.")


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
        chprintln(player, "I see no " + cont_arg + " here.")
        return
    cont_tpl = item_tpl(cont_obj)
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
    tpl = item_tpl(obj)
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
    chprintln(player, "You put " + tpl["short_descr"] + " in " + cont_name + ".")


def _give_target(ch, words):
    """Resolve a give recipient, including the player for mobprog actors. [PRIMESUD]"""
    target = " ".join(words)
    if ch.get("is_npc"):
        from mobprog import _get_char_room
        return _get_char_room(ch, target)
    rs = world.rooms[ch["room"]]
    vid = get_char_room(target, rs["mobs"], world.chars, ch)
    return world.chars.get(vid) if vid is not None else None


def _give_coins(player, amount, coin, rest, victim=None):
    """Coin branch of do_give (cf. 1stMud do_give money path in act_obj.c:655).

    Fires TRIG_BRIBE on the recipient (see below). [PRIMESUD] The changer's
    change comes straight from thin air like 1stMud's till top-up.
    """
    if amount <= 0 or coin not in ("coins", "coin", "gold", "silver"):
        chprintln(player, "Sorry, you can't do that.")
        return
    silver = coin != "gold"
    if victim is None:
        if not rest:
            chprintln(player, "Give what to whom?")
            return
        victim = _give_target(player, rest)
        if victim is None:
            chprintln(player, "They aren't here.")
            return
    wallet = "silver" if silver else "gold"
    if player[wallet] < amount:
        chprintln(player, "You haven't got that much.")
        return
    player[wallet] -= amount
    victim[wallet] = victim.get(wallet, 0) + amount
    act("$n gives you " + num_str(amount) + " " + wallet + ".", player, None, victim, TO_VICT)
    act("$n gives $N some coins.", player, None, victim, TO_NOTVICT)
    act("You give $N " + num_str(amount) + " " + wallet + ".", player, None, victim, TO_CHAR)

    # TRIG_BRIBE: amount normalised to silver (cf. p_bribe_trigger, act_obj.c:710)
    if victim.get("is_npc"):
        from mobprog import has_trigger, bribe_trigger  # deferred: keep mobprog off the boot path
        if has_trigger(victim, "bribe"):
            # [PRIMESUD] stash the payment for 'mob refund' (progs can't
            # see bribe amounts); original denomination so refunds match
            victim["mprog_bribe"] = (amount, wallet)
            bribe_trigger(victim, player, amount if silver else amount * 100)

    # Money changer (cf. 1stMud ACT_IS_CHANGER branch)
    if victim["act_flags"].get("changer"):
        change = (95 * amount // 100 // 100) if silver else (95 * amount)
        if change < 1 and can_see(victim, player):
            act("$n tells you 'I'm sorry, you did not give me enough to change.'",
                victim, None, player, TO_VICT)
            # 1stMud: changer gives the original amount back via do_give
            victim[wallet] -= amount
            player[wallet] += amount
            act("$n gives you " + num_str(amount) + " " + wallet + ".", victim, None, player, TO_VICT)
        elif can_see(victim, player):
            out = "gold" if silver else "silver"
            player[out] += change
            act("$n gives you " + num_str(change) + " " + out + ".", victim, None, player, TO_VICT)
            if silver:
                rem = 95 * amount // 100 - change * 100
                if rem > 0:
                    player["silver"] += rem
                    act("$n gives you " + num_str(rem) + " silver.", victim, None, player, TO_VICT)
            act("$n tells you 'Thank you, come again.'", victim, None, player, TO_VICT)


def do_give(player, args):
    """Give coins or an item to a character in the room (cf. 1stMud do_give in act_obj.c).

    Args:
        player (dict): Player state dict.
        args (list): [amount, coin-word, mob] for coins, or [item, mob];
            [PRIMESUD] picker shown if omitted.
    """
    obj = None
    victim = None
    if not args and not player.get("is_npc"):
        rs = world.rooms[player["room"]]
        victims = [world.chars[i] for i in rs["mobs"]
                   if can_see(player, world.chars[i])]
        if not victims:
            chprintln(player, "Give what to whom?")
            return

        giveables = []
        labels = []
        # str.capitalize is missing on-device; use literal labels
        for coin, cap in (("silver", "Silver"), ("gold", "Gold")):
            amount = player.get(coin, 0)
            if amount:
                giveables.append(coin)
                labels.append(cap + " coins (" + num_str(amount)
                              + " available)")
        for carried in player["inv"]:
            if can_see_obj(player, carried):
                giveables.append(carried)
                labels.append(carried.get("short_descr")
                              or item_tpl(carried)["short_descr"])
        if not giveables:
            chprintln(player, "You have nothing to give.")
            return

        idx = pick_from("Give what?", labels)
        if idx < 0:
            return
        picked = giveables[idx]
        amount = None
        if isinstance(picked, str):
            raw = terminal.tr.input("How many " + picked + " coins? ",
                                    alpha=False, default="1").strip()
            if not raw.isdigit():
                chprintln(player, "Sorry, you can't do that.")
                return
            amount = int(raw)

        idx = pick_from("Give to whom?",
                        [MOB_DEFS[v["tpl"]]["short_descr"] for v in victims])
        if idx < 0:
            return
        victim = victims[idx]
        if amount is not None:
            _give_coins(player, amount, picked, [], victim)
            return
        obj = picked
    else:
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
        victim = _give_target(player, args[1:])
        if victim is None:
            chprintln(player, "They aren't here.")
            return
    tpl = item_tpl(obj)

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
            chprintln(player, "{RReturn to " + _giver_name(player)
                     + " before your time runs out!{x")
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

    if victim.get("is_npc") and MOB_DEFS[victim["tpl"]].get("shop"):
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

    carried = victim["inv"] + [e for e in victim["equip"].values()
                               if e is not None]
    carry_n = sum(_obj_number(o) for o in carried)
    if carry_n + _obj_number(obj) > can_carry_n(victim):
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
    # TRIG_GIVE: obj then room react before the mob (cf. do_give,
    # act_obj.c:851-854); the room "give" pass is unreachable upstream (the
    # room trigger vocabulary lacks "give", so HasTriggerRoom is always
    # false) -- mirrored anyway
    if mobprog.has_otrigger(obj, "give"):
        mobprog.ogive_trigger(
            {"obj": obj, "room": player["room"], "carrier": victim},
            player, "give")
    if mobprog.has_rtrigger(player["room"], "give"):
        mobprog.rgive_trigger(player["room"], player, obj, "give")
    # [PRIMESUD] Player wallets absorb received money objects, matching pickup.
    if (not victim.get("is_npc") and obj in victim["inv"]
            and apply_money_pickup(victim, obj, tpl)):
        victim["inv"].remove(obj)
    # TRIG_GIVE: mob reacts to the received object (cf. do_give, act_obj.c:856)
    if victim.get("is_npc"):
        if mobprog.has_trigger(victim, "give"):
            mobprog.give_trigger(victim, player, obj)


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
    # [PRIMESUD] output accumulated and sent as one unjoined list --
    # batch-rendered by terminal.print_lines
    out = ["{YYou are carrying {W" + num_str(len(player["inv"])) + "/" + num_str(max_carry)
           + "{Y items:{x"]
    if not player["inv"]:
        chprintln(player, out)
        return
    counts = {}
    reps = {}   # vnum -> a representative instance, for item_tpl [PRIMESUD]
    for obj in player["inv"]:
        v = obj["vnum"]
        counts[v] = counts.get(v, 0) + 1
        reps[v] = obj
    # [PRIMESUD] obj vnum overlay under holylight (upstream imms use stat)
    show_vnums = "holylight" in DBG
    for v, n in counts.items():
        tpl = item_tpl(reps[v])
        flags = _obj_flags(tpl)
        name = tpl["short_descr"]
        # cf. 1stMud act_info.c:66 quest obj marker; [PRIMESUD] vnum match
        if is_quester(player) and v == player.get("quest_obj", 0):
            name = "{r[{RTARGET{r] {x" + name
        if show_vnums:  # [PRIMESUD]
            name += " {D[" + num_str(v) + "]{x"
        out.append("  " + flags + name + " x" + num_str(n) if n > 1 else "  " + flags + name)
    chprintln(player, out)


# [PRIMESUD] (prefix, suffix) pairs split around the item name -- avoids
# .format()/{}-placeholder use per the firmware string-format bug (pitfall 8)
_WEAR_MSG = {
    "light":    ("You light ", " and hold it."),
    "finger_l": ("You wear ", " on your left finger."),
    "finger_r": ("You wear ", " on your right finger."),
    "neck_1":   ("You wear ", " around your neck."),
    "neck_2":   ("You wear ", " around your neck."),
    "body":     ("You wear ", " on your torso."),
    "head":     ("You wear ", " on your head."),
    "legs":     ("You wear ", " on your legs."),
    "feet":     ("You wear ", " on your feet."),
    "hands":    ("You wear ", " on your hands."),
    "arms":     ("You wear ", " on your arms."),
    "shield":   ("You wear ", " as a shield."),
    "about":    ("You wear ", " about your torso."),
    "waist":    ("You wear ", " about your waist."),
    "wrist_l":  ("You wear ", " around your left wrist."),
    "wrist_r":  ("You wear ", " around your right wrist."),
    "wield":    ("You wield ", "."),
    "hold":     ("You hold ", " in your hand."),
    "float":    ("You release ", " and it floats next to you."),
}

_DUAL_SLOTS = {
    "finger": ("finger_l", "finger_r"),
    "neck":   ("neck_1",   "neck_2"),
    "wrist":  ("wrist_l",  "wrist_r"),
}

# [PRIMESUD] Balanced combat heuristic. Ten points equal one point of
# do_compare's old raw armor/double-average weapon scale.
_GEAR_MOD_WEIGHTS = {
    "str": 30, "dex": 30, "int": 20, "wis": 20, "con": 30,
    "hit": 1, "mana": 1, "move": 1,
    "hitroll": 10, "damroll": 20,
    # Base armor values are subtracted on equip, so positive protects.
    # APPLY_AC modifiers are added to all four buckets, so negative protects.
    "ac": -40,
    # saves_spell subtracts saving_throw, so negative modifiers protect.
    "saves": -20, "saving_rod": -20, "saving_petri": -20,
    "saving_breath": -20, "saving_spell": -20,
}

_GEAR_AFFECT_WEIGHTS = {
    "blind": -300,
    "haste": 200,
    "protect_evil": 80, "protect_good": 80,
    "flying": 50,
    "invisible": 40,
    "pass_door": 30,
    "dark_vision": 20, "detect_hidden": 20, "detect_invis": 20,
    "infrared": 10,
    "detect_evil": 5, "detect_good": 5, "detect_magic": 5,
}

_BEST_WEAR_FLAGS = (
    "light", "finger", "neck", "body", "head", "legs", "feet", "hands",
    "arms", "about", "waist", "wrist", "float",
)

# Hand slots are optimized together as one layout, not per-slot: see
# _best_hand_layout.
_HAND_FLAGS = ("wield", "secondary", "shield", "hold")


def _wear_flag(obj, tpl):
    """Return obj's wear command flag, or None. [PRIMESUD]"""
    if tpl.get("type") == "light":
        return "light"
    for flag in item_wear_flags(obj, tpl):
        if flag != "take":
            return flag
    return None


def _gear_affect_score(af):
    """Score one numeric/bitvector equipment affect. [PRIMESUD]"""
    score = _GEAR_MOD_WEIGHTS.get(af.get("location"), 0) * af.get("modifier", 0)
    bit = af.get("bitvector")
    if not bit:
        return score
    where = af.get("where", "to_affects")
    if where == "to_immune":
        return score + 300
    if where == "to_resist":
        return score + 100
    if where == "to_vuln":
        return score - 100
    if where == "to_affects":
        return score + _GEAR_AFFECT_WEIGHTS.get(bit, 0)
    return score


def _item_stat_modifier(obj, tpl, location):
    """Return one item's applied modifier for a location. [PRIMESUD]"""
    total = 0
    if not obj.get("enchanted"):
        total += tpl.get("stat_bonuses", {}).get(location, 0)
        for af in tpl_flag_affects(tpl):
            if af.get("location") == location:
                total += af.get("modifier", 0)
    for af in obj.get("affect_list", []):
        if af.get("location") == location:
            total += af.get("modifier", 0)
    return total


def gear_score_components(tpl, armor=None, dice=None, weapon_flags=None,
                          level=None, include_template_affects=True):
    """Return static score and player-specific weapon inputs. [PRIMESUD]

    Args:
        tpl (dict): Item template.
        armor (tuple): Optional runtime armor override.
        dice (tuple): Optional runtime weapon-dice override.
        weapon_flags (dict): Optional runtime weapon-flag override.
        level (int): Optional runtime item-level override.
        include_template_affects (bool): Include template stat/flag affects.

    Returns:
        tuple: static_score, weapon_base, weapon_type, sharp.
    """
    score = 0
    weapon_base = 0
    weapon_type = ""
    sharp = False
    itype = tpl.get("type")
    if itype == "armor":
        values = armor if armor is not None else tpl.get("armor")
        if values is not None:
            # 1stMud do_compare summed only 3 AC buckets; exotic included here.
            score += sum(values) * 10
    elif itype == "weapon":
        values = dice if dice is not None else tpl.get("dice", (0, 0, 0))
        weapon_base = values[0] * (values[1] + 1) + 2 * values[2]
        weapon_type = tpl.get("weapon_type", "")
        flags = weapon_flags if weapon_flags is not None else tpl.get("weapon_flags", {})
        item_level = tpl.get("level", 0) if level is None else level
        sharp = bool(flags.get("sharp"))
        if flags.get("flaming"):
            score += (item_level // 4 + 2) * 10
        if flags.get("frost"):
            score += (item_level // 6 + 3) * 10
        if flags.get("shocking"):
            score += (item_level // 5 + 3) * 10
        if flags.get("vampiric"):
            score += (item_level // 5 + 2) * 15
        if flags.get("poison"):
            score += 20

    if include_template_affects:
        for loc, mod in tpl.get("stat_bonuses", {}).items():
            score += _GEAR_MOD_WEIGHTS.get(loc, 0) * mod
        for af in tpl_flag_affects(tpl):
            score += _gear_affect_score(af)
    return score, weapon_base, weapon_type, sharp


def _weapon_score(weapon_base, sharp, skill):
    """Return weapon score at one effective skill value. [PRIMESUD]"""
    base_score = weapon_base * skill // 10
    if sharp:
        base_score += base_score * skill // 700
    # Expected-hit weighting: one_hit's THAC0 skill terms make relative hit
    # rates track (skill + 20) / 140 (sim-calibrated on save data), reaching
    # exactly 1 at adept (skill 120) so gear_score_weapon_max still bounds.
    return base_score * (skill + 20) // 140


def gear_score_weapon(player, weapon_base, weapon_type, sharp):
    """Return player-specific score for indexed weapon inputs. [PRIMESUD]"""
    if not weapon_base:
        return 0
    sn = WEAPON_GSN_MAP.get(weapon_type, -1)
    # one_hit uses 20 + weapon proficiency for damage and sharp chance.
    return _weapon_score(weapon_base, sharp, 20 + _get_weapon_skill(player, sn))


def shield_block_pct(player):
    """Equal-level shield block chance (cf. check_shield_block). [PRIMESUD]"""
    return get_skill(player, GSN_SHIELD_BLOCK) // 5 + 3


def _weapon_dice_part(player, obj):
    """Skill-scaled dice component of a weapon instance's score. [PRIMESUD]

    The part one_hit multiplies by 11/10 when no shield is worn; static
    affects and proc bonuses are excluded.
    """
    tpl = item_tpl(obj)
    _, weapon_base, weapon_type, sharp = gear_score_components(
        tpl,
        dice=obj.get("dice") or tpl.get("dice", (0, 0, 0)),
        weapon_flags=item_weapon_flags(obj, tpl),
        level=obj.get("level", tpl.get("level", 0)))
    return gear_score_weapon(player, weapon_base, weapon_type, sharp)


def gear_score_weapon_max(weapon_base, sharp):
    """Return gear_score_weapon at 100% proficiency: an upper bound. [PRIMESUD]

    gear.bin sorts each slot region by static_score + this bound,
    descending, so the recommend scan can stop a region once the bound
    cannot beat the owned baseline.
    """
    if not weapon_base:
        return 0
    return _weapon_score(weapon_base, sharp, 120)


def gear_score(player, obj):
    """Return balanced combat score for one wearable item. [PRIMESUD]

    Includes instance-scaled armor/dice, every applied numeric modifier,
    live character/resistance flags, and implemented weapon procs. Scores
    are intentionally heuristic; unknown or mechanically inert flags add 0.

    Args:
        player (dict): Player whose weapon skill supplies weapon context.
        obj (dict): Item instance.

    Returns:
        int: Higher is better.
    """
    tpl = item_tpl(obj)
    score, weapon_base, weapon_type, sharp = gear_score_components(
        tpl,
        armor=_item_armor_runtime(tpl, obj),
        dice=obj.get("dice") or tpl.get("dice", (0, 0, 0)),
        weapon_flags=item_weapon_flags(obj, tpl),
        level=obj.get("level", tpl.get("level", 0)),
        include_template_affects=not obj.get("enchanted"))
    score += gear_score_weapon(player, weapon_base, weapon_type, sharp)
    for af in obj.get("affect_list", []):
        score += _gear_affect_score(af)
    return score

# [PRIMESUD] (threshold, prefix, suffix) -- prefix/suffix split around the
# item name, avoiding .format()/{}-placeholder use (pitfall 8)
_WIELD_SKILL_MSG = (
    (100, "", " feels like a part of you!"),
    ( 85, "You feel quite confident with ", "."),
    ( 70, "You are skilled with ", "."),
    ( 50, "Your skill with ", " is adequate."),
    ( 25, "", " feels a little clumsy in your hands."),
    (  1, "You fumble and almost drop ", "."),
    (  0, "You don't even know which end is up on ", "."),
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
    tpl = item_tpl(obj)
    if item_extra_flags(obj, tpl).get("noremove"):
        chprintln(player, "You can't remove " + tpl["short_descr"] + ".")
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
    tpl = item_tpl(obj)
    if player["level"] < tpl.get("level", 1):
        chprintln(player, "You must be level " + num_str(tpl.get("level", 1)) + " to use this object.")
        return

    if tpl.get("type") == "light":
        if not remove_obj(player, "light", fReplace):
            return
        chprintln(player, _WEAR_MSG["light"][0] + tpl["short_descr"] + _WEAR_MSG["light"][1])
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
            wtpl = item_tpl(wobj)
            if (_get_size(player) < SIZE_RANK["large"]
                    and item_weapon_flags(wobj, wtpl).get("two_hands")):
                chprintln(player, "Your hands are tied up with your weapon!")
                return

    chprintln(player, _WEAR_MSG[slot][0] + tpl["short_descr"] + _WEAR_MSG[slot][1])
    if _zap_anti_align(player, obj, tpl):
        return
    equip_char(player, obj, slot)

    if slot == "wield":
        sn = WEAPON_GSN_MAP.get(tpl.get("weapon_type", ""), -1)
        skill = _get_weapon_skill(player, sn)
        pre, suf = _WIELD_SKILL_MSG[-1][1], _WIELD_SKILL_MSG[-1][2]
        for threshold, p, s in _WIELD_SKILL_MSG[:-1]:
            if skill > threshold:
                pre, suf = p, s
                break
        chprintln(player, pre + tpl["short_descr"] + suf)


def _strength_after_swap(player, removed, added=()):
    """Return STR after removing and adding items. [PRIMESUD]"""
    delta = 0
    for obj in removed:
        delta -= _item_stat_modifier(obj, item_tpl(obj), "str")
    for obj in added:
        delta += _item_stat_modifier(obj, item_tpl(obj), "str")
    if not delta:
        return get_curr_stat(player, "str")
    mods = player["mod_stat"]
    old = mods.get("str", 0)
    mods["str"] = old + delta
    try:
        return get_curr_stat(player, "str")
    finally:
        if old:
            mods["str"] = old
        else:
            mods.pop("str", None)


def _wield_holds_after_swap(player, removed, added=()):
    """Return whether current weapon survives an item swap. [PRIMESUD]"""
    wield = player["equip"].get("wield")
    if wield is None or any(wield is obj for obj in removed):
        return True
    tpl = item_tpl(wield)
    return (tpl.get("weight", 0)
            <= STR_APP_WIELD[_strength_after_swap(
                player, removed, added)] * 10)


def gear_flags_legal(player, extra):
    """Return whether anti-alignment flags permit player use. [PRIMESUD]"""
    return not ((extra.get("anti_evil") and is_evil(player))
                or (extra.get("anti_good") and is_good(player))
                or (extra.get("anti_neutral") and is_neutral(player)))


def _can_wear_best(player, obj, tpl):
    """Return whether wear best may equip obj (sight/level/align). [PRIMESUD]

    No proficiency filter: the expected-hit weighting in _weapon_score
    already sinks unlearnt weapons to their true combat worth.
    """
    if (not can_see_obj(player, obj)
            or tpl.get("level", 1) > player["level"]):
        return False
    return gear_flags_legal(player, item_extra_flags(obj, tpl))


def _best_wear_candidate(player, flag):
    """Return highest-scoring eligible inventory item for flag. [PRIMESUD]"""
    best = None
    best_score = 0
    for obj in player["inv"]:
        tpl = item_tpl(obj)
        if (_wear_flag(obj, tpl) != flag
                or not _can_wear_best(player, obj, tpl)):
            continue
        score = gear_score(player, obj)
        if score > best_score:
            best = obj
            best_score = score
    return best, best_score


def _noremove_worn(obj):
    """Return whether a worn item refuses removal. [PRIMESUD]"""
    return item_extra_flags(obj, item_tpl(obj)).get("noremove")


def _best_hand_layout(player):
    """Re-arrange hand slots into the best-scoring legal layout. [PRIMESUD]

    Enumerates wield/secondary/shield/hold combinations under the existing
    equip rules (noremove locks, small-size two-hands vs shield, secondary
    excludes shield and held item, do_second weight rules, STR wield limit
    evaluated after the whole swap) and applies the layout with the highest
    combined gear score if it strictly beats the current hands.

    Returns:
        bool: True if any hand slot changed.
    """
    equip = player["equip"]
    current = {f: equip.get(f) for f in _HAND_FLAGS}
    locked = {f: current[f] is not None and _noremove_worn(current[f])
              for f in _HAND_FLAGS}
    small = _get_size(player) < SIZE_RANK["large"]

    # Score each item once; enumeration below revisits items many times.
    scores = {}
    dice_parts = {}

    def pool(flag, worn):
        out = []
        for obj in worn:
            if obj is not None:
                scores[id(obj)] = gear_score(player, obj)
                out.append((scores[id(obj)], obj))
        for obj in player["inv"]:
            tpl = item_tpl(obj)
            if _wear_flag(obj, tpl) == flag and _can_wear_best(player, obj, tpl):
                scores[id(obj)] = gear_score(player, obj)
                out.append((scores[id(obj)], obj))
        if flag == "wield":
            for _score, obj in out:
                dice_parts[id(obj)] = _weapon_dice_part(player, obj)
        return out

    weapons = pool("wield", (current["wield"], current["secondary"]))
    shields = pool("shield", (current["shield"],))
    holds = pool("hold", (current["hold"],))
    best_shield = None
    for score, obj in shields:
        if best_shield is None or score > best_shield[0]:
            best_shield = (score, obj)
    best_hold = None
    for score, obj in holds:
        if best_hold is None or score > best_hold[0]:
            best_hold = (score, obj)

    sb_pct = shield_block_pct(player)

    def layout_value(primary, secondary, shield, hold):
        """Combat-weighted layout worth: offense full, defence halved."""
        total = 0
        for o in (primary, secondary):
            if o is not None:
                total += scores[id(o)]
                if shield is None:
                    # one_hit: shieldless swings deal dice damage * 11 // 10
                    total += dice_parts.get(id(o), 0) // 10
        if hold is not None:
            total += scores[id(hold)]
        if shield is not None:
            # check_shield_block negates sb_pct% of incoming melee at equal
            # level; incoming tier approximated by the primary's own score.
            block = (scores[id(primary)] if primary is not None else 0) \
                * sb_pct // 100
            # ponytail: defence at half weight -- surviving loses to taking
            # the mob down; retune the divisor if shields feel mispriced.
            total += (scores[id(shield)] + block) // 2
        return total

    def try_layout(primary, secondary, shield, hold):
        """Return (score, layout dict) if the combination is legal."""
        if ((locked["wield"] and primary is not current["wield"])
                or (locked["secondary"] and secondary is not current["secondary"])
                or (locked["shield"] and shield is not current["shield"])
                or (locked["hold"] and hold is not current["hold"])):
            return None
        if secondary is not None:
            # cf. do_second: needs a primary, excludes shield and held item.
            if (primary is None or primary is secondary
                    or shield is not None or hold is not None):
                return None
        if primary is not None:
            ptpl = item_tpl(primary)
            if (small and shield is not None
                    and item_weapon_flags(primary, ptpl).get("two_hands")):
                return None
        layout = {"wield": primary, "secondary": secondary,
                  "shield": shield, "hold": hold}
        kept = [o for o in layout.values() if o is not None]
        removed = [o for o in current.values()
                   if o is not None and not any(o is k for k in kept)]
        added = [o for o in kept
                 if not any(o is c for c in current.values())]
        # A secondary cannot exist without the primary already wielded
        # (do_second), so its stat mods may not prop up either weight
        # check: evaluate STR as of the moment the primary goes on.
        limit = STR_APP_WIELD[_strength_after_swap(
            player, removed, [o for o in added if o is not secondary])]
        if primary is not None:
            pw = item_tpl(primary).get("weight", 0)
            if pw > limit * 10:
                return None
            if secondary is not None:
                sw = item_tpl(secondary).get("weight", 0)
                # cf. do_second weight rules
                if sw > limit // 2 or sw * 2 > pw:
                    return None
        return layout_value(primary, secondary, shield, hold), layout

    base = layout_value(current["wield"], current["secondary"],
                        current["shield"], current["hold"])

    # ponytail: best shield/hold chosen by score alone; a worse shield whose
    # STR bonus enables a heavier weapon is not explored.
    best = None
    best_score = base
    shield_opts = (None, best_shield and best_shield[1])
    hold_opts = (None, best_hold and best_hold[1])
    for primary in [None] + [o for _s, o in weapons]:
        for shield in shield_opts:
            for hold in hold_opts:
                for secondary in [None] + [o for _s, o in weapons]:
                    opt = try_layout(primary, secondary, shield, hold)
                    if opt is not None and opt[0] > best_score:
                        best_score, best = opt
    if best is None:
        return False

    # affect_modify floor-drops a too-heavy wield the moment STR dips, and
    # removals run before adds. If a kept wield cannot survive the interim
    # dip, park it in inventory across the swap; the equip phase re-wears
    # it at post-add STR (shield/hold go on first).
    removing = [current[f] for f in _HAND_FLAGS
                if current[f] is not None and best[f] is not current[f]]
    if (best["wield"] is not None and best["wield"] is current["wield"]
            and not _wield_holds_after_swap(player, removing)):
        if not remove_obj(player, "wield", True):
            return False

    def bail(changed):
        """Re-wield the old primary so a failed apply never leaves the
        player weaponless; all other items are already back in inventory.
        try_layout mirrors every wear_obj check, so this should be
        unreachable."""
        old = current["wield"]
        if (equip.get("wield") is None and old is not None
                and any(o is old for o in player["inv"])):
            wear_obj(player, old, False)
            if equip.get("wield") is old:
                changed = True
        return changed

    for flag in _HAND_FLAGS:
        cur = current[flag]
        if cur is not None and best[flag] is not cur:
            if not remove_obj(player, flag, True):
                return bail(False)
    changed = False
    # Shield/hold first so their STR bonuses count for the wield check in
    # wear_obj; layout legality already excludes hand conflicts.
    for flag in ("shield", "hold", "wield"):
        obj = best[flag]
        if obj is not None and equip.get(flag) is not obj:
            wear_obj(player, obj, False)
            if equip.get(flag) is not obj:
                return bail(changed)
            changed = True
    obj = best["secondary"]
    if obj is not None and equip.get("secondary") is not obj:
        # cf. do_second equip tail; align already filtered by _can_wear_best.
        tpl = item_tpl(obj)
        chprintln(player, "You wield " + tpl["short_descr"] + " in your off-hand.")
        equip_char(player, obj, "secondary")
        changed = True
    return changed


def _wear_best(player):
    """Equip strictly better inventory gear by wear slot. [PRIMESUD]"""
    changed = False
    for flag in _BEST_WEAR_FLAGS:
        slots = _DUAL_SLOTS.get(flag, (flag,))
        while True:
            candidate, candidate_score = _best_wear_candidate(player, flag)
            if candidate is None:
                break

            target = None
            target_score = 0
            for slot in slots:
                worn = player["equip"].get(slot)
                if worn is None:
                    if not _wield_holds_after_swap(player, (), (candidate,)):
                        continue
                    target = slot
                    target_score = 0
                    break
                if _noremove_worn(worn):
                    continue
                if not _wield_holds_after_swap(player, (worn,), (candidate,)):
                    continue
                score = gear_score(player, worn)
                if target is None or score < target_score:
                    target = slot
                    target_score = score
            if target is None or candidate_score <= target_score:
                break

            outgoing = player["equip"].get(target)
            if outgoing is not None:
                # Removing +STR gear can interim-dip below the wield's
                # weight, and affect_modify floor-drops it on the spot.
                # Park the wield; _best_hand_layout re-equips it after.
                if (not _wield_holds_after_swap(player, (outgoing,))
                        and not remove_obj(player, "wield", True)):
                    break
                if not remove_obj(player, target, True):
                    break
            wear_obj(player, candidate, False)
            # Identity check: `in` compares dicts by equality, and duplicate
            # items (same vnum, fresh instances) are equal dicts.
            if any(o is candidate for o in player["inv"]):
                break
            changed = True
            if flag not in _DUAL_SLOTS:
                break
    # Hands last, so STR from freshly worn gear counts toward wield limits.
    if _best_hand_layout(player):
        changed = True
    if not changed:
        chprintln(player, "You are already wearing your best gear.")


def do_wear(player, args):
    """Equip an item from inventory, or wear all wearable items (cf. 1stMud do_wear in act_obj.c).

    Args:
        player (dict): Player state dict.
        args (list): Parsed command arguments; first token may be "all", or
            "best" for the [PRIMESUD] strict-upgrade sweep.

    Returns:
        str or None: [PRIMESUD] For picker-resolved calls, the equivalent typed
            command, so game_loop records the action rather than bare "wear"
            in command history. None when nothing was resolved.
    """
    if not args:
        equippable = []
        for obj in player["inv"]:
            if not can_see_obj(player, obj):  # cf. 1stMud get_obj_carry can_see_obj gate
                continue
            tpl = item_tpl(obj)
            slot = _wear_flag(obj, tpl)
            if slot is not None and (slot in player["equip"] or slot in _DUAL_SLOTS):
                equippable.append((obj, tpl, slot))
        if not equippable:
            chprintln(player, "You have nothing wearable.")
            return
        names = [tpl["short_descr"] for _, tpl, _ in equippable]
        # [PRIMESUD] bracketed bulk entries; guard each pick on the same
        # condition that appended it -- with one equippable item no "[all]" is
        # offered and len(equippable) collides with best_idx, so a positional
        # `idx == len(equippable)` test alone would depend on branch order.
        if len(equippable) > 1:
            names.append("[all]")
        best_idx = len(names)
        names.append("[best] (Equip strongest gear)")
        idx = pick_from("Wear what?", names)
        if idx < 0:
            return
        if idx == best_idx:
            _wear_best(player)
            return "wear best"
        if len(equippable) > 1 and idx == len(equippable):
            for obj, _, _ in list(equippable):
                wear_obj(player, obj, False)
            return "wear all"
        obj, tpl, slot = equippable[idx]
        wear_obj(player, obj, True)
        return "wear " + tpl.get("keywords", tpl["short_descr"]).split()[0]
    if args[0] == "best":  # [PRIMESUD] gear-score strict-upgrade sweep
        _wear_best(player)
        return
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
        names = [item_tpl(obj)["short_descr"] for _, obj in worn]
        if len(worn) > 1:
            names.append("[all]")
        idx = pick_from("Remove what?", names)
        if idx < 0:
            return
        if idx == len(worn):
            for slot, obj in list(worn):
                remove_obj(player, slot, True)
            return
        slot, obj = worn[idx]
        remove_obj(player, slot, True)
        return "remove " + item_tpl(obj).get("keywords", item_tpl(obj)["short_descr"]).split()[0]
    if args[0] == "all":
        for slot, obj in list(player["equip"].items()):
            if obj is not None and can_see_obj(player, obj):  # cf. 1stMud do_remove all loop, act_obj.c:1763
                remove_obj(player, slot, True)
        return
    target = " ".join(args)
    # cf. 1stMud get_obj_wear (handler.c:2052) -- worn lookup gates on can_see_obj
    for slot, obj in player["equip"].items():
        if (obj is not None and can_see_obj(player, obj)
                and is_name(target, item_tpl(obj).get("keywords", ""))):
            remove_obj(player, slot, True)
            return
    chprintln(player, "You do not have that item.")


def do_equipment(player, args):
    """List all equipment slots and what is worn in each (cf. 1stMud do_equipment in act_info.c).

    Args:
        player (dict): Player state dict.
        args (list): Parsed command arguments (unused).
    """
    # [PRIMESUD] output accumulated and sent as one unjoined list --
    # batch-rendered by terminal.print_lines
    out = ["You are wearing:"]
    # [PRIMESUD] obj vnum overlay under holylight (upstream imms use stat)
    show_vnums = "holylight" in DBG
    for slot, label in WEAR_LABELS:
        obj = player["equip"].get(slot)
        if obj is not None:
            tpl = item_tpl(obj)
            line = label + _obj_flags(tpl) + "{Y" + tpl["short_descr"] + "{x"
            if show_vnums:  # [PRIMESUD]
                line += " {D[" + num_str(obj["vnum"]) + "]{x"
            out.append(line)
        else:
            out.append(label + "nothing")
    chprintln(player, out)


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
        player["affected_by"].pop("sneak", None)

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
        # [PRIMESUD] Bare "gold"/"silver", no "coins" -- 1stMud's unconditional
        # plural prints "1 gold coins". Matches do_sell/do_value in shop.py.
        if silver <= 0:
            chprintln(player, "Bingo!  You got " + num_str(gold) + " gold.")
        elif gold <= 0:
            chprintln(player, "Bingo!  You got " + num_str(silver) + " silver.")
        else:
            chprintln(player, "Bingo!  You got " + num_str(silver) + " silver and "
                      + num_str(gold) + " gold.")
        check_improve(player, GSN_STEAL, True, 2)
        return

    # cf. 1stMud act_obj.c:2324 -- thief is the viewer, not the victim
    obj = get_obj_list(what, victim["inv"], ITEM_DEFS, player)
    if obj is None:
        chprintln(player, "You can't find it.")
        return

    tpl = item_tpl(obj)
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
    """Compare compatible carried equipment by gear score. [PRIMESUD]

    With one arg: compares against worn gear sharing its wear slot. With two
    args: compares two named items sharing a wear slot.

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
    tpl1 = item_tpl(obj1)

    if len(args) < 2:
        obj2 = None
        obj2_score = None
        flag1 = _wear_flag(obj1, tpl1)
        if flag1 is not None:
            for o in player["equip"].values():
                if o is None:
                    continue
                tpl = item_tpl(o)
                if (_wear_flag(o, tpl) == flag1
                        and not item_extra_flags(o, tpl).get("noremove")):
                    score = gear_score(player, o)
                    if obj2_score is None or score < obj2_score:
                        obj2_score = score
                        obj2 = o
        if obj2 is None:
            chprintln(player, "You aren't wearing anything comparable.")
            return
    else:
        obj2 = get_obj_list(args[1], carried, ITEM_DEFS, player)
        if obj2 is None:
            chprintln(player, "You do not have that item.")
            return
    tpl2 = item_tpl(obj2)

    if obj1 is obj2:
        score = int_str(gear_score(player, obj1))
        act("You compare $p to itself.  Its gear score is " + score + ".",
            player, obj1, obj2)
        return
    if (_wear_flag(obj1, tpl1) is None
            or _wear_flag(obj1, tpl1) != _wear_flag(obj2, tpl2)):
        act("You can't compare $p and $P.", player, obj1, obj2)
        return

    value1 = gear_score(player, obj1)
    value2 = gear_score(player, obj2)
    score1 = int_str(value1)
    score2 = int_str(value2)
    if value1 == value2:
        msg = "$p [" + score1 + "] and $P [" + score2 + "] look about the same."
    elif value1 > value2:
        msg = "$p [" + score1 + "] looks better than $P [" + score2 + "]."
    else:
        msg = "$p [" + score1 + "] looks worse than $P [" + score2 + "]."
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
    tpl = item_tpl(obj)
    if player["level"] < tpl.get("level", 1):
        chprintln(player, "You must be level " + num_str(tpl.get("level", 1)) + " to use this object.")
        return
    if player["equip"].get("wield") is None:
        chprintln(player, "You need to wield a primary weapon, before using a secondary one!")
        return
    wield_limit = STR_APP_WIELD[get_curr_stat(player, "str")]
    if tpl.get("weight", 0) > wield_limit // 2:
        chprintln(player, "This weapon is too heavy to be used as a secondary weapon by you.")
        return
    primary_tpl = item_tpl(player["equip"]["wield"])
    if tpl.get("weight", 0) * 2 > primary_tpl.get("weight", 0):
        chprintln(player, "Your secondary weapon has to be considerably lighter than the primary one.")
        return
    if not remove_obj(player, "secondary", True):
        return
    chprintln(player, "You wield " + tpl["short_descr"] + " in your off-hand.")
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
    tpl = item_tpl(obj)
    if _item_type(obj, tpl) != "potion":
        chprintln(player, "You can quaff only potions.")
        return
    if player["level"] < tpl.get("level", 1):
        chprintln(player, "This liquid is too powerful for you to drink.")
        return
    if validate_item_spell_payload(obj) is None:
        return
    chprintln(player, "You quaff " + tpl["short_descr"] + ".")
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
    tpl = item_tpl(obj)
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
    tpl = item_tpl(obj)
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
        if item_tpl(obj).get("type") == "fountain":
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
    tpl = item_tpl(obj)
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
    tpl = item_tpl(obj)
    if tpl.get("type") != "drink":
        chprintln(player, "You can't fill that.")
        return
    ftpl = item_tpl(fountain)
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
    act("You fill $p with " + fliq + " from $P.", player, obj, fountain, TO_CHAR)
    act("$n fills $p with " + fliq + " from $P.", player, obj, fountain, TO_ROOM)
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
    tpl = item_tpl(out)
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
        act("You invert $p, spilling " + liq + " all over the ground.",
            player, out, None, TO_CHAR)
        act("$n inverts $p, spilling " + liq + " all over the ground.",
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
    dtpl = item_tpl(dest)
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
    act("You pour " + liq + " from $p into $P.", player, out, dest, TO_CHAR)
    act("$n pours " + liq + " from $p into $P.", player, out, dest, TO_ROOM)


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
    tpl = item_tpl(scroll)
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
    chprintln(player, "You recite " + tpl["short_descr"] + ".")
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
    tpl = item_tpl(staff)
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
        chprintln(player, "You brandish " + tpl["short_descr"] + ".")
        if player["level"] < tpl.get("level", 1) or randint(1, 100) >= 20 + get_skill(player, GSN_STAVES) * 4 // 5:
            chprintln(player, "You fail to invoke " + tpl["short_descr"] + ".")
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
        chprintln(player, "Your " + tpl["short_descr"] + " blazes bright and is gone.")
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
    tpl = item_tpl(wand)
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
            chprintln(player, "You zap " + item_tpl(obj)["short_descr"] + " with " + tpl["short_descr"] + ".")
        if player["level"] < tpl.get("level", 1) or randint(1, 100) >= 20 + get_skill(player, GSN_WANDS) * 4 // 5:
            chprintln(player, "Your efforts with " + tpl["short_descr"] + " produce only smoke and sparks.")
            check_improve(player, GSN_WANDS, False, 2)
        else:
            cast_item_spells(player, wand, victim, obj)
            check_improve(player, GSN_WANDS, True, 2)
    wand["charges"] = wand.get("charges", tpl.get("charges", tpl.get("max_charges", 0))) - 1
    if wand["charges"] <= 0:
        chprintln(player, "Your " + tpl["short_descr"] + " explodes into fragments.")
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
    if not (wobj and item_tpl(wobj).get("weapon_flags", {}).get("two_hands")):
        _equip("shield", OBJ_VNUM_SCHOOL_SHIELD)

    chprintln(player, "You have been equipped by the gods.")


def _sacrifice_one(player, obj, rs):
    """Sacrifice a single room item for silver (inner helper for do_sacrifice). [PRIMESUD]

    Args:
        player (dict): Player state dict.
        obj: Item instance dict from rs["items"].
        rs (dict): Current room state dict.
    """
    tpl = item_tpl(obj)

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
        chprintln(player, "Your deity gives you " + num_str(silver) + " silver coins for your sacrifice.")

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
