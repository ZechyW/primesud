"""Tests for world.py lazy area loading, save delta application, and edge cases.

Covers:
- LazyDict on-demand loading and load_all_on_iter behavior
- Cross-area reset cascade ordering
- Save delta application (_apply_pending_deltas)
- Mob ID/room alignment in pending deltas
- Room item persistence across save cycles for unvisited areas
- Area age accumulation for unloaded areas
- spec_fun/shop present on MOB_DEFS entries after area load (baked format)
- Serialization round-trip with lazy areas
"""
import os
import sys

import pytest

import world
from world import (
    LazyDict, ROOM_DEFS, MOB_DEFS, ITEM_DEFS, AREA_DEFS, DOOR_DEFS,
    _vnum_to_tag, _ensure_area, _load_area, _load_all,
    _apply_pending_deltas, _retry_pending_deltas,
    is_area_loaded, reset_lazy, init_world,
)


# ---------------------------------------------------------------------------
# Minimal mob template that satisfies create_mobile's field access
# ---------------------------------------------------------------------------
def _mob_tpl(level=1, **overrides):
    tpl = {
        "short_descr": "a test mob",
        "level": level,
        "hp_dice": (1, 1, 10),
        "hitroll": 0,
        "armor": (0, 0, 0, 0),
        "damage": (1, 2, 0),
        "dam_type": "punch",
    }
    tpl.update(overrides)
    return tpl


def _item_tpl(name="test item", **overrides):
    tpl = {
        "name": name,
        "desc": "A test item.",
        "type": "treasure",
        "slot": None,
        "weight": 1,
        "value": 10,
    }
    tpl.update(overrides)
    return tpl


# ===== LazyDict basics =====================================================

class TestLazyDict:
    """LazyDict triggers area load on access and respects load_all_on_iter."""

    def test_getitem_triggers_load(self, fresh_world):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}})
        fw.setup()

        assert not is_area_loaded("alpha")
        _ = ROOM_DEFS[100]
        assert is_area_loaded("alpha")
        assert ROOM_DEFS._data[100]["name"] == "R100"

    def test_contains_triggers_load(self, fresh_world):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}})
        fw.setup()

        assert not is_area_loaded("alpha")
        assert 100 in ROOM_DEFS
        assert is_area_loaded("alpha")

    def test_contains_returns_false_for_unknown_vnum(self, fresh_world):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}})
        fw.setup()

        assert 999 not in ROOM_DEFS

    def test_get_triggers_load(self, fresh_world):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}})
        fw.setup()

        result = ROOM_DEFS.get(100)
        assert result is not None
        assert is_area_loaded("alpha")

    def test_get_returns_default_for_missing(self, fresh_world):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}})
        fw.setup()

        assert ROOM_DEFS.get(999, "nope") == "nope"

    def test_iter_loads_all_when_lai_true(self, fresh_world):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}})
        fw.register_area("beta", 200, 299,
                         rooms={200: {"name": "R200", "exits": {}}})
        fw.setup()

        assert not is_area_loaded("alpha")
        assert not is_area_loaded("beta")
        keys = list(ROOM_DEFS)  # ROOM_DEFS has load_all_on_iter=True
        assert is_area_loaded("alpha")
        assert is_area_loaded("beta")
        assert 100 in keys
        assert 200 in keys

    def test_iter_skips_load_when_lai_false(self, fresh_world):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}})
        fw.setup()

        # world.rooms has load_all_on_iter=False
        keys = list(world.rooms)
        assert not is_area_loaded("alpha")
        assert keys == []

    def test_len_loads_all_when_lai_true(self, fresh_world):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}})
        fw.setup()

        assert len(ROOM_DEFS) == 1
        assert is_area_loaded("alpha")

    def test_setdefault_triggers_load(self, fresh_world):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}})
        fw.setup()

        result = ROOM_DEFS.setdefault(100, {"name": "fallback"})
        assert result["name"] == "R100"
        assert is_area_loaded("alpha")


# ===== _vnum_to_tag =========================================================

