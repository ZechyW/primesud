"""Mob special functions (cf. 1stMud special.c).

Signature: spec_fun(ch) -> bool, matching 1stMud Spec_Fun macro.
"""

from urandom import randint

import world
from actor import act, is_awake, can_see, TO_ROOM


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

    from magic import _skill_lookup, SPELL_FUNS, TARGET_CHAR
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

    sn = _skill_lookup(spell)
    if sn is None:
        return False
    from skills_table import SKILLS
    sk = SKILLS.get(sn)
    if sk is None:
        return False
    fun = SPELL_FUNS.get(sk.get("spell_fun", "spell_null"))
    if fun is None:
        return False
    act("$n utters the word '%s'." % word, ch=ch, type=TO_ROOM)
    fun(sn, ch["level"], ch, player, TARGET_CHAR)
    return True


def _find_combat_victim(ch):
    """Find a victim the mob is fighting in its room (cf. 1stMud `spec_cast_*` in special.c: victim selection)."""
    player = _spec_find_player(ch)
    if player is None:
        return None
    if player.get("fighting") == ch.get("id") and randint(0, 3) == 0:
        return player
    return None


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
    from magic import _skill_lookup, SPELL_FUNS, TARGET_CHAR
    sn = _skill_lookup(spell)
    if sn is None:
        return False
    from skills_table import SKILLS
    sk = SKILLS.get(sn)
    if sk is None:
        return False
    fun = SPELL_FUNS.get(sk.get("spell_fun", "spell_null"))
    if fun is None:
        return False
    fun(sn, ch["level"], ch, victim, TARGET_CHAR)
    return True


def spec_cast_cleric(ch):
    """Offensive cleric spells during combat (cf. 1stMud spec_cast_cleric in special.c)."""
    return _spec_cast_combat(ch, _CLERIC_SPELLS)


def spec_cast_mage(ch):
    """Offensive mage spells during combat (cf. 1stMud spec_cast_mage in special.c)."""
    return _spec_cast_combat(ch, _MAGE_SPELLS)


def spec_fido(ch):
    """Eat corpses in room (cf. 1stMud spec_fido in special.c)."""
    # [PRIMESUD] stub -- corpse system not yet ported
    return False


SPEC_TABLE = {
    "spec_cast_adept": spec_cast_adept,
    "spec_cast_cleric": spec_cast_cleric,
    "spec_cast_mage": spec_cast_mage,
    "spec_fido": spec_fido,
}
