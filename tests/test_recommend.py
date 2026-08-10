"""Tests for zero-load mob and gear recommendations. [PRIMESUD]"""

from pathlib import Path

import pytest

import commands
import inventory
import recommend
import world
from config import WEAR_BEST_SKILL_FLOOR
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
    return {"vnum": vnum, "level": level, "name": name,
            "tags": tags.split(",")}


def _write_foes_bin(path, rows):
    """Pack rows through the builder so fixtures keep the shipped
    level-grouped layout the scanner's band seek depends on."""
    path.write_bytes(build_mob_index.pack_foes_index(list(rows)))


def _gear_row(vnum, slot="body", level=1, score=100, kind="floor",
              source_vnum=0, source_level=0, room=1, source="Test Room",
              tag="test", price=0, flags=(), weapon_base=0,
              weapon_type="", sharp=0, weight=0):
    """Return one gear source row dict in the builder's pack input shape."""
    return {
        "vnum": vnum, "slot": slot, "level": level, "static": score,
        "wbase": weapon_base, "wtype": weapon_type, "sharp": bool(sharp),
        "weight": weight, "flags": list(flags), "kind": kind,
        "source_level": source_level, "source_vnum": source_vnum,
        "room": room, "tag": tag, "price": price,
        "name": "item " + str(vnum), "source_name": source,
    }


def _write_gear_bin(path, rows):
    """Pack rows through the builder so fixtures keep the shipped layout
    invariants (loot first, bound-descending regions)."""
    path.write_bytes(build_mob_index.pack_gear_index(list(rows)))


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


def test_mob_window_is_fixed_and_level_sorted(
        indexed_player, tmp_path, monkeypatch):
    path = tmp_path / "foes.bin"
    _write_foes_bin(path, (
        _fight_row(80, 8, "low two a"),
        _fight_row(81, 8, "low two b"),
        _fight_row(90, 9, "low one a"),
        _fight_row(91, 9, "low one b"),
        _fight_row(92, 9, "low one c"),
        _fight_row(100, 10, "same a"),
        _fight_row(101, 10, "same b"),
        _fight_row(102, 10, "same c"),
        _fight_row(110, 11, "upper a"),
        _fight_row(111, 11, "upper b"),
        _fight_row(70, 7, "too low"),
        _fight_row(120, 12, "too high"),
    ))
    monkeypatch.setattr(recommend, "FOES_INDEX_FILE", str(path))

    rows = recommend._mob_candidates(indexed_player)

    # Band [level-2, level+1] only, displayed level descending then by the
    # packed rank key (here plain file order within each level).
    assert [row["vnum"] for row in rows] == [
        110, 111, 100, 101, 102, 90, 91, 92, 80, 81]


def test_mob_selection_is_round_robin_over_bands(
        indexed_player, tmp_path, monkeypatch):
    """Near-level bands are kept even when one could fill the list; the
    level-2 band only backfills slots they leave over."""
    rows_in = [_fight_row(200 + index, 10, "same " + str(index))
               for index in range(30)]
    rows_in.extend((
        _fight_row(90, 9, "low one"),
        _fight_row(80, 8, "low two"),
        _fight_row(110, 11, "upper"),
    ))
    path = tmp_path / "foes.bin"
    _write_foes_bin(path, rows_in)
    monkeypatch.setattr(recommend, "FOES_INDEX_FILE", str(path))

    rows = recommend._mob_candidates(indexed_player)

    assert len(rows) == 20
    levels = [row["level"] for row in rows]
    assert levels == sorted(levels, reverse=True)
    # One row per near-level band was drawn on the first round; the
    # remaining 18 come from the level-10 bucket, which alone holds 30, so
    # the level-8 filler never gets a slot.
    assert levels.count(11) == 1 and levels.count(9) == 1
    assert levels.count(8) == 0 and levels.count(10) == 18
    assert [row["vnum"] for row in rows[:2]] == [110, 200]


