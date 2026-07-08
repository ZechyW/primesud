"""Item creation, lookup, flags, spell payloads, and save tokens."""

import world
from world import ITEM_DEFS, MOB_DEFS
from handler import is_name, number_argument, can_see_obj

# Item types that can hold contents, for loot/look-in purposes [PRIMESUD]:
# matches 1stMud's do_get/get_obj_list acceptance of ITEM_CONTAINER plus
# ITEM_CORPSE_NPC/ITEM_CORPSE_PC (act_obj.c do_get container switch).
# Open/close/lock/unlock/pick require strict "container" (1stMud
# act_move.c checks item_type != ITEM_CONTAINER) -- use item_type() there.
CONTAINER_TYPES = ("npc_corpse", "pc_corpse", "container")


def obj_vnum(item):
    """Return the VNUM of an item instance dict or a plain VNUM int."""
    return item["vnum"] if isinstance(item, dict) else item


def item_type(obj, tpl):
    """Return the effective item type, checking instance override first. [PRIMESUD]

    An explicit instance type wins over template (e.g., death_cry downgrades
    non-edible body parts to 'trash').
    """
    if isinstance(obj, dict) and "type" in obj:
        return obj["type"]
    return tpl.get("type")


def create_object(vnum):
    """Create an item instance from a template (cf. 1stMud create_object in db.c).

    Args:
        vnum (int): Item template VNUM.

    Returns:
        dict: Item instance dict with mutable fields copied from template.
    """
    tpl = ITEM_DEFS[vnum]
    obj = {"vnum": vnum, "cost": tpl.get("value", 0)}
    if "max_charges" in tpl:
        obj["max_charges"] = tpl["max_charges"]
        obj["charges"] = tpl.get("charges", tpl["max_charges"])
    elif "charges" in tpl:
        obj["charges"] = tpl["charges"]
    # [PRIMESUD] liquid fields stay on the template until first mutated
    # (inventory._set_liquid), keeping instances and save payloads small
    return obj


def promote_obj(player, obj):
    """Swap a plain-vnum item for a mutable instance dict in place. [PRIMESUD]

    Area resets and pickups keep items as plain ints; state mutation and
    act() $p rendering need instance dicts. Replaces the first matching
    vnum in inventory, room, or equipment (identical plain vnums are
    indistinguishable, so first-match is safe).
    """
    if isinstance(obj, dict):
        return obj
    inst = create_object(obj)
    for lst in (player["inv"], world.rooms[player["room"]]["items"]):
        if obj in lst:
            lst[lst.index(obj)] = inst
            return inst
    for slot in player["equip"]:
        if player["equip"][slot] == obj:
            player["equip"][slot] = inst
            return inst
    return inst


def item_extra_flags(obj, tpl):
    """Return extra_flags for obj, preferring instance override over template. [PRIMESUD]"""
    if isinstance(obj, dict) and "extra_flags" in obj:
        return obj["extra_flags"]
    return tpl.get("extra_flags", {})


def item_wear_flags(obj, tpl):
    """Return wear_flags for obj, preferring instance override over template. [PRIMESUD]"""
    if isinstance(obj, dict) and "wear_flags" in obj:
        return obj["wear_flags"]
    return tpl.get("wear_flags", {})


def item_weapon_flags(obj, tpl):
    """Return weapon_flags for obj, preferring instance override over template. [PRIMESUD]"""
    if isinstance(obj, dict) and "weapon_flags" in obj:
        return obj["weapon_flags"]
    return tpl.get("weapon_flags", {})


def set_item_weapon_flag(obj, tpl, flag, enabled):
    """Set or clear one mutable weapon flag on item instance. [PRIMESUD]"""
    if "weapon_flags" not in obj:
        obj["weapon_flags"] = dict(tpl.get("weapon_flags", {}))
    flags = obj["weapon_flags"]
    if enabled:
        flags[flag] = True
    elif flag in flags:
        del flags[flag]
    return flags


