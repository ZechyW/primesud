"""Tests for the binary KX01 keyword indexes (mobs.bin / objs.bin). [PRIMESUD]"""

import debug
import keyidx
import magic
import world
from handler import is_name
from tools import build_mob_index


def _row(vnum, keywords, name="", level=0, home="alpha", tags=("alpha",)):
    """One index row dict in pack_key_index's input shape."""
    return {"vnum": vnum, "level": level, "home": home, "keywords": keywords,
            "name": name, "tags": list(tags)}


def _pack(rows, tags=None):
    return build_mob_index.pack_key_index(list(rows), tags)


def _record_offsets(data, meta):
    """Absolute record offsets in file order (the walk consumers do)."""
    offsets = []
    pos = meta[0]
    while pos < meta[1]:
        offsets.append(pos)
        pos += 11 + data[pos + 10]
    return offsets


def _parsed(blob):
    """(data, meta) for an in-memory blob, as load() would return it."""
    return blob, keyidx._parse_header(blob)


def _match_indexes(blob, target):
    """Row indexes candidates() reports for target."""
    data, meta = _parsed(blob)
    offsets = _record_offsets(data, meta)
    return [offsets.index(pos) for pos in keyidx.candidates(data, meta,
                                                            target)]


def _naive_indexes(rows, target):
    """Reference: is_name over every row's keywords, in file order."""
    return [index for index, row in enumerate(rows)
            if is_name(target, row["keywords"])]


# -- format round trip ------------------------------------------------------

def test_pack_parse_round_trip():
    rows = [
        _row(100, "guard city", "a city guard", 12, "alpha", ["alpha"]),
        _row(101, "GUARD Captain", "the captain", 20, "alpha",
             ["alpha", "beta"]),
        _row(102, "rat", "a rat", 1, "beta", []),
        _row(103, "", "", 0, "beta", ["beta"]),
    ]
    parsed, tags = build_mob_index.parse_key_index(_pack(rows))
    assert tags == ["alpha", "beta"]
    # keywords come back lowercased; everything else round trips verbatim
    assert parsed == [dict(row, keywords=row["keywords"].lower())
                      for row in rows]


def test_pack_layout_invariants():
    rows = [_row(1, "Alpha One", "first"), _row(2, "beta", "second"),
            _row(3, "alpha two", "third")]
    blob = _pack(rows)
    data, meta = _parsed(blob)
    records_off, kw_off, strings_off, count, tags = meta
    assert count == 3 and tags == ["alpha"]
    assert blob[kw_off] == 10  # leading separator keeps hit-1 in bounds
    kwblob = blob[kw_off:strings_off]
    assert kwblob == kwblob.lower()
    assert kwblob == b"\nalpha one\nbeta\nalpha two"
    # record kw offsets ascend with record order -- the two-pointer walk
    # in keyidx.candidates depends on it
    starts = [data[pos + 4] | data[pos + 5] << 8
              for pos in _record_offsets(data, meta)]
    assert starts == sorted(starts) and starts[0] == 1
    # display strings are deduplicated, empties included
    assert blob[strings_off:] == b"firstsecondthird"


def test_shipped_indexes_keep_generator_invariants():
    """The shipped files carry the order and tag table the runtime assumes."""
    area_tags = [entry[1] for entry in world._AREA_FILES]
    order = {tag: index for index, tag in enumerate(area_tags)}
    with open("mobs.bin", "rb") as f:
        mob_rows, mob_tags = build_mob_index.parse_key_index(f.read())
    with open("objs.bin", "rb") as f:
        obj_rows, obj_tags = build_mob_index.parse_key_index(f.read())
    assert mob_tags == area_tags and obj_tags == area_tags

    # mobs: cheapest spawning area first, then vnum ascending
    keys = [(order[(row["tags"] or [row["home"]])[0]], row["vnum"])
            for row in mob_rows]
    assert keys == sorted(keys)
    # objects: areas in _AREA_FILES order, vnums ascending within an area,
    # keyword-less templates dropped
    obj_keys = [(order[row["home"]], row["vnum"]) for row in obj_rows]
    assert obj_keys == sorted(obj_keys)
    assert all(row["keywords"] for row in obj_rows)
    assert all(row["level"] == 0 and row["name"] == "" for row in obj_rows)


# -- loader tolerance -------------------------------------------------------

def test_load_returns_none_for_missing_or_corrupt_files(tmp_path):
    assert keyidx.load(str(tmp_path / "absent.bin")) is None
    blob = _pack([_row(1, "guard")])
    cases = {
        "garbage.bin": b"this is not an index at all",
        "magic.bin": b"XX01" + blob[4:],
        "truncated.bin": blob[:9],
        "short.bin": b"KX0",
        "empty.bin": b"",
        # header claims a string table past the end of the file
        "overrun.bin": blob[:10] + b"\xff\xff\xff\xff" + blob[14:],
    }
    for name, payload in cases.items():
        path = tmp_path / name
        path.write_bytes(payload)
        assert keyidx.load(str(path)) is None, name


def test_consumers_degrade_without_an_index(monkeypatch, tmp_path):
    missing = str(tmp_path / "absent.bin")
    monkeypatch.setattr(magic, "OBJ_INDEX_FILE", missing)
    monkeypatch.setattr(magic, "MOB_INDEX_FILE", missing)
    assert magic._locate_candidate_areas("sword") == []
    assert magic._find_unloaded_mob("guard", {"level": 1}) == (None, None)
    lines = []
    debug._find_idx("guard", missing, lines)
    assert lines == []


