# Cross-Area Resets

Resets that reference mobs, items, or rooms defined in a different area.
Generated from area .dat files.

Note: patch_1stmud_deltas.py (MOVE_RESETS/DROP_RESETS) defers the
midgaard start-load cascade: the juke resets into shire rooms 1116/1144
and the fountain/juke into immort room 1200 now live in the target
area's RESETS, and Kate's Diner `G 1103` (pipeweed bread, shire def) is
dropped. New game loads mud_school+midgaard only instead of also
pulling shire, ofcol2, and immort.

## limbo

| Cmd | Vnum | Description | Def Area | Room | Room Name | Room Area |
|-----|------|-------------|----------|------|-----------|-----------|
| O | 3415 | `a stone sarcophagus` | chapel | 3 | `The Morgue` | limbo |

## mud_school

| Cmd | Vnum | Description | Def Area | Room | Room Name | Room Area |
|-----|------|-------------|----------|------|-----------|-----------|
| G | 3138 | `a buffalo water skin` | midgaard | 3718 | `The Store in Mud School` | mud_school |
| G | 3031 | `a hooded brass lantern` | midgaard | 3718 | `The Store in Mud School` | mud_school |

## shire

| Cmd | Vnum | Description | Def Area | Room | Room Name | Room Area |
|-----|------|-------------|----------|------|-----------|-----------|
| E | 616 | `a leather vest` | ofcol2 | 1110 | `Shiriff Post of the Eastern Shire` | shire |
| E | 616 | `a leather vest` | ofcol2 | 1110 | `Shiriff Post of the Eastern Shire` | shire |
| E | 616 | `a leather vest` | ofcol2 | 1110 | `Shiriff Post of the Eastern Shire` | shire |
| E | 616 | `a leather vest` | ofcol2 | 1111 | `Thain's Office` | shire |
| G | 648 | `a shot of whiskey` | ofcol2 | 1116 | `The Ivy Bush` | shire |
| G | 649 | `a quart of ale` | ofcol2 | 1116 | `The Ivy Bush` | shire |
| G | 650 | `a quart of port brew` | ofcol2 | 1116 | `The Ivy Bush` | shire |
| E | 616 | `a leather vest` | ofcol2 | 1119 | `Shiriff Post of the Bridge` | shire |
| E | 616 | `a leather vest` | ofcol2 | 1119 | `Shiriff Post of the Bridge` | shire |
| E | 616 | `a leather vest` | ofcol2 | 1119 | `Shiriff Post of the Bridge` | shire |
| E | 622 | `a brass helm` | ofcol2 | 1136 | `Bedroom` | shire |
| E | 621 | `brass plate` | ofcol2 | 1136 | `Bedroom` | shire |
| E | 623 | `brass leggings` | ofcol2 | 1137 | `Pantry` | shire |
| G | 648 | `a shot of whiskey` | ofcol2 | 1144 | `The Green Dragon` | shire |
| G | 649 | `a quart of ale` | ofcol2 | 1144 | `The Green Dragon` | shire |
| G | 650 | `a quart of port brew` | ofcol2 | 1144 | `The Green Dragon` | shire |
| E | 616 | `a leather vest` | ofcol2 | 1145 | `Shiriff Post of Delving Lane` | shire |
| E | 616 | `a leather vest` | ofcol2 | 1145 | `Shiriff Post of Delving Lane` | shire |
| E | 616 | `a leather vest` | ofcol2 | 1145 | `Shiriff Post of Delving Lane` | shire |
| E | 616 | `a leather vest` | ofcol2 | 1153 | `Shiriff Post of the Lower Shire` | shire |
| E | 616 | `a leather vest` | ofcol2 | 1153 | `Shiriff Post of the Lower Shire` | shire |
| E | 616 | `a leather vest` | ofcol2 | 1153 | `Shiriff Post of the Lower Shire` | shire |

## haon

| Cmd | Vnum | Description | Def Area | Room | Room Name | Room Area |
|-----|------|-------------|----------|------|-----------|-----------|
| M | 309 | `the cute rabbit` | plains | 6012 | `An intersection in the dense forest` | haon |
| M | 309 | `the cute rabbit` | plains | 6015 | `A small path in the dense forest` | haon |
| M | 309 | `the cute rabbit` | plains | 6017 | `A small path in the dense forest` | haon |
| M | 309 | `the cute rabbit` | plains | 6019 | `A small path in the dense forest` | haon |

## midgaard

| Cmd | Vnum | Description | Def Area | Room | Room Name | Room Area |
|-----|------|-------------|----------|------|-----------|-----------|
| G | 1103 | `a pipeweed bread` | shire | 3150 | `Kate's Diner` | midgaard |
| O | 3135 | `a fountain` | midgaard | 1200 | `The Chat Room` | immort |
| O | 3200 | `the juke` | midgaard | 1200 | `The Chat Room` | immort |
| O | 3200 | `the juke` | midgaard | 1116 | `The Ivy Bush` | shire |
| O | 3200 | `the juke` | midgaard | 1144 | `The Green Dragon` | shire |