def item_container_flags(obj, tpl):
    """Return container_flags for obj, preferring instance override over template. [PRIMESUD]

    Backs the runtime closed/locked/closeable/pickproof state (cf. 1stMud
    ObjData.value[1] CONT_* bits in merc.h) -- mirrors item_extra_flags'
    instance-override-wins pattern so container state can be flipped by
    do_open/do_close/do_lock/do_unlock without mutating the shared template.
    """
    if isinstance(obj, dict) and "container_flags" in obj:
        return obj["container_flags"]
    return tpl.get("container_flags", {})


def ensure_item_container_flags(obj, tpl):
    """Return mutable full container_flags set for item instance. [PRIMESUD]"""
    if "container_flags" not in obj:
        obj["container_flags"] = dict(tpl.get("container_flags", {}))
    return obj["container_flags"]


def set_item_container_flag(obj, tpl, flag, enabled):
    """Set or clear one mutable container flag on item instance. [PRIMESUD]"""
    flags = ensure_item_container_flags(obj, tpl)
    if enabled:
        flags[flag] = True
    elif flag in flags:
        del flags[flag]
    return flags


def item_affect_list(obj):
    """Return runtime object affects list, defaulting to empty list. [PRIMESUD]"""
    if isinstance(obj, dict):
        return obj.get("affect_list", [])
    return []


def ensure_item_extra_flags(obj, tpl):
    """Return mutable full extra_flags set for item instance. [PRIMESUD]"""
    if "extra_flags" not in obj:
        obj["extra_flags"] = dict(tpl.get("extra_flags", {}))
    return obj["extra_flags"]


def set_item_extra_flag(obj, tpl, flag, enabled):
    """Set or clear one mutable extra flag on item instance. [PRIMESUD]"""
    flags = ensure_item_extra_flags(obj, tpl)
    if enabled:
        flags[flag] = True
    elif flag in flags:
        del flags[flag]
    return flags


def item_affect_find(obj, sn):
    """Return first object affect of type sn, or None. [PRIMESUD]"""
    for af in item_affect_list(obj):
        if af.get("type") == sn:
            return af
    return None


def item_affect_remove(obj, af, tpl):
    """Remove one object affect and clear its direct flag bit if present. [PRIMESUD]

    where="to_weapon" affects clear a weapon_flags bit, where="to_object" an
    extra_flags bit; other wheres (to_affects etc.) touch no item flags
    (cf. 1stMud affect_remove_obj switch in handler.c:1233-1245, default case).
    """
    affects = obj.get("affect_list", [])
    if af in affects:
        affects.remove(af)
    if not affects and "affect_list" in obj:
        del obj["affect_list"]
    bit = af.get("bitvector", "")
    if bit:
        if af.get("where") == "to_weapon":
            set_item_weapon_flag(obj, tpl, bit, False)
        elif af.get("where") == "to_object":
            set_item_extra_flag(obj, tpl, bit, False)


def item_affect_to_obj(obj, af, tpl):
    """Apply one timed object affect to runtime item state. [PRIMESUD]

    where="to_weapon" affects set a weapon_flags bit, where="to_object" an
    extra_flags bit; other wheres (to_affects etc.) touch no item flags
    (cf. 1stMud affect_to_obj switch in handler.c:1176-1188, default case).
    """
    cur = dict(af)
    obj.setdefault("affect_list", []).append(cur)
    bit = cur.get("bitvector", "")
    if bit:
        if cur.get("where") == "to_weapon":
            set_item_weapon_flag(obj, tpl, bit, True)
        elif cur.get("where") == "to_object":
            set_item_extra_flag(obj, tpl, bit, True)
    return cur


def item_spell_level(obj, tpl):
    """Return spell level for magical item, preferring instance override. [PRIMESUD]"""
    if isinstance(obj, dict) and "spell_level" in obj:
        return obj["spell_level"]
    return tpl.get("spell_level")


