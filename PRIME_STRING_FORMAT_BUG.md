# Physical HP Prime `%` Formatting Bug

## Summary

Physical HP Prime Python can produce unstable values from `%s` string
formatting in narrow cases. A value may initially pass `isinstance(x, str)`,
but later fail `isinstance(x, str)` after additional list/string operations.
This can break `"~".join(lines)`.

## Observed Trigger

In PrimeSUD `save_char()`, this old area-state serialization was unstable:

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

## Current Workaround

Area tags avoid underscores where possible. The Mud School tag is `mudschool`
instead of `mud_school`.

Use explicit `str()` plus concatenation for all save payload fields:

```python
"a." + str(_as["tag"]) + ".age=" + str(_as["age"])
```

Avoid `%` formatting for serialized/persisted fields on physical HP Prime:
save payloads, HVars/PPL strings, file formats, generated area data, and any
string that will be joined/stored/parsing-critical. Transient UI-only strings
may still use `%` when useful for `{X` colour-code compatibility.

## Status

Confirmed during PrimeSUD save-format probing on physical HP Prime hardware.
The cause appears heap/timing-sensitive: debug `tr.input()` / `tr.print()`
calls can mask the bug.
