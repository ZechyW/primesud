# FIXES.md — 1stMud bugs corrected in PrimeSUD

Bugs in the 1stMud 4.5.3 source that we correct or improve upon during the port.
Each entry references the upstream source location and describes the intended PrimeSUD fix.

---

## automap: closed-door connector symbols are unreachable dead code

**Upstream:** `reference/1stMud4.5.3/src/automap.c`, `map_exits()`, lines 161–181

### The bug

`map_exits` iterates over a room's exits and short-circuits closed ones with an early `continue`:

```c
if (IsSet(pExit->exit_info, EX_CLOSED))
    continue;   /* line 162 — skips the rest of the loop body */
```

Further down in the same loop body there is code intended to render a distinct
closed-door connector symbol from `map_chars_closed` (`I` for N/S, `=` for E/W):

```c
if (IsSet(pExit->exit_info, EX_CLOSED))
    map[exitx][exity].symbol = map_chars_closed[door];  /* UNREACHABLE */
else
    map[exitx][exity].symbol = map_chars[door];
```

Because the `continue` fires first, this branch is never reached.  Closed exits are
silently omitted from the map.  The `_FULL_LEGEND` entry `">I< Closed Doors"` at
`case 7:` in `show_map` is therefore also never visible.

### PrimeSUD fix — implemented in `automap.py`

Render the closed-door connector but do not traverse through it:

1. `_EXIT_CHAR_CLOSED = {"n": "I", "s": "I", "e": "=", "w": "="}` added alongside
   `_EXIT_CHAR` (matching `map_chars_closed[5] = "I=I="` in `automap.c`).

2. In `_map_exits`, closed exits now write `_EXIT_CHAR_CLOSED[direction]` to the
   connector cell and `continue` — the destination room is not added to the BFS
   queue, so the room behind the door stays hidden.

3. `"   I=  Closed Doors"` legend entry added to `_FULL_LEGEND` at index 7
   (between `"|-  Exits"` and `"*   Field/Forest"`); terrain entries shift to
   indices 8–16 (17 entries total).

---

## offhand attack: non-weapon items in WEAR_SECONDARY cause runaway damage

**Upstream:** `reference/1stMud4.5.3/src/act_obj.c`, `do_second()`, line 2994;
`reference/1stMud4.5.3/src/fight.c`, `one_hit()`, lines 711–730.

### The bug

`do_second` (the command for equipping an offhand weapon) validates level, weight,
and shield/hold conflicts, but never checks `obj->item_type == ITEM_WEAPON`.
Any carried item that passes the weight limit can be placed in `WEAR_SECONDARY`.

Inside `one_hit` (called with `secondary=true` for the offhand strike), the damage
block checks only `if (wield != NULL)` before rolling dice:

```c
if (wield != NULL)
{
    dam = dice(wield->value[1], wield->value[2]) * skill / 100;
    ...
}
```

There is no `wield->item_type == ITEM_WEAPON` guard here.  `value[1]` and
`value[2]` are read positionally from the `.are` file and their meaning is entirely
item-type-specific:

| Item type | `value[1]` | `value[2]` |
|---|---|---|
| Weapon | num dice | die size |
| Armor | AC (pierce) | AC (slash) |
| Container | max weight | flags |
| Potion | spell sn | spell sn |

A container with `value[1] = 100` and `value[2] = 50` would roll `dice(100, 50)`
— up to 5000 raw damage — before the `* skill / 100` scaling is applied.

Note: the weapon skill used to scale this damage (`skill = 20 + get_weapon_skill(ch, sn)`)
is also unaffected — `get_weapon_sn` always reads `WEAR_WIELD` (primary slot), so
it returns the primary weapon's sn regardless of what is in the secondary slot.
The malformed dice values are the sole source of the damage spike.

### PrimeSUD fix — implemented in `multi_hit` in `combat.py`

The offhand strike is gated before `one_hit` is called:

```python
secondary_obj = ch["equip"].get("secondary")
if secondary_obj is not None and ITEM_DEFS[secondary_obj["vnum"]].get("type") == "weapon":
    one_hit(ch, victim, dt=dt, secondary=True)
```

