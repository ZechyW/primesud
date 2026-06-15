from hpprime import eval as ppleval
from urandom import randint

from config import (
    SAVE_VAR,
    TERMINAL_COLS,
    STR_APP_TOHIT,
    STR_APP_TODAM,
    DEX_APP_DEF,
    EXIT_NAMES,
)
from world import (
    ROOMS,
    ITEM_TEMPLATES,
    MOB_TEMPLATES,
    RESETS,
    SKILLS,
    DOOR_RESET,
    R_STARTING_ROOM,
    GSN_HAND_TO_HAND,
    GSN_KICK,
    GSN_CURE_LIGHT,
    GSN_PARRY,
    GSN_RECALL,
)

# ── Player flag bits (cf. 1stMud PLR_* in bits.h) ─────────────────────────────
PLR_AUTOMAP = 1
PLR_DEFAULTS = PLR_AUTOMAP

# ── Save format version ────────────────────────────────────────────────────────
# Increment SAVE_VERSION whenever a core mechanic changes in a way that makes
# old saves load incorrectly: e.g. flag-bit layout changes, AC formula changes,
# stat renaming, or any field whose semantics change rather than just new fields
# being added.  Additive changes (new skills, new item slots, new flags that
# default to 0) do NOT require a bump — missing keys are silently left at their
# create_char() defaults, and unknown keys are silently ignored on load.
#
# Skill numeric IDs (GSN_*) are permanent once assigned: recycling an ID for a
# different skill would cause old saves to corrupt the new skill's learned %.
SAVE_VERSION = 1

# ── Player model ──────────────────────────────────────────────────────────────


def _roll_hp(hp_dice):
    """Roll HP from an hp_dice tuple (cf. 1stMud create_mobile in db.c).

    Args:
        hp_dice (tuple): (num (int), size (int), bonus (int)).

    Returns:
        int: Total HP, minimum 1.
    """
    num, size, bonus = hp_dice
    total = bonus
    for _ in range(num):
        total += randint(1, size)
    return max(1, total)


def create_char():
    """Return a fresh player state dict with default starting values.

    Returns:
        dict: Player state dict.
    """
    return {
        "name": "",
        "is_npc": False,
        "level": 1,
        "xp": 0,
        "xp_next": 1000,
        "str": 13,
        "dex": 13,
        "int": 13,
        "wis": 13,
        "con": 13,
        "hp": 20,
        "hp_max": 20,
        "mp": 100,
        "mp_max": 100,
        "practice": 5,
        "train": 3,
        "hitroll": 0,
        "damroll": 0,
        "AC": 100,  # base unarmored (100 = poor; negative = better)
        "wait": 0,  # skill lag in pulses
        "daze": 0,  # stun in pulses
        "affects": {},
        "mod_stat": {},
        "room": R_STARTING_ROOM,
        "inv": [],
        "equip": {
            "light": None,
            "wield": None,
            "hold": None,
            "body": None,
            "head": None,
            "legs": None,
            "feet": None,
            "hands": None,
            "arms": None,
            "shield": None,
            "about": None,
            "waist": None,
            "neck": None,
            "wrist": None,
        },
        "learned": {
            GSN_HAND_TO_HAND: 40,
            GSN_KICK: 50,
            GSN_CURE_LIGHT: 75,
            GSN_PARRY: 10,
            GSN_RECALL: 50,   # cf. 1stMud nanny.c: learned[gsn_recall] = 50
        },
        "fighting": None,
        "pos": "standing",
        "flags": PLR_DEFAULTS,
        "played": 0,  # cumulative playtime in seconds (cf. 1stMud pcdata->played)
        "_logon_ms": 0,  # session start ticks — ephemeral, not persisted
    }


