#!/usr/bin/env python3
"""Decode 1stMud races.dat positional Y/n flags into PrimeSUD RACE_TABLE dict."""

import sys

# Bit-position -> flag name mappings (None = unused bit)
# Derived from 1stMud bits.h BIT_A..BIT_fx definitions

ACT_BITS = [None] * 30
ACT_BITS[0]  = "npc"
ACT_BITS[1]  = "sentinel"
ACT_BITS[2]  = "scavenger"
ACT_BITS[5]  = "aggressive"
ACT_BITS[6]  = "stay_area"
ACT_BITS[7]  = "wimpy"
ACT_BITS[8]  = "pet"
ACT_BITS[9]  = "train"
ACT_BITS[10] = "practice"
ACT_BITS[14] = "undead"
ACT_BITS[16] = "cleric"
ACT_BITS[17] = "mage"
ACT_BITS[18] = "thief"
ACT_BITS[19] = "warrior"
ACT_BITS[20] = "noalign"
ACT_BITS[21] = "nopurge"
ACT_BITS[22] = "outdoors"
ACT_BITS[24] = "indoors"
ACT_BITS[26] = "healer"
ACT_BITS[27] = "gain"
ACT_BITS[28] = "update_always"
ACT_BITS[29] = "changer"

AFF_BITS = [None] * 33
AFF_BITS[0]  = "blind"
AFF_BITS[1]  = "invisible"
AFF_BITS[2]  = "detect_evil"
AFF_BITS[3]  = "detect_invis"
AFF_BITS[4]  = "detect_magic"
AFF_BITS[5]  = "detect_hidden"
AFF_BITS[6]  = "detect_good"
AFF_BITS[7]  = "sanctuary"
AFF_BITS[8]  = "faerie_fire"
AFF_BITS[9]  = "infrared"
AFF_BITS[10] = "curse"
# 11 = AFF_UNUSEd_FLAG (unused)
AFF_BITS[12] = "poison"
AFF_BITS[13] = "protect_evil"
AFF_BITS[14] = "protect_good"
AFF_BITS[15] = "sneak"
AFF_BITS[16] = "hide"
AFF_BITS[17] = "sleep"
AFF_BITS[18] = "charm"
AFF_BITS[19] = "flying"
AFF_BITS[20] = "pass_door"
AFF_BITS[21] = "haste"
AFF_BITS[22] = "calm"
AFF_BITS[23] = "plague"
AFF_BITS[24] = "weaken"
AFF_BITS[25] = "dark_vision"
AFF_BITS[26] = "berserk"
AFF_BITS[27] = "swim"
AFF_BITS[28] = "regeneration"
AFF_BITS[29] = "slow"
AFF_BITS[30] = "force_shield"
AFF_BITS[31] = "static_shield"
AFF_BITS[32] = "flame_shield"

OFF_BITS = [None] * 21
OFF_BITS[0]  = "area_attack"
OFF_BITS[1]  = "backstab"
OFF_BITS[2]  = "bash"
OFF_BITS[3]  = "berserk"
OFF_BITS[4]  = "disarm"
OFF_BITS[5]  = "dodge"
OFF_BITS[6]  = "fade"
OFF_BITS[7]  = "fast"
OFF_BITS[8]  = "kick"
OFF_BITS[9]  = "dirt_kick"
OFF_BITS[10] = "parry"
OFF_BITS[11] = "rescue"
OFF_BITS[12] = "tail"
OFF_BITS[13] = "trip"
OFF_BITS[14] = "crush"
OFF_BITS[15] = "assist_all"
OFF_BITS[16] = "assist_align"
OFF_BITS[17] = "assist_race"
OFF_BITS[18] = "assist_players"
OFF_BITS[19] = "assist_guard"
OFF_BITS[20] = "assist_vnum"

# IMM/RES/VULN all share the same bit layout
IRV_BITS = [None] * 26
IRV_BITS[0]  = "summon"
IRV_BITS[1]  = "charm"
IRV_BITS[2]  = "magic"
IRV_BITS[3]  = "weapon"
IRV_BITS[4]  = "bash"
IRV_BITS[5]  = "pierce"
IRV_BITS[6]  = "slash"
IRV_BITS[7]  = "fire"
IRV_BITS[8]  = "cold"
IRV_BITS[9]  = "lightning"
IRV_BITS[10] = "acid"
IRV_BITS[11] = "poison"
IRV_BITS[12] = "negative"
IRV_BITS[13] = "holy"
IRV_BITS[14] = "energy"
IRV_BITS[15] = "mental"
IRV_BITS[16] = "disease"
IRV_BITS[17] = "drowning"
IRV_BITS[18] = "light"
IRV_BITS[19] = "sound"
# 20-22 unused
IRV_BITS[23] = "wood"
IRV_BITS[24] = "silver"
IRV_BITS[25] = "iron"

