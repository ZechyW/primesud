# PrimeSUD -- single-user dungeon for the HP Prime
# Port by ZechyW.  Not for commercial distribution.
#
# Based on 1stMud ROM Derivative (c) 2001-2003 Ryan Jennings
# Based on ROM 2.4 beta (c) 1993-1996 Russ Taylor
# Based on Merc 2.1 (c) 1992-1993 Chastain, Quan, Tse
# Based on DikuMud (c) 1990-1991 Hammer, Seifert, Storfeldt, Madsen, Nyboe

"""PrimeSUD application entry point and main game loop."""

from tml_prime import _HIST_UP, _HIST_DN

from config import (
    POLL_MS,
    MS_PER_PULSE,
    AUTOSAVE_TICKS,
    KEY_COMMANDS as _KEY_COMMANDS,
    CMD_HISTORY_MAX,
    FNKEY_SENTINELS,
)
from util import free_mem, gc_collect
import world
from world import MOB_DEFS, init_world
from combat import mob_condition
from player import show_prompt
from update import update_handler, UPD_VIOLENCE, UPD_TICK
from commands import interpret
from info import do_look
from macros import _MACRO_SUBST
import terminal
from config import SAVE_VAR
from game_state import (
    init_game_state,
    new_game,
    load_game,
    save_game,
)
from prime_platform import ticks, wait_ms, clear_graphics


def _handle_version_mismatch(game):
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


# -- Main classes --------------------------------------------------------------


