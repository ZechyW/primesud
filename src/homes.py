"""Static single-player home adapted from 1stMud homes.c. [PRIMESUD]"""

import world
from colors import color_len
from handler import chprintln
from item import create_object, obj_vnum
from movement import perform_recall
from util import num_str

HOUSE_PRICE = 5000000
HOUSE_TRIVIA = 40
HOME_KEY_VNUM = 17700
HOME_OFFICE_VNUM = 17701
HOME_ROOM_VNUM = 17702
DEFAULT_HOME_DESC = "A quiet room waits for you to make it your own."


def apply_home(player):
    """Apply saved cosmetics to loaded static home room. [PRIMESUD]"""
    if not player.get("home_owned"):
        return
    room = world.ROOM_DEFS._data.get(HOME_ROOM_VNUM)
    if room is None:
        return
    name = player.get("home_name") or player.get("name", "Hero") + "'s Home"
    room["name"] = name
    room["desc"] = player.get("home_desc") or DEFAULT_HOME_DESC
    room["owner"] = player.get("name", "")
    office = world.ROOM_DEFS._data.get(HOME_OFFICE_VNUM)
    if office is not None:
        door = office.get("exits", {}).get("n")
        if isinstance(door, dict):
            door["desc"] = "You see the door to " + name + "."


def _has_home_key(player):
    for obj in player["inv"]:
        if obj_vnum(obj) == HOME_KEY_VNUM:
            return True
    for obj in player["equip"].values():
        if obj is not None and obj_vnum(obj) == HOME_KEY_VNUM:
            return True
    return False


def _give_key(player):
    if _has_home_key(player):
        chprintln(player, "You already have a key to your home.")
        return False
    key = create_object(HOME_KEY_VNUM)
    name = player.get("name", "Hero")
    key["short_descr"] = name + "'s estate key"
    key["description"] = "The key to " + name + "'s home is here."
    player["inv"].append(key)
    chprintln(player, "A house key appears in your inventory.")
    world.save_pending = True
    return True


def _owned_room(player):
    if not player.get("home_owned"):
        chprintln(player, "You don't own a home.")
        return False
    if player["room"] != HOME_ROOM_VNUM:
        chprintln(player, "But you do not own this room!")
        return False
    return True


def _home_help(player):
    if not player.get("home_owned"):
        chprintln(player, "Home: buy - purchase the vacant estate here")
        return
    chprintln(player, "Home: key, recall, name <title>, describe <text>")
    chprintln(player, "Drop items in your home to decorate it; floor items persist.")


def do_home(player, argument):
    """Manage one static solo home (cf. 1stMud do_home in homes.c). [PRIMESUD]

    Args:
        player (dict): Acting player.
        argument (str): Raw command tail, preserving cosmetic text case.
    """
    if player.get("is_npc"):
        chprintln(player, "Mobiles don't have homes.")
        return
    command, _, text = argument.strip().partition(" ")
    command = command.lower()
    matches = [name for name in ("buy", "key", "recall", "name", "describe")
               if name.startswith(command)] if command else []
    if len(matches) != 1:
        _home_help(player)
        return
    command = matches[0]
    text = text.strip()

    if command == "buy":
        # [PRIMESUD] Owned/location checks front-loaded for UX (upstream
        # home_buy checks gold/trivia first); the owned message drops
        # upstream's reference to the unported 'home add'/'home furnish'.
        # Cost message texts follow 1stMud home_buy.
        if player.get("home_owned"):
            chprintln(player, "You already own a home.")
            return
        if player["room"] != HOME_OFFICE_VNUM:
            chprintln(player, "You must be at the Player Estates office.")
            return
        if player["gold"] < HOUSE_PRICE:
            chprintln(player, "{wIt costs " + num_str(HOUSE_PRICE)
                      + " gold to buy a home.{x")
            return
        if player["trivia"] < HOUSE_TRIVIA:
            chprintln(player, "It costs " + num_str(HOUSE_TRIVIA)
                      + " trivia points to buy a house.")
            return
        player["gold"] -= HOUSE_PRICE
        player["trivia"] -= HOUSE_TRIVIA
        player["home_owned"] = 1
        player["home_name"] = player.get("name", "Hero") + "'s Home"
        player["home_desc"] = DEFAULT_HOME_DESC
        apply_home(player)
        _give_key(player)
        world.save_pending = True
        chprintln(player, "Congratulations, you are now a proud home owner.")
        return

    if not player.get("home_owned"):
        chprintln(player, "You don't own a home.")
        return
    if command == "key":
        _give_key(player)
        return
    if command == "recall":
        # perform_recall moves pets only when destination runtime state exists.
        world.ROOM_DEFS[HOME_ROOM_VNUM]
        perform_recall(player, HOME_ROOM_VNUM, "go home")
        return
    if not _owned_room(player):
        return
    if not text:
        chprintln(player, "Change your home "
                  + ("name" if command == "name" else "description") + " to what?")
        return
    if "~" in text or '"' in text:
        chprintln(player, "Home text may not contain '~' or '\"'.")
        return
    if command == "name":
        if color_len(text) > 25:
            chprintln(player, "That home name is too long.")
            return
        player["home_name"] = text
    else:
        if len(text) > 512:
            chprintln(player, "That home description is too long.")
            return
        player["home_desc"] = text
    apply_home(player)
    world.save_pending = True
    chprintln(player, "Ok.")
