"""Tests for the PrimeSUD-only Swordsman class and sword forms."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import combat
import world
from classes import CLASS_SWORDSMAN, CLASS_TABLE
from groups import group_lookup
from player import create_char
from skills_table import (GSN_DAGGER, GSN_DRIVING_FORM, GSN_FLOWING_FORM,
                          GSN_RIPOSTE, GSN_SWORD, SKILLS)
from world import ITEM_DEFS, ROOM_DEFS


ROOM_VNUM = 9801
SWORD_VNUM = 9802


@pytest.fixture(autouse=True)
def _swordsman_world():
    old_rooms = dict(ROOM_DEFS._data)
    old_wrooms = dict(world.rooms._data)
    old_items = dict(ITEM_DEFS._data)
    old_chars = dict(world.chars)
    room = {"name": "Practice Room", "desc": "x", "exits": {}, "items": [],
            "mobs": [], "area": "test", "flags": {}, "sector": "inside"}
    ROOM_DEFS._data[ROOM_VNUM] = room
    world.rooms._data[ROOM_VNUM] = room
    ITEM_DEFS._data[SWORD_VNUM] = {
        "type": "weapon", "weapon_type": "sword", "dam_type": "slash",
        "dice": (1, 4, 0), "short_descr": "a practice sword",
    }
    yield
    ROOM_DEFS._data.clear()
    ROOM_DEFS._data.update(old_rooms)
    world.rooms._data.clear()
    world.rooms._data.update(old_wrooms)
    ITEM_DEFS._data.clear()
    ITEM_DEFS._data.update(old_items)
    world.chars.clear()
    world.chars.update(old_chars)


def _fighter(cid):
    ch = create_char(CLASS_SWORDSMAN)
    ch["id"] = cid
    ch["name"] = "Tester" + str(cid)
    ch["room"] = ROOM_VNUM
    ch["level"] = 50
    ch["equip"]["wield"] = {"vnum": SWORD_VNUM}
    ch["learned"][GSN_SWORD] = 100
    ch["learned"][GSN_FLOWING_FORM] = 100
    ch["learned"][GSN_RIPOSTE] = 100
    ch["learned"][GSN_DRIVING_FORM] = 100
    world.chars[cid] = ch
    return ch


def test_class_data_and_default_groups():
    ch = create_char(CLASS_SWORDSMAN)
    assert CLASS_TABLE[CLASS_SWORDSMAN]["names"] == ("Swordsman", "Sword Saint")
    assert group_lookup("swordsman basics") in ch["groups"]
    assert group_lookup("swordsman default") in ch["groups"]
    assert GSN_DAGGER not in ch["learned"]
    assert SKILLS[GSN_DAGGER]["rating"][CLASS_SWORDSMAN] == 2
    for sn in (GSN_FLOWING_FORM, GSN_RIPOSTE, GSN_DRIVING_FORM):
        assert sn in ch["learned"]
    assert SKILLS[GSN_FLOWING_FORM]["skill_level"][CLASS_SWORDSMAN] == 12
    assert SKILLS[GSN_RIPOSTE]["skill_level"][CLASS_SWORDSMAN] == 30
    assert SKILLS[GSN_DRIVING_FORM]["skill_level"][CLASS_SWORDSMAN] == 42


@pytest.mark.parametrize(
    "command,sn,form,accuracy,damage",
    ((combat.do_flow, GSN_FLOWING_FORM, "flowing", 4, 90),
     (combat.do_drive, GSN_DRIVING_FORM, "driving", 0, 140)),
)
def test_active_forms_use_one_modified_sword_hit(
        monkeypatch, command, sn, form, accuracy, damage):
    ch = _fighter(1)
    victim = _fighter(2)
    ch["fighting"] = victim["id"]
    victim["fighting"] = ch["id"]
    calls = []
    improves = []
    monkeypatch.setattr(combat, "_sword_act", lambda *args: None)
    monkeypatch.setattr(combat, "randint", lambda a, b: 1)
    monkeypatch.setattr(
        combat, "check_improve", lambda *args: improves.append(args))
    monkeypatch.setattr(
        combat, "one_hit",
        lambda actor, target, **kwargs: calls.append((actor, target, kwargs)) or True)

    command(ch, [])

    assert ch["wait"] == SKILLS[sn]["beats"]
    assert ch["_sword_form"] == form
    assert len(calls) == 1
    assert calls[0][2] == {
        "accuracy_bonus": accuracy,
        "damage_percent": damage,
    }
    assert improves == [(ch, sn, True, 2)]


def test_active_form_dex_bonus_affects_skill_roll(monkeypatch):
    ch = _fighter(1)
    victim = _fighter(2)
    ch["fighting"] = victim["id"]
    ch["learned"][GSN_FLOWING_FORM] = 50
    hits = []
    monkeypatch.setattr(combat, "_sword_act", lambda *args: None)
    monkeypatch.setattr(combat, "randint", lambda a, b: 50)
    monkeypatch.setattr(combat, "check_improve", lambda *args: None)
    monkeypatch.setattr(
        combat, "one_hit",
        lambda *args, **kwargs: hits.append(1) or True)

    combat.do_flow(ch, [])

    assert hits == [1]  # Human Swordsman's starting DEX 16 supplies +1.


def test_failed_active_form_checks_improvement(monkeypatch):
    ch = _fighter(1)
    victim = _fighter(2)
    ch["fighting"] = victim["id"]
    ch["learned"][GSN_FLOWING_FORM] = 50
    improves = []
    monkeypatch.setattr(combat, "_sword_act", lambda *args: None)
    monkeypatch.setattr(combat, "randint", lambda a, b: 100)
    monkeypatch.setattr(combat, "damage", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        combat, "check_improve", lambda *args: improves.append(args))

    combat.do_flow(ch, [])

    assert improves == [(ch, GSN_FLOWING_FORM, False, 2)]


def test_active_form_requires_sword(monkeypatch):
    ch = _fighter(1)
    victim = _fighter(2)
    ch["fighting"] = victim["id"]
    ch["equip"]["wield"] = None
    calls = []
    monkeypatch.setattr(combat, "one_hit", lambda *args, **kwargs: calls.append(1))

    combat.do_flow(ch, [])

    assert calls == []
    assert ch["wait"] == 0


def test_riposte_cannot_chain(monkeypatch):
    attacker = _fighter(1)
    defender = _fighter(2)
    hits = []
    improves = []
    monkeypatch.setattr(combat, "_sword_act", lambda *args: None)
    monkeypatch.setattr(combat, "randint", lambda a, b: 1)
    monkeypatch.setattr(
        combat, "check_improve", lambda *args: improves.append(args))

    def one_hit(actor, target, **kwargs):
        hits.append((actor["id"], target["id"]))
        combat._try_riposte(actor, target)
        return True

    monkeypatch.setattr(combat, "one_hit", one_hit)
    combat._try_riposte(attacker, defender)

    assert hits == [(2, 1)]
    assert "_riposting" not in defender
    assert improves == [(defender, GSN_RIPOSTE, True, 4)]


def test_riposte_dex_bonus_affects_proc_roll(monkeypatch):
    attacker = _fighter(1)
    defender = _fighter(2)
    defender["learned"][GSN_RIPOSTE] = 4
    hits = []
    monkeypatch.setattr(combat, "_sword_act", lambda *args: None)
    monkeypatch.setattr(combat, "randint", lambda a, b: 2)
    monkeypatch.setattr(combat, "check_improve", lambda *args: None)
    monkeypatch.setattr(
        combat, "one_hit",
        lambda *args, **kwargs: hits.append(1) or True)

    combat._try_riposte(attacker, defender)

    assert hits == [1]  # 4 // 4 plus starting DEX bonus 1.


def test_failed_riposte_roll_checks_improvement(monkeypatch):
    attacker = _fighter(1)
    defender = _fighter(2)
    hits = []
    improves = []
    monkeypatch.setattr(combat, "randint", lambda a, b: 100)
    monkeypatch.setattr(
        combat, "one_hit",
        lambda *args, **kwargs: hits.append(1) or True)
    monkeypatch.setattr(
        combat, "check_improve", lambda *args: improves.append(args))

    combat._try_riposte(attacker, defender)

    assert hits == []
    assert improves == [(defender, GSN_RIPOSTE, False, 4)]


def test_successful_parry_triggers_riposte(monkeypatch):
    attacker = _fighter(1)
    defender = _fighter(2)
    defender["learned"][combat.GSN_PARRY] = 100
    hits = []
    monkeypatch.setattr(combat, "_sword_act", lambda *args: None)
    monkeypatch.setattr(combat, "randint", lambda a, b: 1)
    monkeypatch.setattr(combat, "check_improve", lambda *args: None)
    monkeypatch.setattr(
        combat, "one_hit",
        lambda actor, target, **kwargs: hits.append((actor["id"], target["id"])) or True)

    assert combat.check_parry(attacker, defender)
    assert hits == [(2, 1)]


def test_form_defaults_switches_flourish_and_persists(monkeypatch):
    ch = _fighter(1)
    victim = _fighter(2)
    monkeypatch.setattr(combat, "autodrop", lambda actor: None)
    combat.set_fighting(ch, victim)
    victim["fighting"] = ch["id"]
    assert ch["_sword_form"] == "flowing"

    monkeypatch.setattr(combat, "_sword_act", lambda *args: None)
    monkeypatch.setattr(combat, "randint", lambda a, b: 1)
    monkeypatch.setattr(combat, "check_improve", lambda *args: None)
    monkeypatch.setattr(combat, "one_hit", lambda *args, **kwargs: True)
    combat.do_drive(ch, [])
    seen = []
    monkeypatch.setattr(
        combat, "_sword_act", lambda lines, actor, target: seen.append(lines))
    combat._sword_flourish(ch, victim)
    assert seen == [combat._DRIVING_FLOURISHES]

    combat.stop_fighting(ch, both=True)
    assert ch["_sword_form"] == "driving"

    combat.set_fighting(ch, victim)
    assert ch["_sword_form"] == "driving"
