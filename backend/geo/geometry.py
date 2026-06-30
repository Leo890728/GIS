import math


def haversine_m(a, b):
    # 兩個 [lng, lat] 之間的大圓距離（公尺）
    radius = 6371000.0
    lat1 = math.radians(a[1])
    lat2 = math.radians(b[1])
    dlat = math.radians(b[1] - a[1])
    dlng = math.radians(b[0] - a[0])
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 2 * radius * math.asin(min(1.0, math.sqrt(h)))


def point_in_ring(lng, lat, ring):
    # Ray casting：從點向右射水平線，計算穿越 ring 邊的次數
    # 奇數次 = 在環內；`or 1e-12` 防止水平邊造成除以零
    if not isinstance(ring, list) or len(ring) < 4:
        return False

    inside = False
    j = len(ring) - 1
    for i, current in enumerate(ring):
        previous = ring[j]
        if not isinstance(current, list) or not isinstance(previous, list):
            j = i
            continue
        if len(current) < 2 or len(previous) < 2:
            j = i
            continue
        xi, yi = current[:2]
        xj, yj = previous[:2]
        if ((yi > lat) != (yj > lat)) and (lng < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def point_in_polygon(lng, lat, polygon_coordinates):
    # GeoJSON Polygon：coordinates[0] 為外環，coordinates[1:] 為洞（holes）
    # 點必須在外環內且不在任何洞內
    if not isinstance(polygon_coordinates, list) or not polygon_coordinates:
        return False
    if not point_in_ring(lng, lat, polygon_coordinates[0]):
        return False
    for hole in polygon_coordinates[1:]:
        if point_in_ring(lng, lat, hole):
            return False
    return True


def point_in_geometry(lng, lat, geometry):
    # 支援 Polygon 與 MultiPolygon；MultiPolygon 任一子多邊形包含即回傳 True
    if not isinstance(geometry, dict):
        return False
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if geometry_type == "Polygon":
        return point_in_polygon(lng, lat, coordinates)
    if geometry_type == "MultiPolygon":
        return any(point_in_polygon(lng, lat, polygon) for polygon in coordinates or [])
    return False


def point_in_geojson_range(lng, lat, range_def):
    # 最上層 range 過濾，接受多種格式：
    #   None / list(舊 bbox) → 無限制，直接 True
    #   Polygon / MultiPolygon → 幾何判斷
    #   Feature → 取 .geometry 判斷
    #   FeatureCollection → 任一 Feature 包含即 True
    #   含 bbox key → 視為無限制（bbox 裁切由上層處理）
    if not range_def:
        return True
    if isinstance(range_def, list):
        return True
    if not isinstance(range_def, dict):
        raise ValueError("range must be bbox or GeoJSON Polygon/MultiPolygon")

    range_type = range_def.get("type")
    if range_type in ("Polygon", "MultiPolygon"):
        return point_in_geometry(lng, lat, range_def)
    if range_type == "Feature":
        return point_in_geometry(lng, lat, range_def.get("geometry"))
    if range_type == "FeatureCollection":
        return any(point_in_geojson_range(lng, lat, feature) for feature in range_def.get("features", []))
    if "bbox" in range_def:
        return True

    raise ValueError("range must be bbox or GeoJSON Polygon/MultiPolygon")
