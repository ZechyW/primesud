#!/usr/bin/env python3
"""Convert a QuickMUD/ROM 2.4 .are file to a PrimeSUD Python area module.

Usage:
    python are_to_primesud.py school.are area_school.txt

QuickMUD uses standard ROM 2.4 area format which differs from 1stMud:
  - Flag encoding: letter-based (A=bit0, B=bit1 ... Z=bit25, a=bit26 ...)
    instead of 1stMud's +YnnYn bitstrings
  - #AREA header: old-style (filename~ name~ credits~ min_vnum max_vnum)
    instead of #AREADATA key-value
  - Mob line layout: level hitroll on one line (no random/autoset fields)
  - Mob AC: stored as-is (ROM code multiplies by 10 at load time);
    we store raw .are values and note the x10 for PrimeSUD runtime
  - Room exit locks: enum 0-4 instead of bitstring flags
  - Room exits have a key vnum field
  - Resets: slightly different field layout (limit fields differ)

Ground truth for all db.c/db2.c line references in this file: QuickMUD's
C sources, formerly at reference/quickmud/src/ (removed from the tree to
avoid confusion with the similarly-named 1stMud sources; recover via git
history, commit f74****, or reference/quickmud/rom24-quickmud-master.zip).

Sections handled:   #AREA  #ROOMS  #MOBILES  #OBJECTS  #RESETS  #SPECIALS
                    #SHOPS  #HELPS  #SOCIALS  #MOBPROGS
Anything else -- including #AREADATA and legacy #MOBOLD/#OBJOLD -- is a
hard conversion error, mirroring QuickMUD boot_db's bug()+exit(1).

#SPECIALS and #SHOPS are not emitted as standalone sections: each entry is
baked directly into its target mob's MOBILES dict at conversion time
("spec_fun" / "shop" keys) [PRIMESUD]. Verified across all stock QuickMUD
areas that specials/shops never reference a mob outside their own file, so
this is safe; a mob vnum that isn't found in this file's MOBILES raises a
hard error rather than emitting a fallback section.
"""

import re
import sys
from pathlib import Path


# -- Flag tables (same bit positions as ROM 2.4 / 1stMud) ---------------------

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
# Bits 4/5/20/21/22 are 1stMud extensions (no ROM_* define in QuickMUD's
# merc.h). PrimeSUD's runtime is 1stMud-ported, so 1stMud semantics are
# canonical; QuickMUD stock areas never set these bits (verified across all
# shipped areas), so decoding them is unambiguous. [PRIMESUD]
ROOM_FLAGS = {
    0: "dark", 2: "no_mob", 3: "indoors", 4: "arena", 5: "bank",
    9: "private", 10: "safe", 11: "solitary", 12: "pet_shop",
    13: "no_recall", 14: "imp_only", 15: "gods_only", 16: "heroes_only",
    17: "newbies_only", 18: "law", 19: "nowhere",
    20: "noexplore", 21: "noautomap", 22: "save_objs",
}
# cf. merc.h SECT_* (SECT_MAX 11); entries 11-16 previously here don't exist
# in this QuickMUD and have been removed.
SECTOR_NAMES = {
    0: "inside",  1: "city",    2: "field",  3: "forest",
    4: "hills",   5: "mountain", 6: "swim",  7: "noswim",
    8: "unused",  9: "air",    10: "desert",
}
# Bits 17 ("auctioned") and 26 ("quest") are 1stMud extensions (no ITEM_*
# define in QuickMUD's merc.h). PrimeSUD's runtime is 1stMud-ported and
# quest.py/shop.py/inventory.py/magic.py gate on "quest", so 1stMud
# semantics are canonical; QuickMUD stock areas never set these bits
# (verified across all shipped areas). [PRIMESUD]
EXTRA_FLAGS = {
    0: "glow",        1: "hum",          2: "dark",        3: "lock",
    4: "evil",        5: "invis",        6: "magic",       7: "nodrop",
    8: "bless",       9: "anti_good",   10: "anti_evil",  11: "anti_neutral",
   12: "noremove",   13: "inventory",   14: "nopurge",    15: "rot_death",
   16: "vis_death",  17: "auctioned",  18: "nonmetal",   19: "nolocate",
   20: "melt_drop",  21: "had_timer",   22: "sell_extract",
   24: "burn_proof", 25: "nouncurse",  26: "quest",
}
WEAR_SLOT = {
    1: "finger", 2: "neck", 3: "body", 4: "head", 5: "legs",
    6: "feet", 7: "hands", 8: "arms", 9: "shield", 10: "about",
    11: "waist", 12: "wrist", 13: "wield", 14: "hold", 16: "float",
}
APPLY_LOC = {
    1: "str", 2: "dex", 3: "int", 4: "wis", 5: "con",
    6: "sex", 7: "class", 8: "level", 9: "age", 10: "height", 11: "weight",
    12: "mana", 13: "hit", 14: "move", 15: "gold", 16: "exp",
    17: "ac", 18: "hitroll", 19: "damroll",
    20: "saves", 21: "saving_rod", 22: "saving_petri",
    23: "saving_breath", 24: "saving_spell", 25: "spell_affect",
}
FORM_FLAGS = {
    0: "edible", 1: "poison", 2: "magical", 3: "instant_decay", 4: "other",
    6: "animal", 7: "sentient", 8: "undead", 9: "construct", 10: "mist",
    11: "intangible", 12: "biped", 13: "centaur", 14: "insect", 15: "spider",
    16: "crustacean", 17: "worm", 18: "blob", 21: "mammal", 22: "bird",
    23: "reptile", 24: "snake", 25: "dragon", 26: "amphibian", 27: "fish",
    28: "cold_blood",
}
PART_FLAGS = {
    0: "head", 1: "arms", 2: "legs", 3: "heart", 4: "brains", 5: "guts",
    6: "hands", 7: "feet", 8: "fingers", 9: "ear", 10: "eye",
    11: "long_tongue", 12: "eyestalks", 13: "tentacles", 14: "fins",
    15: "wings", 16: "tail", 20: "claws", 21: "fangs", 22: "horns",
    23: "scales", 24: "tusks",
}
CONTAINER_FLAGS = {
    0: "closeable", 1: "pickproof", 2: "closed", 3: "locked", 4: "put_on",
}
# Object condition letter (cf. db2.c load_objects condition switch); missing
# or unrecognized letter defaults to 100 (perfect condition).
OBJ_CONDITION = {
    "P": 100, "G": 90, "A": 75, "W": 50, "D": 25, "B": 10, "R": 0,
}
DIR_NAME = {0: "n", 1: "e", 2: "s", 3: "w", 4: "u", 5: "d"}
ITEM_TYPE_NUM = {
    1: "light", 2: "scroll", 3: "wand", 4: "staff", 5: "weapon",
    8: "treasure", 9: "armor", 10: "potion", 11: "clothing",
    12: "furniture", 13: "trash", 15: "container", 17: "drink",
    18: "key", 19: "food", 20: "money", 22: "boat",
    23: "npc_corpse", 24: "pc_corpse", 25: "fountain", 26: "pill",
    27: "protect", 28: "map", 29: "portal", 30: "warp_stone",
    31: "room_key", 32: "gem", 33: "jewelry", 34: "jukebox",
}
# Valid mobprog trigger type words (cf. tables.c mprog_flags; db2.c
# exit(1)s on a word flag_lookup doesn't find).
MPROG_TRIGGERS = {
    "act", "bribe", "death", "entry", "fight", "give", "greet", "grall",
    "kill", "hpcnt", "random", "speech", "exit", "exall", "delay", "surr",
}
WLOC_SLOT = {
    0:  "light",
    1:  "finger_l", 2:  "finger_r",
    3:  "neck_1",   4:  "neck_2",
    5:  "body",     6:  "head",    7:  "legs",  8: "feet",
    9:  "hands",    10: "arms",    11: "shield", 12: "about",
    13: "waist",    14: "wrist_l", 15: "wrist_r",
    16: "wield",    17: "hold",    18: "float",
}


