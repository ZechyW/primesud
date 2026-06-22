"""Magic command handling and spell dispatch (cf. 1stMud magic.c)."""

from world import SKILLS, SKILL_TABLE, ITEM_TEMPLATES, MOB_TEMPLATES, R_RECALL, ROOM_AREAS
from picker import pick_from
from combat import (WaitState, check_improve, get_skill, set_fighting,
                    deal_player_mob_damage)
from item import (get_char_room, get_obj_list, obj_vnum, item_spell_level,
                  item_spells, item_spell_name, item_extra_flags,
                  item_current_charges, item_max_charges, item_affect_list,
                  item_affect_find, item_affect_remove, item_affect_to_obj,
                  set_item_extra_flag)
from actor import is_name, is_affected, affect_to_char, affect_strip
from skill_utils import can_use_skill_spell, find_skill_spell, spell_mana
from movement import perform_recall
from colors import cap_first
from scan import do_scan

from urandom import randint


TARGET_NONE = "none"
TARGET_CHAR = "char"
TARGET_OBJ = "obj"
TARGET_ROOM = "room"
_AC_LOCS = ("ac_pierce", "ac_bash", "ac_slash", "ac_exotic")

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
    if victim is ch:
        tr.print(msg)
    else:
        tr.print("Ok.")
    return True


def _target_id(ch, victim, world):
    if victim is None or victim is ch:
        return None
    for mob_id, inst in world["chars"].items():
        if inst is victim:
            return mob_id
    return None


def _damage_char(tr, ch, victim, victim_id, dam, sn, world):
    """Apply spell damage through shared combat adapter (cf. 1stMud damage in fight.c)."""
    sk = SKILLS[sn]
    noun = sk.get("noun_damage") or sk["name"]
    deal_player_mob_damage(
        tr, ch, victim, dam, world, victim_id, attack_noun=noun, kill_now=True)
    return True


def _char_name(ch, victim, world):
    if victim is ch:
        return "You"
    if victim.get("is_npc"):
        tpl = MOB_TEMPLATES.get(victim.get("tpl"), {})
        return cap_first(tpl.get("short_descr", "Someone"))
    return cap_first(victim.get("name", "Someone"))


def _skill_lookup(name):
    for sn, sk in SKILL_TABLE:
        if sk["name"] == name:
            return sn
    return None


def _area_state_for_room(world, room_vnum):
    tag = ROOM_AREAS.get(room_vnum)
    if tag is None:
        return None
    for area in world.get("areas", []):
        if area.get("tag") == tag:
            return area
    return None


def _spell_tail(ch):
    return ch.get("_spell_target_name", "")


def _item_name(obj):
    if obj is None:
        return "item"
    tpl = ITEM_TEMPLATES.get(obj_vnum(obj), {})
    return tpl.get("short_descr", "item")


def _flag_names(flags):
    names = sorted(flags)
    if not names:
        return "none"
    return " ".join(names)


def _obj_carried_by(ch, obj):
    return obj in ch.get("inv", [])


def _obj_equipped_by(ch, obj):
    for eq in ch.get("equip", {}).values():
        if eq is obj:
            return True
    return False


def _item_bonus_sum(obj, tpl, location):
    total = tpl.get("stat_bonuses", {}).get(location, 0)
    for af in item_affect_list(obj):
        if af.get("location") == location:
            total += af.get("modifier", 0)
    return total


def _item_armor_bonus(obj, tpl):
    total = 0
    for loc in _AC_LOCS:
        total += _item_bonus_sum(obj, tpl, loc)
    return total // 4


def _add_obj_ac_affect(obj, tpl, sn, level, modifier):
    for loc in _AC_LOCS:
        found = False
        for af in item_affect_list(obj):
            if af.get("location") == loc:
                af["type"] = sn
                af["modifier"] = af.get("modifier", 0) + modifier
                af["level"] = max(af.get("level", 0), level)
                found = True
                break
        if not found:
            item_affect_to_obj(obj, _new_obj_affect(sn, level, -1, loc, modifier), tpl)


def _clear_item_runtime_affects(obj):
    if "affect_list" in obj:
        del obj["affect_list"]


def _new_obj_affect(sn, level, duration, location, modifier, bitvector=""):
    af = _new_affect(sn, level, duration, location, modifier, bitvector)
    af["where"] = "obj"
    return af


def _dev_item_fail(tr, obj, message):
    tr.print("[DEV] " + _item_name(obj) + ": " + message)
    return False


def saves_spell(level, victim, dam_type):
    """Return True when victim saves against spell (cf. 1stMud saves_spell in magic.c)."""
    save = 50 + (victim.get("level", 1) - level) * 5 - victim.get("saving_throw", 0) * 2
    if save < 5:
        save = 5
    elif save > 95:
        save = 95
    return randint(1, 100) < save


def saves_dispel(dis_level, spell_level, duration):
    """Return True when affect resists dispel (cf. 1stMud saves_dispel in magic.c)."""
    if duration == -1:
        spell_level += 5
    save = 50 + (spell_level - dis_level) * 5
    if save < 5:
        save = 5
    elif save > 95:
        save = 95
    return randint(1, 100) < save


