#!/usr/bin/env python3
"""Convert a 1stMud 4.5.x .are file to a PrimeSUD Python area module.

Usage:
    python are_to_primesud.py school.are area_school.py

Sections handled:   #AREADATA  #ROOMS  #MOBILES  #OBJECTS  #RESETS
Sections skipped:   #SHOPS  #SPECIALS  #MOBPROGS  #OBJPROGS  #ROOMPROGS
                    (skipped RESETS commands: E G P R D F — emitted as # TODO)

Design choices:
  - perm_stat omitted: not in .are format
  - respawn omitted: 1stMud uses area-level timed resets, not per-mob timers
  - AC: integer average of the four pierce/bash/slash/exotic values divided by
    10 (REFERENCE.md: "Values stored × 10, so 100 = AC 10").  Verify manually.
  - hitroll: taken from level line field 4; no separate damroll in .are mobs
    (the +B bonus in damage dice IS the damroll analogue in 1stMud)
  - loot: left empty; populate from RESETS E/G lines manually
  - act_flags, off_flags, imm/res/vuln_flags: decoded into name→True dicts
    using flag tables from REFERENCE.md; included even if PrimeSUD ignores them
  - Exits: plain vnum for open passages; dict {"to": vnum, "isdoor": True, ...}
    for exits with any door flags — all EXIT_FLAGS encoded as name→True keys
  - Constant names: generated from display text, deduplicated with _<vnum>
"""

import re
import sys
from pathlib import Path


# ── Flag tables from REFERENCE.md ────────────────────────────────────────────

ACT_FLAGS = {
    0: "is_npc", 1: "sentinel", 2: "scavenger", 5: "aggressive",
    6: "stay_area", 7: "wimpy", 8: "pet", 9: "train", 10: "practice",
    14: "undead", 16: "cleric", 17: "mage", 18: "thief", 19: "warrior",
    20: "noalign", 21: "nopurge", 22: "outdoors", 24: "indoors",
    26: "healer", 27: "gain", 28: "update_always", 29: "changer",
}
AFF_FLAGS = {
    0: "blind", 1: "invisible", 2: "detect_evil", 3: "detect_invis",
    4: "detect_magic", 5: "detect_hidden", 6: "detect_good", 7: "sanctuary",
    8: "faerie_fire", 9: "infrared", 10: "curse", 12: "poison",
    13: "protect_evil", 14: "protect_good", 15: "sneak", 16: "hide",
    17: "sleep", 18: "charm", 19: "flying", 20: "pass_door", 21: "haste",
    22: "calm", 23: "plague", 24: "weaken", 25: "dark_vision",
    26: "berserk", 27: "swim", 28: "regeneration", 29: "slow",
}
OFF_FLAGS = {
    0: "area_attack", 1: "backstab", 2: "bash", 3: "berserk",
    4: "disarm", 5: "dodge", 6: "fade", 7: "fast", 8: "kick",
    9: "kick_dirt", 10: "parry", 11: "rescue", 12: "tail",
    13: "trip", 14: "crush", 15: "assist_all", 16: "assist_align",
    17: "assist_race", 18: "assist_players", 19: "assist_guard",
    20: "assist_vnum",
}
RESIST_FLAGS = {
    0: "summon", 1: "charm", 2: "magic", 3: "weapon", 4: "bash",
    5: "pierce", 6: "slash", 7: "fire", 8: "cold", 9: "lightning",
    10: "acid", 11: "poison", 12: "negative", 13: "holy", 14: "energy",
    15: "mental", 16: "disease", 17: "drowning", 18: "light", 19: "sound",
    23: "wood", 24: "silver", 25: "iron",
}
ROOM_FLAGS = {
    0: "dark", 2: "no_mob", 3: "indoors", 4: "arena", 5: "bank",
    9: "private", 10: "safe", 11: "solitary", 12: "pet_shop",
    13: "no_recall", 14: "imp_only", 15: "gods_only", 16: "heroes_only",
    17: "newbies_only", 18: "law", 19: "nowhere", 20: "noexplore",
    21: "noautomap", 22: "save_objs",
}
EXIT_FLAGS = {
    0: "isdoor", 1: "closed", 2: "locked", 3: "doorbell",
    5: "pickproof", 6: "nopass", 7: "easy", 8: "hard",
    9: "infuriating", 10: "noclose", 11: "nolock",
}
WEAR_SLOT = {
    1: "finger", 2: "neck", 3: "body", 4: "head", 5: "legs",
    6: "feet", 7: "hands", 8: "arms", 9: "shield", 10: "about",
    11: "waist", 12: "wrist", 13: "wield", 14: "hold", 16: "float",
}
APPLY_LOC = {
    1: "str", 2: "dex", 3: "int", 4: "wis", 5: "con",
    12: "mana", 13: "hp", 17: "AC", 18: "hitroll", 19: "damroll",
}
DIR_NAME = {0: "n", 1: "e", 2: "s", 3: "w", 4: "u", 5: "d"}


