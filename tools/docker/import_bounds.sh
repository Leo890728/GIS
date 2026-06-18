#!/bin/sh
# Import boundary SHP files into bounds.sqlite (SpatiaLite format).
# Run inside Docker GDAL: called by tools/init.ps1
set -e

SHP="/workspace/backend/shp"
OUT="/workspace/backend/data/bounds.sqlite"

find_shp() {
  dir="$1"
  found=$(find "$SHP/$dir" -maxdepth 2 -name "*.shp" 2>/dev/null | head -1)
  if [ -z "$found" ]; then
    echo "ERROR: No .shp found in $SHP/$dir" >&2
    exit 1
  fi
  echo "$found"
}

rm -f "$OUT"

echo "=== [1/6] county ==="
ogr2ogr -f SQLite -dsco SPATIALITE=YES \
  -nlt MULTIPOLYGON -nln county \
  -t_srs EPSG:4326 \
  "$OUT" "$(find_shp county)"

echo "=== [2/6] township ==="
ogr2ogr -f SQLite -update \
  -nlt MULTIPOLYGON -nln township \
  -t_srs EPSG:4326 \
  "$OUT" "$(find_shp township)"

echo "=== [3/6] village ==="
ogr2ogr -f SQLite -update \
  -nlt MULTIPOLYGON -nln village \
  -t_srs EPSG:4326 \
  "$OUT" "$(find_shp village)"

echo "=== [4/6] stat_zone_2 ==="
ogr2ogr -f SQLite -update \
  -nlt MULTIPOLYGON -nln stat_zone_2 \
  -s_srs EPSG:3826 -t_srs EPSG:4326 \
  --config SHAPE_ENCODING BIG5 \
  "$OUT" "$(find_shp stat_zone_2)"

echo "=== [5/6] stat_zone_1 ==="
ogr2ogr -f SQLite -update \
  -nlt MULTIPOLYGON -nln stat_zone_1 \
  -s_srs EPSG:3826 -t_srs EPSG:4326 \
  --config SHAPE_ENCODING BIG5 \
  "$OUT" "$(find_shp stat_zone_1)"

echo "=== [6/6] stat_zone ==="
if ! find "$SHP/stat_zone" -maxdepth 2 -name "*.shp" 2>/dev/null | grep -q .; then
  echo "WARNING: stat_zone SHP not found, skipping."
else
  ogr2ogr -f SQLite -update \
    -nlt MULTIPOLYGON -nln stat_zone \
    -s_srs EPSG:3826 -t_srs EPSG:4326 \
    --config SHAPE_ENCODING BIG5 \
    "$OUT" "$(find_shp stat_zone)"
fi

echo "=== Done: $OUT ==="
ogrinfo "$OUT" | grep -E "^[0-9]+:"
