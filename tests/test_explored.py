"""Explore tracking tests (cf. 1stMud explored.c). [PRIMESUD]"""
import world
import explored
from explored import (encode_rle, decode_rle, roomcount, areacount, arearooms,
                      get_mask, mark_explored, _pct2, _pct0, do_explored,
                      TOP_EXPLORED, _MAX_VNUM)


def _blank_player(room=None):
    return {"room": room}


def _set(player, *vnums):
    m = get_mask(player)
    for v in vnums:
        m[v >> 3] |= 1 << (v & 7)


# -- Percent formatting (integer math, no floats) --------------------------

def test_pct2_edges():
    assert _pct2(0, 100) == "0.00"
    assert _pct2(100, 100) == "100.00"
    assert _pct2(1, 3) == "33.33"      # 33.333.. -> round down
    assert _pct2(2, 3) == "66.67"      # 66.666.. -> round up
    assert _pct2(1, 8) == "12.50"
    assert _pct2(5, 0) == "0.00"       # zero denominator guarded
    assert _pct2(1, 200) == "0.50"     # sub-1% keeps two decimals


def test_pct0_edges():
    assert _pct0(0, 100) == 0
    assert _pct0(1, 1) == 100
    assert _pct0(1, 3) == 33
    assert _pct0(2, 3) == 67           # 66.66 -> 67
    assert _pct0(5, 0) == 0


# -- RLE round-trip --------------------------------------------------------

def _roundtrip(src):
    s = encode_rle(src)
    dst = _blank_player()
    decode_rle(dst, s)
    assert bytes(get_mask(dst)) == bytes(get_mask(src)), s
    return s


def test_rle_empty():
    p = _blank_player()
    get_mask(p)  # all zeros
    s = _roundtrip(p)
    assert s.startswith("0 ") and s.endswith("-1")
    assert roomcount(p) == 0


def test_rle_all_set():
    p = _blank_player()
    m = get_mask(p)
    for i in range(len(m)):
        m[i] = 0xFF
    # Last byte may contain padding beyond highest valid vnum.
    m[-1] &= (1 << ((_MAX_VNUM & 7) + 1)) - 1
    _roundtrip(p)


def test_rle_alternating_runs():
    p = _blank_player()
    _set(p, 1, 2, 3, 50, 51, 9000, 9999)
    _roundtrip(p)
    assert roomcount(p) == 7


# -- roomcount / areacount / arearooms -------------------------------------

def test_areacount_handset():
    p = _blank_player()
    # limbo is vnums 1-99 with 3 rooms; set two in-range + one out-of-range
    _set(p, 1, 2, 3050)
    assert areacount(p, "limbo") == 2
    assert areacount(p, "midgaard") == 1   # 3050 is inside midgaard 3000-3399
    assert arearooms("limbo") == 3
    assert areacount(p, None) == 0
    assert areacount(p, "no_such_tag") == 0
    assert roomcount(p) == 3


def test_top_explored_is_sum():
    assert TOP_EXPLORED == sum(world.AREA_ROOM_COUNTS.values())


# -- mark_explored cached-vnum seam ----------------------------------------

def test_mark_explored_cached():
    p = _blank_player(room=3001)
    mark_explored(p)
    assert roomcount(p) == 1
    mark_explored(p)                       # same room -> no double work
    assert roomcount(p) == 1
    p["room"] = 3002
    mark_explored(p)
    assert roomcount(p) == 2
    # walk three rooms -> explored shows 3
    p["room"] = 3005
    mark_explored(p)
    assert roomcount(p) == 3


def test_mark_explored_out_of_range_noop():
    p = _blank_player(room=_MAX_VNUM + 500)
    mark_explored(p)
    assert roomcount(p) == 0


# -- do_explored: list sorting + zero-load ---------------------------------

def _capture(fn, *a):
    lines = []
    _orig = explored.chprintln
    explored.chprintln = lambda ch, txt="": lines.append(txt)
    try:
        fn(*a)
    finally:
        explored.chprintln = _orig
    return lines


def test_do_explored_list_sorts():
    world.init_world()
    p = _blank_player(room=3001)
    _set(p, *range(3000, 3050))            # ~50 midgaard rooms explored
    lines = _capture(do_explored, p, ["list"])
    joined = "\n".join(lines)
    assert "Midgaard" in joined
    # only midgaard has any explored rooms -> it is the highest %, first line
    assert "Midgaard" in lines[0]


def test_do_explored_noarg_lines():
    world.init_world()
    p = _blank_player(room=3001)
    _set(p, 3001, 3002)
    lines = _capture(do_explored, p, [])
    assert len(lines) == 4
    total = sum(world.AREA_ROOM_COUNTS.values())
    assert "The realm has {G" + str(total) + "{x explorable rooms." == lines[0]
    assert "explored {G2 (" in lines[3]     # current area line


def test_do_explored_never_lazy_loads():
    world.init_world()
    p = _blank_player(room=3001)
    _set(p, 3001, 3002)
    before = set(world._LOADED_AREAS)
    do_explored(p, [])
    do_explored(p, ["list"])
    do_explored(p, ["reset"])
    assert set(world._LOADED_AREAS) == before, "do_explored triggered an area load"
    assert roomcount(p) == 0               # reset zeroed the mask
