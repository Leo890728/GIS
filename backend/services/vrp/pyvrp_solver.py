"""PyVRP (HGS) solve engine, selected via ``solver.engine = "pyvrp"``.

Maps the same inputs as :func:`backend.services.vrp.solver._solve_vrp` onto
PyVRP's native concepts: pickups become prize-collecting clients, each unique
disposal point becomes a reload depot (replacing the OR-Tools disposal-clone
trick, so multi-trip counts are not capped), and the chosen metric matrix —
with the disposal visit cost baked into disposal rows — is fed as the cost
matrix so the objective matches the OR-Tools engine.
"""

import logging
import time

import numpy as np

try:
    from pyvrp import Client, Depot, ProblemData, VehicleType
    from pyvrp import solve as _pyvrp_solve
    from pyvrp.stop import MaxRuntime
except ImportError:  # pragma: no cover
    ProblemData = None

from backend.services.vrp.solver import DEFAULT_DROP_PENALTY, _attach_route_geometry


logger = logging.getLogger(__name__)


def _unique_disposal_indices(nodes, disposal_indices):
    """First clone index per disposal point (clones share the id base)."""
    unique = []
    seen = set()
    for index in disposal_indices:
        base_id = nodes[index]["id"].rsplit("-clone-", 1)[0]
        if base_id not in seen:
            seen.add(base_id)
            unique.append(index)
    return unique


def _solve_vrp_pyvrp(nodes, pickup_indices, disposal_indices, start_node_index, end_node_index, config, duration_matrix, distance_matrix):
    if ProblemData is None:
        raise RuntimeError("pyvrp is not installed")

    disposal_orig = _unique_disposal_indices(nodes, disposal_indices)
    # PyVRP requires depots at the low location indices: start, end, disposals,
    # then the pickup clients. orig_order maps location index -> nodes index.
    depot_orig = [start_node_index, end_node_index] + disposal_orig
    orig_order = depot_orig + list(pickup_indices)

    metric_matrix = duration_matrix if config.metric == "duration" else distance_matrix
    selection = np.ix_(orig_order, orig_order)
    cost = np.asarray(metric_matrix, dtype=np.int64)[selection].copy()
    durations = np.asarray(duration_matrix, dtype=np.int64)[selection].copy()

    # Same convention as the OR-Tools engine: every arc leaving a disposal
    # point carries the unload visit cost.
    disposal_locs = range(2, 2 + len(disposal_orig))
    for loc in disposal_locs:
        cost[loc, :] += config.disposal_visit_cost
    np.fill_diagonal(cost, 0)
    np.fill_diagonal(durations, 0)

    depots = [
        Depot(x=nodes[index]["lng"], y=nodes[index]["lat"], name=nodes[index]["id"])
        for index in depot_orig
    ]
    clients = []
    for index in pickup_indices:
        node = nodes[index]
        demand = int(node["demand_int"])
        clients.append(
            Client(
                x=node["lng"],
                y=node["lat"],
                pickup=[demand],
                required=False,
                prize=DEFAULT_DROP_PENALTY + max(0, demand * 1000),
                name=node["id"],
            )
        )

    vehicle_type = VehicleType(
        num_available=config.vehicle_count,
        capacity=[config.capacity_kg],
        start_depot=0,
        end_depot=1,
        reload_depots=list(disposal_locs),
        unit_distance_cost=1,
        unit_duration_cost=0,
    )

    data = ProblemData(clients, depots, [vehicle_type], [cost], [durations])

    solve_started = time.perf_counter()
    result = _pyvrp_solve(
        data,
        stop=MaxRuntime(config.time_limit_sec),
        seed=config.random_seed,
        collect_stats=False,
        display=False,
    )
    solve_seconds = time.perf_counter() - solve_started
    solution = result.best
    if solution is None or not solution.is_feasible():
        raise LookupError("No feasible solution found")

    visited_locs = set()
    routes = []
    total_distance = 0
    total_duration = 0
    geometry_fallback_route_count = 0
    geometry_seconds = 0.0

    for vehicle_id, route in enumerate(solution.routes()):
        vehicle_stops = []
        route_distance = 0
        route_duration = 0
        visited_pickups = 0
        previous_orig = None
        load_kg = 0

        def _append_stop(orig_index, depart_load):
            nonlocal previous_orig, route_distance, route_duration
            node = nodes[orig_index]
            leg_distance = None
            leg_duration = None
            if previous_orig is not None:
                leg_distance = int(distance_matrix[previous_orig][orig_index])
                leg_duration = int(duration_matrix[previous_orig][orig_index])
                route_distance += leg_distance
                route_duration += leg_duration
            vehicle_stops.append(
                {
                    "location_id": node["id"],
                    "name": node["name"],
                    "type": node["type"],
                    "lng": node["lng"],
                    "lat": node["lat"],
                    "load_kg": int(max(0, depart_load)),
                    "memberCount": int(node.get("member_count", 1)),
                    "legFromPrevDistanceM": leg_distance,
                    "legFromPrevDurationS": leg_duration,
                    "instructions": [],
                }
            )
            previous_orig = orig_index

        trips = route.trips()
        _append_stop(orig_order[route.start_depot()], 0)
        for trip_index, trip in enumerate(trips):
            for loc in trip.visits():
                visited_locs.add(loc)
                orig_index = orig_order[loc]
                load_kg += nodes[orig_index]["demand_int"]
                _append_stop(orig_index, load_kg)
                visited_pickups += 1
            if trip_index < len(trips) - 1:
                # Intermediate trip boundary: an unload visit at a reload depot.
                load_kg = 0
                _append_stop(orig_order[trip.end_depot()], 0)
        _append_stop(orig_order[route.end_depot()], 0)

        if visited_pickups == 0:
            continue

        geometry_started = time.perf_counter()
        geometry, geometry_source, geometry_fallback_reason = _attach_route_geometry(vehicle_stops, config)
        if geometry_source == "straight_fallback":
            geometry_fallback_route_count += 1
        geometry_seconds += time.perf_counter() - geometry_started

        routes.append(
            {
                "vehicle_id": f"truck-{vehicle_id + 1}",
                "distance_m": int(route_distance),
                "duration_s": int(route_duration),
                "stops": vehicle_stops,
                "geometry": geometry,
                "geometrySource": geometry_source,
                **(
                    {"geometryFallbackReason": geometry_fallback_reason}
                    if geometry_source == "straight_fallback"
                    else {}
                ),
            }
        )
        total_distance += route_distance
        total_duration += route_duration

    dropped_nodes = [
        nodes[orig_order[loc]]
        for loc in range(len(depot_orig), len(orig_order))
        if loc not in visited_locs
    ]

    logger.info(
        "VRP solver timings (pyvrp): nodes=%d clients=%d vehicles=%d time_limit=%ds pyvrp=%.2fs geometry=%.2fs",
        len(nodes),
        len(clients),
        config.vehicle_count,
        config.time_limit_sec,
        solve_seconds,
        geometry_seconds,
    )

    return {
        "routes": routes,
        "dropped_nodes": dropped_nodes,
        "total_distance": int(total_distance),
        "total_duration": int(total_duration),
        "geometry_fallback_route_count": geometry_fallback_route_count,
    }
