# Skills Rewire Plan

## Goal

Replace `world.py`'s hand-rolled 6-entry skill section with data from `skills_table.py`
(149 entries, canonical 1stMud sn values).  Mirror 1stMud mechanics in consumers
where possible.  Cure light rewrite is deferred (next phase).

---

## Current state

| Thing | Old (`world.py`) | New (`skills_table.py`) |
|---|---|---|
| GSN values | Made-up (4001–4031) | Real 1stMud sn indices (e.g. `GSN_KICK=117`) |
| `skill_level` | Single int | 6-tuple per class |
| `rating` | Single int | 6-tuple per class |
| Spell discriminator | `"type": "spell"` field | `spell_fun != 'spell_null'` |
| Mana field | `"mana"` | `"min_mana"` |
| Total entries | 6 | 149 |

Skills in old table: cure light (27), sword (106), hand to hand (116),
kick (117), parry (118), recall (136).

---

## `world.py` changes

1. **Remove** old `GSN_*` constants (4001–4031) and old `SKILL_TABLE` / `SKILLS` /
   `WEAPON_GSN_MAP` blocks.

2. **Import** from `skills_table`:
   ```python
   from skills_table import (
       SKILL_TABLE as _ST_RAW,
       GSN_KICK, GSN_HAND_TO_HAND, GSN_PARRY, GSN_RECALL,
       GSN_SWORD, GSN_AXE, GSN_DAGGER, GSN_FLAIL, GSN_MACE, GSN_POLEARM,
       GSN_SPEAR, GSN_WHIP, GSN_SHIELD_BLOCK,
       GSN_SECOND_ATTACK, GSN_THIRD_ATTACK,
   )
   ```
   (Add others as needed later.)

