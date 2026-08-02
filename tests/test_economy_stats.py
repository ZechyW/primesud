"""1stMud parity checks for death counters and bank/share economy."""

import economy
import game_state
import info
import keyidx
import shop
import world
from combat import update_death
from game_time import time_info
from player import create_char
from tools import build_mob_index


def _mob_row(vnum, keywords, name, level=7, home="alpha", tags=("alpha",)):
    """One mobs.bin row dict in pack_key_index's input shape."""
    return {"vnum": vnum, "level": level, "home": home,
            "keywords": keywords, "name": name, "tags": list(tags)}


def _write_key_index(path, rows, tags=None):
    """Pack rows through the builder so fixtures keep the shipped layout."""
    path.write_bytes(build_mob_index.pack_key_index(list(rows), tags))


def test_new_player_starts_with_school_donation_money():
    player = create_char()
    assert (player["gold"], player["silver"]) == (10, 100)


def _scene(fresh_world):
    fresh_world.register_area("alpha", 100, 199)
    fresh_world.register_area("beta", 200, 299)
    fresh_world.setup()
    world.ROOM_DEFS._data[100] = {"area": "alpha", "flags": {"bank": True}}
    world.ROOM_DEFS._data[200] = {"area": "beta", "flags": {}}
    world.rooms._data[100] = {"items": [], "mobs": []}
    world.rooms._data[200] = {"items": [], "mobs": []}
    world.MOB_DEFS._data[150] = {
        "short_descr": "a test goblin", "level": 7,
    }
    player = create_char()
    player["name"] = "Tester"
    player["room"] = 100
    player["silver"] = 0
    player["_macros"] = {}
    world.chars[1] = player
    return player


def test_update_death_uses_mob_and_area_perspective(fresh_world):
    player = _scene(fresh_world)
    mob = {"is_npc": True, "tpl": 150, "room": 200}  # wandered from alpha

    update_death(mob, player)
    assert world.mob_stats[150] == [0, 1]
    assert world.area_stats["beta"] == [0, 1]

    player["room"] = 200
    update_death(player, mob)
    assert world.mob_stats[150] == [1, 1]
    assert world.area_stats["beta"] == [1, 1]

    update_death(player, player)
    assert world.area_stats["beta"] == [1, 1]  # upstream excludes self-deaths


def test_empty_mob_counters_skip_index_read(fresh_world, monkeypatch):
    player = _scene(fresh_world)
    pages = []
    monkeypatch.setattr(info, "tpage", lambda lines: pages.append(lines))
    monkeypatch.setattr(keyidx, "load", lambda *args: (_ for _ in ()).throw(
        AssertionError("empty counters read mobs.bin")))

    info.do_mobkills(player, [])
    assert pages[-1][-1] == "No Mobs listed yet."


def test_counter_commands_keep_upstream_threshold_and_ranking(fresh_world,
                                                               monkeypatch,
                                                               tmp_path):
    player = _scene(fresh_world)
    pages = []
    index_file = tmp_path / "mobs.bin"
    _write_key_index(index_file, [
        _mob_row(150, "test goblin", "a test goblin"),
        _mob_row(152, "other goblin", "another goblin", level=8),
    ])
    monkeypatch.setattr(info, "MOB_INDEX_FILE", str(index_file))
    monkeypatch.setattr(world, "_ensure_area_by_tag",
                        lambda tag: (_ for _ in ()).throw(
                            AssertionError("counter loaded area " + tag)))
    monkeypatch.setattr(info, "tpage", lambda lines: pages.append(lines))
    world.mob_stats[150] = [2, 3]
    world.mob_stats[151] = [9, 9]  # stale vnum must not crash the listing
    world.area_stats["alpha"] = [4, 3]

    info.do_mobkills(player, [])
    assert pages[-1][-1] == "No Mobs listed yet."  # upstream requires >2
    info.do_mobdeaths(player, [])
    assert "a test goblin" in pages[-1][2]
    info.do_areakills(player, [])
    assert "alpha" in pages[-1][1].lower()


def test_counter_ranking_drops_stale_vnums_before_top_50(fresh_world,
                                                          monkeypatch,
                                                          tmp_path):
    player = _scene(fresh_world)
    rows = []
    for vnum in range(150, 201):
        rows.append(_mob_row(vnum, "mob", "mob " + str(vnum)))
        world.mob_stats[vnum] = [1000 - vnum, 0]
    world.mob_stats[149] = [9999, 0]  # stale; absent from index
    index_file = tmp_path / "mobs.bin"
    _write_key_index(index_file, rows)
    monkeypatch.setattr(info, "MOB_INDEX_FILE", str(index_file))
    pages = []
    monkeypatch.setattr(info, "tpage", lambda lines: pages.append(lines))

    info.do_mobkills(player, [])
    assert len(pages[-1]) == 52  # two headers plus full top 50
    assert "mob 199" in pages[-1][-1]


def test_add_cost_normalizes_silver_carry():
    wallet = {"gold": 0, "silver": 90}
    shop.add_cost(wallet, 20)
    assert (wallet["gold"], wallet["silver"]) == (1, 10)


def test_bank_round_trip_and_share_price_update(fresh_world, monkeypatch):
    player = _scene(fresh_world)
    out = []
    monkeypatch.setattr(economy, "chprintln", lambda ch, line: out.append(line))
    old_hour = time_info["hour"]
    try:
        time_info["hour"] = 12
        assert economy._amount("14k42", 0) == 14420  # upstream advatoi
        assert economy._atoi("14k") == 14  # upstream share commands use atoi
        player["gold"] = 1000
        economy.do_bank(player, ["deposit", "500"])
        economy.do_bank(player, ["buy", "3"])
        assert (player["gold"], player["gold_bank"], player["shares"]) == (500, 200, 3)

        monkeypatch.setattr(economy, "randint", lambda lo, hi: 1)
        economy.bank_update()  # (-99 / 10) truncates toward zero upstream
        assert world.share_value == 91

        world.mob_stats[150] = [4, 5]
        world.area_stats["alpha"] = [6, 7]
        game_state._serialize_world()

        player["gold_bank"] = 0
        player["shares"] = 0
        world.share_value = 100
        world.mob_stats.clear()
        world.area_stats.clear()
        assert game_state.load_world() == "file"
        assert (player["gold_bank"], player["shares"], world.share_value) == (200, 3, 91)
        assert world.mob_stats[150] == [4, 5]
        assert world.area_stats["alpha"] == [6, 7]
    finally:
        time_info["hour"] = old_hour


def test_bank_fixes_upstream_money_edge_cases(fresh_world, monkeypatch):
    player = _scene(fresh_world)
    out = []
    monkeypatch.setattr(economy, "chprintln", lambda ch, line: out.append(line))
    old_hour = time_info["hour"]
    try:
        time_info["hour"] = 19
        player["gold"] = 0
        player["silver"] = 500
        economy.do_bank(player, ["deposit", "5"])
        assert (player["gold"], player["silver"], player["gold_bank"]) == (0, 0, 5)

        player["gold"] = 1
        player["gold_bank"] = economy.MAX_GOLD
        economy.do_bank(player, ["deposit", "1"])
        assert (player["gold"], player["gold_bank"]) == (1, economy.MAX_GOLD)

        player["shares"] = 1
        economy.do_bank(player, ["sell", "1"])
        assert (player["shares"], player["gold_bank"]) == (1, economy.MAX_GOLD)

        time_info["hour"] = 20
        economy.do_bank(player, ["balance"])
        assert out[-1] == "The bank is closed, it is open from 4am to 8pm."
    finally:
        time_info["hour"] = old_hour
