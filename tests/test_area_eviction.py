"""Tests for world.py far-area eviction (_unload_area / maybe_evict).

Covers:
- Evict buffers mob positions and room items in save-delta format
- Evict + reload round-trip restores mob positions, room items, doors
- Foreign wanderers in evicted rooms deleted without recording
- Dangling fighting refs cleared on evict
- Cross-area resets survive target evict+reload without duplication
- Cross-area resets survive owner evict+reload without duplication
- maybe_evict: cap + LRU order, keep-set (followers, pinned), fast path
- item_tpl/item_tpl_get registry lookup order (resident/snapshot/lazy/orphan)
- Eviction-time ITEM_SNAPSHOTS registry materialization (SNAPSHOT_PLAN.md)
"""
import pytest

import world
from world import (
    ROOM_DEFS, MOB_DEFS, ITEM_DEFS, DOOR_DEFS,
    _load_area, _unload_area, maybe_evict, is_area_loaded,
)


@pytest.fixture(autouse=True)
def _clear_item_snapshots():
    """Keep ITEM_SNAPSHOTS from leaking between tests. [PRIMESUD]

    Unlike ROOM_DEFS/MOB_DEFS/ITEM_DEFS etc., the shared fresh_world fixture
    (tests/conftest.py) does not snapshot/restore world.ITEM_SNAPSHOTS --
    it is out of this task's owned-files scope to extend that fixture, so
    this module clears the registry itself around every test instead.
    """
    world.ITEM_SNAPSHOTS.clear()
    yield
    world.ITEM_SNAPSHOTS.clear()


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


def _live_mobs(tpl):
    return sorted(mid for mid, inst in world.chars.items()
                  if inst.get("is_npc") and inst["tpl"] == tpl)


def _add_player(room):
    world.chars[1] = {"is_npc": False, "room": room, "fighting": None}
    return world.chars[1]


# ===== _unload_area =========================================================

