# Contextual Picker — Implementation Plan

## Goal

When a command requires a target argument and none was supplied, show a numbered
list of valid options (mobs, items, spells, …).  The player presses a digit key
to choose a number, then **Enter** to confirm.  Single-key actions (Esc, +, -)
take effect immediately without Enter.

### Example

```
kill
  Kill whom?
  1) a small rat  (default)
  2) a grey guard
  3) a grey guard
  [Esc] cancel
: 2_
```

Multi-page example:

```
  Pick up what?
  1) a longsword  (default)
  ...
  0) a dagger
  Page 1/3  [+] next  [-] prev  [Esc] cancel
: _
```

Player types **2**, presses Enter → fight starts.  Bare Enter selects item 1.
Typo?  Backspace and retype.  Press **Esc** at any point to cancel immediately.

---

## Architecture decision

**`read_key()`-based picker with two-key confirm for digits** — `pick_from()`
calls `tr.read_key()` in a loop, acting on each keypress directly:

| Input | Effect |
|-------|--------|
| `Esc` (`'\e'`) | Cancel immediately; return -1 |
| `+` | Advance to next page (single key, no Enter) |
| `-` | Retreat to previous page (single key, no Enter) |
| `0`–`9` | Echo digit, enter CONFIRM state |
| `Enter` in CONFIRM | Validate and return selection |
| `Backspace` in CONFIRM | Erase digit, return to FIRST_KEY state |
| `Esc` in CONFIRM | Cancel immediately; return -1 |
| Other | Ignore |

Why `read_key()` instead of `tr.input()`?
- `tr.input()` intercepts `'\e'` internally (clears the line) — Esc never
  surfaces to `pick_from()`, making immediate cancel impossible.
- `read_key()` exposes raw characters, enabling single-key actions for Esc,
  `+`, `-` while still requiring Enter to confirm a digit selection.
- Enter confirmation on digit selection retains the hardware-safety property:
  accidental number key press does not immediately execute a command.
- Commands already block the game loop while running; `read_key()` blocks
  identically to `tr.input()` — no new architectural complexity.

---

## Module: `picker.py`

File: `primesud.hpappdir/picker.py`.

### API

```python
def pick_from(tr, title, options):
    """Display a numbered list and read digit+Enter to select, or Esc to cancel.

    Prints title, then up to 10 options numbered 0-9 per page.
    Uses tr.read_key() directly: Esc and +/- act on single keypress;
    digit selection requires Enter to confirm.

    Args:
        tr: tml renderer instance.
        title (str): Header line, plain text — colour wrapping applied internally.
        options (list[str]): Display strings.

    Returns:
        int: 0-based index of the selected option, or -1 if cancelled.
    """
```

**State machine:**

```
FIRST_KEY:
    char = tr.read_key()
    '\e'    → return -1
    '+'     → page = min(page+1, max_page); rerender; FIRST_KEY
    '-'     → page = max(page-1, 0);        rerender; FIRST_KEY
    '\n'    → return page*10 + 0  (bare Enter = select item 1, i.e. page-offset 0)
    '1'-'9' → page_idx = int(char) - 1; echo digit; CONFIRM
    '0'     → page_idx = 9;              echo digit; CONFIRM
    other   → ignore; FIRST_KEY

CONFIRM:
    char = tr.read_key()
    '\n'    → absolute_idx = page*10 + page_idx
               if absolute_idx < len(options): return absolute_idx
               else: reprint range hint; FIRST_KEY
    '\b'    → erase digit; reprint prompt; FIRST_KEY
    '\e'    → return -1
    other   → ignore; CONFIRM
```

Digit → page-local index mapping: `1`→0, `2`→1, … `9`→8, `0`→9.

**Notes:**
- `_MAX_OPTS = 10` (labels 1–9 then 0).
- Item 1 labelled `(default)`; bare Enter in FIRST_KEY selects it.
- Side-effect-free: does not mutate `player`, `room_state`, or `mob_instances`.
- Scrollback (`Shift+-`) still works from within FIRST_KEY: `read_key()`
  delegates to `tml_prime.read_key()` which handles `_SB_UP` transparently
  before returning the forwarded key.

---

## Pagination

When `len(options) > 10`:
- Page N shows items `[N*10 : N*10+10]`.
- Single-page footer: `{w[Esc] cancel{x`
- Multi-page footer:  `{w[+] next  [-] prev  [Esc] cancel{x`
- `+` on last page: no-op.
- `-` on page 0: no-op.
- Page indicator: `{wPage N/M{x` on same line before the key hints when M > 1.

---

## Trigger pattern for commands

All commands follow the same guard:

