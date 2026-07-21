"""Mutable world catalog and state loaded from area data files."""

import terminal
import config

# Well-known VNUMs referenced by game logic (cf. area_limbo, area_school).
# Names match 1stMud's vnums.h (OBJ_VNUM_*) for easy comparison against the
# original sources. These are literal constants so game modules can import
# them without triggering a full area-data load.
# -- area_limbo items --
OBJ_VNUM_SILVER_ONE     = 1
OBJ_VNUM_GOLD_ONE       = 2
OBJ_VNUM_GOLD_SOME      = 3
OBJ_VNUM_SILVER_SOME    = 4
OBJ_VNUM_COINS          = 5
OBJ_VNUM_CORPSE_NPC     = 10
OBJ_VNUM_CORPSE_PC      = 11
OBJ_VNUM_MUSHROOM       = 20
OBJ_VNUM_LIGHT_BALL     = 21
OBJ_VNUM_SPRING         = 22
OBJ_VNUM_DISC           = 23
OBJ_VNUM_PORTAL         = 25
# [PRIMESUD] 1stMud uses vnum 1001 (vnums.h); the rose object's canonical
# vnum sits outside limbo's 1-99 range, so it is remapped here instead of
# added at 1001 (which would spill into a different area's vnum span).
OBJ_VNUM_ROSE           = 26
# -- area_school items --
OBJ_VNUM_SCHOOL_MACE    = 3700
OBJ_VNUM_SCHOOL_DAGGER  = 3701
OBJ_VNUM_SCHOOL_SWORD   = 3702
OBJ_VNUM_SCHOOL_VEST    = 3703
OBJ_VNUM_SCHOOL_SHIELD  = 3704
OBJ_VNUM_DIPLOMA        = 3715  # [PRIMESUD] no vnums.h entry upstream
OBJ_VNUM_SCHOOL_BANNER  = 3716
OBJ_VNUM_SCHOOL_STAFF   = 3718  # weapon_table's spear-class item is the staff,
                                # not 3717 (SCHOOL_SPEAR, unused upstream)
OBJ_VNUM_SCHOOL_AXE     = 3719
OBJ_VNUM_SCHOOL_FLAIL   = 3720
OBJ_VNUM_SCHOOL_WHIP    = 3721
OBJ_VNUM_SCHOOL_POLEARM = 3722

