from flask import Blueprint, Response, abort, current_app

from backend.services.tile_service import read_vector_tile


bp = Blueprint("tiles", __name__)


@bp.get("/tiles/<dataset>/<int:z>/<int:x>/<int:y>.pbf")
def tile(dataset, z, x, y):
    try:
        payload = read_vector_tile(
            current_app.config["PMTILES_BIN"],
            current_app.config["DATASETS"],
            dataset,
            z,
            x,
            y,
        )
    except FileNotFoundError as err:
        abort(500, description=str(err))

    if payload is None:
        return Response(status=404)

    headers = {"Content-Type": "application/vnd.mapbox-vector-tile"}
    return Response(payload, headers=headers)