Only a confirmed weapon item proceeds to the hit; non-weapons in the secondary slot
are silently skipped rather than producing undefined dice behaviour inside `one_hit`.

---

## randomize_damage: return value discarded — damage variance never applied

**Upstream:** `reference/1stMud4.5.3/src/fight.c`, `randomize_damage()`, line 864;
called at line 1016 inside `damage()`.

### The bug

`randomize_damage` computes `dam = (dam * (am + 50)) / 100` and returns the result,
but the call site in `damage()` discards the return value:

```c
randomize_damage(ch, dam, dice(1, 100));   // line 1016 — return value unused
```

C passes `dam` by value, so the local `dam` inside `damage()` is never modified.
The intended +/-50% damage variance is silently lost; all damage rolls hit at their
exact pre-variance value.

### PrimeSUD fix — implemented in `damage` in `combat.py`

The return value is captured:

```python
dam = _randomize_damage(dam, randint(1, 100))
```

This applies the intended variance: `roll` ranges 1–100, so `(roll + 50)` ranges
51–150, yielding 51%–150% of the original damage (roughly +/-50%).

---

## look / automap: paragraph breaks preserved when condensing room descriptions

**Upstream:** `reference/1stMud4.5.3/src/automap.c`, `erase_new_lines()`, lines 197–236;
also called via `dwrap()` in `reference/1stMud4.5.3/src/h/descriptor.h`, line 252.

### The bug

`erase_new_lines` processes a room description in two passes:

1. Replace every `\n` and `\r` with a space (`\x20`), treating single newlines and
   paragraph-break double-newlines identically.
2. Collapse any run of two or more consecutive spaces into a single space.

The result is a single flat paragraph — all intentional blank-line paragraph breaks
(`\n\n`) are silently destroyed along with ordinary soft-wrap newlines.

### PrimeSUD fix — implemented in `_wrap_paragraphs` in `commands.py`

`_wrap_paragraphs` distinguishes between structural paragraph breaks and
within-paragraph whitespace:

1. Split on `\n\n` to separate paragraphs.
2. Within each paragraph, collapse all whitespace (including embedded single `\n`)
   via `' '.join(para.split())` — equivalent to 1stMud's space-collapse pass but
   scoped to one paragraph.
3. Word-wrap each paragraph to the target width and join the resulting lines.
4. Insert a blank line between adjacent paragraphs in the output.

This preserves the visual structure that area authors encoded with double newlines
while still removing the soft-wrap artifacts that `.are` files embed.

---

## autoloot: searches by name, finds oldest corpse instead of fresh kill

**Upstream:** `reference/1stMud4.5.3/src/fight.c`, `raw_kill()` caller block,
lines 1160--1198; `make_corpse()`, line 1673.

### The bug

`make_corpse` is `void` -- it creates the corpse, appends it to the room's
object list via `Link` (which adds to `content_last`), and returns nothing.

The autoloot/autogold/autosac block that runs after `raw_kill` re-discovers
the corpse by name search:

```c
corpse = get_obj_list(ch, "corpse", ch->in_room->content_first);
```

`get_obj_list` iterates from `content_first` and returns the first match.
Since `make_corpse` appends to the end, the search finds the **oldest** corpse
in the room, not the one just created.

With two corpses present (old empty + new with loot):

1. **Autoloot** (`do_get "all corpse"`) targets the old empty corpse. Gets nothing.
2. **Autogold** checks `content_first` on the old corpse. Empty, skips.
3. **Autosac** (`do_sacrifice "corpse"`) does its own `get_obj_list` search,
   also finds and destroys the old empty corpse.

The new corpse with loot sits untouched. Not destroyed -- just not
auto-picked-up. In practice this rarely manifests because autosac clears
the stale corpse each kill, so it only takes one extra kill to catch up.
In rapid multi-kill scenarios the bug consistently lags by one corpse.

### PrimeSUD fix -- implemented in `make_corpse` / `raw_kill` in `combat.py`

`make_corpse` returns the corpse object. `raw_kill` returns it to the caller.
The autoloot block uses the returned reference directly instead of searching
by name, guaranteeing it always operates on the freshly created corpse
regardless of how many other corpses are in the room.

