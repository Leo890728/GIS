"""Build road-following, time-stamped tracks for history playback.

Each entity's captured position samples are turned into a dense polyline that
follows roads (via self-hosted OSRM) with a timestamp on every vertex, so the
frontend can interpolate a smooth position at any instant. Between two
consecutive samples (posA@tA -> posB@tB) the OSRM route geometry is fetched and
its vertices are time-stamped by cumulative-distance fraction of [tA, tB]
(constant-speed assumption along the road).

Routing is bypassed for near-stationary legs and falls back to a straight
segment when OSRM fails or returns an implausibly long detour.
"""

import math
from datetime import timedelta, timezone

DEFAULT_OSRM_BASE_URL = "http://localhost:5001"
DEFAULT_PROFILE = "driving"
DEFAULT_MIN_MOVE_M = 8.0
DEFAULT_MAX_DETOUR_FACTOR = 4.0


def _iso(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _haversine_m(a, b):
    radius = 6371000.0
    lat1 = math.radians(a[1])
    lat2 = math.radians(b[1])
    dlat = math.radians(b[1] - a[1])
    dlng = math.radians(b[0] - a[0])
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 2 * radius * math.asin(min(1.0, math.sqrt(h)))


def _default_route_fetcher(base_url, profile, coordinates):
    # Imported lazily to avoid a hard dependency / import cycle for tests.
    from backend.services.garbage_vrp_service import _fetch_osrm_route

    geometry, _legs = _fetch_osrm_route(base_url, profile, coordinates)
    return geometry.get("coordinates") or []


def _routed_leg(pa, pb, base_url, profile, route_fetcher, leg_cache, straight_m, max_detour_factor):
    cache_key = (profile, round(pa[0], 5), round(pa[1], 5), round(pb[0], 5), round(pb[1], 5))
    if cache_key in leg_cache:
        return leg_cache[cache_key]

    coords = None
    try:
        coords = route_fetcher(base_url, profile, [[pa[0], pa[1]], [pb[0], pb[1]]])
    except Exception:  # pragma: no cover - network/OSRM failure -> fallback
        coords = None

    if not coords or len(coords) < 2:
        result = [pa, pb]
    else:
        routed_m = sum(_haversine_m(coords[i], coords[i + 1]) for i in range(len(coords) - 1))
        if straight_m > 0 and routed_m > straight_m * max_detour_factor:
            result = [pa, pb]
        else:
            result = [(c[0], c[1]) for c in coords]

    leg_cache[cache_key] = result
    return result


def _timestamp_leg(coords, ta, tb):
    if not coords:
        return []
    if len(coords) == 1:
        return [{"t": _iso(ta), "lng": coords[0][0], "lat": coords[0][1]}]

    cumulative = [0.0]
    for i in range(len(coords) - 1):
        cumulative.append(cumulative[-1] + _haversine_m(coords[i], coords[i + 1]))
    total = cumulative[-1]
    span_seconds = (tb - ta).total_seconds()

    out = []
    last = len(coords) - 1
    for i, coord in enumerate(coords):
        frac = (cumulative[i] / total) if total > 0 else (i / last)
        t = ta + timedelta(seconds=span_seconds * frac)
        out.append({"t": _iso(t), "lng": coord[0], "lat": coord[1]})
    return out


def build_entity_tracks(
    history_db,
    data_id,
    key_fields,
    frm,
    to,
    *,
    osrm_base_url=DEFAULT_OSRM_BASE_URL,
    profile=DEFAULT_PROFILE,
    route_fetcher=None,
    leg_cache=None,
    min_move_m=DEFAULT_MIN_MOVE_M,
    max_detour_factor=DEFAULT_MAX_DETOUR_FACTOR,
):
    route_fetcher = route_fetcher or _default_route_fetcher
    leg_cache = leg_cache if leg_cache is not None else {}

    raw = history_db.entity_tracks(data_id, key_fields, frm, to)
    tracks = []

    for key, info in raw.items():
        samples = info.get("samples") or []
        if not samples:
            continue

        if len(samples) == 1:
            s = samples[0]
            path = [{"t": _iso(s["t"]), "lng": s["lng"], "lat": s["lat"]}]
        else:
            path = []
            for i in range(len(samples) - 1):
                a = samples[i]
                b = samples[i + 1]
                pa = (a["lng"], a["lat"])
                pb = (b["lng"], b["lat"])
                straight_m = _haversine_m(pa, pb)
                if straight_m < min_move_m:
                    leg_coords = [pa, pb]
                else:
                    leg_coords = _routed_leg(
                        pa, pb, osrm_base_url, profile, route_fetcher, leg_cache, straight_m, max_detour_factor
                    )
                segment = _timestamp_leg(leg_coords, a["t"], b["t"])
                if path and segment:
                    segment = segment[1:]  # drop the vertex shared with previous leg
                path.extend(segment)

        # Per-node properties so playback can show the data of the most
        # recently passed capture (not just the latest snapshot).
        node_samples = [
            {"t": _iso(s["t"]), "properties": s.get("properties", {})} for s in samples
        ]
        tracks.append(
            {
                "key": key,
                "properties": info.get("properties", {}),
                "path": path,
                "samples": node_samples,
            }
        )

    return tracks
