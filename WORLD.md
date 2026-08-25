# PrimeSUD -- What's Changed in the World

FEATURES.md indexes engine changes; this file indexes notable authored world
changes -- new rooms, items, lore, and classes, plus substantial rewrites of
stock content. One line per entry; data corrections live in docs/FIXES.md and
the exhaustive source-delta ledger in docs/AREA_FILES.md.

## World

- **Midgaard City Bank reopened** -- room 3008 above the Grunting Boar Inn
  (stock's "The Defunct Reception") carries `ROOM_BANK` again, so the `bank`
  command works there; pairs with the remort fee accepting banked gold
  (DESIGN.md "Remort gold fee").

## Items

- **Quest catalogue expanded** -- six new questmaster rewards modelled on the
  Aardwolf quest item list (`reference/aardwolf_qlist.md`): a dagger, mace,
  and staff alongside the stock sword, plus bracers (arms), wings (about),
  and an amulet (neck).
- **Aura of the Ancients reworked** -- now the Aardwolf Aura of Sanctuary:
  permanent sanctuary and +3 dex, with the stock hitroll/damroll/AC bonuses
  dropped; the level-scaled hp/mana/move stays.
- **Quest items renamed in colour** -- every quest reward's short description
  now reads in the red/yellow of the Ancients rather than plain white.

## Lore

- **Bank notice rewritten** -- the liquidation notice (obj 3140) is now a
  re-opening notice: Merc Industries lifts the charm that kept your gold
  "close, even beyond death".

## Classes

- **Swordsman / Sword Saint** -- first post-1.0 content class, a DEX-primary
  single-sword duelist (DESIGN.md "Swordsman / Sword Saint"); guild,
  trainers, and signature gear planned, sharing the Warrior guild until then.
