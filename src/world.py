"""Mutable world catalog and state loaded from area data files."""

import terminal
import config
from util import sstr

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
    ("area_pestates.txt", "pestates", "Player Estates", 17700, 17899),  # 4036 bytes
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
    ("area_chess2.txt", "chess2", "Chessboard of Midgaard", 4200, 4299), # 90301 bytes
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
    "pestates":   (1, 50),
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
    "pyramid":    (5, 50),
    "chess2":     (10, 35),
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
# = sum of values. CONTENT_REVISION: sha256 (12 hex chars) over every
# area's OBJECTS + OBJPROGS mapping in area_files order, via
# world._snap_encode (DESIGN.md sec. Item template snapshots); item
# snapshots compare this string to detect stale cached template data
# after a content update.
# Regenerate with: python tools/gen_area_adj.py
# [PRIMESUD]
AREA_BUILDERS = {
    "pestates":   "1stMud",
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
    "chess2":     "Exxon",
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
    "pestates": "All",
    "ofcol":    "All",
    "limbo":    "None",
    "quest":    "None",
    "midgaard": "All",
}

_AREA_ADJ = {
    "pestates":   ("midgaard",),
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
    "chess2":     ("midgaard",),
    "moria":      ("dwarven", "midennir", "midgaard", "plains", "sewer"),
    "mirror":     ("grove",),
    "astral":     ("air",),
    "ofcol2":     ("ofcol",),
    "mahntor":    ("thalos",),
    "sewer":      ("midgaard",),
    "tohell":     ("chapel",),
    "hitower":    ("chapel", "draconia", "drow", "dylan", "galaxy", "haon", "midgaard", "olympus", "sewer"),
    "midgaard":   ("air", "chess2", "dream", "eastern", "grave", "haon", "hood", "immort", "limbo", "midennir", "mobfact", "moria", "mud_school", "newthalos", "pestates", "quest", "redferne", "sewer"),
    "newthalos":  ("haon", "midennir", "midgaard"),
}