def _stat_from_level(level):
    """Uniform mob stat derived from level (cf. 1stMud create_mobile perm_stat).

    Args:
        level (int): Mob level.

    Returns:
        int: Stat value in range [11, 25].
    """
    return min(25, 11 + level // 4)


_SIZE_RANK = {"tiny": 0, "small": 1, "medium": 2, "large": 3, "huge": 4, "giant": 5}


def create_mobile(tpl_vnum):
    """Instantiate a mob from its template (cf. 1stMud create_mobile in db.c).

    Returns a placement-agnostic instance dict; caller must set "room" and
    "home_area" before registering it in mob_instances.

    Args:
        tpl_vnum (int): Mob template VNUM.

    Returns:
        dict: Mob instance dict.
    """
    tpl = MOB_TEMPLATES[tpl_vnum]
    hp  = _roll_hp(tpl["hp_dice"])
    base = _stat_from_level(tpl["level"])
    act  = tpl.get("act_flags", {})
    off  = tpl.get("off_flags", {})

    # Per-stat values start uniform then receive class/off/size bonuses
    # (cf. 1stMud create_mobile perm_stat loop + ACT_WARRIOR/THIEF/CLERIC/MAGE blocks)
    s_str = s_dex = s_int = s_wis = s_con = base
    if act.get("warrior"):
        s_str += 3; s_int -= 1; s_con += 2
    if act.get("thief"):
        s_dex += 3; s_int += 1; s_wis -= 1
    if act.get("cleric"):
        s_wis += 3; s_dex -= 1; s_str += 1
    if act.get("mage"):
        s_int += 3; s_str -= 1; s_dex += 1
    if off.get("fast"):
        s_dex += 2
    size_delta = _SIZE_RANK.get(tpl.get("size", "medium"), 2) - 2   # 2 = SIZE_MEDIUM
    s_str += size_delta
    s_con += size_delta // 2

    return {
        "tpl":       tpl_vnum,
        "is_npc":    True,
        "hp":        hp,
        "hp_max":    hp,
        "state":     "idle",
        "affects":   {},
        "wait":      0,
        "daze":      0,
        "fighting":  None,
        "learned":   dict(tpl.get("skills", {})),
        "off_flags": dict(off),
        "inv":       [],
        "equip":     {},
        "level":     tpl["level"],
        "str":       s_str,
        "dex":       s_dex,
        "int":       s_int,
        "wis":       s_wis,
        "con":       s_con,
        "hitroll":   tpl["hitroll"],
        "damroll":   tpl["damage"][2],   # bonus = damroll (cf. 1stMud damage[DICE_BONUS])
        "AC":        tpl["AC"] * 10,     # ×10 storage (cf. 1stMud load_mobiles read_number * 10)
    }


def _tpl_live_count(mob_instances, tpl_vnum):
    """Count live instances of a template across all rooms (cf. pMobIndex->count in db.c)."""
    return sum(1 for inst in mob_instances.values() if inst["tpl"] == tpl_vnum)


def _tpl_room_count(mob_instances, room_vnum, tpl_vnum):
    """Count live instances of a template in a specific room (cf. per-room scan in reset_room, db.c)."""
    return sum(1 for inst in mob_instances.values()
               if inst["tpl"] == tpl_vnum and inst["room"] == room_vnum)


def reset_mobs(mob_instances, room_state, resets):
    """Spawn mobs for each M entry up to global and room limits (cf. 1stMud reset_room 'M' case, db.c).

    E and G entries following a successful M equip or give items to the spawned mob,
    matching 1stMud's LastMob/last context chain.  O and P entries clear the context.

    Mutates mob_instances and room_state in place.  Safe to call on a
    partially-populated mob_instances (area tick) as well as an empty one
    (full reset via reset_area).

    Args:
        mob_instances (dict): Mob instance mapping mob ID → instance dict.
        room_state (dict): Room state mapping room vnum → room state dict.
        resets (tuple): Area RESETS sequence.
    """
    mob_id = max(mob_instances, default=0) + 1
    last_mob_id  = None   # cf. 1stMud LastMob in reset_room
    last_spawned = False  # cf. 1stMud `last` flag in reset_room
    for entry in resets:
        cmd = entry[0]
        if cmd == "M":
            tpl_vnum, gl, room_vnum, rl = entry[1], entry[2], entry[3], entry[4]
            if _tpl_live_count(mob_instances, tpl_vnum) >= gl:
                last_spawned = False
                continue
            if _tpl_room_count(mob_instances, room_vnum, tpl_vnum) >= rl:
                last_spawned = False
                continue
            inst = create_mobile(tpl_vnum)
            inst["room"] = room_vnum
            inst["home_area"] = ROOMS[room_vnum].get("area")
            mob_instances[mob_id] = inst
            room_state[room_vnum]["mobs"].append(mob_id)
            last_mob_id  = mob_id
            last_spawned = True
            mob_id += 1
        elif cmd == "E" and last_spawned:
            mob_instances[last_mob_id]["equip"][entry[2]] = entry[1]
        elif cmd == "G" and last_spawned:
            mob_instances[last_mob_id]["inv"].append(entry[1])
        elif cmd in ("O", "P"):
            last_spawned = False  # breaks mob context (cf. 1stMud last=false on O)


def reset_area():
    """Create fresh room state and mob instances (cf. 1stMud reset_area).

    Returns:
        tuple: (room_state (dict), mob_instances (dict)).
    """
    room_state = {vnum: {"items": [], "mobs": []} for vnum in ROOMS}
    mob_instances = {}
    reset_mobs(mob_instances, room_state, RESETS)
    for entry in RESETS:
        if entry[0] == "O":
            room_state[entry[2]]["items"].append(create_object(entry[1]))
    # Restore all door states to their reset-to values (cf. 1stMud reset_room door loop, db.c:1411)
    for vnum, doors in DOOR_RESET.items():
        exits = ROOMS[vnum]["exits"]
        for d, state in doors.items():
            exits[d]["closed"] = state["closed"]
            exits[d]["locked"] = state["locked"]
    return room_state, mob_instances


def mobile_update(tr, player, mob_instances, room_state):
    """Wander mobs and despawn any that strayed out of their home area (cf. 1stMud mobile_update, char_update in update.c)."""
    for mob_id, inst in list(mob_instances.items()):
        if ROOMS[inst["room"]].get("area") != inst["home_area"] and randint(1, 100) <= 5:
            # 5% chance to despawn when outside home area (cf. char_update, update.c:541)
            if player["room"] == inst["room"]:
                tpl = MOB_TEMPLATES[inst["tpl"]]
                _sd = tpl["short_descr"]
                tr.print("{} wanders on home.".format(_sd[0].upper() + _sd[1:]))
            room_state[inst["room"]]["mobs"].remove(mob_id)
            del mob_instances[mob_id]
            continue
        if inst["fighting"] is not None:
            continue
        act = MOB_TEMPLATES[inst["tpl"]].get("act_flags", {})
        if act.get("sentinel"):
            continue
        if randint(0, 7) != 0:  # 1/8 chance — matches number_bits(3)==0
            continue
        exits = ROOMS[inst["room"]].get("exits", {})
        if not exits:
            continue
        dirs = list(exits.keys())
        direction = dirs[randint(0, len(dirs) - 1)]
        exit_val = exits[direction]
        if isinstance(exit_val, dict) and exit_val.get("closed"):  # cf. EX_CLOSED check, update.c:499
            continue
        dest_vnum = exit_val["to"] if isinstance(exit_val, dict) else exit_val
        if dest_vnum not in ROOMS:
            continue
        dest_flags = ROOMS[dest_vnum].get("flags", {})
        if dest_flags.get("no_mob"):  # cf. ROOM_NO_MOB check, update.c:500
            continue
        if act.get("stay_area") and ROOMS[dest_vnum].get("area") != ROOMS[inst["room"]].get("area"):
            continue  # cf. ACT_STAY_AREA check, update.c:501
        if act.get("outdoors") and dest_flags.get("indoors"):
            continue
        if act.get("indoors") and not dest_flags.get("indoors"):
            continue
        old_room = inst["room"]
        tpl = MOB_TEMPLATES[inst["tpl"]]
        _sd = tpl["short_descr"]
        name = _sd[0].upper() + _sd[1:]
        if player["room"] == old_room:
            tr.print("{} leaves {}.".format(name, EXIT_NAMES.get(direction, direction)))
        room_state[old_room]["mobs"].remove(mob_id)
        inst["room"] = dest_vnum
        room_state[dest_vnum]["mobs"].append(mob_id)
        if player["room"] == dest_vnum:
            tr.print("{} has arrived.".format(name))


# ── Stat application helpers ──────────────────────────────────────────────────

def _clamp_stat(v):
    """Clamp a stat value to the valid range [0, 25]."""
    return min(25, max(0, v))


def get_curr_stat(char, stat):
    """Effective stat value: base + affect modifiers (cf. 1stMud get_curr_stat in handler.c).

    Args:
        char (dict): Character state dict (player or mob instance).
        stat (str): Stat name — one of "str", "dex", "int", "wis", "con".

    Returns:
        int: Clamped stat value in [0, 25].
    """
    return _clamp_stat(char.get(stat, 10) + char.get("mod_stat", {}).get(stat, 0))


def affect_modify(char, loc, modifier, add):
    """Apply or remove a stat modifier for one affect location (cf. 1stMud affect_modify in handler.c).

    Mutates hp_max, mp_max, AC, hitroll, damroll directly; accumulates
    str/dex/int/wis/con into char["mod_stat"] (cf. 1stMud mod_stat[] in handler.c).

    Args:
        char (dict): Character state dict (player or mob instance).
        loc (str): Affect location — one of "str", "dex", "int", "wis", "con",
            "hp", "mp", "AC", "hitroll", "damroll".
        modifier (int): Raw modifier value (positive = bonus).
        add (bool): True to apply, False to remove.
    """
    if not add:
        modifier = -modifier
    if loc == "hp":
        char["hp_max"] = max(1, char["hp_max"] + modifier)
    elif loc == "mp":
        char["mp_max"] = max(1, char["mp_max"] + modifier)
    elif loc == "AC":
        char["AC"] += modifier
    elif loc == "hitroll":
        char["hitroll"] += modifier
    elif loc == "damroll":
        char["damroll"] += modifier
    elif loc in ("str", "dex", "int", "wis", "con"):
        ms = char.setdefault("mod_stat", {})
        ms[loc] = ms.get(loc, 0) + modifier


def affect_to_char(char, sn, loc, modifier, duration):
    """Apply a timed affect to a character (cf. 1stMud affect_to_char in handler.c).

    Stores the affect in char["affects"] keyed by sn (skill/spell number) and
    immediately applies the modifier via affect_modify.  Overwrites any existing
    affect with the same sn.

    Args:
        char (dict): Character state dict (player or mob instance).
        sn (int): Skill/spell number identifying this affect.
        loc (str): Affect location (see affect_modify).
        modifier (int): Stat modifier value.
        duration (int): Duration in ticks (≥ 1).
    """
    existing = char["affects"].get(sn)
    if existing is not None:
        affect_modify(char, existing["loc"], existing["modifier"], False)
    char["affects"][sn] = {"loc": loc, "modifier": modifier, "duration": duration}
    affect_modify(char, loc, modifier, True)


def affect_remove(char, sn):
    """Remove an active affect from a character (cf. 1stMud affect_remove in handler.c).

    Unapplies the modifier via affect_modify then deletes the entry from
    char["affects"].  No-op if sn is not in the affects dict.

    Args:
        char (dict): Character state dict (player or mob instance).
        sn (int): Skill/spell number to remove.
    """
    aff = char["affects"].pop(sn, None)
    if aff is not None:
        affect_modify(char, aff["loc"], aff["modifier"], False)


def get_hitroll(char):
    """Effective hitroll: base + STR bonus + equipped weapon bonus (cf. 1stMud GetHitroll macro in macro.h).

    Args:
        char (dict): Character state dict (player or mob instance).

    Returns:
        int: Total hitroll modifier.
    """
    return char.get("hitroll", 0) + STR_APP_TOHIT[get_curr_stat(char, "str")]


def get_damroll(char):
    """Effective damroll: base + STR bonus + equipped weapon bonus (cf. 1stMud GetDamroll macro in macro.h).

    Args:
        char (dict): Character state dict (player or mob instance).

    Returns:
        int: Total damroll modifier.
    """
    return char.get("damroll", 0) + STR_APP_TODAM[get_curr_stat(char, "str")]


def get_AC(char):
    """Effective AC: base + DEX bonus + equipped armour bonus.

    Args:
        char (dict): Character state dict (player or mob instance).

    Returns:
        int: Total AC (lower is better; negative is excellent).
    """
    return char.get("AC", 100) + DEX_APP_DEF[get_curr_stat(char, "dex")]


def is_name(fragment, namelist):
    """True if every word in fragment prefix-matches a word in namelist (cf. 1stMud is_name).

    Args:
        fragment (str): Space-separated words typed by the player.
        namelist (str): Space-separated keywords from the mob/item template.

    Returns:
        bool: True if all fragment words prefix-match at least one keyword.
    """
    if not fragment or not namelist:
        return False
    keywords = namelist.lower().split()
    for part in fragment.lower().split():
        if not any(kw.startswith(part) for kw in keywords):
            return False
    return True


def obj_vnum(item):
    """Return the VNUM of an item instance dict or a plain VNUM int."""
    return item["vnum"] if isinstance(item, dict) else item


def create_object(vnum):
    """Create an item instance from a template (cf. 1stMud create_object in db.c).

    Args:
        vnum (int): Item template VNUM.

    Returns:
        dict: Item instance dict with mutable fields copied from template.
    """
    return {"vnum": vnum, "cost": ITEM_TEMPLATES[vnum].get("value", 0)}


def item_extra_flags(obj, tpl):
    """Return extra_flags for obj, preferring instance override over template."""
    if isinstance(obj, dict) and "extra_flags" in obj:
        return obj["extra_flags"]
    return tpl.get("extra_flags", {})


def item_wear_flags(obj, tpl):
    """Return wear_flags for obj, preferring instance override over template."""
    if isinstance(obj, dict) and "wear_flags" in obj:
        return obj["wear_flags"]
    return tpl.get("wear_flags", {})


def get_obj_list(fragment, item_list, templates):
    """Find the Nth item in item_list whose keywords match fragment (cf. 1stMud get_obj_list in handler.c).

    Supports "2.sword" prefix syntax (cf. 1stMud number_argument in interp.c):
    the integer before '.' is the ordinal; without a prefix returns the first match.
    Items may be plain VNUM ints (room/mob) or instance dicts (player inv/equip).

    Args:
        fragment (str): Player-typed name fragment, optionally prefixed "N.".
        item_list (list): Ordered list of items (int or instance dict) to search.
        templates (dict): Item template dict mapping vnum → template.

    Returns:
        Item from item_list (int or dict), or None if not found.
    """
    if '.' in fragment:
        prefix, rest = fragment.split('.', 1)
        try:
            nth = int(prefix)
            fragment = rest
        except ValueError:
            nth = 1
    else:
        nth = 1
    count = 0
    for item in item_list:
        vnum = obj_vnum(item)
        if is_name(fragment, templates[vnum].get("keywords", "")):
            count += 1
            if count == nth:
                return item
    return None


def get_char_room(fragment, inst_ids, mob_instances):
    """Find the first mob in inst_ids whose keywords match fragment (cf. 1stMud get_char_room in handler.c).

    Args:
        fragment (str): Player-typed name fragment.
        inst_ids (list): Ordered list of mob instance IDs to search.
        mob_instances (dict): Mob instance mapping mob ID → mob instance dict.

    Returns:
        int or None: First matching mob instance ID, or None if not found.
    """
    for mob_id in inst_ids:
        if is_name(fragment, MOB_TEMPLATES[mob_instances[mob_id]["tpl"]].get("keywords", "")):
            return mob_id
    return None


# ── Tick regen ───────────────────────────────────────────────────────────────

def tick_update(tr, player, room):
    """Regenerate HP and MP once per world tick (cf. 1stMud hit_gain/mana_gain in update.c).

    Position is always treated as resting — no position system [PRIMESUD].
    Hunger/thirst conditions omitted [PRIMESUD].

    Args:
        tr: Terminal for affect wear-off messages.
        player (dict): Player state dict.
        room (dict): Current room (supplies heal_rate/mana_rate).
    """
    con  = get_curr_stat(player, "con")
    int_ = get_curr_stat(player, "int")
    wis  = get_curr_stat(player, "wis")
    level = player.get("level", 1)

    # HP (cf. 1stMud hit_gain in update.c)
    hp_gain = max(3, con - 3 + level // 2) + (player["hp_max"] - 10)
    # TODO: fast_healing bonus — if roll < skill%, gain += roll * gain / 100
    # Position: always resting [PRIMESUD] — sleeping=/1, resting=/2, standing=/4, fighting=/6
    hp_gain //= 2
    # Hunger/thirst omitted [PRIMESUD]
    hp_gain = hp_gain * room.get("heal_rate", 100) // 100
    # TODO: poison /4, plague /8, haste/slow /2
    hp_gain = max(1, hp_gain)

    # MP (cf. 1stMud mana_gain in update.c) — base (WIS+INT+level)/2, resting /2
    mp_gain = (int_ + wis + level) // 4
    mp_gain = mp_gain * room.get("mana_rate", 100) // 100
    # TODO: poison /4, plague /8, haste/slow /2
    mp_gain = max(1, mp_gain)

    player["hp"] = min(player["hp_max"], player["hp"] + hp_gain)
    player["mp"] = min(player["mp_max"], player["mp"] + mp_gain)

    for sn in list(player["affects"]):
        aff = player["affects"].get(sn)
        if aff is None:
            continue
        if aff["duration"] > 0:
            aff["duration"] -= 1
        elif aff["duration"] == 0:
            msg = SKILLS.get(sn, {}).get("msg_off", "")
            if msg and not msg.startswith("!"):
                tr.print(msg)
            affect_remove(player, sn)


# ── Display ───────────────────────────────────────────────────────────────────

def show_prompt(tr, player, buf):
    """Update the terminal status bar with the current HP/MP/XP prompt.

    Args:
        tr: Terminal instance.
        player (dict): Player state dict.
        buf (str): Current input buffer shown on the right of the prompt.
    """
    prefix = "HP:{}/{} MP:{}/{} {}tnl>".format(
        player["hp"], player["hp_max"],
        player["mp"], player["mp_max"],
        player["xp_next"] - player["xp"],
    )
    avail = max(1, TERMINAL_COLS - 6 - len(prefix))
    tr.set_status(prefix + buf[-avail:])


# ── Persistence ───────────────────────────────────────────────────────────────
# Save data is stored in a PPL home variable (SAVE_VAR) via HVars so it
# survives app reinstalls.  Serialisation constraints:
#   - Lines are joined with '~'; no saved field value may contain '~'.
#   - No field value may contain '"' (would break the PPL string literal).
#   - HVars returns the string "Error: Invalid input" when the variable does
#     not exist yet (i.e. no save found); load_char treats this as no-save.

def save_char(player, room_state, mob_instances, area_states=None, macros=None):
    """Serialise player and world state to a PPL HVars variable (cf. 1stMud save_char_obj in save.c).

    Args:
        player (dict): Player state dict.
        room_state (dict): Room state mapping room ID → room state dict.
        mob_instances (dict): Mob instance mapping mob ID → mob instance dict.
        area_states (list or None): List of area state dicts (tag, age, resets); skipped if None.
        macros (dict or None): Macro key→command mapping; skipped if None.

    Returns:
        bool: True on success, False if the PPL write raised an exception.
    """
    lines = ["v={}".format(SAVE_VERSION)]
    for key in ("name", "level", "xp", "xp_next",
                "str", "dex", "int", "wis", "con",
                "hp", "hp_max", "mp", "mp_max",
                "hitroll", "damroll", "AC", "room",
                "practice", "train", "flags", "played"):
        lines.append("p.{}={}".format(key, player[key]))
    lines.append("p.inv={}".format("|".join(
        "{}:{}".format(o["vnum"], o["cost"]) for o in player["inv"])))
    for slot, obj in player["equip"].items():
        lines.append("p.eq.{}={}".format(
            slot, "{}:{}".format(obj["vnum"], obj["cost"]) if obj is not None else ""))
    learned_parts = []
    for sk, pct in player["learned"].items():
        learned_parts.append("{}:{}".format(sk, pct))
    lines.append("p.learned={}".format("|".join(learned_parts)))
    if macros is not None:
        for k, v in macros.items():
            lines.append("p.macro.{}={}".format(k, v))
    if area_states is not None:
        for _as in area_states:
            lines.append("a.{}.age={}".format(_as["tag"], _as["age"]))
    # Build reset-room map for single-instance mobs (gl=1): if the only live
    # instance is already in its reset room, omit it — reset_area() will
    # restore it there on load without any save entry needed.
    _single_reset_room = {}
    for entry in RESETS:
        if entry[0] == "M" and entry[2] == 1:
            _single_reset_room[entry[1]] = entry[3]

    tpl_rooms = {}
    for inst in mob_instances.values():
        tpl = inst["tpl"]
        if tpl not in tpl_rooms:
            tpl_rooms[tpl] = []
        tpl_rooms[tpl].append(inst["room"])
    for tpl_vnum, rooms in tpl_rooms.items():
        if (len(rooms) == 1
                and _single_reset_room.get(tpl_vnum) == rooms[0]):
            continue
        lines.append("m.{}={}".format(tpl_vnum, "|".join(str(r) for r in rooms)))
    for rvnum, rs in room_state.items():
        lines.append("r.{}.items={}".format(rvnum, "|".join(
            "{}:{}".format(o["vnum"], o["cost"]) for o in rs["items"])))
    try:
        payload = "~".join(lines)
        ppleval('HVars("' + SAVE_VAR + '"):="' + payload + '"')
        return True
    except Exception:
        return False


def _parse_item(s):
    """Parse a saved item token ('vnum:cost') into an instance dict."""
    v, c = s.split(":", 1)
    return {"vnum": int(v), "cost": int(c)}


def load_char(player, room_state, mob_instances, area_states=None, macros=None):
    """Deserialise player and world state from the PPL HVars variable (cf. 1stMud load_char_obj in save.c).

    Mutates player, room_state, mob_instances, and optionally area_states and
    macros in-place.

    Args:
        player (dict): Player state dict to populate.
        room_state (dict): Room state mapping room ID → room state dict.
        mob_instances (dict): Mob instance mapping mob ID → mob instance dict.
        area_states (list or None): List of area state dicts (tag, age, resets); skipped if None.
        macros (dict or None): Macro dict to populate; skipped if None.

    Returns:
        bool: True if a save was found and loaded, False if no save exists or on error.
    """
    try:
        data = ppleval('HVars("' + SAVE_VAR + '")')
        if not data or not isinstance(data, str) or data.startswith("Error:"):
            return False
    except Exception:
        return False

    # Reject saves from a different format version.  Additive changes (new
    # fields, new skills) don't require a bump; only semantic/structural changes
    # to existing core fields do.  See SAVE_VERSION comment above for the rule.
    # Returns None (not False) so the caller can distinguish mismatch from
    # "no save found" and prompt the user rather than silently starting fresh.
    _ver_prefix = "v="
    _first = data.split("~", 1)[0]
    if not _first.startswith(_ver_prefix) or int(_first[len(_ver_prefix):]) != SAVE_VERSION:
        try:
            ppleval('HVars("' + SAVE_VAR + '_bak"):="' + data + '"')
            _backup_ok = True
        except Exception:
            _backup_ok = False
        return (None, _backup_ok)

    int_keys = {"level", "xp", "xp_next",
                "str", "dex", "int", "wis", "con",
                "hp", "hp_max", "mp", "mp_max",
                "hitroll", "damroll", "AC", "room",
                "practice", "train", "flags", "played"}

    if macros is not None:
        macros.clear()

    _area_by_tag = {s["tag"]: s for s in area_states} if area_states is not None else {}
    mob_saves = {}  # tpl_vnum → [room, room, ...]

    for line in data.split("~"):
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        if key.startswith("p.eq."):
            slot = key[5:]
            player["equip"][slot] = _parse_item(val) if val else None
        elif key == "p.inv":
            player["inv"] = [_parse_item(v) for v in val.split("|") if v]
        elif key == "p.learned":
            for entry in val.split("|"):
                if ":" in entry:
                    sk_str, pct_str = entry.split(":", 1)
                    try:
                        player["learned"][int(sk_str)] = int(pct_str)
                    except ValueError:
                        pass
        elif key.startswith("p.macro.") and macros is not None:
            macros[key[8:]] = val
        elif key.startswith("p."):
            pkey = key[2:]
            player[pkey] = int(val) if pkey in int_keys else val
        elif key.startswith("r.") and key.endswith(".items"):
            rvnum = int(key.split(".")[1])
            if rvnum in room_state:
                room_state[rvnum]["items"] = [_parse_item(v) for v in val.split("|") if v]
        elif key.startswith("a.") and key.endswith(".age"):
            tag = key[2:-4]
            if tag in _area_by_tag:
                _area_by_tag[tag]["age"] = int(val)
        elif key.startswith("m."):
            mob_saves[int(key[2:])] = [int(r) for r in val.split("|") if r]

    # Apply saved mob rooms: delete killed instances, patch wandered rooms.
    # Same vnum appearing multiple times means multiple instances in one room — correct.
    for tpl_vnum, saved_rooms in mob_saves.items():
        inst_ids = sorted(i for i, inst in mob_instances.items() if inst["tpl"] == tpl_vnum)
        for mid in inst_ids[len(saved_rooms):]:   # excess = killed since last save
            del mob_instances[mid]
        for mid, room_vnum in zip(inst_ids, saved_rooms):
            if room_vnum in ROOMS:
                mob_instances[mid]["room"] = room_vnum

    if player["room"] not in room_state:
        player["room"] = R_STARTING_ROOM

    for rs in room_state.values():
        rs["mobs"] = []
    for mob_id, inst in mob_instances.items():
        room_state[inst["room"]]["mobs"].append(mob_id)

    return True
