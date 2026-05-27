from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Dict, Iterable, Tuple


ROOT_DIR = Path(__file__).resolve().parents[2]


LEVEL_SPECS = (
    {
        "level": "county",
        "file_name": "county.geojson",
        "code_key": "COUNTYCODE",
        "name_key": "COUNTYNAME",
        "name_en_key": "COUNTYENG",
        "county_code_key": "COUNTYCODE",
        "town_code_key": None,
    },
    {
        "level": "township",
        "file_name": "township.geojson",
        "code_key": "TOWNCODE",
        "name_key": "TOWNNAME",
        "name_en_key": "TOWNENG",
        "county_code_key": "COUNTYCODE",
        "town_code_key": "TOWNCODE",
    },
    {
        "level": "village",
        "file_name": "village.geojson",
        "code_key": "VILLCODE",
        "name_key": "VILLNAME",
        "name_en_key": "VILLENG",
        "county_code_key": "COUNTYCODE",
        "town_code_key": "TOWNCODE",
    },
    {
        "level": "stat_zone_min_113",
        "file_name": "stat_zone_min_113.geojson",
        "code_key": "CODEBASE",
        "name_key": "CODEBASE",
        "name_en_key": "CODEBASE",
        "county_code_key": "CODE2",
        "town_code_key": "CODE1",
        "stream_geojson": True,
        "attributes_file_name": "stat_zone_min_113.csv",
        "schema_file_name": "stat_zone_min_113_Schema.ini",
    },
)


class RegionsSyncError(RuntimeError):
    pass


@dataclass(frozen=True)
class SourceFingerprint:
    file_name: str
    file_mtime: float
    file_size: int
    file_sha256: str


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compute_source_fingerprints(geojson_dir: Path) -> Dict[str, SourceFingerprint]:
    fingerprints: Dict[str, SourceFingerprint] = {}
    for spec in LEVEL_SPECS:
        file_names = [spec["file_name"]]
        if spec.get("attributes_file_name"):
            file_names.append(spec["attributes_file_name"])
        if spec.get("schema_file_name"):
            file_names.append(spec["schema_file_name"])

        for file_name in file_names:
            path = geojson_dir / file_name
            if not path.exists():
                raise RegionsSyncError(f"GeoJSON source not found: {path}")
            stat = path.stat()
            fingerprints[file_name] = SourceFingerprint(
                file_name=file_name,
                file_mtime=stat.st_mtime,
                file_size=stat.st_size,
                file_sha256=_sha256_file(path),
            )
    return fingerprints


def connect_regions_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    return connection


def _resolve_extension_file(extension_path: str) -> Tuple[Path | None, list[Path]]:
    raw = Path(extension_path)
    candidates = []
    if raw.is_absolute():
        candidates.append(raw)
    else:
        candidates.append(Path.cwd() / raw)
        candidates.append(ROOT_DIR / raw)

        parts = list(raw.parts)
        if parts and parts[0].lower() == "backend":
            candidates.append(ROOT_DIR.joinpath(*parts[1:]))

    deduped = []
    seen = set()
    for candidate in candidates:
        normalized = candidate.resolve(strict=False)
        key = str(normalized).lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)

    for candidate in deduped:
        if candidate.exists():
            return candidate, deduped
    return None, deduped


