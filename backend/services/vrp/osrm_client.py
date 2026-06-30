"""OSRM access: distance/duration table, nearest snap, route + chunking."""

import httpx


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


def _build_osrm_route_url(osrm_base_url, profile, coordinates):
    coord_part = ";".join([f"{lng:.7f},{lat:.7f}" for lng, lat in coordinates])
    query_part = "overview=full&geometries=geojson&steps=false"
    return f"{osrm_base_url.rstrip('/')}/route/v1/{profile}/{coord_part}?{query_part}"


def _route_request_exceeds_limit(osrm_base_url, profile, coordinates, max_url_length):
    if len(coordinates) <= 1:
        return False
    route_url = _build_osrm_route_url(osrm_base_url, profile, coordinates)
    return len(route_url) > max_url_length


def _fetch_osrm_route(osrm_base_url, profile, coordinates):
    if len(coordinates) < 2:
        raise RuntimeError("OSRM route requires at least two coordinates")

    coord_part = ";".join([f"{lng:.7f},{lat:.7f}" for lng, lat in coordinates])
    url = f"{osrm_base_url.rstrip('/')}/route/v1/{profile}/{coord_part}"
    params = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "false",
    }

    with httpx.Client(timeout=OSRM_TIMEOUT_SECONDS) as client:
        response = client.get(url, params=params)
    if response.status_code >= 400:
        raise RuntimeError(f"OSRM route request failed: {response.status_code}")

    payload = response.json()
    if payload.get("code") != "Ok":
        raise RuntimeError(f"OSRM route error: {payload.get('message') or payload.get('code')}")

    routes = payload.get("routes") or []
    if not routes:
        raise RuntimeError("OSRM route response has no routes")

    route = routes[0]
    geometry = route.get("geometry")
    legs = route.get("legs") or []
    if not isinstance(geometry, dict):
        raise RuntimeError("OSRM route response geometry is missing")
    if geometry.get("type") != "LineString":
        raise RuntimeError("OSRM route geometry must be LineString")
    if not isinstance(geometry.get("coordinates"), list):
        raise RuntimeError("OSRM route geometry coordinates are missing")
    if not isinstance(legs, list):
        raise RuntimeError("OSRM route legs are missing")
    return geometry, legs


def _build_route_geometry_from_osrm(
    coordinates,
    osrm_base_url,
    profile,
    max_waypoints_per_call,
    max_url_length,
):
    if len(coordinates) < 2:
        raise RuntimeError("Route coordinates must contain at least two points")

    merged_coordinates = []
    merged_legs = []
    start_index = 0

    while start_index < len(coordinates) - 1:
        end_index = min(len(coordinates) - 1, start_index + max_waypoints_per_call - 1)

        while end_index > start_index + 1:
            chunk_coordinates = coordinates[start_index : end_index + 1]
            if not _route_request_exceeds_limit(
                osrm_base_url,
                profile,
                chunk_coordinates,
                max_url_length,
            ):
                break
            end_index -= 1

        if end_index <= start_index:
            raise RuntimeError("Cannot create a valid OSRM route chunk")

        chunk_coordinates = coordinates[start_index : end_index + 1]
        chunk_geometry, chunk_legs = _fetch_osrm_route(osrm_base_url, profile, chunk_coordinates)
        chunk_path = chunk_geometry.get("coordinates") or []

        if not chunk_path:
            raise RuntimeError("OSRM route chunk returned empty geometry")
        if not merged_coordinates:
            merged_coordinates.extend(chunk_path)
        else:
            merged_coordinates.extend(chunk_path[1:])

        merged_legs.extend(chunk_legs)
        start_index = end_index

    return (
        {
            "type": "LineString",
            "coordinates": merged_coordinates,
        },
        merged_legs,
    )
