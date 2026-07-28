"""Auto-quest system: questmaster missions and quest points (cf. 1stMud quest.c).

Quest Code (c) 1996 Ryan Addams; 1stMud ROM derivative (c) 2001-2004 Markanth.

[PRIMESUD] Target tracking is by template vnum, not live instance pointer
(1stMud: pcdata->quest.mob / .obj / .room CharData/ObjData/RoomIndex
pointers).  Any mob with the target vnum qualifies as kill/find/deliver
target -- kinder single-player UX, robust against area resets and
save/load, and serializes cleanly.

Player quest state (cf. 1stMud QuestData in structs.h), stored flat on the
player dict for save simplicity:
    quest_points     quest points (pcdata->quest.points)
    quest_status     QUEST_* value (pcdata->quest.status)
    quest_time       world ticks left on quest, or cooldown when QUEST_NONE
                     (assigned/balanced in real minutes; see config.mins_to_ticks)
    quest_mob        target mob template vnum, 0 if none
    quest_obj        target obj template vnum, 0 if none
    quest_room       target room vnum, 0 if none
    quest_giver      questmaster template vnum, 0 if none
    quest_mob_name / quest_room_name / quest_area_name
                     display names captured at generate time so 'quest info'
                     never forces an area load [PRIMESUD]
"""

import world
from world import ROOM_DEFS, MOB_DEFS, ITEM_DEFS, AREA_DEFS, AREA_LEVELS
from world import _ensure_area_by_tag
from classes import lvl_bonus
from comm import do_function, do_say
from config import MAX_LEVEL, mins_to_ticks, ticks_to_mins, on_minute
from races import RACE_TABLE, race_lookup
from handler import (chprintln, act, is_evil, is_good, is_name, can_see_obj,
                     unequip_char, equip_char, TO_CHAR, TO_ROOM, TO_VICT,
                     TO_NOTVICT)
from item import (create_object, obj_vnum, get_obj_list, item_extra_flags,
                  item_wear_flags)
from picker import pick_from
from urandom import randint
from util import num_str, pad_right

# -- Quest types (cf. 1stMud quest_t in defines.h) -----------------------------
QUEST_RETURN_FINDMOB  = -5
QUEST_RETURN_FINDROOM = -4
QUEST_RETURN_DELIVER  = -3
QUEST_RETURN_RETRIEVE = -2
QUEST_RETURN_KILL     = -1
QUEST_NONE            = 0
QUEST_KILL            = 1
QUEST_RETRIEVE        = 2
QUEST_DELIVER         = 3
QUEST_FINDROOM        = 4
QUEST_FINDMOB         = 5

QUEST_TIME = 20  # cf. 1stMud defines.h; base cooldown between quests

# Quest token objects (cf. 1stMud OBJ_VNUM_QUEST1..4 in vnums.h)
_QUEST_PIECES = (214, 215, 216, 217)

# Questmaster shop vnums (cf. 1stMud OBJ_VNUM_QUEST_* in vnums.h)
_OBJ_QUEST_AURA   = 201
_OBJ_QUEST_BPLATE = 204
_OBJ_QUEST_SHIELD = 210

# (name, vnum, cost) cf. 1stMud quest_table in quest.c.
# [PRIMESUD] "nohunger" (vnum 0, 3000qp) omitted -- hunger/thirst not ported.
QUEST_TABLE = (
    ("aura",         _OBJ_QUEST_AURA, 2600),
    ("sword",         203,            2500),
    ("breastplate",  _OBJ_QUEST_BPLATE, 2500),
    ("boots",         205,            2500),
    ("gloves",        206,            2500),
    ("flame",         207,            2500),
    ("helm",          208,            2300),
    ("bag",           209,            1000),
    ("shield",       _OBJ_QUEST_SHIELD, 750),
    ("regeneration",  211,             700),
    ("invisibility",  212,             500),
    ("trivia",        200,             100),
)

# [PRIMESUD] Areas never used for quest targets: limbo (1stMud excludes
# vnum < 100), quest (the questmaster's own area), immort (imm zone).
_QUEST_AREA_EXCLUDE = ("limbo", "quest", "immort")

# cf. 1stMud qmob_desc / qobj_desc in quest.c
_QMOB_DESC = ("fiend", "criminal", "monster", "traitor", "outcast")
_QOBJ_DESC = ("treasure", "artifact", "item", "keepsake")


def chance(num):
    """Roll percentile against num (cf. 1stMud chance in quest.c)."""
    return randint(1, 100) <= num


def is_quester(ch):
    """True if ch is on an active quest (cf. 1stMud IsQuester in macro.h)."""
    return not ch.get("is_npc") and ch.get("quest_status", QUEST_NONE) != QUEST_NONE


def add_qp(ch, qp):
    """Add quest points to ch, return amount granted (cf. 1stMud add_qp in quest.c)."""
    # 1stMud: BONUS_QP event multiplier -- [PRIMESUD] bonus events not ported
    ch["quest_points"] = ch.get("quest_points", 0) + qp
    return qp


def _intstr(n, word):
    """Return "N word(s)" (cf. 1stMud intstr in string.c)."""
    return str(n) + " " + word + ("" if n == 1 else "s")


def mob_tell(player, mob, text):
    """Show an NPC tell to the player (cf. 1stMud mob_tell in quest.c).

    Colours follow CTAG(_TELLS1)/(_TELLS2): cyan / bright cyan.
    """
    name = MOB_DEFS[mob["tpl"]]["short_descr"]
    chprintln(player, "{c" + name + " tells you '{C" + text + "{c'{x")


def _find_spec_mob(player, spec_name):
    """Find NPC with given spec_fun in player's room (cf. 1stMud do_quest questman scan). [PRIMESUD] helper."""
    rs = world.rooms[player["room"]]
    for mid in rs["mobs"]:
        inst = world.chars.get(mid)
        if inst is None or not inst.get("is_npc"):
            continue
        if MOB_DEFS[inst["tpl"]].get("spec_fun") == spec_name:
            return inst
    return None


def _prefix(arg, word):
    """True if arg is a non-empty prefix of word (cf. 1stMud !str_prefix)."""
    return arg != "" and word.startswith(arg)


