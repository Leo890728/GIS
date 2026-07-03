import unittest

from backend.app import create_app
from backend.config import BOUNDS_DB_PATH, DATA_DB_PATH, RANGE_STYLES
from backend.services.dataset_service import DatasetService
from backend.services.regions_service import RegionsService


def fake_dataset_fetcher(request_data_or_url):
    if isinstance(request_data_or_url, dict):
        if "skyeyes" in request_data_or_url.get("url", "").lower() or request_data_or_url.get("method") == "POST":
            return {
                "d": "{\"DATA\":[{\"car_licence\":\"KER-3382\",\"caption\":\"Taichung Demo\",\"dt\":\"2026-05-26 11:17:49\",\"x\":\"120.69058\",\"y\":\"24.266903\",\"direct\":\"↘\",\"status\":\"90\",\"car_no\":\"03\",\"rcar_licence\":\"\",\"cartype\":\"N\",\"car_id\":\"75990051\"}]}"
            }
        if "taichung" in request_data_or_url.get("url", "").lower():
            return [
                {
                    "lineid": "307",
                    "car": "ABC-123",
                    "time": "2026-05-26T10:00:00Z",
                    "location": "Taichung",
                    "X": "120.651",
                    "Y": "24.147",
                    "SpeedValue": 62,
                    "OverSpeed": 1,
                }
            ]
        if "moenv" in request_data_or_url.get("url", "").lower():
            return {
                "records": [
                    {
                        "wepno": "WEPJ2722",
                        "icnrtname": "新竹縣高效能再生能源中心",
                        "budadd": "",
                        "_lng": "120.999",
                        "_lat": "24.888",
                    }
                ]
            }
        return []

    return [
        {
            "lineid": "307",
            "car": "ABC-123",
            "time": "2026-05-26T10:00:00Z",
            "location": "Taichung",
            "X": "120.651",
            "Y": "24.147",
            "SpeedValue": 62,
            "OverSpeed": 1,
        }
    ]


