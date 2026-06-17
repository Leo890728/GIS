import math
from dataclasses import dataclass

import httpx
try:
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2
except ImportError:  # pragma: no cover
    pywrapcp = None
    routing_enums_pb2 = None

from backend.services.point_query import query_points
from backend.services.regions_service import split_codes


OSRM_TIMEOUT_SECONDS = 20
UNREACHABLE_COST = 10**8
DEFAULT_DROP_PENALTY = 10**7
ROUTE_CHUNK_MAX_WAYPOINTS_DEFAULT = 1500
ROUTE_CHUNK_MAX_URL_LENGTH_DEFAULT = 7800
DISPOSAL_VISIT_COST_DEFAULT = 300
DISPOSAL_MAX_CANDIDATES_DEFAULT = 1
SNAP_TO_ROAD_MAX_DISTANCE_METERS_DEFAULT = 200.0


def _as_dict(value, field_name):
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be an object")
    return value


def _as_string(value, field_name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} is required")
    return value.strip()


def _as_bool(value, default=False):
    if value is None:
        return default
    return value is True


def _as_int(value, field_name, minimum=None, default=None):
    if value is None:
        if default is not None:
            return default
        raise ValueError(f"{field_name} is required")
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be an integer")
    if minimum is not None and parsed < minimum:
        raise ValueError(f"{field_name} must be >= {minimum}")
    return parsed


def _as_float(value, field_name, minimum=None, default=None):
    if value is None:
        if default is not None:
            return default
        raise ValueError(f"{field_name} is required")
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a number")
    if minimum is not None and parsed < minimum:
        raise ValueError(f"{field_name} must be >= {minimum}")
    return parsed


def _parse_coord(value, field_name):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{field_name} must be [lng, lat]")
    lng = _as_float(value[0], f"{field_name}[0]")
    lat = _as_float(value[1], f"{field_name}[1]")
    if not -180 <= lng <= 180:
        raise ValueError(f"{field_name}[0] must be a valid longitude")
    if not -90 <= lat <= 90:
        raise ValueError(f"{field_name}[1] must be a valid latitude")
    return [lng, lat]


def _get_point(feature):
    coordinates = feature.get("geometry", {}).get("coordinates") or [None, None]
    return coordinates[0], coordinates[1]


def _feature_collection(features):
    return {"type": "FeatureCollection", "features": features}


def _build_codes(range_payload):
    return {
        "county_codes": split_codes(range_payload.get("countyCodes")),
        "town_codes": split_codes(range_payload.get("townCodes")),
        "village_codes": split_codes(range_payload.get("villageCodes")),
        "stat_zone_codes": split_codes(range_payload.get("statZoneCodes") or range_payload.get("statZoneMinCodes")),
    }


def _build_range_geojson(range_payload, regions_service):
    geojson = range_payload.get("geojson")
    if geojson is not None:
        if not isinstance(geojson, dict):
            raise ValueError("range.geojson must be a GeoJSON object")
        return geojson

    codes = _build_codes(range_payload)
    has_codes = any(codes[key] for key in codes)
    if not has_codes:
        return None
    return regions_service.build_range_geojson(
        codes["county_codes"],
        codes["town_codes"],
        codes["village_codes"],
        codes["stat_zone_codes"],
    )


def _grid_index(lng, lat, cell_meters):
    meters_per_degree_lat = 111_320.0
    lat_rad = math.radians(lat)
    meters_per_degree_lng = max(1e-9, meters_per_degree_lat * math.cos(lat_rad))
    cell_lat = cell_meters / meters_per_degree_lat
    cell_lng = cell_meters / meters_per_degree_lng
    return int(math.floor(lng / cell_lng)), int(math.floor(lat / cell_lat))