def end_quest(player, time):
    """Clear quest state, set cooldown/penalty timer (cf. 1stMud end_quest in quest.c).

    Args:
        player (dict): Player state dict.
        time (int): Cooldown in real minutes (1stMud values verbatim).
    """
    if player.get("is_npc"):
        return
    player["quest_status"] = QUEST_NONE
    player["quest_giver"] = 0
    player["quest_time"] = mins_to_ticks(time) if time > 0 else 0
    player["quest_mob"] = 0
    player["quest_obj"] = 0
    player["quest_room"] = 0
    player["quest_mob_name"] = ""
    player["quest_room_name"] = ""
    player["quest_area_name"] = ""


def quest_level_diff(player, mob_level):
    """True if mob level is within questing range of player (cf. 1stMud quest_level_diff in quest.c).

    Band is 10 + lvl_bonus(ch) either side (quest.c:1025), so remorts quest
    against a wider level range. [PRIMESUD] IsImmortal short-circuit omitted
    (no immortals).
    """
    bonus = 10 + lvl_bonus(player)
    return (mob_level - bonus) <= player["level"] <= (mob_level + bonus)


def quest_target_ok(tpl, rdef):
    """Shared mob-eligibility filter for quest and gquest targets
    (cf. 1stMud random_quest_mob in quest.c / generate_gquest in gquest.c).

    Level and alignment checks are the callers' business; this covers the
    exclusions common to both systems.
    """
    if tpl.get("shop"):
        return False
    act_f = tpl.get("act_flags", {})
    if (act_f.get("train") or act_f.get("practice")
            or act_f.get("is_healer") or act_f.get("healer")
            or act_f.get("pet") or act_f.get("gain")):
        return False
    imm = tpl.get("imm_flags", {})
    if imm.get("weapon") or imm.get("magic"):
        return False
    if tpl.get("affected_by", {}).get("charm"):
        return False
    room_f = rdef.get("flags", {})
    if room_f.get("pet_shop"):
        return False
    if (act_f.get("sentinel")
            and (room_f.get("private") or room_f.get("solitary")
                 or room_f.get("safe"))):
        return False
    # 1stMud: clan-area check -- [PRIMESUD] no clans
    return True


def quest_area_def(tag):
    """Load area by tag and return its AREA_DEFS entry, or None. [PRIMESUD] helper."""
    _ensure_area_by_tag(tag)
    for a in AREA_DEFS:
        if a["tag"] == tag:
            return a if "resets" in a else None
    return None


def _merged_act_flags(tpl):
    """Race act flags merged under template act_flags, as create_mobile
    does at spawn (cf. 1stMud db2.c:88-136). [PRIMESUD] helper."""
    race = race_lookup(tpl.get("race", "Human")) or RACE_TABLE["Human"]
    merged = dict(race.get("act", {}))
    merged.update(tpl.get("act_flags", {}))
    return merged


def _random_quest_mob(player, deliver=False):
    """Pick a random quest target from area reset data.

    [PRIMESUD] Replaces 1stMud random_quest_mob (quest.c), which scans all
    live mobs in the world.  PrimeSUD lazy-loads areas, so instead: pick a
    level-appropriate area, load only that area, and pick a mob template
    from its "M" resets (the reset room stands in for victim->in_room).
    Exclusion filters ported from 1stMud where they map onto template data.

    Args:
        player (dict): Player state dict.
        deliver (bool): Skip aggressive/spec-fun mobs.  [PRIMESUD] 1stMud
            strips those from the live DELIVER victim; vnum matching can't
            mutate one instance, so unsuitable templates are excluded here.

    Returns:
        tuple: (mob_vnum, room_vnum, area_def) or None if no target found.
    """
    tags = []
    for tag, (lo, hi) in AREA_LEVELS.items():
        if tag in _QUEST_AREA_EXCLUDE:
            continue
        # area level band must intersect player's questing range
        if lo - 10 <= player["level"] <= hi + 10:
            tags.append(tag)

    while tags:
        tag = tags.pop(randint(0, len(tags) - 1))
        adef = quest_area_def(tag)
        if adef is None:
            continue
        candidates = []
        for entry in adef["resets"]:
            if entry[0] != "M":
                continue
            mvnum, rvnum = entry[1], entry[3]
            tpl = MOB_DEFS._data.get(mvnum)
            rdef = ROOM_DEFS._data.get(rvnum)
            if tpl is None or rdef is None:
                continue
            # -- exclusions cf. 1stMud random_quest_mob (quest.c) --
            if not quest_level_diff(player, tpl.get("level", 1)):
                continue
            if not quest_target_ok(tpl, rdef):
                continue
            # [PRIMESUD] see docstring; race act flags merged as in
            # create_mobile so race-based aggression is caught too
            if deliver and (_merged_act_flags(tpl).get("aggressive")
                            or tpl.get("spec_fun")):
                continue
            # 1stMud: same-alignment targets skipped half the time
            if is_evil(tpl) and is_evil(player) and chance(50):
                continue
            if is_good(tpl) and is_good(player) and chance(50):
                continue
            # 1stMud: questman-vnum check -- [PRIMESUD] questmaster area
            # excluded by tag above
            candidates.append((mvnum, rvnum))
        if candidates:
            mvnum, rvnum = candidates[randint(0, len(candidates) - 1)]
            return (mvnum, rvnum, adef)
    return None


def quest_lookup(name):
    """Index of name in QUEST_TABLE, or -1 (cf. 1stMud quest_lookup in quest.c)."""
    if not name:
        return -1
    for i, entry in enumerate(QUEST_TABLE):
        if is_name(name, entry[0]):
            return i
    return -1


def qobj_lookup(obj):
    """Index of obj's vnum in QUEST_TABLE, or -1 (cf. 1stMud qobj_lookup in quest.c)."""
    vnum = obj_vnum(obj)
    for i, entry in enumerate(QUEST_TABLE):
        if entry[1] == vnum:
            return i
    return -1


def _quest_can_complete(player):
    """Whether the current quest can receive its reward now. [PRIMESUD]"""
    if player.get("quest_time", 0) <= 0:
        return False
    status = player.get("quest_status", QUEST_NONE)
    if status in (QUEST_RETURN_KILL, QUEST_RETURN_FINDMOB,
                  QUEST_RETURN_FINDROOM, QUEST_RETURN_DELIVER):
        return True
    if status != QUEST_RETURN_RETRIEVE:
        return False
    ovnum = player.get("quest_obj", 0)
    return any(obj_vnum(obj) == ovnum for obj in player["inv"])


