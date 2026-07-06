"""OSRM access for VRP: distance/duration table and nearest snap.

Route geometry (chunking, steps, bisect fallback for unroutable pairs) is
shared with the history-playback path via :mod:`backend.geo.osrm`.
"""

import httpx

from backend.geo.osrm import route_legs_with_details


OSRM_TIMEOUT_SECONDS = 20


def _build_osrm_table(coordinates, osrm_base_url, profile):
    coord_part = ";".join([f"{lng:.7f},{lat:.7f}" for lng, lat in coordinates])
    url = f"{osrm_base_url.rstrip('/')}/table/v1/{profile}/{coord_part}"
    params = {
        "annotations": "distance,duration"
    }
    with httpx.Client(timeout=OSRM_TIMEOUT_SECONDS) as client:
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


def _fetch_osrm_nearest(osrm_base_url, profile, coordinate):
    lng, lat = coordinate
    url = f"{osrm_base_url.rstrip('/')}/nearest/v1/{profile}/{lng:.7f},{lat:.7f}"
    params = {"number": 1}
    with httpx.Client(timeout=OSRM_TIMEOUT_SECONDS) as client:
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
