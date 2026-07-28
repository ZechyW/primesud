"""Automap rendering tests: unloaded-area cells stay visible.

Maps are built from the resident room dict only (world.ROOM_DEFS._data), so
an exit into an unloaded area has no dest room: it must draw its corridor and
a '%' cell on both map forms. The full map fills *empty* cells with '{D.'
(cf. 1stMud show_map fSmall=false); occupied-but-uncoloured cells must not be
swallowed by that fill.
"""

from automap import build_compact_lines, build_full_lines


_ROOMS = {100: {"name": "Border", "exits": {"n": 101}, "sector": "city"}}
_PLAYER = {"room": 100, "affected_by": {}}


def _cells(lines):
    return "\n".join(lines)


def test_full_map_shows_unloaded_room_and_corridor():
    text = _cells(build_full_lines(_PLAYER, _ROOMS))
    # silver, not the {D fill colour (see _room_color)
    assert "{w%" in text, "unloaded-area room cell must render '%'"
    assert "{w|" in text, "corridor into unloaded area must render '|'"


def test_full_map_shows_uncoloured_sector_char(monkeypatch):
    import automap
    # room_is_dark consults world state; irrelevant here
    monkeypatch.setattr(automap, "room_is_dark", lambda vnum: False)
    rooms = {100: {"name": "Deep", "exits": {"n": 101}, "sector": "city"},
             101: {"name": "Jungle", "exits": {}, "sector": "jungle"}}
    text = _cells(build_full_lines(_PLAYER, rooms))
    # jungle has no SECTOR_COLORS entry: '?' must still render (cf. 1stMud,
    # where only pRoom-less cells become '.')
    assert "{D?" in text


def test_compact_map_shows_unloaded_room():
    text = _cells(build_compact_lines(_PLAYER, _ROOMS))
    assert "{w%" in text
