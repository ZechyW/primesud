"""Magic command handling and spell dispatch (cf. 1stMud magic.c)."""

from world import SKILLS, SKILL_TABLE, ITEM_TEMPLATES, MOB_TEMPLATES
from picker import pick_from
from combat import (WaitState, check_improve, get_skill, set_fighting,
                    raw_kill, _advance_target, _damage_verb, _damage_punct)
from item import get_char_room, get_obj_list
from actor import is_name, is_affected, affect_to_char
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


def _dice(num, size):
    total = 0
    for _ in range(num):
        total += randint(1, size)
    return total


def _heal_char(tr, ch, victim, amount, msg):
    victim["hp"] = min(victim["hp_max"], victim["hp"] + amount)
    tr.print(msg)
    if victim is not ch:
        tr.print("Ok.")
    return True


def _target_id(ch, victim, world):
    if victim is None or victim is ch:
        return None
    for mob_id, inst in world["mobs"].items():
        if inst is victim:
            return mob_id
    return None


def _damage_char(tr, ch, victim, victim_id, dam, sn, world):
    """Apply spell damage to a mob and route death through combat kill flow."""
    if dam < 0:
        dam = 0
    victim["hp"] = max(0, victim["hp"] - dam)
    sk = SKILLS[sn]
    noun = sk.get("noun_damage") or sk["name"]
    _vs, vp = _damage_verb(dam)
    punct = _damage_punct(dam)
    name = MOB_TEMPLATES[victim["tpl"]]["short_descr"]
    tr.print("{GYour %s %s {G%s%s {W[{R%d{W]{x" % (noun, vp, name, punct, dam))
    if victim["hp"] == 0 and victim_id is not None and victim_id in world["mobs"]:
        raw_kill(tr, ch, victim_id, victim, MOB_TEMPLATES[victim["tpl"]], world)
        _advance_target(ch, world["mobs"], world["rooms"])
    return True


