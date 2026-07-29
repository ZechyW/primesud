"""Tests for world.py's typed snapshot codec (_snap_encode/_snap_decode).

Covers:
- Unit round-trips for every supported type, including edge cases
- Deterministic output (repeat encodes, dict key order)
- No raw "~" or '"' in encoded records
- bool/int distinction survives round-trip
- Malformed input raises ValueError, never crashes or decodes garbage
- All-area drift guard: every generated OBJECTS template and OBJPROGS
  string round-trips exactly
- reset_lazy() empties ITEM_SNAPSHOTS
"""
import pytest

import world
from world import ITEM_SNAPSHOTS, _snap_encode, _snap_decode, reset_lazy

from tools import gen_area_adj


# ===== Unit round-trips ======================================================

class TestUnitRoundTrips:
    @pytest.mark.parametrize("value", [
        None,
        True,
        False,
        0,
        1,
        -1,
        -42,
        12345678901234,
        "",
        "hello",
        "with\\backslash",
        "with~tilde",
        'with"quote',
        "with\nnewline",
        "mixed \\ ~ \" \n all together",
        [],
        (),
        {},
        [1, 2, 3],
        (1, 2, 3),
        {"a": 1, "b": 2},
        [None, True, False, 0, "s", [1, (2,)], {"k": "v"}],
        ({"a": [1, 2, (3, 4)]}, "tuple of dict and str"),
    ])
    def test_round_trip(self, value):
        assert _snap_decode(_snap_encode(value)) == value

    def test_list_vs_tuple_preserved(self):
        assert isinstance(_snap_decode(_snap_encode([1, 2])), list)
        assert isinstance(_snap_decode(_snap_encode((1, 2))), tuple)
        assert _snap_decode(_snap_encode([1, 2])) != _snap_decode(_snap_encode((1, 2)))

    def test_bool_not_int_after_round_trip(self):
        decoded = _snap_decode(_snap_encode(True))
        assert decoded is True
        assert type(decoded) is bool
        decoded_one = _snap_decode(_snap_encode(1))
        assert type(decoded_one) is int
        assert decoded_one == 1
        assert decoded != decoded_one or type(decoded) is not type(decoded_one)


# ===== Determinism ===========================================================

class TestDeterminism:
    @pytest.mark.parametrize("value", [
        None, True, 0, -7, "abc", [1, "a", (2, 3)],
        {"z": 1, "a": 2, "m": 3},
        {"level": 5, "type": "weapon", "flags": {"take": True, "glow": False}},
    ])
    def test_repeat_encode_identical(self, value):
        assert _snap_encode(value) == _snap_encode(value)

    def test_dict_key_order_does_not_affect_output(self):
        d1 = {"a": 1, "b": 2, "c": 3}
        d2 = {"c": 3, "a": 1, "b": 2}
        assert _snap_encode(d1) == _snap_encode(d2)

    def test_nested_dict_key_order_does_not_affect_output(self):
        d1 = {"outer": {"a": 1, "b": 2}, "z": 9}
        d2 = {"z": 9, "outer": {"b": 2, "a": 1}}
        assert _snap_encode(d1) == _snap_encode(d2)


# ===== Delimiter safety ======================================================

class TestDelimiterSafety:
    @pytest.mark.parametrize("value", [
        "~",
        '"',
        "~~~",
        '"""',
        'mix "of" ~ delims~"and"~backslash\\',
        {"short_descr": 'A "glowing" ~rune~ blade\\'},
        ["~", '"', "\\"],
    ])
    def test_no_raw_delimiters_in_encoded_output(self, value):
        encoded = _snap_encode(value)
        # Every literal "~" or '"' in the encoded string must be preceded
        # by an escaping backslash (the length-prefix header itself never
        # contains either character).
        for i, ch in enumerate(encoded):
            if ch in ("~", '"'):
                assert i > 0 and encoded[i - 1] == "\\", (
                    "unescaped %r at index %d in %r" % (ch, i, encoded))

    def test_round_trip_survives_delimiters(self):
        value = {"a": '~"\\', "b": ['"~\\', "~~"]}
        assert _snap_decode(_snap_encode(value)) == value


# ===== Malformed input ========================================================

class TestMalformedInput:
    @pytest.mark.parametrize("bad", [
        "",
        "z",
        "x9",
        "i",
        "i-",
        "s",
        "s3:ab",  # length longer than remaining payload
        "s2",  # missing ":" terminator
        "l",
        "l2:",  # count says 2 elements but none follow
        "l1:n" + "trailing garbage",
        "d1:",  # missing key/value pair
        "sabc:x",  # non-digit length field
    ])
    def test_raises_value_error(self, bad):
        with pytest.raises(ValueError):
            _snap_decode(bad)

    def test_dangling_escape_raises(self):
        # A string record whose escaped payload ends mid-escape.
        with pytest.raises(ValueError):
            _snap_decode("s1:\\")


# ===== Registry lifecycle ====================================================

class TestRegistryLifecycle:
    def test_reset_lazy_clears_item_snapshots(self):
        ITEM_SNAPSHOTS[999] = ("rev", {"short_descr": "x"}, {})
        reset_lazy()
        assert ITEM_SNAPSHOTS == {}


# ===== All-area drift guard ==================================================
# Every OBJECTS template and every OBJPROGS source string generated area
# data actually uses must round-trip exactly. This replaces a manually
# maintained field list: an unsupported new value type in area data fails
# this test loudly instead of silently vanishing from a future snapshot.

def _iter_area_namespaces():
    for fname, tag, _name, _lo, _hi in world._AREA_FILES:
        yield tag, gen_area_adj.load_area_ns(fname)


class TestAllAreaRoundTrip:
    def test_every_object_template_round_trips(self):
        checked = 0
        for tag, ns in _iter_area_namespaces():
            objects = ns.get("OBJECTS", {})
            for vnum, tpl in objects.items():
                encoded = _snap_encode(tpl)
                decoded = _snap_decode(encoded)
                assert decoded == tpl, (
                    "area %s vnum %d template mismatch after round-trip"
                    % (tag, vnum))
                checked += 1
        assert checked > 0, "expected at least one OBJECTS template"

    def test_every_objprog_source_round_trips(self):
        checked = 0
        for tag, ns in _iter_area_namespaces():
            objprogs = ns.get("OBJPROGS", {})
            for vnum, src in objprogs.items():
                encoded = _snap_encode(src)
                decoded = _snap_decode(encoded)
                assert decoded == src, (
                    "area %s vnum %d objprog mismatch after round-trip"
                    % (tag, vnum))
                checked += 1
        # Current data has exactly one non-empty OBJPROGS entry (midgaard
        # vnum 3005); this stays a >= 1 sanity check rather than a magic
        # count so new area content doesn't need this test edited.
        assert checked >= 1, "expected at least one OBJPROGS entry"
