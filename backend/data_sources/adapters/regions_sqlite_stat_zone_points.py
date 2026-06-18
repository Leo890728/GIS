from pathlib import Path
import sqlite3

from backend.data_sources.base import BaseDataSourceAdapter


class RegionsSqliteStatZonePointsAdapter(BaseDataSourceAdapter):
    def fetch_payload(self, fetcher, source):
        db_path = Path(source.get("db_path", "")).expanduser()
        if not db_path.exists():
            raise RuntimeError(f"bounds.sqlite not found: {db_path}")

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            limit = int(source.get("limit", 200000))
            rows = conn.execute(
                """
                SELECT codebase, villcode, county_id, town_id, lng, lat, p_cnt
                FROM stat_zone_point_cache
                WHERE lng IS NOT NULL AND lat IS NOT NULL
                LIMIT ?
                """,
                (max(0, limit),),
            ).fetchall()
        finally:
            conn.close()

        return [
            {
                "CODEBASE": row["codebase"],
                "VILLAGE_CODE": row["villcode"],
                "COUNTY_CODE": row["county_id"],
                "TOWN_CODE": row["town_id"],
                "P_CNT": row["p_cnt"],
                "X": row["lng"],
                "Y": row["lat"],
            }
            for row in rows
        ]

    def extract_rows(self, payload, source):
        if isinstance(payload, list):
            return payload
        raise ValueError("Unsupported payload for regions_sqlite_stat_zone_points adapter")
