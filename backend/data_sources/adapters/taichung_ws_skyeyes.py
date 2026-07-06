import json

from backend.data_sources.base import BaseDataSourceAdapter


class TaichungWsSkyeyesAdapter(BaseDataSourceAdapter):
    DEFAULT_BOOTSTRAP_URLS = [
        "https://cleaner.epb.taichung.gov.tw/index.aspx",
        "https://cleaner.epb.taichung.gov.tw/system_index.aspx",
    ]

    DEFAULT_HEADERS = {
        "accept": "*/*",
        "accept-language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "content-type": "application/json; charset=UTF-8",
        "x-requested-with": "XMLHttpRequest",
        "origin": "https://cleaner.epb.taichung.gov.tw",
        "referer": "https://cleaner.epb.taichung.gov.tw/index.aspx",
        "dnt": "1",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
    }

    def _bootstrap_urls(self, source):
        configured = source.get("bootstrap_urls")
        urls = []
        if isinstance(configured, list) and configured:
            urls.extend(configured)
        elif source.get("bootstrap_url"):
            urls.append(source.get("bootstrap_url"))
        urls.extend(self.DEFAULT_BOOTSTRAP_URLS)
        urls = [url for url in urls if isinstance(url, str) and url.strip()]
        seen = set()
        deduped = []
        for url in urls:
            if url in seen:
                continue
            seen.add(url)
            deduped.append(url)
        return deduped

    def _bootstrap_headers(self, source):
        headers = {"accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
        headers.update(source.get("bootstrap_headers") or {})
        headers.setdefault("user-agent", self.DEFAULT_HEADERS["user-agent"])
        headers.setdefault("accept-language", self.DEFAULT_HEADERS["accept-language"])
        headers.setdefault("referer", "https://cleaner.epb.taichung.gov.tw/")
        return headers

    def fetch_payload(self, fetcher, source):
        retries = max(1, int(source.get("retries", 2)))

        # 先用現有 session(cookie 保存在共用的 http client)直接打資料端點,
        # session 未過期時就不必重新打 bootstrap URL。
        try:
            return fetcher(self.build_request(source))
        except Exception as err:  # pragma: no cover
            last_error = err

        # 直接請求失敗(session 過期 / 尚未建立 cookie)才 bootstrap 重建 session。
        for bootstrap_url in self._bootstrap_urls(source):
            for _ in range(retries):
                try:
                    bootstrap_request = {
                        "url": bootstrap_url,
                        "method": "GET",
                        "headers": self._bootstrap_headers(source),
                        "body": None,
                        "expect_json": False,
                    }
                    fetcher(bootstrap_request)
                    return fetcher(self.build_request(source))
                except Exception as err:  # pragma: no cover
                    last_error = err
                    continue
        raise last_error

    def build_request(self, source):
        request_data = super().build_request(source)
        request_data["method"] = source.get("method", "POST")
        headers = dict(self.DEFAULT_HEADERS)
        headers.update(request_data["headers"])
        request_data["headers"] = headers
        request_data["body"] = source.get("body", "")
        return request_data

    def extract_rows(self, payload, source):
        if isinstance(payload, dict):
            d_value = payload.get("d")
            if isinstance(d_value, str):
                try:
                    parsed = json.loads(d_value)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, dict):
                    payload = dict(payload)
                    payload["d"] = parsed

        source_with_default_path = dict(source)
        source_with_default_path.setdefault("rows_path", ["d", "DATA"])
        return super().extract_rows(payload, source_with_default_path)
