import ctypes
from functools import lru_cache
import os
from pathlib import Path
import sqlite3

from backend.services.regions_presentation import (
    assemble_regions_tree,
    make_range_node,  # re-exported for backward compatibility
    range_feature_from_row,
    regions_tree_to_ranges,
    regions_tree_to_stat_ranges,
    stat_zone1_rows_to_range_nodes,
    stat_zone2_rows_to_range_nodes,
    stat_zone_point_feature_from_row,
    stat_zone_rows_to_range_nodes,
)

__all__ = ["split_codes", "make_range_node", "RegionsService", "RegionsServiceError"]


# `ancestors` maps each *parent* level → the column carrying its code in this
# table. It excludes the level itself (that is `code_col`); the frontend uses
# these to walk the lazy stat-zone tree down to the picked node.
RANGE_PICK_SPECS = {
    "county": {
        "table": "county",
        "code_col": "countycode",
        "name_col": "countyname",
        "ancestors": {},
    },
    "township": {
        "table": "township",
        "code_col": "towncode",
        "name_col": "townname",
        "ancestors": {"county": "countycode"},
    },
    "village": {
        "table": "village",
        "code_col": "villcode",
        "name_col": "villname",
        "ancestors": {"county": "countycode", "township": "towncode"},
    },
    "stat_zone_2": {
        "table": "stat_zone_2",
        "code_col": "code2",
        "name_col": None,
        "ancestors": {"county": "county_id", "township": "town_id"},
    },
    "stat_zone_1": {
        "table": "stat_zone_1",
        "code_col": "code1",
        "name_col": None,
        "ancestors": {
            "county": "county_id",
            "township": "town_id",
            "stat_zone_2": "code2",
        },
    },
    "stat_zone": {
        "table": "stat_zone",
        "code_col": "codebase",
        "name_col": None,
        "ancestors": {
            "county": "county_id",
            "township": "town_id",
            "stat_zone_2": "code2",
            "stat_zone_1": "code1",
        },
    },
}


def split_codes(value):
    if not value:
        return []
    if isinstance(value, str):
        return [code.strip() for code in value.split(",") if code.strip()]
    if isinstance(value, list):
        return [str(code).strip() for code in value if str(code).strip()]
    return []


class RegionsServiceError(RuntimeError):
    pass


