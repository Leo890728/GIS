"""Node building: pickup/disposal collection, aggregation, snap, VRP nodes."""

import math

from backend.services.point_query import query_points
from backend.services.regions_service import split_codes
from backend.services.vrp.geo import _approx_distance_m, _get_point, _grid_index
from backend.services.vrp.osrm_client import _fetch_osrm_nearest
from backend.services.vrp.payload import _as_dict, _as_int, _as_string


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
