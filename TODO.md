# TODO

Loose ends that don't belong in a specific plan file.

## Combat

- ~~**Match 1stMud loot handling**~~ — Done. Corpses placed in room; autoloot/autogold/autosac ported. Autosplit wired as toggle but no-op until groups ported.

- ~~**Harmonise damage types and attack nouns with 1stMud**~~ — Done. `ATTACK_TABLE` with dam_class in `config.py`; `check_immune` ported to `combat.py` (verified against `handler.c`) and wired into `damage()`; spells pass proper `DAM_*` classes. Regression tests in `tests/test_check_immune.py`.

- Look should allow picking from available targets

- Picker should implement pagination

- Scrollback with mouse?