def test_mob_dedupes_name_and_displayed_area(
        indexed_player, tmp_path, monkeypatch):
    path = tmp_path / "foes.bin"
    _write_foes_bin(path, (
        _fight_row(100, 10, "the duplicate", "test"),
        _fight_row(101, 9, "the duplicate", "test"),
        _fight_row(102, 11, "the duplicate", "far"),
        _fight_row(103, 10, "unique", "test"),
    ))
    monkeypatch.setattr(recommend, "FOES_INDEX_FILE", str(path))

    rows = recommend._mob_candidates(indexed_player)

    assert [(row["vnum"], row["name"], row["tag"]) for row in rows] == [
        (102, "the duplicate", "far"),
        (100, "the duplicate", "test"),
        (103, "unique", "test"),
    ]


def test_mob_quest_target_excluded(indexed_player, tmp_path, monkeypatch):
    indexed_player["quest_status"] = recommend.QUEST_FINDMOB
    indexed_player["quest_mob"] = 102
    path = tmp_path / "foes.bin"
    _write_foes_bin(path, (
        _fight_row(102, 10, "protected"),
        _fight_row(103, 10, "eligible"),
    ))
    monkeypatch.setattr(recommend, "FOES_INDEX_FILE", str(path))

    assert [row["vnum"] for row in
            recommend._mob_candidates(indexed_player)] == [103]