# Area files: (filename, tag, display_name, vnum_lo, vnum_hi).
# Ascending size order: small areas load while heap is fresh (lower ms/KB),
# big areas load last where heap pressure is unavoidable anyway.
_AREA_FILES = [
    ("area_ofcol.txt", "ofcol", "Ofcol", 5500, 5599),                 # 7084 bytes
    ("area_limbo.txt", "limbo", "Limbo", 1, 99),                      # 9466 bytes
    ("area_quest.txt", "quest", "Quest", 200, 249),                   # 12528 bytes
    ("area_trollden.txt", "trollden", "Troll Den", 2800, 2899),       # 19073 bytes
    ("area_redferne.txt", "redferne", "Redferne's", 7900, 7999),      # 20405 bytes
    ("area_daycare.txt", "daycare", "Day Care", 6600, 6699),          # 23024 bytes
    ("area_air.txt", "air", "In the Air", 1000, 1099),                # 24083 bytes
    ("area_mobfact.txt", "mobfact", "Mob Factory", 9400, 9499),       # 24889 bytes
    ("area_immort.txt", "immort", "Valhalla", 1200, 1299),            # 26758 bytes
    ("area_smurf.txt", "smurf", "Smurfville", 100, 199),              # 32221 bytes
    ("area_grave.txt", "grave", "Graveyard", 3600, 3699),             # 32513 bytes
    ("area_marsh.txt", "marsh", "Marsh", 8300, 8399),                 # 35321 bytes
    ("area_dream.txt", "dream", "Machine Dreams", 8600, 8699),        # 35713 bytes
    ("area_mega1.txt", "mega1", "Mega City One", 8000, 8099),         # 39140 bytes
    ("area_grove.txt", "grove", "Holy Grove", 8900, 8999),            # 41050 bytes
    ("area_drow.txt", "drow", "Drow City", 5100, 5199),               # 42409 bytes
    ("area_midennir.txt", "midennir", "Miden'nir", 3500, 3599),       # 43104 bytes
    ("area_arachnos.txt", "arachnos", "Arachnos", 6200, 6399),        # 44543 bytes
    ("area_nirvana.txt", "nirvana", "Nirvana", 9000, 9099),           # 45281 bytes
    ("area_plains.txt", "plains", "Plains", 300, 399),                # 45308 bytes
    ("area_dwarven.txt", "dwarven", "Dwarven Kingdom", 6500, 6599),   # 49806 bytes
    ("area_dylan.txt", "dylan", "Dylan's Area", 9100, 9199),          # 51484 bytes
    ("area_eastern.txt", "eastern", "Sands of Sorrow", 5000, 5099),   # 52160 bytes
    ("area_hood.txt", "hood", "Gangland", 2100, 2199),                # 55546 bytes
    ("area_catacomb.txt", "catacomb", "Catacombs", 2000, 2099),       # 60170 bytes
    ("area_draconia.txt", "draconia", "Dragon Tower", 2200, 2299),    # 64023 bytes
    ("area_olympus.txt", "olympus", "Olympus", 900, 999),             # 65354 bytes
    ("area_wyvern.txt", "wyvern", "Wyvern's Tower", 1600, 1799),      # 67450 bytes
    ("area_valley.txt", "valley", "Valley of the Elves", 7800, 7899), # 70719 bytes
    ("area_chapel.txt", "chapel", "Chapel", 3400, 3499),              # 71267 bytes
    ("area_thalos.txt", "thalos", "Thalos", 5200, 5299),              # 72345 bytes
    ("area_gnome.txt", "gnome", "Gnome Village", 1500, 1599),         # 74271 bytes
    ("area_galaxy.txt", "galaxy", "Galaxy", 9300, 9399),              # 74643 bytes
    ("area_school.txt", "mud_school", "Mud School", 3700, 3799),      # 76023 bytes
    ("area_shire.txt", "shire", "Shire", 1100, 1199),                 # 79009 bytes
    ("area_canyon.txt", "canyon", "Elemental Canyon", 9200, 9299),    # 79432 bytes
    ("area_pyramid.txt", "pyramid", "Pyramid", 8700, 8799),           # 85380 bytes
    ("area_haon.txt", "haon", "Haon Dor", 6000, 6199),                # 85969 bytes
    ("area_moria.txt", "moria", "Moria", 3900, 4199),                 # 98773 bytes
    ("area_mirror.txt", "mirror", "Old Thalos", 5300, 5399),          # 110420 bytes
    ("area_astral.txt", "astral", "Astral Plane", 7700, 7799),        # 112453 bytes
    ("area_ofcol2.txt", "ofcol2", "New Ofcol", 600, 699),             # 126239 bytes
    ("area_mahntor.txt", "mahntor", "Mahn-Tor", 2300, 2399),          # 140720 bytes
    ("area_sewer.txt", "sewer", "Sewers", 7000, 7499),                # 158284 bytes
    ("area_tohell.txt", "tohell", "Hell", 10400, 10599),              # 195277 bytes
    ("area_hitower.txt", "hitower", "High Tower", 1300, 1499),        # 204451 bytes
    ("area_midgaard.txt", "midgaard", "Midgaard", 3000, 3399),        # 259207 bytes
    ("area_newthalos.txt", "newthalos", "New Thalos", 9500, 9799),    # 265007 bytes
]

# Area level ranges, duplicated from each area file's AREA["levels"] so
# quest target selection can filter areas without triggering their load.
# Keep in sync with the area files -- tools/gen_area_adj.py cross-checks
# and exits nonzero on drift. [PRIMESUD]
AREA_LEVELS = {
    "ofcol":      (1, 50),
    "limbo":      (1, 60),
    "quest":      (1, 60),
    "immort":     (51, 60),
    "mobfact":    (5, 15),
    "grave":      (5, 10),
    "plains":     (1, 20),
    "chapel":     (15, 25),
    "mud_school": (1, 5),
    "shire":      (5, 35),
    "haon":       (5, 10),
    "moria":      (5, 15),
    "ofcol2":     (5, 35),
    "midgaard":   (1, 50),
    "trollden":   (10, 15),
    "marsh":      (15, 25),
    "arachnos":   (5, 20),
    "sewer":      (5, 30),
    "tohell":     (32, 51),
    "newthalos":  (10, 35),
    "air":        (5, 10),
    "astral":     (10, 35),
    "canyon":     (5, 30),
    "catacomb":   (10, 20),
    "daycare":    (1, 5),
    "draconia":   (5, 30),
    "dream":      (1, 5),
    "drow":       (15, 25),
    "dwarven":    (10, 25),
    "dylan":      (15, 25),
    "eastern":    (10, 20),
    "galaxy":     (20, 30),
    "gnome":      (5, 15),
    "grove":      (5, 20),
    "hitower":    (10, 30),
    "hood":       (5, 15),
    "mahntor":    (5, 35),
    "mega1":      (5, 35),
    "midennir":   (5, 15),
    "mirror":     (1, 30),
    "nirvana":    (30, 35),
    "olympus":    (5, 50),
    "pyramid":    (1, 60),  # credits carry "5-50" (unparsed -> converter default)
    "redferne":   (20, 30),
    "smurf":      (1, 10),
    "thalos":     (10, 25),
    "valley":     (5, 20),
    "wyvern":     (5, 30),
}

