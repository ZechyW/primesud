"""Build mob, object, and gear recommendation indices.

mobs.idx has one row per mob template. Metadata feeds mob counters without
loading areas; ordered spawn tags feed portal/nexus/gate/summon lookups.
Line order preserves _AREA_FILES priority, so ambiguous names still resolve
to the cheapest area load.

objs.idx (every object template) feeds `debug find` name->vnum lookups
and gives locate-object ordered reset-owning area candidates. It lists all
templates, not just reset ones, because `debug load obj` can spawn any
template and pending saves can contain resetless objects.

gear.bin records static wearable/source relationships for `recommend gear`
in a fixed-width binary layout (see pack_gear_index); the on-device scanner
rejects rows with raw byte arithmetic instead of per-row string splits.
tools/dump_gear_bin.py renders it back to readable text.

Re-run after re-converting any area:

    python tools/build_mob_index.py
"""
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPDIR = os.path.join(ROOT, "src")
OUTDIR = APPDIR
sys.path.insert(0, APPDIR)
sys.path.insert(0, os.path.join(ROOT, "pc_shim"))

import world
from inventory import _wear_flag, gear_score_components, gear_score_weapon_max
from mob import _FLAG_MERGE, _REMOVE_KEY
from races import RACE_TABLE, race_lookup


_GEAR_SLOTS = (
    "light", "finger", "neck", "body", "head", "legs", "feet", "hands",
    "arms", "about", "waist", "wrist", "wield", "shield", "hold", "float",
)
_STARTER_VNUMS = {
    world.OBJ_VNUM_SCHOOL_BANNER, world.OBJ_VNUM_SCHOOL_MACE,
    world.OBJ_VNUM_SCHOOL_DAGGER, world.OBJ_VNUM_SCHOOL_SWORD,
    world.OBJ_VNUM_SCHOOL_VEST, world.OBJ_VNUM_SCHOOL_SHIELD,
    world.OBJ_VNUM_SCHOOL_STAFF, world.OBJ_VNUM_SCHOOL_AXE,
    world.OBJ_VNUM_SCHOOL_FLAIL, world.OBJ_VNUM_SCHOOL_WHIP,
    world.OBJ_VNUM_SCHOOL_POLEARM,
}
_SOURCE_ORDER = {"shop": 0, "floor": 1, "container": 2, "loot": 3}

# gear.bin record layout, little-endian, 30 bytes (offsets for the manual
# byte reads in src/recommend.py._scan_records):
#   0 bound u16 (+32768 bias)   2 item_level u8    3 flags u8
#   4 weight u16                6 static u16 (+32768 bias)
#   8 weapon_base u16          10 wtype_id u8     11 kind u8
#  12 source_level u8          13 tag_id u8       14 item_vnum u16
#  16 source_vnum u16          18 room_vnum u16   20 price u32
#  24 name_off u16  26 name_len u8  27 sname_off u16  29 sname_len u8
_GEAR_RECORD = struct.Struct("<HBBHHHBBBBHHHIHBHB")
_GEAR_MAGIC = b"GB01"
# foes.bin layout, little-endian (manual byte reads in
# src/recommend.py._mob_candidates):
#   0 magic "FB01"   4 header_size u16   6 strings_off u32
#  10 level_count u16   12 per-level segment byte sizes u16 x level_count
#  then the tag table (u8 count; u8 len + ascii per tag); header ends at
#  header_size. Records follow, variable length, grouped by mob level
#  ascending (stable cheapest-area order within a level):
#   0 vnum u16   2 level u8   3 name_off u16   5 name_len u8
#   6 tag_count u8   7.. tag ids u8 x tag_count
#  Deduplicated ascii string table at strings_off.
_FOES_MAGIC = b"FB01"
_GEAR_BIAS = 32768
_GEAR_KIND_NAMES = ("shop", "floor", "container", "loot")
_GEAR_FLAG_BITS = {"sharp": 1, "two_hands": 2, "anti_good": 4,
                   "anti_evil": 8, "anti_neutral": 16}


