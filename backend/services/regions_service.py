from functools import lru_cache
import json
from pathlib import Path
import sqlite3

from backend.services.regions_db import (
    RegionsSyncError,
    import_admin_regions,
    is_sync_required,
    validate_regions_db_ready,
)


def split_codes(value):
    if not value:
        return []
    if isinstance(value, str):
        return [code.strip() for code in value.split(",") if code.strip()]
    if isinstance(value, list):
        return [str(code).strip() for code in value if str(code).strip()]
    return []


def make_range_node(node_id, name, description, color, level, code, children=None, metadata=None):
    return {
        "id": node_id,
        "name": name or code or node_id,
        "description": description or "",
        "color": color,
        "type": "admin",
        "level": level,
        "code": code or "",
        "selectable": True,
        "metadata": metadata or {},
        "children": children or [],
    }


class RegionsService:
    def __init__(
        self,
        geojson_dir,
        range_styles,
        db_path,
        spatialite_extension_path=None,
        sync_mode="manual",
        sync_strict=True,
    ):
        self.geojson_dir = Path(geojson_dir)
        self.range_styles = range_styles
        self.db_path = Path(db_path)
        self.spatialite_extension_path = spatialite_extension_path
        self.sync_mode = (sync_mode or "manual").strip().lower()
        self.sync_strict = bool(sync_strict)

        if self.sync_mode not in {"manual", "startup"}:
            raise RegionsSyncError(
                f"Unsupported REGIONS_SYNC_MODE={sync_mode!r}. Use 'manual' or 'startup'."
            )

        self._ensure_startup_sync()

    def _ensure_startup_sync(self):
        if self.sync_mode == "manual":
            validate_regions_db_ready(db_path=self.db_path)
            return

        try:
            if is_sync_required(geojson_dir=self.geojson_dir, db_path=self.db_path):
                import_admin_regions(
                    geojson_dir=self.geojson_dir,
                    db_path=self.db_path,
                    spatialite_extension_path=self.spatialite_extension_path,
                    require_spatialite=True,
                )
            validate_regions_db_ready(db_path=self.db_path)
        except RegionsSyncError:
            if self.sync_strict:
                raise
            validate_regions_db_ready(db_path=self.db_path)

    def _connect(self):
        connection = sqlite3.connect(str(self.db_path))
        connection.row_factory = sqlite3.Row
        return connection

    def _rows_by_level(self, level):
        connection = self._connect()
        try:
            return connection.execute(
                """
                SELECT code, parent_code, county_code, town_code, name_zh, name_en, raw_properties_json
                FROM admin_region
                WHERE level = ?
                """,
                (level,),
            ).fetchall()
        finally:
            connection.close()

    @lru_cache(maxsize=1)
    def build_regions_tree(self):
        county_rows = self._rows_by_level("county")
        township_rows = self._rows_by_level("township")
        village_rows = self._rows_by_level("village")
        stat_zone_rows = self._rows_by_level("stat_zone_min_113")

        counties_by_code = {}
        counties = []

        def ensure_county(county_code, county_id="", county_name="", county_eng=""):
            code = county_code or "__unknown__"
            existing = counties_by_code.get(code)
            if existing:
                if county_id and not existing["countyId"]:
                    existing["countyId"] = county_id
                if county_name and not existing["countyName"]:
                    existing["countyName"] = county_name
                if county_eng and not existing["countyEng"]:
                    existing["countyEng"] = county_eng
                return existing

            created = {
                "countyId": county_id or "",
                "countyCode": county_code or "",
                "countyName": county_name or "",
                "countyEng": county_eng or "",
                "townships": [],
            }
            counties_by_code[code] = created
            counties.append(created)
            return created

        for row in county_rows:
            props = json.loads(row["raw_properties_json"])
            ensure_county(
                row["county_code"] or row["code"] or props.get("COUNTYCODE", ""),
                props.get("COUNTYID", ""),
                row["name_zh"] or props.get("COUNTYNAME", ""),
                row["name_en"] or props.get("COUNTYENG", ""),
            )

        townships_by_code = {}
        for row in township_rows:
            props = json.loads(row["raw_properties_json"])
            county = ensure_county(
                row["county_code"] or props.get("COUNTYCODE", ""),
                props.get("COUNTYID", ""),
                props.get("COUNTYNAME", ""),
            )

            town_code = row["code"] or ""
            key = town_code or f"__unknown_town__::{props.get('TOWNID', '')}::{len(townships_by_code)}"
            township = townships_by_code.get(key)
            if township:
                continue

            township = {
                "townId": props.get("TOWNID", ""),
                "townCode": town_code,
                "townName": row["name_zh"] or props.get("TOWNNAME", ""),
                "townEng": row["name_en"] or props.get("TOWNENG", ""),
                "villages": [],
            }
            townships_by_code[key] = township
            county["townships"].append(township)

        stat_zone_count_by_village = {}
        for row in stat_zone_rows:
            village_code = row["parent_code"] or ""
            if not village_code:
                continue
            stat_zone_count_by_village[village_code] = stat_zone_count_by_village.get(village_code, 0) + 1

        for row in village_rows:
            props = json.loads(row["raw_properties_json"])
            county = ensure_county(
                row["county_code"] or props.get("COUNTYCODE", ""),
                props.get("COUNTYID", ""),
                props.get("COUNTYNAME", ""),
            )

            town_code = row["town_code"] or ""
            town_key = town_code or f"__unknown_town_for_village__::{props.get('TOWNID', '')}"
            township = townships_by_code.get(town_key)
            if not township:
                township = {
                    "townId": props.get("TOWNID", ""),
                    "townCode": town_code,
                    "townName": props.get("TOWNNAME", ""),
                    "townEng": "",
                    "villages": [],
                }
                townships_by_code[town_key] = township
                county["townships"].append(township)

            village_code = row["code"] or props.get("VILLCODE", "")
            village = {
                "villageCode": village_code,
                "villageName": row["name_zh"] or props.get("VILLNAME", ""),
                "villageEng": row["name_en"] or props.get("VILLENG", ""),
                "statZoneCount": stat_zone_count_by_village.get(village_code, 0),
            }
            township["villages"].append(village)

        for county in counties:
            county["townships"].sort(key=lambda item: (item["townCode"], item["townName"]))
            for township in county["townships"]:
                township["villages"].sort(key=lambda item: (item["villageCode"], item["villageName"]))

        counties.sort(key=lambda item: item["countyId"])

        total_townships = sum(len(county["townships"]) for county in counties)
        total_villages = sum(len(township["villages"]) for county in counties for township in county["townships"])

        return {
            "counties": counties,
            "summary": {
                "countyCount": len(counties),
                "townshipCount": total_townships,
                "villageCount": total_villages,
            },
        }

    @lru_cache(maxsize=1)
    def build_ranges_tree(self):
        regions = self.build_regions_tree()
        ranges = []

        for county in regions["counties"]:
            township_nodes = []

            for town in county.get("townships", []):
                village_nodes = []
                for village in town.get("villages", []):
                    village_code = village.get("villageCode", "")
                    if not village_code:
                        continue
                    village_nodes.append(
                        make_range_node(
                            f"village-{village_code}",
                            village.get("villageName", ""),
                            village.get("villageEng", ""),
                            "#d17827",
                            "village",
                            village_code,
                            metadata={
                                "sourceProperty": "VILLCODE",
                                "statZoneCount": int(village.get("statZoneCount", 0)),
                            },
                        )
                    )

                if not town.get("townCode"):
                    continue

                township_nodes.append(
                    make_range_node(
                        f"township-{town.get('townCode', '')}",
                        town.get("townName", ""),
                        town.get("townEng", ""),
                        "#27a693",
                        "township",
                        town.get("townCode", ""),
                        children=village_nodes,
                        metadata={"sourceProperty": "TOWNCODE"},
                    )
                )

            if not county.get("countyCode"):
                continue

            ranges.append(
                make_range_node(
                    f"county-{county.get('countyCode', '')}",
                    county.get("countyName", ""),
                    county.get("countyEng", ""),
                    "#7fb3ff",
                    "county",
                    county.get("countyCode", ""),
                    children=township_nodes,
                    metadata={"sourceProperty": "COUNTYCODE"},
                )
            )

        return {
            "ranges": ranges,
            "summary": regions["summary"],
        }

    def build_village_stat_zone_ranges(self, village_code):
        village_code = str(village_code or "").strip()
        if not village_code:
            return {"villageCode": "", "ranges": [], "summary": {"statZoneCount": 0}}

        connection = self._connect()
        try:
            rows = connection.execute(
                """
                SELECT
                    r.code,
                    r.name_zh,
                    r.name_en,
                    CAST(json_extract(r.raw_properties_json, '$.P_CNT') AS REAL) AS p_cnt
                FROM admin_region AS r
                WHERE r.level = 'stat_zone_min_113'
                  AND r.parent_code = ?
                ORDER BY r.code
                """,
                (village_code,),
            ).fetchall()
        finally:
            connection.close()

        color = self.range_styles.get("stat_zone_min_113", "#72e9b7")
        ranges = []
        for row in rows:
            code = str(row["code"] or "").strip()
            if not code:
                continue
            population = row["p_cnt"]
            population_text = ""
            if population is not None:
                try:
                    population_text = f"Population {int(float(population)):,}"
                except (TypeError, ValueError):
                    population_text = ""
            ranges.append(
                make_range_node(
                    f"stat_zone_min_113-{code}",
                    row["name_zh"] or code,
                    population_text,
                    color,
                    "stat_zone_min_113",
                    code,
                    metadata={
                        "sourceProperty": "CODEBASE",
                        "parentVillageCode": village_code,
                        "pCnt": population,
                    },
                )
            )

        return {
            "villageCode": village_code,
            "ranges": ranges,
            "summary": {"statZoneCount": len(ranges)},
        }

    def _fetch_features_by_level_and_codes(self, level, codes):
        if not codes:
            return {}

        placeholders = ",".join(["?"] * len(codes))
        sql = (
            "SELECT code, raw_properties_json, geom_json FROM admin_region "
            f"WHERE level = ? AND code IN ({placeholders})"
        )

        connection = self._connect()
        try:
            rows = connection.execute(sql, [level, *codes]).fetchall()
        finally:
            connection.close()

        return {row["code"]: row for row in rows}

    def build_range_geojson(self, county_codes, town_codes, village_codes, stat_zone_codes=None):
        features = []
        seen = set()
        stat_zone_codes = split_codes(stat_zone_codes)

        for dataset, level, codes in (
            ("county", "county", county_codes),
            ("township", "township", town_codes),
            ("village", "village", village_codes),
            ("stat_zone_min_113", "stat_zone_min_113", stat_zone_codes),
        ):
            rows_by_code = self._fetch_features_by_level_and_codes(level, codes)
            for code in codes:
                row = rows_by_code.get(code)
                if not row:
                    continue
                key = f"{dataset}:{code}"
                if key in seen:
                    continue
                seen.add(key)

                properties = json.loads(row["raw_properties_json"])
                geometry = json.loads(row["geom_json"])
                features.append(
                    {
                        "type": "Feature",
                        "geometry": geometry,
                        "properties": {
                            **properties,
                            "rangeId": key,
                            "rangeColor": self.range_styles.get(dataset, "#57a6f5"),
                            "rangeType": "admin",
                            "rangeLevel": dataset,
                        },
                    }
                )

        return {
            "type": "FeatureCollection",
            "features": features,
        }

    def _build_stat_zone_filter_clause(
        self,
        stat_zone_codes=None,
        county_codes=None,
        town_codes=None,
        village_codes=None,
    ):
        stat_zone_codes = split_codes(stat_zone_codes)
        county_codes = split_codes(county_codes)
        town_codes = split_codes(town_codes)
        village_codes = split_codes(village_codes)

        filters = []
        params = []
        if stat_zone_codes:
            placeholders = ",".join(["?"] * len(stat_zone_codes))
            filters.append(f"code IN ({placeholders})")
            params.extend(stat_zone_codes)
        if village_codes:
            placeholders = ",".join(["?"] * len(village_codes))
            filters.append(f"parent_code IN ({placeholders})")
            params.extend(village_codes)
        if town_codes:
            placeholders = ",".join(["?"] * len(town_codes))
            filters.append(
                "parent_code IN (SELECT code FROM admin_region WHERE level = 'village' "
                f"AND town_code IN ({placeholders}))"
            )
            params.extend(town_codes)
        if county_codes:
            placeholders = ",".join(["?"] * len(county_codes))
            filters.append(
                "parent_code IN (SELECT code FROM admin_region WHERE level = 'village' "
                f"AND county_code IN ({placeholders}))"
            )
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
    ):
        params = ["stat_zone_min_113"]
        sql = """
            SELECT
                COUNT(1) AS count,
                COALESCE(SUM(CAST(json_extract(raw_properties_json, '$.P_CNT') AS REAL)), 0) AS population
            FROM admin_region
            WHERE level = ?
        """
        extra_clause, extra_params = self._build_stat_zone_filter_clause(
            stat_zone_codes=stat_zone_codes,
            county_codes=county_codes,
            town_codes=town_codes,
            village_codes=village_codes,
        )
        sql += extra_clause
        params.extend(extra_params)

        connection = self._connect()
        try:
            row = connection.execute(sql, params).fetchone()
        finally:
            connection.close()

        count = int(row["count"]) if row else 0
        population = row["population"] if row and row["population"] is not None else 0
        return {
            "count": count,
            "sum": {
                "P_CNT": int(population),
            },
        }

    @staticmethod
    def _ring_area(ring):
        if not isinstance(ring, list) or len(ring) < 3:
            return 0.0
        area = 0.0
        for i in range(len(ring)):
            x1, y1 = ring[i][:2]
            x2, y2 = ring[(i + 1) % len(ring)][:2]
            area += (x1 * y2) - (x2 * y1)
        return area / 2.0

    @staticmethod
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

    @classmethod
    def _geometry_representative_point(cls, geometry):
        if not isinstance(geometry, dict):
            return None
        geometry_type = geometry.get("type")
        coordinates = geometry.get("coordinates")
        if geometry_type == "Polygon" and isinstance(coordinates, list) and coordinates:
            return cls._ring_centroid(coordinates[0])
        if geometry_type == "MultiPolygon" and isinstance(coordinates, list) and coordinates:
            best_ring = None
            best_area = -1.0
            for polygon in coordinates:
                if not isinstance(polygon, list) or not polygon:
                    continue
                ring = polygon[0]
                area = abs(cls._ring_area(ring))
                if area > best_area:
                    best_area = area
                    best_ring = ring
            if best_ring:
                return cls._ring_centroid(best_ring)
        return None

    def query_stat_zone_population_points(
        self,
        stat_zone_codes=None,
        county_codes=None,
        town_codes=None,
        village_codes=None,
        limit=None,
    ):
        sql = """
            SELECT code, parent_code, name_zh, name_en, raw_properties_json, geom_json
            FROM admin_region
            WHERE level = 'stat_zone_min_113'
        """
        params = []
        extra_clause, extra_params = self._build_stat_zone_filter_clause(
            stat_zone_codes=stat_zone_codes,
            county_codes=county_codes,
            town_codes=town_codes,
            village_codes=village_codes,
        )
        sql += extra_clause
        params.extend(extra_params)
        if limit is not None:
            try:
                safe_limit = max(0, int(limit))
            except (TypeError, ValueError):
                safe_limit = 0
            sql += " LIMIT ?"
            params.append(safe_limit)

        connection = self._connect()
        try:
            rows = connection.execute(sql, params).fetchall()
        finally:
            connection.close()

        features = []
        for row in rows:
            properties = json.loads(row["raw_properties_json"])
            geometry = json.loads(row["geom_json"])
            point = self._geometry_representative_point(geometry)
            if not point:
                continue
            features.append(
                {
                    "type": "Feature",
                    "id": row["code"],
                    "geometry": {
                        "type": "Point",
                        "coordinates": point,
                    },
                    "properties": {
                        **properties,
                        "CODEBASE": row["code"],
                        "VILLAGE_CODE": row["parent_code"],
                        "name_zh": row["name_zh"],
                        "name_en": row["name_en"],
                    },
                }
            )
        return features
