"""Zero-load mob and gear recommendations. [PRIMESUD]"""

import world
from combat import _get_size, _get_weapon_skill
from config import SIZE_RANK, STR_APP_WIELD, WEAR_BEST_SKILL_FLOOR
from handler import chprintln, get_curr_stat, is_evil, is_good, is_neutral
from inventory import (_can_wear_best, _wear_flag, _weapon_dice_part,
                       gear_score, shield_block_pct)
from item import item_weapon_flags
from pager import tpage
from picker import pick_from
from quest import QUEST_DELIVER, QUEST_FINDMOB
from skills_table import WEAPON_GSN_MAP
from util import num_str, pad_left, pad_right
from world import item_tpl


FOES_INDEX_FILE = "foes.bin"
GEAR_INDEX_FILE = "gear.bin"
# Largest single gear.bin read: the whole ~55KB record region usually fits
# one summary-mode read; each seek+read pair costs ~40ms on-device.
_CHUNK = 57344
# gear.bin fixed record size; field offsets documented in
# tools/build_mob_index.py next to _GEAR_RECORD.
_REC = 30
_KIND_NAMES = ("shop", "floor", "container", "loot")

_GEAR_SLOTS = (
    "light", "finger", "neck", "body", "head", "legs", "feet", "hands",
    "arms", "about", "waist", "wrist", "wield", "shield", "hold", "float",
)
_PAIRED_SLOTS = ("finger", "neck", "wrist")
_HAND_SLOTS = ("wield", "shield", "hold")
_SOURCE_ORDER = {"shop": 0, "floor": 1, "container": 2, "loot": 3}


def _current_tag(player):
    """Return player's resident area tag without lazy loading."""
    room = world.ROOM_DEFS._data.get(player.get("room"))
    if room is not None and room.get("area"):
        return room["area"]
    return world._vnum_to_tag(player.get("room", 0))


def _area_name(tag):
    """Return static area display name."""
    return world._TAG_TO_NAME.get(tag, tag)


def _parse_foes_header(head):
    """Decode foes.bin's header (layout in tools/build_mob_index.py).

    Returns (header_size, strings_off, sizes, tags), or None when the
    header is malformed. Raises IndexError/UnicodeError on truncated
    garbage -- the caller wraps.
    """
    if head[:4] != b"FB01":
        return None
    header_size = head[4] | head[5] << 8
    strings_off = head[6] | head[7] << 8 | head[8] << 16 | head[9] << 24
    level_count = head[10] | head[11] << 8
    sizes = []
    pos = 12
    for _ in range(level_count):
        sizes.append(head[pos] | head[pos + 1] << 8)
        pos += 2
    tags = []
    count = head[pos]
    pos += 1
    for _ in range(count):
        length = head[pos]
        tags.append(head[pos + 1:pos + 1 + length].decode())
        pos += 1 + length
    if pos != header_size:
        return None
    return header_size, strings_off, sizes, tags