def _flat(value):
    """Flatten generated display text and reject index delimiters."""
    value = " ".join(value.split())
    assert "|" not in value
    return value


def _merged_mob_flags(tpl):
    """Return race/template flags after create_mobile-style removals."""
    race = race_lookup(tpl.get("race", "Human")) or RACE_TABLE["Human"]
    merged = {}
    for char_key, race_key in _FLAG_MERGE:
        flags = {}
        flags.update(race.get(race_key, {}))
        flags.update(tpl.get(char_key, {}))
        merged[char_key] = flags
    for field, names in tpl.get("flag_removes", ()):
        flags = merged.get(_REMOVE_KEY.get(field))
        if flags:
            for name in names:
                flags.pop(name, None)
    return merged


def _fightable_site(mob, room, previous_room=None):
    """Return whether one static M-reset site is a general combat target."""
    if mob.get("shop"):
        return False
    room_flags = room.get("flags", {})
    if any(room_flags.get(flag) for flag in
           ("safe", "private", "solitary", "pet_shop")):
        return False
    # reset_room marks stock in the room after a pet shop as pets.
    if previous_room and previous_room.get("flags", {}).get("pet_shop"):
        return False
    flags = _merged_mob_flags(mob)
    act = flags["act_flags"]
    if any(act.get(flag) for flag in
           ("train", "practice", "is_healer", "healer", "changer",
            "gain", "pet")):
        return False
    if flags["affected_by"].get("charm"):
        return False
    imm = flags["imm_flags"]
    return not (imm.get("weapon") and imm.get("magic"))


def _shop_price(mob, item):
    """Return fresh-stock buy price matching shop.get_cost()."""
    price = item.get("value", 0) * mob["shop"]["profit_buy"] // 100
    if item.get("type") in ("staff", "wand"):
        max_charges = item.get("max_charges", 0)
        if max_charges == 0:
            price //= 4
        else:
            price = price * item.get("charges", max_charges) // max_charges
    return price


def _gear_metadata(vnum, item):
    """Return shared gear-index fields as a dict, or None for excluded items."""
    if vnum in _STARTER_VNUMS:
        return None
    slot = _wear_flag({}, item)
    if slot not in _GEAR_SLOTS:
        return None
    static_score, weapon_base, weapon_type, sharp = gear_score_components(item)
    flags = []
    extra = item.get("extra_flags", {})
    for name in ("anti_good", "anti_evil", "anti_neutral"):
        if extra.get(name):
            flags.append(name)
    if item.get("weapon_flags", {}).get("two_hands"):
        flags.append("two_hands")
    return {
        "vnum": vnum, "slot": slot, "level": item.get("level", 0),
        "static": static_score, "wbase": weapon_base, "wtype": weapon_type,
        "sharp": sharp, "weight": item.get("weight", 0), "flags": flags,
        "name": _flat(item.get("short_descr", "")),
    }


def _gear_bound(row):
    """Precomputed max-score bound: static + adept weapon score, with the
    two-hander 11/10 dice widening baked in for wield rows."""
    wmax = gear_score_weapon_max(row["wbase"], row["sharp"])
    if row["slot"] == "wield":
        wmax += wmax // 10
    return row["static"] + wmax


