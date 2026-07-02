"""Garbage-collection VRP orchestration facade.

The heavy lifting now lives in the :mod:`backend.services.vrp` package; this
module keeps the public :func:`solve_garbage_vrp` entry point and wires the
domain-specific steps (node sourcing, disposal selection) to the generic
OSRM/OR-Tools core.
"""

from backend.services.vrp.config import _parse_config
from backend.services.vrp.nodes import (
    _aggregate_pickup_nodes,
    _build_pickup_nodes,
    _build_range_geojson,
    _build_vrp_nodes,
    _collect_dataset_nodes,
    _collect_disposal_nodes,
    _collect_preset_nodes,
    _find_nearest_disposal_node,
    _select_nearest_disposal_nodes,
    _snap_pickup_nodes_to_road,
)
from backend.services.vrp.osrm_client import _build_osrm_table
from backend.services.vrp.payload import _as_dict, _as_float, _as_string
from backend.services.vrp.response import _build_response
from backend.services.vrp.solver import _solve_vrp, _to_int_matrix


def solve_garbage_vrp(payload, dataset_service, regions_service):
    payload = _as_dict(payload, "Body")
    node_source = _as_dict(payload.get("nodeSource"), "nodeSource")
    range_payload = _as_dict(payload.get("range"), "range")
    disposal_payload = _as_dict(payload.get("disposal"), "disposal")
    has_explicit_geojson = isinstance(range_payload.get("geojson"), dict)

    config, start_coord, end_coord = _parse_config(payload)

    mode = node_source.get("mode") or "preset"
    demand_field = _as_string(node_source.get("demandField"), "nodeSource.demandField")
    demand_multiplier_kg = _as_float(
        node_source.get("demandMultiplierKg"),
        "nodeSource.demandMultiplierKg",
        minimum=0.000001,
    )

    if mode == "preset":
        # preset mode queries stat_zone_point_cache directly via code filters —
        # geojson boundary is only needed when the caller provides explicit geojson
        range_geojson = _build_range_geojson(range_payload, regions_service) if has_explicit_geojson else None
        features = _collect_preset_nodes(
            node_source,
            range_payload,
            range_geojson,
            regions_service,
            has_explicit_geojson,
        )
    elif mode == "dataset":
        range_geojson = _build_range_geojson(range_payload, regions_service)
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

    if aggregated and config.snap_to_road_enabled:
        # Aggregated centroids are synthetic points that usually sit off-road at
        # the cell center. Snap them with no distance cap so reported stops sit
        # where vehicles actually visit (OSRM snaps unconditionally when routing).
        pickup_nodes, _ = _snap_pickup_nodes_to_road(
            pickup_nodes,
            enabled=True,
            max_distance_m=float("inf"),
            osrm_base_url=config.osrm_base_url,
            profile=config.profile,
        )

    disposal_nodes = _collect_disposal_nodes(disposal_payload, dataset_service)
    if not disposal_nodes:
        raise LookupError("No available disposal nodes")

    # Auto depot: without an explicit start/end the vehicles are based at the
    # disposal point (cleaning team) nearest the pickup area's centroid.
    if start_coord is None or end_coord is None:
        centroid = (
            sum(node["lng"] for node in pickup_nodes) / len(pickup_nodes),
            sum(node["lat"] for node in pickup_nodes) / len(pickup_nodes),
        )
        home = _find_nearest_disposal_node(disposal_nodes, centroid)
        if start_coord is None:
            start_coord = [home["lng"], home["lat"]]
        if end_coord is None:
            end_coord = [home["lng"], home["lat"]]

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

    return _build_response(
        solved,
        pickup_nodes,
        aggregated,
        disposal_nodes,
        raw_node_count,
        snapped_node_count,
        aggregated_node_count,
        start_coord=start_coord,
        end_coord=end_coord,
    )
