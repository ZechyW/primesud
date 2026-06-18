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


