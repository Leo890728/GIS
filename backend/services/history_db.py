"""Diff-based history store for Live (dynamic) datasets.

Each capture of a dataset is appended either as a full ``keyframe`` (the
whole feature list) or as a ``diff`` relative to the previously reconstructed
state. State at any past instant is rebuilt by taking the latest keyframe at or
before that instant and replaying the diffs after it.

Entities are tracked by a configurable *stable key* (``key_fields``) extracted
from ``feature.properties`` so that a moving point (whose ``id`` embeds a
timestamp) is recognised as the same entity across captures. A configurable set
of *volatile* fields (``ignore_fields``, typically the timestamp) is excluded
from change detection so that a stationary entity reporting a fresh timestamp
each poll does not bloat the diff chain.
"""

import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.services.sqlite_util import connect as sqlite_connect

_SCHEMA = """
CREATE TABLE IF NOT EXISTS dataset_history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    data_id      TEXT NOT NULL,
    captured_at  TEXT NOT NULL,
    kind         TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_history_data_time
    ON dataset_history (data_id, captured_at);
"""

DEFAULT_KEYFRAME_INTERVAL = 50


class HistoryDb:
    def __init__(self, db_path):
        self._path = str(db_path)
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_schema()

    # ------------------------------------------------------------------
    # write

    def append(
        self,
        data_id,
        captured_at,
        features,
        *,
        key_fields,
        ignore_fields=("timestamp",),
        keyframe_interval=DEFAULT_KEYFRAME_INTERVAL,
        retention_days=None,
    ):
        """Append one capture.

        Returns ``"keyframe"``, ``"diff"`` or ``None`` (capture skipped because
        nothing changed since the previous one).
        """
        features = list(features or [])
        interval = max(1, int(keyframe_interval or DEFAULT_KEYFRAME_INTERVAL))
        with self._lock, self._connect() as conn:
            keyframe = self._last_keyframe(conn, data_id)
            if keyframe is None:
                self._insert(conn, data_id, captured_at, "keyframe", features)
                kind = "keyframe"
            else:
                diff_count = self._count_since(conn, data_id, keyframe["id"])
                if diff_count >= interval:
                    self._insert(conn, data_id, captured_at, "keyframe", features)
                    kind = "keyframe"
                else:
                    rows = self._rows_from(conn, data_id, keyframe["id"])
                    previous = _reconstruct(rows, key_fields)
                    diff = _compute_diff(previous, features, key_fields, ignore_fields)
                    if not (diff["added"] or diff["changed"] or diff["removed"]):
                        kind = None
                    else:
                        self._insert(conn, data_id, captured_at, "diff", diff)
                        kind = "diff"

            if retention_days is not None:
                self._prune(conn, data_id, retention_days)
        return kind

    # ------------------------------------------------------------------
    # read

    def range(self, data_id):
        """Available time span: ``{from, to, count}`` or ``None`` when empty."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT MIN(captured_at) lo, MAX(captured_at) hi, COUNT(*) c "
                "FROM dataset_history WHERE data_id = ?",
                (data_id,),
            ).fetchone()
        if not row or not row["c"]:
            return None
        return {"from": _parse_dt(row["lo"]), "to": _parse_dt(row["hi"]), "count": row["c"]}

    def frames(self, data_id, frm=None, to=None):
        """Capture timestamps (ascending) within an optional window."""
        clauses = ["data_id = ?"]
        params = [data_id]
        if frm is not None:
            clauses.append("captured_at >= ?")
            params.append(_fmt_dt(frm))
        if to is not None:
            clauses.append("captured_at <= ?")
            params.append(_fmt_dt(to))
        sql = (
            "SELECT captured_at FROM dataset_history WHERE "
            + " AND ".join(clauses)
            + " ORDER BY id ASC"
        )
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_parse_dt(r["captured_at"]) for r in rows]

    def entity_tracks(self, data_id, key_fields, frm=None, to=None):
        """Per-entity position samples over a window.

        Returns ``{key: {"properties": <latest props>, "samples": [{"t": dt,
        "lng": .., "lat": ..}, ...]}}``. Samples are taken at every capture
        where the entity's position was (re)declared — i.e. keyframes plus the
        diffs that added/changed it — starting from the keyframe at or before
        ``frm`` so the first leg can be interpolated from before the window.
        """
        with self._connect() as conn:
            anchor = None
            if frm is not None:
                anchor = conn.execute(
                    "SELECT id FROM dataset_history "
                    "WHERE data_id = ? AND kind = 'keyframe' AND captured_at <= ? "
                    "ORDER BY captured_at DESC, id DESC LIMIT 1",
                    (data_id, _fmt_dt(frm)),
                ).fetchone()
            if anchor is None:
                anchor = conn.execute(
                    "SELECT id FROM dataset_history "
                    "WHERE data_id = ? AND kind = 'keyframe' ORDER BY id ASC LIMIT 1",
                    (data_id,),
                ).fetchone()
            if anchor is None:
                return {}

            sql = "SELECT captured_at, kind, payload_json FROM dataset_history WHERE data_id = ? AND id >= ?"
            params = [data_id, anchor["id"]]
            if to is not None:
                sql += " AND captured_at <= ?"
                params.append(_fmt_dt(to))
            sql += " ORDER BY id ASC"
            rows = conn.execute(sql, params).fetchall()

        samples = {}
        properties = {}

        def add(feature, captured_at):
            key = _feature_key(feature, key_fields)
            coords = (feature.get("geometry") or {}).get("coordinates") or []
            if len(coords) < 2:
                return
            lng = _to_float(coords[0])
            lat = _to_float(coords[1])
            if lng is None or lat is None:
                return
            props = feature.get("properties") or {}
            samples.setdefault(key, []).append({"t": captured_at, "lng": lng, "lat": lat, "properties": props})
            properties[key] = props

        for row in rows:
            captured_at = _parse_dt(row["captured_at"])
            payload = json.loads(row["payload_json"])
            if row["kind"] == "keyframe":
                for feature in payload:
                    add(feature, captured_at)
            else:
                for feature in payload.get("added", []):
                    add(feature, captured_at)
                for feature in payload.get("changed", []):
                    add(feature, captured_at)

        return {
            key: {"properties": properties.get(key, {}), "samples": series}
            for key, series in samples.items()
        }

    def state_at(self, data_id, t, key_fields):
        """Reconstruct the feature list at instant ``t`` (nearest capture <= t)."""
        with self._connect() as conn:
            keyframe = conn.execute(
                "SELECT id FROM dataset_history "
                "WHERE data_id = ? AND kind = 'keyframe' AND captured_at <= ? "
                "ORDER BY captured_at DESC, id DESC LIMIT 1",
                (data_id, _fmt_dt(t)),
            ).fetchone()
            if keyframe is None:
                return []
            rows = conn.execute(
                "SELECT kind, payload_json FROM dataset_history "
                "WHERE data_id = ? AND id >= ? AND captured_at <= ? "
                "ORDER BY id ASC",
                (data_id, keyframe["id"], _fmt_dt(t)),
            ).fetchall()
        features = _reconstruct(rows, key_fields)
        # Tag each feature with the same stable entity key used by entity_tracks
        # so the frontend can map a clicked point to its road-following track.
        for feature in features:
            props = feature.setdefault("properties", {})
            props["__trackKey"] = _feature_key(feature, key_fields)
        return features

    # ------------------------------------------------------------------
    # internals

    def _insert(self, conn, data_id, captured_at, kind, payload):
        conn.execute(
            "INSERT INTO dataset_history (data_id, captured_at, kind, payload_json) "
            "VALUES (?, ?, ?, ?)",
            (data_id, _fmt_dt(captured_at), kind, json.dumps(payload, ensure_ascii=False)),
        )

    def _last_keyframe(self, conn, data_id):
        return conn.execute(
            "SELECT id, captured_at FROM dataset_history "
            "WHERE data_id = ? AND kind = 'keyframe' ORDER BY id DESC LIMIT 1",
            (data_id,),
        ).fetchone()

    def _count_since(self, conn, data_id, after_id):
        return conn.execute(
            "SELECT COUNT(*) c FROM dataset_history WHERE data_id = ? AND id > ?",
            (data_id, after_id),
        ).fetchone()["c"]

    def _rows_from(self, conn, data_id, from_id):
        return conn.execute(
            "SELECT kind, payload_json FROM dataset_history "
            "WHERE data_id = ? AND id >= ? ORDER BY id ASC",
            (data_id, from_id),
        ).fetchall()

    def _prune(self, conn, data_id, retention_days):
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        # Keep the latest keyframe at or before the cutoff so that everything
        # still inside the window remains reconstructable.
        anchor = conn.execute(
            "SELECT id FROM dataset_history "
            "WHERE data_id = ? AND kind = 'keyframe' AND captured_at <= ? "
            "ORDER BY captured_at DESC, id DESC LIMIT 1",
            (data_id, _fmt_dt(cutoff)),
        ).fetchone()
        if anchor is None:
            return
        conn.execute(
            "DELETE FROM dataset_history WHERE data_id = ? AND id < ?",
            (data_id, anchor["id"]),
        )

    def _init_schema(self):
        with self._lock, self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _connect(self):
        return sqlite_connect(self._path)


# ----------------------------------------------------------------------
# diff / reconstruction helpers


def _feature_key(feature, key_fields):
    if key_fields:
        props = feature.get("properties") or {}
        parts = [str(props.get(field, "")).strip() for field in key_fields]
        key = "::".join(parts).strip(":")
        if key:
            return key
    return str(feature.get("id", ""))


def _signature(feature, ignore_fields):
    """Stable representation used to detect meaningful changes.

    Excludes the top-level ``id`` (which may embed a timestamp) and any
    ``ignore_fields`` from ``properties``.
    """
    props = feature.get("properties") or {}
    ignore = set(ignore_fields or ())
    kept = {k: v for k, v in props.items() if k not in ignore}
    return json.dumps(
        {"geometry": feature.get("geometry"), "properties": kept},
        sort_keys=True,
        ensure_ascii=False,
    )


def _compute_diff(previous, current, key_fields, ignore_fields):
    prev_map = {_feature_key(f, key_fields): f for f in previous}
    curr_map = {_feature_key(f, key_fields): f for f in current}

    added = [f for k, f in curr_map.items() if k not in prev_map]
    removed = [k for k in prev_map if k not in curr_map]
    changed = [
        f
        for k, f in curr_map.items()
        if k in prev_map and _signature(prev_map[k], ignore_fields) != _signature(f, ignore_fields)
    ]
    return {"added": added, "changed": changed, "removed": removed}


def _reconstruct(rows, key_fields):
    """Replay ordered rows (first must be a keyframe) into a feature list."""
    state = {}
    for row in rows:
        payload = json.loads(row["payload_json"])
        if row["kind"] == "keyframe":
            state = {_feature_key(f, key_fields): f for f in payload}
        else:
            for feature in payload.get("added", []):
                state[_feature_key(feature, key_fields)] = feature
            for feature in payload.get("changed", []):
                state[_feature_key(feature, key_fields)] = feature
            for key in payload.get("removed", []):
                state.pop(key, None)
    return list(state.values())


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
