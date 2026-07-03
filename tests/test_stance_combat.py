"""Tests for stance combat integration (combat.py) vs 1stMud fight.c."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "primesud.hpappdir")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

from handler import _char_base
import combat
from combat import (can_counter, can_bypass, dambonus, special_move,
                    set_fighting, stop_fighting, check_assist)
from stances import (STANCE_NONE, STANCE_NORMAL, STANCE_VIPER, STANCE_CRANE,
                     STANCE_CRAB, STANCE_BULL, STANCE_MONKEY,
                     STANCE_CURRENT, STANCE_AUTODROP,
                     get_stance, set_stance)
import world
from world import ROOM_DEFS, MOB_DEFS


MOB_TPL = 9403


def _stub_room(vnum):
    room = {"name": "Test Room", "desc": "x", "exits": {}, "items": [],
            "mobs": [], "area": "test", "flags": {}, "sector": "inside"}
    ROOM_DEFS._data[vnum] = room
    world.rooms._data[vnum] = room
    return room


def _make_char(cid=1, npc=False, **overrides):
    ch = _char_base()
    ch["id"] = cid
    ch["is_npc"] = npc
    ch["name"] = "Tester" if not npc else "a test mob"
    ch["level"] = 20
    ch["room"] = 9001
    if npc:
        ch["tpl"] = MOB_TPL
    ch.update(overrides)
    world.chars[cid] = ch
    if npc and 9001 in world.rooms._data:
        world.rooms._data[9001]["mobs"].append(cid)
    return ch


@pytest.fixture(autouse=True)
def _clean_world_state():
    old_rooms = dict(ROOM_DEFS._data)
    old_wrooms = dict(world.rooms._data)
    old_chars = dict(world.chars)
    old_mobs = dict(MOB_DEFS._data)
    MOB_DEFS._data[MOB_TPL] = {
        "short_descr": "a test mob", "long_descr": "A test mob is here.",
        "keywords": "mob test", "level": 5, "race": "Human",
        "hp_dice": (1, 1, 10), "hitroll": 0, "damage": (1, 4, 0),
        "armor": (0, 0, 0, 0),
    }
    _stub_room(9001)
    yield
    ROOM_DEFS._data.clear()
    ROOM_DEFS._data.update(old_rooms)
    world.rooms._data.clear()
    world.rooms._data.update(old_wrooms)
    world.chars.clear()
    world.chars.update(old_chars)
    MOB_DEFS._data.clear()
    MOB_DEFS._data.update(old_mobs)


class TestCounterBypass:
    def test_monkey_counters(self):
        ch = _make_char()
        set_stance(ch, STANCE_CURRENT, STANCE_MONKEY)
        assert can_counter(ch)
        set_stance(ch, STANCE_CURRENT, STANCE_VIPER)
        assert not can_counter(ch)

    def test_bypass_stances(self):
        ch = _make_char()
        other = _make_char(2)
        for st in (1, 6, 8):   # viper, mantis, tiger
            set_stance(ch, STANCE_CURRENT, st)
            assert can_bypass(ch, other)
        set_stance(ch, STANCE_CURRENT, STANCE_CRAB)
        assert not can_bypass(ch, other)


class TestDambonus:
    def test_zero_and_invalid(self):
        ch = _make_char()
        v = _make_char(2)
        assert dambonus(ch, v, 0, STANCE_VIPER) == 0
        assert dambonus(ch, v, 50, STANCE_NONE) == 50

    def test_bull_bonus_over_100(self):
        ch = _make_char()
        v = _make_char(2)
        set_stance(ch, STANCE_CURRENT, STANCE_BULL)
        set_stance(ch, STANCE_BULL, 150)
        # dam += dam * (150 // 100) -> doubled
        assert dambonus(ch, v, 50, STANCE_BULL) == 100

    def test_weak_stance_penalty(self):
        ch = _make_char()
        v = _make_char(2)
        set_stance(ch, STANCE_CURRENT, STANCE_VIPER)
        set_stance(ch, STANCE_VIPER, 50)   # < 100 trained
        assert dambonus(ch, v, 50, STANCE_VIPER) == 25   # dam * 5 // 10

    def test_crab_defense_over_100(self):
        ch = _make_char()
        v = _make_char(2)
        set_stance(ch, STANCE_CURRENT, STANCE_VIPER)
        set_stance(ch, STANCE_VIPER, 150)   # attacker trained, no penalty
        set_stance(v, STANCE_CURRENT, STANCE_CRAB)
        set_stance(v, STANCE_CRAB, 200)
        # dam //= (200 // 100) -> halved
        assert dambonus(ch, v, 50, STANCE_VIPER) == 25

    def test_monkey_mastered_keeps_dam(self):
        ch = _make_char()
        v = _make_char(2)
        set_stance(ch, STANCE_CURRENT, STANCE_MONKEY)
        set_stance(ch, STANCE_MONKEY, 199)
        # (199 + 1) // 200 = 1 -> dam unchanged
        assert dambonus(ch, v, 40, STANCE_MONKEY) == 40

    def test_monkey_untrained_floors_at_quarter(self):
        ch = _make_char()
        v = _make_char(2)
        set_stance(ch, STANCE_CURRENT, STANCE_MONKEY)
        set_stance(ch, STANCE_MONKEY, 10)
        # dam *= (10+1)//200 = 0 -> floored to 25%
        assert dambonus(ch, v, 40, STANCE_MONKEY) == 10

    def test_monkey_victim_counters_defense(self):
        ch = _make_char()
        v = _make_char(2)
        set_stance(ch, STANCE_CURRENT, STANCE_MONKEY)
        set_stance(ch, STANCE_MONKEY, 199)
        set_stance(v, STANCE_CURRENT, STANCE_CRAB)
        set_stance(v, STANCE_CRAB, 200)
        # attacker is monkey (can_counter) -> victim's crab defense skipped
        assert dambonus(ch, v, 40, STANCE_MONKEY) == 40


class TestFightState:
    def test_set_fighting_autodrops(self):
        ch = _make_char()
        v = _make_char(2, npc=True)
        set_stance(ch, STANCE_AUTODROP, STANCE_VIPER)
        set_stance(ch, STANCE_CURRENT, STANCE_NONE)
        set_fighting(ch, v)
        assert get_stance(ch, STANCE_CURRENT) == STANCE_VIPER

    def test_stop_fighting_resets_stance(self):
        ch = _make_char()
        v = _make_char(2, npc=True)
        ch["fighting"] = 2
        set_stance(ch, STANCE_CURRENT, STANCE_VIPER)
        stop_fighting(ch)
        assert get_stance(ch, STANCE_CURRENT) == STANCE_NONE

    def test_special_move_stuns(self):
        ch = _make_char()
        v = _make_char(2, npc=True)
        ch["fighting"] = 2
        v["fighting"] = 1
        special_move(ch, v)
        assert v["pos"] == "stunned"
        assert v["fighting"] is None
        assert ch["fighting"] is None   # stop_fighting(victim, both=True)


class TestMultiHitStances:
    def _fix_rolls(self, monkeypatch, rolls):
        seq = list(rolls)
        monkeypatch.setattr(combat, "randint", lambda a, b: seq.pop(0) if seq else b)

    def test_special_move_trigger(self, monkeypatch):
        ch = _make_char()
        v = _make_char(2, npc=True)
        ch["fighting"] = 2
        v["fighting"] = 1
        set_stance(ch, STANCE_CURRENT, STANCE_VIPER)
        set_stance(ch, STANCE_VIPER, 200)
        hits = []
        monkeypatch.setattr(combat, "one_hit", lambda *a, **k: hits.append(1))
        # roll sequence: special-move roll == 50 triggers immediately
        self._fix_rolls(monkeypatch, [50])
        combat.multi_hit(ch, v)
        assert v["pos"] == "stunned"
        assert hits == [1]   # only the primary hit before the special

    def test_viper_extra_hit(self, monkeypatch):
        ch = _make_char()
        v = _make_char(2, npc=True)
        ch["fighting"] = 2
        v["fighting"] = 1
        set_stance(ch, STANCE_CURRENT, STANCE_VIPER)
        set_stance(ch, STANCE_VIPER, 150)
        hits = []
        monkeypatch.setattr(combat, "one_hit", lambda *a, **k: hits.append(1))
        monkeypatch.setattr(combat, "_try_special_move", lambda *a: 0)
        # rolls: special-move roll skipped (stance < 200); second attack
        # (100, no), third attack (100, no),
        # viper extra ((150+1)//2 = 75; 74 < 75 yes)
        self._fix_rolls(monkeypatch, [100, 100, 74])
        combat.multi_hit(ch, v)
        assert len(hits) == 2   # primary + viper extra

    def test_no_extra_hit_out_of_stance(self, monkeypatch):
        ch = _make_char()
        v = _make_char(2, npc=True)
        ch["fighting"] = 2
        v["fighting"] = 1
        hits = []
        monkeypatch.setattr(combat, "one_hit", lambda *a, **k: hits.append(1))
        monkeypatch.setattr(combat, "_try_special_move", lambda *a: 0)
        self._fix_rolls(monkeypatch, [100, 100, 1])
        combat.multi_hit(ch, v)
        assert len(hits) == 1


class TestPetAssist:
    def test_charmed_pet_assists_master(self, monkeypatch):
        player = _make_char()
        target = _make_char(2, npc=True)
        pet = _make_char(3, npc=True)
        pet["affected_by"]["charm"] = True
        pet["master"] = 1
        pet["leader"] = 1
        player["fighting"] = 2
        target["fighting"] = 1
        hits = []
        monkeypatch.setattr(combat, "multi_hit", lambda ch, v, dt=None: hits.append((ch["id"], v["id"])))
        monkeypatch.setattr(combat, "is_safe", lambda ch, v: False)
        check_assist(player, target)
        assert (3, 2) in hits

    def test_uncharmed_mob_does_not_assist(self, monkeypatch):
        player = _make_char()
        target = _make_char(2, npc=True)
        bystander = _make_char(3, npc=True)
        player["fighting"] = 2
        target["fighting"] = 1
        hits = []
        monkeypatch.setattr(combat, "multi_hit", lambda ch, v, dt=None: hits.append((ch["id"], v["id"])))
        monkeypatch.setattr(combat, "is_safe", lambda ch, v: False)
        check_assist(player, target)
        assert hits == []


class TestDamageFollower:
    def test_attacking_own_follower_breaks_link(self, monkeypatch):
        from config import TYPE_HIT, DAM_BASH
        player = _make_char()
        pet = _make_char(2, npc=True, hit=50, max_hit=50)
        pet["affected_by"]["charm"] = True
        pet["master"] = 1
        player["pet"] = 2
        monkeypatch.setattr(combat, "is_safe", lambda ch, v: False)
        monkeypatch.setattr(combat, "check_dodge", lambda ch, v: False)
        monkeypatch.setattr(combat, "check_parry", lambda ch, v: False)
        monkeypatch.setattr(combat, "check_shield_block", lambda ch, v: False)
        combat.damage(player, pet, 1, TYPE_HIT, DAM_BASH, show=False)
        assert pet["master"] is None
        assert player["pet"] is None


class TestNewPlayerDefaults:
    def test_create_char_starts_out_of_stance(self):
        from player import create_char
        ch = create_char()
        assert get_stance(ch, STANCE_CURRENT) == STANCE_NONE
        # autodrop left at NORMAL -> first combat announces the stance system
        assert get_stance(ch, STANCE_AUTODROP) == STANCE_NORMAL

    def test_first_combat_announces_stance(self, capsys):
        from player import create_char
        ch = create_char()
        ch["id"] = 1
        world.chars[1] = ch
        v = _make_char(2, npc=True)
        set_fighting(ch, v)
        out = capsys.readouterr().out
        assert "autodrop into the normal stance" in out
