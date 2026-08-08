# SWORDSMAN_PLAN.md -- new class: Swordsman / Sword Saint

Plan doc; delete after completion (harvest durable decisions into DESIGN.md / FEATURES.md first).

**Gated: content track.** Implementation starts only after the engine 1.0
tag (see TODO.md "Roadmap" -- 1stMud-parity release precedes content
additions).

Whole class is `[PRIMESUD]` -- no 1stMud equivalent. Inspired by Taijijian (太极剑)
sword forms; flavour condensed from the 20 classical techniques into three skills
plus cosmetic combat flourishes.

## Settled decisions (review round 1-2, 18/07/2026)

- **Names:** base "Swordsman", remort "Sword Saint". Chinese names (Jianke/Jianxian)
  deferred until/unless other martial classes (e.g. Japanese) are introduced.
- **No stance synergy.** Swordsman interacts with the stance system exactly like
  every other class.
- **3 unique skills** (most exclusive actives in game is 3, cf. Thief:
  backstab/envenom/steal): `thrust` (active), `riposte` (passive),
  `flowing water` (passive). "Coil" (enhanced disarm) cut -- plain disarm suffices.
- **Combat flourishes are cosmetic only.** No mechanical effect; power budget lives
  entirely in the three skills. Wuxia flavour, but plain readable English
  (no "cloud" as a verb, no untranslated pinyin).

## Class identity

Single-weapon finesse duelist: best sword user in the game, locked out of nearly
every other weapon. Differentiates from Warrior (breadth + raw power) and Thief
(stealth + dirty tricks) via depth-over-breadth.

### CLASS_TABLE entry (index 6, classes.py)

```python
{
    "names":       ("Swordsman", "Sword Saint"),
    "attr_prime":  "dex",
    "weapon":      "sword",
    "skill_adept": 75,
    "thac0_00":    20, "thac0_32": -8,   # between Thief -4 and Warrior -10
    "hp_min":      9,  "hp_max":   13,   # between Thief 8-13 and Warrior 11-15
    "f_mana":      False,
    "base_group":  "swordsman basics",
    "default_group": "swordsman default",
    "summary":     "Master duelist; peerless with a sword, poor with all else",
},
```

Who-list renders `Swor` / `Sw+1` -- no code change needed.

### Shared-skill ratings (weapon-lockout tax)

- sword: rating 1 (cheapest in game), level 1
- dagger: rating 2 (sidearm), low level
- axe / flail / mace / polearm / spear / whip: rating 0 (cannot learn)
- parry, dodge: cheap and early (parry is the riposte enabler)
- second attack / third attack / enhanced damage / disarm / hand to hand /
  fast healing: available at warrior-comparable ratings
- shield block: available but discouraged (higher rating) -- duelist identity;
  no hard block
- No spells; scrolls/staves/wands at thief-like ratings

Exact numbers assigned during implementation, benchmarked against the Warrior
and Thief columns.

## The three unique skills

All three: `[PRIMESUD]`, sword must be wielded, new entries in skills_table +
hooks in combat.py.

### 1. thrust (active, ~level 12)

Precision opening attack (condenses dian/ci/beng -- point, thrust, flick:
wrist-driven strikes with force focused at the tip).

- Opener only, like backstab (`fighting` check); v1 keeps it opener-only.
- Damage scales with sword% and skill%; multiplier below backstab's
  (no stealth requirement, so cheaper to land).
- Bonus vs unarmoured/lightly-armoured targets (force-at-the-tip flavour);
  simple AC threshold check.
- Messages:
  - self: "You sink your shoulders and send your point darting out in a single straight line."
  - room: "$n's sword darts out in a blur, point first."

### 2. riposte (passive, ~level 30)

Counter-attack on successful parry (condenses gua/jie/jia -- hooking,
intercepting, framing deflections that flow straight into a reply).

- Hook in the parry success path (combat.py check_parry): if defender has
  riposte and wields sword, percent-scaled chance of one immediate extra attack.
- One riposte per incoming attack max; no riposte off a riposte.
- Messages:
  - self: "You hook $n's stroke aside and your blade springs back in reply."
  - victim: "$n turns your blow aside and $s point leaps at you in the same breath."

### 3. flowing water (passive, ~level 42, capstone)

Sustained-flow bonus (condenses the continuous-force principle: power from the
waist, motion never breaking).

- Each consecutive combat round in which the Swordsman lands at least one hit
  adds +1 hitroll/+1 damroll, capped at +5/+5; reset on a round with no hits
  landed or when combat ends.
- State: single counter on ch (e.g. `ch["flow"]`), cleared in combat-end
  cleanup; no persistence -- never saved.
- Cosmetic tell at max flow (once, on reaching cap):
  "Your sword and body move as one, the point never straying from your foe."

## Combat flourishes (cosmetic)

`[PRIMESUD]` hook in combat round handling: when a Swordsman is fighting and
wielding a sword, roughly 1-in-8 rounds emit one extra act() line from the pool
below. Purely additive -- dam_message and all verified 1stMud combat messages
untouched. Pool lives as a module-level tuple (small, ~8 strings).

Draft pool (one per form group, wuxia tone, readable English):

1. "You sweep your blade in a flat circle overhead, brushing the attack aside like parting clouds."
2. "Your sword arcs low and level, driven by the turn of your waist."
3. "You draw your point back to your centreline, yielding a step as you coil to strike."
4. "Your wrist turns in a lazy circle, the point tracing a flower in the air."
5. "You sink your shoulders and let your blade float upward, light as a swallow's wing."
6. "Steel whispers as your blade slices upward in a rising arc."
7. "You press your blade against $N's guard, sticking to it like water finding a crack."
8. "You slip aside and your sword follows the opening, smooth as running water."

Third-person (room) variants for each. Victim-referencing lines ($N) only used
when a target is present (all flourishes fire mid-combat, so always true).

## Implementation checklist

1. `classes.py`: CLASS_TABLE entry (above).
2. `races.py`: extend every race's `class_mult` tuple 6 -> 7 entries.
3. `skills_table.py`: canonical since 18/07/2026 (converter deleted) -- hand-edit
   directly: extend every skill's skill_level/rating tuples 6 -> 7 entries and
   update the index comment header.
4. New skills: table entries for thrust/riposte/flowing water + combat.py hooks.
5. `groups.py`: "swordsman basics" / "swordsman default" groups.
6. Flourish hook + message pool in combat.py (or stances-adjacent module if
   combat.py is getting fat).
7. Chargen picker: new summary line appears automatically from CLASS_TABLE;
   verify picker layout still fits 320x240.
8. Guild rooms: 1stMud guilds are per-class room fields. Open item -- either
   share the Warrior guild rooms or add Swordsman to the guild field of chosen
   rooms in area data. Decide during implementation.
9. `help.txt` entries: class blurb + three skill helps; run `tools/build_help_idx.py`.
10. `FEATURES.md` one-liner + DESIGN.md entry (new class, deviation rationale)
    in the shipping commit.
11. Tests: unit tests for flow counter reset semantics, riposte single-fire
    guard, thrust opener-only gating; `python -m pytest tests -q`.

## Open items

- Exact rating/level numbers for shared skills (benchmark vs Warrior/Thief columns).
- Guild room assignment (step 8).
- Balance pass after play: if thrust multiplier or +5/+5 flow cap feels strong,
  tune down; flourish pool is safe to grow anytime.
