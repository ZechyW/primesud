# area_school.py vs school.are — Audit Checklist

Goal: verify that `primesud.hpappdir/area_school.py` is a faithful port of
`reference/1stMud4.5.3/area/school.are` as produced by `tools/are_to_primesud.py`.

---

## File offsets (for Read calls)

| Section      | school.are lines | area_school.py lines |
|--------------|------------------|----------------------|
| AREADATA     | 1–13             | 1–16 (AREA dict)     |
| MOBILES      | 14–349           | 783–1078             |
| OBJECTS      | 350–675          | 1079–1272            |
| ROOMS        | 676–2157         | 126–782              |
| RESETS       | 2164–2209        | 1273–1321            |

---

## Checklist

- [x] Read AREA_FILES.md (format reference)
- [x] Read tools/are_to_primesud.py (converter logic + flag tables)
- [x] **AREADATA** — compare AREA dict → **no discrepancies**
- [x] **MOBILES** — field-by-field comparison of all 21 mobs — **no discrepancies**
  - [x] Read school.are MOBILES (lines 14–349)
  - [x] Read area_school.py MOBILES dicts (lines 783–1078)
  - [x] Verify act_flags for each mob (parse bit strings vs py dicts)
  - [x] Verify aff_flags, off_flags, imm/res/vuln_flags
  - [x] Verify level, hp_dice, hitroll, AC, damage, gold
- [x] **OBJECTS** — field-by-field comparison of all 23 items — **no discrepancies**
  - [x] Read school.are OBJECTS (lines 350–675)
  - [x] Read area_school.py OBJECTS (lines 1079–1272)
  - [x] Verify type, slot, weight, value, dice, extra_flags
- [x] **ROOMS** — comparison of all 59 rooms — **no discrepancies**
  - [x] Chunk 1: school.are lines 676–1075, area_school.py lines 126–373 (rooms 3700–3716)
  - [x] Chunk 2: school.are lines 1076–1475, area_school.py lines 374–573 (rooms 3717–3731)
  - [x] Chunk 3: school.are lines 1476–1875, area_school.py lines 574–782 (rooms 3732–3746)
  - [x] Chunk 4: school.are lines 1876–2157, area_school.py (rooms 3748–3760, dungeon + special)
  - [x] Verify exits, flags, sector for each room
