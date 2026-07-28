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
from skills_table import (GSN_FAST_HEALING, GSN_MEDITATION, GSN_PLAGUE,
                          GSN_POISON)
from config import REGEN_SECS, TICK_SECS


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
    """PC at full pools so unrelated regen pools remain clamp no-ops."""
    p = _char_base()
    p.update({"id": 1, "room": 3001, "level": 10, "learned": {},
              "hit": 100, "max_hit": 100,
              "mana": 100, "max_mana": 100,
              "move": 100, "max_move": 100})
    return p


def _regen_cycle(player, room, improve=False):
    """Run enough granular pulses to equal one world tick."""
    for _ in range(TICK_SECS // REGEN_SECS):
        player_mod.regen_update(player, room, improve)


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
        monkeypatch.setattr(player_mod, "get_skill",
                            lambda e, sn, is_mob=False:
                            skill if sn == GSN_FAST_HEALING else 0)
        p = _full_player()
        p.update({"pos": "standing", "hit": 1, "max_hit": 100})
        room = {"heal_rate": 100, "mana_rate": 100}
        _regen_cycle(p, room)
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
        monkeypatch.setattr(player_mod, "get_skill",
                            lambda e, sn, is_mob=False: 0)
        room = {"heal_rate": 100, "mana_rate": 100}

        def gain(caster):
            monkeypatch.setattr(player_mod, "has_spells", lambda p: caster)
            p = _full_player()
            p.update({"pos": "standing", "mana": 1, "max_mana": 100})
            _regen_cycle(p, room)
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


# -- Granular player cadence ---------------------------------------------------

class TestGranularPlayerRegen:
    def test_pool_above_reduced_maximum_is_clamped(self):
        p = _full_player()
        p["hit"] = 101

        assert player_mod.regen_update(
            p, {"heal_rate": 100, "mana_rate": 100})
        assert p["hit"] == 100

    def test_small_gain_carries_without_rounding_loss(self, monkeypatch):
        monkeypatch.setattr(player_mod, "randint", lambda a, b: 100)
        monkeypatch.setattr(player_mod, "get_skill", lambda *args: 0)
        monkeypatch.setattr(player_mod, "has_spells", lambda player: False)
        p = _full_player()
        p.update({"pos": "standing", "mana": 1, "max_mana": 100})
        room = {"heal_rate": 100, "mana_rate": 100}
        values = []

        for _ in range(TICK_SECS // REGEN_SECS):
            player_mod.regen_update(p, room)
            values.append(p["mana"])

        # Full-tick mana gain is 2; carry releases it across six pulses.
        assert values == [1, 1, 2, 2, 2, 3]

    def test_improvement_check_uses_explicit_world_tick_gate(self, monkeypatch):
        calls = []
        monkeypatch.setattr(player_mod, "randint", lambda a, b: 1)
        monkeypatch.setattr(player_mod, "get_skill", lambda *args: 100)
        monkeypatch.setattr(player_mod, "check_improve",
                            lambda player, skill, success, mult:
                            calls.append(skill))
        p = _full_player()
        p.update({"pos": "standing", "hit": 1, "mana": 1})
        room = {"heal_rate": 100, "mana_rate": 100}

        player_mod.regen_update(p, room, False)
        assert calls == []
        player_mod.regen_update(p, room, True)
        assert calls == [GSN_FAST_HEALING, GSN_MEDITATION]

    def test_scheduler_reports_only_visible_regen(self, isolate, monkeypatch):
        import update
        player = _full_player()
        player["hit"] = 1
        world.chars[1] = player
        monkeypatch.setattr(world, "maybe_evict", lambda _player: None)
        monkeypatch.setattr(update, "mark_explored", lambda _player: None)
        for name in ("_pulse_area", "_pulse_music", "_pulse_mobile",
                     "_pulse_violence", "_pulse_tick"):
            monkeypatch.setattr(update, name, 1000)
        monkeypatch.setattr(update, "_pulse_regen", 0)
        monkeypatch.setattr(update, "_regen_phase", 0)

        fired = update.update_handler()

        assert fired == update.UPD_REGEN


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


# -- Player disease tick + bleed-out (cf. char_update, update.c:670-746) ------

class TestDiseaseAndBleed:
    def _patch(self, monkeypatch, roll=0):
        """No-op the output layer, record damage() calls, pin the RNG."""
        import combat
        import handler
        calls = []
        monkeypatch.setattr(
            combat, "damage",
            lambda ch, v, dam, sn, dt, show: calls.append((dam, sn, dt)))
        monkeypatch.setattr(handler, "act", lambda *a, **k: None)
        monkeypatch.setattr(handler, "chprintln", lambda *a, **k: None)
        monkeypatch.setattr(player_mod, "randint", lambda a, b: roll)
        return calls

    def _tick(self, p):
        player_mod.tick_update(None, p,
                               {"heal_rate": 100, "mana_rate": 100})

    def test_incap_blocks_regen_and_bleeds(self, isolate, monkeypatch):
        calls = self._patch(monkeypatch, roll=0)  # number_range(0,1)==0 hits
        p = _full_player()
        p.update({"pos": "incap", "hit": 1})
        self._tick(p)
        assert p["hit"] == 1  # gate: no regen below stunned
        from config import TYPE_UNDEFINED, DAM_NONE
        assert calls == [(1, TYPE_UNDEFINED, DAM_NONE)]

    def test_incap_coin_flip_miss(self, isolate, monkeypatch):
        calls = self._patch(monkeypatch, roll=1)  # number_range(0,1)==1 skips
        p = _full_player()
        p.update({"pos": "incap", "hit": 1})
        self._tick(p)
        assert calls == []

    def test_mortal_bleeds_every_tick(self, isolate, monkeypatch):
        calls = self._patch(monkeypatch, roll=1)  # mortal ignores the flip
        p = _full_player()
        p.update({"pos": "mortal", "hit": 1})
        self._tick(p)
        from config import TYPE_UNDEFINED, DAM_NONE
        assert calls == [(1, TYPE_UNDEFINED, DAM_NONE)]

    def test_stunned_player_stands_up(self, isolate, monkeypatch):
        # update.c:566-567: stunned + hit > 0 -> update_pos stands them up
        self._patch(monkeypatch)
        p = _full_player()
        p.update({"pos": "stunned", "hit": 50})
        player_mod.regen_update(
            p, {"heal_rate": 100, "mana_rate": 100})
        assert p["pos"] == "standing"

    def test_poison_tick_damage(self, isolate, monkeypatch):
        calls = self._patch(monkeypatch)
        p = _full_player()
        p.update({"pos": "standing",
                  "affected_by": {"poison": True},
                  "affect_list": [{"type": GSN_POISON, "level": 20,
                                   "duration": 5, "location": "none",
                                   "modifier": 0, "bitvector": "poison"}]})
        self._tick(p)
        from config import DAM_POISON
        assert (20 // 10 + 1, GSN_POISON, DAM_POISON) in calls

    def test_poison_slowed_skips(self, isolate, monkeypatch):
        calls = self._patch(monkeypatch)
        p = _full_player()
        p.update({"pos": "standing",
                  "affected_by": {"poison": True, "slow": True},
                  "affect_list": [{"type": GSN_POISON, "level": 20,
                                   "duration": 5, "location": "none",
                                   "modifier": 0, "bitvector": "poison"}]})
        self._tick(p)
        assert calls == []

    def test_plague_level_one_is_inert(self, isolate, monkeypatch):
        # af.level == 1: messages only, no drain, no damage (update.c:694-695)
        calls = self._patch(monkeypatch)
        p = _full_player()
        p.update({"pos": "standing",
                  "affected_by": {"plague": True},
                  "affect_list": [{"type": GSN_PLAGUE, "level": 1,
                                   "duration": 5, "location": "str",
                                   "modifier": -5, "bitvector": "plague"}]})
        self._tick(p)
        assert calls == []
        assert p["mana"] == 100 and p["move"] == 100

    def test_plague_damages_and_drains(self, isolate, monkeypatch):
        # dam = min(level, af.level//5 + 1) = min(10, 6//5+1) = 2
        calls = self._patch(monkeypatch)
        p = _full_player()
        # room vnum outside every area: keeps the contagion room lookup from
        # lazy-loading midgaard (vnum 3001) inside the test
        p.update({"pos": "standing", "room": 99999,
                  "affected_by": {"plague": True},
                  "affect_list": [{"type": GSN_PLAGUE, "level": 6,
                                   "duration": 5, "location": "str",
                                   "modifier": -5, "bitvector": "plague"}]})
        self._tick(p)
        from config import DAM_DISEASE
        assert (2, GSN_PLAGUE, DAM_DISEASE) in calls
        assert p["mana"] == 98 and p["move"] == 98
