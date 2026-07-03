"""Fighting stance table and helpers (cf. 1stMud stance_table in tables.c, stance helpers in fight.c)."""

# -- Stance constants (cf. 1stMud STANCE_* in defines.h:516-529) ---------------
STANCE_NONE     = -1
STANCE_NORMAL   = 0
STANCE_VIPER    = 1
STANCE_CRANE    = 2
STANCE_CRAB     = 3
STANCE_MONGOOSE = 4
STANCE_BULL     = 5
STANCE_MANTIS   = 6
STANCE_DRAGON   = 7
STANCE_TIGER    = 8
STANCE_MONKEY   = 9
STANCE_SWALLOW  = 10
STANCE_CURRENT  = 11
STANCE_AUTODROP = 12
MAX_STANCE      = 13

# -- Stance table (cf. 1stMud stance_table in tables.c:1625) -------------------
# (name, stance, (prereq0, prereq1), chdrop, odrop)
STANCE_TABLE = (
    ("normal", STANCE_NORMAL, (STANCE_NONE, STANCE_NONE),
     "You drop into a general fighting stance.",
     "$n drops into a general fighting stance."),
    ("viper", STANCE_VIPER, (STANCE_NORMAL, STANCE_NORMAL),
     "You arch your body into the viper fighting stance.",
     "$n arches $s body into the viper fighting stance."),
    ("crane", STANCE_CRANE, (STANCE_NORMAL, STANCE_NORMAL),
     "You swing your body into the crane fighting stance.",
     "$n swings $s body into the crane fighting stance."),
    ("crab", STANCE_CRAB, (STANCE_NORMAL, STANCE_NORMAL),
     "You squat down into the crab fighting stance.",
     "$n squats down into the crab fighting stance."),
    ("mongoose", STANCE_MONGOOSE, (STANCE_NORMAL, STANCE_NORMAL),
     "You twist into the mongoose fighting stance.",
     "$n twists into the mongoose fighting stance."),
    ("bull", STANCE_BULL, (STANCE_NORMAL, STANCE_NORMAL),
     "You hunch down into the bull fighting stance.",
     "$n hunches down into the bull fighting stance."),
    ("mantis", STANCE_MANTIS, (STANCE_CRANE, STANCE_VIPER),
     "You spin your body into the mantis fighting stance.",
     "$n spins $s body into the mantis fighting stance."),
    ("dragon", STANCE_DRAGON, (STANCE_BULL, STANCE_CRAB),
     "You coil your body into the dragon fighting stance.",
     "$n coils $s body into the dragon fighting stance."),
    ("tiger", STANCE_TIGER, (STANCE_BULL, STANCE_VIPER),
     "You lunge into the tiger fighting stance.",
     "$n lunges into the tiger fighting stance."),
    ("monkey", STANCE_MONKEY, (STANCE_CRANE, STANCE_MONGOOSE),
     "You rotate your body into the monkey fighting stance.",
     "$n rotates $s body into the monkey fighting stance."),
    ("swallow", STANCE_SWALLOW, (STANCE_CRAB, STANCE_MONGOOSE),
     "You slide into the swallow fighting stance.",
     "$n slides into the swallow fighting stance."),
    ("current", STANCE_CURRENT, (STANCE_CURRENT, STANCE_CURRENT), "", ""),
    ("autodrop", STANCE_AUTODROP, (STANCE_CURRENT, STANCE_CURRENT), "", ""),
)

# [PRIMESUD] First-combat picker blurbs for the five base stances.
_BASE_STANCE_BLURBS = (
    (STANCE_VIPER,    "viper    - swift extra strikes, slips past guards"),
    (STANCE_CRANE,    "crane    - sweeping style, strong parrying guard"),
    (STANCE_CRAB,     "crab     - low and defensive, rolls with blows"),
    (STANCE_MONGOOSE, "mongoose - light-footed, evades attacks"),
    (STANCE_BULL,     "bull     - aggressive, pure physical power"),
)


# -- improve_stance rank titles (cf. 1stMud improve_stance switch in fight.c) --
_RANK_TITLES = {
    1:   "an apprentice of",
    26:  "a trainee of",
    51:  "a student of",
    76:  "fairly experienced in",
    101: "well trained in",
    126: "highly skilled in",
    151: "an expert of",
    176: "a master of",
    200: "a grand master of",
}


def valid_stance(st):
    """True for a fightable stance id (cf. 1stMud ValidStance in macro.h)."""
    return STANCE_NONE < st < STANCE_CURRENT


def get_stance(ch, st):
    """Read a stance slot (cf. 1stMud GetStance in macro.h).

    Slots 0-10 hold trained percent (0-200); STANCE_CURRENT and
    STANCE_AUTODROP hold a stance id.
    """
    stances = ch.get("stance")
    if stances is None:
        return 0
    return stances[st]


def set_stance(ch, pos, st):
    """Write a stance slot (cf. 1stMud SetStance in macro.h)."""
    stances = ch.get("stance")
    if stances is None:
        stances = [0] * MAX_STANCE
        ch["stance"] = stances
    stances[pos] = st


def in_stance(ch, sn):
    """True if ch's current stance is sn (cf. 1stMud InStance in macro.h)."""
    return get_stance(ch, STANCE_CURRENT) == sn


def stance_name(stance):
    """Return stance name for id (cf. 1stMud stance_name in fight.c)."""
    for entry in STANCE_TABLE:
        if entry[1] == stance:
            return entry[0]
    return "unknown"


def stance_lookup(name):
    """Prefix-match a stance table index (cf. 1stMud stance_lookup in lookup.c)."""
    if not name:
        return -1
    for i in range(MAX_STANCE):
        if STANCE_TABLE[i][0].startswith(name):
            return i
    return -1