def _mob_candidates(player):
    """Read and rank fightable mob rows without loading an area.

    foes.bin groups fightable records into one contiguous segment per mob
    level behind per-level byte sizes in the header, so the band
    [level-2, level+1] is one seek plus one bounded read. Records are
    variable-length (7 bytes + one byte per spawn tag; offsets in
    tools/build_mob_index.py) and walked with raw byte arithmetic -- zero
    allocations per reject, the text index spent ~13ms/row on split
    allocs. Four bounded level buckets keep the best rows, deduplicated by
    displayed name and area, then feed up to 20 winners round-robin so
    every band is represented; the winners are re-sorted level descending
    for display and their names resolve from one string-table read
    afterwards.
    """
    level = player.get("level", 1)
    lowest = max(1, level - 2)
    highest = level + 1
    try:
        f = open(FOES_INDEX_FILE, "rb")
    except OSError:
        return None
    with f:
        head = _as_bytes(f.read(2048))
        try:
            meta = _parse_foes_header(head)
        except (IndexError, ValueError, UnicodeError):
            return None
        if meta is None:
            return None
        header_size, strings_off, sizes, tags = meta
        top = len(sizes) - 1
        low_seg = lowest if lowest <= top else top + 1
        high_seg = highest if highest <= top else top
        skip = 0
        for index in range(low_seg):
            skip += sizes[index]
        length = 0
        for index in range(low_seg, high_seg + 1):
            length += sizes[index]
        data = b""
        if length:
            f.seek(header_size + skip)
            data = _as_bytes(f.read(length))
            if len(data) < length:
                return None

        current = _current_tag(player)
        cur_id = -1
        for index in range(len(tags)):
            if tags[index] == current:
                cur_id = index
                break
        protected = 0
        if player.get("quest_status") in (QUEST_DELIVER, QUEST_FINDMOB):
            protected = player.get("quest_mob", 0)

        # Keep up to 20 per output bucket: level, level-1, level+1,
        # level-2. Packed ascending key is bad record, foreign area,
        # |level diff|, level, file order (order is 15 bits; a band holds
        # a few hundred records at most).
        stats_map = world.mob_stats
        buckets = [[], [], [], []]
        order = 0
        pos = 0
        while pos < length:
            step = 7 + data[pos + 6]
            mob_level = data[pos + 2]
            vnum = data[pos] | data[pos + 1] << 8
            if vnum != protected:
                stats = stats_map.get(vnum)
                if stats:
                    kills = stats[0]
                    deaths = stats[1]
                else:
                    kills = 0
                    deaths = 0
                bad = 1 if kills > deaths else 0
                member = 0
                if cur_id >= 0:
                    for index in range(pos + 7, pos + step):
                        if data[index] == cur_id:
                            member = 1
                            break
                diff = level - mob_level
                if diff < 0:
                    diff = -diff
                key = (bad << 27 | (1 - member) << 26 | diff << 23
                       | mob_level << 15 | order)
                if mob_level == level:
                    bucket_index = 0
                elif mob_level == level - 1:
                    bucket_index = 1
                elif mob_level == level + 1:
                    bucket_index = 2
                else:
                    bucket_index = 3
                bucket = buckets[bucket_index]
                # Dedup only runs on guard-passing candidates, so a
                # guard-rejected better duplicate can leave a worse one
                # behind in another bucket; needs 21+ same-level rows plus
                # a cross-level same-name-same-area dup, so accepted as a
                # keep-rejects-allocation-free tradeoff. If the naive
                # reference test ever diverges on new data, look here.
                if len(bucket) < 20 or key < bucket[19][0]:
                    tag_id = cur_id if member else data[pos + 7]
                    name_ref = ((data[pos + 3] | data[pos + 4] << 8) << 8
                                | data[pos + 5])
                    duplicate = False
                    found = False
                    for other in buckets:
                        for other_index in range(len(other)):
                            entry = other[other_index]
                            if entry[3] == tag_id and entry[5] == name_ref:
                                found = True
                                if key < entry[0]:
                                    other.pop(other_index)
                                else:
                                    duplicate = True
                                break
                        if found:
                            break
                    if duplicate:
                        pos += step
                        order += 1
                        continue
                    row = [key, vnum, mob_level, tag_id,
                           data[pos + 6] - 1, name_ref,
                           kills, deaths, bad]
                    index = len(bucket)
                    while index and bucket[index - 1][0] > key:
                        index -= 1
                    bucket.insert(index, row)
                    if len(bucket) > 20:
                        bucket.pop()
            pos += step
            order += 1

        winners = []
        index = 0
        while len(winners) < 20:
            added = False
            for bucket in buckets:
                if index < len(bucket):
                    winners.append(bucket[index])
                    added = True
                    if len(winners) == 20:
                        break
            if not added:
                break
            index += 1

        # Selection stays round-robin so all four level bands are
        # represented; display sorts level descending, then the packed key
        # (bad record, foreign area, |level diff|, level, file order) so
        # favorable records and the current area lead each level group.
        # <=20 rows, so the sort's allocations are bounded.
        winners.sort(key=lambda entry: (-entry[2], entry[0]))

        rows = []
        if winners:
            f.seek(strings_off)
            names = _as_bytes(f.read())
            for entry in winners:
                ref = entry[5]
                rows.append({
                    "vnum": entry[1], "level": entry[2],
                    "name": names[ref >> 8:(ref >> 8)
                                  + (ref & 255)].decode(),
                    "tag": tags[entry[3]], "extra": entry[4],
                    "kills": entry[6], "deaths": entry[7],
                    "bad": bool(entry[8]),
                })
        return rows


