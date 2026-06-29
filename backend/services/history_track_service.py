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

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import timedelta, timezone
from typing import Callable, Optional

from backend.geo.geometry import haversine_m
from backend.geo.osrm import (
    DEFAULT_MAX_URL_LENGTH,
    DEFAULT_MAX_WAYPOINTS_PER_CALL,
    route_legs,
)

logger = logging.getLogger(__name__)

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


@dataclass
class TrackBuildOptions:
    """Tunables for :func:`build_entity_tracks`, threaded through every phase."""

    osrm_base_url: str = DEFAULT_OSRM_BASE_URL
    profile: str = DEFAULT_PROFILE
    min_move_m: float = DEFAULT_MIN_MOVE_M
    max_detour_factor: float = DEFAULT_MAX_DETOUR_FACTOR
    max_gap_seconds: Optional[float] = DEFAULT_MAX_GAP_SECONDS
    max_waypoints_per_call: int = DEFAULT_MAX_WAYPOINTS_PER_CALL
    max_url_length: int = DEFAULT_MAX_URL_LENGTH
    max_concurrency: int = DEFAULT_OSRM_CONCURRENCY
    progress_cb: Optional[Callable[[int, int], None]] = None


@dataclass
class _TrackPlan:
    """One entity's planning state, carried from planning into assembly.

    ``breaks``/``pairs``/``runs`` stay ``None`` for single-sample entities, which
    have nothing to route. ``runs`` is a list of ``(start, end, chain)``.
    """

    key: object
    info: dict
    samples: list
    node_samples: list
    breaks: Optional[list] = None
    pairs: Optional[list] = None
    runs: Optional[list] = None


