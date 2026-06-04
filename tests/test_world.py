from world import (
    ROOMS, ROOM_INIT, MOB_INIT, MOB_TEMPLATES, ITEM_TEMPLATES,
    M_DUMMY,
)


# ── Data integrity ────────────────────────────────────────────────────────────

def test_all_room_init_vnums_exist_in_rooms():
    """Every vnum in ROOM_INIT must have a matching entry in ROOMS."""
    for vnum in ROOM_INIT:
        assert vnum in ROOMS, f"ROOM_INIT vnum {vnum} missing from ROOMS"

def test_all_mob_init_templates_exist():
    """Every mob instance must reference a tpl vnum that exists in MOB_TEMPLATES."""
    for mob_id, inst in MOB_INIT.items():
        assert inst["tpl"] in MOB_TEMPLATES, f"mob {mob_id} has unknown tpl {inst['tpl']}"

def test_all_mob_init_rooms_exist():
    """Every mob instance must be placed in a room that exists in ROOMS."""
    for mob_id, inst in MOB_INIT.items():
        assert inst["room"] in ROOMS, f"mob {mob_id} has unknown room {inst['room']}"

def test_room_init_mob_ids_registered_in_mob_init():
    """Mob ids listed in ROOM_INIT must all be registered in MOB_INIT."""
    all_ids = set(MOB_INIT.keys())
    for vnum, rs in ROOM_INIT.items():
        for mid in rs["mobs"]:
            assert mid in all_ids, f"room {vnum} references unregistered mob id {mid}"

def test_all_room_exits_point_to_valid_rooms():
    """Every exit destination must be a room vnum that exists in ROOMS."""
    for vnum, room in ROOMS.items():
        for direction, dest in room["exits"].items():
            assert dest in ROOMS, f"room {vnum} exit {direction!r} leads to unknown room {dest}"

def test_mob_templates_have_required_fields():
    """All mob templates must carry the fields the combat and world systems expect."""
    required = {"name", "desc", "hp_max", "atk", "def", "xp", "loot", "respawn"}
    for vnum, tpl in MOB_TEMPLATES.items():
        missing = required - tpl.keys()
        assert not missing, f"template {vnum} missing fields {missing}"

def test_item_templates_have_required_fields():
    """All item templates must carry the fields the inventory and equip systems expect."""
    required = {"name", "desc", "type", "slot", "weight", "stats", "value"}
    for vnum, tpl in ITEM_TEMPLATES.items():
        missing = required - tpl.keys()
        assert not missing, f"item template {vnum} missing fields {missing}"

def test_mob_init_hp_matches_template_hp_max():
    """Each mob instance's starting HP must equal its template's hp_max."""
    for mob_id, inst in MOB_INIT.items():
        tpl = MOB_TEMPLATES[inst["tpl"]]
        assert inst["hp"] == tpl["hp_max"], \
            f"mob {mob_id} init hp {inst['hp']} != template hp_max {tpl['hp_max']}"


# ── Training dummy ────────────────────────────────────────────────────────────

def test_training_dummy_has_zero_atk():
    """The dummy must have atk=0 so calc_damage produces 0 and it never hurts the player."""
    assert MOB_TEMPLATES[M_DUMMY]["atk"] == 0

def test_training_dummy_has_zero_xp():
    """Fighting the dummy must grant no XP — it is not a real enemy."""
    assert MOB_TEMPLATES[M_DUMMY]["xp"] == 0

def test_training_dummy_has_no_loot():
    """The dummy must drop nothing on defeat."""
    assert MOB_TEMPLATES[M_DUMMY]["loot"] == []

