import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from backend.services.history_coverage_service import compute_coverage, prepare_regions
from backend.services.history_db import HistoryDb

KEY_FIELDS = ["car"]
IGNORE = ("time", "timestamp")
BASE = datetime(2026, 6, 18, 8, 0, 0, tzinfo=timezone.utc)


def _t(minutes):
    return BASE + timedelta(minutes=minutes)


def _feat(car, lng, lat, t):
    iso = t.isoformat()
    return {
        "type": "Feature",
        "id": f"{car}::{iso}",
        "geometry": {"type": "Point", "coordinates": [lng, lat]},
        "properties": {"car": car, "time": iso},
    }


def _square(code, x0, y0, size=1.0):
    return {
        "properties": {"code": code, "name": f"R-{code}"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[x0, y0], [x0 + size, y0], [x0 + size, y0 + size], [x0, y0 + size], [x0, y0]]],
        },
    }


class HistoryCoverageServiceTestCase(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        self.db = HistoryDb(self.path)
        # Two adjacent unit squares: A=[0,1]x[0,1], B=[1,2]x[0,1].
        self.regions = prepare_regions([_square("A", 0, 0), _square("B", 1, 0)])

    def tearDown(self):
        try:
            os.remove(self.path)
        except OSError:
            pass

    def _append(self, t, features):
        self.db.append("ds", t, features, key_fields=KEY_FIELDS, ignore_fields=IGNORE)

    def _positions(self, frames):
        out = []
        for t in frames:
            coords = []
            for f in self.db.state_at("ds", t, KEY_FIELDS):
                c = (f.get("geometry") or {}).get("coordinates") or []
                if len(c) >= 2:
                    coords.append((c[0], c[1]))
            out.append((t, coords))
        return out

    def test_full_then_partial_coverage(self):
        # Frame 0: a car in A and a car in B -> both serviced.
        self._append(_t(0), [_feat("A1", 0.5, 0.5, _t(0)), _feat("B1", 1.5, 0.5, _t(0))])
        # Frame 1: both cars now in A -> only A serviced.
        self._append(_t(1), [_feat("A1", 0.4, 0.5, _t(1)), _feat("B1", 0.6, 0.5, _t(1))])

        frames = [_t(0), _t(1)]
        result = compute_coverage(self._positions(frames), self.regions)

        self.assertEqual(2, result["totalRegions"])  # union = {A, B}
        self.assertEqual(1.0, result["series"][0]["pct"])  # A+B / 2
        self.assertEqual(0.5, result["series"][1]["pct"])  # A / 2

    def test_points_outside_all_regions_are_ignored(self):
        self._append(_t(0), [_feat("A1", 0.5, 0.5, _t(0)), _feat("X", 99.0, 99.0, _t(0))])
        result = compute_coverage(self._positions([_t(0)]), self.regions)
        self.assertEqual(1, result["totalRegions"])  # only A ever serviced
        self.assertEqual(1.0, result["series"][0]["pct"])

    def test_coverage_drop_flagged_as_anomaly(self):
        # Steady full coverage, then a sharp single-frame drop.
        for m in range(6):
            self._append(_t(m), [_feat("A1", 0.5, 0.5, _t(m)), _feat("B1", 1.5, 0.5, _t(m))])
        # Frame 6: both in A -> coverage halves.
        self._append(_t(6), [_feat("A1", 0.4, 0.5, _t(6)), _feat("B1", 0.6, 0.5, _t(6))])

        frames = [_t(m) for m in range(7)]
        result = compute_coverage(self._positions(frames), self.regions)

        self.assertTrue(result["anomalies"])
        self.assertEqual("coverage_drop", result["anomalies"][0]["reason"])
        # The flagged frame is the last (the drop).
        self.assertEqual(result["series"][-1]["t"], result["anomalies"][-1]["t"])


if __name__ == "__main__":
    unittest.main()
