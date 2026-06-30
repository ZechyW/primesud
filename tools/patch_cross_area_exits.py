#!/usr/bin/env python3
"""Patch cross-area exits into generated area .py files.

These exits exist in 1stMud but not in QuickMUD .are files.
Run after are_to_primesud_quickmud.py conversion.

Usage:
    python patch_cross_area_exits.py
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


if __name__ == "__main__":
    base = Path(__file__).resolve().parent.parent / "primesud.hpappdir"
    for area_name in sorted(CROSS_AREA_EXITS):
        filepath = base / f"area_{area_name}.dat"
        if filepath.exists():
            print(f"==> {area_name}", file=sys.stderr)
            patch_area(area_name, filepath)
        else:
            print(f"  SKIP: {filepath} not found", file=sys.stderr)
