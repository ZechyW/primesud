# Touch Scrollback — Implementation Plan

## Goal

Use the HP Prime's touchscreen (`hpprime.mouse()`) to trigger and drive the existing
scrollback system, as an alternative to the Shift+- / Shift++ key bindings.

A vertical swipe up on the screen should enter scrollback (or scroll further back if
already in scrollback). A swipe down should scroll forward (toward present), exiting
when depth reaches 0. A tap with no significant vertical movement is a no-op —
it should not exit scrollback, so fat-fingering the screen doesn't eject the user.

---

## Phase 1 — Probe: understand `mouse()` on-device

We do not yet know:

1. **Coordinate system.** Is it 0–319 / 0–239 matching the display, or some other scale?
2. **Poll-or-event.** Does `mouse()` return the *current* live state (must be polled in a
   tight loop), or does it queue events?
3. **Empty-tuple sentinel.** Is a finger-down slot `(x, y)` and finger-up slot `()`, or can
   it be `None` or something else?
4. **Lift detection.** How do we know a finger has been lifted — does the slot go back to
   `()`? Is there a delay?
5. **Multi-touch ordering.** Are the two slots always stable (slot 0 = first finger down),
   or do they swap?

### 1a. Inline test harness

Add the following block to `run()` in `primesud.py`, immediately before `game.show_greeting()`,
and run it on the emulator or device. Remove after gathering results.

```python
# --- TOUCH PROBE (remove after testing) ---
tr.print("{Cmouse() probe — swipe, tap, hold, lift. Esc to quit.{x\n")
_last = None
while True:
    import hpprime as _hp
    _m = _hp.mouse()
    if _m != _last:
        tr.print("%s\n" % repr(_m))
        _last = _m
    # exit on any key
    _c = tr.poll_char()
    if _c is not None:
        break
# --- END TOUCH PROBE ---
```

What to test during the probe:
- **Tap**: touch briefly and release — note what `mouse()` returns while down and after lift.
- **Hold**: keep finger down — does value stay stable?
- **Swipe up**: start low, move up — do coordinates update smoothly?
- **Swipe down**: start high, move down.
- **Two fingers**: place both, lift one, lift both.
- **Edge: no touch**: confirm both slots are `()`.

Record findings in this file under **Phase 1 Results** before proceeding.

### 1b. Emulator caveat

The HP Prime Virtual Calculator (PC) uses mouse clicks to simulate touch. Verify that
`mouse()` actually updates in the emulator; it may need the physical device for real
swipe testing.

---

## Phase 2 — Swipe detection algorithm (design)

Phase 1 confirmed: `mouse()` returns `((x, y), ())` while a finger is down and
`((), ())` when fully lifted. There is also an intermediate `((-1, 0), ())` sentinel
on lift, but it is unreliable — sometimes skipped entirely. The leading hypothesis
is polling lag on the emulator, but this should be confirmed on a physical device.

**Lift detection must therefore treat both `()` and `(-1, 0)` as "not touching".**
A helper predicate captures this:

```python
def _touch_valid(pt):
    return bool(pt) and pt[0] >= 0
```

Algorithm:

```
touch_start_y = None
pt_last_y     = 0

on each poll:
    pt = mouse()[0]
    if _touch_valid(pt):
        if touch_start_y is None:
            touch_start_y = pt[1]   # finger just placed (first valid sample)
        pt_last_y = pt[1]           # track last known position while held
    elif touch_start_y is not None:
        # finger lifted (pt is () or (-1,0))
        delta = pt_last_y - touch_start_y
        touch_start_y = None
        if delta < -SWIPE_THRESHOLD:    # moved up → scroll back
            trigger SB_UP
        elif delta > SWIPE_THRESHOLD:   # moved down → scroll forward
            trigger SB_DN
        # else: tap → no-op (stay in scrollback)
```

**Constants to tune (put in `config.py`):**
- `SWIPE_THRESHOLD = 20`  — minimum pixel delta to register as a swipe vs. a tap.
  Screen is confirmed 320×240, so 20 px is ~8% of screen height — reasonable starting point.

**Coordinate note:** confirmed 0–319 / 0–239, matches display pixel space.

**Repeat scroll:** implemented — while a finger is held, each `TOUCH_SCROLL_STEP *
char_height` pixels of drag scrolls `TOUCH_SCROLL_STEP` rows. `touch_base_y` advances
with each step so subsequent movement is measured from the last trigger point, not from
finger-down. Tap (lift without crossing threshold) is a no-op inside scrollback.

**Interoperability:** entering scrollback via Shift+- and then continuing with touch (or
vice versa) works naturally — `_scrollback()` polls both keyboard and touch in the same
loop. `_in_scrollback` flag (see Phase 3) prevents `poll_char()` from re-entering
`_scrollback()` recursively while the loop is running.

---

## Phase 3 — Integration into `tml_prime.py` *(implemented)*

### Key decisions

