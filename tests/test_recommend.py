"""Tests for zero-load mob and gear recommendations. [PRIMESUD]"""

from pathlib import Path

import pytest

import commands
import inventory
import recommend
import world
from handler import _char_base
from skills_table import WEAPON_GSN_MAP
from tools import build_mob_index


def _player(level=10, room=1):
    player = _char_base()
    player.update({
        "id": 1, "room": room, "level": level, "alignment": 0,
        "gold": 0, "silver": 0, "learned": {}, "inv": [], "equip": {},
        "quest_status": 0, "quest_mob": 0,
    })
    return player


def _fight_row(vnum, level, name, tags="test"):
    return str(vnum) + "|" + str(level) + "|" + name + "|" + tags


def _write_foes_idx(path, rows):
    """Write rows in the level-segmented foes.idx layout."""
    def _row_level(row):
        try:
            return max(0, int(row.split("|")[1]))
        except (IndexError, ValueError):
            return 0
    ordered = sorted(rows, key=_row_level)
    top = max([_row_level(row) for row in ordered], default=0)
    sizes = [0] * (top + 1)
    blob = ""
    for row in ordered:
        line = row + "\n"
        sizes[_row_level(row)] += len(line)
        blob += line
    path.write_bytes(("# test foes.idx\n"
                      + ",".join(str(size) for size in sizes) + "\n"
                      + blob).encode())


def _gear_row(vnum, slot="body", level=1, score=100, kind="floor",
              source_vnum=0, source_level=0, room=1, source="Test Room",
              tag="test", price=0, flags="", weapon_base=0,
              weapon_type="", sharp=0, weight=0):
    return "|".join((
        str(vnum), slot, str(level), str(score), str(weapon_base),
        weapon_type, str(sharp), str(weight), flags, kind,
        str(source_level), str(source_vnum), str(room), tag, str(price),
        "item " + str(vnum), source,
    ))


def _write_gear_idx(path, rows):
    """Write rows in the segmented gear.idx layout (malformed rows -> body)."""
    segments = {slot: [] for slot in recommend._GEAR_SLOTS}
    for row in rows:
        parts = row.split("|")
        slot = parts[1] if len(parts) > 1 and parts[1] in segments else "body"
        segments[slot].append(row + "\n")
    blobs = ["".join(segments[slot]) for slot in recommend._GEAR_SLOTS]
    path.write_bytes(("# test gear.idx\n"
                      + ",".join(str(len(blob)) for blob in blobs) + "\n"
                      + "".join(blobs)).encode())


@pytest.fixture
def indexed_player(fresh_world):
    fresh_world.register_area(
        "test", 1, 99,
        rooms={1: {"name": "Test Room", "flags": {}, "exits": {}}})
    fresh_world.setup()
    return _player()


@pytest.fixture
def capture(monkeypatch):
    pages = []
    lines = []
    monkeypatch.setattr(recommend, "tpage", lambda value: pages.append(value))
    monkeypatch.setattr(recommend, "chprintln",
                        lambda _player, value: lines.append(value))
    return pages, lines


def test_bare_picker_routes_and_cancel(indexed_player, monkeypatch):
    calls = []
    monkeypatch.setattr(recommend, "_show_mobs",
                        lambda player: calls.append(("mobs", player)))
    monkeypatch.setattr(recommend, "_show_gear",
                        lambda player: calls.append(("gear", player)))

    monkeypatch.setattr(recommend, "pick_from", lambda *_args: 0)
    assert recommend.do_recommend(indexed_player, []) == "recommend mobs"
    monkeypatch.setattr(recommend, "pick_from", lambda *_args: 1)
    assert recommend.do_recommend(indexed_player, []) == "recommend gear"
    monkeypatch.setattr(recommend, "pick_from", lambda *_args: -1)
    assert recommend.do_recommend(indexed_player, []) is None
    assert [call[0] for call in calls] == ["mobs", "gear"]


def test_command_registration_keeps_existing_prefix_order():
    names = [entry[0] for entry in commands._CMD_TABLE]
    assert names.index("recall") < names.index("recommend")
    assert next(entry[0] for entry in commands._CMD_TABLE
                if entry[0].startswith("rec")) == "recite"
    assert next(entry[0] for entry in commands._CMD_TABLE
                if entry[0].startswith("reco")) == "recommend"