# -- ROM flag parser -----------------------------------------------------------

def rom_flag_convert(letter):
    """Convert a single ROM flag letter to its bit value (cf. flag_convert in db.c)."""
    if 'A' <= letter <= 'Z':
        return 1 << (ord(letter) - ord('A'))
    elif 'a' <= letter <= 'z':
        return 1 << (26 + ord(letter) - ord('a'))
    return 0


def parse_rom_flag(s):
    """Parse a ROM flag field: letter sequence like 'ABV', plain number, or number|number.

    Mirrors db.c fread_flag/flag_convert exactly (db.c:2743-2809): letters
    accumulate flag_convert(c) into a single running `number`; if a digit
    follows directly (no separating '|'), it does NOT start a fresh value --
    it continues the SAME accumulator via number = number*10 + digit for each
    consecutive digit. E.g. "AB12" -> letters A=1,B=2 give number=3, then
    digit '1' -> 3*10+1=31, digit '2' -> 31*10+2=312 (NOT 3+12=15). A
    trailing '|' recurses: number += fread_flag(rest-of-field).

    Returns integer bitmask.
    """
    s = s.strip()
    if not s:
        return 0

    negative = False
    if s.startswith('-'):
        negative = True
        s = s[1:]

    number = 0
    i = 0
    n = len(s)
    if i < n and not s[i].isdigit():
        while i < n and (('A' <= s[i] <= 'Z') or ('a' <= s[i] <= 'z')):
            number += rom_flag_convert(s[i])
            i += 1
    while i < n and s[i].isdigit():
        number = number * 10 + int(s[i])
        i += 1
    if i < n and s[i] == '|':
        number += parse_rom_flag(s[i + 1:])

    return -number if negative else number


def flag_bits(flag_int):
    """Integer bitmask -> set of bit positions."""
    bits = set()
    n = flag_int
    pos = 0
    while n > 0:
        if n & 1:
            bits.add(pos)
        n >>= 1
        pos += 1
    return bits


def decode_flags(bits, table, skip=None):
    """Bit-position set + table -> {name: True} dict."""
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
    """Split a value line respecting single-quoted tokens (may contain spaces)."""
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
    """'NdM+B' or 'NdM-B' -> (N, M, B).

    Engine quirk (cf. db2.c:250-269, e.g. hit-dice read): fread_letter(fp) is
    called unchecked to consume the '+'/'-' separator, then fread_number(fp)
    reads the bonus digits alone (the sign was already eaten by the
    separator read). So real QuickMUD can NEVER load a negative dice bonus
    -- "2d6-3" loads in-engine as +3, not -3. We keep the faithful sign here
    since no stock .are file actually uses a negative bonus; flagging this
    for awareness only, not changing behavior. [PRIMESUD]
    """
    m = re.match(r"(\d+)d(\d+)([+-]\d+)?", s)
    if m:
        n, d, b = m.groups()
        return (int(n), int(d), int(b) if b else 0)
    return (1, 1, 0)


# -- Low-level .are reader -----------------------------------------------------

def read_tilde_string(lines, i):
    """Read a ~-terminated string from lines[i:]. Returns (text, next_i).

    The blanket .strip() below is an intentional PrimeSUD normalization: ROM's
    fread_string preserves leading/trailing blank lines verbatim, but
    PrimeSUD's display layer manages its own spacing.
    """
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
    ROM's "O Saska~" owner line: fread_string(fp) skips whitespace -- which
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
    """Split .are text into {SECTION_NAME: [lines]} dict.

    Handles both '#SECTION' and old-style '#AREA' (which has no trailing newline
    before data).

    Note: rstrip() drops trailing whitespace on every line, including inside
    description text. Intentional normalization -- trailing spaces are
    render-invisible in the game and the few stock-area occurrences are
    accidental. Accepted deviation from byte-exact fidelity.
    """
    sections = {}
    current = None
    buf = []
    for raw in text.splitlines():
        line = raw.rstrip()
        # QuickMUD's section dispatch uses case-insensitive str_cmp
        # (db.c boot_db); match headers case-insensitively and store the
        # key upper-cased so lookups elsewhere stay uniform. [PRIMESUD]
        if line.startswith("#") and re.match(r"#[A-Za-z]+$", line):
            if current is not None:
                sections[current] = buf
            current = line[1:].upper()
            buf = []
        elif line == "#$":
            if current is not None:
                sections[current] = buf
            break
        else:
            if current is not None:
                buf.append(line)
    if current is not None and current not in sections:
        sections[current] = buf
    return sections


# -- Section parsers -----------------------------------------------------------

