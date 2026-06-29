"""Skill/spell helper functions (cf. 1stMud multiclass.c and magic.c)."""

from skills_table import SKILL_TABLE, SKILLS
from config import MAX_MORTAL_LEVEL, INT_APP_LEARN
from handler import get_curr_stat
from terminal import tprint
from urandom import randint


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


# -- Wait / daze state ---------------------------------------------------------

def WaitState(ch, pulses):
    """Set skill lag: ch cannot act for `pulses` pulses (cf. 1stMud WaitState).

    Args:
        ch (dict): Character state dict (player or mob instance).
        pulses (int): Lag duration in combat pulses.
    """
    if pulses > ch.get("wait", 0):
        ch["wait"] = pulses


def DazeState(ch, pulses):
    """Set daze: skill checks penalised for `pulses` pulses (cf. 1stMud DazeState).

    Args:
        ch (dict): Character state dict (player or mob instance).
        pulses (int): Daze duration in raw pulses.
    """
    if pulses > ch.get("daze", 0):
        ch["daze"] = pulses


# -- Skill improvement ---------------------------------------------------------

def _int_learn(int_stat):
    """Skill improvement rate for an INT stat value (cf. 1stMud int_app[INT].learn).

    Args:
        int_stat (int): Character INT stat.

    Returns:
        int: Improvement rate (e.g. 25 at INT 13, 40 at INT 18).
    """
    return INT_APP_LEARN[int_stat]


def check_improve(player, sk_vnum, success, multiplier):
    """Attempt to improve a skill after use (cf. 1stMud check_improve in skills.c).

    Args:
        player (dict): Player state dict.
        sk_vnum (int): Skill vnum to potentially improve.
        success (bool): True if skill was used correctly (harder to improve near 100);
            False if missed/failed (learn-from-mistakes, faster at low skill).
        multiplier (int): Training context difficulty (1=easy, 6=hard); passed per
            call site as in 1stMud rather than stored in the skill table.
    """
    current = player["learned"].get(sk_vnum, 0)
    if current <= 0 or current >= 100:
        return

    sk        = SKILLS[sk_vnum]
    sk_rating = sk.get("rating", 1)

    chance = 10 * _int_learn(get_curr_stat(player, "int"))
    chance //= max(1, multiplier * sk_rating * 4)
    chance += player["level"]

    if randint(1, 1000) > chance:
        return

    sk_name = sk["name"]
    if success:
        inner = min(95, max(5, 100 - current))
        if randint(1, 100) < inner:
            player["learned"][sk_vnum] += 1
            tprint("You have become better at {}!".format(sk_name))
            player["xp"] += 2 * sk_rating
    else:
        inner = min(30, max(5, current // 2))
        if randint(1, 100) < inner:
            gain = randint(1, 3)
            player["learned"][sk_vnum] = min(100, current + gain)
            tprint("You learn from your mistakes, and your {} improves.".format(sk_name))
            player["xp"] += 2 * sk_rating

    if player["learned"].get(sk_vnum) == 100:
        tprint("{GYou have mastered %s!{x" % sk_name)


# -- Skill lookup -------------------------------------------------------------

def get_skill(entity, sn, is_mob=False):
    """Effective skill score for a player or mob, with status penalties applied
    (cf. 1stMud get_skill in handler.c).

    Args:
        entity (dict): Player or mob instance dict.
        sn (int): Skill GSN constant, or -1 for generic level-based score.
        is_mob (bool): True if entity is a mob instance.

    Returns:
        int: Effective skill percentage, clamped 0-100.
    """
    if is_mob:
        lvl = entity["level"]
        skill = lvl if lvl <= 2 else lvl // 2 + lvl // 3
    else:
        skill = entity["learned"].get(sn, 0) if sn != -1 else entity["level"] * 5 // 2

    if entity.get("daze", 0) > 0:
        is_spell = sn >= 0 and SKILLS.get(sn, {}).get("spell_fun", "spell_null") != "spell_null"
        skill = skill // 2 if is_spell else skill * 2 // 3

    return max(0, min(100, skill))