## multiclass: has_spells checks the wrong class table rows

**Upstream:** `reference/1stMud4.5.3/src/multiclass.c`, `has_spells()`, lines 257-267

### The bug

The loop iterates over the character's class slots but indexes `class_table`
with the loop counter instead of the class held in that slot:

```c
for (i = 0; i < ch->Class[CLASS_COUNT]; i++)
    if (class_table[i].fMana)   /* should be class_table[ch->Class[i]] */
        return true;
```

A single-class character always checks `class_table[0]` (Mage, fMana=true),
so every un-remorted character -- including Thieves and Warriors -- counts as
a caster, and `advance_level()`'s non-caster mana halving never applies to
them.

### PrimeSUD fix -- implemented in `classes.py`

`has_spells()` indexes `CLASS_TABLE[cl]` for each held class index `cl`.

---

## magic: `(level | 50)` bitwise-OR damage rolls in seven attack spells

**Upstream:** `reference/1stMud4.5.3/src/magic.c` -- `spell_magic_missile`
(line 3571), `spell_burning_hands` (822), `spell_chill_touch` (1308),
`spell_color_spray` (1334), `spell_fireball` (2598), `spell_lightning_bolt`
(3503), `spell_shocking_grasp` (~4084).

### The bug

All seven spells roll damage as:

```c
dam = number_range((level | 50) / 2, (level | 50) * 2);
```

`|` is bitwise OR, likely a typo for `+`. For levels 1-50 the expression
produces a non-monotonic value stuck in the 50-63 band (level 2 -> 50,
level 13 -> 63, level 32 -> 50): gaining levels barely changes damage and
can even lower it, and all seven spells share one flat damage band **from
level 1**. Stock ROM 2.4 rolled `number_range(d/2, d*2)` from increasing
per-spell `dam_each` tables, giving each spell its own curve and natural
level gate (magic missile avg ~4-17, fireball 0 below level 15 then up to
~162). 1stMud's rewrite buffed magic missile ~7x and halved fireball's
high end -- this flattening, not a port error, is why attack spells
outdamage weapons from the first level.

### PrimeSUD fix -- implemented in `magic.py`

ROM 2.4 stock `dam_each` tables restored for all seven spells
(`_DAM_MAGIC_MISSILE` etc. + `_table_dam` helper, level clamped to 50).
This deviates from 1stMud on purpose: the tables recover the per-spell
balance the `(level | 50)` rewrite destroyed. An earlier PrimeSUD fix used
`level + 50` (the presumed typo intent), but that kept the flattening --
all seven spells identical, magic missile ~7x ROM at level 50. Each site
carries a `[PRIMESUD]` comment referencing this entry.

---

## magic: energy drain reads the caster's hp for the low-level kill branch

**Upstream:** `reference/1stMud4.5.3/src/magic.c`, `spell_energy_drain`, line 2575.

### The bug

```c
if (victim->level <= 2)
    dam = ch->hit + 1;
```

The branch intends a guaranteed kill on victims of level 2 or below, but it
reads the **caster's** current hp. A wounded caster at 5hp drains a level-2
mob for only 6 damage and it survives.

### PrimeSUD fix -- implemented in `magic.py`

`dam = victim hp + 1`, the intended guaranteed kill.

---

## magic: holy word never buffs the caster in PrimeSUD's first port

**Upstream behaviour (correct):** `magic.c:3118-3128` -- the room walk
includes the caster, who always matches his own alignment and receives
"You feel more powerful." plus frenzy and bless before the move/hp drain.

PrimeSUD's room loop iterates `room["mobs"]`, which never contains the
player, so the self-buff was silently lost. Fixed by applying the
same-alignment branch to the caster after the mob loop. (The upstream
message text "You feel full more powerful." is also a typo; PrimeSUD says
"You feel more powerful.")

---

## magic: gas breath NPC-vs-NPC filter inverted vs fire/frost breath

**Upstream:** `reference/1stMud4.5.3/src/magic.c`, `spell_gas_breath`, line 4506.

### The bug

Fire and frost breath skip NPC bystanders unless the NPC breather is
mutually fighting them:

```c
(IsNPC(vch) && IsNPC(ch) && (ch->fighting != vch || vch->fighting != ch))
```

