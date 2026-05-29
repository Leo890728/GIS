import unittest
from unittest.mock import patch

from backend.data_sources.adapters.moenv_incinerator_geocode import (
    MoenvIncineratorGeocodeAdapter,
)


class FakeCacheDb:
    def __init__(self, geocode_entries=None):
        self.geocode_entries = geocode_entries or {}
        self.saved_success = []
        self.saved_failed = []

    def get_geocode(self, address, retry_after_days=None):
        return self.geocode_entries.get(address)

    def set_geocode(self, address, lng, lat):
        self.saved_success.append((address, lng, lat))
        self.geocode_entries[address] = {"lng": lng, "lat": lat}

    def set_geocode_failed(self, address):
        self.saved_failed.append(address)
        self.geocode_entries[address] = False


class TestableMoenvAdapter(MoenvIncineratorGeocodeAdapter):
    def __init__(self, cache_db, geocode_map=None):
        self._cache_db = cache_db
        self._geocode_map = geocode_map or {}
        self.geocode_calls = []

    def _open_cache_db(self, source):
        return self._cache_db

    def _geocode(self, address, fetcher):
        self.geocode_calls.append(address)
        return self._geocode_map.get(address)

    def _make_http_fetcher(self):
        return lambda request_data: []


class MoenvIncineratorGeocodeAdapterTestCase(unittest.TestCase):
    def setUp(self):
        self.source = {
            "geocode_address_field": "budadd",
            "geocode_retry_days": 7,
        }
        self.payload = {
            "records": [
                {
                    "wepno": "WEP001",
                    "icnrtname": "Demo Plant",
                    "budadd": "新竹縣竹北市尚義里西濱路二段609號",
                }
            ]
        }

    @patch("backend.data_sources.adapters.moenv_incinerator_geocode.time.sleep", lambda *_: None)
    def test_cache_hit_uses_cached_coordinates_without_geocode(self):
        cache_db = FakeCacheDb(
            {
                "新竹縣竹北市尚義里西濱路二段609號": {
                    "lng": 120.987,
                    "lat": 24.875,
                }
            }
        )
        adapter = TestableMoenvAdapter(cache_db)

        rows = adapter.extract_rows(self.payload, self.source | {"rows_path": ["records"]})

        self.assertEqual(1, len(rows))
        self.assertEqual(120.987, rows[0]["_lng"])
        self.assertEqual(24.875, rows[0]["_lat"])
        self.assertEqual([], adapter.geocode_calls)

    @patch("backend.data_sources.adapters.moenv_incinerator_geocode.time.sleep", lambda *_: None)
    def test_failed_cache_entry_skips_retry_until_window_expires(self):
        cache_db = FakeCacheDb({"新竹縣竹北市尚義里西濱路二段609號": False})
        adapter = TestableMoenvAdapter(
            cache_db,
            geocode_map={"新竹縣竹北市尚義里西濱路二段609號": {"lng": 120.1, "lat": 24.1}},
        )

        rows = adapter.extract_rows(self.payload, self.source | {"rows_path": ["records"]})

        self.assertEqual([], rows)
        self.assertEqual([], adapter.geocode_calls)

    @patch("backend.data_sources.adapters.moenv_incinerator_geocode.time.sleep", lambda *_: None)
    def test_retry_after_window_calls_geocode_and_updates_cache(self):
        cache_db = FakeCacheDb({})
        address = "新竹縣竹北市尚義里西濱路二段609號"
        adapter = TestableMoenvAdapter(
            cache_db,
            geocode_map={address: {"lng": 120.222, "lat": 24.333}},
        )

        rows = adapter.extract_rows(self.payload, self.source | {"rows_path": ["records"]})

        self.assertEqual(1, len(rows))
        self.assertEqual(address, adapter.geocode_calls[0])
        self.assertEqual([(address, 120.222, 24.333)], cache_db.saved_success)

    def test_build_queries_produces_progressive_fallbacks(self):
        address = "新竹縣竹北市尚義里西濱路二段609號"
        queries = MoenvIncineratorGeocodeAdapter._build_queries(address)

        self.assertEqual(address, queries[0])
        self.assertIn("新竹縣竹北市尚義里西濱路二段", queries)
        self.assertIn("新竹縣竹北市", queries)

    @patch("backend.data_sources.adapters.moenv_incinerator_geocode.time.sleep", lambda *_: None)
    def test_top_level_list_payload_is_supported(self):
        cache_db = FakeCacheDb(
            {
                "新竹縣竹北市尚義里西濱路二段609號": {
                    "lng": 120.987,
                    "lat": 24.875,
                }
            }
        )
        adapter = TestableMoenvAdapter(cache_db)

        rows = adapter.extract_rows(self.payload["records"], self.source)

        self.assertEqual(1, len(rows))
        self.assertEqual(120.987, rows[0]["_lng"])
        self.assertEqual(24.875, rows[0]["_lat"])


if __name__ == "__main__":
    unittest.main()