class TestVnumToTag:

    def test_exact_boundaries(self, fresh_world):
        fw = fresh_world
        fw.register_area("alpha", 100, 199)
        fw.setup()

        assert _vnum_to_tag(100) == "alpha"
        assert _vnum_to_tag(199) == "alpha"
        assert _vnum_to_tag(99) is None
        assert _vnum_to_tag(200) is None

    def test_gap_between_areas(self, fresh_world):
        fw = fresh_world
        fw.register_area("alpha", 100, 149)
        fw.register_area("beta", 200, 249)
        fw.setup()

        assert _vnum_to_tag(175) is None


# ===== Single area load =====================================================

class TestSingleAreaLoad:
    """_load_area merges rooms, mobs, items, doors, resets correctly."""

    def test_rooms_tagged_with_area(self, fresh_world):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}},
                                101: {"name": "R101", "exits": {}}})
        fw.setup()

        _load_area("alpha")
        assert ROOM_DEFS._data[100]["area"] == "alpha"
        assert ROOM_DEFS._data[101]["area"] == "alpha"

    def test_mob_defs_merged(self, fresh_world):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}},
                         mobiles={100: _mob_tpl()})
        fw.setup()

        _load_area("alpha")
        assert 100 in MOB_DEFS._data
        assert MOB_DEFS._data[100]["level"] == 1

    def test_item_defs_merged(self, fresh_world):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}},
                         objects={100: _item_tpl()})
        fw.setup()

        _load_area("alpha")
        assert 100 in ITEM_DEFS._data
        assert ITEM_DEFS._data[100]["name"] == "test item"

    def test_door_state_captured(self, fresh_world):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {
                             "n": {"to": 101, "isdoor": True,
                                   "closed": True, "locked": True}
                         }},
                                101: {"name": "R101", "exits": {}}})
        fw.setup()

        _load_area("alpha")
        assert 100 in DOOR_DEFS
        assert DOOR_DEFS[100]["n"]["closed"] is True
        assert DOOR_DEFS[100]["n"]["locked"] is True

    def test_resets_partitioned_to_rooms(self, fresh_world):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}},
                                101: {"name": "R101", "exits": {}}},
                         mobiles={100: _mob_tpl()},
                         objects={150: _item_tpl()},
                         resets=(
                             ("M", 100, 1, 100, 1),
                             ("O", 150, 101),
                         ))
        fw.setup()

        _load_area("alpha")
        r100_resets = ROOM_DEFS._data[100].get("resets", [])
        r101_resets = ROOM_DEFS._data[101].get("resets", [])
        assert any(e[0] == "M" for e in r100_resets)
        assert any(e[0] == "O" for e in r101_resets)

    def test_area_defs_updated(self, fresh_world):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}},
                         area={"name": "Alpha Land", "vnums": (100, 199)})
        fw.setup()

        _load_area("alpha")
        adef = next(a for a in AREA_DEFS if a["tag"] == "alpha")
        assert adef["name"] == "Alpha Land"
        assert adef["room_vnums"] == [100]

    def test_spec_fun_present_on_mob_defs(self, fresh_world):
        """spec_fun is baked into the MOBILES entry by the converter now
        (cf. tools/are_to_primesud.py) -- no separate merge step."""
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}},
                         mobiles={100: _mob_tpl(spec_fun="spec_test")})
        fw.setup()

        _load_area("alpha")
        assert MOB_DEFS._data[100]["spec_fun"] == "spec_test"

    def test_shop_present_on_mob_defs(self, fresh_world):
        """shop dict is baked into the MOBILES entry by the converter now
        (cf. tools/are_to_primesud.py) -- no separate merge step."""
        fw = fresh_world
        shop = {"keeper": 100, "buy_types": ["weapon"],
                "profit_buy": 120, "profit_sell": 40,
                "open_hour": 0, "close_hour": 23}
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}},
                         mobiles={100: _mob_tpl(shop=shop)})
        fw.setup()

        _load_area("alpha")
        assert MOB_DEFS._data[100]["shop"]["keeper"] == 100


# ===== Cross-area reset cascade =============================================

