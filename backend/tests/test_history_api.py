import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from backend.app import create_app
from backend.services.dataset_service import DatasetService
from backend.services.history_db import HistoryDb


class MockAdapter:
    def fetch_payload(self, fetcher, source):
        return fetcher({"url": source["url"], "method": "GET"})

    def extract_rows(self, payload, source):
        return payload


class Clock:
    def __init__(self):
        self.t = datetime(2026, 6, 18, 8, 0, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += timedelta(seconds=seconds)


def _iso(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class HistoryApiTestCase(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        self.clock = Clock()
        self.rows = []

        def fetcher(_request):
            return list(self.rows)

        sources = {
            "ds": {
                "adapter": "mock",
                "url": "mock://ds",
                "refresh_seconds": 60,
                "fields": {"id_parts": ["car", "time"], "lng": "X", "lat": "Y", "timestamp": "time"},
                "history": {"enabled": True, "key": ["car"], "keyframe_interval": 50, "retention_days": 7},
            },
            "static_ds": {
                "adapter": "mock",
                "url": "mock://static",
                "refresh_seconds": 60,
                "fields": {"id_parts": ["car"], "lng": "X", "lat": "Y"},
            },
        }
        self.service = DatasetService(
            sources,
            fetcher=fetcher,
            now_func=self.clock,
            adapters={"mock": MockAdapter()},
            history_db=HistoryDb(self.path),
        )

        app = create_app({"DATASET_SERVICE": self.service, "REGIONS_SERVICE": object()})
        app.testing = True
        self.client = app.test_client()
        self.t0 = self.clock.t

    def tearDown(self):
        try:
            os.remove(self.path)
        except OSError:
            pass

    def _row(self, car, lng, lat):
        return {"car": car, "X": lng, "Y": lat, "time": _iso(self.clock.t)}

    def _capture(self, rows):
        self.rows = rows
        self.service.refresh("ds", force=True)

    def _build_three_captures(self):
        self._capture([self._row("A", 120.0, 24.0)])               # keyframe
        self.t1 = self.clock.t
        self.clock.advance(60)
        self._capture([self._row("A", 121.0, 24.0)])               # diff: A moved
        self.t2 = self.clock.t
        self.clock.advance(60)
        self._capture([self._row("A", 121.0, 24.0), self._row("B", 122.0, 25.0)])  # diff: B added
        self.t3 = self.clock.t

    # ------------------------------------------------------------------

    def test_refresh_records_history_range(self):
        self._build_three_captures()
        resp = self.client.get("/data/history/ds/range")
        self.assertEqual(200, resp.status_code)
        body = resp.get_json()
        self.assertEqual("ds", body["dataId"])
        self.assertEqual(3, body["count"])
        self.assertEqual(60, body["intervalSeconds"])
        self.assertEqual(_iso(self.t0), body["from"])

    def test_frames_lists_captures(self):
        self._build_three_captures()
        body = self.client.get("/data/history/ds/frames").get_json()
        self.assertEqual(3, len(body["frames"]))

    def test_state_at_reconstructs_past(self):
        self._build_three_captures()
        # At t1 only A exists at its original position.
        at1 = self.client.get(f"/data/history/ds/at?t={_iso(self.t1)}").get_json()
        cars = {f["properties"]["car"]: f["geometry"]["coordinates"] for f in at1["features"]}
        self.assertEqual({"A": [120.0, 24.0]}, cars)

        # At the latest capture both A (moved) and B are present.
        at3 = self.client.get(f"/data/history/ds/at?t={_iso(self.t3)}").get_json()
        cars3 = {f["properties"]["car"]: f["geometry"]["coordinates"] for f in at3["features"]}
        self.assertEqual({"A": [121.0, 24.0], "B": [122.0, 25.0]}, cars3)

    def test_unknown_dataset_returns_404(self):
        self.assertEqual(404, self.client.get("/data/history/nope/range").status_code)

    def test_non_history_dataset_returns_404(self):
        self.assertEqual(404, self.client.get("/data/history/static_ds/range").status_code)

    def test_at_requires_timestamp(self):
        self.assertEqual(400, self.client.get("/data/history/ds/at").status_code)

    def test_at_rejects_bad_timestamp(self):
        self.assertEqual(400, self.client.get("/data/history/ds/at?t=not-a-time").status_code)

    @staticmethod
    def _parse_sse(body):
        events = []
        for block in body.split("\n\n"):
            if not block.strip():
                continue
            event = "message"
            data_lines = []
            for line in block.splitlines():
                if line.startswith("event:"):
                    event = line.split(":", 1)[1].strip()
                elif line.startswith("data:"):
                    data_lines.append(line.split(":", 1)[1].strip())
            events.append((event, json.loads("\n".join(data_lines)) if data_lines else None))
        return events

    def test_track_stream_emits_progress_tracks_then_result(self):
        self._build_three_captures()
        # Inject a router so the stream never touches a real OSRM instance.
        self.service.osrm_leg_router = lambda b, p, coords: [
            [list(coords[i]), list(coords[i + 1])] for i in range(len(coords) - 1)
        ]

        resp = self.client.get("/data/history/ds/track/stream")
        self.assertEqual(200, resp.status_code)
        self.assertEqual("text/event-stream", resp.mimetype)

        events = self._parse_sse(resp.get_data(as_text=True))
        kinds = [kind for kind, _ in events]
        self.assertIn("progress", kinds)
        self.assertEqual("result", kinds[-1])

        # Progress is monotonic and ends at total.
        progress = [payload for kind, payload in events if kind == "progress"]
        self.assertEqual(progress[0]["done"], 0)
        self.assertEqual(progress[-1]["done"], progress[-1]["total"])

        # One `track` event per entity; the final result only carries metadata.
        tracks = [payload for kind, payload in events if kind == "track"]
        self.assertEqual({"A", "B"}, {t["key"] for t in tracks})

        result = events[-1][1]
        self.assertEqual("ds", result["dataId"])
        self.assertNotIn("tracks", result)

    def test_track_stream_unknown_dataset_emits_error(self):
        resp = self.client.get("/data/history/nope/track/stream")
        # The stream itself opens 200; the failure is delivered as an error event.
        self.assertEqual(200, resp.status_code)
        events = self._parse_sse(resp.get_data(as_text=True))
        self.assertEqual("error", events[-1][0])


if __name__ == "__main__":
    unittest.main()
