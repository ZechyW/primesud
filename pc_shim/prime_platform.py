"""PC replacements for HP Prime platform calls."""
import time
import json
import os


# Repo root, not cwd -- shared between run_source.py and run_dist.py,
# and keeps dist/ a clean transfer artifact
_HVARS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hvars.json")


def ticks():
    return int(time.monotonic() * 1000)


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