# ── Bit-string helpers ────────────────────────────────────────────────────────

def parse_bitstring(s):
    """'+YnnYn...' → set of bit positions where Y appears."""
    bits = set()
    if not s.startswith("+"):
        return bits
    for i, ch in enumerate(s[1:]):
        if ch == "Y":
            bits.add(i)
        elif ch not in "nY":
            break
    return bits


def decode_flags(bits, table, skip=None):
    """Bit-position set + table → {name: True} dict; skip is a set of positions to omit."""
    skip = skip or set()
    result = {}
    unknown = []
    for pos in sorted(bits - skip):
        if pos in table:
            result[table[pos]] = True
        else:
            unknown.append(pos)
    if unknown:
        result["_unknown_bits"] = unknown
    return result


# ── Dice and string helpers ───────────────────────────────────────────────────

def parse_dice(s):
    """'NdM+B' or 'NdM-B' → (N, M, B)."""
    m = re.match(r"(\d+)d(\d+)([+-]\d+)?", s)
    if m:
        n, d, b = m.groups()
        return (int(n), int(d), int(b) if b else 0)
    return (1, 1, 0)


def strip_article(s):
    """Strip leading 'the ', 'a ', 'an ' (case-insensitive)."""
    return re.sub(r"^(?:the|a|an)\s+", "", s.strip(), flags=re.IGNORECASE)


def to_const(prefix, text):
    """Convert display text to PREFIX_SCREAMING_SNAKE_CASE constant name."""
    text = strip_article(text).lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return f"{prefix}_{text.upper()}"


def first_sentence(text, max_len=72):
    """Extract first sentence of a possibly multi-line description."""
    text = " ".join(text.split())
    m = re.search(r"\.", text)
    if m and m.start() < max_len:
        return text[:m.start() + 1]
    return text[:max_len] + ("..." if len(text) > max_len else "")


def make_const_map(prefix, items, name_fn):
    """Build {vnum: const_name}, deduplicating clashes with _<vnum> suffix."""
    used = {}
    result = {}
    for vnum, data in items:
        base = to_const(prefix, name_fn(data))
        name = base
        if name in used and used[name] != vnum:
            name = f"{base}_{vnum}"
        used[name] = vnum
        result[vnum] = name
    return result


# ── Low-level .are reader ─────────────────────────────────────────────────────

def read_tilde_string(lines, i):
    """Read a ~-terminated string from lines[i:]. Returns (text, next_i)."""
    parts = []
    while i < len(lines):
        line = lines[i]
        i += 1
        idx = line.find("~")
        if idx >= 0:
            parts.append(line[:idx])
            break
        parts.append(line)
    return "\n".join(parts).strip(), i


def split_sections(text):
    """Split .are text into {SECTION_NAME: [lines]} dict."""
    sections = {}
    current = None
    buf = []
    for raw in text.splitlines():
        line = raw.rstrip()
        # Section header: '#' followed by all-uppercase letters (e.g. #ROOMS)
        if line.startswith("#") and re.match(r"#[A-Z]+$", line):
            if current is not None:
                sections[current] = buf
            current = line[1:]
            buf = []
        else:
            if current is not None:
                buf.append(line)
    if current is not None:
        sections[current] = buf
    return sections


# ── Section parsers ───────────────────────────────────────────────────────────