AREA_ROOM_COUNTS = {
    "pestates":   3,
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
    "chess2":     67,
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

CONTENT_REVISION = "2f4e7d7226b9"
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
_area_seq = {}             # tag -> visit/load counter (LRU eviction order)
_seq_counter = 0
_last_evict_area = None    # tag of the last area maybe_evict ran a pass for


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


# [PRIMESUD] Runtime cache: item_vnum -> (validated_revision, template_dict,
# objprog_dict). Lets a surviving item instance (player gear, foreign room,
# deferred room token) keep answering item_tpl() after its owning area is
# evicted, without a flat per-instance copy. One entry per VNUM regardless of
# instance count -- item instances carry no marker/reference of their own,
# the VNUM is the key. Populated at eviction (_materialize_item_snapshots)
# and consulted by item_tpl/item_tpl_get; a snapshot answers a lookup only
# while its stamped revision equals CONTENT_REVISION, except for the
# one-time orphan fallback documented on item_tpl. See DESIGN.md sec.
# Item template snapshots.
ITEM_SNAPSHOTS = {}

# [PRIMESUD] Save-time encoded-line cache: item_vnum -> (revision,
# "it.<vnum>=<revision>|<record>" line). Templates are immutable within a
# build (CONTENT_REVISION is constant per session) and the codec is
# deterministic, so each record encodes once: _serialize_world reuses the
# line while the revision it would stamp matches, and load_world prefills
# entries from the raw save bytes. A registry restamp changes the
# revision and misses; an eviction rebuild would re-encode to identical
# bytes, so a stale hit is byte-equal. Owned here (not game_state) so
# reset_lazy clears it with the rest of the world state.
_SNAP_ENC_CACHE = {}


# -- Typed snapshot codec [PRIMESUD] -------------------------------------------
# Encodes item templates + referenced obj-program source for the future
# "it.<vnum>=<revision>|<record>" save section (DESIGN.md sec. Item
# template snapshots). No
# eval/repr/JSON: save data must not become executable code, and HP Prime has
# no verified JSON module. Supports exactly the value types generated area
# data uses: None, bool, int, str, list, tuple, dict (str/int/bool/None keys).
# One-character type tag per value; unsafe bytes are REPLACED by two-char
# escape sequences (see _snap_escape) so encoded output physically contains
# no "~", '"', "\n", or "\r" at all: load_world splits the payload with a
# naive data.split("~"), and hvars_set embeds it in a PPL
# HVars("..."):="..." string literal that cannot hold a raw '"'. The PPL
# parser interprets backslash escapes inside that literal (device-confirmed
# 29/07/2026, debug/hvar_cap-2.log); hvars_set doubles backslashes in
# transit, so the two-char sequences below round-trip unchanged. Every
# value is self-delimiting, so sibling values need no separator and decode
# never scans ahead blindly.
#
# Grammar (tag immediately followed by its payload):
#   n            None
#   T / F        True / False
#   i<digits>    int, e.g. "i-42" / "i0" (leading "-" optional)
#   s<len>:<esc> str, <len> = byte length of the escaped payload that follows
#   l<n>:<...>   list of n encoded values, back to back
#   t<n>:<...>   tuple of n encoded values, back to back
#   d<n>:<...>   dict of n (key, value) encoded pairs, back to back -- keys
#                sorted by their own encoded form for deterministic output

# Escape map: unsafe byte -> two safe bytes. The unsafe byte itself never
# survives into encoded output (prefixing it with "\" would NOT be enough:
# load_world's data.split("~") ignores backslashes, and the PPL literal in
# hvars_set would collapse the pair -- hvars_set's backslash doubling
# protects these sequences in transit). Real area data hits all of these:
# quotes and newlines appear in template descriptions. [PRIMESUD]
_SNAP_ESC = {"\\": "\\\\", "~": "\\t", '"': "\\q", "\n": "\\n", "\r": "\\r"}
_SNAP_UNESC = {"\\": "\\", "t": "~", "q": '"', "n": "\n", "r": "\r"}


def _snap_escape(s):
    """Replace payload-unsafe bytes with backslash sequences. [PRIMESUD]

    The result contains no raw "~", '"', "\\n", or "\\r" -- safe inside
    the naive "~"-split save payload and, via hvars_set's backslash
    doubling, inside a PPL HVars string literal.
    """
    if ("\\" not in s and "~" not in s and '"' not in s
            and "\n" not in s and "\r" not in s):
        return s
    parts = []
    for ch in s:
        esc = _SNAP_ESC.get(ch)
        parts.append(esc if esc is not None else ch)
    return "".join(parts)


def _snap_unescape(s):
    """Inverse of _snap_escape. [PRIMESUD]

    Raises:
        ValueError: a trailing/dangling escape character, or an escape
            sequence outside the fixed _SNAP_UNESC map (strict: unknown
            sequences are corruption, not passthrough).
    """
    if "\\" not in s:
        return s
    parts = []
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        if ch == "\\":
            i += 1
            if i >= n:
                raise ValueError("_snap_unescape: dangling escape")
            orig = _SNAP_UNESC.get(s[i])
            if orig is None:
                raise ValueError("_snap_unescape: bad escape " + s[i])
            parts.append(orig)
        else:
            parts.append(ch)
        i += 1
    return "".join(parts)


def _snap_encode_into(value, parts):
    """Append value's encoded form onto parts (list of str chunks). [PRIMESUD]

    Raises:
        ValueError: value's type (or a nested value's type) is not one of
            the supported snapshot types.
    """
    t = type(value)
    if value is None:
        parts.append("n")
    elif t is bool:  # checked before int: Python bools are ints
        parts.append("T" if value else "F")
    elif t is int:
        parts.append("i")
        parts.append(sstr(value))
    elif t is str:
        esc = _snap_escape(value)
        parts.append("s")
        parts.append(sstr(len(esc)))
        parts.append(":")
        parts.append(esc)
    elif t is list or t is tuple:
        parts.append("l" if t is list else "t")
        parts.append(sstr(len(value)))
        parts.append(":")
        for item in value:
            _snap_encode_into(item, parts)
    elif t is dict:
        pairs = []
        for k, v in value.items():
            pairs.append((_snap_encode(k), v))
        pairs.sort(key=lambda kv: kv[0])
        parts.append("d")
        parts.append(sstr(len(pairs)))
        parts.append(":")
        for kenc, v in pairs:
            parts.append(kenc)
            _snap_encode_into(v, parts)
    else:
        raise ValueError("_snap_encode: unsupported type " + str(t))


def _snap_encode(value):
    """Encode value into a self-delimiting typed snapshot record. [PRIMESUD]

    Supports None, bool, int, str, list, tuple, and dict (of the same
    supported types, recursively). Deterministic: dict keys are sorted by
    their own encoded form, so equal values always encode identically.

    Raises:
        ValueError: value contains an unsupported type anywhere.
    """
    parts = []
    _snap_encode_into(value, parts)
    return "".join(parts)


def _snap_decode_len(s, pos):
    """Read a decimal length/count field up to its ":" terminator. [PRIMESUD]

    Returns:
        tuple: (parsed int, index just past the ":").

    Raises:
        ValueError: no digits found, or the ":" terminator is missing.
    """
    start = pos
    n = len(s)
    while pos < n and s[pos].isdigit():
        pos += 1
    if pos == start or pos >= n or s[pos] != ":":
        raise ValueError("_snap_decode: bad length field")
    return int(s[start:pos]), pos + 1


def _snap_decode_at(s, pos):
    """Decode one value starting at s[pos]. [PRIMESUD]

    Returns:
        tuple: (decoded value, index just past it).

    Raises:
        ValueError: truncated record, unknown type tag, or a malformed
            length/int field.
    """
    n = len(s)
    if pos >= n:
        raise ValueError("_snap_decode: truncated record")
    tag = s[pos]
    pos += 1
    if tag == "n":
        return None, pos
    if tag == "T":
        return True, pos
    if tag == "F":
        return False, pos
    if tag == "i":
        start = pos
        if pos < n and s[pos] == "-":
            pos += 1
        digit_start = pos
        while pos < n and s[pos].isdigit():
            pos += 1
        if pos == digit_start:
            raise ValueError("_snap_decode: bad int")
        return int(s[start:pos]), pos
    if tag == "s":
        length, pos = _snap_decode_len(s, pos)
        if pos + length > n:
            raise ValueError("_snap_decode: truncated string")
        raw = s[pos:pos + length]
        return _snap_unescape(raw), pos + length
    if tag == "l" or tag == "t":
        count, pos = _snap_decode_len(s, pos)
        items = []
        for _i in range(count):
            v, pos = _snap_decode_at(s, pos)
            items.append(v)
        return (items if tag == "l" else tuple(items)), pos
    if tag == "d":
        count, pos = _snap_decode_len(s, pos)
        result = {}
        for _i in range(count):
            k, pos = _snap_decode_at(s, pos)
            v, pos = _snap_decode_at(s, pos)
            result[k] = v
        return result, pos
    raise ValueError("_snap_decode: unknown type tag " + tag)


def _snap_decode(s):
    """Decode a full record produced by _snap_encode. [PRIMESUD]

    Raises:
        ValueError: malformed input of any kind. Never raises anything
            else and never returns a partially-decoded value -- callers
            treat a bad "it.<vnum>=..." save line as an optional cache
            miss, not a load failure.
    """
    try:
        value, pos = _snap_decode_at(s, 0)
    except ValueError:
        raise
    except (IndexError, TypeError, KeyError):
        raise ValueError("_snap_decode: malformed record")
    if pos != len(s):
        raise ValueError("_snap_decode: trailing data")
    return value


def item_tpl(obj):
    """Return obj's item template dict. [PRIMESUD]

    Replaces the bare ITEM_DEFS[obj_vnum(obj)] idiom.  That idiom defeats the
    instance-first item_* accessors: the LazyDict subscript loads (and resets)
    the whole owning area before any accessor gets to prefer the instance.

    Resolution order (DESIGN.md sec. Item template snapshots) -- no
    LazyDict membership test (``vnum in ITEM_DEFS``) anywhere in this chain,
    since that itself triggers a load:

    1. resident ``ITEM_DEFS._data`` -- a loaded area's current data always
       wins, so a pre-existing item adopts updated template stats as soon as
       its home area (re)loads;
    2. a current ``ITEM_SNAPSHOTS`` entry (stamped revision ==
       CONTENT_REVISION) -- lets carried/dropped/deferred gear answer without
       reloading its evicted owner area;
    3. the normal lazy ``ITEM_DEFS[vnum]`` load -- intentional: no snapshot
       was current, so the owning area (if any) loads once;
    4. orphan fallback -- the lazy load ran and the vnum is STILL absent (its
       owning area no longer defines it, or never did).  A stale snapshot
       entry answers anyway rather than losing a valid saved/carried item,
       and gets restamped to CONTENT_REVISION in place (one assignment, no
       retry ladder) so later lookups skip the pointless reload.

    KeyError only when none of the above can answer.

    Genuine instance overrides continue to win through the existing
    instance-first item_* accessors (item_extra_flags, item_current_charges,
    etc.) -- this seam only supplies the template those accessors fall back
    to.
    """
    vnum = obj["vnum"] if isinstance(obj, dict) else obj
    if vnum in ITEM_DEFS._data:
        return ITEM_DEFS._data[vnum]
    entry = ITEM_SNAPSHOTS.get(vnum)
    if entry is not None and entry[0] == CONTENT_REVISION:
        return entry[1]
    try:
        return ITEM_DEFS[vnum]
    except KeyError:
        if entry is not None:
            ITEM_SNAPSHOTS[vnum] = (CONTENT_REVISION, entry[1], entry[2])
            return entry[1]
        raise


def item_tpl_get(obj):
    """item_tpl, but None for an unknown vnum instead of KeyError. [PRIMESUD]

    Same resolution order as item_tpl; for the handful of callers that
    tolerate a template-less object (synthetic or legacy vnums outside every
    area's range) rather than treating the miss as a bug.
    """
    vnum = obj["vnum"] if isinstance(obj, dict) else obj
    if vnum in ITEM_DEFS._data:
        return ITEM_DEFS._data[vnum]
    entry = ITEM_SNAPSHOTS.get(vnum)
    if entry is not None and entry[0] == CONTENT_REVISION:
        return entry[1]
    tpl = ITEM_DEFS.get(vnum)
    if tpl is not None:
        return tpl
    if entry is not None:
        ITEM_SNAPSHOTS[vnum] = (CONTENT_REVISION, entry[1], entry[2])
        return entry[1]
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
    global _draining, _seq_counter
    _loading_notice(tag)
    # [PRIMESUD] Defrag before the load's big allocations: measured ~375ms
    # net wall-clock win on a 265KB area at pressured heap (collect costs
    # 73-132ms, load runs ~500ms faster); worst case ~+75ms on a tiny
    # area, imperceptible. PERFORMANCE.md sec. Area loading.
    import gc
    gc.collect()
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
    if tag == "pestates" and 1 in chars:
        from homes import apply_home  # deferred: homes imports world
        apply_home(chars[1])
    MOB_DEFS.update(_ns["MOBILES"])
    ITEM_DEFS.update(_ns["OBJECTS"])
    # Program tables are optional so synthetic/older generated area files
    # remain loadable. Real area files emit all three, empty when unused.
    # [PRIMESUD]
    MOBPROGS.update(_ns.get("MOBPROGS", {}))
    OBJPROGS.update(_ns.get("OBJPROGS", {}))
    # [PRIMESUD] Fresh resident definitions supersede cached snapshots: drop
    # registry entries this load just made resident again, freeing their
    # template copies.  Orphan entries (vnums the area no longer defines)
    # are retained; the next eviction rebuilds any still-required snapshots
    # from current data (DESIGN.md sec. Item template snapshots).
    for _v in [_k for _k in ITEM_SNAPSHOTS if _k in _ns["OBJECTS"]]:
        del ITEM_SNAPSHOTS[_v]
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
    # [PRIMESUD] Stamp as most-recently-used.  maybe_evict orders victims by
    # _area_seq (default 0), which is otherwise only set when the player
    # *enters* an area -- so an area loaded any other way (border crossing
    # mid-move, gate, quest lookup) would sort to the front of the eviction
    # queue and be dropped on the very next step, then reloaded.
    _seq_counter += 1
    _area_seq[tag] = _seq_counter

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
    from mob import reset_area, reset_room, _object_count_map, _mob_count_maps  # deferred: mob imports world
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
        _mob_counts = _mob_count_maps()
        for _rv in _preloaded:
            if _rv in rooms:
                _next_id = reset_room(_rv, _next_id, _obj_counts, _mob_counts)

    _apply_pending_deltas(tag, _room_vnums)

    if areas:
        for _s in areas:
            if _s["tag"] == tag:
                _s["room_vnums"] = _room_vnums
                _s["age"] = 0
                break


def _apply_pending_deltas(tag, room_vnums):
    """Apply buffered save deltas after area load. [PRIMESUD]

    Mob deltas: restore the exact saved population -- kill excess
    instances, move survivors onto saved rooms, and spawn fresh instances
    (template stats, like a reset) for any shortfall.  Matching is by
    room multiset, so re-application (retry after a deferral) leaves
    already-placed mobs alone.  Saved rooms in still-unloaded areas keep
    the full saved list pending; their mobs wait parked at reset rooms.
    The saved count never exceeds the template's reset global limit
    (spawns were capped by it when the save was written).

    Args:
        tag (str): Area tag just loaded.
        room_vnums (list): Room vnums belonging to this area.
    """
    from mob import create_mobile  # deferred: mob imports world
    from handler import room_is_dark, equip_char
    from item import create_object, ensure_item_extra_flags
    _rvnum_set = set(room_vnums)
    _resets = ()
    for _a in AREA_DEFS:
        if _a["tag"] == tag:
            _resets = _a.get("resets") or ()
            break

    for _tpl in list(_pending_mob_saves):
        if _vnum_to_tag(_tpl) != tag:
            continue
        if _tpl not in MOB_DEFS._data:
            # Stale save: template no longer exists in the area file.
            del _pending_mob_saves[_tpl]
            _PENDING_MOB_CACHE.pop(_tpl, None)
            continue
        # The mayor's route state is process-local. Restoring a mid-route
        # room without its matching route position makes the restarted path
        # walk out of Midgaard and lazy-load unrelated areas. Leave it at its
        # reset room instead, matching upstream's non-persistent NPCs.
        if MOB_DEFS._data.get(_tpl, {}).get("spec_fun") == "spec_mayor":
            del _pending_mob_saves[_tpl]
            _PENDING_MOB_CACHE.pop(_tpl, None)
            continue
        _saved = _pending_mob_saves[_tpl]
        # Owned pets are persisted via p.pet, not m. lines -- never count or
        # cull them against saved template positions. [PRIMESUD]
        _ids = sorted(i for i, inst in chars.items()
                      if inst.get("is_npc") and inst["tpl"] == _tpl
                      and not (inst.get("act_flags", {}).get("pet")
                               and inst.get("master") is not None))
        for _mid in _ids[len(_saved):]:
            _old = chars[_mid]["room"]
            if _old in rooms._data:
                _ml = rooms._data[_old]["mobs"]
                if _mid in _ml:
                    _ml.remove(_mid)
            del chars[_mid]
        _ids = _ids[:len(_saved)]
        # Consume saved rooms already holding an instance (multiset match);
        # what remains is unplaced mobs vs unclaimed rooms.
        _want = list(_saved)
        _unmatched = []
        for _mid in _ids:
            _r = chars[_mid]["room"]
            if _r in _want:
                _want.remove(_r)
            else:
                _unmatched.append(_mid)
        _here = [_rv for _rv in _want if _rv in rooms._data]
        _absent = len(_want) - len(_here)
        for _mid, _rv in zip(_unmatched, _here):
            _old = chars[_mid]["room"]
            if _old in rooms._data:
                _ml = rooms._data[_old]["mobs"]
                if _mid in _ml:
                    _ml.remove(_mid)
            chars[_mid]["room"] = _rv
            rooms._data[_rv]["mobs"].append(_mid)
        # Spawn the shortfall at the remaining loadable rooms (fresh
        # template state, mirroring reset_room's M branch).
        _spawn = _here[len(_unmatched):]
        if _spawn:
            # Reset-granted gear isn't saved, so re-apply the E/G lines
            # trailing the template's first M reset (a naked cityguard
            # respawn is player-visible).  Object limits skipped: this
            # restores a previously-existing instance, not new stock.
            _eq = []
            _in_block = False
            for _e in _resets:
                if _in_block:
                    if _e[0] == "E" or _e[0] == "G":
                        _eq.append(_e)
                    else:
                        break
                elif _e[0] == "M" and _e[1] == _tpl:
                    _in_block = True
            _shop = MOB_DEFS._data[_tpl].get("shop")
            _next_id = max(chars, default=1) + 1
            for _rv in _spawn:
                inst = create_mobile(_tpl)
                for _e in _eq:
                    _obj = create_object(_e[1])
                    if _shop:
                        # Copy-on-write via the helper: a bare setdefault({})
                        # would shadow the template's extra_flags.
                        ensure_item_extra_flags(
                            _obj, ITEM_DEFS._data[_e[1]])["inventory"] = True
                    inst["inv"].append(_obj)
                    if _e[0] == "E":
                        equip_char(inst, _obj, _e[2])
                inst["room"] = _rv
                # Own area, not the spawn room's: a cross-area saved
                # position must keep the wanderer despawn semantics.
                inst["home_area"] = tag
                if room_is_dark(_rv):
                    inst["affected_by"]["infrared"] = True
                _prev = ROOM_DEFS._data.get(_rv - 1)
                if _prev is not None and _prev.get("flags", {}).get("pet_shop"):
                    inst["act_flags"]["pet"] = True
                inst["id"] = _next_id
                chars[_next_id] = inst
                rooms._data[_rv]["mobs"].append(_next_id)
                _next_id += 1
        if _absent:
            # Some saved rooms live in still-unloaded areas: keep the full
            # list so a later pass re-matches idempotently.  A re-save
            # drops it in favour of live positions (serializer skips
            # pending for templates with live instances).
            _pending_mob_saves[_tpl] = _saved
        else:
            del _pending_mob_saves[_tpl]
            _PENDING_MOB_CACHE.pop(_tpl, None)

    from item import parse_item_token  # deferred: item imports world
    for _rv in list(_pending_room_items):
        if _rv not in _rvnum_set:
            continue
        _raw = _pending_room_items.pop(_rv)
        _PENDING_VNUM_CACHE.pop(_rv, None)
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


def _snap_token_fields(token, sep=";"):
    """Split a serialized item token on sep at bracket depth 0, honouring
    '\\' escapes -- structural split only, no unescaping. [PRIMESUD]

    Mirrors item._split_token_fields' delimiter rules exactly (same escape
    char, bracket depth tracking, and sep parameter) so the deferred-token
    vnum walker below finds the same boundaries a real parse_item_token
    would, without building the field-value dict parse_item_token builds.
    """
    fields = []
    depth = 0
    start = 0
    escaped = False
    n = len(token)
    i = 0
    while i < n:
        ch = token[i]
        if escaped:
            escaped = False
        elif ch == "\\":
            escaped = True
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        elif ch == sep and depth == 0:
            fields.append(token[start:i])
            start = i + 1
        i += 1
    fields.append(token[start:])
    return fields


def _snap_token_vnums(token, out):
    """Append the vnum(s) referenced by one serialized item token onto out. [PRIMESUD]

    Walks a single item token (item.serialize_item_token's
    "v:<n>;...;co:[<item>^<item>...]" shape) for its own vnum and every
    nested "co:" content vnum, without constructing item dicts (DESIGN.md
    sec. Item template snapshots).  The nested "co:" content is
    split on "^" at bracket depth 0 -- matching item.parse_item_token's own
    _split_token_fields(inner, "^"), so this walker always agrees with what
    a real parse of the same token would see.
    """
    for field in _snap_token_fields(token):
        if field[:2] == "v:":
            digits = field[2:]
            if digits:
                out.append(int(digits))
        elif field[:4] == "co:[":
            inner = field[4:-1] if field.endswith("]") else field[4:]
            for sub in _snap_token_fields(inner, "^"):
                if sub:
                    _snap_token_vnums(sub, out)


def _snap_pending_vnums(raw, out):
    """Append every vnum referenced by a raw _pending_room_items value onto out. [PRIMESUD]"""
    for tok in raw.split("|"):
        if tok:
            _snap_token_vnums(tok, out)


# [PRIMESUD] Per-room cache over _snap_pending_vnums: rvnum ->
# (raw_string, all_vnums, foreign_vnums). Pending token strings are only
# ever replaced wholesale (load_world "r." lines, eviction re-serialize),
# never mutated in place, so identity of the raw string validates an
# entry and the bracket-aware per-char token scan runs once per distinct
# string instead of on every save: rescanning every pending line each
# save cost ~9s of an 11.7s full-world save on-device
# (debug/save_smoke-1.log).
_PENDING_VNUM_CACHE = {}

# [PRIMESUD] Per-template cache over the pending mob-save serializer:
# tpl_vnum -> (rooms_list, "tpl,room|room" part string). Same identity
# rule as _PENDING_VNUM_CACHE: room lists are only ever installed
# wholesale (load_world "m" line, eviction re-serialize) or reassigned
# as the same object (_apply_pending_deltas' idempotent partial-match
# keep), never mutated in place. Prefilled at load straight from the
# raw save entry, so the steady-state serializer renders nothing:
# re-rendering every pending template cost ln.mob=750ms of a 1.6s save
# on-device (debug/save_smoke-3.log).
_PENDING_MOB_CACHE = {}


def _snap_pending_cached(rv, raw):
    """Return (all_vnums, foreign_vnums) for one pending room line. [PRIMESUD]

    foreign_vnums is the subset whose owning area differs from the
    room's own area (_snap_save_vnums's filter, hoisted here so its
    per-vnum _vnum_to_tag range scans are cached alongside the token
    scan).
    """
    _ent = _PENDING_VNUM_CACHE.get(rv)
    if _ent is not None and _ent[0] is raw:
        return _ent[1], _ent[2]
    _found = []
    _snap_pending_vnums(raw, _found)
    _own = _vnum_to_tag(rv)
    _foreign = []
    for _v in _found:
        if _vnum_to_tag(_v) != _own:
            _foreign.append(_v)
    _PENDING_VNUM_CACHE[rv] = (raw, _found, _foreign)
    return _found, _foreign


def _snap_save_vnums():
    """Compute the persisted item-template snapshot VNUM set fresh. [PRIMESUD]

    Recomputes rather than dumping the whole ITEM_SNAPSHOTS registry
    (DESIGN.md sec. Item template snapshots): the player's inventory/
    equipment
    VNUMs are always included, recursively through contents; a loaded
    room's item VNUMs are included only where the template owner differs
    from the room's own area, recursively; a deferred `_pending_room_items`
    token's VNUMs follow the same foreign-owner rule, found via the
    existing token walker (_snap_pending_vnums) rather than a second
    scanner. Own-area room/pending items are omitted -- they reload
    alongside their template when that area loads.

    Returns:
        set: distinct item template VNUMs that need an
        `it.<vnum>=<revision>|<record>` save line.
    """
    needed = set()

    def _walk_always(items):
        for _o in items:
            if not isinstance(_o, dict):
                continue
            _v = _o.get("vnum")
            if _v is not None:
                needed.add(_v)
            _walk_always(_o.get("contents", []))

    def _walk_foreign(items, own_tag):
        for _o in items:
            if not isinstance(_o, dict):
                continue
            _v = _o.get("vnum")
            if _v is not None and _vnum_to_tag(_v) != own_tag:
                needed.add(_v)
            _walk_foreign(_o.get("contents", []), own_tag)

    _player = chars.get(1)
    if _player is not None:
        _walk_always(_player.get("inv", []))
        _walk_always([_e for _e in _player.get("equip", {}).values()
                      if _e is not None])

    for _rv in rooms._data:
        _items = rooms._data[_rv].get("items")
        if _items:
            _walk_foreign(_items, _vnum_to_tag(_rv))

    for _rv in _pending_room_items:
        needed.update(_snap_pending_cached(_rv, _pending_room_items[_rv])[1])

    return needed


def _snap_live_vnums():
    """Return every item VNUM referenced by any live object or deferred
    room token, regardless of ownership. [PRIMESUD]

    Runtime marks for the save-time cold mark/sweep (DESIGN.md sec. Item
    template snapshots): player, surviving NPC/shop inventories and
    equipment, loaded-room items, and `_pending_room_items` tokens -- all
    recursively, unfiltered by owner area (unlike `_snap_save_vnums`,
    which only wants the foreign subset that needs a save line). A
    registry entry outside this set is not held live by anything and may
    be dropped once its owning area is not resident to rebuild it from.

    Returns:
        set: every VNUM currently referenced anywhere live or deferred.
    """
    found = set()

    def _walk(items):
        for _o in items:
            if not isinstance(_o, dict):
                continue
            _v = _o.get("vnum")
            if _v is not None:
                found.add(_v)
            _walk(_o.get("contents", []))

    for _cid in chars:
        _ch = chars[_cid]
        _walk(_ch.get("inv", []))
        _walk([_e for _e in _ch.get("equip", {}).values() if _e is not None])
    for _rv in rooms._data:
        _walk(rooms._data[_rv].get("items", []))
    for _rv in _pending_room_items:
        found.update(_snap_pending_cached(_rv, _pending_room_items[_rv])[0])

    return found


def _materialize_item_snapshots(lo, hi, rvnum_set):
    """Snapshot [lo, hi]-owned items that survive outside an unloading area. [PRIMESUD]

    Replaces the flat per-instance snapshot_item WIP with one shared
    ITEM_SNAPSHOTS registry entry per distinct surviving VNUM (DESIGN.md
    sec. Item template snapshots).  Call
    this from _unload_area AFTER characters dying with the area have already
    been deleted from `chars` (so the inventory/equipment walk below only
    ever sees survivors) and BEFORE this area's ITEM_DEFS/OBJPROGS entries
    are dropped (the registry copy is read from resident data, never a lazy
    load -- a miss here must not re-trigger the load eviction is undoing).

    Scans, for distinct owned-vnum membership only:

    - inventory/equipment (recursively through contents) of every surviving
      character;
    - items (recursively) in loaded rooms outside rvnum_set;
    - _pending_room_items tokens buffered for rooms outside rvnum_set.

    Objects still sitting in the area's own rooms are skipped: those rooms
    and items are serialized to _pending_room_items afterwards and reload
    alongside their template.  Pre-existing registry entries owned by this
    range that are NOT in the freshly collected set (stale from a prior
    eviction) are pruned.

    ponytail: linear scan of every live object per eviction (~787 on a full
    save, one vnum range check each).  Eviction fires on area change, not per
    pulse, so this stays off the hot path; index objects by owning area if it
    ever shows up in a profile.
    """
    _vnums = set()

    def _walk(items):
        for _o in items:
            if not isinstance(_o, dict):
                continue
            _v = _o.get("vnum")
            if _v is not None and lo <= _v <= hi:
                _vnums.add(_v)
            _walk(_o.get("contents", []))

    for _cid in chars:
        _ch = chars[_cid]
        _walk(_ch.get("inv", []))
        _walk([_e for _e in _ch.get("equip", {}).values() if _e is not None])
    for _rv in rooms._data:
        if _rv not in rvnum_set:
            _walk(rooms._data[_rv].get("items", []))
    for _rv in _pending_room_items:
        if _rv not in rvnum_set:
            for _v in _snap_pending_cached(_rv, _pending_room_items[_rv])[0]:
                if lo <= _v <= hi:
                    _vnums.add(_v)

    for _v in _vnums:
        # _data, not the LazyDict: mid-eviction, a miss must not re-trigger
        # the load we are undoing.
        _tpl = ITEM_DEFS._data.get(_v)
        if _tpl is None:
            continue
        _progs = {}
        for _trig in _tpl.get("obj_triggers", ()):
            _pv = _trig[1]
            if _pv in OBJPROGS:
                _progs[_pv] = OBJPROGS[_pv]
        ITEM_SNAPSHOTS[_v] = (CONTENT_REVISION, dict(_tpl), _progs)

    for _v in [_k for _k in ITEM_SNAPSHOTS if lo <= _k <= hi and _k not in _vnums]:
        del ITEM_SNAPSHOTS[_v]


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

    # [PRIMESUD] Decouple this area's objects that live somewhere else before
    # the templates go: carried gear (chars dying with this area were just
    # deleted above, so only survivors are walked), floor items left in
    # other areas, deferred foreign-room tokens, and anything nested in a
    # container.  Scoped by template OWNERSHIP, not by location -- an item
    # picked up here and dropped two areas away is exactly the case that
    # would otherwise reload us on the next look.
    if _lo is not None:
        _materialize_item_snapshots(_lo, _hi, _rvnum_set)

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
    AREA_CACHE_MAX loaded areas. ``force`` always reaches the cap check --
    even if the player's room did not change, or a pass already ran for
    the player's current area.

    Args:
        player (dict): Player state dict.
        force (bool): Check the cap even if the player's room did not change.
    """
    global _player_room, _seq_counter, _last_evict_area
    _rv = player["room"]
    if _rv == _player_room and not force:
        return
    _moved = _rv != _player_room
    _player_room = _rv
    _tag = _vnum_to_tag(_rv)
    if _tag is None:
        return
    if _moved:
        # Skip the keep-set rebuild while moving inside the area this pass
        # already ran for -- unless forced, which always reaches the cap
        # check below.  Tracked by tag rather than by "_area_seq[_tag] ==
        # _seq_counter": _load_area also stamps _area_seq now, so counter
        # equality no longer implies a completed pass. [PRIMESUD]
        if _tag != _last_evict_area:
            _last_evict_area = _tag
            _seq_counter += 1
            _area_seq[_tag] = _seq_counter
        elif not force:
            return
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
    global _player_room, _seq_counter, _last_evict_area, share_value
    _player_room = None
    _seq_counter = 0
    _last_evict_area = None
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
    ITEM_SNAPSHOTS.clear()
    _SNAP_ENC_CACHE.clear()
    _PENDING_VNUM_CACHE.clear()
    _PENDING_MOB_CACHE.clear()
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