def _aggregate_pickup_nodes(nodes, enabled, cell_meters, max_nodes_before_aggregate):
    if not enabled or len(nodes) <= max_nodes_before_aggregate:
        return nodes, False

    grouped = {}
    for node in nodes:
        lng = node["lng"]
        lat = node["lat"]
        demand_kg = node["demand_kg"]
        key = _grid_index(lng, lat, cell_meters)
        bucket = grouped.setdefault(
            key,
            {
                "sum_demand": 0.0,
                "sum_lng_x_demand": 0.0,
                "sum_lat_x_demand": 0.0,
                "member_count": 0,
                "sample_source_id": node["source_id"],
            },
        )
        bucket["sum_demand"] += demand_kg
        bucket["sum_lng_x_demand"] += lng * demand_kg
        bucket["sum_lat_x_demand"] += lat * demand_kg
        bucket["member_count"] += 1

    aggregated = []
    for index, bucket in enumerate(grouped.values()):
        sum_demand = bucket["sum_demand"]
        if sum_demand <= 0:
            continue
        aggregated.append(
            {
                "id": f"agg-{index}",
                "type": "pickup",
                "name": f"Aggregated cell {index + 1}",
                "lng": bucket["sum_lng_x_demand"] / sum_demand,
                "lat": bucket["sum_lat_x_demand"] / sum_demand,
                "demand_kg": sum_demand,
                "member_count": bucket["member_count"],
                "source_id": bucket["sample_source_id"],
            }
        )
    return aggregated, True


def _collect_preset_nodes(node_source, range_payload, range_geojson, regions_service, apply_geojson_filter):
    preset = node_source.get("preset") or "stat_zone_population_points"
    if preset != "stat_zone_population_points":
        raise ValueError("nodeSource.preset must be stat_zone_population_points")

    codes = _build_codes(range_payload)
    features = regions_service.query_stat_zone_population_points(
        stat_zone_codes=codes["stat_zone_codes"],
        county_codes=codes["county_codes"],
        town_codes=codes["town_codes"],
        village_codes=codes["village_codes"],
        limit=node_source.get("limit"),
    )

    if apply_geojson_filter and range_geojson:
        features = query_points(features, {"range": range_geojson})
    return features


def _collect_dataset_nodes(node_source, range_geojson, dataset_service):
    data_id = _as_string(node_source.get("dataId"), "nodeSource.dataId")
    payload = {}
    if range_geojson:
        payload["range"] = range_geojson
    if node_source.get("filters") is not None:
        if not isinstance(node_source["filters"], dict):
            raise ValueError("nodeSource.filters must be an object")
        payload["filters"] = node_source["filters"]
    if node_source.get("limit") is not None:
        payload["limit"] = _as_int(node_source.get("limit"), "nodeSource.limit", minimum=1)
    return dataset_service.query(data_id, payload)


def _collect_disposal_nodes(disposal_payload, dataset_service):
    source_data_id = disposal_payload.get("sourceDataId") or "moenv_incinerators"
    if not isinstance(source_data_id, str) or not source_data_id.strip():
        raise ValueError("disposal.sourceDataId must be a string")
    policy = disposal_payload.get("policy") or "nearest_auto"
    if policy != "nearest_auto":
        raise ValueError("disposal.policy must be nearest_auto")

    query_payload = {"limit": 1000}
    filters = disposal_payload.get("filters")
    if filters is not None:
        if not isinstance(filters, dict):
            raise ValueError("disposal.filters must be an object")
        query_payload["filters"] = filters

    features = dataset_service.query(source_data_id, query_payload)
    nodes = []
    for feature in features:
        lng, lat = _get_point(feature)
        if not isinstance(lng, (int, float)) or not isinstance(lat, (int, float)):
            continue
        properties = feature.get("properties", {})
        feature_id = feature.get("id") or properties.get("wepno") or properties.get("id")
        if not feature_id:
            continue
        nodes.append(
            {
                "id": f"disposal-{feature_id}",
                "type": "disposal",
                "name": str(properties.get("icnrtname") or properties.get("name_zh") or feature_id),
                "lng": float(lng),
                "lat": float(lat),
                "demand_kg": 0,
            }
        )
    return nodes


