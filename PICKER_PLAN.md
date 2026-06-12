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

| Done | Command | Picker title | Option source |
|------|---------|-------------|---------------|
| ✅ | `do_kill` | `{YKill whom?{x` | live mobs in current room |
| ✅ | `do_open` | `{YOpen which door?{x` | `isdoor`+`closed` exits in current room |
| ✅ | `do_close` | `{YClose which door?{x` | `isdoor`+open exits in current room |
| ☐ | `do_get` | `{YPick up what?{x` | items on ground in current room |
| ☐ | `do_drop` | `{YDrop what?{x` | items in player inventory |
| ☐ | `do_wear` | `{YWear what?{x` | equippable items in inventory (has `"slot"` key) |
| ☐ | `do_remove` | `{YRemove what?{x` | occupied equipment slots |
| ☐ | `do_cast` | `{YCast which spell?{x` | spells in `SKILL_TABLE` where `player["learned"][vnum] > 0` |

Note: no `do_wield` — `do_wear` handles all equipment.

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

## Implementation checklist

- [x] Create `picker.py` — `pick_from()` with colour list, plain-text prompt, re-prompt on empty/invalid
- [x] Add `from picker import pick_from` to `commands.py`
- [x] `do_kill` — picker when no args and 2+ live mobs; auto-select for single mob
  - [ ] Smoke-test: 2+ mobs in room → picker appears; pick valid number → combat starts
  - [ ] Smoke-test: single mob → no picker, auto-starts combat
  - [ ] Smoke-test: `kill rat` with 2+ mobs → fuzzy-match, no picker
  - [ ] Smoke-test: `0` in picker → cancels, no combat
  - [ ] Smoke-test: bare Enter → re-prompts; out-of-range digit → re-prompts
- [ ] `do_get` — picker when no args and 2+ floor items; auto-pick for single item
  - [ ] Smoke-test: multiple items on ground → pick one; single item → auto-picks; `get sword` → fuzzy-matches
- [ ] `do_drop` — picker when no args and 2+ inventory items; auto-drop for single item
  - [ ] Smoke-test: 3 inventory items → picker; cancel with 0; typed arg bypasses picker
- [ ] `do_wear` — picker filtered to items with a `"slot"` key and not already equipped
  - [ ] Smoke-test: mix of equippable and non-equippable in inventory
- [ ] `do_remove` — picker over occupied equipment slots; show as "slot: item name"
  - [ ] Smoke-test: multiple slots equipped; single slot → auto-removes; nothing equipped → existing error
- [ ] `do_cast` — picker over spells where `player["learned"][vnum] > 0`
  - [ ] Confirm `player["learned"]` dict shape in `player.py: create_char` before coding
  - [ ] Smoke-test: 2+ known spells → picker; 1 known spell → auto-casts; no known spells → existing error
- [ ] Final pass: confirm typed arguments bypass picker for all updated commands

---

## Edge cases to verify

- **0 or 1 targets** — picker never shown; existing code path runs unchanged.
- **Exactly 9 targets** — all shown, no truncation line.
- **10+ targets** — truncation line appears; pressing 9 selects the 9th shown item.
- **Empty Enter** — re-prompts (does not cancel; requires explicit `0`).
- **Out-of-range digit** (e.g. "5" when only 3 shown) — re-prompts.
- **Non-digit input** — re-prompts; player can type `0` to cancel after a mistake.
- **Player already in combat** presses a picker command — picker still works.
  All pulse processing (`violence_update`, `world_tick`, `area_update`) runs in the
  main loop *after* `interpret()` returns.  HP Prime has no threading, so while
  `tr.input()` blocks inside `pick_from()` the entire loop is paused: no mob
  attacks, no regen, no area resets.  This is intentional — the player has
  unlimited time to read and choose, same as any other slow command.

---

## Open questions

1. **`do_cast` skill dict shape** — need to check `player["learned"]` structure to
   build the spell-name list correctly.  `create_char` in `player.py` and the
   `do_cast` body in `commands.py` are the primary references.
2. ~~**`tr.input()` prompt display**~~ — **resolved**: `tr.input()` calls the original
   `tml.print()` which does not process colour codes.  Use plain text for the prompt;
   colour the list rows via `tr.print()` instead.
3. **Truncation strategy** — "first 9" is the simplest rule, but for `do_get` in a
   cluttered room "most recently dropped" or "alphabetical" might be more useful.
   Decide at integration time based on what the option list naturally produces.

---

## Files touched

| File | Change |
|------|--------|
| `primesud.hpappdir/picker.py` | **New** — `pick_from()` |
| `primesud.hpappdir/commands.py` | Import `pick_from`; update 6 commands (no `do_wield`) |
| No changes to `tml.py`, `player.py`, `config.py` | |
