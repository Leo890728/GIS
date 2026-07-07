#!/usr/bin/env bash
# Build the full-network OSRM graph for Taiwan.
# Downloads the latest Taiwan extract from Geofabrik (unless one is present),
# then runs the processing pipeline via the osrm-backend image.
#
# Algorithms:
#   mld (default) — extract → partition → customize; fast rebuilds, slower /table
#   ch            — extract → contract; slower build, much faster /table (VRP matrices)
#
#   tools/osrm/build.sh                  # MLD build (taiwan.osrm)
#   tools/osrm/build.sh --algo ch        # CH build (taiwan-ch.osrm)
#   tools/osrm/build.sh --refresh        # re-download the PBF even if present
set -euo pipefail
cd "$(dirname "$0")"

# Git Bash on Windows rewrites container paths like /opt/car.lua into
# C:/Program Files/Git/opt/car.lua; disable that conversion for docker args.
export MSYS_NO_PATHCONV=1

PBF_URL="${PBF_URL:-https://download.geofabrik.de/asia/taiwan-latest.osm.pbf}"
IMAGE="ghcr.io/project-osrm/osrm-backend"
ALGO="mld"

REFRESH=0
while [ $# -gt 0 ]; do
  case "$1" in
    --refresh) REFRESH=1 ;;
    --algo) shift; ALGO="${1:?--algo requires mld or ch}" ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
  shift
done

case "$ALGO" in
  mld) OUT="taiwan.osrm" ;;
  ch) OUT="taiwan-ch.osrm" ;;
  *) echo "--algo must be mld or ch" >&2; exit 1 ;;
esac

PBF="$(ls -1t taiwan-*.osm.pbf 2>/dev/null | head -n1 || true)"
if [ -z "$PBF" ] || [ "$REFRESH" = 1 ]; then
  PBF="taiwan-latest.osm.pbf"
  echo "Downloading $PBF_URL ..."
  curl -fSL -o "$PBF" "$PBF_URL"
fi

echo "PBF=$PBF"
echo "OUT=$OUT (algorithm: $ALGO)"

echo "[1/2] Extract with default car profile..."
docker run --rm -v "$PWD:/data" "$IMAGE" osrm-extract -p /opt/car.lua -o "/data/$OUT" "/data/$PBF"

if [ "$ALGO" = "ch" ]; then
  echo "[2/2] Contract (CH)..."
  docker run --rm -v "$PWD:/data" "$IMAGE" osrm-contract "/data/$OUT"
else
  echo "[2/3] Partition..."
  docker run --rm -v "$PWD:/data" "$IMAGE" osrm-partition "/data/$OUT"
  echo "[3/3] Customize..."
  docker run --rm -v "$PWD:/data" "$IMAGE" osrm-customize "/data/$OUT"
fi

echo "Build complete: $OUT"
echo "Serve it with: OSRM_DATA=$OUT OSRM_ALGO=$ALGO docker compose up -d osrm"
