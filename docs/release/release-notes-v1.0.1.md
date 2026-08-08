# PrimeSUD 1.0.1

Maintenance release fixing game-breaking stability bugs on physical calculators, plus one pacing improvement. Recommended for all players; v1.0.0 saves load unchanged.

## Fixes

- Worked around two heap-corruption bugs in the HP Prime's Python firmware (physical G1/G2 only) that could crash the calculator or corrupt saves and on-screen text during normal play. Validated with an extended on-device autosave soak.
- The app now requests an 8 MB heap (up from 6 MB) for extra headroom, e.g. with multiple areas loaded.

## Gameplay

- Movement lag removed: plain walking no longer costs a recovery pulse. Skill and combat recovery are unchanged.

## Installation

Download `PrimeSUD-v1.0.1-hpprime.zip` and transfer it using the HP Connectivity Kit. The archive contains the complete `primesud.hpappdir` folder. If the calculator reports insufficient memory, power-cycle it before attempting a soft reset; see the README for details.

## Verification

SHA-256: `637d149c11f3503f8a919144c4d46baef11fcce69d9b187e5bfe8cd55f414134`
