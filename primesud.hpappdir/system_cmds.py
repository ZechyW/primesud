"""System command handlers for save and quit."""

from player import save_char


def do_save(tr, player, args, world):
    try:
        save_char(player, world)
        tr.print("Saved.")
    except Exception as e:
        tr.print("Save failed: {}".format(e))


def do_quit(tr, player, args, world):
    return "quit"
