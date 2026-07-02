"""Regression tests from the combat.py fidelity audit against 1stMud fight.c."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "primesud.hpappdir")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

from combat import xp_compute


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