```python
from picker import pick_from

def do_kill(tr, player, args, world):
    rs = world["rooms"][player["room"]]
    live = [i for i in rs["mobs"] if world["mobs"][i]["state"] != "dead"]

    if not live:
        tr.print("There is nobody here to fight.")
        return

    if args:
        mob_id = get_char_room(args[0], live, world["mobs"])
        if mob_id is None:
            tr.print("They are not here.")
            return
    else:
        names = [MOB_TEMPLATES[world["mobs"][i]["tpl"]]["short_descr"] for i in live]
        idx = pick_from(tr, "Kill whom?", names)
        if idx < 0:
            return
        mob_id = live[idx]

    # … existing kill logic …
```

Conventions:
- **Always show the picker** when no argument was supplied, even for a single option —
  prevents accidental action from a mispress.
- If **no** valid targets exist, print the normal error message.
- If the player already typed an argument (`kill rat`), use the existing fuzzy-match
  path; the picker is never shown.

---

## Commands to update (Phase 1)

Picker titles are plain text — `pick_from` wraps them in `{Y...{x` internally.

| Done | Command | Picker title (plain) | Option source |
|------|---------|---------------------|---------------|
| ✅ | `do_kill` | `Kill whom?` | live mobs in current room |
| ✅ | `do_open` | `Open which door?` | `isdoor`+`closed` exits in current room |
| ✅ | `do_close` | `Close which door?` | `isdoor`+open exits in current room |
| ✅ | `do_get` | `Pick up what?` | items on ground in current room |
| ✅ | `do_drop` | `Drop what?` | items in player inventory |
| ✅ | `do_wear` | `Wear what?` | equippable items in inventory (has a non-`take` `wear_flags` entry) |
| ✅ | `do_remove` | `Remove what?` | occupied equipment slots |
| ✅ | `do_cast` | `Cast which spell?` | spells in `SKILL_TABLE` where `player["learned"][vnum] > 0` |
| ✅ | `do_practice` | `Practice which skill?` | skills where `0 < pct < _PRACTICE_CAP (75)`, teacher mob required |
| ✅ | `do_train` | `Train which stat?` | stats where `player[stat] < 25`, trainer mob required (already enforced) |

Note: no `do_wield` — `do_wear` handles all equipment.

**`do_practice` branching** (verified against 1stMud `act_info.c`):
- No args + **no teacher in room** → show skills list + practice count (1stMud parity, no picker).
- No args + **teacher in room** → picker of under-cap skills `[PRIMESUD]`.
- With arg → fuzzy-match + practice (existing path, teacher required).

**`do_train` branching** (verified against 1stMud `act_move.c`):
- Trainer required for all cases (already enforced before the no-arg branch).
- No args → picker of trainable stats (replaces text list).
- With arg → train that stat (existing path).

Phase 2 (if needed):
- `do_use` — usable items in inventory
- `do_give` — two-step: item picker, then mob picker
- Combat special moves (if `do_bash`/`do_kick` etc. added later)

---

## Display budget

Terminal is 64 cols × 22 rows (usable, excluding status bar).  Picker uses
`1 + len(shown) + 1` lines (title + options + footer).  Maximum 10 options →
12 lines + 1 for the `: ` prompt = 13 total.  Leaves at least 9 lines of prior
game output visible above.

---

## Edge cases to verify

- **0 targets** — no picker; existing "nothing here" error message shown.
- **1 target** — picker shown with single option `1) … (default)`; bare Enter selects it.
- **Exactly 10 targets** — all shown on one page, single-page footer `[Esc] cancel`.
- **11+ targets** — multi-page footer; `+` on last page is no-op.
- **Out-of-range digit** (e.g. `5` when only 3 shown on page) — re-prompt with range hint.
- **Bare Enter in FIRST_KEY** — selects item 1 (page-offset 0) immediately; no CONFIRM step.
- **Digit then non-Enter/Backspace/Esc** — ignored; stay in CONFIRM.
- **Esc before digit** — cancel immediately.
- **Esc after digit** — cancel immediately (digit discarded).
- **Backspace in FIRST_KEY** — no-op.
- **`+`/`-` on single-page picker** — no-op (page clamp).
- **Player already in combat** presses a picker command — picker still works.
  All pulse processing (`violence_update`, `world_tick`, `area_update`) runs in the
  main loop *after* `interpret()` returns.  HP Prime has no threading, so while
  `read_key()` blocks inside `pick_from()` the entire loop is paused: no mob
  attacks, no regen, no area resets.  This is intentional — the player has
  unlimited time to read and choose, same as any other slow command.

---

## Resolved decisions

1. **`+` on last page** — no-op. Simple; no wrap.
2. **`do_get` order** — reverse of `rs["items"]` (newest-first).
   Most recently dropped item appears as `1) (default)` — bare Enter picks it up.
