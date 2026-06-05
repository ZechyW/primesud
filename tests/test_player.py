from unittest.mock import patch
from player import (
    create_char, reset_area,
    get_curr_stat, get_obj_list, get_char_room,
    save_char, load_char,
)
from world import (
    I_SWORD_IRON, I_DAGGER, I_POTION_HP,
    ITEM_TEMPLATES, MOB_TEMPLATES, M_RAT,
)


# ── get_curr_stat ─────────────────────────────────────────────────────────────

def test_player_stat_returns_base_when_no_equip():
    """With no equipment, get_curr_stat should return the raw attribute value."""
    p = create_char()
    p["str"] = 14
    assert get_curr_stat(p, "str") == 14

def test_player_stat_adds_weapon_atk_bonus():
    """Equipping a weapon that grants +atk should be reflected in get_curr_stat('atk')."""
    p = create_char()
    p["equip"]["weapon"] = I_SWORD_IRON   # atk: 5
    base = p.get("atk", 0)
    assert get_curr_stat(p, "atk") == base + 5

def test_player_stat_no_bonus_for_unrelated_stat():
    """A weapon's atk bonus must not bleed into unrelated stats like def."""
    p = create_char()
    p["equip"]["weapon"] = I_SWORD_IRON
    assert get_curr_stat(p, "def") == p.get("def", 0)

def test_player_stat_none_slot_ignored():
    """Empty equipment slots (None) must be skipped without raising."""
    p = create_char()
    assert get_curr_stat(p, "atk") == p.get("atk", 0)


# ── get_obj_list ──────────────────────────────────────────────────────────────

_ITEMS = [I_SWORD_IRON, I_DAGGER, I_POTION_HP]

def test_resolve_name_exact_match():
    """An exact name match should return the correct item vnum."""
    result = get_obj_list("dagger", _ITEMS, ITEM_TEMPLATES)
    assert result == I_DAGGER

def test_resolve_name_prefix_match():
    """A prefix fragment should resolve to the item whose name starts with it."""
    result = get_obj_list("iron", _ITEMS, ITEM_TEMPLATES)
    assert result == I_SWORD_IRON

def test_resolve_name_case_insensitive():
    """Name lookup must be case-insensitive."""
    result = get_obj_list("DAGGER", _ITEMS, ITEM_TEMPLATES)
    assert result == I_DAGGER

def test_resolve_name_no_match_returns_none():
    """A fragment that matches nothing should return None, not raise."""
    result = get_obj_list("axe", _ITEMS, ITEM_TEMPLATES)
    assert result is None

def test_resolve_name_exact_beats_prefix():
    """An exact match must win over a prefix match even if both exist in the list."""
    result = get_obj_list("dagger", _ITEMS, ITEM_TEMPLATES)
    assert result == I_DAGGER


# ── get_char_room ─────────────────────────────────────────────────────────────

def test_resolve_mob_name_finds_by_name():
    """Looking up 'giant rat' should return a mob instance whose template is M_RAT."""
    _, instances = reset_area()
    ids = list(instances.keys())
    result = get_char_room("giant rat", ids, instances)
    assert result is not None
    assert instances[result]["tpl"] == M_RAT

def test_resolve_mob_name_prefix():
    """A prefix like 'gob' should resolve to the Goblin instance."""
    _, instances = reset_area()
    ids = list(instances.keys())
    result = get_char_room("gob", ids, instances)
    assert result is not None
    assert "Goblin" in MOB_TEMPLATES[instances[result]["tpl"]]["name"]

def test_resolve_mob_name_no_match_returns_none():
    """A name that matches no mob should return None."""
    _, instances = reset_area()
    ids = list(instances.keys())
    assert get_char_room("dragon", ids, instances) is None


# ── reset_area ────────────────────────────────────────────────────────────────

def test_room_state_has_items_and_mobs_lists():
    """Every room state entry must have both 'items' and 'mobs' as lists."""
    rs, _ = reset_area()
    for vnum, state in rs.items():
        assert "items" in state
        assert "mobs" in state
        assert isinstance(state["items"], list)
        assert isinstance(state["mobs"], list)

def test_mob_instances_have_required_fields():
    """Every mob instance must carry all fields the combat system reads."""
    _, instances = reset_area()
    for mob_id, inst in instances.items():
        for field in ("tpl", "hp", "room", "state", "respawn_at", "affects"):
            assert field in inst, f"mob {mob_id} missing field {field}"

def test_mob_instances_hp_matches_template():
    """Freshly initialised mob HP must equal the template's hp_max."""
    _, instances = reset_area()
    for inst in instances.values():
        tpl = MOB_TEMPLATES[inst["tpl"]]
        assert inst["hp"] == tpl["hp_max"]


# ── save_char / load_char round-trip ─────────────────────────────────────────

def test_save_load_preserves_player_fields(tmp_path):
    """Core player fields (name, level, xp) must survive a save/load cycle."""
    save_file = str(tmp_path / "test.sav")
    p = create_char()
    p["name"] = "Testero"
    p["level"] = 3
    p["xp"] = 75
    rs, mi = reset_area()

    with patch("player.SAVE_FILE", save_file):
        assert save_char(p, rs, mi)
        p2 = create_char()
        rs2, mi2 = reset_area()
        assert load_char(p2, rs2, mi2)

    assert p2["name"] == "Testero"
    assert p2["level"] == 3
    assert p2["xp"] == 75

def test_save_load_preserves_mob_tpl(tmp_path):
    """Each mob's template vnum must be correctly restored after loading."""
    save_file = str(tmp_path / "test.sav")
    rs, mi = reset_area()

    with patch("player.SAVE_FILE", save_file):
        save_char(create_char(), rs, mi)
        rs2, mi2 = reset_area()
        load_char(create_char(), rs2, mi2)

    for mob_id, inst in mi.items():
        assert mi2[mob_id]["tpl"] == inst["tpl"]

def test_load_returns_false_when_no_save(tmp_path):
    """Loading when no save file exists must return False cleanly, not raise."""
    save_file = str(tmp_path / "nosuchfile.sav")
    rs, mi = reset_area()
    with patch("player.SAVE_FILE", save_file):
        assert load_char(create_char(), rs, mi) is False

def test_save_load_preserves_inventory(tmp_path):
    """A player's inventory list must be identical before and after a save/load."""
    save_file = str(tmp_path / "test.sav")
    p = create_char()
    p["inv"] = [I_DAGGER, I_POTION_HP]
    rs, mi = reset_area()

    with patch("player.SAVE_FILE", save_file):
        save_char(p, rs, mi)
        p2 = create_char()
        rs2, mi2 = reset_area()
        load_char(p2, rs2, mi2)

    assert p2["inv"] == [I_DAGGER, I_POTION_HP]
