import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

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


def _coords_by_car(features):
    out = {}
    for f in features:
        out[f["properties"]["car"]] = tuple(f["geometry"]["coordinates"])
    return out


class HistoryDbTestCase(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        self.db = HistoryDb(self.path)

    def tearDown(self):
        try:
            os.remove(self.path)
        except OSError:
            pass

    def _append(self, t, features, **kwargs):
        return self.db.append(
            "ds",
            t,
            features,
            key_fields=KEY_FIELDS,
            ignore_fields=IGNORE,
            **kwargs,
        )

    # ------------------------------------------------------------------

    def test_first_append_is_keyframe(self):
        kind = self._append(_t(0), [_feat("A", 0, 0, _t(0))])
        self.assertEqual("keyframe", kind)

        rng = self.db.range("ds")
        self.assertEqual(1, rng["count"])
        self.assertEqual(_t(0), rng["from"])
        self.assertEqual(_t(0), rng["to"])

        state = self.db.state_at("ds", _t(0), KEY_FIELDS)
        self.assertEqual({"A": (0, 0)}, _coords_by_car(state))

    def test_stationary_entity_with_new_timestamp_is_skipped(self):
        self._append(_t(0), [_feat("A", 0, 0, _t(0))])
        # Same position, only the timestamp differs -> no meaningful change.
        kind = self._append(_t(1), [_feat("A", 0, 0, _t(1))])
        self.assertIsNone(kind)
        # Only the keyframe row exists; nothing was stored for the second poll.
        self.assertEqual(1, self.db.range("ds")["count"])

    def test_moved_entity_produces_diff(self):
        self._append(_t(0), [_feat("A", 0, 0, _t(0))])
        kind = self._append(_t(1), [_feat("A", 1, 1, _t(1))])
        self.assertEqual("diff", kind)
        state = self.db.state_at("ds", _t(1), KEY_FIELDS)
        self.assertEqual({"A": (1, 1)}, _coords_by_car(state))
        # Earlier instant still reflects the original position.
        state0 = self.db.state_at("ds", _t(0), KEY_FIELDS)
        self.assertEqual({"A": (0, 0)}, _coords_by_car(state0))

    def test_added_and_removed_entities(self):
        self._append(_t(0), [_feat("A", 0, 0, _t(0))])
        kind_add = self._append(_t(1), [_feat("A", 0, 0, _t(1)), _feat("B", 2, 2, _t(1))])
        self.assertEqual("diff", kind_add)
        self.assertEqual({"A": (0, 0), "B": (2, 2)}, _coords_by_car(self.db.state_at("ds", _t(1), KEY_FIELDS)))

        kind_remove = self._append(_t(2), [_feat("B", 2, 2, _t(2))])
        self.assertEqual("diff", kind_remove)
        self.assertEqual({"B": (2, 2)}, _coords_by_car(self.db.state_at("ds", _t(2), KEY_FIELDS)))

    def test_keyframe_triggered_after_interval(self):
        # interval=3: 1st keyframe, then diffs, then keyframe once 3 diffs exist.
        self._append(_t(0), [_feat("A", 0, 0, _t(0))], keyframe_interval=3)
        for i in range(1, 4):
            kind = self._append(_t(i), [_feat("A", i, i, _t(i))], keyframe_interval=3)
            self.assertEqual("diff", kind)
        kind = self._append(_t(4), [_feat("A", 4, 4, _t(4))], keyframe_interval=3)
        self.assertEqual("keyframe", kind)

    def test_state_at_matches_snapshots_across_sequence(self):
        snapshots = [
            (_t(0), [_feat("A", 0, 0, _t(0)), _feat("B", 5, 5, _t(0))]),
            (_t(1), [_feat("A", 1, 0, _t(1)), _feat("B", 5, 5, _t(1))]),          # A moves
            (_t(2), [_feat("A", 1, 0, _t(2)), _feat("B", 5, 5, _t(2)), _feat("C", 9, 9, _t(2))]),  # C appears
            (_t(3), [_feat("A", 2, 0, _t(3)), _feat("C", 9, 9, _t(3))]),          # B leaves, A moves
        ]
        for t, feats in snapshots:
            self._append(t, feats, keyframe_interval=2)

        for t, feats in snapshots:
            reconstructed = _coords_by_car(self.db.state_at("ds", t, KEY_FIELDS))
            self.assertEqual(_coords_by_car(feats), reconstructed, f"mismatch at {t.isoformat()}")

    def test_state_before_first_capture_is_empty(self):
        self._append(_t(5), [_feat("A", 0, 0, _t(5))])
        self.assertEqual([], self.db.state_at("ds", _t(0), KEY_FIELDS))

    def test_frames_window(self):
        for i in range(4):
            self._append(_t(i), [_feat("A", i, i, _t(i))], keyframe_interval=10)
        frames = self.db.frames("ds", _t(1), _t(2))
        self.assertEqual([_t(1), _t(2)], frames)

    def test_prune_keeps_reconstructable_window(self):
        # All captures are ~30 days old; retention of 7 days should drop the
        # oldest rows but keep enough (anchored on a keyframe) to reconstruct.
        old = datetime.now(timezone.utc) - timedelta(days=30)

        def ot(minutes):
            return old + timedelta(minutes=minutes)

        for i in range(6):
            self._append(
                ot(i),
                [_feat("A", i, i, ot(i))],
                keyframe_interval=2,
                retention_days=7,
            )

        rng = self.db.range("ds")
        # Pruned below the original 6 rows, but the latest state is intact.
        self.assertLess(rng["count"], 6)
        state = self.db.state_at("ds", ot(5), KEY_FIELDS)
        self.assertEqual({"A": (5, 5)}, _coords_by_car(state))


if __name__ == "__main__":
    unittest.main()
