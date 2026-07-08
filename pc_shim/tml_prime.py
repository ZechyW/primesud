"""PC terminal replacement for tml_prime -- no-echo input, set_status renders prompt."""
import sys
import os
import threading
import queue

_HIST_UP = 12
_HIST_DN = 13

_q = queue.Queue()


def _start_reader():
    if os.name == 'nt':
        import msvcrt
        def _reader():
            while True:
                c = msvcrt.getwch()
                if c in ('\x00', '\xe0'):
                    c2 = msvcrt.getwch()
                    if c == '\xe0' and c2 == 'H':
                        _q.put(_HIST_UP)
                    elif c == '\xe0' and c2 == 'P':
                        _q.put(_HIST_DN)
                    continue
                if c == '\r':
                    c = '\n'
                elif c == '\x1b':
                    c = '\\e'
                _q.put(c)
    else:
        import termios, tty
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        tty.setraw(fd)
        def _reader():
            while True:
                c = sys.stdin.read(1)
                if c == '\r':
                    c = '\n'
                elif c == '\x1b':
                    c = '\\e'
                _q.put(c)

    threading.Thread(target=_reader, daemon=True).start()


_start_reader()


class tml_prime:
    def __init__(self, **kwargs):
        self.cursor_x = 0
        self.cursor_y = 0
        self.rows = 22           # match device geometry for the pager
        self.status_text = ""
        self._scrollback_ms = 0
        self.alpha_lock = False
        self.shift_lock = False
        self.is_alpha = False
        self.is_shift = False
        self.alpha_hold = False
        self.shift_hold = False
        self.symb_hold = False
        self._in_scrollback = False
        self._at_prompt = False

    # print() and set_status() are monkey-patched by install_color_print() immediately
    # after construction; these stubs should never be called in normal use.
    def print(self, *args, sep=' ', end='\n'):
        sys.stdout.write(sep.join(str(a) for a in args) + end)
        sys.stdout.flush()

    def clear(self):
        os.system('cls' if os.name == 'nt' else 'clear')

    def input(self, prompt=None, alpha=True, shift=False, new_line=True, length=0, default=''):
        if prompt:
            sys.stdout.write('\n' + prompt)
            sys.stdout.flush()
        result = list(default)
        if default:
            sys.stdout.write(default)
            sys.stdout.flush()
        while True:
            try:
                c = _q.get(timeout=0.05)
            except queue.Empty:
                continue
            if c == '\x03':
                # Ctrl-C arrives as a raw char (getwch/setraw bypass console
                # signal handling); mirror the calc's On-key exit signal.
                raise KeyboardInterrupt
            if c == '\n':
                break
            elif c == '\b' and result:
                result.pop()
                sys.stdout.write('\b \b')
                sys.stdout.flush()
            else:
                result.append(c)
                sys.stdout.write(c)
                sys.stdout.flush()
        if new_line:
            sys.stdout.write('\n')
            sys.stdout.flush()
        return ''.join(result)

    def set_status(self, text):  # monkey-patched by install_color_print()
        sys.stdout.write('\r' + text)
        sys.stdout.flush()

    def resync_keyboard(self):
        pass

    def has_queued_keys(self):
        return not _q.empty()

    def read_key(self, code=False):
        """Blocking single-key read (pager etc.); esc arrives as '\\e'."""
        while True:
            c = _q.get()
            if c == '\x03':
                raise KeyboardInterrupt
            return c

    def _refresh_indicators(self):
        pass

    def poll_char(self, key_commands=None):
        try:
            c = _q.get_nowait()
        except queue.Empty:
            return None
        if c == '\x03':
            # Ctrl-C arrives as a raw char (getwch/setraw bypass console
            # signal handling); mirror the calc's On-key exit signal.
            raise KeyboardInterrupt
        return (c, None)
