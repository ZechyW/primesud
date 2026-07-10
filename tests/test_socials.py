"""Tests for the socials system (cf. 1stMud find_social / check_social in interp.c)."""
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
import socials
import world
import commands
from handler import _char_base

SOCIALS_TXT = os.path.join(ROOT, "src", "socials.txt")
SOCIALS_IDX = os.path.join(ROOT, "src", "socials.idx")


def _stub_room(vnum, **extra):
    room = {"name": "Test Room", "desc": "x", "exits": {}, "items": [],
            "mobs": [], "area": "test", "flags": {}, "sector": "inside"}
    room.update(extra)
    world.rooms._data[vnum] = room
    return room


def _make_char(cid, npc=False, **overrides):
    ch = _char_base()
    ch["id"] = cid
    ch["is_npc"] = npc
    ch["name"] = overrides.pop("name", "Tester" if not npc else "a test mob")
    ch["room"] = overrides.pop("room", 9001)
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
    return lines


def _has(lines, substr):
    """True if any captured line contains substr (act() output carries a
    trailing '{x' colour-reset code, cf. handler._render_act). [PRIMESUD]"""
    return any(substr in l for l in lines)


@pytest.fixture
def real_files(monkeypatch):
    """Point the socials module at the actual generated data files."""
    monkeypatch.setattr(socials, "SOCIALS_FILE", SOCIALS_TXT)
    monkeypatch.setattr(socials, "SOCIALS_IDX", SOCIALS_IDX)


# ---------------------------------------------------------------------------
# Converter output sanity
# ---------------------------------------------------------------------------

class TestConverterOutput:
    def test_smile_round_trips_via_index(self, real_files):
        f = open(SOCIALS_IDX)
        idx = f.read()
        f.close()
        line = next(l for l in idx.split("\n") if l.split("|", 2)[-1] == "smile")
        off_s, len_s, name = line.split("|", 2)
        assert name == "smile"

        f = open(SOCIALS_TXT)
        f.seek(int(off_s))
        chunk = f.read(int(len_s))
        f.close()

        lines = chunk.split("\n")
        assert len(lines) == 8  # 7 fields + trailing blank from final "\n"
        char_no_arg, others_no_arg, char_found, others_found, vict_found, \
            char_auto, others_auto = lines[:7]
        assert char_no_arg == "You smile happily."
        assert others_no_arg == "$n smiles happily."
        assert char_found == "You smile at $M."
        assert char_auto == "You smile at yourself."

    def test_index_is_ascii_and_sorted(self, real_files):
        with open(SOCIALS_IDX, "rb") as f:
            data = f.read()
        assert all(b < 128 for b in data)
        assert b"\r\n" not in data
        names = [l.split(b"|", 2)[2] for l in data.split(b"\n") if l]
        assert names == sorted(names)

    def test_data_file_is_ascii(self, real_files):
        with open(SOCIALS_TXT, "rb") as f:
            data = f.read()
        assert all(b < 128 for b in data)
        assert b"\r\n" not in data

    def test_aargh_garbled_text_preserved(self, real_files):
        # Known upstream data quirk: "others_no_arg" for "aargh" has
        # "others_found" spliced mid-word ("prothers_found frustration").
        # Preserved verbatim -- not a PrimeSUD conversion bug.
        f = open(SOCIALS_IDX)
        idx = f.read()
        f.close()
        line = next(l for l in idx.split("\n") if l.split("|", 2)[-1] == "aargh")
        off_s, len_s, _ = line.split("|", 2)
        f = open(SOCIALS_TXT)
        f.seek(int(off_s))
        chunk = f.read(int(len_s))
        f.close()
        others_no_arg = chunk.split("\n")[1]
        assert "prothers_found frustration" in others_no_arg


# ---------------------------------------------------------------------------
# find_social
# ---------------------------------------------------------------------------

