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

from classes import CLASS_TABLE, char_classes, class_lookup, class_name
from colors import capitalize, draw_line
from config import MAX_MORTAL_LEVEL
from handler import chprintln
from pager import tpage
from skill_utils import skill_level
from skills_table import SKILL_TABLE, SKILLS

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
    # 1stMud also checks is_race_skill/is_deity_skill -> 2; no race has a
    # group (only individual skills) as a racial grant, so the check is moot.
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


# -- do_grlist (cf. 1stMud do_grlist in skills.c) ----------------------------

_GRLIST_COLS = 4
_GRLIST_COL_W = 16  # [PRIMESUD] 4 x 16 = 64 exactly fits the Prime's 64-col
                     # screen -- upstream's set_cols(Cd, ch, 4, COLS_CHAR, ch)
                     # hardcodes 4 columns too, so the grid ports unchanged;
                     # the longest name ("paladin default", 15 chars) fits.


def _group_name_rows(names):
    """Chunk group names into 4-wide padded columns for tpage. [PRIMESUD helper]"""
    rows = []
    for i in range(0, len(names), _GRLIST_COLS):
        row = names[i:i + _GRLIST_COLS]
        rows.append("{W" + "".join("%-*s" % (_GRLIST_COL_W, n) for n in row) + "{x")
    return rows


def _skill_lookup_prefix(name):
    """Skill/spell sn for a (prefix of a) skill name, or -1
    (cf. 1stMud skill_lookup in magic.c: str_prefix match).

    [PRIMESUD] magic._skill_lookup is exact-match only (its callers all pass
    full internal names -- see its docstring); do_grlist needs upstream's
    prefix match against player-typed text, so it is reimplemented here
    rather than widened there.

    Args:
        name (str): Player-typed word, already lowercased.

    Returns:
        int: Skill sn, or -1 if no skill name starts with *name*.
    """
    if not name:
        return -1
    for sn, sk in SKILL_TABLE:
        if sk["name"].startswith(name):
            return sn
    return -1


def do_slist(player, args):
    """List skills by class and level, or one skill across all classes
    (cf. 1stMud do_slist in skills.c).

    Args:
        player (dict): Player state dict.
        args (list): Skill/spell or class name.
    """
    argument = " ".join(args)
    cl = class_lookup(argument)
    if cl != -1:
        # Single-pass level buckets like upstream's skill_list[level].
        buckets = {}
        for sn, sk in SKILL_TABLE:
            level = sk["skill_level"][cl]
            if level <= MAX_MORTAL_LEVEL:
                buckets.setdefault(level, []).append(sk["name"])
        lines = []
        for level in range(MAX_MORTAL_LEVEL + 1):
            names = buckets.get(level, [])
            for i in range(0, len(names), 2):
                prefix = "{cLevel {W%3d{c: " % level if i == 0 else "{x           "
                lines.append(prefix + "".join("{c%-18s      " % name
                                               for name in names[i:i + 2]) + "{x")
        tpage(lines)
        return

    sn = _skill_lookup_prefix(argument)
    if sn != -1:
        fields = []
        for cl in range(len(CLASS_TABLE)):
            level = SKILLS[sn]["skill_level"][cl]
            fields.append("{W%3s: %3s{c  " %
                          (class_name(player, cl)[:3],
                           "n/a" if level > MAX_MORTAL_LEVEL else "%03d" % level))
        # colors.capitalize -- str.capitalize missing on-device
        name = capitalize(SKILLS[sn]["name"])
        # [PRIMESUD] Upstream's six-class line is wider than the 64-col screen.
        chprintln(player, "{c" + name + ": [ " + "".join(fields[:3]) + "{x")
        chprintln(player, "{c" + " " * (len(name) + 4) +
                  "".join(fields[3:]) + "]{x")
        return

    chprintln(player, "Syntax: slist <skill>")
    chprintln(player, "        slist <spell>")
    chprintln(player, "        slist <class>")


def _grlist_known(player):
    """do_grlist with no argument: groups the player currently knows."""
    names = [GROUP_TABLE[gn][0] for gn in range(len(GROUP_TABLE))
             if gn in player.get("groups", [])]
    if not names:
        chprintln(player, "{cYou know no groups.{x")
        return
    lines = ["{cGroups you currently have:", draw_line()]
    lines.extend(_group_name_rows(names))
    tpage(lines)


