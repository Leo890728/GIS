from flask import Blueprint, abort, current_app, request

from backend.services.regions_service import RegionsServiceError, split_codes


bp = Blueprint("ranges", __name__)


@bp.get("/ranges/tree")
def ranges_tree():
    regions_service = current_app.config["REGIONS_SERVICE"]
    return regions_service.build_ranges_tree()


@bp.get("/ranges/stat-zones/<parent_level>/<parent_code>/children")
def stat_zone_children(parent_level, parent_code):
    regions_service = current_app.config["REGIONS_SERVICE"]
    try:
        return regions_service.build_stat_zone_children(parent_level, parent_code)
    except ValueError as err:
        abort(400, description=str(err))


@bp.route("/regions/range-geojson", methods=["GET", "POST"])
def range_geojson():
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        source = payload.get
    else:
        source = request.args.get

    county_codes = split_codes(source("countyCodes"))
    town_codes = split_codes(source("townCodes"))
    village_codes = split_codes(source("villageCodes"))
    stat_zone_codes = split_codes(source("statZoneCodes") or source("statZoneMinCodes"))
    stat_zone_1_codes = split_codes(source("statZone1Codes"))
    stat_zone_2_codes = split_codes(source("statZone2Codes"))

    regions_service = current_app.config["REGIONS_SERVICE"]
    return regions_service.build_range_geojson(
        county_codes,
        town_codes,
        village_codes,
        stat_zone_codes,
        stat_zone_1_codes,
        stat_zone_2_codes,
    )


@bp.post("/regions/pick")
def range_pick():
    payload = request.get_json(silent=True) or {}
    level = str(payload.get("level") or "").strip()

    try:
        lng = float(payload.get("lng"))
        lat = float(payload.get("lat"))
    except (TypeError, ValueError):
        abort(400, description="lng and lat must be numbers")

    if lng < -180 or lng > 180 or lat < -90 or lat > 90:
        abort(400, description="lng/lat out of WGS84 bounds")

    regions_service = current_app.config["REGIONS_SERVICE"]
    try:
        return regions_service.pick_range_by_point(lng, lat, level)
    except ValueError as err:
        abort(400, description=str(err))
    except RegionsServiceError as err:
        abort(500, description=str(err))
