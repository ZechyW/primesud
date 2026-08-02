"""Zero-load mob and gear recommendations. [PRIMESUD]"""

import world
from combat import _get_size, _get_weapon_skill
from config import SIZE_RANK, STR_APP_WIELD
from handler import chprintln, get_curr_stat
from inventory import (_can_wear_best, _wear_flag, _weapon_dice_part,
                       gear_flags_legal, gear_score, gear_score_weapon,
                       gear_score_weapon_max, shield_block_pct)
from item import item_weapon_flags
from pager import tpage
from picker import pick_from
from quest import QUEST_DELIVER, QUEST_FINDMOB
from skills_table import WEAPON_GSN_MAP
from util import num_str, pad_left, pad_right
from world import item_tpl


FOES_INDEX_FILE = "foes.idx"
GEAR_INDEX_FILE = "gear.idx"
# Largest single gear.idx read: fits the wield segment (~56KB) whole, and
# packs the other 15 segments into ~3 more reads in summary mode.
_CHUNK = 57344

_GEAR_SLOTS = (
    "light", "finger", "neck", "body", "head", "legs", "feet", "hands",
    "arms", "about", "waist", "wrist", "wield", "shield", "hold", "float",
)
_PAIRED_SLOTS = ("finger", "neck", "wrist")
_HAND_SLOTS = ("wield", "shield", "hold")
_SOURCE_ORDER = {"shop": 0, "floor": 1, "container": 2, "loot": 3}


def _index_lines(data):
    """Yield non-comment index rows without allocating an all-lines list."""
    start = 0
    size = len(data)
    while start < size:
        end = data.find("\n", start)
        if end < 0:
            end = size
        if end > start and data[start] != "#":
            line = data[start:end]
            if line and line[-1] == "\r":
                line = line[:-1]
            yield line
        start = end + 1


def _current_tag(player):
    """Return player's resident area tag without lazy loading."""
    room = world.ROOM_DEFS._data.get(player.get("room"))
    if room is not None and room.get("area"):
        return room["area"]
    return world._vnum_to_tag(player.get("room", 0))


def _area_name(tag):
    """Return static area display name."""
    return world._TAG_TO_NAME.get(tag, tag)


def _mob_candidates(player):
    """Read and rank fightable mob rows without loading an area.

    foes.idx groups fightable rows into one contiguous segment per mob
    level behind a directory line of per-level byte lengths, so the widest
    possible band [level-5, level+1] is one seek plus one bounded read --
    never a full-file scan (per-row split allocs dominate on-device).
    """
    level = player.get("level", 1)
    lowest = max(1, level - 5)
    highest = level + 1
    try:
        with open(FOES_INDEX_FILE) as f:
            head = f.read(2048)
            cut = head.find("\n")
            end = head.find("\n", cut + 1) if cut >= 0 else -1
            if end < 0:
                return None
            try:
                sizes = [int(v) for v in head[cut + 1:end].split(",")]
            except (TypeError, ValueError):
                return None
            if not sizes or min(sizes) < 0:
                return None
            top = len(sizes) - 1
            low_seg = lowest if lowest <= top else top + 1
            high_seg = highest if highest <= top else top
            skip = 0
            for index in range(low_seg):
                skip += sizes[index]
            length = 0
            for index in range(low_seg, high_seg + 1):
                length += sizes[index]
            data = ""
            if length:
                f.seek(end + 1 + skip)
                data = f.read(length)
    except OSError:
        return None

    current = _current_tag(player)
    protected = 0
    if player.get("quest_status") in (QUEST_DELIVER, QUEST_FINDMOB):
        protected = player.get("quest_mob", 0)
    rows = []
    order = 0
    for line in _index_lines(data):
        parts = line.split("|")
        if len(parts) < 4:
            continue
        try:
            vnum = int(parts[0])
            mob_level = int(parts[1])
        except (TypeError, ValueError):
            continue
        if vnum == protected or mob_level < lowest or mob_level > highest:
            continue
        tags = [tag for tag in parts[3].split(",") if tag]
        if not tags:
            continue
        tag = current if current in tags else tags[0]
        stats = world.mob_stats.get(vnum)
        kills = stats[0] if stats else 0
        deaths = stats[1] if stats else 0
        rows.append({
            "vnum": vnum, "level": mob_level, "name": parts[2],
            "tag": tag, "extra": len(tags) - 1, "kills": kills,
            "deaths": deaths, "bad": bool(stats and kills > deaths),
            "order": order,
        })
        order += 1

    low = max(1, level - 2)
    while low > lowest:
        count = 0
        for row in rows:
            if row["level"] >= low:
                count += 1
        if count >= 5:
            break
        low -= 1
    rows = [row for row in rows if row["level"] >= low]
    rows.sort(key=lambda row: (
        row["bad"], row["tag"] != current,
        abs(row["level"] - level), row["level"], row["order"]))
    return rows[:10]


