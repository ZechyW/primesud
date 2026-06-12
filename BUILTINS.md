# HP Prime Python — Built-in Type Reference

Methods and attributes verified on the HP Prime's MicroPython via `dir()`.
Use this to check what's available before reaching for a CPython-only feature.

Signatures are **not** verified — only name presence from `dir()` is confirmed.
Assume CPython semantics unless noted otherwise.

---

## `str`

Verified with `dir(str)` on-device.

### Available

| Method       | Notes                                                                     |
|:-------------|:--------------------------------------------------------------------------|
| `center`     |                                                                           |
| `count`      |                                                                           |
| `encode`     |                                                                           |
| `endswith`   |                                                                           |
| `find`       |                                                                           |
| `format`     | Caution: `{` conflicts with `{X` colour codes — use concatenation instead |
| `index`      |                                                                           |
| `isalpha`    |                                                                           |
| `isdigit`    |                                                                           |
| `islower`    |                                                                           |
| `isspace`    |                                                                           |
| `isupper`    |                                                                           |
| `join`       |                                                                           |
| `lower`      |                                                                           |
| `lstrip`     |                                                                           |
| `partition`  |                                                                           |
| `replace`    |                                                                           |
| `rfind`      |                                                                           |
| `rindex`     |                                                                           |
| `rpartition` |                                                                           |
| `rsplit`     |                                                                           |
| `rstrip`     |                                                                           |
| `split`      |                                                                           |
| `splitlines` |                                                                           |
| `startswith` |                                                                           |
| `strip`      |                                                                           |
| `upper`      |                                                                           |

### Not available (CPython only)

| Method         | CPython behaviour                                  |
|:---------------|:---------------------------------------------------|
| `capitalize`   | First char upper, rest lower                       |
| `casefold`     | Aggressive lowercase for case-insensitive matching |
| `expandtabs`   | Replace `\t` with spaces                           |
| `format_map`   | Like `format` but takes a mapping directly         |
| `isalnum`      | True if all chars are alphanumeric                 |
| `isascii`      | True if all chars are ASCII                        |
| `isdecimal`    | True if all chars are decimal characters           |
| `isidentifier` | True if valid Python identifier                    |
| `isnumeric`    | True if all chars are numeric                      |
| `isprintable`  | True if all chars are printable                    |
| `ljust`        | Left-justify in field of given width               |
| `maketrans`    | Build translation table for `translate`            |
| `removeprefix` | Strip prefix if present (Python 3.9+)              |
| `removesuffix` | Strip suffix if present (Python 3.9+)              |
| `rjust`        | Right-justify in field of given width              |
| `title`        | Title-case the string                              |
| `translate`    | Map chars through translation table                |
| `zfill`        | Pad with leading zeros                             |

---

## Language / Syntax Restrictions

Features not supported by HP Prime's MicroPython (confirmed via `SyntaxError` at runtime):

| Feature | Workaround |
|:--------|:-----------|
| `{**a, **b}` dict unpacking in literals | `d = {}; d.update(a); d.update(b)` |
| `f"..."` f-strings | `"{} ...".format(x)` |

<!-- Add sections for other builtins as verified: list, dict, int, etc. -->
