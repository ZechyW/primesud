"""System command handlers for save and quit."""

from game_state import save_world


def do_save(player, args):
    """Save current world state (cf. 1stMud `do_save` in save.c)."""
    save_world()


def do_quit(player, args):
    """Quit the game (cf. 1stMud `do_quit` in act_comm.c)."""
    return "quit"