# -- BEGIN GENERATED: tools/gen_area_adj.py (do not hand-edit) --
# AREA_BUILDERS: {tag: builder name}, extracted from each area's credits
# line (cf. info._extract_builder). AREA_LVL_COMMENTS: {tag: level
# comment} for areas whose credits carry a non-numeric level token
# ("All", "None"), shown verbatim in the do_areas level slot (cf.
# 1stMud lvl_comment). AREA_ADJ: {tag: sorted tuple of neighbor tags
# reachable via a room exit}, computed from ROOMS exits. Lets
# do_areas/do_run consult this data without loading area files at
# runtime. AREA_ROOM_COUNTS: {tag: explorable room count} for
# do_explored/score (cf. 1stMud arearooms/top_explored); world total
# = sum of values. Regenerate with: python tools/gen_area_adj.py
# [PRIMESUD]
AREA_BUILDERS = {
    "ofcol":      "Alfa",
    "limbo":      "Diku",
    "quest":      "1stMud",
    "trollden":   "Merc",
    "redferne":   "Diku",
    "daycare":    "Sandman",
    "air":        "Copper",
    "mobfact":    "PinkF",
    "immort":     "ROM",
    "smurf":      "Generic",
    "grave":      "Alfa",
    "marsh":      "Generic",
    "dream":      "Furey",
    "mega1":      "Glop",
    "grove":      "Alfa",
    "drow":       "Drkside",
    "midennir":   "Copper",
    "arachnos":   "Mahatma",
    "nirvana":    "Fstall",
    "plains":     "Copper",
    "dwarven":    "Anon",
    "dylan":      "Dylan",
    "eastern":    "Anon",
    "hood":       "Raff",
    "catacomb":   "Raff",
    "draconia":   "Wench",
    "olympus":    "Generic",
    "wyvern":     "Tyrst",
    "valley":     "Hatchet",
    "chapel":     "Copper",
    "thalos":     "Drkside",
    "gnome":      "Vougon",
    "galaxy":     "Doctor",
    "mud_school": "Hatchet",
    "shire":      "Poohb",
    "canyon":     "Raff",
    "pyramid":    "Andersen",
    "haon":       "Diku",
    "moria":      "Alfa",
    "mirror":     "Kahn",
    "astral":     "Andersen",
    "ofcol2":     "Hatchet",
    "mahntor":    "Chris",
    "sewer":      "Diku",
    "tohell":     "Strahd",
    "hitower":    "Skylar",
    "midgaard":   "Diku",
    "newthalos":  "Conner",
}

AREA_LVL_COMMENTS = {
    "ofcol":    "All",
    "limbo":    "None",
    "quest":    "None",
    "pyramid":  "5-50",
    "midgaard": "All",
}

_AREA_ADJ = {
    "ofcol":      ("ofcol2", "plains"),
    "limbo":      ("midgaard",),
    "quest":      ("midgaard",),
    "trollden":   ("haon",),
    "redferne":   ("dylan", "midgaard"),
    "daycare":    ("dwarven",),
    "air":        ("astral", "midgaard"),
    "mobfact":    ("midgaard",),
    "immort":     ("limbo", "midgaard"),
    "smurf":      ("midennir",),
    "grave":      ("chapel", "midgaard"),
    "marsh":      ("haon",),
    "dream":      ("midgaard",),
    "mega1":      ("eastern",),
    "grove":      ("midennir", "mirror", "nirvana"),
    "drow":       ("thalos",),
    "midennir":   ("gnome", "grove", "midgaard", "moria", "newthalos", "smurf", "thalos"),
    "arachnos":   ("haon",),
    "nirvana":    ("grove",),
    "plains":     ("moria", "ofcol", "olympus", "valley"),
    "dwarven":    ("catacomb", "daycare", "moria"),
    "dylan":      ("midgaard", "redferne"),
    "eastern":    ("mega1", "midgaard", "pyramid"),
    "hood":       ("midgaard",),
    "catacomb":   ("dwarven",),
    "draconia":   ("hitower",),
    "olympus":    ("plains",),
    "wyvern":     ("thalos",),
    "valley":     ("plains",),
    "chapel":     ("grave", "tohell"),
    "thalos":     ("canyon", "drow", "mahntor", "midennir", "wyvern"),
    "gnome":      ("midennir",),
    "galaxy":     ("hitower", "thalos"),
    "mud_school": ("midgaard",),
    "shire":      ("haon", "midgaard"),
    "canyon":     ("thalos",),
    "pyramid":    ("eastern",),
    "haon":       ("arachnos", "hitower", "marsh", "midgaard", "newthalos", "shire", "trollden"),
    "moria":      ("dwarven", "midennir", "midgaard", "plains", "sewer"),
    "mirror":     ("grove",),
    "astral":     ("air",),
    "ofcol2":     ("ofcol",),
    "mahntor":    ("thalos",),
    "sewer":      ("midgaard",),
    "tohell":     ("chapel",),
    "hitower":    ("chapel", "draconia", "drow", "dylan", "galaxy", "haon", "midgaard", "olympus", "sewer"),
    "midgaard":   ("air", "dream", "eastern", "grave", "haon", "hood", "immort", "limbo", "midennir", "mobfact", "moria", "mud_school", "newthalos", "quest", "redferne", "sewer"),
    "newthalos":  ("haon", "midennir", "midgaard"),
}

