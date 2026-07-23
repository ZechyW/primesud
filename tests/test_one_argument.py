"""Tests for one_argument (cf. 1stMud one_argument in interp.c).

Regression: one_argument once lowercased the *entire* input, mangling say/emote
text and colour codes ("{C" -> "{c").  1stMud only lowercases arg_first (the
command word) and returns the remainder verbatim.  Fixed 2026-07-09.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

from commands import one_argument, split_args


def test_word_lowercased_rest_verbatim():
    assert one_argument("SAY Hello There") == ("say", "Hello There")


def test_colour_codes_preserved_in_rest():
    assert one_argument("say Hello {CWorld") == ("say", "Hello {CWorld")


def test_quoted_word_grouped_and_lowercased():
    assert one_argument("'Get Sword' rest Kept") == ("get sword", "rest Kept")


def test_double_quote_grouping():
    assert one_argument('"foo BAR" tail') == ("foo bar", "tail")


def test_empty_and_whitespace():
    assert one_argument("") == ("", "")
    assert one_argument("   ") == ("", "")


def test_leading_whitespace_skipped():
    assert one_argument("   go North") == ("go", "North")


def test_split_args_lowercases_each_word():
    assert split_args("Get The Sword") == ["get", "the", "sword"]
