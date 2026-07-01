from backend.data_sources.adapters.generic_http_json import GenericHttpJsonAdapter
from backend.data_sources.adapters.moenv_incinerator_geocode import MoenvIncineratorGeocodeAdapter
from backend.data_sources.adapters.regions_sqlite_stat_zone_points import RegionsSqliteStatZonePointsAdapter
from backend.data_sources.adapters.taichung_ws_skyeyes import TaichungWsSkyeyesAdapter


# The geocoding adapter is address-source agnostic (it geocodes whichever
# `geocode_address_field` a source configures), so expose it under a generic
# alias too; `moenv_incinerator_geocode` is kept for backward compatibility.
_geocode_adapter = MoenvIncineratorGeocodeAdapter()

ADAPTER_REGISTRY = {
    "generic_http_json": GenericHttpJsonAdapter(),
    "http_json_geocode": _geocode_adapter,
    "moenv_incinerator_geocode": _geocode_adapter,
    "regions_sqlite_stat_zone_points": RegionsSqliteStatZonePointsAdapter(),
    "taichung_ws_skyeyes": TaichungWsSkyeyesAdapter(),
}

__all__ = [
    "ADAPTER_REGISTRY",
    "GenericHttpJsonAdapter",
    "MoenvIncineratorGeocodeAdapter",
    "RegionsSqliteStatZonePointsAdapter",
    "TaichungWsSkyeyesAdapter",
]
