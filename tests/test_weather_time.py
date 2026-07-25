"""Weather + time command tests (darkness Phase D).

Weather index/report helpers and do_time output format.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import world  # noqa: F401  (ensures src on path / shim init)
from game_time import (time_info, _weather_index, _trunc_div,
                       weather_report_line, ordinal_string)


# ---------------------------------------------------------------------------
# Weather helpers
# ---------------------------------------------------------------------------

class TestWeatherHelpers:
    def test_trunc_div_toward_zero(self):
        assert _trunc_div(-1, 10) == 0      # C truncation, not floor (-1)
        assert _trunc_div(-25, 10) == -2
        assert _trunc_div(25, 10) == 2

    def test_index_bounds(self):
        assert _weather_index(-30) == 0
        assert _weather_index(30) == 5
        assert _weather_index(0) == 2       # (0 + 29)/10 -> 2

    def test_report_line_low_precip(self):
        # precip index < 3 -> windtemp combo + precip single
        line = weather_report_line({"temp": 0, "precip": 0, "wind": 0})
        assert line == ("A lively breeze cools the area"
                        " and thick, grey clouds mask the sun.")

    def test_report_line_high_precip(self):
        # precip index >= 3 -> preciptemp combo + wind single
        line = weather_report_line({"temp": 30, "precip": 30, "wind": 30})
        assert line == ("A torrent of rain soaks the heated earth"
                        " and howling winds whip the air into a frenzy.")


# ---------------------------------------------------------------------------
# Packed per-area state save line
# ---------------------------------------------------------------------------

class TestWeatherPersistence:
    def test_packed_roundtrip(self, tmp_path, monkeypatch):
        import game_state
        from player import create_char
        monkeypatch.setattr(game_state, "SAVE_FILE", str(tmp_path / "t.sav"))
        old_areas, old_chars = world.areas, dict(world.chars)
        wdict = {"temp": -12, "temp_vector": 3, "precip": 5,
                 "precip_vector": -2, "wind": 30, "wind_vector": 1}
        try:
            player = create_char()
            player["name"] = "Tester"
            player["room"] = 3001
            player["_macros"] = {}
            world.chars.clear()
            world.chars[1] = player
            world.areas = [{"tag": "midgaard", "age": 3,
                            "weather": dict(wdict)}]
            game_state._serialize_world()
            with open(str(tmp_path / "t.sav")) as f:
                payload = f.read()
            assert "a.midgaard=3|-12|3|5|-2|30|1" in payload
            assert "a.midgaard.age=" not in payload
            assert "a.midgaard.w=" not in payload

            world.areas[0]["weather"] = {}
            assert game_state.load_world() == "file"
            assert world.areas[0]["weather"] == wdict
        finally:
            world.areas = old_areas
            world.chars.clear()
            world.chars.update(old_chars)


# ---------------------------------------------------------------------------
# do_time output format
# ---------------------------------------------------------------------------

class TestDoTime:
    @pytest.fixture
    def out(self, monkeypatch):
        import info
        lines = []
        monkeypatch.setattr(info, "chprintln",
                            lambda ch, s="": lines.append(s))
        return lines

    def _at(self, hour, day=0, month=0, year=0):
        for k, v in (("hour", hour), ("day", day),
                     ("month", month), ("year", year)):
            time_info[k] = v

    def test_calendar_and_played(self, out):
        import info
        old = dict(time_info)
        try:
            self._at(8)
            info.do_time({"played": 7749}, [])
        finally:
            time_info.update(old)
        assert out[0] == ("It is 8 o'clock am, Day of the Bull,"
                          " first the Month of Winter, year 0.")
        # 7749s -> 2h; (7749//36)%100 = 15 -> "2.15"
        assert out[1] == "You have played approximately 2.15 hours."

    def test_midnight_and_noon(self, out):
        import info
        old = dict(time_info)
        try:
            self._at(0)
            info.do_time({"played": 0}, [])
            self._at(12)
            info.do_time({"played": 0}, [])
        finally:
            time_info.update(old)
        assert out[0].startswith("It is 12 o'clock am,")   # midnight
        assert out[2].startswith("It is 12 o'clock pm,")   # noon

    def test_ordinal_no_special_teens(self):
        # 1stMud quirk preserved: 11th day renders "11st"
        assert ordinal_string(11) == "11st"
        assert ordinal_string(1) == "first"
        assert ordinal_string(21) == "21st"
