"""Tests for world-reset fidelity (RESETS_PLAN): E/G/P/R semantics, spawn extras.

Covers the limit-decode helper, the computed per-template object count map,
E/G template-count limit + 1-in-5 trickle, P container refill, R exit
shuffle, the M dark-room infrared / pet-shop-adjacent pet grants, and the
room_is_dark / room_light predicates that back the infrared grant.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import world
from world import ROOM_DEFS, MOB_DEFS, ITEM_DEFS
import mob
from mob import _decode_limit, _object_count_map, _reset_randomize_exits


# ---------------------------------------------------------------------------
# Synthetic template helpers
# ---------------------------------------------------------------------------

def _mob_tpl(**extra):
    tpl = {"short_descr": "a critter", "keywords": "critter", "level": 1,
           "race": "Human", "hp_dice": (1, 1, 10), "hitroll": 0,
           "armor": (0, 0, 0, 0), "damage": (1, 2, 0), "dam_type": "punch"}
    tpl.update(extra)
    return tpl


def _obj_tpl(**extra):
    tpl = {"short_descr": "a widget", "description": "A widget is here.",
           "keywords": "widget", "type": "treasure", "material": "steel",
           "wear_flags": {"take": True}, "weight": 1, "value": 1, "level": 1}
    tpl.update(extra)
    return tpl


def _room(name="R"):
    return {"name": name, "desc": ".", "exits": {}, "sector": "inside",
            "flags": {}}


# ---------------------------------------------------------------------------
# Limit decode (decision 2)
# ---------------------------------------------------------------------------

class TestDecodeLimit:
    def test_legacy_over_50_is_six(self):
        assert _decode_limit(51, True) == 6
        assert _decode_limit(100, False) == 6

    def test_minus_one_unlimited_both(self):
        assert _decode_limit(-1, True) == 999
        assert _decode_limit(-1, False) == 999

    def test_zero_unlimited_only_for_eg(self):
        assert _decode_limit(0, True) == 999   # E/G: 0 == unlimited
        assert _decode_limit(0, False) == 0    # P: 0 is literal

    def test_plain_value_passthrough(self):
        assert _decode_limit(3, True) == 3
        assert _decode_limit(50, False) == 50


# ---------------------------------------------------------------------------
# Object count map (decision 1)
# ---------------------------------------------------------------------------

class TestObjectCountMap:
    def test_counts_rooms_chars_and_container_nesting(self, fresh_world):
        world.rooms._data[1] = {"items": [
            100, {"vnum": 100},
            {"vnum": 200, "contents": [{"vnum": 300}, 300]},
        ], "mobs": []}
        world.chars[1] = {"is_npc": False, "inv": [{"vnum": 100}],
                          "equip": {"body": {"vnum": 400}, "head": None}}
        counts = _object_count_map()
        assert counts[100] == 3   # two on floor + one in inventory
        assert counts[200] == 1
        assert counts[300] == 2   # both nested in the container
        assert counts[400] == 1   # equipped


# ---------------------------------------------------------------------------
# E/G limit + trickle (decision 3)
# ---------------------------------------------------------------------------

def _run_eg_area(fw, monkeypatch, trickle_on, passes):
    """Register a one-mob/one-item G-reset area, load it, run extra passes.

    Returns the total count of item 7002 across all mob inventories.
    """
    fw.register_area("egt", 7000, 7099,
                     rooms={7000: _room()},
                     mobiles={7001: _mob_tpl()},
                     objects={7002: _obj_tpl()},
                     resets=(("M", 7001, 99, 7000, 99), ("G", 7002, 2)))
    fw.setup()
    # Force the number_range(0,4) trickle either always-on (0) or always-off.
    monkeypatch.setattr(mob, "randint", (lambda a, b: 0) if trickle_on
                        else (lambda a, b: b))
    world._load_area("egt")
    adef = next(a for a in world.AREA_DEFS if a.get("tag") == "egt")
    for _ in range(passes):
        mob.reset_area(adef)
    total = 0
    for ch in world.chars.values():
        if not ch.get("is_npc"):
            continue
        for o in ch.get("inv", []):
            if (o["vnum"] if isinstance(o, dict) else o) == 7002:
                total += 1
    return total


class TestEGLimit:
    def test_over_limit_blocks_without_trickle(self, fresh_world, monkeypatch):
        # 5 mobs spawn (load + 4 passes); limit 2, trickle off -> caps at 2.
        total = _run_eg_area(fresh_world, monkeypatch, False, 4)
        assert total == 2

    def test_trickle_spawns_over_limit(self, fresh_world, monkeypatch):
        # Same setup, trickle always on -> every mob gets one, exceeds 2.
        total = _run_eg_area(fresh_world, monkeypatch, True, 4)
        assert total > 2

    def test_shopkeeper_always_spawns_with_inventory_flag(self, fresh_world,
                                                          monkeypatch):
        fresh_world.register_area(
            "shopt", 7200, 7299,
            rooms={7200: _room()},
            mobiles={7201: _mob_tpl(shop={"keeper": 7201, "buy_types": [],
                                          "profit_buy": 100, "profit_sell": 100,
                                          "open_hour": 0, "close_hour": 23})},
            objects={7202: _obj_tpl()},
            resets=(("M", 7201, 99, 7200, 99), ("G", 7202, 1)))
        fresh_world.setup()
        # trickle off: a non-shop mob at limit 1 would stop, a shopkeeper won't
        monkeypatch.setattr(mob, "randint", lambda a, b: b)
        world._load_area("shopt")
        adef = next(a for a in world.AREA_DEFS if a.get("tag") == "shopt")
        for _ in range(3):
            mob.reset_area(adef)
        stock = 0
        for ch in world.chars.values():
            if not ch.get("is_npc"):
                continue
            for o in ch.get("inv", []):
                if (o["vnum"] if isinstance(o, dict) else o) == 7202:
                    stock += 1
                    assert o.get("extra_flags", {}).get("inventory")
        assert stock >= 4   # one per keeper spawn, never blocked by limit 1


# ---------------------------------------------------------------------------
# P container refill (decision 4)
# ---------------------------------------------------------------------------

class TestPReset:
    def _setup(self, fw, plimit, maxcount, cflags=None):
        fw.register_area(
            "pt", 8000, 8099,
            rooms={8000: _room()},
            mobiles={},
            objects={
                8001: _obj_tpl(type="container", keywords="chest",
                               container_flags=cflags or {"closeable": True,
                                                          "closed": True}),
                8002: _obj_tpl(keywords="gem"),
            },
            resets=(("O", 8001, 8000), ("P", 8002, plimit, 8001, maxcount)))
        fw.setup()
        world._load_area("pt")

    def _container(self):
        for o in world.rooms._data[8000]["items"]:
            if isinstance(o, dict) and o["vnum"] == 8001:
                return o
        return None

    def test_fills_to_max_and_restores_flags(self, fresh_world):
        self._setup(fresh_world, 5, 3)
        cont = self._container()
        assert cont is not None
        contents = cont.get("contents", [])
        assert sum(1 for c in contents if c["vnum"] == 8002) == 3
        # closed/locked state restored from template (db.c:1576)
        assert cont["container_flags"] == {"closeable": True, "closed": True}

    def test_refill_does_not_exceed_max_on_re_reset(self, fresh_world):
        self._setup(fresh_world, 5, 3)
        adef = next(a for a in world.AREA_DEFS if a.get("tag") == "pt")
        for _ in range(3):
            mob.reset_area(adef)
        cont = self._container()
        assert sum(1 for c in cont.get("contents", []) if c["vnum"] == 8002) == 3

    def test_global_limit_caps_below_max(self, fresh_world):
        # limit 2 < max 5: fill stops when the template count reaches the limit
        self._setup(fresh_world, 2, 5)
        cont = self._container()
        assert sum(1 for c in cont.get("contents", []) if c["vnum"] == 8002) == 2


# ---------------------------------------------------------------------------
# R exit shuffle (decision 5)
# ---------------------------------------------------------------------------

class TestRReset:
    def test_shuffle_preserves_exit_set(self, fresh_world, monkeypatch):
        ROOM_DEFS._data[9000] = {"name": "maze", "exits":
                                 {"n": 9001, "e": 9002, "s": 9003, "w": 9004}}
        # force a definite reordering so the permutation actually happens
        monkeypatch.setattr(mob, "randint", lambda a, b: b)
        _reset_randomize_exits(9000, 4)
        assert set(ROOM_DEFS._data[9000]["exits"].values()) == {9001, 9002,
                                                                9003, 9004}

    def test_single_dir_is_noop(self, fresh_world, monkeypatch):
        ROOM_DEFS._data[9010] = {"name": "limbo", "exits": {"n": 9011}}
        monkeypatch.setattr(mob, "randint", lambda a, b: b)
        _reset_randomize_exits(9010, 1)
        assert ROOM_DEFS._data[9010]["exits"] == {"n": 9011}

    def test_door_exit_skips_shuffle(self, fresh_world, monkeypatch):
        door = {"to": 9101, "isdoor": True, "keyword": "gate"}
        exits = {"n": door, "e": 9102, "s": 9103, "w": 9104}
        ROOM_DEFS._data[9100] = {"name": "vault", "exits": exits}
        snapshot = dict(exits)
        monkeypatch.setattr(mob, "randint", lambda a, b: b)
        _reset_randomize_exits(9100, 4)
        assert ROOM_DEFS._data[9100]["exits"] == snapshot   # unchanged


# ---------------------------------------------------------------------------
# room_is_dark / room_light predicates (DARKNESS Phase A early landing)
# ---------------------------------------------------------------------------

class TestRoomDark:
    def _room_def(self, vnum, sector="field", flags=None):
        ROOM_DEFS._data[vnum] = {"name": "R", "exits": {}, "sector": sector,
                                 "flags": flags or {}}

    def test_lit_light_source_lights_room(self, fresh_world):
        from handler import room_is_dark, room_light
        ITEM_DEFS._data[500] = {"type": "light", "light_hours": -1,
                                "keywords": "torch", "short_descr": "a torch"}
        self._room_def(1, sector="field", flags={"dark": True})
        world.chars[1] = {"room": 1, "equip": {"light": {"vnum": 500}}}
        assert room_light(1) == 1
        assert room_is_dark(1) is False   # light overrides the dark flag

    def test_dead_light_does_not_count(self, fresh_world):
        from handler import room_light
        ITEM_DEFS._data[501] = {"type": "light", "light_hours": 0,
                                "keywords": "torch", "short_descr": "a torch"}
        self._room_def(2)
        world.chars[1] = {"room": 2, "equip": {"light": {"vnum": 501}}}
        assert room_light(2) == 0

    def test_dark_flag_forces_dark(self, fresh_world):
        from handler import room_is_dark
        self._room_def(3, sector="city", flags={"dark": True})
        # dark flag beats even a city sector
        assert room_is_dark(3) is True

    def test_inside_and_city_are_lit(self, fresh_world):
        from handler import room_is_dark
        self._room_def(4, sector="inside")
        self._room_def(5, sector="city")
        assert room_is_dark(4) is False
        assert room_is_dark(5) is False

    def test_outdoors_dark_at_night(self, fresh_world):
        from handler import room_is_dark
        from game_time import time_info, SUN_DARK, SUN_LIGHT
        self._room_def(6, sector="field")
        old = time_info["sunlight"]
        try:
            time_info["sunlight"] = SUN_DARK
            assert room_is_dark(6) is True
            time_info["sunlight"] = SUN_LIGHT
            assert room_is_dark(6) is False
        finally:
            time_info["sunlight"] = old


# ---------------------------------------------------------------------------
# M spawn extras end-to-end: real midgaard pet shop (decision 6)
# ---------------------------------------------------------------------------

@pytest.fixture
def real_world(monkeypatch):
    """Snapshot global world state, chdir to src so real area files load."""
    snap = {
        "chars": dict(world.chars),
        "rooms": dict(world.rooms._data),
        "loaded": set(world._LOADED_AREAS),
        "room_defs": dict(ROOM_DEFS._data),
        "mob_defs": dict(MOB_DEFS._data),
        "item_defs": dict(ITEM_DEFS._data),
        "door_defs": dict(world.DOOR_DEFS),
        "areas": list(world.areas),
        "area_defs": list(world.AREA_DEFS),
        "vnum_ranges": list(world._VNUM_RANGES),
        "tag_to_file": dict(world._TAG_TO_FILE),
        "tag_to_name": dict(world._TAG_TO_NAME),
        "ready": world._WORLD_READY,
    }
    world.init_world()
    monkeypatch.chdir(os.path.join(ROOT, _SRC))
    yield
    world.chars.clear(); world.chars.update(snap["chars"])
    world.rooms._data.clear(); world.rooms._data.update(snap["rooms"])
    world._LOADED_AREAS.clear(); world._LOADED_AREAS.update(snap["loaded"])
    ROOM_DEFS._data.clear(); ROOM_DEFS._data.update(snap["room_defs"])
    MOB_DEFS._data.clear(); MOB_DEFS._data.update(snap["mob_defs"])
    ITEM_DEFS._data.clear(); ITEM_DEFS._data.update(snap["item_defs"])
    world.DOOR_DEFS.clear(); world.DOOR_DEFS.update(snap["door_defs"])
    world.areas = snap["areas"]
    world.AREA_DEFS[:] = snap["area_defs"]
    world._VNUM_RANGES[:] = snap["vnum_ranges"]
    world._TAG_TO_FILE.clear(); world._TAG_TO_FILE.update(snap["tag_to_file"])
    world._TAG_TO_NAME.clear(); world._TAG_TO_NAME.update(snap["tag_to_name"])
    world._WORLD_READY = snap["ready"]


class TestMidgaardPetReset:
    def test_reset_flags_pets_and_buy_kitten(self, real_world):
        from player import create_char
        from shop import do_buy
        # Lazy-load midgaard -> area reset spawns pets in room 3032.
        _ = ROOM_DEFS[3031]
        adef = next(a for a in world.AREA_DEFS if a.get("tag") == "midgaard")
        mob.reset_area(adef)   # normalize: guarantee stock present

        stock = [world.chars[m] for m in world.rooms[3032]["mobs"]]
        pets = [m for m in stock if m.get("act_flags", {}).get("pet")]
        assert pets, "reset must flag pet-shop-adjacent mobs (room 3032) as pets"
        assert any("kitten" in MOB_DEFS[m["tpl"]].get("keywords", "")
                   for m in pets)

        player = create_char()
        player["id"] = 1
        player["name"] = "Buyer"
        player["room"] = 3031
        player["gold"] = 100
        player["_macros"] = {}
        world.chars[1] = player

        do_buy(player, ["kitten"])
        assert player["pet"] is not None
        pet = world.chars[player["pet"]]
        assert "kitten" in MOB_DEFS[pet["tpl"]].get("keywords", "")
        assert pet["act_flags"].get("pet")
        assert pet["affected_by"].get("charm")