class TestFindSocial:
    def test_prefix_match(self, real_files):
        hit = socials.find_social("smil")
        assert hit is not None
        assert hit[0] == "smile"

    def test_exact_match(self, real_files):
        hit = socials.find_social("smile")
        assert hit[0] == "smile"

    def test_no_match(self, real_files):
        assert socials.find_social("xyzzyzzy") is None

    def test_empty_command_no_match(self, real_files):
        assert socials.find_social("") is None


# ---------------------------------------------------------------------------
# check_social
# ---------------------------------------------------------------------------

class TestCheckSocialNoMatch:
    def test_unknown_command_returns_false(self, real_files, out):
        player = _make_char(1, npc=False)
        assert socials.check_social(player, "xyzzyzzy", "") is False
        assert out == []


class TestCheckSocialNoArg:
    def test_no_arg_prints_char_message_only(self, real_files, out):
        player = _make_char(1, npc=False)
        assert socials.check_social(player, "smile", "") is True
        assert len(out) == 1
        assert _has(out, "You smile happily.")


class TestCheckSocialSelf:
    def test_self_keyword(self, real_files, out):
        player = _make_char(1, npc=False, name="Tester")
        assert socials.check_social(player, "smile", "self") is True
        assert len(out) == 1
        assert _has(out, "You smile at yourself.")

    def test_own_name(self, real_files, out):
        player = _make_char(1, npc=False, name="Tester")
        assert socials.check_social(player, "smile", "tester") is True
        assert len(out) == 1
        assert _has(out, "You smile at yourself.")


class TestCheckSocialVictimAbsent:
    def test_victim_not_found(self, real_files, out):
        player = _make_char(1, npc=False)
        assert socials.check_social(player, "smile", "bob") is True
        assert out == ["They aren't here."]


class TestCheckSocialVictimFound:
    def test_char_and_vict_messages(self, real_files, out, monkeypatch):
        player = _make_char(1, npc=False, name="Tester")
        _make_char(2, npc=True, name="a test mob", keywords="mob test")
        monkeypatch.setattr(socials, "randint", lambda a, b: 13)  # no NPC mirror
        assert socials.check_social(player, "smile", "mob") is True
        assert _has(out, "You smile at it.")

    def test_npc_mirrors_found_messages(self, real_files, out, monkeypatch):
        player = _make_char(1, npc=False, name="Tester")
        _make_char(2, npc=True, name="a test mob", keywords="mob test")
        monkeypatch.setattr(socials, "randint", lambda a, b: 0)  # mirror branch
        socials.check_social(player, "smile", "mob")
        # vict_found rendered with victim as actor delivers to the player
        assert any("smiles at you" in l for l in out)

    def test_npc_slap_response(self, real_files, out, monkeypatch):
        player = _make_char(1, npc=False, name="Tester")
        _make_char(2, npc=True, name="a test mob", keywords="mob test")
        monkeypatch.setattr(socials, "randint", lambda a, b: 10)  # slap branch
        socials.check_social(player, "smile", "mob")
        assert any("slaps you" in l for l in out)

    def test_npc_no_response(self, real_files, out, monkeypatch):
        player = _make_char(1, npc=False, name="Tester")
        _make_char(2, npc=True, name="a test mob", keywords="mob test")
        monkeypatch.setattr(socials, "randint", lambda a, b: 15)  # nothing
        socials.check_social(player, "smile", "mob")
        assert not any("slaps you" in l for l in out)
        assert not any("smiles at you" in l for l in out)

    def test_sleeping_victim_no_mirror(self, real_files, out, monkeypatch):
        # is_awake gate: a sleeping NPC does not mirror the social back
        player = _make_char(1, npc=False, name="Tester")
        _make_char(2, npc=True, name="a test mob", keywords="mob test",
                    pos="sleeping")
        monkeypatch.setattr(socials, "randint", lambda a, b: 0)
        socials.check_social(player, "smile", "mob")
        assert not any("smiles at you" in l for l in out)
        assert not any("slaps you" in l for l in out)

    def test_charmed_victim_no_mirror(self, real_files, out, monkeypatch):
        player = _make_char(1, npc=False, name="Tester")
        _make_char(2, npc=True, name="a test mob", keywords="mob test",
                    affected_by={"charm": True})
        monkeypatch.setattr(socials, "randint", lambda a, b: 0)
        socials.check_social(player, "smile", "mob")
        assert not any("smiles at you" in l for l in out)
        assert not any("slaps you" in l for l in out)


