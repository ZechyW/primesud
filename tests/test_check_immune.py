"""Tests for check_immune and its wiring into damage() (cf. 1stMud handler.c/fight.c)."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import combat
from combat import check_immune, damage
from config import (
    DAM_NONE, DAM_BASH, DAM_FIRE, DAM_OTHER, DAM_HARM,
    IS_NORMAL, IS_IMMUNE, IS_RESISTANT, IS_VULNERABLE, IMMUNE_NONE,
)
from handler import _char_base
import world


def _victim(**flags):
    ch = _char_base()
    ch["is_npc"] = True
    ch.update(flags)
    return ch


class TestCheckImmune:
    """Pure check_immune behaviour against 1stMud handler.c reference."""

    def test_no_flags_is_normal(self):
        assert check_immune(_victim(), DAM_FIRE) == IS_NORMAL

    def test_dam_none_returns_immune_none(self):
        assert check_immune(_victim(), DAM_NONE) == IMMUNE_NONE

    def test_broad_weapon_covers_physical(self):
        v = _victim(imm_flags={"weapon": True})
        assert check_immune(v, DAM_BASH) == IS_IMMUNE
        assert check_immune(v, DAM_FIRE) == IS_NORMAL

    def test_broad_magic_covers_nonphysical(self):
        v = _victim(res_flags={"magic": True})
        assert check_immune(v, DAM_FIRE) == IS_RESISTANT
        assert check_immune(v, DAM_BASH) == IS_NORMAL

    def test_specific_flag_overrides_broad(self):
        # res magic broadly, but immune to fire specifically
        v = _victim(res_flags={"magic": True}, imm_flags={"fire": True})
        assert check_immune(v, DAM_FIRE) == IS_IMMUNE

    def test_specific_vuln_overrides_broad_immunity(self):
        # 1stMud: pass-2 vuln wins because pass-2 `immune` starts at IMMUNE_NONE
        v = _victim(imm_flags={"magic": True}, vuln_flags={"fire": True})
        assert check_immune(v, DAM_FIRE) == IS_VULNERABLE

    def test_imm_beats_vuln_on_same_flag(self):
        v = _victim(imm_flags={"fire": True}, vuln_flags={"fire": True})
        assert check_immune(v, DAM_FIRE) == IS_IMMUNE

    def test_unmapped_class_falls_back_to_broad(self):
        # DAM_OTHER/DAM_HARM have no specific flag -> broad "magic" default
        v = _victim(vuln_flags={"magic": True})
        assert check_immune(v, DAM_OTHER) == IS_VULNERABLE
        assert check_immune(v, DAM_HARM) == IS_VULNERABLE


class TestDamageScaling:
    """damage() applies immune=0, resistant -dam/3, vulnerable +dam/2."""

    SPELL_DT = 1  # any dt < TYPE_HIT skips dodge/parry

    def _pair(self, **victim_flags):
        atk = _char_base()
        atk["id"] = 1
        atk["room"] = 3001
        vic = _victim(**victim_flags)
        vic["id"] = 2
        vic["room"] = 3001
        vic["hit"] = vic["max_hit"] = 500
        # pre-engaged: is_safe short-circuits, set_fighting skipped
        atk["fighting"] = 2
        vic["fighting"] = 1
        atk["pos"] = vic["pos"] = "fighting"
        world.chars[1] = atk
        world.chars[2] = vic
        return atk, vic

    @pytest.fixture(autouse=True)
    def _deterministic(self, monkeypatch):
        monkeypatch.setattr(combat, "_randomize_damage", lambda dam, roll: dam)
        old_chars = dict(world.chars)
        yield
        world.chars.clear()
        world.chars.update(old_chars)

    def test_normal_takes_full_damage(self):
        atk, vic = self._pair()
        assert damage(atk, vic, 30, self.SPELL_DT, DAM_FIRE, show=False) is True
        assert vic["hit"] == 470

    def test_immune_takes_zero(self):
        atk, vic = self._pair(imm_flags={"fire": True})
        assert damage(atk, vic, 30, self.SPELL_DT, DAM_FIRE, show=False) is False
        assert vic["hit"] == 500

    def test_resistant_takes_two_thirds(self):
        atk, vic = self._pair(res_flags={"fire": True})
        damage(atk, vic, 30, self.SPELL_DT, DAM_FIRE, show=False)
        assert vic["hit"] == 500 - (30 - 30 // 3)

    def test_vulnerable_takes_extra_half(self):
        atk, vic = self._pair(vuln_flags={"fire": True})
        damage(atk, vic, 30, self.SPELL_DT, DAM_FIRE, show=False)
        assert vic["hit"] == 500 - (30 + 30 // 2)
