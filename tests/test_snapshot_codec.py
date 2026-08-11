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
        "with\rcarriage\r\nreturn",
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
        "line1\nline2\r",
        'mix "of" ~ delims~"and"~backslash\\',
        {"short_descr": 'A "glowing" ~rune~ blade\\'},
        {"description": 'She said "hi".\nSecond line.\r\n'},
        ["~", '"', "\\", "\n", "\r"],
    ])
    def test_no_unsafe_bytes_in_encoded_output(self, value):
        encoded = _snap_encode(value)
        # The unsafe bytes must be ABSENT entirely, not merely
        # backslash-prefixed: load_world splits the payload with a naive
        # data.split("~"), and hvars_set embeds it in a PPL string literal
        # where backslash is not an escape -- a prefixed '"'/newline would
        # still break both. Real template descriptions contain quotes and
        # newlines.
        for ch in ("~", '"', "\n", "\r"):
            assert ch not in encoded, (
                "raw %r in encoded output %r" % (ch, encoded))

    def test_round_trip_survives_delimiters(self):
        value = {"a": '~"\\', "b": ['"~\\', "~~", "a\nb\rc"]}
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

    def test_unknown_escape_sequence_raises(self):
        # Strict map: "\z" is corruption, not a passthrough for "z".
        with pytest.raises(ValueError):
            _snap_decode("s2:\\z")

    @pytest.mark.parametrize("bad", [
        "s-1:x",  # "-" where a length digit belongs
        "s99:ab",  # length far past the end of the record
        "i5x",  # trailing junk after a valid int
        "d1:s1:a",  # key decoded, value truncated
        "t2:n",  # count says 2, one value present
    ])
    def test_raises_value_error_extra(self, bad):
        with pytest.raises(ValueError):
            _snap_decode(bad)

    @pytest.mark.parametrize("bad", [5, None, 3.5, ["s1:a"]])
    def test_non_string_input_raises_value_error(self, bad):
        # Contract: ValueError for every malformed input, never another
        # exception type -- the decoder now byte-casts its argument first,
        # so a non-str/bytes argument fails there instead of mid-walk.
        with pytest.raises(ValueError):
            _snap_decode(bad)


# ===== Byte-walk decoder =====================================================
# The decoder walks bytes, not str: these pin the seams that shift with it
# (length prefixes counting ESCAPED bytes, payloads that look like tags,
# bytes input).

class TestByteWalkDecode:
    def test_nested_escapes_and_tag_lookalike_payloads(self):
        # Every string here would mis-decode if a length prefix were read
        # as anything but "bytes of the escaped payload", or if a payload
        # were rescanned for type tags.
        value = {
            "desc": 'He said "hi".\nLine 2\r\n~tilde~ and a back\\slash',
            "lookalike": "i-42",
            "nested": ["s5:abcde", ("d1:", "l2:nn"), {"t1:": "T"}, "n", ""],
        }
        assert _snap_decode(_snap_encode(value)) == value

    def test_length_prefix_counts_escaped_bytes(self):
        # "\t" is the two-byte escape for "~": length 2, one decoded char.
        assert _snap_decode("s2:\\t") == "~"
        assert _snap_decode("l2:s2:\\qs1:a") == ['"', "a"]

    def test_bytes_input_decodes(self):
        value = {"a": [1, -2, True, None, "x~y"]}
        assert _snap_decode(_snap_encode(value).encode()) == value


# ===== Registry lifecycle ====================================================

class TestRegistryLifecycle:
    def test_reset_lazy_clears_item_snapshots(self):
        # reset_lazy() repopulates AREA_DEFS from _AREA_FILES; put it back so
        # the next test does not inherit 50 stub area records.
        old_area_defs = list(world.AREA_DEFS)
        ITEM_SNAPSHOTS[999] = ("rev", {"short_descr": "x"}, {})
        try:
            reset_lazy()
            assert ITEM_SNAPSHOTS == {}
        finally:
            world.AREA_DEFS[:] = old_area_defs


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