def test_mob_ranking_record_current_area_and_no_load(
        indexed_player, tmp_path, monkeypatch):
    path = tmp_path / "foes.bin"
    _write_foes_bin(path, (
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


def test_corrupt_foes_header_fails_softly(indexed_player, tmp_path,
                                          monkeypatch, capture):
    pages, lines = capture
    path = tmp_path / "foes.bin"
    path.write_bytes(b"not a foes index at all")
    monkeypatch.setattr(recommend, "FOES_INDEX_FILE", str(path))
    recommend.do_recommend(indexed_player, ["mobs"])

    # Right magic, garbage sizes: header walk never lands on header_size.
    path.write_bytes(b"FB01\xff\x07\x1e\x00\x00\x00\x99\x99")
    recommend.do_recommend(indexed_player, ["mobs"])

    assert pages == []
    assert lines == ["Mob recommendations are unavailable."] * 2


def test_missing_indexes_fail_softly(indexed_player, tmp_path, monkeypatch,
                                     capture):
    pages, lines = capture
    monkeypatch.setattr(recommend, "FOES_INDEX_FILE",
                        str(tmp_path / "missing-foes.bin"))
    monkeypatch.setattr(recommend, "GEAR_INDEX_FILE",
                        str(tmp_path / "missing-gear.idx"))

    recommend.do_recommend(indexed_player, ["mobs"])
    recommend.do_recommend(indexed_player, ["gear"])

    assert pages == []
    assert lines == [
        "Mob recommendations are unavailable.",
        "Gear recommendations are unavailable.",
    ]


def test_corrupt_gear_header_fails_softly(indexed_player, tmp_path,
                                          monkeypatch, capture):
    pages, lines = capture
    path = tmp_path / "gear.bin"
    path.write_bytes(b"not a gear index at all")
    monkeypatch.setattr(recommend, "GEAR_INDEX_FILE", str(path))
    recommend.do_recommend(indexed_player, ["gear"])

    # Right magic and record size, then truncated garbage.
    path.write_bytes(b"GB01\xff\x0f\x1e\x00\x99\x99")
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


def test_gear_downweights_barely_learnt_weapon(indexed_player, tmp_path,
                                               monkeypatch):
    """Expected-hit weighting ranks a learnt weapon over bigger raw dice."""
    path = tmp_path / "gear.bin"
    _write_gear_bin(path, (
        _gear_row(600, slot="wield", score=0, weapon_base=20,
                  weapon_type="sword"),
        _gear_row(601, slot="wield", score=0, weapon_base=10,
                  weapon_type="dagger"),
    ))
    monkeypatch.setattr(recommend, "GEAR_INDEX_FILE", str(path))
    indexed_player["learned"][WEAPON_GSN_MAP["dagger"]] = 80
    indexed_player["learned"][WEAPON_GSN_MAP["sword"]] = 10

    rows = recommend._scan_gear(indexed_player, "wield")["wield"]

    # dagger 10 base at 80% scores 85; sword 20 base at 10% only 21
    assert [row["vnum"] for row in rows] == [601, 600]
    assert [row["gain"] for row in rows] == [85, 21]


def test_gear_skips_weapons_under_the_wear_best_floor(
        indexed_player, tmp_path, monkeypatch):
    """Rows 'wear best' would refuse (under WEAR_BEST_SKILL_FLOOR) never
    surface; exotic types stay exempt exactly as in _can_wear_best."""
    path = tmp_path / "gear.bin"
    _write_gear_bin(path, (
        _gear_row(600, slot="wield", score=0, weapon_base=20,
                  weapon_type="sword"),
        _gear_row(601, slot="wield", score=0, weapon_base=10,
                  weapon_type="dagger"),
        _gear_row(602, slot="wield", score=0, weapon_base=10,
                  weapon_type="exotic"),
    ))
    monkeypatch.setattr(recommend, "GEAR_INDEX_FILE", str(path))
    indexed_player["learned"][WEAPON_GSN_MAP["dagger"]] = (
        WEAR_BEST_SKILL_FLOOR - 1)
    indexed_player["learned"][WEAPON_GSN_MAP["sword"]] = 10

    rows = recommend._scan_gear(indexed_player, "wield")["wield"]

    # dagger (4%) is gone; sword 20 base at 10% scores 21, exotic 10 base
    # at the level-10 PC's 3 * level = 30% scores 25.
    assert [(row["vnum"], row["gain"]) for row in rows] == [(602, 25),
                                                            (600, 21)]

    # Exotic has no gsn to practise (PCs get 3 * level), so it survives the
    # floor even for a level-1 player whose 3 * level is under it.
    low = _player(level=1)
    low["learned"] = {}
    assert [row["vnum"] for row in
            recommend._scan_gear(low, "wield")["wield"]] == [602]


def test_two_hander_pays_owned_shield_cost(indexed_player, tmp_path,
                                           monkeypatch):
    """A two-hander row is charged for the shield it would force off."""
    world.ITEM_DEFS._data[500] = {
        "type": "armor", "wear_flags": {"take": True, "shield": True},
        "level": 1, "armor": (5, 5, 5, 5),
    }
    indexed_player["inv"] = [{"vnum": 500}]
    indexed_player["learned"][WEAPON_GSN_MAP["sword"]] = 80
    path = tmp_path / "gear.bin"
    _write_gear_bin(path, (
        _gear_row(600, slot="wield", score=0, weapon_base=20,
                  weapon_type="sword"),
        _gear_row(601, slot="wield", score=0, weapon_base=20,
                  weapon_type="sword", flags=("two_hands",)),
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
    path = tmp_path / "gear.bin"
    _write_gear_bin(path, [_gear_row(600, score=150)])
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
    path = tmp_path / "gear.bin"
    _write_gear_bin(path, (
        _gear_row(600, score=200, kind="shop", source_vnum=10,
                  source="shop", price=100, tag="far"),
        _gear_row(600, score=200, kind="floor", source="floor",
                  tag="test"),
        _gear_row(601, score=190, kind="loot", source_vnum=20,
                  source_level=12, source="too strong"),
        _gear_row(602, score=180, flags=("anti_neutral",)),
    ))
    monkeypatch.setattr(recommend, "GEAR_INDEX_FILE", str(path))
    before = set(world._LOADED_AREAS)

    rows = recommend._scan_gear(indexed_player)["body"]

    assert len(rows) == 1
    assert rows[0]["vnum"] == 600
    assert rows[0]["kind"] == "floor"
    # Summary mode keeps a single winner without alt bookkeeping; alt
    # retention is covered by the detail-mode tests.
    assert rows[0]["alts"] == []
    assert world._LOADED_AREAS == before

    detail = recommend._scan_gear(indexed_player, "body")["body"]
    assert [alt["kind"] for alt in detail[0]["alts"]] == ["shop"]


def test_alt_sources_dedupe_rendered_identity(indexed_player, tmp_path,
                                              monkeypatch):
    # Two cityguard rows render identically (same mob, same area, rooms
    # unshown): the pair must collapse to the better-ranked room without
    # keeping the twin (or dropping the distinct thug) as an "also" line.
    path = tmp_path / "gear.bin"
    _write_gear_bin(path, (
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


def test_loot_bound_skip_jumps_to_nonloot_region(indexed_player, tmp_path,
                                                 monkeypatch):
    """A bound below the floor ends the loot region only: the scan jumps
    to the non-loot region and still finds its rows. Loot outside the
    window rejects without affecting either region."""
    world.ITEM_DEFS._data[500] = {
        "type": "armor", "wear_flags": {"take": True, "body": True},
        "level": 1, "armor": (2, 2, 2, 2),  # owned baseline 80
    }
    indexed_player["inv"] = [{"vnum": 500}]
    path = tmp_path / "gear.bin"
    _write_gear_bin(path, (
        # Loot region after pack sort: 601 (window, admitted), 602 (out of
        # window), 603 (bound 50 < floor -> region skip).
        _gear_row(601, score=150, kind="loot", source_vnum=20,
                  source_level=10, source="a fair fight"),
        _gear_row(602, score=140, kind="loot", source_vnum=21,
                  source_level=20, source="too strong"),
        _gear_row(603, score=50, kind="loot", source_vnum=22,
                  source_level=10, source="weak loot"),
        # Non-loot region: must still be reached after the loot skip.
        _gear_row(604, score=120),
        _gear_row(605, score=60),  # bound 60 < floor -> segment ends
    ))
    monkeypatch.setattr(recommend, "GEAR_INDEX_FILE", str(path))

    rows = recommend._scan_gear(indexed_player, "body")["body"]

    assert [row["vnum"] for row in rows] == [601, 604]
    assert [row["gain"] for row in rows] == [70, 40]


def test_full_results_raise_skip_floor(indexed_player, tmp_path, monkeypatch):
    """A full ten-row slot raises the skip floor to the weakest kept score:
    the bound-sorted region ends at the first row below it, while an
    equal-bound alternate source of a kept item still lands in its alts."""
    rows = [_gear_row(600 + index, score=111 - index)
            for index in range(10)]                      # gains 111..102
    rows.append(_gear_row(609, score=102, kind="shop", source_vnum=10,
                          source="shop"))
    rows.append(_gear_row(620, score=101))
    path = tmp_path / "gear.bin"
    _write_gear_bin(path, rows)
    monkeypatch.setattr(recommend, "GEAR_INDEX_FILE", str(path))

    kept = recommend._scan_gear(indexed_player, "body")["body"]

    assert [row["vnum"] for row in kept] == list(range(600, 610))
    assert len(kept[9]["alts"]) == 1  # the tied second source of 609 parsed
    assert all(row["vnum"] != 620 for row in kept)  # bound 101 < floor 102


def test_summary_scan_chunks_contiguous_reads(indexed_player, tmp_path,
                                              monkeypatch):
    """Summary mode packs consecutive segments into bounded chunk reads."""
    path = tmp_path / "gear.bin"
    _write_gear_bin(path, [
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
                        lambda name, mode="r":
                            _CountingFile(real_open(name, mode)),
                        raising=False)

    results = recommend._scan_gear(indexed_player)
    # header + one chunk spanning all 16 segments + the string table
    assert len(reads) == 3
    assert all(len(results[slot]) == 1 for slot in recommend._GEAR_SLOTS)

    # A tiny chunk budget degrades to per-segment reads, same results.
    monkeypatch.setattr(recommend, "_CHUNK", 1)
    del reads[:]
    results = recommend._scan_gear(indexed_player)
    assert len(reads) == 2 + len(recommend._GEAR_SLOTS)
    assert all(len(results[slot]) == 1 for slot in recommend._GEAR_SLOTS)


def _reference_summary(player, slots_rows):
    """Naive full rescoring of parsed rows: the summary winner per slot.

    Mirrors _scan_records' scoring/filters without any of its layout
    shortcuts (bound sort, region breaks, floor) -- if a shortcut ever
    drops a should-win row on real data, this disagrees.
    """
    baselines = recommend._owned_baselines(player)
    current = recommend._current_tag(player)
    area_order = {entry[1]: index
                  for index, entry in enumerate(world._AREA_FILES)}
    funds = player.get("gold", 0) * 100 + player.get("silver", 0)
    level = player["level"]
    loot_low, loot_high = max(1, level - 2), level + 1
    wield_limit = recommend.STR_APP_WIELD[
        recommend.get_curr_stat(player, "str")] * 10
    small = recommend._get_size(player) < recommend.SIZE_RANK["large"]
    sb_pct = inventory.shield_block_pct(player)
    winners = {}
    for slot, rows in slots_rows.items():
        baseline = baselines[slot]
        best = None
        for row in rows:
            if row["level"] > level:
                continue
            if (row["kind"] == "loot"
                    and not (loot_low <= row["source_level"] <= loot_high)):
                continue
            flags = {name: True for name in row["flags"]}
            if not inventory.gear_flags_legal(player, flags):
                continue
            if slot == "wield" and row["weight"] > wield_limit:
                continue
            if row["wbase"]:
                sn = WEAPON_GSN_MAP.get(row["wtype"], -1)
                if (sn != -1 and recommend._get_weapon_skill(player, sn)
                        < WEAR_BEST_SKILL_FLOOR):
                    continue  # wear best's proficiency floor
            wscore = inventory.gear_score_weapon(
                player, row["wbase"], row["wtype"], row["sharp"])
            score = row["static"] + wscore
            if flags.get("two_hands") and small:
                block = score * sb_pct // 100
                score += wscore // 10 - (baselines["shield"] + block) // 2
            if score <= baseline:
                continue
            key = (-score, recommend._source_key(
                row["kind"], row["tag"], row["price"], funds,
                row["source_level"], level, row["source_vnum"], row["room"],
                current, area_order), row["vnum"])
            if best is None or key < best[0]:
                best = (key, row["vnum"], score - baseline)
        if best is not None:
            winners[slot] = (best[1], best[2])
    return winners


def test_shipped_index_matches_naive_rescoring(indexed_player):
    """The shortcut scan of the shipped gear.bin agrees with a naive full
    rescoring of every parsed row, across varied player profiles."""
    with open("gear.bin", "rb") as f:
        slots_rows, _wtypes, _tags = build_mob_index.parse_gear_index(
            f.read())
    profiles = (
        (5, {}),
        (12, {WEAPON_GSN_MAP["sword"]: 80}),
        (35, {WEAPON_GSN_MAP["dagger"]: 100, WEAPON_GSN_MAP["mace"]: 40}),
    )
    for level, learned in profiles:
        player = _player(level=level)
        player["learned"] = learned
        results = recommend._scan_gear(player)
        got = {slot: (rows[0]["vnum"], rows[0]["gain"])
               for slot, rows in results.items() if rows}
        assert got == _reference_summary(player, slots_rows)
        for rows in results.values():
            for row in rows:
                assert isinstance(row["name"], str) and row["name"]
                assert isinstance(row["source_name"], str)


def _reference_mobs(player, rows_all):
    """Naive dict-based ranking (the pre-binary algorithm, no shortcuts):
    filter the fixed band, dedupe name/source, rank each level bucket, draw
    the near-level buckets round-robin and backfill from level-2 until 20
    rows remain, then sort them for display."""
    level = player.get("level", 1)
    lowest = max(1, level - 2)
    highest = level + 1
    current = recommend._current_tag(player)
    protected = 0
    if player.get("quest_status") in (recommend.QUEST_DELIVER,
                                      recommend.QUEST_FINDMOB):
        protected = player.get("quest_mob", 0)
    deduped = {}
    for order, row in enumerate(
            row for row in rows_all
            if lowest <= row["level"] <= highest):
        if row["vnum"] == protected:
            continue
        stats = world.mob_stats.get(row["vnum"])
        kills = stats[0] if stats else 0
        deaths = stats[1] if stats else 0
        tag = current if current in row["tags"] else row["tags"][0]
        candidate = {
            "vnum": row["vnum"], "level": row["level"],
            "name": row["name"], "tag": tag,
            "extra": len(row["tags"]) - 1, "kills": kills,
            "deaths": deaths, "bad": bool(stats and kills > deaths),
            "order": order,
        }
        key = (candidate["bad"], tag != current,
               abs(row["level"] - level), row["level"], order)
        identity = (row["name"], tag)
        old = deduped.get(identity)
        if old is None or key < old[0]:
            deduped[identity] = (key, candidate)
    buckets = [[], [], [], []]
    for key, row in deduped.values():
        if row["level"] == level:
            bucket = 0
        elif row["level"] == level - 1:
            bucket = 1
        elif row["level"] == level + 1:
            bucket = 2
        else:
            bucket = 3
        buckets[bucket].append((key, row))
    for bucket in buckets:
        bucket.sort(key=lambda entry: entry[0])
    rows = []
    index = 0
    while len(rows) < 20:
        added = False
        for bucket in buckets[:3]:
            if index < len(bucket):
                rows.append(bucket[index])
                added = True
                if len(rows) == 20:
                    break
        if not added:
            break
        index += 1
    for entry in buckets[3]:
        if len(rows) >= 20:
            break
        rows.append(entry)
    rows.sort(key=lambda entry: (-entry[1]["level"], entry[0]))
    return [(row["vnum"], row["level"], row["tag"], row["extra"],
             row["kills"], row["deaths"], row["bad"])
            for _key, row in rows]


def test_shipped_foes_matches_naive_ranking(fresh_world):
    """The two-pass packed-key scan of the shipped foes.bin agrees with a
    naive full ranking, across levels, seeded kill records, and both a
    foreign and a resident current area."""
    fresh_world.register_area(
        "midgaard", 3000, 3399,
        rooms={3001: {"name": "Square", "flags": {}, "exits": {}}})
    fresh_world.setup()
    with open("foes.bin", "rb") as f:
        rows_all, _tags, _sizes = build_mob_index.parse_foes_index(f.read())
    for index, row in enumerate(rows_all):
        if index % 7 == 0:
            world.mob_stats[row["vnum"]] = [2, 0]
        elif index % 7 == 3:
            world.mob_stats[row["vnum"]] = [1, 4]
    for level, room in ((3, 1), (10, 3001), (24, 3001), (45, 1)):
        player = _player(level=level, room=room)
        rows = recommend._mob_candidates(player)
        assert [(row["vnum"], row["level"], row["tag"], row["extra"],
                 row["kills"], row["deaths"], row["bad"])
                for row in rows] == _reference_mobs(player, rows_all)
        for row in rows:
            assert isinstance(row["name"], str) and row["name"]


def test_gear_detail_is_bounded_to_ten(indexed_player, tmp_path, monkeypatch):
    path = tmp_path / "gear.bin"
    _write_gear_bin(path, [
        _gear_row(600 + index, score=100 + index)
        for index in range(12)])
    monkeypatch.setattr(recommend, "GEAR_INDEX_FILE", str(path))

    rows = recommend._scan_gear(indexed_player, "body")["body"]

    assert len(rows) == 10
    assert [row["gain"] for row in rows] == list(range(111, 101, -1))


def test_gear_detail_lists_nearest_downgrades(indexed_player, tmp_path,
                                              monkeypatch):
    """Detail mode collects the nearest below-baseline rows: nearest
    first, bounded to five, owned VNUMs suppressed, sidegrades kept."""
    world.ITEM_DEFS._data[500] = {
        "type": "armor", "wear_flags": {"take": True, "body": True},
        "level": 1, "armor": (2, 2, 2, 2),  # owned baseline 80
    }
    indexed_player["inv"] = [{"vnum": 500}]
    rows = [_gear_row(600, score=100),      # upgrade
            _gear_row(500, score=80),       # owned copy: suppressed
            _gear_row(601, score=80)]       # unowned sidegrade: kept
    rows.extend(_gear_row(610 + index, score=78 - index)
                for index in range(7))      # 78..72
    path = tmp_path / "gear.bin"
    _write_gear_bin(path, rows)
    monkeypatch.setattr(recommend, "GEAR_INDEX_FILE", str(path))

    downs = []
    results = recommend._scan_gear(indexed_player, "body", downs)

    assert [row["vnum"] for row in results["body"]] == [600]
    assert [(row["vnum"], row["gain"]) for row in downs] == [
        (601, 0), (610, -2), (611, -3), (612, -4), (613, -5)]
    assert all(row["wtype"] == "" for row in downs)

    # Summary mode never collects downgrades.
    downs = []
    recommend._scan_gear(indexed_player, None, downs)
    assert downs == []


def test_wield_downgrades_best_per_type(indexed_player, tmp_path,
                                        monkeypatch):
    """Wield downgrades keep the best row per weapon type: worse same-type
    rows dedupe, types under the single proficiency floor stay hidden,
    exotic is always eligible, and a type at or above the floor that beats
    the baseline is an ordinary upgrade rather than a downgrade row."""
    world.ITEM_DEFS._data[500] = {
        "type": "weapon", "wear_flags": {"take": True, "wield": True},
        "level": 1, "weapon_type": "sword", "dice": (2, 6, 0),
    }
    indexed_player["inv"] = [{"vnum": 500}]  # baseline 120 at 80% sword
    indexed_player["learned"][WEAPON_GSN_MAP["sword"]] = 80
    indexed_player["learned"][WEAPON_GSN_MAP["axe"]] = 7
    indexed_player["learned"][WEAPON_GSN_MAP["dagger"]] = (
        WEAR_BEST_SKILL_FLOOR - 1)
    path = tmp_path / "gear.bin"
    _write_gear_bin(path, (
        _gear_row(600, slot="wield", score=0, weapon_base=20,
                  weapon_type="sword"),      # 171: upgrade
        _gear_row(601, slot="wield", score=0, weapon_base=10,
                  weapon_type="sword"),      # 85: nearest sword below
        _gear_row(602, slot="wield", score=0, weapon_base=8,
                  weapon_type="sword"),      # 68: worse sword, deduped
        _gear_row(603, slot="wield", score=0, weapon_base=140,
                  weapon_type="axe"),        # 7% skill: 126, an upgrade
        _gear_row(604, slot="wield", score=0, weapon_base=20,
                  weapon_type="dagger"),     # 4% skill: hidden
        _gear_row(605, slot="wield", score=0, weapon_base=10,
                  weapon_type="exotic"),     # 3 * level -> 25
    ))
    monkeypatch.setattr(recommend, "GEAR_INDEX_FILE", str(path))

    downs = []
    results = recommend._scan_gear(indexed_player, "wield", downs)

    # The 7% axe clears the floor, so its 126 is an upgrade like any other.
    assert [(row["vnum"], row["gain"]) for row in results["wield"]] == [
        (600, 51), (603, 6)]
    # One row per eligible type left below the baseline, gain descending.
    assert [(row["vnum"], row["wtype"], row["gain"]) for row in downs] == [
        (601, "sword", -35),
        (605, "exotic", -95)]


def test_gear_detail_renders_downgrade_section(indexed_player, tmp_path,
                                               monkeypatch, capture):
    """Detail output appends the nearest section with signed gains and
    weapon-type labels, and still renders with zero upgrades."""
    pages, _lines = capture
    indexed_player["learned"][WEAPON_GSN_MAP["sword"]] = 80
    indexed_player["learned"][WEAPON_GSN_MAP["axe"]] = 7
    world.ITEM_DEFS._data[500] = {
        "type": "weapon", "wear_flags": {"take": True, "wield": True},
        "level": 1, "weapon_type": "sword", "dice": (2, 9, 0),  # 171
    }
    indexed_player["inv"] = [{"vnum": 500}]
    path = tmp_path / "gear.bin"
    _write_gear_bin(path, (
        _gear_row(601, slot="wield", score=0, weapon_base=10,
                  weapon_type="sword"),      # 85 -> -86
        _gear_row(603, slot="wield", score=0, weapon_base=20,
                  weapon_type="axe"),        # 7% skill: 18 -> -153
    ))
    monkeypatch.setattr(recommend, "GEAR_INDEX_FILE", str(path))

    recommend._show_gear(indexed_player, "wield")

    body = pages[0]
    assert body[0] == "No wield upgrades for you."
    assert "{wNearest by weapon type:{x" in body
    assert any(line.startswith("wield -86 [sword]") for line in body)
    assert any(line.startswith("wield -153 [axe]") for line in body)
    assert not any("*" in line for line in body)


def test_mob_multi_area_marker(indexed_player, tmp_path, monkeypatch,
                               capture):
    pages, _lines = capture
    path = tmp_path / "foes.bin"
    _write_foes_bin(path, (
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
    path = tmp_path / "gear.bin"
    _write_gear_bin(path, (
        _gear_row(600, score=200, kind="floor", source="floor", tag="test"),
        _gear_row(600, score=200, kind="shop", source_vnum=10, source="shop",
                  price=100, tag="far"),
    ))
    monkeypatch.setattr(recommend, "GEAR_INDEX_FILE", str(path))
    picks = []

    def pick(title, options):
        picks.append((title, options))
        return 0

    monkeypatch.setattr(recommend, "pick_from", pick)

    assert recommend.do_recommend(indexed_player, ["gear"]) == (
        "recommend gear body")
    assert picks[0][0] == (
        "Gear upgrades (select one for source and/or alternatives):")
    assert picks[0][1] == ["body     +200 item 600"]
    assert any(line.startswith("  also shop: shop") for line in pages[0])
    assert sum(line.startswith("    area: ") for line in pages[0]) == 2

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
        ("M", 101, 1, 101, 1), ("G", 201, 1), ("G", 209, 1),
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

    mob_rows, mob_tags = build_mob_index.parse_key_index(
        (tmp_path / "mobs.bin").read_bytes())
    assert {"vnum": 100, "level": 10, "home": "test", "keywords": "fighter",
            "name": "a fighter", "tags": ["test"]} in mob_rows
    assert next(row for row in mob_rows
                if row["vnum"] == 101)["tags"] == ["test"]
    assert mob_tags == ["test"]
    obj_rows, _obj_tags = build_mob_index.parse_key_index(
        (tmp_path / "objs.bin").read_bytes())
    assert {"vnum": 203, "level": 0, "home": "test", "keywords": "chest",
            "name": "", "tags": ["test"]} in obj_rows
    foes_blob = (tmp_path / "foes.bin").read_bytes()
    foes_rows, foes_tags, foes_sizes = build_mob_index.parse_foes_index(
        foes_blob)
    # Only mob 100 is fightable (101 is a shopkeeper, 102 sits in a safe
    # room); its level-10 segment is the last and only non-empty one.
    assert [(row["vnum"], row["level"], row["name"], row["tags"])
            for row in foes_rows] == [(100, 10, "a fighter", ["test"])]
    assert len(foes_sizes) == 11
    assert foes_sizes[10] == 8  # 7 fixed bytes + 1 tag id
    assert sum(foes_sizes) == foes_sizes[10]
    assert "test" in foes_tags

    blob = (tmp_path / "gear.bin").read_bytes()
    slots_rows, wtypes, tags = build_mob_index.parse_gear_index(blob)
    all_rows = [row for rows in slots_rows.values() for row in rows]
    assert {row["kind"] for row in all_rows} == {
        "loot", "shop", "floor", "container"}
    assert sum(1 for row in all_rows if row["vnum"] == 200) == 1
    shops = [row for row in all_rows if row["kind"] == "shop"]
    assert sorted(row["vnum"] for row in shops) == [201, 205, 209]
    assert all(row["source_vnum"] == 101 and row["price"] == 120
               for row in shops)
    nested = next(row for row in all_rows if row["vnum"] == 207)
    assert (nested["kind"], nested["source_level"], nested["source_vnum"]
            ) == ("loot", 10, 100)
    assert nested["source_name"] == "a fighter"
    assert "sword" in wtypes and "dagger" in wtypes and "test" in tags

    # Slot routing: the segment implies the slot, so the two weapons must
    # land in the wield segment.
    assert sorted(row["vnum"] for row in slots_rows["wield"]) == [
        208, 209, 209]

    # Layout invariants the runtime shortcuts rely on: per slot, loot
    # records first, each region sorted by bound descending, and the
    # stored bound honestly bounds static + adept weapon score (with the
    # wield two-hander widening baked in).
    for slot, rows in slots_rows.items():
        loot_flags = [row["loot"] for row in rows]
        assert loot_flags == sorted(loot_flags, reverse=True)
        for region in (True, False):
            bounds = [row["bound"] for row in rows if row["loot"] == region]
            assert bounds == sorted(bounds, reverse=True)
        for row in rows:
            assert row["loot"] == (row["kind"] == "loot")
            wmax = inventory.gear_score_weapon_max(row["wbase"],
                                                   row["sharp"])
            if slot == "wield":
                wmax += wmax // 10
            assert row["bound"] == row["static"] + wmax

    # The string table is deduplicated: the fighter's name is stored once
    # even though two loot rows and mobs.bin-independent data cite it.
    assert blob.count(b"a fighter") == 1


def test_shipped_indexes_reproduce(tmp_path, monkeypatch):
    source = Path(build_mob_index.APPDIR)
    monkeypatch.setattr(build_mob_index, "OUTDIR", str(tmp_path))

    build_mob_index.main()

    for name in ("mobs.bin", "objs.bin", "foes.bin", "gear.bin"):
        assert (tmp_path / name).read_bytes() == (source / name).read_bytes()
