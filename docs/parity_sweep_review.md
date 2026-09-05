# Review of the act_obj / handler / update parity sweep

Companion to `docs/parity_sweep.md`. Written 05/09/2026 by a reviewing agent.

**Orientation.** Commit `7d26957` holds the sweep and its five code changes,
exactly as authored. The follow-up fixes described below are left **uncommitted
in the working tree** so they can be read as a diff against that commit:

```
git show 7d26957 --stat     # the sweep's own changes
git diff                    # this review's follow-up fixes
```

The sweep's `[fixed 2026-09-05]` row annotations refer to `7d26957`.

---

## What the sweep did

A read-only parity pass over `act_obj.c`, `handler.c` and `update.c` (142
functions) against the Python port, written to `docs/parity_sweep.md`, plus five
code changes for the gaps it found:

1. `get_obj_weight` -- scale contents by the container's weight multiplier
   (`handler.c:2292`, `WeightMult` in `macro.h:373`).
2. `get_true_weight` -- new function, used by `do_put`'s capacity check
   (`act_obj.c:409-411`).
3. `can_carry_n` / `can_carry_w` -- `ACT_PET` flat caps of 100 items and 1000
   tenths of lbs (`handler.c:806-818`).
4. `_tick_affects` -- the 1-in-5 per-tick affect level fade
   (`update.c:648-651`).
5. `do_get` -- strip a bare `from` token (`act_obj.c:193-194`).

Plus the accompanying tests and an `AGENTS.md` note about the Docker sandbox
venv.

## What was verified and kept

Changes 1, 2 and 4 are faithful and were left untouched.

**Weight multiplier.** C guards the multiplier with
`item_type == ITEM_CONTAINER`; the Python has no type guard, it reads
`container_weight_mult` with a default of 100. That is equivalent *because of
the data*: `tools/are_to_primesud.py` writes the key only inside its container
branch, so corpses, pits and every non-container default to 100. The converted
area files were checked -- 67 items carry the key, with values 0, 20, 25, 50,
75, 80, 90 and 100. Nesting matches C as well: the parent's multiplier applies
to the child's recursive total, and the child applies its own multiplier to its
own contents. `get_true_weight` correctly omits the multiplier for the object
itself while keeping it for nested containers.

**`do_put`.** The port already carried C's `WeightMult(obj) != 100` "bad idea"
guard, so moving the container side to `get_true_weight` did not open a nesting
exploit.

**Affect decay.** Correctly positioned in the loop -- upstream runs the affect
loop before the plague and poison blocks, so the decay does land before the
damage read, which is what the adjusted `test_regen.py` expectations assume.
`randint(0, 4)` is inclusive, matching `number_range(0, 4)`, consistent with the
existing `randint(0, 1)` and `randint(0, 15)` sites. Every char-affect
constructor in `src/` sets `level`, so the bare `aff["level"]` subscript is
safe.

The evidence quality in `parity_sweep.md` is why this review was cheap: every
row carries both C and Python file:line references. Keep doing that.

## What the follow-up changed

### 1. Reverted the pet carry caps, tagged `[PRIMESUD]`

By the user's decision. The caps are an anti-mule measure: in a MUD, a player
parks gear on a pet that another player's character can then reach.
Single-player has nobody to share with, so the cap only shrinks a legitimate
pet -- from roughly 750 lbs down to 100 lbs, which would have made `give` to a
pet start refusing loads that used to fit.

Both functions now carry a `[PRIMESUD]` docstring note naming the upstream
behaviour, its line number, and the reason it was dropped. A one-liner was added
to `FEATURES.md` under "Balance and quality of life" -- house rule: a notable
player-facing deviation needs the tag *and* the index line, in the same commit.

Without the caps, pets fall through to the ordinary formulas:
`20 + 2*dex + level` for item count, and
`STR_APP_CARRY[str] * 10 + level * 25` tenths of lbs for weight. NPC stats come
from `mob._stat_from_level` (`min(25, 11 + level // 4)`) plus the class, off and
size deltas, clamped to [3, 30]. A level-10 pet therefore gets 46 items and
155 lbs; a level-40 pet gets 66 items and 400 lbs. The limit scales with the
pet, which fits the existing "growing and evolving pets" feature.

### 2. Fixed the degenerate case of the `from` strip

