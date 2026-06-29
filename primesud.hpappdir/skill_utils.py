"""Skill/spell helper functions (cf. 1stMud multiclass.c and magic.c)."""

from skills_table import SKILL_TABLE, SKILLS
from config import MAX_MORTAL_LEVEL


def is_spell(sn):
    """Return True if skill-table entry is a spell."""
    sk = SKILLS.get(sn)
    return sk is not None and sk.get("spell_fun", "spell_null") != "spell_null"


def is_runtime_spell(sn):
    """Return True if spell has a runtime implementation registered."""
    sk = SKILLS.get(sn)
    if sk is None:
        return False
    fun = sk.get("spell_fun", "spell_null")
    if fun == "spell_null":
        return False
    try:
        from magic import SPELL_FUNS
        return fun in SPELL_FUNS
    except ImportError:
        return False


def skill_level(player, sn):
    """Return level at which player can use skill/spell (cf. 1stMud skill_level in multiclass.c).

    PrimeSUD is classless for now, so world.py flattens level to earliest class.
    """
    sk = SKILLS.get(sn)
    return sk.get("skill_level", MAX_MORTAL_LEVEL + 1) if sk else MAX_MORTAL_LEVEL + 1


def skill_rating(player, sn):
    """Return practice cost divisor/rating (cf. 1stMud skill_rating in multiclass.c).

    PrimeSUD is classless for now, so world.py flattens rating to lowest positive
    class rating.
    """
    sk = SKILLS.get(sn)
    return sk.get("rating", 0) if sk else 0


def can_use_skill_spell(player, sn):
    """Return whether player can use skill/spell (cf. 1stMud `can_use_skpell` in multiclass.c).

    1stMud name is can_use_skpell, a skill/spell blend; PrimeSUD keeps readable
    helper name.
    """
    return sn in SKILLS and player.get("level", 1) >= skill_level(player, sn)


def find_skill_spell(player, name):
    """Prefix-match a skill/spell, preferring usable learned entries (cf. 1stMud find_spell in magic.c)."""
    found = None
    if not name:
        return None
    first = name[0].lower()
    learned = player.get("learned", {})
    for sn, sk in SKILL_TABLE:
        sk_name = sk["name"]
        if sk_name[0].lower() == first and sk_name.startswith(name):
            if found is None:
                found = sn
            if can_use_skill_spell(player, sn) and learned.get(sn, 0) > 0:
                return sn
    return found


def spell_mana(player, sn):
    """Return current mana cost for spell display (cf. 1stMud do_spells in skills.c)."""
    sk = SKILLS[sn]
    level = skill_level(player, sn)
    if player.get("level", 1) + 2 == level:
        return 50
    return max(sk.get("min_mana", 0), 100 // (2 + player.get("level", 1) - level))
