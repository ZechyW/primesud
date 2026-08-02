"""Mob special functions (cf. 1stMud special.c).

Signature: spec_fun(ch) -> bool, matching 1stMud Spec_Fun macro.
"""

import world
from combat import do_backstab, do_flee, do_murder, is_safe, multi_hit
from config import TYPE_UNDEFINED, POS_ORDER
from game_time import time_info
from handler import (act, chprintln, is_awake, can_see,
                     TO_CHAR, TO_ROOM, TO_VICT, TO_NOTVICT, TO_ALL)
from item import obj_vnum, item_wear_flags, item_type as _item_type
from magic import SPELL_FUNS, TARGET_CHAR, _skill_lookup
from movement import move_char, do_open, do_close
from skills_table import SKILLS
from urandom import randint
from util import obj_remove
from world import ROOM_DEFS, item_tpl


def _spec_find_player(ch):
    """Find the player if in same room as ch (cf. 1stMud `spec_cast_*` in special.c: in_room->person_first scan)."""
    player = world.chars.get(1)
    if player is None or player["room"] != ch["room"]:
        return None
    return player


def spec_cast_adept(ch):
    """Cast beneficial spells on low-level players (cf. 1stMud spec_cast_adept in special.c)."""
    if not is_awake(ch):
        return False
    player = _spec_find_player(ch)
    if player is None:
        return False
    if player.get("is_npc") or player["level"] >= 11:
        return False
    if not can_see(ch, player) or randint(0, 1) != 0:
        return False

    roll = randint(0, 15)
    if roll == 0:
        spell, word = "armor", "abrazak"
    elif roll == 1:
        spell, word = "bless", "fido"
    elif roll == 2:
        spell, word = "cure blindness", "judicandus noselacri"
    elif roll == 3:
        spell, word = "cure light", "judicandus dies"
    elif roll == 4:
        spell, word = "cure poison", "judicandus sausabru"
    elif roll == 5:
        spell, word = "refresh", "candusima"
    elif roll == 6:
        spell, word = "cure disease", "judicandus eugzagz"
    else:
        return False

    act("$n utters the word '" + word + "'.", ch=ch, type=TO_ROOM)
    return _cast_spell(ch, spell, player)


def _room_persons(ch):
    """All chars in ch's room, player included (cf. 1stMud in_room->person_first walk in special.c)."""
    room = world.rooms.get(ch["room"])
    if room is None:
        return []
    persons = []
    player = world.chars.get(1)
    if player is not None and player["room"] == ch["room"]:
        persons.append(player)
    for mob_id in room["mobs"]:
        mob = world.chars.get(mob_id)
        if mob is not None:
            persons.append(mob)
    return persons


def _find_combat_victim(ch, chance=4):
    """Find a char fighting ch in its room, 1-in-chance pick per candidate (cf. 1stMud `spec_cast_*`/dragon in special.c: victim selection)."""
    for victim in _room_persons(ch):
        if victim.get("fighting") == ch.get("id") and randint(0, chance - 1) == 0:
            return victim
    return None


def _cast_spell(ch, spell_name, victim):
    """Look up spell_name and invoke its spell_fun at ch's level (cf. 1stMud skill_lookup + spell_fun call in special.c)."""
    sn = _skill_lookup(spell_name)
    if sn is None:
        return False
    sk = SKILLS.get(sn)
    if sk is None:
        return False
    fun = SPELL_FUNS.get(sk.get("spell_fun", "spell_null"))
    if fun is None:
        return False
    fun(sn, ch["level"], ch, victim, TARGET_CHAR)
    return True


def _pick_combat_spell(ch, spell_list):
    """Pick a level-appropriate spell from a (roll, min_level, name) list (cf. 1stMud `spec_cast_*` in special.c: spell for-loop)."""
    for _ in range(20):
        roll = randint(0, 15)
        for r, ml, name in spell_list:
            if isinstance(r, tuple):
                if roll < r[0] or roll > r[1]:
                    continue
            elif roll != r:
                continue
            if ch["level"] >= ml:
                return name
    return None