Gas breath has the comparison inverted (`==` / `==`), so an NPC gas
breather skips the very NPC it is fighting and gasses uninvolved
bystanders instead.

### PrimeSUD fix -- implemented in `magic.py`

Condition aligned with the fire/frost convention (skip unless mutually
fighting).

---

## continual light: the ball of light has 0 fuel and never illuminates

**Upstream:** `reference/1stMud4.5.3/area/limbo.are`, object `#21` (ball of
light); `reference/1stMud4.5.3/src/magic.c`, `spell_continual_light`, line 1344.

### The bug

`spell_continual_light` creates `OBJ_VNUM_LIGHT_BALL` (vnum 21) and drops it
in the room; the help text promises a light that "runs indefinitely". But the
ball template ships with `value[2]` (light fuel hours) == 0:

```
#21
...
light A A
0 0 0 0 0     <- value[2] = 0
```

`create_object` only rewrites the infinite marker (`value[2] == 999 -> -1`,
`db.c:2102`); 0 is left as-is. Every `room->light` path
(`equip_char`/`char_to_room`, `handler.c:1319/1367/1576/1646`) and the
`can_see_obj` lit-light branch (`handler.c:2470`) gate on `value[2] != 0`, so a
0-fuel light never counts. The conjured ball is visible (it carries
`ITEM_GLOW`) but does not light a dark room even when worn -- confirmed against
a live 1stMud server. `value[2]` should be `-1` (infinite: `!= 0` so it counts,
and never decrements).

### PrimeSUD fix -- corrected in `areas/limbo.are` (converter source)

Object 21's `value[2]` set to `-1` in our QuickMUD `.are` copy (`0 0 -1 0 0`),
regenerated into `src/area_limbo.txt` as `"light_hours": -1`. PrimeSUD's
`create_object` leaves negative fuel unseeded (infinite), and `room_light` /
`can_see_obj` read `-1 != 0` as lit via the template fallback -- so a worn ball
now illuminates and never burns out. Floor lights still do not light rooms
(matches 1stMud: `obj_to_room` never touches `room->light`), so the ball only
lights once picked up and worn, exactly as upstream intends.

---

## magic: ventriloquate audible only to the char it impersonates

**Upstream:** `reference/1stMud4.5.3/src/magic.c`, `spell_ventriloquate`, line 4290.

### The bug

Stock ROM sends the thrown voice to everyone in the room **except** the
character named as the speaker:

```c
if ( !is_name( speaker, vch->name ) )
    send_to_char( saves_spell(...) ? buf2 : buf1, vch );
```

1stMud inverted the test (`is_name(...)`), so only the named character
"hears" its own faked speech and nobody else sees anything. In
single-player PrimeSUD that made the spell a complete no-op.

### PrimeSUD fix -- implemented in `magic.py`

Restored ROM behaviour: every room occupant whose name does not match the
spoken name (including the caster) receives the line, with a successful
save revealing "Someone makes X say ...".

---

## mobprog: $R expansion renders the triggering char, not the random one

**Upstream:** `reference/1stMud4.5.3/src/programs.c`, `expand_arg_mob()`,
case `'R'`, lines 1512-1520.

### The bug

Every random-char $-code resolves `rch` (the picked random char) except `$R`,
whose display expression reads `ch` (the triggering char) instead:

```c
case 'R':
    if (rch == NULL)
        rch = get_random_char(mob, NULL, NULL);
    i = (rch != NULL && can_see(mob, rch))
        ? (IsNPC(ch) ? ch->short_descr : ch->name)   /* ch, should be rch */
        : someone;
    break;
```

The guard tests `rch` for visibility, then renders `ch` -- a copy-paste slip
from the `$N` case just above. `$r` (lowercase, name form) is correct; only
`$R` (short-descr form) is affected. A prog line like `mob echo $R glares at
you` names the triggering player rather than the random bystander it picked.

### PrimeSUD fix -- implemented in `expand_arg` in `mobprog.py`

The `'R'` branch renders `rch` (`_char_short(rch)`), matching `$r`/`$J`/`$K`/
`$L` and the `rch` visibility guard. The site carries a `[PRIMESUD]` comment
referencing this entry.