def item_spells(obj, tpl):
    """Return list of spell names for potion/scroll/pill payloads. [PRIMESUD]"""
    if isinstance(obj, dict) and "spells" in obj:
        return obj["spells"]
    return tpl.get("spells", [])


def item_current_charges(obj, tpl):
    """Return current charges for wand/staff, preferring instance state. [PRIMESUD]"""
    if isinstance(obj, dict) and "charges" in obj:
        return obj["charges"]
    return tpl.get("charges", tpl.get("max_charges"))


def item_max_charges(obj, tpl):
    """Return maximum charges for wand/staff, preferring instance state. [PRIMESUD]"""
    if isinstance(obj, dict) and "max_charges" in obj:
        return obj["max_charges"]
    return tpl.get("max_charges", tpl.get("charges"))


def item_spell_name(obj, tpl):
    """Return single spell name for wand/staff payloads. [PRIMESUD]"""
    if isinstance(obj, dict) and "spell" in obj:
        return obj["spell"]
    return tpl.get("spell")


def _str_escape(s):
    """Escape string for embedding in item token field value. [PRIMESUD]

    Escapes backslash, semicolon (field sep), and square brackets (contents
    scope delimiters). ponytail: only these 4 chars; MUD text never uses them.
    """
    s = s.replace("\\", "\\\\")
    s = s.replace(";", "\\;")
    s = s.replace("[", "\\[")
    s = s.replace("]", "\\]")
    return s


def _str_unescape(s):
    """Unescape a string field value from an item token. [PRIMESUD]"""
    out = []
    i = 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            out.append(s[i + 1])
            i += 2
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


def _split_token_fields(token):
    """Split token into fields on ';', respecting backslash escapes and '[...]' brackets. [PRIMESUD]"""
    fields = []
    depth = 0
    buf = []
    escaped = False
    for ch in token:
        if escaped:
            buf.append(ch)
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            buf.append(ch)
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        if ch == ";" and depth == 0:
            fields.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf:
        fields.append("".join(buf))
    return fields


def serialize_item_token(obj):
    """Serialize item instance to v2 save token. [PRIMESUD]"""
    fields = ["v:" + str(obj["vnum"])]
    if "level" in obj:
        fields.append("lv:" + str(obj["level"]))
    if "cost" in obj:
        fields.append("c:" + str(obj["cost"]))
    if "charges" in obj:
        fields.append("ch:" + str(obj["charges"]))
    if "max_charges" in obj:
        fields.append("mx:" + str(obj["max_charges"]))
    if obj.get("enchanted"):
        fields.append("en:1")
    if "extra_flags" in obj:
        names = sorted(obj["extra_flags"])
        fields.append("ef:" + ",".join(names))
    if "weapon_flags" in obj:
        names = sorted(obj["weapon_flags"])
        fields.append("wf:" + ",".join(names))
    if "container_flags" in obj:
        # instance closed/locked state (see item_container_flags); empty dict
        # preserved -- an opened chest must keep overriding a closed template
        names = sorted(obj["container_flags"])
        fields.append("cf:" + ",".join(names))
    if "type" in obj:
        # instance type override, e.g. death_cry/poison_effect trash downgrade
        fields.append("ty:" + _str_escape(str(obj["type"])))
    for af in obj.get("affect_list", []):
        parts = [
            str(af.get("type", 0)),
            str(af.get("level", 0)),
            str(af.get("duration", 0)),
            str(af.get("location", "")),
            str(af.get("modifier", 0)),
            str(af.get("bitvector", "")),
            str(af.get("where", "")),
        ]
        fields.append("af:" + ",".join(parts))
    if "timer" in obj:
        fields.append("ti:" + str(obj["timer"]))
    if "liquid_left" in obj:
        fields.append("ll:" + str(obj["liquid_left"]))
    if "liquid_total" in obj:
        fields.append("lt:" + str(obj["liquid_total"]))
    if "liquid_type" in obj:
        fields.append("lq:" + _str_escape(str(obj["liquid_type"])))
    if "poisoned" in obj:
        # explicit 0 preserved: a cleared poison must override template
        fields.append("po:" + ("1" if obj["poisoned"] else "0"))
    if "short_descr" in obj:
        fields.append("sd:" + _str_escape(str(obj["short_descr"])))
    if "description" in obj:
        fields.append("de:" + _str_escape(str(obj["description"])))
    if "gold" in obj:
        fields.append("go:" + str(obj["gold"]))
    if "silver" in obj:
        fields.append("si:" + str(obj["silver"]))
    if obj.get("contents"):
        inner = "^".join(serialize_item_token(o) for o in obj["contents"])
        fields.append("co:[" + inner + "]")
    return ";".join(fields)


