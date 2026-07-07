"""OR-Tools model setup, solving, and per-route geometry/solution extraction."""

import logging
import time

try:
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2
except ImportError:  # pragma: no cover
    pywrapcp = None
    routing_enums_pb2 = None

from backend.geo.turn_instructions import leg_instructions
from backend.services.vrp.osrm_client import _build_route_geometry_from_osrm


logger = logging.getLogger(__name__)

UNREACHABLE_COST = 10**8
DEFAULT_DROP_PENALTY = 10**7


def _to_int_matrix(raw_matrix):
    matrix = []
    for row in raw_matrix:
        row_values = []
        for value in row:
            if value is None:
                row_values.append(UNREACHABLE_COST)
            else:
                row_values.append(int(max(0, round(value))))
        matrix.append(row_values)
    return matrix


def _attach_route_geometry(vehicle_stops, config):
    """OSRM road geometry + per-leg data/instructions for a stop sequence.

    Mutates the stops' leg fields on success and returns
    ``(geometry, geometry_source, geometry_fallback_reason)``; on any OSRM
    failure the straight-line geometry between stops is returned instead.
    Shared by the OR-Tools and PyVRP engines.
    """
    geometry = {
        "type": "LineString",
        "coordinates": [[stop["lng"], stop["lat"]] for stop in vehicle_stops],
    }
    geometry_source = "straight_fallback"
    geometry_fallback_reason = ""
    try:
        route_coordinates = [(stop["lng"], stop["lat"]) for stop in vehicle_stops]
        osrm_geometry, osrm_legs = _build_route_geometry_from_osrm(
            coordinates=route_coordinates,
            osrm_base_url=config.osrm_base_url,
            profile=config.profile,
            max_waypoints_per_call=config.route_max_waypoints_per_call,
            max_url_length=config.route_max_url_length,
        )
        geometry = osrm_geometry
        geometry_source = "osrm_route"
        for leg_index, leg in enumerate(osrm_legs):
            stop_index = leg_index + 1
            if stop_index >= len(vehicle_stops):
                break
            if not isinstance(leg, dict):
                continue
            if isinstance(leg.get("distance"), (int, float)):
                vehicle_stops[stop_index]["legFromPrevDistanceM"] = int(round(leg["distance"]))
            if isinstance(leg.get("duration"), (int, float)):
                vehicle_stops[stop_index]["legFromPrevDurationS"] = int(round(leg["duration"]))
            # 這一段（前一站 -> 本站）的逐步導航指示。
            vehicle_stops[stop_index]["instructions"] = leg_instructions(leg)
    except Exception as err:
        geometry_source = "straight_fallback"
        geometry_fallback_reason = str(err)
    return geometry, geometry_source, geometry_fallback_reason


