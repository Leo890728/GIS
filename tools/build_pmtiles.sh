#!/usr/bin/env bash
# Build stat_zone* PMTiles from bounds.sqlite via Docker (ogr2ogr → tippecanoe).
# Linux equivalent of build_pmtiles.ps1. Run from the repo root.
#
#   tools/build_pmtiles.sh                # full run
#   tools/build_pmtiles.sh --skip-export  # reuse existing GeoJSON
set -euo pipefail

SKIP_EXPORT=0
[ "${1:-}" = "--skip-export" ] && SKIP_EXPORT=1

BOUNDS="/workspace/backend/data/bounds.sqlite"
TMP="backend/tmp"
OUT="backend/pmtiles"
GDAL="ghcr.io/osgeo/gdal:alpine-normal-latest"
# tippecanoe has no official image; build it locally from tools/Dockerfile.tippecanoe.
TIPPECANOE_IMAGE="${TIPPECANOE_IMAGE:-tippecanoe:local}"

# layer:minzoom:maxzoom
LAYERS="stat_zone:12:14 stat_zone_1:11:13 stat_zone_2:9:12"

# Build the tippecanoe image once (cached afterwards) unless it already exists.
ensure_tippecanoe() {
  if [ -z "$(docker images -q "$TIPPECANOE_IMAGE" 2>/dev/null)" ]; then
    echo "Building $TIPPECANOE_IMAGE from tools/Dockerfile.tippecanoe ..."
    docker build -t "$TIPPECANOE_IMAGE" -f tools/Dockerfile.tippecanoe tools
  fi
}

mkdir -p "$TMP" "$OUT"

if [ "$SKIP_EXPORT" = 1 ]; then
  echo "=== [1/2] Skipping GeoJSON export ==="
else
  echo "=== [1/2] Exporting GeoJSON from bounds.sqlite ==="
  cmd=""
  for l in $LAYERS; do
    name="${l%%:*}"
    cmd="${cmd:+$cmd && }ogr2ogr -f GeoJSON /workspace/$TMP/$name.geojson $BOUNDS $name"
  done
  docker run --rm -v "$PWD:/workspace" "$GDAL" sh -c "$cmd"
fi

ensure_tippecanoe

for l in $LAYERS; do
  name="${l%%:*}"; rest="${l#*:}"; minz="${rest%%:*}"; maxz="${rest##*:}"
  echo "=== [2/2] tippecanoe: $name (zoom $minz-$maxz) ==="
  docker run --rm -v "$PWD:/workspace" "$TIPPECANOE_IMAGE" \
    -o "/workspace/$OUT/$name.pmtiles" \
    -Z "$minz" -z "$maxz" \
    --layer="$name" \
    --force \
    --coalesce-densest-as-needed \
    --extend-zooms-if-still-dropping \
    --detect-shared-borders \
    "/workspace/$TMP/$name.geojson"
done

echo "=== Done ==="
ls -lh "$OUT"/stat_zone*.pmtiles