def pack_gear_index(rows, tags=None):
    """Pack gear source rows into the binary gear.bin blob.

    rows are dicts (see _gear_metadata plus kind/source_level/source_vnum/
    room/tag/price/source_name). tags is the ordered area-tag table
    (defaults to first-seen row order). Shared with tests so fixtures keep
    the shipped layout invariants: per slot, loot records first, then
    non-loot, each region sorted by bound descending -- the scanner's
    early-stop breaks depend on that order. Display strings live
    deduplicated in a trailing string table.
    """
    if tags is None:
        tags = []
        for row in rows:
            if row["tag"] not in tags:
                tags.append(row["tag"])
    tag_ids = {tag: index for index, tag in enumerate(tags)}
    wtypes = sorted({row["wtype"] for row in rows} | {""})
    wtype_ids = {name: index for index, name in enumerate(wtypes)}
    assert len(tags) < 256 and len(wtypes) < 256

    strings = {}
    string_parts = []

    def intern(text):
        data = text.encode("ascii")
        assert len(data) < 256, text
        ref = strings.get(data)
        if ref is None:
            offset = sum(len(part) for part in string_parts)
            # ponytail: u16 offsets cap the deduped table at 64KB; widen
            # name_off/sname_off to u24 if this ever fires.
            assert offset + len(data) < 65536
            ref = (offset, len(data))
            strings[data] = ref
            string_parts.append(data)
        return ref

    def sort_key(row):
        return (-_gear_bound(row), row["vnum"], _SOURCE_ORDER[row["kind"]],
                tag_ids[row["tag"]], row["source_vnum"], row["room"])

    def pack_row(row):
        mask = _GEAR_FLAG_BITS["sharp"] if row["sharp"] else 0
        for name in row["flags"]:
            mask |= _GEAR_FLAG_BITS[name]
        name_off, name_len = intern(row["name"])
        sname_off, sname_len = intern(row["source_name"])
        bound = _gear_bound(row) + _GEAR_BIAS
        static = row["static"] + _GEAR_BIAS
        assert 0 <= bound < 65536 and 0 <= static < 65536, row
        assert (0 <= row["vnum"] < 65536 and 0 <= row["level"] < 256
                and 0 <= row["wbase"] < 65536 and 0 <= row["weight"] < 65536
                and 0 <= row["source_level"] < 256
                and 0 <= row["source_vnum"] < 65536
                and 0 <= row["room"] < 65536
                and 0 <= row["price"] < 2 ** 32), row
        return _GEAR_RECORD.pack(
            bound, row["level"], mask, row["weight"], static, row["wbase"],
            wtype_ids[row["wtype"]], _GEAR_KIND_NAMES.index(row["kind"]),
            row["source_level"], tag_ids[row["tag"]], row["vnum"],
            row["source_vnum"], row["room"], row["price"],
            name_off, name_len, sname_off, sname_len)

    counts = []
    loot_counts = []
    records = []
    for slot in _GEAR_SLOTS:
        loot = sorted((row for row in rows
                       if row["slot"] == slot and row["kind"] == "loot"),
                      key=sort_key)
        other = sorted((row for row in rows
                        if row["slot"] == slot and row["kind"] != "loot"),
                       key=sort_key)
        counts.append(len(loot) + len(other))
        loot_counts.append(len(loot))
        for row in loot + other:
            records.append(pack_row(row))
    body = b"".join(records)

    tables = bytearray()
    for group in (wtypes, tags):
        tables.append(len(group))
        for name in group:
            data = name.encode("ascii")
            assert len(data) < 256
            tables.append(len(data))
            tables += data
    header_size = 76 + len(tables)
    assert header_size <= 4096  # the scanner's single header read
    strings_off = header_size + len(body)
    header = (_GEAR_MAGIC
              + struct.pack("<HHI", header_size, _GEAR_RECORD.size,
                            strings_off)
              + struct.pack("<16H", *counts)
              + struct.pack("<16H", *loot_counts)
              + bytes(tables))
    return header + body + b"".join(string_parts)