def _approx_distance_m(coord_a, coord_b):
    lng_a, lat_a = coord_a
    lng_b, lat_b = coord_b
    meters_per_degree_lat = 111_320.0
    avg_lat_rad = math.radians((lat_a + lat_b) / 2.0)
    meters_per_degree_lng = max(1e-9, meters_per_degree_lat * math.cos(avg_lat_rad))
    delta_lng_m = (lng_a - lng_b) * meters_per_degree_lng
    delta_lat_m = (lat_a - lat_b) * meters_per_degree_lat
    return math.hypot(delta_lng_m, delta_lat_m)


def _select_nearest_disposal_nodes(disposal_nodes, anchor_coord, max_candidates):
    if max_candidates <= 0:
        return []
    if len(disposal_nodes) <= max_candidates:
        return disposal_nodes
    sorted_nodes = sorted(
        disposal_nodes,
        key=lambda node: _approx_distance_m(anchor_coord, (node["lng"], node["lat"])),
    )
    return sorted_nodes[:max_candidates]


def _build_pickup_nodes(features, demand_field, demand_multiplier_kg):
    nodes = []
    for feature in features:
        properties = feature.get("properties", {})
        raw_demand = properties.get(demand_field)
        try:
            numeric_demand = float(raw_demand)
        except (TypeError, ValueError):
            continue
        demand_kg = numeric_demand * demand_multiplier_kg
        if demand_kg <= 0:
            continue
        lng, lat = _get_point(feature)
        if not isinstance(lng, (int, float)) or not isinstance(lat, (int, float)):
            continue
        feature_id = feature.get("id") or properties.get("id") or properties.get(demand_field)
        nodes.append(
            {
                "id": f"pickup-{feature_id}",
                "type": "pickup",
                "name": str(properties.get("name_zh") or properties.get("name") or feature_id),
                "lng": float(lng),
                "lat": float(lat),
                "demand_kg": demand_kg,
                "member_count": 1,
                "source_id": str(feature_id),
            }
        )
    return nodes


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


def _snap_pickup_nodes_to_road(nodes, enabled, max_distance_m, osrm_base_url, profile):
    if not enabled or not nodes:
        return nodes, 0
    snapped_count = 0
    snapped_nodes = []
    nearest_cache = {}
    for node in nodes:
        cache_key = (round(float(node["lng"]), 7), round(float(node["lat"]), 7))
        if cache_key not in nearest_cache:
            try:
                nearest_cache[cache_key] = _fetch_osrm_nearest(
                    osrm_base_url=osrm_base_url,
                    profile=profile,
                    coordinate=(float(node["lng"]), float(node["lat"])),
                )
            except Exception:
                nearest_cache[cache_key] = None
        snapped = nearest_cache[cache_key]
        if snapped is None:
            snapped_nodes.append(node)
            continue
        if snapped["distance_m"] > max_distance_m:
            snapped_nodes.append(node)
            continue
        snapped_nodes.append(
            {
                **node,
                "lng": snapped["lng"],
                "lat": snapped["lat"],
            }
        )
        snapped_count += 1
    return snapped_nodes, snapped_count


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


@dataclass
class _SolveConfig:
    vehicle_count: int
    capacity_kg: int
    time_limit_sec: int
    random_seed: int
    metric: str
    profile: str
    osrm_base_url: str
    route_max_waypoints_per_call: int
    route_max_url_length: int
    disposal_visit_cost: int
    disposal_max_candidates: int
    aggregate_enabled: bool
    aggregate_cell_meters: float
    aggregate_threshold: int
    snap_to_road_enabled: bool
    snap_to_road_max_distance_m: float


