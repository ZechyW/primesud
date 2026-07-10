# Cross-Area Resets

Resets that reference mobs, items, or rooms defined in a different area.
Generated from area data files (src/area_*.txt).

Note: to defer the midgaard start-load cascade, areas/midgaard.are's own
`#RESETS` places the juke resets directly in areas/shire.are (rooms
1116/1144) and the fountain/juke directly in areas/immort.are (room
1200) -- see the `## shire` / `## immort` sections below (each line
carries a `* [PRIMESUD] ... moved from midgaard` comment in the source
`.are`). Kate's Diner `G 1103` (pipeweed bread, shire def) is dropped
outright (comment left in areas/midgaard.are #RESETS). New game loads
mud_school+midgaard only instead of also pulling shire, ofcol2, and
immort. Limbo's `O 3415` (stone sarcophagus, chapel def, The Morgue) is
likewise dropped outright (comment left in areas/limbo.are #RESETS) --
limbo is preloaded at session start for corpse storage (primesud.py) and
must not cascade into chapel; the morgue simply has no sarcophagus. See
docs/AREA_FILES.md "Deviations from stock QuickMUD" for the full
provenance table.

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
| O | 3200 | `the juke` | midgaard | 1116 | `The Ivy Bush` | shire |
| O | 3200 | `the juke` | midgaard | 1144 | `The Green Dragon` | shire |

## haon

| Cmd | Vnum | Description | Def Area | Room | Room Name | Room Area |
|-----|------|-------------|----------|------|-----------|-----------|
| M | 309 | `the cute rabbit` | plains | 6012 | `An intersection in the dense forest` | haon |
| M | 309 | `the cute rabbit` | plains | 6015 | `A small path in the dense forest` | haon |
| M | 309 | `the cute rabbit` | plains | 6017 | `A small path in the dense forest` | haon |
| M | 309 | `the cute rabbit` | plains | 6019 | `A small path in the dense forest` | haon |

## immort

| Cmd | Vnum | Description | Def Area | Room | Room Name | Room Area |
|-----|------|-------------|----------|------|-----------|-----------|
| O | 3135 | `a fountain` | midgaard | 1200 | `The Chat Room` | immort |
| O | 3200 | `the juke` | midgaard | 1200 | `The Chat Room` | immort |

## arachnos

Note: room 6134 sits inside haon's vnum block (6000-6199) in the QuickMUD
layout, so the queen's den loads with haon, not arachnos.

| Cmd | Vnum | Description | Def Area | Room | Room Name | Room Area |
|-----|------|-------------|----------|------|-----------|-----------|
| M | 6319 | `the Queen Spider` | arachnos | 6134 | `The Den of the Queen Spider` | haon |
| M | 6318 | `the huge, poisonous spider` | arachnos | 6134 | `The Den of the Queen Spider` | haon |
| M | 6318 | `the huge, poisonous spider` | arachnos | 6134 | `The Den of the Queen Spider` | haon |
| M | 6318 | `the huge, poisonous spider` | arachnos | 6134 | `The Den of the Queen Spider` | haon |

## newthalos

Loading newthalos pulls midgaard defs (always loaded anyway -- midgaard is
a start area).

| Cmd | Vnum | Description | Def Area | Room | Room Name | Room Area |
|-----|------|-------------|----------|------|-----------|-----------|
| O | 3200 | `the juke` | midgaard | 9502 | `The Dancing Daemon Inn` | newthalos |
| G | 3061 | `a leather cap` | midgaard | 9642 | `Shipwright` | newthalos |
| G | 3060 | `a leather jerkin` | midgaard | 9642 | `Shipwright` | newthalos |
| M | 3097 | `the tiger` | midgaard | 9706 | `Nabil's Back Room` | newthalos |
| M | 3096 | `the lion` | midgaard | 9706 | `Nabil's Back Room` | newthalos |
| M | 3095 | `the eagle` | midgaard | 9706 | `Nabil's Back Room` | newthalos |
| O | 3200 | `the juke` | midgaard | 9638 | `Smuggler's Inn` | newthalos |

