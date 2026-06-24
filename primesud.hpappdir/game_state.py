"""Game lifecycle helpers for new, load, save, and migration UX."""

import world
from inventory import do_outfit
from macros import _MACRO_SUBST
from mob import reset_area, create_area_states
from player import create_char, save_world, load_world


def init_game_state(game):
    """Initialise mutable game state fields."""
    game._backup_ok = False


def new_game(game, name="Hero"):
    reset_area()
    world.areas = create_area_states()
    player = create_char()
    player["name"] = name
    player["_macros"] = _MACRO_SUBST
    world.chars[1] = player
    do_outfit(game.tr, player, "")  # cf. 1stMud do_outfit in nanny.c for new chars
    save_game(game, quiet=True)


def load_game(game):
    reset_area()
    world.areas = create_area_states()
    player = create_char()
    player["_macros"] = _MACRO_SUBST
    world.chars[1] = player
    result = load_world()
    if isinstance(result, tuple):   # (None, backup_ok) -- version mismatch
        _, game._backup_ok = result
        return None
    return result


def save_game(game, quiet=False):
    return save_world(quiet)
