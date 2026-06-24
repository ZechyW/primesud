"""Magic command handling and spell dispatch (cf. 1stMud magic.c)."""

import world
from actor import (is_name, is_affected, affect_to_char, affect_strip, is_awake,
                   can_see_room)
from area_limbo import (I_MUSHROOM, I_BALL_LIGHT, I_SPRING,
                        I_DISC_DISK_FLOATING_BLACK)
from colors import upper
from combat import (WaitState, check_improve, get_skill, set_fighting,
                    damage, stop_fighting, update_pos)
from config import (POS_ORDER, DAM_ACID, DAM_BASH, DAM_COLD,
                    DAM_DISEASE, DAM_DROWNING, DAM_ENERGY, DAM_FIRE,
                    DAM_HARM, DAM_HOLY, DAM_LIGHT, DAM_LIGHTNING,
                    DAM_NEGATIVE, DAM_PIERCE, DAM_POISON, DAM_SLASH)
from config import R_RECALL, MAX_MORTAL_LEVEL
from item import (get_char_room, get_obj_list, obj_vnum, item_spell_level,
                  item_spells, item_spell_name, item_extra_flags,
                  item_current_charges, item_affect_list,
                  item_affect_find, item_affect_remove, item_affect_to_obj,
                  set_item_extra_flag, create_object)
from movement import perform_recall
from picker import pick_from
from scan import do_scan
from skill_utils import can_use_skill_spell, find_skill_spell, spell_mana
from skills_table import SKILLS, SKILL_TABLE
from terminal import tprint
from urandom import randint
from world import ITEM_DEFS, MOB_DEFS, ROOM_DEFS

TARGET_NONE = "none"
TARGET_CHAR = "char"
TARGET_OBJ = "obj"
TARGET_ROOM = "room"
_AC_LOCS = ("ac_pierce", "ac_bash", "ac_slash", "ac_exotic")

def spell_null(sn, level, ch, vo, target):
    """Do nothing spell placeholder (cf. 1stMud spell_null in magic.c)."""
    return False


def _dice(num, size):
    total = 0
    for _ in range(num):
        total += randint(1, size)
    return total


def _heal_char(ch, victim, amount, msg):
    victim["hit"] = min(victim["max_hit"], victim["hit"] + amount)
    if victim is ch:
        tprint(msg)
    else:
        tprint("Ok.")
    return True


def _target_id(ch, victim):
    if victim is None or victim is ch:
        return None
    for mob_id, inst in world.chars.items():
        if inst is victim:
            return mob_id
    return None



def _char_name(ch, victim):
    if victim is ch:
        return "You"
    if victim.get("is_npc"):
        tpl = MOB_DEFS.get(victim.get("tpl"), {})
        return upper(tpl.get("short_descr", "Someone"))
    return upper(victim.get("name", "Someone"))


def _skill_lookup(name):
    for sn, sk in SKILL_TABLE:
        if sk["name"] == name:
            return sn
    return None


def _area_state_for_room(room_vnum):
    tag = ROOM_DEFS.get(room_vnum, {}).get("area")
    if tag is None:
        return None
    for area in world.areas:
        if area.get("tag") == tag:
            return area
    return None


def _spell_tail(ch):
    return ch.get("_spell_target_name", "")


def _item_name(obj):
    if obj is None:
        return "item"
    tpl = ITEM_DEFS.get(obj_vnum(obj), {})
    return tpl.get("short_descr", "item")


def _flag_names(flags):
    names = sorted(flags)
    if not names:
        return "none"
    return " ".join(names)


def _number_fuzzy(n):
    r = randint(0, 3)
    if r == 0:
        n -= 1
    elif r == 3:
        n += 1
    return max(1, n)


def _is_good(ch):
    return ch.get("alignment", 0) > 350


def _is_evil(ch):
    return ch.get("alignment", 0) < -350


def _is_neutral(ch):
    a = ch.get("alignment", 0)
    return a >= -350 and a <= 350


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
    af["where"] = "to_object"
    return af


def _dev_item_fail(obj, message):
    tprint("[DEV] " + _item_name(obj) + ": " + message)
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


def check_dispel(dis_level, victim, sn, ch=None):
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
                tprint(msg)
            return True
        af["level"] = af.get("level", 0) - 1
    return False


