from backend.data_sources.adapters.generic_http_json import GenericHttpJsonAdapter
from backend.data_sources.adapters.moenv_incinerator_geocode import MoenvIncineratorGeocodeAdapter
from backend.data_sources.adapters.regions_sqlite_stat_zone_points import RegionsSqliteStatZonePointsAdapter
from backend.data_sources.adapters.taichung_ws_skyeyes import TaichungWsSkyeyesAdapter


ADAPTER_REGISTRY = {
    "generic_http_json": GenericHttpJsonAdapter(),
    "moenv_incinerator_geocode": MoenvIncineratorGeocodeAdapter(),
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