def spell_cure_light(tr, sn, level, ch, vo, target, world):
    """Cure light wounds (cf. 1stMud spell_cure_light in magic.c)."""
    return _heal_char(tr, ch, vo, _dice(1, 8) + level // 3, "You feel better!")


def spell_cure_serious(tr, sn, level, ch, vo, target, world):
    """Cure serious wounds (cf. 1stMud spell_cure_serious in magic.c)."""
    return _heal_char(tr, ch, vo, _dice(2, 8) + level // 2, "You feel better!")


def spell_cure_critical(tr, sn, level, ch, vo, target, world):
    """Cure critical wounds (cf. 1stMud spell_cure_critical in magic.c)."""
    return _heal_char(tr, ch, vo, _dice(3, 8) + level - 6, "You feel better!")


def spell_heal(tr, sn, level, ch, vo, target, world):
    """Heal spell (cf. 1stMud spell_heal in magic.c)."""
    return _heal_char(tr, ch, vo, 100, "A warm feeling fills your body.")


def spell_cause_light(tr, sn, level, ch, vo, target, world):
    """Cause light wounds (cf. 1stMud spell_cause_light in magic.c)."""
    return _damage_char(tr, ch, vo, _target_id(ch, vo, world), _dice(1, 8) + level // 3, sn, world)


def spell_cause_serious(tr, sn, level, ch, vo, target, world):
    """Cause serious wounds (cf. 1stMud spell_cause_serious in magic.c)."""
    return _damage_char(tr, ch, vo, _target_id(ch, vo, world), _dice(2, 8) + level // 2, sn, world)


def spell_cause_critical(tr, sn, level, ch, vo, target, world):
    """Cause critical wounds (cf. 1stMud spell_cause_critical in magic.c)."""
    return _damage_char(tr, ch, vo, _target_id(ch, vo, world), _dice(3, 8) + level - 6, sn, world)


def spell_harm(tr, sn, level, ch, vo, target, world):
    """Harm spell, without saves until Phase 4 (cf. 1stMud spell_harm in magic.c)."""
    dam = max(20, vo["hp"] - _dice(1, 4))
    dam = min(100, dam)
    return _damage_char(tr, ch, vo, _target_id(ch, vo, world), dam, sn, world)


def spell_magic_missile(tr, sn, level, ch, vo, target, world):
    """Magic missile, without saves until Phase 4 (cf. 1stMud spell_magic_missile in magic.c)."""
    high = level | 50
    dam = randint(high // 2, high * 2)
    return _damage_char(tr, ch, vo, _target_id(ch, vo, world), dam, sn, world)


def _new_affect(sn, level, duration, location, modifier, bitvector=""):
    return {
        "where": "affects",
        "type": sn,
        "level": level,
        "duration": duration,
        "location": location,
        "modifier": modifier,
        "bitvector": bitvector,
    }


def spell_armor(tr, sn, level, ch, vo, target, world):
    """Armor spell (cf. 1stMud spell_armor in magic.c)."""
    if is_affected(vo, sn):
        tr.print("You are already armored." if vo is ch else "They are already armored.")
        return False
    affect_to_char(vo, _new_affect(sn, level, 24, "AC", -20))
    if vo is ch:
        tr.print("You feel someone protecting you.")
    else:
        tr.print("They are protected by your magic.")
    return True


def spell_shield(tr, sn, level, ch, vo, target, world):
    """Shield spell (cf. 1stMud spell_shield in magic.c)."""
    if is_affected(vo, sn):
        tr.print("You are already shielded from harm." if vo is ch else "They are already protected by a shield.")
        return False
    affect_to_char(vo, _new_affect(sn, level, 8 + level, "AC", -20))
    if vo is ch:
        tr.print("You are surrounded by a force shield.")
    return True


def spell_bless(tr, sn, level, ch, vo, target, world):
    """Bless character path (cf. 1stMud spell_bless in magic.c)."""
    if target == TARGET_OBJ:
        tr.print("That spell does not work on objects yet.")
        return False
    if vo.get("pos") == "fighting" or is_affected(vo, sn):
        tr.print("You are already blessed." if vo is ch else "They already have divine favor.")
        return False
    mod = level // 8
    affect_to_char(vo, _new_affect(sn, level, 6 + level, "hitroll", mod))
    affect_to_char(vo, _new_affect(sn, level, 6 + level, "saving_throw", -mod))
    if vo is ch:
        tr.print("You feel righteous.")
    else:
        tr.print("You grant them the favor of your god.")
    return True


def spell_giant_strength(tr, sn, level, ch, vo, target, world):
    """Giant strength spell (cf. 1stMud spell_giant_strength in magic.c)."""
    if is_affected(vo, sn):
        tr.print("You are already as strong as you can get!" if vo is ch else "They can't get any stronger.")
        return False
    mod = 1 + (level >= 18) + (level >= 25) + (level >= 32)
    affect_to_char(vo, _new_affect(sn, level, level, "str", mod))
    if vo is ch:
        tr.print("Your muscles surge with heightened power!")
    return True


def spell_weaken(tr, sn, level, ch, vo, target, world):
    """Weaken spell, without saves until Phase 4 (cf. 1stMud spell_weaken in magic.c)."""
    if is_affected(vo, sn):
        return False
    affect_to_char(vo, _new_affect(sn, level, level // 2, "str", -1 * (level // 5), "weaken"))
    if vo is ch:
        tr.print("You feel your strength slip away.")
    return True


def spell_faerie_fire(tr, sn, level, ch, vo, target, world):
    """Faerie fire spell (cf. 1stMud spell_faerie_fire in magic.c)."""
    if vo.get("aff_flags", {}).get("faerie_fire"):
        return False
    affect_to_char(vo, _new_affect(sn, level, level, "AC", 2 * level, "faerie_fire"))
    if vo is ch:
        tr.print("You are surrounded by a pink outline.")
    return True


SPELL_FUNS = {
    "spell_armor": spell_armor,
    "spell_bless": spell_bless,
    "spell_cause_critical": spell_cause_critical,
    "spell_cause_light": spell_cause_light,
    "spell_cause_serious": spell_cause_serious,
    "spell_cure_critical": spell_cure_critical,
    "spell_cure_light": spell_cure_light,
    "spell_cure_serious": spell_cure_serious,
    "spell_faerie_fire": spell_faerie_fire,
    "spell_giant_strength": spell_giant_strength,
    "spell_harm": spell_harm,
    "spell_heal": spell_heal,
    "spell_magic_missile": spell_magic_missile,
    "spell_shield": spell_shield,
    "spell_weaken": spell_weaken,
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


def _parse_spell_args(player, args):
    for n in range(len(args), 0, -1):
        sn = find_skill_spell(player, " ".join(args[:n]))
        if sn is not None and _implemented_spell(sn):
            return (sn, " ".join(args[n:]))
    return (find_skill_spell(player, args[0]), " ".join(args[1:]))


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
        sn, target_name = _parse_spell_args(player, args)

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
            and victim_id in world["mobs"]
            and player.get("fighting") is None):
        set_fighting(tr, player, victim_id, world["mobs"])
    return None
