import unittest
from unittest import mock

from backend.app import create_app
from backend.config import BOUNDS_DB_PATH, DATA_DB_PATH, RANGE_STYLES
from backend.services.dataset_service import DatasetService
from backend.services.garbage_vrp_service import _build_route_geometry_from_osrm, _snap_pickup_nodes_to_road
from backend.services.regions_service import RegionsService


def fake_fetcher(request_data_or_url):
    if isinstance(request_data_or_url, dict):
        url = request_data_or_url.get("url", "")
    else:
        url = str(request_data_or_url)

    if "custom-nodes" in url:
        return [
            {"id": "c-1", "name": "Custom A", "X": 120.66, "Y": 24.15, "pop": 10},
            {"id": "c-2", "name": "Custom B", "X": 120.67, "Y": 24.151, "pop": 20},
        ]

    if "incinerator" in url:
        return [
            {"wepno": "I-001", "icnrtname": "Incinerator 1", "_lng": 120.65, "_lat": 24.14},
            {"wepno": "I-002", "icnrtname": "Incinerator 2", "_lng": 120.75, "_lat": 24.24},
        ]

    return []


class GarbageVrpApiTestCase(unittest.TestCase):
    def setUp(self):
        dataset_service = DatasetService(
            {
                "stat_zone_population_points": {
                    "adapter": "regions_sqlite_stat_zone_points",
                    "db_path": str(BOUNDS_DB_PATH),
                    "refresh_seconds": 600,
                    "limit": 100000,
                    "fields": {
                        "id_parts": ["CODEBASE"],
                        "lng": "X",
                        "lat": "Y",
                    },
                },
                "custom_nodes": {
                    "adapter": "generic_http_json",
                    "url": "mock://custom-nodes",
                    "refresh_seconds": 600,
                    "fields": {
                        "id_parts": ["id"],
                        "lng": "X",
                        "lat": "Y",
                    },
                },
                "moenv_incinerators": {
                    "adapter": "generic_http_json",
                    "url": "mock://incinerator",
                    "refresh_seconds": 600,
                    "fields": {
                        "id_parts": ["wepno"],
                        "lng": "_lng",
                        "lat": "_lat",
                    },
                },
            },
            fetcher=fake_fetcher,
        )

        self.app = create_app(
            {
                "TESTING": True,
                "REGIONS_SERVICE": RegionsService(
                    bounds_path=BOUNDS_DB_PATH,
                    data_path=DATA_DB_PATH,
                    range_styles=RANGE_STYLES,
                    spatialite_extension_path=None,
                ),
                "DATASET_SERVICE": dataset_service,
            }
        )
        self.client = self.app.test_client()

    def _base_payload(self):
        return {
            "nodeSource": {
                "mode": "preset",
                "preset": "stat_zone_population_points",
                "demandField": "P_CNT",
                "demandMultiplierKg": 1.36,
                "limit": 5000,
            },
            "range": {
                "countyCodes": [],
                "townCodes": [],
                "villageCodes": [],
                "statZoneCodes": ["A0813-0011-00"],
            },
            "depot": {
                "start": [120.65, 24.14],
                "end": [120.65, 24.14],
            },
            "vehicles": {
                "count": 2,
                "capacityKg": 3000,
            },
            "disposal": {
                "sourceDataId": "moenv_incinerators",
                "policy": "nearest_auto",
            },
            "aggregation": {
                "enabled": True,
                "cellMeters": 300,
                "maxNodesBeforeAggregate": 10,
            },
            "cost": {
                "mode": "osrm",
                "metric": "duration",
                "profile": "driving",
                "osrmBaseUrl": "http://localhost:5002",
            },
            "solver": {
                "timeLimitSec": 3,
                "randomSeed": 1,
            },
        }

    def test_solve_garbage_validation_error(self):
        response = self.client.post("/api/vrp/solve-garbage", json={"foo": "bar"})
        self.assertEqual(400, response.status_code)

    def test_solve_garbage_preset_success(self):
        payload = self._base_payload()

        def fake_osrm_table(coordinates, osrm_base_url, profile):
            size = len(coordinates)
            zeros = [[0 for _ in range(size)] for _ in range(size)]
            return zeros, zeros

        with mock.patch("backend.services.garbage_vrp_service._build_osrm_table", side_effect=fake_osrm_table):
            with mock.patch(
                "backend.services.garbage_vrp_service._solve_vrp",
                return_value={
                    "routes": [
                        {
                            "vehicle_id": "truck-1",
                            "distance_m": 1000,
                            "duration_s": 120,
                            "stops": [
                                {
                                    "location_id": "depot-start",
                                    "name": "Depot Start",
                                    "type": "depot",
                                    "lng": 120.65,
                                    "lat": 24.14,
                                    "load_kg": 0,
                                    "memberCount": 1,
                                    "legFromPrevDistanceM": None,
                                    "legFromPrevDurationS": None,
                                }
                            ],
                            "geometry": {"type": "LineString", "coordinates": []},
                            "geometrySource": "osrm_route",
                        }
                    ],
                    "dropped_nodes": [],
                    "total_distance": 1000,
                    "total_duration": 120,
                    "geometry_fallback_route_count": 0,
                },
            ):
                response = self.client.post("/api/vrp/solve-garbage", json=payload)

        self.assertEqual(200, response.status_code)
        body = response.get_json()
        self.assertEqual("success", body["status"])
        self.assertIn("inputStats", body)
        self.assertGreater(body["inputStats"]["rawNodeCount"], 0)
        self.assertGreater(body["inputStats"]["aggregatedNodeCount"], 0)
        self.assertIn("summary", body)
        self.assertIn("totalDemandKg", body["summary"])
        self.assertIn("geometryFallbackRouteCount", body["summary"])

    def test_solve_garbage_dataset_mode_success(self):
        payload = self._base_payload()
        payload["nodeSource"] = {
            "mode": "dataset",
            "dataId": "custom_nodes",
            "demandField": "pop",
            "demandMultiplierKg": 1.36,
            "limit": 1000,
        }
        payload["range"] = {
            "countyCodes": [],
            "townCodes": [],
            "villageCodes": [],
            "statZoneCodes": []
        }
        payload["aggregation"] = {
            "enabled": False,
            "cellMeters": 500,
            "maxNodesBeforeAggregate": 100,
        }

        def fake_osrm_table(coordinates, osrm_base_url, profile):
            size = len(coordinates)
            zeros = [[0 for _ in range(size)] for _ in range(size)]
            return zeros, zeros

        with mock.patch("backend.services.garbage_vrp_service._build_osrm_table", side_effect=fake_osrm_table):
            with mock.patch(
                "backend.services.garbage_vrp_service._solve_vrp",
                return_value={
                    "routes": [],
                    "dropped_nodes": [],
                    "total_distance": 0,
                    "total_duration": 0,
                },
            ):
                response = self.client.post("/api/vrp/solve-garbage", json=payload)

        self.assertEqual(200, response.status_code)
        body = response.get_json()
        self.assertEqual(2, body["inputStats"]["rawNodeCount"])
        self.assertEqual(2, body["inputStats"]["aggregatedNodeCount"])

    def test_solve_garbage_disposal_defaults_to_nearest_single_candidate(self):
        payload = self._base_payload()
        payload["aggregation"]["enabled"] = False
        payload["range"] = {
            "countyCodes": [],
            "townCodes": [],
            "villageCodes": [],
            "statZoneCodes": ["A0813-0011-00"],
        }

        def fake_osrm_table(coordinates, osrm_base_url, profile):
            size = len(coordinates)
            zeros = [[0 for _ in range(size)] for _ in range(size)]
            return zeros, zeros

        with mock.patch("backend.services.garbage_vrp_service._build_osrm_table", side_effect=fake_osrm_table):
            with mock.patch(
                "backend.services.garbage_vrp_service._solve_vrp",
                return_value={
                    "routes": [],
                    "dropped_nodes": [],
                    "total_distance": 0,
                    "total_duration": 0,
                    "geometry_fallback_route_count": 0,
                },
            ):
                response = self.client.post("/api/vrp/solve-garbage", json=payload)

        self.assertEqual(200, response.status_code)
        body = response.get_json()
        self.assertEqual(1, body["inputStats"]["disposalCount"])

    def test_solve_garbage_disposal_can_expand_nearest_candidates(self):
        payload = self._base_payload()
        payload["disposal"]["maxCandidates"] = 2

        def fake_osrm_table(coordinates, osrm_base_url, profile):
            size = len(coordinates)
            zeros = [[0 for _ in range(size)] for _ in range(size)]
            return zeros, zeros

        with mock.patch("backend.services.garbage_vrp_service._build_osrm_table", side_effect=fake_osrm_table):
            with mock.patch(
                "backend.services.garbage_vrp_service._solve_vrp",
                return_value={
                    "routes": [],
                    "dropped_nodes": [],
                    "total_distance": 0,
                    "total_duration": 0,
                    "geometry_fallback_route_count": 0,
                },
            ):
                response = self.client.post("/api/vrp/solve-garbage", json=payload)

        self.assertEqual(200, response.status_code)
        body = response.get_json()
        self.assertEqual(2, body["inputStats"]["disposalCount"])

    def test_solve_garbage_osrm_error_returns_503(self):
        payload = self._base_payload()

        with mock.patch(
            "backend.services.garbage_vrp_service._build_osrm_table",
            side_effect=RuntimeError("OSRM unavailable"),
        ):
            response = self.client.post("/api/vrp/solve-garbage", json=payload)

        self.assertEqual(503, response.status_code)

    def test_solve_garbage_preserves_route_fallback_metadata(self):
        payload = self._base_payload()

        def fake_osrm_table(coordinates, osrm_base_url, profile):
            size = len(coordinates)
            zeros = [[0 for _ in range(size)] for _ in range(size)]
            return zeros, zeros

        with mock.patch("backend.services.garbage_vrp_service._build_osrm_table", side_effect=fake_osrm_table):
            with mock.patch(
                "backend.services.garbage_vrp_service._solve_vrp",
                return_value={
                    "routes": [
                        {
                            "vehicle_id": "truck-1",
                            "distance_m": 1000,
                            "duration_s": 120,
                            "stops": [],
                            "geometry": {"type": "LineString", "coordinates": []},
                            "geometrySource": "straight_fallback",
                            "geometryFallbackReason": "OSRM route error",
                        }
                    ],
                    "dropped_nodes": [],
                    "total_distance": 1000,
                    "total_duration": 120,
                    "geometry_fallback_route_count": 1,
                },
            ):
                response = self.client.post("/api/vrp/solve-garbage", json=payload)

        self.assertEqual(200, response.status_code)
        body = response.get_json()
        self.assertEqual(1, body["summary"]["geometryFallbackRouteCount"])
        self.assertEqual("straight_fallback", body["routes"][0]["geometrySource"])
        self.assertIn("geometryFallbackReason", body["routes"][0])

    def test_solve_garbage_no_disposal_returns_422(self):
        payload = self._base_payload()
        payload["disposal"]["filters"] = {"wepno": "NO_MATCH"}

        with mock.patch(
            "backend.services.garbage_vrp_service._build_osrm_table",
            side_effect=RuntimeError("should not call"),
        ):
            response = self.client.post("/api/vrp/solve-garbage", json=payload)

        self.assertEqual(422, response.status_code)


