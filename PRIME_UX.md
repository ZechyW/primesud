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

## Digit macros

Digit keys `0`–`9` act as one-key shortcuts that load a command into the input
buffer (not auto-submitted — the player still presses Enter, allowing arguments
to be appended first).

Default bindings (`config.py:DEFAULT_MACROS`):

| Key | Command   |
|-----|-----------|
| 7   | `kill`    |
| 8   | `flee`    |
| 4   | `open`    |
| 5   | `get`     |
| 6   | `wear`    |
| 1   | `score`   |
| 2   | `practice`|
| 3   | `train`   |
| 0   | `macro`   |

Bindings are live-editable with the `macro` command:

```
macro               — show current bindings in a grid layout
macro <digit> <cmd> — bind digit to command
macro <digit>       — clear binding
```

The mapping lives in `commands.py:_MACRO_SUBST` (initialised from
`DEFAULT_MACROS`).  Changes are session-only; defaults are restored on restart.

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
