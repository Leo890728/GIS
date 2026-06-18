import sys
from pathlib import Path

from flask import Flask
from flask_cors import CORS

if __package__ in (None, ""):  # pragma: no cover
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from backend.config import (
    BOUNDS_DB_PATH,
    CACHE_DB_PATH,
    DATA_DB_PATH,
    DATASETS,
    DATA_SOURCES,
    HISTORY_DB_PATH,
    PMTILES_BIN,
    RANGE_STYLES,
    SPATIALITE_EXTENSION_PATH,
)
from backend.routes import ALL_BLUEPRINTS
from backend.services.cache_db import CacheDb
from backend.services.dataset_service import DatasetService
from backend.services.history_db import HistoryDb
from backend.services.regions_service import RegionsService


def create_app(config_overrides=None):
    app = Flask(__name__)
    CORS(app)

    app.config["DATASETS"] = DATASETS
    app.config["PMTILES_BIN"] = PMTILES_BIN

    if config_overrides:
        app.config.update(config_overrides)

    if "REGIONS_SERVICE" not in app.config:
        app.config["REGIONS_SERVICE"] = RegionsService(
            bounds_path=BOUNDS_DB_PATH,
            data_path=DATA_DB_PATH,
            range_styles=RANGE_STYLES,
            spatialite_extension_path=SPATIALITE_EXTENSION_PATH,
        )

    if "DATASET_SERVICE" not in app.config:
        app.config["DATASET_SERVICE"] = DatasetService(
            DATA_SOURCES,
            cache_db=CacheDb(CACHE_DB_PATH),
            history_db=HistoryDb(HISTORY_DB_PATH),
        )

    for blueprint in ALL_BLUEPRINTS:
        app.register_blueprint(blueprint)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)
