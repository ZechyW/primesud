"""Skill/spell helper functions (cf. 1stMud multiclass.c and magic.c)."""

import classes
from config import INT_APP_LEARN
from handler import get_curr_stat, chprintln
from skills_table import SKILL_TABLE, SKILLS
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
        from magic import SPELL_FUNS  # deferred: magic imports skill_utils
        return fun in SPELL_FUNS
    except ImportError:
        return False


def skill_level(player, sn):
    """Return level at which player can use skill/spell (cf. 1stMud skill_level in multiclass.c).

    Class-aware: minimum across the player's held classes (see classes.py).
    """
    return classes.skill_level(player, sn)


def skill_rating(player, sn):
    """Return practice cost divisor/rating (cf. 1stMud skill_rating in multiclass.c).

    Class-aware: best (lowest positive) rating across held classes (see classes.py).
    """
    return classes.skill_rating(player, sn)


def can_use_skill_spell(player, sn):
    """Return whether player can use skill/spell (cf. 1stMud `can_use_skpell` in multiclass.c).

    1stMud name is can_use_skpell, a skill/spell blend; PrimeSUD keeps readable
    helper name.
    """
    return classes.can_use_skill_spell(player, sn)


def _words_prefix(name, sk_name):
    """[PRIMESUD] Sequential per-word prefix match: input word k must prefix
    skill-name word k. Lets 'cu li' or 'c l w' match 'cure light wound';
    bare 'li' still won't match (word 1 must match word 1), so 'cure light'
    vs 'lightning bolt' stays unambiguous."""
    parts = name.split()
    words = sk_name.split()
    if not parts or len(parts) > len(words):
        return False
    i = 0
    for p in parts:
        if not words[i].startswith(p):
            return False
        i += 1
    return True


def find_skill_spell(player, name):
    """Prefix-match a skill/spell, preferring usable learned entries (cf. 1stMud find_spell in magic.c).
    [Verified: 03/07/2026; [PRIMESUD] per-word prefix matching added 17/07/2026]

    [PRIMESUD] 1stMud's IsNPC branch (plain skill_lookup) not ported -- only the
    player casts through this path. Case-sensitive matching is safe: command
    input is lowercased upstream (commands.py) and skill names are lowercase.
    [PRIMESUD] Deviation from 1stMud str_prefix: matches per word via
    _words_prefix, so 'cu li' finds 'cure light'.
    """
    found = None
    if not name:
        return None
    first = name[0].lower()
    learned = player.get("learned", {})
    for sn, sk in SKILL_TABLE:
        sk_name = sk["name"]
        if sk_name[0].lower() == first and _words_prefix(name, sk_name):
            if found is None:
                found = sn
            if can_use_skill_spell(player, sn) and learned.get(sn, 0) > 0:
                return sn
    return found


def spell_mana(player, sn):
    """Return current mana cost for a spell (cf. 1stMud do_cast in magic.c and do_spells in skills.c).
    [Verified: 03/07/2026]

    Matches the live do_cast formula (50 at level+2, else max(min_mana,
    100/(2+level diff))); 1stMud's mana_cost() (returns 1000) is dead code.
    """
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
    # 1stMud: if (IsNPC(ch)) return; -- mob skills never improve
    if player.get("is_npc"):
        return
    current = player["learned"].get(sk_vnum, 0)
    sk_rating = classes.skill_rating(player, sk_vnum)
    if (not classes.can_use_skill_spell(player, sk_vnum) or sk_rating < 1
            or current <= 0 or current >= 100):
        return

    sk = SKILLS[sk_vnum]

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
            chprintln(player, "You have become better at " + sk_name + "!")
            player["xp"] += 2 * sk_rating
    else:
        inner = min(30, max(5, current // 2))
        if randint(1, 100) < inner:
            gain = randint(1, 3)
            player["learned"][sk_vnum] = min(100, current + gain)
            chprintln(player, "You learn from your mistakes, and your " + sk_name + " improves.")
            player["xp"] += 2 * sk_rating

    if player["learned"].get(sk_vnum) == 100:
        chprintln(player, "{GYou have mastered " + sk_name + "!{x")


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
    elif sn == -1:
        skill = entity["level"] * 5 // 2
    elif not classes.can_use_skill_spell(entity, sn):
        # 1stMud: if (!can_use_skpell(ch, sn)) skill = 0;
        skill = 0
    else:
        skill = entity["learned"].get(sn, 0)

    if entity.get("daze", 0) > 0:
        is_spell = sn >= 0 and SKILLS.get(sn, {}).get("spell_fun", "spell_null") != "spell_null"
        skill = skill // 2 if is_spell else skill * 2 // 3

    return max(0, min(100, skill))
