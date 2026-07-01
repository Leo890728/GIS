import re
import time
from urllib.parse import quote

from backend.data_sources.base import BaseDataSourceAdapter

# ArcGIS World Geocoder — noticeably more accurate for Taiwan addresses than
# Nominatim. findAddressCandidates (no result storage) needs no token.
_ARCGIS_URL = "https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates"
_ARCGIS_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-TW,zh;q=0.9",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
    ),
}
# ArcGIS has no strict per-second policy like Nominatim; a small courtesy delay
# is enough to avoid throttling on a daily refresh.
_GEOCODE_DELAY_SECONDS = 0.2
_CITY_DISTRICT_PATTERN = re.compile(r"^(.{2,4}[市縣].{1,4}[區鄉鎮市])")
_BUILDING_NUMBER_SUFFIX_PATTERN = re.compile(r"\d+(?:之\d+)?號.*$")
_TRIM_SUFFIX_PATTERN = re.compile(r"[\s,，]+$")


class MoenvIncineratorGeocodeAdapter(BaseDataSourceAdapter):
    """Fetches HTTP JSON data and geocodes an address field via ArcGIS.

    Geocode results are persisted in a shared SQLite CacheDb instance.
    Failed entries are retried after geocode_retry_days (default 7).
    """

    def extract_rows(self, payload, source):
        rows = self._extract_moenv_rows(payload, source)
        if not rows:
            return rows

        address_field = source.get("geocode_address_field", "budadd")
        retry_after_days = int(source.get("geocode_retry_days", 7))
        cache_db = self._open_cache_db(source)
        http_fetcher = self._make_http_fetcher()

        for row in rows:
            address = (row.get(address_field) or "").strip()
            if not address:
                continue

            cached = (
                cache_db.get_geocode(address, retry_after_days=retry_after_days)
                if cache_db
                else None
            )

            if cached is None:
                coords = self._geocode(address, http_fetcher)
                if coords:
                    if cache_db:
                        cache_db.set_geocode(address, coords["lng"], coords["lat"])
                    row["_lng"] = coords["lng"]
                    row["_lat"] = coords["lat"]
                else:
                    if cache_db:
                        cache_db.set_geocode_failed(address)
                time.sleep(_GEOCODE_DELAY_SECONDS)
            elif cached is not False:
                row["_lng"] = cached["lng"]
                row["_lat"] = cached["lat"]

        return [r for r in rows if "_lng" in r and "_lat" in r]

    def _extract_moenv_rows(self, payload, source):
        # MOENV endpoint has returned both top-level list and {"records":[...]} shapes.
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            records = payload.get("records")
            if isinstance(records, list):
                return records
        return super().extract_rows(payload, source)

    # ------------------------------------------------------------------

    def _open_cache_db(self, source):
        db_path = source.get("cache_db_path")
        if not db_path:
            return None
        from backend.services.cache_db import CacheDb
        return CacheDb(db_path)

    def _geocode(self, address, fetcher):
        """Try progressively simpler queries to maximize ArcGIS hit rate."""
        for query in self._build_queries(address):
            try:
                result = fetcher({
                    "url": (
                        f"{_ARCGIS_URL}?SingleLine={quote(query)}"
                        "&f=json&outSR=4326"
                        "&outFields=Addr_type,Match_addr,StAddr,City"
                        "&maxLocations=6"
                    ),
                    "method": "GET",
                    "headers": _ARCGIS_HEADERS,
                })
                coords = self._best_candidate(result)
                if coords:
                    return coords
            except Exception:
                pass
            time.sleep(_GEOCODE_DELAY_SECONDS)
        return None

    @staticmethod
    def _best_candidate(result):
        """Pick the top ArcGIS candidate (candidates are score-sorted desc)."""
        if not isinstance(result, dict):
            return None
        candidates = result.get("candidates")
        if not candidates:
            return None
        location = candidates[0].get("location") or {}
        x, y = location.get("x"), location.get("y")
        if x is None or y is None:
            return None
        return {"lng": float(x), "lat": float(y)}

    @staticmethod
    def _build_queries(address):
        """Generate fallback query sequence for Taiwan addresses."""
        address = (address or "").strip()
        if not address:
            return []

        queries = [address]

        stripped = _BUILDING_NUMBER_SUFFIX_PATTERN.sub("", address)
        stripped = _TRIM_SUFFIX_PATTERN.sub("", stripped).strip()
        if stripped and stripped != address:
            queries.append(stripped)

        city_district = _CITY_DISTRICT_PATTERN.match(address)
        if city_district:
            cd = city_district.group(1)
            if cd not in queries:
                queries.append(cd)

        return queries

    def _make_http_fetcher(self):
        import httpx

        client = httpx.Client(timeout=10.0, follow_redirects=True)

        def fetcher(request_data):
            r = client.request(
                method=request_data.get("method", "GET"),
                url=request_data["url"],
                headers=request_data.get("headers") or {},
            )
            r.raise_for_status()
            return r.json()

        return fetcher
