"""Magic command handling and spell dispatch (cf. 1stMud magic.c)."""

import world
from handler import (is_name, is_affected, affect_to_char, affect_join, affect_strip, is_awake,
                   can_see_room, act, chprintln, get_char_room,
                   TO_CHAR, TO_ROOM, TO_VICT, TO_NOTVICT, TO_ALL,
                   is_good, is_evil, is_neutral)
from world import (I_MUSHROOM, I_BALL_LIGHT, I_SPRING,
                   I_DISC_DISK_FLOATING_BLACK)
from colors import upper
from classes import has_spells
from combat import (is_safe, is_safe_spell, check_immune, dice, number_fuzzy,
                    multi_hit, damage, stop_fighting, update_pos)
from skill_utils import WaitState, check_improve, get_skill
from config import (POS_ORDER, DAM_ACID, DAM_BASH, DAM_CHARM, DAM_COLD,
                    DAM_DISEASE, DAM_DROWNING, DAM_ENERGY, DAM_FIRE,
                    DAM_HARM, DAM_HOLY, DAM_LIGHT, DAM_LIGHTNING,
                    DAM_NEGATIVE, DAM_OTHER, DAM_PIERCE, DAM_POISON,
                    DAM_SLASH, IS_IMMUNE, IS_RESISTANT, IS_VULNERABLE)
