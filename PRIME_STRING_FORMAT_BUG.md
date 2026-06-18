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

## Current Workaround

Area tags avoid underscores where possible. The Mud School tag is `mudschool`
instead of `mud_school`.

Use explicit `str()` plus concatenation for this save field:

```python
"a." + str(_as["tag"]) + ".age=" + str(_as["age"])
```

Avoid `%s` formatting for serialized fields where physical HP Prime has shown
instability.

## Status

Confirmed during PrimeSUD save-format probing on physical HP Prime hardware.
The cause appears heap/timing-sensitive: debug `tr.input()` / `tr.print()`
calls can mask the bug.