def check_dispel(tr, dis_level, victim, sn, ch=None):
    """Try to dispel one affect type (cf. 1stMud check_dispel in magic.c)."""
    if not is_affected(victim, sn):
        return False
    for af in list(victim.get("affect_list", [])):
        if af.get("type") != sn:
            continue
        if not saves_dispel(dis_level, af.get("level", 0), af.get("duration", 0)):
            affect_strip(victim, sn)
            msg = SKILLS.get(sn, {}).get("msg_off", "")
            if (ch is None or victim is ch) and msg and not msg.startswith("!"):
                tr.print(msg)
            return True
        af["level"] = af.get("level", 0) - 1
    return False


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
    """Harm spell (cf. 1stMud spell_harm in magic.c)."""
    dam = max(20, vo["hp"] - _dice(1, 4))
    if saves_spell(level, vo, "harm"):
        dam = min(50, dam // 2)
    dam = min(100, dam)
    return _damage_char(tr, ch, vo, _target_id(ch, vo, world), dam, sn, world)


def spell_magic_missile(tr, sn, level, ch, vo, target, world):
    """Magic missile (cf. 1stMud spell_magic_missile in magic.c)."""
    high = level | 50
    dam = randint(high // 2, high * 2)
    if saves_spell(level, vo, "energy"):
        dam //= 2
    return _damage_char(tr, ch, vo, _target_id(ch, vo, world), dam, sn, world)


def spell_earthquake(tr, sn, level, ch, vo, target, world):
    """Earthquake room spell (cf. 1stMud spell_earthquake in magic.c)."""
    tr.print("The earth trembles beneath your feet!")
    room = world["rooms"][ch["room"]]
    first_target = None
    for mob_id in list(room["mobs"]):
        victim = world["chars"].get(mob_id)
        if victim is None or victim is ch:
            continue
        dam = 0 if victim.get("aff_flags", {}).get("flying") else level + _dice(2, 8)
        _damage_char(tr, ch, victim, mob_id, dam, sn, world)
        if mob_id in world["chars"]:
            victim = world["chars"][mob_id]
            victim["fighting"] = ch
            if first_target is None:
                first_target = mob_id
    if first_target is not None:
        ch["fighting"] = first_target
        ch["pos"] = "fighting"
    return True


def spell_call_lightning(tr, sn, level, ch, vo, target, world):
    """Call lightning area spell (cf. 1stMud spell_call_lightning in magic.c)."""
    room = ROOMS[ch["room"]]
    if room.get("flags", {}).get("indoors"):
        tr.print("You must be out of doors.")
        return False
    area = _area_state_for_room(world, ch["room"])
    weather = area.get("weather") if area is not None else None
    if weather is None or weather.get("precip", 0) <= 0:
        tr.print("You need bad weather.")
        return False

    dam = _dice(max(1, level // 2), 8)
    tr.print("Your lightning strikes your foes!")
    first_target = None
    room_state = world["rooms"][ch["room"]]
    for mob_id in list(room_state["mobs"]):
        victim = world["chars"].get(mob_id)
        if victim is None or victim is ch:
            continue
        cur_dam = dam
        if saves_spell(level, victim, "lightning"):
            cur_dam //= 2
        _damage_char(tr, ch, victim, mob_id, cur_dam, sn, world)
        if mob_id in world["chars"]:
            victim = world["chars"][mob_id]
            victim["fighting"] = ch
            if first_target is None:
                first_target = mob_id
    if first_target is not None:
        ch["fighting"] = first_target
        ch["pos"] = "fighting"
    return True


def spell_chain_lightning(tr, sn, level, ch, vo, target, world):
    """Chain lightning room spell (cf. 1stMud spell_chain_lightning in magic.c)."""
    victim = vo
    if victim is None or victim.get("is_npc") is not True:
        tr.print("You failed.")
        return False
    tr.print("A lightning bolt leaps from your hand and arcs to " +
             MOB_TEMPLATES[victim["tpl"]]["short_descr"] + ".")

    room_state = world["rooms"][ch["room"]]
    victim_id = _target_id(ch, victim, world)
    first_target = victim_id
    last_victim_id = victim_id
    last_hit_ch = False
    any_hit = False

    while level > 0 and victim is not None:
        dam = _dice(level, 6)
        if saves_spell(level, victim, "lightning"):
            dam //= 3
        _damage_char(tr, ch, victim, victim_id, dam, sn, world)
        any_hit = True
        if victim_id is not None and victim_id in world["chars"]:
            world["chars"][victim_id]["fighting"] = ch
        level -= 4
        last_victim_id = victim_id
        last_hit_ch = False

        if level <= 0:
            break

        next_id = None
        for mob_id in room_state["mobs"]:
            if mob_id != last_victim_id:
                next_id = mob_id
                break

        if next_id is not None:
            victim_id = next_id
            victim = world["chars"].get(victim_id)
            if victim is not None:
                tr.print("The bolt arcs to " + MOB_TEMPLATES[victim["tpl"]]["short_descr"] + "!")
            continue

        # No alternate mob target - arc back to caster (cf. 1stMud last_vict == ch path)
        if last_hit_ch:
            tr.print("The bolt grounds out through your body.")
            break
        tr.print("You are struck by your own lightning!")
        dam2 = _dice(level, 6)
        if saves_spell(level, ch, "lightning"):
            dam2 //= 3
        ch["hp"] = max(-1, ch["hp"] - dam2)
        level -= 4
        last_hit_ch = True
        if level <= 0 or ch["hp"] <= 0:
            break
        next_id = None
        for mob_id in room_state["mobs"]:
            next_id = mob_id
            break
        if next_id is None:
            tr.print("The bolt grounds out through your body.")
            break
        victim_id = next_id
        victim = world["chars"].get(victim_id)
        if victim is not None:
            tr.print("The bolt arcs to " + MOB_TEMPLATES[victim["tpl"]]["short_descr"] + "!")

    if first_target is not None and first_target in world["chars"]:
        ch["fighting"] = first_target
        ch["pos"] = "fighting"
    return any_hit


def _random_teleport_room(ch):
    rooms = []
    for room_vnum, room in ROOMS.items():
        flags = room.get("flags", {})
        if flags.get("private") or flags.get("solitary") or flags.get("safe") or flags.get("arena"):
            continue
        if not ch.get("is_npc") and flags.get("law"):
            continue
        rooms.append(room_vnum)
    if not rooms:
        return None
    return rooms[randint(0, len(rooms) - 1)]


def spell_teleport(tr, sn, level, ch, vo, target, world):
    """Teleport target to random room (cf. 1stMud spell_teleport in magic.c)."""
    victim = vo
    room = ROOMS.get(victim.get("room"))
    if (room is None
            or room.get("flags", {}).get("no_recall")
            or (victim is not ch and saves_spell(level - 5, victim, "other"))
            or (ch.get("is_npc") is not True and victim.get("fighting") is not None)):
        tr.print("You failed.")
        return False
    dest = _random_teleport_room(victim)
    if dest is None:
        tr.print("You failed.")
        return False
    old_room = victim["room"]
    victim["room"] = dest
    victim_id = _target_id(ch, victim, world)
    if victim_id is not None:
        if victim_id in world["rooms"].get(old_room, {}).get("mobs", []):
            world["rooms"][old_room]["mobs"].remove(victim_id)
        world["rooms"][dest]["mobs"].append(victim_id)
    if victim is ch:
        from info import do_look
        do_look(tr, victim, [], world)
    else:
        tr.print(_char_name(ch, victim, world) + " vanishes!")
    return True


def spell_farsight(tr, sn, level, ch, vo, target, world):
    """Farsight spell (cf. 1stMud spell_farsight in magic2.c)."""
    if ch.get("aff_flags", {}).get("blind"):
        tr.print("Maybe it would help if you could see?")
        return False
    do_scan(tr, ch, _spell_tail(ch).split(), world)
    return True


def _iter_world_objects(player, world):
    for obj in player.get("inv", []):
        yield (obj, "one is carried by you")
    for obj in player.get("equip", {}).values():
        if obj is not None:
            yield (obj, "one is carried by you")
    for room_vnum, room_state in world.get("rooms", {}).items():
        for obj in room_state.get("items", []):
            yield (obj, "one is in " + ROOMS.get(room_vnum, {}).get("name", "somewhere"))
    for mob in world.get("mobs", {}).values():
        mob_name = MOB_TEMPLATES[mob["tpl"]]["short_descr"]
        for obj in mob.get("inv", []):
            yield (obj, "one is carried by " + mob_name)
        for obj in mob.get("equip", {}).values():
            if obj is not None:
                yield (obj, "one is carried by " + mob_name)


def spell_locate_object(tr, sn, level, ch, vo, target, world):
    """Locate object by name fragment (cf. 1stMud spell_locate_object in magic.c)."""
    wanted = _spell_tail(ch)
    if not wanted:
        tr.print("Nothing like that in heaven or earth.")
        return False
    found = []
    max_found = 2 * level
    for obj, line in _iter_world_objects(ch, world):
        tpl = ITEM_TEMPLATES[obj_vnum(obj)]
        if not is_name(wanted, tpl.get("keywords", "")):
            continue
        if item_extra_flags(obj, tpl).get("no_locate"):
            continue
        found.append(line)
        if len(found) >= max_found:
            break
    if not found:
        tr.print("Nothing like that in heaven or earth.")
        return False
    for line in found:
        tr.print(line)
    return True


def spell_control_weather(tr, sn, level, ch, vo, target, world):
    """Adjust simplified interim weather state (cf. 1stMud spell_control_weather in magic.c)."""
    arg = _spell_tail(ch)
    area = _area_state_for_room(world, ch["room"])
    if area is None:
        tr.print("The weather is altered by your magic.")
        return True
    weather = area.setdefault("weather", {"precip": 0, "precip_vector": 0})
    change = randint(-1, 1) + max(1, (level * 3) // 20)
    if arg == "wetter":
        weather["precip_vector"] += change
    elif arg == "drier":
        weather["precip_vector"] -= change
    elif arg in ("warmer", "colder", "windier", "calmer"):
        pass  # [PRIMESUD] interim model stores only precipitation.
    else:
        tr.print("Do you want it to get warmer, colder, wetter, drier, windier, or calmer?")
        return False
    if weather["precip_vector"] < -3:
        weather["precip_vector"] = -3
    elif weather["precip_vector"] > 3:
        weather["precip_vector"] = 3
    tr.print("The weather is altered by your magic.")
    return True


def spell_word_of_recall(tr, sn, level, ch, vo, target, world):
    """Word of recall spell (cf. 1stMud spell_word_of_recall in magic.c)."""
    victim = vo if vo is not None else ch
    if victim.get("is_npc"):
        return False
    return perform_recall(tr, victim, R_RECALL, world, "recall")


def spell_trivia_pill(tr, sn, level, ch, vo, target, world):
    """Grant one trivia point (cf. 1stMud spell_trivia_pill in magic.c)."""
    victim = vo if vo is not None else ch
    if victim.get("is_npc"):
        return False
    victim["trivia"] = victim.get("trivia", 0) + 1
    tr.print("You've gained a Trivia Point!")
    if victim is not ch:
        tr.print("Ok.")
    return True


def spell_detect_poison(tr, sn, level, ch, vo, target, world):
    """Detect poison on object target (cf. 1stMud spell_detect_poison in magic.c)."""
    tpl = ITEM_TEMPLATES[obj_vnum(vo)]
    poisoned = bool(vo.get("poisoned") or tpl.get("poisoned"))
    if tpl.get("type") in ("food", "fountain"):
        tr.print("You smell poisonous fumes." if poisoned else "It looks delicious.")
    else:
        tr.print("It doesn't look poisoned.")
    return True


def spell_identify(tr, sn, level, ch, vo, target, world):
    """Identify object details (cf. 1stMud spell_identify in magic.c)."""
    tpl = ITEM_TEMPLATES[obj_vnum(vo)]
    flags = item_extra_flags(vo, tpl)
    tr.print("Object '" + tpl.get("keywords", "") + "' is type " + tpl.get("type", "unknown")
             + ", extra flags " + _flag_names(flags) + ".")
    tr.print("Weight is " + str(tpl.get("weight", 0)) + ", value is "
             + str(vo.get("cost", tpl.get("value", 0))) + ", level is " + str(tpl.get("level", 0)) + ".")
    if tpl.get("type") in ("scroll", "potion", "pill"):
        spells = item_spells(vo, tpl)
        if spells:
            tr.print("Level " + str(item_spell_level(vo, tpl)) + " spells of: '" + "' '".join(spells) + "'.")
    elif tpl.get("type") in ("wand", "staff"):
        line = "Has " + str(item_current_charges(vo, tpl)) + " charges of level " + str(item_spell_level(vo, tpl))
        spell_name = item_spell_name(vo, tpl)
        if spell_name:
            line += " '" + spell_name + "'"
        tr.print(line + ".")
    for loc, mod in tpl.get("stat_bonuses", {}).items():
        tr.print("Affects " + loc + " by " + str(mod) + ".")
    for af in item_affect_list(vo):
        loc = af.get("location", "none")
        mod = af.get("modifier", 0)
        line = "Affects " + loc + " by " + str(mod)
        if af.get("duration", -1) > -1:
            line += ", " + str(af["duration"]) + " hours."
        else:
            line += "."
        tr.print(line)
        bit = af.get("bitvector", "")
        if af.get("where") == "obj" and bit:
            tr.print("Adds " + bit + " object flag.")
    return True


def spell_fireproof(tr, sn, level, ch, vo, target, world):
    """Fireproof object target (cf. 1stMud spell_fireproof in magic.c)."""
    tpl = ITEM_TEMPLATES[obj_vnum(vo)]
    flags = item_extra_flags(vo, tpl)
    if flags.get("burn_proof"):
        tr.print(_item_name(vo) + " is already protected from burning.")
        return False
    item_affect_to_obj(vo, _new_obj_affect(sn, level, max(1, level // 4), "none", 0, "burn_proof"), tpl)
    tr.print("You protect " + _item_name(vo) + " from fire.")
    return True


def spell_enchant_armor(tr, sn, level, ch, vo, target, world):
    """Enchant armor item (cf. 1stMud spell_enchant_armor in magic.c)."""
    tpl = ITEM_TEMPLATES[obj_vnum(vo)]
    if tpl.get("type") != "armor":
        tr.print("That isn't an armor.")
        return False
    if not _obj_carried_by(ch, vo):
        tr.print("The item must be carried to be enchanted.")
        return False
    if item_extra_flags(vo, tpl).get("quest"):
        tr.print("You can't enchant quest items.")
        return False
    ac_bonus = _item_armor_bonus(vo, tpl)
    fail = 25 + (5 * ac_bonus * ac_bonus if ac_bonus else 0) - level
    flags = item_extra_flags(vo, tpl)
    if flags.get("bless"):
        fail -= 15
    if flags.get("glow"):
        fail -= 5
    if fail < 5:
        fail = 5
    elif fail > 85:
        fail = 85
    result = randint(1, 100)
    if result < fail // 5:
        tr.print(_item_name(vo) + " flares blindingly... and evaporates!")
        ch["inv"].remove(vo)
        return False
    if result < fail // 3:
        tr.print(_item_name(vo) + " glows brightly, then fades...oops.")
        vo["enchanted"] = True
        _clear_item_runtime_affects(vo)
        vo["extra_flags"] = {}
        return False
    if result <= fail:
        tr.print("Nothing seemed to happen.")
        return False
    vo["enchanted"] = True
    if result <= (90 - level // 5):
        tr.print(_item_name(vo) + " shimmers with a gold aura.")
        set_item_extra_flag(vo, tpl, "magic", True)
        added = -1
    else:
        tr.print(_item_name(vo) + " glows a brillant gold!")
        set_item_extra_flag(vo, tpl, "magic", True)
        set_item_extra_flag(vo, tpl, "glow", True)
        added = -2
    vo["level"] = min(50, vo.get("level", tpl.get("level", 0)) + 1)
    _add_obj_ac_affect(vo, tpl, sn, level, added)
    return True


def spell_enchant_weapon(tr, sn, level, ch, vo, target, world):
    """Enchant weapon item (cf. 1stMud spell_enchant_weapon in magic.c)."""
    tpl = ITEM_TEMPLATES[obj_vnum(vo)]
    if tpl.get("type") != "weapon":
        tr.print("That isn't a weapon.")
        return False
    if not _obj_carried_by(ch, vo):
        tr.print("The item must be carried to be enchanted.")
        return False
    if item_extra_flags(vo, tpl).get("quest"):
        tr.print("You can't enchant quest items.")
        return False
    hit_bonus = _item_bonus_sum(vo, tpl, "hitroll")
    dam_bonus = _item_bonus_sum(vo, tpl, "damroll")
    fail = 25 + 2 * hit_bonus * hit_bonus + 2 * dam_bonus * dam_bonus - (3 * level // 2)
    flags = item_extra_flags(vo, tpl)
    if flags.get("bless"):
        fail -= 15
    if flags.get("glow"):
        fail -= 5
    if fail < 5:
        fail = 5
    elif fail > 95:
        fail = 95
    result = randint(1, 100)
    if result < fail // 5:
        tr.print(_item_name(vo) + " shivers violently and explodes!")
        ch["inv"].remove(vo)
        return False
    if result < fail // 2:
        tr.print(_item_name(vo) + " glows brightly, then fades...oops.")
        vo["enchanted"] = True
        _clear_item_runtime_affects(vo)
        vo["extra_flags"] = {}
        return False
    if result <= fail:
        tr.print("Nothing seemed to happen.")
        return False
    vo["enchanted"] = True
    if result <= (100 - level // 5):
        tr.print(_item_name(vo) + " glows blue.")
        set_item_extra_flag(vo, tpl, "magic", True)
        added = 1
    else:
        tr.print(_item_name(vo) + " glows a brillant blue!")
        set_item_extra_flag(vo, tpl, "magic", True)
        set_item_extra_flag(vo, tpl, "glow", True)
        added = 2
    vo["level"] = min(50, vo.get("level", tpl.get("level", 0)) + 1)
    found_dam = False
    found_hit = False
    for af in item_affect_list(vo):
        if af.get("location") == "damroll":
            af["type"] = sn
            af["modifier"] = af.get("modifier", 0) + added
            af["level"] = max(af.get("level", 0), level)
            if af["modifier"] > 4:
                set_item_extra_flag(vo, tpl, "hum", True)
            found_dam = True
        elif af.get("location") == "hitroll":
            af["type"] = sn
            af["modifier"] = af.get("modifier", 0) + added
            af["level"] = max(af.get("level", 0), level)
            if af["modifier"] > 4:
                set_item_extra_flag(vo, tpl, "hum", True)
            found_hit = True
    if not found_dam:
        item_affect_to_obj(vo, _new_obj_affect(sn, level, -1, "damroll", added), tpl)
    if not found_hit:
        item_affect_to_obj(vo, _new_obj_affect(sn, level, -1, "hitroll", added), tpl)
    return True


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
        tr.print("You are already armored." if vo is ch else _char_name(ch, vo, world) + " is already armored.")
        return False
    affect_to_char(vo, _new_affect(sn, level, 24, "ac", -20))
    if vo is ch:
        tr.print("You feel someone protecting you.")
    else:
        tr.print(_char_name(ch, vo, world) + " is protected by your magic.")
    return True


def spell_shield(tr, sn, level, ch, vo, target, world):
    """Shield spell (cf. 1stMud spell_shield in magic.c)."""
    if is_affected(vo, sn):
        tr.print("You are already shielded from harm." if vo is ch else _char_name(ch, vo, world) + " is already protected by a shield.")
        return False
    affect_to_char(vo, _new_affect(sn, level, 8 + level, "ac", -20))
    if vo is ch:
        tr.print("You are surrounded by a force shield.")
    else:
        tr.print(_char_name(ch, vo, world) + " is surrounded by a force shield.")
    return True


def spell_bless(tr, sn, level, ch, vo, target, world):
    """Bless character path (cf. 1stMud spell_bless in magic.c)."""
    if target == TARGET_OBJ:
        tpl = ITEM_TEMPLATES[obj_vnum(vo)]
        flags = item_extra_flags(vo, tpl)
        if flags.get("bless"):
            tr.print(_item_name(vo) + " is already blessed.")
            return False
        if flags.get("evil"):
            paf = item_affect_find(vo, _skill_lookup("curse"))
            if not saves_dispel(level, paf.get("level", tpl.get("level", 0)) if paf else tpl.get("level", 0), 0):
                if paf is not None:
                    item_affect_remove(vo, paf, tpl)
                set_item_extra_flag(vo, tpl, "evil", False)
                tr.print(_item_name(vo) + " glows a pale blue.")
                return True
            tr.print("The evil of " + _item_name(vo) + " is too powerful for you to overcome.")
            return False
        item_affect_to_obj(vo, _new_affect(sn, level, 6 + level, "saving_throw", -1, "bless"), tpl)
        vo["affect_list"][-1]["where"] = "obj"
        tr.print(_item_name(vo) + " glows with a holy aura.")
        return True
    if vo.get("pos") == "fighting" or is_affected(vo, sn):
        tr.print("You are already blessed." if vo is ch else _char_name(ch, vo, world) + " already has divine favor.")
        return False
    mod = level // 8
    affect_to_char(vo, _new_affect(sn, level, 6 + level, "hitroll", mod))
    affect_to_char(vo, _new_affect(sn, level, 6 + level, "saving_throw", -mod))
    if vo is ch:
        tr.print("You feel righteous.")
    else:
        tr.print("You grant " + _char_name(ch, vo, world) + " the favor of your god.")
    return True


def spell_giant_strength(tr, sn, level, ch, vo, target, world):
    """Giant strength spell (cf. 1stMud spell_giant_strength in magic.c)."""
    if is_affected(vo, sn):
        tr.print("You are already as strong as you can get!" if vo is ch else _char_name(ch, vo, world) + " can't get any stronger.")
        return False
    mod = 1 + (level >= 18) + (level >= 25) + (level >= 32)
    affect_to_char(vo, _new_affect(sn, level, level, "str", mod))
    if vo is ch:
        tr.print("Your muscles surge with heightened power!")
    else:
        tr.print(_char_name(ch, vo, world) + "'s muscles surge with heightened power.")
    return True


def spell_weaken(tr, sn, level, ch, vo, target, world):
    """Weaken spell (cf. 1stMud spell_weaken in magic.c)."""
    if is_affected(vo, sn) or saves_spell(level, vo, "other"):
        return False
    affect_to_char(vo, _new_affect(sn, level, level // 2, "str", -1 * (level // 5), "weaken"))
    if vo is ch:
        tr.print("You feel your strength slip away.")
    else:
        tr.print(_char_name(ch, vo, world) + " looks tired and weak.")
    return True


def spell_faerie_fire(tr, sn, level, ch, vo, target, world):
    """Faerie fire spell (cf. 1stMud spell_faerie_fire in magic.c)."""
    if vo.get("aff_flags", {}).get("faerie_fire"):
        return False
    affect_to_char(vo, _new_affect(sn, level, level, "ac", 2 * level, "faerie_fire"))
    if vo is ch:
        tr.print("You are surrounded by a pink outline.")
    else:
        tr.print(_char_name(ch, vo, world) + " is surrounded by a pink outline.")
    return True


def spell_blindness(tr, sn, level, ch, vo, target, world):
    """Blindness spell (cf. 1stMud spell_blindness in magic.c)."""
    if vo.get("aff_flags", {}).get("blind") or saves_spell(level, vo, "other"):
        tr.print("You failed.")
        return False
    affect_to_char(vo, _new_affect(sn, level, 1 + level, "hitroll", -4, "blind"))
    if vo is ch:
        tr.print("You are blinded!")
    else:
        tr.print(_char_name(ch, vo, world) + " appears to be blinded.")
    return True


def spell_poison(tr, sn, level, ch, vo, target, world):
    """Poison character path (cf. 1stMud spell_poison in magic.c)."""
    if target == TARGET_OBJ:
        tr.print("That spell does not work on objects yet.")
        return False
    if saves_spell(level, vo, "poison"):
        tr.print("You feel momentarily ill, but it passes." if vo is ch else _char_name(ch, vo, world) + " turns slightly green, but it passes.")
        return False
    affect_to_char(vo, _new_affect(sn, level, level, "str", -2, "poison"))
    if vo is ch:
        tr.print("You feel very sick.")
    else:
        tr.print(_char_name(ch, vo, world) + " looks very ill.")
    return True


def spell_curse(tr, sn, level, ch, vo, target, world):
    """Curse character path (cf. 1stMud spell_curse in magic.c)."""
    if target == TARGET_OBJ:
        tpl = ITEM_TEMPLATES[obj_vnum(vo)]
        flags = item_extra_flags(vo, tpl)
        if flags.get("evil"):
            tr.print(_item_name(vo) + " is already filled with evil.")
            return False
        if flags.get("bless"):
            paf = item_affect_find(vo, _skill_lookup("bless"))
            if not saves_dispel(level, paf.get("level", tpl.get("level", 0)) if paf else tpl.get("level", 0), 0):
                if paf is not None:
                    item_affect_remove(vo, paf, tpl)
                set_item_extra_flag(vo, tpl, "bless", False)
                tr.print(_item_name(vo) + " glows with a red aura.")
                return True
            tr.print("The holy aura of " + _item_name(vo) + " is too powerful for you to overcome.")
            return False
        item_affect_to_obj(vo, _new_affect(sn, level, 2 * level, "saving_throw", 1, "evil"), tpl)
        vo["affect_list"][-1]["where"] = "obj"
        tr.print(_item_name(vo) + " glows with a malevolent aura.")
        return True
    if vo.get("aff_flags", {}).get("curse") or saves_spell(level, vo, "negative"):
        return False
    mod = level // 8
    affect_to_char(vo, _new_affect(sn, level, 2 * level, "hitroll", -mod, "curse"))
    affect_to_char(vo, _new_affect(sn, level, 2 * level, "saving_throw", mod))
    if vo is ch:
        tr.print("You feel unclean.")
    else:
        tr.print(_char_name(ch, vo, world) + " looks very uncomfortable.")
    return True


def spell_plague(tr, sn, level, ch, vo, target, world):
    """Plague spell (cf. 1stMud spell_plague in magic.c)."""
    if saves_spell(level, vo, "disease"):
        tr.print("You feel momentarily ill, but it passes." if vo is ch else _char_name(ch, vo, world) + " seems to be unaffected.")
        return False
    affect_to_char(vo, _new_affect(sn, level * 3 // 4, level, "str", -5, "plague"))
    if vo is ch:
        tr.print("You scream in agony as plague sores erupt from your skin.")
    else:
        tr.print(_char_name(ch, vo, world) + " screams in agony as plague sores erupt from their skin.")
    return True


def spell_cure_blindness(tr, sn, level, ch, vo, target, world):
    """Cure blindness (cf. 1stMud spell_cure_blindness in magic.c)."""
    blind_sn = _skill_lookup("blindness")
    if not is_affected(vo, blind_sn):
        tr.print("You aren't blind." if vo is ch else _char_name(ch, vo, world) + " doesn't appear to be blinded.")
        return False
    if check_dispel(tr, level, vo, blind_sn, ch):
        tr.print("Your vision returns!" if vo is ch else _char_name(ch, vo, world) + " is no longer blinded.")
        return True
    tr.print("Spell failed.")
    return False


def spell_cure_poison(tr, sn, level, ch, vo, target, world):
    """Cure poison (cf. 1stMud spell_cure_poison in magic.c)."""
    poison_sn = _skill_lookup("poison")
    if not is_affected(vo, poison_sn):
        tr.print("You aren't poisoned." if vo is ch else _char_name(ch, vo, world) + " doesn't appear to be poisoned.")
        return False
    if check_dispel(tr, level, vo, poison_sn, ch):
        tr.print("A warm feeling runs through your body." if vo is ch else _char_name(ch, vo, world) + " looks much better.")
        return True
    tr.print("Spell failed.")
    return False


def spell_cure_disease(tr, sn, level, ch, vo, target, world):
    """Cure disease (cf. 1stMud spell_cure_disease in magic.c)."""
    plague_sn = _skill_lookup("plague")
    if not is_affected(vo, plague_sn):
        tr.print("You aren't ill." if vo is ch else _char_name(ch, vo, world) + " doesn't appear to be diseased.")
        return False
    if check_dispel(tr, level, vo, plague_sn, ch):
        tr.print("Your sores vanish." if vo is ch else _char_name(ch, vo, world) + " looks relieved as their sores vanish.")
        return True
    tr.print("Spell failed.")
    return False


def spell_dispel_magic(tr, sn, level, ch, vo, target, world):
    """Dispel magic over implemented affects (cf. 1stMud spell_dispel_magic in magic.c)."""
    if saves_spell(level, vo, "other"):
        if vo is ch:
            tr.print("You feel a brief tingling sensation.")
        tr.print("You failed.")
        return False
    found = False
    for name in ("armor", "bless", "blindness", "curse", "faerie fire",
                 "giant strength", "plague", "poison", "shield", "weaken"):
        cur = _skill_lookup(name)
        if cur is not None and check_dispel(tr, level, vo, cur, ch):
            found = True
    if found:
        tr.print("Ok.")
        return True
    tr.print("Spell failed.")
    return False


SPELL_FUNS = {
    "spell_armor": spell_armor,
    "spell_bless": spell_bless,
    "spell_blindness": spell_blindness,
    "spell_call_lightning": spell_call_lightning,
    "spell_cause_critical": spell_cause_critical,
    "spell_cause_light": spell_cause_light,
    "spell_cause_serious": spell_cause_serious,
    "spell_chain_lightning": spell_chain_lightning,
    "spell_control_weather": spell_control_weather,
    "spell_cure_critical": spell_cure_critical,
    "spell_cure_blindness": spell_cure_blindness,
    "spell_cure_disease": spell_cure_disease,
    "spell_cure_light": spell_cure_light,
    "spell_cure_poison": spell_cure_poison,
    "spell_cure_serious": spell_cure_serious,
    "spell_curse": spell_curse,
    "spell_detect_poison": spell_detect_poison,
    "spell_dispel_magic": spell_dispel_magic,
    "spell_earthquake": spell_earthquake,
    "spell_enchant_armor": spell_enchant_armor,
    "spell_enchant_weapon": spell_enchant_weapon,
    "spell_identify": spell_identify,
    "spell_faerie_fire": spell_faerie_fire,
    "spell_farsight": spell_farsight,
    "spell_fireproof": spell_fireproof,
    "spell_giant_strength": spell_giant_strength,
    "spell_harm": spell_harm,
    "spell_heal": spell_heal,
    "spell_magic_missile": spell_magic_missile,
    "spell_locate_object": spell_locate_object,
    "spell_plague": spell_plague,
    "spell_poison": spell_poison,
    "spell_shield": spell_shield,
    "spell_teleport": spell_teleport,
    "spell_trivia_pill": spell_trivia_pill,
    "spell_weaken": spell_weaken,
    "spell_word_of_recall": spell_word_of_recall,
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
    return (find_skill_spell(player, args[0]), " ".join(args[1:]))


def _quote_cast_spell_name(name):
    if " " in name:
        return "'" + name + "'"
    return name


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
    mob_id = get_char_room(target_name, rs["mobs"], world["chars"])
    if mob_id is None:
        return None
    return world["chars"][mob_id]


def _find_room_char_id(player, world, target_name):
    rs = _room_state(player, world)
    return get_char_room(target_name, rs["mobs"], world["chars"])


def _find_inv_obj(player, target_name):
    return get_obj_list(target_name, player["inv"], ITEM_TEMPLATES)


def _find_room_obj(player, world, target_name):
    rs = _room_state(player, world)
    return get_obj_list(target_name, rs["items"], ITEM_TEMPLATES)


def _mob_pick_name(mob):
    tpl = MOB_TEMPLATES[mob["tpl"]]
    words = tpl.get("keywords", "").split()
    if words:
        return words[0]
    words = tpl.get("short_descr", "").split()
    if words:
        return words[0]
    return ""


def _obj_pick_name(obj):
    tpl = ITEM_TEMPLATES[obj_vnum(obj)]
    words = tpl.get("keywords", "").split()
    if words:
        return words[0]
    words = tpl.get("short_descr", "").split()
    if words:
        return words[0]
    return ""


def _pick_cast_target_name(tr, player, sn, world):
    """Pick missing spell target for PrimeSUD command UI."""
    sk = SKILLS[sn]
    target_type = sk.get("target", "ignore")
    rs = _room_state(player, world)

    if target_type == "char_offensive":
        if player.get("fighting") is not None:
            return ""
        opts = []
        names = []
        for mob_id in rs["mobs"]:
            mob = world["chars"][mob_id]
            opts.append(MOB_TEMPLATES[mob["tpl"]]["short_descr"])
            names.append(_mob_pick_name(mob))
        if not opts:
            return ""
        idx = pick_from(tr, "Cast the spell on whom?", opts)
        if idx < 0:
            return None
        return names[idx]

    if target_type == "obj_inventory":
        opts = []
        names = []
        for obj in player["inv"]:
            tpl = ITEM_TEMPLATES[obj_vnum(obj)]
            opts.append(tpl["short_descr"])
            names.append(_obj_pick_name(obj))
        if not opts:
            return ""
        idx = pick_from(tr, "Cast the spell on what?", opts)
        if idx < 0:
            return None
        return names[idx]

    if target_type == "obj_char_offensive":
        if player.get("fighting") is not None:
            return ""
        opts = []
        names = []
        for mob_id in rs["mobs"]:
            mob = world["chars"][mob_id]
            opts.append(MOB_TEMPLATES[mob["tpl"]]["short_descr"])
            names.append(_mob_pick_name(mob))
        for obj in rs["items"]:
            tpl = ITEM_TEMPLATES[obj_vnum(obj)]
            opts.append(tpl["short_descr"])
            names.append(_obj_pick_name(obj))
        if not opts:
            return ""
        idx = pick_from(tr, "Cast the spell on whom or what?", opts)
        if idx < 0:
            return None
        return names[idx]

    return ""


def _resolve_item_runtime_target(tr, ch, sn, victim, obj, world):
    """Resolve magical item cast target from explicit victim/obj hints."""
    sk = SKILLS[sn]
    target_type = sk.get("target", "ignore")

    if target_type == "ignore":
        return (None, TARGET_NONE, None, True)
    if target_type == "char_offensive":
        if victim is not None:
            return (victim, TARGET_CHAR, _target_id(ch, victim, world), True)
        victim_id = ch.get("fighting")
        if victim_id is None or victim_id not in world["chars"]:
            return (None, TARGET_NONE, None, False)
        return (world["chars"][victim_id], TARGET_CHAR, victim_id, True)
    if target_type == "char_defensive":
        if victim is None:
            victim = ch
        return (victim, TARGET_CHAR, None, True)
    if target_type == "char_self":
        return (ch, TARGET_CHAR, None, True)
    if target_type == "obj_inventory":
        if obj is None:
            return (None, TARGET_NONE, None, False)
        return (obj, TARGET_OBJ, None, True)
    if target_type == "obj_char_offensive":
        if victim is not None:
            return (victim, TARGET_CHAR, _target_id(ch, victim, world), True)
        if obj is not None:
            return (obj, TARGET_OBJ, None, True)
        victim_id = ch.get("fighting")
        if victim_id is None or victim_id not in world["chars"]:
            return (None, TARGET_NONE, None, False)
        return (world["chars"][victim_id], TARGET_CHAR, victim_id, True)
    if target_type == "obj_char_defensive":
        if victim is not None:
            return (victim, TARGET_CHAR, None, True)
        if obj is not None:
            return (obj, TARGET_OBJ, None, True)
        return (ch, TARGET_CHAR, None, True)
    return (None, TARGET_NONE, None, False)


def _resolve_item_spell_sn(tr, spell_name, item_obj):
    if not spell_name:
        return None
    sn = _skill_lookup(spell_name)
    if sn is None:
        _dev_item_fail(tr, item_obj, "unknown spell '" + spell_name + "'")
        return None
    if not _implemented_spell(sn):
        _dev_item_fail(tr, item_obj, "unimplemented spell '" + spell_name + "'")
        return None
    return sn


def validate_item_spell_payload(tr, item_obj):
    """Validate normalized magical item payload before consume/decrement."""
    tpl = ITEM_TEMPLATES[obj_vnum(item_obj)]
    level = item_spell_level(item_obj, tpl)
    if level is None:
        _dev_item_fail(tr, item_obj, "missing spell_level")
        return None
    payload = []
    if tpl.get("type") in ("wand", "staff"):
        spell_name = item_spell_name(item_obj, tpl)
        if spell_name:
            payload.append(spell_name)
    else:
        payload = item_spells(item_obj, tpl)
    if not payload:
        _dev_item_fail(tr, item_obj, "missing spell payload")
        return None
    for spell_name in payload:
        if _resolve_item_spell_sn(tr, spell_name, item_obj) is None:
            return None
    return (level, payload)


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
        return (world["chars"][victim_id], TARGET_CHAR, victim_id, True)

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
            return (world["chars"][victim_id], TARGET_CHAR, victim_id, True)
        victim_id = _find_room_char_id(player, world, target_name)
        if victim_id is not None:
            return (world["chars"][victim_id], TARGET_CHAR, victim_id, True)
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


def obj_cast_spell(tr, spell_name, level, ch, victim, obj, world, item_obj=None):
    """Cast spell payload from magical item (cf. 1stMud obj_cast_spell in magic.c)."""
    sn = _resolve_item_spell_sn(tr, spell_name, item_obj)
    if sn is None:
        return False
    vo, target, victim_id, ok = _resolve_item_runtime_target(tr, ch, sn, victim, obj, world)
    if not ok:
        return _dev_item_fail(tr, item_obj, "target resolution failed for '" + spell_name + "'")
    fun = SPELL_FUNS.get(SKILLS[sn].get("spell_fun", "spell_null"), spell_null)
    if spell_name:
        ch["_spell_target_name"] = spell_name
    ret = fun(tr, sn, level, ch, vo, target, world)
    if "_spell_target_name" in ch:
        del ch["_spell_target_name"]
    if (ret and SKILLS[sn].get("target") in ("char_offensive", "obj_char_offensive")
            and target == TARGET_CHAR and victim_id is not None
            and victim_id in world["chars"] and ch.get("fighting") is None):
        set_fighting(tr, ch, victim_id, world["chars"])
    return ret


def cast_item_spells(tr, ch, item_obj, victim, obj, world):
    """Run normalized spell payload from magical item instance/template."""
    parsed = validate_item_spell_payload(tr, item_obj)
    if parsed is None:
        return False
    level, payload = parsed
    any_success = False
    for spell_name in payload:
        ret = obj_cast_spell(tr, spell_name, level, ch, victim, obj, world, item_obj)
        any_success = any_success or ret
    return any_success


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

    if not target_name:
        target_name = _pick_cast_target_name(tr, player, sn, world)  # [PRIMESUD] calculator UX extension.
        if target_name is None:
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
    player["_spell_target_name"] = target_name
    ret = fun(tr, sn, _spell_level(player, sn), player, vo, target, world)
    del player["_spell_target_name"]
    check_improve(tr, player, sn, ret, 1)

    if (ret and sk.get("target") in ("char_offensive", "obj_char_offensive")
            and target == TARGET_CHAR and victim_id is not None
            and victim_id in world["chars"]
            and player.get("fighting") is None):
        set_fighting(tr, player, victim_id, world["chars"])
    if not args:
        command = "cast " + _quote_cast_spell_name(SKILLS[sn]["name"])
        if target_name:
            command += " " + target_name
        return command
    return None
