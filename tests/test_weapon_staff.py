"""Staff weapon_type must resolve to spear skill (cf. 1stMud const.c weapon_table).

1stMud maps "staff" -> WEAPON_SPEAR / gsn_spear; "staff" is the only data/UI
word for the class (the skill itself is named 'spear', skills.dat sn 105).
WEAPON_GSN_MAP mirrors weapon_table exactly, so the word "spear" is NOT a
key: 1stMud's loader (weapon_class, handler.c) prefix-matches weapon_table
names only and falls back to WEAPON_EXOTIC (sn -1, 3*level skill%) for
anything else.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

from skills_table import WEAPON_GSN_MAP, GSN_SPEAR


def test_staff_maps_to_spear():
    assert WEAPON_GSN_MAP.get('staff') == GSN_SPEAR


def test_staff_not_minus_one():
    """Without the alias, .get('staff', -1) returns -1 (unknown weapon)."""
    assert WEAPON_GSN_MAP.get('staff', -1) != -1


def test_spear_word_falls_back_to_exotic():
    """Area word 'spear' is not in weapon_table; 1stMud loads it as exotic."""
    assert WEAPON_GSN_MAP.get('spear', -1) == -1