class TestUnloadArea:

    def test_program_tables_follow_area_lifetime(self, fresh_world):
        fw = fresh_world
        fw.register_area(
            "alpha", 100, 199,
            rooms={100: {"name": "R100", "exits": {}}},
            mobprogs={150: "mob echo test"},
            objprogs={151: "obj echo test"},
            roomprogs={152: "room echo test"},
        )
        fw.setup()

        _load_area("alpha")
        assert world.MOBPROGS[150] == "mob echo test"
        assert world.OBJPROGS[151] == "obj echo test"
        assert world.ROOMPROGS[152] == "room echo test"

        _unload_area("alpha")
        assert 150 not in world.MOBPROGS
        assert 151 not in world.OBJPROGS
        assert 152 not in world.ROOMPROGS

    def test_buffers_mob_positions_and_drops_defs(self, fresh_world):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}},
                                101: {"name": "R101", "exits": {}}},
                         mobiles={100: _mob_tpl()},
                         resets=(("M", 100, 1, 100, 1),))
        fw.setup()

        _load_area("alpha")
        mid = _live_mobs(100)[0]
        # Move the mob to 101 so the buffered position is non-default
        world.rooms._data[100]["mobs"].remove(mid)
        world.chars[mid]["room"] = 101
        world.rooms._data[101]["mobs"].append(mid)

        _unload_area("alpha")

        assert world._pending_mob_saves[100] == [101]
        assert _live_mobs(100) == []
        assert not is_area_loaded("alpha")
        assert 100 not in ROOM_DEFS._data
        assert 100 not in world.rooms._data
        assert 100 not in MOB_DEFS._data

    def test_snapshots_objects_held_outside_the_area(self, fresh_world):
        """Carried/dropped gear is decoupled before its template goes.

        Reading it back must not reload the area -- that reload is the whole
        reason the registry exists (see world._materialize_item_snapshots).
        """
        from item import create_object, item_extra_flags, set_item_extra_flag
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}},
                         objects={110: _item_tpl(
                             "alpha trinket", short_descr="an alpha trinket",
                             extra_flags={"glow": True})})
        fw.register_area("beta", 200, 299,
                         rooms={200: {"name": "R200", "exits": {}}})
        fw.setup()
        _load_area("alpha")
        _load_area("beta")

        player = _add_player(200)
        player["inv"] = [create_object(110)]
        # ...and one left on the floor of the OTHER area, the case a
        # player-scoped sweep would miss.
        dropped = create_object(110)
        world.rooms._data[200]["items"].append(dropped)

        _unload_area("alpha")
        assert not is_area_loaded("alpha")

        for obj in (player["inv"][0], dropped):
            tpl = world.item_tpl(obj)
            assert tpl["short_descr"] == "an alpha trinket"
            assert item_extra_flags(obj, tpl).get("glow")
            assert tpl.get("weight") == 1
        assert not is_area_loaded("alpha"), "reading gear reloaded the area"
        assert 110 in world.ITEM_SNAPSHOTS
        assert world.ITEM_SNAPSHOTS[110][0] == world.CONTENT_REVISION

        # Registry template is shared, not aliased onto either instance:
        # a copy-on-write instance override must not touch the other
        # instance or the registry's own template dict.
        tpl = world.item_tpl(player["inv"][0])
        set_item_extra_flag(player["inv"][0], tpl, "glow", False)
        assert not item_extra_flags(player["inv"][0], tpl).get("glow")
        dropped_tpl = world.item_tpl(dropped)
        assert item_extra_flags(dropped, dropped_tpl).get("glow")
        assert world.ITEM_SNAPSHOTS[110][1].get("extra_flags", {}).get("glow")

    def test_nested_container_contents_survive_eviction(self, fresh_world):
        """A dropped/carried container's nested contents get their own
        registry entries too -- not just the container's own vnum."""
        from item import create_object
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}},
                         objects={110: _item_tpl("gem", short_descr="a gem")})
        fw.register_area("beta", 200, 299,
                         rooms={200: {"name": "R200", "exits": {}},
                                201: {"name": "R201", "exits": {}}},
                         objects={210: _item_tpl(
                             "pouch", short_descr="a pouch", type="container")})
        fw.setup()
        _load_area("alpha")
        _load_area("beta")

        player = _add_player(200)
        pouch = create_object(210)
        pouch["contents"] = [create_object(110)]
        player["inv"] = [pouch]
        # ...and one nested inside a container sitting on a foreign floor.
        floor_pouch = create_object(210)
        floor_pouch["contents"] = [create_object(110)]
        world.rooms._data[201]["items"].append(floor_pouch)

        _unload_area("alpha")

        assert 110 in world.ITEM_SNAPSHOTS
        assert world.item_tpl(pouch["contents"][0])["short_descr"] == "a gem"
        assert world.item_tpl(floor_pouch["contents"][0])["short_descr"] == "a gem"
        assert not is_area_loaded("alpha")

    def test_equipped_item_survives_eviction(self, fresh_world):
        from item import create_object
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}},
                         objects={110: _item_tpl("ring", short_descr="a ring")})
        fw.register_area("beta", 200, 299,
                         rooms={200: {"name": "R200", "exits": {}}})
        fw.setup()
        _load_area("alpha")
        _load_area("beta")

        player = _add_player(200)
        player["inv"] = []
        player["equip"] = {"finger": create_object(110)}

        _unload_area("alpha")

        assert world.item_tpl(player["equip"]["finger"])["short_descr"] == "a ring"
        assert not is_area_loaded("alpha")

    def test_foreign_room_item_survives_own_room_item_gets_no_entry(self, fresh_world):
        from item import create_object
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}},
                         objects={110: _item_tpl("trinket", short_descr="foreign"),
                                   111: _item_tpl("rock", short_descr="local")})
        fw.register_area("beta", 200, 299,
                         rooms={200: {"name": "R200", "exits": {}}})
        fw.setup()
        _load_area("alpha")
        _load_area("beta")

        world.rooms._data[200]["items"].append(create_object(110))
        world.rooms._data[100]["items"].append(create_object(111))

        _unload_area("alpha")

        assert 110 in world.ITEM_SNAPSHOTS
        assert world.item_tpl(110)["short_descr"] == "foreign"
        assert 111 not in world.ITEM_SNAPSHOTS, (
            "own-area room items reload with their room, not the registry")
        assert not is_area_loaded("alpha")

    def test_deferred_pending_token_foreign_item_produces_entries(self, fresh_world):
        """_pending_room_items for a foreign (unloaded) room is scanned for
        vnums, including one nested inside a co: container field, without
        building item dicts (SNAPSHOT_PLAN.md sec. Deferred-token VNUM
        scan)."""
        from item import create_object, serialize_item_token
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}},
                         objects={110: _item_tpl("outer", short_descr="outer item"),
                                   111: _item_tpl("inner", short_descr="inner item")})
        fw.setup()
        _load_area("alpha")

        outer = create_object(110)
        outer["contents"] = [create_object(111)]
        # Room 9999 belongs to no registered area: any room outside alpha's
        # own rvnum_set exercises the "foreign deferred room" path.
        world._pending_room_items[9999] = serialize_item_token(outer)

        _unload_area("alpha")

        assert 110 in world.ITEM_SNAPSHOTS
        assert 111 in world.ITEM_SNAPSHOTS
        assert world.item_tpl(110)["short_descr"] == "outer item"
        assert world.item_tpl(111)["short_descr"] == "inner item"

    def test_repeated_vnum_creates_one_registry_entry(self, fresh_world):
        from item import create_object
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}},
                         objects={110: _item_tpl("coin", short_descr="a coin")})
        fw.register_area("beta", 200, 299,
                         rooms={200: {"name": "R200", "exits": {}}})
        fw.setup()
        _load_area("alpha")
        _load_area("beta")

        p1 = _add_player(200)
        p1["inv"] = [create_object(110)]
        world.chars[2] = {"is_npc": True, "tpl": 250, "room": 200,
                          "fighting": None, "inv": [create_object(110)],
                          "equip": {}}
        world.rooms._data[200]["mobs"] = [2]

        _unload_area("alpha")

        assert len(world.ITEM_SNAPSHOTS) == 1
        assert 110 in world.ITEM_SNAPSHOTS

    def test_deleted_npc_items_not_snapshotted(self, fresh_world):
        """Gear held only by an NPC that dies with its own area's eviction
        must not leave a registry entry (SNAPSHOT_PLAN.md sec. Decisions 3,
        "do not snapshot inventory of NPCs the same eviction deletes")."""
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}},
                         mobiles={100: _mob_tpl()},
                         objects={150: _item_tpl("dagger", short_descr="a dagger")},
                         resets=(("M", 100, 1, 100, 1), ("E", 150, "wield", 1)))
        fw.setup()

        _load_area("alpha")
        mid = _live_mobs(100)[0]
        granted = list(world.chars[mid]["inv"]) + [
            e for e in world.chars[mid]["equip"].values() if e is not None]
        assert granted, "reset should have granted the dagger"

        _unload_area("alpha")

        assert 150 not in world.ITEM_SNAPSHOTS

    def test_reload_restocks_shop_with_template_flags(self, fresh_world):
        """Delta-replay restock adds `inventory` copy-on-write: template
        extra_flags survive on the instance, template stays untouched."""
        fw = fresh_world
        shop = {"keeper": 100, "buy_types": [], "profit_buy": 100,
                "profit_sell": 100, "open_hour": 0, "close_hour": 23}
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}},
                         mobiles={100: _mob_tpl(shop=shop)},
                         objects={150: _item_tpl(extra_flags={"magic": True})},
                         resets=(("M", 100, 1, 100, 1), ("G", 150, 1)))
        fw.setup()

        _load_area("alpha")
        _unload_area("alpha")
        _load_area("alpha")

        mid = _live_mobs(100)[0]
        stock = [o for o in world.chars[mid]["inv"] if o["vnum"] == 150]
        assert stock, "reload replay must restock the shopkeeper"
        flags = stock[0]["extra_flags"]
        assert flags.get("inventory")
        assert flags.get("magic")
        assert ITEM_DEFS._data[150]["extra_flags"] == {"magic": True}

    def test_reload_roundtrip_restores_state(self, fresh_world):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {
                                    "n": {"to": 101, "isdoor": True,
                                          "closed": True, "locked": False}}},
                                101: {"name": "R101", "exits": {}}},
                         mobiles={100: _mob_tpl()},
                         objects={150: _item_tpl()},
                         resets=(("M", 100, 1, 100, 1),))
        fw.setup()

        _load_area("alpha")
        mid = _live_mobs(100)[0]
        world.rooms._data[100]["mobs"].remove(mid)
        world.chars[mid]["room"] = 101
        world.rooms._data[101]["mobs"].append(mid)
        from item import create_object
        world.rooms._data[100]["items"].append(create_object(150))
        # Player opens the door; live state should NOT survive eviction
        DOOR_DEFS[100]["n"]["closed"] = False

        _unload_area("alpha")
        _load_area("alpha")

        mids = _live_mobs(100)
        assert len(mids) == 1
        assert world.chars[mids[0]]["room"] == 101
        items = world.rooms._data[100]["items"]
        assert len(items) == 1 and items[0]["vnum"] == 150
        assert DOOR_DEFS[100]["n"]["closed"] is True  # baseline rebuilt
        assert 100 not in world._pending_mob_saves
        assert 100 not in world._pending_room_items

    def test_foreign_wanderer_deleted_without_recording(self, fresh_world):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}})
        fw.register_area("beta", 200, 299,
                         rooms={200: {"name": "R200", "exits": {}}},
                         mobiles={200: _mob_tpl()},
                         resets=(("M", 200, 1, 200, 1),))
        fw.setup()

        _load_area("alpha")
        _load_area("beta")
        mid = _live_mobs(200)[0]
        # beta's mob wanders into alpha's room
        world.rooms._data[200]["mobs"].remove(mid)
        world.chars[mid]["room"] = 100
        world.rooms._data[100]["mobs"].append(mid)

        _unload_area("alpha")

        assert _live_mobs(200) == []
        assert 200 not in world._pending_mob_saves

    def test_own_mob_in_foreign_room_buffered_and_removed(self, fresh_world):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}},
                         mobiles={100: _mob_tpl()},
                         resets=(("M", 100, 1, 100, 1),))
        fw.register_area("beta", 200, 299,
                         rooms={200: {"name": "R200", "exits": {}}})
        fw.setup()

        _load_area("alpha")
        _load_area("beta")
        mid = _live_mobs(100)[0]
        # alpha's mob wanders into beta's room
        world.rooms._data[100]["mobs"].remove(mid)
        world.chars[mid]["room"] = 200
        world.rooms._data[200]["mobs"].append(mid)

        _unload_area("alpha")

        assert world._pending_mob_saves[100] == [200]
        assert mid not in world.rooms._data[200]["mobs"]

    def test_fighting_refs_cleared(self, fresh_world):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}},
                         mobiles={100: _mob_tpl()},
                         resets=(("M", 100, 1, 100, 1),))
        fw.register_area("beta", 200, 299,
                         rooms={200: {"name": "R200", "exits": {}}},
                         mobiles={200: _mob_tpl()},
                         resets=(("M", 200, 1, 200, 1),))
        fw.setup()

        _load_area("alpha")
        _load_area("beta")
        amid = _live_mobs(100)[0]
        bmid = _live_mobs(200)[0]
        world.chars[bmid]["fighting"] = amid

        _unload_area("alpha")

        assert world.chars[bmid]["fighting"] is None

    def test_pet_excluded_from_buffer(self, fresh_world):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}},
                         mobiles={100: _mob_tpl()},
                         resets=(("M", 100, 1, 100, 1),))
        fw.setup()

        _load_area("alpha")
        mid = _live_mobs(100)[0]
        player = _add_player(100)
        player["pet"] = mid
        world.chars[mid]["master"] = 1

        _unload_area("alpha")

        # Pet is persisted via p.pet, never as a template position
        assert 100 not in world._pending_mob_saves
        assert mid in world.chars  # pet instance survives eviction


