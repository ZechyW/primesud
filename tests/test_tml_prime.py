import importlib.util
import os
import sys
import types


_ROOT = os.path.dirname(os.path.dirname(__file__))
_PATH = os.path.join(_ROOT, "src", "tml_prime.py")
_HPPRIME = types.ModuleType("hpprime")
_HPPRIME.dimgrob = lambda *args: None
_HPPRIME.eval = lambda expr: 0
_HPPRIME.keyboard = lambda: 0
_HPPRIME.mouse = lambda: [(-1, 0, 0)]
_HPPRIME.strblit2 = lambda *args: None
_TML = types.ModuleType("tml")
_TML.tml = object
sys.modules.setdefault("hpprime", _HPPRIME)
sys.modules.setdefault("tml", _TML)
_SPEC = importlib.util.spec_from_file_location("src_tml_prime", _PATH)
_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)
_advance_fling = _MOD._advance_fling
tml_prime = _MOD.tml_prime


def test_advance_fling_moves_by_row_steps_and_decays_velocity():
    depth, accum_px, velocity, moved = _advance_fling(
        depth=7, accum_px=0, velocity=500, dt_ms=40,
        step_px=10, step_rows=3, hist_count=40,
        min_velocity=120, decay_num=7, decay_den=8)

    assert depth == 13
    assert accum_px == 0
    assert velocity == 437
    assert moved is True


def test_advance_fling_clamps_at_present_and_stops_below_threshold():
    depth, accum_px, velocity, moved = _advance_fling(
        depth=2, accum_px=0, velocity=-500, dt_ms=40,
        step_px=10, step_rows=3, hist_count=40,
        min_velocity=120, decay_num=1, decay_den=4)

    assert depth == 0
    assert accum_px == 0
    assert velocity == -125
    assert moved is True

    depth, accum_px, velocity, moved = _advance_fling(
        depth=depth, accum_px=accum_px, velocity=velocity, dt_ms=40,
        step_px=10, step_rows=3, hist_count=40,
        min_velocity=120, decay_num=1, decay_den=4)

    assert depth == 0
    assert accum_px == 0
    assert velocity == 0
    assert moved is False


def test_poll_char_release_guard_blocks_immediate_reentry(monkeypatch):
    tr = object.__new__(tml_prime)
    tr._hist_size = 1
    tr._hist_count = 1
    tr._in_scrollback = False
    tr._touch_start_y = None
    tr._touch_last_y = 0
    tr._touch_release_seen = False
    tr._swipe_threshold = 20
    tr._scrollback_ms = 0
    tr._key_queue = []
    tr._scroll_calls = 0
    tr._queued = []

    points = iter([
        [(0, 90, 1)],    # finger still down after prior scrollback: must not re-enter
        [(-1, 0, 0)],    # full release re-arms touch entry
        [(0, 50, 1)],    # new touch starts swipe
        [(0, 80, 1)],    # continued drag crosses threshold and enters scrollback
    ])
    monkeypatch.setattr(_MOD, "mouse", lambda: next(points))
    monkeypatch.setattr(_MOD, "ppleval", lambda expr: 0)
    tr._pump_keyboard = lambda key_commands=None: None
    tr._dequeue_key = lambda: None
    tr._queue_key = lambda event: tr._queued.append(event) if event is not None else None

    def _fake_scrollback():
        tr._scroll_calls += 1
        return None

    tr._scrollback = _fake_scrollback

    assert tr.poll_char() is None
    assert tr._scroll_calls == 0
    assert tr._touch_release_seen is False

    assert tr.poll_char() is None
    assert tr._touch_release_seen is True

    assert tr.poll_char() is None
    assert tr._touch_start_y == 50
    assert tr._scroll_calls == 0

    assert tr.poll_char() is None
    assert tr._scroll_calls == 1
    assert tr._queued == []


def test_scrollback_retouch_cancels_pending_fling(monkeypatch):
    tr = object.__new__(tml_prime)
    tr.width = 320
    tr.height = 220
    tr._save_grob = 6
    tr._hist_size = 40
    tr._hist_count = 40
    tr._hist_write = 0
    tr.rows = 22
    tr.char_height = 10
    tr._scroll_step = 5
    tr._touch_scroll_step = 3
    tr._fling_frame_ms = 16
    tr._fling_min_velocity = 120
    tr._fling_decay_num = 7
    tr._fling_decay_den = 8
    tr._fling_smooth_num = 3
    tr._in_scrollback = False
    tr._touch_release_seen = True
    tr._resynced = 0
    rendered = []
    waits = []

    tr._render_scrollback = lambda depth: rendered.append(depth)
    tr.resync_keyboard = lambda: setattr(tr, "_resynced", tr._resynced + 1)

    keys = iter([None, None, None, None, ("x", None)])
    tr.poll_char = lambda key_commands=None: next(keys)

    points = iter([
        [(0, 50, 1)],    # touch down
        [(0, 90, 1)],    # drag enough to scroll and build velocity
        [(-1, 0, 0)],    # lift: fling becomes eligible
        [(0, 80, 1)],    # retouch: should cancel fling and start fresh drag
    ])
    monkeypatch.setattr(_MOD, "mouse", lambda: next(points))

    ticks = iter([0, 20, 40, 50])

    def _fake_ppleval(expr):
        if expr == "Ticks":
            return next(ticks)
        if expr.startswith("WAIT("):
            waits.append(expr)
            return 0
        return 0

    monkeypatch.setattr(_MOD, "ppleval", _fake_ppleval)

    assert tr._scrollback() == "x"
    assert rendered == [5, 8]
    assert tr._resynced == 1
    assert waits
