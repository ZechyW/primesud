"""Jukebox songs: play command, song index, and the music pulse (cf. 1stMud music.c)."""

import world
from world import ITEM_DEFS
from item import obj_vnum, item_type
from handler import act, chprintln, can_see_obj, TO_CHAR
from config import POS_ORDER
from pager import tpage
from util import pad_right

MUSIC_FILE = "music.txt"  # [PRIMESUD] canonical source; idx via tools/build_music_idx.py
MUSIC_INDEX = "music.idx"  # [PRIMESUD] '<offset>|<length>|<lines>|<name>|<group>' per entry, music.dat order

MAX_LINES = 100   # cf. 1stMud MAX_LINES in defines.h
MAX_GLOBAL = 10   # cf. 1stMud MAX_GLOBAL in defines.h -- global "loud" queue depth

# channel_songs[0] = current line ptr, [1] = now-playing song index,
# [2..MAX_GLOBAL] = queued song indices; -1 = empty (cf. 1stMud
# channel_songs in music.c, zeroed to -1 at boot by data_table.c).
_channel_songs = [-1] * (MAX_GLOBAL + 1)
_channel_lines = None  # [PRIMESUD] cached lyrics of the currently-playing loud song

# [PRIMESUD] Resident song index (16 entries, trivial heap cost) loaded once
# from MUSIC_INDEX; unlike help.idx/socials.idx (hundreds of entries,
# rescanned per lookup) this is small enough to just keep in memory.
_SONGS = None

# [PRIMESUD] True while any room jukebox has a queued song; lets song_update
# skip the index disk load and the all-rooms scan on the (common) idle music
# pulse. Set by do_play, cleared by song_update when the scan finds nothing.
_room_playing = False


def _load_songs():
    """Return the (name, group, offset, length, lines) song index, loading it once. [PRIMESUD]"""
    global _SONGS
    if _SONGS is None:
        with open(MUSIC_INDEX) as f:
            data = f.read()
        songs = []
        for line in data.split("\n"):
            if not line:
                continue
            off_s, len_s, lines_s, name, group = line.split("|", 4)
            songs.append((name, group, int(off_s), int(len_s), int(lines_s)))
        _SONGS = songs
    return _SONGS


def _song_lyrics(song):
    """Seek+read one song's lyric lines from MUSIC_FILE (one file read, cf. CLAUDE.md pitfall 7). [PRIMESUD]

    Args:
        song (int): Song index into _load_songs().

    Returns:
        list: Lyric lines, in song order.
    """
    _, _, offset, length, _ = _load_songs()[song]
    with open(MUSIC_FILE) as f:
        f.seek(offset)
        data = f.read(length)
    return data.rstrip("\n").split("\n")


# song_lookup (music.c) not ported: dead code upstream too -- no caller
# besides its own definition; do_play does its own str_prefix scan below.


def _song_prefix_match(text):
    """Return the index of the first song whose name has *text* as a prefix (cf. 1stMud do_play song scan in music.c).

    Args:
        text (str): Player-typed song name fragment (case-insensitive).

    Returns:
        int or None: Song index, or None if no song name has this prefix.
    """
    text = text.lower()
    for i, (name, group, off, length, lines) in enumerate(_load_songs()):
        if name.lower().startswith(text):
            return i
    return None


def _find_jukebox(player):
    """Find a visible jukebox in the player's room (cf. 1stMud do_play juke scan in music.c). [PRIMESUD]"""
    rs = world.rooms[player["room"]]
    for obj in rs["items"]:
        tpl = ITEM_DEFS[obj_vnum(obj)]
        if item_type(obj, tpl) == "jukebox" and can_see_obj(player, obj):
            return obj
    return None


