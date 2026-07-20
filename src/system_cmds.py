"""System command handlers for save, backup, and quit."""

from game_state import save_world, backup_world
from handler import chprintln, chprintlnf
from skill_utils import WaitState
from config import PULSE_VIOLENCE


def do_save(player, args):
    """Save current world state (cf. 1stMud `do_save` in save.c)."""
    save_world()


def do_backup(player, args):
    """Save current world state to a second backup slot (cf. 1stMud
    do_backup in act_comm.c).

    ``backup check`` reports how long it has been since the last backup;
    silent if you've played under an hour total and never backed up
    (matches upstream's nested check -- see act_comm.c:1000-1027).
    Otherwise writes a full save to the backup slot (game_state.backup_world,
    distinct from the primary autosave slot) and records the played-time of
    the backup.

    [PRIMESUD] No min_save_lvl level gate: upstream requires
    get_trust(ch) >= mud_info.min_save_lvl*3 (default level 6) -- matches
    do_save above, which already has no such gate in PrimeSUD (single-player,
    no mud.dat config). No update_statlist/update_members calls -- those sync
    a multiplayer website/clan roster that PrimeSUD doesn't have. No restore
    command -- see game_state.backup_world docstring.

    Args:
        player (dict): Player state dict.
        args (list): ["check"] to query backup age; otherwise ignored.
    """
    if args and args[0] == "check":
        elapsed = player.get("played", 0) - player.get("backup", 0)
        if elapsed >= 3600:  # cf. 1stMud HOUR (act_comm.c uses HOUR = 3600s)
            if player.get("backup", 0) == 0:
                chprintln(player, "{RThere is currently no backup for your character.{x")
            elif elapsed >= 3600 * 24:
                chprintlnf(player,
                          "{RYou have not backed up for {W%d{R hours of gameplay.{x",
                          elapsed // 3600)
            else:
                hrs = elapsed // 3600
                chprintlnf(player,
                          "{RYou have not backed up for {W%d{R hour%s of gameplay.{x",
                          hrs, "" if hrs == 1 else "s")
        return

    if backup_world():
        player["backup"] = player.get("played", 0)
        chprintlnf(player, "%s has been saved to a backup.", player.get("name", ""))
        WaitState(player, PULSE_VIOLENCE)
    else:
        # [PRIMESUD] upstream never checks backup_char_obj's return value and
        # always prints success (the write failure only reaches a server-side
        # bugf log) -- a visible failure message is friendlier for a
        # single-user device where there's no admin watching the log.
        chprintln(player, "Backup failed.")


def do_quit(player, args):
    """Quit the game (cf. 1stMud `do_quit` in act_comm.c)."""
    return "quit"