def test_mob_window_widens_lower_only(indexed_player, tmp_path, monkeypatch):
    path = tmp_path / "foes.idx"
    _write_foes_idx(path, (
        _fight_row(100, 11, "upper"),
        _fight_row(101, 10, "same"),
        _fight_row(102, 9, "lower one"),
        _fight_row(103, 8, "lower two"),
        _fight_row(104, 7, "widened"),
        _fight_row(105, 5, "limit"),
        _fight_row(106, 12, "too high"),
        _fight_row(107, 4, "too low"),
    ))
    monkeypatch.setattr(recommend, "FOES_INDEX_FILE", str(path))

    rows = recommend._mob_candidates(indexed_player)

    assert {row["vnum"] for row in rows} == {100, 101, 102, 103, 104}
    assert all(row["level"] <= 11 for row in rows)


def test_mob_filters_empty_tags_quest_and_malformed(
        indexed_player, tmp_path, monkeypatch):
    indexed_player["quest_status"] = recommend.QUEST_FINDMOB
    indexed_player["quest_mob"] = 102
    path = tmp_path / "foes.idx"
    _write_foes_idx(path, (
        "100|10|too few",
        "101|10|no fight|",
        _fight_row(102, 10, "protected"),
        _fight_row(103, 10, "eligible"),
        "bad|10|broken|test",
    ))
    monkeypatch.setattr(recommend, "FOES_INDEX_FILE", str(path))

    assert [row["vnum"] for row in
            recommend._mob_candidates(indexed_player)] == [103]


def test_mob_ranking_record_current_area_and_no_load(
        indexed_player, tmp_path, monkeypatch):
    path = tmp_path / "foes.idx"
    _write_foes_idx(path, (
        _fight_row(100, 10, "far", "far"),
        _fight_row(101, 10, "current", "test"),
        _fight_row(102, 10, "bad", "test"),
    ))
    world.mob_stats[102] = [2, 0]
    monkeypatch.setattr(recommend, "FOES_INDEX_FILE", str(path))
    monkeypatch.setattr(world, "_ensure_area_by_tag",
                        lambda *_args: pytest.fail("area loaded"))
    before = set(world._LOADED_AREAS)

    rows = recommend._mob_candidates(indexed_player)

    assert [row["vnum"] for row in rows] == [101, 100, 102]
    assert world._LOADED_AREAS == before


def test_corrupt_foes_directory_fails_softly(indexed_player, tmp_path,
                                              monkeypatch, capture):
    pages, lines = capture
    path = tmp_path / "foes.idx"
    path.write_bytes(b"# header only, no directory line")
    monkeypatch.setattr(recommend, "FOES_INDEX_FILE", str(path))
    recommend.do_recommend(indexed_player, ["mobs"])

    path.write_bytes(b"# header\nnot,numbers,here\n")
    recommend.do_recommend(indexed_player, ["mobs"])

    assert pages == []
    assert lines == ["Mob recommendations are unavailable."] * 2


def test_missing_indexes_fail_softly(indexed_player, tmp_path, monkeypatch,
                                     capture):
    pages, lines = capture
    monkeypatch.setattr(recommend, "FOES_INDEX_FILE",
                        str(tmp_path / "missing-foes.idx"))
    monkeypatch.setattr(recommend, "GEAR_INDEX_FILE",
                        str(tmp_path / "missing-gear.idx"))

    recommend.do_recommend(indexed_player, ["mobs"])
    recommend.do_recommend(indexed_player, ["gear"])

    assert pages == []
    assert lines == [
        "Mob recommendations are unavailable.",
        "Gear recommendations are unavailable.",
    ]


def test_corrupt_gear_directory_fails_softly(indexed_player, tmp_path,
                                             monkeypatch, capture):
    pages, lines = capture
    path = tmp_path / "gear.idx"
    path.write_bytes(b"# header only, no directory line")
    monkeypatch.setattr(recommend, "GEAR_INDEX_FILE", str(path))
    recommend.do_recommend(indexed_player, ["gear"])

    path.write_bytes(b"# header\nnot,numbers,here\n")
    recommend.do_recommend(indexed_player, ["gear"])

    assert pages == []
    assert lines == ["Gear recommendations are unavailable."] * 2


@pytest.mark.parametrize("proficiency", (0, 50, 100))
def test_indexed_weapon_score_matches_fresh_instance(
        indexed_player, proficiency):
    template = {
        "type": "weapon", "weapon_type": "sword", "dice": (2, 6, 1),
        "weapon_flags": {"sharp": True, "flaming": True},
        "wear_flags": {"take": True, "wield": True},
        "level": 12, "stat_bonuses": {"damroll": 2},
    }
    world.ITEM_DEFS._data[500] = template
    indexed_player["learned"][WEAPON_GSN_MAP["sword"]] = proficiency
    static, base, weapon_type, sharp = inventory.gear_score_components(
        template)

    assert (static + inventory.gear_score_weapon(
        indexed_player, base, weapon_type, sharp)
            == inventory.gear_score(indexed_player, {"vnum": 500}))