def _do_play_list(player, juke, rest):
    """Show the jukebox's song list via the pager (cf. 1stMud do_play "list" branch in music.c).

    [PRIMESUD] 1stMud's plain "list <name>" filter is unreachable in normal
    play: the C code always consumes one word into a throwaway local before
    checking it against "artist", so a text filter only ever survives when
    it follows "artist" (filtering by group). Ported as-is -- the cmd_syntax
    banner only documents "list [artist]" anyway, matching this behaviour.
    Column layout is single-per-line via tpage [PRIMESUD] instead of
    1stMud's 2-up / 39-col grid, which does not fit the Prime's 64-col
    screen.

    Args:
        player (dict): Player state dict.
        juke (dict): Jukebox object instance.
        rest (list): Words after "list" (already lowercased).
    """
    second = rest[0] if rest else ""
    remainder = rest[1:]
    artist = second == "artist"
    match_text = " ".join(remainder).lower()
    match = bool(match_text)

    tpl = ITEM_DEFS[obj_vnum(juke)]
    short = juke.get("short_descr", tpl.get("short_descr", "it"))
    out_lines = [short + " has the following songs available:"]
    for name, group, off, length, lines in _load_songs():
        if artist:
            if match and not group.lower().startswith(match_text):
                continue
            out_lines.append(pad_right(group, 20) + " " + name)
        else:
            if match and not name.lower().startswith(match_text):
                continue
            out_lines.append(name)
    tpage(out_lines)


def do_play(player, args):
    """Play a jukebox song in the room, or queue it on the mud-wide music channel (cf. 1stMud do_play in music.c).

    Requires a visible jukebox in the room for every branch (list, loud,
    and plain song play). "loud" queues onto the [PRIMESUD] solo music
    channel -- see song_update for the room-vs-loud echo split.

    Args:
        player (dict): Player state dict.
        args (list): Parsed command arguments (already lowercased).
    """
    global _channel_lines, _room_playing
    juke = _find_jukebox(player)

    if not args:
        # cf. 1stMud cmd_syntax(ch, NULL, n_fun, "list [artist]", "[loud] <song>", NULL)
        chprintln(player, "Syntax: play list [artist]")
        chprintln(player, "        play [loud] <song>")
        chprintln(player, "Play what?")
        return

    if juke is None:
        chprintln(player, "You see nothing to play.")
        return

    arg = args[0]
    rest = args[1:]

    if arg == "list":
        _do_play_list(player, juke, rest)
        return

    loud = False
    if arg == "loud":
        args = rest
        loud = True

    if not args:
        chprintln(player, "Play what?")
        return

    if loud:
        full = _channel_songs[MAX_GLOBAL] > -1
    else:
        queue = juke.setdefault("juke_queue", [-1, -1, -1, -1])
        full = queue[3] > -1

    if full:
        chprintln(player, "The jukebox is full up right now.")
        return

    song = _song_prefix_match(" ".join(args))
    if song is None:
        chprintln(player, "That song isn't available.")
        return

    chprintln(player, "Coming right up.")

    if loud:
        for i in range(1, MAX_GLOBAL + 1):
            if _channel_songs[i] < 0:
                if i == 1:
                    _channel_songs[0] = -1
                    _channel_lines = None
                _channel_songs[i] = song
                return
    else:
        for i in range(4):
            if queue[i] < 0:
                if i == 0:
                    juke["juke_line"] = -1
                    juke.pop("juke_lines", None)
                queue[i] = song
                _room_playing = True  # [PRIMESUD] see song_update early-out
                return


