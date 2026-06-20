import os
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
from backend.services.history_poller import start_history_poller
from backend.services.regions_service import RegionsService


def _history_poll_enabled():
    if os.getenv("HISTORY_BACKGROUND_POLL", "1").strip().lower() in ("0", "false", "no", "off"):
        return False
    # Under the Werkzeug debug reloader two processes import the app; only the
    # reloader child sets WERKZEUG_RUN_MAIN. Skip the parent to avoid double jobs.
    if os.getenv("RUN_DEV_SERVER") == "1" and os.getenv("WERKZEUG_RUN_MAIN") != "true":
        return False
    return True


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
        dataset_service = DatasetService(
            DATA_SOURCES,
            cache_db=CacheDb(CACHE_DB_PATH),
            history_db=HistoryDb(HISTORY_DB_PATH),
        )
        app.config["DATASET_SERVICE"] = dataset_service
        if _history_poll_enabled():
            app.config["HISTORY_POLLER"] = start_history_poller(dataset_service, DATA_SOURCES)

    for blueprint in ALL_BLUEPRINTS:
        app.register_blueprint(blueprint)

    return app


if __name__ == "__main__":
    os.environ["RUN_DEV_SERVER"] = "1"
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)
