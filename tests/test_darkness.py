"""Darkness / visibility predicate + gating tests (DARKNESS_PLAN Phases A+B).

Phase A: room_is_dark truth table, the can_see dark/infrared gate,
can_see_obj, and check_blind.
Phase B (below TestCheckBlind): do_look pitch-black gating + red eyes, exits
"Too dark to tell", and aggro shielding.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import world
from world import ROOM_DEFS, MOB_DEFS, ITEM_DEFS
from game_time import time_info, SUN_DARK, SUN_LIGHT, SUN_RISE, SUN_SET


def _room(vnum, sector="field", flags=None):
    ROOM_DEFS._data[vnum] = {"name": "R", "desc": "A dim place.", "exits": {},
                             "sector": sector, "flags": flags or {}}
    world.rooms._data[vnum] = {"mobs": [], "items": []}


def _char(room, **aff):
    return {"room": room, "equip": {"light": None}, "affected_by": dict(aff)}


# ---------------------------------------------------------------------------
# Phase A -- room_is_dark truth table (each sunlight state / sector / flag)
# ---------------------------------------------------------------------------

class TestRoomIsDark:
    def test_sunlight_states_outdoors(self, fresh_world):
        from handler import room_is_dark
        _room(1, sector="field")
        old = time_info["sunlight"]
        try:
            for sun, expected in ((SUN_LIGHT, False), (SUN_RISE, False),
                                  (SUN_SET, True), (SUN_DARK, True)):
                time_info["sunlight"] = sun
                assert room_is_dark(1) is expected, sun
        finally:
            time_info["sunlight"] = old

    def test_inside_and_city_never_dark_at_night(self, fresh_world):
        from handler import room_is_dark
        _room(2, sector="inside")
        _room(3, sector="city")
        old = time_info["sunlight"]
        try:
            time_info["sunlight"] = SUN_DARK
            assert room_is_dark(2) is False
            assert room_is_dark(3) is False
        finally:
            time_info["sunlight"] = old

    def test_dark_flag_beats_sector(self, fresh_world):
        from handler import room_is_dark
        _room(4, sector="city", flags={"dark": True})
        assert room_is_dark(4) is True

    def test_lit_char_overrides_dark_flag(self, fresh_world):
        from handler import room_is_dark
        ITEM_DEFS._data[500] = {"type": "light", "light_hours": -1,
                                "keywords": "torch", "short_descr": "a torch"}
        _room(5, sector="field", flags={"dark": True})
        world.chars[1] = {"room": 5, "equip": {"light": {"vnum": 500}}}
        try:
            assert room_is_dark(5) is False
        finally:
            del world.chars[1]


# ---------------------------------------------------------------------------
# Phase A -- can_see dark / infrared gate
# ---------------------------------------------------------------------------

class TestCanSeeDark:
    def test_dark_room_hides_victim(self, fresh_world):
        from handler import can_see
        _room(1, flags={"dark": True})
        ch = _char(1)
        victim = _char(1)
        assert can_see(ch, victim) is False

    def test_infrared_pierces_dark(self, fresh_world):
        from handler import can_see
        _room(1, flags={"dark": True})
        ch = _char(1, infrared=True)
        victim = _char(1)
        assert can_see(ch, victim) is True

    def test_lit_room_visible(self, fresh_world):
        from handler import can_see
        _room(1, sector="inside")
        assert can_see(_char(1), _char(1)) is True

    def test_blind_beats_everything(self, fresh_world):
        from handler import can_see
        _room(1, sector="inside")
        assert can_see(_char(1, blind=True), _char(1)) is False


# ---------------------------------------------------------------------------
# Phase A -- can_see_obj full port
# ---------------------------------------------------------------------------

class TestCanSeeObj:
    def _item(self, vnum, otype="trash", flags=None, **extra):
        ITEM_DEFS._data[vnum] = dict({"type": otype, "keywords": "thing",
                                      "short_descr": "a thing",
                                      "extra_flags": flags or {}}, **extra)
        return vnum

    def test_vis_death_hidden(self, fresh_world):
        from handler import can_see_obj
        _room(1, sector="inside")
        v = self._item(600, flags={"vis_death": True})
        assert can_see_obj(_char(1), v) is False

    def test_blind_hides_non_potion(self, fresh_world):
        from handler import can_see_obj
        _room(1, sector="inside")
        v = self._item(601)
        assert can_see_obj(_char(1, blind=True), v) is False

    def test_blind_still_sees_potion(self, fresh_world):
        from handler import can_see_obj
        _room(1, sector="inside")
        v = self._item(602, otype="potion")
        assert can_see_obj(_char(1, blind=True), v) is True

    def test_lit_light_visible_in_dark(self, fresh_world):
        from handler import can_see_obj
        _room(1, flags={"dark": True})
        v = self._item(603, otype="light", light_hours=-1)
        assert can_see_obj(_char(1), v) is True

    def test_dead_light_hidden_in_dark(self, fresh_world):
        from handler import can_see_obj
        _room(1, flags={"dark": True})
        v = self._item(604, otype="light", light_hours=0)
        assert can_see_obj(_char(1), v) is False

    def test_invis_needs_detect(self, fresh_world):
        from handler import can_see_obj
        _room(1, sector="inside")
        v = self._item(605, flags={"invis": True})
        assert can_see_obj(_char(1), v) is False
        assert can_see_obj(_char(1, detect_invis=True), v) is True

    def test_glow_visible_in_dark(self, fresh_world):
        from handler import can_see_obj
        _room(1, flags={"dark": True})
        v = self._item(606, flags={"glow": True})
        assert can_see_obj(_char(1), v) is True

    def test_dark_room_hides_plain_item(self, fresh_world):
        from handler import can_see_obj
        _room(1, flags={"dark": True})
        v = self._item(607)
        assert can_see_obj(_char(1), v) is False
        assert can_see_obj(_char(1, dark_vision=True), v) is True

    def test_lit_room_shows_plain_item(self, fresh_world):
        from handler import can_see_obj
        _room(1, sector="inside")
        v = self._item(608)
        assert can_see_obj(_char(1), v) is True


# ---------------------------------------------------------------------------
# Phase A -- check_blind
# ---------------------------------------------------------------------------

class TestCheckBlind:
    def test_blind_prints_and_fails(self, fresh_world, monkeypatch):
        import handler
        lines = []
        monkeypatch.setattr(handler, "chprintln",
                            lambda ch, s="": lines.append(s))
        assert handler.check_blind(_char(1, blind=True)) is False
        assert lines == ["You can't see a thing!"]

    def test_sighted_passes_silently(self, fresh_world, monkeypatch):
        import handler
        lines = []
        monkeypatch.setattr(handler, "chprintln",
                            lambda ch, s="": lines.append(s))
        assert handler.check_blind(_char(1)) is True
        assert lines == []
