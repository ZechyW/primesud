"""Magic command handling and spell dispatch (cf. 1stMud magic.c)."""

from world import SKILLS, SKILL_TABLE, ITEM_TEMPLATES
from picker import pick_from
from combat import WaitState, check_improve, get_skill, set_fighting
from item import get_char_room, get_obj_list
from actor import is_name
from skill_utils import can_use_skill_spell, find_skill_spell, spell_mana

from urandom import randint


TARGET_NONE = "none"
TARGET_CHAR = "char"
TARGET_OBJ = "obj"
TARGET_ROOM = "room"

_POS_ORDER = {
    "dead": 0, "sleeping": 4, "resting": 5,
    "sitting": 6, "fighting": 7, "standing": 8,
}


def spell_null(tr, sn, level, ch, vo, target, world):
    """Do nothing spell placeholder (cf. 1stMud spell_null in magic.c)."""
    return False


def spell_cure_light(tr, sn, level, ch, vo, target, world):
    """Cure light wounds (cf. 1stMud spell_cure_light in magic.c)."""
    victim = vo if target == TARGET_CHAR else ch
    heal = randint(1, 8) + level // 3
    victim["hp"] = min(victim["hp_max"], victim["hp"] + heal)
    tr.print("You feel better!")
    if victim is not ch:
        tr.print("Ok.")
    return True


SPELL_FUNS = {
    "spell_cure_light": spell_cure_light,
}


def _implemented_spell(sn):
    sk = SKILLS.get(sn)
    if sk is None:
        return False
    return sk.get("spell_fun", "spell_null") in SPELL_FUNS


def _known_runtime_spells(player):
    learned = player.get("learned", {})
    rows = []
    for sn, sk in SKILL_TABLE:
        if _implemented_spell(sn) and learned.get(sn, 0) > 0 and can_use_skill_spell(player, sn):
            rows.append((sn, sk))
    return rows


def _is_self_name(player, target_name):
    if not target_name:
        return False
    pname = player.get("name", "")
    return target_name == "self" or (pname and is_name(target_name, pname))


def _room_state(player, world):
    return world["rooms"][player["room"]]


def _find_room_char(player, world, target_name):
    if _is_self_name(player, target_name):
        return player
    rs = _room_state(player, world)
    mob_id = get_char_room(target_name, rs["mobs"], world["mobs"])
    if mob_id is None:
        return None
    return world["mobs"][mob_id]


def _find_room_char_id(player, world, target_name):
    rs = _room_state(player, world)
    return get_char_room(target_name, rs["mobs"], world["mobs"])


def _find_inv_obj(player, target_name):
    return get_obj_list(target_name, player["inv"], ITEM_TEMPLATES)


def _find_room_obj(player, world, target_name):
    rs = _room_state(player, world)
    return get_obj_list(target_name, rs["items"], ITEM_TEMPLATES)


