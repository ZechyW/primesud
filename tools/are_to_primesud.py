#!/usr/bin/env python3
"""Convert a 1stMud 4.5.x .are file to a PrimeSUD Python area module.

Usage:
    python are_to_primesud.py school.are area_school.dat

Sections handled:   #AREADATA  #ROOMS  #MOBILES  #OBJECTS  #RESETS  #SPECIALS
Sections skipped:   #SHOPS  #MOBPROGS  #OBJPROGS  #ROOMPROGS

RESETS handling:
  M O E G  -> emitted as runtime tuples in RESETS
  P R      -> emitted as deferred tuples (no runtime handler yet)
  F D      -> baked into room exit flags at conversion time; not in RESETS

Design choices:
  - perm_stat omitted: not in .are format
  - respawn omitted: 1stMud uses area-level timed resets, not per-mob timers
  - Mob and armor-object AC values are preserved exactly as they appear in the
    source .are file; PrimeSUD runtime applies 1stMud-equivalent scaling
  - hitroll: taken from level line field 4; no separate damroll in .are mobs
    (the +B bonus in damage dice IS the damroll analogue in 1stMud)
  - act_flags, off_flags, imm/res/vuln_flags: decoded into name->True dicts
    using flag tables from REFERENCE.md; included even if PrimeSUD ignores them
  - Exits: plain vnum for open passages; dict {"to": vnum, "isdoor": True, ...}
    for exits with any door flags -- all EXIT_FLAGS encoded as name->True keys
  - Constant names: generated from display text, deduplicated with _<vnum>
  - sector_type: decoded to name string (e.g. 1 -> "city", 0 -> "inside")
"""

import re
import sys
from pathlib import Path


# -- Flag tables from REFERENCE.md --------------------------------------------

