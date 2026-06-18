"""Game lifecycle helpers for new, load, save, and migration UX."""

from config import SAVE_VAR
from player import create_char, save_char, load_char
from mob import reset_area, create_area_states
from inventory import do_outfit
from macros import _MACRO_SUBST


def init_game_state(game):
    """Initialise mutable game state fields."""
    game.player = None
    game.room_state = None
    game.mob_instances = None
    game.area_states = create_area_states()
    game._backup_ok = False


def new_game(game, name="Hero"):
    game.player = create_char()
    game.player["name"] = name
    game.room_state, game.mob_instances = reset_area()
    game.area_states = create_area_states()
    game.player["_macros"] = _MACRO_SUBST
    do_outfit(game.tr, game.player, "", None)  # cf. 1stMud do_outfit in nanny.c for new chars
    save_game(game)


def load_game(game):
    game.player = create_char()
    game.room_state, game.mob_instances = reset_area()
    game.area_states = create_area_states()
    game.player["_macros"] = _MACRO_SUBST
    result = load_char(game.player, {"rooms": game.room_state,
                                     "mobs": game.mob_instances,
                                     "areas": game.area_states})
    if isinstance(result, tuple):   # (None, backup_ok) -- version mismatch
        _, game._backup_ok = result
        return None
    return result


def handle_version_mismatch(game):
    """Prompt the user after a save format version mismatch."""
    tr = game.tr
    tr.print("{RWARNING:{x Save format has changed.")
    if game._backup_ok:
        tr.print("Your old save has been backed up to: {C" + SAVE_VAR + "_bak{x")
    else:
        tr.print("{RWARNING:{x Backup to {C" + SAVE_VAR + "_bak{x FAILED.")
        tr.print("Your old save is still in {C" + SAVE_VAR + "{x -- do NOT start")
        tr.print("a new game here or it will be overwritten.")
    tr.print("")
    tr.print("[N] Start a new game")
    tr.print("[Q] Quit (restore or migrate the save manually)")
    tr.print("")
    while True:
        choice = tr.input("Choice (N/Q): ", alpha=False).strip().lower()
        if choice == "n":
            return True
        if choice == "q":
            return False


def save_game(game):
    try:
        save_char(game.player, {
            "rooms": game.room_state,
            "mobs": game.mob_instances,
            "areas": game.area_states,
        })
    except Exception as e:
        game.tr.print("Save failed: {}".format(e))
