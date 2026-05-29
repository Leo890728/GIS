import re
import time

from backend.data_sources.base import BaseDataSourceAdapter

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_NOMINATIM_HEADERS = {
    "User-Agent": "GIS-Platform/1.0 (lin24362525@gmail.com)",
    "Accept-Language": "zh-TW,zh;q=0.9",
}
_CITY_DISTRICT_PATTERN = re.compile(r"^(.{2,4}[市縣].{1,4}[區鄉鎮市])")
_BUILDING_NUMBER_SUFFIX_PATTERN = re.compile(r"\d+(?:之\d+)?號.*$")
_TRIM_SUFFIX_PATTERN = re.compile(r"[\s,，]+$")


class MoenvIncineratorGeocodeAdapter(BaseDataSourceAdapter):
    """Fetches MOENV incinerator data and geocodes addresses via Nominatim.

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
                time.sleep(1.1)
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
        """Try progressively simpler queries to maximize Nominatim hit rate."""
        for query in self._build_queries(address):
            try:
                result = fetcher({
                    "url": f"{_NOMINATIM_URL}?q={query}&format=json&limit=1&countrycodes=tw",
                    "method": "GET",
                    "headers": _NOMINATIM_HEADERS,
                })
                if result and isinstance(result, list):
                    return {"lng": float(result[0]["lon"]), "lat": float(result[0]["lat"])}
            except Exception:
                pass
            time.sleep(1.1)
        return None

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