def _show_mobs(player):
    """Render level-appropriate static mob recommendations."""
    rows = _mob_candidates(player)
    if rows is None:
        chprintln(player, "Mob recommendations are unavailable.")
        return
    if not rows:
        chprintln(player, "No suitable mob targets near your level.")
        return
    lines = ["Lv  Record  Mob                          Area"]
    for row in rows:
        if row["kills"] or row["deaths"]:
            record = (num_str(row["kills"]) + "/"
                      + num_str(row["deaths"])
                      + ("!" if row["bad"] else ""))
        else:
            record = "-"
        if len(record) > 7:
            record = record[:6] + ("!" if row["bad"] else "")
        # "+n" flags a mob that also spawns in n other areas.
        suffix = (" +" + num_str(row["extra"])) if row["extra"] else ""
        lines.append(
            pad_left(num_str(row["level"]), 2) + " "
            + pad_left(record, 7) + " "
            + pad_right(row["name"][:28], 28) + " "
            + _area_name(row["tag"])[:22 - len(suffix)] + suffix)
    tpage(lines)


def _owned_baselines(player):
    """Return best legal owned score baseline for each wear category."""
    scores = {}
    for slot in _GEAR_SLOTS:
        scores[slot] = []
    small = _get_size(player) < SIZE_RANK["large"]
    wield_2h = []
    owned = player["inv"] + [
        obj for obj in player["equip"].values() if obj is not None]
    for obj in owned:
        tpl = item_tpl(obj)
        slot = _wear_flag(obj, tpl)
        if slot in scores and _can_wear_best(player, obj, tpl):
            score = gear_score(player, obj)
            if (slot == "wield" and small
                    and item_weapon_flags(obj, tpl).get("two_hands")):
                # Scored after the shield baseline exists (loop below).
                wield_2h.append((score, _weapon_dice_part(player, obj)))
            else:
                scores[slot].append(score)
    baselines = {}
    for slot in _GEAR_SLOTS:
        values = scores[slot]
        values.sort(reverse=True)
        if slot in _PAIRED_SLOTS:
            baselines[slot] = values[1] if len(values) > 1 else (
                min(values[0], 0) if values else 0)
        else:
            baselines[slot] = values[0] if values else 0
    # Owned two-handers forfeit the shield: same economics as candidate
    # rows in _scan_records (+10% dice, minus half the shield + block).
    sb_pct = shield_block_pct(player)
    for score, dice_part in wield_2h:
        block = score * sb_pct // 100
        adjusted = (score + dice_part // 10
                    - (baselines["shield"] + block) // 2)
        if adjusted > baselines["wield"]:
            baselines["wield"] = adjusted
    return baselines


def _source_key(kind, tag, price, funds, source_level, player_level,
                source_vnum, room_vnum, current, area_order):
    """Return deterministic acquisition-suitability order."""
    if tag == current:
        bucket = 0
        detail = 0
    elif kind == "shop" and price <= funds:
        bucket = 1
        detail = 0
    elif kind == "floor" or kind == "container":
        bucket = 2
        detail = _SOURCE_ORDER[kind]
    elif kind == "loot":
        bucket = 3
        detail = abs(source_level - player_level)
    else:
        bucket = 4
        detail = 0
    return (bucket, detail, _SOURCE_ORDER.get(kind, 9),
            area_order.get(tag, len(area_order)), source_vnum, room_vnum)


def _candidate_key(row):
    """Return gear candidate ordering: gain, source, VNUM."""
    return (-row["gain"], row["source_key"], row["vnum"])


_MAX_ALT_SOURCES = 2
# Non-wield detail views keep this many nearest-below-current rows.
_DOWN_LIMIT = 5


def _alt_key(row):
    """Return rendered-source identity; detail lines omit the room.

    During the scan source_name is still a packed string-table ref, which
    works as identity because the table is deduplicated.
    """
    return (row["kind"], row["source_vnum"], row["source_name"], row["tag"])


def _keep_alt(alts, source, primary):
    """Insert a non-primary source into a bounded ranked alternate list.

    Sources indistinguishable in rendered detail (same kind, source, and
    area; rooms are not shown) collapse to their best-ranked row.
    """
    source.pop("alts", None)
    key = _alt_key(source)
    if key == _alt_key(primary):
        return
    for index, alt in enumerate(alts):
        if _alt_key(alt) == key:
            if source["source_key"] < alt["source_key"]:
                alts[index] = source
                alts.sort(key=lambda alt: alt["source_key"])
            return
    alts.append(source)
    alts.sort(key=lambda alt: alt["source_key"])
    if len(alts) > _MAX_ALT_SOURCES:
        alts.pop()


def _down_key(row):
    """Return nearest-below ordering: gain descending, source, VNUM."""
    return (-row["gain"], row["source_key"], row["vnum"])


def _keep_down(downs, row, per_type, cap):
    """Insert a downgrade row into a bounded nearest-first list. [PRIMESUD]

    Wield rows dedupe per weapon type (best row per type; the list is
    naturally bounded by the type count), other slots per item VNUM with
    the weakest popped past cap. No alt-source bookkeeping: each row
    keeps only its best-ranked source.
    """
    ident = "wtid" if per_type else "vnum"
    key = _down_key(row)
    for index, kept in enumerate(downs):
        if kept[ident] == row[ident]:
            if key < _down_key(kept):
                downs[index] = row
                downs.sort(key=_down_key)
            return
    downs.append(row)
    downs.sort(key=_down_key)
    if not per_type and len(downs) > cap:
        downs.pop()


def _keep_candidate(rows, candidate, limit):
    """Keep bounded distinct-item results; extra sources become ranked alts."""
    for index, row in enumerate(rows):
        if row["vnum"] == candidate["vnum"]:
            if candidate["source_key"] < row["source_key"]:
                candidate["alts"] = [alt for alt in row["alts"]
                                     if _alt_key(alt) != _alt_key(candidate)]
                _keep_alt(candidate["alts"], row, candidate)
                rows[index] = candidate
                rows.sort(key=_candidate_key)
            else:
                _keep_alt(row["alts"], candidate, row)
            return
    candidate["alts"] = []
    rows.append(candidate)
    rows.sort(key=_candidate_key)
    if len(rows) > limit:
        rows.pop()


def _as_bytes(data):
    """Byte-cast a gear.bin read: device open(.., "rb") can hand back str.

    [PRIMESUD] MicroPython str.encode() returns the underlying byte payload
    without re-encoding, so a byte-faithful read mistagged as str recovers
    exactly; genuinely translated data fails the header checks downstream.
    """
    return data.encode() if type(data) is str else data


def _parse_gear_header(head):
    """Decode gear.bin's header (layout in tools/build_mob_index.py).

    Returns (header_size, strings_off, counts, loot_counts, wtypes, tags),
    or None when the header is malformed. Raises IndexError/UnicodeError
    on truncated garbage -- the caller wraps.
    """
    if head[:4] != b"GB01" or (head[6] | head[7] << 8) != _REC:
        return None
    header_size = head[4] | head[5] << 8
    strings_off = (head[8] | head[9] << 8 | head[10] << 16
                   | head[11] << 24)
    counts = []
    loot_counts = []
    for index in range(16):
        counts.append(head[12 + 2 * index] | head[13 + 2 * index] << 8)
        loot_counts.append(head[44 + 2 * index] | head[45 + 2 * index] << 8)
    pos = 76
    tables = []
    for _ in range(2):
        count = head[pos]
        pos += 1
        names = []
        for _ in range(count):
            length = head[pos]
            names.append(head[pos + 1:pos + 1 + length].decode())
            pos += 1 + length
        tables.append(names)
    if pos != header_size:
        return None
    return header_size, strings_off, counts, loot_counts, tables[0], tables[1]


def _resolve_names(names, row):
    """Swap a candidate's packed (offset << 8 | length) string refs for
    real strings sliced from the string-table read."""
    ref = row["name"]
    row["name"] = names[ref >> 8:(ref >> 8) + (ref & 255)].decode()
    ref = row["source_name"]
    row["source_name"] = names[ref >> 8:(ref >> 8) + (ref & 255)].decode()


def _scan_gear(player, wanted_slot=None, downs=None):
    """Scan needed gear.bin slot segments, retaining only displayed candidates.

    gear.bin is binary: a header (magic, sizes, per-slot record and loot
    counts, weapon-type and area-tag name tables), fixed 30-byte records
    grouped by wear slot, then a deduplicated string table. Records for
    consecutive needed slots are read in bounded <=_CHUNK chunks and
    rejected with raw byte arithmetic -- ints only, no per-row allocation
    (one small heap alloc costs ~0.5ms at full game heap; the old text
    index spent ~15ms/row on split allocs). Winner display strings resolve
    afterwards from one bounded string-table read.

    Args:
        player (dict): Player instance dict.
        wanted_slot (str): Single slot for detail mode, or None for the
            per-slot summary.
        downs (list): Detail mode only: receives nearest non-upgrade rows
            (best per weapon type on wield, nearest _DOWN_LIMIT by score
            elsewhere), all with gain <= 0. None skips downgrade
            collection entirely.
    """
    try:
        f = open(GEAR_INDEX_FILE, "rb")
    except OSError:
        return None

    with f:
        head = _as_bytes(f.read(4096))
        try:
            meta = _parse_gear_header(head)
        except (IndexError, ValueError, UnicodeError):
            return None
        if meta is None:
            return None
        header_size, strings_off, counts, loot_counts, wtypes, tags = meta

        baselines = _owned_baselines(player)
        current = _current_tag(player)
        player_level = player.get("level", 1)
        loot_low = max(1, player_level - 2)
        loot_high = player_level + 1
        wield_limit = STR_APP_WIELD[get_curr_stat(player, "str")] * 10
        funds = player.get("gold", 0) * 100 + player.get("silver", 0)
        small = _get_size(player) < SIZE_RANK["large"]
        sb_pct = shield_block_pct(player)
        area_order = {}
        for index, entry in enumerate(world._AREA_FILES):
            area_order[entry[1]] = index
        # Per-type effective skill (one_hit uses 20 + proficiency): rows
        # index this by wtype_id instead of calling gear_score_weapon.
        # [PRIMESUD] Types under the WEAR_BEST_SKILL_FLOOR proficiency
        # floor 'wear best' enforces (cf. _can_wear_best) get -1 instead:
        # _scan_records rejects their rows before scoring, so the sentinel
        # never reaches the score maths and no row -- upgrade or nearest
        # non-upgrade -- names a weapon 'wear best' would refuse to equip.
        # Exotic (sn -1) is exempt from the floor here exactly as it is
        # there -- PCs get 3 * level and never practice it.
        eff = []
        for name in wtypes:
            sn = WEAPON_GSN_MAP.get(name, -1)
            skill = _get_weapon_skill(player, sn)
            eff.append(-1 if sn != -1 and skill < WEAR_BEST_SKILL_FLOOR
                       else 20 + skill)
        # Alignment legality as one bitmask test (cf. gear_flags_legal;
        # bits match _GEAR_FLAG_BITS in tools/build_mob_index.py).
        align_mask = 0
        if is_good(player):
            align_mask |= 4
        if is_evil(player):
            align_mask |= 8
        if is_neutral(player):
            align_mask |= 16

        results = {}
        if wanted_slot is None:
            for slot in _GEAR_SLOTS:
                results[slot] = []
            downs = None  # summary mode never collects downgrades
        else:
            results[wanted_slot] = []
        limit = 10 if wanted_slot is not None else 1
        owned_vnums = None
        if downs is not None:
            # Suppress "downgrade" rows for items the player already owns
            # in this slot; other equal-score sidegrades stay informative.
            owned_vnums = set()
            for obj in player["inv"] + [
                    obj for obj in player["equip"].values()
                    if obj is not None]:
                if _wear_flag(obj, item_tpl(obj)) == wanted_slot:
                    owned_vnums.add(obj.get("vnum"))

        pos = header_size
        needed = []
        for seg_index in range(len(_GEAR_SLOTS)):
            slot = _GEAR_SLOTS[seg_index]
            size = counts[seg_index] * _REC
            if size and slot in results:
                needed.append((slot, pos, size, loot_counts[seg_index] * _REC))
            pos += size
        # Segments are contiguous, so consecutive needed ones pack into
        # <=_CHUNK-byte reads.
        index = 0
        while index < len(needed):
            run_start = needed[index][1]
            stop = index + 1
            while (stop < len(needed)
                    and needed[stop][1] + needed[stop][2] - run_start
                        <= _CHUNK):
                stop += 1
            run_end = needed[stop - 1][1] + needed[stop - 1][2]
            f.seek(run_start)
            data = _as_bytes(f.read(run_end - run_start))
            if len(data) < run_end - run_start:
                return None
            while index < stop:
                slot, seg_pos, seg_size, loot_size = needed[index]
                off = seg_pos - run_start
                _scan_records(data, off, off + seg_size, off + loot_size,
                              slot, results, baselines, current,
                              player_level, loot_low, loot_high,
                              wield_limit, funds, area_order, limit, eff,
                              align_mask, small, sb_pct, tags, wtypes,
                              downs, owned_vnums)
                index += 1
            data = None

        # Resolve winner display strings: admits are rare, so one bounded
        # read of the deduplicated table covers them all.
        need_names = bool(downs)
        for got in results.values():
            if got:
                need_names = True
                break
        if need_names:
            f.seek(strings_off)
            names = _as_bytes(f.read())
            for got in results.values():
                for row in got:
                    _resolve_names(names, row)
                    for alt in row["alts"]:
                        _resolve_names(names, alt)
            for row in downs or ():
                _resolve_names(names, row)
    return results


def _scan_records(data, pos, stop, loot_end, slot, results, baselines,
                  current, player_level, loot_low, loot_high, wield_limit,
                  funds, area_order, limit, eff, align_mask, small, sb_pct,
                  tags, wtypes, downs, owned_vnums):
    """Score and rank one slot's fixed-width records into results[slot].

    data[pos:stop] holds 30-byte records (offsets documented in
    tools/build_mob_index.py): loot rows first (ending at loot_end), then
    non-loot, each region sorted by its precomputed max-score bound
    (bytes 0-1, biased +32768), descending. A bound below the skip floor
    therefore ends the whole region: the loot remainder jumps to
    loot_end, the non-loot remainder ends the segment. The floor starts
    at the owned baseline and rises to the weakest kept score once
    results[slot] is full (strict compare, so equal-bound alternate
    sources of a kept item still parse). Every reject runs on raw byte
    arithmetic -- ints only, no allocation. Admitted candidates keep
    their display strings as packed (offset << 8 | length) string-table
    refs until _scan_gear resolves the winners. Summary mode (limit 1)
    keeps a single winner per slot with empty alts and no alt
    bookkeeping.

    [PRIMESUD] With downs not None, at-or-below-baseline rows also
    collect: best per eligible weapon type on wield, nearest _DOWN_LIMIT
    below baseline on other slots. The region-exit cut then starts fully
    open and only rises -- never past the baseline, since every collected
    row scores at or below it, so upgrade admissions are untouched -- once
    the downgrade list saturates: all eligible types held on wield,
    _DOWN_LIMIT rows elsewhere (a still-missing type could beat rows below
    the kept minimum, so an early rise would be unsound).
    """
    baseline = baselines[slot]
    floor = baseline + 1
    down_open = downs is not None
    is_wield = slot == "wield"
    per_type = down_open and is_wield
    if per_type:
        down_target = 0
        for skill in eff:
            if skill >= 0:
                down_target += 1
    else:
        down_target = _DOWN_LIMIT
    cut = -32768 if down_open else floor
    fbias = cut + 32768
    rows = results[slot]
    while pos < stop:
        if (data[pos] | data[pos + 1] << 8) < fbias:
            # Bound-sorted region exhausted: no later row in it can win.
            if pos >= loot_end:
                return
            pos = loot_end
            continue
        kind = data[pos + 11]
        if kind == 3 and not (loot_low <= data[pos + 12] <= loot_high):
            pos += 30
            continue
        if data[pos + 2] > player_level:
            pos += 30
            continue
        flags = data[pos + 3]
        if flags & align_mask:
            pos += 30
            continue
        if is_wield and (data[pos + 4] | data[pos + 5] << 8) > wield_limit:
            pos += 30
            continue
        wbase = data[pos + 8] | data[pos + 9] << 8
        wtid = -1
        if wbase:
            # Inlined gear_score_weapon via the per-type eff table.
            wtid = data[pos + 10]
            skill = eff[wtid]
            if skill < 0:
                # [PRIMESUD] Sentinel from _scan_gear: the type sits below
                # the proficiency floor in _can_wear_best, so never
                # suggest a weapon 'wear best' would refuse to equip.
                pos += 30
                continue
            wscore = wbase * skill // 10
            if flags & 1:
                wscore += wscore * skill // 700
            wscore = wscore * (skill + 20) // 140
        else:
            wscore = 0
        score = (data[pos + 6] | data[pos + 7] << 8) - 32768 + wscore
        if score + wscore // 10 < cut:
            # wscore//10 is the most the two-hander branch can add back.
            pos += 30
            continue
        if flags & 2 and small:
            # Forfeits the shield (cf. _best_hand_layout economics): +10%
            # dice, minus half the owned shield's score plus its block value.
            block = score * sb_pct // 100
            score += wscore // 10 - (baselines["shield"] + block) // 2
        if score < cut:
            pos += 30
            continue
        # Survivor: decode the tail fields.
        vnum = data[pos + 14] | data[pos + 15] << 8
        source_level = data[pos + 12]
        source_vnum = data[pos + 16] | data[pos + 17] << 8
        room_vnum = data[pos + 18] | data[pos + 19] << 8
        price = (data[pos + 20] | data[pos + 21] << 8
                 | data[pos + 22] << 16 | data[pos + 23] << 24)
        kind = _KIND_NAMES[kind]
        tag = tags[data[pos + 13]]
        name_ref = ((data[pos + 24] | data[pos + 25] << 8) << 8
                    | data[pos + 26])
        sname_ref = ((data[pos + 27] | data[pos + 28] << 8) << 8
                     | data[pos + 29])
        pos += 30
        source_key = _source_key(
            kind, tag, price, funds, source_level, player_level,
            source_vnum, room_vnum, current, area_order)
        if score >= floor:
            if limit == 1:
                # Summary fast path: a single winner needs no alt
                # bookkeeping or candidate dict for losing ties -- just a
                # key compare matching _candidate_key ordering.
                if rows:
                    row = rows[0]
                    if ((-score, source_key, vnum)
                            >= (-(row["gain"] + baseline),
                                row["source_key"], row["vnum"])):
                        continue
                rows[:] = [{
                    "vnum": vnum, "slot": slot, "gain": score - baseline,
                    "name": name_ref, "kind": kind,
                    "source_vnum": source_vnum,
                    "source_level": source_level,
                    "source_name": sname_ref, "tag": tag, "price": price,
                    "source_key": source_key, "alts": [],
                }]
                floor = score
                cut = floor
                fbias = floor + 32768
                continue
            candidate = {
                "vnum": vnum, "slot": slot, "gain": score - baseline,
                "name": name_ref, "kind": kind, "source_vnum": source_vnum,
                "source_level": source_level, "source_name": sname_ref,
                "tag": tag, "price": price, "source_key": source_key,
            }
            _keep_candidate(rows, candidate, limit)
            if len(rows) == limit and not down_open:
                # Full result list: only rows beating the weakest kept
                # score matter now. Alternate sources of a kept item tie
                # its bound, so the strict compare above still lets them
                # parse into alts. (With downs open the exit floor stays
                # governed by the lower downgrade cut instead.)
                floor = rows[-1]["gain"] + baseline
                cut = floor
                fbias = cut + 32768
            elif len(rows) == limit:
                floor = rows[-1]["gain"] + baseline
        elif down_open and score <= baseline:
            # [PRIMESUD] Nearest non-upgrade collection (detail mode).
            if is_wield and not wbase:
                # Degenerate non-weapon wield row: dropping it keeps the
                # per-type saturation count sound.
                continue
            if vnum in owned_vnums:
                continue
            _keep_down(downs, {
                "vnum": vnum, "slot": slot, "gain": score - baseline,
                "name": name_ref, "kind": kind, "source_vnum": source_vnum,
                "source_level": source_level, "source_name": sname_ref,
                "tag": tag, "price": price, "source_key": source_key,
                "wtid": wtid, "wtype": wtypes[wtid] if wbase else "",
            }, per_type, down_target)
            if len(downs) >= down_target:
                cut = downs[-1]["gain"] + baseline
                fbias = cut + 32768


def _comma_num(value):
    """Render positive int with comma groups without firmware formatting."""
    digits = num_str(value)
    first = len(digits) % 3
    if not first:
        first = 3
    out = digits[:first]
    index = first
    while index < len(digits):
        out += "," + digits[index:index + 3]
        index += 3
    return out


def _source_detail(row):
    """Return detailed acquisition text."""
    if row["kind"] == "loot":
        return ("loot: " + row["source_name"] + " (L"
                + num_str(row["source_level"]) + ")")
    if row["kind"] == "shop":
        return ("shop: " + row["source_name"] + " ("
                + _comma_num(row["price"]) + " silver)")
    if row["kind"] == "container":
        return "container: " + row["source_name"]
    return "floor: " + row["source_name"]


def _show_gear(player, slot=None):
    """Render strict static gear upgrades and nearest non-upgrades.

    Summary mode opens a picker over the per-category best upgrades; choosing
    a row drills into that slot's detail. Detail mode appends a nearest-below
    section (best per weapon type on wield). Returns the resolved command
    string ("recommend gear <slot>") when the player drills in, else None.
    """
    downs = [] if slot is not None else None
    results = _scan_gear(player, slot, downs)
    if results is None:
        chprintln(player, "Gear recommendations are unavailable.")
        return None
    if slot is not None:
        rows = results[slot]
        if not rows and not downs:
            chprintln(player, "No " + slot + " upgrades for you.")
            return None
        lines = []
        if not rows:
            lines.append("No " + slot + " upgrades for you.")
        for row in rows:
            lines.append(slot + " +" + num_str(row["gain"]) + "  "
                         + row["name"][:48])
            lines.append(("  " + _source_detail(row))[:64])
            lines.append(("    area: " + _area_name(row["tag"]))[:64])
            for alt in row["alts"]:
                lines.append(("  also " + _source_detail(alt))[:64])
                lines.append(("    area: " + _area_name(alt["tag"]))[:64])
        if downs:
            # [PRIMESUD] Nearest non-upgrades: sizing context, and on
            # wield the best candidate per weapon type for type switchers.
            lines.append("{wNearest by weapon type:{x" if slot == "wield"
                         else "{wNearest below current:{x")
            for row in downs:
                # Every collected row scores at or below the baseline, so
                # num_str carries the sign (or renders a bare 0 sidegrade).
                head = slot + " " + num_str(row["gain"])
                if row["wtype"]:
                    head += " [" + row["wtype"] + "]"
                lines.append(head + "  " + row["name"][:40])
                lines.append(("  " + _source_detail(row))[:64])
                lines.append(("    area: " + _area_name(row["tag"]))[:64])
        tpage(lines)
        return None

    rows = []
    for category in _GEAR_SLOTS:
        if results[category]:
            rows.append(results[category][0])
    if not rows:
        chprintln(player, "No gear upgrades for you.")
        return None
    options = []
    for row in rows:
        options.append(
            pad_right(row["slot"], 8)
            + pad_left("+" + num_str(row["gain"]), 5) + " "
            + row["name"][:35])
    choice = pick_from(
        "Gear upgrades (select one for source and/or alternatives):", options)
    if choice < 0:
        return None
    picked = rows[choice]["slot"]
    _show_gear(player, picked)
    return "recommend gear " + picked


def do_recommend(player, args):
    """Recommend static mob targets or gear upgrades. [PRIMESUD]"""
    if not args:
        choice = pick_from("Recommend:", ("Mobs to fight", "Gear upgrades"))
        if choice < 0:
            return
        if choice == 0:
            _show_mobs(player)
            return "recommend mobs"
        resolved = _show_gear(player)
        return resolved if resolved else "recommend gear"

    mode = args[0].lower()
    if mode == "mobs" and len(args) == 1:
        _show_mobs(player)
        return
    if mode == "gear":
        if len(args) == 1:
            return _show_gear(player)
        slot = args[1].lower()
        if len(args) == 2 and slot in _GEAR_SLOTS:
            _show_gear(player, slot)
            return
    chprintln(player, "Usage: recommend [mobs|gear [slot]]")