def _pick_quest_table_item(title):
    """Pick an item from the questmaster's reward table. [PRIMESUD]"""
    labels = []
    for _name, vnum, cost in QUEST_TABLE:
        tpl = ITEM_DEFS.get(vnum)
        labels.append("[" + num_str(cost) + "qp] "
                      + (tpl["short_descr"] if tpl else "Unavailable"))
    idx = pick_from(title, labels)
    return QUEST_TABLE[idx][0] if idx >= 0 else None


def obj_cost(obj):
    """Quest-point cost of obj: table cost, else obj cost (cf. 1stMud obj_cost in quest.c)."""
    i = qobj_lookup(obj)
    if i != -1:
        return QUEST_TABLE[i][2]
    if isinstance(obj, dict) and "cost" in obj:
        return obj["cost"]
    return ITEM_DEFS[obj_vnum(obj)].get("cost", 0)


def _add_apply(obj, location, modifier, level):
    """Join a permanent apply onto obj's affect_list (cf. 1stMud add_apply/affect_join_obj in quest.c).

    Updates an existing same-location apply in place instead of stacking,
    so repeat update_questobj calls (level-ups) rescale rather than pile up.
    """
    for af in obj.setdefault("affect_list", []):
        if (af.get("location") == location and af.get("type", 0) == 0
                and not af.get("bitvector")
                and af.get("where", "to_object") == "to_object"):
            af["level"] = level
            af["modifier"] = modifier
            return
    obj["affect_list"].append({
        "type": 0, "level": level, "duration": -1, "location": location,
        "modifier": modifier, "bitvector": "", "where": "to_object",
    })


