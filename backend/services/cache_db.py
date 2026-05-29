import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS dataset_cache (
    data_id         TEXT PRIMARY KEY,
    features_json   TEXT NOT NULL,
    last_success_at TEXT,
    last_updated_at TEXT,
    expires_at      TEXT
);
CREATE TABLE IF NOT EXISTS geocode_cache (
    address     TEXT PRIMARY KEY,
    lng         REAL,
    lat         REAL,
    failed      INTEGER NOT NULL DEFAULT 0,
    geocoded_at TEXT NOT NULL
);
"""


class CacheDb:
    def __init__(self, db_path):
        self._path = str(db_path)
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_schema()

    # ------------------------------------------------------------------
    # dataset_cache

    def load_dataset(self, data_id):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM dataset_cache WHERE data_id = ?", (data_id,)
            ).fetchone()
        if not row:
            return None
        return {
            "features": json.loads(row["features_json"]),
            "last_success_at": _parse_dt(row["last_success_at"]),
            "last_updated_at": _parse_dt(row["last_updated_at"]),
            "expires_at": _parse_dt(row["expires_at"]),
        }

    def save_dataset(self, data_id, features, last_success_at, last_updated_at, expires_at):
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO dataset_cache
                   (data_id, features_json, last_success_at, last_updated_at, expires_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    data_id,
                    json.dumps(features, ensure_ascii=False),
                    _fmt_dt(last_success_at),
                    _fmt_dt(last_updated_at),
                    _fmt_dt(expires_at),
                ),
            )

    # ------------------------------------------------------------------
    # geocode_cache

    def get_geocode(self, address, retry_after_days=None):
        """
        Returns:
            dict  {"lng": ..., "lat": ...}  — cached hit
            False                            — previously failed, skip retry
            None                             — not in cache yet (or failed entry past retry window)
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT lng, lat, failed, geocoded_at FROM geocode_cache WHERE address = ?",
                (address,),
            ).fetchone()
        if row is None:
            return None
        if row["failed"]:
            if retry_after_days is not None:
                geocoded_at = _parse_dt(row["geocoded_at"])
                if geocoded_at:
                    age_days = (datetime.now(timezone.utc) - geocoded_at).days
                    if age_days >= retry_after_days:
                        return None  # treat as unseen so caller retries
            return False
        return {"lng": row["lng"], "lat": row["lat"]}

    def set_geocode(self, address, lng, lat):
        now = _fmt_dt(datetime.now(timezone.utc))
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO geocode_cache
                   (address, lng, lat, failed, geocoded_at) VALUES (?, ?, ?, 0, ?)""",
                (address, lng, lat, now),
            )

    def set_geocode_failed(self, address):
        now = _fmt_dt(datetime.now(timezone.utc))
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO geocode_cache
                   (address, lng, lat, failed, geocoded_at) VALUES (?, NULL, NULL, 1, ?)""",
                (address, now),
            )

    # ------------------------------------------------------------------

    def _init_schema(self):
        with self._lock, self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _connect(self):
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn


def _fmt_dt(dt):
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).isoformat()


def _parse_dt(s):
    if not s:
        return None
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