class TestCheckSocialPosition:
    def test_dead_position(self, real_files, out):
        player = _make_char(1, npc=False, pos="dead")
        assert socials.check_social(player, "smile", "") is True
        assert out == ["Lie still; you are DEAD."]

    def test_incap_position(self, real_files, out):
        player = _make_char(1, npc=False, pos="incap")
        assert socials.check_social(player, "smile", "") is True
        assert out == ["You are hurt far too bad for that."]

    def test_mortal_position(self, real_files, out):
        player = _make_char(1, npc=False, pos="mortal")
        assert socials.check_social(player, "smile", "") is True
        assert out == ["You are hurt far too bad for that."]

    def test_stunned_position(self, real_files, out):
        player = _make_char(1, npc=False, pos="stunned")
        assert socials.check_social(player, "smile", "") is True
        assert out == ["You are too stunned to do that."]

    def test_sleeping_blocks_ordinary_social(self, real_files, out):
        player = _make_char(1, npc=False, pos="sleeping")
        assert socials.check_social(player, "smile", "") is True
        assert out == ["In your dreams, or what?"]

    def test_sleeping_allows_snore(self, real_files, out):
        # cf. 1stMud SENDOK (comm.c) -- act()'s default min_pos is
        # POS_RESTING, which is above POS_SLEEPING, so a sleeping player
        # never actually receives their own char_no_arg text even though
        # "snore" is exempted from the "In your dreams, or what?" gate.
        # This is a faithful upstream quirk, not a PrimeSUD bug: the
        # exemption only lets check_social's position switch fall through
        # to run the social (and return True) instead of blocking it.
        player = _make_char(1, npc=False, pos="sleeping")
        assert socials.check_social(player, "snore", "") is True
        assert out == []


class TestEmptyMessageSkipped:
    def test_snore_found_fields_are_blank_and_skipped(self, real_files, out, monkeypatch):
        # snore's char_found/others_found/vict_found/char_auto/others_auto
        # are all blank in social.dat -- act() must no-op on empty format,
        # not print a blank line.
        player = _make_char(1, npc=False, pos="sleeping", name="Tester")
        _make_char(2, npc=True, name="a test mob", keywords="mob test",
                    pos="sleeping")
        monkeypatch.setattr(socials, "randint", lambda a, b: 15)
        socials.check_social(player, "snore", "mob")
        assert out == []

    def test_self_auto_fields_blank_for_snore(self, real_files, out):
        player = _make_char(1, npc=False, pos="sleeping", name="Tester")
        socials.check_social(player, "snore", "self")
        assert out == []


# ---------------------------------------------------------------------------
# interpret() fallback wiring
# ---------------------------------------------------------------------------

class TestInterpretFallback:
    def test_unknown_command_falls_back_to_social(self, real_files, out, monkeypatch):
        player = _make_char(1, npc=False, name="Tester")
        # avoid the leading blank-line echo tprint("") polluting `out`
        commands.interpret("smile", player)
        assert _has(out, "You smile happily.")

    def test_genuine_garbage_still_prints_huh(self, real_files, out, monkeypatch):
        player = _make_char(1, npc=False, name="Tester")
        monkeypatch.setattr(commands, "randint", lambda a, b: 0)
        commands.interpret("xyzzyzzyplugh", player)
        text = "\n".join(out)
        assert any(msg.split("%s")[0] in text or msg in text
                   for msg in commands._HUH_MESSAGES)
