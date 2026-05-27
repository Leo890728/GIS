class BaseDataSourceAdapter:
    def fetch_payload(self, fetcher, source):
        request_data = self.build_request(source)
        return fetcher(request_data)

    def build_request(self, source):
        return {
            "url": source["url"],
            "method": source.get("method", "GET"),
            "headers": source.get("headers") or {},
            "body": source.get("body"),
        }

    def extract_rows(self, payload, source):
        rows_path = source.get("rows_path")
        if rows_path:
            value = payload
            for key in rows_path:
                if not isinstance(value, dict):
                    raise ValueError("rows_path is invalid for payload")
                value = value.get(key)
            if isinstance(value, list):
                return value
            raise ValueError("rows_path does not point to an array")

        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("data", "rows", "items", "result", "results"):
                value = payload.get(key)
                if isinstance(value, list):
                    return value
        raise ValueError("Unsupported dataset payload format")