The original strip was `if args[1] == "from": cont_arg = " ".join(args[2:])`,
placed inside the container branch. For `get sword from` that yields an empty
container argument, the container lookup fails, and control falls through to a
room lookup of the *unstripped* `"sword from"` -- so the command dies with
"I see no sword from here."

C does not behave that way. `one_argument` overwrites `arg2` with the next word,
which for `get sword from` is empty, and the empty-`arg2` branch is the plain
room get (`act_obj.c:193-196, 205`). Upstream picks the sword up.

The strip now sits above `arg = " ".join(args)` and rebinds `args` itself, so
the container branch's own `len(args) >= 2` test decides correctly and the
room-path string is clean. Net effect: three lines moved, one special case
deleted, and `do_get` now handles its filler word the same way `do_put` already
handled `in` / `on` -- which is where the answer was sitting all along.

### 3. Retired a test that enshrined the bug

`test_get_item_from_bare_token_fails` asserted the broken behaviour, with a
comment explaining the mechanism. It is replaced by
`test_get_with_trailing_from_degrades_to_room_get`, citing the C lines.

### 4. Folded `test_affect_level_decay.py` into `test_regen.py`

The new file was 80 lines: `sys.path` setup, a `ROOM_DEFS` stub-room fixture and
a `_make_player` helper -- for three asserts against a function that never
touches rooms. `test_regen.py` already imports `player as player_mod` and
`GSN_PLAGUE` and has `_full_player()`. The same three cases are now a 30-line
class there, with no fixtures.

### 5. Doc consistency

`parity_sweep.md` opened with "No edits made by this sweep" while carrying
`[fixed 2026-09-05]` annotations. The header was reworded, and rows 35, 94 and
95 rewritten to describe what actually happened.

Verification after each step: `uv run pytest -q -n 4` -> 1738 passed;
`tools/check_ascii_py.py` -> clean.

---

## General lessons

**A missing upstream branch is a gap, not automatically a defect.** Before
porting a branch, ask what it defends against. If the answer is other players,
immortals, clans or a trust hierarchy, the correct verdict is "not applicable",
not "drift" -- and `CLAUDE.md` already states that single-player simplifications
are not drift, while the sweep's own taxonomy already had a `known` bucket for
exactly this. Both pet rows were classified `port-drift` and closed by restoring
the branch. Fidelity means porting intent; an anti-griefing cap in a game with
one player has no intent left to port.

**When a new mechanic perturbs an existing test, neutralize the variable rather
than retuning the inputs to preserve the assertion.** The poison test had its
affect level changed from 20 to 30 so that `level // 10 + 1` would still
evaluate to 3 after decay. The assertion survives, but the test now silently
depends on the decay firing, and a reader cannot tell which mechanic it covers.
Pin the RNG so decay does not fire, or update the expected value and say why.
(The plague test's 1 -> 2 bump was genuinely forced, since level 1 is the value
under test -- that one is fine.)

**When translating C argument parsing, always ask what the empty remainder
does.** C's `one_argument` overwrites its output buffer, so a stripped token
naturally leaves an empty string that falls into an existing empty-argument
branch. A Python port that joins the remainder into a new variable loses that
behaviour for free and has to reconstruct it. More generally: before writing a
new parsing special case, read the sibling command. `do_put` had already solved
the same problem, correctly, forty lines away.

**A test asserting that something fails deserves a check against upstream.** If
the reason for the failure is a quirk of the port's control flow rather than a
rule the game states about itself, the test freezes a bug. Name tests after the
behaviour, not the current outcome.

**New test files must earn their scaffolding.** Fixtures the function under test
never reaches are noise that later readers have to disprove. Prefer appending to
the suite that already has the setup.

**Keep annotation vocabulary distinct.** `[fixed]` was used both for rows where
code changed and for rows where only the verdict was corrected (`get_eq_char`,
`is_exact_name`, `get_obj_carry`). Those are different claims and a reader
cannot tell them apart. And when a document declares itself read-only, an edit
annotation inside it means the declaration needs updating in the same pass.

**Distinguish "equivalent because of the data" from "equivalent by
construction."** Dropping C's `item_type == ITEM_CONTAINER` guard is correct
*today* because the converter only emits that key for containers. That is a real
invariant, but it lives in a different file from the code relying on it, and it
deserves a comment at the point of reliance. The present comment cites the C
macro but not the data invariant that makes the guard unnecessary.
