"""
Build precomputed tables in backend/data/bounds.sqlite (requires SpatiaLite):

  stat_zone_village_map  — which village each stat_zone centroid falls in
  stat_zone_point_cache  — WGS84 centroid + P_CNT per stat_zone

Run via Docker:
  docker run --rm -v "${PWD}:/workspace" ghcr.io/osgeo/gdal:alpine-normal-latest \
    python /workspace/tools/docker/build_bounds_extras.py
"""
import os
import sys
import sqlite3
from pathlib import Path

BOUNDS = os.getenv("BOUNDS_DB", "/workspace/backend/data/bounds.sqlite")
DATA   = os.getenv("DATA_DB",   "/workspace/backend/data/data.sqlite")


def main():
    if not Path(BOUNDS).exists():
        sys.exit(f"ERROR: {BOUNDS} not found")
    if not Path(DATA).exists():
        sys.exit(f"ERROR: {DATA} not found")

    conn = sqlite3.connect(BOUNDS)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.enable_load_extension(True)
    conn.load_extension("/usr/lib/mod_spatialite.so.8")
    print(f"SpatiaLite {conn.execute('SELECT spatialite_version()').fetchone()[0]} loaded")

    # ── 1. stat_zone_village_map ──────────────────────────────────────────────
    print("=== [1/2] stat_zone_village_map ===")
    conn.execute("DROP TABLE IF EXISTS stat_zone_village_map")
    conn.execute("""
        CREATE TABLE stat_zone_village_map (
            codebase TEXT PRIMARY KEY,
            villcode TEXT
        )
    """)
    # Use the R-tree virtual table (idx_village_GEOMETRY) created by ogr2ogr
    # to narrow down candidates before the precise ST_Within check.
    conn.execute("""
        INSERT INTO stat_zone_village_map (codebase, villcode)
        SELECT sz.codebase, v.villcode
        FROM stat_zone AS sz
        JOIN village AS v ON v.ROWID IN (
            SELECT pkid FROM idx_village_GEOMETRY
            WHERE xmin <= ST_X(ST_Centroid(sz.GEOMETRY))
              AND xmax >= ST_X(ST_Centroid(sz.GEOMETRY))
              AND ymin <= ST_Y(ST_Centroid(sz.GEOMETRY))
              AND ymax >= ST_Y(ST_Centroid(sz.GEOMETRY))
        )
        WHERE ST_Within(ST_Centroid(sz.GEOMETRY), v.GEOMETRY)
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_szvm_villcode ON stat_zone_village_map (villcode)")
    n = conn.execute("SELECT COUNT(*) FROM stat_zone_village_map").fetchone()[0]
    print(f"  {n:,} / 157,933 rows mapped")

    # ── 2. stat_zone_point_cache ──────────────────────────────────────────────
    print("=== [2/2] stat_zone_point_cache ===")
    conn.execute(f"ATTACH '{DATA}' AS d")
    conn.execute("DROP TABLE IF EXISTS stat_zone_point_cache")
    conn.execute("""
        CREATE TABLE stat_zone_point_cache (
            codebase  TEXT PRIMARY KEY,
            villcode  TEXT,
            county_id TEXT,
            town_id   TEXT,
            lng       REAL,
            lat       REAL,
            p_cnt     REAL
        )
    """)
    conn.execute("""
        INSERT INTO stat_zone_point_cache
            (codebase, villcode, county_id, town_id, lng, lat, p_cnt)
        SELECT
            sz.codebase,
            m.villcode,
            sz.county_id,
            sz.town_id,
            ST_X(ST_Centroid(sz.GEOMETRY)),
            ST_Y(ST_Centroid(sz.GEOMETRY)),
            CAST(da.P_CNT AS REAL)
        FROM stat_zone sz
        LEFT JOIN stat_zone_village_map m  ON m.codebase  = sz.codebase
        LEFT JOIN d.stat_zone_stats_113 da ON da.CODEBASE = sz.codebase
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_szpc_villcode  ON stat_zone_point_cache (villcode)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_szpc_county_id ON stat_zone_point_cache (county_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_szpc_town_id   ON stat_zone_point_cache (town_id)")
    n = conn.execute("SELECT COUNT(*) FROM stat_zone_point_cache").fetchone()[0]
    print(f"  {n:,} rows")

    conn.commit()
    conn.close()
    print("Done")


main()
