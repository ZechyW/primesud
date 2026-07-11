# fmt: off
"""Class table and multiclass helpers (cf. 1stMud multiclass.c + data/classes.dat).

Players carry "classes": a list of class indices (1stMud ch->Class[] array);
a fresh character has one entry, each remort appends one (max MAX_REMORT).
NPCs have no "classes" key.
"""

from config import (LEVEL_HERO, LEVEL_IMMORTAL, MAX_LEVEL, MAX_MORTAL_LEVEL,
                     MAX_REMORT, SKILL_ADEPT)
from races import RACE_TABLE, race_lookup
from skills_table import SKILLS
from urandom import randint

CLASS_MAGE    = 0
CLASS_CLERIC  = 1
CLASS_THIEF   = 2
CLASS_WARRIOR = 3
CLASS_PALADIN = 4
CLASS_RANGER  = 5

# Indices match the per-class tuples in skills_table.py and races.py class_mult.
# "names" = remort-tier display names (tier index = remort count); needs one
# entry per config.MAX_REMORT tier (see comment there) or extra remorts
# silently reuse the last name.
# "weapon" = starting weapon type ([PRIMESUD] type string; 1stMud stores the
#            school item vnum -- 3700 mace / 3701 dagger / 3702 sword).
# Guild membership lives on rooms as a "guild" field (cf. 1stMud room->guild
# from area-file G room trailers; areas/midgaard.are, converted by
# are_to_primesud.py).
# "summary" = [PRIMESUD] one-line blurb for the chargen picker.
# "base_group"/"default_group" = groups.py names (cf. classes.dat fields);
#                 granted at creation/remort by add_base/default_groups.
CLASS_TABLE = (
    {
        "names":       ("Mage", "Wizard"),
        "attr_prime":  "int",
        "weapon":      "dagger",
        "skill_adept": 75,
        "thac0_00":    20, "thac0_32": 6,
        "hp_min":      6,  "hp_max":   8,
        "f_mana":      True,
        "base_group":  "mage basics",
        "default_group": "mage default",
        "summary":     "Offensive magic; frail early, mighty late",
    },
    {
        "names":       ("Cleric", "Priest"),
        "attr_prime":  "wis",
        "weapon":      "mace",
        "skill_adept": 75,
        "thac0_00":    20, "thac0_32": 2,
        "hp_min":      7,  "hp_max":   10,
        "f_mana":      True,
        "base_group":  "cleric basics",
        "default_group": "cleric default",
        "summary":     "Healing and protection magic; all-rounder",
    },
    {
        "names":       ("Thief", "Bandit"),
        "attr_prime":  "dex",
        "weapon":      "dagger",
        "skill_adept": 75,
        "thac0_00":    20, "thac0_32": -4,
        "hp_min":      8,  "hp_max":   13,
        "f_mana":      False,
        "base_group":  "thief basics",
        "default_group": "thief default",
        "summary":     "Backstab, stealth, and dirty tricks",
    },
    {
        "names":       ("Warrior", "Gladiator"),
        "attr_prime":  "str",
        "weapon":      "sword",
        "skill_adept": 75,
        "thac0_00":    20, "thac0_32": -10,
        "hp_min":      11, "hp_max":   15,
        "f_mana":      False,
        "base_group":  "warrior basics",
        "default_group": "warrior default",
        "summary":     "Best to-hit and HP; weapons and extra attacks",
    },
    {
        "names":       ("Paladin", "Knight"),
        "attr_prime":  "wis",
        "weapon":      "mace",
        "skill_adept": 75,
        "thac0_00":    20, "thac0_32": 2,
        "hp_min":      7,  "hp_max":   10,
        "f_mana":      True,
        "base_group":  "paladin basics",
        "default_group": "paladin default",
        "summary":     "Holy warrior; sturdy, with support magic",
    },
    {
        "names":       ("Ranger", "Strider"),
        "attr_prime":  "str",
        "weapon":      "sword",
        "skill_adept": 75,
        "thac0_00":    20, "thac0_32": -10,
        "hp_min":      11, "hp_max":   15,
        "f_mana":      False,
        "base_group":  "ranger basics",
        "default_group": "ranger default",
        "summary":     "Wilderness fighter; warrior with tricks",
    },
)


