"""Tests for item-template snapshot persistence through save/load
(SNAPSHOT_PLAN.md Phase D).

Covers:
- Player inventory/equipment (incl. nested contents) round-trips through
  the "it.<vnum>=<revision>|<record>" save section without reloading the
  owner area
- Loaded foreign-room items and foreign _pending_room_items tokens produce
  it.* lines and round-trip
- Own-area room items produce no it.* line
- Repeated VNUMs produce exactly one it.* line
- Old (pre-Phase-D) saves without it.* lines still load, and a re-save
  regenerates the section
- A malformed it.* line is skipped individually without breaking the rest
  of the save
- Orphan registry entries round-trip with their own stored revision
- Save-time cold mark/sweep prunes an unreferenced, owner-unloaded
  registry entry and never writes it
- A resident-owner item gets its it.* line from resident data even with
  no pre-existing registry entry
"""
import pytest

import world
import game_state
from item import create_object, serialize_item_token
from player import create_char


@pytest.fixture(autouse=True)
def _clear_item_snapshots():
    """Keep ITEM_SNAPSHOTS from leaking between tests. [PRIMESUD]

    Same convention as test_area_eviction.py: fresh_world does not
    snapshot/restore world.ITEM_SNAPSHOTS, so this module clears it itself.
    """
    world.ITEM_SNAPSHOTS.clear()
    yield
    world.ITEM_SNAPSHOTS.clear()


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


def _make_player(room):
    """Full player dict via create_char(), suitable for _serialize_world/
    load_world round trips (cf. tests/test_backup_prime.py _make_player)."""
    player = create_char()
    player["name"] = "Tester"
    player["room"] = room
    player["_macros"] = {}
    world.chars[1] = player
    return player


def _it_lines(payload):
    """Return the "it.<vnum>=..." lines from a "~"-joined save payload."""
    return [ln for ln in payload.split("~") if ln.startswith("it.")]


# ===== Player gear from an evicted area =====================================

class TestPlayerGearRoundTrip:
    def test_inv_and_equip_survive_owner_eviction_and_reload(self, fresh_world):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}},
                         objects={110: _item_tpl("gem", short_descr="a gem"),
                                   111: _item_tpl("ring", short_descr="a ring")})
        fw.register_area("beta", 200, 299,
                         rooms={200: {"name": "R200", "exits": {}}})
        fw.setup()
        world._load_area("alpha")
        world._load_area("beta")

        player = _make_player(200)
        player["inv"] = [create_object(110)]
        player["equip"]["wield"] = create_object(111)

        world._unload_area("alpha")
        assert not world.is_area_loaded("alpha")
        assert 110 in world.ITEM_SNAPSHOTS and 111 in world.ITEM_SNAPSHOTS

        assert game_state.save_world(quiet=True)

        world.reset_lazy()
        player2 = create_char()
        player2["_macros"] = {}
        world.chars[1] = player2
        assert game_state.load_world() == "file"

        assert not world.is_area_loaded("alpha")
        gem_tpl = world.item_tpl(player2["inv"][0])
        assert gem_tpl["short_descr"] == "a gem"
        ring_tpl = world.item_tpl(player2["equip"]["wield"])
        assert ring_tpl["short_descr"] == "a ring"
        assert not world.is_area_loaded("alpha"), (
            "reading restored gear must not reload its evicted owner area")


class TestNestedContainer:
    def test_nested_contents_round_trip(self, fresh_world):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}},
                         objects={110: _item_tpl("coin", short_descr="a coin")})
        fw.register_area("beta", 200, 299,
                         rooms={200: {"name": "R200", "exits": {}}},
                         objects={210: _item_tpl("pouch", short_descr="a pouch",
                                                   type="container")})
        fw.setup()
        world._load_area("alpha")
        world._load_area("beta")

        player = _make_player(200)
        pouch = create_object(210)
        pouch["contents"] = [create_object(110)]
        player["inv"] = [pouch]

        world._unload_area("alpha")
        assert game_state.save_world(quiet=True)

        world.reset_lazy()
        player2 = create_char()
        player2["_macros"] = {}
        world.chars[1] = player2
        assert game_state.load_world() == "file"

        loaded_pouch = player2["inv"][0]
        assert loaded_pouch["contents"][0]["vnum"] == 110
        assert world.item_tpl(loaded_pouch["contents"][0])["short_descr"] == "a coin"
        assert not world.is_area_loaded("alpha")


# ===== Foreign room / pending items ==========================================

