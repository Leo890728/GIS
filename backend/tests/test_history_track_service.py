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

    def _only_path(self, track):
        # Tests without a configured gap produce exactly one segment.
        self.assertEqual(1, len(track["segments"]))
        return track["segments"][0]["path"]

    def _identity_router(self):
        # leg_router contract: (base_url, profile, coordinates) -> per-pair
        # geometries. The identity router routes each pair as a straight segment
        # and records the waypoint chain of every call.
        def router(base_url, profile, coords):
            self.calls.append([tuple(c) for c in coords])
            return [[list(coords[i]), list(coords[i + 1])] for i in range(len(coords) - 1)]

        return router

    def test_routed_leg_gets_timestamps_along_path(self):
        self._two_leg_setup()

        def fake_route(base_url, profile, coords):
            self.calls.append([tuple(c) for c in coords])
            # One leg with a bent road path between the two endpoints.
            return [[[120.0, 24.0], [120.005, 24.004], [120.01, 24.0]]]

        tracks = build_entity_tracks(
            self.db, "ds", KEY_FIELDS, None, None, leg_router=fake_route, leg_cache={}
        )
        self.assertEqual(1, len(tracks))
        path = self._only_path(tracks[0])
        self.assertEqual(3, len(path))
        times = [datetime.fromtimestamp(p["tMs"] / 1000, tz=timezone.utc) for p in path]
        self.assertEqual(_t(0), times[0])
        self.assertEqual(_t(1), times[-1])
        self.assertTrue(times[0] < times[1] < times[2])  # monotonic
        self.assertEqual(1, len(self.calls))  # routed once

    def test_stationary_leg_is_not_routed(self):
        self._append(_t(0), [_feat("A", 120.0, 24.0, _t(0))])
        self._append(_t(1), [_feat("A", 120.00001, 24.0, _t(1))])  # ~1 m -> below min_move

        tracks = build_entity_tracks(
            self.db, "ds", KEY_FIELDS, None, None, leg_router=self._identity_router(), leg_cache={}
        )
        self.assertEqual(0, len(self.calls))
        self.assertEqual(2, len(self._only_path(tracks[0])))

    def test_excessive_detour_falls_back_to_straight(self):
        self._two_leg_setup()

        def fake_route(base_url, profile, coords):
            self.calls.append([tuple(c) for c in coords])
            # A wildly long detour (far north) -> should be rejected.
            return [[[120.0, 24.0], [120.5, 25.0], [120.01, 24.0]]]

        tracks = build_entity_tracks(
            self.db, "ds", KEY_FIELDS, None, None, leg_router=fake_route, leg_cache={}
        )
        path = self._only_path(tracks[0])
        self.assertEqual(2, len(path))  # straight fallback

    def test_failed_route_falls_back_to_straight(self):
        self._two_leg_setup()

        def failing_route(base_url, profile, coords):
            raise RuntimeError("osrm down")

        tracks = build_entity_tracks(
            self.db, "ds", KEY_FIELDS, None, None, leg_router=failing_route, leg_cache={}
        )
        self.assertEqual(2, len(self._only_path(tracks[0])))

    def test_samples_carry_per_node_properties(self):
        self._append(_t(0), [_feat("A", 120.0, 24.0, _t(0), SpeedValue=10)])
        self._append(_t(1), [_feat("A", 120.01, 24.0, _t(1), SpeedValue=55)])

        tracks = build_entity_tracks(
            self.db, "ds", KEY_FIELDS, None, None, leg_router=self._identity_router(), leg_cache={}
        )
        samples = tracks[0]["samples"]
        self.assertEqual(2, len(samples))
        self.assertEqual(10, samples[0]["properties"]["SpeedValue"])
        self.assertEqual(55, samples[1]["properties"]["SpeedValue"])

    def test_moving_samples_are_batched_into_one_request(self):
        # Three moving samples -> a single batched OSRM call over all waypoints,
        # not one call per consecutive pair.
        self._append(_t(0), [_feat("A", 120.0, 24.0, _t(0))])
        self._append(_t(1), [_feat("A", 120.01, 24.0, _t(1))])
        self._append(_t(2), [_feat("A", 120.02, 24.0, _t(2))])

        build_entity_tracks(
            self.db, "ds", KEY_FIELDS, None, None, leg_router=self._identity_router(), leg_cache={}
        )
        self.assertEqual(1, len(self.calls))  # one batched request
        self.assertEqual(3, len(self.calls[0]))  # all three waypoints in one chain

    def test_stationary_pair_does_not_split_run(self):
        # A stationary middle hop is kept inside the run as a waypoint (one
        # request for the whole session), not split into two requests.
        self._append(_t(0), [_feat("A", 120.0, 24.0, _t(0))])
        self._append(_t(1), [_feat("A", 120.01, 24.0, _t(1))])  # move
        self._append(_t(2), [_feat("A", 120.01001, 24.0, _t(2))])  # ~1 m -> stationary
        self._append(_t(3), [_feat("A", 120.02, 24.0, _t(3))])  # move

        build_entity_tracks(
            self.db, "ds", KEY_FIELDS, None, None, leg_router=self._identity_router(), leg_cache={}
        )
        self.assertEqual(1, len(self.calls))  # single batched request for the session
        self.assertEqual(4, len(self.calls[0]))  # all four points incl. the stationary one

    def test_leg_cache_avoids_duplicate_routing(self):
        # The same directed leg P->Q appears in two distinct entities; the second
        # is served from the shared cache instead of being routed again.
        self._append(_t(0), [_feat("A", 120.0, 24.0, _t(0)), _feat("B", 120.0, 24.0, _t(0))])
        self._append(_t(1), [_feat("A", 120.01, 24.0, _t(1)), _feat("B", 120.01, 24.0, _t(1))])

        cache = {}
        build_entity_tracks(
            self.db, "ds", KEY_FIELDS, None, None, leg_router=self._identity_router(), leg_cache=cache
        )
        # P->Q routed once for the first entity; the second entity hits the cache.
        self.assertEqual(1, len(self.calls))

    def test_routes_run_concurrently(self):
        import threading
        import time

        # Two entities with distinct moving legs -> two independent routing jobs.
        self._append(_t(0), [_feat("A", 120.0, 24.0, _t(0)), _feat("B", 121.0, 24.0, _t(0))])
        self._append(_t(1), [_feat("A", 120.01, 24.0, _t(1)), _feat("B", 121.01, 24.0, _t(1))])

        lock = threading.Lock()
        peak = {"current": 0, "max": 0}

        def slow_router(base_url, profile, coords):
            with lock:
                peak["current"] += 1
                peak["max"] = max(peak["max"], peak["current"])
            time.sleep(0.05)
            with lock:
                peak["current"] -= 1
            return [[list(coords[i]), list(coords[i + 1])] for i in range(len(coords) - 1)]

        tracks = build_entity_tracks(
            self.db, "ds", KEY_FIELDS, None, None,
            leg_router=slow_router, leg_cache={}, max_concurrency=4,
        )
        self.assertEqual(2, len(tracks))
        self.assertGreaterEqual(peak["max"], 2)  # both jobs ran at the same time

    def test_gap_splits_track_into_segments(self):
        # A long time gap between captures = recording interruption -> split, and
        # the bridging leg is not routed.
        self._append(_t(0), [_feat("A", 120.0, 24.0, _t(0))])
        self._append(_t(1), [_feat("A", 120.01, 24.0, _t(1))])  # move within session 1
        self._append(_t(120), [_feat("A", 120.02, 24.0, _t(120))])  # 2 h later -> new session
        self._append(_t(121), [_feat("A", 120.03, 24.0, _t(121))])  # move within session 2

        tracks = build_entity_tracks(
            self.db,
            "ds",
            KEY_FIELDS,
            None,
            None,
            leg_router=self._identity_router(),
            leg_cache={},
            max_gap_seconds=600,  # 10 min
        )
        segments = tracks[0]["segments"]
        self.assertEqual(2, len(segments))
        self.assertEqual(int(_t(0).timestamp() * 1000), segments[0]["from"])
        self.assertEqual(int(_t(1).timestamp() * 1000), segments[0]["to"])
        self.assertEqual(int(_t(120).timestamp() * 1000), segments[1]["from"])
        self.assertEqual(int(_t(121).timestamp() * 1000), segments[1]["to"])
        # The bridging (gap) leg is never routed: only the two intra-session legs.
        self.assertEqual(2, len(self.calls))


if __name__ == "__main__":
    unittest.main()