def parse_gear_index(blob):
    """Decode a gear.bin blob -> ({slot: [row dicts]}, wtypes, tags).

    PC-side reader shared by tools/dump_gear_bin.py and the tests; the
    device scanner in src/recommend.py reads the same layout with manual
    byte arithmetic. Row dicts add "bound" (debiased) and "loot" (True for
    rows in the slot's leading loot region).
    """
    assert blob[:4] == _GEAR_MAGIC
    header_size, rec_size, strings_off = struct.unpack_from("<HHI", blob, 4)
    assert rec_size == _GEAR_RECORD.size
    counts = struct.unpack_from("<16H", blob, 12)
    loot_counts = struct.unpack_from("<16H", blob, 44)
    pos = 76
    tables = []
    for _ in range(2):
        count = blob[pos]
        pos += 1
        names = []
        for _ in range(count):
            length = blob[pos]
            names.append(blob[pos + 1:pos + 1 + length].decode("ascii"))
            pos += 1 + length
        tables.append(names)
    wtypes, tags = tables
    assert pos == header_size

    def text(off, length):
        start = strings_off + off
        return blob[start:start + length].decode("ascii")

    slots = {}
    offset = header_size
    for index, slot in enumerate(_GEAR_SLOTS):
        rows = []
        for rownum in range(counts[index]):
            (bound, level, mask, weight, static, wbase, wtype_id, kind,
             source_level, tag_id, vnum, source_vnum, room, price,
             name_off, name_len, sname_off, sname_len
             ) = _GEAR_RECORD.unpack_from(blob, offset)
            offset += rec_size
            rows.append({
                "vnum": vnum, "slot": slot, "level": level,
                "bound": bound - _GEAR_BIAS, "static": static - _GEAR_BIAS,
                "wbase": wbase, "wtype": wtypes[wtype_id],
                "sharp": bool(mask & _GEAR_FLAG_BITS["sharp"]),
                "weight": weight,
                "flags": [name for name, bit in _GEAR_FLAG_BITS.items()
                          if name != "sharp" and mask & bit],
                "kind": _GEAR_KIND_NAMES[kind],
                "loot": rownum < loot_counts[index],
                "source_level": source_level, "source_vnum": source_vnum,
                "room": room, "tag": tags[tag_id], "price": price,
                "name": text(name_off, name_len),
                "source_name": text(sname_off, sname_len),
            })
        slots[slot] = rows
    assert offset == strings_off
    return slots, wtypes, tags


def pack_foes_index(rows, tags=None):
    """Pack fightable-mob rows into the binary foes.bin blob.

    rows are dicts {vnum, level, name, tags} in cheapest-area order; tags
    is the ordered area-tag table (defaults to first-seen row order).
    Shared with tests so fixtures keep the shipped layout invariant the
    scanner's band seek depends on: records grouped by mob level
    ascending, stable within a level. Names live deduplicated in a
    trailing string table.
    """
    if tags is None:
        tags = []
        for row in rows:
            for tag in row["tags"]:
                if tag not in tags:
                    tags.append(tag)
    tag_ids = {tag: index for index, tag in enumerate(tags)}
    assert len(tags) < 256

    strings = {}
    string_parts = []

    def intern(text):
        data = text.encode("ascii")
        assert len(data) < 256, text
        ref = strings.get(data)
        if ref is None:
            offset = sum(len(part) for part in string_parts)
            assert offset + len(data) < 65536
            ref = (offset, len(data))
            strings[data] = ref
            string_parts.append(data)
        return ref

    ordered = sorted(rows, key=lambda row: max(0, row["level"]))
    top_level = max((max(0, row["level"]) for row in rows), default=0)
    sizes = [0] * (top_level + 1)
    records = []
    for row in ordered:
        level = max(0, row["level"])
        name_off, name_len = intern(row["name"])
        assert 0 <= row["vnum"] < 65536 and level < 256, row
        assert 0 < len(row["tags"]) < 256, row
        record = bytes((
            row["vnum"] & 255, row["vnum"] >> 8, level,
            name_off & 255, name_off >> 8, name_len, len(row["tags"]),
        )) + bytes(tag_ids[tag] for tag in row["tags"])
        sizes[level] += len(record)
        records.append(record)
    body = b"".join(records)

    tables = bytearray()
    tables.append(len(tags))
    for name in tags:
        data = name.encode("ascii")
        assert len(data) < 256
        tables.append(len(data))
        tables += data
    header_size = 12 + 2 * len(sizes) + len(tables)
    assert header_size <= 2048  # the scanner's single header read
    strings_off = header_size + len(body)
    header = (_FOES_MAGIC
              + struct.pack("<HIH", header_size, strings_off, len(sizes))
              + struct.pack("<" + str(len(sizes)) + "H", *sizes)
              + bytes(tables))
    return header + body + b"".join(string_parts)


