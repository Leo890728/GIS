import ctypes
from functools import lru_cache
import json
import os
from pathlib import Path
import sqlite3


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
            sz_count_rows = conn.execute(
                "SELECT villcode, COUNT(*) AS cnt FROM stat_zone_village_map GROUP BY villcode"
            ).fetchall()
        finally:
            conn.close()

        sz_count = {row["villcode"]: row["cnt"] for row in sz_count_rows}

        counties_by_code = {}
        counties = []
        for row in county_rows:
            county = {
                "countyId": row["countyid"] or "",
                "countyCode": row["countycode"] or "",
                "countyName": row["countyname"] or "",
                "countyEng": row["countyeng"] or "",
                "townships": [],
            }
            counties_by_code[row["countycode"]] = county
            counties.append(county)

        townships_by_code = {}
        for row in township_rows:
            county = counties_by_code.get(row["countycode"])
            if not county:
                continue
            township = {
                "townId": row["townid"] or "",
                "townCode": row["towncode"] or "",
                "townName": row["townname"] or "",
                "townEng": row["towneng"] or "",
                "villages": [],
            }
            townships_by_code[row["towncode"]] = township
            county["townships"].append(township)

        for row in village_rows:
            township = townships_by_code.get(row["towncode"])
            if not township:
                continue
            vcode = row["villcode"] or ""
            township["villages"].append({
                "villageCode": vcode,
                "villageName": row["villname"] or "",
                "villageEng": row["villeng"] or "",
                "statZoneCount": sz_count.get(vcode, 0),
            })

        total_townships = sum(len(c["townships"]) for c in counties)
        total_villages = sum(len(t["villages"]) for c in counties for t in c["townships"])

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
                    vcode = village.get("villageCode", "")
                    if not vcode:
                        continue
                    village_nodes.append(
                        make_range_node(
                            f"village-{vcode}",
                            village.get("villageName", ""),
                            village.get("villageEng", ""),
                            "#d17827",
                            "village",
                            vcode,
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
                        f"township-{town['townCode']}",
                        town.get("townName", ""),
                        town.get("townEng", ""),
                        "#27a693",
                        "township",
                        town["townCode"],
                        children=village_nodes,
                        metadata={"sourceProperty": "TOWNCODE"},
                    )
                )

            if not county.get("countyCode"):
                continue
            ranges.append(
                make_range_node(
                    f"county-{county['countyCode']}",
                    county.get("countyName", ""),
                    county.get("countyEng", ""),
                    "#7fb3ff",
                    "county",
                    county["countyCode"],
                    children=township_nodes,
                    metadata={"sourceProperty": "COUNTYCODE"},
                )
            )

        return {"ranges": ranges, "summary": regions["summary"]}

    # ── village stat zones ────────────────────────────────────────────────────

    def build_village_stat_zone_ranges(self, village_code):
        village_code = str(village_code or "").strip()
        if not village_code:
            return {"villageCode": "", "ranges": [], "summary": {"statZoneCount": 0}}

        conn = self._connect_bounds()
        try:
            rows = conn.execute(
                "SELECT codebase, p_cnt FROM stat_zone_point_cache"
                " WHERE villcode = ? ORDER BY codebase",
                (village_code,),
            ).fetchall()
        finally:
            conn.close()

        color = self.range_styles.get("stat_zone", "#72e9b7")
        ranges = []
        for row in rows:
            codebase = row["codebase"]
            population = row["p_cnt"]
            pop_text = ""
            if population is not None:
                try:
                    pop_text = f"Population {int(float(population)):,}"
                except (TypeError, ValueError):
                    pass
            ranges.append(
                make_range_node(
                    f"stat_zone-{codebase}",
                    codebase,
                    pop_text,
                    color,
                    "stat_zone",
                    codebase,
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

    # ── range GeoJSON (requires SpatiaLite) ───────────────────────────────────

    def build_range_geojson(self, county_codes, town_codes, village_codes, stat_zone_codes=None):
        stat_zone_codes = split_codes(stat_zone_codes)

        conn = self._connect_bounds(load_spatialite=True)
        features = []
        seen = set()
        try:
            for layer, table, code_col, codes in (
                ("county",            "county",    "countycode", county_codes),
                ("township",          "township",  "towncode",   town_codes),
                ("village",           "village",   "villcode",   village_codes),
                ("stat_zone",         "stat_zone", "codebase",   stat_zone_codes),
            ):
                if not codes:
                    continue
                ph = ",".join("?" * len(codes))
                rows = conn.execute(
                    f"SELECT *, AsGeoJSON(GEOMETRY) AS _geom"
                    f" FROM {table} WHERE {code_col} IN ({ph})",
                    codes,
                ).fetchall()
                for row in rows:
                    code = row[code_col]
                    key = f"{layer}:{code}"
                    if key in seen:
                        continue
                    seen.add(key)
                    geom_json = row["_geom"]
                    if not geom_json:
                        continue
                    props = {k: row[k] for k in row.keys() if k not in ("GEOMETRY", "_geom")}
                    props.update({
                        "rangeId": key,
                        "rangeColor": self.range_styles.get(layer, "#57a6f5"),
                        "rangeType": "admin",
                        "rangeLevel": layer,
                    })
                    features.append({
                        "type": "Feature",
                        "geometry": json.loads(geom_json),
                        "properties": props,
                    })
        finally:
            conn.close()

        return {"type": "FeatureCollection", "features": features}

    # ── stat zone population ──────────────────────────────────────────────────

    def _stat_zone_cache_filter(
        self, stat_zone_codes, county_codes, town_codes, village_codes
    ):
        stat_zone_codes = split_codes(stat_zone_codes)
        county_codes = split_codes(county_codes)
        town_codes = split_codes(town_codes)
        village_codes = split_codes(village_codes)

        filters, params = [], []
        if stat_zone_codes:
            ph = ",".join("?" * len(stat_zone_codes))
            filters.append(f"codebase IN ({ph})")
            params.extend(stat_zone_codes)
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
    ):
        extra, params = self._stat_zone_cache_filter(
            stat_zone_codes, county_codes, town_codes, village_codes
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
        limit=None,
    ):
        extra, params = self._stat_zone_cache_filter(
            stat_zone_codes, county_codes, town_codes, village_codes
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

        features = []
        for row in rows:
            features.append({
                "type": "Feature",
                "id": row["codebase"],
                "geometry": {"type": "Point", "coordinates": [row["lng"], row["lat"]]},
                "properties": {
                    "CODEBASE": row["codebase"],
                    "VILLAGE_CODE": row["villcode"],
                    "COUNTY_CODE": row["county_id"],
                    "TOWN_CODE": row["town_id"],
                    "P_CNT": row["p_cnt"],
                    "X": row["lng"],
                    "Y": row["lat"],
                },
            })
        return features
