"""Graphical PC adapter for the device tml_prime implementation."""

import importlib.util
import os

from hpprime import clear_events, has_events, poll_event, pump_events


_SRC_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "src", "tml_prime.py",
)
_SPEC = importlib.util.spec_from_file_location("_device_tml_prime", _SRC_PATH)
_DEVICE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_DEVICE)

_SB_UP = _DEVICE._SB_UP
_SB_DN = _DEVICE._SB_DN
_HIST_UP = _DEVICE._HIST_UP
_HIST_DN = _DEVICE._HIST_DN


class tml_prime(_DEVICE.tml_prime):
    """Run device terminal code with Tk keyboard events."""

    def _pump_keyboard(self, key_commands=None):
        pump_events()
        while True:
            event = poll_event()
            if event is None:
                return
            kind, value = event
            if kind == "interrupt":
                raise KeyboardInterrupt
            if kind == "bit":
                self._queue_key(
                    self._translate_key_press(value, key_commands)
                )
            elif kind == "char":
                self._queue_key((value, None))
            elif kind == "scroll_up":
                self._queue_key((_SB_UP, None))
            elif kind == "scroll_down":
                self._queue_key((_SB_DN, None))

    def has_queued_keys(self):
        return _DEVICE.tml_prime.has_queued_keys(self) or has_events()

    def resync_keyboard(self):
        pump_events()
        clear_events()
        _DEVICE.tml_prime.resync_keyboard(self)