class RegionsService:
    def __init__(self, bounds_path, data_path, range_styles, spatialite_extension_path=None):
        self.bounds_path = Path(bounds_path)
        self.data_path = Path(data_path)
        self.range_styles = range_styles
        self.spatialite_extension_path = spatialite_extension_path

        if not self.bounds_path.exists():
            raise RegionsServiceError(f"bounds.sqlite not found: {self.bounds_path}")
        if not self.data_path.exists():
            raise RegionsServiceError(f"data.sqlite not found: {self.data_path}")

    def _connect_bounds(self, load_spatialite=False):
        conn = sqlite3.connect(str(self.bounds_path))
        conn.row_factory = sqlite3.Row
        if load_spatialite:
            self._load_spatialite(conn)
        return conn

    def _load_spatialite(self, conn):
        ext = self.spatialite_extension_path
        if not ext:
            raise RegionsServiceError(
                "SpatiaLite not configured (spatialite_extension_path is None)"
            )
        ext_path = Path(ext)
        if not ext_path.exists():
            raise RegionsServiceError(f"SpatiaLite extension not found: {ext_path}")

        if os.name == "nt" and hasattr(os, "add_dll_directory"):
            os.add_dll_directory(str(ext_path.parent))
            original = os.environ.get("PATH", "")
            os.environ["PATH"] = f"{ext_path.parent}{os.pathsep}{original}"
            for dep in sorted(ext_path.parent.glob("*.dll")):
                if dep.resolve() != ext_path.resolve():
                    try:
                        ctypes.WinDLL(str(dep))
                    except OSError:
                        pass

        conn.enable_load_extension(True)
        conn.load_extension(str(ext_path))

    # ── regions tree ──────────────────────────────────────────────────────────

    @lru_cache(maxsize=1)
    def build_regions_tree(self):
        conn = self._connect_bounds()
        try:
            county_rows = conn.execute(
                "SELECT countyid, countycode, countyname, countyeng FROM county ORDER BY countyid"
            ).fetchall()
            township_rows = conn.execute(
                "SELECT townid, towncode, countycode, townname, towneng FROM township ORDER BY towncode"
            ).fetchall()
            village_rows = conn.execute(
                "SELECT villcode, countycode, towncode, villname, villeng FROM village ORDER BY villcode"
            ).fetchall()
        finally:
            conn.close()

        return assemble_regions_tree(county_rows, township_rows, village_rows)

    @lru_cache(maxsize=1)
    def build_ranges_tree(self):
        regions = self.build_regions_tree()

        conn = self._connect_bounds()
        try:
            sz2_count_rows = conn.execute(
                "SELECT town_id, COUNT(*) AS cnt FROM stat_zone_2 GROUP BY town_id"
            ).fetchall()
        finally:
            conn.close()
        sz2_count_by_town = {row["town_id"]: row["cnt"] for row in sz2_count_rows}

        admin = regions_tree_to_ranges(regions)
        stat = regions_tree_to_stat_ranges(regions, sz2_count_by_town)

        return {
            "trees": [
                {"id": "admin", "name": "行政區", "ranges": admin["ranges"]},
                {"id": "stat", "name": "統計區", "ranges": stat["ranges"]},
            ],
            "summary": regions["summary"],
        }

    # ── stat zone tree children (lazy-loaded) ─────────────────────────────────

    def build_stat_zone_children(self, parent_level, parent_code):
        """Children of a statistical-tree node: township → 二級發布區 →
        一級發布區 → 最小統計區. Raises ValueError on unknown parent level."""
        parent_code = str(parent_code or "").strip()
        base = {"parentLevel": parent_level, "parentCode": parent_code}
        if not parent_code:
            return {**base, "ranges": [], "summary": {"count": 0}}

        conn = self._connect_bounds()
        try:
            if parent_level == "township":
                rows = conn.execute(
                    "SELECT code2 FROM stat_zone_2 WHERE town_id = ? ORDER BY code2",
                    (parent_code,),
                ).fetchall()
                count_rows = conn.execute(
                    "SELECT code2, COUNT(*) AS cnt FROM stat_zone_1"
                    " WHERE town_id = ? GROUP BY code2",
                    (parent_code,),
                ).fetchall()
                ranges = stat_zone2_rows_to_range_nodes(
                    rows,
                    self.range_styles.get("stat_zone_2", "#a78bfa"),
                    {row["code2"]: row["cnt"] for row in count_rows},
                )
            elif parent_level == "stat_zone_2":
                rows = conn.execute(
                    "SELECT code1 FROM stat_zone_1 WHERE code2 = ? ORDER BY code1",
                    (parent_code,),
                ).fetchall()
                count_rows = conn.execute(
                    "SELECT code1, COUNT(*) AS cnt FROM stat_zone"
                    " WHERE code2 = ? GROUP BY code1",
                    (parent_code,),
                ).fetchall()
                ranges = stat_zone1_rows_to_range_nodes(
                    rows,
                    self.range_styles.get("stat_zone_1", "#34d399"),
                    {row["code1"]: row["cnt"] for row in count_rows},
                )
            elif parent_level == "stat_zone_1":
                rows = conn.execute(
                    "SELECT sz.codebase, cache.p_cnt FROM stat_zone AS sz"
                    " LEFT JOIN stat_zone_point_cache AS cache ON cache.codebase = sz.codebase"
                    " WHERE sz.code1 = ? ORDER BY sz.codebase",
                    (parent_code,),
                ).fetchall()
                ranges = stat_zone_rows_to_range_nodes(
                    rows,
                    self.range_styles.get("stat_zone", "#72e9b7"),
                    {"parentCode1": parent_code},
                )
            else:
                raise ValueError(f"unsupported parent level: {parent_level}")
        finally:
            conn.close()

        return {**base, "ranges": ranges, "summary": {"count": len(ranges)}}

    # ── range GeoJSON (requires SpatiaLite) ───────────────────────────────────

    def build_range_geojson(
        self,
        county_codes,
        town_codes,
        village_codes,
        stat_zone_codes=None,
        stat_zone_1_codes=None,
        stat_zone_2_codes=None,
    ):
        stat_zone_codes = split_codes(stat_zone_codes)
        stat_zone_1_codes = split_codes(stat_zone_1_codes)
        stat_zone_2_codes = split_codes(stat_zone_2_codes)

        conn = self._connect_bounds(load_spatialite=True)
        features = []
        seen = set()
        try:
            for layer, table, code_col, codes in (
                ("county",            "county",      "countycode", county_codes),
                ("township",          "township",    "towncode",   town_codes),
                ("village",           "village",     "villcode",   village_codes),
                ("stat_zone_2",       "stat_zone_2", "code2",      stat_zone_2_codes),
                ("stat_zone_1",       "stat_zone_1", "code1",      stat_zone_1_codes),
                ("stat_zone",         "stat_zone",   "codebase",   stat_zone_codes),
            ):
                if not codes:
                    continue
                ph = ",".join("?" * len(codes))
                rows = conn.execute(
                    f"SELECT *, AsGeoJSON(GEOMETRY) AS _geom"
                    f" FROM {table} WHERE {code_col} IN ({ph})",
                    codes,
                ).fetchall()
                color = self.range_styles.get(layer, "#57a6f5")
                for row in rows:
                    key = f"{layer}:{row[code_col]}"
                    if key in seen:
                        continue
                    seen.add(key)
                    feature = range_feature_from_row(row, layer, code_col, color)
                    if feature is not None:
                        features.append(feature)
        finally:
            conn.close()

        return {"type": "FeatureCollection", "features": features}

    def pick_range_by_point(self, lng, lat, level):
        """Return the boundary code at a lng/lat for the selected range level."""
        if level not in RANGE_PICK_SPECS:
            raise ValueError(f"unsupported range pick level: {level}")

        spec = RANGE_PICK_SPECS[level]
        table = spec["table"]
        code_col = spec["code_col"]
        name_col = spec["name_col"]
        ancestors = spec["ancestors"]
        name_select = f"{name_col} AS name" if name_col else f"{code_col} AS name"
        ancestor_select = ", ".join(
            f"{column} AS ancestor_{ancestor_level}"
            for ancestor_level, column in ancestors.items()
        )
        select_expr = f"{code_col} AS code, {name_select}"
        if ancestor_select:
            select_expr = f"{select_expr}, {ancestor_select}"
        indexed_sql = (
            f"SELECT {select_expr}"
            f" FROM {table}"
            f" WHERE ROWID IN ("
            f"   SELECT pkid FROM idx_{table}_GEOMETRY"
            f"   WHERE xmin <= ? AND xmax >= ? AND ymin <= ? AND ymax >= ?"
            f" )"
            f" AND ST_Covers(GEOMETRY, MakePoint(?, ?, 4326)) = 1"
            f" LIMIT 1"
        )
        fallback_sql = (
            f"SELECT {select_expr}"
            f" FROM {table}"
            f" WHERE ST_Covers(GEOMETRY, MakePoint(?, ?, 4326)) = 1"
            f" LIMIT 1"
        )

        conn = self._connect_bounds(load_spatialite=True)
        try:
            try:
                row = conn.execute(indexed_sql, (lng, lng, lat, lat, lng, lat)).fetchone()
            except sqlite3.OperationalError as err:
                # A missing spatial index falls back to a plain scan; any other
                # OperationalError (e.g. SpatiaLite not loaded) is a real fault.
                if "idx_" not in str(err):
                    raise RegionsServiceError(f"range pick query failed: {err}") from err
                row = conn.execute(fallback_sql, (lng, lat)).fetchone()
        except sqlite3.OperationalError as err:
            raise RegionsServiceError(f"range pick query failed: {err}") from err
        finally:
            conn.close()

        if row is None:
            return {"hit": False, "level": level}

        result = {"hit": True, "level": level, "code": str(row["code"])}
        if row["name"]:
            result["name"] = str(row["name"])
        ancestor_values = {}
        for ancestor_level in ancestors.keys():
            value = row[f"ancestor_{ancestor_level}"]
            if value is not None and str(value) != "":
                ancestor_values[ancestor_level] = str(value)
        if ancestor_values:
            result["ancestors"] = ancestor_values
        return result

    # ── stat zone population ──────────────────────────────────────────────────

    def _stat_zone_cache_filter(
        self,
        stat_zone_codes,
        county_codes,
        town_codes,
        village_codes,
        stat_zone_1_codes=None,
        stat_zone_2_codes=None,
    ):
        stat_zone_codes = split_codes(stat_zone_codes)
        county_codes = split_codes(county_codes)
        town_codes = split_codes(town_codes)
        village_codes = split_codes(village_codes)
        stat_zone_1_codes = split_codes(stat_zone_1_codes)
        stat_zone_2_codes = split_codes(stat_zone_2_codes)

        filters, params = [], []
        if stat_zone_codes:
            ph = ",".join("?" * len(stat_zone_codes))
            filters.append(f"codebase IN ({ph})")
            params.extend(stat_zone_codes)
        # 發布區代碼不在 point cache 上，透過 stat_zone 表換回 codebase。
        if stat_zone_1_codes:
            ph = ",".join("?" * len(stat_zone_1_codes))
            filters.append(f"codebase IN (SELECT codebase FROM stat_zone WHERE code1 IN ({ph}))")
            params.extend(stat_zone_1_codes)
        if stat_zone_2_codes:
            ph = ",".join("?" * len(stat_zone_2_codes))
            filters.append(f"codebase IN (SELECT codebase FROM stat_zone WHERE code2 IN ({ph}))")
            params.extend(stat_zone_2_codes)
        if village_codes:
            ph = ",".join("?" * len(village_codes))
            filters.append(f"villcode IN ({ph})")
            params.extend(village_codes)
        if town_codes:
            ph = ",".join("?" * len(town_codes))
            filters.append(f"town_id IN ({ph})")
            params.extend(town_codes)
        if county_codes:
            ph = ",".join("?" * len(county_codes))
            filters.append(f"county_id IN ({ph})")
            params.extend(county_codes)

        if not filters:
            return "", []
        return " AND (" + " OR ".join(filters) + ")", params

    def aggregate_stat_zone_population(
        self,
        stat_zone_codes=None,
        county_codes=None,
        town_codes=None,
        village_codes=None,
        stat_zone_1_codes=None,
        stat_zone_2_codes=None,
    ):
        extra, params = self._stat_zone_cache_filter(
            stat_zone_codes, county_codes, town_codes, village_codes,
            stat_zone_1_codes, stat_zone_2_codes,
        )
        conn = self._connect_bounds()
        try:
            row = conn.execute(
                f"SELECT COUNT(1) AS count, COALESCE(SUM(p_cnt), 0) AS population"
                f" FROM stat_zone_point_cache WHERE 1=1{extra}",
                params,
            ).fetchone()
        finally:
            conn.close()

        count = int(row["count"]) if row else 0
        population = row["population"] if row and row["population"] is not None else 0
        return {"count": count, "sum": {"P_CNT": int(population)}}

    def query_stat_zone_population_points(
        self,
        stat_zone_codes=None,
        county_codes=None,
        town_codes=None,
        village_codes=None,
        stat_zone_1_codes=None,
        stat_zone_2_codes=None,
        limit=None,
    ):
        extra, params = self._stat_zone_cache_filter(
            stat_zone_codes, county_codes, town_codes, village_codes,
            stat_zone_1_codes, stat_zone_2_codes,
        )
        if limit is not None:
            try:
                safe_limit = max(0, int(limit))
            except (TypeError, ValueError):
                safe_limit = 0
            extra += " LIMIT ?"
            params.append(safe_limit)

        conn = self._connect_bounds()
        try:
            rows = conn.execute(
                f"SELECT codebase, villcode, county_id, town_id, lng, lat, p_cnt"
                f" FROM stat_zone_point_cache"
                f" WHERE lng IS NOT NULL AND lat IS NOT NULL{extra}",
                params,
            ).fetchall()
        finally:
            conn.close()

        return [stat_zone_point_feature_from_row(row) for row in rows]