ACT_FLAGS = {
    0: "is_npc", 1: "sentinel", 2: "scavenger", 5: "aggressive",
    6: "stay_area", 7: "wimpy", 8: "pet", 9: "train", 10: "practice",
    14: "undead", 16: "cleric", 17: "mage", 18: "thief", 19: "warrior",
    20: "noalign", 21: "nopurge", 22: "outdoors", 24: "indoors",
    26: "healer", 27: "gain", 28: "update_always", 29: "changer",
}
AFFECTED_BY = {
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
SECTOR_NAMES = {                                        # sector_t enum values (cf. defines.h)
     0: "inside",    1: "city",     2: "field",   3: "forest",
     4: "hills",     5: "mountain", 6: "swim",    7: "noswim",
     8: "ice",       9: "air",     10: "desert",  11: "road",
    12: "path",     13: "swamp",   14: "jungle",  15: "cave",
    16: "none",
}
EXTRA_FLAGS = {                                         # ITEM_* from bits.h (BIT_A=0 ... BIT_a=26; BIT_X=23 unused)
    0: "glow",        1: "hum",          2: "dark",        3: "lock",
    4: "evil",        5: "invis",        6: "magic",       7: "nodrop",
    8: "bless",       9: "anti_good",   10: "anti_evil",  11: "anti_neutral",
   12: "noremove",   13: "inventory",   14: "nopurge",    15: "rot_death",
   16: "vis_death",  17: "auctioned",   18: "nonmetal",   19: "nolocate",
   20: "melt_drop",  21: "had_timer",   22: "sell_extract",
   24: "burn_proof", 25: "nouncurse",   26: "quest",
}
WEAR_SLOT = {
    1: "finger", 2: "neck", 3: "body", 4: "head", 5: "legs",
    6: "feet", 7: "hands", 8: "arms", 9: "shield", 10: "about",
    11: "waist", 12: "wrist", 13: "wield", 14: "hold", 16: "float",
}
# cf. 1stMud h/defines.h apply_t enum -- note APPLY_SAVING_PARA sits at 21,
# shifting rod/petri/breath/spell/spell_affect one slot later than ROM/QuickMUD.
APPLY_LOC = {
    1: "str", 2: "dex", 3: "int", 4: "wis", 5: "con",
    6: "sex", 7: "class", 8: "level", 9: "age", 10: "height", 11: "weight",
    12: "mana", 13: "hit", 14: "move", 15: "gold", 16: "exp",
    17: "ac", 18: "hitroll", 19: "damroll",
    20: "saves", 21: "saving_para", 22: "saving_rod", 23: "saving_petri",
    24: "saving_breath", 25: "saving_spell", 26: "spell_affect",
}
FORM_FLAGS = {                                          # FORM_* from bits.h
    0: "edible", 1: "poison", 2: "magical", 3: "instant_decay", 4: "other",
    6: "animal", 7: "sentient", 8: "undead", 9: "construct", 10: "mist",
    11: "intangible", 12: "biped", 13: "centaur", 14: "insect", 15: "spider",
    16: "crustacean", 17: "worm", 18: "blob", 21: "mammal", 22: "bird",
    23: "reptile", 24: "snake", 25: "dragon", 26: "amphibian", 27: "fish",
    28: "cold_blood",
}
PART_FLAGS = {                                          # PART_* from bits.h
    0: "head", 1: "arms", 2: "legs", 3: "heart", 4: "brains", 5: "guts",
    6: "hands", 7: "feet", 8: "fingers", 9: "ear", 10: "eye",
    11: "long_tongue", 12: "eyestalks", 13: "tentacles", 14: "fins",
    15: "wings", 16: "tail", 20: "claws", 21: "fangs", 22: "horns",
    23: "scales", 24: "tusks",
}
# Object condition letter (cf. db2.c load_objects condition switch); missing
# or unrecognized letter defaults to 100 (perfect condition).
OBJ_CONDITION = {
    "P": 100, "G": 90, "A": 75, "W": 50, "D": 25, "B": 10, "R": 0,
}
# 1stMud position_flags long names (tables.c) -> QuickMUD-style short forms
POS_TO_SHORT = {
    "standing": "stand", "sitting": "sit", "resting": "rest",
    "sleeping": "sleep", "fighting": "fight",
}
DIR_NAME = {0: "n", 1: "e", 2: "s", 3: "w", 4: "u", 5: "d"}
WLOC_SLOT = {                                           # wloc_t enum from h/defines.h (E reset arg3)
    0:  "light",
    1:  "finger_l", 2:  "finger_r",
    3:  "neck_1",   4:  "neck_2",
    5:  "body",     6:  "head",    7:  "legs",  8: "feet",
    9:  "hands",    10: "arms",    11: "shield", 12: "about",
    13: "waist",    14: "wrist_l", 15: "wrist_r",
    16: "wield",    17: "hold",    18: "float",
    19: "secondary",
}


# -- Bit-string helpers --------------------------------------------------------

def parse_bitstring(s):
    """'+YnnYn...' -> set of bit positions where Y appears."""
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
    """Bit-position set + table -> {name: True} dict; skip is a set of positions to omit."""
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


# -- Dice and string helpers ---------------------------------------------------

def split_tokens(line):
    """Split a .are value line respecting single-quoted tokens (may contain spaces).

    '15 'cure critical' '' '' ''  ->  ['15', 'cure critical', '', '', '']
    Falls back to str.split() for lines with no quotes.
    """
    tokens = []
    i = 0
    s = line.strip()
    while i < len(s):
        if s[i] == "'":
            j = s.index("'", i + 1)
            tokens.append(s[i + 1:j])
            i = j + 1
        elif s[i].isspace():
            i += 1
        else:
            j = i
            while j < len(s) and not s[j].isspace():
                j += 1
            tokens.append(s[i:j])
            i = j
    return tokens


def parse_dice(s):
    """'NdM+B' or 'NdM-B' -> (N, M, B)."""
    m = re.match(r"(\d+)d(\d+)([+-]\d+)?", s)
    if m:
        n, d, b = m.groups()
        return (int(n), int(d), int(b) if b else 0)
    return (1, 1, 0)


def parse_flagnum(s):
    """Parse plain int or 1stMud bitstring-encoded numeric field."""
    if s.startswith("+"):
        total = 0
        for i, ch in enumerate(s[1:]):
            if ch == "Y":
                total += 1 << i
            elif ch != "n":
                break
        return total
    return int(s)


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


# -- Low-level .are reader -----------------------------------------------------

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


def read_tilde_string_inline(prefix, lines, i):
    """Like read_tilde_string, but the string may start with `prefix` -- text
    already sitting on the same physical line as a bare command letter (e.g.
    a room owner line "OSaska~"): fread_string(fp) skips whitespace -- which
    includes newlines -- after the single-char fread_letter(fp), so the
    value can be on the SAME line as the letter or, if nothing follows,
    spill onto the next one). Returns (text, next_i).
    """
    idx = prefix.find("~")
    if idx >= 0:
        return prefix[:idx].strip(), i
    parts = [prefix]
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


# -- Section parsers -----------------------------------------------------------

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


# F-line field-word prefix -> (canonical mob.py flag-removal key, decode table
# for that field's bits); cf. db2.c load_mobiles case 'F' str_prefix() chain.
F_PREFIX_MAP = {
    "act": ("act",   ACT_FLAGS),
    "aff": ("aff",   AFFECTED_BY),
    "off": ("off",   OFF_FLAGS),
    "imm": ("imm",   RESIST_FLAGS),
    "res": ("res",   RESIST_FLAGS),
    "vul": ("vuln",  RESIST_FLAGS),
    "for": ("form",  FORM_FLAGS),
    "par": ("parts", PART_FLAGS),
}


def parse_mobiles(lines, version=None):
    is_v4 = isinstance(version, int) and version >= 4
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
        # Normalize to RACE_TABLE key form ("elf" -> "Elf"); .are files store
        # lowercase, race_lookup() in 1stMud is case-insensitive.
        race = race.capitalize()

        # act_flags  affected_by  alignment  group
        parts = lines[i].split(); i += 1
        act_bits = parse_bitstring(parts[0]) if parts else set()
        aff_bits = parse_bitstring(parts[1]) if len(parts) > 1 else set()
        alignment = int(parts[2]) if len(parts) > 2 else 0
        group = int(parts[3]) if len(parts) > 3 else 0

        # level  [random  autoset]  hitroll -- random/autoset only present
        # when #AREADATA Version >= 4 (cf. db2.c load_mobiles:101-107)
        parts = lines[i].split(); i += 1
        level = int(parts[0]) if parts else 0
        if is_v4:
            hitroll = int(parts[3]) if len(parts) > 3 else 0
        else:
            hitroll = int(parts[1]) if len(parts) > 1 else 0

        # hp_dice  mana_dice  dam_dice  'dam_type'
        parts = lines[i].split(); i += 1
        hp_dice   = parse_dice(parts[0]) if parts else (1, 1, 0)
        mana_dice = parse_dice(parts[1]) if len(parts) > 1 else (1, 1, 0)
        dam_dice  = parse_dice(parts[2]) if len(parts) > 2 else (1, 1, 0)
        dam_type  = parts[3].strip("'") if len(parts) > 3 else "hit"

        # ac_pierce  ac_bash  ac_slash  ac_exotic
        parts = lines[i].split(); i += 1
        try:
            armor = tuple(int(x) for x in parts[:4])
        except (ValueError, TypeError):
            armor = (10, 10, 10, 10)

        # off_flags  imm_flags  res_flags  vuln_flags
        parts = lines[i].split(); i += 1
        off_bits  = parse_bitstring(parts[0]) if parts else set()
        imm_bits  = parse_bitstring(parts[1]) if len(parts) > 1 else set()
        res_bits  = parse_bitstring(parts[2]) if len(parts) > 2 else set()
        vuln_bits = parse_bitstring(parts[3]) if len(parts) > 3 else set()

        # start_pos  default_pos  sex  wealth
        # 1stMud .are stores long-form positions ("standing"); normalize to
        # the short form QuickMUD areas use ("stand") so the emitted schema
        # is common across converters and matches config.py POS_FROM_SHORT.
        parts = lines[i].split(); i += 1
        start_pos   = POS_TO_SHORT.get(parts[0], parts[0]) if parts else "stand"
        default_pos = (POS_TO_SHORT.get(parts[1], parts[1])
                       if len(parts) > 1 else "stand")
        sex    = parts[2] if len(parts) > 2 else "neutral"
        wealth = int(parts[3]) if len(parts) > 3 else 0

        # form_flags  part_flags  size  material
        parts = lines[i].split(); i += 1
        form_bits = parse_bitstring(parts[0]) if parts else set()
        part_bits = parse_bitstring(parts[1]) if len(parts) > 1 else set()
        size      = parts[2] if len(parts) > 2 else "medium"
        # read_word() strips surrounding quotes (fileio.c:441): 'unknown' -> unknown
        material  = parts[3].strip("'\"") if len(parts) > 3 else ""

        # optional trailer lines: F (flag remove) / M (mobprog trigger) / S
        # (kills/deaths, runtime save-state -- not modeled, consumed only).
        # cf. db2.c load_mobiles:142-207. [PRIMESUD] neither limbo.are nor
        # quest.are contains any F/M/S mob trailer, so the exact same-line
        # vs. next-line data layout below is inferred by analogy with the
        # OBJECTS 'A'/'F' trailers (bare letter, data on the following
        # line) rather than confirmed against real 1stMud data; the parser
        # tolerates both layouts.
        flag_removes_acc = {}
        mob_triggers = []
        while i < len(lines):
            tline = lines[i].strip()
            if tline.startswith("#") or tline == "":
                break
            tparts = tline.split(None, 1)
            letter = tparts[0] if tparts else ""
            rest_inline = tparts[1] if len(tparts) > 1 else ""
            if letter == "F":
                i += 1
                if rest_inline:
                    fparts = rest_inline.split()
                else:
                    fparts = lines[i].split() if i < len(lines) else []
                    i += 1
                if len(fparts) >= 2:
                    f_field = fparts[0]
                    f_bits = parse_bitstring(fparts[1])
                    for prefix, (canon, table) in F_PREFIX_MAP.items():
                        if f_field.startswith(prefix):
                            prev_table, prev_bits = flag_removes_acc.get(canon, (table, set()))
                            flag_removes_acc[canon] = (table, prev_bits | f_bits)
                            break
            elif letter == "M":
                i += 1
                if rest_inline:
                    data_line, data_i = rest_inline, i
                else:
                    data_line, data_i = (lines[i] if i < len(lines) else ""), i + 1
                mparts = data_line.split(None, 2)
                trig_type = mparts[0] if mparts else "random"
                mpv = int(mparts[1]) if len(mparts) > 1 and mparts[1].lstrip("-").isdigit() else 0
                rest = mparts[2] if len(mparts) > 2 else ""
                phrase, i = read_tilde_string_inline(rest, lines, data_i)
                mob_triggers.append((trig_type.lower(), mpv, phrase))
            elif letter == "S":
                i += 1
                if not rest_inline:
                    i += 1
            else:
                break

        flag_removes = []
        for canon, (table, bits) in flag_removes_acc.items():
            names = tuple(table.get(pos, pos) for pos in sorted(bits))
            flag_removes.append((canon, names))

        mob = {
            "keywords":    keywords,
            "short_descr": short_descr,
            "long_descr":  long_descr,
            "description": description,
            "race":        race,
            "act_flags":   decode_flags(act_bits, ACT_FLAGS, skip={0}),  # omit IS_NPC
            "affected_by":   decode_flags(aff_bits, AFFECTED_BY),
            "alignment":   alignment,
            "group":       group,
            "level":       level,
            "hitroll":     hitroll,
            "hp_dice":     hp_dice,
            "mana_dice":   mana_dice,
            "damage":      dam_dice,
            "dam_type":    dam_type,
            "armor":       armor,
            "off_flags":   decode_flags(off_bits, OFF_FLAGS),
            "imm_flags":   decode_flags(imm_bits, RESIST_FLAGS),
            "res_flags":   decode_flags(res_bits, RESIST_FLAGS),
            "vuln_flags":  decode_flags(vuln_bits, RESIST_FLAGS),
            "start_pos":   start_pos,
            "default_pos": default_pos,
            "form_flags":  decode_flags(form_bits, FORM_FLAGS),
            "part_flags":  decode_flags(part_bits, PART_FLAGS),
            "material":    material,
            "sex":         sex,
            "wealth":      wealth,
            "size":        size,
            "mob_triggers": mob_triggers,
        }
        if flag_removes:
            mob["flag_removes"] = tuple(flag_removes)
        mobs.append((vnum, mob))
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

        # item-type-specific value line (spell names may contain spaces: 'cure critical')
        val_line = split_tokens(lines[i]); i += 1

        # level  weight  cost  condition
        lw_line = lines[i].split(); i += 1
        level  = int(lw_line[0]) if lw_line else 0
        weight = int(lw_line[1]) if len(lw_line) > 1 else 0
        cost   = int(lw_line[2]) if len(lw_line) > 2 else 0
        condition = OBJ_CONDITION.get(lw_line[3], 100) if len(lw_line) > 3 else 100

        # optional A / E / F / O trailer lines
        applies      = {}
        extra_descs  = []
        flag_affects = []
        while i < len(lines):
            tline = lines[i].strip()
            if tline.startswith("#"):
                break
            if tline == "A":
                i += 1
                ap = lines[i].split(); i += 1
                try:
                    loc, mod = int(ap[0]), int(ap[1])
                    # Unknown apply locs are kept under a str(loc) key rather
                    # than silently dropped (cf. F-line handling below).
                    applies[APPLY_LOC.get(loc, str(loc))] = mod
                except (ValueError, IndexError):
                    pass
            elif tline == "E":
                i += 1
                ekw,  i = read_tilde_string(lines, i)
                edesc, i = read_tilde_string(lines, i)
                extra_descs.append((ekw, edesc))
            elif tline == "F":
                # cf. db2.c load_objects case 'F': where apply_loc modifier
                # bitvector (where: A=affects I=immune R=resist V=vuln) --
                # same apply_t location table as the plain 'A' affect above,
                # decoded against AFFECTED_BY/RESIST_FLAGS per `where`.
                i += 1
                fp_ = lines[i].split(); i += 1
                if len(fp_) >= 4:
                    where_map = {"A": "affects", "I": "immune", "R": "resist", "V": "vuln"}
                    where = where_map.get(fp_[0], fp_[0])
                    try:
                        f_loc, f_mod = int(fp_[1]), int(fp_[2])
                    except ValueError:
                        f_loc, f_mod = 0, 0
                    loc_name = APPLY_LOC.get(f_loc, str(f_loc))
                    bit_table = AFFECTED_BY if where == "affects" else RESIST_FLAGS
                    bits = decode_flags(parse_bitstring(fp_[3]), bit_table)
                    flag_affects.append((where, loc_name, f_mod, bits))
            elif tline == "O" or tline == "":
                i += 1
            else:
                break

        # Build wear_flags dict (bit 0 = ITEM_TAKE; WEAR_SLOT covers equip
        # slots; an object may occupy more than one slot bit, e.g. wrist).
        wear_flags = {}
        no_sac = 15 in wear_bits  # ITEM_NO_SAC (bits.h:386)
        if 0 in wear_bits:
            wear_flags["take"] = True
        for pos in sorted(wear_bits):
            if pos in WEAR_SLOT:
                wear_flags[WEAR_SLOT[pos]] = True

        obj = {
            "keywords":    keywords,
            "short_descr": short_descr,
            "description": description,
            "extra_descs": extra_descs,
            "material":    material,
            "type":        item_type,
            "wear_flags":  wear_flags,
            "no_sac":      no_sac,
            "level":       level,
            "weight":      weight,
            "value":       cost,
            "extra_flags": extra_bits,
        }
        if condition != 100:
            obj["condition"] = condition
        if flag_affects:
            obj["flag_affects"] = tuple(flag_affects)

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
                obj["armor"] = (
                    parse_flagnum(val_line[0]),
                    parse_flagnum(val_line[1]) if len(val_line) > 1 else 0,
                    parse_flagnum(val_line[2]) if len(val_line) > 2 else 0,
                    parse_flagnum(val_line[3]) if len(val_line) > 3 else 0,
                )
            except ValueError:
                obj["armor"] = (0, 0, 0, 0)
        elif item_type in ("potion", "pill", "scroll") and val_line:
            obj["spell_level"] = int(val_line[0])
            obj["spells"] = [s for s in val_line[1:] if s]
        elif item_type in ("wand", "staff") and val_line:
            obj["spell_level"] = int(val_line[0])
            obj["max_charges"] = int(val_line[1]) if len(val_line) > 1 else 0
            obj["charges"] = int(val_line[2]) if len(val_line) > 2 else 0
            obj["spell"] = val_line[3] if len(val_line) > 3 and val_line[3] else ""
            # value[4] (recharge) is a dead field in 1stMud 4.5.3 - skipped
        elif item_type == "light" and val_line:
            # value[2] (cf. db2.c load_objects default case: read_flag() --
            # light falls through to the generic 4-flag-field value line, so
            # this token is bitstring-encoded, not a plain decimal number).
            # Raw hours stored as-is; ROM/1stMud 0/999 conventions differ.
            obj["light_hours"] = parse_flagnum(val_line[2]) if len(val_line) > 2 else 0

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
        if len(flag_parts) > 2:
            sector_int = int(flag_parts[2])
            sector = SECTOR_NAMES.get(sector_int, str(sector_int))
        else:
            sector = None

        exits      = {}
        exit_notes = {}
        exit_descs = {}
        extra_descs = []
        heal_rate  = None
        mana_rate  = None
        owner = ""
        room_flags = decode_flags(room_bits, ROOM_FLAGS)
        # "Horrible hack" (db.c load_rooms:895-896): any room in [3000, 3400)
        # is forced ROOM_LAW regardless of its stored flags.
        if 3000 <= vnum < 3400:
            room_flags["law"] = True

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
                ex_desc, i = read_tilde_string(lines, i)
                ex_keyword, i = read_tilde_string(lines, i)
                # New-format (version >= 2) exit line: flags key to_room
                # (cf. db.c load_rooms:982-990).
                ex_parts = lines[i].split(); i += 1
                ex_bits  = parse_bitstring(ex_parts[0]) if ex_parts else set()
                ex_key   = int(ex_parts[1]) if len(ex_parts) > 1 else -1
                to_room  = int(ex_parts[2]) if len(ex_parts) > 2 else -1
                if direction in DIR_NAME:
                    d = DIR_NAME[direction]
                    # to_room <= 0: keep the exit as examinable but
                    # untraversable, preserved as "to": None (cf. quickmud
                    # converter / fix_exits nulling only the destination).
                    exits[d] = to_room if to_room > 0 else None
                    ex_flags = decode_flags(ex_bits, EXIT_FLAGS)
                    if ex_key > 0:
                        ex_flags["key"] = ex_key
                    if ex_flags:
                        exit_notes[d] = ex_flags
                    if ex_desc:
                        exit_descs[d] = ex_desc
                    if ex_keyword:
                        exit_notes.setdefault(d, {})["keyword"] = ex_keyword
            elif tline == "E":
                i += 1
                ekw, i = read_tilde_string(lines, i)
                edesc, i = read_tilde_string(lines, i)
                extra_descs.append((ekw, edesc))
            elif tline[0:2] in ("H ", "M "):
                # heal_rate / mana_rate (cf. db.c load_rooms:915-921)
                parts = tline.split()
                j = 0
                while j < len(parts):
                    if parts[j] == "H" and j + 1 < len(parts):
                        heal_rate = int(parts[j + 1]); j += 2
                    elif parts[j] == "M" and j + 1 < len(parts):
                        mana_rate = int(parts[j + 1]); j += 2
                    else:
                        j += 1
                i += 1
            elif tline == "":
                i += 1
            elif tline[0] == "C":
                # cf. db.c load_rooms:923-929 case 'C': reads and discards a
                # tilde string (`const char *tmp = read_string(fp);
                # free_string(tmp);`) -- 1stMud does NOT persist a room clan
                # value (unlike ROM/QuickMUD); consumed here only so the
                # parser stays aligned, never emitted.
                _discarded, i = read_tilde_string_inline(tline[1:], lines, i + 1)
            elif tline[0] == "O":
                # cf. db.c load_rooms:1007-1016 case 'O': owner = read_string
                # (fp); also force-sets ROOM_NOEXPLORE on the room.
                owner, i = read_tilde_string_inline(tline[1:], lines, i + 1)
                room_flags["noexplore"] = True
            elif tline[0] == "G":
                # cf. db.c load_rooms case 'G': guild = read_number(fp).
                # [PRIMESUD] not modeled at runtime; consumed only.
                i += 1
            else:
                i += 1

        room = {
            "name":       name,
            "desc":       description,
            "exits":      exits,
            "exit_notes": exit_notes,
            "exit_descs": exit_descs,
            "extra_descs": extra_descs,
            "flags":      room_flags,
            "sector":     sector,
            "heal_rate":  heal_rate,
            "mana_rate":  mana_rate,
        }
        if owner:
            room["owner"] = owner
        rooms.append((vnum, room))
    return rooms


def parse_resets(lines):
    """Parse #RESETS section.

    Returns:
        tuple: (resets, foverrides, doverrides)
            resets:     list of (cmd, ...) tuples for M/O/E/G/P/R
            foverrides: {(room_vnum, dir_name): exit_flags_dict} -- F resets baked into exits
            doverrides: {(room_vnum, dir_name): 0|1|2}           -- D resets baked into exits
    """
    resets = []
    foverrides = {}
    doverrides = {}
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
        elif cmd == "E" and len(parts) >= 5:
            # E  0  item_vnum  limit  wloc_num
            slot = WLOC_SLOT.get(int(parts[4]), "hold")
            limit = int(parts[3])
            resets.append(("E", int(parts[2]), slot, limit))
        elif cmd == "G" and len(parts) >= 4:
            # G  0  item_vnum  limit   (arg3 not read for G in 1stMud load_resets)
            limit = int(parts[3])
            resets.append(("G", int(parts[2]), limit))
        elif cmd == "P" and len(parts) >= 6:
            # P  0  item_vnum  global_limit  container_vnum  max_count
            resets.append(("P", int(parts[2]), int(parts[3]), int(parts[4]), int(parts[5])))
        elif cmd == "R" and len(parts) >= 4:
            # R  0  room_vnum  num_dirs
            resets.append(("R", int(parts[2]), int(parts[3])))
        elif cmd == "F" and len(parts) >= 6:
            # F  0  room_vnum  exit_num  0  +flags  -- baked into exits at conversion time
            d = DIR_NAME.get(int(parts[3]))
            if d is not None:
                foverrides[(int(parts[2]), d)] = decode_flags(parse_bitstring(parts[5]), EXIT_FLAGS)
        elif cmd == "D" and len(parts) >= 5:
            # D  0  room_vnum  exit_num  locks (0=open 1=closed 2=locked)
            d = DIR_NAME.get(int(parts[3]))
            if d is not None:
                doverrides[(int(parts[2]), d)] = int(parts[4])
    return resets, foverrides, doverrides


def parse_specials(lines):
    """Parse #SPECIALS section into (cmd, mob_vnum, spec_fun_name) tuples."""
    specials = []
    for line in lines:
        parts = line.split()
        if not parts or parts[0] == "*":
            continue
        cmd = parts[0]
        if cmd == "S":
            break
        if cmd == "M" and len(parts) >= 3:
            specials.append(("M", int(parts[1]), parts[2]))
    return specials


# -- Python emitter ------------------------------------------------------------

def _repr_flags(d):
    """Compact repr for flag dicts: {name: True, ...}."""
    if not d:
        return "{}"
    parts = [f'"{k}": True' for k in d if k != "_unknown_bits"]
    if "_unknown_bits" in d:
        parts.append(f'"_unknown_bits": {pyrepr(d["_unknown_bits"])}')
    return "{" + ", ".join(parts) + "}"


def pyrepr(value):
    """Return an ASCII-only Python literal."""
    return ascii(value)


def asciitext(value):
    """Return ASCII-only plain text for generated comments."""
    return str(value).encode("ascii", "backslashreplace").decode("ascii")


def emit(area_data, rooms, mobs, objs, resets, specials, room_map, mob_map, obj_map,
         foverrides=None, doverrides=None):
    out = []

    def w(s=""):
        out.append(s)

    def r(vnum, mapping=None):
        return str(vnum)

    aname    = area_data.get("name", "Unknown")
    vnums    = area_data.get("vnums", (0, 0))
    version  = area_data.get("version", None)
    # cf. recycle.c new_area(): min_level=0, max_level=MAX_LEVEL (60)
    min_lvl  = area_data.get("min_level", 0)
    max_lvl  = area_data.get("max_level", 60)
    builders = area_data.get("builders", "Unknown")
    credits  = area_data.get("credits", "Unknown")

    w("# fmt: off")
    w(f"# Area: {asciitext(aname)}")
    w(f"# Builders: {asciitext(builders)}")
    w(f"# VNUM ranges: Rooms {vnums[0]}-{vnums[1]}")
    w(f"# Credits: {asciitext(credits)}")
    w("")
    w("")
    w("AREA = {")
    w(f'    "name":     {pyrepr(aname)},')
    w(f'    "builders": {pyrepr(builders)},')
    w(f'    "vnums":    {pyrepr(vnums)},')
    w(f'    "credits":  {pyrepr(credits)},')
    w(f'    "levels":   ({min_lvl}, {max_lvl}),')
    if version is not None:
        w(f'    "version":  {pyrepr(version)},')
    w("}")
    w("")

    BAR = "-"

    # -- MOBILES --
    w(f"# -- Mob templates {BAR * 62}")
    w("# hp_dice / mana_dice / damage: (num_dice, die_size, bonus)")
    w("# armor: (pierce, bash, slash, exotic), raw .are units")
    w("# hitroll: from level line; no separate damroll in .are (dam_dice bonus is it)")
    w("MOBILES = {")
    for vnum, mob in mobs:
        cname = vnum
        w(f"    {cname}: {{")
        w(f'        "keywords":    {pyrepr(mob["keywords"])},')
        w(f'        "short_descr": {pyrepr(mob["short_descr"])},')
        w(f'        "long_descr":  {pyrepr(mob["long_descr"])},')
        w(f'        "description": {pyrepr(mob["description"])},')
        w(f'        "race":        {pyrepr(mob["race"])},')
        for flag_key in ("act_flags", "affected_by"):
            fd = mob[flag_key]
            if fd:
                w(f'        "{flag_key}": {_repr_flags(fd)},')
        w(f'        "alignment": {mob["alignment"]},')
        if mob["group"] != 0:
            w(f'        "group":     {mob["group"]},')
        w(f'        "level":     {mob["level"]},')
        w(f'        "hitroll":   {mob["hitroll"]},')
        w(f'        "hp_dice":   {pyrepr(mob["hp_dice"])},')
        w(f'        "mana_dice": {pyrepr(mob["mana_dice"])},')
        w(f'        "damage":    {pyrepr(mob["damage"])},  "dam_type": {pyrepr(mob["dam_type"])},')
        w(f'        "armor":     {pyrepr(mob["armor"])},')
        for flag_key in ("off_flags", "imm_flags", "res_flags", "vuln_flags"):
            fd = mob[flag_key]
            if fd:
                w(f'        "{flag_key}": {_repr_flags(fd)},')
        w(f'        "start_pos":   {pyrepr(mob["start_pos"])},')
        w(f'        "default_pos": {pyrepr(mob["default_pos"])},')
        for flag_key in ("form_flags", "part_flags"):
            fd = mob[flag_key]
            if fd:
                w(f'        "{flag_key}": {_repr_flags(fd)},')
        w(f'        "material": {pyrepr(mob["material"])},')
        w(f'        "sex":    {pyrepr(mob["sex"])},')
        w(f'        "wealth": {mob["wealth"]},')
        w(f'        "size":   {pyrepr(mob["size"])},')
        if mob.get("mob_triggers"):
            w(f'        "mob_triggers": (')
            for trig_type, mpv, phrase in mob["mob_triggers"]:
                w(f'            ({pyrepr(trig_type)}, {mpv}, {pyrepr(phrase)}),')
            w(f'        ),')
        if mob.get("flag_removes"):
            # F-line flag removals, applied after race-merge at runtime
            # (cf. mob.py create_mobile; db2.c load_mobiles REMOVE_BIT).
            w(f'        "flag_removes": (')
            for canon, names in mob["flag_removes"]:
                w(f'            ({pyrepr(canon)}, {pyrepr(names)}),')
            w(f'        ),')
        w("    },")
    w("}")
    w("")

    # -- SPECIALS --
    w(f"# -- Specials {BAR * 67}")
    w('# ("M", mob_vnum, spec_fun_name) -- assign special function to mob template')
    w("SPECIALS = (")
    for special in specials:
        if special[0] == "M":
            _, mv, spec_name = special
            mc = r(mv, mob_map)
            w(f'    ("M", {mc}, {pyrepr(spec_name)}),')
    w(")")
    w("")

    # -- ROOMS --
    w(f"# -- Rooms {BAR * 70}")
    w("ROOMS = {")
    for vnum, room in rooms:
        cname = vnum
        w(f"    {cname}: {{")
        w(f'        "name": {pyrepr(room["name"])},')
        w(f'        "desc": {pyrepr(room["desc"])},')
        w(f'        "exits": {{')
        for d in sorted(room["exits"], key=lambda x: "neswud".index(x)):
            to_vnum = room["exits"][d]
            # "to": None = examinable-but-untraversable exit (blind exit,
            # to_room <= 0 in the .are data).
            to_c    = "None" if to_vnum is None else r(to_vnum, room_map)
            note    = room["exit_notes"].get(d) or {}
            # F override completely replaces exit flags (cf. 1stMud rs_flags
            # = arg5); "key" is a separate exit field untouched by the F
            # reset (db.c only overwrites rs_flags/exit_info), so preserve it.
            if foverrides and (vnum, d) in foverrides:
                saved_key = note.get("key")
                note = dict(foverrides[(vnum, d)])
                if saved_key:
                    note["key"] = saved_key
            # D override sets closed/locked state (only valid on isdoor exits)
            dstate = (doverrides or {}).get((vnum, d))
            if dstate is not None and note.get("isdoor"):
                note = dict(note)
                if dstate == 0:
                    note.pop("closed", None)
                    note.pop("locked", None)
                elif dstate == 1:
                    note["closed"] = True
                    note.pop("locked", None)
                else:
                    note["closed"] = True
                    note["locked"] = True
            ex_desc = room.get("exit_descs", {}).get(d, "")
            if note or ex_desc or to_vnum is None:
                eparts = [f'"to": {to_c}']
                if ex_desc:
                    eparts.append(f'"desc": {pyrepr(ex_desc)}')
                if note.get("keyword"):
                    eparts.append(f'"keyword": {pyrepr(note["keyword"])}')
                for flag in ("isdoor", "closed", "locked", "pickproof", "nopass",
                             "doorbell", "easy", "hard", "infuriating", "noclose", "nolock"):
                    if note.get(flag):
                        eparts.append(f'"{flag}": True')
                if note.get("key") and note["key"] > 0:
                    eparts.append(f'"key": {note["key"]}')
                w(f'            "{d}": {{{", ".join(eparts)}}},')
            else:
                w(f'            "{d}": {to_c},')
        w("        },")
        if room["flags"]:
            w(f'        "flags": {_repr_flags(room["flags"])},')
        if room["sector"] is not None:
            w(f'        "sector": {pyrepr(room["sector"])},')
        if room.get("heal_rate") is not None:
            w(f'        "heal_rate": {room["heal_rate"]},')
        if room.get("mana_rate") is not None:
            w(f'        "mana_rate": {room["mana_rate"]},')
        if room.get("extra_descs"):
            w(f'        "extra_descs": {pyrepr(room["extra_descs"])},')
        if room.get("owner"):
            w(f'        "owner": {pyrepr(room["owner"])},')
        w("    },")
    w("}")
    w("")

    # -- OBJECTS --
    w(f"# -- Item templates {BAR * 61}")
    w("OBJECTS = {")
    for vnum, obj in objs:
        cname = vnum
        w(f"    {cname}: {{")
        w(f'        "keywords":    {pyrepr(obj["keywords"])},')
        w(f'        "short_descr": {pyrepr(obj["short_descr"])},')
        w(f'        "description": {pyrepr(obj["description"])},')
        w(f'        "material":    {pyrepr(obj["material"])},')
        w(f'        "type": {pyrepr(obj["type"])},')
        w(f'        "wear_flags": {_repr_flags(obj["wear_flags"])},')
        if obj.get("no_sac"):
            w(f'        "no_sac": True,')
        if "condition" in obj:
            # cf. db2.c load_objects condition switch; absent = 100 (perfect)
            w(f'        "condition": {obj["condition"]},')
        if obj.get("extra_flags"):
            bits = decode_flags(obj["extra_flags"], EXTRA_FLAGS)
            if bits:
                w(f'        "extra_flags": {_repr_flags(bits)},')
        if obj["type"] == "weapon":
            wt = obj.get("weapon_type", "unknown")
            an = obj.get("dam_type", "hit")
            dc = obj.get("dice", (1, 1, 0))
            w(f'        "weapon_type": {pyrepr(wt)}, "dam_type": {pyrepr(an)}, "dice": {pyrepr(dc)},')
            wf = obj.get("weapon_flags", {})
            w(f'        "weapon_flags": {_repr_flags(wf)},')
        elif obj["type"] == "armor" and "armor" in obj:
            w(f'        "armor": {pyrepr(obj["armor"])},')
        elif obj["type"] in ("potion", "pill", "scroll"):
            if "spell_level" in obj:
                w(f'        "spell_level": {obj["spell_level"]},')
            if obj.get("spells"):
                w(f'        "spells": {pyrepr(obj["spells"])},')
        elif obj["type"] in ("wand", "staff"):
            if "spell_level" in obj:
                w(f'        "spell_level": {obj["spell_level"]},')
            if "max_charges" in obj:
                w(f'        "max_charges": {obj["max_charges"]}, "charges": {obj["charges"]},')
            if obj.get("spell"):
                w(f'        "spell": {pyrepr(obj["spell"])},')
        elif obj["type"] == "light":
            if "light_hours" in obj:
                w(f'        "light_hours": {obj["light_hours"]},')
        if obj.get("stat_bonuses"):
            w(f'        "stat_bonuses": {pyrepr(obj["stat_bonuses"])},')
        if obj.get("flag_affects"):
            # F-line flag-setting affects (cf. db2.c load_objects 'F' case).
            w(f'        "flag_affects": (')
            for where, loc_name, mod, bits in obj["flag_affects"]:
                w(f'            ({pyrepr(where)}, {pyrepr(loc_name)}, {mod}, {_repr_flags(bits)}),')
            w(f'        ),')
        w(f'        "level": {obj["level"]}, "weight": {obj["weight"]}, "value": {obj["value"]},')
        if obj["extra_descs"]:
            w(f'        "extra_descs": {pyrepr(obj["extra_descs"])},')
        w("    },")
    w("}")
    w("")

    # -- RESETS --
    w(f"# -- Resets {BAR * 69}")
    w('# ("M", mob_vnum, global_limit, room_vnum, room_limit) -- spawn mob up to limits')
    w('# ("O", item_vnum, room_vnum)                          -- place one item copy in room')
    w('# ("E", item_vnum, slot_name, limit)                   -- equip item on last M mob')
    w('# ("G", item_vnum, limit)                              -- give item to last M mob inventory')
    w('# E/G limit: raw 1stMud reset-count field (cf. db.c reset_room): a value')
    w('# > 50 is a legacy encoding meaning limit 6; -1 or 0 means unlimited (999).')
    w('# Runtime enforcement of this limit is deferred [PRIMESUD].')
    w('# ("P", item_vnum, limit, container_vnum, max)         -- [PRIMESUD] deferred: no containers')
    w('# ("R", room_vnum, num_dirs)                           -- [PRIMESUD] deferred: not enforced by runtime yet')
    w('# F and D .are resets are baked into room exit flags at conversion time')
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
        elif reset[0] == "E":
            _, iv, slot, limit = reset
            ic = r(iv, obj_map)
            w(f'    ("E", {ic}, "{slot}", {limit}),')
        elif reset[0] == "G":
            _, iv, limit = reset
            ic = r(iv, obj_map)
            w(f'    ("G", {ic}, {limit}),')
        elif reset[0] == "P":
            _, iv, lim, cv, mx = reset
            ic = r(iv, obj_map)
            cc = r(cv, obj_map)
            w(f'    ("P", {ic}, {lim}, {cc}, {mx}),')
        elif reset[0] == "R":
            _, rv, nd = reset
            rc = r(rv, room_map)
            w(f'    ("R", {rc}, {nd}),')
    w(")")
    w("")

    return "\n".join(out)


# -- Entry point ---------------------------------------------------------------

def convert(are_path, out_path=None):
    text  = Path(are_path).read_text(encoding="utf-8", errors="replace")
    sects = split_sections(text)

    area_data = parse_areadata(sects.get("AREADATA", []))
    rooms     = parse_rooms(sects.get("ROOMS", []))
    mobs      = parse_mobiles(sects.get("MOBILES", []), area_data.get("version"))
    objs      = parse_objects(sects.get("OBJECTS", []))
    resets, foverrides, doverrides = parse_resets(sects.get("RESETS", []))
    specials = parse_specials(sects.get("SPECIALS", []))

    room_map = make_const_map("R", rooms, lambda d: d["name"])
    mob_map  = make_const_map("M", mobs,  lambda d: d["keywords"])
    obj_map  = make_const_map("I", objs,  lambda d: d["keywords"])

    code = emit(area_data, rooms, mobs, objs, resets, specials, room_map, mob_map, obj_map,
                foverrides, doverrides)

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
