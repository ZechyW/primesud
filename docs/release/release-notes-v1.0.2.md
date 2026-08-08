# PrimeSUD 1.0.2

Maintenance release rolling up the engine work since 1.0.1: large on-device performance gains, new play aids, and combat-message parity fixes. Recommended for all players; v1.0.x saves load unchanged.

## Performance

All figures measured on a physical HP Prime G1.

- World boot is roughly twice as fast (13.0 s to 6.2 s) via binary-walk parsers for the world data, save file, and pathfinding index.
- Saves are faster and quieter: the autosave stall shrank from ~0.9 s of frozen UI to a live echo preview that keeps typing responsive throughout.
- New binary keyword indexes make mob and item lookups near-instant without loading their areas.

## New

- RECOMMEND command: `recommend mobs` ranks level-appropriate opponents (with your win/loss record against each); `recommend gear` finds strict upgrades over your equipped items and where they come from.
- Browsable help: `index` opens a categorised, level-filtered help browser with pickers throughout.
- Keypad macros: five more bindable keys plus EEX, a full-screen macro grid, and sensible default bindings for previously unset keys.

## Gameplay and fixes

- Pet kills apply the present owner's autoloot/autogold/autosacrifice, and owned pets no longer dilute group XP.
- Wielding a two-handed weapon now auto-removes a blocking shield.
- WEAR BEST and RECOMMEND skip weapons you have no proficiency in.
- Ported missing 1stMud combat observer messages (disarm and damage lines seen by bystanders).
- Spilled corpse loot decays unless picked up.
- Item instance overrides (e.g. quest-modified gear) win over templates in display and gates; a duplicate-object removal bug is fixed.

## Installation

Download `PrimeSUD-v1.0.2-hpprime.zip` and transfer it using the HP Connectivity Kit. The archive contains the complete `primesud.hpappdir` folder. If the calculator reports insufficient memory, power-cycle it before attempting a soft reset; see the README for details.

## Verification

SHA-256: `15493858edf6b66e4aa8ca1266b4dfff750025ac0afab5bd368042a6c62b73ec`