def parse_area_old(lines):
    """Parse old-style #AREA header: filename~ name~ credits~ min_vnum max_vnum."""
    area = {}
    i = 0
    if i < len(lines):
        filename, i = read_tilde_string(lines, i)
        area["filename"] = filename
    if i < len(lines):
        name, i = read_tilde_string(lines, i)
        area["name"] = name
    if i < len(lines):
        credits, i = read_tilde_string(lines, i)
        area["credits"] = credits
        m = re.match(r"\{\s*(\d+)\s+(\d+)\s*\}", credits)
        if m:
            area["min_level"] = int(m.group(1))
            area["max_level"] = int(m.group(2))
        elif "All" in credits:
            area["min_level"] = 1
            area["max_level"] = 50
    if i < len(lines):
        vn = lines[i].split()
        if len(vn) < 2:
            raise ValueError(
                "area vnum-range line has fewer than 2 tokens: " + repr(lines[i])
            )
        try:
            area["vnums"] = (int(vn[0]), int(vn[1]))
        except ValueError:
            area["vnums"] = (0, 0)
    if "name" not in area:
        area["name"] = "Unknown"
    if "vnums" not in area:
        area["vnums"] = (0, 0)
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
        # Preserve source spelling/case; runtime uses race_lookup().

        # act_flags  affected_by  alignment  group
        parts = lines[i].split(); i += 1
        act_int = parse_rom_flag(parts[0]) if parts else 0
        aff_int = parse_rom_flag(parts[1]) if len(parts) > 1 else 0
        alignment = int(parts[2]) if len(parts) > 2 else 0
        group = int(parts[3]) if len(parts) > 3 else 0

        # level  hitroll  hp_dice  mana_dice  dam_dice  dam_type  (all one line in ROM)
        parts = lines[i].split(); i += 1
        level   = int(parts[0]) if parts else 0
        hitroll = int(parts[1]) if len(parts) > 1 else 0
        hp_dice   = parse_dice(parts[2]) if len(parts) > 2 else (1, 1, 0)
        mana_dice = parse_dice(parts[3]) if len(parts) > 3 else (1, 1, 0)
        dam_dice  = parse_dice(parts[4]) if len(parts) > 4 else (1, 1, 0)
        dam_type  = parts[5].strip("'") if len(parts) > 5 else "hit"

        # ac_pierce  ac_bash  ac_slash  ac_exotic
        # ROM stores raw then does *10 at load; we store raw
        parts = lines[i].split(); i += 1
        armor = tuple(int(x) for x in parts[:4])

        # off_flags  imm_flags  res_flags  vuln_flags
        parts = lines[i].split(); i += 1
        off_int  = parse_rom_flag(parts[0]) if parts else 0
        imm_int  = parse_rom_flag(parts[1]) if len(parts) > 1 else 0
        res_int  = parse_rom_flag(parts[2]) if len(parts) > 2 else 0
        vuln_int = parse_rom_flag(parts[3]) if len(parts) > 3 else 0

        # start_pos  default_pos  sex  wealth
        parts = lines[i].split(); i += 1
        start_pos   = parts[0] if parts else "standing"
        default_pos = parts[1] if len(parts) > 1 else "standing"
        sex    = parts[2] if len(parts) > 2 else "neutral"
        wealth = int(parts[3]) if len(parts) > 3 else 0

        # form_flags  part_flags  size  material
        parts = lines[i].split(); i += 1
        form_int = parse_rom_flag(parts[0]) if parts else 0
        part_int = parse_rom_flag(parts[1]) if len(parts) > 1 else 0
        size     = parts[2] if len(parts) > 2 else "medium"
        material = parts[3] if len(parts) > 3 else ""

        # optional trailer lines: F (flag remove) or M (mobprog trigger)
        # F lines REMOVE bits inherited from race table (cf. db2.c:307-335)
        f_removes = []
        mob_triggers = []
        while i < len(lines):
            tline = lines[i].strip()
            if tline.startswith("#") or tline == "":
                break
            if tline and tline[0] == "F":
                # db2.c:307-313 reads word/vector via whitespace-skipping
                # freads, so the payload may spill onto the next line(s)
                # (mirrors the OBJECTS 'F' trailer handling below).
                fparts = tline.split()
                while len(fparts) < 3 and i + 1 < len(lines) and lines[i + 1].strip():
                    i += 1
                    fparts += lines[i].split()
                if len(fparts) < 3:
                    raise ValueError(
                        "mob trailer 'F' line incomplete (need field + flag-vector): " +
                        repr(tline)
                    )
                f_field = fparts[1]
                f_vector = parse_rom_flag(fparts[2])
                f_removes.append((f_field, f_vector))
                i += 1
            elif tline and tline[0] == "M":
                # M <trig_type> <mprog_vnum> <trig_phrase>~
                # db2.c:337-355: fread_word + fread_number + fread_string,
                # all whitespace-skipping -- type/vnum may spill onto later
                # lines and the phrase is a full multi-line tilde string.
                mparts = tline.split(None, 3)
                while len(mparts) < 3 and i + 1 < len(lines) and lines[i + 1].strip():
                    i += 1
                    mparts = " ".join(mparts + [lines[i]]).split(None, 3)
                if len(mparts) < 3:
                    raise ValueError(
                        "mob trailer 'M' line incomplete (need trig_type + "
                        "mprog vnum + phrase): " + repr(tline)
                    )
                trig_type = mparts[1].lower()
                if trig_type not in MPROG_TRIGGERS:
                    # cf. db2.c: flag_lookup(word, mprog_flags) == NO_FLAG
                    # -> bug ("MOBprogs: invalid trigger.", 0); exit (1);
                    raise ValueError(
                        "mob trailer 'M' has invalid trigger type " +
                        repr(mparts[1])
                    )
                mprog_vnum = int(mparts[2])
                phrase_start = mparts[3] if len(mparts) > 3 else ""
                trig_phrase, i = read_tilde_string_inline(
                    phrase_start, lines, i + 1)
                mob_triggers.append((trig_type, mprog_vnum, trig_phrase))
            else:
                break

        # Apply F-line flag removals (cf. db2.c REMOVE_BIT, db2.c:307-335).
        # F_PREFIX_MAP: file field-word prefix -> (canonical mob.py race key,
        # decode table for that field's bits).
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
        flag_removes_acc = {}  # canonical field -> (table, combined bit vector)
        for f_field, f_vector in f_removes:
            # db2.c:315-334 matches with !str_prefix(word, canonical), i.e.
            # the FILE's word must be a prefix of the canonical field name
            # ("vu" matches "vul"; "actz" does NOT match "act"), compared
            # case-insensitively (str_prefix LOWERs both sides). [PRIMESUD
            # note: the converter previously had this inverted.]
            f_field_lower = f_field.lower()
            matched = False
            if f_field_lower:
                for prefix, (canon, table) in F_PREFIX_MAP.items():
                    if prefix.startswith(f_field_lower):
                        # Mutate the file-level int (still correct for race-merge
                        # independent bits set directly on this mob's own flags).
                        if prefix == "act":  act_int  &= ~f_vector
                        elif prefix == "aff": aff_int &= ~f_vector
                        elif prefix == "off": off_int &= ~f_vector
                        elif prefix == "imm": imm_int &= ~f_vector
                        elif prefix == "res": res_int &= ~f_vector
                        elif prefix == "vul": vuln_int &= ~f_vector
                        elif prefix == "for": form_int &= ~f_vector
                        elif prefix == "par": part_int &= ~f_vector
                        # Also record the removal itself so the runtime race-merge
                        # (mob.py create_mobile) can subtract race-granted bits
                        # that this mob's F line strips off (cf. db2.c: race bits
                        # OR'd in at load time, then F lines REMOVE_BIT).
                        prev_vec = flag_removes_acc.get(canon, (table, 0))[1]
                        flag_removes_acc[canon] = (table, prev_vec | f_vector)
                        matched = True
                        break
            if not matched:
                # cf. db2.c:331-334: falls to `else { bug(...); exit(1); }`
                # when no field-word prefix matches. [PRIMESUD]
                raise ValueError(
                    "mob trailer 'F' field word " + repr(f_field) +
                    " does not match any of act/aff/off/imm/res/vul/for/par"
                )

        flag_removes = []
        for canon, (table, vector) in flag_removes_acc.items():
            names = tuple(table.get(pos, pos) for pos in sorted(flag_bits(vector)))
            flag_removes.append((canon, names))

        mob = {
            "keywords":    keywords,
            "short_descr": short_descr,
            "long_descr":  long_descr,
            "description": description,
            "race":        race,
            "act_flags":   decode_flags(flag_bits(act_int), ACT_FLAGS, skip={0}),
            "affected_by": decode_flags(flag_bits(aff_int), AFFECTED_BY),
            "alignment":   alignment,
            "group":       group,
            "level":       level,
            "hitroll":     hitroll,
            "hp_dice":     hp_dice,
            "mana_dice":   mana_dice,
            "damage":      dam_dice,
            "dam_type":    dam_type,
            "armor":       armor,
            "off_flags":   decode_flags(flag_bits(off_int), OFF_FLAGS),
            "imm_flags":   decode_flags(flag_bits(imm_int), RESIST_FLAGS),
            "res_flags":   decode_flags(flag_bits(res_int), RESIST_FLAGS),
            "vuln_flags":  decode_flags(flag_bits(vuln_int), RESIST_FLAGS),
            "start_pos":   start_pos,
            "default_pos": default_pos,
            "form_flags":  decode_flags(flag_bits(form_int), FORM_FLAGS),
            "part_flags":  decode_flags(flag_bits(part_int), PART_FLAGS),
            "material":    material,
            "sex":         sex,
            "wealth":      wealth,
            "size":        size,
            "mob_triggers": mob_triggers,
        }
        if f_removes:
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
        item_type = parts[0] if parts else "unknown"
        extra_int = parse_rom_flag(parts[1]) if len(parts) > 1 else 0
        wear_int  = parse_rom_flag(parts[2]) if len(parts) > 2 else 0

        # item-type-specific value line
        val_line = split_tokens(lines[i]); i += 1

        # level  weight  cost  condition_letter
        lw_line = lines[i].split(); i += 1
        level  = int(lw_line[0]) if lw_line else 0
        weight = int(lw_line[1]) if len(lw_line) > 1 else 0
        cost   = int(lw_line[2]) if len(lw_line) > 2 else 0
        cond_letter = lw_line[3] if len(lw_line) > 3 else ""
        condition = OBJ_CONDITION.get(cond_letter, 100)

        # optional A / E / F trailer lines
        applies      = {}
        extra_descs  = []
        flag_affects = []
        while i < len(lines):
            tline = lines[i].strip()
            if tline.startswith("#"):
                break
            if tline and tline[0] == "A":
                # db2.c:519-534 reads loc/mod via two whitespace-skipping
                # fread_number calls, so the payload may spill onto the
                # next line(s) just like the 'F' trailer below. Previously
                # a single-line split wrapped in a bare except swallowed
                # both malformed applies AND desynced the line pointer.
                aparts = tline.split()
                while len(aparts) < 3 and i + 1 < len(lines) and lines[i + 1].strip():
                    i += 1
                    aparts += lines[i].split()
                if len(aparts) < 3:
                    raise ValueError(
                        "object trailer 'A' line incomplete (need loc + modifier): " +
                        repr(tline)
                    )
                loc, mod = int(aparts[1]), int(aparts[2])
                if loc in APPLY_LOC:
                    applies[APPLY_LOC[loc]] = mod
                i += 1
            elif tline == "E":
                i += 1
                ekw,  i = read_tilde_string(lines, i)
                edesc, i = read_tilde_string(lines, i)
                extra_descs.append((ekw, edesc))
            elif tline and tline[0] == "F":
                # F lines on objects add flag-setting affects (cf. db2.c:536-569)
                # Format: F <where_letter> <apply_loc> <modifier> <bitvector>
                # db2.c reads each token with whitespace-skipping freads, so
                # the payload may follow on the next line(s) (e.g. shire.are
                # #1105) instead of sharing the F line.
                fparts = tline.split()
                while len(fparts) < 5 and i + 1 < len(lines) and lines[i + 1].strip():
                    i += 1
                    fparts += lines[i].split()
                if len(fparts) < 5:
                    # db2.c reads all four payload tokens unconditionally --
                    # a short F trailer means the file is malformed.
                    raise ValueError(
                        "object trailer 'F' line incomplete (need where + "
                        "loc + modifier + bitvector): " + repr(tline)
                    )
                where_map = {"A": "affects", "I": "immune", "R": "resist", "V": "vuln"}
                where = where_map.get(fparts[1])
                if where is None:
                    # cf. db2.c:556-559: `default: bug ("Load_objects: Bad
                    # where on flag set.", 0); exit (1);`
                    raise ValueError(
                        "object trailer 'F' has bad where-letter " +
                        repr(fparts[1]) + " (expected A/I/R/V)"
                    )
                loc = int(fparts[2])
                mod = int(fparts[3])
                bv = parse_rom_flag(fparts[4])
                loc_name = APPLY_LOC.get(loc, str(loc))
                bit_table = AFFECTED_BY if where == "affects" else RESIST_FLAGS
                bits = decode_flags(flag_bits(bv), bit_table)
                flag_affects.append((where, loc_name, mod, bits))
                i += 1
            elif tline == "":
                i += 1
            else:
                break

        wear_bits = flag_bits(wear_int)
        wear_flags = {}
        no_sac = 15 in wear_bits
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
            "extra_flags": flag_bits(extra_int),
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
            wf_int = parse_rom_flag(val_line[4]) if len(val_line) > 4 else 0
            obj["weapon_flags"] = decode_flags(flag_bits(wf_int), {
                0: "flaming", 1: "frost", 2: "vampiric", 3: "sharp",
                4: "vorpal", 5: "two_hands", 6: "shocking", 7: "poison",
            })
        elif item_type == "armor" and val_line:
            # db2.c's switch has no ITEM_ARMOR case, so it falls to the
            # `default:` branch: all 4 (of 5) value[] slots used here are
            # read via fread_flag, not fread_number -- letter forms are
            # legal. Previously read with bare int() + a try/except that
            # masked a field desync from earlier misparse by defaulting to
            # a fixed quartet; every other numeric field fails loud, so
            # this one should too.
            obj["armor"] = (
                parse_rom_flag(val_line[0]),
                parse_rom_flag(val_line[1]) if len(val_line) > 1 else 0,
                parse_rom_flag(val_line[2]) if len(val_line) > 2 else 0,
                parse_rom_flag(val_line[3]) if len(val_line) > 3 else 0,
            )
        elif item_type in ("potion", "pill", "scroll") and val_line:
            obj["spell_level"] = int(val_line[0])
            obj["spells"] = [s for s in val_line[1:] if s]
        elif item_type in ("wand", "staff") and val_line:
            # db2.c ITEM_WAND/ITEM_STAFF: value[0]/[1]/[2] (spell_level,
            # max_charges, charges) are read via fread_number, not
            # fread_flag -- these stay plain int().
            obj["spell_level"] = int(val_line[0])
            obj["max_charges"] = int(val_line[1]) if len(val_line) > 1 else 0
            obj["charges"] = int(val_line[2]) if len(val_line) > 2 else 0
            obj["spell"] = val_line[3] if len(val_line) > 3 and val_line[3] else ""
        elif item_type == "light" and val_line:
            # No ITEM_LIGHT case in db2.c's switch either -- `default:`
            # branch, value[2] (hours) read via fread_flag.
            # value[2]: hours of light (cf. db2.c load_objects / act_obj.c);
            # raw int, ROM/1stMud 0/999 conventions differ -- stored as-is.
            obj["light_hours"] = parse_rom_flag(val_line[2]) if len(val_line) > 2 else 0
        elif item_type == "container" and val_line:
            obj["container_max_weight"] = int(val_line[0]) if val_line else 0
            container_flags = parse_rom_flag(val_line[1]) if len(val_line) > 1 else 0
            obj["container_flags"] = container_flags
            obj["container_key"] = int(val_line[2]) if len(val_line) > 2 else 0
            # value[3]/value[4] (cf. db2.c load_objects ITEM_CONTAINER case +
            # merc.h WEIGHT_MULT). Old-format containers predating these
            # fields have no tokens here; ROM's struct default (0-init /
            # zeroed value[]) would read as 0, but WEIGHT_MULT() falls back
            # to 100 when the field is unset, so we mirror that default here.
            obj["container_max_item_weight"] = int(val_line[3]) if len(val_line) > 3 else 0
            obj["container_weight_mult"] = int(val_line[4]) if len(val_line) > 4 else 100
        elif item_type in ("drink", "fountain") and val_line:
            obj["liquid_total"] = int(val_line[0]) if val_line else 0
            obj["liquid_left"]  = int(val_line[1]) if len(val_line) > 1 else 0
            obj["liquid_type"]  = val_line[2] if len(val_line) > 2 else "water"
            # value[3] (cf. act_obj.c do_drink: nonzero -> poisoned); ROM's
            # ITEM_DRINK_CON/ITEM_FOUNTAIN case reads value[3] via
            # fread_number, so this stays plain int().
            if len(val_line) > 3 and int(val_line[3]) != 0:
                obj["poisoned"] = True
        elif item_type == "food" and val_line:
            # No ITEM_FOOD case in db2.c's switch -- `default:` branch,
            # all values read via fread_flag.
            obj["food_hours"]   = parse_rom_flag(val_line[0]) if val_line else 0
            obj["food_hunger"]  = parse_rom_flag(val_line[1]) if len(val_line) > 1 else 0
            # value[3] (cf. act_obj.c do_eat: nonzero -> poisoned; NOT value[2])
            if len(val_line) > 3 and parse_rom_flag(val_line[3]) != 0:
                obj["poisoned"] = True
        elif item_type == "money" and val_line:
            # No ITEM_MONEY case in db2.c's switch -- `default:` branch,
            # all values read via fread_flag.
            obj["silver"] = parse_rom_flag(val_line[0]) if val_line else 0
            obj["gold"]   = parse_rom_flag(val_line[1]) if len(val_line) > 1 else 0
        elif val_line:
            # [PRIMESUD] Fallback for every item type not special-cased
            # above (furniture, portal, jukebox, map, warp_stone, key,
            # treasure, clothing, trash, boat, gem, jewelry, npc_corpse,
            # pc_corpse, protect, room_key): db2.c's `default:` branch
            # reads all 5 value[] slots via fread_flag (db2.c:471-477), and
            # the engine consumes them (e.g. furniture occupancy in
            # act_move.c:1016-1030). Omitted from output when all-zero to
            # keep shipped data lean; runtime should read via
            # obj.get("values", (0, 0, 0, 0, 0)).
            values = tuple(
                parse_rom_flag(val_line[j]) if j < len(val_line) else 0
                for j in range(5)
            )
            if any(values):
                obj["values"] = values

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

        # area_num  room_flags  sector_type
        flag_parts = lines[i].split(); i += 1
        room_int = parse_rom_flag(flag_parts[1]) if len(flag_parts) > 1 else 0
        if len(flag_parts) > 2:
            sector_int = int(flag_parts[2])
            # Unknown/negative sector (upstream data typos, e.g. sewer
            # #7426 "-1") falls back to inside
            sector = SECTOR_NAMES.get(sector_int, "inside")
        else:
            sector = None

        exits      = {}
        exit_notes = {}
        exit_descs = {}
        extra_descs = []
        heal_rate  = None
        mana_rate  = None
        room_flags = decode_flags(flag_bits(room_int), ROOM_FLAGS)
        # "Horrible hack" (db.c load_rooms): any room in [3000, 3400) is
        # forced ROOM_LAW regardless of its stored flags.
        if 3000 <= vnum < 3400:
            room_flags["law"] = True
        clan  = ""
        owner = ""

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
                # ROM exit format: locks key to_room
                ex_parts = lines[i].split(); i += 1
                locks   = int(ex_parts[0]) if ex_parts else 0
                ex_key  = int(ex_parts[1]) if len(ex_parts) > 1 else -1
                to_room = int(ex_parts[2]) if len(ex_parts) > 2 else -1
                if direction in DIR_NAME:
                    d = DIR_NAME[direction]
                    # to_room <= 0: ROM keeps the exit as examinable but
                    # untraversable (fix_exits only nulls the destination
                    # pointer); preserved as "to": None.
                    exits[d] = to_room if to_room > 0 else None
                    # ROM lock types: 0=open, 1=door, 2=door+pickproof,
                    #                 3=door+nopass, 4=door+nopass+pickproof.
                    # db.c load_rooms only has cases 1-4 in its switch;
                    # anything else falls through with exit_info left at 0
                    # (no door), so values outside 0-4 are treated as 0 here.
                    ex_flags = {}
                    if locks in (1, 2, 3, 4):
                        ex_flags["isdoor"] = True
                        if locks == 2:
                            ex_flags["pickproof"] = True
                        elif locks == 3:
                            ex_flags["nopass"] = True
                        elif locks == 4:
                            ex_flags["pickproof"] = True
                            ex_flags["nopass"] = True
                    elif locks != 0:
                        print(
                            "warning: room " + str(vnum) + " exit " +
                            DIR_NAME.get(direction, str(direction)) +
                            ": unrecognized lock value " + str(locks) +
                            " (db.c load_rooms only handles 1-4); treating as no door",
                            file=sys.stderr,
                        )
                    if ex_key > 0:
                        ex_flags["key"] = ex_key
                    if ex_flags:
                        exit_notes[d] = ex_flags
                    if ex_desc:
                        exit_descs[d] = ex_desc
                    if ex_keyword:
                        exit_notes.setdefault(d, {})["keyword"] = ex_keyword
                else:
                    # cf. db.c load_rooms: "if (door < 0 || door > 5) { bug
                    # (...); exit (1); }" -- fail loud rather than silently
                    # dropping the whole exit block.
                    raise ValueError(
                        "room " + str(vnum) + " has D-exit with direction " +
                        str(direction) + " outside 0-5"
                    )
            elif tline == "E":
                i += 1
                ekw, i = read_tilde_string(lines, i)
                edesc, i = read_tilde_string(lines, i)
                extra_descs.append((ekw, edesc))
            elif tline[0:2] in ("H ", "M "):
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
                # clan: 'C' letter, then a tilde string that may continue on
                # the same line (cf. db.c load_rooms:
                # clan_lookup(fread_string(fp)))
                clan, i = read_tilde_string_inline(tline[1:], lines, i + 1)
            elif tline[0] == "O":
                # owner: 'O' letter, then a tilde string that may continue on
                # the same line (cf. db.c load_rooms: fread_string(fp))
                owner, i = read_tilde_string_inline(tline[1:], lines, i + 1)
            else:
                # cf. db.c load_rooms: "bug (...vnum %d has flag not
                # 'DES'...); exit (1);" -- fail loud on any unrecognized
                # non-blank trailer line rather than silently eating it.
                raise ValueError(
                    "room " + str(vnum) +
                    " has trailer letter not DESHMCO: " + repr(tline)
                )

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
        if clan:
            room["clan"] = clan
        if owner:
            room["owner"] = owner
        rooms.append((vnum, room))
    return rooms