def test_gear_downweights_unlearnt_weapon(indexed_player, tmp_path,
                                          monkeypatch):
    """Expected-hit weighting ranks a learnt weapon over bigger unlearnt dice."""
    path = tmp_path / "gear.idx"
    _write_gear_idx(path, (
        _gear_row(600, slot="wield", score=0, weapon_base=20,
                  weapon_type="sword"),
        _gear_row(601, slot="wield", score=0, weapon_base=10,
                  weapon_type="dagger"),
    ))
    monkeypatch.setattr(recommend, "GEAR_INDEX_FILE", str(path))
    indexed_player["learned"][WEAPON_GSN_MAP["dagger"]] = 80

    rows = recommend._scan_gear(indexed_player, "wield")["wield"]

    # dagger 10 base at 80% scores 85; sword 20 base at 0% only 11
    assert [row["vnum"] for row in rows] == [601, 600]
    assert [row["gain"] for row in rows] == [85, 11]


def test_two_hander_pays_owned_shield_cost(indexed_player, tmp_path,
                                           monkeypatch):
    """A two-hander row is charged for the shield it would force off."""
    world.ITEM_DEFS._data[500] = {
        "type": "armor", "wear_flags": {"take": True, "shield": True},
        "level": 1, "armor": (5, 5, 5, 5),
    }
    indexed_player["inv"] = [{"vnum": 500}]
    indexed_player["learned"][WEAPON_GSN_MAP["sword"]] = 80
    path = tmp_path / "gear.idx"
    _write_gear_idx(path, (
        _gear_row(600, slot="wield", score=0, weapon_base=20,
                  weapon_type="sword"),
        _gear_row(601, slot="wield", score=0, weapon_base=20,
                  weapon_type="sword", flags="two_hands"),
    ))
    monkeypatch.setattr(recommend, "GEAR_INDEX_FILE", str(path))

    rows = recommend._scan_gear(indexed_player, "wield")["wield"]
    # both score 171; the 2H gains the no-shield 10% but pays half the
    # owned shield (200) plus its block value
    assert [row["vnum"] for row in rows] == [600, 601]

    indexed_player["inv"] = []
    rows = recommend._scan_gear(indexed_player, "wield")["wield"]
    # no shield owned: nothing to forfeit, the no-shield bonus leads
    assert [row["vnum"] for row in rows] == [601, 600]


def test_owned_two_hander_baseline_pays_shield_cost(indexed_player):
    """Owned two-hander baselines use the same shield economics as rows."""
    world.ITEM_DEFS._data[500] = {
        "type": "armor", "wear_flags": {"take": True, "shield": True},
        "level": 1, "armor": (5, 5, 5, 5),
    }
    world.ITEM_DEFS._data[501] = {
        "type": "weapon", "wear_flags": {"take": True, "wield": True},
        "level": 1, "weapon_type": "sword", "dice": (2, 9, 0),
        "weapon_flags": {"two_hands": True},
    }
    indexed_player["inv"] = [{"vnum": 500}, {"vnum": 501}]
    indexed_player["learned"][WEAPON_GSN_MAP["sword"]] = 80

    baselines = recommend._owned_baselines(indexed_player)

    # weapon 171 + 17 no-shield bonus - (shield 200 + block 5) // 2
    assert baselines["shield"] == 200
    assert baselines["wield"] == 86


def test_runtime_owned_affect_suppresses_index_candidate(
        indexed_player, tmp_path, monkeypatch):
    world.ITEM_DEFS._data[500] = {
        "type": "armor", "wear_flags": {"take": True, "body": True},
        "level": 1, "armor": (0, 0, 0, 0), "stat_bonuses": {"damroll": 99},
    }
    indexed_player["inv"] = [{
        "vnum": 500, "enchanted": True,
        "affect_list": [{"where": "to_object", "location": "damroll",
                         "modifier": 10, "bitvector": ""}],
    }]
    path = tmp_path / "gear.idx"
    _write_gear_idx(path, [_gear_row(600, score=150)])
    monkeypatch.setattr(recommend, "GEAR_INDEX_FILE", str(path))

    assert recommend._scan_gear(indexed_player)["body"] == []


def test_paired_baseline_uses_weaker_owned_position(indexed_player):
    for vnum, score in ((500, 3), (501, 1)):
        world.ITEM_DEFS._data[vnum] = {
            "type": "jewelry", "wear_flags": {"take": True, "finger": True},
            "level": 1, "stat_bonuses": {"hitroll": score},
        }
    indexed_player["inv"] = [{"vnum": 500}, {"vnum": 501}]

    assert recommend._owned_baselines(indexed_player)["finger"] == 10