AREA_ROOM_COUNTS = {
    "ofcol":      8,
    "limbo":      3,
    "quest":      3,
    "trollden":   5,
    "redferne":   17,
    "daycare":    19,
    "air":        40,
    "mobfact":    25,
    "immort":     22,
    "smurf":      29,
    "grave":      33,
    "marsh":      18,
    "dream":      36,
    "mega1":      28,
    "grove":      22,
    "drow":       51,
    "midennir":   52,
    "arachnos":   56,
    "nirvana":    60,
    "plains":     44,
    "dwarven":    51,
    "dylan":      88,
    "eastern":    47,
    "hood":       70,
    "catacomb":   69,
    "draconia":   44,
    "olympus":    50,
    "wyvern":     61,
    "valley":     84,
    "chapel":     67,
    "thalos":     81,
    "gnome":      89,
    "galaxy":     61,
    "mud_school": 59,
    "shire":      58,
    "canyon":     55,
    "pyramid":    60,
    "haon":       71,
    "moria":      121,
    "mirror":     86,
    "astral":     80,
    "ofcol2":     100,
    "mahntor":    100,
    "sewer":      177,
    "tohell":     141,
    "hitower":    183,
    "midgaard":   143,
    "newthalos":  257,
}
# -- END GENERATED --

# -- Lazy loading state -------------------------------------------------------
_LOADED_AREAS = set()
_TAG_TO_FILE = {}
_TAG_TO_NAME = {}
_VNUM_RANGES = []
_pending_mob_saves = {}    # {tpl_vnum: [room_vnum, ...]} from save data
_pending_room_items = {}   # {rvnum: "raw|token|string"} from save data
mob_stats = {}             # {tpl_vnum: [kills, deaths]} (cf. CharIndex)
area_stats = {}            # {area_tag: [kills, deaths]} (cf. AreaData)
share_value = 100          # cf. 1stMud mud_info.share_value
_reset_queue = []          # iterative drain prevents stack overflow
_draining = False
_LOADING_ALL = False
# -- Far-area eviction state (see maybe_evict) [PRIMESUD] -----------------------
_PINNED = ("limbo",)       # corpse/coin/portal templates spawn on every kill
_player_room = None        # maybe_evict fast path: room unchanged -> no work
_area_seq = {}             # tag -> visit counter (LRU eviction order)
_seq_counter = 0


class LazyDict:
    """Dict wrapper that loads area data on demand via vnum range lookup. [PRIMESUD]"""

    def __init__(self, load_all_on_iter=True):
        self._data = {}
        self._lai = load_all_on_iter

    def __getitem__(self, key):
        if key not in self._data:
            _ensure_area(key)
        return self._data[key]

    def __contains__(self, key):
        if key in self._data:
            return True
        _ensure_area(key)
        return key in self._data

    def __setitem__(self, key, value):
        self._data[key] = value

    def __delitem__(self, key):
        del self._data[key]

    def __len__(self):
        if self._lai:
            _load_all()
        return len(self._data)

    def __iter__(self):
        if self._lai:
            _load_all()
        return iter(self._data)

    def get(self, key, default=None):
        if key not in self._data:
            _ensure_area(key)
        return self._data.get(key, default)

    def items(self):
        if self._lai:
            _load_all()
        return self._data.items()

    def values(self):
        if self._lai:
            _load_all()
        return self._data.values()

    def keys(self):
        if self._lai:
            _load_all()
        return self._data.keys()

    def update(self, other):
        self._data.update(other)

    def clear(self):
        self._data.clear()

    def pop(self, key, *args):
        return self._data.pop(key, *args)

    def setdefault(self, key, default=None):
        if key not in self._data:
            _ensure_area(key)
        return self._data.setdefault(key, default)


def _vnum_to_tag(vnum):
    """Return area tag owning a vnum, or None. [PRIMESUD]"""
    if vnum is None:  # blind exits ("to": None) probe ROOM_DEFS with None
        return None
    for lo, hi, tag in _VNUM_RANGES:
        if lo <= vnum <= hi:
            return tag
    return None


def _ensure_area(vnum):
    """Load the area owning vnum if not already loaded. [PRIMESUD]"""
    tag = _vnum_to_tag(vnum)
    if tag and tag not in _LOADED_AREAS:
        _load_area(tag)


def _ensure_area_by_tag(tag):
    """Load area by tag if not already loaded. [PRIMESUD]"""
    if tag and tag not in _LOADED_AREAS and tag in _TAG_TO_FILE:
        _load_area(tag)


