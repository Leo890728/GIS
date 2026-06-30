#!/usr/bin/env bash
# Build the full-network OSRM graph (MLD) for Taiwan on Linux.
# Downloads the latest Taiwan extract from Geofabrik (unless one is present),
# then runs extract → partition → customize via the osrm-backend image.
#
#   tools/osrm/build.sh              # download if missing, then build
#   tools/osrm/build.sh --refresh    # re-download the PBF even if present
set -euo pipefail
cd "$(dirname "$0")"

PBF_URL="${PBF_URL:-https://download.geofabrik.de/asia/taiwan-latest.osm.pbf}"
IMAGE="ghcr.io/project-osrm/osrm-backend"
OUT="taiwan.osrm"

REFRESH=0
[ "${1:-}" = "--refresh" ] && REFRESH=1

PBF="$(ls -1t taiwan-*.osm.pbf 2>/dev/null | head -n1 || true)"
if [ -z "$PBF" ] || [ "$REFRESH" = 1 ]; then
  PBF="taiwan-latest.osm.pbf"
  echo "Downloading $PBF_URL ..."
  curl -fSL -o "$PBF" "$PBF_URL"
fi

echo "PBF=$PBF"
echo "OUT=$OUT"

echo "[1/3] Extract with default car profile..."
docker run --rm -v "$PWD:/data" "$IMAGE" osrm-extract -p /opt/car.lua -o "/data/$OUT" "/data/$PBF"
echo "[2/3] Partition..."
docker run --rm -v "$PWD:/data" "$IMAGE" osrm-partition "/data/$OUT"
echo "[3/3] Customize..."
docker run --rm -v "$PWD:/data" "$IMAGE" osrm-customize "/data/$OUT"

echo "Build complete: $OUT"
echo "Serve it with: OSRM_DATA=$OUT docker compose up -d osrm"
