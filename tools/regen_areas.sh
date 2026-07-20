#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."

# areas/*.are: ROM 2.4 / QuickMUD-format area sources, converted from
# their original 1stMud/QuickMUD layouts (originals live untouched under
# reference/). Regenerate src/area_<name>.txt for every one.
AREAS="air arachnos astral canyon catacomb chapel daycare draconia dream drow dwarven dylan eastern galaxy gnome grave grove haon hitower hood immort limbo mahntor marsh mega1 midennir midgaard mirror mobfact moria newthalos nirvana ofcol ofcol2 olympus plains pyramid quest redferne school sewer shire smurf thalos tohell trollden valley wyvern"

for area in $AREAS; do
    echo "==> $area"
    uv run tools/are_to_primesud.py \
        "areas/${area}.are" \
        "src/area_${area}.txt"
done

# Refresh world.py's static tables (AREA_BUILDERS/_AREA_ADJ; fails on
# AREA_LEVELS drift) BEFORE the index builds below -- both bootstrap the
# world from those tables, so a just-added area would otherwise be
# missing from the indexes.
echo "==> world.py static tables"
uv run tools/gen_area_adj.py

# Rebuild mobs.idx (spec_fun/portal/summon target lookup) -- must be
# regenerated after any area regen since it derives from RESETS/MOBILES.
echo "==> mobs.idx"
uv run tools/build_mob_index.py

# Rebuild paths.idx (path/run border-graph routing) -- must be
# regenerated after any area regen since it derives from room exits.
echo "==> paths.idx"
uv run tools/build_path_index.py

# Verify ASCII safety
echo "==> ASCII check"
uv run tools/check_ascii_py.py