class GarbageVrpRouteGeometryHelperTestCase(unittest.TestCase):
    def test_build_route_geometry_from_osrm_splits_by_waypoint_limit(self):
        coordinates = [
            (120.650001, 24.140001),
            (120.660001, 24.150001),
            (120.670001, 24.160001),
            (120.680001, 24.170001),
            (120.690001, 24.180001),
        ]
        calls = []

        def fake_fetch(osrm_base_url, profile, chunk_coordinates):
            calls.append(chunk_coordinates)
            return (
                {
                    "type": "LineString",
                    "coordinates": [[lng, lat] for lng, lat in chunk_coordinates],
                },
                [{"distance": 100, "duration": 10} for _ in range(len(chunk_coordinates) - 1)],
            )

        with mock.patch("backend.services.garbage_vrp_service._fetch_osrm_route", side_effect=fake_fetch):
            geometry, legs = _build_route_geometry_from_osrm(
                coordinates=coordinates,
                osrm_base_url="http://localhost:5002",
                profile="driving",
                max_waypoints_per_call=3,
                max_url_length=9000,
            )

        self.assertEqual(2, len(calls))
        self.assertEqual(5, len(geometry["coordinates"]))
        self.assertEqual(4, len(legs))

    def test_build_route_geometry_from_osrm_splits_by_url_length(self):
        coordinates = [
            (120.650001, 24.140001),
            (120.660001, 24.150001),
            (120.670001, 24.160001),
            (120.680001, 24.170001),
        ]
        calls = []

        def fake_fetch(osrm_base_url, profile, chunk_coordinates):
            calls.append(chunk_coordinates)
            return (
                {
                    "type": "LineString",
                    "coordinates": [[lng, lat] for lng, lat in chunk_coordinates],
                },
                [{"distance": 100, "duration": 10} for _ in range(len(chunk_coordinates) - 1)],
            )

        def fake_exceeds(_osrm_base_url, _profile, chunk_coordinates, _max_url_length):
            return len(chunk_coordinates) > 2

        with mock.patch("backend.services.garbage_vrp_service._fetch_osrm_route", side_effect=fake_fetch):
            with mock.patch(
                "backend.services.garbage_vrp_service._route_request_exceeds_limit",
                side_effect=fake_exceeds,
            ):
                geometry, legs = _build_route_geometry_from_osrm(
                    coordinates=coordinates,
                    osrm_base_url="http://localhost:5002",
                    profile="driving",
                    max_waypoints_per_call=1500,
                    max_url_length=7800,
                )

        self.assertEqual(3, len(calls))
        self.assertEqual(4, len(geometry["coordinates"]))
        self.assertEqual(3, len(legs))


