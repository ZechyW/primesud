"""Tests for world.py far-area eviction (_unload_area / maybe_evict).

Covers:
- Evict buffers mob positions and room items in save-delta format
- Evict + reload round-trip restores mob positions, room items, doors
- Foreign wanderers in evicted rooms deleted without recording
- Dangling fighting refs cleared on evict
- Cross-area resets survive target evict+reload without duplication
- Cross-area resets survive owner evict+reload without duplication
- maybe_evict: cap + LRU order, keep-set (followers, pinned), fast path
"""
import pytest

import world
from world import (
    ROOM_DEFS, MOB_DEFS, ITEM_DEFS, DOOR_DEFS,
    _load_area, _unload_area, maybe_evict, is_area_loaded,
)


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
        reason the snapshot exists (see world._snapshot_foreign_objs).
        """
        from item import create_object
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
            assert tpl.get("extra_flags", {}).get("glow")
            assert tpl.get("weight") == 1
        assert not is_area_loaded("alpha"), "reading gear reloaded the area"

        # Template dict is copied, not aliased: mutating the instance's flags
        # must not write through to anything shared.
        player["inv"][0]["extra_flags"]["glow"] = False
        assert dropped["extra_flags"].get("glow")

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