def parse_resets(lines):
    """Parse #RESETS section (ROM format).

    ROM reset fields (after command letter):
        M  if_flag  mob_vnum  global_limit  room_vnum  room_limit
        O  if_flag  obj_vnum  limit         room_vnum
        E  if_flag  obj_vnum  limit         wloc
        G  if_flag  obj_vnum  limit
        P  if_flag  obj_vnum  limit         container_vnum  max_count
        D  if_flag  room_vnum dir           locks
        R  if_flag  room_vnum num_dirs

    D resets are baked into exit flags at conversion time.
    """
    resets = []
    doverrides = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped[0] == '*':
            continue
        parts = stripped.split()
        cmd = parts[0]
        if cmd == "S":
            break
        if cmd == "M" and len(parts) >= 6:
            resets.append(("M", int(parts[2]), int(parts[3]), int(parts[4]), int(parts[5])))
        elif cmd == "O" and len(parts) >= 5:
            resets.append(("O", int(parts[2]), int(parts[4])))
        elif cmd == "E" and len(parts) >= 5:
            slot = WLOC_SLOT.get(int(parts[4]), "hold")
            limit = int(parts[3])
            resets.append(("E", int(parts[2]), slot, limit))
        elif cmd == "G" and len(parts) >= 4:
            # cmd if_flag arg1(obj_vnum) arg2(limit) -- db.c load_resets
            # reads if_flag/arg1/arg2 unconditionally for every command
            # letter (arg3/arg4 are skipped for 'G'), so 4 tokens minimum.
            resets.append(("G", int(parts[2]), int(parts[3])))
        elif cmd == "P" and len(parts) >= 6:
            resets.append(("P", int(parts[2]), int(parts[3]), int(parts[4]), int(parts[5])))
        elif cmd == "R" and len(parts) >= 4:
            resets.append(("R", int(parts[2]), int(parts[3])))
        elif cmd == "D" and len(parts) >= 5:
            d = DIR_NAME.get(int(parts[3]))
            if d is None:
                # cf. db.c fix_exits 'D' case: get_room_index/pexit NULL
                # checks end in bug()+exit(1) for a bogus direction.
                raise ValueError(
                    "RESETS 'D' line has direction " + repr(parts[3]) +
                    " outside 0-5: " + repr(stripped)
                )
            doverrides[(int(parts[2]), d)] = int(parts[4])
        else:
            raise ValueError(
                "RESETS: unrecognized command letter " + repr(cmd) +
                " or too few fields: " + repr(stripped)
            )
    return resets, doverrides


