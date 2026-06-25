"""System command handlers for save and quit."""

from actor import chprintln
from player import save_world


def do_save(player, args):
    save_world()


def do_quit(player, args):
    return "quit"


def do_debug(player, args):  # [PRIMESUD]
    """Debug playtesting helper: inject test items with patched stats."""
    from item import create_object
    from area_school import I_DIPLOMA
    obj = create_object(I_DIPLOMA)
    obj["affect_list"] = [{"location": "ac", "modifier": -1100}]
    player["inv"].append(obj)
    chprintln(player, "Debug: diploma (ac -1100) added to inventory.")
