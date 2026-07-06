import unittest
from unittest import mock

import httpx

from backend.geo import osrm


def _leg(pairs):
    """Build a fake steps=true leg whose geometry is the given coordinates."""
    return {"steps": [{"geometry": {"coordinates": [list(p) for p in pairs]}}]}


def _ok_route(coordinates):
    legs = [_leg([coordinates[i], coordinates[i + 1]]) for i in range(len(coordinates) - 1)]
    return [list(c) for c in coordinates], legs


class RouteLegsBisectTestCase(unittest.TestCase):
    def setUp(self):
        self.coords = [(120.0 + i * 0.001, 24.0) for i in range(5)]

    def test_all_legs_routed_in_one_call(self):
        calls = []

        def fake_fetch(base_url, profile, chunk, *, steps=False, timeout=None):
            calls.append(list(chunk))
            return _ok_route(chunk)

        with mock.patch.object(osrm, "fetch_route", side_effect=fake_fetch):
            legs = osrm.route_legs("http://osrm", "driving", self.coords)

        self.assertEqual(1, len(calls))
        self.assertEqual(len(self.coords) - 1, len(legs))

    def test_one_bad_waypoint_only_straight_lines_its_pairs(self):
        # OSRM rejects any request containing the bad point with 400 NoSegment;
        # bisecting must keep every other pair road-following.
        bad = self.coords[2]

        def fake_fetch(base_url, profile, chunk, *, steps=False, timeout=None):
            if bad in chunk:
                raise RuntimeError("OSRM route request failed: 400 NoSegment")
            return _ok_route(chunk)

        with mock.patch.object(osrm, "fetch_route", side_effect=fake_fetch):
            legs = osrm.route_legs("http://osrm", "driving", self.coords)

        self.assertEqual(len(self.coords) - 1, len(legs))
        # Pairs not touching the bad point are routed (fake router echoes them).
        self.assertEqual([list(self.coords[0]), list(self.coords[1])], legs[0])
        self.assertEqual([list(self.coords[3]), list(self.coords[4])], legs[3])
        # Pairs touching the bad point fall back to straight segments.
        self.assertEqual([list(self.coords[1]), list(self.coords[2])], legs[1])
        self.assertEqual([list(self.coords[2]), list(self.coords[3])], legs[2])

    def test_transport_error_propagates_without_bisecting(self):
        calls = []

        def fake_fetch(base_url, profile, chunk, *, steps=False, timeout=None):
            calls.append(list(chunk))
            raise httpx.ConnectError("connection refused")

        with mock.patch.object(osrm, "fetch_route", side_effect=fake_fetch):
            with self.assertRaises(httpx.ConnectError):
                osrm.route_legs("http://osrm", "driving", self.coords)

        # No retry storm against a dead server.
        self.assertEqual(1, len(calls))


if __name__ == "__main__":
    unittest.main()
