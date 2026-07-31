# Plural helper consolidation -- plan

Status: **not started**. Everything below is agreed but unimplemented.
Written 31 Jul 2026 for handoff to another workstation.

## Why

`quest._intstr(n, word)` (`src/quest.py`) is the port of 1stMud `intstr` and
is already the de-facto SSOT: 25 call sites across `quest.py`, `gquest.py`,
`info.py`, `update.py`. But it lives in the quest module (three other modules
import a *text* helper from it), it drops upstream's irregular-plural
branches, and it uses `str(n)` where the house rule is `num_str`. Meanwhile a
second idiom -- inline `("" if n == 1 else "s")` -- has accumulated at ~10
other sites.

## Decisions taken (do not re-litigate)

1. **Name it `count_str`, not `intstr`.** `util.int_str(n)` (digit-table
   renderer) and `intstr(n, word)` would sit one underscore apart in the same
   module with different arity and meaning. `util.int_str` is the *documented*
   pitfall-8 API (CLAUDE.md sec. Constraints item 8, `docs/BUILTINS.md`,
   `docs/PERFORMANCE.md`, `docs/PRIME_FIRMWARE_BUGS.md` x7, `TODO.md`) and is
   referenced inside frozen G1 crash write-ups -- renaming it to make room for
   the newcomer is backwards. The docstring keeps `(cf. 1stMud intstr in
   db2.c)` so the upstream mapping stays greppable.
2. **No import-cycle gain; do it for homing.** `quest.py` imports none of
   `info`/`update`/`gquest`, so no cycle exists today. All three importers
   keep their `quest` import for other symbols (`is_quester`, `quest_update`,
   `chance`, `mob_tell`, `quest_target_ok`), so the move removes zero edges.
   `util.py` imports only `gc` + `hpprime`, so it cannot create one either.
3. **Leave split-string sites inline.** Forcing them through the helper needs
   a word-only variant; that abstraction is not worth having.

## Upstream reference

`reference/1stMud4.5.3/src/db2.c:735` -- `char *intstr(long i, const char
*word)`. Four branches:

| word ends in | upstream output | our current `_intstr` |
|---|---|---|
| (i == 1) | `1 word` | same |
| `y` | strip `y`, `+ies` | `+s` -> "pennaltys" |
| `ss` | `+es` | `+s` |
| `s` (not `ss`) | unchanged (already plural) | `+s` -> "seriess" |
| else | `+s` | same |

No current call word hits the irregular branches (minute, hour, mob,
questpoint, quest point, trivia point, note, user, character, corpse), so this
is latent fidelity, not a live bug.

## Step 1 -- add `util.count_str`

New in `src/util.py` (leaf module, no game imports):

```python
def count_str(n, word):
    """Return "N word(s)", pluralising the word (cf. 1stMud intstr in db2.c). [PRIMESUD]"""
```

- number via `num_str(n)`, never `str(n)` (pitfall 8)
- port all four upstream branches
- concat only, no `%` / `.format()`
- name deliberately differs from upstream `intstr`; see decision 1

## Step 2 -- retire `quest._intstr`

Delete `src/quest.py:118` `_intstr` and repoint its 25 call sites:

- `src/quest.py` -- 10 sites (`636, 690, 921, 926, 929, 971, 1011, 1067, 1090, 1148`)
- `src/gquest.py` -- 10 sites (`212, 216, 357, 367, 371, 444, 489, 499, 521, 532`);
  keep the `[PRIMESUD] 1stMud intstr(..., "minute") slip fixed to "mob"`
  comment at `518`
- `src/info.py` -- `1137, 1138, 1175, 1176`; drop `_intstr` from the
  `from quest import is_quester, _intstr` at line 31 (import stays for
  `is_quester`)
- `src/update.py` -- `104`; drop `_intstr` from line 23 (import stays for
  `quest_update`)

## Step 3 -- convert adjacent inline ternaries

Only where the count and the word are adjacent in the output string:

- `src/path.py` -- `do_path`, the "Shortest path to X is N step(s): route."
  line (already singular-correct as of this commit, converts cleanly)
- `src/movement.py` -- `do_run` picker label, `"{C" + name + "{x (N step(s))"`
- `src/combat.py:2874, 2876, 3015` -- experience point(s), practice(s)
- `src/training.py:69, 152, 698` -- training session(s), practice session(s),
  train(s)

Keep the existing `[PRIMESUD] singular/plural fix` comments -- upstream always
printed the plural form at these sites.

### Do NOT convert

- `src/system_cmds.py:50` -- `"{R hour"`: a colour code sits between the
  number and the word
- `src/shop.py:551` -- plural keys off `cost`, not off the adjacent number

## Verification

```
python -m pytest -q
python tools/check_ascii_py.py
```

Existing assertions that pin the wording: `tests/test_path.py` (steps
messages). Grep for `" steps"`, `"sessions"`, `"points"` in `tests/` before
assuming a rename is invisible.

Add one test for `count_str` covering the four branches -- it is a parser-ish
branch, so it needs its own check; the call-site conversions are covered by
existing tests.

## Bookkeeping

- No `docs/FIXES.md` entry: existing singular/plural fixes have none either --
  that file tracks behavioural deviations, not linguistic slips.
- No `FEATURES.md` entry: not player-facing beyond wording.
- Delete this file when the work lands (completed plans are deleted, not
  archived -- CLAUDE.md sec. Documentation map).
