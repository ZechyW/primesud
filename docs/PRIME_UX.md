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

Digit keys `0`–`9`, the decimal key, and ten function keys act as one-key
shortcuts that load a command into the input buffer when it is empty (not
auto-submitted — the player still presses Enter, allowing arguments to be
appended first).  With a non-empty buffer, digits and the decimal key type
normally, so numeric arguments still work.

Default bindings live in `config.py` (`DEFAULT_MACROS` for digits and the
decimal key, `DEFAULT_FNKEY_MACROS` for the two function-key rows above the
numpad) — see that file for the current mapping, or `macro` in-game.

Bindings are live-editable with the `macro` command:

```
macro             — show current bindings in a grid layout
macro <key> <cmd> — bind key (digit, `.`, or fn-key name) to command
macro <key>       — show the full binding without changing it
macro unset <key> — clear binding
macro default     — restore all defaults
```

The overview follows the physical keypad, with fixed keys shown dim. Long
commands are truncated with `...`; `macro <key>` shows the full command.
The dim `/` key has `[Recall]` beneath it; `/` is a built-in, non-configurable
alias for `recall`. The dim `On` key similarly has `[Exit]` beneath it and is
not configurable: the calculator raises `KeyboardInterrupt` when it is
pressed, which exits PrimeSUD.

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
command and every combat, regen, or world-tick pulse:

```
HP:45/50 MP:12/20 38tnl> _input buffer_
```

Fields: current and max HP, current and max MP, XP remaining to next level,
then the current input buffer (right-truncated to fit).  Implemented in
`player.py:show_prompt` / `tr.set_status`.

---

## Contextual target picker

When a command (e.g. `kill`, `get`, `give`, `wear`, `practice`, `buy`, `sell`)
is given without a target and multiple valid targets exist, a numbered menu
is presented:

```
[Target] Choose a target:
  1) large rat          (default)
  2) small snake
  0) cancel
```

The player types a digit and Enter.  Option 1 is the default and pre-selected.
For bare `give`, the first picker includes carried items and available silver
or gold. Choosing coins prompts for the amount, then the recipient picker.
Bare `buy` lists visible shop stock with level, price, and quantity; pet shops
list pets with level and price. Bare `sell` lists only carried items the
shopkeeper accepts, with the offered price; multi-item `drop`, `wear`, and
`sell` pickers include an `[all]` choice. Typed forms remain available for bulk
purchases and custom pet names. Bare `wear` also offers `[best] Equip strongest
gear`, equivalent to `wear best`, and is the only picker to carry it. Bare
`quest` shows status directly away from a questmaster; at one, it opens a
contextual action picker for status, request/completion, giving up, and the
quest shop. Quest and global-quest action
labels include their equivalent typed command in brackets. Buy, sell, and
identify open item pickers with quest-point prices. A completed quest cannot be
accidentally abandoned: `quest quit` completes it instead when its reward is
ready (including the carried-token check for retrieval quests). Practice
picker entries put the highest current proficiency first. Bare `gquest`
shows the next-event countdown when no global quest is running. During one,
it opens a contextual picker for information, remaining targets, joining,
completion, or giving up as each becomes valid. A completed global quest
cannot be accidentally abandoned: `gquest quit` completes it instead.
Implemented in `picker.py:pick_from`; blocks until a valid choice is made.

---

## Gear score and `wear best`

`compare` reports a numerical gear score for equipment sharing a wear slot.
The balanced combat heuristic includes player-scaled weapon damage, all four
base armor values, template and runtime numeric modifiers, equipment affects,
resistance flags, and implemented weapon procs. Positive base armor protects
because equip subtracts it from AC; negative `ac` modifiers protect because
affect application adds them to all four AC buckets. Negative saving-throw
modifiers are likewise beneficial. Unknown or mechanically inert flags score
zero.

`wear best` compares visible, level-appropriate, alignment-compatible inventory
items against each occupied slot. It replaces only strict upgrades, keeps worn
items on ties, fills paired finger/neck/wrist slots independently, and preserves
`noremove` gear. Hand slots (wield/secondary/shield/hold) are optimized as one
layout: every legal combination -- weapon and shield, two-handed, dual wield,
held item -- is scored under the normal equip rules (noremove locks, small-size
two-handed vs shield conflict, secondary weight rules, STR wield limit evaluated
after the whole swap) and the best combined layout wins if it strictly beats the
current hands.

---

## Help browser

Typing a help keyword means alpha-shifting every letter, so bare `help` opens
a two-level picker instead of printing the command summary and stopping:

```
[Help] Help: pick a category
  1) summary (one-page command overview)   (default)
  2) creation (38 helps)
  3) commands (85 helps)
  4) skills (15 helps)
  ...
```