def try_load_spatialite(connection: sqlite3.Connection, extension_path: str | None) -> Tuple[bool, str | None]:
    if not extension_path:
        return False, "SPATIALITE_EXTENSION_PATH is not configured"

    extension_file, attempted_paths = _resolve_extension_file(extension_path)
    if extension_file is None:
        attempted = "; ".join(str(path) for path in attempted_paths) or extension_path
        return False, f"SpatiaLite extension not found. attempted={attempted}"

    dll_handles = []
    original_path = os.environ.get("PATH", "")
    try:
        if os.name == "nt" and hasattr(os, "add_dll_directory"):
            dll_handles.append(os.add_dll_directory(str(extension_file.parent)))
            os.environ["PATH"] = f"{extension_file.parent}{os.pathsep}{original_path}"

            dependency_errors = []
            for dependency in sorted(extension_file.parent.glob("*.dll")):
                if dependency.resolve() == extension_file.resolve():
                    continue
                try:
                    ctypes.WinDLL(str(dependency))
                except OSError as dep_err:
                    dependency_errors.append(f"{dependency.name}: {dep_err}")
            if dependency_errors:
                detail = "; ".join(dependency_errors)
                return False, f"Failed to preload SpatiaLite dependencies: {detail}"

        connection.enable_load_extension(True)
        connection.load_extension(str(extension_file))
        connection.execute("SELECT spatialite_version()")
        return True, None
    except (AttributeError, sqlite3.Error) as err:
        return False, f"Failed to load SpatiaLite extension ({extension_file}): {err}"
    finally:
        try:
            connection.enable_load_extension(False)
        except Exception:
            pass
        for handle in dll_handles:
            try:
                handle.close()
            except Exception:
                pass
        if os.name == "nt":
            os.environ["PATH"] = original_path


