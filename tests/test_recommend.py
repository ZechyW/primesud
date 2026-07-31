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


def _mob_row(vnum, level, name, tags="test"):
    return (str(vnum) + "|test|" + str(level) + "|mob|" + name
            + "|" + tags + "|" + tags)


def _gear_row(vnum, slot="body", level=1, score=100, kind="floor",
              source_vnum=0, source_level=0, room=1, source="Test Room",
              tag="test", price=0, flags="", weapon_base=0,
              weapon_type="", sharp=0, weight=0):
    return "|".join((
        str(vnum), slot, str(level), str(score), str(weapon_base),
        weapon_type, str(sharp), str(weight), flags, "item " + str(vnum),
        kind, str(source_vnum), str(source_level), str(room), source, tag,
        str(price),
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
    path = tmp_path / "mobs.idx"
    path.write_text("\n".join((
        _mob_row(100, 11, "upper"),
        _mob_row(101, 10, "same"),
        _mob_row(102, 9, "lower one"),
        _mob_row(103, 8, "lower two"),
        _mob_row(104, 7, "widened"),
        _mob_row(105, 5, "limit"),
        _mob_row(106, 12, "too high"),
        _mob_row(107, 4, "too low"),
    )))
    monkeypatch.setattr(recommend, "MOB_INDEX_FILE", str(path))

    rows = recommend._mob_candidates(indexed_player)

    assert {row["vnum"] for row in rows} == {100, 101, 102, 103, 104}
    assert all(row["level"] <= 11 for row in rows)


def test_mob_filters_legacy_empty_tags_quest_and_malformed(
        indexed_player, tmp_path, monkeypatch):
    indexed_player["quest_status"] = recommend.QUEST_FINDMOB
    indexed_player["quest_mob"] = 102
    path = tmp_path / "mobs.idx"
    path.write_text("\n".join((
        "100|test|10|mob|legacy|test",
        "101|test|10|mob|no fight|test|",
        _mob_row(102, 10, "protected"),
        _mob_row(103, 10, "eligible"),
        "bad|row|x|mob|broken|test|test",
    )))
    monkeypatch.setattr(recommend, "MOB_INDEX_FILE", str(path))

    assert [row["vnum"] for row in
            recommend._mob_candidates(indexed_player)] == [103]


def test_mob_ranking_record_current_area_and_no_load(
        indexed_player, tmp_path, monkeypatch):
    path = tmp_path / "mobs.idx"
    path.write_text("\n".join((
        _mob_row(100, 10, "far", "far"),
        _mob_row(101, 10, "current", "test"),
        _mob_row(102, 10, "bad", "test"),
    )))
    world.mob_stats[102] = [2, 0]
    monkeypatch.setattr(recommend, "MOB_INDEX_FILE", str(path))
    monkeypatch.setattr(world, "_ensure_area_by_tag",
                        lambda *_args: pytest.fail("area loaded"))
    before = set(world._LOADED_AREAS)

    rows = recommend._mob_candidates(indexed_player)

    assert [row["vnum"] for row in rows] == [101, 100, 102]
    assert world._LOADED_AREAS == before


def test_missing_indexes_fail_softly(indexed_player, tmp_path, monkeypatch,
                                     capture):
    pages, lines = capture
    monkeypatch.setattr(recommend, "MOB_INDEX_FILE",
                        str(tmp_path / "missing-mobs.idx"))
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
    path = tmp_path / "mobs.idx"
    path.write_text("\n".join((
        _mob_row(100, 10, "roamer", "far,test"),
        _mob_row(101, 10, "homebody", "test"),
    )))
    monkeypatch.setattr(recommend, "MOB_INDEX_FILE", str(path))

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
    }
    # O/P share the shopkeeper's room: partitioning keeps the trailing G in
    # room 101's list, where reset_room's room-scoped last-mob still points
    # at mob 101 across the successful O/P, so the G is genuine shop stock.
    resets = (
        ("M", 100, 1, 100, 1), ("E", 200, "body", 1),
        ("E", 200, "body", 1), ("G", 206, 1),
        ("P", 207, 1, 206, 1),
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
    assert next(row for row in mob_rows if row.startswith("100|")).endswith(
        "|test|test")
    assert next(row for row in mob_rows if row.startswith("101|")).endswith(
        "|test|")
    assert next(row for row in mob_rows if row.startswith("102|")).endswith(
        "|test|")
    gear_lines = (tmp_path / "gear.idx").read_text().splitlines()
    sizes = [int(v) for v in gear_lines[1].split(",")]
    assert len(sizes) == len(recommend._GEAR_SLOTS)
    assert sum(sizes) == sum(len(line) + 1 for line in gear_lines[2:])
    gear_rows = [row.split("|") for row in gear_lines[2:]]
    assert {row[10] for row in gear_rows} == {
        "loot", "shop", "floor", "container"}
    # Segments follow _GEAR_SLOTS order, so slot column is grouped.
    slot_seq = [row[1] for row in gear_rows]
    assert slot_seq == sorted(
        slot_seq, key=list(recommend._GEAR_SLOTS).index)
    assert sum(1 for row in gear_rows if row[0] == "200") == 1
    shops = [row for row in gear_rows if row[10] == "shop"]
    assert sorted(row[0] for row in shops) == ["201", "205"]
    assert all(row[11] == "101" and row[16] == "120" for row in shops)
    nested = next(row for row in gear_rows if row[0] == "207")
    assert nested[10:13] == ["loot", "100", "10"]
    assert nested[14] == "a fighter"


def test_shipped_indexes_reproduce(tmp_path, monkeypatch):
    source = Path(build_mob_index.APPDIR)
    monkeypatch.setattr(build_mob_index, "OUTDIR", str(tmp_path))

    build_mob_index.main()

    for name in ("mobs.idx", "objs.idx", "gear.idx"):
        assert (tmp_path / name).read_bytes() == (source / name).read_bytes()