def _show_mobs(player):
    """Render level-appropriate static mob recommendations."""
    rows = _mob_candidates(player)
    if rows is None:
        chprintln(player, "Mob recommendations are unavailable.")
        return
    if not rows:
        chprintln(player, "No suitable known mob targets near your level.")
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
    lines.append("Known reset sites; availability is not live.")
    lines.append("Use path <mob> or path <area> after choosing.")
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
    # rows in _scan_segment (+10% dice, minus half the shield + block).
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


def _alt_key(row):
    """Return rendered-source identity; detail lines omit the room."""
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


def _scan_gear(player, wanted_slot=None):
    """Scan needed gear.idx slot segments, retaining only displayed candidates.

    gear.idx is segmented by wear slot (help.dat pattern): a comment header,
    then one directory line of per-slot segment byte lengths in _GEAR_SLOTS
    order, then the segments. Consecutive needed segments are read in
    bounded <=_CHUNK chunks, so peak transient heap stays around one chunk,
    never the file.
    """
    try:
        f = open(GEAR_INDEX_FILE)
    except OSError:
        return None

    with f:
        head = f.read(1024)
        cut = head.find("\n")
        end = head.find("\n", cut + 1) if cut >= 0 else -1
        if end < 0:
            return None
        try:
            sizes = [int(v) for v in head[cut + 1:end].split(",")]
        except (TypeError, ValueError):
            return None
        if len(sizes) != len(_GEAR_SLOTS) or min(sizes) < 0:
            return None

        baselines = _owned_baselines(player)
        current = _current_tag(player)
        player_level = player.get("level", 1)
        loot_low = max(1, player_level - 2)
        loot_high = player_level + 1
        wield_limit = STR_APP_WIELD[get_curr_stat(player, "str")] * 10
        funds = player.get("gold", 0) * 100 + player.get("silver", 0)
        area_order = {}
        for index, entry in enumerate(world._AREA_FILES):
            area_order[entry[1]] = index
        results = {}
        if wanted_slot is None:
            for slot in _GEAR_SLOTS:
                results[slot] = []
        else:
            results[wanted_slot] = []

        pos = end + 1
        needed = []
        for seg_index in range(len(_GEAR_SLOTS)):
            slot = _GEAR_SLOTS[seg_index]
            size = sizes[seg_index]
            if size and slot in results:
                needed.append((slot, pos, size))
            pos += size
        limit = 10 if wanted_slot is not None else 1
        # Segments are contiguous, so consecutive needed ones pack into
        # <=_CHUNK-byte reads: each seek+read pair costs ~40ms on-device,
        # and chunking drops the 16 summary-mode reads to ~4.
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
            data = f.read(run_end - run_start)
            while index < stop:
                slot, seg_pos, seg_size = needed[index]
                off = seg_pos - run_start
                _scan_segment(player, data, off, off + seg_size, slot,
                              results, baselines, current, player_level,
                              loot_low, loot_high, wield_limit, funds,
                              area_order, limit)
                index += 1
            data = None
    return results