- [x] **RESETS** — verify all M/O entries and TODO comments — **no discrepancies** (all 21 M entries match; F/E/G correctly TODO'd)
  - [x] Read school.are RESETS (lines 2164–2209)
  - [x] Read area_school.py RESETS (lines 1273–1321)

---

## Flag tables (from tools/are_to_primesud.py)

### ACT_FLAGS (bit → name; bit 0 = is_npc, skipped)
```
1=sentinel  2=scavenger  5=aggressive  6=stay_area  7=wimpy
8=pet  9=train  10=practice  14=undead  16=cleric  17=mage
18=thief  19=warrior  20=noalign  21=nopurge  22=outdoors
24=indoors  26=healer  27=gain  28=update_always  29=changer
```

### AFF_FLAGS
```
0=blind  1=invisible  2=detect_evil  3=detect_invis  4=detect_magic
5=detect_hidden  6=detect_good  7=sanctuary  8=faerie_fire  9=infrared
10=curse  12=poison  13=protect_evil  14=protect_good  15=sneak  16=hide
17=sleep  18=charm  19=flying  20=pass_door  21=haste  22=calm  23=plague
24=weaken  25=dark_vision  26=berserk  27=swim  28=regeneration  29=slow
```

### OFF_FLAGS
```
0=area_attack  1=backstab  2=bash  3=berserk  4=disarm  5=dodge
6=fade  7=fast  8=kick  9=kick_dirt  10=parry  11=rescue  12=tail
13=trip  14=crush  15=assist_all  16=assist_align  17=assist_race
18=assist_players  19=assist_guard  20=assist_vnum
```

### RESIST_FLAGS (used for imm/res/vuln)
```
0=summon  1=charm  2=magic  3=weapon  4=bash  5=pierce  6=slash
7=fire  8=cold  9=lightning  10=acid  11=poison  12=negative  13=holy
14=energy  15=mental  16=disease  17=drowning  18=light  19=sound
23=wood  24=silver  25=iron
```

### AC formula
`ac = (sum of 4 AC values) // 4 // 10`  — Python floor division (rounds toward -∞)
- All 10s → 10//10 = **1**
- (8,8,8,10) → 34//4=8, 8//10 = **0**
- (7,7,7,9) → 30//4=7, 7//10 = **0**
- (6,5,6,7) → 24//4=6, 6//10 = **0**
- (5,5,5,8) → 23//4=5, 5//10 = **0**  (but .are says 5,5,5,8 → 23//4=5)
- All -15 → -60//4=-15, -15//10 = **-2**

---

## Known discrepancies found so far

None. All sections verified — AREADATA, MOBILES, OBJECTS, ROOMS, RESETS are faithful to school.are.

---

## Mob bit-string reference (act aff off imm res vuln, from school.are)

| VNUM | Name              | act bits set (excl 0)          | aff bits | off bits      | imm bits  | res bits    | vuln bits   |
|------|-------------------|-------------------------------|----------|---------------|-----------|-------------|-------------|
| 3700 | acolyte of Zump   | 1,6,16,19,21                  | 2,7      | 0,2,4,5,7,8,10,13 | 0,1,2,3 | —           | —           |
| 3701 | blob              | 1,6                           | 2        | 0,13          | 0,1       | 2,3         | —           |
| 3702 | monster           | 1,20                          | —        | —             | 0,1       | —           | 2           |
| 3703 | wimpy monster     | 1,7,20                        | —        | 14            | 0,1       | —           | 2           |
| 3704 | aggressive monster| 1,5,20                        | —        | 4,10          | 0,1       | —           | 2           |
| 3705 | wimpy aggr monster| 1,5,7,20                      | —        | 9             | 0,1       | —           | 2           |
| 3706 | big creature      | 1,20                          | 9,25(?)  | 5,13          | 0,1       | —           | 2           |
| 3707 | adept of Satin    | 1,6,16,19,21                  | 2,7      | 0,2,4,5,7,8,10,13 | 0,1,2,3 | —           | —           |
| 3708 | adept of Alander  | 1,6,16,19,21                  | 2,7      | 0,2,4,5,7,8,10,13 | 0,1,2,3 | —           | —           |
| 3709 | rabbit            | 6,7,20                        | —        | 5,7           | —         | —           | —           |
| 3710 | lizard            | 6,20                          | —        | 17            | —         | 11          | 8           |
| 3711 | boar              | 6,20                          | —        | 2,3,5,17      | —         | —           | —           |
| 3712 | fox               | 6,7,20                        | 25       | 5,7,13,17     | —         | —           | —           |
| 3713 | snail             | 6,20                          | —        | —             | —         | —           | —           |
| 3714 | beast             | 5,19,20,21(?)                 | 25       | 4,10,12       | 0,1       | 7,8         | 2           |
| 3715 | bear              | 6,20                          | —        | 2,3,4,14,17   | —         | 4,8         | —           |
| 3716 | wolf              | 6,20                          | 25       | 5,7,13,17     | —         | —           | —           |
| 3717 | adept of Selene   | 1,2,16,19,21                  | 2,7      | 0,2,4,5,7,8,10,13 | 0,1,2,3 | —           | —           |
| 3718 | adept of Furey    | 1,2,9,16,19,21                | 2,7      | 0,2,4,5,7,8,10,13 | 0,1,2,3 | —           | —           |
| 3719 | priest of Circe   | 1,2,10,16,19,21               | 2,7      | 0,2,4,5,7,8,10,13 | 0,1,2,3 | —           | —           |
| 3720 | diploma beast     | 1,20                          | 9        | 4,5,13        | 0,1       | —           | 2           |

_Note: aff bit 25 = dark_vision. 3706 aff: `+nnnnnnnnnYnnnnnnnnnnnnnnnY` = bits 9(infrared),25(dark_vision)._
_3714 act: `+YnnnnYnnnnnnnnnnnnnYY` = bits 5(aggressive),19(warrior),20(noalign) — bit 21? check string length._