def parse_specials(lines):
    """Parse #SPECIALS section (cf. db.c load_specials:1344-1376).

    Raises ValueError on any unrecognized command letter or malformed 'M'
    line -- db.c's `default: bug(...); exit(1);` has no silent fallback.
    """
    specials = []
    for line in lines:
        parts = line.split()
        if not parts or parts[0] == "*":
            continue
        cmd = parts[0]
        if cmd == "S":
            break
        if cmd != "M":
            raise ValueError(
                "SPECIALS: unrecognized command letter " + repr(cmd) +
                " (expected 'M', '*', or 'S')"
            )
        if len(parts) < 3:
            raise ValueError(
                "SPECIALS 'M' line malformed (need vnum + spec_name): " + repr(line)
            )
        specials.append(("M", int(parts[1]), parts[2]))
    return specials


def parse_shops(lines):
    """Parse #SHOPS section.

    Each line: keeper_vnum  buy_type[0..4]  profit_buy  profit_sell  open_hour  close_hour
    Terminated by keeper_vnum == 0.
    (cf. QuickMUD load_shops in db.c)
    """
    shops = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped[0] == '*':
            continue
        parts = stripped.split()
        if not parts:
            continue
        keeper = int(parts[0])
        if keeper == 0:
            break
        buy_types = []
        for j in range(1, 6):
            bt = int(parts[j]) if len(parts) > j else 0
            if bt != 0:
                buy_types.append(ITEM_TYPE_NUM.get(bt, str(bt)))
        profit_buy  = int(parts[6]) if len(parts) > 6 else 100
        profit_sell = int(parts[7]) if len(parts) > 7 else 100
        open_hour   = int(parts[8]) if len(parts) > 8 else 0
        close_hour  = int(parts[9]) if len(parts) > 9 else 23
        shops.append({
            "keeper":      keeper,
            "buy_types":   buy_types,
            "profit_buy":  profit_buy,
            "profit_sell": profit_sell,
            "open_hour":   open_hour,
            "close_hour":  close_hour,
        })
    return shops