# -- search semantics -------------------------------------------------------

_SEARCH_ROWS = [
    _row(1, "guard city", "a city guard"),
    _row(2, "guardian statue", "a statue"),
    _row(3, "sword silver long", "a silver sword"),
    _row(4, "gu", "a gu"),
    _row(5, "rat", "a rat"),
    _row(6, "the guard captain", "the captain"),
    _row(7, "sword", "a plain sword"),
]


def test_candidates_matches_naive_is_name():
    blob = _pack(_SEARCH_ROWS)
    targets = [
        "guard",            # exact keyword, hits first and later records
        "gua",              # prefix hit across two records
        "guardian",         # longer than one record's keyword
        "ard",              # mid-word: must NOT match "guard"
        "GuArD",            # case-insensitive
        "silver sword",     # multi-word, both words present
        "sword shield",     # second word absent -> miss
        "'guard'",          # quoted first word (is_name rejects it)
        "guard city",       # multi-word on one record
        "city guard",       # first word not the leading keyword
        "gu",               # shared prefix across records incl. an exact one
        "rat",              # last-but-one record
        "sword",            # hits the final record too
        "xyzzyq",           # miss: full sweep, no hits
        "",                 # empty target
    ]
    for target in targets:
        assert _match_indexes(blob, target) == _naive_indexes(
            _SEARCH_ROWS, target), target


def test_whitespace_only_target_matches_nothing():
    """[PRIMESUD] The one deviation from bare is_name: a fragment of only
    whitespace splits to no words, which is_name treats as "matches every
    record". Command paths always pass parsed words, so nothing can reach
    it; the scan returns no candidates rather than the whole file."""
    blob = _pack(_SEARCH_ROWS)
    assert _match_indexes(blob, "   ") == []
    assert _naive_indexes(_SEARCH_ROWS, "   ") == list(
        range(len(_SEARCH_ROWS)))


def test_candidates_finds_first_and_last_records():
    rows = [_row(1, "alpha"), _row(2, "filler"), _row(3, "alpha")]
    blob = _pack(rows)
    assert _match_indexes(blob, "alpha") == [0, 2]


def test_candidates_on_shipped_indexes_matches_naive():
    with open("mobs.bin", "rb") as f:
        mob_blob = f.read()
    with open("objs.bin", "rb") as f:
        obj_blob = f.read()
    mob_rows, _tags = build_mob_index.parse_key_index(mob_blob)
    obj_rows, _tags = build_mob_index.parse_key_index(obj_blob)
    for target in ("guard", "the", "sword", "guard city", "gu",
                   "qqxzzy nothing"):
        assert _match_indexes(mob_blob, target) == _naive_indexes(
            mob_rows, target), target
        assert _match_indexes(obj_blob, target) == _naive_indexes(
            obj_rows, target), target
    # sanity: the reference is not vacuously empty
    assert _naive_indexes(mob_rows, "guard")
    assert _naive_indexes(obj_rows, "sword")

    # Sweep real keywords: exact, three-letter prefix, upper-cased last
    # word and a two-word target, sampled deterministically across both
    # files (the full ~5,000-target sweep passes too, just slowly).
    for blob, rows in ((mob_blob, mob_rows), (obj_blob, obj_rows)):
        targets = set()
        for row in rows[::17]:
            words = row["keywords"].split()
            if not words:
                continue
            targets.add(words[0])
            targets.add(words[0][:3])
            targets.add(words[-1].upper())
            if len(words) > 1:
                targets.add(words[0] + " " + words[1])
        for target in sorted(targets):
            assert _match_indexes(blob, target) == _naive_indexes(
                rows, target), target


# -- consumers against the shipped data -------------------------------------

def test_locate_candidate_areas_keeps_stored_tag_order(monkeypatch):
    # Real static tables, but nothing loaded and no deferred room items, so
    # the shipped index alone decides the candidate list.
    monkeypatch.setattr(world, "_LOADED_AREAS", set())
    monkeypatch.setattr(world, "_pending_room_items", {})
    with open("objs.bin", "rb") as f:
        rows, _tags = build_mob_index.parse_key_index(f.read())
    for target in ("sword", "silver sword", "the", "qqxzzy"):
        expected = []
        for row in rows:
            if is_name(target, row["keywords"]):
                for tag in row["tags"]:
                    if tag not in expected:
                        expected.append(tag)
        assert magic._locate_candidate_areas(target) == expected, target


def test_find_unloaded_mob_keeps_area_priority_order(monkeypatch):
    monkeypatch.setattr(world, "_LOADED_AREAS", set())
    monkeypatch.setattr(world, "chars", {})
    area_tags = [entry[1] for entry in world._AREA_FILES]
    with open("mobs.bin", "rb") as f:
        rows, tags = build_mob_index.parse_key_index(f.read())
    assert tags == area_tags
    for target in ("guard", "cityguard"):
        expected = []
        for row in rows:
            if is_name(target, row["keywords"]):
                for tag in row["tags"]:
                    if tag not in expected:
                        expected.append(tag)
        expected.sort(key=lambda tag: area_tags.index(tag))
        loaded = []
        monkeypatch.setattr(world, "_ensure_area_by_tag", loaded.append)
        # No instance ever spawns, so the two-load cap stops the walk after
        # the two cheapest candidate areas.
        assert magic._find_unloaded_mob(target, {"level": 1}) == (None, None)
        assert loaded == expected[:2], target