def ensure_base_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS admin_region (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            level TEXT NOT NULL,
            code TEXT NOT NULL,
            parent_code TEXT,
            county_code TEXT,
            town_code TEXT,
            name_zh TEXT,
            name_en TEXT,
            raw_properties_json TEXT NOT NULL,
            geom_json TEXT NOT NULL,
            UNIQUE(level, code)
        );

        CREATE INDEX IF NOT EXISTS idx_admin_region_level ON admin_region(level);
        CREATE INDEX IF NOT EXISTS idx_admin_region_county_code ON admin_region(county_code);
        CREATE INDEX IF NOT EXISTS idx_admin_region_town_code ON admin_region(town_code);

        CREATE TABLE IF NOT EXISTS stat_zone_point (
            code TEXT PRIMARY KEY,
            village_code TEXT,
            county_code TEXT,
            town_code TEXT,
            name_zh TEXT,
            name_en TEXT,
            lng REAL NOT NULL,
            lat REAL NOT NULL,
            p_cnt REAL,
            raw_properties_json TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_stat_zone_point_village_code ON stat_zone_point(village_code);
        CREATE INDEX IF NOT EXISTS idx_stat_zone_point_town_code ON stat_zone_point(town_code);
        CREATE INDEX IF NOT EXISTS idx_stat_zone_point_county_code ON stat_zone_point(county_code);

        CREATE TABLE IF NOT EXISTS sync_meta (
            file_name TEXT PRIMARY KEY,
            file_mtime REAL NOT NULL,
            file_size INTEGER NOT NULL,
            file_sha256 TEXT NOT NULL,
            synced_at TEXT NOT NULL
        );
        """
    )


def _column_exists(connection: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    for row in rows:
        if row["name"] == column_name:
            return True
    return False


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return bool(row)


def _spatial_index_exists(connection: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    index_table_name = f"idx_{table_name}_{column_name}"
    return _table_exists(connection, index_table_name)


def ensure_spatial_schema(connection: sqlite3.Connection) -> None:
    if not _table_exists(connection, "spatial_ref_sys"):
        try:
            connection.execute("SELECT InitSpatialMetaData(1)")
        except sqlite3.Error:
            pass

    if not _column_exists(connection, "admin_region", "geom"):
        connection.execute(
            "SELECT AddGeometryColumn('admin_region', 'geom', 4326, 'MULTIPOLYGON', 'XY')"
        )

    if not _spatial_index_exists(connection, "admin_region", "geom"):
        try:
            connection.execute("SELECT CreateSpatialIndex('admin_region', 'geom')")
        except sqlite3.Error:
            pass


def _normalize_code(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _to_xy_coordinates(value):
    if isinstance(value, list) and value and all(isinstance(item, (int, float)) for item in value[:2]):
        return value[:2]
    if isinstance(value, list):
        return [_to_xy_coordinates(item) for item in value]
    return value


def _to_multipolygon(geometry: dict) -> dict:
    geometry_type = (geometry or {}).get("type")
    coordinates = _to_xy_coordinates((geometry or {}).get("coordinates"))

    if geometry_type == "MultiPolygon":
        return {"type": "MultiPolygon", "coordinates": coordinates}
    if geometry_type == "Polygon":
        return {"type": "MultiPolygon", "coordinates": [coordinates]}
    raise RegionsSyncError(f"Unsupported geometry type for admin region import: {geometry_type}")


def _ring_area(ring) -> float:
    if not isinstance(ring, list) or len(ring) < 3:
        return 0.0
    area = 0.0
    for i in range(len(ring)):
        x1, y1 = ring[i][:2]
        x2, y2 = ring[(i + 1) % len(ring)][:2]
        area += (x1 * y2) - (x2 * y1)
    return area / 2.0


def _ring_centroid(ring):
    area2 = 0.0
    cx = 0.0
    cy = 0.0
    for i in range(len(ring)):
        x1, y1 = ring[i][:2]
        x2, y2 = ring[(i + 1) % len(ring)][:2]
        cross = (x1 * y2) - (x2 * y1)
        area2 += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    if abs(area2) < 1e-12:
        xs = [point[0] for point in ring if isinstance(point, list) and len(point) >= 2]
        ys = [point[1] for point in ring if isinstance(point, list) and len(point) >= 2]
        if not xs or not ys:
            return None
        return [sum(xs) / len(xs), sum(ys) / len(ys)]
    factor = 1.0 / (3.0 * area2)
    return [cx * factor, cy * factor]


def _geometry_representative_point(geometry):
    if not isinstance(geometry, dict):
        return None
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if geometry_type == "Polygon" and isinstance(coordinates, list) and coordinates:
        return _ring_centroid(coordinates[0])
    if geometry_type == "MultiPolygon" and isinstance(coordinates, list) and coordinates:
        best_ring = None
        best_area = -1.0
        for polygon in coordinates:
            if not isinstance(polygon, list) or not polygon:
                continue
            ring = polygon[0]
            area = abs(_ring_area(ring))
            if area > best_area:
                best_area = area
                best_ring = ring
        if best_ring:
            return _ring_centroid(best_ring)
    return None


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def rebuild_stat_zone_point_cache(connection: sqlite3.Connection) -> None:
    connection.execute("DELETE FROM stat_zone_point")
    rows = connection.execute(
        """
        SELECT code, parent_code, county_code, town_code, name_zh, name_en, raw_properties_json, geom_json
        FROM admin_region
        WHERE level = 'stat_zone_min_113'
        """
    ).fetchall()

    batch = []
    for row in rows:
        geometry = json.loads(row["geom_json"])
        point = _geometry_representative_point(geometry)
        if not point:
            continue
        properties = json.loads(row["raw_properties_json"])
        p_cnt = _to_float(properties.get("P_CNT"))
        batch.append(
            (
                row["code"],
                row["parent_code"],
                row["county_code"],
                row["town_code"],
                row["name_zh"],
                row["name_en"],
                float(point[0]),
                float(point[1]),
                p_cnt,
                row["raw_properties_json"],
            )
        )
        if len(batch) >= 5000:
            connection.executemany(
                """
                INSERT OR REPLACE INTO stat_zone_point (
                    code, village_code, county_code, town_code, name_zh, name_en, lng, lat, p_cnt, raw_properties_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                batch,
            )
            batch.clear()

    if batch:
        connection.executemany(
            """
            INSERT OR REPLACE INTO stat_zone_point (
                code, village_code, county_code, town_code, name_zh, name_en, lng, lat, p_cnt, raw_properties_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            batch,
        )


def _iter_geojson_features(source_path: Path, stream_geojson: bool) -> Iterable[dict]:
    if not stream_geojson:
        payload = json.loads(source_path.read_text(encoding="utf-8", errors="ignore"))
        yield from payload.get("features", [])
        return

    decoder = json.JSONDecoder()
    with source_path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            text = line.strip()
            if not text or not text.startswith('{"type":"Feature"'):
                continue
            try:
                feature, _ = decoder.raw_decode(text)
            except json.JSONDecodeError as err:
                raise RegionsSyncError(f"Failed to parse streamed feature from {source_path}: {err}") from err
            yield feature


def _parse_stat_zone_schema(schema_path: Path) -> dict:
    unit_code_field = None
    column_labels = {}
    current_section = None

    with schema_path.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue

            if line.startswith("[") and line.endswith("]"):
                current_section = line[1:-1].strip()
                continue

            if "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if key == "統計單元代碼" and value:
                unit_code_field = value
            if key == "中文欄位名" and current_section:
                column_labels[current_section] = value

    return {
        "unit_code_field": unit_code_field,
        "column_labels": column_labels,
    }


def _is_stat_zone_label_row(row: list[str] | None, code_field: str) -> bool:
    if not row:
        return False
    if not row[0]:
        return True
    if row[0] == code_field:
        return False
    return bool(re.search(r"[\u4e00-\u9fff]", row[0]))


def _load_stat_zone_attribute_table(connection: sqlite3.Connection, geojson_dir: Path, spec: dict) -> str:
    csv_path = geojson_dir / spec["attributes_file_name"]
    schema_path = geojson_dir / spec["schema_file_name"]
    schema = _parse_stat_zone_schema(schema_path)
    code_field = schema.get("unit_code_field") or spec["code_key"]

    connection.execute("DROP TABLE IF EXISTS temp.stat_zone_attr")
    connection.execute(
        """
        CREATE TEMP TABLE stat_zone_attr (
            code TEXT PRIMARY KEY,
            raw_properties_json TEXT NOT NULL
        )
        """
    )

    with csv_path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as handle:
        reader = csv.reader(handle)
        field_names = next(reader, None)
        if not field_names:
            raise RegionsSyncError(f"CSV has no header row: {csv_path}")
        if code_field not in field_names:
            raise RegionsSyncError(f"CSV code field not found ({code_field}) in {csv_path}")
        code_index = field_names.index(code_field)

        pending = []

        def append_row(values: list[str]) -> None:
            normalized = list(values[: len(field_names)])
            if len(normalized) < len(field_names):
                normalized.extend([""] * (len(field_names) - len(normalized)))
            row_dict = {
                field_name: normalized[idx]
                for idx, field_name in enumerate(field_names)
                if normalized[idx] not in ("", None)
            }
            code = _normalize_code(row_dict.get(code_field))
            if not code:
                return
            pending.append((code, json.dumps(row_dict, ensure_ascii=False, separators=(",", ":"))))

        first_data_row = next(reader, None)
        if first_data_row is not None and not _is_stat_zone_label_row(first_data_row, code_field):
            append_row(first_data_row)

        for row in reader:
            append_row(row)
            if len(pending) >= 2000:
                connection.executemany(
                    """
                    INSERT OR REPLACE INTO stat_zone_attr (code, raw_properties_json)
                    VALUES (?, ?)
                    """,
                    pending,
                )
                pending.clear()

        if pending:
            connection.executemany(
                """
                INSERT OR REPLACE INTO stat_zone_attr (code, raw_properties_json)
                VALUES (?, ?)
                """,
                pending,
            )

    return code_field


def _iter_rows_for_level(geojson_dir: Path, spec: dict, connection: sqlite3.Connection) -> Iterable[dict]:
    source_path = geojson_dir / spec["file_name"]
    stat_zone_code_field = None
    if spec.get("attributes_file_name") and spec.get("schema_file_name"):
        stat_zone_code_field = _load_stat_zone_attribute_table(connection, geojson_dir, spec)

    for feature in _iter_geojson_features(source_path, stream_geojson=bool(spec.get("stream_geojson"))):
        geo_properties = feature.get("properties") or {}
        properties = geo_properties
        if stat_zone_code_field:
            lookup_code = _normalize_code(geo_properties.get(stat_zone_code_field) or geo_properties.get(spec["code_key"]))
            if lookup_code:
                row = connection.execute(
                    "SELECT raw_properties_json FROM temp.stat_zone_attr WHERE code = ?",
                    (lookup_code,),
                ).fetchone()
                if row:
                    csv_properties = json.loads(row["raw_properties_json"])
                    properties = {**geo_properties, **csv_properties}

        code = _normalize_code(properties.get(spec["code_key"]))
        if not code:
            continue

        county_code = _normalize_code(properties.get(spec["county_code_key"]))
        town_code_key = spec.get("town_code_key")
        town_code = _normalize_code(properties.get(town_code_key)) if town_code_key else ""

        if spec["level"] == "county":
            parent_code = None
        elif spec["level"] == "township":
            parent_code = county_code or None
        elif spec["level"] == "stat_zone_min_113":
            parent_code = None
        else:
            parent_code = town_code or None

        geometry = _to_multipolygon(feature.get("geometry") or {})

        yield {
            "level": spec["level"],
            "code": code,
            "parent_code": parent_code,
            "county_code": county_code or None,
            "town_code": town_code or None,
            "name_zh": _normalize_code(properties.get(spec["name_key"])),
            "name_en": _normalize_code(properties.get(spec["name_en_key"])),
            "raw_properties_json": json.dumps(properties, ensure_ascii=False, separators=(",", ":")),
            "geom_json": json.dumps(geometry, ensure_ascii=False, separators=(",", ":")),
        }


def _link_stat_zones_to_villages(connection: sqlite3.Connection) -> None:
    connection.execute("DROP TABLE IF EXISTS temp.stat_zone_parent_map")
    connection.execute(
        """
        CREATE TEMP TABLE stat_zone_parent_map (
            stat_code TEXT PRIMARY KEY,
            village_code TEXT NOT NULL
        )
        """
    )

    connection.execute(
        """
        INSERT OR REPLACE INTO stat_zone_parent_map (stat_code, village_code)
        WITH ranked AS (
            SELECT
                s.code AS stat_code,
                v.code AS village_code,
                ROW_NUMBER() OVER (
                    PARTITION BY s.code
                    ORDER BY ST_Area(ST_Intersection(v.geom, s.geom)) DESC
                ) AS rn
            FROM admin_region AS s
            JOIN admin_region AS v
              ON v.level = 'village'
             AND v.ROWID IN (
                SELECT ROWID
                FROM SpatialIndex
                WHERE f_table_name = 'admin_region'
                  AND search_frame = s.geom
             )
             AND ST_Covers(v.geom, ST_PointOnSurface(s.geom))
            WHERE s.level = 'stat_zone_min_113'
        )
        SELECT stat_code, village_code
        FROM ranked
        WHERE rn = 1
        """
    )

    connection.execute(
        """
        INSERT OR REPLACE INTO stat_zone_parent_map (stat_code, village_code)
        WITH ranked AS (
            SELECT
                s.code AS stat_code,
                v.code AS village_code,
                ROW_NUMBER() OVER (
                    PARTITION BY s.code
                    ORDER BY ST_Area(ST_Intersection(v.geom, s.geom)) DESC
                ) AS rn
            FROM admin_region AS s
            JOIN admin_region AS v
              ON v.level = 'village'
             AND v.ROWID IN (
                SELECT ROWID
                FROM SpatialIndex
                WHERE f_table_name = 'admin_region'
                  AND search_frame = s.geom
             )
             AND ST_Intersects(v.geom, s.geom)
            WHERE s.level = 'stat_zone_min_113'
              AND s.code NOT IN (SELECT stat_code FROM stat_zone_parent_map)
        )
        SELECT stat_code, village_code
        FROM ranked
        WHERE rn = 1
        """
    )

    connection.execute(
        """
        UPDATE admin_region
        SET parent_code = (
            SELECT village_code
            FROM stat_zone_parent_map
            WHERE stat_code = admin_region.code
        )
        WHERE level = 'stat_zone_min_113'
        """
    )


def _insert_rows_batch(
    connection: sqlite3.Connection,
    rows: list[dict],
    spatialite_loaded: bool,
    has_geometry_column: bool,
) -> None:
    if not rows:
        return

    if spatialite_loaded and has_geometry_column:
        connection.executemany(
            """
            INSERT INTO admin_region (
                level, code, parent_code, county_code, town_code,
                name_zh, name_en, raw_properties_json, geom_json, geom
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, SetSRID(GeomFromGeoJSON(?), 4326))
            """,
            [
                (
                    row["level"],
                    row["code"],
                    row["parent_code"],
                    row["county_code"],
                    row["town_code"],
                    row["name_zh"],
                    row["name_en"],
                    row["raw_properties_json"],
                    row["geom_json"],
                    row["geom_json"],
                )
                for row in rows
            ],
        )
        return

    connection.executemany(
        """
        INSERT INTO admin_region (
            level, code, parent_code, county_code, town_code,
            name_zh, name_en, raw_properties_json, geom_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                row["level"],
                row["code"],
                row["parent_code"],
                row["county_code"],
                row["town_code"],
                row["name_zh"],
                row["name_en"],
                row["raw_properties_json"],
                row["geom_json"],
            )
            for row in rows
        ],
    )