## multiclass: finish_remort zeroes race skills when the race is kept

**Upstream:** `reference/1stMud4.5.3/src/multiclass.c`, `finish_remort`,
lines 213-222.

### The bug

The remort skill-reset loop special-cases race skills on the `stay_race`
flag:

```c
if (ch->pcdata->learned[sn] > 0 && ch->pcdata->learned[sn] < 100)
{
    if (is_race_skill(ch, sn) && !ch->pcdata->stay_race)
        ch->pcdata->learned[sn] = 0;    /* forgotten entirely */
    else
        ch->pcdata->learned[sn] = 1;
}
```

`stay_race` is only set when a remort picks a *different* race
(nanny.c:519-523), so `!stay_race` here means the player went through the
race prompt and **kept** their race. Their own racial skills are zeroed to
unknown -- and the `group_add` re-grant in `HANDLE_CON_GET_NEW_RACE` ran
*earlier* in the flow, so nothing restores them. Changing race (the case
the special-case presumably meant to handle, dropping the old race's
skills) instead leaves the old race's skills at 1% via the generic branch.
The condition appears inverted.

### PrimeSUD fix -- implemented in `finish_remort` in `training.py`

No race special-case: in-progress race skills reset to 1% like every other
skill, and the new race's skills are granted at 1% by `_apply_remort_race`.
Old-race skills at 1% match upstream's (accidental) race-change behaviour.

---

## mobprog: get_random_char candidate pool narrowed to visible non-self chars

### 1stMud bug (programs.c:208-246)

For a mob caller the loop's first branch correctly restricts candidates to
visible players other than the mob -- but any occupant that FAILS those
conditions falls through to a bare `else if (number_percent() > highest)`,
which happily rolls for the mob itself, other NPCs, and invisible chars.
So the restriction only weights the odds; it doesn't restrict the pool, and
a prog can pick the acting mob as its own "random bystander".

### PrimeSUD deviation -- implemented in `get_random_char` in `mobprog.py`

Candidates are visible characters other than the acting mob, which is the
behaviour the $-codes ($r/$R "random char here") plainly intend. Marked
[PRIMESUD] at the site.

---

## bank: currency, cap, hours, and score inconsistencies

**Upstream:** `reference/1stMud4.5.3/src/economy.c`, `do_bank()`, lines
63-440; `reference/1stMud4.5.3/src/act_info.c`, `dlm_score()`, lines 1848-1858.

### The bugs

Personal deposits use `check_worth(..., VALUE_DEFAULT)`, which treats the
amount as silver, but `paybank` subtracts that number from gold and credits it
unchanged as bank gold. Silver can therefore satisfy the check without being
deducted, creating bank gold. Deposits also check the amount alone instead of
the resulting balance, so repeated deposits can exceed `MAX_GOLD`. Share sales
at the cap consume every share while silently discarding excess proceeds.

The bank advertises 4am-8pm hours but closes only when `hour > 20`, leaving it
open through 8:59pm. The score format passes `shares` twice before
`share_value`; its "value" field therefore shows the share count, not the
current price.

### PrimeSUD fixes -- implemented in `economy.py` and `info.py`

- [PRIMESUD] Deposits are denominated in whole gold but may draw from the
  combined wallet at 100 silver per gold. `all` leaves any sub-gold silver.
- Deposit and share-sale mutations are rejected if the resulting bank balance
  would exceed `MAX_GOLD`; shares are never consumed for discarded proceeds.
- The bank closes at hour 20, matching its stated 8pm closing time.
- Score uses a 64-column-safe full-width bank row and shows the real share
  price.

---

## quest info: active quests omit their remaining time

**Upstream:** `reference/1stMud4.5.3/src/quest.c`, `do_quest()`, lines 371-443.

`HELP QUEST` says `quest info` reminds the player of the target and time
remaining, but every active objective branch returns immediately after the
target location. Only cooldown and return-to-questmaster states show time.

PrimeSUD prints the remaining time for every active quest, matching the help
text. The contextual bare-`quest` picker and completed-quest quit protection
are separate `[PRIMESUD]` calculator UX extensions.


---

