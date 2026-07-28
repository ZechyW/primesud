"""Graphical PC terminal using source TML atlas rendering."""

import time

from fling import advance_fling
from hpprime import (
    dimgrob, has_events, mouse, poll_event, pump_events, strblit2,
    wait_event, wait_ms,
)
from tml import tml


_SB_UP = 10
_SB_DN = 11
_HIST_UP = 12
_HIST_DN = 13


class tml_prime(tml):
    """TML renderer with desktop keyboard input and pixel scrollback."""

    def __init__(self, scrollback_size=250, scroll_step=5,
                 touch_scroll_step=3, swipe_threshold=20,
                 fling_frame_ms=16, fling_min_velocity=120,
                 fling_decay_num=7, fling_decay_den=8, fling_smooth_num=3,
                 hist_grob=7, save_grob=6, **kwargs):
        tml.__init__(self, **kwargs)
        self._hist_size = scrollback_size
        self._hist_write = 0
        self._hist_count = 0
        self._hist_grob = hist_grob
        self._save_grob = save_grob
        self._scroll_step = scroll_step
        self._touch_scroll_step = touch_scroll_step
        self._swipe_threshold = swipe_threshold
        self._fling_frame_ms = fling_frame_ms
        self._fling_min_velocity = fling_min_velocity
        self._fling_decay_num = fling_decay_num
        self._fling_decay_den = fling_decay_den
        self._fling_smooth_num = fling_smooth_num
        self._scrollback_ms = 0
        self._in_scrollback = False
        self._touch_start_y = None
        self._touch_last_y = 0
        self._touch_release_seen = True
        if scrollback_size > 0:
            dimgrob(
                hist_grob, self.width, scrollback_size * self.char_height,
                self.back_color,
            )
            dimgrob(save_grob, self.width, self.height, self.back_color)

    def _scroll_up(self):
        if self._hist_size > 0:
            strblit2(
                self._hist_grob, 0, self._hist_write * self.char_height,
                self.width, self.char_height,
                0, 0, 0, self.width, self.char_height,
            )
            self._hist_write = (self._hist_write + 1) % self._hist_size
            if self._hist_count < self._hist_size:
                self._hist_count += 1
        tml._scroll_up(self)

    def _end_of_screen_check(self):
        pass

    def _put_char(self, char):
        if char != "\n":
            while self.cursor_y >= self.rows:
                self._scroll_up()
        tml._put_char(self, char)

    def input(self, prompt=None, length=0, alpha=True, shift=False,
              new_line=True, default=""):
        """Read one editable line using desktop keys."""
        if prompt:
            self.print(prompt, end="")
            while self.cursor_y >= self.rows:
                self._scroll_up()
        start_x = self.cursor_x
        limit = min(length, self.columns - start_x - 1) if length > 0 else (
            self.columns - start_x - 1
        )
        value = list(default[:limit])
        if value:
            self.print_xy(start_x, self.cursor_y, "".join(value))
            self.cursor_x += len(value)

        cursor_on = False
        try:
            self._invert_cursor()
            cursor_on = True
            while True:
                char = self.read_key()
                if char == "\n":
                    break
                if char == "\b":
                    if value:
                        self._invert_cursor()
                        cursor_on = False
                        value.pop()
                        self.cursor_x -= 1
                        self.print_xy(self.cursor_x, self.cursor_y, " ")
                elif char == "\\e":
                    self._invert_cursor()
                    cursor_on = False
                    self.print_xy(start_x, self.cursor_y, " " * len(value))
                    self.cursor_x = start_x
                    value = []
                elif isinstance(char, str) and len(char) == 1 and len(value) < limit:
                    self._invert_cursor()
                    cursor_on = False
                    value.append(char)
                    self.print_xy(self.cursor_x, self.cursor_y, char)
                    self.cursor_x += 1
                else:
                    continue
                self._invert_cursor()
                cursor_on = True
        finally:
            if cursor_on:
                self._invert_cursor()

        if new_line:
            self._put_char("\n")
        self.alpha_lock = self.is_alpha = False
        self.shift_lock = self.is_shift = False
        self._refresh_indicators()
        return "".join(value)

    def read_key(self, code=False):
        while True:
            char = wait_event()
            if char == "\x03":
                raise KeyboardInterrupt
            if char == _SB_UP and self._hist_count > 0:
                started = time.monotonic()
                char = self._scrollback()
                self._scrollback_ms += int((time.monotonic() - started) * 1000)
                if char is None:
                    continue
            if isinstance(char, int):
                continue
            return char

    def poll_char(self, key_commands=None):
        pump_events()
        if self._hist_size > 0 and self._hist_count > 0 and not self._in_scrollback:
            point = self._touch_point()
            if point is not None:
                if self._touch_release_seen:
                    if self._touch_start_y is None:
                        self._touch_start_y = point[1]
                    self._touch_last_y = point[1]
                    if self._touch_last_y - self._touch_start_y > self._swipe_threshold:
                        self._touch_start_y = None
                        self._touch_release_seen = False
                        started = time.monotonic()
                        char = self._scrollback()
                        self._scrollback_ms += int(
                            (time.monotonic() - started) * 1000
                        )
                        return (char, None) if char is not None else None
            else:
                self._touch_start_y = None
                self._touch_release_seen = True

        char = poll_event()
        if char is None:
            return None
        if char == "\x03":
            raise KeyboardInterrupt
        if char == _SB_UP and self._hist_count > 0:
            started = time.monotonic()
            char = self._scrollback()
            self._scrollback_ms += int((time.monotonic() - started) * 1000)
            return (char, None) if char is not None else None
        if char == _SB_DN:
            return None
        return (char, None)

    def has_queued_keys(self):
        return has_events()

    def resync_keyboard(self):
        self.alpha_lock = self.is_alpha = False
        self.shift_lock = self.is_shift = False
        self.alpha_hold = self.shift_hold = self.symb_hold = False
        self._refresh_indicators()

    def _touch_point(self):
        point = mouse()[0]
        if point and 0 <= point[0] < 1000:
            return point
        return None

    def _scrollback(self):
        strblit2(
            self._save_grob, 0, 0, self.width, self.height,
            0, 0, 0, self.width, self.height,
        )
        depth = min(self._scroll_step, self._hist_count)
        self._render_scrollback(depth)
        result = None
        touch_mode = "idle"
        touch_last_y = 0
        touch_base_y = 0
        touch_last_ticks = 0
        touch_velocity = 0
        touch_accum_px = 0
        fling_ticks = 0
        step_px = self._touch_scroll_step * self.char_height
        self._in_scrollback = True
        try:
            while True:
                char = poll_event()
                if char == "\x03":
                    raise KeyboardInterrupt
                if char == _SB_UP or char == "-":
                    depth = min(depth + self._scroll_step, self._hist_count)
                    self._render_scrollback(depth)
                elif char == _SB_DN or char == "+":
                    depth = max(depth - self._scroll_step, 0)
                    if depth == 0:
                        break
                    self._render_scrollback(depth)
                elif char is not None:
                    result = char
                    break

                point = self._touch_point()
                touching = point is not None
                now = (
                    int(time.monotonic() * 1000)
                    if touching or touch_mode != "idle" else 0
                )
                if touching:
                    if touch_mode != "drag":
                        touch_mode = "drag"
                        touch_base_y = point[1]
                        touch_last_y = point[1]
                        touch_last_ticks = now
                        touch_velocity = 0
                        touch_accum_px = 0
                    else:
                        if now - touch_last_ticks >= self._fling_frame_ms:
                            instant_velocity = (
                                (point[1] - touch_last_y) * 1000
                                // (now - touch_last_ticks)
                            )
                            touch_velocity = (
                                touch_velocity * self._fling_smooth_num
                                + instant_velocity
                            ) // (self._fling_smooth_num + 1)
                            touch_last_ticks = now
                            touch_last_y = point[1]
                        delta = point[1] - touch_base_y
                        if delta > step_px:
                            depth = min(
                                depth + self._touch_scroll_step,
                                self._hist_count,
                            )
                            self._render_scrollback(depth)
                            touch_base_y += step_px
                        elif delta < -step_px:
                            depth = max(depth - self._touch_scroll_step, 0)
                            touch_base_y -= step_px
                            if depth == 0:
                                break
                            self._render_scrollback(depth)
                elif touch_mode == "drag":
                    if abs(touch_velocity) >= self._fling_min_velocity:
                        touch_mode = "fling"
                        fling_ticks = now
                    else:
                        touch_mode = "idle"
                        touch_velocity = 0
                        touch_accum_px = 0
                elif touch_mode == "fling":
                    elapsed = now - fling_ticks
                    if elapsed >= self._fling_frame_ms:
                        fling_ticks = now
                        (
                            depth, touch_accum_px, touch_velocity, moved,
                        ) = advance_fling(
                            depth, touch_accum_px, touch_velocity, elapsed,
                            step_px, self._touch_scroll_step,
                            self._hist_count, self._fling_min_velocity,
                            self._fling_decay_num, self._fling_decay_den,
                        )
                        if moved:
                            if depth == 0:
                                break
                            self._render_scrollback(depth)
                        if touch_velocity == 0:
                            touch_mode = "idle"
                wait_ms(1)
        finally:
            self._in_scrollback = False
            self._touch_release_seen = self._touch_point() is None
            self._touch_start_y = None
            strblit2(
                0, 0, 0, self.width, self.height,
                self._save_grob, 0, 0, self.width, self.height,
            )
        return result

    def _render_scrollback(self, depth):
        char_height = self.char_height
        slot_start = (self._hist_write - depth) % self._hist_size
        display_rows = min(depth, self.rows)

        if slot_start + display_rows <= self._hist_size:
            strblit2(
                0, 0, 0, self.width, display_rows * char_height,
                self._hist_grob, 0, slot_start * char_height,
                self.width, display_rows * char_height,
            )
        else:
            tail = self._hist_size - slot_start
            strblit2(
                0, 0, 0, self.width, tail * char_height,
                self._hist_grob, 0, slot_start * char_height,
                self.width, tail * char_height,
            )
            head = display_rows - tail
            strblit2(
                0, 0, tail * char_height, self.width, head * char_height,
                self._hist_grob, 0, 0, self.width, head * char_height,
            )

        if display_rows < self.rows:
            remaining = self.rows - display_rows
            strblit2(
                0, 0, display_rows * char_height,
                self.width, remaining * char_height,
                self._save_grob, 0, 0,
                self.width, remaining * char_height,
            )
