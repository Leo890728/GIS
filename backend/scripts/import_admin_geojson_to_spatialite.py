from __future__ import annotations

import argparse
import sys

from backend.config import GEOJSON_DIR, REGIONS_DB_PATH, SPATIALITE_EXTENSION_PATH
from backend.services.regions_db import RegionsSyncError, import_admin_regions


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Import admin GeoJSON into SQLite/SpatiaLite")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild admin_region table from source GeoJSON")
    parser.add_argument(
        "--allow-no-spatialite",
        action="store_true",
        help="Allow import even when SpatiaLite extension cannot be loaded",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv or sys.argv[1:])
    if not args.rebuild:
        print("No operation requested. Use --rebuild.")
        return 0

    try:
        import_admin_regions(
            geojson_dir=GEOJSON_DIR,
            db_path=REGIONS_DB_PATH,
            spatialite_extension_path=SPATIALITE_EXTENSION_PATH,
            require_spatialite=not args.allow_no_spatialite,
        )
    except RegionsSyncError as err:
        print(f"Import failed: {err}")
        return 1

    print(f"Import completed: {REGIONS_DB_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
