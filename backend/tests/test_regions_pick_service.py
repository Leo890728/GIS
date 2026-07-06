import sqlite3
import unittest

from backend.services.regions_service import RegionsService, RegionsServiceError


class FakeCursor:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class FakeConn:
    """Stands in for a SpatiaLite connection so pick_range_by_point can be
    tested without a real database. `results` is a list of row-or-exception,
    consumed one per execute() call (first = indexed query, second = fallback)."""

    def __init__(self, results):
        self._results = list(results)
        self.calls = []
        self.closed = False

    def execute(self, sql, params):
        self.calls.append((sql, params))
        outcome = self._results.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return FakeCursor(outcome)

    def close(self):
        self.closed = True


def make_service(conn):
    service = RegionsService.__new__(RegionsService)
    service._connect_bounds = lambda load_spatialite=False: conn
    return service


class PickRangeByPointTestCase(unittest.TestCase):
    def test_unsupported_level_raises_value_error(self):
        service = make_service(FakeConn([None]))
        with self.assertRaises(ValueError):
            service.pick_range_by_point(120.0, 24.0, "nope")

    def test_hit_returns_code_name_and_ancestors(self):
        row = {
            "code": "6800100",
            "name": "中正里",
            "ancestor_county": "68000",
            "ancestor_township": "6800100",
        }
        conn = FakeConn([row])
        service = make_service(conn)

        result = service.pick_range_by_point(120.65, 24.15, "village")

        self.assertEqual(
            {
                "hit": True,
                "level": "village",
                "code": "6800100",
                "name": "中正里",
                "ancestors": {"county": "68000", "township": "6800100"},
            },
            result,
        )
        self.assertTrue(conn.closed)
        # indexed query passes bbox (lng,lng,lat,lat) + point (lng,lat)
        _, params = conn.calls[0]
        self.assertEqual((120.65, 120.65, 24.15, 24.15, 120.65, 24.15), params)

    def test_miss_returns_hit_false(self):
        service = make_service(FakeConn([None]))
        self.assertEqual(
            {"hit": False, "level": "county"},
            service.pick_range_by_point(120.0, 24.0, "county"),
        )

    def test_stat_zone_uses_code_as_name_and_omits_empty_ancestors(self):
        row = {
            "code": "A1234-0001",
            "name": "A1234-0001",  # name_col is None → SELECT aliases code AS name
            "ancestor_county": "68000",
            "ancestor_township": "6800100",
            "ancestor_stat_zone_2": "",  # empty → dropped
            "ancestor_stat_zone_1": None,  # null → dropped
        }
        service = make_service(FakeConn([row]))

        result = service.pick_range_by_point(120.65, 24.15, "stat_zone")

        self.assertEqual("A1234-0001", result["name"])
        self.assertEqual({"county": "68000", "township": "6800100"}, result["ancestors"])

    def test_missing_spatial_index_falls_back_to_scan(self):
        row = {"code": "68000", "name": "臺中市", "ancestor_county": "68000"}
        conn = FakeConn([sqlite3.OperationalError("no such table: idx_township_GEOMETRY"), row])
        service = make_service(conn)

        result = service.pick_range_by_point(120.65, 24.15, "township")

        self.assertEqual("68000", result["code"])
        self.assertEqual(2, len(conn.calls))  # indexed failed, fallback ran

    def test_non_index_operational_error_wrapped(self):
        conn = FakeConn([sqlite3.OperationalError("no such function: ST_Covers")])
        service = make_service(conn)

        with self.assertRaises(RegionsServiceError):
            service.pick_range_by_point(120.65, 24.15, "township")
        self.assertTrue(conn.closed)


if __name__ == "__main__":
    unittest.main()
