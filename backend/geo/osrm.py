"""Self-hosted OSRM HTTP client (route service).

Standalone OSRM access for the history playback path. Kept separate from the
VRP module so callers don't have to import that module; the pure-geometry
helpers live in :mod:`backend.geo.geometry`.

The headline helper is :func:`route_legs`: given a chain of waypoints it
returns one road-following geometry per consecutive pair, batching the
waypoints into as few OSRM calls as possible (so 1000 history points become a
handful of requests, not 999). Per-leg geometry is obtained with
``steps=true`` and the step geometries within each leg are concatenated.
"""

import httpx

from backend.geo.geometry import haversine_m

DEFAULT_TIMEOUT_SECONDS = 20
# A single GET /route URL carries every waypoint, so both a waypoint count and
# a URL-length ceiling are needed to stay under OSRM/proxy limits.
DEFAULT_MAX_WAYPOINTS_PER_CALL = 1000
DEFAULT_MAX_URL_LENGTH = 7800


def _build_route_url(base_url, profile, coordinates, steps):
    coord_part = ";".join(f"{lng:.7f},{lat:.7f}" for lng, lat in coordinates)
    steps_str = "true" if steps else "false"
    query = f"overview=full&geometries=geojson&steps={steps_str}"
    return f"{base_url.rstrip('/')}/route/v1/{profile}/{coord_part}?{query}"


def _exceeds_url_limit(base_url, profile, coordinates, max_url_length):
    if len(coordinates) <= 1:
        return False
    return len(_build_route_url(base_url, profile, coordinates, steps=True)) > max_url_length


def fetch_route(base_url, profile, coordinates, *, steps=False, timeout=DEFAULT_TIMEOUT_SECONDS):
    """One OSRM ``/route`` call. Returns ``(geometry_coords, legs)``.

    ``geometry_coords`` is the merged ``[lng, lat]`` polyline; ``legs`` is the
    OSRM legs array (one per consecutive waypoint pair).
    """
    if len(coordinates) < 2:
        raise RuntimeError("OSRM route requires at least two coordinates")

    url = _build_route_url(base_url, profile, coordinates, steps)
    with httpx.Client(timeout=timeout) as client:
        response = client.get(url)
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
    if not isinstance(geometry, dict) or geometry.get("type") != "LineString":
        raise RuntimeError("OSRM route geometry must be a LineString")
    coords = geometry.get("coordinates")
    if not isinstance(coords, list):
        raise RuntimeError("OSRM route geometry coordinates are missing")

    legs = route.get("legs")
    if not isinstance(legs, list):
        raise RuntimeError("OSRM route legs are missing")

    return coords, legs


def _leg_coordinates(leg):
    """Concatenate a leg's per-step geometries into one ``[lng, lat]`` list.

    Requires the route to have been fetched with ``steps=true``; the vertex
    shared between consecutive steps is dropped.
    """
    coords = []
    for step in leg.get("steps") or []:
        geometry = step.get("geometry") or {}
        for point in geometry.get("coordinates") or []:
            pair = [point[0], point[1]]
            if coords and coords[-1] == pair:
                continue
            coords.append(pair)
    return coords


def route_legs(
    base_url,
    profile,
    coordinates,
    *,
    max_waypoints_per_call=DEFAULT_MAX_WAYPOINTS_PER_CALL,
    max_url_length=DEFAULT_MAX_URL_LENGTH,
    timeout=DEFAULT_TIMEOUT_SECONDS,
):
    """Road-following geometry for each consecutive pair in ``coordinates``.

    Returns a list of length ``len(coordinates) - 1``; entry ``i`` is the
    ``[lng, lat]`` polyline from ``coordinates[i]`` to ``coordinates[i + 1]``.
    Waypoints are split into chunks bounded by ``max_waypoints_per_call`` and
    ``max_url_length``, then the legs are concatenated across chunks.
    """
    if len(coordinates) < 2:
        raise RuntimeError("route_legs requires at least two coordinates")

    leg_geometries = []
    start = 0
    while start < len(coordinates) - 1:
        end = min(len(coordinates) - 1, start + max_waypoints_per_call - 1)
        while end > start + 1 and _exceeds_url_limit(
            base_url, profile, coordinates[start : end + 1], max_url_length
        ):
            end -= 1
        if end <= start:
            raise RuntimeError("Cannot build a valid OSRM route chunk within the URL limit")

        chunk = coordinates[start : end + 1]
        _coords, legs = fetch_route(base_url, profile, chunk, steps=True, timeout=timeout)
        if len(legs) != len(chunk) - 1:
            raise RuntimeError("OSRM returned an unexpected number of legs for the chunk")
        leg_geometries.extend(_leg_coordinates(leg) for leg in legs)
        start = end

    return leg_geometries