def char_classes(ch):
    """Class index list for ch; empty for NPCs. [PRIMESUD] (cf. 1stMud ch->Class[])"""
    return ch.get("classes") or []


def is_class(ch, cl):
    """True if ch holds class cl (cf. 1stMud is_class in multiclass.c)."""
    return cl in char_classes(ch)


def prime_class(ch):
    """Player-chosen prominent class (cf. 1stMud prime_class in multiclass.c).

    Returns:
        int: Class index, or -1 for NPCs / no classes.
    """
    classes = char_classes(ch)
    if not classes:
        return -1
    slot = ch.get("prime_class", 0)
    slot = max(0, min(slot, len(classes) - 1))
    return classes[slot]


def current_class(ch):
    """Most recently added class (cf. 1stMud current_class in multiclass.c)."""
    classes = char_classes(ch)
    return classes[-1] if classes else -1


def is_race_skill(ch, sn):
    """True if sn is a racial skill for ch's race (cf. 1stMud is_race_skill in multiclass.c)."""
    sk = SKILLS.get(sn)
    if sk is None:
        return False
    race = race_lookup(ch.get("race", "Human"))
    return race is not None and sk["name"] in race.get("skills", ())


def skill_level(ch, sn):
    """Level at which ch can use skill sn (cf. 1stMud skill_level in multiclass.c).

    Minimum across held classes; racial skills are level 1; skills no held
    class learns return LEVEL_IMMORTAL.
    """
    sk = SKILLS.get(sn)
    if sk is None:
        return MAX_LEVEL + 1
    if is_race_skill(ch, sn):
        return 1
    # [not ported] 1stMud also checks is_deity_skill (deity system not ported)
    lv = 999
    for cl in char_classes(ch):
        if sk["skill_level"][cl] < lv:
            lv = sk["skill_level"][cl]
    return LEVEL_IMMORTAL if lv == 999 else lv


def skill_rating(ch, sn):
    """Practice-cost rating for skill sn (cf. 1stMud skill_rating in multiclass.c).

    Best (lowest) positive rating across held classes; racial skills rate 2;
    0 if no held class can learn it.
    """
    sk = SKILLS.get(sn)
    if sk is None:
        return 0
    if is_race_skill(ch, sn):
        return 2
    # [not ported] 1stMud also checks is_deity_skill (deity system not ported)
    rate = 999
    for cl in char_classes(ch):
        r = sk["rating"][cl]
        if 0 < r < rate:
            rate = r
    return 0 if rate == 999 else rate


def can_use_skill_spell(ch, sn):
    """Whether ch can use skill/spell sn (cf. 1stMud can_use_skpell in multiclass.c)."""
    sk = SKILLS.get(sn)
    if sk is None:
        return False
    if ch.get("is_npc"):
        return True
    if is_race_skill(ch, sn):
        return True
    level = ch.get("level", 1)
    for cl in char_classes(ch):
        if level >= sk["skill_level"][cl]:
            return True
    return False


def has_spells(ch):
    """True if any held class is a caster (cf. 1stMud has_spells in multiclass.c).

    1stMud indexes class_table[i] instead of class_table[ch->Class[i]] -- an
    upstream bug (see FIXES.md); PrimeSUD checks the held classes.
    """
    if ch.get("is_npc"):
        return False
    for cl in char_classes(ch):
        if CLASS_TABLE[cl]["f_mana"]:
            return True
    return False


def is_prime_stat(ch, stat):
    """True if stat is a prime stat of any held class (cf. 1stMud is_prime_stat in multiclass.c)."""
    if ch.get("is_npc"):
        return True
    for cl in char_classes(ch):
        if CLASS_TABLE[cl]["attr_prime"] == stat:
            return True
    return False


def get_thac00(ch):
    """Worst-case THAC0 at level 0 across classes (cf. 1stMud get_thac00 in multiclass.c)."""
    temp = 0
    for cl in char_classes(ch):
        if CLASS_TABLE[cl]["thac0_00"] > temp:
            temp = CLASS_TABLE[cl]["thac0_00"]
    return temp


def get_thac32(ch):
    """Best THAC0 at level 32 across classes (cf. 1stMud get_thac32 in multiclass.c)."""
    temp = 999
    for cl in char_classes(ch):
        if CLASS_TABLE[cl]["thac0_32"] < temp:
            temp = CLASS_TABLE[cl]["thac0_32"]
    return 0 if temp == 999 else temp


