#!/usr/bin/env python3
"""Convert 1stMud 4.5.x skills.dat to a PrimeSUD Python skills module.

Usage:
    uv run python skills_to_primesud.py skills.dat skills_table.py

Output module exports:
    GSN_*              -- named integer constants for skills that have a gsn_* pgsn
    _SKILL_TABLE_RAW   -- list of (sn, dict) in load order; raw per-class tuples
    SKILL_TABLE        -- alias of _SKILL_TABLE_RAW (per-class tuples preserved;
                          class-aware lookups live in classes.py)
    SKILLS             -- dict keyed by sn (same data as SKILL_TABLE)
    WEAPON_GSN_MAP     -- maps weapon_type string -> GSN constant

Fields emitted per raw entry (faithful to source data):
    name           -- canonical skill/spell name
    skill_level    -- 6-tuple (Mage Cleric Thief Warrior Paladin Ranger); 53=unavailable
    rating         -- 6-tuple train cost / difficulty; 0=unavailable to that class
    spell_fun      -- spell function name string (spell_null -> passive skill)
    target         -- target type string (ignore / char_offensive / char_defensive / ...)
    min_pos        -- minimum position string (standing / fighting / resting / ...)
    pgsn           -- gsn variable name (gsn_null -> no named reference)
    min_mana       -- int; minimum mana cost floor for spells
    beats          -- int; lag in pulses after use (12 = one combat round)
    noun_damage    -- string; noun used in damage messages (empty for non-damaging skills)
    msg_off        -- string; message when affect expires (empty if none)
    msg_obj        -- string; room message when object affect expires (empty if none)

_SKILL_TABLE_RAW indices map directly to the 1stMud sn values documented in SKILLS.md.
"""

import sys
from pathlib import Path

# -- GSN name -> constant identifier -------------------------------------------

def gsn_to_const(gsn_name):
    """'gsn_shield_block' -> 'GSN_SHIELD_BLOCK'."""
    if gsn_name == "gsn_null":
        return None
    return gsn_name.upper()


# -- Parser --------------------------------------------------------------------

def parse_int_array(rest):
    """'53 53 53 53 53 53 @' -> (53, 53, 53, 53, 53, 53)."""
    tokens = rest.split()
    return tuple(int(t) for t in tokens if t != "@")


def parse_string(rest):
    """'acid blast~' -> 'acid blast'."""
    idx = rest.find("~")
    return rest[:idx].strip() if idx >= 0 else rest.strip()


def parse_skills(text):
    """Parse full skills.dat text. Returns list of dicts in load order."""
    skills = []
    for block in text.split("#SKILL")[1:]:
        block = block[:block.find("#END")]
        entry = {}
        for raw in block.splitlines():
            line = raw.strip()
            if not line:
                continue
            parts = line.split(None, 1)
            key = parts[0]
            rest = parts[1].strip() if len(parts) > 1 else ""

            if key == "name":
                entry["name"] = parse_string(rest)
            elif key == "skill_level":
                entry["skill_level"] = parse_int_array(rest)
            elif key == "rating":
                entry["rating"] = parse_int_array(rest)
            elif key == "spell_fun":
                entry["spell_fun"] = parse_string(rest)
            elif key == "target":
                entry["target"] = parse_string(rest)
            elif key == "minimum_position":
                entry["min_pos"] = parse_string(rest)
            elif key == "pgsn":
                entry["pgsn"] = parse_string(rest)
            elif key == "min_mana":
                entry["min_mana"] = int(rest)
            elif key == "beats":
                entry["beats"] = int(rest)
            elif key == "noun_damage":
                entry["noun_damage"] = parse_string(rest)
            elif key == "msg_off":
                entry["msg_off"] = parse_string(rest)
            elif key == "msg_obj":
                entry["msg_obj"] = parse_string(rest)
            # flags / sound: OLC-only / MSP -- not present in reference data; skip

        if entry.get("name") is not None:
            skills.append(entry)

    return skills


# -- Emitter -------------------------------------------------------------------

