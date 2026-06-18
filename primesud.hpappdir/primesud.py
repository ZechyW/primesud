# PrimeSUD -- single-user dungeon for the HP Prime
# Port by ZechyW.  Not for commercial distribution.
#
# Based on 1stMud ROM Derivative (c) 2001-2003 Ryan Jennings
# Based on ROM 2.4 beta (c) 1993-1996 Russ Taylor
# Based on Merc 2.1 (c) 1992-1993 Chastain, Quan, Tse
# Based on DikuMud (c) 1990-1991 Hammer, Seifert, Storfeldt, Madsen, Nyboe

"""PrimeSUD application entry point and main game loop."""

from tml_prime import tml_prime as tml, _HIST_UP, _HIST_DN

from config import (DARK_MODE, BG_COLOR, TAB_SIZE, POLL_MS,
                    MS_PER_PULSE, PULSE_VIOLENCE, PULSE_MOBILE, PULSE_TICK, PULSE_AREA,
                    AUTOSAVE_TICKS, TICK_SECS,
                    KEY_COMMANDS as _KEY_COMMANDS,
                    FONT,
                    DEATH_MSG_DELAY,
                    SCROLLBACK_SIZE, SCROLL_STEP,
                    SWIPE_THRESHOLD, TOUCH_SCROLL_STEP,
                    CMD_HISTORY_MAX,
                    FNKEY_SENTINELS)
from util import free_mem, gc_collect
from world import R_STARTING_ROOM, ROOMS
from combat import violence_update
from mob import mobile_update, area_update
from player import tick_update, show_prompt
from commands import interpret
from info import do_look
from macros import _MACRO_SUBST
from terminal import install_color_print
from game_state import (init_game_state, new_game, load_game,
                        handle_version_mismatch, save_game)
from prime_platform import (ticks, wait, wait_ms,
                            save_prime_settings, configure_prime, restore_prime_settings,
                            clear_graphics)


# -- Main classes --------------------------------------------------------------