def _load_all():
    """Load all unloaded areas. [PRIMESUD]"""
    global _LOADING_ALL
    _LOADING_ALL = True
    try:
        for _, tag, _, _, _ in _AREA_FILES:
            if tag not in _LOADED_AREAS:
                _load_area(tag)
    finally:
        _LOADING_ALL = False


def _loading_notice(tag):
    """Print a subtle notice before slow lazy area loading. [PRIMESUD]"""
    if _LOADING_ALL:
        return
    try:
        if terminal.tr is not None:
            terminal.tprint("{D[Loading area: " + _TAG_TO_NAME.get(tag, tag) + "]{x")
    except Exception:
        pass


def _load_area(tag):
    """Load one area on demand: exec data file, merge defs, queue reset. [PRIMESUD]

    Args:
        tag (str): Area tag (e.g. "midgaard").
    """
    global _draining
    _loading_notice(tag)
    # Explicit close: MicroPython has no refcounting, so open().read()
    # leaks the handle until (if ever) GC finalization -- the Prime's FD
    # table is small and repeated loads exhaust it (OSError: 0 on open).
    with open(_TAG_TO_FILE[tag]) as _f:
        _src = _f.read()
    _ns = {}
    exec(_src, _ns)
    _src = None  # release before the merge allocations below

    _room_vnums = []
    for _vnum, _room in _ns["ROOMS"].items():
        _room["area"] = tag
        ROOM_DEFS._data[_vnum] = _room
        _room_vnums.append(_vnum)
        for _d, _ev in _room.get("exits", {}).items():
            if isinstance(_ev, dict) and _ev.get("isdoor"):
                if _vnum not in DOOR_DEFS:
                    DOOR_DEFS[_vnum] = {}
                DOOR_DEFS[_vnum][_d] = {
                    "closed": bool(_ev.get("closed")),
                    "locked": bool(_ev.get("locked")),
                }
    MOB_DEFS.update(_ns["MOBILES"])
    ITEM_DEFS.update(_ns["OBJECTS"])
    # Program tables are optional so synthetic/older generated area files
    # remain loadable. Real area files emit all three, empty when unused.
    # [PRIMESUD]
    MOBPROGS.update(_ns.get("MOBPROGS", {}))
    OBJPROGS.update(_ns.get("OBJPROGS", {}))
    ROOMPROGS.update(_ns.get("ROOMPROGS", {}))
    # Partition resets to per-room lists (cf. 1stMud pRoom->reset_first).
    # Cross-area resets (target room in a different area) are deferred to
    # avoid the cascade-load race: accessing ROOM_DEFS[cross_vnum] via
    # LazyDict triggers the target area's load+reset before this area
    # finishes partitioning, so the cross-area reset misses the first
    # reset cycle (bug #16).
    _cur_rvnum = None
    _cross_area_rooms = set()
    for _entry in _ns["RESETS"]:
        _cmd = _entry[0]
        if _cmd == "M":
            _cur_rvnum = _entry[3]
        elif _cmd == "O":
            _cur_rvnum = _entry[2]
        elif _cmd == "R":
            # 'R' attaches to its own arg1 room (cf. db.c load_resets:827);
            # like M/O it sets the running room context.  Without this an 'R'
            # that precedes any M/O (e.g. the daycare maze) would be dropped.
            _cur_rvnum = _entry[1]
        if _cur_rvnum is None:
            continue
        if _cur_rvnum in _room_vnums:
            _rdef = ROOM_DEFS._data[_cur_rvnum]
            if "resets" not in _rdef:
                _rdef["resets"] = []
            _rdef["resets"].append(_entry)
        else:
            # Cross-area: access via LazyDict to trigger target load, but
            # partition after own reset so target's first reset sees them.
            _cross_area_rooms.add(_cur_rvnum)

    # Pull cross-area resets that other loaded areas own targeting our
    # rooms.  The owner appends its cross-entries only into rooms that were
    # resident at its load (see _reset_loaded_area); if we load (or reload
    # after eviction) later, we pull them here instead.  The two paths are
    # disjoint by construction -- appending in both would duplicate resets.
    _rvs = set(_room_vnums)
    for _oa in AREA_DEFS:
        if _oa["tag"] == tag or _oa["tag"] not in _LOADED_AREAS:
            continue
        _cur_rvnum = None
        for _entry in _oa["resets"]:
            _cmd = _entry[0]
            if _cmd == "M":
                _cur_rvnum = _entry[3]
            elif _cmd == "O":
                _cur_rvnum = _entry[2]
            elif _cmd == "R":
                _cur_rvnum = _entry[1]
            if _cur_rvnum is not None and _cur_rvnum in _rvs:
                _rdef = ROOM_DEFS._data[_cur_rvnum]
                if "resets" not in _rdef:
                    _rdef["resets"] = []
                _rdef["resets"].append(_entry)

    # Update AREA_DEFS entry with full metadata
    _adef = None
    for _a in AREA_DEFS:
        if _a["tag"] == tag:
            _adef = _a
            break
    _adef["resets"] = _ns["RESETS"]
    _adef.update(_ns["AREA"])
    _adef["room_vnums"] = _room_vnums

    _LOADED_AREAS.add(tag)

    # Queue reset; drain iteratively to prevent stack overflow from
    # cross-area LazyDict lookups during create_object/create_mobile.
    _reset_queue.append((tag, _adef, _room_vnums, _cross_area_rooms))
    if not _draining:
        _draining = True
        try:
            while _reset_queue:
                _reset_loaded_area(*_reset_queue.pop(0))
        finally:
            _draining = False


