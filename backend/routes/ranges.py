from flask import Blueprint, current_app, request

from backend.services.regions_service import split_codes


bp = Blueprint("ranges", __name__)


@bp.get("/ranges/tree")
def ranges_tree():
    regions_service = current_app.config["REGIONS_SERVICE"]
    return regions_service.build_ranges_tree()


@bp.get("/ranges/village/<village_code>/stat-zones")
def village_stat_zones(village_code):
    regions_service = current_app.config["REGIONS_SERVICE"]
    return regions_service.build_village_stat_zone_ranges(village_code)


@bp.route("/regions/range-geojson", methods=["GET", "POST"])
def range_geojson():
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        county_codes = split_codes(payload.get("countyCodes"))
        town_codes = split_codes(payload.get("townCodes"))
        village_codes = split_codes(payload.get("villageCodes"))
        stat_zone_codes = split_codes(payload.get("statZoneCodes") or payload.get("statZoneMinCodes"))
    else:
        county_codes = split_codes(request.args.get("countyCodes"))
        town_codes = split_codes(request.args.get("townCodes"))
        village_codes = split_codes(request.args.get("villageCodes"))
        stat_zone_codes = split_codes(
            request.args.get("statZoneCodes") or request.args.get("statZoneMinCodes")
        )

    regions_service = current_app.config["REGIONS_SERVICE"]
    return regions_service.build_range_geojson(
        county_codes,
        town_codes,
        village_codes,
        stat_zone_codes,
    )
