from tml import tml
from hpprime import dimgrob, eval as ppleval

from world import MOB_TEMPLATES
from player import (
    make_player, make_room_state, make_mob_instances,
    show_prompt, _wait_digit, _poll_char, _resync_keyboard,
    save_game as _save_game, load_game as _load_game,
)
from commands import _dispatch_command, cmd_look


# ── World tick ────────────────────────────────────────────────────────────────

def world_tick(player, room_state, mob_instances):
    now = int(ppleval("Ticks"))
    for iid, inst in mob_instances.items():
        if inst["state"] == "dead" and inst.get("respawn_at", 0) > 0:
            if now >= inst["respawn_at"]:
                tpl = MOB_TEMPLATES[inst["tpl"]]
                inst["hp"] = tpl["hp_max"]
                inst["state"] = "idle"
                inst["respawn_at"] = 0
                room_state[inst["room"]]["mobs"].append(iid)


# ── Main classes ──────────────────────────────────────────────────────────────

class Game:
    """Holds game state and drives the main loop."""

    def __init__(self):
        self.tr = tml(dark_mode=True, tab_size=8, bg_color=0x3000)
        self.input_buf = ""
        self.config = {"tick_interval": 5000}
        self.player = None
        self.room_state = None
        self.mob_instances = None

    def new_game(self, name="Hero"):
        self.player = make_player()
        self.player["name"] = name
        self.room_state = make_room_state()
        self.mob_instances = make_mob_instances()

    def load_game(self):
        self.player = make_player()
        self.room_state = make_room_state()
        self.mob_instances = make_mob_instances()
        return _load_game(self.player, self.room_state, self.mob_instances)

    def save_game(self):
        return _save_game(self.player, self.room_state, self.mob_instances)

    def run_title(self):
        tr = self.tr
        tr.clear()
        tr.print("=== PRIMESUD ===")
        tr.print("A single-user dungeon.")
        tr.print("")
        tr.print("1. New Game")
        tr.print("2. Load Game")
        tr.print("3. Quit")
        while True:
            choice = _wait_digit(3)
            if choice == 1:
                return "new"
            if choice == 2:
                return "load"
            if choice == 3:
                return "quit"

    def game_loop(self):
        tr = self.tr
        player = self.player
        room_state = self.room_state
        mob_instances = self.mob_instances

        t = int(ppleval("Ticks"))
        next_tick = t + self.config["tick_interval"]

        _resync_keyboard(tr)

        show_prompt(tr, player, self.input_buf)
        cmd_look(tr, player, room_state, mob_instances)

        while True:
            char = _poll_char(tr)
            if char is not None:
                if char == '\n':
                    result = _dispatch_command(
                        self.input_buf, tr, player, room_state, mob_instances)
                    if result == "quit":
                        break
                    self.input_buf = ""
                    show_prompt(tr, player, self.input_buf)
                elif char == '\b':
                    self.input_buf = self.input_buf[:-1]
                    show_prompt(tr, player, self.input_buf)
                elif char == '\e':
                    self.input_buf = ""
                    show_prompt(tr, player, self.input_buf)
                elif char not in ('\L', '\R', '\SR'):
                    self.input_buf += char
                    show_prompt(tr, player, self.input_buf)

            t = int(ppleval("Ticks"))
            if t >= next_tick:
                world_tick(player, room_state, mob_instances)
                next_tick += self.config["tick_interval"]

            ppleval("WAIT(1/1e3)")


class PrimeSud:
    """
    Manages environment setup/teardown and top-level game flow.

    Environment pattern adapted from JezzBall 1.23 by Piotr Kowalewski (komame).
    """

    def __enter__(self):
        sep = ppleval("HSeparator")
        ppleval("HSeparator:=0")
        self.vars = tuple(ppleval("{AAngle,AFormat,AComplex,Bits}")) + (sep,)
        ppleval("AAngle:=1;AFormat:=1;AComplex:=0;Bits:=32")
        self.game = Game()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for n in range(1, 9):
            dimgrob(n, 0, 0, 0)
        ppleval(
            "AAngle:=%d;AFormat:=%d;AComplex:=%d;Bits:=%d;HSeparator:=%d;TOff:=TOff"
            % self.vars
        )
        return exc_type is KeyboardInterrupt

    def run(self):
        """Entry point: run the game inside the environment context manager."""
        with self:
            game = self.game
            mode = game.run_title()

            if mode == "quit":
                return
            if mode == "new":
                game.new_game()
            elif mode == "load":
                if not game.load_game():
                    game.tr.print("No save found. Starting new game.")
                    game.new_game()

            game.game_loop()
            game.save_game()


PrimeSud().run()
