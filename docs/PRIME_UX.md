# PrimeSUD — HP Prime UX Enhancements

All items below are PrimeSUD inventions with no 1stMud equivalent unless noted.
Code locations marked `[PRIMESUD]` throughout the source.

---

## D-pad navigation keys

Physical d-pad keys (and Up/Down) auto-submit directional commands without
pressing Enter.  The mapping is defined in `config.py:KEY_COMMANDS`:

| Key (bit index) | Command | Direction |
|---|---|---|
| 2  (d-pad Up)    | `n` | north |
| 12 (d-pad Down)  | `s` | south |
| 7  (d-pad Left)  | `w` | west  |
| 8  (d-pad Right) | `e` | east  |
| 6               | `u` | up    |
| 9               | `d` | down  |

`auto_submit=True` means the command fires the instant the key is pressed;
`auto_submit=False` (not currently used for nav) would load it into the input
buffer instead.  Add or remap keys by editing `KEY_COMMANDS` in `config.py`;
bit indices may differ between hardware revisions.

---

## Digit and function-key macros

Digit keys `0`–`9` and nine function keys act as one-key shortcuts that load a
command into the input buffer when it is empty (not auto-submitted — the player
still presses Enter, allowing arguments to be appended first).  With a
non-empty buffer, digits type normally, so numeric arguments still work.

Default digit bindings (`config.py:DEFAULT_MACROS`):

| Key | Command   |
|-----|-----------|
| 7   | `kill`    |
| 8   | `flee`    |
| 9   | `cast`    |
| 4   | `open`    |
| 5   | `get`     |
| 6   | `drop`    |
| 1   | `score`   |
| 2   | `practice`|
| 3   | `train`   |
| 0   | `macro`   |

Default function-key bindings (`config.py:FNKEY_TABLE`; the two key rows above
the numpad):

| Key | Name  | Command     |
|-----|-------|-------------|
| sin | `sin` | `look`      |
| cos | `cos` | `rest`      |
| tan | `tan` | `stand`     |
| ln  | `ln`  | `recall`    |
| log | `log` | `sac`       |
| x²  | `x2`  | `inventory` |
| +/- | `pm`  | `equip`     |
| ( ) | `()`  | `wear`      |
| ,   | `,`   | `remove`    |

Bindings are live-editable with the `macro` command:

```
macro             — show current bindings in a grid layout
macro <key> <cmd> — bind key (digit or fn-key name) to command
macro <key>       — clear binding
macro default     — restore all defaults
```

The mapping lives in `macros.py:_MACRO_SUBST` (initialised from
`DEFAULT_MACROS` + `DEFAULT_FNKEY_MACROS`) and persists in the save file
(`p.macro.*` lines in game_state.py).

---

## Command history

Previously submitted commands are stored in `Game._cmd_history` (oldest first,
capped at `config.py:CMD_HISTORY_MAX`).  Consecutive duplicates are
not stored.

| Key  | Action |
|------|--------|
| Symb (index 1) | Load the previous (older) command into the input buffer |
| Help (index 3) | Load the next (newer) command; at the newest, restore the original half-typed input |

**Saved input:** the first Symb press snapshots the current input buffer into
`_hist_saved`.  Navigating Help all the way past the newest entry restores that
snapshot, so a half-typed command is never lost.  ESC or Enter clear the snapshot.

**Editing while browsing:** typing or backspacing modifies the input buffer
without affecting the history list or exiting navigation mode (ephemeral edits).
Pressing Help back to the end still restores the original `_hist_saved` text.

Sentinels `_HIST_UP` / `_HIST_DN` are defined in `tml_prime.py` and returned by
`poll_char` on key press.  History logic lives entirely in `game_loop`
(`primesud.py`).

---

## Scrollback history

`tml_prime` (subclass of `tml`) captures each row that scrolls off the top into
a ring buffer (GROB 7, default 250 rows).

