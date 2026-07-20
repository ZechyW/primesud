# HANDOFF — path border-graph work (2026-07-20)

Session continuity doc for another PC. Delete after work completes
(per CLAUDE.md: completed plan docs are deleted, durable decisions
harvested into DESIGN.md first).

## Where we are

Branch `dev`. The `path` command port was reviewed, then a 5-phase fix
plan was approved by the user. Phases 1-3 committed and green; phase 4
was ~30% done by a subagent when this PC's network proxy (McAfee Web
Gateway) killed the API session. Partial phase-4 work is committed as a
WIP commit (unreviewed — treat accordingly).

- `388****` feat(path): port + phase 1 (NPC-gated quest checks in
  `_mob_destination`, message-edge tests in tests/test_path.py)
- `d94****` fix(magic): phase 2 — can_see filter at all five world
  mob-lookup sites (gate/summon/portal-nexus scans, path `_loaded_mob`,
  `_find_unloaded_mob` which gained an observer arg). Verified tags
  extended; invis-mob tests added.
- `1bc****` fix(magic): phase 3 — locate object: can_see_obj filter +
  invisible-carrier "one is in somewhere" branch; docstring notes
  loaded-areas-only scan; PARITY.md row for unloaded-area coverage.
  New tests/test_locate_object.py.
- WIP commit (this one): HANDOFF.md + phase-4 partials.

Suite was 1127 passed + `python tools/check_ascii_py.py` clean before
the WIP files landed.

## Why phase 4 exists (audit findings)

Corridor-bounded `_route` in src/path.py is broken on real data
(measured by loading all areas in CPython and comparing corridor BFS vs
unrestricted BFS over all 3124 source rooms x 48 target areas):
- 536/2256 ordered area pairs: NO route found though one exists.
- 22,938 source-room->area cases: route longer than true shortest
  (worst sampled: 71 steps reported vs 18 true — limbo room 2 ->
  olympus).
- 30% of exact-room (mob) targets unreachable (2.56M of 8.66M checks).
- Mechanism: intra-area partitioning. `world._AREA_ADJ` itself verified
  EXACT vs real room exits (both directions). Canonical failure:
  catacomb->midgaard; chain catacomb->dwarven->moria->midgaard, but
  moria entered from dwarven cannot reach its midgaard exit without
  passing through midennir. Area-level chains assume any entry of an
  area reaches any exit; real areas break that constantly.
- Same machinery underlies `run` (movement.py -> info.find_path_to_area),
  which survives via a load-all fallback (the 5.9MB behaviour far-area
  eviction exists to prevent) and silently walks overlong routes.

## Phase 4 — border graph (in progress)

Design (user-approved): precompute a static border graph offline; at
runtime Dijkstra over it + two live BFS legs inside already-loaded
areas. Zero area loads at routing time. True shortest paths.

DONE (unreviewed WIP):
- tools/build_path_index.py — builds the index; core is importable
  (build_records(rooms_data)) for tests; main() bootstraps world like
  the tests do (src + pc_shim on sys.path, init_world, iterate
  ROOM_DEFS to force-load, use ROOM_DEFS._data).
- src/paths.idx — generated: 637 `S|from|to|dist|dirs` intra-area
  segment records (entry room -> exit room per area, BFS restricted to
  that area, dirs in _compress_path run format e.g. "3n2e"), 141
  `X|from|dir|to` cross-area exit records, ASCII, sorted, header line.
  REVIEW ITEM: S=637 is below the rough few-thousand ballpark — verify
  per-area coverage (midgaard should contribute many pairs) and
  determinism (run tool twice, byte-identical) before trusting.

