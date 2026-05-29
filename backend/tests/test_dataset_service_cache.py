import unittest
from datetime import datetime, timedelta, timezone

from backend.services.dataset_service import DatasetService


class MockAdapter:
    def fetch_payload(self, fetcher, source):
        return fetcher({"url": source["url"], "method": "GET"})

    def extract_rows(self, payload, source):
        return payload


class FakeCacheDb:
    def __init__(self, stored_by_id=None):
        self._stored_by_id = stored_by_id or {}
        self.saved = []

    def load_dataset(self, data_id):
        return self._stored_by_id.get(data_id)

    def save_dataset(self, data_id, features, last_success_at, last_updated_at, expires_at):
        self.saved.append((data_id, features, last_success_at, last_updated_at, expires_at))


def _now():
    return datetime(2026, 5, 28, 12, 0, 0, tzinfo=timezone.utc)


def _valid_feature(feature_id="WEP001", lng=120.65, lat=24.14):
    return {
        "type": "Feature",
        "id": feature_id,
        "geometry": {"type": "Point", "coordinates": [lng, lat]},
        "properties": {"wepno": feature_id},
    }


class DatasetServiceCacheValidationTestCase(unittest.TestCase):
    def setUp(self):
        self.fetch_calls = []

        def fetcher(request_data):
            self.fetch_calls.append(request_data)
            return [{"wepno": "WEP002", "_lng": "120.7", "_lat": "24.2"}]

        self.source_id = "moenv_incinerators"
        self.source_config = {
            self.source_id: {
                "adapter": "mock",
                "url": "mock://moenv",
                "refresh_seconds": 86400,
                "fields": {
                    "id_parts": ["wepno"],
                    "lng": "_lng",
                    "lat": "_lat",
                },
            }
        }
        self.adapters = {"mock": MockAdapter()}
        self.fetcher = fetcher

    def _service(self, cache_db=None):
        return DatasetService(
            self.source_config,
            fetcher=self.fetcher,
            now_func=_now,
            adapters=self.adapters,
            cache_db=cache_db,
        )

    def test_invalid_cached_features_are_ignored_and_rebuilt(self):
        service = self._service(cache_db=FakeCacheDb())
        service._cache[self.source_id] = {
            "features": [{"wepno": "legacy-row-only"}],
            "expires_at": _now() + timedelta(hours=1),
        }

        features = service.refresh(self.source_id)

        self.assertEqual(1, len(self.fetch_calls))
        self.assertEqual("Feature", features[0]["type"])
        self.assertIn("geometry", features[0])
        self.assertIn("properties", features[0])

    def test_upstream_error_falls_back_to_valid_in_memory_cache(self):
        def failing_fetcher(request_data):
            raise RuntimeError("upstream down")

        service = DatasetService(
            self.source_config,
            fetcher=failing_fetcher,
            now_func=_now,
            adapters=self.adapters,
            cache_db=FakeCacheDb(),
        )
        feature = _valid_feature()
        service._cache[self.source_id] = {
            "features": [feature],
            "expires_at": _now() - timedelta(seconds=1),
        }

        features = service.refresh(self.source_id)
        self.assertEqual([feature], features)

    def test_upstream_error_with_only_invalid_cache_raises(self):
        def failing_fetcher(request_data):
            raise RuntimeError("upstream down")

        invalid_cached = {
            "features": [{"wepno": "legacy"}],
            "last_success_at": _now(),
            "last_updated_at": _now(),
            "expires_at": _now() + timedelta(hours=1),
        }
        cache_db = FakeCacheDb({self.source_id: invalid_cached})

        service = DatasetService(
            self.source_config,
            fetcher=failing_fetcher,
            now_func=_now,
            adapters=self.adapters,
            cache_db=cache_db,
        )
        service._cache[self.source_id] = invalid_cached

        with self.assertRaises(RuntimeError):
            service.refresh(self.source_id)

    def test_upstream_error_falls_back_to_valid_sqlite_cache(self):
        def failing_fetcher(request_data):
            raise RuntimeError("upstream down")

        valid_cached = {
            "features": [_valid_feature("WEP777")],
            "last_success_at": _now(),
            "last_updated_at": _now(),
            "expires_at": _now() + timedelta(hours=1),
        }
        cache_db = FakeCacheDb({self.source_id: valid_cached})

        service = DatasetService(
            self.source_config,
            fetcher=failing_fetcher,
            now_func=_now,
            adapters=self.adapters,
            cache_db=cache_db,
        )
        service._cache[self.source_id] = {
            "features": [{"wepno": "legacy"}],
            "expires_at": _now() - timedelta(seconds=1),
        }

        features = service.refresh(self.source_id)
        self.assertEqual(valid_cached["features"], features)


if __name__ == "__main__":
    unittest.main()