class Game:
    """Holds game state and drives the main loop."""

    def __init__(self):
        self.tr = tml(dark_mode=DARK_MODE, tab_size=TAB_SIZE, bg_color=BG_COLOR, font=FONT,
                      scrollback_size=SCROLLBACK_SIZE, scroll_step=SCROLL_STEP,
                      touch_scroll_step=TOUCH_SCROLL_STEP, swipe_threshold=SWIPE_THRESHOLD)
        install_color_print(self.tr)
        self.input_buf = ""
        self._cmd_history = []   # [PRIMESUD] submitted commands, oldest first
        self._hist_pos    = None # None = not browsing; int = index into _cmd_history
        self._hist_saved  = ""   # input_buf snapshot from when browsing started
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
        player = self.player
        world = {
            "rooms": self.room_state,
            "mobs": self.mob_instances,
            "areas": self.area_states,
        }

        pulse      = 0
        tick_count = 0
        now        = ticks()
        next_pulse = now + MS_PER_PULSE

        gc_collect()

        tr.resync_keyboard()
        show_prompt(tr, player, self.input_buf)
        do_look(tr, player, [], world)

        while True:
            result = tr.poll_char(_KEY_COMMANDS)
            if tr._scrollback_ms:  # [PRIMESUD] shift pulse clock forward by time spent in scrollback
                next_pulse += tr._scrollback_ms
                tr._scrollback_ms = 0
            if result is not None:
                char, auto_submit = result
                if char == "\n":
                    if self.input_buf:  # [PRIMESUD] append to command history
                        if not self._cmd_history or self._cmd_history[-1] != self.input_buf:
                            self._cmd_history.append(self.input_buf)
                            if len(self._cmd_history) > CMD_HISTORY_MAX:
                                self._cmd_history.pop(0)
                    self._hist_pos   = None
                    self._hist_saved = ""
                    _t0 = ticks()
                    _quit = interpret(self.input_buf, tr, player, world) == "quit"
                    next_pulse += ticks() - _t0  # [PRIMESUD] skip missed pulses during blocking input (e.g. picker)
                    if _quit:
                        break
                    self.input_buf = ""
                    show_prompt(tr, player, self.input_buf)
                elif char == "\b":
                    self.input_buf = self.input_buf[:-1]
                    show_prompt(tr, player, self.input_buf)
                elif char == "\\e":
                    self.input_buf = ""
                    self._hist_pos   = None  # [PRIMESUD] ESC commits to the empty buffer
                    self._hist_saved = ""
                    show_prompt(tr, player, self.input_buf)
                elif char == _HIST_UP:  # [PRIMESUD] recall older command
                    if self._cmd_history:
                        if self._hist_pos is None:
                            self._hist_saved = self.input_buf
                            self._hist_pos = len(self._cmd_history) - 1
                        elif self._hist_pos > 0:
                            self._hist_pos -= 1
                        self.input_buf = self._cmd_history[self._hist_pos]
                        show_prompt(tr, player, self.input_buf)
                elif char == _HIST_DN:  # [PRIMESUD] recall newer command / restore saved
                    if self._hist_pos is not None:
                        if self._hist_pos < len(self._cmd_history) - 1:
                            self._hist_pos += 1
                            self.input_buf = self._cmd_history[self._hist_pos]
                        else:
                            self.input_buf = self._hist_saved
                            self._hist_pos   = None
                            self._hist_saved = ""
                        show_prompt(tr, player, self.input_buf)
                elif auto_submit is True:  # [PRIMESUD] hardware key -- immediate submit
                    _t0 = ticks()
                    _quit = interpret(char, tr, player, world) == "quit"
                    next_pulse += ticks() - _t0  # [PRIMESUD] skip missed pulses during blocking input
                    if _quit:
                        break
                    show_prompt(tr, player, self.input_buf)
                elif auto_submit is False:  # [PRIMESUD] hardware key -- load into buffer
                    self.input_buf = char
                    show_prompt(tr, player, self.input_buf)
                elif char is not None and char not in ("\\L", "\\R", "\\SR"):
                    subst = _MACRO_SUBST.get(char)
                    if subst is not None and not self.input_buf:
                        self.input_buf = subst
                    elif char not in FNKEY_SENTINELS:
                        self.input_buf += char
                    show_prompt(tr, player, self.input_buf)

            now = ticks()
            if now >= next_pulse:
                next_pulse += MS_PER_PULSE
                pulse += 1

                if pulse % PULSE_VIOLENCE == 0:
                    if violence_update(tr, player, world):
                        # [PRIMESUD] Handle auto respawn on death
                        tr.print("You have been KILLED!!")
                        tr.print("Your lifeforce ebbs away...")
                        wait(DEATH_MSG_DELAY)
                        tr.print("A distant warmth draws you back.")
                        wait(DEATH_MSG_DELAY)
                        player["room"] = R_STARTING_ROOM
                        player["hp"]   = 1
                        player["mp"]   = 1
                        player["wait"] = 0
                        player["daze"] = 0
                        tr.print("You come to your senses. Alive, but barely.")
                        tr.print("")
                        do_look(tr, player, [], world)
                    show_prompt(tr, player, self.input_buf)

                if pulse % PULSE_TICK == 0:
                    player["played"] = player.get("played", 0) + TICK_SECS
                    tick_update(tr, player, ROOMS[player["room"]])
                    show_prompt(tr, player, self.input_buf)
                    tick_count += 1
                    if tick_count >= AUTOSAVE_TICKS:
                        save_game(self)
                        tick_count = 0

                if pulse % PULSE_MOBILE == 0:
                    mobile_update(tr, player, world)

                if pulse % PULSE_AREA == 0:
                    area_update(tr, player, world)

                if pulse >= 14400:  # wrap at 1 hour (3600 s x 4 pulses/s)
                    pulse = 0

            wait_ms(POLL_MS)

class PrimeSud:
    """
    Manages environment setup/teardown and top-level game flow.

    Environment pattern adapted from JezzBall 1.23 by Piotr Kowalewski (komame).
    """

    def __enter__(self):
        self.vars = save_prime_settings()
        configure_prime()
        self.game = Game()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        clear_graphics()
        restore_prime_settings(self.vars)
        return exc_type is KeyboardInterrupt

    def run(self):
        """Entry point: run the game inside the environment context manager."""
        with self:
            game = self.game

            # from save_probe import save_format_probe
            # save_format_probe(game.tr)
            game.show_greeting()

            result = load_game(game)
            if result is None:          # version mismatch
                if not handle_version_mismatch(game):
                    return              # user chose quit -- exit without saving
                new_game(game)
            elif not result:            # no save found
                game.tr.print("No save found. Starting new game.")
                game.tr.print("")
                new_game(game)

            try:
                game.game_loop()
            finally:
                save_game(game)


PrimeSud().run()