_CLERIC_SPELLS = (
    (0, 0, "blindness"),
    (1, 3, "cause serious"),
    (2, 7, "earthquake"),
    (3, 9, "cause critical"),
    (4, 10, "dispel evil"),
    (5, 12, "curse"),
    (6, 12, "change sex"),
    (7, 13, "flamestrike"),
    ((8, 10), 15, "harm"),
    (11, 15, "plague"),
    ((12, 15), 16, "dispel magic"),
)


_MAGE_SPELLS = (
    (0, 0, "blindness"),
    (1, 3, "chill touch"),
    (2, 7, "weaken"),
    (3, 8, "teleport"),
    (4, 11, "color spray"),
    (5, 12, "change sex"),
    (6, 13, "energy drain"),
    ((7, 9), 15, "fireball"),
    (10, 20, "plague"),
    ((11, 15), 20, "acid blast"),
)


def _spec_cast_combat(ch, spell_list):
    """Shared combat-casting logic for mage/cleric (cf. 1stMud spec_cast_mage/cleric in special.c)."""
    if ch.get("pos") != "fighting":
        return False
    victim = _find_combat_victim(ch)
    if victim is None:
        return False
    spell = _pick_combat_spell(ch, spell_list)
    if spell is None:
        return False
    return _cast_spell(ch, spell, victim)


def spec_cast_cleric(ch):
    """Offensive cleric spells during combat (cf. 1stMud spec_cast_cleric in special.c)."""
    return _spec_cast_combat(ch, _CLERIC_SPELLS)


def spec_cast_mage(ch):
    """Offensive mage spells during combat (cf. 1stMud spec_cast_mage in special.c)."""
    return _spec_cast_combat(ch, _MAGE_SPELLS)


_UNDEAD_SPELLS = (
    (0, 0, "curse"),
    (1, 3, "weaken"),
    (2, 6, "chill touch"),
    (3, 9, "blindness"),
    (4, 12, "poison"),
    (5, 15, "energy drain"),
    (6, 18, "harm"),
    (7, 21, "teleport"),
    (8, 20, "plague"),
    ((9, 15), 18, "harm"),
)


def spec_cast_undead(ch):
    """Offensive undead spells during combat (cf. 1stMud spec_cast_undead in special.c)."""
    return _spec_cast_combat(ch, _UNDEAD_SPELLS)


def spec_cast_judge(ch):
    """Cast high explosive during combat (cf. 1stMud spec_cast_judge in special.c)."""
    if ch.get("pos") != "fighting":
        return False
    victim = _find_combat_victim(ch)
    if victim is None:
        return False
    return _cast_spell(ch, "high explosive", victim)


def _dragon(ch, spell_name):
    """Breathe on a char fighting the dragon (cf. 1stMud dragon in special.c)."""
    if ch.get("pos") != "fighting":
        return False
    victim = _find_combat_victim(ch, 8)
    if victim is None:
        return False
    return _cast_spell(ch, spell_name, victim)


def spec_breath_acid(ch):
    """Acid breath attack (cf. 1stMud spec_breath_acid in special.c)."""
    return _dragon(ch, "acid breath")


def spec_breath_fire(ch):
    """Fire breath attack (cf. 1stMud spec_breath_fire in special.c)."""
    return _dragon(ch, "fire breath")


def spec_breath_frost(ch):
    """Frost breath attack (cf. 1stMud spec_breath_frost in special.c)."""
    return _dragon(ch, "frost breath")


def spec_breath_gas(ch):
    """Room-wide gas breath attack (cf. 1stMud spec_breath_gas in special.c)."""
    if ch.get("pos") != "fighting":
        return False
    return _cast_spell(ch, "gas breath", None)


def spec_breath_lightning(ch):
    """Lightning breath attack (cf. 1stMud spec_breath_lightning in special.c)."""
    return _dragon(ch, "lightning breath")


def spec_breath_any(ch):
    """Random breath attack (cf. 1stMud spec_breath_any in special.c)."""
    if ch.get("pos") != "fighting":
        return False
    roll = randint(0, 7)
    if roll == 0:
        return spec_breath_fire(ch)
    if roll in (1, 2):
        return spec_breath_lightning(ch)
    if roll == 3:
        return spec_breath_gas(ch)
    if roll == 4:
        return spec_breath_acid(ch)
    return spec_breath_frost(ch)