# ===== item_tpl / item_tpl_get registry lookup order ========================
# resident ITEM_DEFS._data -> current ITEM_SNAPSHOTS entry -> lazy
# ITEM_DEFS[vnum] load -> orphan snapshot fallback + restamp (SNAPSHOT_PLAN.md
# sec. Runtime lifecycle, Lookup).

class TestItemTplRegistry:

    def test_resident_template_wins_over_registry_entry(self, fresh_world):
        """A loaded area's current data always wins, even over a (contrived,
        deliberately different) current-revision registry entry for the
        same vnum."""
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}},
                         objects={110: _item_tpl("resident", weight=1)})
        fw.setup()
        _load_area("alpha")

        world.ITEM_SNAPSHOTS[110] = (
            world.CONTENT_REVISION, {"name": "stale", "weight": 999}, {})

        tpl = world.item_tpl(110)
        assert tpl is ITEM_DEFS._data[110]
        assert tpl["weight"] == 1

    def test_current_snapshot_answers_without_loading_owner_area(self, fresh_world):
        """A snapshot created by a real eviction (not hand-injected) answers
        item_tpl without reloading its owner -- the entry must actually be
        held live by a survivor, or eviction's own prune step would drop
        it again (see TestUnloadArea eviction-collector tests)."""
        from item import create_object
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}},
                         objects={110: _item_tpl("gear", weight=7)})
        fw.register_area("beta", 200, 299,
                         rooms={200: {"name": "R200", "exits": {}}})
        fw.setup()
        _load_area("alpha")
        _load_area("beta")
        player = _add_player(200)
        player["inv"] = [create_object(110)]

        _unload_area("alpha")
        assert not is_area_loaded("alpha")
        assert 110 in world.ITEM_SNAPSHOTS

        tpl = world.item_tpl(player["inv"][0])

        assert tpl["weight"] == 7
        assert not is_area_loaded("alpha"), "current snapshot must not trigger a reload"

    def test_missing_snapshot_loads_exactly_one_owning_area(self, fresh_world):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}},
                         objects={110: _item_tpl("gear", weight=7)})
        fw.setup()

        assert not is_area_loaded("alpha")
        tpl = world.item_tpl(110)

        assert tpl["weight"] == 7
        assert is_area_loaded("alpha")

    def test_stale_revision_loads_current_area_and_uses_updated_stats(self, fresh_world):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}},
                         objects={110: _item_tpl("gear", weight=7)})
        fw.setup()
        world.ITEM_SNAPSHOTS[110] = ("stale-rev", {"weight": 999}, {})

        tpl = world.item_tpl(110)

        assert tpl["weight"] == 7, "stale snapshot must not win over current data"
        assert is_area_loaded("alpha")

    def test_removed_vnum_uses_orphan_snapshot_and_restamps(self, fresh_world):
        """Revision mismatch, corrective load confirms the owning area no
        longer defines the vnum: fall back to the stale snapshot and
        restamp its revision so the next lookup skips the reload."""
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}},
                         objects={})  # 110 no longer defined by the area
        fw.setup()
        world.ITEM_SNAPSHOTS[110] = (
            "stale-rev", {"weight": 5, "short_descr": "orphan gear"}, {})

        tpl = world.item_tpl(110)

        assert tpl == {"weight": 5, "short_descr": "orphan gear"}
        assert is_area_loaded("alpha"), "one corrective load must have run"
        assert world.ITEM_SNAPSHOTS[110][0] == world.CONTENT_REVISION, (
            "orphan entry must be restamped so a later lookup skips the reload")

        # Restamped entry now answers directly, no second corrective load:
        # re-clear _LOADED_AREAS membership is not possible without another
        # real eviction, so assert via the cheaper resident-miss branch
        # instead -- a second item_tpl call must return the same object
        # without item_tpl ever touching ITEM_DEFS again (still resident,
        # still lacking 110).
        assert 110 not in ITEM_DEFS._data
        tpl2 = world.item_tpl(110)
        assert tpl2 is tpl, "second lookup should hit the now-current entry directly"

    def test_item_tpl_get_returns_none_for_unknown_vnum(self, fresh_world):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}})
        fw.setup()
        assert world.item_tpl_get(999999) is None

    def test_instance_override_wins_through_accessors_after_drift(self, fresh_world):
        """A genuine per-instance override still wins through the item_*
        accessors regardless of which lookup rung answered item_tpl."""
        from item import item_extra_flags
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}},
                         objects={})  # orphaned vnum, forces the fallback rung
        fw.setup()
        world.ITEM_SNAPSHOTS[110] = (
            "stale-rev", {"weight": 5, "extra_flags": {"glow": True}}, {})

        obj = {"vnum": 110, "extra_flags": {"glow": False}}
        tpl = world.item_tpl(obj)

        assert item_extra_flags(obj, tpl) == {"glow": False}, (
            "instance override must win even over an orphaned snapshot")

    def test_area_load_prunes_now_resident_entries_keeps_orphans(self, fresh_world):
        """Loading an area drops registry entries it just made resident
        (fresh data supersedes the cache) but retains orphan entries for
        vnums the area no longer defines (SNAPSHOT_PLAN.md sec. Area
        load)."""
        from item import create_object
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}},
                         objects={110: _item_tpl("gear", weight=7)})
        fw.register_area("beta", 200, 299,
                         rooms={200: {"name": "R200", "exits": {}}})
        fw.setup()
        _load_area("alpha")
        _load_area("beta")
        player = _add_player(200)
        player["inv"] = [create_object(110)]

        _unload_area("alpha")
        assert 110 in world.ITEM_SNAPSHOTS
        # Orphan for a vnum alpha never defines must survive the reload.
        world.ITEM_SNAPSHOTS[199] = ("stale-rev", {"weight": 1}, {})

        _load_area("alpha")

        assert 110 not in world.ITEM_SNAPSHOTS, (
            "resident again -- registry copy must be dropped")
        assert 199 in world.ITEM_SNAPSHOTS, "orphan entry must be retained"