def import_admin_regions(
    *,
    geojson_dir: Path,
    db_path: Path,
    spatialite_extension_path: str | None,
    require_spatialite: bool,
) -> None:
    fingerprints = compute_source_fingerprints(geojson_dir)
    synced_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    connection = connect_regions_db(db_path)
    try:
        ensure_base_schema(connection)
        spatialite_loaded, load_error = try_load_spatialite(connection, spatialite_extension_path)
        if require_spatialite and not spatialite_loaded:
            raise RegionsSyncError(load_error or "SpatiaLite extension load failed")
        if spatialite_loaded:
            ensure_spatial_schema(connection)

        connection.execute("BEGIN")
        try:
            connection.execute("DELETE FROM admin_region")

            has_geometry_column = _column_exists(connection, "admin_region", "geom")
            for spec in LEVEL_SPECS:
                batch = []
                for row in _iter_rows_for_level(geojson_dir, spec, connection):
                    batch.append(row)
                    if len(batch) >= 500:
                        _insert_rows_batch(connection, batch, spatialite_loaded, has_geometry_column)
                        batch.clear()
                _insert_rows_batch(connection, batch, spatialite_loaded, has_geometry_column)

            if spatialite_loaded and has_geometry_column:
                _link_stat_zones_to_villages(connection)
            rebuild_stat_zone_point_cache(connection)

            connection.execute("DELETE FROM sync_meta")
            connection.executemany(
                """
                INSERT INTO sync_meta (file_name, file_mtime, file_size, file_sha256, synced_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        fingerprint.file_name,
                        fingerprint.file_mtime,
                        fingerprint.file_size,
                        fingerprint.file_sha256,
                        synced_at,
                    )
                    for fingerprint in fingerprints.values()
                ],
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    finally:
        connection.close()


def is_sync_required(*, geojson_dir: Path, db_path: Path) -> bool:
    if not db_path.exists():
        return True

    connection = connect_regions_db(db_path)
    try:
        ensure_base_schema(connection)
        current = compute_source_fingerprints(geojson_dir)
        rows = connection.execute(
            "SELECT file_name, file_mtime, file_size, file_sha256 FROM sync_meta"
        ).fetchall()
        if len(rows) != len(current):
            return True

        db_fingerprints = {
            row["file_name"]: (
                float(row["file_mtime"]),
                int(row["file_size"]),
                row["file_sha256"],
            )
            for row in rows
        }

        for file_name, fingerprint in current.items():
            row = db_fingerprints.get(file_name)
            if not row:
                return True
            if row[1] != fingerprint.file_size:
                return True
            if row[2] != fingerprint.file_sha256:
                return True
        return False
    finally:
        connection.close()


def validate_regions_db_ready(*, db_path: Path) -> None:
    if not db_path.exists():
        raise RegionsSyncError(f"Regions database not found: {db_path}")

    connection = connect_regions_db(db_path)
    try:
        table_exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='admin_region'"
        ).fetchone()
        if not table_exists:
            raise RegionsSyncError("Regions database is missing admin_region table")

        count_row = connection.execute("SELECT COUNT(1) AS count FROM admin_region").fetchone()
        if not count_row or int(count_row["count"]) == 0:
            raise RegionsSyncError("Regions database is empty; run import script first")
    finally:
        connection.close()