def _reset_loaded_area(tag, _adef, _room_vnums, _cross_area_rooms):
    """Reset a loaded area and apply pending deltas. [PRIMESUD]"""
    from mob import reset_area, reset_room, _object_count_map  # deferred: mob imports world
    reset_area(_adef)

    if _cross_area_rooms:
        # Split targets by residency BEFORE any LazyDict access: rooms
        # already resident get our entries appended (and reset) here;
        # unloaded targets are only touched to trigger their load --
        # their _load_area pulls our entries from _adef["resets"] itself.
        # Appending here AND letting the pull run would duplicate resets.
        _preloaded = set(_rv for _rv in _cross_area_rooms
                         if _rv in ROOM_DEFS._data)
        _cur_rvnum = None
        for _entry in _adef["resets"]:
            _cmd = _entry[0]
            if _cmd == "M":
                _cur_rvnum = _entry[3]
            elif _cmd == "O":
                _cur_rvnum = _entry[2]
            elif _cmd == "R":
                _cur_rvnum = _entry[1]
            if _cur_rvnum is not None and _cur_rvnum in _preloaded:
                _rdef = ROOM_DEFS._data[_cur_rvnum]
                if "resets" not in _rdef:
                    _rdef["resets"] = []
                _rdef["resets"].append(_entry)
        for _rv in _cross_area_rooms:
            if _rv not in _preloaded:
                _ensure_area(_rv)
        _next_id = max(chars, default=1) + 1
        _obj_counts = _object_count_map()
        for _rv in _preloaded:
            if _rv in rooms:
                _next_id = reset_room(_rv, _next_id, _obj_counts)

    _apply_pending_deltas(tag, _room_vnums)

    if areas:
        for _s in areas:
            if _s["tag"] == tag:
                _s["room_vnums"] = _room_vnums
                _s["age"] = 0
                break


def _apply_pending_deltas(tag, room_vnums):
    """Apply buffered save deltas after area load. [PRIMESUD]

    Mob deltas: kill excess instances, move remaining to saved rooms.
    Cross-area wanderers (mob from area A at room in area B) are skipped
    by the ``_vnum_to_tag(_tpl) != tag`` guard -- their saved position is
    silently lost.  This matches 1stMud's effective behavior: NPC positions
    are never persisted, and the 5% per-tick despawn (update.c:541) keeps
    cross-area wanderers short-lived.  The mob respawns at its home room
    on next area reset.

    Args:
        tag (str): Area tag just loaded.
        room_vnums (list): Room vnums belonging to this area.
    """
    _rvnum_set = set(room_vnums)

    for _tpl in list(_pending_mob_saves):
        if _vnum_to_tag(_tpl) != tag:
            continue
        _saved = _pending_mob_saves[_tpl]
        # Owned pets are persisted via p.pet, not m. lines -- never count or
        # cull them against saved template positions. [PRIMESUD]
        _ids = sorted(i for i, inst in chars.items()
                      if inst.get("is_npc") and inst["tpl"] == _tpl
                      and not (inst.get("act_flags", {}).get("pet")
                               and inst.get("master") is not None))
        if not _ids:
            continue
        for _mid in _ids[len(_saved):]:
            _old = chars[_mid]["room"]
            if _old in rooms._data:
                _ml = rooms._data[_old]["mobs"]
                if _mid in _ml:
                    _ml.remove(_mid)
            del chars[_mid]
        _deferred = []
        for _mid, _rv in zip(_ids, _saved):
            _old = chars[_mid]["room"]
            if _rv == _old:
                continue
            if _rv not in rooms._data:
                _deferred.append(_rv)
                continue
            if _old in rooms._data:
                _ml = rooms._data[_old]["mobs"]
                if _mid in _ml:
                    _ml.remove(_mid)
            chars[_mid]["room"] = _rv
            rooms._data[_rv]["mobs"].append(_mid)
        if _deferred:
            _pending_mob_saves[_tpl] = _deferred
        else:
            del _pending_mob_saves[_tpl]

    from item import parse_item_token  # deferred: item imports world
    for _rv in list(_pending_room_items):
        if _rv not in _rvnum_set:
            continue
        _raw = _pending_room_items.pop(_rv)
        if _rv in rooms._data:
            rooms._data[_rv]["items"] = [parse_item_token(v)
                                         for v in _raw.split("|") if v]


