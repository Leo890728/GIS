"""Solve configuration: defaults, ``_SolveConfig`` and payload parsing."""

import os
from dataclasses import dataclass

from backend.services.vrp.payload import (
    _as_bool,
    _as_dict,
    _as_float,
    _as_int,
    _parse_coord,
)


ROUTE_CHUNK_MAX_WAYPOINTS_DEFAULT = 1500
ROUTE_CHUNK_MAX_URL_LENGTH_DEFAULT = 7800
DISPOSAL_VISIT_COST_DEFAULT = 300
DISPOSAL_MAX_CANDIDATES_DEFAULT = 1
SNAP_TO_ROAD_MAX_DISTANCE_METERS_DEFAULT = 200.0


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
    engine: str = "ortools"


def _parse_config(payload):
    # depot.start / depot.end are optional: when omitted the service picks the
    # disposal point (cleaning team) nearest the pickup area as the vehicle base.
    depot_payload = payload.get("depot") or {}
    if not isinstance(depot_payload, dict):
        raise ValueError("depot must be an object")
    start = _parse_coord(depot_payload.get("start"), "depot.start") if depot_payload.get("start") is not None else None
    end = _parse_coord(depot_payload.get("end"), "depot.end") if depot_payload.get("end") is not None else None

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
    # OSRM topology is a server concern: an explicit VRP_OSRM_URL wins over the
    # client-supplied value (e.g. so a container reaches the osrm service).
    osrm_base_url = os.getenv("VRP_OSRM_URL") or cost_payload.get("osrmBaseUrl") or "http://localhost:5001"
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
    engine = solver_payload.get("engine") or os.getenv("VRP_SOLVER_ENGINE") or "ortools"
    if engine not in {"ortools", "pyvrp"}:
        raise ValueError("solver.engine must be ortools or pyvrp")

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
            engine=engine,
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
