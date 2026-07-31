"""util.count_str -- the four 1stMud intstr branches. [PRIMESUD]"""

from util import count_str


def test_singular_never_pluralises():
    assert count_str(1, "minute") == "1 minute"
    assert count_str(1, "penalty") == "1 penalty"
    assert count_str(1, "class") == "1 class"


def test_regular_plural():
    assert count_str(0, "minute") == "0 minutes"
    assert count_str(3, "quest point") == "3 quest points"
    assert count_str(-2, "mob") == "-2 mobs"


def test_y_becomes_ies():
    assert count_str(2, "penalty") == "2 penalties"


def test_double_s_takes_es():
    assert count_str(2, "class") == "2 classes"


def test_lone_s_already_plural():
    assert count_str(2, "series") == "2 series"
    assert count_str(5, "s") == "5 s"
