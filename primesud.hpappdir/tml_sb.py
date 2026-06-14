from hpprime import dimgrob, strblit2
from tml import tml

# Sentinels injected into the key map for scrollback navigation.
# Shift+- (key 45, index 2) was None;  shift++ (key 50, index 2) was '\\'.
_SB_UP = '\x10'   # shift+- : enter scrollback / scroll up further
_SB_DN = '\x11'   # shift++ : scroll down (within scrollback)

# Public aliases — import these in callers that bypass read_key() (e.g. _poll_char)
SB_UP = _SB_UP
SB_DN = _SB_DN

class tml_sb(tml):
    """tml subclass adding a ring-buffer scrollback history.

    Extra constructor args:
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
                 hist_grob=7, save_grob=6, **kwargs):
        super().__init__(**kwargs)
        # Inject sentinels: key_map lists are mutable, index 2 = shift modifier
        self.key_map[45][2] = _SB_UP
        self.key_map[50][2] = _SB_DN
        self._hist_size = scrollback_size
        self._hist_write = 0
        self._hist_count = 0
        self._hist_grob = hist_grob
        self._save_grob = save_grob
        self._scroll_step = scroll_step
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
    # Override: intercept shift+- sentinel to enter scrollback
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
    # Scrollback sub-loop
    # ------------------------------------------------------------------

    def _scrollback(self):
        strblit2(self._save_grob, 0, 0, self.width, self.height,
                 0, 0, 0, self.width, self.height)
        depth = min(self._scroll_step, self._hist_count)
        self._render_scrollback(depth)

        result = None
        while True:
            char = super().read_key(code=False)
            if char is None or char == '\SR':
                continue
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

        strblit2(0, 0, 0, self.width, self.height,
                 self._save_grob, 0, 0, self.width, self.height)
        return result

    def _render_scrollback(self, depth):
        ch = self.char_height
        slot_start = (self._hist_write - depth) % self._hist_size

        # Region A: top 'depth' rows from history ring
        if slot_start + depth <= self._hist_size:
            strblit2(0, 0, 0, self.width, depth * ch,
                     self._hist_grob, 0, slot_start * ch, self.width, depth * ch)
        else:
            # Wraps around ring end — two blits
            tail = self._hist_size - slot_start
            strblit2(0, 0, 0, self.width, tail * ch,
                     self._hist_grob, 0, slot_start * ch, self.width, tail * ch)
            head = depth - tail
            strblit2(0, 0, tail * ch, self.width, head * ch,
                     self._hist_grob, 0, 0, self.width, head * ch)

        # Region B: bottom (rows - depth) rows from saved screen
        if depth < self.rows:
            rem = self.rows - depth
            strblit2(0, 0, depth * ch, self.width, rem * ch,
                     self._save_grob, 0, 0, self.width, rem * ch)