class GarbageVrpSnapToRoadHelperTestCase(unittest.TestCase):
    def test_snap_pickup_nodes_to_road_updates_coordinate_when_within_distance(self):
        pickup_nodes = [
            {
                "id": "pickup-1",
                "type": "pickup",
                "name": "Pickup 1",
                "lng": 120.6501,
                "lat": 24.1401,
                "demand_kg": 100,
                "member_count": 1,
                "source_id": "1",
            }
        ]

        with mock.patch(
            "backend.services.garbage_vrp_service._fetch_osrm_nearest",
            return_value={"lng": 120.651, "lat": 24.141, "distance_m": 35},
        ):
            snapped_nodes, snapped_count = _snap_pickup_nodes_to_road(
                pickup_nodes,
                enabled=True,
                max_distance_m=200,
                osrm_base_url="http://localhost:5002",
                profile="driving",
            )

        self.assertEqual(1, snapped_count)
        self.assertEqual(120.651, snapped_nodes[0]["lng"])
        self.assertEqual(24.141, snapped_nodes[0]["lat"])

    def test_snap_pickup_nodes_to_road_skips_when_too_far(self):
        pickup_nodes = [
            {
                "id": "pickup-1",
                "type": "pickup",
                "name": "Pickup 1",
                "lng": 120.6501,
                "lat": 24.1401,
                "demand_kg": 100,
                "member_count": 1,
                "source_id": "1",
            }
        ]

        with mock.patch(
            "backend.services.garbage_vrp_service._fetch_osrm_nearest",
            return_value={"lng": 120.651, "lat": 24.141, "distance_m": 999},
        ):
            snapped_nodes, snapped_count = _snap_pickup_nodes_to_road(
                pickup_nodes,
                enabled=True,
                max_distance_m=200,
                osrm_base_url="http://localhost:5002",
                profile="driving",
            )

        self.assertEqual(0, snapped_count)
        self.assertEqual(120.6501, snapped_nodes[0]["lng"])
        self.assertEqual(24.1401, snapped_nodes[0]["lat"])

    def test_snap_pickup_nodes_to_road_falls_back_when_nearest_fails(self):
        pickup_nodes = [
            {
                "id": "pickup-1",
                "type": "pickup",
                "name": "Pickup 1",
                "lng": 120.6501,
                "lat": 24.1401,
                "demand_kg": 100,
                "member_count": 1,
                "source_id": "1",
            }
        ]

        with mock.patch(
            "backend.services.garbage_vrp_service._fetch_osrm_nearest",
            side_effect=RuntimeError("nearest unavailable"),
        ):
            snapped_nodes, snapped_count = _snap_pickup_nodes_to_road(
                pickup_nodes,
                enabled=True,
                max_distance_m=200,
                osrm_base_url="http://localhost:5002",
                profile="driving",
            )

        self.assertEqual(0, snapped_count)
        self.assertEqual(120.6501, snapped_nodes[0]["lng"])
        self.assertEqual(24.1401, snapped_nodes[0]["lat"])


if __name__ == "__main__":
    unittest.main()