def parse_item_token(token):
    """Parse v2 save token into runtime item instance dict. [PRIMESUD]"""
    obj = {"affect_list": []}
    for field in _split_token_fields(token):
        if not field or ":" not in field:
            continue
        key, value = field.split(":", 1)
        if key == "v":
            obj["vnum"] = int(value)
        elif key == "lv":
            obj["level"] = int(value)
        elif key == "c":
            obj["cost"] = int(value)
        elif key == "ch":
            obj["charges"] = int(value)
        elif key == "mx":
            obj["max_charges"] = int(value)
        elif key == "en":
            obj["enchanted"] = value == "1"
        elif key == "ef":
            flags = {}
            for name in value.split(","):
                if name:
                    flags[name] = True
            obj["extra_flags"] = flags
        elif key == "wf":
            flags = {}
            for name in value.split(","):
                if name:
                    flags[name] = True
            obj["weapon_flags"] = flags
        elif key == "cf":
            flags = {}
            for name in value.split(","):
                if name:
                    flags[name] = True
            obj["container_flags"] = flags
        elif key == "ty":
            obj["type"] = _str_unescape(value)
        elif key == "af":
            parts = value.split(",")
            while len(parts) < 7:
                parts.append("")
            obj["affect_list"].append({
                "type": int(parts[0]) if parts[0] else 0,
                "level": int(parts[1]) if parts[1] else 0,
                "duration": int(parts[2]) if parts[2] else 0,
                "location": parts[3],
                "modifier": int(parts[4]) if parts[4] else 0,
                "bitvector": parts[5],
                "where": parts[6],
            })
        elif key == "ti":
            obj["timer"] = int(value)
        elif key == "ll":
            obj["liquid_left"] = int(value)
        elif key == "lt":
            obj["liquid_total"] = int(value)
        elif key == "lq":
            obj["liquid_type"] = _str_unescape(value)
        elif key == "po":
            obj["poisoned"] = value == "1"
        elif key == "sd":
            obj["short_descr"] = _str_unescape(value)
        elif key == "de":
            obj["description"] = _str_unescape(value)
        elif key == "go":
            obj["gold"] = int(value)
        elif key == "si":
            obj["silver"] = int(value)
        elif key == "co":
            inner = value[1:-1] if (value.startswith("[") and value.endswith("]")) else value
            obj["contents"] = [parse_item_token(t) for t in inner.split("^") if t]
    if "vnum" not in obj:
        raise ValueError("item token missing v")
    if not obj["affect_list"]:
        obj.pop("affect_list")
    return obj