def test_gear_filters_and_source_order(indexed_player, tmp_path, monkeypatch):
    indexed_player["gold"] = 1
    path = tmp_path / "gear.idx"
    _write_gear_idx(path, (
        _gear_row(600, score=200, kind="shop", source_vnum=10,
                  source="shop", price=100, tag="far"),
        _gear_row(600, score=200, kind="floor", source="floor",
                  tag="test"),
        _gear_row(601, score=190, kind="loot", source_vnum=20,
                  source_level=12, source="too strong"),
        _gear_row(602, score=180, flags="anti_neutral"),
        "malformed|row",
    ))
    monkeypatch.setattr(recommend, "GEAR_INDEX_FILE", str(path))
    before = set(world._LOADED_AREAS)

    rows = recommend._scan_gear(indexed_player)["body"]

    assert len(rows) == 1
    assert rows[0]["vnum"] == 600
    assert rows[0]["kind"] == "floor"
    assert [alt["kind"] for alt in rows[0]["alts"]] == ["shop"]
    assert world._LOADED_AREAS == before


def test_alt_sources_dedupe_rendered_identity(indexed_player, tmp_path,
                                              monkeypatch):
    # Rows 1 and 3 render identically (same mob, same area, rooms unshown):
    # the later, better-ranked room demotes the first and must not keep it
    # (or drop the distinct thug) as an "also" line.
    path = tmp_path / "gear.idx"
    _write_gear_idx(path, (
        _gear_row(600, score=200, kind="loot", source_vnum=20,
                  source_level=10, room=2, source="a cityguard"),
        _gear_row(600, score=200, kind="loot", source_vnum=21,
                  source_level=10, room=3, source="a thug"),
        _gear_row(600, score=200, kind="loot", source_vnum=20,
                  source_level=10, room=1, source="a cityguard"),
    ))
    monkeypatch.setattr(recommend, "GEAR_INDEX_FILE", str(path))

    rows = recommend._scan_gear(indexed_player, "body")["body"]

    assert len(rows) == 1
    assert rows[0]["source_vnum"] == 20 and rows[0]["kind"] == "loot"
    assert rows[0]["source_key"][-1] == 1  # demoted to the room-1 site
    assert [alt["source_vnum"] for alt in rows[0]["alts"]] == [21]


def test_banded_gear_segment_breaks_and_jumps(indexed_player, tmp_path,
                                              monkeypatch):
    # Band headers drive the shortcuts: a bound below the baseline jumps
    # past the band's remaining (bound-sorted) rows, and a band above the
    # player's level ends the segment even if a mislabeled row inside
    # would have been eligible.
    def _seg(*rows):
        return "".join(row + "\n" for row in rows)

    band0 = _seg(_gear_row(600, score=150),
                 _gear_row(601, score=0),
                 _gear_row(602, score=120))
    band5 = _seg(_gear_row(603, score=130, level=5))
    band15 = _seg(_gear_row(604, score=999, level=1))
    body = ("@0|" + str(len(band0)) + "\n" + band0
            + "@5|" + str(len(band5)) + "\n" + band5
            + "@15|" + str(len(band15)) + "\n" + band15)
    blobs = ["" for _slot in recommend._GEAR_SLOTS]
    blobs[recommend._GEAR_SLOTS.index("body")] = body
    path = tmp_path / "gear.idx"
    path.write_bytes(("# test gear.idx\n"
                      + ",".join(str(len(blob)) for blob in blobs) + "\n"
                      + "".join(blobs)).encode())
    monkeypatch.setattr(recommend, "GEAR_INDEX_FILE", str(path))

    rows = recommend._scan_gear(indexed_player, "body")["body"]

    # 602 sits after the 601 bound-jump; 604 sits past the level break.
    assert [row["vnum"] for row in rows] == [600, 603]