def emit(skills):
    out = []

    def w(s=""):
        out.append(s)

    w("# fmt: off")
    w('"""Global skill table data converted from 1stMud."""')
    w("")
    w("# Generated from 1stMud 4.5.3 skills.dat -- do not edit manually.")
    w("# Re-generate: uv run python tools/skills_to_primesud.py reference/1stMud4.5.3/data/skills.dat")
    w("")
    w("# skill_level / rating indices:  0=Mage  1=Cleric  2=Thief  3=Warrior  4=Paladin  5=Ranger")
    w("# skill_level 53 = ANGEL (not available to that class)  52 = LEVEL_IMMORTAL (immo-only)")
    w("# rating 0 = class cannot learn this skill individually")
    w("")

    BAR = "-"

    # -- GSN constants --
    # gsn_str_to_const: 'gsn_sword' -> 'GSN_SWORD' for use in pgsn field values
    gsn_entries = [(sn, sk) for sn, sk in enumerate(skills) if sk.get("pgsn") != "gsn_null"]
    gsn_str_to_const = {sk["pgsn"]: gsn_to_const(sk["pgsn"]) for _, sk in gsn_entries}
    w(f"# -- GSN constants {BAR * 62}")
    for sn, sk in gsn_entries:
        const = gsn_to_const(sk["pgsn"])
        if const:
            w(f"{const:<30} = {sn}")
    w("")

    # -- _SKILL_TABLE_RAW --
    w(f"# -- _SKILL_TABLE_RAW {BAR * 59}")
    w("_SKILL_TABLE_RAW = [")
    for sn, sk in enumerate(skills):
        gsn_const = gsn_to_const(sk.get("pgsn", "gsn_null"))
        sn_comment = f"  # sn {sn}"
        if gsn_const:
            sn_comment += f"  {gsn_const}"
        w(f"    ({sn:3d}, {{  #{sn_comment[3:]}")
        w(f'        "name":        {sk["name"]!r},')
        w(f'        "skill_level": {sk["skill_level"]!r},')
        w(f'        "rating":      {sk["rating"]!r},')
        w(f'        "spell_fun":   {sk["spell_fun"]!r},')
        w(f'        "target":      {sk["target"]!r},')
        w(f'        "min_pos":     {sk["min_pos"]!r},')
        pgsn_val = gsn_str_to_const.get(sk.get("pgsn", "gsn_null"), "None")
        w(f'        "pgsn":        {pgsn_val},')
        w(f'        "min_mana":    {sk["min_mana"]},')
        w(f'        "beats":       {sk["beats"]},')
        w(f'        "noun_damage": {sk["noun_damage"]!r},')
        w(f'        "msg_off":     {sk["msg_off"]!r},')
        w(f'        "msg_obj":     {sk["msg_obj"]!r},')
        w("    }),")
    w("]")
    w("")

    # -- Derived lookups (cf. 1stMud skill_table + weapon_table in const.c) --
    w(f"# -- Derived lookups {BAR * 59}")
    w("# skill_level / rating stay per-class tuples; class-aware lookups live in")
    w("# classes.py (skill_level / skill_rating, cf. 1stMud multiclass.c).")
    w("SKILL_TABLE = _SKILL_TABLE_RAW")
    w("")
    w("SKILLS = dict(SKILL_TABLE)")
    w("")
    # Weapon GSN map -- uses GSN constants emitted above
    weapon_types = [
        ("sword",   "GSN_SWORD"),
        ("axe",     "GSN_AXE"),
        ("dagger",  "GSN_DAGGER"),
        ("flail",   "GSN_FLAIL"),
        ("mace",    "GSN_MACE"),
        ("polearm", "GSN_POLEARM"),
        ("spear",   "GSN_SPEAR"),
        ("whip",    "GSN_WHIP"),
    ]
    w("# Maps item weapon_type string -> GSN (cf. 1stMud weapon_table in const.c).")
    w("WEAPON_GSN_MAP = {")
    for wtype, gsn in weapon_types:
        w(f'    {wtype!r:10s}: {gsn},')
    w("}")
    w("")

    return "\n".join(out)


# -- Entry point ---------------------------------------------------------------

def convert(dat_path, out_path=None):
    text = Path(dat_path).read_text(encoding="latin-1")
    skills = parse_skills(text)
    print(f"Parsed {len(skills)} skills.", file=sys.stderr)
    code = emit(skills)
    if out_path:
        Path(out_path).write_text(code, encoding="utf-8")
        print(f"Written to {out_path}", file=sys.stderr)
    else:
        sys.stdout.write(code)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <skills.dat> [output.py]", file=sys.stderr)
        sys.exit(1)
    convert(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
