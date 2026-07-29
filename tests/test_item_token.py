"""Item save-token structural edge cases. [PRIMESUD]

Nested-container splitting: serialize_item_token joins a container's
children with '^' inside "co:[...]"; a child with its own co:[...] contents
embeds further '^' separators inside those brackets.  parse_item_token and
the deferred-token walker world._snap_token_vnums must both split on '^'
bracket-aware or a sibling after such a child gets sliced apart
(TODO 29/07/2026, fixed same day).
"""
import world
from item import parse_item_token, serialize_item_token, _str_escape


def _bag(vnum, contents=None, **extra):
    obj = {"vnum": vnum}
    if contents:
        obj["contents"] = contents
    obj.update(extra)
    return obj


class TestNestedContentsSplit:
    def test_sibling_after_nested_container_round_trips(self):
        # outer holds [inner-bag(grandchild), sibling]: the flat split used
        # to slice grandchild's '^'-joined token across the siblings.
        outer = _bag(1, [
            _bag(2, [_bag(3), _bag(4)]),
            _bag(5),
        ])
        restored = parse_item_token(serialize_item_token(outer))
        assert [o["vnum"] for o in restored["contents"]] == [2, 5]
        assert [o["vnum"] for o in restored["contents"][0]["contents"]] == [3, 4]
        assert "contents" not in restored["contents"][1]

    def test_three_levels_of_nesting(self):
        outer = _bag(1, [
            _bag(2, [_bag(3, [_bag(4), _bag(5)]), _bag(6)]),
            _bag(7),
        ])
        restored = parse_item_token(serialize_item_token(outer))
        lvl2 = restored["contents"][0]
        lvl3 = lvl2["contents"][0]
        assert [o["vnum"] for o in restored["contents"]] == [2, 7]
        assert [o["vnum"] for o in lvl2["contents"]] == [3, 6]
        assert [o["vnum"] for o in lvl3["contents"]] == [4, 5]

    def test_caret_in_string_field_round_trips(self):
        outer = _bag(1, [
            _bag(2, short_descr="a ^weird^ trinket"),
            _bag(3),
        ])
        restored = parse_item_token(serialize_item_token(outer))
        assert [o["vnum"] for o in restored["contents"]] == [2, 3]
        assert restored["contents"][0]["short_descr"] == "a ^weird^ trinket"

    def test_str_escape_covers_caret(self):
        assert _str_escape("a^b") == "a\\^b"


class TestSnapTokenVnumsMirror:
    def test_walker_sees_all_nested_vnums(self):
        outer = _bag(1, [
            _bag(2, [_bag(3), _bag(4)]),
            _bag(5, short_descr="a ^odd^ box"),
        ])
        token = serialize_item_token(outer)
        found = []
        world._snap_token_vnums(token, found)
        assert sorted(found) == [1, 2, 3, 4, 5]