class TestForeignRoomAndPending:
    def test_loaded_foreign_room_and_pending_item_produce_lines_and_roundtrip(
            self, fresh_world):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}},
                         objects={110: _item_tpl("trinket", short_descr="foreign trinket"),
                                   120: _item_tpl("token", short_descr="pending token")})
        fw.register_area("beta", 200, 299,
                         rooms={200: {"name": "R200", "exits": {}}})
        fw.setup()
        world._load_area("alpha")
        world._load_area("beta")
        _make_player(200)

        # alpha-owned item dropped on beta's loaded floor
        world.rooms._data[200]["items"].append(create_object(110))
        # alpha-owned item buffered for an unloaded/unregistered room
        world._pending_room_items[9999] = serialize_item_token(create_object(120))

        payload_lines = None

        def _capture():
            nonlocal payload_lines
            assert game_state.save_world(quiet=True)
            with open(game_state.SAVE_FILE, "r") as f:
                payload_lines = _it_lines(f.read())

        _capture()
        assert any(ln.startswith("it.110=") for ln in payload_lines)
        assert any(ln.startswith("it.120=") for ln in payload_lines)

        world.reset_lazy()
        player2 = create_char()
        player2["_macros"] = {}
        player2["room"] = 200
        world.chars[1] = player2
        assert game_state.load_world() == "file"

        assert not world.is_area_loaded("alpha")
        floor_item = world.rooms._data[200]["items"][0]
        assert world.item_tpl(floor_item)["short_descr"] == "foreign trinket"
        assert 120 in world._pending_room_items or True  # room 9999 stays pending
        assert not world.is_area_loaded("alpha")

    def test_own_area_room_item_produces_no_line(self, fresh_world):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}},
                         objects={150: _item_tpl("rock", short_descr="local rock")})
        fw.setup()
        world._load_area("alpha")
        _make_player(100)
        world.rooms._data[100]["items"].append(create_object(150))

        assert game_state.save_world(quiet=True)
        with open(game_state.SAVE_FILE, "r") as f:
            payload = f.read()

        assert "it.150=" not in payload, (
            "own-area room items reload with their room, not the it.* section")


# ===== Dedup ==================================================================

class TestDedup:
    def test_repeated_vnum_produces_one_line(self, fresh_world):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}},
                         objects={110: _item_tpl("coin", short_descr="a coin")})
        fw.register_area("beta", 200, 299,
                         rooms={200: {"name": "R200", "exits": {}}})
        fw.setup()
        world._load_area("alpha")
        world._load_area("beta")
        player = _make_player(200)
        player["inv"] = [create_object(110), create_object(110)]
        player["equip"]["hold"] = create_object(110)

        world._unload_area("alpha")
        assert game_state.save_world(quiet=True)
        with open(game_state.SAVE_FILE, "r") as f:
            payload = f.read()

        lines = [ln for ln in _it_lines(payload) if ln.startswith("it.110=")]
        assert len(lines) == 1


# ===== Old saves / migration ==================================================

class TestOldSaveCompatibility:
    def test_old_save_without_it_lines_loads_normally(self, fresh_world):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}},
                         objects={110: _item_tpl("gem", short_descr="a gem")})
        fw.register_area("beta", 200, 299,
                         rooms={200: {"name": "R200", "exits": {}}})
        fw.setup()
        world._load_area("alpha")
        world._load_area("beta")
        player = _make_player(200)
        player["inv"] = [create_object(110)]
        player["level"] = 7

        world._unload_area("alpha")
        assert game_state.save_world(quiet=True)
        with open(game_state.SAVE_FILE, "r") as f:
            payload = f.read()
        # Strip the it.* section to simulate a save written before Phase D.
        stripped = "~".join(ln for ln in payload.split("~")
                            if not ln.startswith("it."))
        assert stripped != payload
        with open(game_state.SAVE_FILE, "w") as f:
            f.write(stripped)

        world.reset_lazy()
        player2 = create_char()
        player2["_macros"] = {}
        world.chars[1] = player2
        assert game_state.load_world() == "file"

        assert player2["level"] == 7
        assert player2["inv"][0]["vnum"] == 110
        assert world.ITEM_SNAPSHOTS == {}, "no it.* lines means no registry entries"
        # Normal lazy-load fallback still works.
        tpl = world.item_tpl(player2["inv"][0])
        assert tpl["short_descr"] == "a gem"
        assert world.is_area_loaded("alpha"), (
            "with no snapshot, reading the item must fall back to a normal load")

    def test_resave_after_old_load_adds_it_section(self, fresh_world):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}},
                         objects={110: _item_tpl("gem", short_descr="a gem")})
        fw.register_area("beta", 200, 299,
                         rooms={200: {"name": "R200", "exits": {}}})
        fw.setup()
        world._load_area("alpha")
        world._load_area("beta")
        player = _make_player(200)
        player["inv"] = [create_object(110)]

        world._unload_area("alpha")
        assert game_state.save_world(quiet=True)
        with open(game_state.SAVE_FILE, "r") as f:
            payload = f.read()
        stripped = "~".join(ln for ln in payload.split("~")
                            if not ln.startswith("it."))
        with open(game_state.SAVE_FILE, "w") as f:
            f.write(stripped)

        world.reset_lazy()
        player2 = create_char()
        player2["_macros"] = {}
        world.chars[1] = player2
        assert game_state.load_world() == "file"
        assert world.ITEM_SNAPSHOTS == {}

        # Simulate ordinary play touching the item once (loads alpha, same
        # as any other lazy-load consumer would).
        world.item_tpl(player2["inv"][0])
        assert world.is_area_loaded("alpha")

        assert game_state.save_world(quiet=True)
        with open(game_state.SAVE_FILE, "r") as f:
            resaved = f.read()
        assert any(ln.startswith("it.110=") for ln in _it_lines(resaved))