def parse_helps(lines):
    """Parse #HELPS section.

    Each entry: level  keyword~  text~
    Terminated by keyword starting with '$'.
    (cf. QuickMUD load_helps in db.c)
    """
    helps = []
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped:
            i += 1
            continue
        parts = stripped.split(None, 1)
        if not parts:
            i += 1
            continue
        try:
            level = int(parts[0])
        except ValueError:
            # cf. db.c load_helps: level = fread_number(fp), which exit(1)s
            # on a non-numeric token -- fail loud instead of skipping.
            raise ValueError("HELPS entry has non-integer level: " + repr(stripped))
        rest = parts[1] if len(parts) > 1 else ""
        tilde = rest.find("~")
        if tilde >= 0:
            keyword = rest[:tilde].strip()
            i += 1
        else:
            keyword_parts = [rest]
            i += 1
            while i < len(lines):
                idx = lines[i].find("~")
                if idx >= 0:
                    keyword_parts.append(lines[i][:idx])
                    i += 1
                    break
                keyword_parts.append(lines[i])
                i += 1
            keyword = " ".join(keyword_parts).strip()

        if keyword.startswith("$"):
            break

        text, i = read_tilde_string(lines, i)
        helps.append({
            "level":   level,
            "keyword": keyword,
            "text":    text,
        })
    return helps


def parse_socials(lines):
    """Parse #SOCIALS section.

    Each social: name [min_pos char_pos]
    Then up to 8 message lines (fread_string_eol each):
      char_no_arg, others_no_arg, char_found, others_found,
      vict_found, char_not_found, char_auto, others_auto
    '$' = NULL for that field, '#' = end-of-social (remaining fields NULL).
    Terminated by '#0'.
    (cf. QuickMUD load_socials in db2.c)
    """
    socials = []
    i = 0
    fields = ("char_no_arg", "others_no_arg", "char_found", "others_found",
              "vict_found", "char_not_found", "char_auto", "others_auto")
    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped:
            i += 1
            continue
        if stripped == "#0":
            break
        name_parts = stripped.split()
        name = name_parts[0]
        i += 1

        social = {"name": name}
        for field in fields:
            # fread_string_eol skips leading whitespace INCLUDING newlines
            # (db.c:2950-2954 do/while isspace(c)), so a blank line inside
            # a social block is transparent to ROM -- it must not shift
            # the remaining fields. Blank line BETWEEN socials is handled
            # by the loop-top check above and is unaffected by this.
            while i < len(lines) and not lines[i].strip():
                i += 1
            if i >= len(lines):
                break
            val = lines[i].strip()
            i += 1
            if val == "$":
                social[field] = None
            elif val == "#":
                break
            else:
                social[field] = val

        socials.append(social)
    return socials


def parse_mobprogs(lines):
    """Parse #MOBPROGS section.

    Each entry: #vnum  code~
    Terminated by #0.
    (cf. QuickMUD load_mobprogs in db.c)
    """
    progs = []
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
        code, i = read_tilde_string(lines, i)
        progs.append((vnum, code))
    return progs


# -- Python emitter (matches are_to_primesud.py output exactly) ----------------

def _repr_flags(d):
    if not d:
        return "{}"
    parts = [f'"{k}": True' for k in d if k != "_unknown_bits"]
    if "_unknown_bits" in d:
        parts.append(f'"_unknown_bits": {pyrepr(d["_unknown_bits"])}')
    return "{" + ", ".join(parts) + "}"


def pyrepr(value):
    return ascii(value)


def asciitext(value):
    return str(value).encode("ascii", "backslashreplace").decode("ascii")


