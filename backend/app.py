import sys
from pathlib import Path

from flask import Flask
from flask_cors import CORS

if __package__ in (None, ""):  # pragma: no cover
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from backend.config import (
    DATASETS,
    DATA_SOURCES,
    GEOJSON_DIR,
    PMTILES_BIN,
    RANGE_STYLES,
    REGIONS_DB_PATH,
    REGIONS_SYNC_MODE,
    REGIONS_SYNC_STRICT,
    SPATIALITE_EXTENSION_PATH,
)
from backend.routes import ALL_BLUEPRINTS
from backend.services.dataset_service import DatasetService
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
            geojson_dir=GEOJSON_DIR,
            range_styles=RANGE_STYLES,
            db_path=REGIONS_DB_PATH,
            spatialite_extension_path=SPATIALITE_EXTENSION_PATH,
            sync_mode=REGIONS_SYNC_MODE,
            sync_strict=REGIONS_SYNC_STRICT,
        )

    if "DATASET_SERVICE" not in app.config:
        app.config["DATASET_SERVICE"] = DatasetService(DATA_SOURCES)

    for blueprint in ALL_BLUEPRINTS:
        app.register_blueprint(blueprint)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)