def _retry_pending_deltas():
    """Retry pending deltas for all loaded areas. [PRIMESUD]

    Called after load_world to handle deltas that were skipped because
    the destination area's rooms weren't in rooms._data yet (cascade
    during reset partitioning runs before reset_area creates room state).
    """
    for _a in AREA_DEFS:
        if _a["tag"] in _LOADED_AREAS and "room_vnums" in _a:
            _apply_pending_deltas(_a["tag"], _a["room_vnums"])


def _unload_area(tag):
    """Evict one loaded area: buffer live state as save deltas, drop defs. [PRIMESUD]

    Inverse of _load_area.  Mob positions and floor items are written to
    _pending_mob_saves / _pending_room_items in the exact shape the save
    system uses, so reload replays them through _apply_pending_deltas just
    like a game load.  Dropped without recording (same as save/load):
    live door state (rebuilt from area file), mob hp/inventory (fresh from
    template on reset), and foreign-template wanderers standing in evicted
    rooms (respawn at home on their area's next reset).

    Caller must guarantee the area holds nothing player-critical (the pet,
    combatants, the player itself) -- maybe_evict's keep-set does.
    """
    _adef = None
    for _a in AREA_DEFS:
        if _a["tag"] == tag:
            _adef = _a
            break
    if _adef is None or "room_vnums" not in _adef:
        return
    _room_vnums = _adef["room_vnums"]
    _rvnum_set = set(_room_vnums)
    _lo = _hi = None
    for _l, _h, _t in _VNUM_RANGES:
        if _t == tag:
            _lo, _hi = _l, _h
            break

    # Remove our cross-area reset entries from resident foreign rooms, or
    # reload would append them a second time (duplicate mobs/objects).
    _cur_rvnum = None
    for _entry in _adef["resets"]:
        _cmd = _entry[0]
        if _cmd == "M":
            _cur_rvnum = _entry[3]
        elif _cmd == "O":
            _cur_rvnum = _entry[2]
        elif _cmd == "R":
            _cur_rvnum = _entry[1]
        if _cur_rvnum is not None and _cur_rvnum not in _rvnum_set:
            _rdef = ROOM_DEFS._data.get(_cur_rvnum)
            if _rdef and "resets" in _rdef:
                try:
                    _rdef["resets"].remove(_entry)
                except ValueError:
                    pass

    # Buffer mob positions: our templates wherever they stand (mirrors the
    # m.<tpl>= save lines; sorted ids match _apply_pending_deltas), then
    # delete them plus foreign wanderers standing in our rooms.  The pet is
    # excluded like the save path (persisted via p.pet).
    _pet = chars[1].get("pet") if 1 in chars else None
    _tpl_rooms = {}
    _dead = []
    for _mid in sorted(chars):
        _inst = chars[_mid]
        if not _inst.get("is_npc") or _mid == _pet:
            continue
        _tpl = _inst["tpl"]
        if _lo is not None and _lo <= _tpl <= _hi:
            _tpl_rooms.setdefault(_tpl, []).append(_inst["room"])
            _dead.append(_mid)
        elif _inst["room"] in _rvnum_set:
            _dead.append(_mid)
    for _tpl in _tpl_rooms:
        # Overwrites any deferred pending entry for this template --
        # deferred moves into still-unloaded areas are dropped, matching
        # the documented wanderer-position-loss semantics.
        _pending_mob_saves[_tpl] = _tpl_rooms[_tpl]
    _dead_set = set(_dead)
    for _mid in _dead:
        _rv = chars[_mid]["room"]
        if _rv in rooms._data and _rv not in _rvnum_set:
            _ml = rooms._data[_rv]["mobs"]
            if _mid in _ml:
                _ml.remove(_mid)
        del chars[_mid]
    if _dead_set:
        for _inst in chars.values():
            if _inst.get("fighting") in _dead_set:
                _inst["fighting"] = None

    # Buffer floor items (mirrors the r.<vnum>.items= save lines).
    from item import serialize_item_token  # deferred: item imports world
    for _rv in _room_vnums:
        _rs = rooms._data.get(_rv)
        if _rs and _rs["items"]:
            _toks = []
            for _o in _rs["items"]:
                _toks.append(serialize_item_token(_o))
            _pending_room_items[_rv] = "|".join(_toks)

    # Drop definitions and runtime state.
    for _rv in _room_vnums:
        ROOM_DEFS._data.pop(_rv, None)
        rooms._data.pop(_rv, None)
        DOOR_DEFS.pop(_rv, None)
    if _lo is not None:
        for _k in [k for k in MOB_DEFS._data if _lo <= k <= _hi]:
            del MOB_DEFS._data[_k]
        for _k in [k for k in ITEM_DEFS._data if _lo <= k <= _hi]:
            del ITEM_DEFS._data[_k]
        for _k in [k for k in MOBPROGS if _lo <= k <= _hi]:
            del MOBPROGS[_k]
        for _k in [k for k in OBJPROGS if _lo <= k <= _hi]:
            del OBJPROGS[_k]
        for _k in [k for k in ROOMPROGS if _lo <= k <= _hi]:
            del ROOMPROGS[_k]
    _adef["resets"] = []
    _adef.pop("room_vnums", None)
    for _s in areas:
        if _s["tag"] == tag:
            _s.pop("room_vnums", None)  # area_update skips it while evicted
            break
    _LOADED_AREAS.discard(tag)