class TestCrossAreaCascade:
    """When area A's resets reference rooms in area B, loading A triggers B."""

    def test_cross_area_mob_reset_triggers_other_area_load(self, fresh_world):
        """M-reset in alpha places mob in beta's room -> beta loads."""
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "A-R100", "exits": {}}},
                         mobiles={100: _mob_tpl()},
                         resets=(("M", 100, 1, 200, 1),))  # room 200 is in beta
        fw.register_area("beta", 200, 299,
                         rooms={200: {"name": "B-R200", "exits": {}}})
        fw.setup()

        _load_area("alpha")
        assert is_area_loaded("beta"), "beta should be loaded by cascade"
        assert 200 in ROOM_DEFS._data

    def test_cross_area_object_reset_triggers_other_area_load(self, fresh_world):
        """O-reset in alpha places item in beta's room -> beta loads."""
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "A-R100", "exits": {}}},
                         objects={150: _item_tpl()},
                         resets=(("O", 150, 200),))  # room 200 is in beta
        fw.register_area("beta", 200, 299,
                         rooms={200: {"name": "B-R200", "exits": {}}})
        fw.setup()

        _load_area("alpha")
        assert is_area_loaded("beta")

    def test_cascade_does_not_infinite_loop(self, fresh_world):
        """Mutual cross-references don't loop: _LOADED_AREAS guard works."""
        fw = fresh_world
        # alpha reset -> beta room, beta reset -> alpha room
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "A-R100", "exits": {}}},
                         mobiles={100: _mob_tpl()},
                         resets=(("M", 100, 1, 200, 1),))
        fw.register_area("beta", 200, 299,
                         rooms={200: {"name": "B-R200", "exits": {}}},
                         mobiles={200: _mob_tpl()},
                         resets=(("M", 200, 1, 100, 1),))
        fw.setup()

        # Should complete without infinite recursion
        _load_area("alpha")
        assert is_area_loaded("alpha")
        assert is_area_loaded("beta")

    def test_cascade_half_populated_room_defs(self, fresh_world):
        """When alpha triggers beta during reset partitioning, alpha's rooms
        added before the cascade point should be visible to beta's resets."""
        fw = fresh_world
        # alpha has rooms 100,101. Its reset references beta room 200.
        # beta's reset references alpha room 100 (already added to ROOM_DEFS).
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "A-R100", "exits": {}},
                                101: {"name": "A-R101", "exits": {}}},
                         mobiles={100: _mob_tpl()},
                         resets=(("M", 100, 1, 200, 1),))
        fw.register_area("beta", 200, 299,
                         rooms={200: {"name": "B-R200", "exits": {}}},
                         mobiles={200: _mob_tpl()},
                         resets=(("M", 200, 1, 100, 1),))
        fw.setup()

        _load_area("alpha")
        # beta's M-reset targeted room 100 (in alpha). It should have been
        # partitioned to room 100's resets.
        r100_resets = ROOM_DEFS._data[100].get("resets", [])
        has_beta_mob = any(e[0] == "M" and e[1] == 200 for e in r100_resets)
        assert has_beta_mob, (
            "beta's M-reset for room 100 should be partitioned there; "
            "got resets: %r" % r100_resets
        )


# ===== Pending mob save deltas ==============================================