def parse_foes_index(blob):
    """Decode a foes.bin blob -> (rows in file order, tags, sizes).

    PC-side reader shared by tools/dump_foes_bin.py and the tests; the
    device scanner in src/recommend.py reads the same layout with manual
    byte arithmetic. Row dicts carry vnum/level/name/tags.
    """
    assert blob[:4] == _FOES_MAGIC
    header_size, strings_off, level_count = struct.unpack_from("<HIH", blob, 4)
    sizes = list(struct.unpack_from("<" + str(level_count) + "H", blob, 12))
    pos = 12 + 2 * level_count
    count = blob[pos]
    pos += 1
    tags = []
    for _ in range(count):
        length = blob[pos]
        tags.append(blob[pos + 1:pos + 1 + length].decode("ascii"))
        pos += 1 + length
    assert pos == header_size

    rows = []
    offset = header_size
    while offset < strings_off:
        vnum = blob[offset] | blob[offset + 1] << 8
        level = blob[offset + 2]
        name_off = blob[offset + 3] | blob[offset + 4] << 8
        name_len = blob[offset + 5]
        tag_count = blob[offset + 6]
        start = strings_off + name_off
        rows.append({
            "vnum": vnum, "level": level,
            "name": blob[start:start + name_len].decode("ascii"),
            "tags": [tags[blob[offset + 7 + i]] for i in range(tag_count)],
        })
        offset += 7 + tag_count
    assert offset == strings_off
    return rows, tags, sizes


