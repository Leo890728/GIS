from flask import Blueprint, abort, current_app, request

from backend.schemas.data_points import normalize_point_collection
from backend.services.point_query import feature_collection
from backend.services.regions_service import split_codes


bp = Blueprint("data_api", __name__)


def _payload():
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        abort(400, description="Body must be a JSON object")
    return payload


def _features_from_payload(payload):
    if "data" not in payload:
        return None
    try:
        return normalize_point_collection(payload["data"])
    except ValueError as err:
        abort(400, description=str(err))


def _resolve_data_id(payload):
    data_id = payload.get("dataId")
    if not data_id or not isinstance(data_id, str):
        abort(400, description="dataId is required when data is not provided")
    return data_id


@bp.get("/datasets")
def datasets():
    service = current_app.config["DATASET_SERVICE"]
    return {"datasets": service.list_datasets()}


@bp.get("/data/meta/<data_id>")
def data_meta(data_id):
    service = current_app.config["DATASET_SERVICE"]
    try:
        return service.get_meta(data_id)
    except KeyError as err:
        abort(404, description=str(err))


@bp.post("/data/refresh/<data_id>")
def data_refresh(data_id):
    service = current_app.config["DATASET_SERVICE"]
    try:
        features = service.refresh(data_id, force=True)
        return {"ok": True, "dataId": data_id, "count": len(features)}
    except KeyError as err:
        abort(404, description=str(err))
    except RuntimeError as err:
        abort(503, description=str(err))


@bp.post("/data/query")
def data_query():
    payload = _payload()
    service = current_app.config["DATASET_SERVICE"]
    inline_features = _features_from_payload(payload)
    try:
        if inline_features is not None:
            features = service.query_inline(inline_features, payload)
        else:
            features = service.query(_resolve_data_id(payload), payload)
    except KeyError as err:
        abort(404, description=str(err))
    except RuntimeError as err:
        abort(503, description=str(err))
    except ValueError as err:
        abort(400, description=str(err))
    return feature_collection(features)


@bp.post("/data/aggregate")
def data_aggregate():
    payload = _payload()
    service = current_app.config["DATASET_SERVICE"]
    inline_features = _features_from_payload(payload)
    try:
        if inline_features is not None:
            result = service.aggregate_inline(inline_features, payload)
        else:
            result = service.aggregate(_resolve_data_id(payload), payload)
    except KeyError as err:
        abort(404, description=str(err))
    except RuntimeError as err:
        abort(503, description=str(err))
    except ValueError as err:
        abort(400, description=str(err))
    return result


@bp.post("/data/admin/aggregate")
def data_admin_aggregate():
    payload = _payload()
    regions_service = current_app.config["REGIONS_SERVICE"]
    stat_zone_codes = payload.get("statZoneCodes") or payload.get("statZoneMinCodes")
    county_codes = payload.get("countyCodes")
    town_codes = payload.get("townCodes")
    village_codes = payload.get("villageCodes")
    try:
        return regions_service.aggregate_stat_zone_population(
            stat_zone_codes=stat_zone_codes,
            county_codes=county_codes,
            town_codes=town_codes,
            village_codes=village_codes,
            stat_zone_1_codes=payload.get("statZone1Codes"),
            stat_zone_2_codes=payload.get("statZone2Codes"),
        )
    except ValueError as err:
        abort(400, description=str(err))


@bp.post("/data/admin/stat-zone-points")
def data_admin_stat_zone_points():
    payload = _payload()
    regions_service = current_app.config["REGIONS_SERVICE"]
    stat_zone_codes = split_codes(payload.get("statZoneCodes") or payload.get("statZoneMinCodes"))
    county_codes = split_codes(payload.get("countyCodes"))
    town_codes = split_codes(payload.get("townCodes"))
    village_codes = split_codes(payload.get("villageCodes"))
    try:
        features = regions_service.query_stat_zone_population_points(
            stat_zone_codes=stat_zone_codes,
            county_codes=county_codes,
            town_codes=town_codes,
            village_codes=village_codes,
            stat_zone_1_codes=split_codes(payload.get("statZone1Codes")),
            stat_zone_2_codes=split_codes(payload.get("statZone2Codes")),
            limit=payload.get("limit"),
        )
    except ValueError as err:
        abort(400, description=str(err))
    return feature_collection(features)
