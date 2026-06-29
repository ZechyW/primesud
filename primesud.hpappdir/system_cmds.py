"""System command handlers for save and quit."""

from actor import chprintln
from player import save_world


def do_save(player, args):
    """Save current world state (cf. 1stMud `do_save` in save.c)."""
    save_world()


def do_quit(player, args):
    """Quit the game (cf. 1stMud `do_quit` in act_comm.c)."""
    return "quit"


def do_debug(player, args):
    """Debug playtesting helper: inject test items with patched stats. [PRIMESUD]"""
    from item import create_object
    from area_school import I_DIPLOMA
    obj = create_object(I_DIPLOMA)
    obj["affect_list"] = [{"location": "ac", "modifier": -1100}]
    player["inv"].append(obj)
    chprintln(player, "Debug: diploma (ac -1100) added to inventory.")
