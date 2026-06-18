import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = Path(__file__).resolve().parent
PMTILES_BIN = ROOT / "tools" / "pmtiles" / "pmtiles.exe"
PMTILES_DIR = BACKEND_DIR / "pmtiles"
BOUNDS_DB_PATH = BACKEND_DIR / "data" / "bounds.sqlite"
DATA_DB_PATH   = BACKEND_DIR / "data" / "data.sqlite"

DATASETS = {
    "county":            PMTILES_DIR / "county.pmtiles",
    "township":          PMTILES_DIR / "township.pmtiles",
    "village":           PMTILES_DIR / "village.pmtiles",
    "stat_zone_2":       PMTILES_DIR / "stat_zone_2.pmtiles",
    "stat_zone_1":       PMTILES_DIR / "stat_zone_1.pmtiles",
    "stat_zone":         PMTILES_DIR / "stat_zone.pmtiles",
}

RANGE_STYLES = {
    "county":      "#7fb3ff",
    "township":    "#57a6f5",
    "village":     "#d17827",
    "stat_zone_2": "#a78bfa",
    "stat_zone_1": "#34d399",
    "stat_zone":   "#72e9b7",
}

CACHE_DB_PATH = BACKEND_DIR / "data" / "cache.sqlite"
SPATIALITE_EXTENSION_PATH = os.getenv(
    "SPATIALITE_EXTENSION_PATH",
    str(ROOT / "tools" / "spatialite" / "mod_spatialite.dll"),
)

DATA_SOURCES = {
	"taichung_garbage_recycling_dynamic": {
		"adapter": "generic_http_json",
		"url": "https://newdatacenter.taichung.gov.tw/api/v1/no-auth/resource.download?rid=c923ad20-2ec6-43b9-b3ab-54527e99f7bc",
		"refresh_seconds": 600,
		"fields": {
			"id_parts": ["lineid", "car", "time"],
			"lng": "X",
			"lat": "Y",
			"timestamp": "time",
		},
	},
	"taichung_garbage_recycling_dynamic_V2": {
		"adapter": "taichung_ws_skyeyes",
		"bootstrap_url": "https://cleaner.epb.taichung.gov.tw/index.aspx",
		"url": "https://cleaner.epb.taichung.gov.tw/WebService/WsSkyeyes.asmx/NewgetCarsinfo",
		"method": "POST",
		"headers": {
			"accept": "*/*",
			"content-type": "application/json; charset=UTF-8",
			"x-requested-with": "XMLHttpRequest",
			"origin": "https://cleaner.epb.taichung.gov.tw",
			"referer": "https://cleaner.epb.taichung.gov.tw/index.aspx",
		},
		"body": "",
		"rows_path": ["d", "DATA"],
		"refresh_seconds": 60,
		"fields": {
			"id_parts": ["car_id", "car_licence", "dt"],
			"lng": "x",
			"lat": "y",
			"timestamp": "dt",
		},
	},
    "stat_zone_population_points": {
        "adapter": "regions_sqlite_stat_zone_points",
        "db_path": str(BOUNDS_DB_PATH),
        "refresh_seconds": 86400,
        "limit": 200000,
        "fields": {
            "id_parts": ["CODEBASE"],
            "lng": "X",
            "lat": "Y",
        },
    },
    "moenv_incinerators": {
        "adapter": "moenv_incinerator_geocode",
        "url": (
            "https://data.moenv.gov.tw/api/v2/fac_s_01"
            "?api_key=af57253c-e838-46da-a1f5-12b43afd75f3"
            "&limit=1000&sort=ImportDate%20desc&format=JSON"
        ),
        "refresh_seconds": 86400,
        "geocode_address_field": "budadd",
        "geocode_retry_days": 7,
        "cache_db_path": str(CACHE_DB_PATH),
        "fields": {
            "id_parts": ["wepno"],
            "lng": "_lng",
            "lat": "_lat",
        },
    },
}
