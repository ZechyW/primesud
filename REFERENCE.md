# 1stMud Reference Notes

Snippets of implementation detail from the reference 1stMud 4.5.3 source
(`reference/1stMud4.5.3/`).

---

## Custom colour slots

Defined in `src/h/ansi.h`; in-game names and ordering from `src/tables.c`
(`custom_colors[]`); default values from `data/color_templates.dat` (the
"Default" colour scheme loaded at startup via `data_table.c:2602`).

At the source level, a colour tag is written as `CTAG(_CONSTANT)`, which
expands to the byte sequence `\x11 <slot-number> \x12`.  At render time
(`ansi.c:make_color`) the slot is looked up in `ch->pcdata->colors[]` and
converted to an ANSI escape.

| Slot | Constant    | In-game name | Default colour       | ANSI code  |
|------|-------------|--------------|----------------------|------------|
|  0   | `_DEFAULT`  | clear        | reset                | `ESC[0m`   |
|  1   | `_GOSSIP`   | gossip       | bright + magenta     | `ESC[1;35m`|
|  2   | `_MUSIC`    | music        | bright + red         | `ESC[1;31m`|
|  3   | `_QA`       | qa           | bright + yellow      | `ESC[1;33m`|
|  4   | `_QUOTE`    | quote        | bright + white       | `ESC[1;37m`|
|  5   | `_GRATS`    | gratz        | bright + green       | `ESC[1;32m`|
|  6   | `_SHOUT1`   | shout1       | magenta              | `ESC[0;35m`|
|  7   | `_SHOUT2`   | shout2       | bright + magenta     | `ESC[1;35m`|
|  8   | `_IMMTALK`  | immtalk      | cyan                 | `ESC[0;36m`|
|  9   | `_TELLS1`   | tells1       | cyan                 | `ESC[0;36m`|
| 10   | `_TELLS2`   | tells2       | bright + cyan        | `ESC[1;36m`|
| 11   | `_SAY1`     | say1         | green                | `ESC[0;32m`|
| 12   | `_SAY2`     | say2         | bright + green       | `ESC[1;32m`|
| 13   | `_SKILL`    | skills       | bright + yellow      | `ESC[1;33m`|
| 14   | `_YHIT`     | yhit         | bright + green       | `ESC[1;32m`|
| 15   | `_OHIT`     | ohit         | bright + blue        | `ESC[1;34m`|
| 16   | `_VHIT`     | vhit         | bright + red         | `ESC[1;31m`|
| 17   | `_WRACE`    | whorace      | bright + red         | `ESC[1;31m`|
| 18   | `_WCLASS`   | whoclass     | bright + cyan        | `ESC[1;36m`|
| 19   | `_WLEVEL`   | wholvl       | bright + blue        | `ESC[1;34m`|
| 20   | `_RTITLE`   | roomtitle    | bright + yellow      | `ESC[1;33m`|
| 21   | `_SCORE1`   | score1       | cyan                 | `ESC[0;36m`|
| 22   | `_SCORE2`   | score2       | bright + cyan        | `ESC[1;36m`|
| 23   | `_SCORE3`   | score3       | white                | `ESC[0;37m`|
| 24   | `_SCOREB`   | score4       | bright + white       | `ESC[1;37m`|
| 25   | `_WIZNET`   | wiznet       | green                | `ESC[0;32m`|
| 26   | `_GTELL1`   | gtell1       | yellow               | `ESC[0;33m`|
| 27   | `_GTELL2`   | gtell2       | bright + green       | `ESC[1;32m`|
| 28   | `_BTALK`    | btalk        | bright + blue        | `ESC[1;34m`|
| 29   | `_WSEX`     | whosex       | green                | `ESC[0;32m`|
| 30   | `_AUTOMAP`  | automap      | bright + red         | `ESC[1;31m`|
| 31   | `_AUTOEXITS`| autoexits    | green                | `ESC[0;32m`|
| 32   | `_MOBILES`  | mobiles      | bright + magenta     | `ESC[1;35m`|
| 33   | `_OBJECTS`  | objects      | bright + yellow      | `ESC[1;33m`|
| 34   | `_SOCIALS`  | socials      | bright + random      | `ESC[1;?m` |
| 35   | `_OLCBORDER`| olcborder    | cyan                 | `ESC[0;36m`|
| 36   | `_OLCVAR`   | olcvar       | bright + white       | `ESC[1;37m`|
| 37   | `_OLCVAL`   | olcval       | white                | `ESC[0;37m`|

`_CUSTOM_COLORS = 38` is the count, not a slot.

**Note — slot 1 (`_GOSSIP`):** the raw data has `CT_BACK = 35`, which fails
`VALID_BG()` (requires ≥ 40), so no background is actually applied.

**How to check a slot's default:** read the `colors` blob in
`data/color_templates.dat` under the "Default" scheme.  Values are packed as
`<count> [CT_ATTR CT_FORE CT_BACK] × count`, zero-indexed by slot number.
