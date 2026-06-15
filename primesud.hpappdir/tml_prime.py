from hpprime import dimgrob, eval as ppleval, keyboard, mouse, strblit2
from tml import tml

_SB_UP = '\x10'   # shift+- : enter scrollback / scroll up further
_SB_DN = '\x11'   # shift++ : scroll down (within scrollback)

_HIST_UP = '\x16'   # symb key (index 1) — recall older command
_HIST_DN = '\x17'   # help key (index 3) — recall newer command

_FN_X2    = '\x12'  # x² key — index 26, row above numpad
_FN_PM    = '\x13'  # +/- key — index 27
_FN_PAREN = '\x14'  # ()  key — index 28
_FN_COMMA = '\x15'  # ,   key — index 29


class tml_prime(tml):
    """tml subclass with HP Prime-specific enhancements: scrollback history and
    non-blocking poll_char / resync_keyboard.

    Extra constructor args (scrollback):
        scrollback_size: rows to keep (0 = disabled, default 250)
        scroll_step:     rows scrolled per keypress (default 5)
        hist_grob:       GROB number for history ring (default 7)
        save_grob:       GROB number for screen save (default 6)

    Key bindings (when history exists):
        Shift+-  enter scrollback / scroll up further
        Shift++  scroll down; reaching depth 0 auto-exits
        any other key  exits scrollback and is forwarded to the caller
    """

    def __init__(self, scrollback_size=250, scroll_step=5,
                 touch_scroll_step=3, swipe_threshold=20,
                 hist_grob=7, save_grob=6, **kwargs):
        super().__init__(**kwargs)
        self.key_map[26][0] = _FN_X2
        self.key_map[27][0] = _FN_PM
        self.key_map[28][0] = _FN_PAREN
        self.key_map[29][0] = _FN_COMMA
        self.key_map[45][2] = _SB_UP
        self.key_map[50][2] = _SB_DN
        self._hist_size = scrollback_size
        self._hist_write = 0
        self._hist_count = 0
        self._hist_grob = hist_grob
        self._save_grob = save_grob
        self._scroll_step = scroll_step
        self._scrollback_ms = 0  # [PRIMESUD] time spent in scrollback; consumed by game_loop
        self._in_scrollback     = False
        self._touch_scroll_step = touch_scroll_step
        self._swipe_threshold   = swipe_threshold
        self._touch_start_y     = None
        self._touch_last_y      = 0
        if scrollback_size > 0:
            dimgrob(hist_grob, self.width, scrollback_size * self.char_height, self.back_color)
            dimgrob(save_grob, self.width, self.height, self.back_color)

    # ------------------------------------------------------------------
    # Override: capture the row about to scroll off before shifting G0
    # ------------------------------------------------------------------

    def _scroll_up(self):
        if self._hist_size > 0:
            strblit2(self._hist_grob, 0, self._hist_write * self.char_height,
                     self.width, self.char_height,
                     0, 0, 0, self.width, self.char_height)
            self._hist_write = (self._hist_write + 1) % self._hist_size
            if self._hist_count < self._hist_size:
                self._hist_count += 1
        super()._scroll_up()

    # ------------------------------------------------------------------
    # Override: intercept shift+- sentinel in the blocking read path
    # ------------------------------------------------------------------

    def read_key(self, code=False):
        if code or self._hist_size == 0:
            return super().read_key(code=code)

        while True:
            char = super().read_key(code=False)
            if char == _SB_UP and self._hist_count > 0:
                result = self._scrollback()
                # None  → depth reached 0 (auto-exit); loop for next key
                # other → key forwarded from scrollback exit
                if result is not None:
                    return result
            else:
                return char

    # ------------------------------------------------------------------
    # Non-blocking poll — replaces the standalone _poll_char function
    # ------------------------------------------------------------------

    def poll_char(self, key_commands=None):
        """Non-blocking: return (char, auto_submit) if a new key was pressed, else None."""
        # -- touch entry into scrollback (game-loop path) --
        if self._hist_size > 0 and self._hist_count > 0 and not self._in_scrollback:
            pt = mouse()[0]
            if pt and pt[0] >= 0:
                # Finger is currently down
                if self._touch_start_y is None:
                    self._touch_start_y = pt[1]
                self._touch_last_y = pt[1]
                if self._touch_last_y - self._touch_start_y > self._swipe_threshold:
                    self._touch_start_y = None
                    _t0 = int(ppleval("Ticks"))
                    forwarded = self._scrollback()
                    self._scrollback_ms += int(ppleval("Ticks")) - _t0
                    return (forwarded, None) if forwarded is not None else None
            elif self._touch_start_y is not None:
                # Finger is currently lifted
                self._touch_start_y = None  # sub-threshold lift = tap, no-op

        cur = keyboard()
        changed = cur ^ self.last_keyboard_state
        if not changed:
            return None
        self.last_keyboard_state = cur
        for bit in range(52):
            mask = 1 << bit
            if not (changed & mask):
                continue
            if cur & mask:  # key pressed
                if bit == 36:  # Alpha
                    self.alpha_hold = True
                    if self.alpha_lock:
                        if self.is_shift:
                            self.shift_lock = not self.shift_lock
                        else:
                            self.alpha_lock = self.is_alpha = False
                            self.shift_lock = False
                        self.is_shift = False
                    elif self.is_alpha:
                        if self.is_shift:
                            if self.alpha_lock:
                                self.shift_lock = not self.shift_lock
                            else:
                                self.alpha_lock = True
                            self.is_shift = False
                        else:
                            self.alpha_lock = True
                    else:
                        self.is_alpha = True
                    self._refresh_indicators()
                elif bit == 41:  # Shift
                    self.shift_hold = True
                    if self.is_shift:
                        self.is_shift = self.shift_lock if not self.is_shift else False
                    else:
                        self.is_shift = True
                    self._refresh_indicators()
                elif bit == 1:   # Symb — command history up
                    return (_HIST_UP, None)
                elif bit == 3:   # Help — command history down
                    return (_HIST_DN, None)
                else:
                    if key_commands and bit in key_commands:
                        cmd, auto_submit = key_commands[bit]
                        return (cmd, auto_submit)
                    if self.shift_hold:
                        self.is_shift = True
                    if self.alpha_hold:
                        self.is_alpha = True
                    mod_idx = ((self.is_shift ^ self.shift_lock) << 1) | (self.is_alpha | self.alpha_lock)
                    char = self.key_map.get(bit, [None, None, None, None])[mod_idx]
                    if not self.alpha_lock:
                        self.is_alpha = False
                    if self.is_shift:
                        self.is_shift = False
                    self._refresh_indicators()
                    if self._hist_size > 0 and not self._in_scrollback:
                        if char == _SB_UP and self._hist_count > 0:
                            _t0 = int(ppleval("Ticks"))
                            forwarded = self._scrollback()
                            self._scrollback_ms += int(ppleval("Ticks")) - _t0
                            return (forwarded, None) if forwarded is not None else None
                        if char == _SB_DN:
                            return None
                    return (char, None)
            else:  # key released
                if bit == 36:
                    self.alpha_hold = False
                    self._refresh_indicators()
                elif bit == 41:
                    self.shift_hold = False
                    self._refresh_indicators()
        return None

    def resync_keyboard(self):
        """Reset keyboard state after a blocking input section."""
        self.last_keyboard_state = keyboard()
        self.is_alpha = self.is_shift = self.alpha_hold = self.shift_hold = self.symb_hold = False
        self._refresh_indicators()

    # ------------------------------------------------------------------
    # Scrollback sub-loop
    # ------------------------------------------------------------------

    def _scrollback(self):
        strblit2(self._save_grob, 0, 0, self.width, self.height,
                 0, 0, 0, self.width, self.height)
        depth = min(self._scroll_step, self._hist_count)
        self._render_scrollback(depth)

        result       = None
        t_finger_down = False
        t_last_y     = 0
        t_base_y     = 0
        step_px      = self._touch_scroll_step * self.char_height

        self._in_scrollback = True
        try:
            while True:
                # -- keyboard (non-blocking via poll_char; _in_scrollback prevents re-entry) --
                kc = self.poll_char()
                if kc is not None:
                    char, _ = kc
                    if char is None or char == '\SR':
                        pass
                    elif char == _SB_UP or char == '-':
                        depth = min(depth + self._scroll_step, self._hist_count)
                        self._render_scrollback(depth)
                    elif char == _SB_DN or char == '+':
                        depth = max(depth - self._scroll_step, 0)
                        if depth == 0:
                            break
                        self._render_scrollback(depth)
                    else:
                        result = char
                        break

                # -- touch (repeat scroll while dragging) --
                pt = mouse()[0]
                if pt and pt[0] >= 0:
                    # Finger is down
                    if not t_finger_down:
                        t_finger_down = True
                        t_base_y = pt[1]
                    t_last_y = pt[1]
                    delta = t_last_y - t_base_y
                    if delta > step_px:
                        depth = min(depth + self._touch_scroll_step, self._hist_count)
                        self._render_scrollback(depth)
                        t_base_y += step_px
                    elif delta < -step_px:
                        depth = max(depth - self._touch_scroll_step, 0)
                        t_base_y -= step_px
                        if depth == 0:
                            break
                        self._render_scrollback(depth)
                elif t_finger_down:
                    t_finger_down = False  # finger lifted; direction already handled by repeat scroll
        finally:
            self._in_scrollback = False

        strblit2(0, 0, 0, self.width, self.height,
                 self._save_grob, 0, 0, self.width, self.height)
        self.resync_keyboard()
        return result

    def _render_scrollback(self, depth):
        ch = self.char_height
        slot_start = (self._hist_write - depth) % self._hist_size
        display_rows = min(depth, self.rows)

        if slot_start + display_rows <= self._hist_size:
            strblit2(0, 0, 0, self.width, display_rows * ch,
                     self._hist_grob, 0, slot_start * ch, self.width, display_rows * ch)
        else:
            # Wraps around ring end — two blits
            tail = self._hist_size - slot_start
            strblit2(0, 0, 0, self.width, tail * ch,
                     self._hist_grob, 0, slot_start * ch, self.width, tail * ch)
            head = display_rows - tail
            strblit2(0, 0, tail * ch, self.width, head * ch,
                     self._hist_grob, 0, 0, self.width, head * ch)

        if display_rows < self.rows:
            rem = self.rows - display_rows
            strblit2(0, 0, display_rows * ch, self.width, rem * ch,
                     self._save_grob, 0, 0, self.width, rem * ch)
