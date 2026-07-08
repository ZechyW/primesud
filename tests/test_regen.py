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
from handler import _char_base
from skills_table import GSN_FAST_HEALING


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
        # roll == skill% is a MISS (strict <), roll below skill% hits.
        miss = self._hp_gain(monkeypatch, roll=50, skill=50)
        hit = self._hp_gain(monkeypatch, roll=49, skill=50)
        assert hit > miss

    def test_fast_healing_bonus_math(self, monkeypatch):
        # base (standing): max(3, con-3+5) + (100-10), /4. With roll<skill the
        # bonus roll*gain//100 applies BEFORE the position divisor.
        no_skill = self._hp_gain(monkeypatch, roll=49, skill=0)
        with_skill = self._hp_gain(monkeypatch, roll=49, skill=50)
        assert with_skill > no_skill

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

        assert gain(True) == gain(False) * 2

    def test_real_has_spells_warrior_vs_mage(self):
        import classes
        from player import create_char
        warrior = create_char(classes.CLASS_WARRIOR, "Human")
        mage = create_char(classes.CLASS_MAGE, "Human")
        assert classes.has_spells(warrior) is False
        assert classes.has_spells(mage) is True
