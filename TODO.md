# TODO

Loose ends that don't belong in a specific plan file.

## Roadmap (18/07/2026)

Two-track release plan:

1. **Engine 1.0 first**: sweep that all general 1stMud systems/mechanics are
   ported (minus multiplayer-only ones -- see DESIGN.md for settled
   non-ports) and finalised; close the open items below and the
   on-calculator checklist, then tag a main release (`v1.0.0`).
2. **Content track after**: new-content additions (new classes, areas,
   quests -- e.g. SWORDSMAN_PLAN.md) land only after the 1.0 tag, released
   as content versions on top of the stable engine. Keeps "1stMud parity"
   auditable separately from "PrimeSUD original content".

## Combat

(nothing outstanding)

## Items

(nothing outstanding)

## Magic

(nothing outstanding)

## Classes

(nothing outstanding -- prestige tiering shipped 11/07/2026, see DESIGN.md
"Multiclass prestige tiering")

## Commands

- Genuinely still-deferred commands (commented-out rows in
  `commands.py:_CMD_TABLE`): `gossip`, `shout`, `auction`,
  immortal commands. Port when/if a solo gameplay hook appears.
  (`alias`/`unalias` and social actions ported 10/07/2026; the 20/07/2026
  S-effort batch ported `play`, `socials`, `sshow`, `brief`, `compact`,
  `show`, `title`, `version`, `heel`, `grlist`, `backup`, `prime`; later
  parity work ported `path`, `bank`, and `balance` -- see docs/PARITY.md.)

## Housing

- **Player housing (homes.c) — discussion deferred (19/07/2026).** Not a
  parity item: no stock area carries `AREA_PLAYER_HOMES`, so the system is
  inert even upstream without imm-built content, and the faithful port
  needs runtime room creation + world-state persistence (our save surface
  is player-only). Possible middle ground for 1.0: ship it as a [PRIMESUD]
  feature adapted to our context — pre-built home area in area data,
  `home` command subset (buy/recall/describe/furnish), home state saved as
  a player-owned blob — rather than full OLC. Decide before the 1.0 gate.

## Area data

- **Deferred runtime hooks for converter-emitted fields** — the 2026-07
  converter audit brought `are_to_primesud.py` (the single ROM 2.4
  converter; formerly `are_to_primesud_quickmud.py`, renamed after the
  1stMud-format converter was deleted) to a lossless schema. Re-audited
  2026-07-10: `no_sac`, container `container_max_item_weight` /
  `container_weight_mult`, food/drink `poisoned`, mob `group` (assist),
  room `heal_rate`/`mana_rate` (regen), and `light_hours` are all consumed
  now; room `owner` is settled (can_see_room always-permissive, see
  DESIGN.md). Still unconsumed:
  - object `condition` (spawn wear-state) — item condition/wear not
    modeled at all (see quest.py reward note)
  - mob `material` — only in-scope 1stMud consumer is the death_cry
    case-1 guard (`material == 0` falls through to guts); no-op for stock
    data since every stock mob is material `'0'`. Cheap fidelity fix via
    `MOB_DEFS[tpl].get("material")` if ever wanted — see comment at
    `combat.py:_DEATH_CRY_CASES`
  - object `values` raw value[0..4] fallback for item types with no
    dedicated decode (furniture max-occupants/position flags, key linked
    vnum, map, portal, jukebox, ...) — emitted only when nonzero
    (2026-07-05 audit); runtime reads via `obj.get("values", ...)` when a
    consumer (e.g. furniture occupancy, see DESIGN.md furniture row) gets
    ported
- **No `fix_exits` equivalent at world load** — QuickMUD's post-boot pass
  (db.c fix_exits) nulls exits whose destination room doesn't exist and
  auto-sets `no_mob` on rooms with zero resolvable exits. The per-file
  converter architecturally can't do this (cross-area vnums); the runtime
  has no such pass either. Currently zero behavioral impact (audited: the
  only affected stock room, newthalos 9706, is unreachable anyway), but a
  future area with a dangling exit would surface it. Belongs in world.py
  after-load if ever needed.
- **Room flag `save_objs` (bit 22, 1stMud extension) has no runtime reader** —
  resolved 19/07/2026 (parity sweep): its only stock use is player-home
  floor persistence (homes.c:313); the home system is unported, so the
  flag is N/A. No runtime reader needed.

## Tests

(nothing outstanding)

## Platform

- **Validate mobs.idx heap headroom on device (21/07/2026)** -- the index
  grew 32KB -> 58KB (all templates, counter metadata). `mobkills`/
  `mobdeaths` and `_find_unloaded_mob` each do one whole-file `read()` +
  `split("\n")` (~120KB transient). Sanity-check on hardware: `mobkills`
  with populated counters, and portal/summon into an unloaded area;
  watch `gc.mem_free`.
- **Validate fling-scroll tuning on physical Prime** — touch scrollback now
  uses row-step fling easing with touch-cancel/release guard
  (`tml_prime.py`, 06/07/2026). Re-tune thresholds/decay on device if it
  still feels jumpy or too eager.
- **On-calculator checklist from the 08/07 planning queue** (consolidated
  final audit 10/07/2026; one walk of the world covers all, ordered by area):
  - *Mud School*: acolyte demo prog end to end (entry greeting, donate one
    silver twice, give any item); prog-room idle CPU/heap vs an empty room
    (`gc.mem_free`, act-heavy room); school banner light burnout pacing
    (flicker at <=5 hours, both goes-out messages)
  - *Midgaard*: idle tick cost with the full area loaded (regen + weather +
    mobprog pulse); weather message cadence over several ticks; buy + name a
    pet at the pet shop, `group` rendering on the 64-col screen
  - *Any dark room (e.g. caves/sewers)*: automap rendering while dark;
    "It is pitch black ... " + glowing red eyes on the physical screen;
    light a torch and re-look
  - *Anywhere*: `explored`/`score` permille after the walk; `gc.mem_free`
    before/after the ~2KB explored-mask alloc and a save/load round-trip
  - *Path/run border graph (20/07/2026)*: `path midgaard` from a far area
    and `run` picker to a multi-area destination on hardware -- route
    correctness (walk it), plus latency/`gc.mem_free` around the
    per-command paths.idx parse (~780 records, one f.read + transient
    dicts per `path`/no-arg `run`)
  - *Autoskill (18/07/2026)*: idle-fight CPU/`gc.mem_free` with autoskill on
    during a long fight in a mobprog-heavy room (rotation scan runs per
    violence pulse); message volume on the 64-col screen (one auto action
    per ~2s round plus combat spam -- confirm readable); `autoskill edit`
    on hardware -- navpad sentinel remap via `poll_char(dict)`, status-line
    cursor legibility, `*` toggle feel
- **Far-area eviction: validated on device 14/07/2026** via the (since
  deleted) `debug evicttest` command -- all checks passed: load-all, evict
  to keep-set, far-area unload, dropped-item round-trip through
  `_pending_room_items`, recovery via `get`. Remaining spot-check during
  the on-calculator walk above: long natural wander crossing >12 areas
  (evicttest forced `AREA_CACHE_MAX = 1`; stock cap 12 untested in play).
  The 1 MB stock-heap device remains unsupported (keep-set floor ~12 areas
  exceeds it).