FORM_BITS = [None] * 29
FORM_BITS[0]  = "edible"
FORM_BITS[1]  = "poison"
FORM_BITS[2]  = "magical"
FORM_BITS[3]  = "instant_decay"
FORM_BITS[4]  = "other"
# 5 unused
FORM_BITS[6]  = "animal"
FORM_BITS[7]  = "sentient"
FORM_BITS[8]  = "undead"
FORM_BITS[9]  = "construct"
FORM_BITS[10] = "mist"
FORM_BITS[11] = "intangible"
FORM_BITS[12] = "biped"
FORM_BITS[13] = "centaur"
FORM_BITS[14] = "insect"
FORM_BITS[15] = "spider"
FORM_BITS[16] = "crustacean"
FORM_BITS[17] = "worm"
FORM_BITS[18] = "blob"
# 19-20 unused
FORM_BITS[21] = "mammal"
FORM_BITS[22] = "bird"
FORM_BITS[23] = "reptile"
FORM_BITS[24] = "snake"
FORM_BITS[25] = "dragon"
FORM_BITS[26] = "amphibian"
FORM_BITS[27] = "fish"
FORM_BITS[28] = "cold_blood"

PART_BITS = [None] * 25
PART_BITS[0]  = "head"
PART_BITS[1]  = "arms"
PART_BITS[2]  = "legs"
PART_BITS[3]  = "heart"
PART_BITS[4]  = "brains"
PART_BITS[5]  = "guts"
PART_BITS[6]  = "hands"
PART_BITS[7]  = "feet"
PART_BITS[8]  = "fingers"
PART_BITS[9]  = "ear"
PART_BITS[10] = "eye"
PART_BITS[11] = "long_tongue"
PART_BITS[12] = "eyestalks"
PART_BITS[13] = "tentacles"
PART_BITS[14] = "fins"
PART_BITS[15] = "wings"
PART_BITS[16] = "tail"
# 17-19 unused
PART_BITS[20] = "claws"
PART_BITS[21] = "fangs"
PART_BITS[22] = "horns"
PART_BITS[23] = "scales"
PART_BITS[24] = "tusks"


def decode_flags(yn_str, bit_table):
    """Decode '+YnnY...' positional flag string into {name: True} dict."""
    if not yn_str or yn_str == "+n":
        return {}
    s = yn_str.lstrip("+-")
    result = {}
    for i, ch in enumerate(s):
        if ch == 'Y' and i < len(bit_table) and bit_table[i] is not None:
            result[bit_table[i]] = True
        elif ch == 'Y' and (i >= len(bit_table) or bit_table[i] is None):
            print(f"  WARNING: Y at position {i} has no flag name", file=sys.stderr)
    return result


def parse_races(filepath):
    """Parse races.dat and return list of race dicts."""
    races = []
    current = None

    with open(filepath, 'r') as f:
        for line in f:
            line = line.rstrip('\n\r')
            stripped = line.strip()

            if stripped == '#RACE':
                current = {}
                continue
            if stripped == '#END':
                if current:
                    races.append(current)
                current = None
                continue
            if stripped == '#!' or not stripped:
                continue
            if current is None:
                continue

            parts = line.split('\t')
            parts = [p for p in parts if p]
            if len(parts) < 2:
                continue

            key = parts[0].strip()
            val = parts[-1].strip()

            if key == 'name':
                current['name'] = val.rstrip('~')
            elif key == 'pc_race':
                current['pc_race'] = val == 'true'
            elif key == 'act':
                current['act'] = val
            elif key == 'aff':
                current['aff'] = val
            elif key == 'off':
                current['off'] = val
            elif key == 'imm':
                current['imm'] = val
            elif key == 'res':
                current['res'] = val
            elif key == 'vuln':
                current['vuln'] = val
            elif key == 'form':
                current['form'] = val
            elif key == 'parts':
                current['parts'] = val
            elif key == 'points':
                current['points'] = int(val)
            elif key == 'size':
                current['size'] = val.rstrip('~')
            elif key == 'stats':
                nums = [int(x) for x in val.replace('@', '').split() if x]
                current['stats'] = nums
            elif key == 'max_stats':
                nums = [int(x) for x in val.replace('@', '').split() if x]
                current['max_stats'] = nums
            elif key == 'class_mult':
                nums = [int(x) for x in val.replace('@', '').split() if x]
                current['class_mult'] = nums
            elif key == 'skills':
                sk = [s.rstrip('~') for s in val.split('~') if s.strip() and s.strip() != '@']
                # Filter out the trailing @~ markers
                sk = [s.strip() for s in sk if s.strip() and s.strip() != '@']
                current['skills'] = sk

    return races


