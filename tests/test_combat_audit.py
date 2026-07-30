"""Regression tests from the combat.py fidelity audit against 1stMud fight.c."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import world
from combat import _advance_target, xp_compute


class TestXpComputeAlignmentDrift:
    """Alignment drift must match C truncation-toward-zero semantics."""

    def test_negative_alignment_drift_truncates_toward_zero(self):
        # gch align -300, victim align 0 -> else branch (|diff| <= 500).
        # C: change = ((-300*83)/500)*10/10 = -49 (trunc); align = -300-(-49) = -251
        # Python floor division would give -50 -> -250.
        gch = {"level": 10, "alignment": -300}
        victim = {"level": 10, "alignment": 0, "act_flags": {}}
        xp_compute(gch, victim, 10)
        assert gch["alignment"] == -251

    def test_positive_alignment_drift_unchanged(self):
        # Positive path was already correct: change = (300*83)/500*10/10 = 49
        gch = {"level": 10, "alignment": 300}
        victim = {"level": 10, "alignment": 0, "act_flags": {}}
        xp_compute(gch, victim, 10)
        assert gch["alignment"] == 251


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
            player = {"id": 1, "room": 9001, "fighting": None,
                      "is_npc": True, "pos": "standing"}
            mobs = {2: {"id": 2, "fighting": 1}}
            rooms = {9001: {"mobs": [2]}}
            _advance_target(player, mobs, rooms)
            assert player["fighting"] == 2
            assert 1 in world.FIGHTERS
            assert player["pos"] == "fighting"
        finally:
            world.FIGHTERS.clear()
            world.FIGHTERS.update(old_fx)
