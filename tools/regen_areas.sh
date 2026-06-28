#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."

# 1stMud areas (converted with 1stMud converter)
FIRST_AREAS="limbo quest"

for area in $FIRST_AREAS; do
    echo "==> $area (1stMud)"
    uv run tools/are_to_primesud.py \
        "reference/1stMud4.5.3/area/${area}.are" \
        "primesud.hpappdir/area_${area}.py"
done

# QuickMUD areas (converted with quickmud converter)
QM_AREAS="chapel grave haon immort midgaard mobfact ofcol2 plains school shire"

for area in $QM_AREAS; do
    echo "==> $area (QuickMUD)"
    uv run tools/are_to_primesud_quickmud.py \
        "reference/quickmud/area/${area}.are" \
        "primesud.hpappdir/area_${area}.py"
done

# Wire in cross-area exits from 1stMud (not in quickmud .are files)
echo "==> cross-area exits"
uv run tools/patch_cross_area_exits.py

# Verify ASCII safety
echo "==> ASCII check"
uv run tools/check_ascii_py.py
