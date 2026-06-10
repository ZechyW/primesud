# License Credits Implementation Plan

PrimeSUD derives from a four-layer MUD codebase: Diku → Merc → ROM → 1stMud.
Each layer carries license obligations. This plan records what must be done in code.

Original license files are already present in `reference/1stMud4.5.3/doc/` — no
changes needed there.

---

## Touch points

### 1. Title screen — `run_title()` in `primesud.py`

ROM and 1stMud both specify exact wording that must appear in the "login sequence".
Diku requires its creators' names there too. Append after the current banner output:

```
Based on 1stMud ROM Derivative (c) 2001-2003 by Ryan Jennings
Based on ROM 2.4 beta (c) 1993-1996 Russ Taylor
Based on Merc 2.1  (c) 1992-1993 Chastain, Quan & Tse
Based on DikuMud   (c) 1990-1991 Hammer, Seifert, Storfeldt, Madsen, Nyboe
Type 'credits' in-game for full author credits.
```

---

### 2. New `do_credits()` command — `commands.py`

Diku requires a `credits` command containing names, addresses, and a notice that
they created DikuMud. 1stMud requires an unaltered `1stMud` help/credits entry.
The addresses are from 1990–1996 and stale, but the Diku license text specifies
they must be present.

Content to print:

```
PrimeSUD — a single-user dungeon for the HP Prime
Port by ZechyW.  Not for commercial distribution.

1stMud ROM Derivative
  (c) 2001-2003 Ryan Jennings (Markanth)
  markanth@firstmud.com

ROM 2.4 beta
  (c) 1993-1996 Russ Taylor
  rtaylor@efn.org

Merc 2.1
  (c) 1992-1993 Michael Chastain  mec@shell.portal.com
                Michael Quan       michael@uclink.berkeley.edu
                Mitchell Tse       hatchet@uclink.berkeley.edu

DikuMud — creators of the original game
  (c) 1990-1991 Sebastian Hammer       quinn@freja.diku.dk
                Michael Seifert        seifert@freja.diku.dk
                Hans Henrik Storfeldt  bombman@freja.diku.dk
                Tom Madsen             noop@freja.diku.dk
                Katja Nyboe            katz@freja.diku.dk
  DIKU, Computer Science Institute, Copenhagen University
```

---

### 3. Wire `credits` into the command table — `commands.py`

- Add `("credits", do_credits)` to `_CMD_TABLE`.
- Add `credits` to the one-line cheat-sheet in `do_help()`.

---

### 4. Attribution comment block — top of `primesud.py`

Satisfies the spirit of "copyrights must remain in original source" for anyone
reading or distributing the source. One block in the entry-point file is enough.

```python
# PrimeSUD — single-user dungeon for the HP Prime
# Port by ZechyW.  Not for commercial distribution.
#
# Based on 1stMud ROM Derivative (c) 2001-2003 Ryan Jennings
# Based on ROM 2.4 beta (c) 1993-1996 Russ Taylor
# Based on Merc 2.1 (c) 1992-1993 Chastain, Quan, Tse
# Based on DikuMud (c) 1990-1991 Hammer, Seifert, Storfeldt, Madsen, Nyboe
```

---

## Coverage summary

| Requirement | How it's met |
|---|---|
| Diku names in login sequence | Title screen (item 1) |
| ROM "based on ROM 2.4 beta…" in login | Title screen (item 1) |
| 1stMud "based on 1stMud ROM Derivative…" in login | Title screen (item 1) |
| `credits` command with Diku names/addresses | `do_credits()` (item 2) |
| 1stMud help entry readable by all | `do_credits()` doubles as this (item 2) |
| Copyright notices in source | Comment block (item 4) |
| License documents retained | Already in `reference/` — no change needed |
| No commercial use | Already non-commercial — no code change needed |
| Notify ROM/Diku authors before running | Grey area for a personal calculator game; consider a courtesy email to whoever is still reachable |