def _scan_segment(player, data, pos, stop, slot, results, baselines,
                  current, player_level, loot_low, loot_high, wield_limit,
                  funds, area_order, limit):
    """Score and rank one slot segment's rows into results[slot].

    Scans data[pos:stop] (the segment may share a chunked read with its
    neighbours). Loot rows lead the segment in "@@min_source_level|bytes"
    5-level source-level bands, skipped whole when they cannot intersect
    the loot window; admitted bands hold "@@=source_level|bytes"
    exact-level sub-segments, so boundary-band rows whose carrier level
    misses the window are skipped unparsed too. Non-loot rows follow in
    "@min_level|bytes" item-level bands (ascending), where the walk
    breaks at the first band above the player's level -- safe only
    because loot comes first. Rows inside a band sort by max-score bound,
    descending, so the walk jumps a band's remaining rows once the bound
    cannot beat the skip floor -- the owned baseline, raised to the
    weakest kept score once results[slot] is full (strict <, so
    equal-bound alternate sources of a kept item still parse). Wield item
    bands hold "@=type|max_static|max_wmax|bytes" sub-segments whose
    adept-skill bound is rescaled to the player's proficiency, skipping a
    whole unlearnt weapon type without parsing a row. Rows reject from a
    short partial split (reject fields lead the row; the slot is implied
    by the segment; display strings trail and are only parsed for kept
    candidates). Summary mode (limit 1) keeps a single winner per slot
    with empty alts and no alt bookkeeping. Data without headers or
    ordering still scans correctly, just without the shortcuts.
    """
    baseline = baselines[slot]
    floor = baseline + 1
    rows = results[slot]
    small = _get_size(player) < SIZE_RANK["large"]
    sb_pct = shield_block_pct(player)
    jump_end = -1
    while pos < stop:
        end = data.find("\n", pos)
        if end < 0 or end > stop:
            end = stop
        line = data[pos:end]
        pos = end + 1
        if not line or line[0] == "#":
            continue
        if line[-1] == "\r":
            line = line[:-1]
        if line[0] == "@":
            jump_end = -1
            parts = line.split("|")
            if line[1:2] == "@":
                if line[2:3] == "=":
                    # "@@=source_level|bytes": exact source-level group
                    # inside an admitted loot band; skip it whole when the
                    # level misses the loot window (a 5-level band can
                    # overlap the 4-level window only partially).
                    try:
                        sub_end = pos + int(parts[1])
                        sub_level = int(parts[0][3:])
                        if sub_level < loot_low or sub_level > loot_high:
                            pos = sub_end
                        else:
                            jump_end = sub_end
                    except (TypeError, ValueError, IndexError):
                        pass
                    continue
                # "@@min_source_level|bytes": 5-level source-level band of
                # loot rows; skip it whole unless it can intersect the
                # loot window.
                try:
                    band_end = pos + int(parts[1])
                    low = int(parts[0][2:])
                    if low > loot_high or low + 4 < loot_low:
                        pos = band_end
                    else:
                        jump_end = band_end
                except (TypeError, ValueError, IndexError):
                    pass
                continue
            if line[1:2] == "=":
                # Weapon-type sub-segment header. _weapon_score at skill s
                # is at most its adept (s=120) value times s*(s+20)/16800;
                # the sharp term only shrinks that ratio. +4 absorbs the
                # few points of floor-division slack, and scaled//10
                # mirrors the two-hander bound widening below.
                try:
                    sub_end = pos + int(parts[3])
                    eff = 20 + _get_weapon_skill(
                        player, WEAPON_GSN_MAP.get(parts[0][2:], -1))
                    scaled = int(parts[2]) * eff * (eff + 20) // 16800
                    if int(parts[1]) + scaled + scaled // 10 + 4 < floor:
                        pos = sub_end
                    else:
                        jump_end = sub_end
                except (TypeError, ValueError, IndexError):
                    pass
                continue
            try:
                if int(parts[0][1:]) > player_level:
                    return
                jump_end = pos + int(parts[1])
            except (TypeError, ValueError, IndexError):
                pass
            continue
        # Partial split: fields 0-7 decide every score-based reject, so
        # most rows never allocate their source/display tail (per-row
        # allocs dominate the on-device scan). The slot is implied by the
        # segment and not stored in the row.
        parts = line.split("|", 8)
        if len(parts) != 9:
            continue
        try:
            item_level = int(parts[1])
            static_score = int(parts[2])
            weapon_base = int(parts[3])
            sharp = parts[5] == "1"
            weight = int(parts[6])
        except (TypeError, ValueError):
            continue
        bound = gear_score_weapon_max(weapon_base, sharp)
        if slot == "wield":
            # Two-hander rows may add the no-shield 11/10 dice bonus below;
            # widen the bound so the band skip stays conservative.
            bound += bound // 10
        if static_score + bound < floor:
            # Bound-sorted band/type group: no later row in it can beat
            # the floor either.
            if jump_end >= 0:
                pos = jump_end
                jump_end = -1
            continue
        if item_level > player_level:
            continue
        if slot == "wield" and weight > wield_limit:
            continue
        wscore = gear_score_weapon(player, weapon_base, parts[4], sharp)
        score = static_score + wscore
        if score + wscore // 10 < floor:
            # wscore//10 is the most the two-hander branch can add back.
            continue
        flags = {}
        for flag in parts[7].split(","):
            if flag:
                flags[flag] = True
        if not gear_flags_legal(player, flags):
            continue
        if flags.get("two_hands") and small:
            # Forfeits the shield (cf. _best_hand_layout economics): +10%
            # dice, minus half the owned shield's score plus its block value.
            block = score * sb_pct // 100
            score += wscore // 10 - (baselines["shield"] + block) // 2
        if score < floor:
            continue
        # Survivor: parse the source/display tail.
        rest = parts[8].split("|")
        if len(rest) != 8:
            continue
        kind = rest[0]
        if kind not in _SOURCE_ORDER:
            continue
        try:
            vnum = int(parts[0])
            source_level = int(rest[1])
            source_vnum = int(rest[2])
            room_vnum = int(rest[3])
            price = int(rest[5])
        except (TypeError, ValueError):
            continue
        if (kind == "loot"
                and not (loot_low <= source_level <= loot_high)):
            continue
        tag = rest[4]
        source_key = _source_key(
            kind, tag, price, funds, source_level, player_level,
            source_vnum, room_vnum, current, area_order)
        if limit == 1:
            # Summary fast path: a single winner needs no alt bookkeeping
            # or candidate dict for losing ties -- just a key compare
            # matching _candidate_key ordering.
            if rows:
                row = rows[0]
                if ((-score, source_key, vnum)
                        >= (-(row["gain"] + baseline), row["source_key"],
                            row["vnum"])):
                    continue
            rows[:] = [{
                "vnum": vnum, "slot": slot, "gain": score - baseline,
                "name": rest[6], "kind": kind, "source_vnum": source_vnum,
                "source_level": source_level, "source_name": rest[7],
                "tag": tag, "price": price, "source_key": source_key,
                "alts": [],
            }]
            floor = score
            continue
        candidate = {
            "vnum": vnum, "slot": slot, "gain": score - baseline,
            "name": rest[6], "kind": kind, "source_vnum": source_vnum,
            "source_level": source_level, "source_name": rest[7],
            "tag": tag, "price": price, "source_key": source_key,
        }
        _keep_candidate(rows, candidate, limit)
        if len(rows) == limit:
            # Full result list: only rows beating the weakest kept score
            # matter now. Alternate sources of a kept item tie its bound,
            # so the strict < above still lets them parse into alts.
            floor = rows[-1]["gain"] + baseline


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


