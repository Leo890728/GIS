from datetime import datetime, timezone


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def parse_timestamp(value):
    if not value:
        return None
    if not isinstance(value, str):
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def feature_timestamp(feature):
    return parse_timestamp(feature.get("properties", {}).get("timestamp"))


def normalize_point_feature(feature):
    if not isinstance(feature, dict) or feature.get("type") != "Feature":
        raise ValueError("Every item must be a GeoJSON Feature")

    geometry = feature.get("geometry") or {}
    if geometry.get("type") != "Point":
        raise ValueError("Only GeoJSON Point features are supported")

    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, list) or len(coordinates) < 2:
        raise ValueError("Point coordinates must include longitude and latitude")

    lng, lat = coordinates[:2]
    if not is_number(lng) or not is_number(lat):
        raise ValueError("Point coordinates must be numeric")

    feature_id = feature.get("id") or feature.get("properties", {}).get("id")
    if feature_id in (None, ""):
        raise ValueError("Point feature id is required for upsert")

    return {
        "type": "Feature",
        "id": str(feature_id),
        "geometry": {
            "type": "Point",
            "coordinates": [float(lng), float(lat)],
        },
        "properties": feature.get("properties") or {},
    }


def normalize_point_collection(payload):
    if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection":
        raise ValueError("Body must be a GeoJSON FeatureCollection")
    features = payload.get("features")
    if not isinstance(features, list):
        raise ValueError("FeatureCollection.features must be an array")
    return [normalize_point_feature(feature) for feature in features]