def parse_areadata(lines):
    area = {}
    for line in lines:
        parts = line.split(None, 1)
        if not parts:
            continue
        key = parts[0]
        val = parts[1].rstrip("~").strip() if len(parts) > 1 else ""
        if key == "Name":
            area["name"] = val
        elif key == "VNUMs":
            ns = val.split()
            area["vnums"] = (int(ns[0]), int(ns[1]))
        elif key == "MinLevel":
            area["min_level"] = int(val)
        elif key == "MaxLevel":
            area["max_level"] = int(val)
        elif key == "Version":
            area["version"] = int(val) if val.isdigit() else val
        elif key == "Builders":
            area["builders"] = val
        elif key == "Credits":
            area["credits"] = val
    return area


def parse_mobiles(lines):
    mobs = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not (line.startswith("#") and line[1:].isdigit()):
            i += 1
            continue
        vnum = int(line[1:])
        if vnum == 0:
            break
        i += 1

        keywords,    i = read_tilde_string(lines, i)
        short_descr, i = read_tilde_string(lines, i)
        long_descr,  i = read_tilde_string(lines, i)
        description, i = read_tilde_string(lines, i)
        race,        i = read_tilde_string(lines, i)

        # act_flags  aff_flags  alignment  group
        parts = lines[i].split(); i += 1
        act_bits = parse_bitstring(parts[0]) if parts else set()
        aff_bits = parse_bitstring(parts[1]) if len(parts) > 1 else set()
        alignment = int(parts[2]) if len(parts) > 2 else 0

        # level  random  autoset  hitroll
        parts = lines[i].split(); i += 1
        level   = int(parts[0]) if parts else 0
        hitroll = int(parts[3]) if len(parts) > 3 else 0

        # hp_dice  mana_dice  dam_dice  'dam_type'
        parts = lines[i].split(); i += 1
        hp_dice   = parse_dice(parts[0]) if parts else (1, 1, 0)
        mana_dice = parse_dice(parts[1]) if len(parts) > 1 else (1, 1, 0)
        dam_dice  = parse_dice(parts[2]) if len(parts) > 2 else (1, 1, 0)
        dam_type  = parts[3].strip("'") if len(parts) > 3 else "hit"

        # ac_pierce  ac_bash  ac_slash  ac_exotic  (stored × 10 per REFERENCE.md)
        parts = lines[i].split(); i += 1
        try:
            ac_vals = [int(x) for x in parts[:4]]
            ac = sum(ac_vals) // len(ac_vals) // 10
        except (ValueError, ZeroDivisionError):
            ac = 10

        # off_flags  imm_flags  res_flags  vuln_flags
        parts = lines[i].split(); i += 1
        off_bits  = parse_bitstring(parts[0]) if parts else set()
        imm_bits  = parse_bitstring(parts[1]) if len(parts) > 1 else set()
        res_bits  = parse_bitstring(parts[2]) if len(parts) > 2 else set()
        vuln_bits = parse_bitstring(parts[3]) if len(parts) > 3 else set()

        # start_pos  default_pos  sex  wealth
        parts = lines[i].split(); i += 1
        sex  = parts[2] if len(parts) > 2 else "neutral"
        gold = int(parts[3]) if len(parts) > 3 else 0

        # form_flags  part_flags  size  material
        parts = lines[i].split(); i += 1
        size = parts[2] if len(parts) > 2 else "medium"

        # optional trailer lines: S / M / F
        while i < len(lines):
            tline = lines[i].strip()
            if tline.startswith("#") or tline == "":
                break
            if tline and tline[0] in "SMF":
                i += 1
            else:
                break

        mobs.append((vnum, {
            "keywords":    keywords,
            "short_descr": short_descr,
            "long_descr":  long_descr,
            "description": description,
            "race":        race,
            "act_flags":   decode_flags(act_bits, ACT_FLAGS, skip={0}),  # omit IS_NPC
            "aff_flags":   decode_flags(aff_bits, AFF_FLAGS),
            "alignment":   alignment,
            "level":       level,
            "hitroll":     hitroll,
            "hp_dice":     hp_dice,
            "mana_dice":   mana_dice,
            "damage":      dam_dice,
            "dam_type":    dam_type,
            "AC":          ac,
            "off_flags":   decode_flags(off_bits, OFF_FLAGS),
            "imm_flags":   decode_flags(imm_bits, RESIST_FLAGS),
            "res_flags":   decode_flags(res_bits, RESIST_FLAGS),
            "vuln_flags":  decode_flags(vuln_bits, RESIST_FLAGS),
            "sex":         sex,
            "gold":        gold,
            "size":        size,
        }))
    return mobs


