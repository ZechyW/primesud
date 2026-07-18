"""Tests for do_enter (act_enter.c) and spell_portal/spell_nexus (magic2.c)."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

from handler import _char_base
import handler
import magic
import movement
import world
from world import ROOM_DEFS, MOB_DEFS, ITEM_DEFS, OBJ_VNUM_PORTAL

MOB_TPL = 9401
STONE_VNUM = 9420


def _stub_room(vnum, **extra):
    room = {"name": "Test Room", "desc": "A test room.", "exits": {},
            "items": [], "mobs": [], "area": "test", "flags": {},
            "sector": "inside"}
    room.update(extra)
    ROOM_DEFS._data[vnum] = room
    world.rooms._data[vnum] = room
    return room


def _make_player(room=9001):
    ch = _char_base()
    ch["id"] = 1
    ch["name"] = "Tester"
    ch["level"] = 30
    ch["room"] = room
    world.chars[1] = ch
    return ch


def _make_mob(mid, room=9001, **overrides):
    ch = _char_base()
    ch["id"] = mid
    ch["is_npc"] = True
    ch["tpl"] = MOB_TPL
    ch["name"] = "a test dog"
    ch["level"] = 5
    ch["room"] = room
    ch.update(overrides)
    world.chars[mid] = ch
    if room in world.rooms._data:
        world.rooms._data[room]["mobs"].append(mid)
    return ch


@pytest.fixture(autouse=True)
def _clean_world_state(monkeypatch):
    old_rooms = dict(ROOM_DEFS._data)
    old_wrooms = dict(world.rooms._data)
    old_chars = dict(world.chars)
    old_mobs = dict(MOB_DEFS._data)
    old_items = dict(ITEM_DEFS._data)
    MOB_DEFS._data[MOB_TPL] = {
        "short_descr": "a test dog", "long_descr": "A test dog is here.",
        "keywords": "dog test", "level": 5, "race": "Human",
        "hp_dice": (1, 1, 10), "hitroll": 0, "damage": (1, 4, 0),
        "armor": (0, 0, 0, 0),
    }
    ITEM_DEFS._data[OBJ_VNUM_PORTAL] = {
        "keywords": "gate portal", "short_descr": "A shimmering gate",
        "description": "A shimmering black gate rises from the ground.",
        "type": "portal", "wear_flags": {},
        "extra_flags": {"magic": True, "nopurge": True},
        "level": 0, "weight": 0, "value": 0,
    }
    ITEM_DEFS._data[STONE_VNUM] = {
        "keywords": "warp stone", "short_descr": "a warp stone",
        "type": "warp_stone", "wear_flags": {"take": True, "hold": True},
        "level": 0,
    }
    _stub_room(9001)
    _stub_room(9002)
    _stub_room(9003)
    # deterministic saves + no room rendering
    monkeypatch.setattr(magic, "saves_spell", lambda *a: False)
    monkeypatch.setattr(movement, "do_look", lambda ch, args: None)
    yield
    ROOM_DEFS._data.clear()
    ROOM_DEFS._data.update(old_rooms)
    world.rooms._data.clear()
    world.rooms._data.update(old_wrooms)
    world.chars.clear()
    world.chars.update(old_chars)
    MOB_DEFS._data.clear()
    MOB_DEFS._data.update(old_mobs)
    ITEM_DEFS._data.clear()
    ITEM_DEFS._data.update(old_items)


@pytest.fixture
def out(monkeypatch):
    lines = []
    capture = lambda *a, **kw: lines.append(" ".join(str(x) for x in a))
    monkeypatch.setattr(handler, "tprint", capture)
    monkeypatch.setattr(movement, "tprint", capture)
    return lines


def _held_stone(player):
    stone = {"vnum": STONE_VNUM}
    player["equip"]["hold"] = stone
    return stone


# -- spell_portal / spell_nexus -------------------------------------------------

def test_spell_portal_creates_portal(out):
    player = _make_player(9001)
    _make_mob(2, room=9002)
    _held_stone(player)
    player["_target_name"] = "dog"
    ok = magic.spell_portal(0, 30, player, None, "char")
    assert ok
    assert player["equip"]["hold"] is None  # stone consumed
    items = world.rooms._data[9001]["items"]
    assert len(items) == 1
    portal = items[0]
    assert portal["vnum"] == OBJ_VNUM_PORTAL
    assert portal["to_vnum"] == 9002
    assert portal["timer"] == 2 + 30 // 25


def test_spell_portal_needs_warp_stone(out):
    player = _make_player(9001)
    _make_mob(2, room=9002)
    player["_target_name"] = "dog"
    ok = magic.spell_portal(0, 30, player, None, "char")
    assert not ok
    assert any("lack the proper component" in l for l in out)
    assert world.rooms._data[9001]["items"] == []


def test_spell_portal_rejects_norecall_dest(out):
    ROOM_DEFS._data[9002]["flags"]["no_recall"] = True
    player = _make_player(9001)
    _make_mob(2, room=9002)
    _held_stone(player)
    player["_target_name"] = "dog"
    assert not magic.spell_portal(0, 30, player, None, "char")
    assert any("You failed." in l for l in out)


def test_spell_nexus_creates_both_ends(out):
    player = _make_player(9001)
    _make_mob(2, room=9002)
    _held_stone(player)
    player["_target_name"] = "dog"
    ok = magic.spell_nexus(0, 30, player, None, "char")
    assert ok
    near = world.rooms._data[9001]["items"]
    far = world.rooms._data[9002]["items"]
    assert len(near) == 1 and near[0]["to_vnum"] == 9002
    assert len(far) == 1 and far[0]["to_vnum"] == 9001
    assert near[0]["timer"] == 1 + 30 // 10


# -- do_enter ---------------------------------------------------------------------

def _room_portal(room=9001, to_vnum=9002, **fields):
    portal = {"vnum": OBJ_VNUM_PORTAL, "to_vnum": to_vnum}
    portal.update(fields)
    world.rooms._data[room]["items"].append(portal)
    return portal


def test_enter_moves_player(out):
    player = _make_player(9001)
    _room_portal()
    movement.do_enter(player, ["gate"])
    assert player["room"] == 9002
    assert any("walk through" in l for l in out)


def test_enter_no_portal(out):
    player = _make_player(9001)
    movement.do_enter(player, ["gate"])
    assert player["room"] == 9001
    assert any("don't see that here" in l for l in out)


def test_enter_dead_destination(out):
    player = _make_player(9001)
    _room_portal(to_vnum=0)
    movement.do_enter(player, ["gate"])
    assert player["room"] == 9001
    assert any("doesn't seem to go anywhere" in l for l in out)


def test_enter_cursed_player_blocked(out):
    player = _make_player(9001)
    player["affected_by"] = {"curse": True}
    _room_portal()
    movement.do_enter(player, ["gate"])
    assert player["room"] == 9001
    assert any("Something prevents you from leaving" in l for l in out)


def test_enter_last_charge_fades_portal(out):
    player = _make_player(9001)
    _room_portal(charges=1)
    movement.do_enter(player, ["gate"])
    assert player["room"] == 9002
    assert world.rooms._data[9001]["items"] == []
    assert world.rooms._data[9002]["items"] == []
    assert any("fades out of existence" in l for l in out)


def test_portal_targets_unloaded_area_mob(out, monkeypatch, tmp_path):
    # _find_unloaded_mob: index hit -> area load -> spawned instance found
    player = _make_player(9001)
    _held_stone(player)
    player["_target_name"] = "dragon"
    idx = tmp_path / "mobs.idx"
    idx.write_text("testarea|9402|red dragon\n")
    monkeypatch.setattr(magic, "MOB_INDEX_FILE", str(idx))
    loaded = []

    def fake_load(tag):
        loaded.append(tag)
        MOB_DEFS._data[9402] = {"keywords": "red dragon",
                                "short_descr": "a red dragon", "level": 10}
        _make_mob(3, room=9002, tpl=9402)
    monkeypatch.setattr(world, "_ensure_area_by_tag", fake_load)
    ok = magic.spell_portal(0, 30, player, None, "char")
    assert ok
    assert loaded == ["testarea"]
    assert world.rooms._data[9001]["items"][0]["to_vnum"] == 9002


def test_find_unloaded_mob_second_mob_same_area(monkeypatch, tmp_path):
    # first index hit has no instance; sibling mob spawned by the same
    # area load must still be found (later same-tag lines get skipped)
    _make_player(9001)
    idx = tmp_path / "mobs.idx"
    idx.write_text("testarea|9402|red dragon\n"
                   "testarea|9403|blue dragon\n")
    monkeypatch.setattr(magic, "MOB_INDEX_FILE", str(idx))

    def fake_load(tag):
        # 9402 never spawns; 9403 does
        MOB_DEFS._data[9403] = {"keywords": "blue dragon",
                                "short_descr": "a blue dragon", "level": 10}
        _make_mob(3, room=9002, tpl=9403)
        world._LOADED_AREAS.add(tag)
    monkeypatch.setattr(world, "_ensure_area_by_tag", fake_load)
    monkeypatch.setattr(world, "_LOADED_AREAS", set())
    cid, mob = magic._find_unloaded_mob("dragon")
    assert cid == 3
    assert mob["tpl"] == 9403


def test_find_unloaded_mob_edge_cases(monkeypatch, tmp_path):
    # missing index file: fail loud (index always shipped in a dist)
    monkeypatch.setattr(magic, "MOB_INDEX_FILE", str(tmp_path / "absent.dat"))
    with pytest.raises(OSError):
        magic._find_unloaded_mob("dragon")
    # loaded areas skipped; header comment ignored; no-spawn load capped at 2
    idx = tmp_path / "mobs.idx"
    idx.write_text("# tag|vnum|keywords header\n"
                   "loadedarea|9402|red dragon\n"
                   "ghost1|9403|red dragon\n"
                   "ghost2|9404|red dragon\n"
                   "ghost3|9405|red dragon\n")
    monkeypatch.setattr(magic, "MOB_INDEX_FILE", str(idx))
    monkeypatch.setattr(world, "_LOADED_AREAS", {"loadedarea"})
    loaded = []
    monkeypatch.setattr(world, "_ensure_area_by_tag", loaded.append)
    assert magic._find_unloaded_mob("dragon") == (None, None)
    assert loaded == ["ghost1", "ghost2"]


def test_random_gate_uses_area_pick(out, monkeypatch):
    # get_random_room: random area -> ensure loaded -> room within it
    player = _make_player(9001)
    monkeypatch.setattr(world, "_AREA_FILES",
                        [("test.py", "test", "Test", 0, 0)])
    monkeypatch.setattr(world, "_ensure_area_by_tag", lambda tag: None)
    world.AREA_DEFS.append({"tag": "test", "room_vnums": [9002]})
    try:
        _room_portal(to_vnum=-1, gate_flags={"random": True})
        movement.do_enter(player, ["gate"])
    finally:
        world.AREA_DEFS.pop()
    assert player["room"] == 9002


def test_enter_pet_follows(out):
    player = _make_player(9001)
    pet = _make_mob(2, room=9001)
    pet["master"] = 1
    pet["leader"] = 1
    pet["affected_by"] = {"charm": True}
    pet["pos"] = "standing"
    _room_portal()
    movement.do_enter(player, ["gate"])
    assert player["room"] == 9002
    assert pet["room"] == 9002
    assert 2 in world.rooms._data[9002]["mobs"]
    assert 2 not in world.rooms._data[9001]["mobs"]