def fmt_dict(d, indent=8):
    """Format a dict as Python source."""
    if not d:
        return "{}"
    prefix = " " * indent
    items = ['"%s": True' % k for k in sorted(d)]
    if len(items) <= 3:
        return "{" + ", ".join(items) + "}"
    lines = ["{"]
    for item in items:
        lines.append(prefix + "    " + item + ",")
    lines.append(prefix + "}")
    return "\n".join(lines)


def fmt_list(lst):
    """Format a list of ints."""
    return "(" + ", ".join(str(x) for x in lst) + ")"


def main():
    filepath = sys.argv[1] if len(sys.argv) > 1 else "reference/1stMud4.5.3/data/races.dat"
    races = parse_races(filepath)

    stat_names = ("str", "int", "wis", "dex", "con")

    print('# fmt: off')
    print('"""Race table data decoded from 1stMud races.dat (cf. 1stMud race_table in data_table.c).')
    print('')
    print('Each entry maps race name -> race defaults dict.  Flag dicts use the')
    print('same {flag_name: True} convention as PrimeSUD area mob templates.')
    print('')
    print('Bit-position decoding derived from 1stMud bits.h BIT_A..BIT_fx defines')
    print('cross-referenced with tables.c flag table arrays."""')
    print('')
    print('')
    print('RACE_TABLE = {')

    for race in races:
        name = race['name']
        print(f'    "{name}": {{')
        print(f'        "pc_race": {race["pc_race"]},')

        act  = decode_flags(race.get('act', '+n'), ACT_BITS)
        aff  = decode_flags(race.get('aff', '+n'), AFF_BITS)
        off  = decode_flags(race.get('off', '+n'), OFF_BITS)
        imm  = decode_flags(race.get('imm', '+n'), IRV_BITS)
        res  = decode_flags(race.get('res', '+n'), IRV_BITS)
        vuln = decode_flags(race.get('vuln', '+n'), IRV_BITS)
        form = decode_flags(race.get('form', '+n'), FORM_BITS)
        parts = decode_flags(race.get('parts', '+n'), PART_BITS)

        print(f'        "act":  {fmt_dict(act, 8)},')
        print(f'        "aff":  {fmt_dict(aff, 8)},')
        print(f'        "off":  {fmt_dict(off, 8)},')
        print(f'        "imm":  {fmt_dict(imm, 8)},')
        print(f'        "res":  {fmt_dict(res, 8)},')
        print(f'        "vuln": {fmt_dict(vuln, 8)},')
        print(f'        "form":  {fmt_dict(form, 8)},')
        print(f'        "parts": {fmt_dict(parts, 8)},')

        stats = race.get('stats', [13, 13, 13, 13, 13])
        max_stats = race.get('max_stats', [18, 18, 18, 18, 18])
        # 1stMud stat order: str, int, wis, dex, con
        print(f'        "stats":     {fmt_list(stats)},')
        print(f'        "max_stats": {fmt_list(max_stats)},')

        print(f'        "size": "{race.get("size", "medium")}",')

        # class_mult and skills only for pc_race
        if race['pc_race']:
            cm = race.get('class_mult', [100]*6)
            print(f'        "class_mult": {fmt_list(cm)},  # [not ported] chargen creation points')
            print(f'        "points": {race.get("points", 0)},  # [not ported] chargen creation points')
            sk = race.get('skills', [])
            if sk:
                print(f'        "skills": {sk},  # [not ported] racial skills/groups')
            else:
                print(f'        "skills": [],')

        print('    },')

    print('}')
    print('')
    print('')
    print('def race_lookup(name):')
    print('    """Look up a race by name (case-insensitive prefix match, cf. 1stMud race_lookup).')
    print('')
    print('    Args:')
    print('        name (str): Race name or prefix.')
    print('')
    print('    Returns:')
    print('        dict or None: Race data dict, or None if no match.')
    print('    """')
    print('    if not name:')
    print('        return None')
    print('    nl = name.lower()')
    print('    # Exact match first')
    print('    for rn, rd in RACE_TABLE.items():')
    print('        if rn.lower() == nl:')
    print('            return rd')
    print('    # Prefix match')
    print('    for rn, rd in RACE_TABLE.items():')
    print('        if rn.lower().startswith(nl):')
    print('            return rd')
    print('    return None')


if __name__ == '__main__':
    main()