class TestPendingMobDeltas:
    """_apply_pending_deltas kills excess mobs, moves survivors, and
    spawns fresh instances for any shortfall vs the saved population."""

    def test_excess_mobs_killed(self, fresh_world):
        """Save says 1 instance, reset created 2 -> excess killed."""
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}},
                         mobiles={100: _mob_tpl()},
                         resets=(
                             ("M", 100, 3, 100, 3),  # gl=3, rl=3
                             ("M", 100, 3, 100, 3),
                             ("M", 100, 3, 100, 3),
                         ))
        # Save data says only 1 instance of tpl 100, in room 100
        world._pending_mob_saves[100] = [100]
        fw.setup()

        _load_area("alpha")
        # reset_area spawned 3, delta should kill 2
        live = [mid for mid, inst in world.chars.items()
                if inst.get("is_npc") and inst["tpl"] == 100]
        assert len(live) == 1

    def test_mob_moved_to_saved_room(self, fresh_world):
        """Save says mob is in room 101, reset put it in 100 -> moved."""
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}},
                                101: {"name": "R101", "exits": {}}},
                         mobiles={100: _mob_tpl()},
                         resets=(("M", 100, 1, 100, 1),))
        world._pending_mob_saves[100] = [101]  # save says room 101
        fw.setup()

        _load_area("alpha")
        live = [(mid, inst["room"]) for mid, inst in world.chars.items()
                if inst.get("is_npc") and inst["tpl"] == 100]
        assert len(live) == 1
        assert live[0][1] == 101, "mob should be moved to saved room 101"
        # Room 101 mob list should contain it
        assert live[0][0] in world.rooms._data[101]["mobs"]
        # Room 100 mob list should NOT contain it
        assert live[0][0] not in world.rooms._data[100]["mobs"]

    def test_mayor_stays_in_reset_room(self, fresh_world):
        """Mayor position is not restored without its process-local route state."""
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}},
                                101: {"name": "R101", "exits": {}}},
                         mobiles={100: _mob_tpl(spec_fun="spec_mayor")},
                         resets=(("M", 100, 1, 100, 1),))
        world._pending_mob_saves[100] = [101]
        fw.setup()

        _load_area("alpha")

        live = [inst for inst in world.chars.values()
                if inst.get("is_npc") and inst["tpl"] == 100]
        assert len(live) == 1
        assert live[0]["room"] == 100
        assert 100 not in world._pending_mob_saves

    def test_cross_area_move_deferred(self, fresh_world):
        """Mob saved in unloaded area's room -> move deferred, not lost."""
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}},
                         mobiles={100: _mob_tpl()},
                         resets=(("M", 100, 1, 100, 1),))
        fw.register_area("beta", 200, 299,
                         rooms={200: {"name": "R200", "exits": {}}})
        # Save says mob is in room 200 (beta, not loaded yet)
        world._pending_mob_saves[100] = [200]
        fw.setup()

        _load_area("alpha")
        # Mob should still exist (not killed), room move deferred
        live = [mid for mid, inst in world.chars.items()
                if inst.get("is_npc") and inst["tpl"] == 100]
        assert len(live) == 1
        # Pending delta should remain for this template
        assert 100 in world._pending_mob_saves

    def test_shortfall_spawned(self, fresh_world):
        """Save says 2 instances, reset created 1 -> shortfall spawned fresh."""
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}},
                                101: {"name": "R101", "exits": {}}},
                         mobiles={100: _mob_tpl()},
                         resets=(("M", 100, 2, 100, 1),))  # room limit 1 -> 1 spawn
        world._pending_mob_saves[100] = [100, 101]
        fw.setup()

        _load_area("alpha")
        live = sorted(inst["room"] for inst in world.chars.values()
                      if inst.get("is_npc") and inst["tpl"] == 100)
        assert live == [100, 101]
        assert 100 not in world._pending_mob_saves

    def test_shortfall_spawn_gets_reset_equipment(self, fresh_world):
        """Spawned shortfall mob receives the E/G gear trailing its M reset."""
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}},
                                101: {"name": "R101", "exits": {}}},
                         mobiles={100: _mob_tpl()},
                         objects={150: _item_tpl(slot="wield"),
                                  151: _item_tpl()},
                         resets=(("M", 100, 2, 100, 1),
                                 ("E", 150, "wield", -1),
                                 ("G", 151, -1)))
        world._pending_mob_saves[100] = [100, 101]
        fw.setup()

        _load_area("alpha")
        spawned = [inst for inst in world.chars.values()
                   if inst.get("is_npc") and inst["tpl"] == 100
                   and inst["room"] == 101]
        assert len(spawned) == 1
        inst = spawned[0]
        assert inst["equip"].get("wield", {}).get("vnum") == 150
        assert [o["vnum"] for o in inst["inv"]] == [151]

    def test_partial_deferral_keeps_placed_mobs(self, fresh_world):
        """Mixed loadable/unloadable saved rooms: the placed mob survives
        the retry pass untouched; the deferred room spawns once loadable."""
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}},
                                101: {"name": "R101", "exits": {}}},
                         mobiles={100: _mob_tpl()},
                         resets=(("M", 100, 2, 100, 1),))
        fw.register_area("beta", 200, 299,
                         rooms={200: {"name": "R200", "exits": {}}})
        world._pending_mob_saves[100] = [101, 200]
        fw.setup()

        _load_area("alpha")
        live = [(mid, inst["room"]) for mid, inst in world.chars.items()
                if inst.get("is_npc") and inst["tpl"] == 100]
        assert len(live) == 1
        mid = live[0][0]
        assert live[0][1] == 101
        # Full saved list stays pending until every room is loadable
        assert world._pending_mob_saves[100] == [101, 200]

        _load_area("beta")
        _retry_pending_deltas()
        live = sorted((m, inst["room"]) for m, inst in world.chars.items()
                      if inst.get("is_npc") and inst["tpl"] == 100)
        assert len(live) == 2
        assert (mid, 101) in live       # placed mob not culled or moved
        assert sorted(r for _, r in live) == [101, 200]
        assert 100 not in world._pending_mob_saves

    def test_mob_id_alignment_with_gaps(self, fresh_world):
        """When IDs aren't contiguous (gap from mid-session death + respawn),
        _apply_pending_deltas aligns by sorted ID order, not creation order."""
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}},
                                101: {"name": "R101", "exits": {}}},
                         mobiles={100: _mob_tpl()},
                         resets=(
                             ("M", 100, 2, 100, 2),
                             ("M", 100, 2, 100, 2),
                         ))
        world._pending_mob_saves[100] = [100, 101]  # 2 saved rooms
        fw.setup()

        _load_area("alpha")
        # reset_area spawns 2 with sequential IDs. Sorted IDs map to saved
        # rooms in order. First mob -> room 100, second -> room 101.
        live = sorted(
            [(mid, inst["room"]) for mid, inst in world.chars.items()
             if inst.get("is_npc") and inst["tpl"] == 100],
            key=lambda x: x[0]
        )
        assert len(live) == 2
        assert live[0][1] == 100
        assert live[1][1] == 101