def _resolve_target(tr, player, sn, target_name, world):
    """Resolve spell target (cf. 1stMud do_cast target switch in magic.c)."""
    sk = SKILLS[sn]
    target_type = sk.get("target", "ignore")
    arg2 = target_name.split()[0] if target_name else ""

    if target_type == "ignore":
        return (None, TARGET_NONE, None, True)

    if target_type == "char_offensive":
        victim_id = None
        if not arg2:
            victim_id = player.get("fighting")
            if victim_id is None:
                tr.print("Cast the spell on whom?")
                return (None, TARGET_NONE, None, False)
        else:
            victim_id = _find_room_char_id(player, world, target_name)
            if victim_id is None:
                tr.print("They aren't here.")
                return (None, TARGET_NONE, None, False)
        return (world["mobs"][victim_id], TARGET_CHAR, victim_id, True)

    if target_type == "char_defensive":
        if not arg2:
            return (player, TARGET_CHAR, None, True)
        victim = _find_room_char(player, world, target_name)
        if victim is None:
            tr.print("They aren't here.")
            return (None, TARGET_NONE, None, False)
        return (victim, TARGET_CHAR, None, True)

    if target_type == "char_self":
        if arg2 and not _is_self_name(player, target_name):
            tr.print("You cannot cast this spell on another.")
            return (None, TARGET_NONE, None, False)
        return (player, TARGET_CHAR, None, True)

    if target_type == "obj_inventory":
        if not arg2:
            tr.print("What should the spell be cast upon?")
            return (None, TARGET_NONE, None, False)
        obj = _find_inv_obj(player, target_name)
        if obj is None:
            tr.print("You are not carrying that.")
            return (None, TARGET_NONE, None, False)
        return (obj, TARGET_OBJ, None, True)

    if target_type == "obj_char_offensive":
        victim_id = None
        if not arg2:
            victim_id = player.get("fighting")
            if victim_id is None:
                tr.print("Cast the spell on whom or what?")
                return (None, TARGET_NONE, None, False)
            return (world["mobs"][victim_id], TARGET_CHAR, victim_id, True)
        victim_id = _find_room_char_id(player, world, target_name)
        if victim_id is not None:
            return (world["mobs"][victim_id], TARGET_CHAR, victim_id, True)
        obj = _find_room_obj(player, world, target_name)
        if obj is not None:
            return (obj, TARGET_OBJ, None, True)
        tr.print("You don't see that here.")
        return (None, TARGET_NONE, None, False)

    if target_type == "obj_char_defensive":
        if not arg2:
            return (player, TARGET_CHAR, None, True)
        victim = _find_room_char(player, world, target_name)
        if victim is not None:
            return (victim, TARGET_CHAR, None, True)
        obj = _find_inv_obj(player, target_name)
        if obj is not None:
            return (obj, TARGET_OBJ, None, True)
        tr.print("You don't see that here.")
        return (None, TARGET_NONE, None, False)

    return (None, TARGET_NONE, None, False)


def _spell_level(player, sn):
    """Return cast level for classless PrimeSUD (cf. 1stMud do_cast in magic.c)."""
    return player.get("level", 1)  # [PRIMESUD] no class system or has_spells() penalty.


def do_cast(tr, player, args, world):
    """Cast a spell through 1stMud-style command flow (cf. 1stMud do_cast in magic.c)."""
    if player.get("wait", 0) > 0:
        tr.print("You are still recovering.")
        return None

    if not args:
        known = _known_runtime_spells(player)
        if not known:
            tr.print("You know no spells.")
            return None
        names = [sk["name"] for _, sk in known]
        idx = pick_from(tr, "Cast which spell?", names)  # [PRIMESUD] calculator UX extension.
        if idx < 0:
            return None
        sn = known[idx][0]
        target_name = ""
    else:
        sn = find_skill_spell(player, args[0])
        target_name = " ".join(args[1:])

    if (sn is None or not _implemented_spell(sn)
            or not can_use_skill_spell(player, sn)
            or player.get("learned", {}).get(sn, 0) == 0):
        tr.print("You don't know any spells of that name.")
        return None

    sk = SKILLS[sn]
    if _POS_ORDER.get(player.get("pos", "standing"), 8) < _POS_ORDER.get(sk.get("min_pos", "standing"), 8):
        tr.print("You can't concentrate enough.")
        return None

    vo, target, victim_id, ok = _resolve_target(tr, player, sn, target_name, world)
    if not ok:
        return None

    mana = spell_mana(player, sn)
    if player["mp"] < mana:
        tr.print("You don't have enough mana.")
        return None

    WaitState(player, sk.get("beats", 0))

    if randint(1, 100) > get_skill(player, sn):
        tr.print("You lost your concentration.")
        check_improve(tr, player, sn, False, 1)
        player["mp"] -= mana // 2
        return None

    player["mp"] -= mana
    fun = SPELL_FUNS.get(sk.get("spell_fun", "spell_null"), spell_null)
    ret = fun(tr, sn, _spell_level(player, sn), player, vo, target, world)
    check_improve(tr, player, sn, ret, 1)

    if (ret and sk.get("target") in ("char_offensive", "obj_char_offensive")
            and target == TARGET_CHAR and victim_id is not None
            and player.get("fighting") is None):
        set_fighting(tr, player, victim_id, world["mobs"])
    return None
