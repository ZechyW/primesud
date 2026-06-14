# PrimeSUD — single-user dungeon for the HP Prime
# Port by ZechyW.  Not for commercial distribution.
#
# Based on 1stMud ROM Derivative (c) 2001-2003 Ryan Jennings
# Based on ROM 2.4 beta (c) 1993-1996 Russ Taylor
# Based on Merc 2.1 (c) 1992-1993 Chastain, Quan, Tse
# Based on DikuMud (c) 1990-1991 Hammer, Seifert, Storfeldt, Madsen, Nyboe

from tml_sb import tml_sb as tml, SB_UP as _SB_UP, SB_DN as _SB_DN
from hpprime import dimgrob, eval as ppleval, getpix, pixon, grobw, grobh, strblit2

from urandom import randint
from config import (DARK_MODE, BG_COLOR, TAB_SIZE, POLL_MS,
                    MS_PER_PULSE, PULSE_VIOLENCE, PULSE_MOBILE, PULSE_TICK, PULSE_AREA,
                    AUTOSAVE_TICKS,
                    KEY_COMMANDS as _KEY_COMMANDS,
                    TERMINAL_COLS, FONT, FONT_GROB, COLOR_GROB,
                    DEATH_MSG_DELAY)
from util import free_mem
from world import R_STARTING_ROOM, ROOMS, AREA_DEFS
from combat import violence_update
from player import (
    create_char,
    reset_area,
    reset_mobs,
    mobile_update,
    tick_update,
    show_prompt,
    _poll_char,
    _resync_keyboard,
    save_char as _save_char,
    load_char as _load_char,
)
from commands import interpret, do_look, _MACRO_SUBST
from colors import COLOR_CODE, ANSI_COLORS, _RESET_CODES, color_wrap_full


# ── World tick / area update ──────────────────────────────────────────────────

# Area age thresholds (cf. 1stMud area_update: age < 3 skip; age >= 15 reset
# when player present; age >= 31 hard cap).  Single-player simplification:
# player is always present, so the condition collapses to age >= 15.
_AREA_AGE_MIN   = 3   # skip reset below this age
_AREA_AGE_RESET = 15  # reset threshold (player always present)


_RESET_MSGS = (
    "The area repopulates itself.",
    "You notice a change in the area.",
    "Time completes another cycle bringing life to the area.",
    "You feel a sudden deja-vu bringing change to the area.",
    "You hear noises off in the distance...",
)


def area_update(tr, player, area_states, room_state, mob_instances):
    """Increment each area's age and reset any that reach the threshold (cf. 1stMud area_update, db.c)."""
    for area_state in area_states:
        area_state["age"] += 1
        if area_state["age"] >= _AREA_AGE_MIN and area_state["age"] >= _AREA_AGE_RESET:
            reset_mobs(mob_instances, room_state, area_state["resets"])
            if area_state["tag"] == "mud_school":
                area_state["age"] = 13  # resets every 2 ticks (cf. db.c:1330: age = 15-2)
            else:
                area_state["age"] = randint(0, 3)
                # School area is intentionally silent (cf. db.c:1335 else-if excludes it).
                if ROOMS[player["room"]].get("area") == area_state["tag"]:
                    tr.print(_RESET_MSGS[randint(0, len(_RESET_MSGS) - 1)])


def _wrap_plain(text, width):
    """Plain-text word-wrap (no colour codes); fast path in _wrapped_print."""
    lines = []
    while len(text) > width:
        i = text.rfind(' ', 0, width)
        if i <= 0:
            i = width - 1
        lines.append(text[:i])
        text = text[i:].lstrip(' ')
    lines.append(text)
    return lines


# ── Main classes ──────────────────────────────────────────────────────────────


