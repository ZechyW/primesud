"""Game lifecycle helpers for new, load, save, and migration UX."""

import world
from inventory import do_outfit
from macros import _MACRO_SUBST
from mob import reset_area, create_area_states
from player import create_char, save_world, load_world, reset_char


def init_game_state(game):
    """Initialise mutable game state fields. [PRIMESUD]"""
    game._backup_ok = False


def new_game(game, name="Hero"):
    """Create a new game world with a fresh player character. [PRIMESUD]"""
    reset_area()
    world.areas = create_area_states()
    player = create_char()
    player["name"] = name
    player["_macros"] = _MACRO_SUBST
    world.chars[1] = player
    do_outfit(player, "")  # cf. 1stMud do_outfit in nanny.c for new chars
    save_game(game, quiet=True)


def load_game(game):
    """Load a saved game from persistent storage and restore world state. [PRIMESUD]"""
    reset_area()
    world.areas = create_area_states()
    player = create_char()
    player["_macros"] = _MACRO_SUBST
    world.chars[1] = player
    result = load_world()
    if isinstance(result, tuple):   # (None, backup_ok) -- version mismatch
        _, game._backup_ok = result
        return None
    reset_char(player)
    return result


def save_game(game, quiet=False):
    """Persist the current world state to storage. [PRIMESUD]"""
    return save_world(quiet)
