"""Tests for spell_locate_object world coverage and visibility fidelity."""

import pytest
import magic
import world
from handler import _char_base
from tools import build_mob_index
from world import ITEM_DEFS, MOB_DEFS, ROOM_DEFS


def _obj_row(vnum, keywords, home="beta", tags=("beta",)):
    """One objs.bin row dict in pack_key_index's input shape."""
    return {"vnum": vnum, "level": 0, "home": home, "keywords": keywords,
            "name": "", "tags": list(tags)}


def _write_key_index(path, rows):
    """Pack rows through the builder so fixtures keep the shipped layout."""
    path.write_bytes(build_mob_index.pack_key_index(list(rows)))


def _setup(fw, monkeypatch):
    fw.register_area("alpha", 100, 199,
                     rooms={100: {"name": "alpha", "exits": {}}})
    fw.setup()
    _ = ROOM_DEFS[100]
    monkeypatch.setattr(magic, "randint", lambda a, b: 1)
    out = []
    monkeypatch.setattr(magic, "chprintln",
                        lambda _ch, text="": out.append(text))
    player = _char_base()
    player.update({"id": 1, "name": "Tester", "room": 100, "level": 20,
                   "_target_name": "sword"})
    return player, out


def _room(name):
    return {"name": name, "desc": ".", "exits": {}, "sector": "inside",
            "flags": {}}


def _obj(keywords, **extra):
    tpl = {"keywords": keywords, "short_descr": "an object", "level": 0,
           "type": "treasure", "wear_flags": {"take": True}, "weight": 1,
           "value": 1}
    tpl.update(extra)
    return tpl


def _mob(keywords):
    return {"keywords": keywords, "short_descr": "a hidden carrier",
            "level": 1, "race": "Human", "hp_dice": (1, 1, 1),
            "hitroll": 0, "armor": (0, 0, 0, 0),
            "damage": (1, 1, 0), "dam_type": "punch"}


def _setup_remote(fw, monkeypatch, tmp_path, objects, resets=(), mobiles=None,
                  index=None):
    fw.register_area("alpha", 100, 199, rooms={100: _room("Alpha")})
    fw.register_area("beta", 200, 299, rooms={200: _room("Beta")},
                     mobiles=mobiles, objects=objects, resets=resets)
    fw.setup()
    _ = ROOM_DEFS[100]
    idx = tmp_path / "objs.bin"
    if index is None:
        index = [_obj_row(250, "silver sword")]
    _write_key_index(idx, index)
    monkeypatch.setattr(magic, "OBJ_INDEX_FILE", str(idx))
    monkeypatch.setattr(magic, "randint", lambda a, b: 1)
    out = []
    monkeypatch.setattr(magic, "chprintln",
                        lambda _ch, text="": out.append(text))
    player = _char_base()
    player.update({"id": 1, "name": "Tester", "room": 100, "level": 20,
                   "_target_name": "sword"})
    return player, out


def test_locate_finds_carried_item(fresh_world, monkeypatch):
    player, out = _setup(fresh_world, monkeypatch)
    ITEM_DEFS._data[5000] = {"keywords": "long sword", "level": 0}
    player["inv"] = [{"vnum": 5000}]

    assert magic.spell_locate_object(0, 20, player, None, "char")
    assert out == ["one is carried by you"]


def test_locate_skips_invis_item_without_detect(fresh_world, monkeypatch):
    player, out = _setup(fresh_world, monkeypatch)
    ITEM_DEFS._data[5000] = {"keywords": "long sword", "level": 0,
                             "extra_flags": {"invis": True}}
    player["inv"] = [{"vnum": 5000}]

    assert not magic.spell_locate_object(0, 20, player, None, "char")
    assert out == ["Nothing like that in heaven or earth."]

    out[:] = []
    player["affected_by"] = {"detect_invis": True}
    assert magic.spell_locate_object(0, 20, player, None, "char")
    assert out == ["one is carried by you"]


def test_locate_hides_invisible_carrier(fresh_world, monkeypatch):
    player, out = _setup(fresh_world, monkeypatch)
    ITEM_DEFS._data[5000] = {"keywords": "long sword", "level": 0}
    MOB_DEFS._data[150] = {"keywords": "shadow guard",
                           "short_descr": "a shadow guard"}
    mob = _char_base()
    mob.update({"id": 2, "is_npc": True, "tpl": 150, "room": 100,
                "level": 10, "inv": [{"vnum": 5000}]})
    world.chars[2] = mob

    assert magic.spell_locate_object(0, 20, player, None, "char")
    assert out == ["one is carried by a shadow guard"]

    out[:] = []
    mob["affected_by"] = {"invisible": True}
    assert magic.spell_locate_object(0, 20, player, None, "char")
    assert out == ["one is in somewhere"]