## path: random saving-throw gate on an information command

**Upstream:** `reference/1stMud4.5.3/src/act_enter.c`, `do_path()`, lines 445-460.

The mob-target disqualifier chain ends with
`(IsNPC(victim) && saves_spell(ch->level, victim, DAM_OTHER))`, so an
otherwise-valid target refuses to route on a failed roll. Nothing the player
controls feeds that roll: `saves_spell` reads only the victim's level, saving
throw, berserk state, immunities, and `has_spells`, plus the caster's raw
level. No skill, stat, or equipment applies.

The result on a free, instant, no-feedback command is pure friction --
`path` prints the same `No such destination.` as a mistyped name, and the
optimal play is to repeat it until the roll passes. `DAM_OTHER` also falls
into the `magic` broad category in `check_immune`, so `IMM_MAGIC` mobs return
`IS_IMMUNE` and save unconditionally, making them permanently unpathable.

### PrimeSUD deviation -- implemented in `_mob_destination` in `path.py`

The `saves_spell` clause is dropped; mob targets resolve deterministically.
The level signal it encoded is already carried by the adjacent
`victim->level >= ch->level + 3` gate, which is retained verbatim, as are
every other disqualifier in the chain. Marked [PRIMESUD] at the site.
`HELP PATH` lists only the deterministic disqualifiers and never mentions a
roll, so the drop also brings the code in line with the player-facing text.


---

## act TO_ALL: ROM call sites inherited against a redefined constant

**Upstream:** `reference/1stMud4.5.3/src/h/bits.h`, line 121;
`reference/1stMud4.5.3/src/comm.c`, `act_new()`, lines 2288-2300.
Compared against ROM 2.4 via `reference/quickmud/rom24-quickmud-master.zip`:
`src/merc.h` line 487, `src/comm.c` `act_new()` line 2184.

### The bug

In ROM 2.4, `TO_ALL` is the plain enum value 4, and `act_new` loops only
`ch->in_room->people`. `TO_ALL` matches none of the four skip conditions, so it
means **everyone in ch's room, including ch** -- `TO_ROOM` plus the actor.

1stMud redefined `TO_ALL` as `BIT_E` and gave it a separate branch in `act_new`
that walks `descriptor_first`, a mud-wide broadcast which also excludes ch
(`vch != ch`). It did not convert any of the call sites it inherited from ROM.
The two sets are identical, one for one:

| file | sites |
|------|-------|
| `effects.c` | 8 (acid/fire/cold/shock item destruction) |
| `magic.c` | 8 (bless, holy aura, faerie fire, continual light, curse, invis object, poison weapon, remove curse) |
| `music.c` | 2 (room jukebox lyric lines) |
| `special.c` | 3 (troll gang taunt, ogre gang taunt, patrolman) |
| `update.c` | 1 (object affect wear-off, floor case) |

Every one was written against the room-scoped meaning, so the redefinition
silently flips two things at each site:

1. **Scope, room -> mud-wide.** Room chatter reaches every connected player.
   Worst offender is `spec_troll_member` / `spec_ogre_member`: `update.c` runs
   spec funs for every mob in the world, so the hood.are gang war broadcasts
   `$n says 'Let's rock.'` to the whole mud, forever. In single-player the lone
   player is always "everyone online", so it is unconditional spam from any
   room in any area once hood.are has been visited and stays resident.

2. **ch, included -> excluded.** A message whose only recipient was the actor is
   dropped entirely. Player-cast `continual light` on an already-glowable
   object, `poison weapon`, `remove curse`, and the bless/holy-aura family print
   nothing at all.

The `$n`/`$N` codes at those sites, the room-local `multi_hit` that follows the
gang taunts, and the `TO_ROOM` used by every neighbouring spec fun
(`spec_guard`, `spec_janitor`) all confirm the room-scoped reading.

### PrimeSUD fix -- implemented in `handler.py`

`TO_ALL` is defined as `TO_ROOM | TO_CHAR`, restoring ROM's meaning, and the
`act_new` router's `TO_ALL | TO_ZONE` branch is narrowed to `TO_ZONE` alone.
This corrects all ten ported call sites at once (`special.py` x2, `effects.py`
x4, `magic.py` x4) with no call-site churn; `BIT_E` (16) is left unused.
`TO_ZONE` keeps 1stMud's same-area descriptor semantics, which has no ROM
ancestor and no such conflict.

