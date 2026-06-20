"""Region coverage over time for history playback analytics.

Coverage% at a capture = (# service regions with >=1 vehicle) / (# service
regions), where *service regions* are the admin areas (default: township) the
fleet touches anywhere in the requested window -- a data-driven denominator, so
"coverage" means "of the areas this fleet actually serves, how many are being
serviced right now". A *coverage drop* anomaly flags captures whose coverage
falls notably below the window's own norm.

Coverage is sampled at capture frames only (not animation ticks). Region
polygons are injected so this module stays free of any SpatiaLite dependency and
is unit-testable; the route supplies real geometry via RegionsService.
"""

import statistics
from datetime import timezone

from backend.geo.geometry import point_in_geometry

DEFAULT_ANOMALY_K = 1.5
MIN_FRAMES_FOR_ANOMALY = 4


def _iso(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _bbox(geometry):
    """Axis-aligned bounds (minx, miny, maxx, maxy) of a Polygon/MultiPolygon."""
    minx = miny = float("inf")
    maxx = maxy = float("-inf")

    def walk(coords):
        nonlocal minx, miny, maxx, maxy
        if not coords:
            return
        if isinstance(coords[0], (int, float)):
            x, y = coords[0], coords[1]
            minx, miny = min(minx, x), min(miny, y)
            maxx, maxy = max(maxx, x), max(maxy, y)
            return
        for c in coords:
            walk(c)

    walk((geometry or {}).get("coordinates"))
    return (minx, miny, maxx, maxy)


def prepare_regions(features):
    """Pre-compute bbox prefilters for a list of region GeoJSON features.

    Each feature needs ``properties`` with a stable ``code`` (and optional
    ``name``) plus a Polygon/MultiPolygon ``geometry``.
    """
    regions = []
    for feature in features or []:
        geometry = feature.get("geometry")
        props = feature.get("properties") or {}
        code = props.get("code") or props.get("CODE")
        if not geometry or not code:
            continue
        regions.append(
            {
                "code": code,
                "name": props.get("name") or props.get("NAME") or code,
                "geometry": geometry,
                "bbox": _bbox(geometry),
            }
        )
    return regions


def _region_of(lng, lat, regions):
    for region in regions:
        minx, miny, maxx, maxy = region["bbox"]
        if lng < minx or lng > maxx or lat < miny or lat > maxy:
            continue
        if point_in_geometry(lng, lat, region["geometry"]):
            return region["code"]
    return None


def compute_coverage(frames_positions, regions, *, anomaly_k=DEFAULT_ANOMALY_K):
    """Coverage% series + coverage-drop anomalies.

    ``frames_positions`` is a list of ``(datetime, [(lng, lat), ...])`` -- one
    entry per capture frame with that frame's vehicle positions. ``regions``
    comes from :func:`prepare_regions`. Returns
    ``{totalRegions, series, anomalies, regions}``.
    """
    per_frame = []
    union = set()
    last_seen = {}
    for t, positions in frames_positions:
        covered = set()
        for lng, lat in positions:
            code = _region_of(lng, lat, regions)
            if code is not None:
                covered.add(code)
        per_frame.append((t, covered))
        union |= covered
        for code in covered:
            last_seen[code] = t

    denom = len(union) or 1
    series = [
        {"t": _iso(t), "covered": len(covered), "pct": round(len(covered) / denom, 4)}
        for t, covered in per_frame
    ]

    anomalies = []
    pcts = [s["pct"] for s in series]
    if len(pcts) >= MIN_FRAMES_FOR_ANOMALY:
        mean = statistics.fmean(pcts)
        std = statistics.pstdev(pcts)
        if std > 0:
            threshold = mean - anomaly_k * std
            for entry in series:
                if entry["pct"] < threshold:
                    anomalies.append(
                        {"t": entry["t"], "pct": entry["pct"], "reason": "coverage_drop"}
                    )

    name_by_code = {r["code"]: r["name"] for r in regions}
    region_summary = [
        {"code": code, "name": name_by_code.get(code, code), "lastSeen": _iso(t)}
        for code, t in sorted(last_seen.items(), key=lambda kv: kv[1], reverse=True)
    ]

    return {
        "totalRegions": denom,
        "series": series,
        "anomalies": anomalies,
        "regions": region_summary,
    }