def emit(area_data, rooms, mobs, objs, resets, helps, socials,
         mobprogs, doverrides=None):
    out = []

    def w(s=""):
        out.append(s)

    aname    = area_data.get("name", "Unknown")
    vnums    = area_data.get("vnums", (0, 0))
    min_lvl  = area_data.get("min_level", 1)
    max_lvl  = area_data.get("max_level", 60)
    credits  = area_data.get("credits", "Unknown")

    w("# fmt: off")
    w(f"# Area: {asciitext(aname)}")
    w(f"# Source: QuickMUD/ROM 2.4")
    w(f"# VNUM ranges: {vnums[0]}-{vnums[1]}")
    w(f"# Credits: {asciitext(credits)}")
    w("")
    w("")
    w("AREA = {")
    w(f'    "name":     {pyrepr(aname)},')
    # QuickMUD load_area hardcodes builders="None" for old-style areas
    # (the raw credits text is preserved separately under "credits").
    w(f'    "builders": {pyrepr("None")},')
    w(f'    "vnums":    {pyrepr(vnums)},')
    w(f'    "credits":  {pyrepr(credits)},')
    # [PRIMESUD] heuristic parsed from the credits text; ROM derives no
    # level range for old-style areas.
    w(f'    "levels":   ({min_lvl}, {max_lvl}),')
    w("}")
    w("")

    BAR = "-"

    # -- MOBILES --
    w(f"# -- Mob templates {BAR * 62}")
    w("# hp_dice / mana_dice / damage: (num_dice, die_size, bonus)")
    w("# armor: (pierce, bash, slash, exotic), raw .are units")
    w("# hitroll: from mob level line")
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
            # (cf. mob.py create_mobile; QuickMUD db2.c REMOVE_BIT).
            w(f'        "flag_removes": (')
            for canon, names in mob["flag_removes"]:
                w(f'            ({pyrepr(canon)}, {pyrepr(names)}),')
            w(f'        ),')
        if mob.get("spec_fun"):
            # [PRIMESUD] baked from this file's #SPECIALS section at
            # conversion time (formerly a standalone SPECIALS tuple merged
            # into MOB_DEFS by world.py at load time).
            w(f'        "spec_fun": {pyrepr(mob["spec_fun"])},')
        if mob.get("shop"):
            # [PRIMESUD] baked from this file's #SHOPS section at conversion
            # time (formerly a standalone SHOPS tuple merged into MOB_DEFS
            # by world.py at load time). Dict shape matches exactly what
            # world.py used to assign to MOB_DEFS[keeper]["shop"], including
            # the redundant "keeper" key.
            shop = mob["shop"]
            bt = pyrepr(shop["buy_types"]) if shop["buy_types"] else "[]"
            w(f'        "shop": {{"keeper": {shop["keeper"]}, "buy_types": {bt},'
              f' "profit_buy": {shop["profit_buy"]}, "profit_sell": {shop["profit_sell"]},'
              f' "open_hour": {shop["open_hour"]}, "close_hour": {shop["close_hour"]}}},')
        w("    },")
    w("}")
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
            # "to": None = examinable-but-untraversable exit (ROM keeps
            # exits whose to_room fails to resolve; fix_exits nulls only
            # the destination pointer).
            to_c    = "None" if to_vnum is None else str(to_vnum)
            note    = room["exit_notes"].get(d) or {}
            # D override sets closed/locked state
            dstate = (doverrides or {}).get((vnum, d))
            if dstate is not None and note.get("isdoor"):
                note = dict(note)
                # cf. db.c load_resets 'D' switch: case 0 = no change,
                # case 1 = SET closed, case 2 = SET closed+locked; anything
                # else hits `default: bug(...)` and leaves state unchanged.
                if dstate == 0:
                    note.pop("closed", None)
                    note.pop("locked", None)
                elif dstate == 1:
                    note["closed"] = True
                    note.pop("locked", None)
                elif dstate == 2:
                    note["closed"] = True
                    note["locked"] = True
                else:
                    print(
                        "warning: room " + str(vnum) + " exit " + str(d) +
                        ": D-reset lock value " + str(dstate) +
                        " unrecognized (db.c load_resets 'D' bug()); exit state left unchanged",
                        file=sys.stderr,
                    )
            ex_desc = room.get("exit_descs", {}).get(d, "")
            if note or ex_desc or to_vnum is None:
                eparts = [f'"to": {to_c}']
                if ex_desc:
                    eparts.append(f'"desc": {pyrepr(ex_desc)}')
                if note.get("keyword"):
                    eparts.append(f'"keyword": {pyrepr(note["keyword"])}')
                for flag in ("isdoor", "closed", "locked", "pickproof", "nopass",
                             "easy", "hard", "infuriating", "noclose", "nolock"):
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
        if room["heal_rate"] is not None:
            w(f'        "heal_rate": {room["heal_rate"]},')
        if room["mana_rate"] is not None:
            w(f'        "mana_rate": {room["mana_rate"]},')
        if room.get("extra_descs"):
            w(f'        "extra_descs": {pyrepr(room["extra_descs"])},')
        if room.get("clan"):
            w(f'        "clan": {pyrepr(room["clan"])},')
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
            if "spell" in obj:
                w(f'        "spell": {pyrepr(obj["spell"])},')
        elif obj["type"] == "light":
            if "light_hours" in obj:
                w(f'        "light_hours": {obj["light_hours"]},')
        elif obj["type"] == "container":
            if "container_max_weight" in obj:
                w(f'        "container_max_weight": {obj["container_max_weight"]},')
            if "container_flags" in obj:
                cf = decode_flags(flag_bits(obj["container_flags"]), CONTAINER_FLAGS)
                w(f'        "container_flags": {_repr_flags(cf)},')
            if obj.get("container_key", 0) > 0:
                w(f'        "container_key": {obj["container_key"]},')
            if "container_max_item_weight" in obj:
                # value[3]/value[4] (cf. db2.c load_objects + merc.h
                # WEIGHT_MULT); old-format containers lack these tokens --
                # default max_item_weight to 0, weight_mult to 100 (ROM's
                # WEIGHT_MULT() fallback for non-container/unset value[4]).
                w(f'        "container_max_item_weight": {obj["container_max_item_weight"]},')
                w(f'        "container_weight_mult": {obj["container_weight_mult"]},')
        elif obj["type"] in ("drink", "fountain"):
            if "liquid_total" in obj:
                w(f'        "liquid_total": {obj["liquid_total"]}, "liquid_left": {obj["liquid_left"]},')
                w(f'        "liquid_type": {pyrepr(obj.get("liquid_type", "water"))},')
            if obj.get("poisoned"):
                w(f'        "poisoned": True,')
        elif obj["type"] == "food":
            if "food_hours" in obj:
                w(f'        "food_hours": {obj["food_hours"]}, "food_hunger": {obj["food_hunger"]},')
            if obj.get("poisoned"):
                w(f'        "poisoned": True,')
        elif obj["type"] == "money":
            if "silver" in obj:
                w(f'        "silver": {obj["silver"]}, "gold": {obj["gold"]},')
        elif "values" in obj:
            # [PRIMESUD] raw value[0..4] fallback for item types not
            # otherwise special-cased above; see parse_objects.
            w(f'        "values": {pyrepr(obj["values"])},')
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
    w('# E/G limit: raw ROM reset-count field (cf. db.c reset_room): a value')
    w('# > 50 is a legacy encoding meaning limit 6; -1 (or 0, for E/G specifically)')
    w('# means unlimited. Runtime enforcement of this limit is deferred [PRIMESUD].')
    w('# ("P", item_vnum, limit, container_vnum, max)         -- [PRIMESUD] deferred: no containers')
    w('# ("R", room_vnum, num_dirs)                           -- [PRIMESUD] deferred: not enforced by runtime yet')
    w('# D resets are baked into room exit flags at conversion time')
    w("RESETS = (")
    for reset in resets:
        if reset[0] == "M":
            _, mv, gl, rv, rl = reset
            mc = str(mv)
            rc = str(rv)
            w(f'    ("M", {mc}, {gl}, {rc}, {rl}),')
        elif reset[0] == "O":
            _, ov, rv = reset
            oc = str(ov)
            rc = str(rv)
            w(f'    ("O", {oc}, {rc}),')
        elif reset[0] == "E":
            _, iv, slot, limit = reset
            ic = str(iv)
            w(f'    ("E", {ic}, "{slot}", {limit}),')
        elif reset[0] == "G":
            _, iv, limit = reset
            ic = str(iv)
            w(f'    ("G", {ic}, {limit}),')
        elif reset[0] == "P":
            _, iv, lim, cv, mx = reset
            ic = str(iv)
            cc = str(cv)
            w(f'    ("P", {ic}, {lim}, {cc}, {mx}),')
        elif reset[0] == "R":
            _, rv, nd = reset
            rc = str(rv)
            w(f'    ("R", {rc}, {nd}),')
    w(")")
    w("")

    # -- HELPS --
    w(f"# -- Helps {BAR * 69}")
    w("HELPS = (")
    for h in helps:
        w(f'    {{"level": {h["level"]}, "keyword": {pyrepr(h["keyword"])},')
        w(f'     "text": {pyrepr(h["text"])}}},')
    w(")")
    w("")

    # -- SOCIALS --
    w(f"# -- Socials {BAR * 67}")
    w("SOCIALS = (")
    for soc in socials:
        parts = [f'"name": {pyrepr(soc["name"])}']
        for field in ("char_no_arg", "others_no_arg", "char_found", "others_found",
                      "vict_found", "char_not_found", "char_auto", "others_auto"):
            val = soc.get(field)
            if val is not None:
                parts.append(f'"{field}": {pyrepr(val)}')
        w(f'    {{{", ".join(parts)}}},')
    w(")")
    w("")

    # -- MOBPROGS --
    w(f"# -- MobProgs {BAR * 66}")
    w('# (vnum, code) -- mob program code blocks, referenced by mob triggers')
    w("MOBPROGS = {")
    for mpv, code in mobprogs:
        w(f'    {mpv}: {pyrepr(code)},')
    w("}")
    w("")

    return "\n".join(out)