# ===== Pending room item deltas =============================================

class TestPendingRoomItems:
    """_apply_pending_deltas restores room items from save tokens."""

    def test_room_items_restored(self, fresh_world):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}},
                         objects={150: _item_tpl()})
        # Simulated save token for room 100
        world._pending_room_items[100] = "v:150;c:10"
        fw.setup()

        _load_area("alpha")
        items = world.rooms._data[100]["items"]
        assert len(items) == 1
        assert items[0]["vnum"] == 150

    def test_room_items_for_other_area_not_consumed(self, fresh_world):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}})
        fw.register_area("beta", 200, 299,
                         rooms={200: {"name": "R200", "exits": {}}})
        world._pending_room_items[200] = "v:250;c:5"
        fw.setup()

        _load_area("alpha")
        # Beta's pending items should remain unconsumed
        assert 200 in world._pending_room_items


# ===== Room item loss across save cycles for unvisited areas ================

class TestRoomItemSaveCyclePrecondition:
    """Unvisited areas' room items stay in _pending_room_items (not in
    world.rooms). _serialize_world must re-serialize them separately."""

    def test_unvisited_area_room_items_in_pending(self, fresh_world):
        """After load, unvisited area's room items stay in _pending_room_items."""
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}})
        fw.register_area("beta", 200, 299,
                         rooms={200: {"name": "R200", "exits": {}}})
        world._pending_room_items[200] = "v:250;c:5"
        fw.setup()

        # Only load alpha (player visits alpha, not beta)
        _load_area("alpha")

        # Beta's items are still pending
        assert 200 in world._pending_room_items
        # Beta's rooms are NOT in world.rooms._data
        assert 200 not in world.rooms._data

        # When serializing, iterating world.rooms won't see room 200.
        # _pending_room_items is NOT consulted by _serialize_world.
        # This means a save at this point would lose beta's room items.
        visible_rooms = list(world.rooms)  # lai=False, no load triggered
        assert 200 not in visible_rooms, (
            "room 200 should NOT be visible in world.rooms iteration"
        )


