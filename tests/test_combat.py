from unittest.mock import MagicMock
from combat import calc_damage, _try_special_move
from player import create_char
from world import I_DAGGER


# ── calc_damage ───────────────────────────────────────────────────────────────

def test_dummy_zero_atk_zero_power_deals_zero():
    """atk=0 and power=0 must produce 0 damage — the training dummy guarantee."""
    assert calc_damage(0, 0, 0) == 0

def test_equal_atk_def_result_near_power():
    """When atk == def the atk bonus is 0, so damage centres on power ± variance band."""
    for _ in range(50):
        dmg = calc_damage(10, 10, 10)
        assert 8 <= dmg <= 12

def test_excess_atk_increases_damage():
    """Atk well above def should add to the damage floor beyond power alone."""
    for _ in range(50):
        dmg = calc_damage(20, 5, 10)
        assert dmg >= 10

def test_high_def_clamps_atk_bonus():
    """Def higher than atk clamps the atk bonus to 0; raw equals power only."""
    for _ in range(50):
        dmg = calc_damage(5, 50, 10)
        assert 8 <= dmg <= 12

def test_low_raw_gives_zero_variance():
    """raw < 5 gives band = 0, so there is no variance and the result is deterministic."""
    assert calc_damage(0, 0, 4) == 4

def test_mod_atk_adds_to_atk():
    """mod_atk (e.g. from a buff) should raise damage at least as often as not."""
    for _ in range(50):
        base = calc_damage(5, 5, 10)
        boosted = calc_damage(5, 5, 10, mod_atk=5)
        assert boosted >= base

def test_mod_def_reduces_damage():
    """mod_def (e.g. from a debuff on the mob) should lower damage at least as often as not."""
    for _ in range(50):
        base = calc_damage(10, 0, 10)
        reduced = calc_damage(10, 0, 10, mod_def=10)
        assert reduced <= base


# ── _try_special_move ─────────────────────────────────────────────────────────

def _mock_tpl():
    return {"name": "Rat", "def": 0, "hp_max": 100}

def test_special_move_never_fires_when_armed():
    """Special moves are unarmed only — equipping any weapon must suppress them entirely."""
    player = create_char()
    player["equip"]["weapon"] = I_DAGGER
    tr = MagicMock()
    inst = {"hp": 100}
    for _ in range(20):
        assert _try_special_move(tr, player, inst, _mock_tpl()) == 0
    tr.print.assert_not_called()

def test_special_move_always_fires_at_max_dex():
    """With dex=100 the trigger chance (290 %) exceeds any randint(1,100) roll, so it always fires."""
    player = create_char()
    player["dex"] = 100
    player["str"] = 10
    tr = MagicMock()
    inst = {"hp": 100}
    result = _try_special_move(tr, player, inst, _mock_tpl())
    assert result > 0
    assert tr.print.called

def test_special_move_prints_mob_name():
    """The flavour text printed by a special move must include the target mob's name."""
    player = create_char()
    player["dex"] = 100
    tr = MagicMock()
    inst = {"hp": 100}
    tpl = {"name": "Goblin", "def": 0, "hp_max": 50}
    _try_special_move(tr, player, inst, tpl)
    printed = " ".join(str(c) for c in tr.print.call_args_list)
    assert "Goblin" in printed
