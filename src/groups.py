# fmt: off
"""Skill groups (cf. 1stMud group_table from data/groups.dat; helpers in skills.c).

Groups bundle skills and sub-groups; gaining a group grants every member
skill at 1% and marks all member groups known. Characters get their class's
base + default groups at creation/remort (1stMud nanny default path); other
groups cost trains at a gain trainer (do_gain in training.py).

[PRIMESUD] The creation-point economy (gen_groups customization, gain
points, >40-point exp_per_level escalation) is not ported: default-path
characters never exceed the flat exp rate, so it has no observable effect
single-player. group_add's deduct flag is dropped with it.
"""

from classes import CLASS_TABLE, char_classes
from skills_table import SKILLS

# Ported verbatim from 1stMud data/groups.dat. Rating 6-tuple order matches
# CLASS_TABLE (mage, cleric, thief, warrior, paladin, ranger); -1 = not
# available to that class, 0 = free (basics). Members are skill names or
# other group names, resolved below at import.
# groups.dat lists "invis"; the skill is "invisibility" (1stMud skill_lookup
# is prefix-based) -- stored under the full name.
GROUP_TABLE = (
    ("rom basics",      (0, 0, 0, 0, 0, 0),
     ("scrolls", "staves", "wands", "recall")),
    ("mage basics",     (0, -1, -1, -1, -1, -1), ("dagger",)),
    ("cleric basics",   (-1, 0, -1, -1, -1, -1), ("mace",)),
    ("thief basics",    (-1, -1, 0, -1, -1, -1), ("dagger", "steal")),
    ("warrior basics",  (-1, -1, -1, 0, -1, -1), ("sword", "second attack")),
    ("paladin basics",  (-1, -1, -1, -1, 0, -1), ("mace",)),
    ("ranger basics",   (-1, -1, -1, -1, -1, 0), ("sword", "second attack")),
    ("mage default",    (40, -1, -1, -1, -1, -1),
     ("lore", "beguiling", "combat", "detection", "enhancement", "illusion",
      "maladictions", "protective", "transportation", "weather")),
    ("cleric default",  (-1, 40, -1, -1, -1, -1),
     ("flail", "attack", "creation", "curative", "benedictions", "detection",
      "healing", "maladictions", "protective", "shield block",
      "transportation", "weather")),
    ("thief default",   (-1, -1, 40, -1, -1, -1),
     ("mace", "sword", "backstab", "disarm", "dodge", "second attack", "trip",
      "hide", "peek", "pick lock", "sneak")),
    ("warrior default", (-1, -1, -1, 40, -1, -1),
     ("weaponsmaster", "shield block", "bash", "disarm", "enhanced damage",
      "parry", "rescue", "third attack")),
    ("paladin default", (-1, -1, -1, -1, 40, -1),
     ("flail", "attack", "creation", "curative", "benedictions", "detection",
      "healing", "maladictions", "protective", "shield block",
      "transportation", "weather")),
    ("ranger default",  (-1, -1, -1, -1, -1, 40),
     ("weaponsmaster", "shield block", "bash", "disarm", "enhanced damage",
      "parry", "rescue", "third attack")),
    ("weaponsmaster",   (40, 40, 40, 20, 40, 20),
     ("axe", "dagger", "flail", "mace", "polearm", "spear", "sword", "whip")),
    ("attack",          (-1, 5, -1, 8, 5, 8),
     ("demonfire", "dispel evil", "dispel good", "earthquake", "flamestrike",
      "heat metal", "ray of truth")),
    ("beguiling",       (4, -1, 6, -1, -1, -1),
     ("calm", "charm person", "sleep")),
    ("benedictions",    (-1, 4, -1, 8, 4, 8),
     ("bless", "calm", "frenzy", "holy word", "remove curse")),
    ("combat",          (6, -1, 10, 9, -1, 9),
     ("acid blast", "burning hands", "chain lightning", "chill touch",
      "fireball", "lightning bolt", "magic missile", "shocking grasp",
      "color spray")),
    ("creation",        (4, 4, 8, 8, 4, 8),
     ("continual light", "create food", "create spring", "create water",
      "create rose", "floating disc")),
    ("curative",        (-1, 4, -1, 8, 4, 8),
     ("cure blindness", "cure disease", "cure poison")),
    ("detection",       (4, 3, 6, -1, 3, -1),
     ("detect evil", "detect good", "detect hidden", "detect invis",
      "detect magic", "detect poison", "farsight", "identify",
      "know alignment", "locate object")),
    ("draconian",       (8, -1, -1, -1, -1, -1),
     ("acid breath", "fire breath", "frost breath", "gas breath",
      "lightning breath")),
    ("enchantment",     (6, -1, -1, -1, -1, -1),
     ("enchant armor", "enchant weapon", "fireproof", "recharge")),
    ("enhancement",     (5, -1, 9, 9, -1, 9),
     ("giant strength", "haste", "infravision", "refresh")),
    ("harmful",         (-1, 3, -1, 6, 3, 6),
     ("cause critical", "cause light", "cause serious", "harm")),
    ("healing",         (-1, 3, -1, 6, 3, 6),
     ("cure critical", "cure light", "cure serious", "heal", "mass healing",
      "refresh")),
    ("illusion",        (4, -1, 7, -1, -1, -1),
     ("invisibility", "mass invis", "ventriloquate")),
    ("maladictions",    (5, 5, 9, 9, 5, 9),
     ("blindness", "change sex", "curse", "energy drain", "plague", "poison",
      "slow", "weaken")),
    ("protective",      (4, 4, 7, 8, 4, 8),
     ("armor", "cancellation", "dispel magic", "fireproof",
      "protection evil", "protection good", "sanctuary", "shield",
      "stone skin")),
    ("transportation",  (4, 4, 8, 9, 4, 9),
     ("fly", "gate", "nexus", "pass door", "portal", "summon", "teleport",
      "word of recall")),
    ("weather",         (4, 4, 8, 8, 4, 8),
     ("call lightning", "control weather", "faerie fire", "faerie fog",
      "lightning bolt")),
)