def get_obj_list(fragment, item_list, templates, viewer=None):
    """Find the Nth item in item_list whose keywords match fragment (cf. 1stMud get_obj_list in handler.c).

    Supports "2.sword" prefix syntax (cf. 1stMud number_argument in interp.c):
    the integer before '.' is the ordinal; without a prefix returns the first match.
    Items may be plain VNUM ints (room/mob) or instance dicts (player inv/equip).

    Args:
        fragment (str): Player-typed name fragment, optionally prefixed "N.".
        item_list (list): Ordered list of items (int or instance dict) to search.
        templates (dict): Item template dict mapping vnum -> template.
        viewer (dict): Optional observer; when given, items it cannot see
            (can_see_obj) are skipped, matching 1stMud get_obj_list's built-in
            gate (handler.c:2007). [PRIMESUD] darkness gating is scoped to the
            get/drop paths that pass a viewer; other callers leave it None.

    Returns:
        Item from item_list (int or dict), or None if not found.
    """
    nth, fragment = number_argument(fragment)
    count = 0
    for item in item_list:
        vnum = obj_vnum(item)
        if viewer is not None and not can_see_obj(viewer, item):
            continue
        if is_name(fragment, templates[vnum].get("keywords", "")):
            count += 1
            if count == nth:
                return item
    return None


def get_obj_here(player, arg):
    """Find obj in room, inventory, or equipped (cf. 1stMud get_obj_here in handler.c).

    Args:
        player (dict): Player state dict.
        arg (str): Player-typed name fragment.

    Returns:
        Item (int or dict), or None if not found.
    """
    rs = world.rooms[player["room"]]
    obj = get_obj_list(arg, rs["items"], ITEM_DEFS)
    if obj is not None:
        return obj
    obj = get_obj_list(arg, player["inv"], ITEM_DEFS)
    if obj is not None:
        return obj
    equipped = [it for it in player["equip"].values() if it is not None]
    return get_obj_list(arg, equipped, ITEM_DEFS)


def apply_money_pickup(player, obj, tpl):
    """Credit player with coin value silently (cf. 1stMud get_obj in act_obj.c).

    1stMud prints the "You get $p." message in the caller, not here;
    money is just credited and the obj consumed.

    Args:
        player (dict): Player state.
        obj (dict): Coin item instance.
        tpl (dict): Item template.

    Returns:
        bool: True if item was money and was consumed.
    """
    if tpl.get("type") != "money":
        return False
    player["silver"] += obj.get("silver", 0)
    player["gold"] += obj.get("gold", 0)
    return True


def can_drop_obj(ch, obj):
    """True if ch can release obj (cf. 1stMud can_drop_obj in handler.c).

    Nodrop items cannot be dropped, sold, or sacrificed.
    [PRIMESUD] ITEM_AUCTIONED not ported (no auction system).
    """
    tpl = ITEM_DEFS[obj_vnum(obj)]
    if item_extra_flags(obj, tpl).get("nodrop"):
        return False
    return True


def can_carry_n(ch):
    """Max number of items ch can carry (cf. 1stMud can_carry_n in handler.c)."""
    from handler import get_curr_stat
    return 20 + 2 * get_curr_stat(ch, "dex") + ch["level"]


def can_carry_w(ch):
    """Max carry weight for ch in tenths of lbs (cf. 1stMud can_carry_w in handler.c)."""
    from handler import get_curr_stat
    from config import STR_APP_CARRY
    return STR_APP_CARRY[get_curr_stat(ch, "str")] * 10 + ch["level"] * 25


def get_obj_weight(obj):
    """Total weight of obj including contents (cf. 1stMud get_obj_weight in handler.c)."""
    tpl = ITEM_DEFS[obj_vnum(obj)]
    w = tpl.get("weight", 0)
    if isinstance(obj, dict):
        for c in obj.get("contents", []):
            w += get_obj_weight(c)
    return w


def get_carry_weight(ch):
    """Total carried weight incl. coin weight, in tenths of lbs
    (cf. 1stMud get_carry_weight in macro.h)."""
    w = 0
    for o in ch["inv"]:
        w += get_obj_weight(o)
    for e in ch["equip"].values():
        if e is not None:
            w += get_obj_weight(e)
    return w + ch.get("silver", 0) // 10 + ch.get("gold", 0) * 2 // 5

