"""Tests for the alias system (cf. 1stMud alias.c: substitute_alias, do_alias, do_unalias)."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
_SRC = os.environ.get("PRIMESUD_SRC", "src")
sys.path.insert(0, os.path.join(ROOT, _SRC))
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

from terminal import init_terminal
init_terminal()

import handler
import world
import commands
import aliases
from handler import _char_base
from aliases import do_alias, do_unalias, substitute_alias, MAX_ALIAS


def _stub_room(vnum, **extra):
    room = {"name": "Test Room", "desc": "x", "exits": {}, "items": [],
            "mobs": [], "area": "test", "flags": {}, "sector": "inside"}
    room.update(extra)
    world.rooms._data[vnum] = room
    return room


def _make_char(cid=1, npc=False, **overrides):
    ch = _char_base()
    ch["id"] = cid
    ch["is_npc"] = npc
    ch["name"] = overrides.pop("name", "Tester" if not npc else "a test mob")
    ch["room"] = overrides.pop("room", 9001)
    ch["aliases"] = overrides.pop("aliases", [])
    ch.update(overrides)
    world.chars[cid] = ch
    if npc and ch["room"] in world.rooms._data:
        world.rooms._data[ch["room"]]["mobs"].append(cid)
    return ch


@pytest.fixture(autouse=True)
def _clean_world_state():
    old_rooms = dict(world.rooms._data)
    old_chars = dict(world.chars)
    world.rooms._data.clear()
    world.chars.clear()
    _stub_room(9001)
    yield
    world.rooms._data.clear()
    world.rooms._data.update(old_rooms)
    world.chars.clear()
    world.chars.update(old_chars)


@pytest.fixture
def out(monkeypatch):
    lines = []
    cap = lambda s="", end="\n": lines.append(s)
    monkeypatch.setattr(handler, "tprint", cap)
    monkeypatch.setattr(commands, "tprint", cap)
    monkeypatch.setattr(aliases, "tprint", cap)
    return lines


def _has(lines, substr):
    return any(substr in l for l in lines)


# ---------------------------------------------------------------------------
# do_alias: list / show / set / realias / limit / reserved
# ---------------------------------------------------------------------------

class TestDoAlias:
    def test_no_aliases_defined(self, out):
        player = _make_char()
        do_alias(player, "")
        assert _has(out, "You have no aliases defined.")

    def test_set_new_alias(self, out):
        player = _make_char()
        do_alias(player, "gc get corpse")
        assert _has(out, "gc is now aliased to 'get corpse'.")
        assert player["aliases"] == [["gc", "get corpse"]]

    def test_list_aliases(self, out):
        player = _make_char()
        do_alias(player, "gc get corpse")
        del out[:]
        do_alias(player, "")
        assert _has(out, "Your current aliases are:")
        assert _has(out, "    gc:  get corpse")

    def test_show_single_alias(self, out):
        player = _make_char()
        do_alias(player, "gc get corpse")
        del out[:]
        do_alias(player, "gc")
        assert _has(out, "gc aliases to 'get corpse'.")

    def test_show_undefined_alias(self, out):
        player = _make_char()
        do_alias(player, "gc")
        assert _has(out, "That alias is not defined.")

    def test_realias_existing(self, out):
        player = _make_char()
        do_alias(player, "gc get corpse")
        del out[:]
        do_alias(player, "gc get corpse 2")
        assert _has(out, "gc is now realiased to 'get corpse 2'.")
        assert player["aliases"] == [["gc", "get corpse 2"]]

    def test_realias_preserves_slot_order(self, out):
        player = _make_char()
        do_alias(player, "a one")
        do_alias(player, "b two")
        do_alias(player, "a three")
        assert player["aliases"] == [["a", "three"], ["b", "two"]]

    @pytest.mark.parametrize("word", ["alias", "una", "unalias", "unafoo"])
    def test_reserved_word_rejected(self, out, word):
        player = _make_char()
        do_alias(player, word + " something")
        assert _has(out, "Sorry, that word is reserved.")
        assert player["aliases"] == []

    @pytest.mark.parametrize("name", ["a=b", "a.b", "a~b"])
    def test_bad_chars_rejected(self, out, name):
        player = _make_char()
        do_alias(player, name + " test")
        assert player["aliases"] == []

    def test_tilde_in_substitution_rejected(self, out):
        # '~' is the save-payload line separator (game_state.py) -- an
        # alias sub containing it would corrupt the save on the next write.
        player = _make_char()
        do_alias(player, "gc get corpse~say hi")
        assert _has(out, "may not contain")
        assert player["aliases"] == []

    def test_alias_limit(self, out):
        player = _make_char()
        for i in range(MAX_ALIAS):
            do_alias(player, "a%d cmd%d" % (i, i))
        assert len(player["aliases"]) == MAX_ALIAS
        del out[:]
        do_alias(player, "overflow cmd")
        assert _has(out, "Sorry, you have reached the alias limit.")
        assert len(player["aliases"]) == MAX_ALIAS

    def test_npc_no_op(self, out):
        player = _make_char(npc=True)
        do_alias(player, "gc get corpse")
        assert out == []
        assert player["aliases"] == []


# ---------------------------------------------------------------------------
# do_unalias
# ---------------------------------------------------------------------------

class TestDoUnalias:
    def test_unalias_what(self, out):
        player = _make_char()
        do_unalias(player, [])
        assert _has(out, "Unalias what?")

    def test_unalias_removes_alias(self, out):
        player = _make_char()
        do_alias(player, "gc get corpse")
        del out[:]
        do_unalias(player, ["gc"])
        assert _has(out, "Alias removed.")
        assert player["aliases"] == []

    def test_unalias_compacts_list(self, out):
        player = _make_char()
        do_alias(player, "a one")
        do_alias(player, "b two")
        do_alias(player, "c three")
        do_unalias(player, ["b"])
        assert player["aliases"] == [["a", "one"], ["c", "three"]]

    def test_unalias_not_found(self, out):
        player = _make_char()
        do_unalias(player, ["nope"])
        assert _has(out, "No alias of that name to remove.")

    def test_npc_no_op(self, out):
        player = _make_char(npc=True, aliases=[["gc", "get corpse"]])
        do_unalias(player, ["gc"])
        assert out == []
        assert player["aliases"] == [["gc", "get corpse"]]


# ---------------------------------------------------------------------------
# substitute_alias -- unit level
# ---------------------------------------------------------------------------

class TestSubstituteAliasUnit:
    def test_no_match_returns_unchanged(self):
        player = _make_char(aliases=[["gc", "get corpse"]])
        assert substitute_alias(player, "look") == "look"

    def test_match_appends_tail(self):
        player = _make_char(aliases=[["gc", "get corpse"]])
        assert substitute_alias(player, "gc 2") == "get corpse 2"

    def test_match_no_tail(self):
        player = _make_char(aliases=[["gc", "get corpse"]])
        assert substitute_alias(player, "gc") == "get corpse"

    def test_alias_prefixed_input_not_substituted(self):
        player = _make_char(aliases=[["alias", "should not fire"]])
        assert substitute_alias(player, "alias foo bar") == "alias foo bar"

    def test_una_prefixed_input_not_substituted(self):
        player = _make_char(aliases=[["gc", "get corpse"]])
        assert substitute_alias(player, "unalias gc") == "unalias gc"
        assert substitute_alias(player, "una gc") == "una gc"

    def test_no_aliases_returns_unchanged(self):
        player = _make_char(aliases=[])
        assert substitute_alias(player, "gc") == "gc"

    def test_npc_actor_skips_substitution(self):
        # Simulate a mobprog command actor: is_npc True even though (per
        # normal creation) NPCs never get an "aliases" list -- the is_npc
        # check itself must short-circuit, not just the missing-key fallback.
        player = _make_char(npc=True, aliases=[["gc", "get corpse"]])
        assert substitute_alias(player, "gc") == "gc"


# ---------------------------------------------------------------------------
# substitute_alias -- end-to-end via commands.interpret()
# ---------------------------------------------------------------------------

class TestInterpretSubstitution:
    def test_alias_expands_through_interpret(self, out):
        player = _make_char()
        do_alias(player, "gc say hello")
        del out[:]
        commands.interpret("gc there", player)
        assert _has(out, "hello there")

    def test_alias_no_recursion(self, out):
        """alias "say" -> "say hello" must not loop -- substitution fires
        exactly once per interpret() call, never re-entering itself."""
        player = _make_char()
        do_alias(player, "say say hello")
        del out[:]
        commands.interpret("say", player)
        assert _has(out, "hello")

    def test_alias_word_not_substituted(self, out):
        player = _make_char()
        do_alias(player, "gc say hello")
        del out[:]
        commands.interpret("alias gc say goodbye", player)
        assert _has(out, "gc is now realiased to 'say goodbye'.")

    def test_unalias_word_not_substituted(self, out):
        player = _make_char()
        do_alias(player, "gc say hello")
        del out[:]
        commands.interpret("unalias gc", player)
        assert _has(out, "Alias removed.")
        assert player["aliases"] == []


# ---------------------------------------------------------------------------
# Save/load round trip
# ---------------------------------------------------------------------------

class TestSaveLoad:
    def test_alias_roundtrip(self, tmp_path, monkeypatch):
        import game_state
        from player import create_char
        monkeypatch.setattr(game_state, "SAVE_FILE", str(tmp_path / "t.sav"))
        world.areas = []
        player = create_char()
        player["name"] = "Tester"
        player["room"] = 9001
        player["_macros"] = {}
        player["aliases"] = [["gc", "get corpse"], ["n", "north"]]
        world.chars[1] = player
        game_state._serialize_world()

        world.chars.clear()
        player2 = create_char()
        player2["name"] = "Tester"
        player2["room"] = 9001
        player2["_macros"] = {}
        world.chars[1] = player2
        assert game_state.load_world() == "file"
        assert player2["aliases"] == [["gc", "get corpse"], ["n", "north"]]

    def test_load_without_alias_lines_leaves_empty_list(self, tmp_path, monkeypatch):
        import game_state
        from player import create_char
        monkeypatch.setattr(game_state, "SAVE_FILE", str(tmp_path / "t.sav"))
        world.areas = []
        player = create_char()
        player["name"] = "Tester"
        player["room"] = 9001
        player["_macros"] = {}
        # No aliases set -- mirrors a pre-alias-feature save file.
        world.chars[1] = player
        game_state._serialize_world()

        world.chars.clear()
        player2 = create_char()
        player2["name"] = "Tester"
        player2["room"] = 9001
        player2["_macros"] = {}
        world.chars[1] = player2
        assert game_state.load_world() == "file"
        assert player2["aliases"] == []
