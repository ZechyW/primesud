# PETS_GROUPS_PLAN.md -- Pet/follower residuals: do_group + safety gates

> 1stMud sources: `reference/1stMud4.5.3/src/`. Items 2-3 independent;
> item 4's end-to-end verification depends on RESETS_PLAN decision 6
> (buy-pet fix) landing first.
> On completion: delete stale `not ported` pet comments in combat.py;
> if the do_group two-line wrap concession is taken, add a DESIGN.md
> "Adjusted from 1stMud" row; strike TODO.md Commands `group` bullet;
> delete this file.

Audit result (08/07/2026): the pet/follower system assumed missing is
almost entirely ported already -- `spawn_pet` (mob.py:160), pet-shop
buy/list branches (shop.py:193/250/352), `add_follower`/`stop_follower`/
`nuke_pets`/`die_follower` (comm.py:204-289), `do_follow`/`do_order`
(comm.py:290/401, active in `_CMD_TABLE`), follower movement + charm
anchor + ROOM_LAW aggressive-pet gate (movement.py:157/270-308), portal
follower recursion (movement.py:511), charmed-follower combat assist
(combat.py check_assist, `[Verified]`). Several `not ported` comments in
combat.py predate this and are stale.

What actually remains -- three small items plus one bug fix that lives in
RESETS_PLAN.md:

## 1. Pet purchase is broken until RESETS_PLAN decision 6 lands

Midgaard pet templates (3090-3093) carry no `"pet"` act flag; 1stMud sets
ACT_PET at reset time for mobs spawned in a room adjacent to a `pet_shop`
room (db.c:1484-1488). `_buy_pet` (shop.py:209) checks the flag and so
always refuses. Fix is reset-side -- tracked there; this plan's
verification depends on it.

## 2. `do_group` (act_comm.c:1304) + command row #15

Port faithfully; solo value is pet/charmie status display.

- No arg: `"%s's group:"` header (leader = `ch["leader"]` or self), then
  one line per `is_same_group` member:
  `"[%2d %s] %-16s %4ld/%4ld hp %4ld/%4ld mana %4ld/%4ld mv %5d xp"`
  with `"Mob"` for NPCs / class name for the player (class_who
  equivalent -- see how do_score renders class). Trailer line advertising
  `group where`. Iterate `world.chars` + player instead of char_first.
  32-col screen: this line is ~70 chars -- wraps; keep 1stMud format
  anyway (tml wraps), or split hp/mana/mv onto a second indented line as
  a `[PRIMESUD]` concession -- implementer's call, note whichever.
- `where` arg: member lines `"{W%s is in %s the general area of %s.{x"`
  (room name + area display name from static tables).
- `<member>` arg: add/remove semantics act_comm.c:1352-1401 -- follower
  check, "You can't remove charmed mobs from your group.", join/remove
  acts. With only charmed followers in a solo game most branches are
  unreachable but they're cheap; port them for fidelity.
- `commands.py`: uncomment row #15 (`group`, "sleeping"); TODO.md
  "Commands" bullet: remove `group` from the deferred list.
- XP field: PrimeSUD player has `xp`; mobs have none -- render 0 for mobs
  (1stMud mob exp field exists but is meaningless there too).

## 3. `is_safe` / `is_safe_spell` gates now unlockable

combat.py:897-1028 has inline-commented branches for ROOM_SAFE and
ACT_PET ("room_flags not on rooms yet" -- stale: rooms now carry
`"flags"`, and `"safe": True` exists in limbo/midgaard/immort data; pets
get their act flag from item 1).

- Enable ROOM_SAFE checks: room flag `"safe"` on `ROOM_DEFS[vnum]["flags"]`
  at combat.py:916/954/985/1019 spots, with 1stMud's exact messages
  (fight.c is_safe/is_safe_spell -- re-read the source block when editing).
- Enable ACT_PET checks at combat.py:931/993 ("But $N looks so cute and
  cuddly..." branch -- verify exact text against fight.c).
- Both functions are `[Verified]`-tagged: these edits resolve documented
  inline TODOs, so per CLAUDE.md they're allowed WITHOUT asking, but must
  be minimal, re-verified against fight.c, and the tag extended
  (`ROOM_SAFE/ACT_PET added and re-verified <date>`).

## 4. Verification sweep (no code expected)

- Charm expiry: when the charm affect wears off, 1stMud leaves
  `master` linked (stop_follower fires only on explicit paths / damage
  fight.c `victim->master == ch`); confirm PrimeSUD's affect-expiry path
  (effects.py / update.py) matches -- i.e. does NOT strip master -- and
  that combat.py:1138 stop_follower-on-hit covers the aggression case.
- End-to-end after RESETS fix: buy + name a pet
  (`buy kitten Fluffy`), pet follows through doors and portals, charm
  anchor blocks pet-initiated flee, `order fluffy kill rat` works,
  `group` shows the pet, pet dies -> links cleaned (die_follower), player
  dies -> nuke_pets fires, save/load restores pet with custom name
  (`pet_name` already persisted).
- `python tools/check_ascii_py.py`.