The `update.c` object-affect wear-off is not ported yet -- `skills_table.py`
carries the `msg_obj` strings but nothing reads them -- so it inherits the fix
whenever it lands.

`music.py`'s `song_update` had already reasoned its way to the room-scoped
behaviour independently and is unaffected.

---

## P-reset: mob-carried containers were never filled (PrimeSUD-side regression, fixed)

**Upstream:** `reference/1stMud4.5.3/src/db.c`, `reset_room` case `'P'`, lines 1532-1578

### The divergence

Not an upstream bug -- a PrimeSUD deviation whose stated rationale was wrong.
Upstream's `P` reset locates its container via `get_obj_type` (global scan for
the most recent instance) and explicitly accepts a **mob-carried** container:
`(LastObj->in_room == NULL && !last)` (db.c:1554) only rejects a carried
container when the previous reset in the walk failed.  PrimeSUD's port
searched **the resetting room's floor items only**, on the documented claim
that "converted stock P always fills a container O-placed in the same room".

That claim was false.  A full-world scan (31/07/2026) found 19 stock `P`
resets targeting containers E/G-given to a mob in the same room, all silently
skipped, plus one knock-on `G` skip (`last` cleared by the failed `P`):

- **mahntor** -- 8 door keys (2351-2358) inside the Ring-Keeper's key ring
  (2382, worn at waist).  Progression-blocking: the keys gate the
  closed+locked+**pickproof** doors of the 2388-2399 wing and have no other
  spawn source.
- **hitower** -- Mad Alchemist's pouch (spoon + 4 potions), spell binder's
  holstered wand, illusionist's beltpouch dust.
- **moria** -- coins in the cartographer's corpse carried by the huge python,
  plus the knock-on skip of the Moria level-2 map `G` that follows.
- **chapel** -- black marble ring inside the mummified head.
- **gnome** -- grain + peanuts in the scientist's wicker basket.

### PrimeSUD fix -- implemented in `mob.py`, `tools/are_to_primesud.py`

1. `reset_room` `'P'`: when the floor search misses, search the room's mobs'
   inventory and equipment for the container -- gated on `last_spawned`,
   mirroring db.c:1554.  Still room-scoped (never touches unloaded areas), so
   the lazy-loading rationale for avoiding a true global scan survives.
2. `reset_room` `'E'/'G'`: null-LastMob guard (log + skip) mirroring
   db.c:1592, replacing a latent `KeyError` on `world.chars[None]`.
3. Converter: `fix_exits`-style per-room reset-list checks (db.c:1136-1181) --
   `E`/`G` require a preceding `M` in their partitioned room list, `P` a
   preceding `O`/`E`/`G` -- rejected at conversion time as upstream rejects
   them at boot, so future data cannot silently drop content again.

`DESIGN.md` "P-reset container target" row updated to match.

---

## coin messages: unconditional or wrongly-gated plurals ("1 gold pieces", "1 silver coins")

**Upstream:** `reference/1stMud4.5.3/src/act_obj.c`, `do_steal` line 2317,
`do_sell` line 2883, `do_value` line 2953; `reference/1stMud4.5.3/src/handler.c`,
`create_money()` line 2258 (mixed-pile `OBJ_VNUM_COINS` template);
`reference/1stMud4.5.3/src/act_info.c`, line 1420 (examine money pile).

### The bug

Five money messages hard-code (or mis-gate) the plural coin noun:

- `do_sell`: `"You sell $p for %ld silver and %ld gold piece%s."` gates the `s`
  on **total cost**, not the gold part -- selling for 100 silver (cost 100,
  gold_part 1) prints "1 gold pieces", and cost 1 (0 gold) prints
  "0 silver and 0 gold piece".
- `do_value`: `"... %ld silver and %ld gold coins for $p'."` -- unconditional
  plural: "1 gold coins".
- `do_steal`: `"Bingo!  You got %d gold coins."` (and the silver/mixed
  variants) -- unconditional plural.