def _solve_vrp(nodes, pickup_indices, disposal_indices, start_node_index, end_node_index, config, duration_matrix, distance_matrix):
    if pywrapcp is None or routing_enums_pb2 is None:
        raise RuntimeError("ortools is not installed")
    vehicle_capacities = [config.capacity_kg] * config.vehicle_count
    manager = pywrapcp.RoutingIndexManager(
        len(nodes),
        config.vehicle_count,
        [start_node_index] * config.vehicle_count,
        [end_node_index] * config.vehicle_count,
    )
    routing = pywrapcp.RoutingModel(manager)

    cost_matrix = duration_matrix if config.metric == "duration" else distance_matrix
    disposal_index_set = set(disposal_indices)

    # Registering the full matrix keeps cost lookups in C++; a Python transit
    # callback would cross the language boundary on every arc evaluation and
    # slash search throughput within the same time limit.
    arc_cost_matrix = [list(row) for row in cost_matrix]
    for from_node in disposal_index_set:
        arc_cost_matrix[from_node] = [value + config.disposal_visit_cost for value in arc_cost_matrix[from_node]]

    transit_index = routing.RegisterTransitMatrix(arc_cost_matrix)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_index)

    demands = [node.get("demand_int", 0) for node in nodes]
    demand_index = routing.RegisterUnaryTransitVector(demands)
    routing.AddDimensionWithVehicleCapacity(
        demand_index,
        config.capacity_kg,
        vehicle_capacities,
        True,
        "Load",
    )
    load_dimension = routing.GetDimensionOrDie("Load")

    # Allow unloading slack only at disposal nodes.
    for node_index in range(len(nodes)):
        index = manager.NodeToIndex(node_index)
        if index < 0:
            continue
        slack_var = load_dimension.SlackVar(index)
        if node_index in disposal_index_set:
            slack_var.SetRange(0, config.capacity_kg)
        else:
            slack_var.SetValue(0)

    for pickup_node in pickup_indices:
        index = manager.NodeToIndex(pickup_node)
        penalty = DEFAULT_DROP_PENALTY + max(0, demands[pickup_node] * 1000)
        routing.AddDisjunction([index], penalty)

    for disposal_node in disposal_indices:
        index = manager.NodeToIndex(disposal_node)
        routing.AddDisjunction([index], 0)

    search_params = pywrapcp.DefaultRoutingSearchParameters()
    search_params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    search_params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    search_params.time_limit.seconds = config.time_limit_sec
    search_params.log_search = False

    _solve_started = time.perf_counter()
    solution = routing.SolveWithParameters(search_params)
    ortools_seconds = time.perf_counter() - _solve_started
    if solution is None:
        raise LookupError("No feasible solution found")

    dropped_nodes = []
    pickup_index_set = set(pickup_indices)
    for node_index in pickup_indices:
        index = manager.NodeToIndex(node_index)
        if solution.Value(routing.NextVar(index)) == index:
            dropped_nodes.append(nodes[node_index])

    routes = []
    total_distance = 0
    total_duration = 0
    geometry_fallback_route_count = 0
    geometry_seconds = 0.0
    for vehicle_id in range(config.vehicle_count):
        index = routing.Start(vehicle_id)
        vehicle_stops = []
        route_distance = 0
        route_duration = 0
        visited_pickups = 0

        previous_node_index = None
        while not routing.IsEnd(index):
            node_index = manager.IndexToNode(index)
            node = nodes[node_index]
            next_index = solution.Value(routing.NextVar(index))
            next_node_index = manager.IndexToNode(next_index)

            depart_load = solution.Value(load_dimension.CumulVar(next_index))
            leg_distance = None
            leg_duration = None
            if previous_node_index is not None:
                leg_distance = int(distance_matrix[previous_node_index][node_index])
                leg_duration = int(duration_matrix[previous_node_index][node_index])

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
            if node_index in pickup_index_set:
                visited_pickups += 1

            route_distance += distance_matrix[node_index][next_node_index]
            route_duration += duration_matrix[node_index][next_node_index]
            previous_node_index = node_index
            index = next_index

        end_node_index_resolved = manager.IndexToNode(index)
        end_node = nodes[end_node_index_resolved]
        end_leg_distance = None
        end_leg_duration = None
        if previous_node_index is not None:
            end_leg_distance = int(distance_matrix[previous_node_index][end_node_index_resolved])
            end_leg_duration = int(duration_matrix[previous_node_index][end_node_index_resolved])
        vehicle_stops.append(
            {
                "location_id": end_node["id"],
                "name": end_node["name"],
                "type": end_node["type"],
                "lng": end_node["lng"],
                "lat": end_node["lat"],
                "load_kg": 0,
                "memberCount": 1,
                "legFromPrevDistanceM": end_leg_distance,
                "legFromPrevDurationS": end_leg_duration,
                "instructions": [],
            }
        )

        if visited_pickups > 0:
            _geometry_started = time.perf_counter()
            geometry, geometry_source, geometry_fallback_reason = _attach_route_geometry(vehicle_stops, config)
            if geometry_source == "straight_fallback":
                geometry_fallback_route_count += 1
            geometry_seconds += time.perf_counter() - _geometry_started

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

    logger.info(
        "VRP solver timings: nodes=%d vehicles=%d time_limit=%ds ortools=%.2fs geometry=%.2fs",
        len(nodes),
        config.vehicle_count,
        config.time_limit_sec,
        ortools_seconds,
        geometry_seconds,
    )

    return {
        "routes": routes,
        "dropped_nodes": dropped_nodes,
        "total_distance": int(total_distance),
        "total_duration": int(total_duration),
        "geometry_fallback_route_count": geometry_fallback_route_count,
    }
