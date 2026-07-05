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
I_GATE_PORTAL              = 25   # cf. 1stMud OBJ_VNUM_PORTAL
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

# Area files: (filename, tag, display_name, vnum_lo, vnum_hi).
# Ascending size order: small areas load while heap is fresh (lower ms/KB),
# big areas load last where heap pressure is unavoidable anyway.
_AREA_FILES = [
    ("area_ofcol.dat", "ofcol", "Ofcol", 5500, 5599),                 # 7084 bytes
    ("area_limbo.dat", "limbo", "Limbo", 1, 99),                      # 9466 bytes
    ("area_quest.dat", "quest", "Quest", 200, 249),                   # 12528 bytes
    ("area_trollden.dat", "trollden", "Troll Den", 2800, 2899),       # 19073 bytes
    ("area_mobfact.dat", "mobfact", "Mob Factory", 9400, 9499),       # 24889 bytes
    ("area_immort.dat", "immort", "Valhalla", 1200, 1299),            # 26758 bytes
    ("area_grave.dat", "grave", "Graveyard", 3600, 3699),             # 32513 bytes
    ("area_marsh.dat", "marsh", "Marsh", 8300, 8399),                 # 35321 bytes
    ("area_arachnos.dat", "arachnos", "Arachnos", 6200, 6399),        # 44543 bytes
    ("area_plains.dat", "plains", "Plains", 300, 399),                # 45308 bytes
    ("area_chapel.dat", "chapel", "Chapel", 3400, 3499),              # 71267 bytes
    ("area_school.dat", "mud_school", "Mud School", 3700, 3799),      # 76023 bytes
    ("area_shire.dat", "shire", "Shire", 1100, 1199),                 # 79009 bytes
    ("area_haon.dat", "haon", "Haon Dor", 6000, 6199),                # 85969 bytes
    ("area_moria.dat", "moria", "Moria", 3900, 4199),                 # 98773 bytes
    ("area_ofcol2.dat", "ofcol2", "New Ofcol", 600, 699),             # 126239 bytes
    ("area_sewer.dat", "sewer", "Sewers", 7000, 7499),                # 158284 bytes
    ("area_tohell.dat", "tohell", "Hell", 10400, 10599),              # 195277 bytes
    ("area_midgaard.dat", "midgaard", "Midgaard", 3000, 3399),        # 259207 bytes
    ("area_newthalos.dat", "newthalos", "New Thalos", 9500, 9799),    # 265007 bytes
]

# Area level ranges, duplicated from each .dat AREA["levels"] so quest
# target selection can filter areas without triggering their load.
# Keep in sync with the .dat files. [PRIMESUD]
AREA_LEVELS = {
    "ofcol":      (1, 50),
    "limbo":      (1, 10),
    "quest":      (1, 10),
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
}

# -- Lazy loading state -------------------------------------------------------
_LOADED_AREAS = set()
_TAG_TO_FILE = {}
_TAG_TO_NAME = {}
_VNUM_RANGES = []
_pending_mob_saves = {}    # {tpl_vnum: [room_vnum, ...]} from save data
_pending_room_items = {}   # {rvnum: "raw|token|string"} from save data
_reset_queue = []          # iterative drain prevents stack overflow
_draining = False
_LOADING_ALL = False


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
        import terminal
        if terminal.tr is not None:
            terminal.tprint("{D[Loading area: " + _TAG_TO_NAME.get(tag, tag) + "]{x")
    except Exception:
        pass


def _load_area(tag):
    """Load one area on demand: exec .dat, merge defs, queue reset. [PRIMESUD]

    Args:
        tag (str): Area tag (e.g. "midgaard").
    """
    global _draining
    _loading_notice(tag)
    _ns = {}
    exec(open(_TAG_TO_FILE[tag]).read(), _ns)

    _room_vnums = []
    for _vnum, _room in _ns["ROOMS"].items():
        _room["area"] = tag
        ROOM_DEFS[_vnum] = _room
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
    for _entry in _ns.get("SPECIALS", ()):
        if _entry[0] == "M" and _entry[1] in MOB_DEFS._data:
            MOB_DEFS._data[_entry[1]]["spec_fun"] = _entry[2]
    ITEM_DEFS.update(_ns["OBJECTS"])
    for _entry in _ns.get("SHOPS", ()):
        _keeper = _entry["keeper"]
        if _keeper in MOB_DEFS._data:
            MOB_DEFS._data[_keeper]["shop"] = _entry
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
    from mob import reset_area, reset_room
    reset_area(_adef)

    if _cross_area_rooms:
        _cur_rvnum = None
        for _entry in _adef["resets"]:
            _cmd = _entry[0]
            if _cmd == "M":
                _cur_rvnum = _entry[3]
            elif _cmd == "O":
                _cur_rvnum = _entry[2]
            if _cur_rvnum is not None and _cur_rvnum in _cross_area_rooms:
                if _cur_rvnum in ROOM_DEFS:
                    _rdef = ROOM_DEFS[_cur_rvnum]
                    if "resets" not in _rdef:
                        _rdef["resets"] = []
                    _rdef["resets"].append(_entry)
        _next_id = max(chars, default=1) + 1
        for _rv in _cross_area_rooms:
            if _rv in rooms:
                reset_room(_rv, _next_id)

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

    from item import parse_item_token
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


def is_area_loaded(tag):
    """Check whether an area has been loaded. [PRIMESUD]"""
    return tag in _LOADED_AREAS


# -- Static definitions (LazyDict for on-demand area loading) ------------------
ROOM_DEFS = LazyDict(load_all_on_iter=True)
MOB_DEFS = LazyDict(load_all_on_iter=True)
ITEM_DEFS = LazyDict(load_all_on_iter=True)
AREA_DEFS = []
DOOR_DEFS = {}
_WORLD_READY = False

# -- Mutable runtime state (mutated by reset_area / game functions) ------------
rooms = LazyDict(load_all_on_iter=False)
chars = {}
areas = []
save_pending = False


def reset_lazy():
    """Reset mutable state and lazy loading for new/load game. [PRIMESUD]"""
    rooms._data.clear()
    chars.clear()
    _LOADED_AREAS.clear()
    _pending_mob_saves.clear()
    _pending_room_items.clear()
    del _reset_queue[:]
    ROOM_DEFS._data.clear()
    MOB_DEFS._data.clear()
    ITEM_DEFS._data.clear()
    DOOR_DEFS.clear()
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
