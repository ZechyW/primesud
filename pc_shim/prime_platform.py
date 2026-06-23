"""PC replacements for HP Prime platform calls."""
import time
import json


_HVARS_FILE = "hvars.json"


def ticks():
    return int(time.monotonic() * 1000)


def wait(seconds):
    time.sleep(seconds)


def wait_ms(ms):
    time.sleep(ms / 1000.0)


def clear_graphics(*a):
    pass


def _load():
    try:
        with open(_HVARS_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def hvars_get(name):
    return _load().get(name, "")


def hvars_set(name, value):
    d = _load()
    d[name] = value
    with open(_HVARS_FILE, "w") as f:
        json.dump(d, f)