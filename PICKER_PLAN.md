# Contextual Picker — Implementation Plan

## Goal

When a command requires a target argument and none was supplied, show a numbered
list of valid options (mobs, items, spells, …).  The player presses a digit key
to choose a number, then **Enter** to confirm.  Backspace and re-entry work
normally before Enter, preventing accidental selection.

### Example

```
kill
  Kill whom?
  1) a small rat
  2) a grey guard
  3) a grey guard
  0) cancel
> 2_
```

Player types **2**, presses Enter → fight starts.  Typo?  Backspace and retype.

---

## Architecture decision

**Blocking inline picker using `tr.input()`** — `pick_from()` is called
synchronously inside a command handler.  It prints the numbered list, then calls
`tr.input()` for a one-line response, validates the digit, and returns the
0-based index (or -1 for cancel / empty input).

Why `tr.input()` instead of raw keypress polling?
- Enter confirmation prevents erroneous selection on hardware — explicit user intent.
- `tr.input()` already handles cursor display, backspace, alpha/shift state on the
  HP Prime; no need to reimplement.
- Commands already block the game loop while running; the extra blocking call adds
  no new architectural complexity.
- Invalid input (non-digit, out-of-range) can loop with a re-prompt rather than
  silently ignoring the keypress.

---

## Module: `picker.py`

New file `primesud.hpappdir/picker.py`.

### API

```python
def pick_from(tr, title, options):
    """Display a numbered list and read a digit + Enter to select.

    Prints `title`, then up to 9 options numbered 1–9, then "0) cancel".
    Calls tr.input() for each attempt; re-prompts on invalid input.

    Args:
        tr: tml renderer instance.
        title (str): Header line, plain text — colour wrapping applied internally.
        options (list[str]): Display strings.  At most 9 are shown.

    Returns:
        int: 0-based index of the selected option, or -1 if cancelled.
    """
```

**Notes:**
- `tr.input(prompt=…)` blocks until Enter; no extra keyboard code needed.
- Only `raw[0]` is inspected — typing "2foo" still selects option 2.
- Empty input (bare Enter) defaults to option 1.
- Re-prompts on out-of-range or non-digit input rather than silently looping.
- Side-effect-free: does not mutate `player`, `room_state`, or `mob_instances`.

---

## Trigger pattern for commands

All commands follow the same guard:

```python
from picker import pick_from

def do_kill(tr, player, args, room_state, mob_instances):
    rs = room_state[player["room"]]
    live = [i for i in rs["mobs"] if mob_instances[i]["state"] != "dead"]

    if not live:
        tr.print("There is nobody here to fight.")
        return

    if args:
        target_id = get_char_room(args[0], live, mob_instances)
        if target_id is None:
            tr.print("They are not here.")
            return
    else:
        names = [mob_instances[i]["name"] for i in live]
        idx = pick_from(tr, "Kill whom?", names)
        if idx < 0:
            return
        target_id = live[idx]

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
| ☐ | `do_get` | `Pick up what?` | items on ground in current room |
| ☐ | `do_drop` | `Drop what?` | items in player inventory |
| ☐ | `do_wear` | `Wear what?` | equippable items in inventory (has a non-`take` `wear_flags` entry) |
| ☐ | `do_remove` | `Remove what?` | occupied equipment slots |
| ☐ | `do_cast` | `Cast which spell?` | spells in `SKILL_TABLE` where `player["learned"][vnum] > 0` |
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

Terminal is 64 cols × 24 rows.  Picker uses `2 + len(shown) + 1` lines (title +
options + cancel hint).  Maximum 9 options → 11 lines + 1 for the `> ` prompt
= 12 total.  Leaves at least 12 lines of prior game output visible above.

If more than 9 targets exist, show the first 9 and a `... (N more not shown)` line.
Pagination is out of scope for Phase 1.

---

## Edge cases to verify

- **0 targets** — no picker; existing "nothing here" error message shown.
- **1 target** — picker shown with single option labelled `(default)`; bare Enter selects it; `0` cancels.
- **Exactly 9 targets** — all shown, no truncation line.
- **10+ targets** — truncation line appears; pressing 9 selects the 9th shown item.
- **Empty Enter** — selects option 1 (the default); explicit `0` required to cancel.
- **Out-of-range digit** (e.g. "5" when only 3 shown) — re-prompts with valid range hint.
- **Non-digit input** — re-prompts; player can type `0` to cancel after a mistake.
- **Player already in combat** presses a picker command — picker still works.
  All pulse processing (`violence_update`, `world_tick`, `area_update`) runs in the
  main loop *after* `interpret()` returns.  HP Prime has no threading, so while
  `tr.input()` blocks inside `pick_from()` the entire loop is paused: no mob
  attacks, no regen, no area resets.  This is intentional — the player has
  unlimited time to read and choose, same as any other slow command.

---

## Open questions

1. **Truncation strategy** — "first 9" is the simplest rule, but for `do_get` in a
   cluttered room "most recently dropped" or "alphabetical" might be more useful.
   Decide at integration time based on what the option list naturally produces.
