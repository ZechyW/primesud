"""spell_identify weapon-type wording (cf. 1stMud magic.c:3241-3275).

1stMud switches on the parsed weapon class: WEAPON_SPEAR prints
"spear/staff.", WEAPON_MACE prints "mace/club.", and unknown area words were
already degraded to exotic at load (weapon_class fallback, handler.c).
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

from handler import _char_base
import magic
from world import ITEM_DEFS

VNUM = 9730


def _identify_lines(monkeypatch, weapon_type):
    ITEM_DEFS._data[VNUM] = {
        "keywords": "test weapon", "short_descr": "a test weapon",
        "type": "weapon", "weapon_type": weapon_type, "dam_type": "pound",
        "dice": (1, 6, 0), "level": 5, "wear_flags": {"take": True, "wield": True},
    }
    lines = []
    monkeypatch.setattr(magic, "chprintln", lambda ch, s="": lines.append(s))
    try:
        magic.spell_identify(0, 10, _char_base(), {"vnum": VNUM}, None)
    finally:
        del ITEM_DEFS._data[VNUM]
    return lines


@pytest.mark.parametrize("word,shown", [
    ("staff", "spear/staff"),   # WEAPON_SPEAR class
    ("mace", "mace/club"),      # WEAPON_MACE class
    ("sword", "sword"),
    ("spear", "exotic"),        # not a weapon_table word -> loader exotic fallback
])
def test_weapon_type_wording(monkeypatch, word, shown):
    lines = _identify_lines(monkeypatch, word)
    assert ("Weapon type is " + shown + ".") in lines
