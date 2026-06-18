from datetime import datetime, timezone


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def parse_timestamp(value):
    # 將 ISO 8601 字串統一轉為 UTC datetime；格式不合或空值回傳 None
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
    # 從 Feature.properties.timestamp 取得 UTC datetime，用於 dataset 排序與過濾
    return parse_timestamp(feature.get("properties", {}).get("timestamp"))


def normalize_point_feature(feature):
    # 驗證並正規化單一 GeoJSON Point Feature：
    #   - type 必須為 Feature，geometry 必須為 Point
    #   - coordinates 須為 [lng, lat]（數字）
    #   - id 必填（Feature.id 或 properties.id），作為 upsert key
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
    # 驗證 FeatureCollection，逐一正規化每個 Feature
    if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection":
        raise ValueError("Body must be a GeoJSON FeatureCollection")
    features = payload.get("features")
    if not isinstance(features, list):
        raise ValueError("FeatureCollection.features must be an array")
    return [normalize_point_feature(feature) for feature in features]
