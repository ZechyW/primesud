"""System command handlers for save and quit."""

from player import save_state


def do_save(tr, player, args, world):
    save_state(tr, player, world)


def do_quit(tr, player, args, world):
    return "quit"