The category set is `[PRIMESUD]`: upstream's eight are half unusable as menu
rows -- a 50-entry `unknown` bucket, two single-entry categories, and 23 helps
for the unported OLC editor.  `info.py:HELP_CATEGORIES` lists the rebalanced
set; the eight a mortal sees (`creation`, `commands`, `skills`, `spells`,
`combat`, `world`, `interface`, `credits`) fit one picker page with `summary`.

Helps for systems PrimeSUD does not port -- OLC, clans, deities, immortal
powers, plus the two upstream `GREETING` entries nothing reads -- stay in
`help.txt` at level 51, above any reachable player level.  They never surface
in a menu and never match a keyword lookup, but survive intact if the system
lands.  `index` applies the same filter to its category listing and numbers it
gap-free, so `index <n>` always names a category the player can read.

Picking a category opens its entries, ten per page (`+`/`-` to page); picking
an entry prints it through the pager and returns to the entry menu at the page
it was picked from, so reading several entries in a row costs no re-paging.
Esc steps back one level: entry menu to category menu, category menu to the
prompt.  Option 1 of the category menu is `summary`, so `help` followed by
Enter reproduces 1stMud's bare-`help` output in one keypress.

Entries are filtered by player level and listed in `help.txt` order — the same
filter and order `index` uses — so menu position N is the number
`index <category> N` takes.

`help <letter>` uses the same picker.  Upstream prints a numbered
three-column list of every entry with a keyword starting with that letter,
which the player can only act on by retyping `help <n>.<word>` with enough
letters to leave list mode — a dead end on the calculator keypad.  The picker
opens any match directly and returns to the list afterwards, same as the
category menus.

Every other argument form is unchanged; `do_help` (`info.py`) branches to the
browser only when called with no arguments.

---

## Autoskill rotation editor

`autoskill edit` opens a blocking editor for the automatic combat rotation
(see DESIGN.md "Autoskill combat automation" for the engine policy):

```
Autoskill rotation
[Up/Dn] sel  [+/-] move  [*] on/off  [Enter] save  [Esc] cancel
  1) blindness 75%
  2) fireball 52% (off)
  3) bash 100%
  4) trip 88% (new)
```

The list prints once through the normal scroll path; the cursor lives in the
status line (`> 2) fireball (off)  [2/4]`), updated in place, so navpad
navigation produces zero scroll spam — only reordering (`+`/`-`) and
include/exclude toggling (`*`) reprint the list.  Digits jump to a row
(picker-style 1–9 then 0, per block of ten).  Enter saves the custom
rotation; Esc discards.  `(off)` marks excluded entries, `(new)` marks
newly learned entries not yet in a saved rotation.

The navpad Up/Down keys (bits 2/12, normally n/s movement in the game loop)
are remapped for the editor by passing a private `key_commands` dict to
`tml_prime.poll_char` — no changes to the tml key map.

---

## Streaming output reveal

All multi-row output — room looks, combat rounds, help/pager pages, the
greeting — streams onto the screen one text row at a time at
`config.py:REVEAL_MS_PER_LINE` (25 ms/row, tuned on device 30/07/2026;
0 disables).  The first row of a burst is instant; cadence is time-based
and shared across calls, so consecutive bursts hold rhythm instead of
doubling rows at burst boundaries.

Pressing any key during a reveal latches pacing off: the remainder blits
instantly and the key is kept as pending input, so type-to-skip never
eats a keystroke.  The latch holds until the prompt returns (any
`set_status` call re-arms the first-row-instant rule).

`config.py:REVEAL_MS_PER_CHAR` (default 0/off) adds left-to-right
per-character streaming within each revealed row on top.

---

## Autosave

The player's state is saved automatically every 4 world ticks (≈ 2 minutes at
the default pulse rate).  A manual `save` command is also available.  Save data
is stored in the PPL home variable `primesud_save` via `HVars`.

While the player is fighting, due autosaves (and after-kill saves) are
deferred and merged into one save on the first non-fighting pulse, so the
~0.9 s save stall never lands mid-combat.  Mob HP and fight state never
persist anyway, so nothing of value is lost by waiting.

Interval configurable via `config.py:AUTOSAVE_TICKS`.

---

## Auto-respawn on death

On death the player is immediately returned to the starting room with 1 HP and
1 MP (wait and daze states cleared).  No corpse, no item drop, no XP penalty.
A short flavour sequence plays (`WAIT`-separated lines) before the respawn room
description is shown.

1stMud equivalent: none — 1stMud sends the player to the death room and
requires manual `recall`.
