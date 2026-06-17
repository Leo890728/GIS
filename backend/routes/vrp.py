from flask import Blueprint, abort, current_app, request

from backend.services.garbage_vrp_service import solve_garbage_vrp


bp = Blueprint("vrp", __name__)


@bp.post("/api/vrp/solve-garbage")
def solve_garbage():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        abort(400, description="Body must be a JSON object")

    dataset_service = current_app.config["DATASET_SERVICE"]
    regions_service = current_app.config["REGIONS_SERVICE"]

    try:
        return solve_garbage_vrp(payload, dataset_service, regions_service)
    except ValueError as err:
        abort(400, description=str(err))
    except LookupError as err:
        abort(422, description=str(err))
    except RuntimeError as err:
        abort(503, description=str(err))