def _grlist_all(player):
    """do_grlist "all": every group available to the player's classes.

    [PRIMESUD] Upstream also lists everything for IsImmortal(ch) -- no
    immortal player levels (single-player), so only group_rating gates.
    """
    names = [GROUP_TABLE[gn][0] for gn in range(len(GROUP_TABLE))
             if group_rating(player, gn) > 0]
    if not names:
        chprintln(player, "{cNo groups are available to you.{x")
        return
    lines = ["{cGroups available to you:", draw_line()]
    lines.extend(_group_name_rows(names))
    tpage(lines)


def _grlist_class(player, cl):
    """do_grlist <class>: groups available to one class."""
    cname = CLASS_TABLE[cl]["names"][0]
    names = [GROUP_TABLE[gn][0] for gn in range(len(GROUP_TABLE))
             if GROUP_TABLE[gn][1][cl] > 0]
    if not names:
        chprintln(player, "{cThere are no groups available to the {W" + cname + "{c class.{x")
        return
    lines = ["{cGroups available for the {W" + cname + "{c class:", draw_line()]
    lines.extend(_group_name_rows(names))
    tpage(lines)


def _grlist_group_spells(player, gn):
    """do_grlist <group>: spells/skills the player can use within one group."""
    rows = []
    for sn in GROUP_SKILLS[gn]:
        lvl = skill_level(player, sn)
        if lvl <= MAX_MORTAL_LEVEL:
            rows.append("{c%-5d {W%s{x" % (lvl, SKILLS[sn]["name"]))
    if not rows:
        chprintln(player, "{cNo spells available in the {W" + GROUP_TABLE[gn][0] + "{c group.{x")
        return
    lines = ["{cSpells available in {W" + GROUP_TABLE[gn][0] + "{c:{x",
             "{cLevel {WSpell{x", "{c" + draw_line() + "{x"]
    lines.extend(rows)
    tpage(lines)


def _grlist_skill_groups(player, sn):
    """do_grlist <skill>: groups that directly carry a given skill."""
    sk_name = SKILLS[sn]["name"]
    names = [GROUP_TABLE[gn][0] for gn in range(len(GROUP_TABLE))
             if sn in GROUP_SKILLS[gn]]
    if not names:
        chprintln(player, "{W" + sk_name + "{c can't be found in any groups.{x")
        return
    lines = ["{W" + sk_name + "{c is in the following groups:{x",
             "{c" + draw_line() + "{x"]
    lines.extend(_group_name_rows(names))
    tpage(lines)


def do_grlist(player, args):
    """List skill groups: known, available, by class, by group, or by skill
    (cf. 1stMud do_grlist in skills.c).

    [PRIMESUD] The creation-point economy is not ported (see module
    docstring), so the no-argument branch's "Creation points: %d" trailer is
    dropped. Long listings go through the tpage pager (upstream sendpage /
    Column buffering) in a 4 x 16 grid (see _GRLIST_COLS) sized to the
    Prime's 64-col screen.

    Args:
        player (dict): Player state dict.
        args (list): Sub-command words: none, "all", or a class/group/skill
            name (possibly multi-word, e.g. "rom basics").
    """
    argument = " ".join(args)

    if not argument:
        _grlist_known(player)
        return
    if argument == "all":
        _grlist_all(player)
        return
    cl = class_lookup(argument)
    if cl != -1:
        _grlist_class(player, cl)
        return
    gn = group_lookup(argument)
    if gn != -1:
        _grlist_group_spells(player, gn)
        return
    sn = _skill_lookup_prefix(argument)
    if sn != -1:
        _grlist_skill_groups(player, sn)
        return
    chprintln(player, "Syntax: grlist         -list your current groups")
    chprintln(player, "        grlist all     -list all available groups")
    chprintln(player, "        grlist <group> -list all spells in a group")
    chprintln(player, "        grlist <skill> -list all groups a skill is in")
    chprintln(player, "        grlist <class> -list all groups available to a class")