from config import R_RECALL, MAX_MORTAL_LEVEL
from item import (get_obj_list, obj_vnum, item_spell_level,
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
def _enchant_copy_template(vo, tpl):
    """Copy template stat_bonuses to runtime affect_list before enchant (cf. 1stMud enchant_armor/weapon in magic.c)."""
    for loc, mod in tpl.get("stat_bonuses", {}).items():
        item_affect_to_obj(vo, _new_obj_affect("", 0, -1, loc, mod), tpl)

def spell_null(sn, level, ch, vo, target):
    """Do nothing spell placeholder (cf. 1stMud spell_null in magic.c).
    [Verified: 03/07/2026]"""
    chprintln(ch, "That's not a spell!")
    return False


def _heal_char(ch, victim, amount, msg):
    """Heal victim by amount, clamped to max_hit, and print message. [PRIMESUD]
    [Verified: 03/07/2026]

    Inlines the pattern repeated across spell_cure_light / spell_heal / etc.
    in 1stMud magic.c (hit = Min(hit + amount, max_hit); update_pos; message;
    "Ok." to caster when healing another).
    """
    victim["hit"] = min(victim["max_hit"], victim["hit"] + amount)
    update_pos(victim)
    chprintln(victim, msg)
    if victim is not ch:
        chprintln(ch, "Ok.")
    return True




def _skill_lookup(name):
    """Look up a skill/spell by exact name and return its sn (cf. 1stMud `skill_lookup` in magic.c).
    [Verified: 03/07/2026]

    [PRIMESUD] 1stMud prefix-matches; exact match kept here since all callers
    pass full internal names (avoids earlier-table prefix collisions).
    """
    for sn, sk in SKILL_TABLE:
        if sk["name"] == name:
            return sn
    return None


def _area_state_for_room(room_vnum):
    """Return the area state dict for a room's area tag, or None. [PRIMESUD]
    [Verified: 03/07/2026]"""
    tag = ROOM_DEFS.get(room_vnum, {}).get("area")
    if tag is None:
        return None
    for area in world.areas:
        if area.get("tag") == tag:
            return area
    return None



def _item_name(obj):
    """Return the short description of an item, or 'item' if None. [PRIMESUD]
    [Verified: 03/07/2026]"""
    if obj is None:
        return "item"
    tpl = ITEM_DEFS.get(obj_vnum(obj), {})
    return tpl.get("short_descr", "item")









def _new_obj_affect(sn, level, duration, location, modifier, bitvector=""):
    """Create a new affect dict targeting an object. [PRIMESUD]
    [Verified: 03/07/2026]

    Same fields as _new_affect but with where="to_object" (cf. 1stMud
    TO_OBJECT in handler.h, used by affect_to_obj in handler.c).
    """
    af = _new_affect(sn, level, duration, location, modifier, bitvector)
    af["where"] = "to_object"
    return af


def _dev_item_fail(obj, message):
    """Log a dev-mode item failure message and return False. [PRIMESUD]
    [Verified: 03/07/2026]"""
    tprint("[DEV] " + _item_name(obj) + ": " + message)
    return False


def saves_spell(level, victim, dam_type):
    """Return True when victim saves against spell (cf. 1stMud saves_spell in magic.c).
    [Verified: 03/07/2026]"""
    save = 50 + (victim.get("level", 1) - level) * 5 - victim.get("saving_throw", 0) * 2
    if victim.get("affected_by", {}).get("berserk"):
        save += victim.get("level", 1) // 2

    res = check_immune(victim, dam_type)
    if res == IS_IMMUNE:
        return True
    if res == IS_RESISTANT:
        save += 2
    elif res == IS_VULNERABLE:
        save -= 2

    if not victim.get("is_npc") and has_spells(victim):
        save = 9 * save // 10
    if save < 5:
        save = 5
    elif save > 95:
        save = 95
    return randint(1, 100) < save


def saves_dispel(dis_level, spell_level, duration):
    """Return True when affect resists dispel (cf. 1stMud saves_dispel in magic.c).
    [Verified: 03/07/2026]"""
    if duration == -1:
        spell_level += 5
    save = 50 + (spell_level - dis_level) * 5
    if save < 5:
        save = 5
    elif save > 95:
        save = 95
    return randint(1, 100) < save


def check_dispel(dis_level, victim, sn):
    """Try to dispel one affect type (cf. 1stMud check_dispel in magic.c).
    [Verified: 03/07/2026]"""
    if not is_affected(victim, sn):
        return False
    for af in list(victim.get("affect_list", [])):
        if af.get("type") != sn:
            continue
        if not saves_dispel(dis_level, af.get("level", 0), af.get("duration", 0)):
            affect_strip(victim, sn)
            msg = SKILLS.get(sn, {}).get("msg_off", "")
            # [PRIMESUD] 1stMud skills.dat uses "!Spell Name!~" as msg_off
            # placeholder for affects with no wear-off message; skip those.
            if msg and not msg.startswith("!"):
                chprintln(victim, msg)
            return True
        af["level"] = af.get("level", 0) - 1
    return False


def spell_cure_light(sn, level, ch, vo, target):
    """Cure light wounds (cf. 1stMud spell_cure_light in magic.c).
    [Verified: 03/07/2026]"""
    return _heal_char(ch, vo, dice(1, 8) + level // 3, "You feel better!")


def spell_cure_serious(sn, level, ch, vo, target):
    """Cure serious wounds (cf. 1stMud spell_cure_serious in magic.c).
    [Verified: 03/07/2026]"""
    return _heal_char(ch, vo, dice(2, 8) + level // 2, "You feel better!")


def spell_cure_critical(sn, level, ch, vo, target):
    """Cure critical wounds (cf. 1stMud spell_cure_critical in magic.c).
    [Verified: 03/07/2026]"""
    return _heal_char(ch, vo, dice(3, 8) + level - 6, "You feel better!")


def spell_heal(sn, level, ch, vo, target):
    """Heal spell (cf. 1stMud spell_heal in magic.c).
    [Verified: 03/07/2026]"""
    return _heal_char(ch, vo, 100, "A warm feeling fills your body.")


def spell_cause_light(sn, level, ch, vo, target):
    """Cause light wounds (cf. 1stMud spell_cause_light in magic.c)."""
    return damage(ch, vo, dice(1, 8) + level // 3, sn, DAM_HARM, True)


def spell_cause_serious(sn, level, ch, vo, target):
    """Cause serious wounds (cf. 1stMud spell_cause_serious in magic.c)."""
    return damage(ch, vo, dice(2, 8) + level // 2, sn, DAM_HARM, True)


def spell_cause_critical(sn, level, ch, vo, target):
    """Cause critical wounds (cf. 1stMud spell_cause_critical in magic.c)."""
    return damage(ch, vo, dice(3, 8) + level - 6, sn, DAM_HARM, True)


def spell_harm(sn, level, ch, vo, target):
    """Harm spell (cf. 1stMud spell_harm in magic.c)."""
    dam = max(20, vo["hit"] - dice(1, 4))
    if saves_spell(level, vo, DAM_HARM):
        dam = min(50, dam // 2)
    dam = min(100, dam)
    return damage(ch, vo, dam, sn, DAM_HARM, True)


def spell_magic_missile(sn, level, ch, vo, target):
    """Magic missile (cf. 1stMud spell_magic_missile in magic.c)."""
    high = level | 50
    dam = randint(high // 2, high * 2)
    if saves_spell(level, vo, DAM_ENERGY):
        dam //= 2
    return damage(ch, vo, dam, sn, DAM_ENERGY, True)


def spell_earthquake(sn, level, ch, vo, target):
    """Earthquake room spell (cf. 1stMud spell_earthquake in magic.c)."""
    chprintln(ch, "The earth trembles beneath your feet!")
    act("$n makes the earth tremble and shiver.", ch, None, None, TO_ROOM)
    room = world.rooms[ch["room"]]
    for mob_id in list(room["mobs"]):
        victim = world.chars.get(mob_id)
        if victim is None or victim is ch:
            continue
        dam = 0 if victim.get("affected_by", {}).get("flying") else level + dice(2, 8)
        damage(ch, victim, dam, sn, DAM_BASH, True)
    return True


def spell_call_lightning(sn, level, ch, vo, target):
    """Call lightning area spell (cf. 1stMud spell_call_lightning in magic.c)."""
    room = ROOM_DEFS[ch["room"]]
    if room.get("flags", {}).get("indoors"):
        chprintln(ch, "You must be out of doors.")
        return False
    area = _area_state_for_room(ch["room"])
    weather = area.get("weather") if area is not None else None
    if weather is None or weather.get("precip", 0) <= 0:
        chprintln(ch, "You need bad weather.")
        return False

    dam = dice(max(1, level // 2), 8)
    act("$g's lightning strikes your foes!", ch, None, None, TO_CHAR)
    act("$n calls $g's lightning to strike $s foes!", ch, None, None, TO_ROOM)
    room_state = world.rooms[ch["room"]]
    for mob_id in list(room_state["mobs"]):
        victim = world.chars.get(mob_id)
        if victim is None or victim is ch:
            continue
        cur_dam = dam
        if saves_spell(level, victim, DAM_LIGHTNING):
            cur_dam //= 2
        damage(ch, victim, cur_dam, sn, DAM_LIGHTNING, True)
    return True


def spell_chain_lightning(sn, level, ch, vo, target):
    """Chain lightning room spell (cf. 1stMud spell_chain_lightning in magic.c)."""
    victim = vo
    act("A lightning bolt leaps from $n's hand and arcs to $N.", ch, None, victim, TO_ROOM)
    act("A lightning bolt leaps from your hand and arcs to $N.", ch, None, victim, TO_CHAR)
    act("A lightning bolt leaps from $n's hand and hits you!", ch, None, victim, TO_VICT)
    dam = dice(level, 6)
    if saves_spell(level, victim, DAM_LIGHTNING):
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
            if is_safe_spell(ch, tmp, True):
                continue
            found = True
            last_vict = tmp
            act("The bolt arcs to $n!", tmp, None, None, TO_ROOM)
            act("The bolt hits you!", tmp, None, None, TO_CHAR)
            dam = dice(level, 6)
            if saves_spell(level, tmp, DAM_LIGHTNING):
                dam //= 3
            damage(ch, tmp, dam, sn, DAM_LIGHTNING, True)
            level -= 4
            break
        if not found:
            if last_vict is ch:
                act("The bolt seems to have fizzled out.", ch, None, None, TO_ROOM)
                act("The bolt grounds out through your body.", ch, None, None, TO_CHAR)
                return False
            last_vict = ch
            act("The bolt arcs to $n...whoops!", ch, None, None, TO_ROOM)
            chprintln(ch, "You are struck by your own lightning!")
            dam = dice(level, 6)
            if saves_spell(level, ch, DAM_LIGHTNING):
                dam //= 3
            damage(ch, ch, dam, sn, DAM_LIGHTNING, True)
            level -= 4
    return found


def _teleport_candidates(area_tag, is_npc):
    """Return valid teleport destination vnums within one loaded area. [PRIMESUD]"""
    adef = None
    for a in world.AREA_DEFS:
        if a.get("tag") == area_tag:
            adef = a
            break
    if adef is None or "room_vnums" not in adef:
        return []
    result = []
    for rv in adef["room_vnums"]:
        rd = ROOM_DEFS._data.get(rv)
        if rd is None:
            continue
        flags = rd.get("flags", {})
        if flags.get("private") or flags.get("solitary") or flags.get("safe") or flags.get("arena"):
            continue
        if not is_npc and flags.get("law"):
            continue
        result.append(rv)
    return result


def spell_teleport(sn, level, ch, vo, target):
    """Teleport target to random room (cf. 1stMud spell_teleport in magic.c).

    [PRIMESUD] Picks a random area first, loads it if needed, then picks a
    room within it. Avoids loading every area into memory (OOM on HP Prime).
    """
    victim = vo
    room = ROOM_DEFS.get(victim.get("room"))
    if (room is None
            or room.get("flags", {}).get("no_recall")
            or (victim is not ch and saves_spell(level - 5, victim, DAM_OTHER))
            or (ch.get("is_npc") is not True and victim.get("fighting") is not None)):
        chprintln(ch, "You failed.")
        return False
    area_files = world._AREA_FILES
    if not area_files:
        chprintln(ch, "You failed.")
        return False
    is_npc = victim.get("is_npc", False)
    dest = None
    # Pick random area, load if needed, filter rooms. Retry up to 10 times.
    tried = set()
    for _ in range(min(10, len(area_files))):
        idx = randint(0, len(area_files) - 1)
        _, area_tag, _, _ = area_files[idx]
        if area_tag in tried:
            continue
        tried.add(area_tag)
        world._ensure_area_by_tag(area_tag)
        candidates = _teleport_candidates(area_tag, is_npc)
        if candidates:
            dest = candidates[randint(0, len(candidates) - 1)]
            break
    if dest is None:
        chprintln(ch, "You failed.")
        return False
    old_room = victim["room"]
    victim["room"] = dest
    victim_id = None
    if victim is not None and victim is not ch:
        for mid, inst in world.chars.items():
            if inst is victim:
                victim_id = mid
                break
    if victim_id is not None:
        if victim_id in world.rooms.get(old_room, {}).get("mobs", []):
            world.rooms[old_room]["mobs"].remove(victim_id)
        world.rooms[dest]["mobs"].append(victim_id)
    if victim is not ch:
        chprintln(victim, "You have been teleported!")
    act("$n vanishes!", victim, None, None, TO_ROOM)
    if victim is ch:
        from info import do_look
    act("$n slowly fades into existence.", victim, None, None, TO_ROOM)
    if victim is ch:
        do_look(victim, [])
    return True


def spell_farsight(sn, level, ch, vo, target):
    """Farsight spell (cf. 1stMud spell_farsight in magic2.c)."""
    if ch.get("affected_by", {}).get("blind"):
        chprintln(ch, "Maybe it would help if you could see?")
        return False
    do_scan(ch, ch.get("_target_name", "").split())
    return True


def _collect_objs_recursive(obj_list, location, out):
    """Append (obj, location_str) for items and nested contents to out (cf. 1stMud obj_first flat list)."""
    for obj in obj_list:
        out.append((obj, location))
        _collect_objs_recursive(obj.get("contents", []), location, out)


def spell_locate_object(sn, level, ch, vo, target):
    """Locate object by name fragment (cf. 1stMud spell_locate_object in magic.c).

    Recurses into container contents to match 1stMud's flat obj_first
    iteration (magic.c:3523).
    """
    wanted = ch.get("_target_name", "")
    if not wanted:
        chprintln(ch, "Nothing like that in heaven or earth.")
        return False
    found = []
    max_found = 2 * level
    world_objs = []
    loc = "one is carried by you"
    _collect_objs_recursive(ch.get("inv", []), loc, world_objs)
    for obj in ch.get("equip", {}).values():
        if obj is not None:
            world_objs.append((obj, loc))
            _collect_objs_recursive(obj.get("contents", []), loc, world_objs)
    for room_vnum, room_state in world.rooms.items():
        rloc = "one is in " + ROOM_DEFS.get(room_vnum, {}).get("name", "somewhere")
        _collect_objs_recursive(room_state.get("items", []), rloc, world_objs)
    for cid, mob in world.chars.items():
        if not mob.get("is_npc"):
            continue
        mloc = "one is carried by " + MOB_DEFS[mob["tpl"]]["short_descr"]
        _collect_objs_recursive(mob.get("inv", []), mloc, world_objs)
        for obj in mob.get("equip", {}).values():
            if obj is not None:
                world_objs.append((obj, mloc))
                _collect_objs_recursive(obj.get("contents", []), mloc, world_objs)
    for obj, line in world_objs:
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
        chprintln(ch, "Nothing like that in heaven or earth.")
        return False
    for line in found:
        chprintln(ch, line)
    return True


def spell_control_weather(sn, level, ch, vo, target):
    """Adjust simplified interim weather state (cf. 1stMud spell_control_weather in magic.c)."""
    arg = ch.get("_target_name", "")
    area = _area_state_for_room(ch["room"])
    if area is None:
        chprintln(ch, "The weather is altered by your magic.")
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
        chprintln(ch, "Do you want it to get warmer, colder, wetter, drier, windier, or calmer?")
        return False
    if weather["precip_vector"] < -3:
        weather["precip_vector"] = -3
    elif weather["precip_vector"] > 3:
        weather["precip_vector"] = 3
    chprintln(ch, "The weather is altered by your magic.")
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
    chprintln(victim, "You've gained a Trivia Point!")
    if ch is not victim:
        chprintln(ch, "Ok.")
    return True


def spell_detect_poison(sn, level, ch, vo, target):
    """Detect poison on object target (cf. 1stMud spell_detect_poison in magic.c)."""
    tpl = ITEM_DEFS[obj_vnum(vo)]
    poisoned = bool(vo.get("poisoned") or tpl.get("poisoned"))
    if tpl.get("type") in ("food", "fountain"):
        chprintln(ch, "You smell poisonous fumes." if poisoned else "It looks delicious.")
    else:
        chprintln(ch, "It doesn't look poisoned.")
    return True


def spell_identify(sn, level, ch, vo, target):
    """Identify object details (cf. 1stMud spell_identify in magic.c)."""
    tpl = ITEM_DEFS[obj_vnum(vo)]
    flags = item_extra_flags(vo, tpl)
    chprintln(ch, "Object '" + tpl.get("keywords", "") + "' is type " + tpl.get("type", "unknown")
             + ", extra flags " + (" ".join(sorted(flags)) or "none") + ".")
    chprintln(ch, "Weight is " + str(tpl.get("weight", 0)) + ", value is "
             + str(vo.get("cost", tpl.get("value", 0))) + ", level is "
             + str(vo.get("level", tpl.get("level", 0))) + ".")  # instance level (quest gear scales)
    if tpl.get("type") in ("scroll", "potion", "pill"):
        spells = item_spells(vo, tpl)
        if spells:
            chprintln(ch, "Level " + str(item_spell_level(vo, tpl)) + " spells of: '" + "' '".join(spells) + "'.")
    elif tpl.get("type") in ("wand", "staff"):
        line = "Has " + str(item_current_charges(vo, tpl)) + " charges of level " + str(item_spell_level(vo, tpl))
        spell_name = item_spell_name(vo, tpl)
        if spell_name:
            line += " '" + spell_name + "'"
        chprintln(ch, line + ".")
    elif tpl.get("type") == "weapon":
        chprintln(ch, "Weapon type is " + tpl.get("weapon_type", "unknown") + ".")
        # 1stMud new_format: instance value[1]/[2] (quest gear scales dice)
        d = vo.get("dice") or tpl.get("dice", (0, 0, 0))
        chprintln(ch, "Damage is " + str(d[0]) + "d" + str(d[1])
                  + " (average " + str((1 + d[1]) * d[0] // 2) + ").")
        # [PRIMESUD] weapon flags line skipped -- weapon flags not ported
    for loc, mod in tpl.get("stat_bonuses", {}).items():
        chprintln(ch, "Affects " + loc + " by " + str(mod) + ".")
    for af in item_affect_list(vo):
        loc = af.get("location", "none")
        mod = af.get("modifier", 0)
        line = "Affects " + loc + " by " + str(mod)
        if af.get("duration", -1) > -1:
            line += ", " + str(af["duration"]) + " hours."
        else:
            line += "."
        chprintln(ch, line)
        bit = af.get("bitvector", "")
        if af.get("where") == "to_object" and bit:
            chprintln(ch, "Adds " + bit + " object flag.")
    return True


def spell_fireproof(sn, level, ch, vo, target):
    """Fireproof object target (cf. 1stMud spell_fireproof in magic.c)."""
    tpl = ITEM_DEFS[obj_vnum(vo)]
    flags = item_extra_flags(vo, tpl)
    if flags.get("burn_proof"):
        chprintln(ch, _item_name(vo) + " is already protected from burning.")
        return False
    item_affect_to_obj(vo, _new_obj_affect(sn, level, max(1, level // 4), "none", 0, "burn_proof"), tpl)
    chprintln(ch, "You protect " + _item_name(vo) + " from fire.")
    return True


def spell_enchant_armor(sn, level, ch, vo, target):
    """Enchant armor item (cf. 1stMud spell_enchant_armor in magic.c)."""
    tpl = ITEM_DEFS[obj_vnum(vo)]
    if tpl.get("type") != "armor":
        chprintln(ch, "That isn't an armor.")
        return False
    if vo not in ch.get("inv", []):
        chprintln(ch, "The item must be carried to be enchanted.")
        return False
    if item_extra_flags(vo, tpl).get("quest"):
        chprintln(ch, "You can't enchant quest items.")
        return False
    ac_found = False
    fail = 25
    if not vo.get("enchanted"):
        for loc, val in tpl.get("stat_bonuses", {}).items():
            if loc == "ac":
                ac_found = True
                fail += 5 * (val * val)
            else:
                fail += 20
    for af in item_affect_list(vo):
        if af.get("location") == "ac":
            ac_found = True
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
        chprintln(ch, _item_name(vo) + " flares blindingly... and evaporates!")
        ch["inv"].remove(vo)
        return False
    if result < fail // 3:
        chprintln(ch, _item_name(vo) + " glows brightly, then fades...oops.")
        vo["enchanted"] = True
        if "affect_list" in vo:
            del vo["affect_list"]
        vo["extra_flags"] = {}
        return False
    if result <= fail:
        chprintln(ch, "Nothing seemed to happen.")
        return False
    if not vo.get("enchanted"):
        vo["enchanted"] = True
        _enchant_copy_template(vo, tpl)
    if result <= (90 - level // 5):
        chprintln(ch, _item_name(vo) + " shimmers with a gold aura.")
        set_item_extra_flag(vo, tpl, "magic", True)
        added = -1
    else:
        chprintln(ch, _item_name(vo) + " glows a brillant gold!")
        set_item_extra_flag(vo, tpl, "magic", True)
        set_item_extra_flag(vo, tpl, "glow", True)
        added = -2
    vo["level"] = min(50, vo.get("level", tpl.get("level", 0)) + 1)
    if ac_found:
        for af in item_affect_list(vo):
            if af.get("location") == "ac":
                af["type"] = sn
                af["modifier"] = af.get("modifier", 0) + added
                af["level"] = max(af.get("level", 0), level)
    else:
        item_affect_to_obj(vo, _new_obj_affect(sn, level, -1, "ac", added), tpl)
    return True


def spell_enchant_weapon(sn, level, ch, vo, target):
    """Enchant weapon item (cf. 1stMud spell_enchant_weapon in magic.c)."""
    tpl = ITEM_DEFS[obj_vnum(vo)]
    if tpl.get("type") != "weapon":
        chprintln(ch, "That isn't a weapon.")
        return False
    if vo not in ch.get("inv", []):
        chprintln(ch, "The item must be carried to be enchanted.")
        return False
    if item_extra_flags(vo, tpl).get("quest"):
        chprintln(ch, "You can't enchant quest items.")
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
        chprintln(ch, _item_name(vo) + " shivers violently and explodes!")
        ch["inv"].remove(vo)
        return False
    if result < fail // 2:
        chprintln(ch, _item_name(vo) + " glows brightly, then fades...oops.")
        vo["enchanted"] = True
        if "affect_list" in vo:
            del vo["affect_list"]
        vo["extra_flags"] = {}
        return False
    if result <= fail:
        chprintln(ch, "Nothing seemed to happen.")
        return False
    if not vo.get("enchanted"):
        vo["enchanted"] = True
        _enchant_copy_template(vo, tpl)
    if result <= (100 - level // 5):
        chprintln(ch, _item_name(vo) + " glows blue.")
        set_item_extra_flag(vo, tpl, "magic", True)
        added = 1
    else:
        chprintln(ch, _item_name(vo) + " glows a brillant blue!")
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
    """Create a new affect dict with default 'to_affects' placement (cf. 1stMud `new_affect` in recycle.c: dict constructor)."""
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
        if vo is ch:
            chprintln(ch, "You are already armored.")
        else:
            act("$N is already armored.", ch, None, vo, TO_CHAR)
        return False
    affect_to_char(vo, _new_affect(sn, level, 24, "ac", -20))
    chprintln(vo, "You feel someone protecting you.")
    if ch is not vo:
        act("$N is protected by your magic.", ch, None, vo, TO_CHAR)
    return True


def spell_shield(sn, level, ch, vo, target):
    """Shield spell (cf. 1stMud spell_shield in magic.c)."""
    if is_affected(vo, sn):
        if vo is ch:
            chprintln(ch, "You are already shielded from harm.")
        else:
            act("$N is already protected by a shield.", ch, None, vo, TO_CHAR)
        return False
    affect_to_char(vo, _new_affect(sn, level, 8 + level, "ac", -20))
    act("$n is surrounded by a force shield.", vo, None, None, TO_ROOM)
    chprintln(vo, "You are surrounded by a force shield.")
    return True


def spell_bless(sn, level, ch, vo, target):
    """Bless character path (cf. 1stMud spell_bless in magic.c)."""
    if target == TARGET_OBJ:
        tpl = ITEM_DEFS[obj_vnum(vo)]
        flags = item_extra_flags(vo, tpl)
        if flags.get("bless"):
            chprintln(ch, _item_name(vo) + " is already blessed.")
            return False
        if flags.get("evil"):
            paf = item_affect_find(vo, _skill_lookup("curse"))
            if not saves_dispel(level, paf.get("level", tpl.get("level", 0)) if paf else tpl.get("level", 0), 0):
                if paf is not None:
                    item_affect_remove(vo, paf, tpl)
                set_item_extra_flag(vo, tpl, "evil", False)
                chprintln(ch, _item_name(vo) + " glows a pale blue.")
                return True
            chprintln(ch, "The evil of " + _item_name(vo) + " is too powerful for you to overcome.")
            return False
        item_affect_to_obj(vo, _new_obj_affect(sn, level, 6 + level, "saves", -1, "bless"), tpl)
        chprintln(ch, _item_name(vo) + " glows with a holy aura.")
        # TODO [PRIMESUD] saving_throw adjust for worn blessed items
        return True
    if vo.get("pos") == "fighting" or is_affected(vo, sn):
        if vo is ch:
            chprintln(ch, "You are already blessed.")
        else:
            act("$N already has divine favor.", ch, None, vo, TO_CHAR)
        return False
    mod = level // 8
    affect_to_char(vo, _new_affect(sn, level, 6 + level, "hitroll", mod))
    affect_to_char(vo, _new_affect(sn, level, 6 + level, "saves", -mod))
    chprintln(vo, "You feel righteous.")
    if ch is not vo:
        act("You grant $N the favor of your god.", ch, None, vo, TO_CHAR)
    return True


def spell_giant_strength(sn, level, ch, vo, target):
    """Giant strength spell (cf. 1stMud spell_giant_strength in magic.c)."""
    if is_affected(vo, sn):
        if vo is ch:
            chprintln(ch, "You are already as strong as you can get!")
        else:
            act("$N can't get any stronger.", ch, None, vo, TO_CHAR)
        return False
    mod = 1 + (level >= 18) + (level >= 25) + (level >= 32)
    affect_to_char(vo, _new_affect(sn, level, level, "str", mod))
    chprintln(vo, "Your muscles surge with heightened power!")
    act("$n's muscles surge with heightened power.", vo, None, None, TO_ROOM)
    return True


def spell_weaken(sn, level, ch, vo, target):
    """Weaken spell (cf. 1stMud spell_weaken in magic.c)."""
    if is_affected(vo, sn) or saves_spell(level, vo, DAM_OTHER):
        return False
    affect_to_char(vo, _new_affect(sn, level, level // 2, "str", -1 * (level // 5), "weaken"))
    chprintln(vo, "You feel your strength slip away.")
    act("$n looks tired and weak.", vo, None, None, TO_ROOM)
    return True


def spell_faerie_fire(sn, level, ch, vo, target):
    """Faerie fire spell (cf. 1stMud spell_faerie_fire in magic.c)."""
    if vo.get("affected_by", {}).get("faerie_fire"):
        return False
    affect_to_char(vo, _new_affect(sn, level, level, "ac", 2 * level, "faerie_fire"))
    chprintln(vo, "You are surrounded by a pink outline.")
    act("$n is surrounded by a pink outline.", vo, None, None, TO_ROOM)
    return True


def spell_blindness(sn, level, ch, vo, target):
    """Blindness spell (cf. 1stMud spell_blindness in magic.c)."""
    if vo.get("affected_by", {}).get("blind") or saves_spell(level, vo, DAM_OTHER):
        chprintln(ch, "You failed.")
        return False
    affect_to_char(vo, _new_affect(sn, level, 1 + level, "hitroll", -4, "blind"))
    chprintln(vo, "You are blinded!")
    act("$n appears to be blinded.", vo, None, None, TO_ROOM)
    return True


def spell_poison(sn, level, ch, vo, target):
    """Poison character path (cf. 1stMud spell_poison in magic.c)."""
    if target == TARGET_OBJ:
        chprintln(ch, "That spell does not work on objects yet.")
        return False
    if saves_spell(level, vo, DAM_POISON):
        act("$n turns slightly green, but it passes.", vo, None, None, TO_ROOM)
        chprintln(vo, "You feel momentarily ill, but it passes.")
        return False
    affect_join(vo, _new_affect(sn, level, level, "str", -2, "poison"))
    chprintln(vo, "You feel very sick.")
    act("$n looks very ill.", vo, None, None, TO_ROOM)
    return True


def spell_curse(sn, level, ch, vo, target):
    """Curse character path (cf. 1stMud spell_curse in magic.c)."""
    if target == TARGET_OBJ:
        tpl = ITEM_DEFS[obj_vnum(vo)]
        flags = item_extra_flags(vo, tpl)
        if flags.get("evil"):
            chprintln(ch, _item_name(vo) + " is already filled with evil.")
            return False
        if flags.get("bless"):
            paf = item_affect_find(vo, _skill_lookup("bless"))
            if not saves_dispel(level, paf.get("level", tpl.get("level", 0)) if paf else tpl.get("level", 0), 0):
                if paf is not None:
                    item_affect_remove(vo, paf, tpl)
                set_item_extra_flag(vo, tpl, "bless", False)
                chprintln(ch, _item_name(vo) + " glows with a red aura.")
                return True
            chprintln(ch, "The holy aura of " + _item_name(vo) + " is too powerful for you to overcome.")
            return False
        item_affect_to_obj(vo, _new_obj_affect(sn, level, 2 * level, "saves", 1, "evil"), tpl)
        chprintln(ch, _item_name(vo) + " glows with a malevolent aura.")
        # TODO [PRIMESUD] saving_throw adjust for worn cursed items
        return True
    if vo.get("affected_by", {}).get("curse") or saves_spell(level, vo, DAM_NEGATIVE):
        return False
    mod = level // 8
    affect_to_char(vo, _new_affect(sn, level, 2 * level, "hitroll", -mod, "curse"))
    affect_to_char(vo, _new_affect(sn, level, 2 * level, "saves", mod))
    chprintln(vo, "You feel unclean.")
    if ch is not vo:
        act("$N looks very uncomfortable.", ch, None, vo, TO_CHAR)
    return True


def spell_plague(sn, level, ch, vo, target):
    """Plague spell (cf. 1stMud spell_plague in magic.c)."""
    if saves_spell(level, vo, DAM_DISEASE) or (
            vo.get("is_npc") and MOB_DEFS.get(vo.get("tpl"), {}).get("act_flags", {}).get("undead")):
        if vo is ch:
            chprintln(ch, "You feel momentarily ill, but it passes.")
        else:
            act("$N seems to be unaffected.", ch, None, vo, TO_CHAR)
        return False
    affect_join(vo, _new_affect(sn, level * 3 // 4, level, "str", -5, "plague"))
    chprintln(vo, "You scream in agony as plague sores erupt from your skin.")
    act("$n screams in agony as plague sores erupt from $s skin.", vo, None, None, TO_ROOM)
    return True


def spell_cure_blindness(sn, level, ch, vo, target):
    """Cure blindness (cf. 1stMud spell_cure_blindness in magic.c)."""
    blind_sn = _skill_lookup("blindness")
    if not is_affected(vo, blind_sn):
        if vo is ch:
            chprintln(ch, "You aren't blind.")
        else:
            act("$N doesn't appear to be blinded.", ch, None, vo, TO_CHAR)
        return False
    if check_dispel(level, vo, blind_sn):
        chprintln(vo, "Your vision returns!")
        act("$n is no longer blinded.", vo, None, None, TO_ROOM)
        return True
    chprintln(ch, "Spell failed.")
    return False


def spell_cure_poison(sn, level, ch, vo, target):
    """Cure poison (cf. 1stMud spell_cure_poison in magic.c)."""
    poison_sn = _skill_lookup("poison")
    if not is_affected(vo, poison_sn):
        if vo is ch:
            chprintln(ch, "You aren't poisoned.")
        else:
            act("$N doesn't appear to be poisoned.", ch, None, vo, TO_CHAR)
        return False
    if check_dispel(level, vo, poison_sn):
        chprintln(vo, "A warm feeling runs through your body.")
        act("$n looks much better.", vo, None, None, TO_ROOM)
        return True
    chprintln(ch, "Spell failed.")
    return False


def spell_cure_disease(sn, level, ch, vo, target):
    """Cure disease (cf. 1stMud spell_cure_disease in magic.c)."""
    plague_sn = _skill_lookup("plague")
    if not is_affected(vo, plague_sn):
        if vo is ch:
            chprintln(ch, "You aren't ill.")
        else:
            act("$N doesn't appear to be diseased.", ch, None, vo, TO_CHAR)
        return False
    if check_dispel(level, vo, plague_sn):
        chprintln(vo, "Your sores vanish.")
        act("$n looks relieved as $s sores vanish.", vo, None, None, TO_ROOM)
        return True
    chprintln(ch, "Spell failed.")
    return False


def spell_dispel_magic(sn, level, ch, vo, target):
    """Dispel magic (cf. 1stMud spell_dispel_magic in magic.c)."""
    if saves_spell(level, vo, DAM_OTHER):
        chprintln(vo, "You feel a brief tingling sensation.")
        chprintln(ch, "You failed.")
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
        if cur is not None and check_dispel(level, vo, cur):
            found = True
    sanc_sn = _skill_lookup("sanctuary")
    if (vo.get("affected_by", {}).get("sanctuary")
            and not saves_dispel(level, vo.get("level", 1), -1)
            and not is_affected(vo, sanc_sn)):
        vo.get("affected_by", {}).pop("sanctuary", None)
        found = True
    if found:
        chprintln(ch, "Ok.")
        return True
    chprintln(ch, "Spell failed.")
    return False


# ====================================================================
# Remaining spell ports from 1stMud magic.c / magic2.c
# ====================================================================


def spell_acid_blast(sn, level, ch, vo, target):
    """Acid blast (cf. 1stMud spell_acid_blast in magic.c)."""
    dam = dice(level, 12)
    if saves_spell(level, vo, DAM_ACID):
        dam //= 2
    return damage(ch, vo, dam, sn, DAM_ACID, True)


def spell_burning_hands(sn, level, ch, vo, target):
    """Burning hands (cf. 1stMud spell_burning_hands in magic.c)."""
    high = level | 50
    dam = randint(high // 2, high * 2)
    if saves_spell(level, vo, DAM_FIRE):
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
            chprintln(ch, "A wave of calm passes over you.")
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
            and not (ch.get("affected_by", {}).get("charm")
                     and ch.get("master") == victim.get("id")))
            or (ch.get("is_npc") and not victim.get("is_npc"))):
        chprintln(ch, "You failed, try dispel magic.")
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
        if cur is not None and check_dispel(level, victim, cur):
            found = True
    if found:
        chprintln(ch, "Ok.")
    else:
        chprintln(ch, "Spell failed.")
    return found


def spell_change_sex(sn, level, ch, vo, target):
    """Change sex (cf. 1stMud spell_change_sex in magic.c)."""
    if is_affected(vo, sn):
        if vo is ch:
            chprintln(ch, "You've already been changed.")
        else:
            act("$N has already had $s(?) sex changed.", ch, None, vo, TO_CHAR)
        return False
    if saves_spell(level, vo, DAM_OTHER):
        return False
    cur_sex = vo.get("sex", 0)
    mod = 0
    while mod == 0:
        mod = randint(0, 2) - cur_sex
    affect_to_char(vo, _new_affect(sn, level, 2 * level, "sex", mod))
    chprintln(vo, "You feel different.")
    act("$n doesn't look like $mself anymore...", vo, None, None, TO_ROOM)
    return True


def spell_charm_person(sn, level, ch, vo, target):
    """Charm person (cf. 1stMud spell_charm_person in magic.c)."""
    victim = vo
    if is_safe(ch, victim):
        return False
    if victim is ch:
        chprintln(ch, "You like yourself even better!")
        return False
    if (victim.get("affected_by", {}).get("charm")
            or ch.get("affected_by", {}).get("charm")
            or level < victim.get("level", 1)
            or victim.get("imm_flags", {}).get("charm")
            or saves_spell(level, victim, DAM_CHARM)):
        return False
    room = ROOM_DEFS.get(ch.get("room"))
    if room and room.get("flags", {}).get("law"):
        chprintln(ch, "The mayor does not allow charming in the city limits.")
        return False
    from comm import add_follower, stop_follower  # lazy import to avoid circular dependency
    if victim.get("master") is not None:
        stop_follower(victim)
    add_follower(victim, ch)
    victim["leader"] = ch["id"]
    affect_to_char(victim, _new_affect(sn, level, number_fuzzy(level // 4), "none", 0, "charm"))
    act("Isn't $n just so nice?", ch, None, victim, TO_VICT)
    act("$N looks at you with adoring eyes.", ch, None, victim, TO_CHAR)
    return True


def spell_chill_touch(sn, level, ch, vo, target):
    """Chill touch (cf. 1stMud spell_chill_touch in magic.c)."""
    high = level | 50
    dam = randint(high // 2, high * 2)
    if not saves_spell(level, vo, DAM_COLD):
        affect_join(vo, _new_affect(sn, level, 6, "str", -1))
    else:
        dam //= 2
    return damage(ch, vo, dam, sn, DAM_COLD, True)


def spell_color_spray(sn, level, ch, vo, target):
    """Color spray (cf. 1stMud spell_color_spray in magic.c)."""
    high = level | 50
    dam = randint(high // 2, high * 2)
    if saves_spell(level, vo, DAM_LIGHT):
        dam //= 2
    else:
        blind_sn = _skill_lookup("blindness")
        if blind_sn is not None:
            spell_blindness(blind_sn, level // 2, ch, vo, TARGET_CHAR)
    return damage(ch, vo, dam, sn, DAM_LIGHT, True)


def spell_continual_light(sn, level, ch, vo, target):
    """Create light ball or make carried item glow (cf. 1stMud spell_continual_light in magic.c)."""
    tail = ch.get("_target_name", "")
    if tail:
        obj = get_obj_list(tail, ch["inv"], ITEM_DEFS)
        if obj is None:
            chprintln(ch, "You don't see that here.")
            return False
        tpl = ITEM_DEFS[obj_vnum(obj)]
        flags = item_extra_flags(obj, tpl)
        if flags.get("glow"):
            act("$p is already glowing.", ch, obj, None, TO_CHAR)
            return False
        set_item_extra_flag(obj, tpl, "glow", True)
        act("$p glows with a white light.", ch, obj, None, TO_ALL)
        return True
    light = create_object(I_BALL_LIGHT)
    rs = world.rooms[ch["room"]]
    rs.setdefault("items", []).append(light)
    act("$n twiddles $s thumbs and $p appears.", ch, light, None, TO_ROOM)
    act("You twiddle your thumbs and $p appears.", ch, light, None, TO_CHAR)
    return True


def spell_create_food(sn, level, ch, vo, target):
    """Create a mushroom (cf. 1stMud spell_create_food in magic.c)."""
    mushroom = create_object(I_MUSHROOM)
    mushroom["level"] = level // 2 if level // 2 > 0 else 1
    mushroom["food_hours"] = level // 2
    mushroom["timer"] = 24
    rs = world.rooms[ch["room"]]
    rs.setdefault("items", []).append(mushroom)
    act("$p suddenly appears.", ch, mushroom, None, TO_ROOM)
    act("$p suddenly appears.", ch, mushroom, None, TO_CHAR)
    return True


def spell_create_rose(sn, level, ch, vo, target):
    """Create a rose (cf. 1stMud spell_create_rose in magic.c).

    TODO: OBJ_VNUM_ROSE template not yet defined in area data.
    """
    # TODO [PRIMESUD] need rose item template
    act("$n has created a beautiful red rose.", ch, None, None, TO_ROOM)
    chprintln(ch, "You create a beautiful red rose.")
    return True


def spell_create_spring(sn, level, ch, vo, target):
    """Create a magical spring (cf. 1stMud spell_create_spring in magic.c)."""
    spring = create_object(I_SPRING)
    spring["timer"] = level
    rs = world.rooms[ch["room"]]
    rs.setdefault("items", []).append(spring)
    act("$p flows from the ground.", ch, spring, None, TO_ROOM)
    act("$p flows from the ground.", ch, spring, None, TO_CHAR)
    return True


def spell_create_water(sn, level, ch, vo, target):
    """Fill drink container with water (cf. 1stMud spell_create_water in magic.c).

    TODO: drink container system not fully ported.
    """
    tpl = ITEM_DEFS[obj_vnum(vo)]
    if tpl.get("type") != "drink_con":
        chprintln(ch, "It is unable to hold water.")
        return False
    # TODO [PRIMESUD] liquid type / fill level not yet modeled
    act("$p is filled.", ch, vo, None, TO_CHAR)
    return True


def spell_demonfire(sn, level, ch, vo, target):
    """Demonfire (cf. 1stMud spell_demonfire in magic.c)."""
    victim = vo
    if not ch.get("is_npc") and not is_evil(ch):
        victim = ch
        chprintln(ch, "The demons turn upon you!")
    ch["alignment"] = max(-1000, ch.get("alignment", 0) - 50)
    if victim is not ch:
        act("$n calls forth the demons of Hell upon $N!", ch, None, victim, TO_ROOM)
        act("$n has assailed you with the demons of Hell!", ch, None, victim, TO_VICT)
        chprintln(ch, "You conjure forth the demons of hell!")
    dam = dice(level, 10)
    if saves_spell(level, victim, DAM_NEGATIVE):
        dam //= 2
    curse_sn = _skill_lookup("curse")
    if curse_sn is not None:
        spell_curse(curse_sn, 3 * level // 4, ch, victim, TARGET_CHAR)
    return damage(ch, victim, dam, sn, DAM_NEGATIVE, True)


def spell_detect_evil(sn, level, ch, vo, target):
    """Detect evil (cf. 1stMud spell_detect_evil in magic.c)."""
    if vo.get("affected_by", {}).get("detect_evil"):
        if vo is ch:
            chprintln(ch, "You can already sense evil.")
        else:
            act("$N can already detect evil.", ch, None, vo, TO_CHAR)
        return False
    affect_to_char(vo, _new_affect(sn, level, level, "none", 0, "detect_evil"))
    chprintln(vo, "Your eyes tingle.")
    if ch is not vo:
        chprintln(ch, "Ok.")
    return True


def spell_detect_good(sn, level, ch, vo, target):
    """Detect good (cf. 1stMud spell_detect_good in magic.c)."""
    if vo.get("affected_by", {}).get("detect_good"):
        if vo is ch:
            chprintln(ch, "You can already sense good.")
        else:
            act("$N can already detect good.", ch, None, vo, TO_CHAR)
        return False
    affect_to_char(vo, _new_affect(sn, level, level, "none", 0, "detect_good"))
    chprintln(vo, "Your eyes tingle.")
    if ch is not vo:
        chprintln(ch, "Ok.")
    return True


def spell_detect_hidden(sn, level, ch, vo, target):
    """Detect hidden (cf. 1stMud spell_detect_hidden in magic.c)."""
    if vo.get("affected_by", {}).get("detect_hidden"):
        if vo is ch:
            chprintln(ch, "You are already as alert as you can be.")
        else:
            act("$N can already sense hidden lifeforms.", ch, None, vo, TO_CHAR)
        return False
    affect_to_char(vo, _new_affect(sn, level, level, "none", 0, "detect_hidden"))
    chprintln(vo, "Your awareness improves.")
    if ch is not vo:
        chprintln(ch, "Ok.")
    return True


def spell_detect_invis(sn, level, ch, vo, target):
    """Detect invis (cf. 1stMud spell_detect_invis in magic.c)."""
    if vo.get("affected_by", {}).get("detect_invis"):
        if vo is ch:
            chprintln(ch, "You can already see invisible.")
        else:
            act("$N can already see invisible things.", ch, None, vo, TO_CHAR)
        return False
    affect_to_char(vo, _new_affect(sn, level, level, "none", 0, "detect_invis"))
    chprintln(vo, "Your eyes tingle.")
    if ch is not vo:
        chprintln(ch, "Ok.")
    return True


def spell_detect_magic(sn, level, ch, vo, target):
    """Detect magic (cf. 1stMud spell_detect_magic in magic.c)."""
    if vo.get("affected_by", {}).get("detect_magic"):
        if vo is ch:
            chprintln(ch, "You can already sense magical auras.")
        else:
            act("$N can already detect magic.", ch, None, vo, TO_CHAR)
        return False
    affect_to_char(vo, _new_affect(sn, level, level, "none", 0, "detect_magic"))
    chprintln(vo, "Your eyes tingle.")
    if ch is not vo:
        chprintln(ch, "Ok.")
    return True


def spell_dispel_evil(sn, level, ch, vo, target):
    """Dispel evil (cf. 1stMud spell_dispel_evil in magic.c)."""
    victim = vo
    if not ch.get("is_npc") and is_evil(ch):
        victim = ch
    if is_good(victim):
        act("$G protects $N.", ch, None, victim, TO_ROOM)
        return False
    if is_neutral(victim):
        act("$N does not seem to be affected.", ch, None, victim, TO_CHAR)
        return False
    if victim.get("hit", 0) > ch.get("level", 1) * 4:
        dam = dice(level, 4)
    else:
        dam = max(victim.get("hit", 0), dice(level, 4))
    if saves_spell(level, victim, DAM_HOLY):
        dam //= 2
    return damage(ch, victim, dam, sn, DAM_HOLY, True)


def spell_dispel_good(sn, level, ch, vo, target):
    """Dispel good (cf. 1stMud spell_dispel_good in magic.c)."""
    victim = vo
    if not ch.get("is_npc") and is_good(ch):
        victim = ch
    if is_evil(victim):
        act("$N is protected by $S evil.", ch, None, victim, TO_ROOM)
        return False
    if is_neutral(victim):
        act("$N does not seem to be affected.", ch, None, victim, TO_CHAR)
        return False
    if victim.get("hit", 0) > ch.get("level", 1) * 4:
        dam = dice(level, 4)
    else:
        dam = max(victim.get("hit", 0), dice(level, 4))
    if saves_spell(level, victim, DAM_NEGATIVE):
        dam //= 2
    return damage(ch, victim, dam, sn, DAM_NEGATIVE, True)


def spell_energy_drain(sn, level, ch, vo, target):
    """Energy drain (cf. 1stMud spell_energy_drain in magic.c)."""
    victim = vo
    if victim is not ch:
        ch["alignment"] = max(-1000, ch.get("alignment", 0) - 50)
    if saves_spell(level, victim, DAM_NEGATIVE):
        chprintln(victim, "You feel a momentary chill.")
        return False
    if victim.get("level", 1) <= 2:
        dam = ch.get("hit", 1) + 1
    else:
        # TODO [PRIMESUD] gain_exp not yet ported
        victim["mana"] = victim.get("mana", 0) // 2
        victim["move"] = victim.get("move", 0) // 2
        dam = dice(1, level)
        ch["hit"] = ch.get("hit", 0) + dam
    chprintln(victim, "You feel your life slipping away!")
    chprintln(ch, "Wow....what a rush!")
    damage(ch, victim, dam, sn, DAM_NEGATIVE, True)
    return True


def spell_fireball(sn, level, ch, vo, target):
    """Fireball (cf. 1stMud spell_fireball in magic.c)."""
    high = level | 50
    dam = randint(high // 2, high * 2)
    if saves_spell(level, vo, DAM_FIRE):
        dam //= 2
    return damage(ch, vo, dam, sn, DAM_FIRE, True)


def spell_flamestrike(sn, level, ch, vo, target):
    """Flamestrike (cf. 1stMud spell_flamestrike in magic.c)."""
    dam = dice(6 + level // 2, 8)
    if saves_spell(level, vo, DAM_FIRE):
        dam //= 2
    return damage(ch, vo, dam, sn, DAM_FIRE, True)


def spell_faerie_fog(sn, level, ch, vo, target):
    """Faerie fog -- reveal hidden/invisible in room (cf. 1stMud spell_faerie_fog in magic.c)."""
    act("$n conjures a cloud of purple smoke.", ch, None, None, TO_ROOM)
    chprintln(ch, "You conjure a cloud of purple smoke.")
    room = world.rooms[ch["room"]]
    found = False
    for mob_id in list(room["mobs"]):
        mob = world.chars.get(mob_id)
        if mob is None or mob is ch:
            continue
        if saves_spell(level, mob, DAM_OTHER):
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
        act("$n is revealed!", mob, None, None, TO_ROOM)
        chprintln(mob, "You are revealed!")
        found = True
    return found


def spell_floating_disc(sn, level, ch, vo, target):
    """Create a floating disc container (cf. 1stMud spell_floating_disc in magic.c).

    TODO: equip-to-float slot not yet ported; disc added to inventory.
    """
    disc = create_object(I_DISC_DISK_FLOATING_BLACK)
    disc["timer"] = ch.get("level", 1) * 2 - randint(0, level // 2)
    ch.setdefault("inv", []).append(disc)
    act("$n has created a floating black disc.", ch, None, None, TO_ROOM)
    chprintln(ch, "You create a floating disc.")
    # TODO [PRIMESUD] auto-equip to float slot: wear_obj(ch, disc, True)
    return True


def spell_fly(sn, level, ch, vo, target):
    """Fly spell (cf. 1stMud spell_fly in magic.c)."""
    if vo.get("affected_by", {}).get("flying"):
        if vo is ch:
            chprintln(ch, "You are already airborne.")
        else:
            act("$N doesn't need your help to fly.", ch, None, vo, TO_CHAR)
        return False
    affect_to_char(vo, _new_affect(sn, level, level + 3, "none", 0, "flying"))
    chprintln(vo, "Your feet rise off the ground.")
    act("$n's feet rise off the ground.", vo, None, None, TO_ROOM)
    return True


def spell_frenzy(sn, level, ch, vo, target):
    """Frenzy spell (cf. 1stMud spell_frenzy in magic.c)."""
    if is_affected(vo, sn) or vo.get("affected_by", {}).get("berserk"):
        if vo is ch:
            chprintln(ch, "You are already in a frenzy.")
        else:
            act("$N is already in a frenzy.", ch, None, vo, TO_CHAR)
        return False
    calm_sn = _skill_lookup("calm")
    if calm_sn is not None and is_affected(vo, calm_sn):
        if vo is ch:
            chprintln(ch, "Why don't you just relax for a while?")
        else:
            act("$N doesn't look like $e wants to fight anymore.", ch, None, vo, TO_CHAR)
        return False
    if ((is_good(ch) and not is_good(vo))
            or (is_neutral(ch) and not is_neutral(vo))
            or (is_evil(ch) and not is_evil(vo))):
        act("Your god doesn't seem to like $N", ch, None, vo, TO_CHAR)
        return False
    mod = level // 6
    affect_to_char(vo, _new_affect(sn, level, level // 3, "hitroll", mod))
    affect_to_char(vo, _new_affect(sn, level, level // 3, "damroll", mod))
    affect_to_char(vo, _new_affect(sn, level, level // 3, "ac", 10 * (level // 12)))
    chprintln(vo, "You are filled with holy wrath!")
    act("$n gets a wild look in $s eyes!", vo, None, None, TO_ROOM)
    return True


def spell_gate(sn, level, ch, vo, target):
    """Gate to another character's location (cf. 1stMud spell_gate in magic.c)."""
    tail = ch.get("_target_name", "")
    if not tail:
        chprintln(ch, "You failed.")
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
        chprintln(ch, "You failed.")
        return False

    victim_vnum = victim.get("room")
    if victim_vnum is None:
        chprintln(ch, "You failed.")
        return False

    src_flags = ROOM_DEFS.get(ch.get("room"), {}).get("flags", {})
    dst_flags = ROOM_DEFS.get(victim_vnum, {}).get("flags", {})

    from quest import is_quester
    from gquest import gq_is_target
    if (not can_see_room(ch, victim_vnum)
            or dst_flags.get("safe")
            # TODO [PRIMESUD] arena flag not yet implemented
            or src_flags.get("no_recall")
            or dst_flags.get("no_recall")
            or dst_flags.get("private")
            or dst_flags.get("solitary")
            # TODO [PRIMESUD] clan check (is_clan/is_same_clan) not yet ported
            # 1stMud: gquest targets can't be gated to (is_gqmob)
            or (victim.get("is_npc") and gq_is_target(victim.get("tpl")))
            # 1stMud: can't gate to your own quest mob;
            # [PRIMESUD] vnum match instead of instance pointer
            or (victim.get("is_npc") and is_quester(ch)
                and victim.get("tpl") == ch.get("quest_mob", 0))
            or victim.get("level", 0) >= level + 3
            or (not victim.get("is_npc") and victim.get("level", 0) >= MAX_MORTAL_LEVEL)
            or (victim.get("is_npc") and victim.get("imm_flags", {}).get("summon"))
            or (victim.get("is_npc") and saves_spell(level, victim, DAM_OTHER))):
        chprintln(ch, "You failed.")
        return False

    # TODO [PRIMESUD] pet teleport not yet implemented
    act("$n steps through a gate and vanishes.", ch, None, None, TO_ROOM)
    chprintln(ch, "You step through a gate and vanish.")
    ch["room"] = victim_vnum
    # act("$n has arrived through a gate.", ..., TO_ROOM) omitted -- single-player
    from info import do_look
    do_look(ch, [])
    return True


def spell_haste(sn, level, ch, vo, target):
    """Haste spell (cf. 1stMud spell_haste in magic.c)."""
    if is_affected(vo, sn) or vo.get("affected_by", {}).get("haste") or vo.get("off_flags", {}).get("fast"):
        if vo is ch:
            chprintln(ch, "You can't move any faster!")
        else:
            act("$N is already moving as fast as $E can.", ch, None, vo, TO_CHAR)
        return False
    # 1stMud: if slowed, haste spends its energy dispelling slow and does NOT
    # apply haste afterward -- returns False in both cases (dispel success or
    # failure). This matches 1stMud magic.c:2908-2918 exactly.
    if vo.get("affected_by", {}).get("slow"):
        slow_sn = _skill_lookup("slow")
        if slow_sn is not None and not check_dispel(level, vo, slow_sn):
            if vo is not ch:
                chprintln(ch, "Spell failed.")
            chprintln(vo, "You feel momentarily faster.")
            return False
        act("$n is moving less slowly.", vo, None, None, TO_ROOM)
        return False
    dur = level // 2 if vo is ch else level // 4
    mod = 1 + (level >= 18) + (level >= 25) + (level >= 32)
    affect_to_char(vo, _new_affect(sn, level, dur, "dex", mod, "haste"))
    chprintln(vo, "You feel yourself moving more quickly.")
    act("$n is moving more quickly.", vo, None, None, TO_ROOM)
    if ch is not vo:
        chprintln(ch, "Ok.")
    return True


def spell_heat_metal(sn, level, ch, vo, target):
    """Heat metal (cf. 1stMud spell_heat_metal in magic.c).

    TODO: equipment drop/sear mechanic requires full equipment iteration.
    Simplified to flat damage based on level.
    """
    victim = vo
    if saves_spell(level + 2, victim, DAM_FIRE) or victim.get("imm_flags", {}).get("fire"):
        chprintln(ch, "Your spell had no effect.")
        chprintln(victim, "You feel momentarily warmer.")
        return False
    dam = dice(level // 2, 8)
    if saves_spell(level, victim, DAM_FIRE):
        dam = 2 * dam // 3
    act("You sear $N with heat!", ch, None, victim, TO_CHAR)  # [PRIMESUD] simplified stub
    # TODO [PRIMESUD] full equipment iteration and drop/sear mechanic
    return damage(ch, victim, dam, sn, DAM_FIRE, True)


def spell_holy_word(sn, level, ch, vo, target):
    """Holy word (cf. 1stMud spell_holy_word in magic.c)."""
    act("$n utters a word of divine power!", ch, None, None, TO_ROOM)
    chprintln(ch, "You utter a word of divine power.")
    bless_sn = _skill_lookup("bless")
    curse_sn = _skill_lookup("curse")
    frenzy_sn = _skill_lookup("frenzy")
    room = world.rooms[ch["room"]]
    for mob_id in list(room["mobs"]):
        mob = world.chars.get(mob_id)
        if mob is None:
            continue
        if ((is_good(ch) and is_good(mob))
                or (is_evil(ch) and is_evil(mob))
                or (is_neutral(ch) and is_neutral(mob))):
            chprintln(mob, "You feel full more powerful.")
            if frenzy_sn is not None:
                spell_frenzy(frenzy_sn, level, ch, mob, TARGET_CHAR)
            if bless_sn is not None:
                spell_bless(bless_sn, level, ch, mob, TARGET_CHAR)
        elif (is_good(ch) and is_evil(mob)) or (is_evil(ch) and is_good(mob)):
            if is_safe_spell(ch, mob, True):
                continue
            if curse_sn is not None:
                spell_curse(curse_sn, level, ch, mob, TARGET_CHAR)
            chprintln(mob, "You are struck down!")
            dam = dice(level, 6)
            damage(ch, mob, dam, sn, DAM_ENERGY, True)
        elif is_neutral(ch):
            if is_safe_spell(ch, mob, True):
                continue
            if curse_sn is not None:
                spell_curse(curse_sn, level // 2, ch, mob, TARGET_CHAR)
            chprintln(mob, "You are struck down!")
            dam = dice(level, 4)
            damage(ch, mob, dam, sn, DAM_ENERGY, True)
    chprintln(ch, "You feel drained.")
    ch["move"] = 0
    ch["hit"] = ch.get("hit", 1) // 2
    return True


def spell_infravision(sn, level, ch, vo, target):
    """Infravision (cf. 1stMud spell_infravision in magic.c)."""
    if vo.get("affected_by", {}).get("infrared"):
        if vo is ch:
            chprintln(ch, "You can already see in the dark.")
        else:
            act("$N already has infravision.", ch, None, vo, TO_CHAR)
        return False
    affect_to_char(vo, _new_affect(sn, level, 2 * level, "none", 0, "infrared"))
    act("$n's eyes glow red.", ch, None, None, TO_ROOM)
    chprintln(vo, "Your eyes glow red.")
    return True


def spell_invis(sn, level, ch, vo, target):
    """Invisibility (cf. 1stMud spell_invis in magic.c)."""
    if target == TARGET_OBJ:
        tpl = ITEM_DEFS[obj_vnum(vo)]
        flags = item_extra_flags(vo, tpl)
        if flags.get("invis"):
            act("$p is already invisible.", ch, vo, None, TO_CHAR)
            return False
        item_affect_to_obj(vo, _new_obj_affect(sn, level, level + 12, "none", 0, "invis"), tpl)
        act("$p fades out of sight.", ch, vo, None, TO_ALL)
        return True
    if vo.get("affected_by", {}).get("invisible"):
        return False
    act("$n fades out of existence.", vo, None, None, TO_ROOM)
    affect_to_char(vo, _new_affect(sn, level, level + 12, "none", 0, "invisible"))
    chprintln(vo, "You fade out of existence.")
    return True


def spell_know_alignment(sn, level, ch, vo, target):
    """Know alignment (cf. 1stMud spell_know_alignment in magic.c)."""
    ap = vo.get("alignment", 0)
    if ap > 700:
        msg = "$N has a pure and good aura."
    elif ap > 350:
        msg = "$N is of excellent moral character."
    elif ap > 100:
        msg = "$N is often kind and thoughtful."
    elif ap > -100:
        msg = "$N doesn't have a firm moral commitment."
    elif ap > -350:
        msg = "$N lies to $S friends."
    elif ap > -700:
        msg = "$N is a black-hearted murderer."
    else:
        msg = "$N is the embodiment of pure evil!."
    act(msg, ch, None, vo, TO_CHAR)
    return True


def spell_lightning_bolt(sn, level, ch, vo, target):
    """Lightning bolt (cf. 1stMud spell_lightning_bolt in magic.c)."""
    high = level | 50
    dam = randint(high // 2, high * 2)
    if saves_spell(level, vo, DAM_LIGHTNING):
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
        chprintln(ch, "You are already invisible.")
        return True
    act("$n slowly fades out of existence.", ch, None, None, TO_ROOM)
    chprintln(ch, "You slowly fade out of existence.")
    affect_to_char(ch, _new_affect(sn, level // 2, 24, "none", 0, "invisible"))
    chprintln(ch, "Ok.")
    return True


def spell_pass_door(sn, level, ch, vo, target):
    """Pass door (cf. 1stMud spell_pass_door in magic.c)."""
    if vo.get("affected_by", {}).get("pass_door"):
        if vo is ch:
            chprintln(ch, "You are already out of phase.")
        else:
            act("$N is already shifted out of phase.", ch, None, vo, TO_CHAR)
        return False
    affect_to_char(vo, _new_affect(sn, level, number_fuzzy(level // 4), "none", 0, "pass_door"))
    act("$n turns translucent.", vo, None, None, TO_ROOM)
    chprintln(vo, "You turn translucent.")
    return True


def spell_protection_evil(sn, level, ch, vo, target):
    """Protection from evil (cf. 1stMud spell_protection_evil in magic.c)."""
    if vo.get("affected_by", {}).get("protect_evil") or vo.get("affected_by", {}).get("protect_good"):
        if vo is ch:
            chprintln(ch, "You are already protected.")
        else:
            act("$N is already protected.", ch, None, vo, TO_CHAR)
        return False
    affect_to_char(vo, _new_affect(sn, level, 24, "saves", -1, "protect_evil"))
    chprintln(vo, "You feel holy and pure.")
    if ch is not vo:
        act("$N is protected from evil.", ch, None, vo, TO_CHAR)
    return True


def spell_protection_good(sn, level, ch, vo, target):
    """Protection from good (cf. 1stMud spell_protection_good in magic.c)."""
    if vo.get("affected_by", {}).get("protect_good") or vo.get("affected_by", {}).get("protect_evil"):
        if vo is ch:
            chprintln(ch, "You are already protected.")
        else:
            act("$N is already protected.", ch, None, vo, TO_CHAR)
        return False
    affect_to_char(vo, _new_affect(sn, level, 24, "saves", -1, "protect_good"))
    chprintln(vo, "You feel aligned with darkness.")
    if ch is not vo:
        act("$N is protected from good.", ch, None, vo, TO_CHAR)
    return True


def spell_ray_of_truth(sn, level, ch, vo, target):
    """Ray of truth (cf. 1stMud spell_ray_of_truth in magic.c)."""
    victim = vo
    if is_evil(ch):
        victim = ch
        chprintln(ch, "The energy explodes inside you!")
    if is_good(victim):
        act("$n seems unharmed by the light.", victim, None, victim, TO_ROOM)
        chprintln(victim, "The light seems powerless to affect you.")
        return False
    dam = dice(level, 10)
    if saves_spell(level, victim, DAM_HOLY):
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
        chprintln(ch, "That item does not carry charges.")
        return False
    spell_lvl = tpl.get("spell_level", 0)
    if spell_lvl >= 3 * level // 2:
        chprintln(ch, "Your skills are not great enough for that.")
        return False
    max_ch = vo.get("max_charges", tpl.get("max_charges", 0))
    cur_ch = vo.get("charges", tpl.get("charges", 0))
    if max_ch == 0:
        chprintln(ch, "That item has already been recharged once.")
        return False
    chance = 40 + 2 * level - spell_lvl
    used = max_ch - cur_ch
    chance -= used * used
    chance = max(level // 2, chance)
    pct = randint(1, 100)
    if pct < chance // 2:
        act("$p glows softly.", ch, vo, None, TO_CHAR)
        act("$p glows softly.", ch, vo, None, TO_ROOM)
        vo["charges"] = max(max_ch, cur_ch)
        vo["max_charges"] = 0
        return True
    if pct <= chance:
        act("$p glows softly.", ch, vo, None, TO_CHAR)
        act("$p glows softly.", ch, vo, None, TO_ROOM)
        chargeback = max(1, used * pct // 100) if used > 0 else 0
        vo["charges"] = cur_ch + chargeback
        vo["max_charges"] = 0
        return True
    if pct <= min(95, 3 * chance // 2):
        chprintln(ch, "Nothing seems to happen.")
        if max_ch > 1:
            vo["max_charges"] = max_ch - 1
        return False
    act("$p glows brightly and explodes!", ch, vo, None, TO_CHAR)
    act("$p glows brightly and explodes!", ch, vo, None, TO_ROOM)
    if vo in ch.get("inv", []):
        ch["inv"].remove(vo)
    return False


def spell_refresh(sn, level, ch, vo, target):
    """Refresh movement (cf. 1stMud spell_refresh in magic.c)."""
    vo["move"] = min(vo.get("move", 0) + level, vo.get("max_move", 100))
    if vo.get("max_move", 100) == vo.get("move", 0):
        chprintln(vo, "You feel fully refreshed!")
    else:
        chprintln(vo, "You feel less tired.")
    if ch is not vo:
        chprintln(ch, "Ok.")
    return True


def spell_remove_curse(sn, level, ch, vo, target):
    """Remove curse (cf. 1stMud spell_remove_curse in magic.c).

    Inv scan is direct children only -- matches 1stMud carrying_first
    (magic.c:4005), which does not recurse into containers.
    """
    if target == TARGET_OBJ:
        tpl = ITEM_DEFS[obj_vnum(vo)]
        flags = item_extra_flags(vo, tpl)
        if flags.get("nodrop") or flags.get("noremove"):
            if not flags.get("nouncurse") and not saves_dispel(level + 2, tpl.get("level", 0), 0):
                set_item_extra_flag(vo, tpl, "nodrop", False)
                set_item_extra_flag(vo, tpl, "noremove", False)
                act("$p glows blue.", ch, vo, None, TO_ALL)
                return True
            act("The curse on $p is beyond your power.", ch, vo, None, TO_CHAR)
            return False
        act("There doesn't seem to be a curse on $p.", ch, vo, None, TO_CHAR)
        return False
    curse_sn = _skill_lookup("curse")
    found = False
    if curse_sn is not None and check_dispel(level, vo, curse_sn):
        chprintln(vo, "You feel better.")
        act("$n looks more relaxed.", vo, None, None, TO_ROOM)
        found = True
    for obj in list(vo.get("inv", [])):
        tpl = ITEM_DEFS[obj_vnum(obj)]
        flags = item_extra_flags(obj, tpl)
        if (flags.get("nodrop") or flags.get("noremove")) and not flags.get("nouncurse"):
            if not saves_dispel(level, tpl.get("level", 0), 0):
                set_item_extra_flag(obj, tpl, "nodrop", False)
                set_item_extra_flag(obj, tpl, "noremove", False)
                act("Your $p glows blue.", vo, obj, None, TO_CHAR)
                act("$n's $p glows blue.", vo, obj, None, TO_ROOM)
                found = True
                break
    return found


def spell_sanctuary(sn, level, ch, vo, target):
    """Sanctuary (cf. 1stMud spell_sanctuary in magic.c)."""
    if vo.get("affected_by", {}).get("sanctuary"):
        if vo is ch:
            chprintln(ch, "You are already in sanctuary.")
        else:
            act("$N is already in sanctuary.", ch, None, vo, TO_CHAR)
        return False
    affect_to_char(vo, _new_affect(sn, level, level // 6, "none", 0, "sanctuary"))
    act("$n is surrounded by a white aura.", vo, None, None, TO_ROOM)
    chprintln(vo, "You are surrounded by a white aura.")
    return True


def spell_shocking_grasp(sn, level, ch, vo, target):
    """Shocking grasp (cf. 1stMud spell_shocking_grasp in magic.c)."""
    high = level | 50
    dam = randint(high // 2, high * 2)
    if saves_spell(level, vo, DAM_LIGHTNING):
        dam //= 2
    return damage(ch, vo, dam, sn, DAM_LIGHTNING, True)


def spell_sleep(sn, level, ch, vo, target):
    """Sleep spell (cf. 1stMud spell_sleep in magic.c)."""
    if (vo.get("affected_by", {}).get("sleep")
            or (level + 2) < vo.get("level", 1)
            or saves_spell(level - 4, vo, DAM_CHARM)):
        return False
    affect_join(vo, _new_affect(sn, level, 4 + level, "none", 0, "sleep"))
    if is_awake(vo):
        chprintln(vo, "You feel very sleepy ..... zzzzzz.")
        act("$n goes to sleep.", vo, None, None, TO_ROOM)
        vo["pos"] = "sleeping"
    return True


def spell_slow(sn, level, ch, vo, target):
    """Slow spell (cf. 1stMud spell_slow in magic.c)."""
    if is_affected(vo, sn) or vo.get("affected_by", {}).get("slow"):
        if vo is ch:
            chprintln(ch, "You can't move any slower!")
        else:
            act("$N can't get any slower than that.", ch, None, vo, TO_CHAR)
        return False
    if saves_spell(level, vo, DAM_OTHER) or vo.get("imm_flags", {}).get("magic"):
        if vo is not ch:
            chprintln(ch, "Nothing seemed to happen.")
        chprintln(vo, "You feel momentarily lethargic.")
        return False
    if vo.get("affected_by", {}).get("haste"):
        haste_sn = _skill_lookup("haste")
        if haste_sn is not None and not check_dispel(level, vo, haste_sn):
            if vo is not ch:
                chprintln(ch, "Spell failed.")
            chprintln(vo, "You feel momentarily slower.")
            return False
        act("$n is moving less quickly.", vo, None, None, TO_ROOM)
        return True
    mod = -1 - (level >= 18) - (level >= 25) - (level >= 32)
    affect_to_char(vo, _new_affect(sn, level, level // 2, "dex", mod, "slow"))
    chprintln(vo, "You feel yourself slowing d o w n...")
    act("$n starts to move in slow motion.", vo, None, None, TO_ROOM)
    return True


def spell_stone_skin(sn, level, ch, vo, target):
    """Stone skin (cf. 1stMud spell_stone_skin in magic.c)."""
    # 1stMud checks ch instead of vo here (magic.c:4175). Looks wrong, and
    # the vo != ch message branch below is dead code (target is char_self,
    # so ch is vo always). Likely copy-paste from char_defensive template.
    if is_affected(ch, sn):
        if vo is ch:
            chprintln(ch, "Your skin is already as hard as a rock.")
        else:
            act("$N is already as hard as can be.", ch, None, vo, TO_CHAR)
        return False
    affect_to_char(vo, _new_affect(sn, level, level, "ac", -40))
    act("$n's skin turns to stone.", vo, None, None, TO_ROOM)
    chprintln(vo, "Your skin turns to stone.")
    return True


def spell_summon(sn, level, ch, vo, target):
    """Summon (cf. 1stMud spell_summon in magic.c).

    TODO: world-wide char search not ported. PrimeSUD is single-player.
    """
    # TODO [PRIMESUD] get_char_world for cross-room summoning
    chprintln(ch, "You failed.")
    return False


def spell_ventriloquate(sn, level, ch, vo, target):
    """Ventriloquate (cf. 1stMud spell_ventriloquate in magic.c)."""
    tail = ch.get("_target_name", "")
    parts = tail.split(None, 1)
    if len(parts) < 2:
        chprintln(ch, "What do you want to make who say?")
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
            if saves_spell(level, mob, DAM_OTHER):
                chprintln(mob, "Someone makes " + speaker + " say '" + message + "'.")
            else:
                chprintln(mob, upper(speaker) + " says '" + message + "'.")
            found = True
    return found


# -- Breath weapons (cf. 1stMud magic.c) --
# Note: *_effect functions (acid_effect, fire_effect, cold_effect,
# shock_effect, poison_effect) are environmental item-damage effects
# not yet ported.  Damage is applied; environmental effects are TODO.


def spell_acid_breath(sn, level, ch, vo, target):
    """Acid breath (cf. 1stMud spell_acid_breath in magic.c)."""
    victim = vo
    act("$n spits acid at $N.", ch, None, victim, TO_NOTVICT)
    act("$n spits a stream of corrosive acid at you.", ch, None, victim, TO_VICT)
    act("You spit acid at $N.", ch, None, victim, TO_CHAR)
    hpch = max(12, ch.get("hit", 12))
    hp_dam = randint(hpch // 11 + 1, hpch // 6)
    dice_dam = dice(level, 16)
    dam = max(hp_dam + dice_dam // 10, dice_dam + hp_dam // 10)
    if saves_spell(level, victim, DAM_ACID):
        # TODO [PRIMESUD] acid_effect(victim, level/2, dam/4, TARGET_CHAR)
        dam //= 2
    # else: TODO acid_effect(victim, level, dam, TARGET_CHAR)
    return damage(ch, victim, dam, sn, DAM_ACID, True)


def spell_fire_breath(sn, level, ch, vo, target):
    """Fire breath -- area effect (cf. 1stMud spell_fire_breath in magic.c)."""
    victim = vo
    act("$n breathes forth a cone of fire.", ch, None, victim, TO_NOTVICT)
    act("$n breathes a cone of hot fire over you!", ch, None, victim, TO_VICT)
    act("You breath forth a cone of fire.", ch, None, None, TO_CHAR)
    hpch = max(10, ch.get("hit", 10))
    hp_dam = randint(hpch // 9 + 1, hpch // 5)
    dice_dam = dice(level, 20)
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
            cur_dam = dam // 2 if saves_spell(level, vch, DAM_FIRE) else dam
        else:
            cur_dam = dam // 4 if saves_spell(level - 2, vch, DAM_FIRE) else dam // 2
        damage(ch, vch, cur_dam, sn, DAM_FIRE, True)
    return found


def spell_frost_breath(sn, level, ch, vo, target):
    """Frost breath -- area effect (cf. 1stMud spell_frost_breath in magic.c)."""
    victim = vo
    act("$n breathes out a freezing cone of frost!", ch, None, victim, TO_NOTVICT)
    act("$n breathes a freezing cone of frost over you!", ch, None, victim, TO_VICT)
    act("You breath out a cone of frost.", ch, None, None, TO_CHAR)
    hpch = max(12, ch.get("hit", 12))
    hp_dam = randint(hpch // 11 + 1, hpch // 6)
    dice_dam = dice(level, 16)
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
            cur_dam = dam // 2 if saves_spell(level, vch, DAM_COLD) else dam
        else:
            cur_dam = dam // 4 if saves_spell(level - 2, vch, DAM_COLD) else dam // 2
        damage(ch, vch, cur_dam, sn, DAM_COLD, True)
    return found


def spell_gas_breath(sn, level, ch, vo, target):
    """Gas breath -- area poison (cf. 1stMud spell_gas_breath in magic.c)."""
    act("$n breathes out a cloud of poisonous gas!", ch, None, None, TO_ROOM)
    act("You breath out a cloud of poisonous gas.", ch, None, None, TO_CHAR)
    hpch = max(16, ch.get("hit", 16))
    hp_dam = randint(hpch // 15 + 1, 8)
    dice_dam = dice(level, 12)
    dam = max(hp_dam + dice_dam // 10, dice_dam + hp_dam // 10)
    # TODO [PRIMESUD] poison_effect(room, level, dam, TARGET_ROOM)
    room = world.rooms[ch["room"]]
    found = False
    for mob_id in list(room["mobs"]):
        vch = world.chars.get(mob_id)
        if vch is None or vch is ch:
            continue
        found = True
        if saves_spell(level, vch, DAM_POISON):
            cur_dam = dam // 2
        else:
            cur_dam = dam
        damage(ch, vch, cur_dam, sn, DAM_POISON, True)
    return found


def spell_lightning_breath(sn, level, ch, vo, target):
    """Lightning breath (cf. 1stMud spell_lightning_breath in magic.c)."""
    victim = vo
    act("You breathe a bolt of lightning at $N.", ch, None, victim, TO_CHAR)
    act("$n breathes a bolt of lightning at you!", ch, None, victim, TO_VICT)
    hpch = max(10, ch.get("hit", 10))
    hp_dam = randint(hpch // 9 + 1, hpch // 5)
    dice_dam = dice(level, 20)
    dam = max(hp_dam + dice_dam // 10, dice_dam + hp_dam // 10)
    if saves_spell(level, victim, DAM_LIGHTNING):
        # TODO [PRIMESUD] shock_effect(victim, level/2, dam/4, TARGET_CHAR)
        dam //= 2
    # else: TODO shock_effect(victim, level, dam, TARGET_CHAR)
    return damage(ch, victim, dam, sn, DAM_LIGHTNING, True)


def spell_general_purpose(sn, level, ch, vo, target):
    """General purpose (cf. 1stMud spell_general_purpose in magic.c)."""
    dam = randint(25, 100)
    if saves_spell(level, vo, DAM_PIERCE):
        dam //= 2
    return damage(ch, vo, dam, sn, DAM_PIERCE, True)


def spell_high_explosive(sn, level, ch, vo, target):
    """High explosive (cf. 1stMud spell_high_explosive in magic.c)."""
    dam = randint(30, 120)
    if saves_spell(level, vo, DAM_PIERCE):
        dam //= 2
    return damage(ch, vo, dam, sn, DAM_PIERCE, True)


# -- magic2.c spells --


def spell_portal(sn, level, ch, vo, target):
    """Create a portal to another location (cf. 1stMud spell_portal in magic2.c).

    TODO: world-wide char search and portal object placement not fully ported.
    """
    # TODO [PRIMESUD] get_char_world, warp stone component, portal creation
    chprintln(ch, "You failed.")
    return False


def spell_nexus(sn, level, ch, vo, target):
    """Create a two-way portal (cf. 1stMud spell_nexus in magic2.c).

    TODO: world-wide char search and portal object placement not fully ported.
    """
    # TODO [PRIMESUD] similar to portal but creates portals in both rooms
    chprintln(ch, "You failed.")
    return False


def spell_forceshield(sn, level, ch, vo, target):
    """Force shield (cf. 1stMud spell_forceshield in magic2.c)."""
    if is_affected(vo, sn):
        if vo is ch:
            chprintln(ch, "You are already force-shielded.")
        else:
            act("$N is already force-shielded.", ch, None, vo, TO_CHAR)
        return False
    affect_to_char(vo, _new_affect(sn, level, level // 4, "ac", (level // 5) * -1, "force_shield"))
    act("A sparkling force-shield encircles $n.", vo, None, None, TO_ROOM)
    chprintln(vo, "You are encircled by a sparkling force-shield.")
    return True


def spell_staticshield(sn, level, ch, vo, target):
    """Static shield (cf. 1stMud spell_staticshield in magic2.c)."""
    if is_affected(vo, sn):
        if vo is ch:
            chprintln(ch, "You are surrounded by static charge.")
        else:
            act("$N is already surrounded by static charge.", ch, None, vo, TO_CHAR)
        return False
    affect_to_char(vo, _new_affect(sn, level, level // 3, "ac", (level // 4) * -1, "static_shield"))
    act("$n is surrounded by a pulse of static charge.", vo, None, None, TO_ROOM)
    chprintln(vo, "You are surrounded by a pulse of static charge.")
    return True


def spell_flameshield(sn, level, ch, vo, target):
    """Flame shield (cf. 1stMud spell_flameshield in magic2.c)."""
    if is_affected(vo, sn):
        if vo is ch:
            chprintln(ch, "You are already protected by fire.")
        else:
            act("$N is already protected by fire.", ch, None, vo, TO_CHAR)
        return False
    affect_to_char(vo, _new_affect(sn, level, level // 10, "ac", (level // 2) * -1, "flame_shield"))
    act("$n is shielded by red walls of flame.", vo, None, None, TO_ROOM)
    chprintln(vo, "You are shielded by red walls of flame.")
    return True


def spell_channel(sn, level, ch, vo, target):
    """Channel mana to another (cf. 1stMud spell_channel in magic2.c)."""
    if vo is ch:
        chprintln(ch, "You cannot channel energy into yourself.")
        return False
    heal = dice(3, 3) + (level // 3) * 2
    vo["mana"] = min(vo.get("mana", 0) + heal, vo.get("max_mana", 100))
    chprintln(vo, "A swirling cloud of energy engulfs you!")
    chprintln(ch, "A swirling cloud of energy slips from your fingertips.")
    return True


def spell_investiture(sn, level, ch, vo, target):
    """Convert movement to mana (cf. 1stMud spell_investiture in magic2.c)."""
    heal = ch.get("move", 0)
    vo["mana"] = min(vo.get("mana", 0) + heal, vo.get("max_mana", 100))
    vo["move"] = 0
    update_pos(vo)
    chprintln(vo, "{cThe forces of the earth fill you with energy!{x")
    # 1stMud: act("$n draws magic from the very earth!", ch, NULL, NULL, TO_ROOM)
    # [PRIMESUD] single-user, no room audience
    return True


def spell_powerstorm(sn, level, ch, vo, target):
    """Powerstorm area damage (cf. 1stMud spell_powerstorm in magic2.c)."""
    act("$n makes a firey blaze of magic engulf the room!", ch, None, None, TO_ROOM)
    room = world.rooms[ch["room"]]
    found = False
    for mob_id in list(room["mobs"]):
        vch = world.chars.get(mob_id)
        if vch is None or vch is ch:
            continue
        if is_safe_spell(ch, vch, True):
            continue
        dam = level // 3 * 2 + dice(20, 20)
        damage(ch, vch, dam, sn, DAM_FIRE, True)
        found = True
    return found


def spell_mana_burn(sn, level, ch, vo, target):
    """Mana burn (cf. 1stMud spell_mana_burn in magic2.c)."""
    dam = dice(level, 13)
    if saves_spell(level, vo, DAM_FIRE):
        dam //= 2
    # TODO [PRIMESUD] fire_effect(victim, level/2, dam/10, TARGET_CHAR)
    return damage(ch, vo, dam, sn, DAM_FIRE, True)


def spell_bark_skin(sn, level, ch, vo, target):
    """Bark skin (cf. 1stMud spell_bark_skin in magic2.c)."""
    if is_affected(vo, sn):
        if vo is ch:
            chprintln(ch, "Your skin is already covered in bark.")
        else:
            act("$N's skin is already bark.", ch, None, vo, TO_CHAR)
        return False
    affect_to_char(vo, _new_affect(sn, level, level // 3, "ac", -30 - level // 5))
    chprintln(vo, "Your skin becomes as tough as bark.")
    if ch is not vo:
        act("$N's skin becomes as tough as bark.", ch, None, vo, TO_CHAR)
    return True


def spell_spell_mantle(sn, level, ch, vo, target):
    """Spell mantle (cf. 1stMud spell_spell_mantle in magic2.c)."""
    if is_affected(vo, sn):
        if vo is ch:
            chprintln(ch, "You are already protected against magic.")
        else:
            act("$N is already protected.", ch, None, vo, TO_CHAR)
        return False
    affect_to_char(vo, _new_affect(sn, level, level // 3, "saves", 1 - level // 6))
    chprintln(vo, "You are surrounded by a glowing spell mantle.")
    if ch is not vo:
        act("$N is surrounded by a glowing spell mantle.", ch, None, vo, TO_CHAR)
    return True


def spell_animal_instinct(sn, level, ch, vo, target):
    """Animal instinct (cf. 1stMud spell_animal_instinct in magic2.c)."""
    if is_affected(vo, sn):
        if vo is ch:
            chprintln(ch, "You are already animalistic.")
        else:
            act("$N is already animalistic.", ch, None, vo, TO_CHAR)
        return False
    affect_to_char(vo, _new_affect(sn, level, level // 2, "str", level // 25))
    affect_to_char(vo, _new_affect(sn, level, level // 2, "damroll", level // 20))
    chprintln(vo, "You suddenly look like a wild beast!")
    if ch is not vo:
        act("$N suddenly grows fangs and claws!", ch, None, vo, TO_CHAR)
    return True


def spell_chaos_flare(sn, level, ch, vo, target):
    """Chaos flare -- random buff/debuff (cf. 1stMud spell_chaos_flare in magic2.c)."""
    if is_affected(vo, sn):
        if vo is ch:
            chprintln(ch, "You are already touched by chaos.")
        else:
            act("$N's skin is already touched by chaos.", ch, None, vo, TO_CHAR)
        return False
    rnum = randint(1, 100)
    if rnum <= 5:
        affect_to_char(vo, _new_affect(sn, level, level // 3, "ac", -30 - level // 5))
        chprintln(vo, "Glinting scales form over your skin!")
        if ch is not vo:
            act("$N's skin is suddenly covered with metallic scales.", ch, None, vo, TO_CHAR)
    elif rnum <= 15:
        affect_to_char(vo, _new_affect(sn, level, level // 3, "damroll", level // 20))
        chprintln(vo, "Sharp spikes jut out of your skin!")
        if ch is not vo:
            act("$N's skin is suddenly covered with jagged spikes.", ch, None, vo, TO_CHAR)
    elif rnum <= 25:
        affect_to_char(vo, _new_affect(sn, level, level // 3, "hitroll", level // 20))
        chprintln(vo, "Your eyes gleam.")
        if ch is not vo:
            act("$N's eyes gleam.", ch, None, vo, TO_CHAR)
    elif rnum <= 35:
        affect_to_char(vo, _new_affect(sn, level, level // 3, "move", level * 2))
        chprintln(vo, "You suddenly grow an extra set of legs!")
        if ch is not vo:
            act("$N suddenly grows an extra set of legs! Yipes!", ch, None, vo, TO_CHAR)
    elif rnum <= 45:
        affect_to_char(vo, _new_affect(sn, level, level // 3, "con", level // 20))
        chprintln(vo, "You grow much tougher!")
        if ch is not vo:
            act("$N seems much tougher all of a sudden.", ch, None, vo, TO_CHAR)
    elif rnum <= 50:
        affect_to_char(vo, _new_affect(sn, level, level // 3, "damroll", level // 4))
        chprintln(vo, "{YA blaze of light surrounds you!{x")
        if ch is not vo:
            act("{YA blazing halo surrounds $N!{x", ch, None, vo, TO_CHAR)
    elif rnum <= 65:
        affect_to_char(vo, _new_affect(sn, level, level // 3, "dex", 1 - level // 20))
        chprintln(vo, "One of your arms suddenly turns into a flipper.")
        if ch is not vo:
            act("One of $N's arms turns into a.. dolphin flipper.", ch, None, vo, TO_CHAR)
    elif rnum <= 75:
        affect_to_char(vo, _new_affect(sn, level, level // 3, "int", 1 - level // 20))
        chprintln(vo, "Me say wah? You suddenly feel very stoopid.")
        if ch is not vo:
            act("$N is suddenly looking very stupid.", ch, None, vo, TO_CHAR)
    elif rnum <= 85:
        affect_to_char(vo, _new_affect(sn, level, level // 3, "hit", level * 3))
        chprintln(vo, "You grow two sizes bigger!")
        if ch is not vo:
            act("$N suddenly gets bigger.. and bigger.. and bigger.", ch, None, vo, TO_CHAR)
    elif rnum <= 95:
        affect_to_char(vo, _new_affect(sn, level, level // 3, "ac", 1 + level * 2))
        chprintln(vo, "You suddenly feel quite vulnerable. They're all out to get you!")
        if ch is not vo:
            act("$N looks might paranoid all of a sudden.", ch, None, vo, TO_CHAR)
    else:
        affect_to_char(vo, _new_affect(sn, level, level // 3, "damroll", 1 - level))
        chprintln(vo, "{cAck! You turn into an oozing gelatinous blob!")
        if ch is not vo:
            act("{c$N's been turned into a green oozing blob!{c", ch, None, vo, TO_ROOM)
    return True


def spell_wild_magic(sn, level, ch, vo, target):
    """Wild magic -- random damage type (cf. 1stMud spell_wild_magic in magic2.c).

    Structure mirrors 1stMud exactly: each branch saves, halves dam, deals
    damage, then applies elemental effect, then early-returns.
    """
    dam = dice(level * 3 // 2, 14)
    numba = randint(1, 100)
    if numba <= 10:
        if saves_spell(level, vo, DAM_ACID):
            dam //= 2
        damage(ch, vo, dam, sn, DAM_ACID, True)
        # TODO [PRIMESUD] acid_effect(vo, level, dam, TARGET_CHAR)
        return True
    if numba <= 20:
        if saves_spell(level, vo, DAM_FIRE):
            dam //= 2
        damage(ch, vo, dam, sn, DAM_FIRE, True)
        # TODO [PRIMESUD] fire_effect(vo, level, dam, TARGET_CHAR)
        return True
    if numba <= 30:
        if saves_spell(level, vo, DAM_LIGHTNING):
            dam //= 2
        damage(ch, vo, dam, sn, DAM_LIGHTNING, True)
        # TODO [PRIMESUD] shock_effect(vo, level, dam, TARGET_CHAR)
        return True
    if numba <= 40:
        if saves_spell(level, vo, DAM_COLD):
            dam //= 2
        damage(ch, vo, dam, sn, DAM_COLD, True)
        # TODO [PRIMESUD] cold_effect(vo, level, dam, TARGET_CHAR)
        return True
    if numba <= 50:
        if saves_spell(level, vo, DAM_HOLY):
            dam //= 2
        damage(ch, vo, dam, sn, DAM_HOLY, True)
        return True
    if numba <= 60:
        if saves_spell(level, vo, DAM_LIGHT):
            dam //= 2
        damage(ch, vo, dam, sn, DAM_LIGHT, True)
        return True
    if numba <= 70:
        if saves_spell(level, vo, DAM_DROWNING):
            dam //= 2
        damage(ch, vo, dam, sn, DAM_DROWNING, True)
        return True
    if numba <= 80:
        if saves_spell(level, vo, DAM_DISEASE):
            dam //= 2
        damage(ch, vo, dam, sn, DAM_DISEASE, True)
        return True
    if numba <= 90:
        if saves_spell(level, vo, DAM_SLASH):
            dam //= 2
        damage(ch, vo, dam, sn, DAM_SLASH, True)
        return True
    # numba <= 100: negative -- saves halves FIRST, then /5, then all four effects
    if saves_spell(level, vo, DAM_NEGATIVE):
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
    "spell_investiture": spell_investiture,
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
    """Return True if spell sn has a registered spell_fun implementation. [PRIMESUD]"""
    sk = SKILLS.get(sn)
    if sk is None:
        return False
    return sk.get("spell_fun", "spell_null") in SPELL_FUNS


def _known_runtime_spells(player):
    """Return list of (sn, sk) pairs for spells the player knows and can use. [PRIMESUD]"""
    learned = player.get("learned", {})
    rows = []
    for sn, sk in SKILL_TABLE:
        if _implemented_spell(sn) and learned.get(sn, 0) > 0 and can_use_skill_spell(player, sn):
            rows.append((sn, sk))
    return rows



def _is_self_name(player, target_name):
    """Return True if target_name refers to the player themselves. [PRIMESUD]"""
    if not target_name:
        return False
    pname = player.get("name", "")
    return target_name == "self" or (pname and is_name(target_name, pname))


def _room_state(player):
    """Return the room state dict for the player's current room. [PRIMESUD]"""
    return world.rooms[player["room"]]


def _find_room_char(player, target_name):
    """Find a character in the player's room by name (cf. 1stMud `get_char_room` in handler.c)."""
    if _is_self_name(player, target_name):
        return player
    rs = _room_state(player)
    mob_id = get_char_room(target_name, rs["mobs"], world.chars, player)
    if mob_id is None:
        return None
    return world.chars[mob_id]


def _find_room_char_id(player, target_name):
    """Find a character id in the player's room by name (cf. 1stMud `get_char_room` in handler.c: by id)."""
    rs = _room_state(player)
    return get_char_room(target_name, rs["mobs"], world.chars, player)




def _mob_pick_name(mob):
    """Return the first keyword or short_descr word for a mob. [PRIMESUD]"""
    tpl = MOB_DEFS[mob["tpl"]]
    words = tpl.get("keywords", "").split()
    if words:
        return words[0]
    words = tpl.get("short_descr", "").split()
    if words:
        return words[0]
    return ""


def _obj_pick_name(obj):
    """Return the first keyword or short_descr word for an item. [PRIMESUD]"""
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



def _resolve_item_spell_sn(spell_name, item_obj):
    """Look up and validate a spell name from an item, returning sn or None. [PRIMESUD]"""
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
                chprintln(player, "Cast the spell on whom?")
                return (None, TARGET_NONE, None, False)
        else:
            victim_id = _find_room_char_id(player, target_name)
            if victim_id is None:
                chprintln(player, "They aren't here.")
                return (None, TARGET_NONE, None, False)
        return (world.chars[victim_id], TARGET_CHAR, victim_id, True)

    if target_type == "char_defensive":
        if not arg2:
            return (player, TARGET_CHAR, None, True)
        victim = _find_room_char(player, target_name)
        if victim is None:
            chprintln(player, "They aren't here.")
            return (None, TARGET_NONE, None, False)
        return (victim, TARGET_CHAR, None, True)

    if target_type == "char_self":
        if arg2 and not _is_self_name(player, target_name):
            chprintln(player, "You cannot cast this spell on another.")
            return (None, TARGET_NONE, None, False)
        return (player, TARGET_CHAR, None, True)

    if target_type == "obj_inventory":
        if not arg2:
            chprintln(player, "What should the spell be cast upon?")
            return (None, TARGET_NONE, None, False)
        obj = get_obj_list(target_name, player["inv"], ITEM_DEFS)
        if obj is None:
            chprintln(player, "You are not carrying that.")
            return (None, TARGET_NONE, None, False)
        return (obj, TARGET_OBJ, None, True)

    if target_type == "obj_char_offensive":
        victim_id = None
        if not arg2:
            victim_id = player.get("fighting")
            if victim_id is None:
                chprintln(player, "Cast the spell on whom or what?")
                return (None, TARGET_NONE, None, False)
            return (world.chars[victim_id], TARGET_CHAR, victim_id, True)
        victim_id = _find_room_char_id(player, target_name)
        if victim_id is not None:
            return (world.chars[victim_id], TARGET_CHAR, victim_id, True)
        rs = _room_state(player)
        obj = get_obj_list(target_name, rs["items"], ITEM_DEFS)
        if obj is not None:
            return (obj, TARGET_OBJ, None, True)
        chprintln(player, "You don't see that here.")
        return (None, TARGET_NONE, None, False)

    if target_type == "obj_char_defensive":
        if not arg2:
            return (player, TARGET_CHAR, None, True)
        victim = _find_room_char(player, target_name)
        if victim is not None:
            return (victim, TARGET_CHAR, None, True)
        obj = get_obj_list(target_name, player["inv"], ITEM_DEFS)
        if obj is not None:
            return (obj, TARGET_OBJ, None, True)
        chprintln(player, "You don't see that here.")
        return (None, TARGET_NONE, None, False)

    return (None, TARGET_NONE, None, False)



def obj_cast_spell(spell_name, level, ch, victim, obj, item_obj=None):
    """Cast spell payload from magical item (cf. 1stMud obj_cast_spell in magic.c).
    [Verified: 03/07/2026]"""
    sn = _resolve_item_spell_sn(spell_name, item_obj)
    if sn is None:
        return False

    sk = SKILLS[sn]
    tgt_type = sk.get("target", "ignore")
    vo = None
    target = TARGET_NONE

    if tgt_type == "ignore":
        vo = None
    elif tgt_type == "char_offensive":
        if victim is None:
            victim_id = ch.get("fighting")
            if victim_id is not None and victim_id in world.chars:
                victim = world.chars[victim_id]
        if victim is None:
            chprintln(ch, "You can't do that.")
            return False
        if is_safe(ch, victim) and victim is not ch:
            chprintln(ch, "Something isn't right...")
            return False
        vo = victim
        target = TARGET_CHAR
    elif tgt_type in ("char_defensive", "char_self"):
        if victim is None:
            victim = ch
        vo = victim
        target = TARGET_CHAR
    elif tgt_type == "obj_inventory":
        if obj is None:
            chprintln(ch, "You can't do that.")
            return False
        vo = obj
        target = TARGET_OBJ
    elif tgt_type == "obj_char_offensive":
        if victim is None and obj is None:
            victim_id = ch.get("fighting")
            if victim_id is not None and victim_id in world.chars:
                victim = world.chars[victim_id]
            else:
                chprintln(ch, "You can't do that.")
                return False
        if victim is not None:
            if is_safe_spell(ch, victim, False) and victim is not ch:
                # [PRIMESUD] typo fix: 1stMud has "Somehting isn't right..."
                chprintln(ch, "Something isn't right...")
                return False
            vo = victim
            target = TARGET_CHAR
        else:
            vo = obj
            target = TARGET_OBJ
    elif tgt_type == "obj_char_defensive":
        if victim is None and obj is None:
            vo = ch
            target = TARGET_CHAR
        elif victim is not None:
            vo = victim
            target = TARGET_CHAR
        else:
            vo = obj
            target = TARGET_OBJ
    else:
        _dev_item_fail(item_obj, "bad target for '" + spell_name + "'")
        return False

    fun = SPELL_FUNS.get(sk.get("spell_fun", "spell_null"), spell_null)
    # 1stMud: target_name = "" (no user-typed argument for item spells)
    ch["_target_name"] = ""
    ret = fun(sn, level, ch, vo, target)
    if "_target_name" in ch:
        del ch["_target_name"]
    # 1stmud: victim retaliates after offensive item spell (even on failed
    # spell) if still in the room
    # (skipping victim->master != ch guard -- master field not yet ported)
    if (tgt_type in ("char_offensive", "obj_char_offensive")
            and target == TARGET_CHAR and vo is not ch
            and vo.get("fighting") is None):
        for mid in world.rooms[ch["room"]]["mobs"]:
            if world.chars.get(mid) is vo:
                multi_hit(vo, ch)
                break
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
    """Cast a spell through 1stMud-style command flow (cf. 1stMud do_cast in magic.c).
    [Verified: 03/07/2026]"""
    if not args:
        known = _known_runtime_spells(player)
        if not known:
            chprintln(player, "You know no spells.")
            return None
        names = [sk["name"] for _, sk in known]
        idx = pick_from("Cast which spell?",
                        names)  # [PRIMESUD] calculator UX extension.
        if idx < 0:
            return None
        sn = known[idx][0]
        target_name = ""
    else:
        sn, target_name = find_skill_spell(player, args[0]), " ".join(args[1:])

    if (sn is None or not _implemented_spell(sn)
            or not can_use_skill_spell(player, sn)
            or player.get("learned", {}).get(sn, 0) == 0):
        chprintln(player, "You don't know any spells of that name.")
        return None

    sk = SKILLS[sn]
    if POS_ORDER[player["pos"]] < POS_ORDER[sk["min_pos"]]:
        chprintln(player, "You can't concentrate enough.")
        return None

    if not target_name:
        target_name = _pick_cast_target_name(player, sn)  # [PRIMESUD] calculator UX extension.
        if target_name is None:
            return None

    vo, target, victim_id, ok = _resolve_target(player, sn, target_name)
    if not ok:
        return None

    # 1stmud: safety guard on offensive char targets
    # (cf. do_cast TAR_CHAR_OFFENSIVE / TAR_OBJ_CHAR_OFF in magic.c)
    if target == TARGET_CHAR and vo is not player:
        tgt_type = sk.get("target")
        if tgt_type == "char_offensive" and is_safe(player, vo):
            chprintln(player, "Not on that target.")
            return None
        if tgt_type == "obj_char_offensive" and is_safe_spell(player, vo, False):
            chprintln(player, "Not on that target.")
            return None
        # 1stmud: AFF_CHARM && master == victim -> "You can't do that on your
        # own follower." -- master/follower field not yet ported

    mana = spell_mana(player, sn)
    if player["mana"] < mana:
        chprintln(player, "You don't have enough mana.")
        return None

    # 1stmud: say_spell(ch, sn) shows garbled incantation to room --
    # single-player, no observers to display to

    WaitState(player, sk.get("beats", 0))

    if randint(1, 100) > get_skill(player, sn):
        chprintln(player, "You lost your concentration.")
        check_improve(player, sn, False, 1)
        player["mana"] -= mana // 2
    else:
        player["mana"] -= mana
        fun = SPELL_FUNS.get(sk.get("spell_fun", "spell_null"), spell_null)
        player["_target_name"] = target_name  # cf. 1stMud global target_name (magic.c:266)
        ret = fun(sn, player.get("level", 1), player, vo, target)  # [PRIMESUD] classless
        del player["_target_name"]
        check_improve(player, sn, ret, 1)

    # 1stmud: victim retaliates after offensive cast (even on fizzle) if
    # still in the caster's room
    # (skipping victim->master != ch guard -- master field not yet ported)
    if (sk.get("target") in ("char_offensive", "obj_char_offensive")
            and target == TARGET_CHAR and vo is not player
            and victim_id is not None
            and victim_id in world.rooms[player["room"]]["mobs"]
            and vo.get("fighting") is None):
        multi_hit(vo, player)
    # [PRIMESUD] return full command string for calculator command history
    if not args:
        spell_name = SKILLS[sn]["name"]
        command = "cast " + ("'" + spell_name + "'" if " " in spell_name else spell_name)
        if target_name:
            command += " " + target_name
        return command
    return None