def _iso(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _point(sample):
    return {"t": _iso(sample["t"]), "lng": sample["lng"], "lat": sample["lat"]}


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


def _plan_entity_runs(samples, min_move_m, breaks):
    """Group an entity's samples into routing runs.

    A run is a maximal block of consecutive pairs *between recording gaps*
    (breaks). Near-stationary points are kept inside the run as OSRM waypoints so
    one continuous session is a single request (preserving stop-and-go timing)
    rather than being fragmented at every short hop. A block with no real move
    (all hops < ``min_move_m``) is skipped entirely. Returns ``(pairs, runs)``
    where ``runs`` is a list of ``(start, end, coordinates)``.
    """
    pairs = []
    for i in range(len(samples) - 1):
        pa = (samples[i]["lng"], samples[i]["lat"])
        pb = (samples[i + 1]["lng"], samples[i + 1]["lat"])
        pairs.append((pa, pb, haversine_m(pa, pb)))

    non_break = [i for i in range(len(pairs)) if not breaks[i]]
    runs = []
    for block in _contiguous_runs(non_break):
        start, end = block[0], block[-1]
        if not any(pairs[i][2] >= min_move_m for i in range(start, end + 1)):
            continue  # whole block is stationary -> nothing worth routing
        coordinates = [pairs[start][0]] + [pairs[i][1] for i in range(start, end + 1)]
        runs.append((start, end, coordinates))
    return pairs, runs


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


def _plan_track_jobs(raw, options, leg_cache):
    """Phase 1: plan every entity and collect unique, uncached routing jobs.

    Returns ``(plans, jobs)`` where ``jobs`` maps a ``chain_key`` to its
    coordinates, de-duplicated across all entities and skipping cache hits.
    """
    plans = []
    jobs = {}  # chain_key -> coordinates (de-duplicated across all entities)
    for key, info in raw.items():
        samples = info.get("samples") or []
        if not samples:
            continue
        node_samples = [
            {"t": _iso(s["t"]), "properties": s.get("properties", {})} for s in samples
        ]
        plan = _TrackPlan(key=key, info=info, samples=samples, node_samples=node_samples)
        if len(samples) > 1:
            plan.breaks = [
                options.max_gap_seconds is not None
                and (samples[i + 1]["t"] - samples[i]["t"]).total_seconds() > options.max_gap_seconds
                for i in range(len(samples) - 1)
            ]
            pairs, runs = _plan_entity_runs(samples, options.min_move_m, plan.breaks)
            named_runs = []
            for start, end, coordinates in runs:
                chain = _chain_key(options.profile, coordinates)
                if chain not in leg_cache:
                    jobs.setdefault(chain, coordinates)
                named_runs.append((start, end, chain))
            plan.pairs = pairs
            plan.runs = named_runs
        plans.append(plan)
    return plans, jobs


def _route_track_jobs(jobs, leg_router, leg_cache, options):
    """Phase 2: route all unique jobs concurrently; cache successes.

    Returns ``results`` mapping ``chain_key -> legs`` (or ``None`` on failure),
    seeded with cross-build cache hits.
    """
    total = len(jobs)
    if options.progress_cb:
        options.progress_cb(0, total)
    results = dict(leg_cache)  # seed with cross-build cache hits (chain -> legs)
    if jobs:
        done = 0
        with ThreadPoolExecutor(max_workers=min(options.max_concurrency, len(jobs))) as pool:
            future_to_chain = {
                pool.submit(leg_router, options.osrm_base_url, options.profile, coords): chain
                for chain, coords in jobs.items()
            }
            for future in as_completed(future_to_chain):
                chain = future_to_chain[future]
                try:
                    routed = future.result()
                except Exception as err:  # network/OSRM failure -> straight-segment fallback
                    logger.warning(
                        "OSRM leg routing failed (%s); falling back to straight segments", err
                    )
                    routed = None
                results[chain] = routed
                if routed is not None:
                    leg_cache[chain] = routed
                done += 1
                if options.progress_cb:
                    options.progress_cb(done, total)
    return results


def _assemble_track_results(plans, results, options):
    """Phase 3: assemble each entity's timestamped segments from routed legs."""
    tracks = []
    for plan in plans:
        samples = plan.samples
        if len(samples) == 1:
            segments = [_segment([_point(samples[0])])]
        else:
            pairs = plan.pairs
            # Default every leg to a straight segment (covers breaks, stationary
            # hops, and routing fallbacks); routed runs override the real moves.
            legs = [[pa, pb] for (pa, pb, _straight) in pairs]
            for start, end, chain in plan.runs:
                routed = results.get(chain)
                for offset, i in enumerate(range(start, end + 1)):
                    pa, pb, straight_m = pairs[i]
                    if straight_m < options.min_move_m:
                        continue  # keep stationary hop straight (anti-jitter)
                    leg = routed[offset] if routed and offset < len(routed) else None
                    legs[i] = _validate_leg(leg, pa, pb, straight_m, options.max_detour_factor)
            segments = _assemble_segments(samples, legs, plan.breaks)

        tracks.append(
            {
                "key": plan.key,
                "properties": plan.info.get("properties", {}),
                "segments": segments,
                "samples": plan.node_samples,
            }
        )
    return tracks


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
    """Build road-following, time-stamped tracks per entity (plan/route/assemble).

    Keyword signature is preserved for callers; the work is delegated to the
    three phase functions through a :class:`TrackBuildOptions` bundle.
    """
    options = TrackBuildOptions(
        osrm_base_url=osrm_base_url,
        profile=profile,
        min_move_m=min_move_m,
        max_detour_factor=max_detour_factor,
        max_gap_seconds=max_gap_seconds,
        max_waypoints_per_call=max_waypoints_per_call,
        max_url_length=max_url_length,
        max_concurrency=max_concurrency,
        progress_cb=progress_cb,
    )

    if leg_router is None:
        def leg_router(b, p, coordinates):
            return route_legs(
                b,
                p,
                coordinates,
                max_waypoints_per_call=options.max_waypoints_per_call,
                max_url_length=options.max_url_length,
            )

    leg_cache = leg_cache if leg_cache is not None else {}

    raw = history_db.entity_tracks(data_id, key_fields, frm, to)
    plans, jobs = _plan_track_jobs(raw, options, leg_cache)
    results = _route_track_jobs(jobs, leg_router, leg_cache, options)
    return _assemble_track_results(plans, results, options)
