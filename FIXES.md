# FIXES.md — 1stMud bugs corrected in PrimeSUD

Bugs in the 1stMud 4.5.3 source that we correct or improve upon during the port.
Each entry references the upstream source location and describes the intended PrimeSUD fix.

---

## automap: closed-door connector symbols are unreachable dead code

**Upstream:** `reference/1stMud4.5.3/src/automap.c`, `map_exits()`, lines 161–181

### The bug

`map_exits` iterates over a room's exits and short-circuits closed ones with an early `continue`:

```c
if (IsSet(pExit->exit_info, EX_CLOSED))
    continue;   /* line 162 — skips the rest of the loop body */
```

Further down in the same loop body there is code intended to render a distinct
closed-door connector symbol from `map_chars_closed` (`I` for N/S, `=` for E/W):

```c
if (IsSet(pExit->exit_info, EX_CLOSED))
    map[exitx][exity].symbol = map_chars_closed[door];  /* UNREACHABLE */
else
    map[exitx][exity].symbol = map_chars[door];
```

Because the `continue` fires first, this branch is never reached.  Closed exits are
silently omitted from the map.  The `_FULL_LEGEND` entry `">I< Closed Doors"` at
`case 7:` in `show_map` is therefore also never visible.

### PrimeSUD fix — implemented in `automap.py`

Render the closed-door connector but do not traverse through it:

1. `_EXIT_CHAR_CLOSED = {"n": "I", "s": "I", "e": "=", "w": "="}` added alongside
   `_EXIT_CHAR` (matching `map_chars_closed[5] = "I=I="` in `automap.c`).

2. In `_map_exits`, closed exits now write `_EXIT_CHAR_CLOSED[direction]` to the
   connector cell and `continue` — the destination room is not added to the BFS
   queue, so the room behind the door stays hidden.

3. `"   I=  Closed Doors"` legend entry added to `_FULL_LEGEND` at index 7
   (between `"|-  Exits"` and `"*   Field/Forest"`); terrain entries shift to
   indices 8–16 (17 entries total).