class SmokeApiTestCase(unittest.TestCase):
    def setUp(self):
        self.fetch_requests = []

        def fetcher_with_trace(request_data_or_url):
            self.fetch_requests.append(request_data_or_url)
            return fake_dataset_fetcher(request_data_or_url)

        self.dataset_service = DatasetService(
            {
                "taichung_garbage_recycling_dynamic": {
                    "adapter": "generic_http_json",
                    "url": "mock://taichung",
                    "refresh_seconds": 600,
                    "fields": {
                        "id_parts": ["lineid", "car", "time"],
                        "lng": "X",
                        "lat": "Y",
                        "timestamp": "time",
                    },
                },
                "taichung_garbage_recycling_dynamic_V2": {
                    "adapter": "taichung_ws_skyeyes",
                    "url": "mock://skyeyes",
                    "bootstrap_url": "mock://cleaner-index",
                    "method": "POST",
                    "rows_path": ["d", "DATA"],
                    "refresh_seconds": 600,
                    "fields": {
                        "id_parts": ["car_id", "car_licence", "dt"],
                        "lng": "x",
                        "lat": "y",
                        "timestamp": "dt",
                    },
                },
                "stat_zone_population_points": {
                    "adapter": "regions_sqlite_stat_zone_points",
                    "db_path": str(BOUNDS_DB_PATH),
                    "refresh_seconds": 600,
                    "limit": 5000,
                    "fields": {
                        "id_parts": ["CODEBASE"],
                        "lng": "X",
                        "lat": "Y",
                    },
                },
                "moenv_incinerators": {
                    "adapter": "moenv_incinerator_geocode",
                    "url": "mock://moenv",
                    "refresh_seconds": 600,
                    "rows_path": ["records"],
                    "geocode_address_field": "budadd",
                    "geocode_retry_days": 7,
                    "fields": {
                        "id_parts": ["wepno"],
                        "lng": "_lng",
                        "lat": "_lat",
                    },
                },
            },
            fetcher=fetcher_with_trace,
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
                "DATASET_SERVICE": self.dataset_service,
            }
        )
        self.client = self.app.test_client()

    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(200, response.status_code)
        self.assertEqual({"ok": True}, response.get_json())

    def test_ranges_tree(self):
        response = self.client.get("/ranges/tree")
        response_json = response.get_json()
        self.assertEqual(200, response.status_code)
        self.assertIn("summary", response_json)
        trees = response_json.get("trees", [])
        self.assertEqual(["admin", "stat"], [tree.get("id") for tree in trees])
        for tree in trees:
            self.assertIn("ranges", tree)

    def test_stat_zone_children_chain(self):
        tree_response = self.client.get("/ranges/tree")
        self.assertEqual(200, tree_response.status_code)
        trees = tree_response.get_json().get("trees", [])
        stat_tree = next((tree for tree in trees if tree.get("id") == "stat"), {})

        town_code = None
        for county in stat_tree.get("ranges", []):
            for township in county.get("children", []):
                if int(township.get("metadata", {}).get("childCount", 0)) > 0:
                    town_code = township.get("code")
                    break
            if town_code:
                break

        if town_code is None:
            self.skipTest("No township with stat zone metadata in fixture")

        # 區 → 二級發布區
        response = self.client.get(f"/ranges/stat-zones/township/{town_code}/children")
        self.assertEqual(200, response.status_code)
        payload = response.get_json()
        self.assertGreater(len(payload.get("ranges", [])), 0)
        sz2 = payload["ranges"][0]
        self.assertEqual("stat_zone_2", sz2.get("level"))
        self.assertEqual("stat_zone_1", sz2.get("metadata", {}).get("childLevel"))

        # 二級發布區 → 一級發布區
        response = self.client.get(f"/ranges/stat-zones/stat_zone_2/{sz2['code']}/children")
        self.assertEqual(200, response.status_code)
        payload = response.get_json()
        self.assertGreater(len(payload.get("ranges", [])), 0)
        sz1 = payload["ranges"][0]
        self.assertEqual("stat_zone_1", sz1.get("level"))
        self.assertEqual("stat_zone", sz1.get("metadata", {}).get("childLevel"))

        # 一級發布區 → 最小統計區
        response = self.client.get(f"/ranges/stat-zones/stat_zone_1/{sz1['code']}/children")
        self.assertEqual(200, response.status_code)
        payload = response.get_json()
        self.assertGreater(len(payload.get("ranges", [])), 0)
        self.assertEqual("stat_zone", payload["ranges"][0].get("level"))

    def test_stat_zone_children_rejects_unknown_level(self):
        response = self.client.get("/ranges/stat-zones/nope/123/children")
        self.assertEqual(400, response.status_code)

    def test_tiles_endpoint(self):
        response = self.client.get("/tiles/__missing__/0/0/0.pbf")
        self.assertEqual(404, response.status_code)

    def test_dataset_query_and_aggregate_with_data_id(self):
        query_response = self.client.post(
            "/data/query",
            json={
                "dataId": "taichung_garbage_recycling_dynamic",
                "filters": {"OverSpeed": {"gte": 1}},
            },
        )
        self.assertEqual(200, query_response.status_code)
        query_json = query_response.get_json()
        self.assertEqual("FeatureCollection", query_json["type"])
        self.assertEqual(1, len(query_json["features"]))

        aggregate_response = self.client.post(
            "/data/aggregate",
            json={
                "dataId": "taichung_garbage_recycling_dynamic",
                "metrics": ["count", "sum:SpeedValue", "avg:SpeedValue"],
            },
        )
        self.assertEqual(200, aggregate_response.status_code)
        self.assertEqual(
            {"count": 1, "sum": {"SpeedValue": 62}, "avg": {"SpeedValue": 62.0}},
            aggregate_response.get_json(),
        )

    def test_dataset_query_with_inline_data(self):
        response = self.client.post(
            "/data/query",
            json={
                "data": {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "id": "inline-1",
                            "geometry": {"type": "Point", "coordinates": [120.65, 24.14]},
                            "properties": {"SpeedValue": 80, "OverSpeed": 1},
                        }
                    ],
                },
                "filters": {"OverSpeed": 1},
            },
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(response.get_json()["features"]))

    def test_dataset_meta_endpoint(self):
        refresh_response = self.client.post("/data/refresh/taichung_garbage_recycling_dynamic")
        self.assertEqual(200, refresh_response.status_code)

        meta_response = self.client.get("/data/meta/taichung_garbage_recycling_dynamic")
        self.assertEqual(200, meta_response.status_code)
        meta_json = meta_response.get_json()
        self.assertEqual("taichung_garbage_recycling_dynamic", meta_json["dataId"])
        self.assertEqual(1, meta_json["count"])

    def test_dataset_v2_query(self):
        response = self.client.post(
            "/data/query",
            json={
                "dataId": "taichung_garbage_recycling_dynamic_V2",
                "filters": {"cartype": "N"},
            },
        )
        self.assertEqual(200, response.status_code)
        payload = response.get_json()
        self.assertEqual("FeatureCollection", payload["type"])
        self.assertEqual(1, len(payload["features"]))
        # 有可用 session 時直接打資料端點,不應重新 bootstrap index 頁。
        self.assertEqual(1, len(self.fetch_requests))
        only = self.fetch_requests[0]
        self.assertIsInstance(only, dict)
        self.assertEqual("POST", only.get("method"))
        self.assertEqual("mock://skyeyes", only.get("url"))
        self.assertFalse(
            any(req.get("method") == "GET" for req in self.fetch_requests if isinstance(req, dict))
        )

    def test_dataset_v2_bootstraps_only_after_session_expiry(self):
        from backend.data_sources.adapters.taichung_ws_skyeyes import (
            TaichungWsSkyeyesAdapter,
        )

        source = {
            "url": "mock://skyeyes",
            "bootstrap_url": "mock://cleaner-index",
            "method": "POST",
        }
        calls = []
        state = {"has_session": False}

        def fetcher(request):
            calls.append(request)
            if request.get("method") == "GET":  # bootstrap 建立 session
                state["has_session"] = True
                return ""
            if not state["has_session"]:  # session 過期/未建立 -> 直接 POST 失敗
                raise RuntimeError("session expired")
            return {"d": "{\"DATA\":[]}"}

        adapter = TaichungWsSkyeyesAdapter()

        # 首次:無 session,直接 POST 失敗後 bootstrap 再重試。
        adapter.fetch_payload(fetcher, source)
        self.assertEqual(["POST", "GET", "POST"], [c.get("method") for c in calls])

        # session 已建立:後續請求直接 POST,不再 bootstrap。
        calls.clear()
        adapter.fetch_payload(fetcher, source)
        self.assertEqual(["POST"], [c.get("method") for c in calls])

    def test_admin_stat_zone_aggregate(self):
        response = self.client.post(
            "/data/admin/aggregate",
            json={"statZoneCodes": ["A0813-0011-00"]},
        )
        self.assertEqual(200, response.status_code)
        payload = response.get_json()
        self.assertIn("count", payload)
        self.assertIn("sum", payload)
        self.assertIn("P_CNT", payload["sum"])
        self.assertGreaterEqual(payload["count"], 1)

    def test_admin_stat_zone_points(self):
        response = self.client.post(
            "/data/admin/stat-zone-points",
            json={"statZoneCodes": ["A0813-0011-00"]},
        )
        self.assertEqual(200, response.status_code)
        payload = response.get_json()
        self.assertEqual("FeatureCollection", payload.get("type"))
        self.assertGreaterEqual(len(payload.get("features", [])), 1)
        first = payload["features"][0]
        self.assertEqual("Point", first["geometry"]["type"])
        self.assertIn("P_CNT", first["properties"])

    def test_data_query_stat_zone_population_points_via_data_query(self):
        response = self.client.post(
            "/data/query",
            json={
                "dataId": "stat_zone_population_points",
                "limit": 5,
            },
        )
        self.assertEqual(200, response.status_code)
        payload = response.get_json()
        self.assertEqual("FeatureCollection", payload.get("type"))
        self.assertGreaterEqual(len(payload.get("features", [])), 1)
        first = payload["features"][0]
        self.assertEqual("Point", first["geometry"]["type"])
        self.assertIn("P_CNT", first["properties"])

    def test_data_query_moenv_incinerators_returns_points(self):
        response = self.client.post(
            "/data/query",
            json={
                "dataId": "moenv_incinerators",
                "limit": 5,
            },
        )
        self.assertEqual(200, response.status_code)
        payload = response.get_json()
        self.assertEqual("FeatureCollection", payload.get("type"))
        self.assertGreaterEqual(len(payload.get("features", [])), 1)
        first = payload["features"][0]
        self.assertEqual("Point", first["geometry"]["type"])
        self.assertIn("icnrtname", first["properties"])


if __name__ == "__main__":
    unittest.main()