def spell_cure_light(sn, level, ch, vo, target):
    """Cure light wounds (cf. 1stMud spell_cure_light in magic.c)."""
    return _heal_char(ch, vo, _dice(1, 8) + level // 3, "You feel better!")


def spell_cure_serious(sn, level, ch, vo, target):
    """Cure serious wounds (cf. 1stMud spell_cure_serious in magic.c)."""
    return _heal_char(ch, vo, _dice(2, 8) + level // 2, "You feel better!")


def spell_cure_critical(sn, level, ch, vo, target):
    """Cure critical wounds (cf. 1stMud spell_cure_critical in magic.c)."""
    return _heal_char(ch, vo, _dice(3, 8) + level - 6, "You feel better!")


def spell_heal(sn, level, ch, vo, target):
    """Heal spell (cf. 1stMud spell_heal in magic.c)."""
    return _heal_char(ch, vo, 100, "A warm feeling fills your body.")


def spell_cause_light(sn, level, ch, vo, target):
    """Cause light wounds (cf. 1stMud spell_cause_light in magic.c)."""
    return damage(ch, vo, _dice(1, 8) + level // 3, sn, DAM_HARM, True)


def spell_cause_serious(sn, level, ch, vo, target):
    """Cause serious wounds (cf. 1stMud spell_cause_serious in magic.c)."""
    return damage(ch, vo, _dice(2, 8) + level // 2, sn, DAM_HARM, True)


def spell_cause_critical(sn, level, ch, vo, target):
    """Cause critical wounds (cf. 1stMud spell_cause_critical in magic.c)."""
    return damage(ch, vo, _dice(3, 8) + level - 6, sn, DAM_HARM, True)


def spell_harm(sn, level, ch, vo, target):
    """Harm spell (cf. 1stMud spell_harm in magic.c)."""
    dam = max(20, vo["hit"] - _dice(1, 4))
    if saves_spell(level, vo, "harm"):
        dam = min(50, dam // 2)
    dam = min(100, dam)
    return damage(ch, vo, dam, sn, DAM_HARM, True)


def spell_magic_missile(sn, level, ch, vo, target):
    """Magic missile (cf. 1stMud spell_magic_missile in magic.c)."""
    high = level | 50
    dam = randint(high // 2, high * 2)
    if saves_spell(level, vo, "energy"):
        dam //= 2
    return damage(ch, vo, dam, sn, DAM_ENERGY, True)


def spell_earthquake(sn, level, ch, vo, target):
    """Earthquake room spell (cf. 1stMud spell_earthquake in magic.c)."""
    tprint("The earth trembles beneath your feet!")
    room = world.rooms[ch["room"]]
    for mob_id in list(room["mobs"]):
        victim = world.chars.get(mob_id)
        if victim is None or victim is ch:
            continue
        dam = 0 if victim.get("affected_by", {}).get("flying") else level + _dice(2, 8)
        damage(ch, victim, dam, sn, DAM_BASH, True)
    return True


def spell_call_lightning(sn, level, ch, vo, target):
    """Call lightning area spell (cf. 1stMud spell_call_lightning in magic.c)."""
    room = ROOM_DEFS[ch["room"]]
    if room.get("flags", {}).get("indoors"):
        tprint("You must be out of doors.")
        return False
    area = _area_state_for_room(ch["room"])
    weather = area.get("weather") if area is not None else None
    if weather is None or weather.get("precip", 0) <= 0:
        tprint("You need bad weather.")
        return False

    dam = _dice(max(1, level // 2), 8)
    tprint("Your lightning strikes your foes!")
    room_state = world.rooms[ch["room"]]
    for mob_id in list(room_state["mobs"]):
        victim = world.chars.get(mob_id)
        if victim is None or victim is ch:
            continue
        cur_dam = dam
        if saves_spell(level, victim, "lightning"):
            cur_dam //= 2
        damage(ch, victim, cur_dam, sn, DAM_LIGHTNING, True)
    return True


def spell_chain_lightning(sn, level, ch, vo, target):
    """Chain lightning room spell (cf. 1stMud spell_chain_lightning in magic.c)."""
    victim = vo
    tprint("A lightning bolt leaps from your hand and arcs to " +
           _char_name(ch, victim) + ".")
    dam = _dice(level, 6)
    if saves_spell(level, victim, "lightning"):
        dam //= 3
    damage(ch, victim, dam, sn, DAM_LIGHTNING, True)
    last_vict = victim
    level -= 4
    room_state = world.rooms[ch["room"]]
    while level > 0:
        found = False
        for mob_id in list(room_state["mobs"]):
            tmp = world.chars.get(mob_id)
            if tmp is None or tmp is last_vict:
                continue
            # [PRIMESUD] is_safe_spell not ported
            found = True
            last_vict = tmp
            tprint("The bolt arcs to " + _char_name(ch, tmp) + "!")
            dam = _dice(level, 6)
            if saves_spell(level, tmp, "lightning"):
                dam //= 3
            damage(ch, tmp, dam, sn, DAM_LIGHTNING, True)
            level -= 4
            break
        if not found:
            if last_vict is ch:
                tprint("The bolt grounds out through your body.")
                return False
            last_vict = ch
            tprint("You are struck by your own lightning!")
            dam = _dice(level, 6)
            if saves_spell(level, ch, "lightning"):
                dam //= 3
            damage(ch, ch, dam, sn, DAM_LIGHTNING, True)
            level -= 4
    return found


def _random_teleport_room(ch):
    rooms = []
    for room_vnum, room in ROOM_DEFS.items():
        flags = room.get("flags", {})
        if flags.get("private") or flags.get("solitary") or flags.get("safe") or flags.get("arena"):
            continue
        if not ch.get("is_npc") and flags.get("law"):
            continue
        rooms.append(room_vnum)
    if not rooms:
        return None
    return rooms[randint(0, len(rooms) - 1)]


def spell_teleport(sn, level, ch, vo, target):
    """Teleport target to random room (cf. 1stMud spell_teleport in magic.c)."""
    victim = vo
    room = ROOM_DEFS.get(victim.get("room"))
    if (room is None
            or room.get("flags", {}).get("no_recall")
            or (victim is not ch and saves_spell(level - 5, victim, "other"))
            or (ch.get("is_npc") is not True and victim.get("fighting") is not None)):
        tprint("You failed.")
        return False
    dest = _random_teleport_room(victim)
    if dest is None:
        tprint("You failed.")
        return False
    old_room = victim["room"]
    victim["room"] = dest
    victim_id = _target_id(ch, victim)
    if victim_id is not None:
        if victim_id in world.rooms.get(old_room, {}).get("mobs", []):
            world.rooms[old_room]["mobs"].remove(victim_id)
        world.rooms[dest]["mobs"].append(victim_id)
    if victim is ch:
        from info import do_look
        do_look(victim, [])
    else:
        tprint(_char_name(ch, victim) + " vanishes!")
    return True


def spell_farsight(sn, level, ch, vo, target):
    """Farsight spell (cf. 1stMud spell_farsight in magic2.c)."""
    if ch.get("affected_by", {}).get("blind"):
        tprint("Maybe it would help if you could see?")
        return False
    do_scan(ch, _spell_tail(ch).split())
    return True


def _iter_world_objects(player):
    for obj in player.get("inv", []):
        yield (obj, "one is carried by you")
    for obj in player.get("equip", {}).values():
        if obj is not None:
            yield (obj, "one is carried by you")
    for room_vnum, room_state in world.rooms.items():
        for obj in room_state.get("items", []):
            yield (obj, "one is in " + ROOM_DEFS.get(room_vnum, {}).get("name", "somewhere"))
    for cid, mob in world.chars.items():
        if not mob.get("is_npc"):
            continue
        mob_name = MOB_DEFS[mob["tpl"]]["short_descr"]
        for obj in mob.get("inv", []):
            yield (obj, "one is carried by " + mob_name)
        for obj in mob.get("equip", {}).values():
            if obj is not None:
                yield (obj, "one is carried by " + mob_name)


def spell_locate_object(sn, level, ch, vo, target):
    """Locate object by name fragment (cf. 1stMud spell_locate_object in magic.c)."""
    wanted = _spell_tail(ch)
    if not wanted:
        tprint("Nothing like that in heaven or earth.")
        return False
    found = []
    max_found = 2 * level
    for obj, line in _iter_world_objects(ch):
        tpl = ITEM_DEFS[obj_vnum(obj)]
        if not is_name(wanted, tpl.get("keywords", "")):
            continue
        if item_extra_flags(obj, tpl).get("no_locate"):
            continue
        if randint(1, 100) > 2 * level:
            continue
        if ch.get("level", 1) < tpl.get("level", 0):
            continue
        found.append(line)
        if len(found) >= max_found:
            break
    if not found:
        tprint("Nothing like that in heaven or earth.")
        return False
    for line in found:
        tprint(line)
    return True


def spell_control_weather(sn, level, ch, vo, target):
    """Adjust simplified interim weather state (cf. 1stMud spell_control_weather in magic.c)."""
    arg = _spell_tail(ch)
    area = _area_state_for_room(ch["room"])
    if area is None:
        tprint("The weather is altered by your magic.")
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
        tprint("Do you want it to get warmer, colder, wetter, drier, windier, or calmer?")
        return False
    if weather["precip_vector"] < -3:
        weather["precip_vector"] = -3
    elif weather["precip_vector"] > 3:
        weather["precip_vector"] = 3
    tprint("The weather is altered by your magic.")
    return True


def spell_word_of_recall(sn, level, ch, vo, target):
    """Word of recall spell (cf. 1stMud spell_word_of_recall in magic.c)."""
    victim = vo if vo is not None else ch
    if victim.get("is_npc"):
        return False
    return perform_recall(victim, R_RECALL, "recall")


def spell_trivia_pill(sn, level, ch, vo, target):
    """Grant one trivia point (cf. 1stMud spell_trivia_pill in magic.c)."""
    victim = vo if vo is not None else ch
    if victim.get("is_npc"):
        return False
    victim["trivia"] = victim.get("trivia", 0) + 1
    tprint("You've gained a Trivia Point!")
    if victim is not ch:
        tprint("Ok.")
    return True


def spell_detect_poison(sn, level, ch, vo, target):
    """Detect poison on object target (cf. 1stMud spell_detect_poison in magic.c)."""
    tpl = ITEM_DEFS[obj_vnum(vo)]
    poisoned = bool(vo.get("poisoned") or tpl.get("poisoned"))
    if tpl.get("type") in ("food", "fountain"):
        tprint("You smell poisonous fumes." if poisoned else "It looks delicious.")
    else:
        tprint("It doesn't look poisoned.")
    return True


def spell_identify(sn, level, ch, vo, target):
    """Identify object details (cf. 1stMud spell_identify in magic.c)."""
    tpl = ITEM_DEFS[obj_vnum(vo)]
    flags = item_extra_flags(vo, tpl)
    tprint("Object '" + tpl.get("keywords", "") + "' is type " + tpl.get("type", "unknown")
             + ", extra flags " + _flag_names(flags) + ".")
    tprint("Weight is " + str(tpl.get("weight", 0)) + ", value is "
             + str(vo.get("cost", tpl.get("value", 0))) + ", level is " + str(tpl.get("level", 0)) + ".")
    if tpl.get("type") in ("scroll", "potion", "pill"):
        spells = item_spells(vo, tpl)
        if spells:
            tprint("Level " + str(item_spell_level(vo, tpl)) + " spells of: '" + "' '".join(spells) + "'.")
    elif tpl.get("type") in ("wand", "staff"):
        line = "Has " + str(item_current_charges(vo, tpl)) + " charges of level " + str(item_spell_level(vo, tpl))
        spell_name = item_spell_name(vo, tpl)
        if spell_name:
            line += " '" + spell_name + "'"
        tprint(line + ".")
    for loc, mod in tpl.get("stat_bonuses", {}).items():
        tprint("Affects " + loc + " by " + str(mod) + ".")
    for af in item_affect_list(vo):
        loc = af.get("location", "none")
        mod = af.get("modifier", 0)
        line = "Affects " + loc + " by " + str(mod)
        if af.get("duration", -1) > -1:
            line += ", " + str(af["duration"]) + " hours."
        else:
            line += "."
        tprint(line)
        bit = af.get("bitvector", "")
        if af.get("where") == "to_object" and bit:
            tprint("Adds " + bit + " object flag.")
    return True


def spell_fireproof(sn, level, ch, vo, target):
    """Fireproof object target (cf. 1stMud spell_fireproof in magic.c)."""
    tpl = ITEM_DEFS[obj_vnum(vo)]
    flags = item_extra_flags(vo, tpl)
    if flags.get("burn_proof"):
        tprint(_item_name(vo) + " is already protected from burning.")
        return False
    item_affect_to_obj(vo, _new_obj_affect(sn, level, max(1, level // 4), "none", 0, "burn_proof"), tpl)
    tprint("You protect " + _item_name(vo) + " from fire.")
    return True


def spell_enchant_armor(sn, level, ch, vo, target):
    """Enchant armor item (cf. 1stMud spell_enchant_armor in magic.c)."""
    tpl = ITEM_DEFS[obj_vnum(vo)]
    if tpl.get("type") != "armor":
        tprint("That isn't an armor.")
        return False
    if not _obj_carried_by(ch, vo):
        tprint("The item must be carried to be enchanted.")
        return False
    if item_extra_flags(vo, tpl).get("quest"):
        tprint("You can't enchant quest items.")
        return False
    fail = 25
    if not vo.get("enchanted"):
        for loc, val in tpl.get("stat_bonuses", {}).items():
            if loc in _AC_LOCS:
                fail += 5 * (val * val)
            else:
                fail += 20
    for af in item_affect_list(vo):
        if af.get("location") in _AC_LOCS:
            fail += 5 * (af.get("modifier", 0) ** 2)
        else:
            fail += 20
    fail -= level
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
        tprint(_item_name(vo) + " flares blindingly... and evaporates!")
        ch["inv"].remove(vo)
        return False
    if result < fail // 3:
        tprint(_item_name(vo) + " glows brightly, then fades...oops.")
        vo["enchanted"] = True
        _clear_item_runtime_affects(vo)
        vo["extra_flags"] = {}
        return False
    if result <= fail:
        tprint("Nothing seemed to happen.")
        return False
    vo["enchanted"] = True
    if result <= (90 - level // 5):
        tprint(_item_name(vo) + " shimmers with a gold aura.")
        set_item_extra_flag(vo, tpl, "magic", True)
        added = -1
    else:
        tprint(_item_name(vo) + " glows a brillant gold!")
        set_item_extra_flag(vo, tpl, "magic", True)
        set_item_extra_flag(vo, tpl, "glow", True)
        added = -2
    vo["level"] = min(50, vo.get("level", tpl.get("level", 0)) + 1)
    _add_obj_ac_affect(vo, tpl, sn, level, added)
    return True


def spell_enchant_weapon(sn, level, ch, vo, target):
    """Enchant weapon item (cf. 1stMud spell_enchant_weapon in magic.c)."""
    tpl = ITEM_DEFS[obj_vnum(vo)]
    if tpl.get("type") != "weapon":
        tprint("That isn't a weapon.")
        return False
    if not _obj_carried_by(ch, vo):
        tprint("The item must be carried to be enchanted.")
        return False
    if item_extra_flags(vo, tpl).get("quest"):
        tprint("You can't enchant quest items.")
        return False
    fail = 25
    hit_found = False
    dam_found = False
    if not vo.get("enchanted"):
        for loc, val in tpl.get("stat_bonuses", {}).items():
            if loc == "hitroll":
                hit_found = True
                fail += 2 * (val * val)
            elif loc == "damroll":
                dam_found = True
                fail += 2 * (val * val)
            else:
                fail += 25
    for af in item_affect_list(vo):
        loc = af.get("location")
        if loc == "hitroll":
            hit_found = True
            fail += 2 * (af.get("modifier", 0) ** 2)
        elif loc == "damroll":
            dam_found = True
            fail += 2 * (af.get("modifier", 0) ** 2)
        else:
            fail += 25
    fail -= 3 * level // 2
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
        tprint(_item_name(vo) + " shivers violently and explodes!")
        ch["inv"].remove(vo)
        return False
    if result < fail // 2:
        tprint(_item_name(vo) + " glows brightly, then fades...oops.")
        vo["enchanted"] = True
        _clear_item_runtime_affects(vo)
        vo["extra_flags"] = {}
        return False
    if result <= fail:
        tprint("Nothing seemed to happen.")
        return False
    vo["enchanted"] = True
    if result <= (100 - level // 5):
        tprint(_item_name(vo) + " glows blue.")
        set_item_extra_flag(vo, tpl, "magic", True)
        added = 1
    else:
        tprint(_item_name(vo) + " glows a brillant blue!")
        set_item_extra_flag(vo, tpl, "magic", True)
        set_item_extra_flag(vo, tpl, "glow", True)
        added = 2
    vo["level"] = min(50, vo.get("level", tpl.get("level", 0)) + 1)
    if dam_found:
        for af in item_affect_list(vo):
            if af.get("location") == "damroll":
                af["type"] = sn
                af["modifier"] = af.get("modifier", 0) + added
                af["level"] = max(af.get("level", 0), level)
                if af["modifier"] > 4:
                    set_item_extra_flag(vo, tpl, "hum", True)
    else:
        item_affect_to_obj(vo, _new_obj_affect(sn, level, -1, "damroll", added), tpl)
    if hit_found:
        for af in item_affect_list(vo):
            if af.get("location") == "hitroll":
                af["type"] = sn
                af["modifier"] = af.get("modifier", 0) + added
                af["level"] = max(af.get("level", 0), level)
                if af["modifier"] > 4:
                    set_item_extra_flag(vo, tpl, "hum", True)
    else:
        item_affect_to_obj(vo, _new_obj_affect(sn, level, -1, "hitroll", added), tpl)
    return True


def _new_affect(sn, level, duration, location, modifier, bitvector=""):
    return {
        "where": "to_affects",
        "type": sn,
        "level": level,
        "duration": duration,
        "location": location,
        "modifier": modifier,
        "bitvector": bitvector,
    }


def spell_armor(sn, level, ch, vo, target):
    """Armor spell (cf. 1stMud spell_armor in magic.c)."""
    if is_affected(vo, sn):
        tprint("You are already armored." if vo is ch else _char_name(ch, vo) + " is already armored.")
        return False
    affect_to_char(vo, _new_affect(sn, level, 24, "ac", -20))
    if vo is ch:
        tprint("You feel someone protecting you.")
    else:
        tprint(_char_name(ch, vo) + " is protected by your magic.")
    return True


def spell_shield(sn, level, ch, vo, target):
    """Shield spell (cf. 1stMud spell_shield in magic.c)."""
    if is_affected(vo, sn):
        tprint("You are already shielded from harm." if vo is ch else _char_name(ch, vo) + " is already protected by a shield.")
        return False
    affect_to_char(vo, _new_affect(sn, level, 8 + level, "ac", -20))
    if vo is ch:
        tprint("You are surrounded by a force shield.")
    else:
        tprint(_char_name(ch, vo) + " is surrounded by a force shield.")
    return True


def spell_bless(sn, level, ch, vo, target):
    """Bless character path (cf. 1stMud spell_bless in magic.c)."""
    if target == TARGET_OBJ:
        tpl = ITEM_DEFS[obj_vnum(vo)]
        flags = item_extra_flags(vo, tpl)
        if flags.get("bless"):
            tprint(_item_name(vo) + " is already blessed.")
            return False
        if flags.get("evil"):
            paf = item_affect_find(vo, _skill_lookup("curse"))
            if not saves_dispel(level, paf.get("level", tpl.get("level", 0)) if paf else tpl.get("level", 0), 0):
                if paf is not None:
                    item_affect_remove(vo, paf, tpl)
                set_item_extra_flag(vo, tpl, "evil", False)
                tprint(_item_name(vo) + " glows a pale blue.")
                return True
            tprint("The evil of " + _item_name(vo) + " is too powerful for you to overcome.")
            return False
        item_affect_to_obj(vo, _new_obj_affect(sn, level, 6 + level, "saves", -1, "bless"), tpl)
        tprint(_item_name(vo) + " glows with a holy aura.")
        # TODO [PRIMESUD] saving_throw adjust for worn blessed items
        return True
    if vo.get("pos") == "fighting" or is_affected(vo, sn):
        tprint("You are already blessed." if vo is ch else _char_name(ch, vo) + " already has divine favor.")
        return False
    mod = level // 8
    affect_to_char(vo, _new_affect(sn, level, 6 + level, "hitroll", mod))
    affect_to_char(vo, _new_affect(sn, level, 6 + level, "saves", -mod))
    if vo is ch:
        tprint("You feel righteous.")
    else:
        tprint("You grant " + _char_name(ch, vo) + " the favor of your god.")
    return True


def spell_giant_strength(sn, level, ch, vo, target):
    """Giant strength spell (cf. 1stMud spell_giant_strength in magic.c)."""
    if is_affected(vo, sn):
        tprint("You are already as strong as you can get!" if vo is ch else _char_name(ch, vo) + " can't get any stronger.")
        return False
    mod = 1 + (level >= 18) + (level >= 25) + (level >= 32)
    affect_to_char(vo, _new_affect(sn, level, level, "str", mod))
    if vo is ch:
        tprint("Your muscles surge with heightened power!")
    else:
        tprint(_char_name(ch, vo) + "'s muscles surge with heightened power.")
    return True


def spell_weaken(sn, level, ch, vo, target):
    """Weaken spell (cf. 1stMud spell_weaken in magic.c)."""
    if is_affected(vo, sn) or saves_spell(level, vo, "other"):
        return False
    affect_to_char(vo, _new_affect(sn, level, level // 2, "str", -1 * (level // 5), "weaken"))
    if vo is ch:
        tprint("You feel your strength slip away.")
    else:
        tprint(_char_name(ch, vo) + " looks tired and weak.")
    return True


def spell_faerie_fire(sn, level, ch, vo, target):
    """Faerie fire spell (cf. 1stMud spell_faerie_fire in magic.c)."""
    if vo.get("affected_by", {}).get("faerie_fire"):
        return False
    affect_to_char(vo, _new_affect(sn, level, level, "ac", 2 * level, "faerie_fire"))
    if vo is ch:
        tprint("You are surrounded by a pink outline.")
    else:
        tprint(_char_name(ch, vo) + " is surrounded by a pink outline.")
    return True


def spell_blindness(sn, level, ch, vo, target):
    """Blindness spell (cf. 1stMud spell_blindness in magic.c)."""
    if vo.get("affected_by", {}).get("blind") or saves_spell(level, vo, "other"):
        tprint("You failed.")
        return False
    affect_to_char(vo, _new_affect(sn, level, 1 + level, "hitroll", -4, "blind"))
    if vo is ch:
        tprint("You are blinded!")
    else:
        tprint(_char_name(ch, vo) + " appears to be blinded.")
    return True


def spell_poison(sn, level, ch, vo, target):
    """Poison character path (cf. 1stMud spell_poison in magic.c)."""
    if target == TARGET_OBJ:
        tprint("That spell does not work on objects yet.")
        return False
    if saves_spell(level, vo, "poison"):
        tprint("You feel momentarily ill, but it passes." if vo is ch else _char_name(ch, vo) + " turns slightly green, but it passes.")
        return False
    affect_to_char(vo, _new_affect(sn, level, level, "str", -2, "poison"))
    if vo is ch:
        tprint("You feel very sick.")
    else:
        tprint(_char_name(ch, vo) + " looks very ill.")
    return True


def spell_curse(sn, level, ch, vo, target):
    """Curse character path (cf. 1stMud spell_curse in magic.c)."""
    if target == TARGET_OBJ:
        tpl = ITEM_DEFS[obj_vnum(vo)]
        flags = item_extra_flags(vo, tpl)
        if flags.get("evil"):
            tprint(_item_name(vo) + " is already filled with evil.")
            return False
        if flags.get("bless"):
            paf = item_affect_find(vo, _skill_lookup("bless"))
            if not saves_dispel(level, paf.get("level", tpl.get("level", 0)) if paf else tpl.get("level", 0), 0):
                if paf is not None:
                    item_affect_remove(vo, paf, tpl)
                set_item_extra_flag(vo, tpl, "bless", False)
                tprint(_item_name(vo) + " glows with a red aura.")
                return True
            tprint("The holy aura of " + _item_name(vo) + " is too powerful for you to overcome.")
            return False
        item_affect_to_obj(vo, _new_obj_affect(sn, level, 2 * level, "saves", 1, "evil"), tpl)
        tprint(_item_name(vo) + " glows with a malevolent aura.")
        # TODO [PRIMESUD] saving_throw adjust for worn cursed items
        return True
    if vo.get("affected_by", {}).get("curse") or saves_spell(level, vo, "negative"):
        return False
    mod = level // 8
    affect_to_char(vo, _new_affect(sn, level, 2 * level, "hitroll", -mod, "curse"))
    affect_to_char(vo, _new_affect(sn, level, 2 * level, "saves", mod))
    if vo is ch:
        tprint("You feel unclean.")
    else:
        tprint(_char_name(ch, vo) + " looks very uncomfortable.")
    return True


def spell_plague(sn, level, ch, vo, target):
    """Plague spell (cf. 1stMud spell_plague in magic.c)."""
    if saves_spell(level, vo, "disease") or (
            vo.get("is_npc") and MOB_DEFS.get(vo.get("tpl"), {}).get("act_flags", {}).get("undead")):
        tprint("You feel momentarily ill, but it passes." if vo is ch else _char_name(ch, vo) + " seems to be unaffected.")
        return False
    affect_to_char(vo, _new_affect(sn, level * 3 // 4, level, "str", -5, "plague"))
    if vo is ch:
        tprint("You scream in agony as plague sores erupt from your skin.")
    else:
        tprint(_char_name(ch, vo) + " screams in agony as plague sores erupt from their skin.")
    return True


def spell_cure_blindness(sn, level, ch, vo, target):
    """Cure blindness (cf. 1stMud spell_cure_blindness in magic.c)."""
    blind_sn = _skill_lookup("blindness")
    if not is_affected(vo, blind_sn):
        tprint("You aren't blind." if vo is ch else _char_name(ch, vo) + " doesn't appear to be blinded.")
        return False
    if check_dispel(level, vo, blind_sn, ch):
        tprint("Your vision returns!" if vo is ch else _char_name(ch, vo) + " is no longer blinded.")
        return True
    tprint("Spell failed.")
    return False


def spell_cure_poison(sn, level, ch, vo, target):
    """Cure poison (cf. 1stMud spell_cure_poison in magic.c)."""
    poison_sn = _skill_lookup("poison")
    if not is_affected(vo, poison_sn):
        tprint("You aren't poisoned." if vo is ch else _char_name(ch, vo) + " doesn't appear to be poisoned.")
        return False
    if check_dispel(level, vo, poison_sn, ch):
        tprint("A warm feeling runs through your body." if vo is ch else _char_name(ch, vo) + " looks much better.")
        return True
    tprint("Spell failed.")
    return False


def spell_cure_disease(sn, level, ch, vo, target):
    """Cure disease (cf. 1stMud spell_cure_disease in magic.c)."""
    plague_sn = _skill_lookup("plague")
    if not is_affected(vo, plague_sn):
        tprint("You aren't ill." if vo is ch else _char_name(ch, vo) + " doesn't appear to be diseased.")
        return False
    if check_dispel(level, vo, plague_sn, ch):
        tprint("Your sores vanish." if vo is ch else _char_name(ch, vo) + " looks relieved as their sores vanish.")
        return True
    tprint("Spell failed.")
    return False


def spell_dispel_magic(sn, level, ch, vo, target):
    """Dispel magic (cf. 1stMud spell_dispel_magic in magic.c)."""
    if saves_spell(level, vo, "other"):
        if vo is ch:
            tprint("You feel a brief tingling sensation.")
        tprint("You failed.")
        return False
    found = False
    for name in ("armor", "bless", "blindness", "calm", "change sex",
                 "charm person", "chill touch", "curse",
                 "detect evil", "detect good", "detect hidden",
                 "detect invis", "detect magic", "faerie fire",
                 "fly", "frenzy", "giant strength", "haste",
                 "infravision", "invis", "mass invis", "pass door",
                 "protection evil", "protection good", "sanctuary",
                 "shield", "sleep", "slow", "stone skin", "weaken",
                 "force shield", "static shield", "flame shield"):
        cur = _skill_lookup(name)
        if cur is not None and check_dispel(level, vo, cur, ch):
            found = True
    sanc_sn = _skill_lookup("sanctuary")
    if (vo.get("affected_by", {}).get("sanctuary")
            and not saves_dispel(level, vo.get("level", 1), -1)
            and not is_affected(vo, sanc_sn)):
        vo.get("affected_by", {}).pop("sanctuary", None)
        found = True
    if found:
        tprint("Ok.")
        return True
    tprint("Spell failed.")
    return False


# ====================================================================
# Remaining spell ports from 1stMud magic.c / magic2.c
# ====================================================================


def spell_acid_blast(sn, level, ch, vo, target):
    """Acid blast (cf. 1stMud spell_acid_blast in magic.c)."""
    dam = _dice(level, 12)
    if saves_spell(level, vo, "acid"):
        dam //= 2
    return damage(ch, vo, dam, sn, DAM_ACID, True)


def spell_burning_hands(sn, level, ch, vo, target):
    """Burning hands (cf. 1stMud spell_burning_hands in magic.c)."""
    high = level | 50
    dam = randint(high // 2, high * 2)
    if saves_spell(level, vo, "fire"):
        dam //= 2
    return damage(ch, vo, dam, sn, DAM_FIRE, True)


def spell_calm(sn, level, ch, vo, target):
    """Calm room occupants (cf. 1stMud spell_calm in magic.c)."""
    room = world.rooms[ch["room"]]
    mlevel = 0
    count = 0
    high_level = 0
    for mob_id in room["mobs"]:
        mob = world.chars.get(mob_id)
        if mob is None:
            continue
        if mob.get("pos") == "fighting":
            count += 1
            if mob.get("is_npc"):
                mlevel += mob.get("level", 1)
            else:
                mlevel += mob.get("level", 1) // 2
            high_level = max(high_level, mob.get("level", 1))
    if ch.get("pos") == "fighting":
        count += 1
        mlevel += ch.get("level", 1) // 2
        high_level = max(high_level, ch.get("level", 1))
    chance = 4 * level - high_level + 2 * count
    if randint(0, chance) < mlevel:
        return False
    found = False
    bail = False
    all_ids = list(room["mobs"])
    for mob_id in all_ids:
        mob = world.chars.get(mob_id)
        if mob is None:
            continue
        if mob.get("is_npc"):
            tpl = MOB_DEFS.get(mob.get("tpl"), {})
            if mob.get("imm_flags", tpl.get("imm_flags", {})).get("magic"):
                bail = True
                break
            if tpl.get("act_flags", {}).get("undead"):
                bail = True
                break
        if mob.get("affected_by", {}).get("calm") or mob.get("affected_by", {}).get("berserk"):
            bail = True
            break
        if is_affected(mob, _skill_lookup("frenzy")):
            bail = True
            break
        found = True
        if mob.get("fighting") is not None or mob.get("pos") == "fighting":
            stop_fighting(mob, False)
        mod = -2 if mob.get("is_npc") else -5
        affect_to_char(mob, _new_affect(sn, level, level // 4, "hitroll", mod, "calm"))
        affect_to_char(mob, _new_affect(sn, level, level // 4, "damroll", mod, "calm"))
    if not bail and not ch.get("is_npc"):
        if not (ch.get("affected_by", {}).get("calm") or ch.get("affected_by", {}).get("berserk")
                or is_affected(ch, _skill_lookup("frenzy"))):
            found = True
            tprint("A wave of calm passes over you.")
            if ch.get("fighting") is not None or ch.get("pos") == "fighting":
                stop_fighting(ch, False)
            affect_to_char(ch, _new_affect(sn, level, level // 4, "hitroll", -5, "calm"))
            affect_to_char(ch, _new_affect(sn, level, level // 4, "damroll", -5, "calm"))
    return found


def spell_cancellation(sn, level, ch, vo, target):
    """Cancellation -- dispel for self/allies (cf. 1stMud spell_cancellation in magic.c)."""
    victim = vo
    level += 2
    if ((not ch.get("is_npc") and victim.get("is_npc")
            and not (ch.get("affected_by", {}).get("charm") and ch.get("master") is victim))
            or (ch.get("is_npc") and not victim.get("is_npc"))):
        tprint("You failed, try dispel magic.")
        return False
    found = False
    for name in ("armor", "bless", "blindness", "calm", "change sex",
                 "charm person", "chill touch", "curse",
                 "detect evil", "detect good", "detect hidden",
                 "detect invis", "detect magic", "faerie fire",
                 "fly", "frenzy", "giant strength", "haste",
                 "infravision", "invis", "mass invis", "pass door",
                 "protection evil", "protection good", "sanctuary",
                 "shield", "sleep", "slow", "stone skin", "weaken",
                 "force shield", "static shield", "flame shield"):
        cur = _skill_lookup(name)
        if cur is not None and check_dispel(level, victim, cur, ch):
            found = True
    if found:
        tprint("Ok.")
    else:
        tprint("Spell failed.")
    return found


def spell_change_sex(sn, level, ch, vo, target):
    """Change sex (cf. 1stMud spell_change_sex in magic.c)."""
    if is_affected(vo, sn):
        tprint("You've already been changed." if vo is ch else _char_name(ch, vo) + " has already had their sex changed.")
        return False
    if saves_spell(level, vo, "other"):
        return False
    cur_sex = vo.get("sex", 0)
    mod = 0
    while mod == 0:
        mod = randint(0, 2) - cur_sex
    affect_to_char(vo, _new_affect(sn, level, 2 * level, "sex", mod))
    tprint("You feel different." if vo is ch else _char_name(ch, vo) + " doesn't look like themselves anymore.")
    return True


def spell_charm_person(sn, level, ch, vo, target):
    """Charm person (cf. 1stMud spell_charm_person in magic.c).

    TODO: follower/master system (add_follower, stop_follower) not yet ported.
    Charm affect applied but follower linkage stubbed.
    """
    victim = vo
    if victim is ch:
        tprint("You like yourself even better!")
        return False
    if (victim.get("affected_by", {}).get("charm")
            or ch.get("affected_by", {}).get("charm")
            or level < victim.get("level", 1)
            or victim.get("imm_flags", {}).get("charm")
            or saves_spell(level, victim, "charm")):
        return False
    room = ROOM_DEFS.get(ch.get("room"))
    if room and room.get("flags", {}).get("law"):
        tprint("The mayor does not allow charming in the city limits.")
        return False
    # TODO [PRIMESUD] follower system: stop_follower(victim); add_follower(victim, ch); victim.leader = ch
    affect_to_char(victim, _new_affect(sn, level, _number_fuzzy(level // 4), "none", 0, "charm"))
    tprint(_char_name(ch, victim) + " looks at you with adoring eyes.")
    return True


def spell_chill_touch(sn, level, ch, vo, target):
    """Chill touch (cf. 1stMud spell_chill_touch in magic.c)."""
    high = level | 50
    dam = randint(high // 2, high * 2)
    if not saves_spell(level, vo, "cold"):
        # 1stMud uses affect_join; affect_to_char used [PRIMESUD]
        affect_to_char(vo, _new_affect(sn, level, 6, "str", -1))
    else:
        dam //= 2
    return damage(ch, vo, dam, sn, DAM_COLD, True)


def spell_color_spray(sn, level, ch, vo, target):
    """Color spray (cf. 1stMud spell_color_spray in magic.c)."""
    high = level | 50
    dam = randint(high // 2, high * 2)
    if saves_spell(level, vo, "light"):
        dam //= 2
    else:
        blind_sn = _skill_lookup("blindness")
        if blind_sn is not None:
            spell_blindness(blind_sn, level // 2, ch, vo, TARGET_CHAR)
    return damage(ch, vo, dam, sn, DAM_LIGHT, True)


def spell_continual_light(sn, level, ch, vo, target):
    """Create light ball or make carried item glow (cf. 1stMud spell_continual_light in magic.c)."""
    tail = _spell_tail(ch)
    if tail:
        obj = _find_inv_obj(ch, tail)
        if obj is None:
            tprint("You don't see that here.")
            return False
        tpl = ITEM_DEFS[obj_vnum(obj)]
        flags = item_extra_flags(obj, tpl)
        if flags.get("glow"):
            tprint(_item_name(obj) + " is already glowing.")
            return False
        set_item_extra_flag(obj, tpl, "glow", True)
        tprint(_item_name(obj) + " glows with a white light.")
        return True
    light = create_object(I_BALL_LIGHT)
    rs = world.rooms[ch["room"]]
    rs.setdefault("items", []).append(light)
    tprint("You twiddle your thumbs and a ball of light appears.")
    return True


def spell_create_food(sn, level, ch, vo, target):
    """Create a mushroom (cf. 1stMud spell_create_food in magic.c)."""
    mushroom = create_object(I_MUSHROOM)
    mushroom["level"] = level // 2 if level // 2 > 0 else 1
    mushroom["food_hours"] = level // 2
    mushroom["timer"] = 24
    rs = world.rooms[ch["room"]]
    rs.setdefault("items", []).append(mushroom)
    tprint("A magic mushroom suddenly appears.")
    return True


def spell_create_rose(sn, level, ch, vo, target):
    """Create a rose (cf. 1stMud spell_create_rose in magic.c).

    TODO: OBJ_VNUM_ROSE template not yet defined in area data.
    """
    # TODO [PRIMESUD] need rose item template
    tprint("A beautiful red rose appears in your hands.")
    return True


def spell_create_spring(sn, level, ch, vo, target):
    """Create a magical spring (cf. 1stMud spell_create_spring in magic.c)."""
    spring = create_object(I_SPRING)
    spring["timer"] = level
    rs = world.rooms[ch["room"]]
    rs.setdefault("items", []).append(spring)
    tprint("A magical spring flows from the ground.")
    return True


def spell_create_water(sn, level, ch, vo, target):
    """Fill drink container with water (cf. 1stMud spell_create_water in magic.c).

    TODO: drink container system not fully ported.
    """
    tpl = ITEM_DEFS[obj_vnum(vo)]
    if tpl.get("type") != "drink_con":
        tprint("It is unable to hold water.")
        return False
    # TODO [PRIMESUD] liquid type / fill level not yet modeled
    tprint("The container fills with water.")
    return True


def spell_demonfire(sn, level, ch, vo, target):
    """Demonfire (cf. 1stMud spell_demonfire in magic.c)."""
    victim = vo
    if not ch.get("is_npc") and not _is_evil(ch):
        victim = ch
        tprint("The demons turn upon you!")
    ch["alignment"] = max(-1000, ch.get("alignment", 0) - 50)
    dam = _dice(level, 10)
    if saves_spell(level, victim, "negative"):
        dam //= 2
    curse_sn = _skill_lookup("curse")
    if curse_sn is not None:
        spell_curse(curse_sn, 3 * level // 4, ch, victim, TARGET_CHAR)
    return damage(ch, victim, dam, sn, DAM_NEGATIVE, True)


def spell_detect_evil(sn, level, ch, vo, target):
    """Detect evil (cf. 1stMud spell_detect_evil in magic.c)."""
    if vo.get("affected_by", {}).get("detect_evil"):
        tprint("You can already sense evil." if vo is ch else _char_name(ch, vo) + " can already detect evil.")
        return False
    affect_to_char(vo, _new_affect(sn, level, level, "none", 0, "detect_evil"))
    tprint("Your eyes tingle." if vo is ch else "Ok.")
    return True


def spell_detect_good(sn, level, ch, vo, target):
    """Detect good (cf. 1stMud spell_detect_good in magic.c)."""
    if vo.get("affected_by", {}).get("detect_good"):
        tprint("You can already sense good." if vo is ch else _char_name(ch, vo) + " can already detect good.")
        return False
    affect_to_char(vo, _new_affect(sn, level, level, "none", 0, "detect_good"))
    tprint("Your eyes tingle." if vo is ch else "Ok.")
    return True


def spell_detect_hidden(sn, level, ch, vo, target):
    """Detect hidden (cf. 1stMud spell_detect_hidden in magic.c)."""
    if vo.get("affected_by", {}).get("detect_hidden"):
        tprint("You are already as alert as you can be." if vo is ch else _char_name(ch, vo) + " can already sense hidden lifeforms.")
        return False
    affect_to_char(vo, _new_affect(sn, level, level, "none", 0, "detect_hidden"))
    tprint("Your awareness improves." if vo is ch else "Ok.")
    return True


def spell_detect_invis(sn, level, ch, vo, target):
    """Detect invis (cf. 1stMud spell_detect_invis in magic.c)."""
    if vo.get("affected_by", {}).get("detect_invis"):
        tprint("You can already see invisible." if vo is ch else _char_name(ch, vo) + " can already see invisible things.")
        return False
    affect_to_char(vo, _new_affect(sn, level, level, "none", 0, "detect_invis"))
    tprint("Your eyes tingle." if vo is ch else "Ok.")
    return True


def spell_detect_magic(sn, level, ch, vo, target):
    """Detect magic (cf. 1stMud spell_detect_magic in magic.c)."""
    if vo.get("affected_by", {}).get("detect_magic"):
        tprint("You can already sense magical auras." if vo is ch else _char_name(ch, vo) + " can already detect magic.")
        return False
    affect_to_char(vo, _new_affect(sn, level, level, "none", 0, "detect_magic"))
    tprint("Your eyes tingle." if vo is ch else "Ok.")
    return True


def spell_dispel_evil(sn, level, ch, vo, target):
    """Dispel evil (cf. 1stMud spell_dispel_evil in magic.c)."""
    victim = vo
    if not ch.get("is_npc") and _is_evil(ch):
        victim = ch
    if _is_good(victim):
        tprint(_char_name(ch, victim) + " is protected.")
        return False
    if _is_neutral(victim):
        tprint(_char_name(ch, victim) + " does not seem to be affected.")
        return False
    if victim.get("hit", 0) > ch.get("level", 1) * 4:
        dam = _dice(level, 4)
    else:
        dam = max(victim.get("hit", 0), _dice(level, 4))
    if saves_spell(level, victim, "holy"):
        dam //= 2
    return damage(ch, victim, dam, sn, DAM_HOLY, True)


def spell_dispel_good(sn, level, ch, vo, target):
    """Dispel good (cf. 1stMud spell_dispel_good in magic.c)."""
    victim = vo
    if not ch.get("is_npc") and _is_good(ch):
        victim = ch
    if _is_evil(victim):
        tprint(_char_name(ch, victim) + " is protected by their evil.")
        return False
    if _is_neutral(victim):
        tprint(_char_name(ch, victim) + " does not seem to be affected.")
        return False
    if victim.get("hit", 0) > ch.get("level", 1) * 4:
        dam = _dice(level, 4)
    else:
        dam = max(victim.get("hit", 0), _dice(level, 4))
    if saves_spell(level, victim, "negative"):
        dam //= 2
    return damage(ch, victim, dam, sn, DAM_NEGATIVE, True)


def spell_energy_drain(sn, level, ch, vo, target):
    """Energy drain (cf. 1stMud spell_energy_drain in magic.c)."""
    victim = vo
    if victim is not ch:
        ch["alignment"] = max(-1000, ch.get("alignment", 0) - 50)
    if saves_spell(level, victim, "negative"):
        tprint("You feel a momentary chill." if victim is ch else "")
        return False
    if victim.get("level", 1) <= 2:
        dam = ch.get("hit", 1) + 1
    else:
        # TODO [PRIMESUD] gain_exp not yet ported
        victim["mana"] = victim.get("mana", 0) // 2
        victim["move"] = victim.get("move", 0) // 2
        dam = _dice(1, level)
        ch["hit"] = ch.get("hit", 0) + dam
    tprint("You feel your life slipping away!" if victim is ch else "Wow....what a rush!")
    damage(ch, victim, dam, sn, DAM_NEGATIVE, True)
    return True


def spell_fireball(sn, level, ch, vo, target):
    """Fireball (cf. 1stMud spell_fireball in magic.c)."""
    high = level | 50
    dam = randint(high // 2, high * 2)
    if saves_spell(level, vo, "fire"):
        dam //= 2
    return damage(ch, vo, dam, sn, DAM_FIRE, True)


def spell_flamestrike(sn, level, ch, vo, target):
    """Flamestrike (cf. 1stMud spell_flamestrike in magic.c)."""
    dam = _dice(6 + level // 2, 8)
    if saves_spell(level, vo, "fire"):
        dam //= 2
    return damage(ch, vo, dam, sn, DAM_FIRE, True)


def spell_faerie_fog(sn, level, ch, vo, target):
    """Faerie fog -- reveal hidden/invisible in room (cf. 1stMud spell_faerie_fog in magic.c)."""
    tprint("You conjure a cloud of purple smoke.")
    room = world.rooms[ch["room"]]
    found = False
    for mob_id in list(room["mobs"]):
        mob = world.chars.get(mob_id)
        if mob is None or mob is ch:
            continue
        if saves_spell(level, mob, "other"):
            continue
        invis_sn = _skill_lookup("invis")
        if invis_sn is not None:
            affect_strip(mob, invis_sn)
        mass_invis_sn = _skill_lookup("mass invis")
        if mass_invis_sn is not None:
            affect_strip(mob, mass_invis_sn)
        sneak_sn = _skill_lookup("sneak")
        if sneak_sn is not None:
            affect_strip(mob, sneak_sn)
        aff = mob.get("affected_by", {})
        aff.pop("hide", None)
        aff.pop("invisible", None)
        aff.pop("sneak", None)
        tprint(_char_name(ch, mob) + " is revealed!")
        found = True
    return found


def spell_floating_disc(sn, level, ch, vo, target):
    """Create a floating disc container (cf. 1stMud spell_floating_disc in magic.c).

    TODO: equip-to-float slot not yet ported; disc added to inventory.
    """
    disc = create_object(I_DISC_DISK_FLOATING_BLACK)
    disc["timer"] = ch.get("level", 1) * 2 - randint(0, level // 2)
    ch.setdefault("inv", []).append(disc)
    tprint("You create a floating disc.")
    # TODO [PRIMESUD] auto-equip to float slot: wear_obj(ch, disc, True)
    return True


def spell_fly(sn, level, ch, vo, target):
    """Fly spell (cf. 1stMud spell_fly in magic.c)."""
    if vo.get("affected_by", {}).get("flying"):
        tprint("You are already airborne." if vo is ch else _char_name(ch, vo) + " doesn't need your help to fly.")
        return False
    affect_to_char(vo, _new_affect(sn, level, level + 3, "none", 0, "flying"))
    tprint("Your feet rise off the ground." if vo is ch else _char_name(ch, vo) + "'s feet rise off the ground.")
    return True


def spell_frenzy(sn, level, ch, vo, target):
    """Frenzy spell (cf. 1stMud spell_frenzy in magic.c)."""
    if is_affected(vo, sn) or vo.get("affected_by", {}).get("berserk"):
        tprint("You are already in a frenzy." if vo is ch else _char_name(ch, vo) + " is already in a frenzy.")
        return False
    calm_sn = _skill_lookup("calm")
    if calm_sn is not None and is_affected(vo, calm_sn):
        tprint("Why don't you just relax for a while?" if vo is ch else _char_name(ch, vo) + " doesn't look like they want to fight anymore.")
        return False
    if ((_is_good(ch) and not _is_good(vo))
            or (_is_neutral(ch) and not _is_neutral(vo))
            or (_is_evil(ch) and not _is_evil(vo))):
        tprint("Your god doesn't seem to like " + _char_name(ch, vo) + ".")
        return False
    mod = level // 6
    affect_to_char(vo, _new_affect(sn, level, level // 3, "hitroll", mod))
    affect_to_char(vo, _new_affect(sn, level, level // 3, "damroll", mod))
    affect_to_char(vo, _new_affect(sn, level, level // 3, "ac", 10 * (level // 12)))
    tprint("You are filled with holy wrath!" if vo is ch else _char_name(ch, vo) + " gets a wild look in their eyes!")
    return True


def spell_gate(sn, level, ch, vo, target):
    """Gate to another character's location (cf. 1stMud spell_gate in magic.c)."""
    tail = _spell_tail(ch)
    if not tail:
        tprint("You failed.")
        return False

    # get_char_world: search all loaded chars by name.
    # In PrimeSUD there are no other PCs, so this covers all NPCs in the world.
    victim = None
    if _is_self_name(ch, tail):
        victim = ch
    else:
        for _c in world.chars.values():
            if _c is ch:
                continue
            if _c.get("is_npc"):
                _tpl = MOB_DEFS.get(_c.get("tpl"), {})
                if is_name(tail, _tpl.get("keywords", "")):
                    victim = _c
                    break

    if victim is None or victim is ch:
        tprint("You failed.")
        return False

    victim_vnum = victim.get("room")
    if victim_vnum is None:
        tprint("You failed.")
        return False

    src_flags = ROOM_DEFS.get(ch.get("room"), {}).get("flags", {})
    dst_flags = ROOM_DEFS.get(victim_vnum, {}).get("flags", {})

    if (not can_see_room(ch, victim_vnum)
            or dst_flags.get("safe")
            # TODO [PRIMESUD] arena flag not yet implemented
            or src_flags.get("no_recall")
            or dst_flags.get("no_recall")
            or dst_flags.get("private")
            or dst_flags.get("solitary")
            # TODO [PRIMESUD] clan check (is_clan/is_same_clan) not yet ported
            # TODO [PRIMESUD] gquest mob check (is_gqmob) not yet ported
            # TODO [PRIMESUD] quester pcdata.quest.mob check not yet ported
            or victim.get("level", 0) >= level + 3
            or (not victim.get("is_npc") and victim.get("level", 0) >= MAX_MORTAL_LEVEL)
            or (victim.get("is_npc") and victim.get("imm_flags", {}).get("summon"))
            or (victim.get("is_npc") and saves_spell(level, victim, "other"))):
        tprint("You failed.")
        return False

    # TODO [PRIMESUD] pet teleport not yet implemented
    tprint("You step through a gate and vanish.")
    ch["room"] = victim_vnum
    # act("$n has arrived through a gate.", ..., TO_ROOM) omitted -- single-player
    from info import do_look
    do_look(ch, [])
    return True


def spell_haste(sn, level, ch, vo, target):
    """Haste spell (cf. 1stMud spell_haste in magic.c)."""
    if is_affected(vo, sn) or vo.get("affected_by", {}).get("haste") or vo.get("off_flags", {}).get("fast"):
        tprint("You can't move any faster!" if vo is ch else _char_name(ch, vo) + " is already moving as fast as they can.")
        return False
    if vo.get("affected_by", {}).get("slow"):
        slow_sn = _skill_lookup("slow")
        if slow_sn is not None and not check_dispel(level, vo, slow_sn, ch):
            if vo is not ch:
                tprint("Spell failed.")
            tprint("You feel momentarily faster.")
            return False
        return False
    dur = level // 2 if vo is ch else level // 4
    mod = 1 + (level >= 18) + (level >= 25) + (level >= 32)
    affect_to_char(vo, _new_affect(sn, level, dur, "dex", mod, "haste"))
    tprint("You feel yourself moving more quickly." if vo is ch else _char_name(ch, vo) + " is moving more quickly.")
    if ch is not vo:
        tprint("Ok.")
    return True


def spell_heat_metal(sn, level, ch, vo, target):
    """Heat metal (cf. 1stMud spell_heat_metal in magic.c).

    TODO: equipment drop/sear mechanic requires full equipment iteration.
    Simplified to flat damage based on level.
    """
    victim = vo
    if saves_spell(level + 2, victim, "fire") or victim.get("imm_flags", {}).get("fire"):
        tprint("Your spell had no effect.")
        return False
    dam = _dice(level // 2, 8)
    if saves_spell(level, victim, "fire"):
        dam = 2 * dam // 3
    tprint("You sear " + _char_name(ch, victim) + " with heat!")
    # TODO [PRIMESUD] full equipment iteration and drop/sear mechanic
    return damage(ch, victim, dam, sn, DAM_FIRE, True)


def spell_holy_word(sn, level, ch, vo, target):
    """Holy word (cf. 1stMud spell_holy_word in magic.c)."""
    tprint("You utter a word of divine power.")
    bless_sn = _skill_lookup("bless")
    curse_sn = _skill_lookup("curse")
    frenzy_sn = _skill_lookup("frenzy")
    room = world.rooms[ch["room"]]
    for mob_id in list(room["mobs"]):
        mob = world.chars.get(mob_id)
        if mob is None:
            continue
        if ((_is_good(ch) and _is_good(mob))
                or (_is_evil(ch) and _is_evil(mob))
                or (_is_neutral(ch) and _is_neutral(mob))):
            if frenzy_sn is not None:
                spell_frenzy(frenzy_sn, level, ch, mob, TARGET_CHAR)
            if bless_sn is not None:
                spell_bless(bless_sn, level, ch, mob, TARGET_CHAR)
        elif (_is_good(ch) and _is_evil(mob)) or (_is_evil(ch) and _is_good(mob)):
            # [PRIMESUD] is_safe_spell not ported
            if curse_sn is not None:
                spell_curse(curse_sn, level, ch, mob, TARGET_CHAR)
            # 1stmud: chprintln(vch, ...) — message to victim only
            # if _is_pc(mob):
            #     tprint("You are struck down!")
            dam = _dice(level, 6)
            damage(ch, mob, dam, sn, DAM_ENERGY, True)
        elif _is_neutral(ch):
            # [PRIMESUD] is_safe_spell not ported
            if curse_sn is not None:
                spell_curse(curse_sn, level // 2, ch, mob, TARGET_CHAR)
            # if _is_pc(mob):
            #     tprint("You are struck down!")
            dam = _dice(level, 4)
            damage(ch, mob, dam, sn, DAM_ENERGY, True)
    tprint("You feel drained.")
    ch["move"] = 0
    ch["hit"] = ch.get("hit", 1) // 2
    return True


def spell_infravision(sn, level, ch, vo, target):
    """Infravision (cf. 1stMud spell_infravision in magic.c)."""
    if vo.get("affected_by", {}).get("infrared"):
        tprint("You can already see in the dark." if vo is ch else _char_name(ch, vo) + " already has infravision.")
        return False
    affect_to_char(vo, _new_affect(sn, level, 2 * level, "none", 0, "infrared"))
    tprint("Your eyes glow red.")
    return True


def spell_invis(sn, level, ch, vo, target):
    """Invisibility (cf. 1stMud spell_invis in magic.c)."""
    if target == TARGET_OBJ:
        tpl = ITEM_DEFS[obj_vnum(vo)]
        flags = item_extra_flags(vo, tpl)
        if flags.get("invis"):
            tprint(_item_name(vo) + " is already invisible.")
            return False
        item_affect_to_obj(vo, _new_obj_affect(sn, level, level + 12, "none", 0, "invis"), tpl)
        tprint(_item_name(vo) + " fades out of sight.")
        return True
    if vo.get("affected_by", {}).get("invisible"):
        return False
    affect_to_char(vo, _new_affect(sn, level, level + 12, "none", 0, "invisible"))
    tprint("You fade out of existence." if vo is ch else _char_name(ch, vo) + " fades out of existence.")
    return True


def spell_know_alignment(sn, level, ch, vo, target):
    """Know alignment (cf. 1stMud spell_know_alignment in magic.c)."""
    ap = vo.get("alignment", 0)
    if ap > 700:
        msg = "has a pure and good aura."
    elif ap > 350:
        msg = "is of excellent moral character."
    elif ap > 100:
        msg = "is often kind and thoughtful."
    elif ap > -100:
        msg = "doesn't have a firm moral commitment."
    elif ap > -350:
        msg = "lies to their friends."
    elif ap > -700:
        msg = "is a black-hearted murderer."
    else:
        msg = "is the embodiment of pure evil!"
    tprint(_char_name(ch, vo) + " " + msg)
    return True


def spell_lightning_bolt(sn, level, ch, vo, target):
    """Lightning bolt (cf. 1stMud spell_lightning_bolt in magic.c)."""
    high = level | 50
    dam = randint(high // 2, high * 2)
    if saves_spell(level, vo, "lightning"):
        dam //= 2
    return damage(ch, vo, dam, sn, DAM_LIGHTNING, True)


def spell_mass_healing(sn, level, ch, vo, target):
    """Mass healing (cf. 1stMud spell_mass_healing in magic.c)."""
    heal_sn = _skill_lookup("heal")
    refresh_sn = _skill_lookup("refresh")
    if heal_sn is not None:
        spell_heal(heal_sn, level, ch, ch, TARGET_CHAR)
    if refresh_sn is not None:
        spell_refresh(refresh_sn, level, ch, ch, TARGET_CHAR)
    # [PRIMESUD] single-player: only heal player (1stMud heals same-type chars)
    return True


def spell_mass_invis(sn, level, ch, vo, target):
    """Mass invis (cf. 1stMud spell_mass_invis in magic.c).

    TODO: group system not ported. Applies invis to caster only.
    """
    if ch.get("affected_by", {}).get("invisible"):
        tprint("You are already invisible.")
        return True
    tprint("You slowly fade out of existence.")
    affect_to_char(ch, _new_affect(sn, level // 2, 24, "none", 0, "invisible"))
    tprint("Ok.")
    return True


def spell_pass_door(sn, level, ch, vo, target):
    """Pass door (cf. 1stMud spell_pass_door in magic.c)."""
    if vo.get("affected_by", {}).get("pass_door"):
        tprint("You are already out of phase." if vo is ch else _char_name(ch, vo) + " is already shifted out of phase.")
        return False
    affect_to_char(vo, _new_affect(sn, level, _number_fuzzy(level // 4), "none", 0, "pass_door"))
    tprint("You turn translucent." if vo is ch else _char_name(ch, vo) + " turns translucent.")
    return True


def spell_protection_evil(sn, level, ch, vo, target):
    """Protection from evil (cf. 1stMud spell_protection_evil in magic.c)."""
    if vo.get("affected_by", {}).get("protect_evil") or vo.get("affected_by", {}).get("protect_good"):
        tprint("You are already protected." if vo is ch else _char_name(ch, vo) + " is already protected.")
        return False
    affect_to_char(vo, _new_affect(sn, level, 24, "saves", -1, "protect_evil"))
    tprint("You feel holy and pure." if vo is ch else _char_name(ch, vo) + " is protected from evil.")
    return True


def spell_protection_good(sn, level, ch, vo, target):
    """Protection from good (cf. 1stMud spell_protection_good in magic.c)."""
    if vo.get("affected_by", {}).get("protect_good") or vo.get("affected_by", {}).get("protect_evil"):
        tprint("You are already protected." if vo is ch else _char_name(ch, vo) + " is already protected.")
        return False
    affect_to_char(vo, _new_affect(sn, level, 24, "saves", -1, "protect_good"))
    tprint("You feel aligned with darkness." if vo is ch else _char_name(ch, vo) + " is protected from good.")
    return True


def spell_ray_of_truth(sn, level, ch, vo, target):
    """Ray of truth (cf. 1stMud spell_ray_of_truth in magic.c)."""
    victim = vo
    if _is_evil(ch):
        victim = ch
        tprint("The energy explodes inside you!")
    if _is_good(victim):
        tprint("The light seems powerless to affect " + _char_name(ch, victim) + ".")
        return False
    dam = _dice(level, 10)
    if saves_spell(level, victim, "holy"):
        dam //= 2
    align = victim.get("alignment", 0) - 350
    if align < -1000:
        align = -1000 + (align + 1000) // 3
    dam = (dam * align * align) // 1000000
    damage(ch, victim, dam, sn, DAM_HOLY, True)
    blind_sn = _skill_lookup("blindness")
    if blind_sn is not None:
        spell_blindness(blind_sn, 3 * level // 4, ch, victim, TARGET_CHAR)
    return True


def spell_recharge(sn, level, ch, vo, target):
    """Recharge wand/staff (cf. 1stMud spell_recharge in magic.c)."""
    tpl = ITEM_DEFS[obj_vnum(vo)]
    if tpl.get("type") not in ("wand", "staff"):
        tprint("That item does not carry charges.")
        return False
    spell_lvl = tpl.get("spell_level", 0)
    if spell_lvl >= 3 * level // 2:
        tprint("Your skills are not great enough for that.")
        return False
    max_ch = vo.get("max_charges", tpl.get("max_charges", 0))
    cur_ch = vo.get("charges", tpl.get("charges", 0))
    if max_ch == 0:
        tprint("That item has already been recharged once.")
        return False
    chance = 40 + 2 * level - spell_lvl
    used = max_ch - cur_ch
    chance -= used * used
    chance = max(level // 2, chance)
    pct = randint(1, 100)
    if pct < chance // 2:
        tprint(_item_name(vo) + " glows softly.")
        vo["charges"] = max(max_ch, cur_ch)
        vo["max_charges"] = 0
        return True
    if pct <= chance:
        tprint(_item_name(vo) + " glows softly.")
        chargeback = max(1, used * pct // 100) if used > 0 else 0
        vo["charges"] = cur_ch + chargeback
        vo["max_charges"] = 0
        return True
    if pct <= min(95, 3 * chance // 2):
        tprint("Nothing seems to happen.")
        if max_ch > 1:
            vo["max_charges"] = max_ch - 1
        return False
    tprint(_item_name(vo) + " glows brightly and explodes!")
    if vo in ch.get("inv", []):
        ch["inv"].remove(vo)
    return False


def spell_refresh(sn, level, ch, vo, target):
    """Refresh movement (cf. 1stMud spell_refresh in magic.c)."""
    vo["move"] = min(vo.get("move", 0) + level, vo.get("max_move", 100))
    if vo.get("max_move", 100) == vo.get("move", 0):
        tprint("You feel fully refreshed!" if vo is ch else "Ok.")
    else:
        tprint("You feel less tired." if vo is ch else "Ok.")
    return True


def spell_remove_curse(sn, level, ch, vo, target):
    """Remove curse (cf. 1stMud spell_remove_curse in magic.c)."""
    if target == TARGET_OBJ:
        tpl = ITEM_DEFS[obj_vnum(vo)]
        flags = item_extra_flags(vo, tpl)
        if flags.get("nodrop") or flags.get("noremove"):
            if not flags.get("nouncurse") and not saves_dispel(level + 2, tpl.get("level", 0), 0):
                set_item_extra_flag(vo, tpl, "nodrop", False)
                set_item_extra_flag(vo, tpl, "noremove", False)
                tprint(_item_name(vo) + " glows blue.")
                return True
            tprint("The curse on " + _item_name(vo) + " is beyond your power.")
            return False
        tprint("There doesn't seem to be a curse on " + _item_name(vo) + ".")
        return False
    curse_sn = _skill_lookup("curse")
    found = False
    if curse_sn is not None and check_dispel(level, vo, curse_sn, ch):
        tprint("You feel better." if vo is ch else _char_name(ch, vo) + " looks more relaxed.")
        found = True
    for obj in list(vo.get("inv", [])):
        tpl = ITEM_DEFS[obj_vnum(obj)]
        flags = item_extra_flags(obj, tpl)
        if (flags.get("nodrop") or flags.get("noremove")) and not flags.get("nouncurse"):
            if not saves_dispel(level, tpl.get("level", 0), 0):
                set_item_extra_flag(obj, tpl, "nodrop", False)
                set_item_extra_flag(obj, tpl, "noremove", False)
                tprint("Your " + _item_name(obj) + " glows blue.")
                found = True
                break
    return found


def spell_sanctuary(sn, level, ch, vo, target):
    """Sanctuary (cf. 1stMud spell_sanctuary in magic.c)."""
    if vo.get("affected_by", {}).get("sanctuary"):
        tprint("You are already in sanctuary." if vo is ch else _char_name(ch, vo) + " is already in sanctuary.")
        return False
    affect_to_char(vo, _new_affect(sn, level, level // 6, "none", 0, "sanctuary"))
    tprint("You are surrounded by a white aura." if vo is ch else _char_name(ch, vo) + " is surrounded by a white aura.")
    return True


def spell_shocking_grasp(sn, level, ch, vo, target):
    """Shocking grasp (cf. 1stMud spell_shocking_grasp in magic.c)."""
    high = level | 50
    dam = randint(high // 2, high * 2)
    if saves_spell(level, vo, "lightning"):
        dam //= 2
    return damage(ch, vo, dam, sn, DAM_LIGHTNING, True)


def spell_sleep(sn, level, ch, vo, target):
    """Sleep spell (cf. 1stMud spell_sleep in magic.c)."""
    if (vo.get("affected_by", {}).get("sleep")
            or (level + 2) < vo.get("level", 1)
            or saves_spell(level - 4, vo, "charm")):
        return False
    # 1stMud uses affect_join; affect_to_char used [PRIMESUD]
    affect_to_char(vo, _new_affect(sn, level, 4 + level, "none", 0, "sleep"))
    if is_awake(vo):
        tprint("You feel very sleepy ..... zzzzzz." if vo is ch else _char_name(ch, vo) + " goes to sleep.")
        vo["pos"] = "sleeping"
    return True


def spell_slow(sn, level, ch, vo, target):
    """Slow spell (cf. 1stMud spell_slow in magic.c)."""
    if is_affected(vo, sn) or vo.get("affected_by", {}).get("slow"):
        tprint("You can't move any slower!" if vo is ch else _char_name(ch, vo) + " can't get any slower than that.")
        return False
    if saves_spell(level, vo, "other") or vo.get("imm_flags", {}).get("magic"):
        if vo is not ch:
            tprint("Nothing seemed to happen.")
        tprint("You feel momentarily lethargic." if vo is ch else "")
        return False
    if vo.get("affected_by", {}).get("haste"):
        haste_sn = _skill_lookup("haste")
        if haste_sn is not None and not check_dispel(level, vo, haste_sn, ch):
            if vo is not ch:
                tprint("Spell failed.")
            tprint("You feel momentarily slower." if vo is ch else "")
            return False
        return True
    mod = -1 - (level >= 18) - (level >= 25) - (level >= 32)
    affect_to_char(vo, _new_affect(sn, level, level // 2, "dex", mod, "slow"))
    tprint("You feel yourself slowing d o w n..." if vo is ch else _char_name(ch, vo) + " starts to move in slow motion.")
    return True


def spell_stone_skin(sn, level, ch, vo, target):
    """Stone skin (cf. 1stMud spell_stone_skin in magic.c)."""
    if is_affected(ch, sn):
        tprint("Your skin is already as hard as a rock." if vo is ch else _char_name(ch, vo) + " is already as hard as can be.")
        return False
    affect_to_char(vo, _new_affect(sn, level, level, "ac", -40))
    tprint("Your skin turns to stone." if vo is ch else _char_name(ch, vo) + "'s skin turns to stone.")
    return True


def spell_summon(sn, level, ch, vo, target):
    """Summon (cf. 1stMud spell_summon in magic.c).

    TODO: world-wide char search not ported. PrimeSUD is single-player.
    """
    # TODO [PRIMESUD] get_char_world for cross-room summoning
    tprint("You failed.")
    return False


def spell_ventriloquate(sn, level, ch, vo, target):
    """Ventriloquate (cf. 1stMud spell_ventriloquate in magic.c)."""
    tail = _spell_tail(ch)
    parts = tail.split(None, 1)
    if len(parts) < 2:
        tprint("What do you want to make who say?")
        return False
    speaker = parts[0]
    message = parts[1]
    room = world.rooms[ch["room"]]
    found = False
    for mob_id in room["mobs"]:
        mob = world.chars.get(mob_id)
        if mob is None:
            continue
        tpl = MOB_DEFS.get(mob.get("tpl"), {})
        if is_name(speaker, tpl.get("keywords", "")) and is_awake(mob):
            if saves_spell(level, mob, "other"):
                tprint("Someone makes " + speaker + " say '" + message + "'.")
            else:
                tprint(upper(speaker) + " says '" + message + "'.")
            found = True
    return found


# -- Breath weapons (cf. 1stMud magic.c) --
# Note: *_effect functions (acid_effect, fire_effect, cold_effect,
# shock_effect, poison_effect) are environmental item-damage effects
# not yet ported.  Damage is applied; environmental effects are TODO.


def spell_acid_breath(sn, level, ch, vo, target):
    """Acid breath (cf. 1stMud spell_acid_breath in magic.c)."""
    victim = vo
    tprint("You spit acid at " + _char_name(ch, victim) + ".")
    hpch = max(12, ch.get("hit", 12))
    hp_dam = randint(hpch // 11 + 1, hpch // 6)
    dice_dam = _dice(level, 16)
    dam = max(hp_dam + dice_dam // 10, dice_dam + hp_dam // 10)
    if saves_spell(level, victim, "acid"):
        # TODO [PRIMESUD] acid_effect(victim, level/2, dam/4, TARGET_CHAR)
        dam //= 2
    # else: TODO acid_effect(victim, level, dam, TARGET_CHAR)
    return damage(ch, victim, dam, sn, DAM_ACID, True)


def spell_fire_breath(sn, level, ch, vo, target):
    """Fire breath -- area effect (cf. 1stMud spell_fire_breath in magic.c)."""
    victim = vo
    tprint("You breathe forth a cone of fire.")
    hpch = max(10, ch.get("hit", 10))
    hp_dam = randint(hpch // 9 + 1, hpch // 5)
    dice_dam = _dice(level, 20)
    dam = max(hp_dam + dice_dam // 10, dice_dam + hp_dam // 10)
    # TODO [PRIMESUD] fire_effect(room, level, dam/2, TARGET_ROOM)
    room = world.rooms[ch["room"]]
    found = False
    for mob_id in list(room["mobs"]):
        vch = world.chars.get(mob_id)
        if vch is None or vch is ch:
            continue
        found = True
        if vch is victim:
            cur_dam = dam // 2 if saves_spell(level, vch, "fire") else dam
        else:
            cur_dam = dam // 4 if saves_spell(level - 2, vch, "fire") else dam // 2
        damage(ch, vch, cur_dam, sn, DAM_FIRE, True)
    return found


def spell_frost_breath(sn, level, ch, vo, target):
    """Frost breath -- area effect (cf. 1stMud spell_frost_breath in magic.c)."""
    victim = vo
    tprint("You breathe out a cone of frost.")
    hpch = max(12, ch.get("hit", 12))
    hp_dam = randint(hpch // 11 + 1, hpch // 6)
    dice_dam = _dice(level, 16)
    dam = max(hp_dam + dice_dam // 10, dice_dam + hp_dam // 10)
    # TODO [PRIMESUD] cold_effect(room, level, dam/2, TARGET_ROOM)
    room = world.rooms[ch["room"]]
    found = False
    for mob_id in list(room["mobs"]):
        vch = world.chars.get(mob_id)
        if vch is None or vch is ch:
            continue
        found = True
        if vch is victim:
            cur_dam = dam // 2 if saves_spell(level, vch, "cold") else dam
        else:
            cur_dam = dam // 4 if saves_spell(level - 2, vch, "cold") else dam // 2
        damage(ch, vch, cur_dam, sn, DAM_COLD, True)
    return found


def spell_gas_breath(sn, level, ch, vo, target):
    """Gas breath -- area poison (cf. 1stMud spell_gas_breath in magic.c)."""
    tprint("You breathe out a cloud of poisonous gas.")
    hpch = max(16, ch.get("hit", 16))
    hp_dam = randint(hpch // 15 + 1, 8)
    dice_dam = _dice(level, 12)
    dam = max(hp_dam + dice_dam // 10, dice_dam + hp_dam // 10)
    # TODO [PRIMESUD] poison_effect(room, level, dam, TARGET_ROOM)
    room = world.rooms[ch["room"]]
    found = False
    for mob_id in list(room["mobs"]):
        vch = world.chars.get(mob_id)
        if vch is None or vch is ch:
            continue
        found = True
        if saves_spell(level, vch, "poison"):
            cur_dam = dam // 2
        else:
            cur_dam = dam
        damage(ch, vch, cur_dam, sn, DAM_POISON, True)
    return found


def spell_lightning_breath(sn, level, ch, vo, target):
    """Lightning breath (cf. 1stMud spell_lightning_breath in magic.c)."""
    victim = vo
    tprint("You breathe a bolt of lightning at " + _char_name(ch, victim) + ".")
    hpch = max(10, ch.get("hit", 10))
    hp_dam = randint(hpch // 9 + 1, hpch // 5)
    dice_dam = _dice(level, 20)
    dam = max(hp_dam + dice_dam // 10, dice_dam + hp_dam // 10)
    if saves_spell(level, victim, "lightning"):
        # TODO [PRIMESUD] shock_effect(victim, level/2, dam/4, TARGET_CHAR)
        dam //= 2
    # else: TODO shock_effect(victim, level, dam, TARGET_CHAR)
    return damage(ch, victim, dam, sn, DAM_LIGHTNING, True)


def spell_general_purpose(sn, level, ch, vo, target):
    """General purpose (cf. 1stMud spell_general_purpose in magic.c)."""
    dam = randint(25, 100)
    if saves_spell(level, vo, "pierce"):
        dam //= 2
    return damage(ch, vo, dam, sn, DAM_PIERCE, True)


def spell_high_explosive(sn, level, ch, vo, target):
    """High explosive (cf. 1stMud spell_high_explosive in magic.c)."""
    dam = randint(30, 120)
    if saves_spell(level, vo, "pierce"):
        dam //= 2
    return damage(ch, vo, dam, sn, DAM_PIERCE, True)


# -- magic2.c spells --


def spell_portal(sn, level, ch, vo, target):
    """Create a portal to another location (cf. 1stMud spell_portal in magic2.c).

    TODO: world-wide char search and portal object placement not fully ported.
    """
    # TODO [PRIMESUD] get_char_world, warp stone component, portal creation
    tprint("You failed.")
    return False


def spell_nexus(sn, level, ch, vo, target):
    """Create a two-way portal (cf. 1stMud spell_nexus in magic2.c).

    TODO: world-wide char search and portal object placement not fully ported.
    """
    # TODO [PRIMESUD] similar to portal but creates portals in both rooms
    tprint("You failed.")
    return False


def spell_forceshield(sn, level, ch, vo, target):
    """Force shield (cf. 1stMud spell_forceshield in magic2.c)."""
    if is_affected(vo, sn):
        tprint("You are already force-shielded." if vo is ch else _char_name(ch, vo) + " is already force-shielded.")
        return False
    affect_to_char(vo, _new_affect(sn, level, level // 4, "ac", (level // 5) * -1, "force_shield"))
    tprint("You are encircled by a sparkling force-shield." if vo is ch else "A sparkling force-shield encircles " + _char_name(ch, vo) + ".")
    return True


def spell_staticshield(sn, level, ch, vo, target):
    """Static shield (cf. 1stMud spell_staticshield in magic2.c)."""
    if is_affected(vo, sn):
        tprint("You are surrounded by static charge." if vo is ch else _char_name(ch, vo) + " is already surrounded by static charge.")
        return False
    affect_to_char(vo, _new_affect(sn, level, level // 3, "ac", (level // 4) * -1, "static_shield"))
    tprint("You are surrounded by a pulse of static charge." if vo is ch else _char_name(ch, vo) + " is surrounded by a pulse of static charge.")
    return True


def spell_flameshield(sn, level, ch, vo, target):
    """Flame shield (cf. 1stMud spell_flameshield in magic2.c)."""
    if is_affected(vo, sn):
        tprint("You are already protected by fire." if vo is ch else _char_name(ch, vo) + " is already protected by fire.")
        return False
    affect_to_char(vo, _new_affect(sn, level, level // 10, "ac", (level // 2) * -1, "flame_shield"))
    tprint("You are shielded by red walls of flame." if vo is ch else _char_name(ch, vo) + " is shielded by red walls of flame.")
    return True


def spell_channel(sn, level, ch, vo, target):
    """Channel mana to another (cf. 1stMud spell_channel in magic2.c)."""
    if vo is ch:
        tprint("You cannot channel energy into yourself.")
        return False
    heal = _dice(3, 3) + (level // 3) * 2
    vo["mana"] = min(vo.get("mana", 0) + heal, vo.get("max_mana", 100))
    tprint("A swirling cloud of energy slips from your fingertips.")
    return True


def spell_investiture(sn, level, ch, vo, target):
    """Convert movement to mana (cf. 1stMud spell_investiture in magic2.c).

    [PRIMESUD] Skipped -- move/max_move not ported. Function kept for
    reference; not wired into spell dispatch table.
    """
    heal = ch.get("move", 0)
    vo["mana"] = min(vo.get("mana", 0) + heal, vo.get("max_mana", 100))
    vo["move"] = 0
    update_pos(vo)
    tprint("{cThe forces of the earth fill you with energy!{x")
    # 1stMud: act("$n draws magic from the very earth!", ..., TO_ROOM)
    # [PRIMESUD] single-user, no room audience
    return True


def spell_powerstorm(sn, level, ch, vo, target):
    """Powerstorm area damage (cf. 1stMud spell_powerstorm in magic2.c)."""
    tprint("A fiery blaze of magic engulfs the room!")
    room = world.rooms[ch["room"]]
    found = False
    for mob_id in list(room["mobs"]):
        vch = world.chars.get(mob_id)
        if vch is None or vch is ch:
            continue
        # [PRIMESUD] is_safe_spell not ported
        dam = level // 3 * 2 + _dice(20, 20)
        damage(ch, vch, dam, sn, DAM_FIRE, True)
        found = True
    return found


def spell_mana_burn(sn, level, ch, vo, target):
    """Mana burn (cf. 1stMud spell_mana_burn in magic2.c)."""
    dam = _dice(level, 13)
    if saves_spell(level, vo, "fire"):
        dam //= 2
    # TODO [PRIMESUD] fire_effect(victim, level/2, dam/10, TARGET_CHAR)
    return damage(ch, vo, dam, sn, DAM_FIRE, True)


def spell_bark_skin(sn, level, ch, vo, target):
    """Bark skin (cf. 1stMud spell_bark_skin in magic2.c)."""
    if is_affected(vo, sn):
        tprint("Your skin is already covered in bark." if vo is ch else _char_name(ch, vo) + "'s skin is already bark.")
        return False
    affect_to_char(vo, _new_affect(sn, level, level // 3, "ac", -30 - level // 5))
    tprint("Your skin becomes as tough as bark." if vo is ch else _char_name(ch, vo) + "'s skin becomes as tough as bark.")
    return True


def spell_spell_mantle(sn, level, ch, vo, target):
    """Spell mantle (cf. 1stMud spell_spell_mantle in magic2.c)."""
    if is_affected(vo, sn):
        tprint("You are already protected against magic." if vo is ch else _char_name(ch, vo) + " is already protected.")
        return False
    affect_to_char(vo, _new_affect(sn, level, level // 3, "saves", 1 - level // 6))
    tprint("You are surrounded by a glowing spell mantle." if vo is ch else _char_name(ch, vo) + " is surrounded by a glowing spell mantle.")
    return True


def spell_animal_instinct(sn, level, ch, vo, target):
    """Animal instinct (cf. 1stMud spell_animal_instinct in magic2.c)."""
    if is_affected(vo, sn):
        tprint("You are already animalistic." if vo is ch else _char_name(ch, vo) + " is already animalistic.")
        return False
    affect_to_char(vo, _new_affect(sn, level, level // 2, "str", level // 25))
    affect_to_char(vo, _new_affect(sn, level, level // 2, "damroll", level // 20))
    tprint("You suddenly look like a wild beast!" if vo is ch else _char_name(ch, vo) + " suddenly grows fangs and claws!")
    return True


def spell_chaos_flare(sn, level, ch, vo, target):
    """Chaos flare -- random buff/debuff (cf. 1stMud spell_chaos_flare in magic2.c)."""
    if is_affected(vo, sn):
        tprint("You are already touched by chaos." if vo is ch else _char_name(ch, vo) + " is already touched by chaos.")
        return False
    rnum = randint(1, 100)
    if rnum <= 5:
        affect_to_char(vo, _new_affect(sn, level, level // 3, "ac", -30 - level // 5))
        tprint("Glinting scales form over your skin!")
    elif rnum <= 15:
        affect_to_char(vo, _new_affect(sn, level, level // 3, "damroll", level // 20))
        tprint("Sharp spikes jut out of your skin!")
    elif rnum <= 25:
        affect_to_char(vo, _new_affect(sn, level, level // 3, "hitroll", level // 20))
        tprint("Your eyes gleam.")
    elif rnum <= 35:
        affect_to_char(vo, _new_affect(sn, level, level // 3, "move", level * 2))
        tprint("You suddenly grow an extra set of legs!")
    elif rnum <= 45:
        affect_to_char(vo, _new_affect(sn, level, level // 3, "con", level // 20))
        tprint("You grow much tougher!")
    elif rnum <= 50:
        affect_to_char(vo, _new_affect(sn, level, level // 3, "damroll", level // 4))
        tprint("{YA blaze of light surrounds you!{x")
    elif rnum <= 65:
        affect_to_char(vo, _new_affect(sn, level, level // 3, "dex", 1 - level // 20))
        tprint("One of your arms suddenly turns into a flipper.")
    elif rnum <= 75:
        affect_to_char(vo, _new_affect(sn, level, level // 3, "int", 1 - level // 20))
        tprint("Me say wah? You suddenly feel very stoopid.")
    elif rnum <= 85:
        affect_to_char(vo, _new_affect(sn, level, level // 3, "hit", level * 3))
        tprint("You grow two sizes bigger!")
    elif rnum <= 95:
        affect_to_char(vo, _new_affect(sn, level, level // 3, "ac", 1 + level * 2))
        tprint("You suddenly feel quite vulnerable. They're all out to get you!")
    else:
        affect_to_char(vo, _new_affect(sn, level, level // 3, "damroll", 1 - level))
        tprint("{cAck! You turn into an oozing gelatinous blob!")
    return True


def spell_wild_magic(sn, level, ch, vo, target):
    """Wild magic -- random damage type (cf. 1stMud spell_wild_magic in magic2.c).

    Structure mirrors 1stMud exactly: each branch saves, halves dam, deals
    damage, then applies elemental effect, then early-returns.
    """
    dam = _dice(level * 3 // 2, 14)
    numba = randint(1, 100)
    if numba <= 10:
        if saves_spell(level, vo, "acid"):
            dam //= 2
        damage(ch, vo, dam, sn, DAM_ACID, True)
        # TODO [PRIMESUD] acid_effect(vo, level, dam, TARGET_CHAR)
        return True
    if numba <= 20:
        if saves_spell(level, vo, "fire"):
            dam //= 2
        damage(ch, vo, dam, sn, DAM_FIRE, True)
        # TODO [PRIMESUD] fire_effect(vo, level, dam, TARGET_CHAR)
        return True
    if numba <= 30:
        if saves_spell(level, vo, "lightning"):
            dam //= 2
        damage(ch, vo, dam, sn, DAM_LIGHTNING, True)
        # TODO [PRIMESUD] shock_effect(vo, level, dam, TARGET_CHAR)
        return True
    if numba <= 40:
        if saves_spell(level, vo, "cold"):
            dam //= 2
        damage(ch, vo, dam, sn, DAM_COLD, True)
        # TODO [PRIMESUD] cold_effect(vo, level, dam, TARGET_CHAR)
        return True
    if numba <= 50:
        if saves_spell(level, vo, "holy"):
            dam //= 2
        damage(ch, vo, dam, sn, DAM_HOLY, True)
        return True
    if numba <= 60:
        if saves_spell(level, vo, "light"):
            dam //= 2
        damage(ch, vo, dam, sn, DAM_LIGHT, True)
        return True
    if numba <= 70:
        if saves_spell(level, vo, "drowning"):
            dam //= 2
        damage(ch, vo, dam, sn, DAM_DROWNING, True)
        return True
    if numba <= 80:
        if saves_spell(level, vo, "disease"):
            dam //= 2
        damage(ch, vo, dam, sn, DAM_DISEASE, True)
        return True
    if numba <= 90:
        if saves_spell(level, vo, "slash"):
            dam //= 2
        damage(ch, vo, dam, sn, DAM_SLASH, True)
        return True
    # numba <= 100: negative -- saves halves FIRST, then /5, then all four effects
    if saves_spell(level, vo, "negative"):
        dam //= 2
    dam //= 5
    damage(ch, vo, dam, sn, DAM_NEGATIVE, True)
    # TODO [PRIMESUD] acid_effect(vo, level, dam, TARGET_CHAR)
    # TODO [PRIMESUD] fire_effect(vo, level, dam, TARGET_CHAR)
    # TODO [PRIMESUD] cold_effect(vo, level, dam, TARGET_CHAR)
    # TODO [PRIMESUD] shock_effect(vo, level, dam, TARGET_CHAR)
    return True


SPELL_FUNS = {
    "spell_acid_blast": spell_acid_blast,
    "spell_acid_breath": spell_acid_breath,
    "spell_animal_instinct": spell_animal_instinct,
    "spell_armor": spell_armor,
    "spell_bark_skin": spell_bark_skin,
    "spell_bless": spell_bless,
    "spell_blindness": spell_blindness,
    "spell_burning_hands": spell_burning_hands,
    "spell_call_lightning": spell_call_lightning,
    "spell_calm": spell_calm,
    "spell_cancellation": spell_cancellation,
    "spell_cause_critical": spell_cause_critical,
    "spell_cause_light": spell_cause_light,
    "spell_cause_serious": spell_cause_serious,
    "spell_chain_lightning": spell_chain_lightning,
    "spell_change_sex": spell_change_sex,
    "spell_channel": spell_channel,
    "spell_chaos_flare": spell_chaos_flare,
    "spell_charm_person": spell_charm_person,
    "spell_chill_touch": spell_chill_touch,
    "spell_color_spray": spell_color_spray,
    "spell_continual_light": spell_continual_light,
    "spell_control_weather": spell_control_weather,
    "spell_create_food": spell_create_food,
    "spell_create_rose": spell_create_rose,
    "spell_create_spring": spell_create_spring,
    "spell_create_water": spell_create_water,
    "spell_cure_blindness": spell_cure_blindness,
    "spell_cure_critical": spell_cure_critical,
    "spell_cure_disease": spell_cure_disease,
    "spell_cure_light": spell_cure_light,
    "spell_cure_poison": spell_cure_poison,
    "spell_cure_serious": spell_cure_serious,
    "spell_curse": spell_curse,
    "spell_demonfire": spell_demonfire,
    "spell_detect_evil": spell_detect_evil,
    "spell_detect_good": spell_detect_good,
    "spell_detect_hidden": spell_detect_hidden,
    "spell_detect_invis": spell_detect_invis,
    "spell_detect_magic": spell_detect_magic,
    "spell_detect_poison": spell_detect_poison,
    "spell_dispel_evil": spell_dispel_evil,
    "spell_dispel_good": spell_dispel_good,
    "spell_dispel_magic": spell_dispel_magic,
    "spell_earthquake": spell_earthquake,
    "spell_enchant_armor": spell_enchant_armor,
    "spell_enchant_weapon": spell_enchant_weapon,
    "spell_energy_drain": spell_energy_drain,
    "spell_faerie_fire": spell_faerie_fire,
    "spell_faerie_fog": spell_faerie_fog,
    "spell_farsight": spell_farsight,
    "spell_fireball": spell_fireball,
    "spell_fire_breath": spell_fire_breath,
    "spell_fireproof": spell_fireproof,
    "spell_flameshield": spell_flameshield,
    "spell_flamestrike": spell_flamestrike,
    "spell_floating_disc": spell_floating_disc,
    "spell_fly": spell_fly,
    "spell_forceshield": spell_forceshield,
    "spell_frenzy": spell_frenzy,
    "spell_frost_breath": spell_frost_breath,
    "spell_gas_breath": spell_gas_breath,
    "spell_gate": spell_gate,
    "spell_general_purpose": spell_general_purpose,
    "spell_giant_strength": spell_giant_strength,
    "spell_harm": spell_harm,
    "spell_haste": spell_haste,
    "spell_heal": spell_heal,
    "spell_heat_metal": spell_heat_metal,
    "spell_high_explosive": spell_high_explosive,
    "spell_holy_word": spell_holy_word,
    "spell_identify": spell_identify,
    "spell_infravision": spell_infravision,
    # "spell_investiture": spell_investiture,  # [PRIMESUD] move not ported
    "spell_invis": spell_invis,
    "spell_know_alignment": spell_know_alignment,
    "spell_lightning_bolt": spell_lightning_bolt,
    "spell_lightning_breath": spell_lightning_breath,
    "spell_locate_object": spell_locate_object,
    "spell_magic_missile": spell_magic_missile,
    "spell_mana_burn": spell_mana_burn,
    "spell_mass_healing": spell_mass_healing,
    "spell_mass_invis": spell_mass_invis,
    "spell_nexus": spell_nexus,
    "spell_pass_door": spell_pass_door,
    "spell_plague": spell_plague,
    "spell_poison": spell_poison,
    "spell_portal": spell_portal,
    "spell_powerstorm": spell_powerstorm,
    "spell_protection_evil": spell_protection_evil,
    "spell_protection_good": spell_protection_good,
    "spell_ray_of_truth": spell_ray_of_truth,
    "spell_recharge": spell_recharge,
    "spell_refresh": spell_refresh,
    "spell_remove_curse": spell_remove_curse,
    "spell_sanctuary": spell_sanctuary,
    "spell_shield": spell_shield,
    "spell_shocking_grasp": spell_shocking_grasp,
    "spell_sleep": spell_sleep,
    "spell_slow": spell_slow,
    "spell_spell_mantle": spell_spell_mantle,
    "spell_staticshield": spell_staticshield,
    "spell_stone_skin": spell_stone_skin,
    "spell_summon": spell_summon,
    "spell_teleport": spell_teleport,
    "spell_trivia_pill": spell_trivia_pill,
    "spell_ventriloquate": spell_ventriloquate,
    "spell_weaken": spell_weaken,
    "spell_wild_magic": spell_wild_magic,
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


def _room_state(player):
    return world.rooms[player["room"]]


def _find_room_char(player, target_name):
    if _is_self_name(player, target_name):
        return player
    rs = _room_state(player)
    mob_id = get_char_room(target_name, rs["mobs"], world.chars)
    if mob_id is None:
        return None
    return world.chars[mob_id]


def _find_room_char_id(player, target_name):
    rs = _room_state(player)
    return get_char_room(target_name, rs["mobs"], world.chars)


def _find_inv_obj(player, target_name):
    return get_obj_list(target_name, player["inv"], ITEM_DEFS)


def _find_room_obj(player, target_name):
    rs = _room_state(player)
    return get_obj_list(target_name, rs["items"], ITEM_DEFS)


def _mob_pick_name(mob):
    tpl = MOB_DEFS[mob["tpl"]]
    words = tpl.get("keywords", "").split()
    if words:
        return words[0]
    words = tpl.get("short_descr", "").split()
    if words:
        return words[0]
    return ""


def _obj_pick_name(obj):
    tpl = ITEM_DEFS[obj_vnum(obj)]
    words = tpl.get("keywords", "").split()
    if words:
        return words[0]
    words = tpl.get("short_descr", "").split()
    if words:
        return words[0]
    return ""


def _pick_cast_target_name(player, sn):
    """Pick missing spell target for PrimeSUD command UI."""
    sk = SKILLS[sn]
    target_type = sk.get("target", "ignore")
    rs = _room_state(player)

    if target_type == "char_offensive":
        if player.get("fighting") is not None:
            return ""
        opts = []
        names = []
        for mob_id in rs["mobs"]:
            mob = world.chars[mob_id]
            opts.append(MOB_DEFS[mob["tpl"]]["short_descr"])
            names.append(_mob_pick_name(mob))
        if not opts:
            return ""
        idx = pick_from("Cast the spell on whom?", opts)
        if idx < 0:
            return None
        return names[idx]

    if target_type == "obj_inventory":
        opts = []
        names = []
        for obj in player["inv"]:
            tpl = ITEM_DEFS[obj_vnum(obj)]
            opts.append(tpl["short_descr"])
            names.append(_obj_pick_name(obj))
        if not opts:
            return ""
        idx = pick_from("Cast the spell on what?", opts)
        if idx < 0:
            return None
        return names[idx]

    if target_type == "obj_char_offensive":
        if player.get("fighting") is not None:
            return ""
        opts = []
        names = []
        for mob_id in rs["mobs"]:
            mob = world.chars[mob_id]
            opts.append(MOB_DEFS[mob["tpl"]]["short_descr"])
            names.append(_mob_pick_name(mob))
        for obj in rs["items"]:
            tpl = ITEM_DEFS[obj_vnum(obj)]
            opts.append(tpl["short_descr"])
            names.append(_obj_pick_name(obj))
        if not opts:
            return ""
        idx = pick_from("Cast the spell on whom or what?", opts)
        if idx < 0:
            return None
        return names[idx]

    return ""


def _resolve_item_runtime_target(ch, sn, victim, obj):
    """Resolve magical item cast target from explicit victim/obj hints."""
    sk = SKILLS[sn]
    target_type = sk.get("target", "ignore")

    if target_type == "ignore":
        return (None, TARGET_NONE, None, True)
    if target_type == "char_offensive":
        if victim is not None:
            return (victim, TARGET_CHAR, _target_id(ch, victim), True)
        victim_id = ch.get("fighting")
        if victim_id is None or victim_id not in world.chars:
            return (None, TARGET_NONE, None, False)
        return (world.chars[victim_id], TARGET_CHAR, victim_id, True)
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
            return (victim, TARGET_CHAR, _target_id(ch, victim), True)
        if obj is not None:
            return (obj, TARGET_OBJ, None, True)
        victim_id = ch.get("fighting")
        if victim_id is None or victim_id not in world.chars:
            return (None, TARGET_NONE, None, False)
        return (world.chars[victim_id], TARGET_CHAR, victim_id, True)
    if target_type == "obj_char_defensive":
        if victim is not None:
            return (victim, TARGET_CHAR, None, True)
        if obj is not None:
            return (obj, TARGET_OBJ, None, True)
        return (ch, TARGET_CHAR, None, True)
    return (None, TARGET_NONE, None, False)


def _resolve_item_spell_sn(spell_name, item_obj):
    if not spell_name:
        return None
    sn = _skill_lookup(spell_name)
    if sn is None:
        _dev_item_fail(item_obj, "unknown spell '" + spell_name + "'")
        return None
    if not _implemented_spell(sn):
        _dev_item_fail(item_obj, "unimplemented spell '" + spell_name + "'")
        return None
    return sn


def validate_item_spell_payload(item_obj):
    """Validate normalized magical item payload before consume/decrement."""
    tpl = ITEM_DEFS[obj_vnum(item_obj)]
    level = item_spell_level(item_obj, tpl)
    if level is None:
        _dev_item_fail(item_obj, "missing spell_level")
        return None
    payload = []
    if tpl.get("type") in ("wand", "staff"):
        spell_name = item_spell_name(item_obj, tpl)
        if spell_name:
            payload.append(spell_name)
    else:
        payload = item_spells(item_obj, tpl)
    if not payload:
        _dev_item_fail(item_obj, "missing spell payload")
        return None
    for spell_name in payload:
        if _resolve_item_spell_sn(spell_name, item_obj) is None:
            return None
    return (level, payload)


def _resolve_target(player, sn, target_name):
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
                tprint("Cast the spell on whom?")
                return (None, TARGET_NONE, None, False)
        else:
            victim_id = _find_room_char_id(player, target_name)
            if victim_id is None:
                tprint("They aren't here.")
                return (None, TARGET_NONE, None, False)
        return (world.chars[victim_id], TARGET_CHAR, victim_id, True)

    if target_type == "char_defensive":
        if not arg2:
            return (player, TARGET_CHAR, None, True)
        victim = _find_room_char(player, target_name)
        if victim is None:
            tprint("They aren't here.")
            return (None, TARGET_NONE, None, False)
        return (victim, TARGET_CHAR, None, True)

    if target_type == "char_self":
        if arg2 and not _is_self_name(player, target_name):
            tprint("You cannot cast this spell on another.")
            return (None, TARGET_NONE, None, False)
        return (player, TARGET_CHAR, None, True)

    if target_type == "obj_inventory":
        if not arg2:
            tprint("What should the spell be cast upon?")
            return (None, TARGET_NONE, None, False)
        obj = _find_inv_obj(player, target_name)
        if obj is None:
            tprint("You are not carrying that.")
            return (None, TARGET_NONE, None, False)
        return (obj, TARGET_OBJ, None, True)

    if target_type == "obj_char_offensive":
        victim_id = None
        if not arg2:
            victim_id = player.get("fighting")
            if victim_id is None:
                tprint("Cast the spell on whom or what?")
                return (None, TARGET_NONE, None, False)
            return (world.chars[victim_id], TARGET_CHAR, victim_id, True)
        victim_id = _find_room_char_id(player, target_name)
        if victim_id is not None:
            return (world.chars[victim_id], TARGET_CHAR, victim_id, True)
        obj = _find_room_obj(player, target_name)
        if obj is not None:
            return (obj, TARGET_OBJ, None, True)
        tprint("You don't see that here.")
        return (None, TARGET_NONE, None, False)

    if target_type == "obj_char_defensive":
        if not arg2:
            return (player, TARGET_CHAR, None, True)
        victim = _find_room_char(player, target_name)
        if victim is not None:
            return (victim, TARGET_CHAR, None, True)
        obj = _find_inv_obj(player, target_name)
        if obj is not None:
            return (obj, TARGET_OBJ, None, True)
        tprint("You don't see that here.")
        return (None, TARGET_NONE, None, False)

    return (None, TARGET_NONE, None, False)


def _spell_level(player, sn):
    """Return cast level for classless PrimeSUD (cf. 1stMud do_cast in magic.c)."""
    return player.get("level", 1)  # [PRIMESUD] no class system or has_spells() penalty.


def obj_cast_spell(spell_name, level, ch, victim, obj, item_obj=None):
    """Cast spell payload from magical item (cf. 1stMud obj_cast_spell in magic.c)."""
    sn = _resolve_item_spell_sn(spell_name, item_obj)
    if sn is None:
        return False
    vo, target, victim_id, ok = _resolve_item_runtime_target(ch, sn, victim, obj)
    if not ok:
        return _dev_item_fail(item_obj, "target resolution failed for '" + spell_name + "'")
    fun = SPELL_FUNS.get(SKILLS[sn].get("spell_fun", "spell_null"), spell_null)
    if spell_name:
        ch["_spell_target_name"] = spell_name
    ret = fun(sn, level, ch, vo, target)
    if "_spell_target_name" in ch:
        del ch["_spell_target_name"]
    if (ret and SKILLS[sn].get("target") in ("char_offensive", "obj_char_offensive")
            and target == TARGET_CHAR and victim_id is not None
            and victim_id in world.chars and ch.get("fighting") is None):
        set_fighting(ch, world.chars[victim_id])
    return ret


def cast_item_spells(ch, item_obj, victim, obj):
    """Run normalized spell payload from magical item instance/template."""
    parsed = validate_item_spell_payload(item_obj)
    if parsed is None:
        return False
    level, payload = parsed
    any_success = False
    for spell_name in payload:
        ret = obj_cast_spell(spell_name, level, ch, victim, obj, item_obj)
        any_success = any_success or ret
    return any_success


def do_cast(player, args):
    """Cast a spell through 1stMud-style command flow (cf. 1stMud do_cast in magic.c)."""
    if not args:
        known = _known_runtime_spells(player)
        if not known:
            tprint("You know no spells.")
            return None
        names = [sk["name"] for _, sk in known]
        idx = pick_from("Cast which spell?",
                        names)  # [PRIMESUD] calculator UX extension.
        if idx < 0:
            return None
        sn = known[idx][0]
        target_name = ""
    else:
        sn, target_name = _parse_spell_args(player, args)

    if (sn is None or not _implemented_spell(sn)
            or not can_use_skill_spell(player, sn)
            or player.get("learned", {}).get(sn, 0) == 0):
        tprint("You don't know any spells of that name.")
        return None

    sk = SKILLS[sn]
    if POS_ORDER[player["pos"]] < POS_ORDER[sk["min_pos"]]:
        tprint("You can't concentrate enough.")
        return None

    if not target_name:
        target_name = _pick_cast_target_name(player, sn)  # [PRIMESUD] calculator UX extension.
        if target_name is None:
            return None

    vo, target, victim_id, ok = _resolve_target(player, sn, target_name)
    if not ok:
        return None

    mana = spell_mana(player, sn)
    if player["mana"] < mana:
        tprint("You don't have enough mana.")
        return None

    WaitState(player, sk.get("beats", 0))

    if randint(1, 100) > get_skill(player, sn):
        tprint("You lost your concentration.")
        check_improve(player, sn, False, 1)
        player["mana"] -= mana // 2
        return None

    player["mana"] -= mana
    fun = SPELL_FUNS.get(sk.get("spell_fun", "spell_null"), spell_null)
    player["_spell_target_name"] = target_name
    ret = fun(sn, _spell_level(player, sn), player, vo, target)
    del player["_spell_target_name"]
    check_improve(player, sn, ret, 1)

    if (ret and sk.get("target") in ("char_offensive", "obj_char_offensive")
            and target == TARGET_CHAR and victim_id is not None
            and victim_id in world.chars
            and player.get("fighting") is None):
        set_fighting(player, world.chars[victim_id])
    if not args:
        command = "cast " + _quote_cast_spell_name(SKILLS[sn]["name"])
        if target_name:
            command += " " + target_name
        return command
    return None
