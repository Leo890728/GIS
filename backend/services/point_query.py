from backend.geo.geometry import point_in_geojson_range
from backend.schemas.data_points import feature_timestamp, is_number, parse_timestamp


def feature_collection(features):
    return {"type": "FeatureCollection", "features": features}


def point_coordinates(feature):
    coordinates = feature.get("geometry", {}).get("coordinates") or [None, None]
    return coordinates[0], coordinates[1]


def extract_bbox(range_def, fallback_bbox=None):
    if isinstance(fallback_bbox, list) and len(fallback_bbox) == 4:
        return fallback_bbox
    if isinstance(range_def, list) and len(range_def) == 4:
        return range_def
    if isinstance(range_def, dict):
        bbox = range_def.get("bbox")
        if isinstance(bbox, list) and len(bbox) == 4:
            return bbox
    return None


def point_in_bbox(lng, lat, bbox):
    if not bbox:
        return True
    try:
        min_lng, min_lat, max_lng, max_lat = [float(value) for value in bbox]
    except (TypeError, ValueError):
        raise ValueError("bbox must contain four numeric values")
    return min_lng <= lng <= max_lng and min_lat <= lat <= max_lat


def feature_matches_filters(feature, filters):
    if not filters:
        return True
    if not isinstance(filters, dict):
        raise ValueError("filters must be an object")

    properties = feature.get("properties", {})
    for key, expected in filters.items():
        actual = properties.get(key)
        if isinstance(expected, list):
            if actual not in expected:
                return False
        elif isinstance(expected, dict):
            if "eq" in expected and actual != expected["eq"]:
                return False
            if "in" in expected and actual not in expected["in"]:
                return False
            if "gte" in expected and (
                not is_number(actual) or not is_number(expected["gte"]) or actual < expected["gte"]
            ):
                return False
            if "lte" in expected and (
                not is_number(actual) or not is_number(expected["lte"]) or actual > expected["lte"]
            ):
                return False
        elif actual != expected:
            return False
    return True


def query_points(point_features, payload):
    payload = payload or {}
    if not isinstance(payload, dict):
        raise ValueError("Body must be a JSON object")

    range_def = payload.get("range")
    bbox = extract_bbox(range_def, payload.get("bbox"))
    filters = payload.get("filters") or {}
    since_timestamp = parse_timestamp(payload.get("sinceTimestamp"))

    matched = []
    for feature in point_features:
        lng, lat = point_coordinates(feature)
        if not point_in_bbox(lng, lat, bbox):
            continue
        if not point_in_geojson_range(lng, lat, range_def):
            continue
        if since_timestamp:
            point_timestamp = feature_timestamp(feature)
            if not point_timestamp or point_timestamp <= since_timestamp:
                continue
        if not feature_matches_filters(feature, filters):
            continue
        matched.append(feature)

    limit = payload.get("limit")
    if limit is not None:
        try:
            limit = max(0, int(limit))
        except (TypeError, ValueError):
            raise ValueError("limit must be an integer")
        matched = matched[:limit]

    return matched