def can_use_stance(ch, stance):
    """True if ch meets the prereqs for stance (cf. 1stMud can_use_stance in fight.c)."""
    if not valid_stance(stance):
        return False

    pos = -1
    for i in range(MAX_STANCE):
        if STANCE_TABLE[i][1] == stance:
            pos = i
            break
    if pos == -1:
        return False

    if STANCE_TABLE[pos][2][0] <= STANCE_NORMAL:
        return True

    if (get_stance(ch, STANCE_TABLE[pos][2][0]) >= 200
            and get_stance(ch, STANCE_TABLE[pos][2][1]) >= 200):
        return True

    return False


def improve_stance(ch):
    """Chance to improve the current stance by 1% per hit (cf. 1stMud improve_stance in fight.c)."""
    from urandom import randint
    from handler import chprintlnf

    dice1 = randint(1, 100)
    dice2 = randint(1, 100)

    stance = get_stance(ch, STANCE_CURRENT)
    if not valid_stance(stance):
        return
    skill = get_stance(ch, stance)
    if skill >= 200:
        set_stance(ch, stance, 200)
        return
    if (dice1 > skill and dice2 > skill) or dice1 == 100 or dice2 == 100:
        set_stance(ch, stance, skill + 1)
    else:
        return
    if skill == get_stance(ch, stance):
        return

    if ch.get("is_npc"):
        return

    title = _RANK_TITLES.get(get_stance(ch, stance))
    if title is None:
        return
    chprintlnf(ch, "{RYou are now %s the %s stance.{x", title,
               stance_name(stance))


def _never_stanced(ch):
    """[PRIMESUD] True if ch has no current stance and no stance training."""
    if valid_stance(get_stance(ch, STANCE_CURRENT)):
        return False
    for st in range(STANCE_NORMAL, STANCE_CURRENT):
        if get_stance(ch, st) != 0:
            return False
    return True


def first_stance_pick(ch):
    """One-time cinematic stance choice when first entering combat. [PRIMESUD]

    Sets both STANCE_AUTODROP and STANCE_CURRENT to the chosen stance and
    arms the one-time post-battle hint.  Esc (likely accidental) shows a
    close-call flavor line and re-prompts -- a stance must be chosen.
    """
    from handler import chprintln, _pers
    from picker import pick_from
    import world

    foe = world.chars.get(ch.get("fighting"))
    foe_name = _pers(foe, ch)
    foe_name = foe_name[0].upper() + foe_name[1:]

    chprintln(ch, "")
    chprintln(ch, "{cAs you and your opponent square off, a half-forgotten"
                  " memory stirs -- long hours of drills, a teacher's voice,"
                  " the ache of repetition. Almost reflexively, your body"
                  " begins to settle into a fighting stance...{x")
    cancels = 0
    while True:
        idx = pick_from("Which stance?", [b[1] for b in _BASE_STANCE_BLURBS])
        if idx >= 0:
            break
        cancels += 1
        if cancels == 1:
            chprintln(ch, "{c" + foe_name + "'s attack whizzes past your"
                          " ear, almost punishing your moment of hesitation."
                          " Too close. You steady your frazzled nerves and"
                          " will your body to answer...{x")
        else:
            # Repeat-safe escalation: reads naturally however many times
            # the player keeps cancelling.
            chprintln(ch, "{cAnother blow hammers past, close enough to"
                          " sting. You duck and weave on instinct alone,"
                          " but instinct will not hold forever --"
                          " choose, now...{x")
    stance = _BASE_STANCE_BLURBS[idx][0]
    set_stance(ch, STANCE_AUTODROP, stance)
    set_stance(ch, STANCE_CURRENT, stance)
    for entry in STANCE_TABLE:
        if entry[1] == stance:
            chprintln(ch, entry[3])
            break
    # Runtime-only flag: not in the save allowlist, so it never persists.
    ch["_stance_tip"] = True


def first_stance_tip(ch):
    """One-time post-battle stance hint, armed by first_stance_pick. [PRIMESUD]"""
    from handler import chprintln

    if not ch.get("_stance_tip"):
        return
    ch["_stance_tip"] = False
    if ch.get("hit", 1) <= 0:
        return
    chprintln(ch, "")
    chprintln(ch, "{cYou catch your breath and shake out your limbs. The"
                  " stance felt awkward -- but with practice it will become"
                  " second nature.{x")
    chprintln(ch, "{w(Stances improve as you fight, growing stronger past"
                  " 100%. See 'sskill' for mastery, 'autostance' to change"
                  " your reflex, 'stance none' to relax, and 'help"
                  " stancetable' for details.){x")


def autodrop(ch):
    """Drop into the autostance when combat starts (cf. 1stMud autodrop in fight.c).

    [PRIMESUD] A player who has never touched stances (no autostance, no
    current stance, no training) gets the one-time first-combat stance
    pick instead.
    """
    from handler import act, chprintlnf, TO_ROOM

    stance = get_stance(ch, STANCE_AUTODROP)

    if not valid_stance(stance):
        # [PRIMESUD] first-combat stance awakening
        if not ch.get("is_npc") and _never_stanced(ch):
            first_stance_pick(ch)
        return

    if not valid_stance(get_stance(ch, STANCE_CURRENT)):
        set_stance(ch, STANCE_CURRENT, stance)
        chprintlnf(ch, "You autodrop into the %s stance. (%d%%)",
                   stance_name(stance), get_stance(ch, stance))
        act("$n autodrops into the $T stance.", ch, None, stance_name(stance),
            TO_ROOM)
