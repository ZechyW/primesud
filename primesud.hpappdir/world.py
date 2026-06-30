"""Mutable world catalog and state loaded from area data files."""

# Well-known VNUMs referenced by game logic (cf. area_limbo, area_school).
# These are literal constants so game modules can import them without
# triggering a full area-data load.
# -- area_limbo items --
I_COIN_SILVER_GCASH        = 1
I_COIN_GOLD_GCASH          = 2
I_COINS_GOLD_GCASH         = 3
I_COINS_SILVER_GCASH       = 4
I_COINS_SILVER_GOLD_GCASH  = 5
I_CORPSE                   = 10
I_CORPSE_11                = 11
I_MUSHROOM                 = 20
I_BALL_LIGHT               = 21
I_SPRING                   = 22
I_DISC_DISK_FLOATING_BLACK = 23
# -- area_school items --
I_MACE_SUB_MERC            = 3700
I_DAGGER_SUB_MERC          = 3701
I_SWORD_SUB_MERC           = 3702
I_VEST_SUB_MERC            = 3703
I_SHIELD_SUB_MERC          = 3704
I_DIPLOMA                  = 3715
I_BANNER_WAR_MERC          = 3716
I_SPEAR_SUB_MERC           = 3717
I_AXE_SUB_MERC             = 3719
I_FLAIL_SUB_MERC           = 3720
I_WHIP_SUB_MERC            = 3721
I_GLAIVE_SUB_MERC          = 3722

# List of (filename, area_tag) -- add/remove areas here only.
# Ascending size order: small areas load while heap is fresh (lower ms/KB),
# big areas load last where heap pressure is unavoidable anyway.
_AREA_FILES = [
    ("area_limbo.dat", "limbo"),
    ("area_quest.dat", "quest"),
    ("area_immort.dat", "immort"),
    ("area_mobfact.dat", "mobfact"),
    ("area_grave.dat", "grave"),
    ("area_plains.dat", "plains"),
    ("area_chapel.dat", "chapel"),
    ("area_school.dat", "mud_school"),
    ("area_shire.dat", "shire"),
    ("area_haon.dat", "haon"),
    ("area_ofcol2.dat", "ofcol2"),
    ("area_midgaard.dat", "midgaard"),
]

# -- Static definitions (populated by init_world, constant after) -----------
ROOM_DEFS = {}
MOB_DEFS = {}
ITEM_DEFS = {}
AREA_DEFS = []
DOOR_DEFS = {}
_WORLD_READY = False

# -- Mutable runtime state (mutated by reset_area / game functions) ---------
rooms = {}
chars = {}
areas = []
save_pending = False


def init_world():
    """Initialise merged world catalogs on first use."""
    global _WORLD_READY
    if _WORLD_READY:
        return

    ROOM_DEFS.clear()
    MOB_DEFS.clear()
    ITEM_DEFS.clear()
    del AREA_DEFS[:]
    DOOR_DEFS.clear()

    for _fname, _tag in _AREA_FILES:
        _ns = {}
        exec(open(_fname).read(), _ns)
        for _vnum, _room in _ns["ROOMS"].items():
            _room["area"] = _tag
            ROOM_DEFS[_vnum] = _room
        MOB_DEFS.update(_ns["MOBILES"])
        for _entry in _ns.get("SPECIALS", ()):
            if _entry[0] == "M" and _entry[1] in MOB_DEFS:
                MOB_DEFS[_entry[1]]["spec_fun"] = _entry[2]
        ITEM_DEFS.update(_ns["OBJECTS"])
        for _entry in _ns.get("SHOPS", ()):
            _keeper = _entry["keeper"]
            if _keeper in MOB_DEFS:
                MOB_DEFS[_keeper]["shop"] = _entry
        _adef = {"tag": _tag, "resets": _ns["RESETS"]}
        _adef.update(_ns["AREA"])
        AREA_DEFS.append(_adef)

    # Snapshot initial door closed/locked state for reset (cf. 1stMud reset_room door loop, db.c:1411)
    for _vnum, _room in ROOM_DEFS.items():
        for _d, _ev in _room.get("exits", {}).items():
            if isinstance(_ev, dict) and _ev.get("isdoor"):
                if _vnum not in DOOR_DEFS:
                    DOOR_DEFS[_vnum] = {}
                DOOR_DEFS[_vnum][_d] = {
                    "closed": bool(_ev.get("closed")),
                    "locked": bool(_ev.get("locked")),
                }

    _WORLD_READY = True
