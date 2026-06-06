import gc

from tml import tml
from hpprime import dimgrob, eval as ppleval

from config import (DARK_MODE, BG_COLOR, TAB_SIZE, POLL_MS,
                    MS_PER_PULSE, PULSE_VIOLENCE, PULSE_TICK,
                    AUTOSAVE_TICKS, HP_REGEN_NUM, HP_REGEN_DENOM,
                    MP_REGEN_NUM, MP_REGEN_DENOM,
                    KEY_COMMANDS as _KEY_COMMANDS, NAV_KEYS as _NAV_KEYS,
                    TERMINAL_COLS)
from combat import violence_update
from world import MOB_TEMPLATES
from player import (
    create_char,
    reset_area,
    show_prompt,
    _poll_char,
    _resync_keyboard,
    save_char as _save_char,
    load_char as _load_char,
    _roll_hp,
)
from commands import interpret, do_look, _MACRO_SUBST


# ── World tick ────────────────────────────────────────────────────────────────


def world_tick(player, room_state, mob_instances):
    now = int(ppleval("Ticks"))
    for mob_id, inst in mob_instances.items():
        if inst["state"] == "dead" and inst.get("respawn_at", 0) > 0:
            if now >= inst["respawn_at"]:
                tpl = MOB_TEMPLATES[inst["tpl"]]
                _hp = _roll_hp(tpl["hp_dice"])
                inst["hp"] = _hp
                inst["hp_max"] = _hp
                inst["state"] = "idle"
                inst["respawn_at"] = 0
                if mob_id not in room_state[inst["room"]]["mobs"]:
                    room_state[inst["room"]]["mobs"].append(mob_id)

    player["hp"] = min(player["hp_max"], player["hp"] + player["con"] * HP_REGEN_NUM // HP_REGEN_DENOM)
    player["mp"] = min(player["mp_max"], player["mp"] + player["int"] * MP_REGEN_NUM // MP_REGEN_DENOM)


# ── Main classes ──────────────────────────────────────────────────────────────


class Game:
    """Holds game state and drives the main loop."""

    def __init__(self):
        # std5x10green: 64 cols x 24 rows (excluding status bar), green colour
        self.tr = tml(dark_mode=DARK_MODE, tab_size=TAB_SIZE, bg_color=BG_COLOR, font="std5x10green")
        _orig_print = self.tr.print
        _cols = TERMINAL_COLS
        def _wrapped_print(*args, sep=' ', end='\n'):
            text = sep.join(str(a) for a in args)
            lines = []
            while len(text) > _cols:
                i = text.rfind(' ', 0, _cols + 1)
                if i <= 0:
                    i = _cols
                lines.append(text[:i])
                text = text[i:].lstrip(' ')
            lines.append(text)
            for idx, line in enumerate(lines):
                _orig_print(line, end='')
                is_last = (idx == len(lines) - 1)
                # If tml auto-wrapped (non-empty line landed in the last col),
                # cursor_x resets to 0 — the explicit newline would double-advance.
                auto_wrapped = bool(line) and self.tr.cursor_x == 0
                if not is_last and not auto_wrapped:
                    _orig_print('', end='\n')
                elif is_last and end and not auto_wrapped:
                    _orig_print('', end=end)
        self.tr.print = _wrapped_print
        self.input_buf = ""
        self.player = None
        self.room_state = None
        self.mob_instances = None

    def new_game(self, name="Hero"):
        self.player = create_char()
        self.player["name"] = name
        self.room_state, self.mob_instances = reset_area()

    def load_game(self):
        self.player = create_char()
        self.room_state, self.mob_instances = reset_area()
        return _load_char(self.player, self.room_state, self.mob_instances, _MACRO_SUBST)

    def save_game(self):
        if not _save_char(self.player, self.room_state, self.mob_instances, _MACRO_SUBST):
            self.tr.print("Save failed.")
        else:
            self.tr.print("Saved.")

    def run_title(self):
        tr = self.tr
        tr.clear()
        tr.print("=== PRIMESUD ===")
        tr.print("A single-user dungeon.")

        def fmt_bytes(n):
            for unit in ("B", "KB", "MB"):
                if n < 1024:
                    return "{} {}".format(n, unit)
                n //= 1024
            return "{} GB".format(n)

        tr.print("Memory free: {}".format(fmt_bytes(gc.mem_free())))
        tr.print("")

    def game_loop(self):
        tr = self.tr
        player = self.player
        room_state = self.room_state
        mob_instances = self.mob_instances

        pulse      = 0
        tick_count = 0
        now        = int(ppleval("Ticks"))
        next_pulse = now + MS_PER_PULSE

        _resync_keyboard(tr)
        show_prompt(tr, player, self.input_buf)
        do_look(tr, player, [], room_state, mob_instances)

        while True:
            char = _poll_char(tr, _KEY_COMMANDS)
            if char is not None:
                if char == "\n":
                    if interpret(self.input_buf, tr, player, room_state, mob_instances) == "quit":
                        break
                    self.input_buf = ""
                    show_prompt(tr, player, self.input_buf)
                elif char == "\b":
                    self.input_buf = self.input_buf[:-1]
                    show_prompt(tr, player, self.input_buf)
                elif char == "\e":
                    self.input_buf = ""
                    show_prompt(tr, player, self.input_buf)
                elif char in _KEY_COMMANDS.values():
                    if char in _NAV_KEYS:  # [PRIMESUD] immediate nav-pad movement
                        if interpret(char, tr, player, room_state, mob_instances) == "quit":
                            break
                        show_prompt(tr, player, self.input_buf)
                    else:
                        self.input_buf = char
                        show_prompt(tr, player, self.input_buf)
                elif char not in ("\L", "\R", "\SR"):
                    subst = _MACRO_SUBST.get(char)
                    if subst is not None and not self.input_buf:
                        self.input_buf = subst
                    else:
                        self.input_buf += char
                    show_prompt(tr, player, self.input_buf)

            now = int(ppleval("Ticks"))
            if now >= next_pulse:
                next_pulse += MS_PER_PULSE
                pulse += 1

                if pulse % PULSE_VIOLENCE == 0:
                    violence_update(tr, player, mob_instances, room_state)
                    show_prompt(tr, player, self.input_buf)

                if pulse % PULSE_TICK == 0:
                    world_tick(player, room_state, mob_instances)
                    show_prompt(tr, player, self.input_buf)
                    tick_count += 1
                    if tick_count >= AUTOSAVE_TICKS:
                        self.save_game()
                        tick_count = 0

                if pulse >= 14400:  # wrap at 1 hour (3600 s × 4 pulses/s)
                    pulse = 0

            ppleval("WAIT({}/1e3)".format(POLL_MS))


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
            game.run_title()

            if not game.load_game():
                game.tr.print("No save found. Starting new game.")
                game.tr.print("")
                game.new_game()

            try:
                game.game_loop()
            finally:
                game.save_game()


PrimeSud().run()
