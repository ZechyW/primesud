#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."

# 1stMud areas (converted with 1stMud converter)
FIRST_AREAS="limbo quest"

for area in $FIRST_AREAS; do
    echo "==> $area (1stMud)"
    uv run tools/are_to_primesud.py \
        "reference/1stMud4.5.3/area/${area}.are" \
        "primesud.hpappdir/area_${area}.dat"
done

# QuickMUD areas (converted with quickmud converter)
QM_AREAS="arachnos chapel grave haon immort marsh midgaard mobfact moria newthalos ofcol ofcol2 plains school sewer shire tohell trollden"

for area in $QM_AREAS; do
    echo "==> $area (QuickMUD)"
    uv run tools/are_to_primesud_quickmud.py \
        "reference/quickmud/area/${area}.are" \
        "primesud.hpappdir/area_${area}.dat"
done

# Wire in 1stMud-only deltas (not in quickmud .are files): cross-area
# exits, guildmaster act flags
echo "==> 1stMud deltas"
uv run tools/patch_1stmud_deltas.py

# Verify ASCII safety
echo "==> ASCII check"
uv run tools/check_ascii_py.py
