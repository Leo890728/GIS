import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from backend.services.history_db import HistoryDb
from backend.services.history_track_service import build_entity_tracks

KEY_FIELDS = ["car"]
IGNORE = ("time", "timestamp")
BASE = datetime(2026, 6, 18, 8, 0, 0, tzinfo=timezone.utc)


def _t(minutes):
    return BASE + timedelta(minutes=minutes)


def _feat(car, lng, lat, t, **extra):
    iso = t.isoformat()
    return {
        "type": "Feature",
        "id": f"{car}::{iso}",
        "geometry": {"type": "Point", "coordinates": [lng, lat]},
        "properties": {"car": car, "time": iso, **extra},
    }


class HistoryTrackServiceTestCase(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        self.db = HistoryDb(self.path)
        self.calls = []

    def tearDown(self):
        try:
            os.remove(self.path)
        except OSError:
            pass

    def _append(self, t, features):
        self.db.append("ds", t, features, key_fields=KEY_FIELDS, ignore_fields=IGNORE)

    def _two_leg_setup(self):
        self._append(_t(0), [_feat("A", 120.0, 24.0, _t(0))])
        self._append(_t(1), [_feat("A", 120.01, 24.0, _t(1))])  # ~1 km east -> routed

    def test_routed_leg_gets_timestamps_along_path(self):
        self._two_leg_setup()

        def fake_route(base_url, profile, coords):
            self.calls.append(coords)
            # A bent road path between the two endpoints.
            return [[120.0, 24.0], [120.005, 24.004], [120.01, 24.0]]

        tracks = build_entity_tracks(
            self.db, "ds", KEY_FIELDS, None, None, route_fetcher=fake_route, leg_cache={}
        )
        self.assertEqual(1, len(tracks))
        path = tracks[0]["path"]
        self.assertEqual(3, len(path))
        times = [datetime.fromisoformat(p["t"].replace("Z", "+00:00")) for p in path]
        self.assertEqual(_t(0), times[0])
        self.assertEqual(_t(1), times[-1])
        self.assertTrue(times[0] < times[1] < times[2])  # monotonic
        self.assertEqual(1, len(self.calls))  # routed once

    def test_stationary_leg_is_not_routed(self):
        self._append(_t(0), [_feat("A", 120.0, 24.0, _t(0))])
        self._append(_t(1), [_feat("A", 120.00001, 24.0, _t(1))])  # ~1 m -> below min_move

        def fake_route(base_url, profile, coords):
            self.calls.append(coords)
            return [[0, 0], [1, 1]]

        tracks = build_entity_tracks(
            self.db, "ds", KEY_FIELDS, None, None, route_fetcher=fake_route, leg_cache={}
        )
        self.assertEqual(0, len(self.calls))
        self.assertEqual(2, len(tracks[0]["path"]))

    def test_excessive_detour_falls_back_to_straight(self):
        self._two_leg_setup()

        def fake_route(base_url, profile, coords):
            self.calls.append(coords)
            # A wildly long detour (far north) -> should be rejected.
            return [[120.0, 24.0], [120.5, 25.0], [120.01, 24.0]]

        tracks = build_entity_tracks(
            self.db, "ds", KEY_FIELDS, None, None, route_fetcher=fake_route, leg_cache={}
        )
        path = tracks[0]["path"]
        self.assertEqual(2, len(path))  # straight fallback

    def test_failed_route_falls_back_to_straight(self):
        self._two_leg_setup()

        def failing_route(base_url, profile, coords):
            raise RuntimeError("osrm down")

        tracks = build_entity_tracks(
            self.db, "ds", KEY_FIELDS, None, None, route_fetcher=failing_route, leg_cache={}
        )
        self.assertEqual(2, len(tracks[0]["path"]))

    def test_samples_carry_per_node_properties(self):
        self._append(_t(0), [_feat("A", 120.0, 24.0, _t(0), SpeedValue=10)])
        self._append(_t(1), [_feat("A", 120.01, 24.0, _t(1), SpeedValue=55)])

        def fake_route(base_url, profile, coords):
            return [coords[0], coords[1]]

        tracks = build_entity_tracks(
            self.db, "ds", KEY_FIELDS, None, None, route_fetcher=fake_route, leg_cache={}
        )
        samples = tracks[0]["samples"]
        self.assertEqual(2, len(samples))
        self.assertEqual(10, samples[0]["properties"]["SpeedValue"])
        self.assertEqual(55, samples[1]["properties"]["SpeedValue"])

    def test_leg_cache_avoids_duplicate_routing(self):
        # Same leg appears twice (A moves out and back over the same segment).
        self._append(_t(0), [_feat("A", 120.0, 24.0, _t(0))])
        self._append(_t(1), [_feat("A", 120.01, 24.0, _t(1))])
        self._append(_t(2), [_feat("A", 120.0, 24.0, _t(2))])

        def fake_route(base_url, profile, coords):
            self.calls.append((round(coords[0][0], 5), round(coords[1][0], 5)))
            return [coords[0], coords[1]]

        cache = {}
        build_entity_tracks(self.db, "ds", KEY_FIELDS, None, None, route_fetcher=fake_route, leg_cache=cache)
        # Two distinct directed legs (A->B and B->A); each routed once, cached after.
        self.assertEqual(2, len(self.calls))


if __name__ == "__main__":
    unittest.main()