def _source_summary(row):
    """Return compact summary source text."""
    return row["kind"] + ": " + row["source_name"]


def _source_detail(row):
    """Return detailed acquisition text."""
    area = _area_name(row["tag"])
    if row["kind"] == "loot":
        return ("  loot from " + row["source_name"] + " (L"
                + num_str(row["source_level"]) + "), " + area)
    if row["kind"] == "shop":
        return ("  buy from " + row["source_name"] + ", " + area + ": "
                + _comma_num(row["price"]) + " silver")
    if row["kind"] == "container":
        return "  inside " + row["source_name"] + ", " + area
    return "  floor in " + row["source_name"] + ", " + area


def _show_gear(player, slot=None):
    """Render strict static gear upgrades.

    Summary mode opens a picker over the per-category best upgrades; choosing
    a row drills into that slot's detail. Returns the resolved command string
    ("recommend gear <slot>") when the player drills in, else None.
    """
    results = _scan_gear(player, slot)
    if results is None:
        chprintln(player, "Gear recommendations are unavailable.")
        return None
    if slot is not None:
        rows = results[slot]
        if not rows:
            chprintln(player, "No known static " + slot + " upgrades for you.")
            return None
        lines = []
        for row in rows:
            lines.append(slot + " +" + num_str(row["gain"]) + "  "
                         + row["name"][:48])
            lines.append(_source_detail(row)[:64])
            for alt in row["alts"]:
                lines.append(("  also" + _source_detail(alt)[1:])[:64])
        lines.append("Known source, not current availability.")
        if slot in _HAND_SLOTS:
            lines.append("Hand item is a candidate; wear best decides layout.")
        tpage(lines)
        return None

    rows = []
    for category in _GEAR_SLOTS:
        if results[category]:
            rows.append(results[category][0])
    if not rows:
        chprintln(player, "No known static gear upgrades for you.")
        return None
    options = []
    for row in rows:
        options.append(
            pad_right(row["slot"], 8)
            + pad_left("+" + num_str(row["gain"]), 5) + " "
            + pad_right(row["name"][:22], 22) + " "
            + _source_summary(row)[:16])
    choice = pick_from("Gear upgrades (known sources, not live):", options)
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