# ===== Cross-area resets across evictions ===================================

class TestCrossAreaEviction:

    def _register_pair(self, fw):
        """alpha owns an M-reset targeting beta's room 200."""
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "A-R100", "exits": {}}},
                         mobiles={100: _mob_tpl()},
                         resets=(("M", 100, 1, 200, 1),))
        fw.register_area("beta", 200, 299,
                         rooms={200: {"name": "B-R200", "exits": {}}})
        fw.setup()

    def test_no_duplicate_on_cascade_load(self, fresh_world):
        self._register_pair(fresh_world)

        _load_area("alpha")  # cascades into beta

        entries = [e for e in ROOM_DEFS._data[200].get("resets", [])
                   if e[0] == "M" and e[1] == 100]
        assert len(entries) == 1, "cross reset partitioned exactly once"
        assert len(_live_mobs(100)) == 1

    def test_survives_target_evict_reload(self, fresh_world):
        self._register_pair(fresh_world)

        _load_area("alpha")
        _unload_area("beta")
        _load_area("beta")

        entries = [e for e in ROOM_DEFS._data[200].get("resets", [])
                   if e[0] == "M" and e[1] == 100]
        assert len(entries) == 1
        mids = _live_mobs(100)
        assert len(mids) == 1
        assert world.chars[mids[0]]["room"] == 200

    def test_survives_owner_evict_reload(self, fresh_world):
        self._register_pair(fresh_world)

        _load_area("alpha")
        _unload_area("alpha")

        # Owner's entry must be pulled out of beta's resident room def
        entries = [e for e in ROOM_DEFS._data[200].get("resets", [])
                   if e[0] == "M" and e[1] == 100]
        assert entries == [], "evicted owner's cross entries removed"

        _load_area("alpha")

        entries = [e for e in ROOM_DEFS._data[200].get("resets", [])
                   if e[0] == "M" and e[1] == 100]
        assert len(entries) == 1
        assert len(_live_mobs(100)) == 1

    def test_target_loads_first_then_owner(self, fresh_world):
        self._register_pair(fresh_world)

        _load_area("beta")
        _load_area("alpha")

        entries = [e for e in ROOM_DEFS._data[200].get("resets", [])
                   if e[0] == "M" and e[1] == 100]
        assert len(entries) == 1
        assert len(_live_mobs(100)) == 1


