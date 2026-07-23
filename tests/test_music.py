"""Tests for the jukebox play command and music pulse (cf. 1stMud music.c)."""
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
import music
import world
from handler import _char_base
from world import ITEM_DEFS

JUKE_VNUM = 9700
ROOM_A = 9701  # jukebox's room
ROOM_B = 9702  # a different room, no jukebox

SONGS = [
    ("Alpha Song", "Testers", ["La la la", "Boom boom"]),
    ("Beta Tune", "Testers", ["Yeah yeah"]),
]


def _write_song_data(tmp_path, songs):
    """Write a tiny synthetic music.txt/music.idx pair (cf. tools/build_music_idx.py format)."""
    header = "# test\n"
    txt_parts = [header]
    idx_lines = []
    pos = len(header)
    for name, group, lyric_lines in songs:
        marker = "#" + name + "|" + group + "|" + str(len(lyric_lines)) + "\n"
        txt_parts.append(marker)
        pos += len(marker)
        body = [l + "\n" for l in lyric_lines]
        length = sum(len(l) for l in body)
        idx_lines.append(str(pos) + "|" + str(length) + "|" + str(len(lyric_lines))
                          + "|" + name + "|" + group)
        txt_parts.extend(body)
        pos += length
    txt_path = str(tmp_path / "music.txt")
    idx_path = str(tmp_path / "music.idx")
    # newline="" -- avoid Windows CRLF translation, which would shift the
    # byte offsets music.idx computes above out from under music.txt.
    with open(txt_path, "w", newline="") as f:
        f.write("".join(txt_parts))
    with open(idx_path, "w", newline="") as f:
        f.write("\n".join(idx_lines) + "\n")
    return txt_path, idx_path


def _stub_room(vnum, **extra):
    room = {"name": "Test Room", "desc": "A test room.", "exits": {},
            "items": [], "mobs": [], "area": "test", "flags": {},
            "sector": "inside"}
    room.update(extra)
    world.rooms._data[vnum] = room
    return room


def _make_player(room=ROOM_A, **overrides):
    ch = _char_base()
    ch.update({"id": 1, "name": "Tester", "level": 1, "room": room})
    ch.update(overrides)
    world.chars[1] = ch
    return ch


@pytest.fixture(autouse=True)
def _clean_world_state(tmp_path, monkeypatch):
    old_rooms = dict(world.rooms._data)
    old_chars = dict(world.chars)
    old_items = dict(ITEM_DEFS._data)

    ITEM_DEFS._data[JUKE_VNUM] = {
        "keywords": "juke box music", "short_descr": "the juke",
        "description": "A neon-lit juke box sits in the corner.",
        "type": "jukebox", "wear_flags": {}, "level": 0, "weight": 0, "value": 0,
    }
    _stub_room(ROOM_A)
    _stub_room(ROOM_B)

    txt_path, idx_path = _write_song_data(tmp_path, SONGS)
    monkeypatch.setattr(music, "MUSIC_FILE", txt_path)
    monkeypatch.setattr(music, "MUSIC_INDEX", idx_path)
    music._SONGS = None
    music._channel_songs = [-1] * (music.MAX_GLOBAL + 1)
    music._channel_lines = None
    music._room_playing = False

    yield

    world.rooms._data.clear()
    world.rooms._data.update(old_rooms)
    world.chars.clear()
    world.chars.update(old_chars)
    ITEM_DEFS._data.clear()
    ITEM_DEFS._data.update(old_items)
    music._SONGS = None
    music._channel_songs = [-1] * (music.MAX_GLOBAL + 1)
    music._channel_lines = None
    music._room_playing = False


def _make_jukebox():
    juke = {"vnum": JUKE_VNUM, "cost": 0}
    world.rooms._data[ROOM_A]["items"].append(juke)
    return juke


@pytest.fixture
def out(monkeypatch):
    lines = []
    monkeypatch.setattr(handler, "tprint", lambda s="", end="\n": lines.append(s))
    return lines


@pytest.fixture
def paged(monkeypatch):
    captured = []
    monkeypatch.setattr(music, "tpage", lambda lines: captured.extend(lines))
    return captured


def _has(lines, substr):
    return any(substr in l for l in lines)


# ---------------------------------------------------------------------------
# do_play: syntax / no-jukebox guards
# ---------------------------------------------------------------------------

def test_no_args_prints_syntax_and_play_what(out):
    player = _make_player()
    music.do_play(player, [])
    assert _has(out, "Syntax: play list [artist]")
    assert _has(out, "play [loud] <song>")
    assert _has(out, "Play what?")


def test_no_jukebox_in_room(out):
    player = _make_player(room=ROOM_B)
    music.do_play(player, ["alpha"])
    assert _has(out, "You see nothing to play.")


# ---------------------------------------------------------------------------
# do_play list
# ---------------------------------------------------------------------------

def test_play_list_shows_songs(paged):
    _make_jukebox()
    player = _make_player()
    music.do_play(player, ["list"])
    assert _has(paged, "the juke has the following songs available:")
    assert _has(paged, "Alpha Song")
    assert _has(paged, "Beta Tune")