def test_wield_type_header_skips_unlearnt_type(indexed_player, tmp_path,
                                               monkeypatch):
    """An unlearnt type's sub-segment is skipped from header arithmetic
    alone -- its mislabeled monster row is never parsed."""
    world.ITEM_DEFS._data[500] = {
        "type": "weapon", "wear_flags": {"take": True, "wield": True},
        "level": 1, "weapon_type": "dagger", "dice": (2, 4, 0),
    }
    indexed_player["inv"] = [{"vnum": 500}]
    indexed_player["learned"][WEAPON_GSN_MAP["dagger"]] = 80

    sword = _gear_row(600, slot="wield", score=0, weapon_base=1000,
                      weapon_type="sword") + "\n"
    dagger = _gear_row(601, slot="wield", score=0, weapon_base=12,
                       weapon_type="dagger") + "\n"
    band = ("@=dagger|0|144|" + str(len(dagger)) + "\n" + dagger
            + "@=sword|0|240|" + str(len(sword)) + "\n" + sword)
    wield = "@0|" + str(len(band)) + "\n" + band
    blobs = ["" for _slot in recommend._GEAR_SLOTS]
    blobs[recommend._GEAR_SLOTS.index("wield")] = wield
    path = tmp_path / "gear.idx"
    path.write_bytes(("# test gear.idx\n"
                      + ",".join(str(len(blob)) for blob in blobs) + "\n"
                      + "".join(blobs)).encode())
    monkeypatch.setattr(recommend, "GEAR_INDEX_FILE", str(path))

    rows = recommend._scan_gear(indexed_player, "wield")["wield"]

    # The sword header's adept bound 240 rescales to ~11 at unlearnt skill:
    # below the owned-dagger floor 86, so the wb-1000 row inside is skipped
    # unparsed. The learnt dagger row scores 102 for a 17 gain.
    assert [row["vnum"] for row in rows] == [601]
    assert rows[0]["gain"] == 17


def test_loot_band_outside_window_skips_unparsed(indexed_player, tmp_path,
                                                 monkeypatch):
    """An @@source-level band that cannot intersect the loot window is
    skipped whole -- its mislabeled in-window row is never parsed."""
    low = _gear_row(600, score=500, kind="loot", source_vnum=20,
                    source_level=10, source="mislabeled mob") + "\n"
    ok = _gear_row(601, score=150, kind="loot", source_vnum=21,
                   source_level=10, source="a fair fight") + "\n"
    body = ("@@0|" + str(len(low)) + "\n" + low
            + "@@10|" + str(len(ok)) + "\n" + ok)
    blobs = ["" for _slot in recommend._GEAR_SLOTS]
    blobs[recommend._GEAR_SLOTS.index("body")] = body
    path = tmp_path / "gear.idx"
    path.write_bytes(("# test gear.idx\n"
                      + ",".join(str(len(blob)) for blob in blobs) + "\n"
                      + "".join(blobs)).encode())
    monkeypatch.setattr(recommend, "GEAR_INDEX_FILE", str(path))

    rows = recommend._scan_gear(indexed_player, "body")["body"]

    # Player L10 window is [8, 11]: the @@0 band (sources 0-4) is jumped
    # even though the row inside claims source level 10; @@10 scans.
    assert [row["vnum"] for row in rows] == [601]


def test_full_results_raise_skip_floor(indexed_player, tmp_path, monkeypatch):
    """A full ten-row slot raises the jump floor to the weakest kept score:
    rows bounded below it jump the band (the mislabeled 200 is never
    parsed), while an equal-bound alternate source of a kept item still
    lands in its alts."""
    rows = [_gear_row(600 + index, score=111 - index)
            for index in range(10)]                      # gains 111..102
    rows.append(_gear_row(609, score=102, kind="shop", source_vnum=10,
                          source="shop"))
    rows.append(_gear_row(620, score=101))
    rows.append(_gear_row(699, score=200))
    band = "".join(row + "\n" for row in rows)
    body = "@0|" + str(len(band)) + "\n" + band
    blobs = ["" for _slot in recommend._GEAR_SLOTS]
    blobs[recommend._GEAR_SLOTS.index("body")] = body
    path = tmp_path / "gear.idx"
    path.write_bytes(("# test gear.idx\n"
                      + ",".join(str(len(blob)) for blob in blobs) + "\n"
                      + "".join(blobs)).encode())
    monkeypatch.setattr(recommend, "GEAR_INDEX_FILE", str(path))

    kept = recommend._scan_gear(indexed_player, "body")["body"]

    assert [row["vnum"] for row in kept] == list(range(600, 610))
    assert len(kept[9]["alts"]) == 1  # the tied second source of 609 parsed
    # 620's bound 101 < floor 102 jumped the band; 699 was never seen.
    assert all(row["vnum"] != 699 for row in kept)


