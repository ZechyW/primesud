"""Light-fuel burnout tests (darkness Phase C).

create_object fuel seeding, char_update burnout (flicker / extract / infinite),
and light_hours save round-trip.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import world
from world import ITEM_DEFS


# ---------------------------------------------------------------------------
# create_object seeds mutable fuel only for positive light_hours (decision 4)
# ---------------------------------------------------------------------------

class TestFuelSeed:
    def _tpl(self, vnum, lh):
        d = {"type": "light", "keywords": "torch", "short_descr": "a torch"}
        if lh is not None:
            d["light_hours"] = lh
        ITEM_DEFS._data[vnum] = d
        return vnum

    def test_positive_fuel_seeded(self, fresh_world):
        from item import create_object
        v = self._tpl(700, 50)
        assert create_object(v).get("light_hours") == 50

    def test_infinite_not_seeded(self, fresh_world):
        # negative = infinite: read from template via fallback, no instance copy
        from item import create_object
        v = self._tpl(701, -1)
        assert "light_hours" not in create_object(v)

    def test_dead_not_seeded(self, fresh_world):
        from item import create_object
        v = self._tpl(702, 0)
        assert "light_hours" not in create_object(v)

    def test_absent_not_seeded(self, fresh_world):
        from item import create_object
        v = self._tpl(703, None)
        assert "light_hours" not in create_object(v)


# ---------------------------------------------------------------------------
# Burnout in the tick handler (cf. 1stMud char_update in update.c:597-613)
# ---------------------------------------------------------------------------

class TestBurnout:
    def _setup(self, monkeypatch, fuel, vnum=710):
        import handler
        import player
        ITEM_DEFS._data[vnum] = {"type": "light", "keywords": "lantern",
                                 "short_descr": "a lantern"}
        light = {"vnum": vnum}
        if fuel is not None:
            light["light_hours"] = fuel
        p = {"id": 1, "name": "T", "room": 1, "inv": [],
             "equip": {"light": light}, "affected_by": {}}
        msgs = []
        monkeypatch.setattr(handler, "act",
                            lambda m, ch, o, v, t: msgs.append(m))
        player._light_burnout(None, p)
        return p, light, msgs

    def test_flicker_at_five(self, fresh_world, monkeypatch):
        p, light, msgs = self._setup(monkeypatch, 6)
        assert light["light_hours"] == 5
        assert msgs == ["$p flickers."]
        assert p["equip"]["light"] is light  # still worn

    def test_no_flicker_above_five(self, fresh_world, monkeypatch):
        p, light, msgs = self._setup(monkeypatch, 7)
        assert light["light_hours"] == 6
        assert msgs == []

    def test_burnout_extracts(self, fresh_world, monkeypatch):
        p, light, msgs = self._setup(monkeypatch, 1)
        assert light["light_hours"] == 0
        # both 1stMud messages, TO_ROOM then TO_CHAR
        assert msgs == ["$p goes out.", "$p flickers and goes out."]
        assert p["equip"]["light"] is None          # unequipped
        assert light not in p["inv"]                # extracted, not returned

    def test_infinite_never_decrements(self, fresh_world, monkeypatch):
        # instance carries no light_hours (infinite / absent fuel)
        p, light, msgs = self._setup(monkeypatch, None)
        assert "light_hours" not in light
        assert msgs == []
        assert p["equip"]["light"] is light

    def test_negative_never_decrements(self, fresh_world, monkeypatch):
        p, light, msgs = self._setup(monkeypatch, -5)
        assert light["light_hours"] == -5
        assert msgs == []


# ---------------------------------------------------------------------------
# light_hours save round-trip (only-when-present)
# ---------------------------------------------------------------------------

class TestFuelSaveRoundTrip:
    def test_present_survives(self):
        from item import serialize_item_token, parse_item_token
        tok = serialize_item_token({"vnum": 3716, "light_hours": 42})
        assert "lh:42" in tok
        assert parse_item_token(tok)["light_hours"] == 42

    def test_absent_omitted(self):
        from item import serialize_item_token, parse_item_token
        tok = serialize_item_token({"vnum": 3716})
        assert "lh:" not in tok
        assert "light_hours" not in parse_item_token(tok)