# ===== maybe_evict ==========================================================

class TestMaybeEvict:

    def _register_chain(self, fw, n=4):
        """Areas a0..a(n-1), rooms 100*(i+1)."""
        for i in range(n):
            lo = 100 * (i + 1)
            fw.register_area("a%d" % i, lo, lo + 99,
                             rooms={lo: {"name": "R%d" % lo, "exits": {}}})
        fw.setup()

    def test_evicts_lru_over_cap(self, fresh_world, monkeypatch):
        import config
        monkeypatch.setattr(config, "AREA_CACHE_MAX", 2)
        self._register_chain(fresh_world, 3)
        player = _add_player(100)

        for room in (100, 200, 300):
            player["room"] = room
            tag = world._vnum_to_tag(room)
            if not is_area_loaded(tag):
                _load_area(tag)
            maybe_evict(player)

        assert not is_area_loaded("a0"), "oldest visit evicted"
        assert is_area_loaded("a1")
        assert is_area_loaded("a2")

    def test_fast_path_same_room_no_bump(self, fresh_world, monkeypatch):
        import config
        monkeypatch.setattr(config, "AREA_CACHE_MAX", 2)
        self._register_chain(fresh_world, 2)
        player = _add_player(100)
        _load_area("a0")

        maybe_evict(player)
        seq = dict(world._area_seq)
        maybe_evict(player)  # same room: no work
        assert world._area_seq == seq

    def test_keeps_follower_areas(self, fresh_world, monkeypatch):
        import config
        monkeypatch.setattr(config, "AREA_CACHE_MAX", 1)
        self._register_chain(fresh_world, 3)
        player = _add_player(100)
        _load_area("a0")
        # Charmed follower: template owned by a0, standing in a0
        world.chars[50] = {"is_npc": True, "tpl": 100, "room": 100,
                           "master": 1, "fighting": None}
        world.rooms._data[100]["mobs"].append(50)

        for room in (200, 300):
            player["room"] = room
            _load_area(world._vnum_to_tag(room))
            maybe_evict(player)

        assert is_area_loaded("a0"), "follower's area never evicted"

    def test_keeps_combatant_area(self, fresh_world, monkeypatch):
        import config
        monkeypatch.setattr(config, "AREA_CACHE_MAX", 1)
        self._register_chain(fresh_world, 3)
        player = _add_player(100)
        _load_area("a0")
        world.chars[50] = {"is_npc": True, "tpl": 100, "room": 100,
                           "fighting": 1}
        world.rooms._data[100]["mobs"].append(50)
        player["fighting"] = 50

        for room in (200, 300):
            player["room"] = room
            _load_area(world._vnum_to_tag(room))
            maybe_evict(player)

        assert is_area_loaded("a0"), "combatant's area never evicted"

    def test_pinned_area_never_evicted(self, fresh_world, monkeypatch):
        import config
        monkeypatch.setattr(config, "AREA_CACHE_MAX", 1)
        fw = fresh_world
        fw.register_area("limbo", 1, 99,
                         rooms={2: {"name": "Limbo", "exits": {}}})
        fw.register_area("a1", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}})
        fw.register_area("a2", 200, 299,
                         rooms={200: {"name": "R200", "exits": {}}})
        fw.setup()
        player = _add_player(100)
        _load_area("limbo")
        _load_area("a1")

        player["room"] = 200
        _load_area("a2")
        maybe_evict(player)

        assert is_area_loaded("limbo"), "pinned limbo never evicted"
        assert not is_area_loaded("a1")

    def test_force_enforces_cap_after_same_area_move(self, fresh_world,
                                                     monkeypatch):
        """force=True must reach the cap check even when the player moved
        within the area maybe_evict last ran a pass for."""
        import config
        monkeypatch.setattr(config, "AREA_CACHE_MAX", 1)
        fw = fresh_world
        fw.register_area("a0", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}},
                                101: {"name": "R101", "exits": {}}})
        fw.register_area("a1", 200, 299,
                         rooms={200: {"name": "R200", "exits": {}}})
        fw.setup()
        player = _add_player(100)
        _load_area("a0")
        maybe_evict(player)          # pass for a0: _last_evict_area = "a0"

        _load_area("a1")             # remote load pushes over the cap
        player["room"] = 101         # moved, still inside a0
        maybe_evict(player, True)

        assert not is_area_loaded("a1"), "forced pass must enforce the cap"
        assert is_area_loaded("a0")

    def test_under_cap_no_eviction(self, fresh_world, monkeypatch):
        import config
        monkeypatch.setattr(config, "AREA_CACHE_MAX", 12)
        self._register_chain(fresh_world, 3)
        player = _add_player(100)
        for room in (100, 200, 300):
            player["room"] = room
            _load_area(world._vnum_to_tag(room))
            maybe_evict(player)

        assert is_area_loaded("a0")
        assert is_area_loaded("a1")
        assert is_area_loaded("a2")
