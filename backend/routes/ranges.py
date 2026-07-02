from flask import Blueprint, abort, current_app, request

from backend.services.regions_service import split_codes


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
