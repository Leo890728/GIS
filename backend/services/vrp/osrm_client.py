"""OSRM access for VRP: distance/duration table and nearest snap.

Route geometry (chunking, steps, bisect fallback for unroutable pairs) is
shared with the history-playback path via :mod:`backend.geo.osrm`.
"""

import math
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx

from backend.geo.osrm import route_legs_with_details


OSRM_TIMEOUT_SECONDS = int(os.getenv("VRP_OSRM_TIMEOUT_SECONDS", "60"))

# /table tiling: above the threshold the matrix is split into row×col blocks
# fetched in parallel. Tile work on MLD scales with sources+destinations, so
# smaller tiles trade extra total work for wall-clock parallelism. The union
# of an off-diagonal tile's coordinates (2 × block size) must stay under the
# server's --max-table-size (1500 in docker-compose.yml).
TABLE_SPLIT_THRESHOLD = int(os.getenv("VRP_TABLE_SPLIT_THRESHOLD", "400"))
TABLE_BLOCK_MAX_COORDS = int(os.getenv("VRP_TABLE_BLOCK_MAX_COORDS", "600"))
TABLE_MAX_PARALLEL_REQUESTS = int(os.getenv("VRP_TABLE_MAX_PARALLEL_REQUESTS", "8"))


def _fetch_table_tile(client, osrm_base_url, profile, coordinates, row_block, col_block):
    row_start, row_stop = row_block
    col_start, col_stop = col_block
    if (row_start, row_stop) == (col_start, col_stop):
        tile_coords = coordinates[row_start:row_stop]
        params = {"annotations": "distance,duration"}
    else:
        row_coords = coordinates[row_start:row_stop]
        col_coords = coordinates[col_start:col_stop]
        tile_coords = row_coords + col_coords
        params = {
            "annotations": "distance,duration",
            "sources": ";".join(str(i) for i in range(len(row_coords))),
            "destinations": ";".join(str(i) for i in range(len(row_coords), len(tile_coords))),
        }
    coord_part = ";".join([f"{lng:.7f},{lat:.7f}" for lng, lat in tile_coords])
    url = f"{osrm_base_url.rstrip('/')}/table/v1/{profile}/{coord_part}"
    response = client.get(url, params=params)
    if response.status_code >= 400:
        raise RuntimeError(f"OSRM table request failed: {response.status_code}")
    payload = response.json()
    if payload.get("code") != "Ok":
        raise RuntimeError(f"OSRM table error: {payload.get('message') or payload.get('code')}")
    distances = payload.get("distances")
    durations = payload.get("durations")
    if not isinstance(distances, list) or not isinstance(durations, list):
        raise RuntimeError("OSRM table response is missing distances/durations")
    return distances, durations


def _build_osrm_table(coordinates, osrm_base_url, profile):
    size = len(coordinates)
    blocks_per_side = 1
    if size > TABLE_SPLIT_THRESHOLD:
        # At least 2×2 so mid-sized matrices still parallelize instead of
        # degenerating into one big tile plus slivers.
        blocks_per_side = max(2, math.ceil(size / TABLE_BLOCK_MAX_COORDS))
    block_size = math.ceil(size / blocks_per_side)
    blocks = [(start, min(start + block_size, size)) for start in range(0, size, block_size)]

    with httpx.Client(timeout=OSRM_TIMEOUT_SECONDS) as client:
        if len(blocks) == 1:
            return _fetch_table_tile(client, osrm_base_url, profile, coordinates, blocks[0], blocks[0])

        distances = [[None] * size for _ in range(size)]
        durations = [[None] * size for _ in range(size)]
        with ThreadPoolExecutor(max_workers=TABLE_MAX_PARALLEL_REQUESTS) as pool:
            futures = {
                pool.submit(_fetch_table_tile, client, osrm_base_url, profile, coordinates, row_block, col_block): (
                    row_block,
                    col_block,
                )
                for row_block in blocks
                for col_block in blocks
            }
            for future in as_completed(futures):
                (row_start, _), (col_start, col_stop) = futures[future]
                tile_distances, tile_durations = future.result()
                for offset, tile_row in enumerate(tile_distances):
                    distances[row_start + offset][col_start:col_stop] = tile_row
                for offset, tile_row in enumerate(tile_durations):
                    durations[row_start + offset][col_start:col_stop] = tile_row
    return distances, durations


def _fetch_osrm_nearest(osrm_base_url, profile, coordinate, client=None):
    lng, lat = coordinate
    url = f"{osrm_base_url.rstrip('/')}/nearest/v1/{profile}/{lng:.7f},{lat:.7f}"
    params = {"number": 1}
    if client is None:
        with httpx.Client(timeout=OSRM_TIMEOUT_SECONDS) as owned_client:
            response = owned_client.get(url, params=params)
    else:
        response = client.get(url, params=params)
    if response.status_code != 200:
        raise RuntimeError(f"OSRM nearest request failed: {response.status_code}")
    payload = response.json()
    if payload.get("code") != "Ok":
        raise RuntimeError(f"OSRM nearest error: {payload.get('message') or payload.get('code')}")
    waypoints = payload.get("waypoints")
    if not isinstance(waypoints, list) or not waypoints:
        raise RuntimeError("OSRM nearest response has no waypoints")
    nearest = waypoints[0] or {}
    location = nearest.get("location")
    if not isinstance(location, list) or len(location) != 2:
        raise RuntimeError("OSRM nearest waypoint location is invalid")
    snapped_lng, snapped_lat = location[0], location[1]
    if not isinstance(snapped_lng, (int, float)) or not isinstance(snapped_lat, (int, float)):
        raise RuntimeError("OSRM nearest waypoint location must be numeric")
    distance_m = nearest.get("distance")
    if not isinstance(distance_m, (int, float)):
        distance_m = 0.0
    return {
        "lng": float(snapped_lng),
        "lat": float(snapped_lat),
        "distance_m": float(distance_m),
    }


def _build_route_geometry_from_osrm(
    coordinates,
    osrm_base_url,
    profile,
    max_waypoints_per_call,
    max_url_length,
):
    """Road-following geometry + OSRM legs for a vehicle's stop sequence.

    Built on the shared chunked/bisecting client, so one unroutable stop
    (snapped outside the extract, GPS junk) degrades only its own leg to a
    straight segment instead of failing the whole route. A leg entry is the
    OSRM leg dict (distance/duration/steps), or ``None`` for a fallback pair —
    the solver keeps its matrix estimates and skips instructions for those.
    """
    if len(coordinates) < 2:
        raise RuntimeError("Route coordinates must contain at least two points")

    pairs = route_legs_with_details(
        osrm_base_url,
        profile,
        coordinates,
        max_waypoints_per_call=max_waypoints_per_call,
        max_url_length=max_url_length,
        timeout=OSRM_TIMEOUT_SECONDS,
    )

    merged_coordinates = []
    merged_legs = []
    for coords, leg in pairs:
        if not merged_coordinates:
            merged_coordinates.extend(coords)
        elif coords:
            merged_coordinates.extend(coords[1:] if merged_coordinates[-1] == coords[0] else coords)
        merged_legs.append(leg)

    if not merged_coordinates:
        raise RuntimeError("OSRM route returned empty geometry")

    return (
        {
            "type": "LineString",
            "coordinates": merged_coordinates,
        },
        merged_legs,
    )
