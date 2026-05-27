import json
from pathlib import Path
import sqlite3

from backend.data_sources.base import BaseDataSourceAdapter
from backend.services.regions_db import ensure_base_schema, rebuild_stat_zone_point_cache


class RegionsSqliteStatZonePointsAdapter(BaseDataSourceAdapter):
    def fetch_payload(self, fetcher, source):
        db_path = Path(source.get("db_path", "")).expanduser()
        if not db_path.exists():
            raise RuntimeError(f"Regions DB not found: {db_path}")

        connection = sqlite3.connect(str(db_path))
        connection.row_factory = sqlite3.Row
        try:
            ensure_base_schema(connection)
            count_row = connection.execute("SELECT COUNT(1) AS count FROM stat_zone_point").fetchone()
            if not count_row or int(count_row["count"]) == 0:
                rebuild_stat_zone_point_cache(connection)

            limit = int(source.get("limit", 200000))
            rows = connection.execute(
                """
                SELECT
                    code,
                    village_code,
                    county_code,
                    town_code,
                    name_zh,
                    name_en,
                    lng,
                    lat,
                    p_cnt,
                    raw_properties_json
                FROM stat_zone_point
                LIMIT ?
                """,
                (max(0, limit),),
            ).fetchall()
        finally:
            connection.close()

        payload = []
        for row in rows:
            properties = {}
            raw_json = row["raw_properties_json"] or "{}"
            try:
                parsed = json.loads(raw_json)
                if isinstance(parsed, dict):
                    properties.update(parsed)
            except json.JSONDecodeError:
                pass

            properties.update(
                {
                    "CODEBASE": row["code"],
                    "VILLAGE_CODE": row["village_code"],
                    "COUNTY_CODE": row["county_code"],
                    "TOWN_CODE": row["town_code"],
                    "name_zh": row["name_zh"],
                    "name_en": row["name_en"],
                    "P_CNT": row["p_cnt"],
                    "X": row["lng"],
                    "Y": row["lat"],
                }
            )
            payload.append(properties)
        return payload

    def extract_rows(self, payload, source):
        if isinstance(payload, list):
            return payload
        raise ValueError("Unsupported payload for regions_sqlite_stat_zone_points adapter")