def main():
    # Two passes: an M-reset may spawn a template defined in another file
    # (haon.are places arachnos-defined spiders in room 6134), so template
    # lookup must span all areas. The emitted tag stays the reset-owning
    # area -- that's the load that makes the instance exist.
    areas = []
    all_mobiles = {}
    all_objects = {}
    all_rooms = {}
    home_tags = {}
    area_order = {}
    for order, (fname, tag, _name, _lo, _hi) in enumerate(world._AREA_FILES):
        ns = {}
        with open(os.path.join(APPDIR, fname)) as f:
            exec(f.read(), ns)
        areas.append((tag, ns))
        area_order[tag] = order
        for vnum, mob in ns["MOBILES"].items():
            all_mobiles[vnum] = mob
            home_tags[vnum] = tag
        all_objects.update(ns.get("OBJECTS", {}))
        all_rooms.update(ns.get("ROOMS", {}))
    spawn_tags = {}
    fight_tags = {}
    for tag, ns in areas:
        seen = set()
        fight_seen = set()
        for reset in ns.get("RESETS", ()):
            if reset[0] != "M":
                continue
            vnum = reset[1]
            if vnum not in seen:
                seen.add(vnum)
                spawn_tags.setdefault(vnum, []).append(tag)
            room_vnum = reset[3]
            if (vnum not in fight_seen and vnum in all_mobiles
                    and room_vnum in all_rooms
                    and _fightable_site(all_mobiles[vnum], all_rooms[room_vnum],
                                        all_rooms.get(room_vnum - 1))):
                fight_seen.add(vnum)
                fight_tags.setdefault(vnum, []).append(tag)
    # Reset-backed mobs retain old cheapest-area ordering. Resetless templates
    # follow their defining area and remain visible to debug/counter listings.
    vnums = sorted(all_mobiles, key=lambda v: (
        area_order[(spawn_tags.get(v) or [home_tags[v]])[0]], v))
    lines = []
    for vnum in vnums:
        mob = all_mobiles[vnum]
        # Flatten whitespace: some source fields carry stray newlines.
        kw = " ".join(mob.get("keywords", "").split())
        short = " ".join(mob.get("short_descr", "").split())
        assert "|" not in kw, "pipe in keywords of mob %d" % vnum
        assert "|" not in short, "pipe in short_descr of mob %d" % vnum
        lines.append(str(vnum) + "|" + home_tags[vnum] + "|"
                     + str(mob.get("level", 0)) + "|" + kw + "|" + short
                     + "|" + ",".join(spawn_tags.get(vnum, ())))
    out_path = os.path.join(OUTDIR, "mobs.idx")
    header = ("# vnum|home_tag|level|keywords|short_descr|spawn_tags per mob"
               " template -- built by tools/build_mob_index.py, do not edit\n")
    with open(out_path, "w", newline="\n") as f:
        f.write(header + "\n".join(lines) + "\n")
    print("Wrote", out_path, "-", len(lines), "mobs,",
          os.path.getsize(out_path), "bytes")

    # foes.bin: fightable rows only, binary, one contiguous segment per mob
    # level, so `recommend mobs` seeks and reads just its level band and
    # rejects rows with raw byte arithmetic (per-row split allocs dominated
    # on-device: 2.4s for the text index).
    fight_rows = []
    for vnum in vnums:
        tags = fight_tags.get(vnum)
        if not tags:
            continue
        mob = all_mobiles[vnum]
        fight_rows.append({
            "vnum": vnum, "level": mob.get("level", 0),
            "name": " ".join(mob.get("short_descr", "").split()),
            "tags": tags,
        })
    blob = pack_foes_index(fight_rows, [entry[1] for entry in
                                        world._AREA_FILES])
    out_path = os.path.join(OUTDIR, "foes.bin")
    with open(out_path, "wb") as f:
        f.write(blob)
    print("Wrote", out_path, "-", len(fight_rows), "fightable mobs,",
          os.path.getsize(out_path), "bytes")

    obj_spawn_tags = {}
    for tag, ns in areas:
        seen = set()
        for reset in ns.get("RESETS", ()):
            if (reset[0] not in ("O", "E", "G", "P")
                    or reset[1] in seen):
                continue
            seen.add(reset[1])
            obj_spawn_tags.setdefault(reset[1], []).append(tag)
    obj_lines = []
    for tag, ns in areas:
        for vnum in sorted(ns.get("OBJECTS", {})):
            kw = " ".join(ns["OBJECTS"][vnum].get("keywords", "").split())
            assert "|" not in kw, "pipe in keywords of obj %d" % vnum
            if kw:
                obj_lines.append(tag + "|" + str(vnum) + "|" + kw + "|"
                                 + ",".join(obj_spawn_tags.get(vnum, ())))
    out_path = os.path.join(OUTDIR, "objs.idx")
    header = ("# home_tag|vnum|keywords|spawn_tags per object template,"
              " areas ascending by size -- built by tools/build_mob_index.py,"
              " do not edit\n")
    with open(out_path, "w", newline="\n") as f:
        f.write(header + "\n".join(obj_lines) + "\n")
    print("Wrote", out_path, "-", len(obj_lines), "objects,",
          os.path.getsize(out_path), "bytes")

    gear_rows = []
    gear_seen = set()

    def add_gear(item_vnum, kind, source_vnum, source_level, room_vnum,
                 source_name, tag, price):
        item = all_objects.get(item_vnum)
        if item is None:
            return
        metadata = _gear_metadata(item_vnum, item)
        if metadata is None:
            return
        key = (item_vnum, kind, source_vnum, room_vnum, tag)
        if key in gear_seen:
            return
        gear_seen.add(key)
        row = dict(metadata)
        row.update(kind=kind, source_level=source_level,
                   source_vnum=source_vnum, room=room_vnum, tag=tag,
                   price=price, source_name=_flat(source_name))
        gear_rows.append(row)

    # Model the device pipeline: world._load_area partitions the flat reset
    # list into per-room lists via a running room context (M/O/R update it;
    # E/G/P inherit it), and mob.reset_room then walks each room's list with
    # room-scoped last-mob/last-spawned state and a room-scoped container
    # search (floor items, then mob-carried).  Emitting from the same
    # two-stage walk keeps every row a relationship that actually
    # materializes at runtime.
    for tag, ns in areas:
        room_lists = {}
        cur_room = None
        for reset in ns.get("RESETS", ()):
            command = reset[0]
            if command == "M":
                cur_room = reset[3]
            elif command == "O":
                cur_room = reset[2]
            elif command == "R":
                cur_room = reset[1]
            if cur_room is not None:
                room_lists.setdefault(cur_room, []).append(reset)
        for room_vnum, entries in room_lists.items():
            current_mob = None
            current_mob_vnum = 0
            mob_fightable = False
            last_spawned = False
            floor_containers = set()
            # vnum -> (holder vnum, level, short_descr, lootable)
            carried_containers = {}
            for reset in entries:
                command = reset[0]
                if command == "M":
                    current_mob_vnum = reset[1]
                    current_mob = all_mobiles.get(reset[1])
                    mob_fightable = (
                        current_mob is not None and room_vnum in all_rooms
                        and _fightable_site(current_mob,
                                            all_rooms[room_vnum],
                                            all_rooms.get(room_vnum - 1)))
                    last_spawned = current_mob is not None
                elif command == "E" or command == "G":
                    if not last_spawned or reset[1] not in all_objects:
                        continue
                    if current_mob is None:
                        # Mob-less E/G (e.g. G partitioned after a foreign
                        # O) would KeyError in reset_room; surface it.
                        print("WARNING: E/G reset with no mob in room",
                              room_vnum, "(", tag, ")")
                        continue
                    # A carried item is a valid P target by vnum regardless
                    # of its declared type (reset_room matches vnum only);
                    # its contents are lootable iff the holder is a
                    # fightable non-shop mob.
                    carried_containers[reset[1]] = (
                        current_mob_vnum, current_mob.get("level", 0),
                        current_mob.get("short_descr", ""),
                        mob_fightable and not current_mob.get("shop"))
                    if current_mob.get("shop"):
                        add_gear(reset[1], "shop", current_mob_vnum,
                                 0, room_vnum,
                                 current_mob.get("short_descr", ""), tag,
                                 _shop_price(current_mob,
                                             all_objects[reset[1]]))
                    elif mob_fightable:
                        add_gear(reset[1], "loot", current_mob_vnum,
                                 current_mob.get("level", 0), room_vnum,
                                 current_mob.get("short_descr", ""), tag, 0)
                elif command == "O":
                    floor_containers.add(reset[1])
                    room = all_rooms.get(room_vnum)
                    if room is not None:
                        add_gear(reset[1], "floor", 0, 0, room_vnum,
                                 room.get("name", ""), tag, 0)
                    last_spawned = True
                elif command == "P":
                    # reset_room finds containers O-placed on this room's
                    # floor, or (gated on last_spawned, cf. db.c:1554)
                    # carried by the room's mobs; a failed search clears
                    # last_spawned so a following E/G is skipped too.
                    container_vnum = reset[3]
                    if container_vnum in floor_containers:
                        container = all_objects.get(container_vnum)
                        if container is not None:
                            add_gear(reset[1], "container", container_vnum,
                                     0, room_vnum,
                                     container.get("short_descr", ""), tag,
                                     0)
                        last_spawned = True
                    elif container_vnum in carried_containers and last_spawned:
                        holder_vnum, holder_level, holder_name, lootable = (
                            carried_containers[container_vnum])
                        if lootable:
                            # Acquiring nested contents still means defeating
                            # the holder; represent that actionable bottleneck
                            # as ordinary level-filtered loot.
                            add_gear(reset[1], "loot", holder_vnum,
                                     holder_level, room_vnum,
                                     holder_name, tag, 0)
                        # last_spawned stays True even for a shop-held or
                        # unfightable holder: the fill itself succeeds at
                        # runtime, only the recommendation is suppressed.
                    else:
                        last_spawned = False

    blob = pack_gear_index(
        gear_rows, [entry[1] for entry in world._AREA_FILES])
    out_path = os.path.join(OUTDIR, "gear.bin")
    with open(out_path, "wb") as f:
        f.write(blob)
    print("Wrote", out_path, "-", len(gear_rows), "gear sources,",
          os.path.getsize(out_path), "bytes")


if __name__ == "__main__":
    main()
