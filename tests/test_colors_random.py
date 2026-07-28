"""Random colour code ({? / {`) resolution."""

from colors import (_RANDOM_POOL, color_wrap_full, resolve_random,
                    strip_colors)


def test_no_random_code_is_untouched():
    assert resolve_random("{RPlain{x text") == "{RPlain{x text"
    assert resolve_random("no codes here") == "no codes here"


def test_random_code_resolves_to_a_pool_colour():
    for raw in ("{?Hello{x", "{`Hello{x"):
        out = resolve_random(raw)
        assert out[0] == "{"
        assert out[1] in _RANDOM_POOL
        assert out[2:] == "Hello{x"


def test_black_is_excluded_from_the_pool():
    # 1stMud random_color() draws FG_RED..FG_WHITE, so never black.
    assert "d" not in _RANDOM_POOL and "D" not in _RANDOM_POOL


def test_brace_escape_is_not_treated_as_a_code():
    # '{{' is a literal '{'; the '?' after it is plain text, not a colour code.
    out = resolve_random("{?a{{?b")
    assert out[1] in _RANDOM_POOL
    assert out[2:] == "a{{?b"


def test_each_occurrence_rolls_independently():
    seen = set()
    for _ in range(50):
        out = resolve_random("{?a{?b")
        assert out[0] == "{" and out[1] in _RANDOM_POOL
        assert out[2] == "a" and out[3] == "{" and out[4] in _RANDOM_POOL
        assert out[5] == "b"
        seen.add((out[1], out[4]))
    # 14 codes squared: two independent rolls should differ at least once.
    assert any(a != b for a, b in seen)


def test_wrapped_span_keeps_one_colour():
    # The reason resolution happens before wrapping: color_wrap_full re-emits
    # the active code at each continuation piece, so an unresolved code would
    # re-roll per physical line.
    text = resolve_random("{?" + "word " * 40)
    code = text[1]
    pieces = color_wrap_full(text, 20)
    assert len(pieces) > 1
    for piece in pieces:
        assert piece.startswith("{" + code)
    assert "?" not in strip_colors("".join(pieces))