def test_locate_finds_unloaded_floor_item_then_releases_area(
        fresh_world, monkeypatch, tmp_path):
    player, out = _setup_remote(
        fresh_world, monkeypatch, tmp_path,
        {250: _obj("silver sword")}, resets=(("O", 250, 200),))

    assert magic.spell_locate_object(0, 20, player, None, "char")
    assert out == ["one is in Beta"]
    assert world._LOADED_AREAS == {"alpha"}


def test_locate_finds_unloaded_nested_pending_item(
        fresh_world, monkeypatch, tmp_path):
    player, out = _setup_remote(
        fresh_world, monkeypatch, tmp_path,
        {240: _obj("wooden chest", type="container"),
         250: _obj("silver sword")},
        index=[_obj_row(250, "silver sword", tags=())])
    world._pending_room_items[200] = "v:240;co:[v:250]"

    assert magic.spell_locate_object(0, 20, player, None, "char")
    assert out == ["one is in Beta"]
    assert world._LOADED_AREAS == {"alpha"}


def test_locate_does_not_load_resetless_template_without_pending_instance(
        fresh_world, monkeypatch, tmp_path):
    player, out = _setup_remote(
        fresh_world, monkeypatch, tmp_path,
        {250: _obj("silver sword")},
        index=[_obj_row(250, "silver sword", tags=())])

    assert not magic.spell_locate_object(0, 20, player, None, "char")
    assert out == ["Nothing like that in heaven or earth."]
    assert world._LOADED_AREAS == {"alpha"}


def test_locate_finds_unloaded_nested_reset_item(
        fresh_world, monkeypatch, tmp_path):
    player, out = _setup_remote(
        fresh_world, monkeypatch, tmp_path,
        {240: _obj("wooden chest", type="container"),
         250: _obj("silver sword")},
        resets=(("O", 240, 200), ("P", 250, 2, 240, 1)))

    assert magic.spell_locate_object(0, 20, player, None, "char")
    assert out == ["one is in Beta"]
    assert world._LOADED_AREAS == {"alpha"}


def test_locate_finds_unloaded_item_on_invisible_mob(
        fresh_world, monkeypatch, tmp_path):
    player, out = _setup_remote(
        fresh_world, monkeypatch, tmp_path,
        {250: _obj("silver sword")},
        resets=(("M", 210, 1, 200, 1), ("G", 250, 1)),
        mobiles={210: _mob("carrier")})

    # Every remote carrier is invisible to exercise upstream's "somewhere".
    original = magic.can_see
    monkeypatch.setattr(magic, "can_see",
                        lambda ch, mob: False if mob.get("tpl") == 210
                        else original(ch, mob))
    assert magic.spell_locate_object(0, 20, player, None, "char")
    assert out == ["one is in somewhere"]
    assert world._LOADED_AREAS == {"alpha"}


def test_locate_finds_wanderer_restored_into_scanned_area(
        fresh_world, monkeypatch, tmp_path):
    player, out = _setup_remote(
        fresh_world, monkeypatch, tmp_path,
        {250: _obj("silver sword")},
        resets=(("M", 210, 1, 200, 1), ("G", 250, 1)),
        mobiles={210: _mob("carrier")})
    # Beta's wanderer was buffered standing in alpha's (already-scanned)
    # room; hydration restores it there, so the room-tag filter alone
    # would miss it -- the template-tag test must catch it.
    world._pending_mob_saves[210] = [100]

    assert magic.spell_locate_object(0, 20, player, None, "char")
    assert out == ["one is carried by a hidden carrier"]
    assert world._LOADED_AREAS == {"alpha"}


def test_locate_result_cap_prevents_remote_load(
        fresh_world, monkeypatch, tmp_path):
    player, out = _setup_remote(
        fresh_world, monkeypatch, tmp_path,
        {250: _obj("silver sword")}, resets=(("O", 250, 200),))
    ITEM_DEFS._data[150] = _obj("silver sword")
    player["inv"] = [{"vnum": 150}, {"vnum": 150}]

    assert magic.spell_locate_object(0, 1, player, None, "char")
    assert out == ["one is carried by you", "one is carried by you"]
    assert world._LOADED_AREAS == {"alpha"}
    assert 200 not in world._pending_room_items


def test_locate_releases_remote_area_when_scan_raises(
        fresh_world, monkeypatch, tmp_path):
    player, _out = _setup_remote(
        fresh_world, monkeypatch, tmp_path,
        {250: _obj("silver sword")}, resets=(("O", 250, 200),))
    def fail_scan(_ch, _obj):
        raise RuntimeError("boom")

    monkeypatch.setattr(magic, "can_see_obj", fail_scan)

    with pytest.raises(RuntimeError, match="boom"):
        magic.spell_locate_object(0, 20, player, None, "char")
    assert world._LOADED_AREAS == {"alpha"}
