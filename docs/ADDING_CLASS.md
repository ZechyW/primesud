# Adding a Player Class

Player class indices are persisted in `p.classes`. Append new classes; never
insert, remove, or reorder existing entries without a save migration.

## Wiring checklist

1. Add a `CLASS_*` constant and append one `CLASS_TABLE` entry in
   `src/classes.py`. Supply both remort-tier names, prime stat, starting
   weapon, THAC0/HP curve, mana flag, group names, and picker summary.
2. Append one XP multiplier to every PC race `class_mult` tuple in
   `src/races.py`. NPC races do not carry this field.
3. Append one value to every `skill_level` and `rating` tuple in
   `src/skills_table.py`. Use level `53` and rating `0` when the class cannot
   learn a skill. Preserve special sentinels such as reserved skill rating
   `999`. Add GSN constants and full table entries for new skills.
4. Append one rating to every `GROUP_TABLE` tuple in `src/groups.py`. Add the
   class's basics/default groups and ensure every named member resolves at
   import. Check `grlist` column width if a new group name is longer than
   existing names.
5. Register active commands in `src/commands.py`; implement mechanics at the
   existing shared seam. Keep PrimeSUD-only code marked `[PRIMESUD]`. If a
   verified function must change, record the extension in its verification
   tag.
6. Chargen and remort pickers read `CLASS_TABLE` automatically. Verify all
   options and summaries still fit 320x240. Check prefix collisions between
   class names, skills, groups, and commands.
7. Give the class a reachable guild. Add its numeric index as a room `G`
   trailer in the canonical `areas/*.are`, then regenerate that artifact:

   ```
   python tools/are_to_primesud.py areas/midgaard.are src/area_midgaard.txt
   ```

   Record intentional area changes in `docs/AREA_FILES.md`.
8. Add class and skill entries to `src/help.txt`, then rebuild offsets:

   ```
   python tools/build_help_idx.py
   ```

9. Add durable rationale to `DESIGN.md` and a reader-facing line to
   `FEATURES.md`. Remove completed plan files after harvesting decisions.
10. Add focused tests for table widths, creation grants, guild access, command
    gates, and unique mechanics.

## Required checks

On managed Windows, run:

```
python tools/check_ascii_py.py
python -m pytest -q -p no:cacheprovider
git diff --check
```

Useful audits:

```
rg -n "6 classes|six-class|6-tuple|range\(6\)" src tests docs
rg -n "CLASS_RANGER|CLASS_TABLE|class_mult|skill_level|rating" src tests
```

PowerShell: pass directories to `rg` and use `-g` for globs; do not pass
wildcard paths.
