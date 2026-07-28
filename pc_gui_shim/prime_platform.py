"""PC platform calls for Tkinter graphical mode."""

import json
import os
import time

import hpprime


_HVARS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "hvars.json",
)


def ticks():
    return int(time.monotonic() * 1000)


def wait_ms(ms):
    hpprime.wait_ms(ms)


def clear_graphics(*args):
    hpprime.close_display()


def _load():
    try:
        with open(_HVARS_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def hvars_get(name):
    return _load().get(name, "")


def hvars_set(name, value):
    data = _load()
    data[name] = value
    with open(_HVARS_FILE, "w") as f:
        json.dump(data, f)
