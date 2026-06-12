# TODO

Loose ends that don't belong in a specific plan file.

## Combat

- **Harmonise damage types and attack nouns with 1stMud** — `dam_type` on mobs and weapons currently drives only the attack noun in combat messages. In 1stMud, `attack_table` (see `reference/1stMud4.5.3/src/const.c` line 103) maps each entry to both a noun *and* a `dam_class` (DAM_SLASH, DAM_PIERCE, DAM_BASH, etc.), which is used in `damage()` (`fight.c`) to check `check_immune()` for mob immunities and resistances. PrimeSUD should eventually expose a damage-class mapping derived from `attack_table` and wire it into the combat damage path so that mob `imm_flags`, `res_flags`, and `vuln_flags` actually affect damage taken.