def test_summary_scan_chunks_contiguous_reads(indexed_player, tmp_path,
                                              monkeypatch):
    """Summary mode packs consecutive segments into bounded chunk reads."""
    path = tmp_path / "gear.idx"
    _write_gear_idx(path, [
        _gear_row(600 + index, slot=slot, score=100)
        for index, slot in enumerate(recommend._GEAR_SLOTS)])
    monkeypatch.setattr(recommend, "GEAR_INDEX_FILE", str(path))

    reads = []
    real_open = open

    class _CountingFile:
        def __init__(self, handle):
            self._handle = handle

        def read(self, *args):
            reads.append(args)
            return self._handle.read(*args)

        def seek(self, *args):
            return self._handle.seek(*args)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return self._handle.__exit__(*args)

    monkeypatch.setattr(recommend, "open",
                        lambda name: _CountingFile(real_open(name)),
                        raising=False)

    results = recommend._scan_gear(indexed_player)
    assert len(reads) == 2  # header + one chunk spanning all 16 segments
    assert all(len(results[slot]) == 1 for slot in recommend._GEAR_SLOTS)

    # A tiny chunk budget degrades to per-segment reads, same results.
    monkeypatch.setattr(recommend, "_CHUNK", 1)
    del reads[:]
    results = recommend._scan_gear(indexed_player)
    assert len(reads) == 1 + len(recommend._GEAR_SLOTS)
    assert all(len(results[slot]) == 1 for slot in recommend._GEAR_SLOTS)


def test_headers_never_change_results_on_shipped_index(indexed_player,
                                                       tmp_path, monkeypatch):
    """Band/type headers are pure perf: scanning the shipped index with all
    @ lines stripped (no jumps, no type skips, no early-stop shortcuts on
    sorted data) yields identical results for varied player profiles."""
    source = Path("gear.idx").read_text()
    directory, body = source.split("\n", 2)[1:]
    sizes = [int(value) for value in directory.split(",")]
    offset = 0
    stripped = []
    for size in sizes:
        segment = body[offset:offset + size]
        offset += size
        stripped.append("".join(
            line + "\n" for line in segment.splitlines()
            if line and not line.startswith("@")))
    flat = tmp_path / "gear_flat.idx"
    flat.write_bytes(("# flat\n"
                      + ",".join(str(len(blob)) for blob in stripped)
                      + "\n" + "".join(stripped)).encode())

    profiles = (
        (5, {}),
        (12, {WEAPON_GSN_MAP["sword"]: 80}),
        (35, {WEAPON_GSN_MAP["dagger"]: 100, WEAPON_GSN_MAP["mace"]: 40}),
    )
    for level, learned in profiles:
        player = _player(level=level)
        player["learned"] = learned
        for slot in (None, "wield", "body"):
            monkeypatch.setattr(recommend, "GEAR_INDEX_FILE", "gear.idx")
            with_headers = recommend._scan_gear(player, slot)
            monkeypatch.setattr(recommend, "GEAR_INDEX_FILE", str(flat))
            assert recommend._scan_gear(player, slot) == with_headers


def test_gear_detail_is_bounded_to_ten(indexed_player, tmp_path, monkeypatch):
    path = tmp_path / "gear.idx"
    _write_gear_idx(path, [
        _gear_row(600 + index, score=100 + index)
        for index in range(12)])
    monkeypatch.setattr(recommend, "GEAR_INDEX_FILE", str(path))

    rows = recommend._scan_gear(indexed_player, "body")["body"]

    assert len(rows) == 10
    assert [row["gain"] for row in rows] == list(range(111, 101, -1))


def test_mob_multi_area_marker(indexed_player, tmp_path, monkeypatch,
                               capture):
    pages, _lines = capture
    path = tmp_path / "foes.idx"
    _write_foes_idx(path, (
        _fight_row(100, 10, "roamer", "far,test"),
        _fight_row(101, 10, "homebody", "test"),
    ))
    monkeypatch.setattr(recommend, "FOES_INDEX_FILE", str(path))

    recommend._show_mobs(indexed_player)

    body = pages[0][1:3]
    assert any(line.rstrip().endswith("+1") for line in body)
    assert not all(line.rstrip().endswith("+1") for line in body)


def test_gear_summary_picker_drills_to_slot(indexed_player, tmp_path,
                                            monkeypatch, capture):
    pages, _lines = capture
    path = tmp_path / "gear.idx"
    _write_gear_idx(path, (
        _gear_row(600, score=200, kind="floor", source="floor", tag="test"),
        _gear_row(600, score=200, kind="shop", source_vnum=10, source="shop",
                  price=100, tag="far"),
    ))
    monkeypatch.setattr(recommend, "GEAR_INDEX_FILE", str(path))
    monkeypatch.setattr(recommend, "pick_from", lambda *_args: 0)

    assert recommend.do_recommend(indexed_player, ["gear"]) == (
        "recommend gear body")
    assert any(line.startswith("  also buy from shop")
               for line in pages[0])

    monkeypatch.setattr(recommend, "pick_from", lambda *_args: -1)
    assert recommend.do_recommend(indexed_player, ["gear"]) is None