def parse_objects(lines):
    objs = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not (line.startswith("#") and line[1:].isdigit()):
            i += 1
            continue
        vnum = int(line[1:])
        if vnum == 0:
            break
        i += 1

        keywords,    i = read_tilde_string(lines, i)
        short_descr, i = read_tilde_string(lines, i)
        description, i = read_tilde_string(lines, i)
        material,    i = read_tilde_string(lines, i)

        # item_type  extra_flags  wear_flags
        parts = lines[i].split(); i += 1
        item_type  = parts[0] if parts else "unknown"
        extra_bits = parse_bitstring(parts[1]) if len(parts) > 1 else set()
        wear_bits  = parse_bitstring(parts[2]) if len(parts) > 2 else set()

        # item-type-specific value line
        val_line = lines[i].split(); i += 1

        # level  weight  cost  condition
        lw_line = lines[i].split(); i += 1
        level  = int(lw_line[0]) if lw_line else 0
        weight = int(lw_line[1]) if len(lw_line) > 1 else 0
        cost   = int(lw_line[2]) if len(lw_line) > 2 else 0

        # optional A / E / F / O trailer lines
        applies     = {}
        extra_descs = []
        while i < len(lines):
            tline = lines[i].strip()
            if tline.startswith("#"):
                break
            if tline == "A":
                i += 1
                ap = lines[i].split(); i += 1
                try:
                    loc, mod = int(ap[0]), int(ap[1])
                    if loc in APPLY_LOC:
                        applies[APPLY_LOC[loc]] = mod
                except (ValueError, IndexError):
                    pass
            elif tline == "E":
                i += 1
                ekw,  i = read_tilde_string(lines, i)
                edesc, i = read_tilde_string(lines, i)
                extra_descs.append((ekw, edesc))
            elif tline in ("F", "O") or tline == "":
                i += 1
            else:
                break

        # Build wear_flags dict (bit 0 = ITEM_TAKE; WEAR_SLOT covers equip slots)
        wear_flags = {}
        if 0 in wear_bits:
            wear_flags["take"] = True
        for pos in sorted(wear_bits):
            if pos in WEAR_SLOT:
                wear_flags[WEAR_SLOT[pos]] = True
                break

        obj = {
            "keywords":    keywords,
            "short_descr": short_descr,
            "description": description,
            "extra_descs": extra_descs,
            "material":    material,
            "type":        item_type,
            "wear_flags":  wear_flags,
            "level":       level,
            "weight":      weight,
            "value":       cost,
            "extra_flags": extra_bits,
        }

        if item_type == "weapon" and val_line:
            obj["weapon_type"] = val_line[0]
            obj["dam_type"]    = val_line[3] if len(val_line) > 3 else "hit"
            obj["dice"] = (
                int(val_line[1]) if len(val_line) > 1 else 1,
                int(val_line[2]) if len(val_line) > 2 else 1,
                0,
            )
            wf_bits = parse_bitstring(val_line[4]) if len(val_line) > 4 else set()
            obj["weapon_flags"] = decode_flags(wf_bits, {
                0: "flaming", 1: "frost", 2: "vampiric", 3: "sharp",
                4: "vorpal", 5: "two_hands", 6: "shocking", 7: "poison",
            })
        elif item_type == "armor" and val_line:
            try:
                obj["AC"] = int(val_line[0])
            except ValueError:
                obj["AC"] = 0
        elif item_type == "potion" and val_line:
            obj["spell_level"] = int(val_line[0]) if val_line else 0
            obj["spells"] = [s for s in val_line[1:] if not s.startswith("+")]

        if applies:
            obj["stat_bonuses"] = applies

        objs.append((vnum, obj))
    return objs