def test_play_list_artist_shows_group(paged):
    _make_jukebox()
    player = _make_player()
    music.do_play(player, ["list", "artist"])
    assert any("Testers" in l and "Alpha Song" in l for l in paged)


# ---------------------------------------------------------------------------
# do_play: queueing
# ---------------------------------------------------------------------------

def test_queue_song_by_prefix(out):
    juke = _make_jukebox()
    player = _make_player()
    music.do_play(player, ["alpha"])
    assert _has(out, "Coming right up.")
    assert juke["juke_queue"][0] == 0  # Alpha Song is index 0
    assert juke["juke_queue"][1] == -1


def test_unknown_song_rejected(out):
    _make_jukebox()
    player = _make_player()
    music.do_play(player, ["nonexistent"])
    assert _has(out, "That song isn't available.")


def test_full_queue_rejection(out):
    juke = _make_jukebox()
    juke["juke_queue"] = [0, 0, 0, 0]  # all four slots full
    player = _make_player()
    music.do_play(player, ["beta"])
    assert _has(out, "The jukebox is full up right now.")
    assert juke["juke_queue"] == [0, 0, 0, 0]  # unchanged


def test_loud_queues_onto_channel(out):
    _make_jukebox()  # loud still requires a jukebox in the room to type "play loud"
    player = _make_player()
    music.do_play(player, ["loud", "alpha"])
    assert _has(out, "Coming right up.")
    assert music._channel_songs[1] == 0


def test_loud_full_channel_rejection(out):
    _make_jukebox()
    player = _make_player()
    music._channel_songs[music.MAX_GLOBAL] = 0  # last slot full
    music.do_play(player, ["loud", "beta"])
    assert _has(out, "The jukebox is full up right now.")


# ---------------------------------------------------------------------------
# song_update: room jukebox line advance + rotation
# ---------------------------------------------------------------------------

def test_song_update_advances_lines_and_rotates(out):
    juke = _make_jukebox()
    player = _make_player(room=ROOM_A)
    juke["juke_queue"] = [0, 1, -1, -1]  # Alpha then Beta queued
    music._room_playing = True  # normally set by do_play

    music.song_update()  # starts Alpha
    assert _has(out, "starts playing Testers, Alpha Song")
    assert juke["juke_line"] == 0

    music.song_update()  # first lyric line
    assert _has(out, "bops: 'La la la'")
    assert juke["juke_line"] == 1

    music.song_update()  # second (last) lyric line
    assert _has(out, "bops: 'Boom boom'")
    assert juke["juke_line"] == 2

    out[:] = []
    music.song_update()  # rotation pulse: no message, advances to Beta
    assert out == []
    assert juke["juke_queue"][0] == 1  # Beta now current
    assert juke["juke_line"] == -1

    music.song_update()  # starts Beta
    assert _has(out, "starts playing Testers, Beta Tune")

    music.song_update()  # Beta's only lyric line
    assert _has(out, "bops: 'Yeah yeah'")

    out[:] = []
    music.song_update()  # rotation pulse: queue now empty
    assert out == []
    assert juke["juke_queue"] == [-1, -1, -1, -1]


def test_room_jukebox_silent_when_player_elsewhere(out):
    juke = _make_jukebox()
    _make_player(room=ROOM_B)  # player not in the jukebox's room
    juke["juke_queue"] = [0, -1, -1, -1]
    music._room_playing = True  # normally set by do_play

    music.song_update()
    music.song_update()
    assert out == []
    # queue still advances even though nothing was echoed
    assert juke["juke_line"] == 1


# ---------------------------------------------------------------------------
# song_update: loud channel echoes regardless of player's room
# ---------------------------------------------------------------------------

def test_loud_channel_echoes_when_player_elsewhere(out):
    _make_jukebox()
    player = _make_player(room=ROOM_A)
    music.do_play(player, ["loud", "alpha"])
    out[:] = []

    player["room"] = ROOM_B  # player leaves the jukebox's room entirely

    music.song_update()  # announce
    assert _has(out, "Music: Testers, Alpha Song")

    music.song_update()  # first lyric
    assert _has(out, "Music: 'La la la'")


# ---------------------------------------------------------------------------
# song_update: idle early-out ([PRIMESUD])
# ---------------------------------------------------------------------------

def test_song_update_idle_skips_index_load(out):
    _make_player()
    music.song_update()  # nothing queued anywhere
    assert out == []
    assert music._SONGS is None  # index never loaded from disk


def test_room_playing_flag_clears_when_queue_drains(out):
    juke = _make_jukebox()
    player = _make_player()
    music.do_play(player, ["beta"])  # 1-line song
    assert music._room_playing
    for _ in range(4):  # announce, lyric, rotation-to-empty, idle detect
        music.song_update()
    assert juke["juke_queue"] == [-1, -1, -1, -1]
    assert not music._room_playing
