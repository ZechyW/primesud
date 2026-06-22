"""System command handlers for save and quit."""

from player import save_world


def do_save(tr, player, args, world):
    save_world(tr, world)


def do_quit(tr, player, args, world):
    return "quit"


def do_debug(tr, player, args, world):  # [PRIMESUD]
    """Debug playtesting helper: inject test items with patched stats."""
    from item import create_object
    from area_school import I_DIPLOMA
    obj = create_object(I_DIPLOMA)
    obj["affect_list"] = [{"location": "ac", "modifier": -1100}]
    player["inv"].append(obj)
    tr.print("Debug: diploma (ac -1100) added to inventory.")
