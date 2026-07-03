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
offhand = player["equip"].get("offhand")
if offhand is not None and ITEM_TEMPLATES[offhand["vnum"]].get("type") == "weapon":
    one_hit(tr, player, target_inst, slot="offhand")
```

Only a confirmed weapon item proceeds to the hit; non-weapons in the offhand slot
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

`|` is bitwise OR, almost certainly a typo for `+`. Stock ROM used
increasing per-level damage tables here; 1stMud replaced them with this
expression, which for levels 1-50 produces a non-monotonic value stuck in
the 50-63 band (level 2 -> 50, level 13 -> 63, level 32 -> 50). Gaining
levels barely changes damage and can even lower it, and all seven spells
share one flat damage band.

### PrimeSUD fix -- implemented in `magic.py`

`high = level + 50` in all seven spell functions, giving the obviously
intended smooth scaling (`randint((level+50)/2, (level+50)*2)`). Each site
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
