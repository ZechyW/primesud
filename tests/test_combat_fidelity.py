"""Regression tests from the combat.py fidelity audit against 1stMud fight.c."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import combat
import world
from combat import _advance_target, group_gain, xp_compute
from handler import _char_base


class TestXpComputeAlignmentDrift:
    """Alignment drift must match C truncation-toward-zero semantics."""

    def test_negative_alignment_drift_truncates_toward_zero(self):
        # gch align -300, victim align 0 -> else branch (|diff| <= 500).
        # C: change = ((-300*83)/500)*10/10 = -49 (trunc); align = -300-(-49) = -251
        # Python floor division would give -50 -> -250.
        gch = _char_base()
        gch.update({"level": 10, "alignment": -300})
        victim = _char_base()
        victim.update({"level": 10, "alignment": 0, "act_flags": {}})
        xp_compute(gch, victim, 10)
        assert gch["alignment"] == -251

    def test_positive_alignment_drift_unchanged(self):
        # Positive path was already correct: change = (300*83)/500*10/10 = 49
        gch = _char_base()
        gch.update({"level": 10, "alignment": 300})
        victim = _char_base()
        victim.update({"level": 10, "alignment": 0, "act_flags": {}})
        xp_compute(gch, victim, 10)
        assert gch["alignment"] == 251


def test_pet_does_not_dilute_xp_but_charmie_does(monkeypatch):
    player = _char_base()
    player.update({"id": 1, "level": 10, "room": 9001, "pet": 2})
    pet = _char_base()
    pet.update({"id": 2, "is_npc": True, "level": 10, "room": 9001,
                "master": 1, "leader": 1, "act_flags": {"pet": True}})
    charmie = _char_base()
    charmie.update({"id": 3, "is_npc": True, "level": 10, "room": 9001,
                    "master": 1, "leader": 1})
    victim = _char_base()
    victim.update({"id": 4, "is_npc": True, "level": 10, "room": 9001})
    monkeypatch.setattr(world, "chars", {1: player, 2: pet, 3: charmie})
    monkeypatch.setattr(world, "rooms", {9001: {"mobs": [2, 3], "items": []}})

    seen = []
    monkeypatch.setattr(combat, "xp_compute",
                        lambda gch, mob, total_levels: seen.append(total_levels) or 0)
    monkeypatch.setattr(combat, "gain_exp", lambda ch, xp: None)
    monkeypatch.setattr(combat, "quest_kill_check", lambda ch, mob: None)
    monkeypatch.setattr(combat, "gq_kill_check", lambda ch, mob: None)

    group_gain(player, victim)

    assert seen == [15]  # player 10 + charmie 5; pet contributes 0


def test_good_pet_kill_does_not_zap_neutral_owners_anti_good_gear(monkeypatch):
    player = _char_base()
    gear = {"vnum": 42}
    player.update({"id": 1, "level": 10, "room": 9001, "pet": 2,
                   "alignment": 14, "equip": {"body": gear}})
    pet = _char_base()
    pet.update({"id": 2, "is_npc": True, "level": 10, "room": 9001,
                "master": 1, "leader": 1, "alignment": 500,
                "act_flags": {"pet": True}})
    victim = _char_base()
    victim.update({"id": 3, "is_npc": True, "level": 10, "room": 9001})
    monkeypatch.setattr(world, "chars", {1: player, 2: pet})
    monkeypatch.setattr(world, "rooms", {9001: {"mobs": [2], "items": []}})
    monkeypatch.setattr(combat, "xp_compute", lambda gch, mob, levels: 0)
    monkeypatch.setattr(combat, "gain_exp", lambda ch, xp: None)
    monkeypatch.setattr(combat, "quest_kill_check", lambda ch, mob: None)
    monkeypatch.setattr(combat, "gq_kill_check", lambda ch, mob: None)
    monkeypatch.setattr(combat, "chprintln", lambda ch, text: None)
    monkeypatch.setattr(combat, "act", lambda *args: None)
    monkeypatch.setattr(combat, "item_tpl", lambda obj: {})
    monkeypatch.setattr(combat, "item_extra_flags",
                        lambda obj, tpl: {"anti_good": True})

    group_gain(pet, victim)

    assert player["equip"]["body"] is gear
    assert world.rooms[9001]["items"] == []


class TestAdvanceTargetFighterIndex:
    """Post-kill retarget must run full set_fighting: raw_kill's
    stop_fighting(both=True) cleared fighting/pos/stance and removed the
    player from world.FIGHTERS, and the next mob's damage() can't re-engage
    them (set_fighting early-returns on non-None fighting)."""

    def test_retarget_reengages_via_set_fighting(self):
        old_fx = set(world.FIGHTERS)
        try:
            world.FIGHTERS.discard(1)
            # is_npc=True keeps set_fighting's autodrop/first-stance-pick and
            # Swordsman-form branches quiet; _advance_target itself doesn't care.
            player = _char_base()
            player.update({"id": 1, "room": 9001, "fighting": None,
                           "is_npc": True, "pos": "standing"})
            mob2 = _char_base()
            mob2.update({"id": 2, "fighting": 1})
            mobs = {2: mob2}
            rooms = {9001: {"mobs": [2]}}
            _advance_target(player, mobs, rooms)
            assert player["fighting"] == 2
            assert 1 in world.FIGHTERS
            assert player["pos"] == "fighting"
        finally:
            world.FIGHTERS.clear()
            world.FIGHTERS.update(old_fx)