def class_mult(ch):
    """XP multiplier: best (lowest) race class_mult across held classes
    (cf. 1stMud class_mult in multiclass.c)."""
    race = race_lookup(ch.get("race", "Human")) or RACE_TABLE["Human"]
    mults = race.get("class_mult", (100,) * len(CLASS_TABLE))
    temp = 999
    for cl in char_classes(ch):
        if mults[cl] < temp:
            temp = mults[cl]
    return 100 if temp == 999 else temp


def exp_per_level(ch):
    """XP needed per level (cf. 1stMud exp_per_level in skills.c).

    [PRIMESUD] Creation-point system not ported, so the points branch
    (points >= max_points) never applies: base 1000 scaled by class_mult.
    """
    if ch.get("is_npc"):
        return 1000
    return 1000 * class_mult(ch) // 100


def get_hp_gain(ch):
    """Level-up HP roll: best class die, plus fuzz per class
    (cf. 1stMud get_hp_gain in multiclass.c)."""
    gain = 0
    count = 0
    for cl in char_classes(ch):
        c = CLASS_TABLE[cl]
        roll = randint(c["hp_min"], c["hp_max"])
        if roll > gain:
            gain = roll
        count += 1
    return randint(gain, gain + count)


def skill_adept_cap(ch):
    """Practice ceiling: SKILL_ADEPT + 5 per prestige tier, max 95. [PRIMESUD]

    Tier perk (see finish_tier_reset in training.py); use-based improvement
    (check_improve) still runs to 100 independently of this cap.
    """
    return min(95, SKILL_ADEPT + 5 * ch.get("tier", 0))


def lvl_bonus(ch):
    """Remort progression multiplier (cf. 1stMud lvl_bonus in multiclass.c).

    [PRIMESUD] Integer port of the upstream float loop (adlev/inclev in
    thousandths); exact for the decimal constants involved.
    """
    adlev = len(char_classes(ch)) * 1000
    inclev = 90
    for _ in range(1, ch.get("level", 1)):
        adlev += 900 + inclev
        inclev += 9
    return (adlev + inclev) // 1000


def class_name(ch, cl):
    """Full name of class cl at the char's current remort tier
    (cf. 1stMud ClassName macro in macro.h: class_table[i].name[GetRemort(ch)])."""
    tier = min(len(char_classes(ch)) - 1, len(CLASS_TABLE[0]["names"]) - 1)
    return CLASS_TABLE[cl]["names"][max(0, tier)]


def class_who(ch):
    """Short who-list class tag (cf. 1stMud class_who in multiclass.c).

    'Mob' for NPCs; for a remort, the 2-char prime class name plus '+<remort
    count>'; otherwise the 4-char prime class name.
    """
    if ch.get("is_npc"):
        return "Mob"
    classes = char_classes(ch)
    if not classes:
        return "Mob"
    name = class_name(ch, prime_class(ch))
    if len(classes) > 1:
        name = name[:2] + "+" + str(len(classes) - 1)
    else:
        name = name[:4]
    # [PRIMESUD] prestige tier suffix (see finish_tier_reset in training.py)
    tier = ch.get("tier", 0)
    if tier:
        name = name + "*" + str(tier)
    return name


def class_long(ch):
    """Slash-joined full class names at current remort tier
    (cf. 1stMud class_long in multiclass.c)."""
    classes = char_classes(ch)
    if not classes:
        return "Mobile"
    tier = min(len(classes) - 1, len(CLASS_TABLE[0]["names"]) - 1)
    return "/".join(CLASS_TABLE[cl]["names"][tier] for cl in classes)


def calc_max_level(ch):
    """Mortal level cap: LEVEL_HERO + remort count (cf. 1stMud calc_max_level in handler.c)."""
    if ch.get("is_npc"):
        return MAX_LEVEL
    return min(MAX_MORTAL_LEVEL, LEVEL_HERO + len(char_classes(ch)) - 1)


def class_short(ch):
    """Slash-joined 4-char class names at current remort tier
    (cf. 1stMud class_short in multiclass.c)."""
    classes = char_classes(ch)
    if not classes:
        return "Mob"
    tier = min(len(classes) - 1, len(CLASS_TABLE[0]["names"]) - 1)
    return "/".join(CLASS_TABLE[cl]["names"][tier][:4] for cl in classes)
