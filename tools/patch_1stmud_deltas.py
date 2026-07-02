#!/usr/bin/env python3
"""Patch 1stMud-only deltas into generated area .dat files.

Data that exists in 1stMud but not in the QuickMUD .are files the
converter reads: cross-area exits, and mob act flags (1stMud gives its
midgaard guildmasters ACT_TRAIN/ACT_GAIN). Run after
are_to_primesud_quickmud.py conversion (regen_areas.sh does).

Usage:
    python patch_1stmud_deltas.py
"""

import re
import sys
from pathlib import Path

# {area_name: {room_vnum: {direction: target_vnum}}}
CROSS_AREA_EXITS = {
    "midgaard": {
        3001: {"e": 200, "w": 201},   # quest area (1stMud-only)
        3054: {"d": 3},                # limbo (1stMud-only)
        3303: {"s": 202},              # quest area trivia shop (1stMud-only)
    },
}

# {area_name: {mob_vnum: (flag, ...)}} -- added to the mob's act_flags.
# 3020/3023 (mage/warrior GM): train + gain per 1stMud midgaard.are.
# 3021/3022 (cleric/thief GM): gain is [PRIMESUD] -- upstream has neither,
# but every guild must be gain/remort-capable single-area (CLASS_PLAN.md
# Phase D).
MOB_ACT_FLAGS = {
    "midgaard": {
        3020: ("train", "gain"),
        3021: ("gain",),
        3022: ("gain",),
        3023: ("train", "gain"),
    },
}

# {area_name: {room_vnum: (class_idx, ...)}} -- written as a "guild" field
# on the room (cf. 1stMud midgaard.are G <class> fields; single class per
# room upstream). Class indices per classes.py CLASS_TABLE: 0 mage,
# 1 cleric, 2 thief, 3 warrior, 4 paladin, 5 ranger. Paladin sharing the
# cleric rooms and ranger the warrior rooms is [PRIMESUD] -- no
# paladin/ranger guilds exist in midgaard (CLASS_PLAN.md).
ROOM_GUILDS = {
    "midgaard": {
        3018: (0,),     3019: (0,),      # Mage's Bar / Laboratory
        3002: (1, 4),   3003: (1, 4),    # Cleric's Inner Sanctum / Bar
        3028: (2,),     3029: (2,),      # Thieves Bar / Secret Yard
        3022: (3, 5),   3023: (3, 5),    # Bar of Swordsmen / Tournament Yard
    },
}

DIR_ORDER = "neswud"


def exit_sort_key(line):
    m = re.match(r'\s+"([neswud])":', line)
    return DIR_ORDER.index(m.group(1)) if m else 99


def patch_area(area_name, filepath):
    exits_to_add = CROSS_AREA_EXITS.get(area_name)
    if not exits_to_add:
        return False

    text = Path(filepath).read_text(encoding="utf-8")
    lines = text.split("\n")

    rooms_section = None
    for idx in range(len(lines)):
        if lines[idx].startswith("ROOMS = {"):
            rooms_section = idx
            break

    modified = False
    for vnum, new_exits in sorted(exits_to_add.items()):
        room_pattern = f"    {vnum}: {{"
        room_start = None
        for idx in range(rooms_section or 0, len(lines)):
            if lines[idx].startswith(room_pattern):
                room_start = idx
                break
        if room_start is None:
            print(f"  WARNING: room block for {vnum} not found", file=sys.stderr)
            continue

        exits_start = None
        for idx in range(room_start, min(room_start + 50, len(lines))):
            if '"exits": {' in lines[idx]:
                exits_start = idx
                break
        if exits_start is None:
            print(f"  WARNING: exits block not found for {vnum}", file=sys.stderr)
            continue

        exits_end = None
        for idx in range(exits_start + 1, min(exits_start + 50, len(lines))):
            if lines[idx].strip() == "},":
                exits_end = idx
                break
        if exits_end is None:
            print(f"  WARNING: exits end not found for {vnum}", file=sys.stderr)
            continue

        exit_lines = lines[exits_start + 1:exits_end]
        for d in new_exits:
            target = new_exits[d]
            exit_lines.append(
                f'            "{d}": {target},'
                f"  # [PRIMESUD] cross-area (1stMud)"
            )
        exit_lines.sort(key=exit_sort_key)

        lines[exits_start + 1:exits_end] = exit_lines
        modified = True
        dirs = ", ".join(sorted(new_exits.keys(), key=lambda x: DIR_ORDER.index(x)))
        print(f"  {vnum}: +{dirs}", file=sys.stderr)

    if modified:
        Path(filepath).write_text("\n".join(lines), encoding="utf-8")
    return modified


