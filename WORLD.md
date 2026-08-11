# PrimeSUD -- What's Changed in the World

FEATURES.md indexes engine changes; this file indexes world changes -- the
rooms, items, lore, and classes PrimeSUD adds or rewrites on top of stock
1stMud content. Anything not listed here is stock. One line per entry;
depth lives in DESIGN.md, docs/AREA_FILES.md, and the `areas/*.are` sources.

## World

- **Midgaard City Bank reopened** -- room 3008 above the Grunting Boar Inn
  (stock's "The Defunct Reception") carries `ROOM_BANK` again, so the `bank`
  command works there; pairs with the remort fee accepting banked gold
  (DESIGN.md "Remort gold fee").

## Lore

- **Bank notice rewritten** -- the liquidation notice (obj 3140) is now a
  re-opening notice: Merc Industries lifts the charm that kept your gold
  "close, even beyond death".

## Classes

- **Swordsman / Sword Saint** -- first post-1.0 content class, a DEX-primary
  single-sword duelist (DESIGN.md "Swordsman / Sword Saint"); guild,
  trainers, and signature gear planned, sharing the Warrior guild until then.