class Game:
    """Holds game state and drives the main loop."""

    def __init__(self):
        self.tr = tml(dark_mode=DARK_MODE, tab_size=TAB_SIZE, bg_color=BG_COLOR, font=FONT)
        self._font_w = grobw(FONT_GROB)
        self._font_h = grobh(FONT_GROB)
        dimgrob(COLOR_GROB, self._font_w, self._font_h, 0)
        strblit2(COLOR_GROB, 0, 0, self._font_w, self._font_h, FONT_GROB, 0, 0, self._font_w, self._font_h)
        _w_x = (ord('W') - 32) * self.tr.char_width + self.tr.char_width // 2
        self._font_fg = getpix(FONT_GROB, _w_x, self.tr.char_height // 2)
        _fg = self._font_fg
        # Precomputed fg pixel coords — eliminates all getpix calls in set_color.
        self._fg_rows = [
            [x for x in range(self._font_w) if getpix(FONT_GROB, x, y) == _fg]
            for y in range(self._font_h)
        ]
        self._current_fg = None  # colour cache; None = default (white)
        _orig_print = self.tr.print
        self._orig_print = _orig_print
        _cols = TERMINAL_COLS
        # Closure-captured for faster lookup than globals in the hot print path.
        _CC = COLOR_CODE
        _ANSI = ANSI_COLORS
        _RST = _RESET_CODES
        _pxy = self.tr.print_xy
        _pch = self.tr._put_char
        def _wrapped_print(*args, sep=' ', end='\n'):
            text = sep.join(str(a) for a in args)
            i = 0
            while i + 1 < len(text) and text[i] == _CC:
                i += 2
            if i < len(text):
                # Always capitalise first letter of output
                text = text[:i] + text[i].upper() + text[i + 1:]
            if _CC not in text:
                # Fast path: skip color_wrap and all colour-code scanning.
                # Reset lazily here — a previous colored print may have left _current_fg set.
                if self._current_fg is not None:
                    self.reset_color()
                lines = _wrap_plain(text, _cols)
                n = len(lines)
                for idx, line in enumerate(lines):
                    _orig_print(line, end='')
                    auto_wrapped = line and self.tr.cursor_x == 0
                    if not auto_wrapped:
                        _orig_print('', end=end if idx == n - 1 else '\n')
                return
            # Colour-first rendering: inline split+group in one pass, then render
            # one set_color/reset_color per distinct colour.
            # Fast check skips wrap scan when visible length clearly fits.
            if len(text) - 2 * text.count(_CC) <= _cols and '{{' not in text:
                pieces = (text,)
            else:
                pieces = color_wrap_full(text, _cols)
            n = len(pieces)
            for idx, piece in enumerate(pieces):
                # Parse and group in one pass via C-level split.
                # parts[0] = text before first code; each subsequent part =
                # code_char + text (or empty for '{{' escape).
                x = 0
                current = None
                colour_order = []
                groups = {}
                parts = piece.split(_CC)
                seg = parts[0]
                if seg:
                    colour_order.append(None)
                    groups[None] = [(0, seg)]
                    x = len(seg)
                skip = False
                for part in parts[1:]:
                    if not part:
                        # '{{' escape: literal '{'.
                        if current not in groups:
                            colour_order.append(current)
                            groups[current] = []
                        groups[current].append((x, _CC))
                        x += 1
                        skip = True
                        continue
                    if skip:
                        skip = False
                        seg = part
                    else:
                        code = part[0]
                        seg = part[1:]
                        if code in _ANSI:
                            current = _ANSI[code]
                        elif code in _RST:
                            current = None
                        else:
                            seg = _CC + part
                    if seg:
                        if current not in groups:
                            colour_order.append(current)
                            groups[current] = []
                        groups[current].append((x, seg))
                        x += len(seg)
                row = self.tr.cursor_y
                for colour in colour_order:
                    if colour is None:
                        self.reset_color()
                    else:
                        self.set_color(colour)
                    for x_pos, seg in groups[colour]:
                        _pxy(x_pos, row, seg)
                is_last = idx == n - 1
                if not is_last:
                    _pch('\n')
                elif end:
                    for c in end:
                        _pch(c)
        self.tr.print = _wrapped_print
        _orig_set_status = self.tr.set_status
        def _wrapped_set_status(text):
            if self._current_fg is not None:
                self.reset_color()
            _orig_set_status(text)
        self.tr.set_status = _wrapped_set_status
        self.input_buf = ""
        self.player = None
        self.room_state = None
        self.mob_instances = None
        self._area_states = [{"tag": d["tag"], "age": 0, "resets": d["resets"]} for d in AREA_DEFS]

    def set_color(self, color):
        """Recolour the font grob for subsequent glyph rendering.

        Cache hit (same color): immediate return, ~0 ms.
        Cache miss: pixon-paints the ~1037 precomputed fg pixels (~3.6 ms vs
        ~26 ms full-scan — ~7x speedup).  No strblit2 restore needed: bg pixels
        are never touched by colour operations, so painting all fg pixels is
        sufficient for any color→color transition.  Local _po capture shaves a
        further ~2% vs global pixon lookup.
        """
        if color == self._current_fg:
            return
        self._current_fg = color
        _po = pixon
        for y, xs in enumerate(self._fg_rows):
            for x in xs:
                _po(FONT_GROB, x, y, color)

    def reset_color(self):
        """Restore font grob to default foreground.  No-op when already at default."""
        if self._current_fg is None:
            return
        self._current_fg = None
        strblit2(FONT_GROB, 0, 0, self._font_w, self._font_h, COLOR_GROB, 0, 0, self._font_w, self._font_h)

    def new_game(self, name="Hero"):
        self.player = create_char()
        self.player["name"] = name
        self.player["_logon_ms"] = int(ppleval("Ticks"))
        self.room_state, self.mob_instances = reset_area()
        self._area_states = [{"tag": d["tag"], "age": 0, "resets": d["resets"]} for d in AREA_DEFS]

    def load_game(self):
        self.player = create_char()
        self.room_state, self.mob_instances = reset_area()
        self._area_states = [{"tag": d["tag"], "age": 0, "resets": d["resets"]} for d in AREA_DEFS]
        result = _load_char(self.player, self.room_state, self.mob_instances,
                            self._area_states, _MACRO_SUBST)
        self.player["_logon_ms"] = int(ppleval("Ticks"))
        return result

    def save_game(self):
        now = int(ppleval("Ticks"))
        elapsed = (now - self.player.get("_logon_ms", now)) // 1000
        self.player["played"] = self.player.get("played", 0) + elapsed
        self.player["_logon_ms"] = now
        if not _save_char(self.player, self.room_state, self.mob_instances,
                          self._area_states, _MACRO_SUBST):
            self.tr.print("Save failed.")
        else:
            self.tr.print("Saved.")

    def show_greeting(self):
        tr = self.tr
        tr.clear()

        mem_part = "{{G(Mem. free: {})".format(free_mem())
        pad = 64 - 23 - len(mem_part) - 1
        _first = '{C 8888888b.          d8b' + ' ' * pad + mem_part + '{x'
        tr.print(_first)
        tr.print('{C 888   Y88b         Y8P                                       {x')
        tr.print('{C 888    888                                                   {x')
        tr.print('{C 888   d88P 888d888 888 88888b.d88b.   .d88b.                 {x')
        tr.print('{C 8888888P"  888P"   888 888 "888 "88b d8P  Y8b                {x')
        tr.print('{C 888        888     888 888  888  888 88888888                {x')
        tr.print('{C 888        888     888 888  888  888 Y8b.                    {x')
        tr.print('{C 888        888     888 888  888  888  "Y8888                 {x')
        tr.print('{C                             .d8888b.  888     888 8888888b.  {x')
        tr.print('{C                            d88P  Y88b 888     888 888  "Y88b {x')
        tr.print('{C                            Y88b.      888     888 888    888 {x')
        tr.print('{C                             "Y888b.   888     888 888    888 {x')
        tr.print('{C                                "Y88b. 888     888 888    888 {x')
        tr.print('{C                                  "888 888     888 888    888 {x')
        tr.print('{C                            Y88b  d88P Y88b. .d88P 888  .d88P {x')
        tr.print('{C                             "Y8888P"   "Y88888P"  8888888P"  {x')
        tr.print("{c      Original DikuMUD by Hans Staerfeldt, Katja Nyboe,       {x")
        tr.print("{c      Tom Madsen, Michael Seifert, and Sebastian Hammer       {x")
        tr.print("{c      Based on MERC 2.1 code by Hatchet, Furey, and Kahn      {x")
        tr.print("{c      ROM 2.4 copyright (c) 1993-1998 Russ Taylor.            {x")
        tr.print("{c      1stMud Server copyright (c) 2001-2004, Markanth.        {x")
        tr.input(  "                    [Press Enter to start]                    "  )
        
        tr.print()


        
        # tr.print("Memory free: {G" + mem + "{x")

    def game_loop(self):
        tr = self.tr
        player = self.player
        room_state = self.room_state
        mob_instances = self.mob_instances
        area_states = self._area_states

        pulse      = 0
        tick_count = 0
        now        = int(ppleval("Ticks"))
        next_pulse = now + MS_PER_PULSE

        _resync_keyboard(tr)
        show_prompt(tr, player, self.input_buf)
        do_look(tr, player, [], room_state, mob_instances)



        while True:
            result = _poll_char(tr, _KEY_COMMANDS)
            if result is not None:
                char, auto_submit = result
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
                elif auto_submit is True:  # [PRIMESUD] hardware key — immediate submit
                    if interpret(char, tr, player, room_state, mob_instances) == "quit":
                        break
                    show_prompt(tr, player, self.input_buf)
                elif auto_submit is False:  # [PRIMESUD] hardware key — load into buffer
                    self.input_buf = char
                    show_prompt(tr, player, self.input_buf)
                elif char == _SB_UP:  # [PRIMESUD] enter scrollback
                    if tr._hist_count > 0:
                        tr._scrollback()
                        _resync_keyboard(tr)
                elif char == _SB_DN:  # [PRIMESUD] scroll-down key outside scrollback — ignore
                    pass
                elif char is not None and char not in ("\L", "\R", "\SR"):
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
                    if violence_update(tr, player, mob_instances, room_state):
                        # [PRIMESUD] Handle auto respawn on death
                        tr.print("You have been KILLED!!")
                        tr.print("Your lifeforce ebbs away...")
                        ppleval("WAIT({})".format(DEATH_MSG_DELAY))
                        tr.print("A distant warmth draws you back.")
                        ppleval("WAIT({})".format(DEATH_MSG_DELAY))
                        player["room"] = R_STARTING_ROOM
                        player["hp"]   = 1
                        player["mp"]   = 1
                        player["wait"] = 0
                        player["daze"] = 0
                        tr.print("You come to your senses. Alive, but barely.")
                        tr.print("")
                        do_look(tr, player, [], room_state, mob_instances)
                    show_prompt(tr, player, self.input_buf)

                if pulse % PULSE_TICK == 0:
                    tick_update(tr, player, ROOMS[player["room"]])
                    show_prompt(tr, player, self.input_buf)
                    tick_count += 1
                    if tick_count >= AUTOSAVE_TICKS:
                        self.save_game()
                        tick_count = 0

                if pulse % PULSE_MOBILE == 0:
                    mobile_update(tr, player, mob_instances, room_state)

                if pulse % PULSE_AREA == 0:
                    area_update(tr, player, area_states, room_state, mob_instances)

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

            game.show_greeting()

            if not game.load_game():
                game.tr.print("No save found. Starting new game.")
                game.tr.print("")
                game.new_game()

            try:
                game.game_loop()
            finally:
                # ppleval('HVars("DBGSAVE_ENTER"):="1"')  # [PRIMESUD] debug: did finally run?
                game.save_game()
                # ppleval('HVars("DBGSAVE_DONE"):="2"')   # [PRIMESUD] debug: did save_game return?


PrimeSud().run()
