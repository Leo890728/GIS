from datetime import datetime, timedelta, timezone
import json
import hashlib
import httpx

from backend.data_sources import ADAPTER_REGISTRY
from backend.services.history_track_service import DEFAULT_OSRM_CONCURRENCY, build_entity_tracks
from backend.services.point_aggregate import aggregate_grouped
from backend.services.point_query import query_points

# Smooth tracks split into a new segment when a gap exceeds this many poll cycles.
HISTORY_GAP_FACTOR = 4


def utc_now():
    return datetime.now(timezone.utc)


def iso_utc(value):
    if not value:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class DatasetService:
    def __init__(self, sources, fetcher=None, now_func=None, adapters=None, cache_db=None, history_db=None, osrm_leg_router=None):
        self.sources = sources or {}
        self.fetcher = fetcher or self._default_fetcher
        self.now_func = now_func or utc_now
        self.adapters = adapters or ADAPTER_REGISTRY
        self.cache_db = cache_db
        self.history_db = history_db
        self.osrm_leg_router = osrm_leg_router
        self._osrm_leg_cache = {}
        self._http_client = None
        self._cache = {}
        if cache_db:
            self._preload_from_db()

    def list_datasets(self):
        return sorted(self.sources.keys())

    def get_meta(self, data_id):
        source = self._get_source(data_id)
        entry = self._cache.get(data_id, {})
        features = entry.get("features", []) if self._entry_has_valid_features(entry) else []
        return {
            "dataId": data_id,
            "sourceUrl": source["url"],
            "refreshSeconds": source.get("refresh_seconds", 600),
            "count": len(features),
            "lastUpdatedAt": iso_utc(entry.get("last_updated_at")),
            "lastSuccessAt": iso_utc(entry.get("last_success_at")),
            "lastError": entry.get("last_error"),
        }

    def refresh(self, data_id, force=False):
        source = self._get_source(data_id)
        entry = self._cache.setdefault(data_id, {})
        interval = int(source.get("refresh_seconds", 600))
        now = self.now_func()
        expires_at = entry.get("expires_at")
        has_valid_cached_features = self._entry_has_valid_features(entry)

        if not force and expires_at and expires_at > now and has_valid_cached_features:
            return entry["features"]

        try:
            adapter = self._resolve_adapter(source)
            payload = adapter.fetch_payload(self._execute_fetch, source)
            rows = adapter.extract_rows(payload, source)
            features = self._rows_to_features(rows, source.get("fields", {}))
            entry["features"] = features
            entry["last_error"] = None
            entry["last_success_at"] = now
            if self.cache_db:
                self.cache_db.save_dataset(
                    data_id, features, now, now, now + timedelta(seconds=interval)
                )
            self._record_history(data_id, source, features, now)
        except Exception as err:  # pragma: no cover
            entry["last_error"] = str(err)
            if not self._entry_has_valid_features(entry):
                # in-memory cache is absent/invalid; try SQLite as last resort
                if self.cache_db:
                    stored = self.cache_db.load_dataset(data_id)
                    if stored is not None and self._entry_has_valid_features(stored):
                        entry.update(stored)
            if not self._entry_has_valid_features(entry):
                entry.pop("features", None)
                raise RuntimeError(f"Failed to load dataset {data_id}: {err}") from err
        finally:
            entry["last_updated_at"] = now
            entry["expires_at"] = now + timedelta(seconds=interval)

        return entry["features"]

    def query(self, data_id, payload):
        features = self.refresh(data_id)
        return query_points(features, payload)

    def aggregate(self, data_id, payload):
        metrics = payload.get("metrics") or ["count"]
        if not isinstance(metrics, list):
            raise ValueError("metrics must be an array")
        features = self.refresh(data_id)
        filtered = query_points(features, payload)
        return aggregate_grouped(filtered, metrics, payload.get("groupBy"))

    def query_inline(self, features, payload):
        return query_points(features, payload)

    def aggregate_inline(self, features, payload):
        metrics = payload.get("metrics") or ["count"]
        if not isinstance(metrics, list):
            raise ValueError("metrics must be an array")
        filtered = query_points(features, payload)
        return aggregate_grouped(filtered, metrics, payload.get("groupBy"))

    # ------------------------------------------------------------------
    # history (diff-based capture log for Live datasets)

    def _record_history(self, data_id, source, features, now):
        if not self.history_db:
            return
        history = source.get("history") or {}
        if not history.get("enabled"):
            return
        fields = source.get("fields", {})
        ignore_fields = {fields.get("timestamp", "time"), "timestamp"}
        try:
            self.history_db.append(
                data_id,
                now,
                features,
                key_fields=history.get("key") or [],
                ignore_fields=tuple(ignore_fields),
                keyframe_interval=history.get("keyframe_interval", 50),
                retention_days=history.get("retention_days"),
            )
        except Exception:  # pragma: no cover - history is best-effort
            # Never let history capture break the live data flow.
            pass

    def _require_history(self, data_id):
        source = self._get_source(data_id)
        history = source.get("history") or {}
        if not self.history_db or not history.get("enabled"):
            raise KeyError(f"History not available for dataId: {data_id}")
        return source

    def history_range(self, data_id):
        self._require_history(data_id)
        return self.history_db.range(data_id)

    def history_frames(self, data_id, frm=None, to=None):
        self._require_history(data_id)
        return self.history_db.frames(data_id, frm, to)

    def history_state_at(self, data_id, t):
        source = self._require_history(data_id)
        key_fields = (source.get("history") or {}).get("key") or []
        return self.history_db.state_at(data_id, t, key_fields)

    def history_tracks(self, data_id, frm=None, to=None, progress_cb=None):
        source = self._require_history(data_id)
        history = source.get("history") or {}
        key_fields = history.get("key") or []
        osrm = history.get("osrm") or {}
        # A gap longer than a few poll cycles means recording was interrupted.
        refresh = int(source.get("refresh_seconds", 600) or 600)
        max_gap_seconds = refresh * HISTORY_GAP_FACTOR
        return build_entity_tracks(
            self.history_db,
            data_id,
            key_fields,
            frm,
            to,
            osrm_base_url=osrm.get("base_url") or "http://localhost:5001",
            profile=osrm.get("profile") or "driving",
            leg_router=self.osrm_leg_router,
            leg_cache=self._osrm_leg_cache,
            max_gap_seconds=max_gap_seconds,
            max_concurrency=int(osrm.get("concurrency") or DEFAULT_OSRM_CONCURRENCY),
            progress_cb=progress_cb,
        )

    def _get_source(self, data_id):
        source = self.sources.get(data_id)
        if not source:
            raise KeyError(f"Unknown dataId: {data_id}")
        return source

    def _resolve_adapter(self, source):
        adapter_key = source.get("adapter", "generic_http_json")
        adapter = self.adapters.get(adapter_key)
        if not adapter:
            raise ValueError(f"Unsupported adapter: {adapter_key}")
        return adapter

    def _execute_fetch(self, request_data):  # pragma: no cover
        try:
            return self.fetcher(request_data)
        except TypeError:
            return self.fetcher(request_data["url"])

    def _default_fetcher(self, request_data):  # pragma: no cover
        if self._http_client is None:
            self._http_client = httpx.Client(timeout=30.0, follow_redirects=True)

        method = request_data.get("method", "GET")
        headers = request_data.get("headers") or {}
        body = request_data.get("body")
        expect_json = request_data.get("expect_json", True)
        content = None
        if body is not None:
            if isinstance(body, bytes):
                content = body
            else:
                content = str(body).encode("utf-8")

        response = self._http_client.request(
            method=method,
            url=request_data["url"],
            headers=headers,
            content=content,
        )
        if response.status_code >= 400:
            snippet = (response.text or "").replace("\n", " ").replace("\r", " ")[:300]
            raise RuntimeError(
                f"Upstream HTTP {response.status_code} for {request_data['url']}. body={snippet}"
            )

        if not expect_json:
            return response.text

        try:
            return response.json()
        except ValueError as err:
            content_type = response.headers.get("content-type", "")
            snippet = (response.text or "").replace("\n", " ").replace("\r", " ")[:300]
            raise RuntimeError(
                f"Expected JSON from {request_data['url']} (content-type={content_type}). body={snippet}"
            ) from err

    def _rows_to_features(self, rows, fields):
        features = []
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            feature = self._row_to_feature(row, fields, index)
            if feature:
                features.append(feature)
        return features

    def _preload_from_db(self):
        for data_id in self.sources:
            stored = self.cache_db.load_dataset(data_id)
            if stored and self._entry_has_valid_features(stored):
                self._cache[data_id] = stored

    def _entry_has_valid_features(self, entry):
        features = entry.get("features") if isinstance(entry, dict) else None
        if not isinstance(features, list):
            return False
        return all(self._is_valid_feature(feature) for feature in features)

    @staticmethod
    def _is_valid_feature(feature):
        if not isinstance(feature, dict):
            return False

        geometry = feature.get("geometry")
        properties = feature.get("properties")
        if not isinstance(geometry, dict) or not isinstance(properties, dict):
            return False

        coordinates = geometry.get("coordinates")
        if not isinstance(coordinates, (list, tuple)) or len(coordinates) < 2:
            return False

        lng = to_float(coordinates[0])
        lat = to_float(coordinates[1])
        return lng is not None and lat is not None

    def _row_to_feature(self, row, fields, index):
        lng = to_float(row.get(fields.get("lng", "X")))
        lat = to_float(row.get(fields.get("lat", "Y")))
        if lng is None or lat is None:
            return None

        timestamp_field = fields.get("timestamp", "time")
        id_parts = fields.get("id_parts", ["lineid", "car", timestamp_field])
        feature_id = "::".join(str(row.get(key, "")).strip() for key in id_parts).strip(":")
        if not feature_id:
            digest = hashlib.md5(json.dumps(row, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
            feature_id = f"row-{index}-{digest[:12]}"

        properties = dict(row)
        if timestamp_field in row and "timestamp" not in properties:
            properties["timestamp"] = row.get(timestamp_field)

        return {
            "type": "Feature",
            "id": feature_id,
            "geometry": {
                "type": "Point",
                "coordinates": [lng, lat],
            },
            "properties": properties,
        }