# ===== Area age for unloaded areas ==========================================

class TestAreaAgeUnloaded:
    """area_update increments age for all areas but only resets loaded ones.
    Unloaded areas age up to the cap set by area_update."""

    def test_unloaded_area_ages_without_reset(self, fresh_world):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}})
        fw.setup()

        # Simulate area_update ticking age without loading
        area_state = world.areas[0]
        assert area_state["tag"] == "alpha"

        # Area not loaded -> no room_vnums key in state
        assert "room_vnums" not in area_state

        # Tick age past reset threshold
        for _ in range(20):
            area_state["age"] += 1

        assert area_state["age"] == 20
        # In area_update, age >= 15 triggers reset but only if room_vnums
        # present. Without it, reset is skipped but age keeps climbing.
        # 1stMud hard cap is 31 -> force reset. PrimeSUD doesn't enforce this.


# ===== reset_lazy / init_world ==============================================

class TestResetLazy:

    def test_reset_clears_all_state(self, fresh_world):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}},
                         mobiles={100: _mob_tpl()},
                         resets=(("M", 100, 1, 100, 1),))
        fw.setup()

        _load_area("alpha")
        assert len(world.chars) > 0
        assert len(world.rooms._data) > 0

        reset_lazy()
        assert len(world.chars) == 0
        assert len(world.rooms._data) == 0
        assert len(ROOM_DEFS._data) == 0
        assert len(MOB_DEFS._data) == 0
        assert len(ITEM_DEFS._data) == 0
        assert len(DOOR_DEFS) == 0
        assert not is_area_loaded("alpha")

    def test_reset_repopulates_area_defs(self, fresh_world):
        fw = fresh_world
        fw.register_area("alpha", 100, 199)
        fw.register_area("beta", 200, 299)
        fw.setup()

        reset_lazy()
        tags = [a["tag"] for a in AREA_DEFS]
        assert tags == ["alpha", "beta"]
        for a in AREA_DEFS:
            assert a["resets"] == []


# ===== _retry_pending_deltas ================================================

class TestRetryPendingDeltas:

    def test_retry_applies_deferred_moves(self, fresh_world):
        """After load cascade, _retry_pending_deltas should apply moves that
        were deferred because dest room state wasn't created yet."""
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}},
                                101: {"name": "R101", "exits": {}}},
                         mobiles={100: _mob_tpl()},
                         resets=(("M", 100, 1, 100, 1),))
        fw.setup()

        _load_area("alpha")
        mob_ids = [mid for mid, inst in world.chars.items()
                   if inst.get("is_npc") and inst["tpl"] == 100]
        assert len(mob_ids) == 1
        mid = mob_ids[0]

        # Simulate: pending delta that was deferred (dest room exists now)
        world._pending_mob_saves[100] = [101]

        _retry_pending_deltas()

        assert world.chars[mid]["room"] == 101
        assert mid in world.rooms._data[101]["mobs"]
        assert mid not in world.rooms._data[100]["mobs"]
        assert 100 not in world._pending_mob_saves


# ===== _load_all ============================================================

class TestLoadAll:

    def test_loads_all_registered_areas(self, fresh_world):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}})
        fw.register_area("beta", 200, 299,
                         rooms={200: {"name": "R200", "exits": {}}})
        fw.register_area("gamma", 300, 399,
                         rooms={300: {"name": "R300", "exits": {}}})
        fw.setup()

        _load_all()
        assert is_area_loaded("alpha")
        assert is_area_loaded("beta")
        assert is_area_loaded("gamma")

    def test_idempotent(self, fresh_world):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}})
        fw.setup()

        _load_all()
        _load_all()  # should not error
        assert is_area_loaded("alpha")


# ===== Integration: area_update on areas tick state =========================