**Non-blocking keyboard inside `_scrollback()`:** base `tml` has no non-blocking
`poll_char`. Rather than adding one, `_scrollback()` calls `self.poll_char()` (already
non-blocking in `tml_prime`) with a `_in_scrollback = True` guard that prevents
`poll_char()` from intercepting `_SB_UP`/`_SB_DN` and recursing back into `_scrollback()`.

**`_in_scrollback` flag:** set in `_scrollback()` under a `try/finally`, checked in
`poll_char()` before the scrollback re-entry block and before the touch-entry block.
Cleaner than temporarily zeroing `_hist_size` — expresses intent directly.

**`poll_char()` touch entry (game-loop path):** touch state (`_touch_start_y`,
`_touch_last_y`) persists across calls as instance variables. On lift, if Y-delta
exceeds `_swipe_threshold`, `_scrollback()` is called exactly as Shift+- would do it
(same `_scrollback_ms` accounting, same `resync_keyboard()` call).

The touch block is placed at the **top** of `poll_char()`, before the
`if not changed: return None` early exit. Placing it at the bottom was a bug: the
early return meant the touch state machine never ran during a swipe (no keyboard
activity → immediate return). It also caused the next keypress after a sub-threshold
touch to arrive late, because the half-set touch state was occasionally reached via
modifier-key releases and left `_touch_start_y` in a dirty state. A sub-threshold
lift (tap) resets the touch state and falls through to keyboard handling normally.

### 3c. Import

```python
from hpprime import dimgrob, eval as ppleval, keyboard, mouse, strblit2
```

---

## Phase 4 — Edge cases and hardening

- **Accidental touch while typing:** If `SWIPE_THRESHOLD` is large enough (20 px+), brief
  accidental grazes should not fire. Tune after physical device testing.
- **Emulator:** If `mouse()` does not work in the emulator, the keyboard path is
  unaffected — touch integration degrades silently.
- **Two touch points:** Only slot 0 is used for scrollback. This avoids interference
  from two-finger holds or accidental second-finger contact.
- **Time in scrollback accounting:** The `_scrollback_ms` clock mechanism (already in
  place) should continue to work unchanged since it wraps the entire `_scrollback()` call.

---

## Open questions (resolve in Phase 1)

1. Does `mouse()` return `((), ())` when no touch, or something else?
2. Are coordinates in screen pixels (0–319, 0–239)?
3. Does the emulator support `mouse()` at all?
4. Is polling fast enough for smooth drag, or is there noticeable lag?

---

## Phase 1 Results

Tested on HP Prime emulator (PC).

| Question | Finding |
|---|---|
| Coordinate system | Confirmed 0–319 / 0–239, matches display pixel space |
| Finger down | `((x, y), ())` — slot 0 has coordinates, slot 1 empty |
| Finger held | Value stays stable between polls |
| Swipe | New coordinates printed smoothly on each poll iteration |
| Finger lift | Usually `((-1, 0), ())` then `((), ())`, but `(-1, 0)` step sometimes absent |
| Poll-or-event | **Not yet conclusive.** Smooth updates and stable hold are consistent with live-state polling. The skipped `(-1, 0)` step is better explained by polling past a transient state than by an event queue (which would normally preserve every transition) — but an event queue that drops stale intermediates would look identical. To confirm: call `mouse()` twice in rapid succession mid-swipe and verify both return the same coordinates (live state) rather than advancing independently (queue). |
| Two-finger / edge | Not tested — emulator only supports single mouse pointer |

**Consequence for implementation:** lift detection must treat both `(-1, 0)` and `()`
as "not touching" regardless of poll-or-event outcome, since the sentinel is unreliable.
Physical device testing needed to confirm whether `(-1, 0)` is consistently present on
real hardware, and to settle the poll-or-event question.

---

## Known issues (post-implementation)

### 1. Scroll direction is inverted ✓ FIXED

Swipe direction flipped in both `poll_char()` touch blocks and `_scrollback()` drag logic.
`delta > threshold` now means scroll-back (swipe down); `delta < -threshold` means scroll-forward.

### 2. Scrollback does not start until finger lift ✓ FIXED

Threshold check moved into the *held* branch of both `poll_char()` touch blocks.
`_scrollback()` is now called as soon as `delta > _swipe_threshold` while the finger
is still down. The lift branch now only resets state for a sub-threshold tap.

### 3. Next keypress swallowed after swipe-exit from scrollback

**Current behaviour:** after swiping forward past depth 0 (exiting scrollback), the very
next character typed is silently consumed and never delivered to the caller of
`poll_char()`.

**Root cause (hypothesis):** when `_scrollback()` exits, the keyboard state from the
preceding swipe lift (or the first subsequent keypress) is left in a consumed or
partially-advanced state inside `poll_char()`'s `changed` / `last_kb` tracking, so
the first real keypress is seen as a no-change and discarded.

**Fix:** call `self.resync_keyboard()` immediately before returning from `_scrollback()`
(in addition to the call already present on entry). This resets `last_kb` to the
current hardware state so the next `poll_char()` poll starts clean.