3. **Build `SKILL_TABLE` + `SKILLS`** — mirrors current world.py structure
   (`SKILL_TABLE` list is source; `SKILLS` dict derived from it), with tuples
   flattened during list construction:
   ```python
   SKILL_TABLE = [
       (sn, {**data,
             "skill_level": min(data["skill_level"]),
             "rating":      min((v for v in data["rating"] if v > 0), default=1)})
       for sn, data in _ST_RAW
   ]
   SKILLS = dict(SKILL_TABLE)
   ```
   - `skill_level` → `min(tuple)` — earliest any class can learn it
   - `rating` → `min(non-zero)` — best rate; `default=1` guards all-zero edge case
     (cf. 1stMud: rating 0 means class can't practise individually)
   - All other fields kept as-is (`spell_fun`, `target`, `min_pos`, `min_mana`,
     `beats`, `noun_damage`, `msg_off`, `msg_obj`, `pgsn`)
   - **No `type` alias, no `mana` alias** — consumers updated to use `spell_fun`
     and `min_mana` directly

4. **Expand `WEAPON_GSN_MAP`** to all 8 weapon types:
   ```python
   WEAPON_GSN_MAP = {
       "sword":   GSN_SWORD,
       "axe":     GSN_AXE,
       "dagger":  GSN_DAGGER,
       "flail":   GSN_FLAIL,
       "mace":    GSN_MACE,
       "polearm": GSN_POLEARM,
       "spear":   GSN_SPEAR,
       "whip":    GSN_WHIP,
   }
   ```

---

## `combat.py` changes

### Imports
- Remove `GSN_SWORD` (no longer referenced directly)
- Add `GSN_SECOND_ATTACK`, `GSN_THIRD_ATTACK` from `world`

### `check_improve`
- `sk_rating = sk.get("rating", 1)` — still works; `rating` is flattened to a
  single int in `SKILLS`.  No change needed.

### `advance_level` (level-up skill notification)
- `data["type"] == "spell"` → `data["spell_fun"] != 'spell_null'`

### `multi_hit` — second/third attack via learned skills (mirror 1stMud fight.c)
Current code: primary hit → unarmed special → offhand.  Player has no second/third
attack skill check.  New order mirrors 1stMud (primary → offhand → extra attacks → unarmed special [PRIMESUD]):
```python
# Primary (unchanged)
one_hit(tr, player, target_inst)
if target_inst["hp"] == 0:
    return True

# Offhand weapon (1stmud uses WEAR_SECONDARY)
offhand = player["equip"].get("offhand")
if offhand is not None and ITEM_TEMPLATES[offhand["vnum"]].get("type") == "weapon":
   one_hit(tr, player, target_inst, slot="offhand")
   if target_inst["hp"] == 0:
      return True

# Second attack (cf. 1stMud multi_hit fight.c)
if player["learned"].get(GSN_SECOND_ATTACK, 0) > randint(1, 100):
    one_hit(tr, player, target_inst)
    if target_inst["hp"] == 0:
        return True

# Third attack (cf. 1stMud multi_hit fight.c)
if player["learned"].get(GSN_THIRD_ATTACK, 0) > randint(1, 100):
    one_hit(tr, player, target_inst)
    if target_inst["hp"] == 0:
        return True

# [PRIMESUD] Unarmed special move — unchanged, keep before extra attacks
if player["equip"].get("wield") is None:
    _try_special_move(tr, player, target_inst)
    if target_inst["hp"] == 0:
        return True

```

### `_weapon_skill` — refactor to mirror `get_weapon_sn` / `get_weapon_skill` (handler.c)

Unknown weapon type → sn `-1` (not `GSN_HAND_TO_HAND`); `-1` gets level-scaled
skill instead of a `learned[]` lookup.  Mirrors 1stMud exactly and is conceptually
correct: hand-to-hand proficiency does not transfer to an exotic weapon; level is the
proxy for general proficiency.

`WEAPON_GSN_MAP` fallback in `world.py` stays `None`/absent — callers use `.get(t, -1)`.

New helpers (replace current `_weapon_skill`):

```python
def _get_weapon_sn(player):
    """Return (sn, tpl_or_None) for player's wielded weapon (cf. get_weapon_sn handler.c)."""
    wobj = player["equip"].get("wield")
    if wobj is None:
        return GSN_HAND_TO_HAND, None
    tpl = ITEM_TEMPLATES[wobj["vnum"]]
    sn = WEAPON_GSN_MAP.get(tpl.get("weapon_type", ""), -1)
    return sn, tpl

def _get_weapon_skill(player, sn):
    """Return learned% for sn (cf. get_weapon_skill handler.c).
    sn==-1 (unknown weapon type) → 3*level, capped 100.
    """
    if sn == -1:
        return min(3 * player["level"], 100)
    return player["learned"].get(sn, 0)
```

Call sites in `one_hit`:
- `sn, tpl = _get_weapon_sn(player)` (or pass `slot` for offhand)
- `learned_pct = _get_weapon_skill(player, sn)`
- `check_improve(tr, player, sn, True, 5)` — skip when `sn == -1` (no skill to improve)

---

## `commands.py` changes

### `do_cast` — spell discriminator
```python
# old
if sk.get("type") != "spell":
# new
if sk.get("spell_fun", "spell_null") == "spell_null":
```

### `do_cast` — mana field
```python
# old
mana = sk.get("mana", 0)
# new
mana = sk.get("min_mana", 0)
```

### `do_skills` / `do_practice` / `do_affects`
- `SKILLS.get(sk_vnum)` — unchanged (still keyed by sn)
- `sk["name"]`, `sk.get("rating", 1)` — unchanged (flattened in build)

---

## Flags / risks

1. **GSN value change breaks saved `learned` dicts.**  Old keys 4001–4031 won't
   match new sn values.  Single-player game — no persistent cloud save, so
   existing saves become stale.  Acceptable; player state resets on next run.

2. **Memory.**  149 entries vs. 6.  `skills_table.py` is ~2300 lines.  Flag for
   on-device testing.  Mitigation: if too heavy, trim to only used SNs at startup.

3. **Deferred:** cure light spell implementation rewrite (`do_cast` effect dispatch
   via `spell_fun` string → actual Python function).  Current `effect`/`heal_dice`/
   `level_div` will be broken as a known issue until that phase.