def test_generator_emits_fight_tags_and_all_source_kinds(
        fresh_world, tmp_path, monkeypatch):
    rooms = {
        100: {"name": "Field", "flags": {}, "exits": {}},
        101: {"name": "Shop", "flags": {}, "exits": {}},
        102: {"name": "Floor", "flags": {}, "exits": {}},
        103: {"name": "Sanctuary", "flags": {"safe": True}, "exits": {}},
    }
    mobiles = {
        100: {"keywords": "fighter", "short_descr": "a fighter",
              "race": "human", "level": 10},
        101: {"keywords": "merchant", "short_descr": "a merchant",
              "race": "human", "level": 10,
              "shop": {"keeper": 101, "profit_buy": 120}},
        102: {"keywords": "protected", "short_descr": "a protected mob",
              "race": "human", "level": 10},
    }
    objects = {
        200: {"keywords": "loot", "short_descr": "loot armor",
              "type": "armor", "wear_flags": {"take": True, "body": True},
              "armor": (1, 1, 1, 1), "level": 1, "value": 100},
        201: {"keywords": "stock", "short_descr": "stock armor",
              "type": "armor", "wear_flags": {"take": True, "head": True},
              "armor": (1, 1, 1, 1), "level": 1, "value": 100},
        202: {"keywords": "floor", "short_descr": "floor armor",
              "type": "armor", "wear_flags": {"take": True, "legs": True},
              "armor": (1, 1, 1, 1), "level": 1, "value": 100},
        203: {"keywords": "chest", "short_descr": "a chest",
              "type": "container", "wear_flags": {"take": True},
              "level": 1, "value": 100},
        204: {"keywords": "inside", "short_descr": "inside armor",
              "type": "armor", "wear_flags": {"take": True, "hands": True},
              "armor": (1, 1, 1, 1), "level": 1, "value": 100},
        205: {"keywords": "late", "short_descr": "late stock armor",
              "type": "armor", "wear_flags": {"take": True, "about": True},
              "armor": (1, 1, 1, 1), "level": 1, "value": 100},
        206: {"keywords": "bag", "short_descr": "a carried bag",
              "type": "container", "wear_flags": {"take": True},
              "level": 1, "value": 100},
        207: {"keywords": "nested", "short_descr": "nested armor",
              "type": "armor", "wear_flags": {"take": True, "feet": True},
              "armor": (1, 1, 1, 1), "level": 1, "value": 100},
        208: {"keywords": "sword", "short_descr": "a plain sword",
              "type": "weapon", "weapon_type": "sword", "dice": (2, 3, 0),
              "wear_flags": {"take": True, "wield": True}, "level": 1,
              "value": 100},
        209: {"keywords": "dirk", "short_descr": "a sharp dirk",
              "type": "weapon", "weapon_type": "dagger", "dice": (1, 4, 0),
              "weapon_flags": {"sharp": True},
              "wear_flags": {"take": True, "wield": True}, "level": 1,
              "value": 100},
    }
    # O/P share the shopkeeper's room: partitioning keeps the trailing G in
    # room 101's list, where reset_room's room-scoped last-mob still points
    # at mob 101 across the successful O/P, so the G is genuine shop stock.
    resets = (
        ("M", 100, 1, 100, 1), ("E", 200, "body", 1),
        ("E", 200, "body", 1), ("G", 206, 1),
        ("P", 207, 1, 206, 1),
        ("E", 208, "wield", 1), ("G", 209, 1),
        ("M", 101, 1, 101, 1), ("G", 201, 1),
        ("O", 202, 101), ("O", 203, 101), ("P", 204, 1, 203, 1),
        ("G", 205, 1),
        ("M", 102, 1, 103, 1),
    )
    fresh_world.register_area(
        "test", 100, 299, rooms=rooms, mobiles=mobiles,
        objects=objects, resets=resets)
    fresh_world.setup()
    monkeypatch.setattr(build_mob_index, "APPDIR", str(tmp_path))
    monkeypatch.setattr(build_mob_index, "OUTDIR", str(tmp_path))

    build_mob_index.main()

    mob_rows = (tmp_path / "mobs.idx").read_text().splitlines()
    assert "100|test|10|fighter|a fighter|test" in mob_rows
    assert next(row for row in mob_rows if row.startswith("101|")).endswith(
        "|test")
    foes_lines = (tmp_path / "foes.idx").read_text().splitlines()
    foes_sizes = [int(v) for v in foes_lines[1].split(",")]
    # Only mob 100 is fightable (101 is a shopkeeper, 102 sits in a safe
    # room); its level-10 segment is the last and only non-empty one.
    assert foes_lines[2:] == ["100|10|a fighter|test"]
    assert len(foes_sizes) == 11
    assert foes_sizes[10] == len(foes_lines[2]) + 1
    assert sum(foes_sizes) == foes_sizes[10]

    gear_lines = (tmp_path / "gear.idx").read_text().splitlines()
    sizes = [int(v) for v in gear_lines[1].split(",")]
    assert len(sizes) == len(recommend._GEAR_SLOTS)
    assert sum(sizes) == sum(len(line) + 1 for line in gear_lines[2:])
    gear_rows = [row.split("|") for row in gear_lines[2:]
                 if not row.startswith("@")]
    assert {row[9] for row in gear_rows} == {
        "loot", "shop", "floor", "container"}
    # Segments follow _GEAR_SLOTS order, so slot column is grouped.
    slot_seq = [row[1] for row in gear_rows]
    assert slot_seq == sorted(
        slot_seq, key=list(recommend._GEAR_SLOTS).index)
    assert sum(1 for row in gear_rows if row[0] == "200") == 1
    shops = [row for row in gear_rows if row[9] == "shop"]
    assert sorted(row[0] for row in shops) == ["201", "205"]
    assert all(row[11] == "101" and row[14] == "120" for row in shops)
    nested = next(row for row in gear_rows if row[0] == "207")
    assert nested[9:12] == ["loot", "10", "100"]
    assert nested[16] == "a fighter"

    # Band invariants the runtime shortcuts rely on: every row sits under a
    # header, headers partition each slot segment exactly, loot rows lead
    # in ascending @@source-level bands followed by non-loot in ascending
    # @item-level bands, rows inside a band (or wield type group) descend
    # by max-score bound, and wield type headers carry honest group maxima.
    text = (tmp_path / "gear.idx").read_text()
    body = text.split("\n", 2)[2]
    offset = 0
    saw_type_header = False
    saw_loot_band = False
    for size in sizes:
        segment = body[offset:offset + size]
        offset += size
        pos = 0
        last_band = -1
        in_loot_part = True
        while pos < len(segment):
            end = segment.index("\n", pos)
            header = segment[pos:end]
            assert header.startswith("@") and not header.startswith("@=")
            loot_band = header.startswith("@@")
            if loot_band:
                saw_loot_band = True
                assert in_loot_part  # loot bands never follow item bands
                band_level, band_bytes = header[2:].split("|")
            else:
                if in_loot_part:
                    in_loot_part = False
                    last_band = -1
                band_level, band_bytes = header[1:].split("|")
            assert int(band_level) > last_band
            last_band = int(band_level)
            band = segment[end + 1:end + 1 + int(band_bytes)]
            pos = end + 1 + int(band_bytes)
            groups = []
            if band.startswith("@="):
                saw_type_header = True
                sub_pos = 0
                while sub_pos < len(band):
                    sub_end = band.index("\n", sub_pos)
                    sub = band[sub_pos:sub_end]
                    assert sub.startswith("@=")
                    wtype, max_static, max_wmax, sub_bytes = (
                        sub[2:].split("|"))
                    group = [row.split("|") for row in
                             band[sub_end + 1:sub_end + 1
                                  + int(sub_bytes)].splitlines()]
                    sub_pos = sub_end + 1 + int(sub_bytes)
                    assert group and all(row[5] == wtype for row in group)
                    assert int(max_static) == max(
                        int(row[3]) for row in group)
                    assert int(max_wmax) == max(
                        inventory.gear_score_weapon_max(
                            int(row[4]), row[6] == "1") for row in group)
                    groups.append(group)
            else:
                groups.append([row.split("|")
                               for row in band.splitlines()])
            for group in groups:
                bounds = []
                for parts in group:
                    if loot_band:
                        assert parts[9] == "loot"
                        assert int(parts[10]) // 5 * 5 == int(band_level)
                    else:
                        assert parts[9] != "loot"
                        assert int(parts[2]) // 5 * 5 == int(band_level)
                    bounds.append(int(parts[3])
                                  + inventory.gear_score_weapon_max(
                                      int(parts[4]), parts[6] == "1"))
                assert bounds == sorted(bounds, reverse=True)
    assert saw_type_header  # the wield segment exercised the @= path
    assert saw_loot_band  # loot sources exercised the @@ path


def test_shipped_indexes_reproduce(tmp_path, monkeypatch):
    source = Path(build_mob_index.APPDIR)
    monkeypatch.setattr(build_mob_index, "OUTDIR", str(tmp_path))

    build_mob_index.main()

    for name in ("mobs.idx", "objs.idx", "foes.idx", "gear.idx"):
        assert (tmp_path / name).read_bytes() == (source / name).read_bytes()