def spec_poison(ch):
    """Poisonous bite during combat (cf. 1stMud spec_poison in special.c)."""
    victim = world.chars.get(ch.get("fighting"))
    if (ch.get("pos") != "fighting" or victim is None
            or randint(1, 100) > 2 * ch["level"]):
        return False
    act("You bite $N!", ch, None, victim, TO_CHAR)
    act("$n bites $N!", ch, None, victim, TO_NOTVICT)
    act("$n bites you!", ch, None, victim, TO_VICT)
    _cast_spell(ch, "poison", victim)
    return True  # 1stMud returns true even if the spell lookup failed


def spec_thief(ch):
    """Steal coins from players in the room (cf. 1stMud spec_thief in special.c)."""
    if ch.get("pos") != "standing":
        return False
    # 1stMud walks all room persons; the player is the only non-NPC
    # candidate, and can never be immortal [PRIMESUD]
    victim = _spec_find_player(ch)
    if victim is None:
        return False
    if randint(0, 31) != 0 or not can_see(ch, victim):
        return False
    if is_awake(victim) and randint(0, ch["level"]) == 0:
        act("You discover $n's hands in your wallet!", ch, None, victim, TO_VICT)
        act("$N discovers $n's hands in $S wallet!", ch, None, victim, TO_NOTVICT)
        return True
    gold = victim.get("gold", 0) * min(randint(1, 20), ch["level"] // 2) // 100
    gold = min(gold, ch["level"] * ch["level"] * 10)
    ch["gold"] = ch.get("gold", 0) + gold
    victim["gold"] = victim.get("gold", 0) - gold
    silver = victim.get("silver", 0) * min(randint(1, 20), ch["level"] // 2) // 100
    silver = min(silver, ch["level"] * ch["level"] * 25)
    ch["silver"] = ch.get("silver", 0) + silver
    victim["silver"] = victim.get("silver", 0) - silver
    return True


def spec_guard(ch):
    """Attack evil characters fighting in the room (cf. 1stMud spec_guard in special.c)."""
    if not is_awake(ch) or ch.get("fighting") is not None:
        return False
    # [PRIMESUD] PLR_OUTLAW yell-and-attack branch not ported (outlaw flag
    # not modeled)
    max_evil = 300
    ech = None
    for victim in _room_persons(ch):
        if (victim.get("fighting") is not None
                and victim["fighting"] != ch["id"]
                and victim.get("alignment", 0) < max_evil):
            max_evil = victim["alignment"]
            ech = victim
    if ech is not None:
        # [PRIMESUD] added missing closing quote
        act("$n screams 'PROTECT THE INNOCENT!!  BANZAI!!'", ch, None, None, TO_ROOM)
        multi_hit(ch, ech, TYPE_UNDEFINED)
        return True
    return False


def spec_executioner(ch):
    """Attack outlawed players (cf. 1stMud spec_executioner in special.c)."""
    # [PRIMESUD] TODO stub -- PLR_OUTLAW flag not modeled; nothing to execute
    return False


def spec_janitor(ch):
    """Pick up trash from the room (cf. 1stMud spec_janitor in special.c)."""
    if not is_awake(ch):
        return False
    rs = world.rooms.get(ch["room"])
    if rs is None:
        return False
    for trash in rs["items"]:
        tpl = item_tpl(trash)
        if "take" not in item_wear_flags(trash, tpl):
            continue
        # [PRIMESUD] can_loot check not ported (no corpse ownership)
        # Room items may be plain vnums (area resets) or instance dicts
        if isinstance(trash, dict):
            cost = trash.get("cost", tpl.get("value", 0))
        else:
            cost = tpl.get("value", 0)
        if _item_type(trash, tpl) in ("drink", "trash") or cost < 10:
            act("$n picks up some trash.", ch, None, None, TO_ROOM)
            obj_remove(rs["items"], trash)
            ch["inv"].append(trash)
            return True
    return False


# Gangland vnums (cf. 1stMud vnums.h; all live in hood.are's 2100-2199 range)
MOB_VNUM_GROUP_TROLLS = 2100
MOB_VNUM_GROUP_OGRES = 2101
MOB_VNUM_PATROLMAN = 2106
OBJ_VNUM_WHISTLE = 2116

# Shared taunts for the troll/ogre gang wars (cf. 1stMud spec_troll_member /
# spec_ogre_member switch blocks; index = number_range(0,6)). Slot 2 differs
# per gang and is filled in by the caller.
_GANG_TAUNTS = (
    "$n yells 'I've been looking for you, punk!'",
    # [PRIMESUD] 1stMud's ogre variant carries a stray trailing apostrophe
    "With a scream of rage, $n attacks $N.",
    None,
    "$n cracks his knuckles and says 'Do ya feel lucky?'",
    "$n says 'There's no cops to save you this time!'",
    "$n says 'Time to join your brother, spud.'",
    "$n says 'Let's rock.'",
)


def _spec_gang_member(ch, rival_group, rival_taunt):
    """Attack a rival gang member in the room (cf. 1stMud spec_troll_member/spec_ogre_member in special.c)."""
    aff = ch["affected_by"]
    if (not is_awake(ch) or aff.get("calm") or aff.get("charm")
            or ch.get("fighting") is not None):
        return False
    victim = None
    count = 0
    for vch in _room_persons(ch):
        if not vch.get("is_npc") or vch is ch:
            continue
        if vch["tpl"] == MOB_VNUM_PATROLMAN:
            return False
        if (world.MOB_DEFS.get(vch["tpl"], {}).get("group") == rival_group
                and ch["level"] > vch["level"] - 2
                and not is_safe(ch, vch)):
            if randint(0, count) == 0:
                victim = vch
            count += 1
    if victim is None:
        return False

    message = _GANG_TAUNTS[randint(0, 6)]
    if message is None:
        message = rival_taunt
    act(message, ch, None, victim, TO_ALL)
    multi_hit(ch, victim, TYPE_UNDEFINED)
    return True


def spec_troll_member(ch):
    """Troll gangster attacks ogre gangsters (cf. 1stMud spec_troll_member in special.c)."""
    return _spec_gang_member(
        ch, MOB_VNUM_GROUP_OGRES,
        "$n says 'What's slimy Ogre trash like you doing around here?'")


def spec_ogre_member(ch):
    """Ogre gangster attacks troll gangsters (cf. 1stMud spec_ogre_member in special.c)."""
    return _spec_gang_member(
        ch, MOB_VNUM_GROUP_TROLLS,
        "$n says 'What's Troll filth like you doing around here?'")


def spec_patrolman(ch):
    """Break up fights, whistling for backup (cf. 1stMud spec_patrolman in special.c)."""
    aff = ch["affected_by"]
    if (not is_awake(ch) or aff.get("calm") or aff.get("charm")
            or ch.get("fighting") is not None):
        return False
    victim = None
    count = 0
    for vch in _room_persons(ch):
        if vch is ch:
            continue
        if vch.get("fighting") is not None:
            opp = world.chars.get(vch["fighting"])
            if opp is None:
                continue
            if randint(0, count) == 0:
                victim = vch if vch["level"] > opp["level"] else opp
            count += 1
    if victim is None or (victim.get("is_npc")
                          and world.MOB_DEFS.get(victim["tpl"], {}).get("spec_fun")
                          == world.MOB_DEFS.get(ch["tpl"], {}).get("spec_fun")):
        return False

    eq = ch["equip"]
    whistle = None
    for slot in ("neck_1", "neck_2"):
        obj = eq.get(slot)
        if obj is not None and obj_vnum(obj) == OBJ_VNUM_WHISTLE:
            whistle = obj
            break
    if whistle is not None:
        act("You blow down hard on $p.", ch, whistle, None, TO_CHAR)
        act("$n blows on $p, ***WHEEEEEEEEEEEET***", ch, whistle, None, TO_ROOM)
        # Same-area broadcast, excluding ch's room (cf. 1stMud char_first walk)
        player = world.chars.get(1)
        if player is not None and player["room"] != ch["room"]:
            ch_area = ROOM_DEFS.get(ch["room"], {}).get("area")
            pl_area = ROOM_DEFS.get(player["room"], {}).get("area")
            if ch_area is not None and ch_area == pl_area:
                chprintln(player, "You hear a shrill whistling sound.")

    roll = randint(0, 6)
    if roll == 0:
        message = "$n yells 'All roit! All roit! break it up!'"
    elif roll == 1:
        message = "$n says 'Society's to blame, but what's a bloke to do?'"
    elif roll == 2:
        message = "$n mumbles 'bloody kids will be the death of us all.'"
    elif roll == 3:
        message = "$n shouts 'Stop that! Stop that!' and attacks."
    elif roll == 4:
        message = "$n pulls out his billy and goes to work."
    elif roll == 5:
        message = "$n sighs in resignation and proceeds to break up the fight."
    else:
        message = "$n says 'Settle down, you hooligans!'"
    act(message, ch, None, None, TO_ALL)
    multi_hit(ch, victim, TYPE_UNDEFINED)
    return True


# Mayor's scripted gate-walk path strings (cf. 1stMud spec_mayor open_path/
# close_path in special.c). Digits 0-3 step n/e/s/w; letters speak/wake/
# sleep; 'O'/'C' open/close the "gate"-keyworded exit in the mayor's current
# room (only Midgaard's west and east gates carry that keyword -- north and
# south never had one upstream either, so the mayor never touches them,
# matching 1stMud exactly); '.' ends the walk.
_MAYOR_OPEN_PATH = "W3a3003b33000c111d0d111Oe333333Oe22c222112212111a1S."
_MAYOR_CLOSE_PATH = "W3a3003b33000c111d0d111CE333333CE22c222112212111a1S."

# [PRIMESUD] module-level state mirrors 1stMud's `static` locals in
# spec_mayor (special.c:1006-1008): they persist for the process lifetime,
# shared across every mob using this spec_fun. Stock Midgaard has exactly
# one mayor, so a single-slot latch here is equivalent.
_mayor_path = None
_mayor_pos = 0
_mayor_move = False


def spec_mayor(ch):
    """Mayor's scripted day/night gate walk (cf. 1stMud spec_mayor in special.c).

    Fights like a mage if attacked; otherwise advances one token of the
    open/close path per call once the path is latched at 6am/8pm.

    Returns:
        bool: Always False -- the walk never consumes the mob's normal turn
            (cf. 1stMud spec_mayor: every path branch falls through to the
            trailing ``return false``).
    """
    global _mayor_path, _mayor_pos, _mayor_move

    if not _mayor_move:
        if time_info["hour"] == 6:
            _mayor_path = _MAYOR_OPEN_PATH
            _mayor_move = True
            _mayor_pos = 0
        if time_info["hour"] == 20:
            _mayor_path = _MAYOR_CLOSE_PATH
            _mayor_move = True
            _mayor_pos = 0

    if ch.get("fighting") is not None:
        return spec_cast_mage(ch)

    if not _mayor_move or POS_ORDER[ch["pos"]] < POS_ORDER["sleeping"]:
        return False

    token = _mayor_path[_mayor_pos]
    if token in "0123":
        move_char(ch, "nesw"[int(token)])
    elif token == "W":
        ch["pos"] = "standing"
        act("$n awakens and groans loudly.", ch, None, None, TO_ROOM)
    elif token == "S":
        ch["pos"] = "sleeping"
        act("$n lies down and falls asleep.", ch, None, None, TO_ROOM)
    elif token == "a":
        act("$n says 'Hello Honey!'", ch, None, None, TO_ROOM)
    elif token == "b":
        act("$n says 'What a view!  I must do something about that dump!'",
            ch, None, None, TO_ROOM)
    elif token == "c":
        act("$n says 'Vandals!  Youngsters have no respect for anything!'",
            ch, None, None, TO_ROOM)
    elif token == "d":
        act("$n says 'Good day, citizens!'", ch, None, None, TO_ROOM)
    elif token == "e":
        act("$n says 'I hereby declare the city of Midgaard open!'",
            ch, None, None, TO_ROOM)
    elif token == "E":
        act("$n says 'I hereby declare the city of Midgaard closed!'",
            ch, None, None, TO_ROOM)
    elif token == "O":
        do_open(ch, ["gate"])
    elif token == "C":
        do_close(ch, ["gate"])
    elif token == ".":
        _mayor_move = False

    _mayor_pos += 1
    return False


def spec_nasty(ch):
    """Ambush a wealthy-looking player, then rob or flee once fighting (cf. 1stMud spec_nasty in special.c)."""
    if not is_awake(ch):
        return False
    if ch.get("pos") != "fighting":
        # 1stMud walks all room persons for a victim whose level is above
        # ch's but within 10; the player is the only non-NPC candidate
        # [PRIMESUD]
        victim = _spec_find_player(ch)
        if (victim is not None and victim["level"] > ch["level"]
                and victim["level"] < ch["level"] + 10):
            do_backstab(ch, [], victim=victim)
            if ch.get("pos") != "fighting":
                do_murder(ch, [], victim=victim)
            return True
        return False
    victim = world.chars.get(ch.get("fighting"))
    if victim is None:
        return False
    roll = randint(0, 3)
    if roll == 0:
        act("$n rips apart your coin purse, spilling your gold!",
            ch, None, victim, TO_VICT)
        # [PRIMESUD] "his" -> "$S"
        act("You slash apart $N's coin purse and gather $S gold.",
            ch, None, victim, TO_CHAR)
        act("$N's coin purse is ripped apart!", ch, None, victim, TO_NOTVICT)
        gold = victim.get("gold", 0) // 10
        victim["gold"] = victim.get("gold", 0) - gold
        ch["gold"] = ch.get("gold", 0) + gold
        return True
    if roll == 1:
        do_flee(ch, [])
        return True
    return False


def spec_questmaster(ch):
    """Questmaster fights like a mage (cf. 1stMud spec_questmaster in special.c)."""
    if ch.get("fighting") is not None:
        return spec_cast_mage(ch)
    return False


def spec_triviamob(ch):
    """Trivia mob fights like a mage (cf. 1stMud spec_triviamob in special.c)."""
    if ch.get("fighting") is not None:
        return spec_cast_mage(ch)
    return False


def spec_registar(ch):
    """Registar fights like a mage (cf. 1stMud spec_registar in special.c)."""
    if ch.get("fighting") is not None:
        return spec_cast_mage(ch)
    return False


def spec_fido(ch):
    """Devour the first NPC corpse in the room (cf. 1stMud spec_fido in special.c).

    Corpse contents spill onto the room floor and the corpse is removed,
    matching 1stMud's obj_from_obj/obj_to_room + extract_obj sequence.

    Returns:
        bool: True if a corpse was eaten (mob's turn is consumed).
    """
    if not is_awake(ch):
        return False
    rs = world.rooms.get(ch["room"])
    if rs is None:
        return False
    for corpse in list(rs.get("items", [])):
        tpl = item_tpl(corpse)
        if _item_type(corpse, tpl) != "npc_corpse":
            continue
        act("$n savagely devours a corpse.", ch, None, None, TO_ROOM)
        for inner in corpse.get("contents", []):
            rs["items"].append(inner)
        obj_remove(rs["items"], corpse)
        return True
    return False


SPEC_TABLE = {
    "spec_breath_any": spec_breath_any,
    "spec_breath_acid": spec_breath_acid,
    "spec_breath_fire": spec_breath_fire,
    "spec_breath_frost": spec_breath_frost,
    "spec_breath_gas": spec_breath_gas,
    "spec_breath_lightning": spec_breath_lightning,
    "spec_cast_adept": spec_cast_adept,
    "spec_cast_cleric": spec_cast_cleric,
    "spec_cast_judge": spec_cast_judge,
    "spec_cast_mage": spec_cast_mage,
    "spec_cast_undead": spec_cast_undead,
    "spec_executioner": spec_executioner,
    "spec_fido": spec_fido,
    "spec_guard": spec_guard,
    "spec_janitor": spec_janitor,
    "spec_mayor": spec_mayor,
    "spec_nasty": spec_nasty,
    "spec_ogre_member": spec_ogre_member,
    "spec_patrolman": spec_patrolman,
    "spec_poison": spec_poison,
    "spec_questmaster": spec_questmaster,
    "spec_registar": spec_registar,
    "spec_thief": spec_thief,
    "spec_triviamob": spec_triviamob,
    "spec_troll_member": spec_troll_member,
}
