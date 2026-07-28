"""Checks for graphical PC GROB operations."""

import importlib.util
import os


ROOT = os.path.dirname(os.path.dirname(__file__))
_PATH = os.path.join(ROOT, "pc_gui_shim", "hpprime.py")
_SPEC = importlib.util.spec_from_file_location("gui_hpprime_test", _PATH)
gui_hpprime = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(gui_hpprime)

_FLING_PATH = os.path.join(ROOT, "pc_gui_shim", "fling.py")
_FLING_SPEC = importlib.util.spec_from_file_location(
    "gui_fling_test", _FLING_PATH,
)
gui_fling = importlib.util.module_from_spec(_FLING_SPEC)
_FLING_SPEC.loader.exec_module(gui_fling)


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
    event = type("Event", (), {"x": 40, "y": 60})()
    gui_hpprime._scale = 2
    gui_hpprime._on_pointer_down(event)
    assert gui_hpprime.mouse() == [(20, 30, 1)]
    gui_hpprime._on_pointer_up(event)
    assert gui_hpprime.mouse() == [(-1, 0, 0)]


def test_fling_uses_device_integer_step_and_decay():
    assert gui_fling.advance_fling(
        depth=5, accum_px=0, velocity=1000, dt_ms=100,
        step_px=30, step_rows=3, hist_count=20,
        min_velocity=120, decay_num=7, decay_den=8,
    ) == (14, 10, 875, True)