def _parse_config(payload):
    depot_payload = _as_dict(payload.get("depot"), "depot")
    start = _parse_coord(depot_payload.get("start"), "depot.start")
    end = _parse_coord(depot_payload.get("end"), "depot.end")

    vehicles_payload = _as_dict(payload.get("vehicles"), "vehicles")
    vehicle_count = _as_int(vehicles_payload.get("count"), "vehicles.count", minimum=1)
    capacity_kg = _as_int(vehicles_payload.get("capacityKg"), "vehicles.capacityKg", minimum=1)

    cost_payload = _as_dict(payload.get("cost"), "cost")
    cost_mode = cost_payload.get("mode") or "osrm"
    if cost_mode != "osrm":
        raise ValueError("cost.mode must be osrm")
    metric = cost_payload.get("metric") or "duration"
    if metric not in {"duration", "distance"}:
        raise ValueError("cost.metric must be duration or distance")
    profile = cost_payload.get("profile") or "driving"
    osrm_base_url = cost_payload.get("osrmBaseUrl") or "http://localhost:5002"
    route_max_waypoints_per_call = _as_int(
        cost_payload.get("routeMaxWaypointsPerCall"),
        "cost.routeMaxWaypointsPerCall",
        minimum=2,
        default=ROUTE_CHUNK_MAX_WAYPOINTS_DEFAULT,
    )
    route_max_url_length = _as_int(
        cost_payload.get("routeMaxUrlLength"),
        "cost.routeMaxUrlLength",
        minimum=1024,
        default=ROUTE_CHUNK_MAX_URL_LENGTH_DEFAULT,
    )
    disposal_payload = payload.get("disposal") or {}
    if disposal_payload and not isinstance(disposal_payload, dict):
        raise ValueError("disposal must be an object")
    disposal_visit_cost = _as_int(
        disposal_payload.get("visitCost"),
        "disposal.visitCost",
        minimum=0,
        default=DISPOSAL_VISIT_COST_DEFAULT,
    )
    disposal_max_candidates = _as_int(
        disposal_payload.get("maxCandidates"),
        "disposal.maxCandidates",
        minimum=1,
        default=DISPOSAL_MAX_CANDIDATES_DEFAULT,
    )

    solver_payload = payload.get("solver") or {}
    if not isinstance(solver_payload, dict):
        raise ValueError("solver must be an object")
    time_limit_sec = _as_int(solver_payload.get("timeLimitSec"), "solver.timeLimitSec", minimum=1, default=15)
    random_seed = _as_int(solver_payload.get("randomSeed"), "solver.randomSeed", minimum=0, default=0)

    aggregation_payload = payload.get("aggregation") or {}
    if not isinstance(aggregation_payload, dict):
        raise ValueError("aggregation must be an object")
    aggregate_enabled = _as_bool(aggregation_payload.get("enabled"), default=False)
    aggregate_cell_meters = _as_float(
        aggregation_payload.get("cellMeters"),
        "aggregation.cellMeters",
        minimum=10.0,
        default=500.0,
    )
    aggregate_threshold = _as_int(
        aggregation_payload.get("maxNodesBeforeAggregate"),
        "aggregation.maxNodesBeforeAggregate",
        minimum=10,
        default=500,
    )
    snap_to_road_payload = aggregation_payload.get("snapToRoad") or {}
    if snap_to_road_payload and not isinstance(snap_to_road_payload, dict):
        raise ValueError("aggregation.snapToRoad must be an object")
    snap_to_road_enabled = _as_bool(snap_to_road_payload.get("enabled"), default=False)
    snap_to_road_max_distance_m = _as_float(
        snap_to_road_payload.get("maxDistanceMeters"),
        "aggregation.snapToRoad.maxDistanceMeters",
        minimum=0.0,
        default=SNAP_TO_ROAD_MAX_DISTANCE_METERS_DEFAULT,
    )

    return (
        _SolveConfig(
            vehicle_count=vehicle_count,
            capacity_kg=capacity_kg,
            time_limit_sec=time_limit_sec,
            random_seed=random_seed,
            metric=metric,
            profile=profile,
            osrm_base_url=osrm_base_url,
            route_max_waypoints_per_call=route_max_waypoints_per_call,
            route_max_url_length=route_max_url_length,
            disposal_visit_cost=disposal_visit_cost,
            disposal_max_candidates=disposal_max_candidates,
            aggregate_enabled=aggregate_enabled,
            aggregate_cell_meters=aggregate_cell_meters,
            aggregate_threshold=aggregate_threshold,
            snap_to_road_enabled=snap_to_road_enabled,
            snap_to_road_max_distance_m=snap_to_road_max_distance_m,
        ),
        start,
        end,
    )


