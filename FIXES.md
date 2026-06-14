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

---

## look / automap: paragraph breaks preserved when condensing room descriptions

**Upstream:** `reference/1stMud4.5.3/src/automap.c`, `erase_new_lines()`, lines 197–236;
also called via `dwrap()` in `reference/1stMud4.5.3/src/h/descriptor.h`, line 252.

### The bug

`erase_new_lines` processes a room description in two passes:

1. Replace every `\n` and `\r` with a space (`\x20`), treating single newlines and
   paragraph-break double-newlines identically.
2. Collapse any run of two or more consecutive spaces into a single space.

The result is a single flat paragraph — all intentional blank-line paragraph breaks
(`\n\n`) are silently destroyed along with ordinary soft-wrap newlines.

### PrimeSUD fix — implemented in `_wrap_paragraphs` in `commands.py`

`_wrap_paragraphs` distinguishes between structural paragraph breaks and
within-paragraph whitespace:

1. Split on `\n\n` to separate paragraphs.
2. Within each paragraph, collapse all whitespace (including embedded single `\n`)
   via `' '.join(para.split())` — equivalent to 1stMud's space-collapse pass but
   scoped to one paragraph.
3. Word-wrap each paragraph to the target width and join the resulting lines.
4. Insert a blank line between adjacent paragraphs in the output.

This preserves the visual structure that area authors encoded with double newlines
while still removing the soft-wrap artifacts that `.are` files embed.
