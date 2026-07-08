"""Regen fidelity tests: player gain modifiers + mob hp regen (cf. 1stMud
hit_gain/mana_gain/char_update in update.c)."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import player as player_mod
import skill_utils
import world
from handler import _char_base
from world import ROOM_DEFS
from skills_table import GSN_FAST_HEALING


@pytest.fixture
def isolate():
    """Snapshot/restore world.chars + ROOM_DEFS for a test room."""
    old_chars = dict(world.chars)
    old_rooms = dict(ROOM_DEFS._data)
    world.chars.clear()
    ROOM_DEFS._data[3001] = {"name": "T", "heal_rate": 100, "mana_rate": 100,
                             "area": "test"}
    yield
    world.chars.clear()
    world.chars.update(old_chars)
    ROOM_DEFS._data.clear()
    ROOM_DEFS._data.update(old_rooms)


def _full_player():
    """PC at full pools so tick_update's player half is a clamp no-op."""
    p = _char_base()
    p.update({"id": 1, "room": 3001, "level": 10, "learned": {},
              "hit": 100, "max_hit": 100,
              "mana": 100, "max_mana": 100,
              "move": 100, "max_move": 100})
    return p


# -- _regen_tail: affect divisors + room rate ---------------------------------

class TestRegenTail:
    def test_poison_then_haste_stack(self):
        # 100 -> poison /4 = 25 -> haste /2 = 12
        c = {"affected_by": {"poison": True, "haste": True}}
        assert player_mod._regen_tail(100, c, 100) == 12

    def test_plague(self):
        c = {"affected_by": {"plague": True}}
        assert player_mod._regen_tail(100, c, 100) == 12  # 100//8

    def test_slow_same_as_haste(self):
        c = {"affected_by": {"slow": True}}
        assert player_mod._regen_tail(100, c, 100) == 50

    def test_heal_rate_multiplies(self):
        c = {"affected_by": {}}
        assert player_mod._regen_tail(100, c, 110) == 110
        assert player_mod._regen_tail(100, c, 100) == 100


# -- Player: fast-healing / meditation / has_spells ---------------------------

class TestPlayerGains:
    def _hp_gain(self, monkeypatch, roll, skill):
        monkeypatch.setattr(player_mod, "randint", lambda a, b: roll)
        monkeypatch.setattr(skill_utils, "get_skill",
                            lambda e, sn, is_mob=False:
                            skill if sn == GSN_FAST_HEALING else 0)
        p = _full_player()
        p.update({"pos": "standing", "hit": 1, "max_hit": 100})
        room = {"heal_rate": 100, "mana_rate": 100}
        player_mod.tick_update(None, p, room)
        return p["hit"] - 1

    def test_fast_healing_roll_boundary(self, monkeypatch):
        # base 105 = max(3, con13-3+5) + (100-10); standing -> //4.
        # roll == skill% is a MISS (strict <): 105//4 = 26.
        # roll < skill%: bonus 49*105//100 before //4 -> (105+51)//4 = 39.
        assert self._hp_gain(monkeypatch, roll=50, skill=50) == 26
        assert self._hp_gain(monkeypatch, roll=49, skill=50) == 39

    def test_fast_healing_bonus_math(self, monkeypatch):
        # Bonus roll*gain//100 applies BEFORE the position divisor.
        assert self._hp_gain(monkeypatch, roll=49, skill=0) == 26   # 105//4
        assert self._hp_gain(monkeypatch, roll=49, skill=50) == 39  # (105+51)//4

    def test_has_spells_halves_mana(self, monkeypatch):
        # roll high -> no meditation bonus; isolate the has_spells branch.
        monkeypatch.setattr(player_mod, "randint", lambda a, b: 100)
        monkeypatch.setattr(skill_utils, "get_skill",
                            lambda e, sn, is_mob=False: 0)
        room = {"heal_rate": 100, "mana_rate": 100}

        def gain(caster):
            monkeypatch.setattr(player_mod, "has_spells", lambda p: caster)
            p = _full_player()
            p.update({"pos": "standing", "mana": 1, "max_mana": 100})
            player_mod.tick_update(None, p, room)
            return p["mana"] - 1

        # mana base (int13+wis13+level10)//2 = 18; standing -> //4.
        # caster: 18//4 = 4. non-caster: 18//2=9 then //4 = 2.
        assert gain(True) == 4
        assert gain(False) == 2

    def test_real_has_spells_warrior_vs_mage(self):
        import classes
        from player import create_char
        warrior = create_char(classes.CLASS_WARRIOR, "Human")
        mage = create_char(classes.CLASS_MAGE, "Human")
        assert classes.has_spells(warrior) is False
        assert classes.has_spells(mage) is True


# -- Mob hp regen -------------------------------------------------------------

class TestMobRegen:
    def _mob(self, **kw):
        m = _char_base()
        m.update({"is_npc": True, "id": 2, "room": 3001, "level": 10,
                  "hit": 1, "max_hit": 100, "pos": "resting"})
        m.update(kw)
        world.chars[2] = m
        return m

    def _tick(self):
        player_mod.tick_update(None, _full_player(),
                               {"heal_rate": 100, "mana_rate": 100})

    def test_resting_base(self, isolate):
        m = self._mob(pos="resting")  # gain = 5 + level = 15, unchanged
        self._tick()
        assert m["hit"] == 1 + 15

    def test_position_ordering(self, isolate):
        gains = {}
        for pos in ("sleeping", "resting", "fighting", "standing"):
            m = self._mob(pos=pos)
            self._tick()
            gains[pos] = m["hit"] - 1
        # sleeping 3*15//2=22, resting 15, standing(other) //2=7, fighting //3=5
        assert gains["sleeping"] == 22
        assert gains["resting"] == 15
        assert gains["standing"] == 7
        assert gains["fighting"] == 5

    def test_regeneration_doubles(self, isolate):
        m = self._mob(pos="resting", affected_by={"regeneration": True})
        self._tick()
        assert m["hit"] == 1 + 30  # (5+10)*2

    def test_full_hp_early_out(self, isolate):
        m = self._mob(pos="resting", hit=100, max_hit=100)
        self._tick()
        assert m["hit"] == 100

    def test_stunned_gate_blocks_incap(self, isolate):
        # position < POS_STUNNED (incap/mortal/dead) does not regen
        m = self._mob(pos="incap")
        self._tick()
        assert m["hit"] == 1

    def test_stunned_regens(self, isolate):
        m = self._mob(pos="stunned")  # other -> gain //2
        self._tick()
        assert m["hit"] == 1 + 7

    def test_heal_rate_scales(self, isolate):
        ROOM_DEFS._data[3001]["heal_rate"] = 200
        m = self._mob(pos="resting")
        self._tick()
        assert m["hit"] == 1 + 30  # 15 * 200 // 100

    def test_poison_divides(self, isolate):
        m = self._mob(pos="resting", affected_by={"poison": True})
        self._tick()
        assert m["hit"] == 1 + 3  # 15 // 4

    def test_clamp_to_max_hit(self, isolate):
        m = self._mob(pos="sleeping", hit=95, max_hit=100)
        self._tick()
        assert m["hit"] == 100
