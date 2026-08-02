"""Build mob, object, and gear recommendation indices.

mobs.idx has one row per mob template. Metadata feeds mob counters without
loading areas; ordered spawn tags feed portal/nexus/gate/summon lookups.
Line order preserves _AREA_FILES priority, so ambiguous names still resolve
to the cheapest area load.

objs.idx (every object template) feeds `debug find` name->vnum lookups
and gives locate-object ordered reset-owning area candidates. It lists all
templates, not just reset ones, because `debug load obj` can spawn any
template and pending saves can contain resetless objects.

gear.idx records static wearable/source relationships for `recommend gear`.

Re-run after re-converting any area:

    python tools/build_mob_index.py
"""
import os
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
    """Return shared gear-index fields, or None for excluded items."""
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
    name = _flat(item.get("short_descr", ""))
    assert "|" not in weapon_type
    # Reject-relevant fields lead so the runtime can drop a row from a
    # short partial split; display strings (name, source_name) trail the
    # row and are only parsed for kept candidates.
    return (
        (str(vnum), slot, str(item.get("level", 0)), str(static_score),
         str(weapon_base), weapon_type, "1" if sharp else "0",
         str(item.get("weight", 0)), ",".join(flags)),
        name,
    )


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

    # foes.idx: fightable rows only, one contiguous segment per mob level,
    # so `recommend mobs` seeks and reads just its level band instead of
    # scanning 1,000 rows (per-row split allocs dominate on-device).
    fight_rows = []
    for vnum in vnums:
        tags = fight_tags.get(vnum)
        if not tags:
            continue
        mob = all_mobiles[vnum]
        short = " ".join(mob.get("short_descr", "").split())
        fight_rows.append((max(0, mob.get("level", 0)),
                           str(vnum) + "|" + str(mob.get("level", 0)) + "|"
                           + short + "|" + ",".join(tags) + "\n"))
    # Stable sort: within a level, mobs.idx cheapest-area order is kept.
    fight_rows.sort(key=lambda row: row[0])
    top_level = fight_rows[-1][0] if fight_rows else 0
    level_sizes = [0] * (top_level + 1)
    for level, row in fight_rows:
        level_sizes[level] += len(row)
    out_path = os.path.join(OUTDIR, "foes.idx")
    header = ("# vnum|level|short_descr|fight_tags per fightable mob, grouped"
              " by level; line 2 lists per-level segment byte lengths for"
              " levels 0..N -- built by tools/build_mob_index.py, do not"
              " edit\n")
    with open(out_path, "w", newline="\n") as f:
        f.write(header
                + ",".join(str(size) for size in level_sizes) + "\n"
                + "".join(row for _level, row in fight_rows))
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
        lead, name = metadata
        gear_rows.append(lead + (
            kind, str(source_level), str(source_vnum), str(room_vnum),
            tag, str(price), name, _flat(source_name),
        ))

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

    def _bound(row):
        return int(row[3]) + gear_score_weapon_max(int(row[4]), row[6] == "1")

    def _row_line(row):
        # The slot (index 1) is implied by the segment and not emitted.
        return "|".join(row[:1] + row[2:]) + "\n"

    def _emit_bands(rows, band_of, sigil, wield_subs, level_subs=False):
        """Emit rows as "<sigil><min_level>|<bytes>" bands; rows must be
        pre-sorted by band (ascending), then exact source level when
        level_subs / weapon type when wield_subs, then bound descending.
        Wield bands hold "@=<type>|<max_static>|<max_wmax>|<row bytes>"
        type sub-segments (max_wmax = best adept-skill weapon bound in
        the group); loot bands hold "@@=<source_level>|<row bytes>" exact
        source-level sub-segments, so the runtime parses no row whose
        carrier level misses the loot window (a 5-level band can overlap
        the 4-level window only partially)."""
        chunks = []
        index = 0
        while index < len(rows):
            band = band_of(rows[index])
            band_rows = []
            while index < len(rows) and band_of(rows[index]) == band:
                band_rows.append(rows[index])
                index += 1
            if level_subs:
                parts = []
                sub = 0
                while sub < len(band_rows):
                    level = band_rows[sub][10]
                    group = []
                    while (sub < len(band_rows)
                           and band_rows[sub][10] == level):
                        group.append(band_rows[sub])
                        sub += 1
                    blob = "".join(_row_line(row) for row in group)
                    parts.append("@@=" + level + "|" + str(len(blob))
                                 + "\n" + blob)
                blob = "".join(parts)
            elif wield_subs:
                parts = []
                sub = 0
                while sub < len(band_rows):
                    wtype = band_rows[sub][5]
                    group = []
                    while (sub < len(band_rows)
                           and band_rows[sub][5] == wtype):
                        group.append(band_rows[sub])
                        sub += 1
                    blob = "".join(_row_line(row) for row in group)
                    parts.append(
                        "@=" + wtype + "|"
                        + str(max(int(row[3]) for row in group)) + "|"
                        + str(max(gear_score_weapon_max(
                              int(row[4]), row[6] == "1") for row in group))
                        + "|" + str(len(blob)) + "\n" + blob)
                blob = "".join(parts)
            else:
                blob = "".join(_row_line(row) for row in band_rows)
            chunks.append(sigil + str(band * 5) + "|" + str(len(blob))
                          + "\n" + blob)
        return "".join(chunks)

    # One contiguous segment per wear slot so the runtime can seek and read
    # only the slots it needs instead of the whole file (help.dat pattern).
    # Each segment leads with its loot rows in "@@<min_source_level>|bytes"
    # 5-level SOURCE-level bands: the runtime skips whole bands outside its
    # loot window without parsing a row. Non-loot rows follow in
    # "@<min_item_level>|bytes" item-level bands (ascending), where the
    # walker breaks at the first band above the player's level -- safe only
    # because the loot part comes first. Rows inside a band (or wield type
    # group) sort by score upper bound, descending, so the walker jumps a
    # band's remainder once the bound cannot beat the skip floor.
    def _tiebreak(row):
        return (-_bound(row), int(row[0]), _SOURCE_ORDER[row[9]],
                area_order[row[13]], int(row[11]), int(row[12]))

    segments = []
    for slot in _GEAR_SLOTS:
        subs = slot == "wield"
        # Loot bands sub-group by exact source level, not weapon type: the
        # loot window admits at most 4 levels, so the surviving row volume
        # is too small for type skips to pay for their headers.
        loot = [row for row in gear_rows
                if row[1] == slot and row[9] == "loot"]
        loot.sort(key=lambda row: (
            int(row[10]) // 5, int(row[10])) + _tiebreak(row))
        other = [row for row in gear_rows
                 if row[1] == slot and row[9] != "loot"]
        other.sort(key=lambda row: (
            int(row[2]) // 5, row[5] if subs else "") + _tiebreak(row))
        segments.append(
            _emit_bands(loot, lambda row: int(row[10]) // 5, "@@", False,
                        level_subs=True)
            + _emit_bands(other, lambda row: int(row[2]) // 5, "@", subs))
    out_path = os.path.join(OUTDIR, "gear.idx")
    header = (
        "# item_vnum|item_level|static_score|weapon_base|weapon_type|"
        "sharp|weight|item_flags|source_kind|source_level|source_vnum|"
        "room_vnum|tag|price|item_name|source_name -- one segment per wear"
        " slot in fixed slot order (the slot is implied by the segment);"
        " line 2 lists segment byte lengths; loot rows lead in"
        " @@min_source_level|bytes bands holding @@=source_level|bytes"
        " exact-level sub-segments, then non-loot in @min_item_level|bytes"
        " bands, all sorted by max score; wield item bands hold"
        " @=type|max_static|max_wmax|bytes sub-segments"
        " -- built by tools/build_mob_index.py, do not edit\n")
    with open(out_path, "w", newline="\n") as f:
        f.write(header
                + ",".join(str(len(segment)) for segment in segments) + "\n"
                + "".join(segments))
    print("Wrote", out_path, "-", len(gear_rows), "gear sources,",
          os.path.getsize(out_path), "bytes")


if __name__ == "__main__":
    main()