def patch_mob_flags(area_name, filepath):
    flags_to_add = MOB_ACT_FLAGS.get(area_name)
    if not flags_to_add:
        return False

    text = Path(filepath).read_text(encoding="utf-8")
    lines = text.split("\n")

    mob_section = end_section = None
    for idx in range(len(lines)):
        if lines[idx].startswith("MOBILES = {"):
            mob_section = idx
        elif mob_section is not None and re.match(r"^[A-Z_]+ = ", lines[idx]):
            end_section = idx
            break

    modified = False
    for vnum, flags in sorted(flags_to_add.items()):
        mob_pattern = f"    {vnum}: {{"
        act_idx = None
        for idx in range(mob_section or 0, end_section or len(lines)):
            if lines[idx].startswith(mob_pattern):
                for j in range(idx, min(idx + 30, len(lines))):
                    if '"act_flags": {' in lines[j]:
                        act_idx = j
                        break
                break
        if act_idx is None:
            print(f"  WARNING: act_flags for mob {vnum} not found", file=sys.stderr)
            continue

        line = lines[act_idx]
        prefix, suffix = line.rsplit("}", 1)
        added = [f for f in flags if f'"{f}"' not in prefix]
        if not added:
            continue
        lines[act_idx] = (prefix
                          + "".join(f', "{f}": True' for f in added)
                          + "}" + suffix
                          + "  # [PRIMESUD] +" + "/".join(added)
                          + " (patch_1stmud_deltas)")
        modified = True
        print(f"  mob {vnum}: +{'/'.join(added)}", file=sys.stderr)

    if modified:
        Path(filepath).write_text("\n".join(lines), encoding="utf-8")
    return modified


def patch_room_guilds(area_name, filepath):
    guilds_to_add = ROOM_GUILDS.get(area_name)
    if not guilds_to_add:
        return False

    text = Path(filepath).read_text(encoding="utf-8")
    lines = text.split("\n")

    rooms_section = None
    for idx in range(len(lines)):
        if lines[idx].startswith("ROOMS = {"):
            rooms_section = idx
            break

    modified = False
    for vnum, classes in sorted(guilds_to_add.items()):
        room_pattern = f"    {vnum}: {{"
        room_start = None
        for idx in range(rooms_section or 0, len(lines)):
            if lines[idx].startswith(room_pattern):
                room_start = idx
                break
        if room_start is None:
            print(f"  WARNING: room block for {vnum} not found", file=sys.stderr)
            continue
        if '"guild"' in lines[room_start + 1]:
            continue  # already patched
        tup = "(" + ", ".join(str(c) for c in classes) + ("," if len(classes) == 1 else "") + ")"
        lines.insert(room_start + 1,
                     f'        "guild": {tup},'
                     "  # [PRIMESUD] cf. 1stMud G field (patch_1stmud_deltas)")
        modified = True
        print(f"  room {vnum}: guild {tup}", file=sys.stderr)

    if modified:
        Path(filepath).write_text("\n".join(lines), encoding="utf-8")
    return modified


if __name__ == "__main__":
    base = Path(__file__).resolve().parent.parent / "primesud.hpappdir"
    for area_name in sorted(set(CROSS_AREA_EXITS) | set(MOB_ACT_FLAGS)
                            | set(ROOM_GUILDS)):
        filepath = base / f"area_{area_name}.dat"
        if filepath.exists():
            print(f"==> {area_name}", file=sys.stderr)
            patch_area(area_name, filepath)
            patch_mob_flags(area_name, filepath)
            patch_room_guilds(area_name, filepath)
        else:
            print(f"  SKIP: {filepath} not found", file=sys.stderr)
