"""PrimeSUD extensions for text input history and scrollback."""

from hpprime import dimgrob, eval as ppleval, keyboard, mouse, strblit2
from tml import tml

# Int sentinels -- not chars, so no \x escape issues on Prime hardware
_SB_UP = 10   # shift+- : enter scrollback / scroll up further
_SB_DN = 11   # shift++ : scroll down (within scrollback)

_HIST_UP = 12   # symb key (index 1) -- recall older command
_HIST_DN = 13   # help key (index 3) -- recall newer command

_FN_SIN   = 14  # sin key -- index 21, two rows above numpad
_FN_COS   = 15  # cos key -- index 22
_FN_TAN   = 16  # tan key -- index 23
_FN_LN    = 17  # ln  key -- index 24
_FN_LOG   = 18  # log key -- index 25
_FN_X2    = 19  # x2 key -- index 26, row above numpad
_FN_PM    = 20  # +/- key -- index 27
_FN_PAREN = 21  # ()  key -- index 28
_FN_COMMA = 22  # ,   key -- index 29

_KEY_QUEUE_SIZE = 16


def _advance_fling(depth, accum_px, velocity, dt_ms, step_px, step_rows,
                   hist_count, min_velocity, decay_num, decay_den):
    """Advance fling state by dt_ms using integer row steps. [PRIMESUD]"""
    if velocity == 0 or dt_ms <= 0:
        return depth, accum_px, velocity, False

    accum_px += velocity * dt_ms // 1000
    moved = False
    while accum_px >= step_px:
        new_depth = min(depth + step_rows, hist_count)
        if new_depth == depth:
            accum_px = 0
            break
        depth = new_depth
        accum_px -= step_px
        moved = True
    while accum_px <= -step_px:
        new_depth = max(depth - step_rows, 0)
        if new_depth == depth:
            accum_px = 0
            break
        depth = new_depth
        accum_px += step_px
        moved = True

    velocity = velocity * decay_num // decay_den
    if -min_velocity < velocity < min_velocity:
        velocity = 0
    if velocity == 0 or (depth == 0 and accum_px < 0) or (depth == hist_count and accum_px > 0):
        accum_px = 0
    return depth, accum_px, velocity, moved


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
                 fling_frame_ms=16, fling_min_velocity=120,
                 fling_decay_num=7, fling_decay_den=8, fling_smooth_num=3,
                 hist_grob=7, save_grob=6, **kwargs):
        tml.__init__(self, **kwargs)
        # [PRIMESUD] Rebuild key_map: G2 Prime's MicroPython corrupts
        # inherited dicts from super()/tml.__init__() -- missing keys.
        self.key_map = {
            4: ['\\e','\\e','\\e','\\e'],
            7: ['\\L','\\L','\\L','\\L'],
            8: ['\\R','\\R','\\R','\\R'],
            14: [None,'a',None,'A'],
            15: [None,'b',None,'B'],
            16: [None,'c',None,'C'],
            17: [None,'d',None,'D'],
            18: [None,'e',None,'E'],
            19: ['\b','\b','\b','\b'],
            20: ['^','f',None,'F'],
            21: [_FN_SIN,'g',None,'G'],
            22: [_FN_COS,'h',None,'H'],
            23: [_FN_TAN,'i',None,'I'],
            24: [_FN_LN,'j',None,'J'],
            25: [_FN_LOG,'k',None,'K'],
            26: [_FN_X2,'l',None,'L'],
            27: [_FN_PM,'m','|','M'],
            28: [_FN_PAREN,'n',"'",'N'],
            29: [_FN_COMMA,'o',None,'O'],
            30: ['\n','\n','\n','\n'],
            31: [None,'p',None,'P'],
            32: ['7','q','&','Q'],
            33: ['8','r','{}','R'],
            34: ['9','s','!','S'],
            35: ['/','t','%','T'],
            37: ['4','u','$','U'],
            38: ['5','v','[]','V'],
            39: ['6','w','^','W'],
            40: ['*','x','','X'],
            42: ['1','y','~','Y'],
            43: ['2','z','@','Z'],
            44: ['3','#','?','#'],
            45: ['-',':',_SB_UP,':'],
            47: ['0','"','`','"'],
            48: ['.','.','=','.'],
            49: [' ',' ','_','_'],
            50: ['+',';',_SB_DN,'|']
        }
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
        self._fling_frame_ms    = fling_frame_ms
        self._fling_min_velocity = fling_min_velocity
        self._fling_decay_num   = fling_decay_num
        self._fling_decay_den   = fling_decay_den
        self._fling_smooth_num  = fling_smooth_num
        self._touch_start_y     = None
        self._touch_last_y      = 0
        self._touch_release_seen = True
        self._input_replay      = ''  # pending chars fed to read_key by input(default=)
        self._key_queue         = [None] * _KEY_QUEUE_SIZE
        self._key_queue_head    = 0
        self._key_queue_tail    = 0
        self._key_queue_count   = 0
        self._key_queue_drops   = 0  # debug counter; full queue drops newest event
        self._drain_polls       = 0  # pending GETKEY drains (see _pump_keyboard)
        self._last_pump_ticks   = 0  # Ticks at last pump; long gap = computation ran
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
    # Override: lazy scroll -- defer scrolling past the bottom row until
    # the next character is actually drawn, so output ending in '\n' on
    # the last row does not waste the bottom row of the screen.
    # ------------------------------------------------------------------

    def _end_of_screen_check(self):
        # [PRIMESUD] no-op: pending scroll resolved in _put_char /
        # terminal.wrapped_print just before the next draw.
        pass

    def _put_char(self, char):
        if char != '\n':
            while self.cursor_y >= self.rows:
                self._scroll_up()
        super()._put_char(char)

    # ------------------------------------------------------------------
    # Override: intercept shift+- sentinel in the blocking read path
    # ------------------------------------------------------------------

    def input(self, prompt=None, length=0, alpha=True, shift=False, new_line=True, default=''):
        """Blocking input with optional pre-filled, editable default text.

        [PRIMESUD] default chars are replayed through read_key, so tml.input
        builds and echoes them exactly like typed input (backspace, Esc-clear
        and arrows all work on them); tml.py itself stays untouched.
        """
        self._input_replay = default
        try:
            if prompt:
                self.print(prompt, end='')
                while self.cursor_y >= self.rows:
                    self._scroll_up()
                prompt = None
            return tml.input(self, prompt, length, alpha, shift, new_line)
        finally:
            self._input_replay = ''

    def read_key(self, code=False):
        if self._input_replay and not code:
            char = self._input_replay[0]
            self._input_replay = self._input_replay[1:]
            return char
        if code:
            # Raw key-index path -- unused in PrimeSUD; base implementation.
            return super().read_key(code=True)

        # [PRIMESUD] Blocking read built on the same GETKEY pump as
        # poll_char, replacing tml.read_key's keyboard()-edge + get_key()
        # pair, whose firmware race could swallow keystrokes (see the
        # _pump_keyboard note).
        while True:
            self._pump_keyboard()
            event = self._dequeue_key()
            if event is None:
                ppleval("WAIT(0.005)")
                continue
            char = event[0]
            if char == _SB_UP and self._hist_count > 0:
                result = self._scrollback()
                # None  -> depth reached 0 (auto-exit); loop for next key
                # other -> key forwarded from scrollback exit (int
                #          sentinels dropped, same as below)
                if result is not None and not isinstance(result, int):
                    return result
                continue
            if isinstance(char, int):
                # Fn-key/history/scrollback sentinels are game-loop only;
                # tml.input cannot consume ints -- drop in blocking reads.
                continue
            return char

    # ------------------------------------------------------------------
    # Non-blocking poll -- replaces the standalone _poll_char function
    # ------------------------------------------------------------------

    def _queue_key(self, event):
        """Append translated key event to small fixed queue. [PRIMESUD]"""
        if event is None:
            return
        if self._key_queue_count >= _KEY_QUEUE_SIZE:
            self._key_queue_drops += 1
            return
        self._key_queue[self._key_queue_tail] = event
        self._key_queue_tail = (self._key_queue_tail + 1) % _KEY_QUEUE_SIZE
        self._key_queue_count += 1

    def _dequeue_key(self):
        """Pop next translated key event, or None. [PRIMESUD]"""
        if self._key_queue_count <= 0:
            return None
        event = self._key_queue[self._key_queue_head]
        self._key_queue[self._key_queue_head] = None
        self._key_queue_head = (self._key_queue_head + 1) % _KEY_QUEUE_SIZE
        self._key_queue_count -= 1
        return event

    def _touch_point(self):
        """Current touch (x, y), or None when lifted. [PRIMESUD]

        Filters the firmware latch artifact: a GETKEY call landing on a
        touch-release leaves mouse() reporting (2147483647, 0) as a
        "down" pointer for over a second (probed 2026-07-07,
        debug/touch_probe.py; see docs/BUILTINS.md Touch input).
        """
        pt = mouse()[0]
        if pt and 0 <= pt[0] < 1000:
            return pt
        return None

    def _clear_key_queue(self):
        """Discard queued key events after keyboard resync. [PRIMESUD]"""
        for i in range(_KEY_QUEUE_SIZE):
            self._key_queue[i] = None  # drop refs -- heap-constrained device
        self._key_queue_head = 0
        self._key_queue_tail = 0
        self._key_queue_count = 0

    def has_queued_keys(self):
        """Return True if translated key events are waiting. [PRIMESUD]"""
        return self._key_queue_count > 0

    def _translate_key_press(self, bit, key_commands=None):
        """Update modifier state or return translated press event. [PRIMESUD]"""
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
            return None
        if bit == 41:  # Shift
            self.shift_hold = True
            if self.is_shift:
                self.is_shift = self.shift_lock if not self.is_shift else False
            else:
                self.is_shift = True
            self._refresh_indicators()
            return None
        if bit == 1:   # Symb -- command history up
            return (_HIST_UP, None)
        if bit == 3:   # Help -- command history down
            return (_HIST_DN, None)
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
        # [PRIMESUD] _SB_UP/_SB_DN pass through the queue; scrollback is
        # triggered at the dequeue site in poll_char, never mid-pump --
        # _scrollback() ends in resync_keyboard(), which clears the queue,
        # so running it here would let the pump loop re-queue stale events
        # from the pre-scrollback keyboard snapshot afterwards.
        return (char, None)

    # [PRIMESUD] Press events come from the firmware's key-event queue via
    # PPL GETKEY, not from keyboard() bitmask edges. Probed on-device
    # 2026-07-06 (debug/keydrop_probe.py): the firmware buffers presses in
    # a 4-deep FIFO that survives long pure-Python computations (bitmask
    # edges do not -- press+release inside a computation is invisible to
    # keyboard()), GETKEY codes equal keyboard() bit indices, events are
    # chronological (modifier combos like Shift+key arrive in order), no
    # hold auto-repeat, and cas.get_key() reads the same queue. The
    # bitmask is used only to reconcile modifier *hold* state: hold flags
    # must track the live key state, since the release of a modifier
    # tapped inside a computation never appears as an edge and would
    # otherwise stick. NOTE: base tml.read_key() still pairs keyboard()
    # edges with cas.get_key(), which lags a poll behind the bitmask and
    # can swallow a keystroke; PrimeSUD never routes through it (see
    # read_key above) -- watch for that race if it is ever reinstated.
    #
    # GETKEY cannot simply run every pump: a GETKEY landing on a
    # touch-release latches mouse() into a garbage (2147483647, 0) "down"
    # state for >1s, during which real touches go unseen (probed
    # 2026-07-07, debug/touch_probe.py). So the drain is gated:
    #   - bitmask activity (any key down, or an edge) drains now and for
    #     the next few pumps -- FIFO population lags the bitmask by a
    #     firmware poll, so a single edge-poll drain can race and miss;
    #   - a long gap since the previous pump means a computation just ran
    #     and may have buried a press+release in the FIFO with no visible
    #     edge; drain once, unless a touch is live (the latch above).
    # At the regular ~10ms poll cadence a press+release can never hide
    # between two pumps, so the bitmask gate loses nothing there. A key
    # pressed mid-touch still drains (bitmask gate) and can latch -- rare
    # and self-recovering; accepted.
    def _pump_keyboard(self, key_commands=None):
        """Drain firmware key queue into the local queue; sync modifier holds. [PRIMESUD]"""
        cur = keyboard()
        now = int(ppleval("Ticks"))
        if cur or cur != self.last_keyboard_state:
            self._drain_polls = 3
        elif self._drain_polls == 0 and now - self._last_pump_ticks > 50:
            if self._touch_point() is None:
                self._drain_polls = 1
        self.last_keyboard_state = cur
        self._last_pump_ticks = now
        shift_held = bool(cur & (1 << 41))
        alpha_held = bool(cur & (1 << 36))
        if shift_held != self.shift_hold or alpha_held != self.alpha_hold:
            self.shift_hold = shift_held
            self.alpha_hold = alpha_held
            self._refresh_indicators()
        if self._drain_polls == 0:
            return
        self._drain_polls -= 1
        while True:
            code = int(ppleval("GETKEY"))
            if code < 0:
                return
            self._queue_key(self._translate_key_press(code, key_commands))

    def poll_char(self, key_commands=None):
        """Non-blocking: queue new key presses, return next queued event or None."""
        # -- touch entry into scrollback (game-loop path) --
        if self._hist_size > 0 and self._hist_count > 0 and not self._in_scrollback:
            pt = self._touch_point()
            if pt is not None:
                if self._touch_release_seen:
                    # Finger is currently down
                    if self._touch_start_y is None:
                        self._touch_start_y = pt[1]
                    self._touch_last_y = pt[1]
                    if self._touch_last_y - self._touch_start_y > self._swipe_threshold:
                        self._touch_start_y = None
                        self._touch_release_seen = False
                        _t0 = int(ppleval("Ticks"))
                        forwarded = self._scrollback()
                        self._scrollback_ms += int(ppleval("Ticks")) - _t0
                        self._queue_key((forwarded, None) if forwarded is not None else None)
            else:
                # Finger is currently lifted; sub-threshold lift = tap, no-op.
                self._touch_start_y = None
                self._touch_release_seen = True

        self._pump_keyboard(key_commands)
        event = self._dequeue_key()
        if event is None or self._hist_size == 0 or self._in_scrollback:
            return event
        char = event[0]
        if char == _SB_UP and self._hist_count > 0:
            _t0 = int(ppleval("Ticks"))
            forwarded = self._scrollback()
            self._scrollback_ms += int(ppleval("Ticks")) - _t0
            return (forwarded, None) if forwarded is not None else None
        if char == _SB_DN:
            return None
        return event

    def resync_keyboard(self):
        """Reset keyboard state after a blocking input section."""
        self.last_keyboard_state = keyboard()
        # [PRIMESUD] flush the firmware key queue (4-deep) alongside the
        # local one; bounded in case a firmware quirk never returns -1.
        # Skipped while a touch is live: GETKEY on a touch-release latches
        # mouse() into a garbage "down" state for >1s (see _pump_keyboard).
        # Stale FIFO keys may then surface at the next drain as phantom
        # presses -- rare (needs typing during a touch-exited scrollback)
        # and preferable to >1s of dead touch input.
        if self._touch_point() is None:
            for _ in range(8):
                if int(ppleval("GETKEY")) < 0:
                    break
        self._drain_polls = 0  # cancel leftover drain tail; FIFO just flushed
        self.is_alpha = self.is_shift = self.alpha_hold = self.shift_hold = self.symb_hold = False
        self._clear_key_queue()
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
        t_mode       = "idle"
        t_last_y     = 0
        t_base_y     = 0
        t_last_ticks = 0
        t_velocity   = 0
        t_accum_px   = 0
        t_fling_ticks = 0
        t_last_kb    = -1
        step_px      = self._touch_scroll_step * self.char_height

        self._in_scrollback = True
        try:
            while True:
                # -- keyboard (pump + dequeue; poll_char's touch entry is
                # moot here since _in_scrollback prevents re-entry) --
                # [PRIMESUD] _pump_keyboard costs >=1 ppleval("GETKEY")
                # per call; at this loop's cadence that throttles mouse()
                # sampling enough to gut drag/fling velocity. Only pump
                # when the (cheap) bitmask shows a key down or an edge --
                # this loop polls fast, so taps land on the bitmask; the
                # firmware FIFO drain still happens on that hit, and
                # resync_keyboard() flushes leftovers at exit.
                kb = keyboard()
                if kb or kb != t_last_kb:
                    self._pump_keyboard()
                t_last_kb = kb
                kc = self._dequeue_key()
                if kc is not None:
                    char, _ = kc
                    if char is None or char == '\\SR':
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
                pt = self._touch_point()
                touching = pt is not None
                # Ticks is only needed while a gesture is live; skip the ppleval when idle.
                now = int(ppleval("Ticks")) if touching or t_mode != "idle" else 0
                if touching:
                    # New touch cancels any in-flight fling and re-arms drag from here.
                    if t_mode != "drag":
                        t_mode = "drag"
                        t_base_y = pt[1]
                        t_last_y = pt[1]
                        t_last_ticks = now
                        t_velocity = 0
                        t_accum_px = 0
                    else:
                        # Velocity EMA samples position/time as a pair; t_last_y advances
                        # only alongside t_last_ticks so dy and dt cover the same span.
                        # [PRIMESUD] Gate sampling to fling_frame_ms: the touch
                        # controller reports new positions only every ~16ms
                        # (60Hz, probed 2026-07-07, debug/touch_probe.py), but
                        # this loop can iterate ~1ms. Sampling per iteration
                        # decays the EMA to nothing between touch frames
                        # (killing fling) and turns 1-3px jitter over 1ms into
                        # +/-1000s px/s spikes (spurious reverse fling ->
                        # instant depth-0 exit). Frame-gating makes velocity
                        # independent of loop cadence.
                        if now - t_last_ticks >= self._fling_frame_ms:
                            inst_v = (pt[1] - t_last_y) * 1000 // (now - t_last_ticks)
                            t_velocity = ((t_velocity * self._fling_smooth_num + inst_v)
                                          // (self._fling_smooth_num + 1))
                            t_last_ticks = now
                            t_last_y = pt[1]
                        delta = pt[1] - t_base_y
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
                elif t_mode == "drag":
                    if abs(t_velocity) >= self._fling_min_velocity:
                        t_mode = "fling"
                        t_fling_ticks = now
                    else:
                        t_mode = "idle"
                        t_velocity = 0
                        t_accum_px = 0
                elif t_mode == "fling":
                    dt_ms = now - t_fling_ticks
                    if dt_ms >= self._fling_frame_ms:
                        t_fling_ticks = now
                        depth, t_accum_px, t_velocity, moved = _advance_fling(
                            depth, t_accum_px, t_velocity, dt_ms, step_px,
                            self._touch_scroll_step, self._hist_count,
                            self._fling_min_velocity, self._fling_decay_num,
                            self._fling_decay_den)
                        if moved:
                            if depth == 0:
                                break
                            self._render_scrollback(depth)
                        if t_velocity == 0:
                            t_mode = "idle"
                ppleval("WAIT(0.001)")
        finally:
            self._in_scrollback = False
            # [PRIMESUD] Arm re-entry from the live touch state, not a
            # blanket False: a fling exits with the finger already up, and
            # if the next swipe touches down before the game loop gets a
            # finger-up poll (fast swipe chains + game-loop blind windows),
            # a hardcoded False leaves entry disarmed until a deliberate
            # tap-and-release. Finger still down (drag exit) stays False so
            # the same gesture can't immediately re-enter.
            self._touch_release_seen = self._touch_point() is None
            self._touch_start_y = None

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
            # Wraps around ring end -- two blits
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
