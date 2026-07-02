# TODO

Loose ends that don't belong in a specific plan file.

## Combat

- ~~**Match 1stMud loot handling**~~ — Done. Corpses placed in room; autoloot/autogold/autosac ported. Autosplit wired as toggle but no-op until groups ported.

- ~~**Harmonise damage types and attack nouns with 1stMud**~~ — Done. `ATTACK_TABLE` with dam_class in `config.py`; `check_immune` ported to `combat.py` (verified against `handler.c`) and wired into `damage()`; spells pass proper `DAM_*` classes. Regression tests in `tests/test_check_immune.py`.

- ~~Look should allow picking from available targets~~ — Done via `examine` with no args: picker over room mobs, room items, inventory, and equipped (`do_examine` in `info.py`). Bare `look` keeps its "show room" meaning.

- ~~Picker should implement pagination~~ — Done (was stale): `pick_from` pages 10/entry with `+`/`-` nav (`picker.py`).

- ~~Scrollback with mouse?~~ — Done (was stale): touch scrollback via `mouse()` in `tml_prime.py` -- swipe to enter (`SWIPE_THRESHOLD`), drag to scroll (`TOUCH_SCROLL_STEP`), shift+-/+ keyboard path, pulse-clock compensation in game loop.

## Classes

- Full multiclassing (allowing remorts on the same char into all available classes), possibly tiering (start back with 1 class, but with perm bonuses, e.g. to starting skill proficiencies/stats/etc.)