def song_update():
    """Advance the loud channel and every room jukebox by one lyric line (cf. 1stMud song_update in music.c).

    Called every PULSE_MUSIC tick from update.py. Both queues advance even
    when the player is elsewhere: lines are consumed either way, matching
    upstream (which ticks every jukebox in the world regardless of who is
    nearby). [PRIMESUD] The loud channel is a mud-wide broadcast in 1stMud
    (channel_songs, heard by every connected player); collapsed to a solo
    echo here -- delivered to the player every pulse regardless of room,
    gated by the same POS_SLEEPING floor 1stMud uses for that channel. Room
    (non-loud) jukeboxes keep 1stMud's `room->person_first != NULL` gate,
    ported as "echo only if the player is actually in that room" -- 1stMud
    literally calls act() with TO_ALL there (a mud-wide send once someone
    is present to trigger it), which would reach the solo player from any
    room; narrowing it to TO_CHAR-when-present matches the documented
    room/loud split's intent instead of that broadcast quirk.
    """
    global _channel_lines, _room_playing
    if _channel_songs[1] < 0 and not _room_playing:
        # [PRIMESUD] Idle early-out: nothing queued anywhere, so skip the
        # index load and the all-rooms jukebox scan (pulse fires every 6s;
        # slot 1 empty implies the whole channel queue is empty -- fills
        # lowest-first, rotates down).
        return
    player = world.chars.get(1)
    songs = _load_songs()
    n = len(songs)

    if _channel_songs[1] >= n:
        _channel_songs[1] = -1

    if _channel_songs[1] > -1:
        cur = _channel_songs[1]
        name, group, off, length, num_lines = songs[cur]
        if _channel_songs[0] >= MAX_LINES or _channel_songs[0] >= num_lines:
            _channel_songs[0] = -1
            for i in range(1, MAX_GLOBAL):
                _channel_songs[i] = _channel_songs[i + 1]
            _channel_songs[MAX_GLOBAL] = -1
            _channel_lines = None
        else:
            if _channel_songs[0] < 0:
                buf = "Music: " + group + ", " + name
                _channel_songs[0] = 0
            else:
                if _channel_lines is None:
                    _channel_lines = _song_lyrics(cur)
                buf = "Music: '" + _channel_lines[_channel_songs[0]] + "'"
                _channel_songs[0] += 1
            # 1stMud gates the descriptor loop on COMM_NOMUSIC/COMM_QUIET
            # [PRIMESUD] not ported -- no comm flags in single-player.
            if (player is not None
                    and POS_ORDER.get(player.get("pos", "standing"), 0) >= POS_ORDER["sleeping"]):
                chprintln(player, buf)

    # [PRIMESUD] Room-only scan: the jukebox item type ships with no "take"
    # wear flag (cf. src/area_midgaard.txt vnum 3200), so it can never be
    # picked up -- 1stMud's carried_by->in_room fallback has no reachable
    # case here and is not ported.
    active = False  # [PRIMESUD] any jukebox still playing after this scan?
    if not _room_playing:
        return
    for rvnum, room in world.rooms.items():
        for obj in room.get("items", []):
            tpl = ITEM_DEFS[obj_vnum(obj)]
            if item_type(obj, tpl) != "jukebox":
                continue
            queue = obj.get("juke_queue")
            if not queue or queue[0] < 0:
                continue
            if queue[0] >= n:
                queue[0] = -1
                continue
            active = True

            cur = queue[0]
            name, group, off, length, num_lines = songs[cur]
            line_ptr = obj.get("juke_line", -1)
            here = player is not None and player.get("room") == rvnum

            if line_ptr < 0:
                if here:
                    buf = "$p starts playing " + group + ", " + name + "."
                    act(buf, player, obj, None, TO_CHAR)
                obj["juke_line"] = 0
                continue

            if line_ptr >= MAX_LINES or line_ptr >= num_lines:
                obj["juke_line"] = -1
                obj.pop("juke_lines", None)
                queue[0] = queue[1]
                queue[1] = queue[2]
                queue[2] = queue[3]
                queue[3] = -1
                continue

            lyrics = obj.get("juke_lines")
            if lyrics is None:
                lyrics = _song_lyrics(cur)
                obj["juke_lines"] = lyrics
            line = lyrics[line_ptr]
            obj["juke_line"] = line_ptr + 1

            if here:
                buf = "$p bops: '" + line + "'"
                act(buf, player, obj, None, TO_CHAR)

    _room_playing = active