- `create_money` mixed pile: the `OBJ_VNUM_COINS` short-descr template is
  `"%d silver coins and %d gold coins"` -- "1 silver coins and 5 gold coins".
- examine pile: `"There are %ld gold and %ld silver coins in the pile."` --
  noun only attaches to the silver half, and is unconditionally plural.

In all five, the silver half of sell/value/steal already prints bare
("%ld silver"), with no noun at all.

### PrimeSUD fix — implemented in `shop.py`, `inventory.py`, `combat.py`, `info.py` (7bc0280)

Two treatments, by whether the message names an object:

1. `do_sell` / `do_value` (`shop.py`) and `do_steal` (`inventory.py`): drop the
   coin noun entirely -- "N silver and N gold". Silver already went bare
   upstream, and any gating of the noun misreads at some value, so symmetry
   beats repair.
2. `create_money` (`combat.py`) and `_examine_extras` (`info.py`) keep the noun
   -- they name an object/pile, and the `*_ONE` fallback objects are
   "A gold coin" -- but pluralise each half independently via
   `util.count_str`: "1 silver coin and 5 gold coins".

All sites `[PRIMESUD]`-commented; the two `[Verified:]` functions
(`create_money`, `_examine_extras`) have their tags extended.

---

## obj_update: timerless mob-loot spill accumulates as permanent world litter

**Upstream:** `reference/1stMud4.5.3/src/update.c`, `obj_update()` (corpse
decay spill); `reference/1stMud4.5.3/src/fight.c`, `make_corpse()` (only
potions, scrolls, and rot-death items get a content timer).

### The bug (upstream-masked)

When an NPC corpse decays, its contents spill to the room floor keeping
whatever timer they had -- and `make_corpse` stamps timers only on
potions/scrolls/rot-death items, so weapons, armour, containers, and coins
spill with no timer and never decay. 1stMud gets away with it because a
reboot rebuilds the world; PrimeSUD persists floor items across saves
(`r.<vnum>.items` lines), so mob-vs-mob combat areas accumulate loot
forever (measured: 299 persisted floor items, 186 in gangland alone).

### PrimeSUD fix — implemented in `update.py`, `inventory.py` (02/08/2026)

Mirrors 1stMud's own `ITEM_HAD_TIMER` shop idiom (`act_obj.c` sell/buy-back,
already ported in `shop.py`):

1. `obj_update` room spill: a spilled item with no timer gets
   `timer = randint(25, 40)` plus a `litter` extra flag (set via
   `set_item_extra_flag`, round-trips saves as `ef:` names).
2. `_get_triggers` (the chokepoint every `do_get` path calls): picking up a
   litter-flagged item pops the flag and the timer -- looted goods become
   the player's for keeps, and re-dropping them stays persistent (home
   decoration promise in `homes.py` intact).

Items with a canonical timer never carry the flag, so potions looted from
the floor still rot in inventory as upstream intends. Scavenger mobs that
grab litter tick it down in the NPC-inventory loop instead -- acceptable.

---

## advance_level: "You can now use" announced for skills the char doesn't know

**Upstream:** `reference/1stMud4.5.3/src/update.c`, lines 106-121 (gain_exp
skill-availability loop -- a 1stMud addition; ROM 2.4 prints no such message).

### The bug

The loop fires for every skill whose `skill_level(ch, sn)` equals the new
level, regardless of whether the char knows it. The verb is chosen by
`learned[sn] == 1` -> "learn", **else** -> "use" -- and the else branch
includes `learned == 0`. So a warrior hitting level 14 is told "You can now
use the earthquake spell" while `do_practice` refuses unknown skills
(`learned < 1`, act_info.c:3692) and spells can't be gained individually:
the message promises what the game then denies.

### PrimeSUD fix -- implemented in `combat.py` (advance_level)

Verb chosen by actionability: `learned == 0` -> "learn" (must `gain` it, or
its group, first) and `learned >= 1` -> "use" (known; practicable now).
The line still appears for unknown skills -- warrior/earthquake at 14 is
genuine ROM+1stMud data (`skills.dat`: warrior column 14, gainable via the
`attack` group) -- but no longer claims the char can already use them.