| Key     | Action |
|---------|--------|
| Shift+- | Enter scrollback / scroll up one step |
| - or Shift+- | Scroll up further (inside scrollback) |
| + or Shift++ | Scroll down; exits automatically at depth 0 |
| Any other key | Exit scrollback; key is forwarded to the game |

Works in both the blocking input path (`read_key`) and the non-blocking poll
loop (`poll_char`).  Screen is saved to GROB 6 on entry and restored on exit.
Ring size and step are configurable via `tml_prime` constructor args
`scrollback_size` and `scroll_step`.

### Touch scrollback

Alongside the key bindings above, a vertical drag on the touchscreen
(`hpprime.mouse()`) can enter and drive scrollback.  Only the first touch
slot (finger 0) is read; a second touch point is ignored.

| Gesture | Action |
|---------|--------|
| Swipe down (drag toward the bottom of the screen) | Enter scrollback, or scroll further back if already inside it |
| Swipe up (drag toward the top of the screen) | Scroll toward the present; exits automatically at depth 0 |
| Tap (lift with no significant vertical movement) | No-op -- stays put, so an accidental touch can't eject the player |
| Continued drag past the threshold | Keeps scrolling in `touch_scroll_step`-row steps for as long as the finger is held, without needing to lift and re-swipe |
| Fast lift after a drag | Starts a short row-step fling that eases to a stop |
| New touch during a fling | Cancels the fling immediately and starts a fresh gesture from that touch-down |

Entry (from the game loop's `poll_char`) fires as soon as the drag exceeds
`swipe_threshold` pixels while the finger is still down; a sub-threshold
lift resets the touch state as a tap.  Once inside scrollback, `_scrollback()`
measures drag distance against `touch_scroll_step * char_height` pixels per
step, so a continued hold-and-drag keeps scrolling mid-hold.  A quick lift
can carry into a fling using the same row-step renderer; velocity decays each
`fling_frame_ms` tick until it falls below `fling_min_velocity`.

Touch and keyboard scrollback share the same underlying `_scrollback()` loop,
so switching between Shift+-/Shift++ and touch mid-session works naturally.
After scrollback exits, touch re-entry is blocked until the screen sees one
full release, so a lift-off or retouch cannot immediately re-trigger and jump.

Constructor args (`tml_prime`): `swipe_threshold` (default 20 px) is the
minimum drag distance to register as a swipe rather than a tap;
`touch_scroll_step` (default 3 rows) is how many rows each scroll step moves
once inside scrollback; `fling_frame_ms`, `fling_min_velocity`,
`fling_decay_num`, and `fling_decay_den` tune fling timing and easing.

---

## Status bar prompt

The terminal's bottom status line shows live game state, updated after every
command and every combat/tick pulse:

```
HP:45/50 MP:12/20 38tnl> _input buffer_
```

Fields: current and max HP, current and max MP, XP remaining to next level,
then the current input buffer (right-truncated to fit).  Implemented in
`player.py:show_prompt` / `tr.set_status`.

---

## Contextual target picker

When a command (e.g. `kill`, `get`, `wear`, `practice`) is given without a
target and multiple valid targets exist, a numbered menu is presented:

```
[Target] Choose a target:
  1) large rat          (default)
  2) small snake
  0) cancel
```

The player types a digit and Enter.  Option 1 is the default and pre-selected.
Implemented in `picker.py:pick_from`; blocks until a valid choice is made.

---

## Autosave

The player's state is saved automatically every 4 world ticks (≈ 2 minutes at
the default pulse rate).  A manual `save` command is also available.  Save data
is stored in the PPL home variable `primesud_save` via `HVars`.

Interval configurable via `config.py:AUTOSAVE_TICKS`.

---

## Auto-respawn on death

On death the player is immediately returned to the starting room with 1 HP and
1 MP (wait and daze states cleared).  No corpse, no item drop, no XP penalty.
A short flavour sequence plays (`WAIT`-separated lines) before the respawn room
description is shown.

1stMud equivalent: none — 1stMud sends the player to the death room and
requires manual `recall`.