def maybe_evict(player, force=False):
    """Evict far areas when over the cache cap; call every pulse. [PRIMESUD]

    Fast path is one int compare (player's room unchanged).  On area
    transition, builds a keep-set -- current area, its static neighbours,
    pinned areas, and any area owning or hosting a follower or combatant --
    and evicts the rest, least-recently-visited first, until at
    AREA_CACHE_MAX loaded areas. ``force`` lets non-moving remote lookups
    enforce the cap immediately.

    Args:
        player (dict): Player state dict.
        force (bool): Check the cap even if the player's room did not change.
    """
    global _player_room, _seq_counter
    _rv = player["room"]
    if _rv == _player_room and not force:
        return
    _moved = _rv != _player_room
    _player_room = _rv
    _tag = _vnum_to_tag(_rv)
    if _tag is None:
        return
    if _moved:
        if _area_seq.get(_tag) == _seq_counter:
            return
        _seq_counter += 1
        _area_seq[_tag] = _seq_counter
    if len(_LOADED_AREAS) <= config.AREA_CACHE_MAX:
        return
    _keep = set(_PINNED)
    _keep.add(_tag)
    _keep.update(_AREA_ADJ.get(_tag, ()))
    _target = player.get("fighting")
    for _i, _inst in chars.items():
        if not _inst.get("is_npc"):
            continue
        if (_inst.get("master") is not None
                or _inst.get("fighting") == 1
                or _i == _target):
            _keep.add(_vnum_to_tag(_inst["tpl"]))
            _keep.add(_vnum_to_tag(_inst["room"]))
    _victims = [t for t in _LOADED_AREAS if t not in _keep]
    _victims.sort(key=lambda t: _area_seq.get(t, 0))
    _evicted = False
    while _victims and len(_LOADED_AREAS) > config.AREA_CACHE_MAX:
        _unload_area(_victims.pop(0))
        _evicted = True
    if _evicted:
        import gc
        gc.collect()


def is_area_loaded(tag):
    """Check whether an area has been loaded. [PRIMESUD]"""
    return tag in _LOADED_AREAS


# -- Static definitions (LazyDict for on-demand area loading) ------------------
ROOM_DEFS = LazyDict(load_all_on_iter=True)
MOB_DEFS = LazyDict(load_all_on_iter=True)
ITEM_DEFS = LazyDict(load_all_on_iter=True)
AREA_DEFS = []
DOOR_DEFS = {}
# Program code blocks by vnum, merged from each area's corresponding dict as
# it loads (like MOB_DEFS -- heap cost only for loaded areas). [PRIMESUD]
MOBPROGS = {}
OBJPROGS = {}
ROOMPROGS = {}
_WORLD_READY = False

# -- Mutable runtime state (mutated by reset_area / game functions) ------------
rooms = LazyDict(load_all_on_iter=False)
chars = {}
areas = []
save_pending = False


def reset_lazy():
    """Reset mutable state and lazy loading for new/load game. [PRIMESUD]"""
    global _player_room, _seq_counter, share_value
    _player_room = None
    _seq_counter = 0
    _area_seq.clear()
    rooms._data.clear()
    chars.clear()
    _LOADED_AREAS.clear()
    _pending_mob_saves.clear()
    _pending_room_items.clear()
    mob_stats.clear()
    area_stats.clear()
    share_value = 100
    del _reset_queue[:]
    ROOM_DEFS._data.clear()
    MOB_DEFS._data.clear()
    ITEM_DEFS._data.clear()
    DOOR_DEFS.clear()
    MOBPROGS.clear()
    OBJPROGS.clear()
    ROOMPROGS.clear()
    del AREA_DEFS[:]
    for _, _tag, _, _, _ in _AREA_FILES:
        AREA_DEFS.append({"tag": _tag, "resets": []})


def init_world():
    """Build vnum range index for lazy area loading."""
    global _WORLD_READY
    if _WORLD_READY:
        return

    _TAG_TO_FILE.clear()
    _TAG_TO_NAME.clear()
    del _VNUM_RANGES[:]
    for _fname, _tag, _name, _lo, _hi in _AREA_FILES:
        _TAG_TO_FILE[_tag] = _fname
        _TAG_TO_NAME[_tag] = _name
        _VNUM_RANGES.append((_lo, _hi, _tag))

    reset_lazy()
    _WORLD_READY = True
