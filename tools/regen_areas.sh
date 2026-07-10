#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."

# areas/*.are: ROM 2.4 / QuickMUD-format area sources, converted from
# their original 1stMud/QuickMUD layouts (originals live untouched under
# reference/). Regenerate src/area_<name>.txt for every one.
AREAS="arachnos chapel daycare grave haon immort limbo marsh midgaard mobfact moria newthalos ofcol ofcol2 plains quest school sewer shire tohell trollden"

for area in $AREAS; do
    echo "==> $area"
    uv run tools/are_to_primesud.py \
        "areas/${area}.are" \
        "src/area_${area}.txt"
done

# Rebuild mob_index.txt (spec_fun/portal/summon target lookup) -- must be
# regenerated after any area regen since it derives from RESETS/MOBILES.
echo "==> mob_index"
uv run tools/build_mob_index.py

# Verify ASCII safety
echo "==> ASCII check"
uv run tools/check_ascii_py.py
