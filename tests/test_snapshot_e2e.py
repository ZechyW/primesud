"""End-to-end guard for SNAPSHOT_PLAN.md Phase E (sec. Tests, End to end).

A player carries/wears gear from two evicted foreign areas (one item nested
inside a container). Those areas are evicted, the world is saved, reset, and
reloaded, then every hot instance-aware path swept in Phase E runs over the
restored gear in turn: reset_char, can_see_obj, get_obj_list keyword lookup,
info.do_look's extra-desc scan, and shop browse/list over a foreign-stocked
keeper. Each step re-asserts that the owner areas are still unloaded, so a
regression pinpoints exactly which path dragged an area back in.
"""
import pytest

import world
import game_state
from item import create_object, get_obj_list
from handler import _char_base, can_see_obj
from player import create_char, reset_char
import info
import shop


@pytest.fixture(autouse=True)
def _clear_item_snapshots():
    """Keep ITEM_SNAPSHOTS from leaking between tests. [PRIMESUD]

    Same convention as test_area_eviction.py / test_snapshot_save.py: fresh_world
    does not snapshot/restore world.ITEM_SNAPSHOTS, so this module clears it
    itself.
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


HOME_ROOM = 900
KEEPER_VNUM = 950
GEM = 110
RING = 111
POUCH = 210
BEAD = 211


def _register_world(fw):
    """Home area (stays loaded) plus two foreign areas that get evicted."""
    fw.register_area(
        "home", 900, 999,
        rooms={HOME_ROOM: {"name": "Home", "exits": {}}},
        mobiles={KEEPER_VNUM: {
            "short_descr": "a shopkeeper", "keywords": "shopkeeper",
            "level": 1, "hp_dice": (1, 1, 10), "hitroll": 0,
            "armor": (0, 0, 0, 0), "damage": (1, 2, 0), "dam_type": "punch",
            "shop": {"keeper": KEEPER_VNUM, "buy_types": ["treasure"],
                     "profit_buy": 100, "profit_sell": 50,
                     "open_hour": 0, "close_hour": 23},
        }})
    fw.register_area(
        "alpha", 100, 199,
        rooms={100: {"name": "R100", "exits": {}}},
        objects={
            GEM: _item_tpl("gem", short_descr="a gem", keywords="gem",
                            extra_descs=[("gem", "It sparkles with a foreign light.")]),
            RING: _item_tpl("ring", short_descr="a ring", keywords="ring"),
        })
    fw.register_area(
        "beta", 200, 299,
        rooms={200: {"name": "R200", "exits": {}}},
        objects={
            POUCH: _item_tpl("pouch", short_descr="a pouch", keywords="pouch",
                              type="container"),
            BEAD: _item_tpl("bead", short_descr="a bead", keywords="bead"),
        })
    fw.setup()


def _assert_foreign_unloaded():
    assert not world.is_area_loaded("alpha")
    assert not world.is_area_loaded("beta")


class TestSnapshotEndToEnd:
    def test_restored_gear_from_multiple_areas_never_reloads_owner(
            self, fresh_world, monkeypatch):
        fw = fresh_world
        _register_world(fw)

        world._load_area("home")
        world._load_area("alpha")
        world._load_area("beta")

        player = create_char()
        player["name"] = "Tester"
        player["room"] = HOME_ROOM
        player["_macros"] = {}
        world.chars[1] = player

        gem = create_object(GEM)
        pouch = create_object(POUCH)
        pouch["contents"] = [create_object(BEAD)]
        player["inv"] = [gem, pouch]
        player["equip"]["finger_l"] = create_object(RING)

        world._unload_area("alpha")
        world._unload_area("beta")
        _assert_foreign_unloaded()
        assert {GEM, RING, POUCH, BEAD} <= set(world.ITEM_SNAPSHOTS)

        assert game_state.save_world(quiet=True)
        _assert_foreign_unloaded()

        world.reset_lazy()
        player2 = create_char()
        player2["_macros"] = {}
        player2["room"] = HOME_ROOM
        world.chars[1] = player2
        assert game_state.load_world() == "file"

        # load_world's "player room in world.rooms" probe loads only the
        # player's OWN area (home); alpha/beta must stay untouched.
        assert world.is_area_loaded("home")
        _assert_foreign_unloaded()

        gem2, pouch2 = player2["inv"]
        ring2 = player2["equip"]["finger_l"]
        bead2 = pouch2["contents"][0]

        # -- reset_char: equip/affect recompute over restored gear
        reset_char(player2)
        _assert_foreign_unloaded()

        # -- can_see_obj on each item (including the nested content)
        for obj in (gem2, pouch2, ring2, bead2):
            assert can_see_obj(player2, obj)
        _assert_foreign_unloaded()

        # -- keyword lookup through get_obj_list (get/wear-style resolution)
        assert get_obj_list("gem", player2["inv"], world.ITEM_DEFS, player2) is gem2
        assert get_obj_list("pouch", player2["inv"], world.ITEM_DEFS, player2) is pouch2
        assert get_obj_list("ring", [ring2], world.ITEM_DEFS, player2) is ring2
        _assert_foreign_unloaded()

        # -- look/examine extra-description scan (info._look_scan_items)
        look_lines = []
        monkeypatch.setattr(
            info, "chprintln",
            lambda *a, **kw: look_lines.append(" ".join(str(x) for x in a)))
        info.do_look(player2, ["gem"])
        assert any("sparkles" in ln for ln in look_lines)
        _assert_foreign_unloaded()

        # -- shop browse/list over foreign keeper stock: NPCs aren't
        # persisted (SNAPSHOT_PLAN.md sec. Serialization), so spawn the
        # keeper fresh in the now-loaded home area, stocked with a vnum
        # that is only reachable through the registry -- built by hand,
        # not create_object, since ITEM_DEFS[vnum] would itself reload
        # alpha.
        keeper = _char_base()
        keeper.update({"id": 2, "name": "Shopkeeper", "is_npc": True,
                       "tpl": KEEPER_VNUM, "room": HOME_ROOM, "level": 1,
                       "inv": [{"vnum": GEM, "cost": 10}], "equip": {}})
        world.chars[2] = keeper
        world.rooms._data[HOME_ROOM]["mobs"].append(2)

        list_lines = []
        monkeypatch.setattr(
            shop, "chprintln",
            lambda *a, **kw: list_lines.append(" ".join(str(x) for x in a)))
        shop.do_list(player2, [])
        assert any("a gem" in ln for ln in list_lines)
        _assert_foreign_unloaded()

        found = shop._get_obj_keeper(player2, keeper, "gem")
        assert found is keeper["inv"][0]
        _assert_foreign_unloaded()

        # -- a second save_world call
        assert game_state.save_world(quiet=True)
        _assert_foreign_unloaded()
