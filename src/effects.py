"""Elemental item/room/character environmental effects (cf. 1stMud effects.c).

Split out of magic.py/combat.py into its own module to avoid an import
cycle: magic.py and combat.py both call into these functions, so effects.py
must not import either at module level (see saves_spell/_enchant_copy_template
lazy imports below, matching the existing combat.py<->magic.py pattern).
"""

import world
from world import ITEM_DEFS
from handler import act, chprintln, affect_join, affect_to_char, unequip_char, TO_ROOM, TO_ALL
from item import obj_vnum, item_extra_flags, item_affect_to_obj, create_object, item_type
from skill_utils import DazeState
from skills_table import SKILL_TABLE, GSN_POISON
from config import DAM_FIRE, DAM_COLD, DAM_LIGHTNING, DAM_POISON
from urandom import randint

TARGET_NONE = "none"
TARGET_CHAR = "char"
TARGET_OBJ = "obj"
TARGET_ROOM = "room"


def _skill_lookup(name):
    """Look up a skill/spell by exact name and return its sn. [PRIMESUD]

    Local copy of magic.py's private `_skill_lookup` -- duplicated rather
    than imported to avoid a module-load-order cycle with magic.py.
    """
    for sn, sk in SKILL_TABLE:
        if sk["name"] == name:
            return sn
    return -1


def _obj_level(obj, tpl):
    """Return obj->level, preferring instance override over template. [PRIMESUD]"""
    if isinstance(obj, dict) and "level" in obj:
        return obj["level"]
    return tpl.get("level", 0)


def _room_person(room):
    """Approximate 1stMud room->person_first for messaging. [PRIMESUD]

    PrimeSUD has no room occupant linked list; the player (if present) is
    treated as the first occupant, else the first mob, matching the only
    thing person_first is used for here (a valid `ch` argument for act()).
    """
    if room is None:
        return None
    player = world.chars.get(1)
    if player is not None and world.rooms.get(player.get("room")) is room:
        return player
    for mid in room.get("mobs", []):
        mob = world.chars.get(mid)
        if mob is not None:
            return mob
    return None


def _promote_in_place(obj, container):
    """Ensure obj is a mutable instance dict, replacing it in its container. [PRIMESUD]

    Args:
        obj: Item instance dict, or plain VNUM int.
        container: None, ("list", the_list), or ("equip", ch, slot).
    """
    if isinstance(obj, dict):
        return obj
    inst = create_object(obj)
    if container is not None:
        kind = container[0]
        if kind == "list":
            lst = container[1]
            if obj in lst:
                lst[lst.index(obj)] = inst
        else:
            _, ch, slot = container
            ch["equip"][slot] = inst
    return inst


def _remove_from_container(obj, container):
    """Extract obj from wherever it currently lives (cf. 1stMud extract_obj). [PRIMESUD]

    Equipped items are unequipped first (reversing stat/armor bonuses, cf.
    1stMud obj_from_char -> unequip_char) before being dropped from inventory.
    """
    if container is None:
        return
    kind = container[0]
    if kind == "list":
        lst = container[1]
        if obj in lst:
            lst.remove(obj)
    else:
        _, ch, slot = container
        if ch["equip"].get(slot) is obj:
            unequip_char(ch, slot)
            if obj in ch["inv"]:
                ch["inv"].remove(obj)