def update_questobj(ch, obj):
    """Rescale a quest item to ch's level (cf. 1stMud update_questobj in quest.c).

    If obj is currently equipped, use update_all_qobjs instead so the
    char's stat modifiers are reapplied.
    """
    tpl = ITEM_DEFS[obj_vnum(obj)]
    if not item_extra_flags(obj, tpl).get("quest"):
        return
    lvl = ch["level"]
    bonus = max(5, lvl // 10)
    pbonus = max(5, lvl // 5)

    obj["level"] = lvl
    # 1stMud: obj->condition = -1 -- [PRIMESUD] item condition not modeled
    obj["cost"] = obj_cost(obj)
    wf = dict(item_wear_flags(obj, tpl))
    if not wf.get("no_sac"):
        wf["no_sac"] = True
        obj["wear_flags"] = wf
    ef = dict(item_extra_flags(obj, tpl))
    if not ef.get("burn_proof"):
        ef["burn_proof"] = True
        obj["extra_flags"] = ef

    vnum = obj_vnum(obj)
    if vnum in (_OBJ_QUEST_BPLATE, _OBJ_QUEST_SHIELD):
        _add_apply(obj, "damroll", pbonus, lvl)
        _add_apply(obj, "hitroll", pbonus, lvl)
    elif vnum == _OBJ_QUEST_AURA:
        _add_apply(obj, "hit", max(50, lvl), lvl)
        _add_apply(obj, "mana", max(50, lvl), lvl)
        _add_apply(obj, "move", max(50, lvl), lvl)

    itype = tpl.get("type")
    if itype == "container":
        # 1stMud: negative weight + capacity scaling --
        # [PRIMESUD] container weight/capacity not modeled
        pass
    elif itype == "weapon":
        # 1stMud: value[1] = Max(15, level); value[2] = 4 (5 at half max level)
        # one_hit/do_compare/spell_identify read instance dice first
        obj["dice"] = (max(15, lvl), 4 if lvl < MAX_LEVEL // 2 else 5, 0)
        _add_apply(obj, "damroll", bonus, lvl)
        _add_apply(obj, "hitroll", bonus, lvl)
    elif itype == "armor":
        v = max(20, lvl)
        obj["armor"] = (v, v, v, 5 * v // 6)
    elif itype == "light":
        # 1stMud: value[2] = -1 (infinite) -- [PRIMESUD] light fuel not modeled
        pass
    # 1stMud staff/portal branches: no such items in the quest table


def rescale_quest_gear(ch):
    """Data-only rescale of quest items in inventory and equipment. [PRIMESUD]

    Used on game load: armor/dice instance overrides are regenerated rather
    than saved. Caller must reapply equipment mods afterwards (reset_char);
    for live rescaling use update_all_qobjs instead.
    """
    for obj in ch["inv"]:
        update_questobj(ch, obj)
    for obj in ch["equip"].values():
        if obj is not None:
            update_questobj(ch, obj)


def update_all_qobjs(ch):
    """Rescale all carried/worn quest items (cf. 1stMud update_all_qobjs in quest.c)."""
    for obj in list(ch["inv"]):
        update_questobj(ch, obj)
    for slot in list(ch["equip"].keys()):
        obj = ch["equip"].get(slot)
        if obj is None:
            continue
        if item_extra_flags(obj, ITEM_DEFS[obj_vnum(obj)]).get("quest"):
            # cf. 1stMud: unequip/equip cycle reapplies stat modifiers
            unequip_char(ch, slot)
            update_questobj(ch, obj)
            equip_char(ch, obj, slot)


def create_quest_obj(player, vnum=-1):
    """Create a quest token object owned by this quest (cf. 1stMud create_quest_obj in quest.c).

    Returns:
        dict: Object instance, or None on failure.
    """
    if vnum <= 0:
        vnum = _QUEST_PIECES[randint(0, 3)]  # cf. random_quest_piece
    obj = create_object(vnum)
    if obj is None:
        return None
    # 1stMud: replace_str(&obj->owner, ch->name) anti-theft owner tag --
    # [PRIMESUD] skipped, single player
    # 1stMud formula is in minutes; quest_time stores ticks, so convert out
    # and back (obj timers also decrement per world tick)
    obj["timer"] = mins_to_ticks(
        (4 * ticks_to_mins(player["quest_time"]) + 10) // 3)
    return obj


def generate_quest(player, questman, qtype=QUEST_NONE):
    """Roll and assign a new quest (cf. 1stMud generate_quest in quest.c).

    Args:
        player (dict): Player state dict.
        questman (dict): Questmaster mob instance.
        qtype (int): Forced quest type, or QUEST_NONE for a random roll.
    """
    # [PRIMESUD] type rolled before the pick (1stMud rolls after) so DELIVER
    # can filter its target; the rolls are independent of the pick
    if qtype > QUEST_NONE:
        status = qtype
    elif chance(10):
        status = QUEST_FINDMOB if chance(50) else QUEST_FINDROOM
    elif chance(20):
        status = QUEST_RETRIEVE if chance(50) else QUEST_DELIVER
    else:
        status = QUEST_KILL

    picked = _random_quest_mob(player, deliver=(status == QUEST_DELIVER))
    if picked is None:
        mob_tell(player, questman,
                 "I'm sorry, but I don't have any quests for you at this time.")
        mob_tell(player, questman, "Try again later.")
        end_quest(player, QUEST_TIME // 10)
        return
    mvnum, rvnum, adef = picked
    mob_name = MOB_DEFS._data[mvnum]["short_descr"]
    room_name = ROOM_DEFS._data[rvnum]["name"]
    area_name = adef.get("name", adef["tag"])

    player["quest_giver"] = questman["tpl"]
    player["quest_room"] = rvnum
    player["quest_room_name"] = room_name
    player["quest_area_name"] = area_name
    player["quest_time"] = mins_to_ticks(randint(15, 30))
    player["quest_status"] = status

    if status == QUEST_RETRIEVE:
        obj = create_quest_obj(player)
        if obj is None:
            end_quest(player, QUEST_TIME // 5)
            return
        world.rooms[rvnum]["items"].append(obj)
        player["quest_obj"] = obj_vnum(obj)
        player["quest_mob"] = 0
        player["quest_mob_name"] = ""
        short = ITEM_DEFS[obj_vnum(obj)]["short_descr"]
        if randint(0, 1) == 0:
            mob_tell(player, questman,
                     "Vile pilferers have stolen " + short + " from the royal treasury!")
            mob_tell(player, questman,
                     "My court wizardess, with her magic mirror, has pinpointed its location.")
        else:
            mob_tell(player, questman,
                     "A powerful wizard has stolen " + short + " for his personal power!")
        mob_tell(player, questman,
                 "This " + _QOBJ_DESC[randint(0, len(_QOBJ_DESC) - 1)]
                 + " was last seen somewhere in the vicinity of " + room_name + "!")

    elif status == QUEST_KILL:
        player["quest_mob"] = mvnum
        player["quest_mob_name"] = mob_name
        player["quest_obj"] = 0
        variant = randint(0, 3)
        if variant == 0:
            mob_tell(player, questman,
                     "An enemy of mine, " + mob_name + ", is making vile threats against the crown.")
            mob_tell(player, questman, "This threat must be eliminated!")
        elif variant == 1:
            # [PRIMESUD] "{n" (mud name) rendered as "The realm";
            # "civillians" typo fixed
            mob_tell(player, questman,
                     "The realm's most heinous criminal, " + mob_name + ", has escaped from the dungeon!")
            mob_tell(player, questman,
                     "Since the escape, " + mob_name + " has murdered "
                     + str(randint(2, 20)) + " civilians!")
            mob_tell(player, questman,
                     "The penalty for this crime is death, and you are to deliver the sentence!")
        elif variant == 2:
            # [PRIMESUD] "severly" typo fixed
            mob_tell(player, questman,
                     "The Mayor of Midgaard has recently been attacked by " + mob_name + ".  This is an act of war!")
            mob_tell(player, questman,
                     mob_name + " must be severely dealt with for this injustice.")
        else:
            mob_tell(player, questman,
                     mob_name + " has been stealing valuables from the citizens of "
                     + area_name + ".")
            mob_tell(player, questman,
                     "Make sure that " + mob_name + " never has the chance to steal again.")
        mob_tell(player, questman,
                 "Seek this " + _QMOB_DESC[randint(0, len(_QMOB_DESC) - 1)]
                 + " out somewhere in the vicinity of " + room_name + "!")

    elif status == QUEST_DELIVER:
        # 1stMud strips ACT_AGGRESSIVE/spec_fun from the live victim;
        # [PRIMESUD] vnum matching can't mutate one instance, so aggressive
        # and spec mobs are excluded at selection instead (_random_quest_mob)
        obj = create_quest_obj(player)
        if obj is None:
            end_quest(player, QUEST_TIME // 5)
            return
        player["inv"].append(obj)
        player["quest_obj"] = obj_vnum(obj)
        player["quest_mob"] = mvnum
        player["quest_mob_name"] = mob_name
        short = ITEM_DEFS[obj_vnum(obj)]["short_descr"]
        # [PRIMESUD] "Time is the essence" grammar fixed
        mob_tell(player, questman,
                 "Please deliver this " + short + " to my friend - " + mob_name
                 + ". Time is of the essence, please hurry.")
        mob_tell(player, questman,
                 "Seek " + mob_name + " out somewhere in the vicinity of {W"
                 + room_name + "{x!")
        act("$n gives $p to $N.", questman, obj, player, TO_NOTVICT)
        act("$n gives you $p.", questman, obj, player, TO_VICT)
        act("You give $p to $N.", questman, obj, player, TO_CHAR)

    elif status == QUEST_FINDROOM:
        player["quest_mob"] = 0
        player["quest_mob_name"] = ""
        player["quest_obj"] = 0
        # [PRIMESUD] "{n" (mud name) rendered as "the realm"
        mob_tell(player, questman,
                 "This quest tests your knowledge of the realm. Your goal is simple, seek out")
        mob_tell(player, questman,
                 "the location '{W" + room_name + "{x' and return to me.")
        mob_tell(player, questman,
                 "You will be told when you find the right place.")

    elif status == QUEST_FINDMOB:
        player["quest_mob"] = mvnum
        player["quest_mob_name"] = mob_name
        player["quest_obj"] = 0
        mob_tell(player, questman,
                 "This quest tests your knowledge of the realm. Your goal is simple, seek out")
        mob_tell(player, questman,
                 "'{W" + mob_name + "{x' in vicinity of {W" + room_name
                 + "{x, and return to me.")
        mob_tell(player, questman,
                 "You will be told when you find the right person.")

    else:
        # cf. 1stMud generate_quest default: bug + abort
        end_quest(player, QUEST_TIME // 5)
        return

    mob_tell(player, questman,
             "The location is in the general area of " + area_name + ".")
    mob_tell(player, questman,
             "You have " + _intstr(ticks_to_mins(player["quest_time"]), "minute")
             + " to complete this quest.")
    # 1stMud: "May %s go with you!" (ch->deity->name) -- [PRIMESUD] no deities
    mob_tell(player, questman, "May the gods go with you!")


def quest_reward(player, questman, rtype):
    """Grant quest completion rewards (cf. 1stMud quest_reward in quest.c)."""
    time_adj = 0
    if rtype == QUEST_RETURN_KILL:
        pointreward = 50
        reward = player["level"] * 4
    elif rtype == QUEST_RETURN_DELIVER:
        pointreward = 40
        reward = player["level"] * 3
    elif rtype == QUEST_RETURN_RETRIEVE:
        pointreward = 30
        reward = player["level"] * 2
    elif rtype == QUEST_RETURN_FINDMOB:
        pointreward = 25
        reward = player["level"] * 2
        time_adj = -4
    elif rtype == QUEST_RETURN_FINDROOM:
        pointreward = 20
        reward = player["level"] * 2
        time_adj = -5
    else:
        pointreward = 20
        reward = player["level"]

    pointreward = randint(pointreward * 4 // 5, pointreward)
    reward = randint(reward * 4 // 5, reward)

    # cf. 1stMud: quest points cap at 32000; overflow converts to gold
    if pointreward + player.get("quest_points", 0) > 32000:
        t = (pointreward + player["quest_points"]) - 32000
        pointreward -= t
        reward += t

    # 1stMud: extract_obj(quest.obj) / extract_char(quest.mob) --
    # [PRIMESUD] remove carried quest token by vnum; mobs stay in world
    ovnum = player.get("quest_obj", 0)
    if ovnum:
        for obj in list(player["inv"]):
            if obj_vnum(obj) == ovnum:
                player["inv"].remove(obj)
                break

    end_quest(player, QUEST_TIME + time_adj)
    player["gold"] += reward
    pointreward = add_qp(player, pointreward)
    # 1stMud: act("$N congratulates $n.", TO_ROOM) -- no audience, skipped
    mob_tell(player, questman,
             "Congratulations on completing your quest! As a reward, I am giving you {W"
             + _intstr(pointreward, "quest point") + "{x, and {Y" + str(reward) + "{x gold.")
    if chance(pointreward // 5):
        chprintln(player, "You gain an extra {YTrivia {RPoint{x!")
        player["trivia"] = player.get("trivia", 0) + 1
    world.save_pending = True  # cf. 1stMud save_char_obj


def quest_complete(player, questman):
    """Handle 'quest complete' at the questmaster (cf. 1stMud quest_complete in quest.c).

    Returns:
        bool: True if handled (reward, timeout, or refusal); False if the
            quest is simply not finished yet.
    """
    if player.get("quest_time", 0) <= 0:
        chprintln(player, "But you didn't complete your quest in time!")
        end_quest(player, QUEST_TIME + 5)
        return True

    status = player.get("quest_status", QUEST_NONE)

    if status == QUEST_NONE:
        chprintln(player, "You have to REQUEST a quest first.")
        return True

    if status in (QUEST_KILL, QUEST_RETRIEVE, QUEST_DELIVER,
                  QUEST_FINDMOB, QUEST_FINDROOM):
        if status == QUEST_RETRIEVE:
            # 1stMud QUEST_RETURN_RETRIEVE: reward only if carrying the token.
            # Status flips to RETURN_RETRIEVE on pickup (quest_obj_check);
            # falls through to the not-finished message otherwise.
            return False
        return False

    if status in (QUEST_RETURN_KILL, QUEST_RETURN_FINDMOB,
                  QUEST_RETURN_FINDROOM, QUEST_RETURN_DELIVER):
        quest_reward(player, questman, status)
        return True

    if status == QUEST_RETURN_RETRIEVE:
        ovnum = player.get("quest_obj", 0)
        obj_found = False
        for obj in player["inv"]:
            if obj_vnum(obj) == ovnum:
                # 1stMud: is_name(ch->name, obj->owner) anti-cheat check --
                # [PRIMESUD] skipped, single player
                obj_found = True
                break
        if obj_found:
            quest_reward(player, questman, status)
        else:
            chprintln(player,
                      "You haven't completed the quest yet, but there is still time!")
        return True

    return False


def quest_room_check(player):
    """Check quest progress on room entry (cf. 1stMud quest_room_check in quest.c).

    [PRIMESUD] Find/kill/deliver targets match by template vnum in any room,
    not only the recorded quest room (kinder single-player semantics); the
    findroom check still requires the exact room.
    """
    if not is_quester(player):
        return
    status = player.get("quest_status", QUEST_NONE)

    if status == QUEST_FINDROOM:
        if player["room"] != player.get("quest_room", 0):
            return
        # [PRIMESUD] "{5+R" (blink) rendered as {R
        chprintln(player, "{RYou have almost completed your QUEST!{x")
        chprintln(player, "{RReturn to " + _giver_name(player) + " before your time runs out!{x")
        player["quest_status"] = QUEST_RETURN_FINDROOM
        player["quest_room"] = 0
        return

    target = player.get("quest_mob", 0)
    if not target:
        return
    victim = None
    for mid in world.rooms[player["room"]]["mobs"]:
        inst = world.chars.get(mid)
        if inst is not None and inst.get("tpl") == target:
            victim = inst
            break
    if victim is None:
        return

    if status == QUEST_FINDMOB:
        do_function(victim, do_say,
                    "Excellent! You have found me. Good job!")
        chprintln(player, "{RYou have almost completed your QUEST!{x")
        chprintln(player, "{RReturn to " + _giver_name(player) + " before your time runs out!{x")
        player["quest_status"] = QUEST_RETURN_FINDMOB
        player["quest_mob"] = 0
    elif status == QUEST_KILL:
        act("$N eye's you warily...", player, None, victim, TO_CHAR)
        act("$N eye's $n warily...", player, None, victim, TO_ROOM)
    elif status == QUEST_DELIVER:
        act("$N smiles at you...", player, None, victim, TO_CHAR)
        act("$N smiles at $n...", player, None, victim, TO_ROOM)


def quest_obj_check(player, obj):
    """Flip retrieve quest to return state on token pickup (cf. 1stMud do_get hook in act_obj.c:169).

    Call after obj lands in player's inventory. [PRIMESUD] vnum match.
    """
    if (player.get("quest_status", QUEST_NONE) == QUEST_RETRIEVE
            and obj_vnum(obj) == player.get("quest_obj", 0)):
        # [PRIMESUD] "{5+R" (blink) rendered as {R
        chprintln(player, "{RYou have almost completed your QUEST!{x")
        chprintln(player, "{RReturn to " + _giver_name(player) + " before your time runs out!{x")
        player["quest_status"] = QUEST_RETURN_RETRIEVE


def quest_kill_check(player, victim):
    """Handle quest target death (cf. 1stMud group_gain quest hook in fight.c:2121).

    Call from group_gain for each PC group member. [PRIMESUD] vnum match.
    """
    if not is_quester(player) or victim.get("tpl") != player.get("quest_mob", 0):
        return
    status = player.get("quest_status", QUEST_NONE)
    if status == QUEST_DELIVER:
        chprintln(player,
                  "{rOOPS! Now you did it! You were supposed to deliver the item, not kill!{x")
        chprintln(player,
                  "You just lost {R50{r questpoints and " + _giver_name(player) + " is very mad!{x")
        end_quest(player, QUEST_TIME + 10)
        player["quest_points"] = max(0, player.get("quest_points", 0) - 50)
    elif status == QUEST_KILL:
        # [PRIMESUD] "{5+R" (blink) rendered as {R
        chprintln(player, "{RYou have almost completed your QUEST!{x")
        chprintln(player, "{RReturn to " + _giver_name(player) + " before your time runs out!{x")
        player["quest_status"] = QUEST_RETURN_KILL


def quest_update():
    """Tick quest timers once per world tick (cf. 1stMud quest_update in update.c pulse_point).

    [PRIMESUD] Timers count world ticks; durations are balanced in real
    minutes like 1stMud's 60s pulse_point, so per-minute messages fire on
    whole-minute boundaries (on_minute) and display via ticks_to_mins.
    """
    player = world.chars.get(1)
    if player is None or player.get("quest_time", 0) <= 0:
        return

    if player.get("quest_status", QUEST_NONE) != QUEST_NONE:
        player["quest_time"] -= 1
        if player["quest_time"] <= 0:
            end_quest(player, QUEST_TIME - 2)
            chprintln(player,
                      "{RYou have run out of time for your quest!"
                      "  You may quest again in " + str(ticks_to_mins(player["quest_time"]))
                      + " minutes.{x")
        elif (player["quest_time"] < mins_to_ticks(6)
                and on_minute(player["quest_time"])):
            # [PRIMESUD] "{p" (1stMud pink) rendered as {M
            chprintln(player,
                      "{MBetter hurry, you're almost out of time for your quest!{x")
    else:
        player["quest_time"] -= 1
        if player["quest_time"] <= 0:
            chprintln(player, "{WYou may now {?quest{W again.{x")


def _giver_name(player):
    """Display name of the quest giver, from template defs. [PRIMESUD] helper."""
    gvnum = player.get("quest_giver", 0)
    tpl = MOB_DEFS._data.get(gvnum)
    return tpl["short_descr"] if tpl else "the questmaster"


def do_quest(player, args):
    """Quest command: info/request/complete/quit and the questmaster shop
    list/buy/sell/identify (cf. 1stMud do_quest in quest.c).

    [PRIMESUD] Bare command opens a contextual picker at a questmaster;
    elsewhere it shows quest info directly. Bare buy/sell/identify commands
    open item pickers. Immortal-only branches (reset, typed request menu)
    not ported.
    """
    if not args:
        questman = _find_spec_mob(player, "spec_questmaster")
        if questman is None:
            do_quest(player, ["info"])
            return "quest info"

        status = player.get("quest_status", QUEST_NONE)
        same_giver = (status != QUEST_NONE
                      and player.get("quest_giver", 0) == questman["tpl"])
        actions = [("Quest status", "info")]
        if status == QUEST_NONE and player.get("quest_time", 0) <= 0:
            actions.append(("Request a quest", "request"))
        if same_giver:
            actions.append(("Complete quest", "complete"))
        actions.extend((
            ("List quest rewards", "list"),
            ("Buy quest reward", "buy"),
            ("Sell quest item", "sell"),
            ("Identify quest reward", "identify"),
        ))
        if same_giver and not _quest_can_complete(player):
            actions.append(("Give up quest", "quit"))

        idx = pick_from("Quest: choose an action",
                        [entry[0] + " [quest " + entry[1] + "]"
                         for entry in actions])
        if idx < 0:
            return
        action = actions[idx][1]
        result = do_quest(player, [action])
        if action in ("buy", "sell", "identify"):
            return result
        return result or "quest " + action

    arg1 = args[0].lower() if args else ""
    arg2 = args[1].lower() if len(args) > 1 else ""

    if _prefix(arg1, "info"):
        status = player.get("quest_status", QUEST_NONE)
        chprintln(player, "")
        if status > QUEST_NONE:
            # [PRIMESUD] HELP QUEST promises the remaining time, but 1stMud's
            # active-objective branches never print it (see docs/FIXES.md).
            chprintln(player, "You have "
                      + _intstr(ticks_to_mins(player.get("quest_time", 0)), "minute")
                      + " remaining to complete this quest.")
        if status == QUEST_NONE:
            chprintln(player, "You aren't currently on a quest.")
            chprintln(player,
                      "There are " + _intstr(ticks_to_mins(player.get("quest_time", 0)), "minute")
                      + " remaining until you can go on another quest.")
            chprintln(player, "You have "
                      + _intstr(player.get("quest_points", 0), "quest point") + ".")
        elif status == QUEST_RETRIEVE and player.get("quest_obj", 0):
            chprintln(player, "You are on a quest to recover the fabled "
                      + ITEM_DEFS[player["quest_obj"]]["short_descr"] + "!")
            chprintln(player,
                      "Rumor has it this " + _QOBJ_DESC[randint(0, len(_QOBJ_DESC) - 1)]
                      + " was last seen in the area known as "
                      + player.get("quest_area_name", "?") + ", near "
                      + player.get("quest_room_name", "?") + ".")
        elif status == QUEST_DELIVER and player.get("quest_mob", 0):
            # 1stMud: "known area %s" grammar slip fixed [PRIMESUD]
            chprintln(player, "You are on a quest to deliver an item to "
                      + player.get("quest_mob_name", "?") + ".")
            chprintln(player,
                      "Rumor has it " + player.get("quest_mob_name", "?")
                      + " was last seen in the area known as "
                      + player.get("quest_area_name", "?") + ", near "
                      + player.get("quest_room_name", "?") + ".")
        elif status == QUEST_KILL and player.get("quest_mob", 0):
            chprintln(player, "You are on a quest to slay "
                      + player.get("quest_mob_name", "?") + "!")
            chprintln(player,
                      "Rumor has it this " + _QMOB_DESC[randint(0, len(_QMOB_DESC) - 1)]
                      + " was last seen in the area known as "
                      + player.get("quest_area_name", "?") + ", near "
                      + player.get("quest_room_name", "?") + ".")
        elif status == QUEST_FINDROOM and player.get("quest_room", 0):
            chprintln(player, "You are on a quest to find "
                      + player.get("quest_room_name", "?") + " in "
                      + player.get("quest_area_name", "?") + "!")
        elif status == QUEST_FINDMOB and player.get("quest_mob", 0):
            chprintln(player, "You are on a quest to find "
                      + player.get("quest_mob_name", "?") + " near "
                      + player.get("quest_room_name", "?") + " in "
                      + player.get("quest_area_name", "?") + "!")
        else:
            # QUEST_RETURN_* states
            # [PRIMESUD] "{5ALMOST" (blink) rendered as {W
            chprintln(player, "{RYour quest is {WALMOST{R complete!{x")
            chprintln(player,
                      "{RYou have " + _intstr(ticks_to_mins(player.get("quest_time", 0)), "minute")
                      + " to get back to " + _giver_name(player)
                      + " before your time runs out!{x")
        return

    # 1stMud imm-only 'quest reset' not ported

    questman = _find_spec_mob(player, "spec_questmaster")
    if questman is None:
        chprintln(player, "You can't do that here.")
        return
    if questman.get("fighting") is not None:
        chprintln(player, "Wait until the fighting stops.")
        return

    if _prefix(arg1, "list"):
        act("$n asks $N for a list of quest items.", player, None, questman, TO_ROOM)
        chprintln(player, "  Current Quest Items available for Purchase:")
        for name, vnum, cost in QUEST_TABLE:
            tpl = ITEM_DEFS.get(vnum)
            chprintln(player, "  " + pad_right(num_str(cost), 4) + "qp ........ "
                      + (tpl["short_descr"] if tpl else "Unavailable"))
        chprintln(player, "  To buy an item, type 'quest buy <item>'.")
        return

    if _prefix(arg1, "buy"):
        picked = False
        if arg2 == "":
            arg2 = _pick_quest_table_item("Buy which quest reward?")
            if arg2 is None:
                return
            picked = True
        i = quest_lookup(arg2)
        if i == -1:
            mob_tell(player, questman,
                     "I don't have that item, " + player["name"] + ".")
            return ("quest buy " + arg2) if picked else None
        name, vnum, cost = QUEST_TABLE[i]
        if player.get("quest_points", 0) < cost:
            mob_tell(player, questman,
                     "You need " + _intstr(cost, "questpoint") + " for that.")
            return ("quest buy " + name) if picked else None
        # 1stMud vnum 0 = nohunger service -- [PRIMESUD] omitted from table
        obj = create_object(vnum)
        if obj is None:
            chprintln(player, "That object could not be found, contact an immortal.")
            return ("quest buy " + name) if picked else None
        player["quest_points"] -= cost
        update_questobj(player, obj)  # cf. 1stMud obj_to_char quest hook
        act("$N gives $p to $n.", player, obj, questman, TO_ROOM)
        act("$N gives you $p.", player, obj, questman, TO_CHAR)
        player["inv"].append(obj)
        world.save_pending = True  # cf. 1stMud save_char_obj
        return ("quest buy " + name) if picked else None

    if _prefix(arg1, "sell"):
        picked = False
        obj = None
        if arg2 == "":
            sellables = []
            labels = []
            for carried in player["inv"]:
                i = qobj_lookup(carried)
                tpl = ITEM_DEFS[obj_vnum(carried)]
                if (i >= 0
                        and can_see_obj(player, carried)
                        and item_extra_flags(carried, tpl).get("quest")):
                    sellables.append(carried)
                    labels.append("[" + num_str(QUEST_TABLE[i][2] // 3)
                                  + "qp] "
                                  + (carried.get("short_descr")
                                     or tpl["short_descr"]))
            if not sellables:
                chprintln(player, "You have no quest items to sell.")
                return
            idx = pick_from("Sell which quest item?", labels)
            if idx < 0:
                return
            obj = sellables[idx]
            picked = True
        else:
            obj = get_obj_list(arg2, player["inv"], ITEM_DEFS, player)
        if obj is None:
            chprintln(player, "Which item is that?")
            return
        if not item_extra_flags(obj, ITEM_DEFS[obj_vnum(obj)]).get("quest"):
            mob_tell(player, questman, "That is not a quest item.")
            return
        i = qobj_lookup(obj)
        if i == -1:
            mob_tell(player, questman,
                     "I only take items I sell, " + player["name"] + ".")
            return
        name = QUEST_TABLE[i][0]
        cost = QUEST_TABLE[i][2]
        player["quest_points"] = player.get("quest_points", 0) + cost // 3
        act("$N takes $p from you for " + _intstr(cost // 3, "questpoint") + ".",
            player, obj, questman, TO_CHAR)
        player["inv"].remove(obj)  # cf. 1stMud extract_obj
        world.save_pending = True  # cf. 1stMud save_char_obj
        return ("quest sell " + name) if picked else None

    if _prefix(arg1, "identify"):
        picked = False
        if arg2 == "":
            arg2 = _pick_quest_table_item("Identify which quest reward?")
            if arg2 is None:
                return
            picked = True
        i = quest_lookup(arg2)
        if i == -1:
            mob_tell(player, questman, "I don't have that item.")
            return ("quest identify " + arg2) if picked else None
        name, vnum, cost = QUEST_TABLE[i]
        obj = create_object(vnum)
        if obj is None:
            chprintln(player, "That object could not be found, contact an immortal.")
            return ("quest identify " + name) if picked else None
        update_questobj(player, obj)
        act("$p costs $T.", player, obj, _intstr(cost, "questpoint"), TO_CHAR)
        from magic import spell_identify  # deferred: magic imports quest
        # cf. 1stMud spell_identify(0, ch->level, ch, obj, TAR_OBJ_INV)
        spell_identify(0, player["level"], player, obj, None)
        # temp object discarded (cf. 1stMud extract_obj)
        return ("quest identify " + name) if picked else None

    if _prefix(arg1, "request"):
        # 1stMud imm-only typed request menu not ported
        act("You ask $N for a quest.", player, None, questman, TO_CHAR)
        act("$n asks $N for a quest.", player, None, questman, TO_ROOM)
        if is_quester(player):
            mob_tell(player, questman, "But you're already on a quest!")
            return
        if player.get("quest_time", 0) > 0:
            mob_tell(player, questman,
                     "You're very brave, " + player["name"]
                     + ", but let someone else have a chance.")
            mob_tell(player, questman, "Come back later.")
            return
        mob_tell(player, questman, "Thank you, brave " + player["name"] + "!")
        generate_quest(player, questman, QUEST_NONE)
        return

    if _prefix(arg1, "complete"):
        if player.get("quest_giver", 0) != questman["tpl"]:
            mob_tell(player, questman,
                     "I never sent you on a quest! Perhaps you're thinking of someone else.")
            return
        if is_quester(player):
            if quest_complete(player, questman):
                return
            if (player.get("quest_status", QUEST_NONE) > QUEST_NONE
                    and player.get("quest_time", 0) > 0):
                mob_tell(player, questman,
                         "You haven't completed the quest yet, but there is still time!")
            return
        mob_tell(player, questman, "You have to REQUEST a quest first.")
        return

    if _prefix(arg1, "quit") or _prefix(arg1, "fail"):
        if player.get("quest_giver", 0) != questman["tpl"]:
            mob_tell(player, questman,
                     "I never sent you on a quest! Perhaps you're thinking of someone else.")
            return
        # [PRIMESUD] Protect a completed quest from an accidental quit:
        # reward it instead. Applies to typed commands and picker choices.
        if _quest_can_complete(player):
            quest_complete(player, questman)
            return "quest complete"
        act("You inform $N you wish to quit $S quest.", player, None, questman, TO_CHAR)
        if is_quester(player):
            # [PRIMESUD] 1stMud sets QUEST_TIME*3/2 = 30 but announces
            # "15 minutes"; resolved toward the lenient announced value
            end_quest(player, QUEST_TIME * 3 // 4)
            mob_tell(player, questman,
                     "Your quest is over, but for your cowardly behavior,"
                     " you may not quest again for "
                     + _intstr(ticks_to_mins(player["quest_time"]), "minute") + ".")
        else:
            chprintln(player, "You aren't on a quest!")
        return

    # unknown subcommand: reprint syntax (cf. 1stMud do_quest tail recursion)
    do_quest(player, [])


def do_tpspend(player, args):
    """Spend trivia points at the trivia shopkeeper (cf. 1stMud do_tpspend in quest.c).

    [PRIMESUD] Skipped options: corpse retrieval (respawn keeps all items;
    corpses are cosmetic), transfer (do_transfer not ported), pretitle
    (titles not ported), PK flag (no PvP).
    """
    arg1 = args[0].lower() if args else ""

    if arg1 == "":
        chprintln(player, "Syntax: tpspend <item>|list")
        return

    if is_name(arg1, "list"):
        chprintln(player, "Trivia Point Options")
        # [PRIMESUD] Pretitle/PK Flag/corpse/transfer lines dropped (see above)
        chprintln(player, "restore..............1tp")
        chprintln(player, "5 trains.............1tp")
        chprintln(player, "40 practices.........1tp")
        chprintln(player, "75 questpoints.......1tp")
        chprintln(player, "1 Trivia Pill........1tp")
        chprintln(player, "See HELP TRIVIA for important info before buying.")
        return

    triviamob = _find_spec_mob(player, "spec_triviamob")
    if triviamob is None:
        chprintln(player, "You can't do that here.")
        return
    if triviamob.get("fighting") is not None:
        chprintln(player, "Wait until the fighting stops.")
        return

    if player.get("trivia", 0) >= 1:
        if is_name(arg1, "practices pracs practice"):
            player["trivia"] -= 1
            player["practice"] += 40
            act("$N gives you 40 practices.", player, None, triviamob, TO_CHAR)
            return
        if is_name(arg1, "trains train"):
            player["trivia"] -= 1
            player["train"] += 5
            act("$N gives you 5 training sessions.", player, None, triviamob, TO_CHAR)
            return
        if is_name(arg1, "questpoints points"):
            player["trivia"] -= 1
            player["quest_points"] = player.get("quest_points", 0) + 75
            act("$N gives you 75 questpoints.", player, None, triviamob, TO_CHAR)
            return
        if is_name(arg1, "pill"):
            obj = create_object(200)  # cf. 1stMud OBJ_VNUM_TRIVIA_PILL
            if obj is None:
                # [PRIMESUD] "I don't any more" slip fixed
                mob_tell(player, triviamob,
                         "I don't have any more trivia pills to give.")
                return
            act("$N gives you $p.", player, obj, triviamob, TO_CHAR)
            player["inv"].append(obj)
            player["trivia"] -= 1
            return
        if is_name(arg1, "restore"):
            # cf. 1stMud do_restore: refill hit/mana/move
            player["trivia"] -= 1
            player["hit"] = player["max_hit"]
            player["mana"] = player["max_mana"]
            player["move"] = player["max_move"]
            act("$N has restored you.", player, None, triviamob, TO_CHAR)
            return
        mob_tell(player, triviamob,
                 "You don't have enough trivia points for that.")
        return

    # cf. 1stMud tail: not enough points -> show the list
    do_tpspend(player, ["list"])