def _build_vrp_nodes(start_coord, end_coord, pickup_nodes, disposal_nodes, capacity_kg):
    total_demand = sum(node["demand_kg"] for node in pickup_nodes)
    clones_per_disposal = max(1, min(20, int(math.ceil(total_demand / max(1, capacity_kg)))))

    nodes = [
        {"id": "depot-start", "type": "depot", "name": "Depot Start", "lng": start_coord[0], "lat": start_coord[1], "demand_int": 0},
        *[
            {
                **pickup,
                "demand_int": int(max(1, round(pickup["demand_kg"]))),
            }
            for pickup in pickup_nodes
        ],
    ]

    disposal_indices = []
    for disposal in disposal_nodes:
        for clone_idx in range(clones_per_disposal):
            nodes.append(
                {
                    "id": f"{disposal['id']}-clone-{clone_idx + 1}",
                    "type": "disposal",
                    "name": disposal["name"],
                    "lng": disposal["lng"],
                    "lat": disposal["lat"],
                    "demand_int": -capacity_kg,
                    "demand_kg": 0,
                }
            )
            disposal_indices.append(len(nodes) - 1)

    end_index = len(nodes)
    nodes.append(
        {
            "id": "depot-end",
            "type": "depot",
            "name": "Depot End",
            "lng": end_coord[0],
            "lat": end_coord[1],
            "demand_int": 0,
        }
    )

    pickup_indices = [index for index, node in enumerate(nodes) if node["type"] == "pickup"]
    return nodes, pickup_indices, disposal_indices, 0, end_index


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

    def transit_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        cost = cost_matrix[from_node][to_node]
        if from_node in disposal_index_set:
            cost += config.disposal_visit_cost
        return cost

    transit_index = routing.RegisterTransitCallback(transit_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_index)

    demands = [node.get("demand_int", 0) for node in nodes]

    def demand_callback(from_index):
        from_node = manager.IndexToNode(from_index)
        return demands[from_node]

    demand_index = routing.RegisterUnaryTransitCallback(demand_callback)
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

    solution = routing.SolveWithParameters(search_params)
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
            }
        )

        if visited_pickups > 0:
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
            except Exception as err:
                geometry_source = "straight_fallback"
                geometry_fallback_reason = str(err)
                geometry_fallback_route_count += 1

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

    return {
        "routes": routes,
        "dropped_nodes": dropped_nodes,
        "total_distance": int(total_distance),
        "total_duration": int(total_duration),
        "geometry_fallback_route_count": geometry_fallback_route_count,
    }


