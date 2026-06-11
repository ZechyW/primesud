# Score Screen — Planned Additions

## 1. Position (easy, no new infrastructure)

**1stMud source:** `flag_string(position_flags, ch->position)` — displayed in col 1 of segment 2, row after "To Lvl".

**PrimeSUD approach:** Derive from `player['fighting']`:
- `"Fighting"` if `player['fighting'] is not None`
- `"Standing"` otherwise (resting/sleeping can be added later when those states exist)

Add as a new `_val`-style entry in segment 2 col 1, using the existing `bright=True` `_val` call pattern.

---

## 2. Hours + Age (requires new playtime infrastructure)

**1stMud source** (`handler.c` / `act_info.c`):
```c
// Hours (real playtime):
hours = (ch->pcdata->played + (int)(current_time - ch->logon)) / HOUR;
// HOUR = 3600 seconds

// Age (derived, starts at 17):
age = 17 + (ch->pcdata->played + (int)(current_time - ch->logon)) / (20 * HOUR);
// +1 year per 20 real hours played
```

**New fields needed in player dict:**
- `player['played']` — cumulative playtime in seconds (persisted via `save_char` in `player.py`)
- Default: `0`

**New tracking needed in `primesud.py`:**
- Record `_logon_ticks = int(ppleval("Ticks"))` at game start (in `Game.__init__` or `run_title`)
- Session seconds = `(int(ppleval("Ticks")) - _logon_ticks) // 1000`
- Accumulate into `player['played']` on save and on clean exit

**Score display:**
- `hours = (player['played'] + session_secs) // 3600`
- `age   = 17 + (player['played'] + session_secs) // 72000`
- Both shown in col 2 of segment 2 via `_val(..., bright=True)`

**Files to touch:** `player.py` (default dict, `save_char`), `primesud.py` (`Game.__init__`, save/quit path), `commands.py` (`do_score` — pass session seconds in somehow, or compute via a helper).
