"""Item creation, lookup, flags, spell payloads, and save tokens."""

import world
from world import ITEM_DEFS, MOB_DEFS
from actor import is_name


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
    tpl = ITEM_DEFS[vnum]
    obj = {"vnum": vnum, "cost": tpl.get("value", 0)}
    if "max_charges" in tpl:
        obj["max_charges"] = tpl["max_charges"]
        obj["charges"] = tpl.get("charges", tpl["max_charges"])
    elif "charges" in tpl:
        obj["charges"] = tpl["charges"]
    return obj


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
    """Remove one object affect and clear its direct flag bit if present. [PRIMESUD]"""
    affects = obj.get("affect_list", [])
    if af in affects:
        affects.remove(af)
    if not affects and "affect_list" in obj:
        del obj["affect_list"]
    bit = af.get("bitvector", "")
    if bit:
        set_item_extra_flag(obj, tpl, bit, False)


def item_affect_to_obj(obj, af, tpl):
    """Apply one timed object affect to runtime item state. [PRIMESUD]"""
    cur = dict(af)
    obj.setdefault("affect_list", []).append(cur)
    bit = cur.get("bitvector", "")
    if bit:
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


def get_obj_list(fragment, item_list, templates):
    """Find the Nth item in item_list whose keywords match fragment (cf. 1stMud get_obj_list in handler.c).

    Supports "2.sword" prefix syntax (cf. 1stMud number_argument in interp.c):
    the integer before '.' is the ordinal; without a prefix returns the first match.
    Items may be plain VNUM ints (room/mob) or instance dicts (player inv/equip).

    Args:
        fragment (str): Player-typed name fragment, optionally prefixed "N.".
        item_list (list): Ordered list of items (int or instance dict) to search.
        templates (dict): Item template dict mapping vnum -> template.

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
    from actor import get_curr_stat
    return 20 + 2 * get_curr_stat(ch, "dex") + ch["level"]


def can_carry_w(ch):
    """Max carry weight for ch in tenths of lbs (cf. 1stMud can_carry_w in handler.c)."""
    from actor import get_curr_stat
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


def get_char_room(fragment, inst_ids, mob_instances):
    """Find the first mob in inst_ids whose keywords match fragment (cf. 1stMud get_char_room in handler.c).

    Args:
        fragment (str): Player-typed name fragment.
        inst_ids (list): Ordered list of mob instance IDs to search.
        mob_instances (dict): Mob instance mapping mob ID -> mob instance dict.

    Returns:
        int or None: First matching mob instance ID, or None if not found.
    """
    for mob_id in inst_ids:
        if is_name(fragment, MOB_DEFS[mob_instances[mob_id]["tpl"]].get("keywords", "")):
            return mob_id
    return None