def parse_rooms(lines):
    rooms = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not (line.startswith("#") and line[1:].isdigit()):
            i += 1
            continue
        vnum = int(line[1:])
        if vnum == 0:
            break
        i += 1

        name,        i = read_tilde_string(lines, i)
        description, i = read_tilde_string(lines, i)

        # 0  room_flags  sector_type
        flag_parts = lines[i].split(); i += 1
        room_bits = parse_bitstring(flag_parts[1]) if len(flag_parts) > 1 else set()
        sector    = int(flag_parts[2]) if len(flag_parts) > 2 else 0

        exits      = {}
        exit_notes = {}
        room_flags = decode_flags(room_bits, ROOM_FLAGS)

        while i < len(lines):
            tline = lines[i].strip()
            if tline == "S":
                i += 1
                break
            if tline.startswith("#"):
                break
            if re.match(r"^D\d+$", tline):
                direction = int(tline[1:])
                i += 1
                _ex_desc, i = read_tilde_string(lines, i)
                _keyword,  i = read_tilde_string(lines, i)
                ex_parts = lines[i].split(); i += 1
                ex_bits  = parse_bitstring(ex_parts[0]) if ex_parts else set()
                to_room  = int(ex_parts[2]) if len(ex_parts) > 2 else -1
                if to_room > 0 and direction in DIR_NAME:
                    d = DIR_NAME[direction]
                    exits[d] = to_room
                    ex_flags = decode_flags(ex_bits, EXIT_FLAGS)
                    if ex_flags:
                        exit_notes[d] = ex_flags
            elif tline == "E":
                i += 1
                _, i = read_tilde_string(lines, i)
                _, i = read_tilde_string(lines, i)
            elif tline == "" or tline[0] in "HMG":
                i += 1
            else:
                i += 1

        rooms.append((vnum, {
            "name":       name,
            "desc":       description,
            "exits":      exits,
            "exit_notes": exit_notes,
            "flags":      room_flags,
            "sector":     sector,
        }))
    return rooms


def parse_resets(lines):
    resets = []
    for line in lines:
        parts = line.split()
        if not parts or parts[0] == "*":
            continue
        cmd = parts[0]
        if cmd == "S":
            break
        if cmd == "M" and len(parts) >= 6:
            # M  0  mob_vnum  global_limit  room_vnum  room_limit
            resets.append(("M", int(parts[2]), int(parts[3]), int(parts[4]), int(parts[5])))
        elif cmd == "O" and len(parts) >= 5:
            # O  0  obj_vnum  0  room_vnum
            resets.append(("O", int(parts[2]), int(parts[4])))
        elif cmd in "EGPRDF":
            resets.append(("TODO", line.rstrip()))
    return resets


# ── Python emitter ────────────────────────────────────────────────────────────

def _repr_flags(d):
    """Compact repr for flag dicts: {name: True, ...}."""
    if not d:
        return "{}"
    parts = [f'"{k}": True' for k in d if k != "_unknown_bits"]
    if "_unknown_bits" in d:
        parts.append(f'"_unknown_bits": {d["_unknown_bits"]!r}')
    return "{" + ", ".join(parts) + "}"