def solve_garbage_vrp(payload, dataset_service, regions_service):
    payload = _as_dict(payload, "Body")
    node_source = _as_dict(payload.get("nodeSource"), "nodeSource")
    range_payload = _as_dict(payload.get("range"), "range")
    disposal_payload = _as_dict(payload.get("disposal"), "disposal")
    has_explicit_geojson = isinstance(range_payload.get("geojson"), dict)

    config, start_coord, end_coord = _parse_config(payload)
    range_geojson = _build_range_geojson(range_payload, regions_service)

    mode = node_source.get("mode") or "preset"
    demand_field = _as_string(node_source.get("demandField"), "nodeSource.demandField")
    demand_multiplier_kg = _as_float(
        node_source.get("demandMultiplierKg"),
        "nodeSource.demandMultiplierKg",
        minimum=0.000001,
    )

    if mode == "preset":
        features = _collect_preset_nodes(
            node_source,
            range_payload,
            range_geojson,
            regions_service,
            has_explicit_geojson,
        )
    elif mode == "dataset":
        features = _collect_dataset_nodes(node_source, range_geojson, dataset_service)
    else:
        raise ValueError("nodeSource.mode must be preset or dataset")

    pickup_nodes = _build_pickup_nodes(features, demand_field=demand_field, demand_multiplier_kg=demand_multiplier_kg)
    raw_node_count = len(pickup_nodes)
    if raw_node_count == 0:
        raise LookupError("No valid pickup nodes in selected range")

    pickup_nodes, snapped_node_count = _snap_pickup_nodes_to_road(
        pickup_nodes,
        enabled=config.snap_to_road_enabled,
        max_distance_m=config.snap_to_road_max_distance_m,
        osrm_base_url=config.osrm_base_url,
        profile=config.profile,
    )

    pickup_nodes, aggregated = _aggregate_pickup_nodes(
        pickup_nodes,
        enabled=config.aggregate_enabled,
        cell_meters=config.aggregate_cell_meters,
        max_nodes_before_aggregate=config.aggregate_threshold,
    )
    aggregated_node_count = len(pickup_nodes)
    if aggregated_node_count == 0:
        raise LookupError("No pickup nodes after aggregation")

    disposal_nodes = _collect_disposal_nodes(disposal_payload, dataset_service)
    if not disposal_nodes:
        raise LookupError("No available disposal nodes")
    disposal_nodes = _select_nearest_disposal_nodes(
        disposal_nodes,
        anchor_coord=(start_coord[0], start_coord[1]),
        max_candidates=config.disposal_max_candidates,
    )
    if not disposal_nodes:
        raise LookupError("No disposal nodes available after nearest selection")

    nodes, pickup_indices, disposal_indices, start_node_index, end_node_index = _build_vrp_nodes(
        start_coord,
        end_coord,
        pickup_nodes,
        disposal_nodes,
        config.capacity_kg,
    )

    coordinates = [(node["lng"], node["lat"]) for node in nodes]
    raw_distances, raw_durations = _build_osrm_table(coordinates, config.osrm_base_url, config.profile)
    distance_matrix = _to_int_matrix(raw_distances)
    duration_matrix = _to_int_matrix(raw_durations)

    solved = _solve_vrp(
        nodes=nodes,
        pickup_indices=pickup_indices,
        disposal_indices=disposal_indices,
        start_node_index=start_node_index,
        end_node_index=end_node_index,
        config=config,
        duration_matrix=duration_matrix,
        distance_matrix=distance_matrix,
    )

    total_demand_kg = int(round(sum(node["demand_kg"] for node in pickup_nodes)))
    dropped_demand_kg = int(round(sum(node.get("demand_kg", 0) for node in solved["dropped_nodes"])))
    served_demand_kg = max(0, total_demand_kg - dropped_demand_kg)

    return {
        "status": "success",
        "summary": {
            "totalDistanceM": solved["total_distance"],
            "totalDurationS": solved["total_duration"],
            "totalDemandKg": total_demand_kg,
            "servedDemandKg": served_demand_kg,
            "droppedDemandKg": dropped_demand_kg,
            "vehicleUsed": len(solved["routes"]),
            "aggregated": aggregated,
            "geometryFallbackRouteCount": int(solved.get("geometry_fallback_route_count", 0)),
        },
        "routes": solved["routes"],
        "droppedNodes": [
            {
                "id": node["id"],
                "name": node.get("name", node["id"]),
                "lng": node["lng"],
                "lat": node["lat"],
                "demandKg": int(round(node.get("demand_kg", 0))),
                "memberCount": int(node.get("member_count", 1)),
            }
            for node in solved["dropped_nodes"]
        ],
        "inputStats": {
            "rawNodeCount": raw_node_count,
            "snappedNodeCount": snapped_node_count,
            "aggregatedNodeCount": aggregated_node_count,
            "disposalCount": len(disposal_nodes),
        },
    }