NOT STARTED:
- src/path.py `_route()` rewrite. Contract: same signature/returns
  (("",0) no-walk / (route,steps) / (None,0) unreachable); ONE f.read()
  of paths.idx (module const PATH_INDEX_FILE = "paths.idx", cwd is
  src/); parse to segs[from]->[(to,dist,dirs)], xedges[from]->
  [(dir,to)]; live BFS legs: source leg from player room restricted to
  source area (always loaded) giving dist+dirs to each source-area exit
  room (and to target_room if same area); target leg (mob targets) from
  each entry room of the target area (X-record targets with that tag)
  to the mob's room — target area is loaded by the mob lookup; Dijkstra
  int weights, O(V^2) linear-min (NO heapq — device availability
  unverified), virtual start seeded by source leg; area-target goal =
  first settled node crossing an X edge into target-tag room (upstream
  stops at first room of destination area); mob-target goal = virtual
  node fed by target-leg edges PLUS direct same-area edge (partitioned
  source area may still require leave-and-re-enter — graph handles it
  if direct edge is just one candidate). Reconstruct by concatenating
  dirs, then merge adjacent same-direction runs across boundaries
  ("3n"+"2n" -> "5n"; format is count-then-dir, absent count = 1).
  Steps must equal decoded route length (assert in tests, not runtime).
  Tie-break note: step count matches upstream, chosen equal-length
  route may differ ([PRIMESUD] docstring note). Keep do_path /
  _area_lookup / _loaded_mob / _mob_destination and all messages
  EXACTLY as-is (verified against 1stMud act_enter.c); keep the
  finally world.maybe_evict(player, True); drop _area_chain/corridor
  imports and _ensure_area_by_tag preloading.
- tests/test_path.py rewrite: replace _AREA_ADJ monkeypatch setup with
  build_records on the synthetic world -> tmp index -> monkeypatch
  path_cmd.PATH_INDEX_FILE. Keep every existing test's intent (eviction
  test changes: area targets now load NOTHING beyond source area). NEW:
  partition test (A:a1 -> B:b1, B:b2 -> C:c1, no b1->b2 inside B,
  b1 -> D:d1 -> b2; route a1-b1-d1-b2-c1 must be found for area-C and
  mob-in-c1 targets, exact steps); run-merge test ("2n"+"n" -> "3n").
- NEW tests/test_path_realworld.py: load real world (snapshot/restore
  world state like conftest fresh_world teardown), build records in
  memory, ~8 sample pairs asserting _route steps == inline unrestricted
  full-world BFS AND that walking the route string through
  ROOM_DEFS._data exits actually arrives. Must include catacomb ->
  midgaard and limbo room 2 -> olympus (old 71 vs true ~18).
- Docs: DESIGN.md path paragraph (search "src/path.py") -> border-graph
  description + one clause on why corridor was replaced (536 no-routes
  / 30% room targets); fix eviction paragraph's path sentence;
  FEATURES.md "Bounded world paths" bullet -> exact routes, zero
  route-time loads; docs/PARITY.md path paragraph likewise.
- Verify: full pytest + check_ascii_py + tool determinism. Commit
  feat(path) after review.

## Phase 5 — approved, not started

`run` (movement.py / info.find_path_to_area) adopts the border graph;
drop the load-all find_area_paths fallback. Fixes run's silent 3-4x
overlong walks and 5.9MB fallback loads. Separate
refactor(movement) commit.

## Environment / process notes

- THIS PC's proxy chokes on large single API payloads and killed a
  subagent (McAfee Web Gateway error). If the other PC shares the
  proxy: chunk file reads (~250 lines), write long files incrementally
  (small Write + ~120-line Edit appends), truncate command output.
- Subagent management rules: ~/.claude/delegation-framework.md on this
  PC (contract scoping, durable increments >200 lines, stall = resume
  same agent, report-back format). Copy to the other PC's ~/.claude if
  delegating there; global CLAUDE.md there should point at it.
- A CONCURRENT agent session is porting slist: src/groups.py,
  tests/conftest.py, tests/test_slist.py, rows in docs/PARITY.md are
  THEIRS — never sweep into commits (bit us once already; caught).
- Verified-port rule: user granted permission for the phase-2 gate/
  summon/portal edits (done). Phase 4/5 need no further permission
  (path.py is unverified new code; movement/info edits are toward
  documented fidelity — still re-check tags when touching).
- Audit scripts lived in this PC's session scratchpad (not
  transferred): corridor_audit.py (all-pairs corridor vs global BFS)
  and adj_audit.py (_AREA_ADJ walkability + pair dissection). Rebuild
  from the methodology above if needed (~80 lines each, CPython, loads
  world via src + pc_shim + init_world).
