#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."

AREAS="chapel school quest limbo midgaard"

for area in $AREAS; do
    echo "==> $area"
    uv run tools/are_to_primesud.py \
        "reference/1stMud4.5.3/area/${area}.are" \
        "primesud.hpappdir/area_${area}.py"
done
