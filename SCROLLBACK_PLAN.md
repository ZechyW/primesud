# Scrollback Plan — tml.py

## Implementation module

Implemented as a **subclass of `tml`** in a new file (e.g. `tml_sb.py`), not
by modifying `tml.py`. This honours the "stable library" constraint in CLAUDE.md.
The subclass overrides `__init__`, `_scroll_up`, and `read_key`, and adds
`_scrollback` / `_render_scrollback`. The game imports the subclass instead of
`tml` directly.

---

## Approach

Store scrolled-off rows in a dedicated GROB (the "history GROB") arranged as a
ring buffer. Each scroll event writes one row into the ring at O(1) cost.
Scrollback display composites a viewport from the history GROB and a saved copy
of the current screen.

Rejected alternative: shift the entire history GROB upward on every scroll event
(simpler viewport math but O(history_size) blit cost per line of game output once
the buffer is full).

---

## GROB allocation

| GROB | Purpose | Notes |
|------|---------|-------|
| G0   | Display (existing) | |
| G9   | Font bitmap (existing) | |
| G8   | Coloured font bitmap (existing) | Used by `set_color()` |
| G7   | History ring buffer (default) | `width × (scrollback_size × char_height)` px |
| G6   | G0 save buffer (default) | `width × height` px (visible area only) |

- G7 and G6 are the proposed defaults; both are constructor parameters (like the
  existing `grob=9`), so callers can override if they use those GROBs themselves.
- `Ghist` and `Gsave` are allocated at init time if `scrollback_size > 0` using
  the Python-native `dimgrob` function (import from `hpprime`):
  ```python
  dimgrob(hist_grob, width, scrollback_size * char_height, back_color)
  dimgrob(save_grob, width, height, back_color)
  ```
  Signature: `dimgrob(graphic, width, height, color)` where `graphic` is the
  integer GROB number. Prefer this over `ppleval('DIMGROB_P(...)')` — no string
  building, no PPL eval overhead.

---

## Data added to `tml`

```
_hist_grob      int   GROB number for history ring buffer
_save_grob      int   GROB number for G0 save
_hist_size      int   capacity in rows (0 = scrollback disabled)
_hist_write     int   next write slot index (0 … _hist_size-1)
_hist_count     int   rows stored so far, capped at _hist_size
```

---

## Write path — changes to `_scroll_up`

Before the existing G0 pixel shift:

1. Blit the top row of G0 (the row about to be lost) into slot `_hist_write` of
   the history GROB:
   ```
   strblit2(Ghist, 0, _hist_write * char_height,
            width, char_height,
            0,     0, 0, width, char_height)
   ```
2. Advance the ring:
   ```python
   self._hist_write = (self._hist_write + 1) % self._hist_size
   if self._hist_count < self._hist_size:
       self._hist_count += 1
   ```

The existing G0 blit + fillrect in `_scroll_up` is unchanged.

---

## Read path — internal `_scrollback()` sub-loop

Triggered **automatically inside `read_key()`** when key 45 (`-`) is pressed
and `_hist_count > 0`. No public API change; works transparently whether the
caller is the main game loop or `input()`.

### Entry (first `-` press)
1. Save G0's visible area to `Gsave`:
   ```
   strblit2(Gsave, 0, 0, width, height, 0, 0, 0, width, height)
   ```
2. Set `depth = min(scroll_step, _hist_count)` and immediately render (the
   first press scrolls back `scroll_step` rows before entering the key loop).

### Key loop
- **Key 45 (`-`)**: `depth = min(depth + scroll_step, _hist_count)`; re-render.
- **Key 50 (`+`)**: `depth = max(depth - scroll_step, 0)`; re-render. If
  `depth` reaches 0, exit scrollback (see below).
- **Any other key**: exit scrollback, then process the key normally (pass it
  back to the `read_key()` caller).

### Exit (depth returns to 0)
Restore G0 from `Gsave`:
```
strblit2(0, 0, 0, width, height, Gsave, 0, 0, width, height)
```
Return `None` from `read_key()` (caller loops and waits for the next key).

### Re-render at depth N

There are two regions to composite onto G0:

**Region A — top N rows — from history GROB**

The N most-recently-stored rows are slots:
```
slot_start = (_hist_write - N) % _hist_size   # oldest of the N
slot_end   = _hist_write - 1  (mod _hist_size) # most recent
```
These slots are in reverse-chronological order in the ring, so we blit them
from `slot_end` down to `slot_start`, mapping each slot to display row 0, 1, …
N-1.

If the range `[slot_start … slot_end]` does not wrap: one pass.
If it wraps: two passes (tail of ring, then head of ring).

**Region B — bottom (rows - N) rows — from Gsave**

```
strblit2(0, 0, N * char_height,
         width, (rows - N) * char_height,
         Gsave, 0, 0, width, (rows - N) * char_height)
```

---

## Constructor signature change

```python
def __init__(self, ..., scrollback_size=0, scroll_step=5, hist_grob=7, save_grob=6):
```

`scrollback_size=0` disables the feature entirely (no GROBs allocated, no
overhead).

---

## Open questions

1. [x] **GROB numbers**: G7 (hist) and G6 (save) as defaults; both are
   constructor parameters matching the `grob=9` pattern.

2. [x] **Trigger key**: Key 45 (`-`) auto-enters scrollback from inside
   `read_key()`; no game-side call needed. First press also performs the first
   scroll-up.

3. [x] **Navigation keys**: Key 45 (`-`) = scroll up, key 50 (`+`) = scroll
   down. Depth returning to 0 auto-exits; any other key exits and is forwarded
   to the caller.

4. [x] **Scroll step**: 5 rows per keypress (configurable via `scroll_step`
   constructor parameter, default 5). Depth is clamped to `_hist_count` on the
   way up and to 0 on the way down (auto-exit).

5. [x] **Reasonable `scrollback_size`**: Default **250 rows**. G1 tested OK up
   to 1000 rows; 250 is well within budget on both G1 and G2.

6. [x] **Self-blit safety**: No new self-blits introduced. All scrollback
   `strblit2` calls use distinct source/dest GROBs. The only self-blit in the
   file is the existing `_scroll_up` (G0→G0, scroll-up shift), already proven
   to work in production.

7. [x] **Status bar**: Remains visible and untouched during scrollback.
   Compositing only covers the text area (`height`); status bar rows are outside
   that region and unaffected.
