# Physical HP Prime String Formatting Bug

## Summary

Physical HP Prime Python corrupts strings produced by `%` or `.format()`
in certain contexts. The corruption zeroes or mangles the first byte of the
result. A standalone call with identical arguments is clean; the bug triggers
under memory pressure, particularly inside list comprehensions with nested dict
lookups.

## Observed Triggers

### Trigger 1 — `%` formatting in save payload loop

In PrimeSUD `save_char()`, this area-state serialization was unstable:

```python
"a.%s.age=%s" % (_as["tag"], _as["age"])
```

The failure reproduced when:

- `_as["tag"] == "mud_school"`
- `_as["age"] == 0`
- the line was built as part of the save payload prefix through area-state
  serialization

Probe result:

```text
normal percent/through_areas n=62 bad=58 join=True
```

Changing only the probe tag from `mud_school` to `mudschool` made the same
suite pass.

A later physical-device autosave isolation test reproduced a crash after about
200 autosaves when area resets were enabled and save payload lines used `%`
formatting. The crash disappeared after converting save payload construction to
explicit `str()` plus concatenation; the same build ran past 300 autosaves.
Payload length was not the trigger: a 20x payload padding test did not
meaningfully change the autosave count before failure.

### Trigger 2 — `.format()` inside list comprehension with nested dict lookups

In PrimeSUD `do_practice()`, this names list was unstable:

```python
names = ["{} ({}%)".format(SKILLS[vnum]["name"], pct) for vnum, pct in practicable]
```

Observed on physical device (G2): entry 5 ("parry") produced `'\x00arry (35%)'` —
first byte zeroed, rest of string intact. A standalone call with the same
arguments was clean:

```python
"{} ({}%)".format("parry", 35)  # correct on its own
```

A minimal reproduction (`debug/test_fmt_bug.py`) confirmed the pattern:
10-entry comprehension iterating a dict, each entry doing a nested dict lookup
(`_skills[k]["name"]`) and `.format()`, reliably produced `\x00`-corrupted
first bytes on at least one entry.

With tr.print, the corrupted `\x00` first byte caused the string to print with the first
visible character missing and the underlying HP Prime Python terminal to bleed
through on the first print of the affected string.

Note: On the G1, the MWE as is doesn't trigger the bug; might need more reliable example
if we intend to file a report.

## Mechanism

Cause appears to be heap write-before-allocation or buffer underwrite triggered
by memory pressure during comprehension evaluation. Debug `tr.print()` calls
can mask the bug. The corruption is not reproducible from the emulator — only
physical hardware.

## Workaround

Use explicit `str()` plus concatenation everywhere a string is built from
dict-sourced values, especially inside list comprehensions and loops:

```python
# Instead of:
"{} ({}%)".format(SKILLS[vnum]["name"], pct)
# Use:
str(SKILLS[vnum]["name"]) + " (" + str(pct) + "%)"

# Instead of:
"a.%s.age=%s" % (_as["tag"], _as["age"])
# Use:
"a." + str(_as["tag"]) + ".age=" + str(_as["age"])
```

Avoid both `%` and `.format()` for:
- List comprehensions with nested dict lookups
- Save payloads, HVars/PPL strings, file formats, generated area data
- Any string that will be joined/stored/parsing-critical

Transient UI-only strings built from simple literals (no dict lookup) may still
use `%` when useful for `{X` colour-code compatibility.

Area tags avoid underscores where possible. The Mud School tag is `mudschool`
instead of `mud_school`.

## Status

Two independent triggers confirmed on physical HP Prime hardware.
MWE in `debug/test_fmt_bug.py`.