def emit(area_data, rooms, mobs, objs, resets, room_map, mob_map, obj_map):
    out = []

    def w(s=""):
        out.append(s)

    def r(vnum, mapping):
        return mapping.get(vnum, str(vnum))

    aname    = area_data.get("name", "Unknown")
    vnums    = area_data.get("vnums", (0, 0))
    version  = area_data.get("version", None)
    min_lvl  = area_data.get("min_level", 1)
    max_lvl  = area_data.get("max_level", 10)
    builders = area_data.get("builders", "Unknown")
    credits  = area_data.get("credits", "Unknown")

    w("# fmt: off")
    w(f"# Area: {aname}")
    w(f"# Builders: {builders}")
    w(f"# VNUM ranges: Rooms {vnums[0]}-{vnums[1]}")
    w(f"# Credits: {credits}")
    w("")
    w("")
    w("AREA = {")
    w(f'    "name":     {aname!r},')
    w(f'    "builders": {builders!r},')
    w(f'    "vnums":    {vnums!r},')
    w(f'    "credits":  {credits!r},')
    w(f'    "levels":   ({min_lvl}, {max_lvl}),')
    if version is not None:
        w(f'    "version":  {version!r},')
    w("}")
    w("")

    # ── Constants ──
    BAR = "─"
    w(f"# ── Room VNUMs {BAR * 65}")
    for vnum, _ in rooms:
        w(f"{room_map[vnum]:<34} = {vnum}")
    w("")
    w(f"# ── Mob template VNUMs {BAR * 57}")
    for vnum, _ in mobs:
        w(f"{mob_map[vnum]:<34} = {vnum}")
    w("")
    w(f"# ── Item template VNUMs {BAR * 56}")
    for vnum, _ in objs:
        w(f"{obj_map[vnum]:<34} = {vnum}")
    w("")

    # ── MOBILES ──
    w(f"# ── Mob templates {BAR * 62}")
    w("# hp_dice / mana_dice / damage: (num_dice, die_size, bonus)")
    w("# AC: avg(pierce,bash,slash,exotic) / 10 per REFERENCE.md  # TODO: verify scale")
    w("# hitroll: from level line; no separate damroll in .are (dam_dice bonus is it)")
    w("# loot: left empty — populate from RESETS E/G lines if needed")
    w("MOBILES = {")
    for vnum, mob in mobs:
        cname = mob_map[vnum]
        w(f"    {cname}: {{")
        w(f'        "keywords":    {mob["keywords"]!r},')
        w(f'        "short_descr": {mob["short_descr"]!r},')
        w(f'        "long_descr":  {mob["long_descr"]!r},')
        w(f'        "description": {mob["description"]!r},')
        w(f'        "race":        {mob["race"]!r},')
        for flag_key in ("act_flags", "aff_flags"):
            fd = mob[flag_key]
            if fd:
                w(f'        "{flag_key}": {_repr_flags(fd)},')
        w(f'        "alignment": {mob["alignment"]},')
        w(f'        "level":     {mob["level"]},')
        w(f'        "hitroll":   {mob["hitroll"]},')
        w(f'        "hp_dice":   {mob["hp_dice"]!r},')
        w(f'        "mana_dice": {mob["mana_dice"]!r},')
        w(f'        "damage":    {mob["damage"]!r},  "dam_type": {mob["dam_type"]!r},')
        w(f'        "AC":        {mob["AC"]},')
        for flag_key in ("off_flags", "imm_flags", "res_flags", "vuln_flags"):
            fd = mob[flag_key]
            if fd:
                w(f'        "{flag_key}": {_repr_flags(fd)},')
        w(f'        "sex":  {mob["sex"]!r},')
        w(f'        "gold": {mob["gold"]},')
        w(f'        "size": {mob["size"]!r},')
        w(f'        "loot": [],  # TODO: from RESETS E/G')
        w("    },")
    w("}")
    w("")

    # ── ROOMS ──
    w(f"# ── Rooms {BAR * 70}")
    w("ROOMS = {")
    for vnum, room in rooms:
        cname = room_map[vnum]
        w(f"    {cname}: {{")
        w(f'        "name": {room["name"]!r},')
        w(f'        "desc": {repr(room["desc"])},')
        w(f'        "exits": {{')
        for d in sorted(room["exits"], key=lambda x: "neswud".index(x)):
            to_vnum = room["exits"][d]
            to_c    = r(to_vnum, room_map)
            note    = room["exit_notes"].get(d)
            if note:
                parts = [f'"to": {to_c}']
                for flag in ("isdoor", "closed", "locked", "pickproof", "nopass",
                             "doorbell", "easy", "hard", "infuriating", "noclose", "nolock"):
                    if note.get(flag):
                        parts.append(f'"{flag}": True')
                w(f'            "{d}": {{{", ".join(parts)}}},')
            else:
                w(f'            "{d}": {to_c},')
        w("        },")
        if room["flags"]:
            w(f'        "flags": {_repr_flags(room["flags"])},')
        if room["sector"]:
            w(f'        "sector": {room["sector"]},')
        w("    },")
    w("}")
    w("")

    # ── OBJECTS ──
    w(f"# ── Item templates {BAR * 61}")
    w("OBJECTS = {")
    for vnum, obj in objs:
        cname = obj_map[vnum]
        w(f"    {cname}: {{")
        w(f'        "keywords":    {obj["keywords"]!r},')
        w(f'        "short_descr": {obj["short_descr"]!r},')
        w(f'        "description": {obj["description"]!r},')
        w(f'        "material":    {obj["material"]!r},')
        w(f'        "type": {obj["type"]!r},')
        w(f'        "wear_flags": {_repr_flags(obj["wear_flags"])},')
        if obj.get("extra_flags"):
            bits = decode_flags(obj["extra_flags"], {
                0: "glow", 1: "hum", 6: "magic", 7: "nodrop",
                8: "bless", 13: "inventory", 14: "nopurge",
                20: "melt_drop", 26: "quest",
            })
            if bits:
                w(f'        "extra_flags": {_repr_flags(bits)},')
        if obj["type"] == "weapon":
            wt = obj.get("weapon_type", "unknown")
            an = obj.get("dam_type", "hit")
            dc = obj.get("dice", (1, 1, 0))
            w(f'        "weapon_type": {wt!r}, "dam_type": {an!r}, "dice": {dc!r},')
            wf = obj.get("weapon_flags", {})
            w(f'        "weapon_flags": {_repr_flags(wf)},')
        elif obj["type"] == "armor" and "AC" in obj:
            w(f'        "AC": {obj["AC"]},')
        elif obj["type"] == "potion":
            if "spell_level" in obj:
                w(f'        "spell_level": {obj["spell_level"]},')
            if obj.get("spells"):
                w(f'        "spells": {obj["spells"]!r},')
        if obj.get("stat_bonuses"):
            w(f'        "stat_bonuses": {obj["stat_bonuses"]!r},')
        w(f'        "level": {obj["level"]}, "weight": {obj["weight"]}, "value": {obj["value"]},')
        if obj["extra_descs"]:
            w(f'        "extra_descs": {obj["extra_descs"]!r},')
        w("    },")
    w("}")
    w("")

    # ── RESETS ──
    w(f"# ── Resets {BAR * 69}")
    w('# ("M", mob_template_vnum, global_limit, room_vnum, room_limit)  — spawn mob instance up to limits')
    w('# ("O", item_template_vnum, room_vnum) — place one item copy in room')
    w('# E/G/P/R/D/F resets from .are are not yet handled — see # TODO lines')
    w("RESETS = (")
    for reset in resets:
        if reset[0] == "M":
            _, mv, gl, rv, rl = reset
            mc = r(mv, mob_map)
            rc = r(rv, room_map)
            w(f'    ("M", {mc}, {gl}, {rc}, {rl}),')
        elif reset[0] == "O":
            _, ov, rv = reset
            oc = r(ov, obj_map)
            rc = r(rv, room_map)
            w(f'    ("O", {oc}, {rc}),')
        else:
            w(f"    # TODO: {reset[1]}")
    w(")")
    w("")

    return "\n".join(out)


# ── Entry point ───────────────────────────────────────────────────────────────

def convert(are_path, out_path=None):
    text  = Path(are_path).read_text(encoding="utf-8", errors="replace")
    sects = split_sections(text)

    area_data = parse_areadata(sects.get("AREADATA", []))
    rooms     = parse_rooms(sects.get("ROOMS", []))
    mobs      = parse_mobiles(sects.get("MOBILES", []))
    objs      = parse_objects(sects.get("OBJECTS", []))
    resets    = parse_resets(sects.get("RESETS", []))

    room_map = make_const_map("R", rooms, lambda d: d["name"])
    mob_map  = make_const_map("M", mobs,  lambda d: d["keywords"])
    obj_map  = make_const_map("I", objs,  lambda d: d["keywords"])

    code = emit(area_data, rooms, mobs, objs, resets, room_map, mob_map, obj_map)

    if out_path:
        Path(out_path).write_text(code, encoding="utf-8")
        print(f"Written to {out_path}", file=sys.stderr)
    else:
        sys.stdout.write(code)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <input.are> [output.py]", file=sys.stderr)
        sys.exit(1)
    convert(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