# -- Resolve member names to skill sns / group indices at import ---------------
_name_to_gn = {}
for _gn in range(len(GROUP_TABLE)):
    _name_to_gn[GROUP_TABLE[_gn][0]] = _gn
_name_to_sn = {}
for _sn in SKILLS:
    _name_to_sn[SKILLS[_sn]["name"]] = _sn

GROUP_SKILLS = []     # per gn: tuple of member skill sns
GROUP_SUBGROUPS = []  # per gn: tuple of member group indices
for _gn in range(len(GROUP_TABLE)):
    _sns = []
    _gns = []
    for _m in GROUP_TABLE[_gn][2]:
        if _m in _name_to_gn:
            _gns.append(_name_to_gn[_m])
        else:
            _sns.append(_name_to_sn[_m])  # KeyError = data bug, fail at import
    GROUP_SKILLS.append(tuple(_sns))
    GROUP_SUBGROUPS.append(tuple(_gns))
del _name_to_gn, _name_to_sn, _sns, _gns, _gn, _sn, _m


def group_lookup(name):
    """Group index for a (prefix of a) group name, or -1
    (cf. 1stMud group_lookup in skills.c: str_prefix match)."""
    if not name:
        return -1
    for gn in range(len(GROUP_TABLE)):
        if GROUP_TABLE[gn][0].startswith(name):
            return gn
    return -1


def group_rating(ch, gn):
    """Best (lowest positive) rating across held classes, 0 if unavailable
    (cf. 1stMud group_rating in multiclass.c)."""
    if gn < 0 or gn >= len(GROUP_TABLE):
        return 0
    # [not ported] 1stMud also checks is_race_skill/is_deity_skill -> 2
    rate = 999
    for cl in char_classes(ch):
        r = GROUP_TABLE[gn][1][cl]
        if 0 < r < rate:
            rate = r
    return 0 if rate == 999 else rate


def gn_add(player, gn):
    """Grant group gn: mark known, learn member skills at 1%, recurse into
    member groups (cf. 1stMud gn_add + group_add in skills.c)."""
    if gn < 0 or gn >= len(GROUP_TABLE):
        return
    if gn not in player["groups"]:
        player["groups"].append(gn)
    for sn in GROUP_SKILLS[gn]:
        if player["learned"].get(sn, 0) == 0:
            player["learned"][sn] = 1
    for sub in GROUP_SUBGROUPS[gn]:
        gn_add(player, sub)


def add_base_groups(player):
    """Grant the basics group of every held class
    (cf. 1stMud add_base_groups in multiclass.c)."""
    for cl in char_classes(player):
        gn_add(player, group_lookup(CLASS_TABLE[cl]["base_group"]))


def add_default_groups(player):
    """Grant the default group of every held class
    (cf. 1stMud add_default_groups in multiclass.c).

    [PRIMESUD] Upstream also charges 40/50 creation points -- points economy
    not ported (see module docstring).
    """
    for cl in char_classes(player):
        gn_add(player, group_lookup(CLASS_TABLE[cl]["default_group"]))
