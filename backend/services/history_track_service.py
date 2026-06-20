"""Build road-following, time-stamped tracks for history playback.

Each entity's captured position samples are turned into a dense polyline that
follows roads (via self-hosted OSRM) with a timestamp on every vertex, so the
frontend can interpolate a smooth position at any instant. Between two
consecutive samples (posA@tA -> posB@tB) the OSRM route geometry is fetched and
its vertices are time-stamped by cumulative-distance fraction of [tA, tB]
(constant-speed assumption along the road).

To keep the network cost low, every entity's samples are sent to OSRM in a
single batched request (see :func:`backend.geo.osrm.route_legs`), which returns
one road geometry per consecutive pair -- so an entity with 1000 samples costs
a handful of requests, not 999. Near-stationary legs skip routing entirely,
already-seen directed legs are served from a cache, and any leg falls back to a
straight segment when OSRM fails or returns an implausibly long detour.

Routing across all entities is planned first, de-duplicated, then issued to OSRM
concurrently with a bounded thread pool, so playback no longer waits on hundreds
of serial round-trips.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta, timezone

from backend.geo.geometry import haversine_m
from backend.geo.osrm import (
    DEFAULT_MAX_URL_LENGTH,
    DEFAULT_MAX_WAYPOINTS_PER_CALL,
    route_legs,
)

DEFAULT_OSRM_BASE_URL = "http://localhost:5001"
DEFAULT_PROFILE = "driving"
DEFAULT_MIN_MOVE_M = 8.0
DEFAULT_MAX_DETOUR_FACTOR = 4.0
# Number of OSRM route requests issued in parallel.
DEFAULT_OSRM_CONCURRENCY = 8
# A leg whose two captures are further apart in time than this is treated as a
# recording interruption: it is not routed, and the track is split into a new
# segment so playback never fabricates motion across the gap. None disables it.
DEFAULT_MAX_GAP_SECONDS = None


def _iso(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _point(sample):
    return {"t": _iso(sample["t"]), "lng": sample["lng"], "lat": sample["lat"]}


def _cache_key(profile, pa, pb):
    return (profile, round(pa[0], 5), round(pa[1], 5), round(pb[0], 5), round(pb[1], 5))


def _chain_key(profile, coordinates):
    return (profile,) + tuple((round(x, 5), round(y, 5)) for x, y in coordinates)


def _contiguous_runs(indices):
    """Group a sorted list of pair indices into maximal contiguous runs."""
    runs = []
    for i in indices:
        if runs and i == runs[-1][-1] + 1:
            runs[-1].append(i)
        else:
            runs.append([i])
    return runs


def _validate_leg(leg, pa, pb, straight_m, max_detour_factor):
    """Accept the routed geometry, or fall back to a straight segment."""
    if not leg or len(leg) < 2:
        return [pa, pb]
    routed_m = sum(haversine_m(leg[i], leg[i + 1]) for i in range(len(leg) - 1))
    if straight_m > 0 and routed_m > straight_m * max_detour_factor:
        return [pa, pb]
    return [(c[0], c[1]) for c in leg]


def _plan_entity_runs(samples, profile, leg_cache, min_move_m, breaks):
    """Decide each pair's leg without routing.

    Break and near-stationary pairs are filled with straight placeholders, cached
    pairs are reused, and the rest are grouped into maximal contiguous runs that
    still need OSRM. Returns ``(pairs, legs, runs)`` where ``runs`` is a list of
    ``(start, end, coordinates)``.
    """
    pairs = []
    for i in range(len(samples) - 1):
        pa = (samples[i]["lng"], samples[i]["lat"])
        pb = (samples[i + 1]["lng"], samples[i + 1]["lat"])
        pairs.append((pa, pb, haversine_m(pa, pb)))

    legs = [None] * len(pairs)
    needs_routing = []
    for i, (pa, pb, straight_m) in enumerate(pairs):
        if breaks[i]:
            legs[i] = [pa, pb]  # placeholder; a break leg is never rendered
            continue
        if straight_m < min_move_m:
            legs[i] = [pa, pb]
            continue
        cached = leg_cache.get(_cache_key(profile, pa, pb))
        if cached is not None:
            legs[i] = cached
            continue
        needs_routing.append(i)

    runs = []
    for run in _contiguous_runs(needs_routing):
        start, end = run[0], run[-1]
        coordinates = [pairs[start][0]] + [pairs[i][1] for i in range(start, end + 1)]
        runs.append((start, end, coordinates))
    return pairs, legs, runs


def _timestamp_leg(coords, ta, tb):
    if not coords:
        return []
    if len(coords) == 1:
        return [{"t": _iso(ta), "lng": coords[0][0], "lat": coords[0][1]}]

    cumulative = [0.0]
    for i in range(len(coords) - 1):
        cumulative.append(cumulative[-1] + haversine_m(coords[i], coords[i + 1]))
    total = cumulative[-1]
    span_seconds = (tb - ta).total_seconds()

    out = []
    last = len(coords) - 1
    for i, coord in enumerate(coords):
        frac = (cumulative[i] / total) if total > 0 else (i / last)
        t = ta + timedelta(seconds=span_seconds * frac)
        out.append({"t": _iso(t), "lng": coord[0], "lat": coord[1]})
    return out


def _segment(path):
    return {"from": path[0]["t"], "to": path[-1]["t"], "path": path}


def _assemble_segments(samples, leg_coords, breaks):
    """Stitch timestamped legs into continuous segments, split on breaks.

    A break leg ends the current segment and starts a fresh one at the leg's
    far endpoint, so the gap between two segments marks a recording interruption.
    """
    segments = []
    current = [_point(samples[0])]
    for i, coords in enumerate(leg_coords):
        if breaks[i]:
            segments.append(_segment(current))
            current = [_point(samples[i + 1])]
            continue
        leg = _timestamp_leg(coords, samples[i]["t"], samples[i + 1]["t"])
        current.extend(leg[1:])  # drop the vertex shared with the current tail
    segments.append(_segment(current))
    return segments


def build_entity_tracks(
    history_db,
    data_id,
    key_fields,
    frm,
    to,
    *,
    osrm_base_url=DEFAULT_OSRM_BASE_URL,
    profile=DEFAULT_PROFILE,
    leg_router=None,
    leg_cache=None,
    min_move_m=DEFAULT_MIN_MOVE_M,
    max_detour_factor=DEFAULT_MAX_DETOUR_FACTOR,
    max_gap_seconds=DEFAULT_MAX_GAP_SECONDS,
    max_waypoints_per_call=DEFAULT_MAX_WAYPOINTS_PER_CALL,
    max_url_length=DEFAULT_MAX_URL_LENGTH,
    max_concurrency=DEFAULT_OSRM_CONCURRENCY,
    progress_cb=None,
):
    if leg_router is None:
        def leg_router(b, p, coordinates):
            return route_legs(
                b,
                p,
                coordinates,
                max_waypoints_per_call=max_waypoints_per_call,
                max_url_length=max_url_length,
            )

    leg_cache = leg_cache if leg_cache is not None else {}

    raw = history_db.entity_tracks(data_id, key_fields, frm, to)

    # --- Phase 1: plan every entity; collect unique routing jobs. -------------
    plans = []
    jobs = {}  # chain_key -> coordinates (de-duplicated across all entities)
    for key, info in raw.items():
        samples = info.get("samples") or []
        if not samples:
            continue
        node_samples = [
            {"t": _iso(s["t"]), "properties": s.get("properties", {})} for s in samples
        ]
        plan = {"key": key, "info": info, "samples": samples, "node_samples": node_samples}
        if len(samples) > 1:
            plan["breaks"] = [
                max_gap_seconds is not None
                and (samples[i + 1]["t"] - samples[i]["t"]).total_seconds() > max_gap_seconds
                for i in range(len(samples) - 1)
            ]
            pairs, legs, runs = _plan_entity_runs(
                samples, profile, leg_cache, min_move_m, plan["breaks"]
            )
            named_runs = []
            for start, end, coordinates in runs:
                chain = _chain_key(profile, coordinates)
                jobs.setdefault(chain, coordinates)
                named_runs.append((start, end, chain))
            plan.update(pairs=pairs, legs=legs, runs=named_runs)
        plans.append(plan)

    # --- Phase 2: route all unique jobs concurrently. -------------------------
    total = len(jobs)
    if progress_cb:
        progress_cb(0, total)
    routed_by_chain = {}
    if jobs:
        done = 0
        with ThreadPoolExecutor(max_workers=min(max_concurrency, len(jobs))) as pool:
            future_to_chain = {
                pool.submit(leg_router, osrm_base_url, profile, coords): chain
                for chain, coords in jobs.items()
            }
            for future in as_completed(future_to_chain):
                chain = future_to_chain[future]
                try:
                    routed_by_chain[chain] = future.result()
                except Exception:  # pragma: no cover - network/OSRM failure -> fallback
                    routed_by_chain[chain] = None
                done += 1
                if progress_cb:
                    progress_cb(done, total)

    # --- Phase 3: assemble each entity's segments from the routed legs. -------
    tracks = []
    for plan in plans:
        samples = plan["samples"]
        if len(samples) == 1:
            segments = [_segment([_point(samples[0])])]
        else:
            pairs, legs = plan["pairs"], plan["legs"]
            for start, end, chain in plan["runs"]:
                routed = routed_by_chain.get(chain)
                for offset, i in enumerate(range(start, end + 1)):
                    pa, pb, straight_m = pairs[i]
                    leg = routed[offset] if routed and offset < len(routed) else None
                    resolved = _validate_leg(leg, pa, pb, straight_m, max_detour_factor)
                    legs[i] = resolved
                    leg_cache[_cache_key(profile, pa, pb)] = resolved
            segments = _assemble_segments(samples, legs, plan["breaks"])

        tracks.append(
            {
                "key": plan["key"],
                "properties": plan["info"].get("properties", {}),
                "segments": segments,
                "samples": plan["node_samples"],
            }
        )

    return tracks
