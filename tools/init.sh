#!/usr/bin/env bash
# Build all data assets from source on Linux (Docker required).
# Linux equivalent of init.ps1 (build-from-source mode): downloads boundary
# SHP, imports them into bounds.sqlite + precomputed tables, then builds the
# stat_zone PMTiles. OSRM data is built separately by tools/osrm/build.sh.
#
#   tools/init.sh                  # full run
#   tools/init.sh --skip-download  # SHP already in backend/shp/
#   tools/init.sh --skip-import    # bounds.sqlite already built
#   tools/init.sh --skip-pmtiles   # PMTiles already built
set -euo pipefail
cd "$(git rev-parse --show-toplevel 2>/dev/null || dirname "$(dirname "$0")")"

SKIP_DOWNLOAD=0; SKIP_IMPORT=0; SKIP_PMTILES=0
for a in "$@"; do
  case "$a" in
    --skip-download) SKIP_DOWNLOAD=1 ;;
    --skip-import)   SKIP_IMPORT=1 ;;
    --skip-pmtiles)  SKIP_PMTILES=1 ;;
    *) echo "unknown option: $a" >&2; exit 2 ;;
  esac
done

GDAL="ghcr.io/osgeo/gdal:alpine-normal-latest"

command -v docker >/dev/null 2>&1 || { echo "Docker not found." >&2; exit 1; }
docker info >/dev/null 2>&1 || { echo "Docker is not running." >&2; exit 1; }

# Tolerate CRLF in the committed .sh helpers (repo is edited on Windows).
run_sh() { docker run --rm -v "$PWD:/workspace" "$GDAL" sh -c "tr -d '\015' < $1 | sh"; }

echo "=== [1/3] Download SHP files ==="
if [ "$SKIP_DOWNLOAD" = 1 ]; then echo "Skipped."; else
  mkdir -p backend/shp
  run_sh /workspace/tools/docker/download_shp.sh
fi

echo "=== [2/3] Import SHP -> bounds.sqlite + precomputed tables ==="
if [ "$SKIP_IMPORT" = 1 ]; then echo "Skipped."; else
  mkdir -p backend/data
  run_sh /workspace/tools/docker/import_bounds.sh
  docker run --rm -v "$PWD:/workspace" "$GDAL" python /workspace/tools/docker/build_bounds_extras.py
fi

echo "=== [3/3] Build PMTiles ==="
if [ "$SKIP_PMTILES" = 1 ]; then echo "Skipped."; else
  # build_pmtiles.sh builds the tippecanoe image locally on first run.
  tools/build_pmtiles.sh
fi

echo "=== Init complete ==="
[ -f backend/data/bounds.sqlite ] && ls -lh backend/data/bounds.sqlite
ls -lh backend/pmtiles/*.pmtiles 2>/dev/null || true
echo "OSRM: run tools/osrm/build.sh separately to (re)build the routing graph."
