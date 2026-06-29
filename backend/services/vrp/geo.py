"""Pure geometric helpers used during node building and aggregation."""

import math


def _get_point(feature):
    coordinates = feature.get("geometry", {}).get("coordinates") or [None, None]
    return coordinates[0], coordinates[1]


def _grid_index(lng, lat, cell_meters):
    meters_per_degree_lat = 111_320.0
    lat_rad = math.radians(lat)
    meters_per_degree_lng = max(1e-9, meters_per_degree_lat * math.cos(lat_rad))
    cell_lat = cell_meters / meters_per_degree_lat
    cell_lng = cell_meters / meters_per_degree_lng
    return int(math.floor(lng / cell_lng)), int(math.floor(lat / cell_lat))


def _approx_distance_m(coord_a, coord_b):
    lng_a, lat_a = coord_a
    lng_b, lat_b = coord_b
    meters_per_degree_lat = 111_320.0
    avg_lat_rad = math.radians((lat_a + lat_b) / 2.0)
    meters_per_degree_lng = max(1e-9, meters_per_degree_lat * math.cos(avg_lat_rad))
    delta_lng_m = (lng_a - lng_b) * meters_per_degree_lng
    delta_lat_m = (lat_a - lat_b) * meters_per_degree_lat
    return math.hypot(delta_lng_m, delta_lat_m)
