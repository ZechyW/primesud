"""Checks for graphical PC GROB operations."""

import importlib.util
import os
import sys


ROOT = os.path.dirname(os.path.dirname(__file__))
_PATH = os.path.join(ROOT, "pc_gui_shim", "hpprime.py")
_SPEC = importlib.util.spec_from_file_location("gui_hpprime_test", _PATH)
gui_hpprime = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(gui_hpprime)


def _load_gui_tml():
    names = ("hpprime", "tml", "uio", "cas")
    old_modules = {name: sys.modules.get(name) for name in names}
    old_path = sys.path[:]
    try:
        sys.path[0:0] = [
            os.path.join(ROOT, "pc_gui_shim"),
            os.path.join(ROOT, "src"),
        ]
        sys.modules["hpprime"] = gui_hpprime
        for name in names[1:]:
            sys.modules.pop(name, None)
        path = os.path.join(ROOT, "pc_gui_shim", "tml_prime.py")
        spec = importlib.util.spec_from_file_location("gui_tml_test", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path[:] = old_path
        for name, module in old_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


gui_tml = _load_gui_tml()


def _event(keysym, char="", state=0):
    return type(
        "Event", (), {"keysym": keysym, "char": char, "state": state}
    )()


def _bare_terminal():
    tr = object.__new__(gui_tml.tml_prime)
    tr._key_queue = [None] * 16
    tr._key_queue_head = 0
    tr._key_queue_tail = 0
    tr._key_queue_count = 0
    tr._key_queue_drops = 0
    return tr


def test_grob_blit_and_overlap():
    gui_hpprime.dimgrob(1, 2, 3, 0)
    gui_hpprime.pixon(1, 0, 0, 0xFF0000)
    gui_hpprime.pixon(1, 0, 1, 0x00FF00)
    gui_hpprime.pixon(1, 0, 2, 0x0000FF)

    gui_hpprime.dimgrob(2, 2, 3, 0)
    gui_hpprime.strblit2(2, 0, 0, 2, 3, 1, 0, 0, 2, 3)
    assert gui_hpprime.getpix(2, 0, 1) == 0x00FF00

    gui_hpprime.strblit2(1, 0, 0, 2, 2, 1, 0, 1, 2, 2)
    assert [gui_hpprime.getpix(1, 0, y) for y in range(3)] == [
        0x00FF00, 0x0000FF, 0x0000FF,
    ]


def test_pointer_coordinates_use_unscaled_screen_pixels():
    pad = gui_hpprime._PAD
    event = type("Event", (), {"x": 40 + pad, "y": 60 + pad})()
    gui_hpprime._scale = 2
    gui_hpprime._on_pointer_down(event)
    assert gui_hpprime.mouse() == [(20, 30, 1)]
    gui_hpprime._on_pointer_up(event)
    assert gui_hpprime.mouse() == [(-1, 0, 0)]


def test_fillrect_uses_edge_and_fill_colors():
    gui_hpprime.dimgrob(3, 3, 3, 0)
    gui_hpprime.fillrect(3, 0, 0, 3, 3, 0xFF0000, 0x00FF00)

    assert gui_hpprime.getpix(3, 0, 0) == 0xFF0000
    assert gui_hpprime.getpix(3, 1, 1) == 0x00FF00


def test_desktop_keys_route_through_device_translation():
    tr = _bare_terminal()
    gui_hpprime.clear_events()

    assert gui_tml.tml_prime.__mro__[1] is gui_tml._DEVICE.tml_prime

    gui_hpprime._on_key(_event("Up"))
    tr._pump_keyboard({2: ("n", True)})
    assert tr._dequeue_key() == (gui_tml._HIST_UP, None)

    gui_hpprime._on_key(_event("Down"))
    tr._pump_keyboard({12: ("s", True)})
    assert tr._dequeue_key() == (gui_tml._HIST_DN, None)

    gui_hpprime._on_key(_event("Left"))
    gui_hpprime._on_key(_event("Right"))
    tr._pump_keyboard({7: ("w", True), 8: ("e", True)})
    assert tr._dequeue_key() is None

    gui_hpprime._on_key(_event("Up"))
    tr._pump_keyboard({2: ("\\U", None)})
    assert tr._dequeue_key() == ("\\U", None)

    # A modal keymap (pager.hpan) reclaims the otherwise-unused Left/Right
    # arrows, which only carry the prompt-history override at their default
    # w/e movement binding.
    gui_hpprime._on_key(_event("Left"))
    gui_hpprime._on_key(_event("Right"))
    tr._pump_keyboard({7: ("\\L", None), 8: ("\\R", None)})
    assert tr._dequeue_key() == ("\\L", None)
    assert tr._dequeue_key() == ("\\R", None)

    gui_hpprime._on_key(_event("Prior"))
    tr._pump_keyboard()
    assert tr._dequeue_key() == (gui_tml._HIST_UP, None)

    gui_hpprime._on_key(_event("Next", state=1))
    tr._pump_keyboard()
    assert tr._dequeue_key() == (gui_tml._SB_DN, None)


def test_desktop_scale_shortcuts(monkeypatch):
    configured = []
    monkeypatch.setattr(
        gui_hpprime, "_canvas",
        type("Canvas", (), {"configure": lambda self, **values: configured.append(values)})(),
    )
    gui_hpprime._scale = 1

    gui_hpprime._on_key(_event("equal", char="=", state=4))
    assert gui_hpprime._scale == 2
    assert configured[-1]["width"] == 320 * 2 + 2 * gui_hpprime._PAD

    gui_hpprime._on_key(_event("minus", char="-", state=4))
    assert gui_hpprime._scale == 1

    gui_hpprime._scale = 3
    gui_hpprime._on_key(_event("0", char="0", state=4))
    assert gui_hpprime._scale == 1


def test_keyboard_resync_clears_desktop_events():
    tr = _bare_terminal()
    tr._refresh_indicators = lambda: None
    gui_hpprime._on_key(_event("x", char="x"))

    tr.resync_keyboard()

    assert not gui_hpprime.has_events()
    assert tr._key_queue_count == 0