# -- Entry point ---------------------------------------------------------------

# Section names this converter (and QuickMUD's boot_db) recognizes.
KNOWN_SECTIONS = {
    "AREA", "ROOMS", "MOBILES", "OBJECTS", "RESETS", "SPECIALS",
    "SHOPS", "HELPS", "SOCIALS", "MOBPROGS",
}


def check_known_sections(sects):
    """Raise ValueError naming any section this converter doesn't handle.

    cf. db.c boot_db:359-406, which exit(1)s on an unrecognized section
    name via `bug ("Boot_db: bad section name.", 0); exit (1);`.
    """
    for name in sects:
        if name in KNOWN_SECTIONS:
            continue
        if name == "AREADATA":
            raise ValueError(
                "#AREADATA: new-style area header not supported; convert to "
                "old-style #AREA 4-line header"
            )
        if name in ("MOBOLD", "OBJOLD"):
            new_name = "MOBILES" if name == "MOBOLD" else "OBJECTS"
            raise ValueError(
                "#" + name + ": legacy pre-ROM-2.4 format not supported; "
                "convert to new-format #" + new_name
            )
        raise ValueError("unknown section #" + name)


def load_spec_names():
    """Read src/special.py's SPEC_TABLE keys: the implemented spec_fun names.

    [PRIMESUD] cf. db.c load_specials 'M' case / spec_lookup(): QuickMUD
    treats an unrecognized spec_fun name as a hard bug()+exit(1) at boot
    time. The converter has no such runtime check, so an unimplemented name
    would otherwise silently produce a mob with no AI; we mirror QuickMUD's
    fail-loud behavior here instead.
    """
    special_path = Path(__file__).resolve().parent.parent / "src" / "special.py"
    text = special_path.read_text(encoding="utf-8")
    names = set(re.findall(r'"(spec_\w+)"\s*:', text))
    if not names:
        raise ValueError("could not find any SPEC_TABLE entries in " + str(special_path))
    return names


def convert(are_path, out_path=None):
    text  = Path(are_path).read_text(encoding="utf-8", errors="replace")
    sects = split_sections(text)
    check_known_sections(sects)

    area_data = parse_area_old(sects.get("AREA", []))
    rooms     = parse_rooms(sects.get("ROOMS", []))
    mobs      = parse_mobiles(sects.get("MOBILES", []))
    objs      = parse_objects(sects.get("OBJECTS", []))
    resets, doverrides = parse_resets(sects.get("RESETS", []))
    specials  = parse_specials(sects.get("SPECIALS", []))
    shops     = parse_shops(sects.get("SHOPS", []))
    helps     = parse_helps(sects.get("HELPS", []))
    socials   = parse_socials(sects.get("SOCIALS", []))
    mobprogs  = parse_mobprogs(sects.get("MOBPROGS", []))

    # [PRIMESUD] Bake #SPECIALS and #SHOPS entries directly into their target
    # mob's MOBILES dict ("spec_fun" / "shop" keys) instead of emitting them
    # as standalone SPECIALS/SHOPS sections merged at runtime by world.py.
    # Verified across all stock QuickMUD areas: specials/shops never
    # reference a mob vnum outside their own file. A vnum that isn't found
    # here is a hard error rather than a silently dropped fallback section.
    mobs_by_vnum = dict(mobs)
    spec_lookup = None
    if specials:
        # ROM's spec_lookup() matches case-insensitively (str_cmp); bake the
        # canonical SPEC_TABLE spelling into the output regardless of the
        # case used in the .are file. [PRIMESUD]
        spec_lookup = {name.lower(): name for name in load_spec_names()}
    for special in specials:
        if special[0] != "M":
            continue
        _, mv, spec_name = special
        if mv not in mobs_by_vnum:
            raise ValueError(
                "SPECIALS entry (\"M\", " + str(mv) + ", " + repr(spec_name) +
                ") references mob vnum " + str(mv) +
                " not present in this file's MOBILES section"
            )
        canonical = spec_lookup.get(spec_name.lower())
        if canonical is None:
            raise ValueError(
                "SPECIALS entry (\"M\", " + str(mv) + ", " + repr(spec_name) +
                ") is not an implemented spec_fun (see src/special.py SPEC_TABLE)"
            )
        mobs_by_vnum[mv]["spec_fun"] = canonical
    for shop in shops:
        keeper = shop["keeper"]
        if keeper not in mobs_by_vnum:
            raise ValueError(
                "SHOPS entry references keeper vnum " + str(keeper) +
                " not present in this file's MOBILES section"
            )
        mobs_by_vnum[keeper]["shop"] = shop

    code = emit(area_data, rooms, mobs, objs, resets, helps, socials,
                mobprogs, doverrides)

    if out_path:
        Path(out_path).write_text(code, encoding="utf-8", newline="\n")
        print(f"Written to {out_path}", file=sys.stderr)
    else:
        sys.stdout.write(code)
    return code


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <input.are> [output.py]", file=sys.stderr)
        sys.exit(1)
    convert(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