class TestAreaTickState:

    def test_create_area_states_omits_room_vnums_before_load(self, fresh_world):
        """create_area_states should NOT include room_vnums for unloaded areas."""
        from mob import create_area_states

        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}})
        fw.setup()

        states = create_area_states()
        assert len(states) == 1
        assert "room_vnums" not in states[0]

    def test_load_area_updates_tick_state(self, fresh_world):
        """After _load_area, world.areas entry gains room_vnums."""
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}},
                                101: {"name": "R101", "exits": {}}})
        fw.setup()

        _load_area("alpha")
        area_state = next(s for s in world.areas if s["tag"] == "alpha")
        assert "room_vnums" in area_state
        assert set(area_state["room_vnums"]) == {100, 101}


# ===== BUG: unvisited area data lost on re-save ============================
#
# _serialize_world iterates world.rooms (lai=False) and world.chars for room
# items and mob positions. Unloaded areas have no entries in either. Pending
# deltas (_pending_room_items, _pending_mob_saves) are NOT re-serialized.
# Result: load -> play in area A only -> save -> load -> area B's room items
# and mob positions are gone.

class TestUnvisitedDataPreservedOnResave:
    """Pending deltas for unvisited areas must survive re-serialization."""

    def test_pending_room_items_in_serialized_output(self, fresh_world):
        """Room items for unvisited areas appear in save payload."""
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}})
        fw.register_area("beta", 200, 299,
                         rooms={200: {"name": "R200", "exits": {}}},
                         objects={250: _item_tpl()})
        world._pending_room_items[200] = "v:250;c:5"
        fw.setup()

        _load_area("alpha")

        # Simulate what _serialize_world now does: loaded rooms + pending
        serialized_lines = []
        for rvnum in sorted(world.rooms):
            rs = world.rooms[rvnum]
            if rs["items"]:
                from item import serialize_item_token
                parts = [serialize_item_token(o) for o in rs["items"]]
                serialized_lines.append("r." + str(rvnum) + ".items=" + "|".join(parts))
        for rvnum in sorted(world._pending_room_items):
            serialized_lines.append(
                "r." + str(rvnum) + ".items=" + str(world._pending_room_items[rvnum]))

        room_200_lines = [l for l in serialized_lines if l.startswith("r.200.")]
        assert len(room_200_lines) == 1
        assert "v:250" in room_200_lines[0]

    def test_pending_mob_saves_in_serialized_output(self, fresh_world):
        """Mob positions for unvisited areas appear in save payload."""
        import game_state
        from player import create_char

        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}},
                         mobiles={100: _mob_tpl()},
                         resets=(("M", 100, 1, 100, 1),))
        fw.register_area("beta", 200, 299,
                         rooms={200: {"name": "R200", "exits": {}}},
                         mobiles={200: _mob_tpl()})
        world._pending_mob_saves[200] = [200]
        fw.setup()

        player = create_char()
        player["name"] = "Tester"
        player["room"] = 100
        player["_macros"] = {}
        world.chars[1] = player
        game_state._serialize_world()

        with open(game_state.SAVE_FILE) as f:
            payload = f.read()
        assert "~m=200,200" in payload
        assert "~m.200=" not in payload

        world._pending_mob_saves.clear()
        assert game_state.load_world() == "file"
        assert world._pending_mob_saves[200] == [200]


# ===== BUG: area age unbounded for unloaded areas ==========================
#
# area_update increments age for ALL areas, but only resets loaded ones
# (skips when "room_vnums" not in area state). 1stMud has a hard cap at
# age >= 31 that forces reset regardless. PrimeSUD doesn't enforce this,
# so unloaded areas accumulate age without bound.

class TestAreaAgeCapped:

    def test_unloaded_area_age_capped_at_reset_threshold(self, fresh_world):
        """Unloaded area age clamped at _AREA_AGE_RESET, not unbounded."""
        from mob import area_update, _AREA_AGE_RESET

        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}})
        fw.setup()

        area_state = world.areas[0]

        from handler import _char_base
        player = _char_base()
        player["room"] = 100

        class FakeTr:
            def print(self, *a, **kw):
                pass

        for _ in range(35):
            area_update(FakeTr(), player)

        assert area_state["age"] == _AREA_AGE_RESET