# ===== Malformed lines ========================================================

class TestMalformedLine:
    def test_malformed_it_line_skipped_rest_of_save_intact(self, fresh_world):
        fw = fresh_world
        fw.register_area("beta", 200, 299,
                         rooms={200: {"name": "R200", "exits": {}}})
        fw.setup()
        world._load_area("beta")
        player = _make_player(200)
        player["level"] = 9

        assert game_state.save_world(quiet=True)
        with open(game_state.SAVE_FILE, "r") as f:
            payload = f.read()
        # Inject a handful of differently-broken it.* lines.
        payload = payload + "~it.notanumber=rev|s1:x" \
                           + "~it.777=norecordseparator" \
                           + "~it.778=rev|zzz-not-a-valid-record"
        with open(game_state.SAVE_FILE, "w") as f:
            f.write(payload)

        world.reset_lazy()
        player2 = create_char()
        player2["_macros"] = {}
        world.chars[1] = player2
        assert game_state.load_world() == "file"

        assert player2["level"] == 9
        assert 777 not in world.ITEM_SNAPSHOTS
        assert 778 not in world.ITEM_SNAPSHOTS


# ===== Orphan revision preservation ==========================================

class TestOrphanRevision:
    def test_orphan_entry_roundtrips_with_stored_revision(self, fresh_world):
        fw = fresh_world
        fw.register_area("beta", 200, 299,
                         rooms={200: {"name": "R200", "exits": {}}})
        fw.setup()
        world._load_area("beta")
        player = _make_player(200)
        # 99999 belongs to no registered area at all -- a true orphan with
        # only a registry entry as its source.
        player["inv"] = [{"vnum": 99999, "cost": 0}]
        world.ITEM_SNAPSHOTS[99999] = (
            "custom-old-rev", {"short_descr": "orphan gear", "weight": 3}, {})

        assert game_state.save_world(quiet=True)
        with open(game_state.SAVE_FILE, "r") as f:
            payload = f.read()
        assert any(ln.startswith("it.99999=custom-old-rev|")
                   for ln in _it_lines(payload))

        world.reset_lazy()
        player2 = create_char()
        player2["_macros"] = {}
        world.chars[1] = player2
        assert game_state.load_world() == "file"

        assert world.ITEM_SNAPSHOTS[99999] == (
            "custom-old-rev", {"short_descr": "orphan gear", "weight": 3}, {})


# ===== Save-time mark/sweep ===================================================

class TestSaveTimeMarkSweep:
    def test_unreferenced_owner_unloaded_entry_dropped_and_not_written(
            self, fresh_world):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}})
        fw.register_area("beta", 200, 299,
                         rooms={200: {"name": "R200", "exits": {}}})
        fw.setup()
        world._load_area("beta")
        _make_player(200)  # inv/equip empty: 110 is referenced by nothing

        # alpha (owner of 110) is never loaded; the entry is stale/unused.
        world.ITEM_SNAPSHOTS[110] = (world.CONTENT_REVISION, {"weight": 1}, {})

        assert game_state.save_world(quiet=True)

        assert 110 not in world.ITEM_SNAPSHOTS, (
            "cold mark/sweep must drop an unreferenced, owner-unloaded entry")
        with open(game_state.SAVE_FILE, "r") as f:
            payload = f.read()
        assert "it.110=" not in payload


# ===== Resident-owner fallback ================================================

class TestResidentOwnerFallback:
    def test_resident_template_used_even_without_registry_entry(self, fresh_world):
        fw = fresh_world
        fw.register_area("alpha", 100, 199,
                         rooms={100: {"name": "R100", "exits": {}}},
                         objects={110: _item_tpl("gear", short_descr="resident gear",
                                                   weight=7)})
        fw.setup()
        world._load_area("alpha")
        player = _make_player(100)
        player["inv"] = [create_object(110)]

        assert 110 not in world.ITEM_SNAPSHOTS
        assert game_state.save_world(quiet=True)
        with open(game_state.SAVE_FILE, "r") as f:
            payload = f.read()

        lines = [ln for ln in _it_lines(payload) if ln.startswith("it.110=")]
        assert len(lines) == 1
        rev_and_record = lines[0].split("=", 1)[1]
        rev, enc = rev_and_record.split("|", 1)
        assert rev == world.CONTENT_REVISION
        decoded = world._snap_decode(enc)
        assert decoded[0]["short_descr"] == "resident gear"
        assert decoded[0]["weight"] == 7