def _spill_contents(obj, obj_effect_fn, level, dam, owner, room):
    """Dump obj's contents into a room and recurse the effect at half force
    (cf. 1stMud acid_effect/fire_effect obj_to_room + recursive TARGET_OBJ call).

    Contents always land on a room floor (obj's room, or the carrier's
    current room) -- never back into an inventory. If neither is known
    (ownerless top-level call), contents have nowhere to go and are
    dropped, matching 1stMud's extract_obj() fallback.
    """
    contents = obj.get("contents", []) if isinstance(obj, dict) else []
    if not contents:
        return
    if room is not None:
        dest_room = room
    elif owner is not None:
        dest_room = world.rooms.get(owner.get("room"))
    else:
        dest_room = None
    for inner in list(contents):
        if dest_room is None:
            continue  # [PRIMESUD] no known destination -- item discarded (cf. extract_obj)
        items = dest_room.setdefault("items", [])
        items.append(inner)
        obj_effect_fn(inner, level // 2, dam // 2, None, dest_room, ("list", items))


# -- Acid --------------------------------------------------------------------

def _acid_obj(obj, level, dam, owner, room, container, worn=False):
    """Object-level acid effect (cf. 1stMud acid_effect TARGET_OBJ in effects.c)."""
    tpl = ITEM_DEFS[obj_vnum(obj)]
    flags = item_extra_flags(obj, tpl)
    if flags.get("burn_proof") or flags.get("nopurge") or randint(0, 4) == 0:
        return
    chance = level // 4 + dam // 10
    if chance > 25:
        chance = (chance - 25) // 2 + 25
    if chance > 50:
        chance = (chance - 50) // 2 + 50
    if flags.get("bless"):
        chance -= 5
    chance -= _obj_level(obj, tpl) * 2

    itype = item_type(obj, tpl)
    if itype in ("container", "npc_corpse", "pc_corpse"):
        msg = "$p fumes and dissolves."
    elif itype == "armor":
        msg = "$p is pitted and etched."
    elif itype == "clothing":
        msg = "$p is corroded into scrap."
    elif itype in ("staff", "wand"):
        chance -= 10
        msg = "$p corrodes and breaks."
    elif itype == "scroll":
        chance += 10
        msg = "$p is burned into waste."
    else:
        return

    chance = max(5, min(95, chance))
    if randint(1, 100) > chance:
        return

    obj = _promote_in_place(obj, container)
    ch_for_act = owner if owner is not None else _room_person(room)
    if ch_for_act is not None:
        act(msg, ch_for_act, obj, None, TO_ALL)

    if itype == "armor":
        # cf. 1stMud affect_enchant(obj): copy template stat_bonuses onto the
        # instance the first time it's ever modified in place.
        from magic import _enchant_copy_template, _new_obj_affect  # late import: magic imports effects
        if not obj.get("enchanted"):
            obj["enchanted"] = True
            _enchant_copy_template(obj, tpl)
        paf = None
        for af in obj.get("affect_list", []):
            if af.get("location") == "ac":
                paf = af
                break
        if paf is not None:
            paf["type"] = ""  # [PRIMESUD] "" sentinel for "no spell", cf. type=-1 in 1stMud
            paf["modifier"] = paf.get("modifier", 0) + 1
            paf["level"] = max(paf.get("level", 0), level)
        else:
            item_affect_to_obj(obj, _new_obj_affect("", level, -1, "ac", 1), tpl)
        if worn and owner is not None:
            a = owner.get("armor") or (100, 100, 100, 100)
            owner["armor"] = (a[0] + 1, a[1] + 1, a[2] + 1, a[3] + 1)
        return

    _spill_contents(obj, _acid_obj, level, dam, owner, room)
    _remove_from_container(obj, container)


def acid_effect(vo, level, dam, target):
    """Acid destroys/corrodes items; no direct effect on characters
    (cf. 1stMud acid_effect in effects.c)."""
    if target == TARGET_ROOM:
        room = vo
        for obj in list(room.get("items", [])):
            _acid_obj(obj, level, dam, None, room, ("list", room["items"]))
        return None

    if target == TARGET_CHAR:
        victim = vo
        for obj in list(victim.get("inv", [])):
            _acid_obj(obj, level, dam, victim, None, ("list", victim["inv"]))
        for slot, obj in list(victim.get("equip", {}).items()):
            if obj is not None:
                _acid_obj(obj, level, dam, victim, None, ("equip", victim, slot), worn=True)
        return None

    if target == TARGET_OBJ:
        _acid_obj(vo, level, dam, None, None, None)
        return None
    return None


# -- Fire ----------------------------------------------------------------------

def _fire_obj(obj, level, dam, owner, room, container):
    """Object-level fire effect (cf. 1stMud fire_effect TARGET_OBJ in effects.c)."""
    tpl = ITEM_DEFS[obj_vnum(obj)]
    flags = item_extra_flags(obj, tpl)
    if flags.get("burn_proof") or flags.get("nopurge") or randint(0, 4) == 0:
        return
    chance = level // 4 + dam // 10
    if chance > 25:
        chance = (chance - 25) // 2 + 25
    if chance > 50:
        chance = (chance - 50) // 2 + 50
    if flags.get("bless"):
        chance -= 5
    chance -= _obj_level(obj, tpl) * 2

    itype = item_type(obj, tpl)
    if itype == "container":
        msg = "$p ignites and burns!"
    elif itype == "potion":
        chance += 25
        msg = "$p bubbles and boils!"
    elif itype == "scroll":
        chance += 50
        msg = "$p crackles and burns!"
    elif itype == "staff":
        chance += 10
        msg = "$p smokes and chars!"
    elif itype == "wand":
        msg = "$p sparks and sputters!"
    elif itype == "food":
        msg = "$p blackens and crisps!"
    elif itype == "pill":
        msg = "$p melts and drips!"
    else:
        return

    chance = max(5, min(95, chance))
    if randint(1, 100) > chance:
        return

    obj = _promote_in_place(obj, container)
    ch_for_act = owner if owner is not None else _room_person(room)
    if ch_for_act is not None:
        act(msg, ch_for_act, obj, None, TO_ALL)

    _spill_contents(obj, _fire_obj, level, dam, owner, room)
    _remove_from_container(obj, container)


def fire_effect(vo, level, dam, target):
    """Fire destroys items and may blind a character with smoke
    (cf. 1stMud fire_effect in effects.c)."""
    if target == TARGET_ROOM:
        room = vo
        for obj in list(room.get("items", [])):
            _fire_obj(obj, level, dam, None, room, ("list", room["items"]))
        return None

    if target == TARGET_CHAR:
        from magic import saves_spell  # late import: magic imports effects
        victim = vo
        if (not victim.get("affected_by", {}).get("blind")
                and not saves_spell(level // 4 + dam // 20, victim, DAM_FIRE)):
            act("$n is blinded by smoke!", victim, None, None, TO_ROOM)
            chprintln(victim, "Your eyes tear up from smoke...you can't see a thing!")
            affect_to_char(victim, {
                "where": "to_affects", "type": _skill_lookup("fire breath"),
                "level": level, "duration": randint(0, level // 10),
                "location": "hitroll", "modifier": -4, "bitvector": "blind",
            })
        # [PRIMESUD] gain_condition(victim, COND_THIRST, dam/20) not ported --
        # hunger/thirst condition tracking doesn't exist (see do_drink note
        # in inventory.py).
        for obj in list(victim.get("inv", [])):
            _fire_obj(obj, level, dam, victim, None, ("list", victim["inv"]))
        for slot, obj in list(victim.get("equip", {}).items()):
            if obj is not None:
                _fire_obj(obj, level, dam, victim, None, ("equip", victim, slot))
        return None

    if target == TARGET_OBJ:
        _fire_obj(vo, level, dam, None, None, None)
        return None
    return None


# -- Cold ------------------------------------------------------------------------

def _cold_obj(obj, level, dam, owner, room, container):
    """Object-level cold effect (cf. 1stMud cold_effect TARGET_OBJ in effects.c)."""
    tpl = ITEM_DEFS[obj_vnum(obj)]
    flags = item_extra_flags(obj, tpl)
    if flags.get("burn_proof") or flags.get("nopurge") or randint(0, 4) == 0:
        return
    chance = level // 4 + dam // 10
    if chance > 25:
        chance = (chance - 25) // 2 + 25
    if chance > 50:
        chance = (chance - 50) // 2 + 50
    if flags.get("bless"):
        chance -= 5
    chance -= _obj_level(obj, tpl) * 2

    itype = item_type(obj, tpl)
    if itype == "potion":
        chance += 25
        msg = "$p freezes and shatters!"
    elif itype == "drink":
        chance += 5
        msg = "$p freezes and shatters!"
    else:
        return

    chance = max(5, min(95, chance))
    if randint(1, 100) > chance:
        return

    obj = _promote_in_place(obj, container)
    ch_for_act = owner if owner is not None else _room_person(room)
    if ch_for_act is not None:
        act(msg, ch_for_act, obj, None, TO_ALL)
    _remove_from_container(obj, container)


def cold_effect(vo, level, dam, target):
    """Cold destroys items and may chill a character with a STR debuff
    (cf. 1stMud cold_effect in effects.c)."""
    if target == TARGET_ROOM:
        room = vo
        for obj in list(room.get("items", [])):
            _cold_obj(obj, level, dam, None, room, ("list", room["items"]))
        return None

    if target == TARGET_CHAR:
        from magic import saves_spell  # late import: magic imports effects
        victim = vo
        if not saves_spell(level // 4 + dam // 20, victim, DAM_COLD):
            act("$n turns blue and shivers.", victim, None, None, TO_ROOM)
            chprintln(victim, "A chill sinks deep into your bones.")
            affect_join(victim, {
                "where": "to_affects", "type": _skill_lookup("chill touch"),
                "level": level, "duration": 6,
                "location": "str", "modifier": -1, "bitvector": "",
            })
        # [PRIMESUD] gain_condition(victim, COND_HUNGER, dam/20) not ported --
        # hunger/thirst condition tracking doesn't exist (see do_drink note
        # in inventory.py).
        for obj in list(victim.get("inv", [])):
            _cold_obj(obj, level, dam, victim, None, ("list", victim["inv"]))
        for slot, obj in list(victim.get("equip", {}).items()):
            if obj is not None:
                _cold_obj(obj, level, dam, victim, None, ("equip", victim, slot))
        return None

    if target == TARGET_OBJ:
        _cold_obj(vo, level, dam, None, None, None)
        return None
    return None


# -- Poison ----------------------------------------------------------------------

def _poison_obj(obj, level, dam, container):
    """Object-level poison effect (cf. 1stMud poison_effect TARGET_OBJ in effects.c)."""
    tpl = ITEM_DEFS[obj_vnum(obj)]
    flags = item_extra_flags(obj, tpl)
    if flags.get("burn_proof") or flags.get("bless") or randint(0, 4) == 0:
        return
    chance = level // 4 + dam // 10
    if chance > 25:
        chance = (chance - 25) // 2 + 25
    if chance > 50:
        chance = (chance - 50) // 2 + 50
    chance -= _obj_level(obj, tpl) * 2

    itype = item_type(obj, tpl)
    if itype == "food":
        pass
    elif itype == "drink":
        total = obj.get("liquid_total", tpl.get("liquid_total", 0)) if isinstance(obj, dict) else tpl.get("liquid_total", 0)
        left = obj.get("liquid_left", tpl.get("liquid_left", 0)) if isinstance(obj, dict) else tpl.get("liquid_left", 0)
        if total == left:
            return
    else:
        return

    chance = max(5, min(95, chance))
    if randint(1, 100) > chance:
        return

    obj = _promote_in_place(obj, container)
    obj["poisoned"] = True
    # Consumed by do_eat / do_drink poison branches (inventory.py).


def poison_effect(vo, level, dam, target):
    """Poison sickens a character and taints food/open drinks
    (cf. 1stMud poison_effect in effects.c)."""
    if target == TARGET_ROOM:
        room = vo
        for obj in list(room.get("items", [])):
            _poison_obj(obj, level, dam, ("list", room["items"]))
        return None

    if target == TARGET_CHAR:
        from magic import saves_spell  # late import: magic imports effects
        victim = vo
        if not saves_spell(level // 4 + dam // 20, victim, DAM_POISON):
            chprintln(victim, "You feel poison coursing through your veins.")
            act("$n looks very ill.", victim, None, None, TO_ROOM)
            affect_join(victim, {
                "where": "to_affects", "type": GSN_POISON,
                "level": level, "duration": level // 2,
                "location": "str", "modifier": -1, "bitvector": "poison",
            })
        for obj in list(victim.get("inv", [])):
            _poison_obj(obj, level, dam, ("list", victim["inv"]))
        for slot, obj in list(victim.get("equip", {}).items()):
            if obj is not None:
                _poison_obj(obj, level, dam, ("equip", victim, slot))
        return None

    if target == TARGET_OBJ:
        _poison_obj(vo, level, dam, None)
        return None
    return None


# -- Shock -----------------------------------------------------------------------

def _shock_obj(obj, level, dam, owner, room, container):
    """Object-level shock effect (cf. 1stMud shock_effect TARGET_OBJ in effects.c)."""
    tpl = ITEM_DEFS[obj_vnum(obj)]
    flags = item_extra_flags(obj, tpl)
    if flags.get("burn_proof") or flags.get("nopurge") or randint(0, 4) == 0:
        return
    chance = level // 4 + dam // 10
    if chance > 25:
        chance = (chance - 25) // 2 + 25
    if chance > 50:
        chance = (chance - 50) // 2 + 50
    if flags.get("bless"):
        chance -= 5
    chance -= _obj_level(obj, tpl) * 2

    itype = item_type(obj, tpl)
    if itype in ("wand", "staff"):
        chance += 10
        msg = "$p overloads and explodes!"
    elif itype == "jewelry":
        chance -= 10
        msg = "$p is fused into a worthless lump."
    else:
        return

    chance = max(5, min(95, chance))
    if randint(1, 100) > chance:
        return

    obj = _promote_in_place(obj, container)
    ch_for_act = owner if owner is not None else _room_person(room)
    if ch_for_act is not None:
        act(msg, ch_for_act, obj, None, TO_ALL)
    _remove_from_container(obj, container)


def shock_effect(vo, level, dam, target):
    """Shock destroys items and may daze a character
    (cf. 1stMud shock_effect in effects.c)."""
    if target == TARGET_ROOM:
        room = vo
        for obj in list(room.get("items", [])):
            _shock_obj(obj, level, dam, None, room, ("list", room["items"]))
        return None

    if target == TARGET_CHAR:
        from magic import saves_spell  # late import: magic imports effects
        victim = vo
        if not saves_spell(level // 4 + dam // 20, victim, DAM_LIGHTNING):
            chprintln(victim, "Your muscles stop responding.")
            DazeState(victim, max(12, level // 4 + dam // 20))
        for obj in list(victim.get("inv", [])):
            _shock_obj(obj, level, dam, victim, None, ("list", victim["inv"]))
        for slot, obj in list(victim.get("equip", {}).items()):
            if obj is not None:
                _shock_obj(obj, level, dam, victim, None, ("equip", victim, slot))
        return None

    if target == TARGET_OBJ:
        _shock_obj(vo, level, dam, None, None, None)
        return None
    return None