class Game:
    """Holds game state and drives the main loop."""

    def __init__(self):
        self.tr = terminal.tr
        self.input_buf = ""
        self._cmd_history = []   # [PRIMESUD] submitted commands, oldest first
        self._hist_pos    = None # None = not browsing; int = index into _cmd_history
        self._hist_saved  = ""   # input_buf snapshot from when browsing started
        self._pending_cmd = None # command queued while wait > 0 (cf. 1stMud comm.c input buffer)
        self._backup_ok = False  # set by load_game on version mismatch
        init_game_state(self)

    def show_greeting(self):
        tr = self.tr
        tr.clear()

        mem_part = "{G(Mem. free: %s)" % free_mem()
        pad = 64 - 23 - len(mem_part) - 1
        _first = '{C 8888888b.          d8b' + ' ' * pad + mem_part + '{x'
        tr.print(_first)
        tr.print("{C 888   Y88b         Y8P                                       {x")
        tr.print("{C 888    888                                                   {x")
        tr.print("{C 888   d88P 888d888 888 88888b.d88b.   .d88b.                 {x")
        tr.print('{C 8888888P"  888P"   888 888 "888 "88b d8P  Y8b                {x')
        tr.print("{C 888        888     888 888  888  888 88888888                {x")
        tr.print("{C 888        888     888 888  888  888 Y8b.                    {x")
        tr.print('{C 888        888     888 888  888  888  "Y8888                 {x')
        tr.print("{C                             .d8888b.  888     888 8888888b.  {x")
        tr.print('{C                            d88P  Y88b 888     888 888  "Y88b {x')
        tr.print("{C                            Y88b.      888     888 888    888 {x")
        tr.print('{C                             "Y888b.   888     888 888    888 {x')
        tr.print('{C                                "Y88b. 888     888 888    888 {x')
        tr.print('{C                                  "888 888     888 888    888 {x')
        tr.print("{C                            Y88b  d88P Y88b. .d88P 888  .d88P {x")
        tr.print('{C                             "Y8888P"   "Y88888P"  8888888P"  {x')
        tr.print("{c      Original DikuMUD by Hans Staerfeldt, Katja Nyboe,       {x")
        tr.print("{c      Tom Madsen, Michael Seifert, and Sebastian Hammer       {x")
        tr.print("{c      Based on MERC 2.1 code by Hatchet, Furey, and Kahn      {x")
        tr.print("{c      ROM 2.4 copyright (c) 1993-1998 Russ Taylor.            {x")
        tr.print("{c      1stMud Server copyright (c) 2001-2004, Markanth.        {x")
        tr.input("                    [Press Enter to start]                    ",
            alpha=False,
        )

        tr.print()

    def game_loop(self):
        tr = self.tr
        player = world.chars[1]

        tick_count = 0
        now        = ticks()
        next_pulse = now + MS_PER_PULSE

        gc_collect()

        tr.resync_keyboard()
        show_prompt(player, self.input_buf)
        do_look(player, [])

        while True:
            result = tr.poll_char(_KEY_COMMANDS)
            if tr._scrollback_ms:  # [PRIMESUD] shift pulse clock forward by time spent in scrollback
                next_pulse += tr._scrollback_ms
                tr._scrollback_ms = 0
            if result is not None:
                char, auto_submit = result
                if char == "\n":
                    self._hist_pos   = None
                    self._hist_saved = ""
                    if player.get("wait", 0) > 0:
                        # cf. 1stMud comm.c: wait > 0 queues command
                        if self.input_buf:
                            self._pending_cmd = self.input_buf
                            tr.print("{D[Recovering... command queued]{x")  # [PRIMESUD]
                        self.input_buf = ""
                        show_prompt(player, self.input_buf)
                    else:
                        _t0 = ticks()
                        resolved = interpret(self.input_buf, player)
                        next_pulse += ticks() - _t0  # [PRIMESUD] skip missed pulses during blocking input (e.g. picker)
                        _quit = resolved == "quit"
                        entry = resolved if (resolved and resolved != "quit") else self.input_buf
                        if entry:  # [PRIMESUD] store picker-resolved form so replay works
                            if not self._cmd_history or self._cmd_history[-1] != entry:
                                self._cmd_history.append(entry)
                                if len(self._cmd_history) > CMD_HISTORY_MAX:
                                    self._cmd_history.pop(0)
                        if _quit:
                            break
                        self.input_buf = ""
                        tr.alpha_lock = tr.is_alpha = False
                        tr._refresh_indicators()
                        show_prompt(player, self.input_buf)
                elif char == "\b":
                    self.input_buf = self.input_buf[:-1]
                    show_prompt(player, self.input_buf)
                elif char == "\\e":
                    self.input_buf = ""
                    self._hist_pos   = None  # [PRIMESUD] ESC commits to the empty buffer
                    self._hist_saved = ""
                    show_prompt(player, self.input_buf)
                elif char == _HIST_UP:  # [PRIMESUD] recall older command
                    if self._cmd_history:
                        if self._hist_pos is None:
                            self._hist_saved = self.input_buf
                            self._hist_pos = len(self._cmd_history) - 1
                        elif self._hist_pos > 0:
                            self._hist_pos -= 1
                        self.input_buf = self._cmd_history[self._hist_pos]
                        show_prompt(player, self.input_buf)
                elif char == _HIST_DN:  # [PRIMESUD] recall newer command / restore saved
                    if self._hist_pos is not None:
                        if self._hist_pos < len(self._cmd_history) - 1:
                            self._hist_pos += 1
                            self.input_buf = self._cmd_history[self._hist_pos]
                        else:
                            self.input_buf = self._hist_saved
                            self._hist_pos   = None
                            self._hist_saved = ""
                        show_prompt(player, self.input_buf)
                elif auto_submit is True:  # [PRIMESUD] hardware key -- immediate submit
                    if player.get("wait", 0) > 0:
                        self._pending_cmd = char
                        tr.print("{D[Recovering... command queued]{x")  # [PRIMESUD]
                    else:
                        _t0 = ticks()
                        _quit = interpret(char, player) == "quit"
                        next_pulse += ticks() - _t0  # [PRIMESUD] skip missed pulses during blocking input
                        if _quit:
                            break
                        show_prompt(player, self.input_buf)
                elif auto_submit is False:  # [PRIMESUD] hardware key -- load into buffer
                    self.input_buf = char
                    show_prompt(player, self.input_buf)
                elif char is not None and char not in ("\\L", "\\R", "\\SR"):
                    subst = _MACRO_SUBST.get(char)
                    if subst is not None and not self.input_buf:
                        self.input_buf = subst
                    elif char not in FNKEY_SENTINELS:
                        self.input_buf += char
                    show_prompt(player, self.input_buf)

            now = ticks()
            if now >= next_pulse:
                next_pulse += MS_PER_PULSE

                # Per-pulse player timer decrement (cf. 1stMud comm.c:865-870)
                if player.get("wait", 0) > 0:
                    player["wait"] -= 1
                    if player["wait"] == 0 and self._pending_cmd is not None:
                        _t0 = ticks()
                        _cmd = self._pending_cmd
                        self._pending_cmd = None
                        resolved = interpret(_cmd, player)
                        next_pulse += ticks() - _t0
                        _quit = resolved == "quit"
                        entry = resolved if (resolved and resolved != "quit") else _cmd
                        if entry:
                            if not self._cmd_history or self._cmd_history[-1] != entry:
                                self._cmd_history.append(entry)
                                if len(self._cmd_history) > CMD_HISTORY_MAX:
                                    self._cmd_history.pop(0)
                        if _quit:
                            break
                        show_prompt(player, self.input_buf)
                if player.get("daze", 0) > 0:
                    player["daze"] -= 1

                fired = update_handler()

                # [PRIMESUD] display follows -- not part of 1stMud update_handler
                if fired & UPD_VIOLENCE:
                    if player["fighting"] is not None:
                        fid = player["fighting"]
                        finst = world.chars[fid]
                        tr.print(mob_condition(finst, MOB_DEFS[finst["tpl"]]))
                        tr.print("")
                    show_prompt(player, self.input_buf)

                if fired & UPD_TICK:
                    show_prompt(player, self.input_buf)
                    tick_count += 1
                    if tick_count >= AUTOSAVE_TICKS:
                        save_game(self, quiet=False)
                        tick_count = 0

            wait_ms(POLL_MS)

class PrimeSud:
    """
    Manages environment setup/teardown and top-level game flow.

    Environment pattern adapted from JezzBall 1.23 by Piotr Kowalewski (komame).
    """

    def __enter__(self):
        self.game = Game()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        clear_graphics()
        return exc_type is KeyboardInterrupt

    def run(self):
        """Entry point: run the game inside the environment context manager."""
        # Initialise world catalogs here so imports stay light but runtime users
        # can treat world globals as ready.
        init_world()
        with self:
            game = self.game

            game.show_greeting()

            result = load_game(game)
            if result is None:          # version mismatch
                if not _handle_version_mismatch(game):
                    return              # user chose quit -- exit without saving
                new_game(game)
            elif not result:            # no save found
                game.tr.print("No save found. Starting new game.")
                game.tr.print("")
                new_game(game)
            else:                       # save loaded
                game.tr.print("Loaded from: %s." % result)
                game.tr.print("")

            try:
                game.game_loop()
            finally:
                save_game(game, quiet=True)


PrimeSud().run()
