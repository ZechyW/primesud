"""Item creation, lookup, flags, spell payloads, and save tokens."""

from world import ITEM_TEMPLATES, MOB_TEMPLATES
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
    tpl = ITEM_TEMPLATES[vnum]
    obj = {"vnum": vnum, "cost": tpl.get("value", 0)}
    if "max_charges" in tpl:
        obj["max_charges"] = tpl["max_charges"]
        obj["charges"] = tpl.get("charges", tpl["max_charges"])
    elif "charges" in tpl:
        obj["charges"] = tpl["charges"]
    return obj


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


def item_affect_list(obj):
    """Return runtime object affects list, defaulting to empty list."""
    if isinstance(obj, dict):
        return obj.get("affect_list", [])
    return []


def item_spell_level(obj, tpl):
    """Return spell level for magical item, preferring instance override."""
    if isinstance(obj, dict) and "spell_level" in obj:
        return obj["spell_level"]
    return tpl.get("spell_level")


def item_spells(obj, tpl):
    """Return list of spell names for potion/scroll/pill payloads."""
    if isinstance(obj, dict) and "spells" in obj:
        return obj["spells"]
    return tpl.get("spells", [])


def item_current_charges(obj, tpl):
    """Return current charges for wand/staff, preferring instance state."""
    if isinstance(obj, dict) and "charges" in obj:
        return obj["charges"]
    return tpl.get("charges", tpl.get("max_charges"))


def item_max_charges(obj, tpl):
    """Return maximum charges for wand/staff, preferring instance state."""
    if isinstance(obj, dict) and "max_charges" in obj:
        return obj["max_charges"]
    return tpl.get("max_charges", tpl.get("charges"))


def item_spell_name(obj, tpl):
    """Return single spell name for wand/staff payloads."""
    if isinstance(obj, dict) and "spell" in obj:
        return obj["spell"]
    return tpl.get("spell")


def serialize_item_token(obj):
    """Serialize item instance to v2 save token."""
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
    return ";".join(fields)


def parse_item_token(token):
    """Parse v2 save token into runtime item instance dict."""
    obj = {"affect_list": []}
    for field in token.split(";"):
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
        if is_name(fragment, MOB_TEMPLATES[mob_instances[mob_id]["tpl"]].get("keywords", "")):
            return mob_id
    return None

