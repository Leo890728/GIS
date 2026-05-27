import json
from urllib import request


BASE_URL = "http://127.0.0.1:5000"


def call_json(path, method="GET", payload=None):
    body = None
    headers = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = request.Request(f"{BASE_URL}{path}", data=body, method=method, headers=headers)
    with request.urlopen(req) as response:
        data = response.read().decode("utf-8")
        return response.status, json.loads(data)


def main():
    status, health = call_json("/health")
    assert status == 200 and health.get("ok") is True

    inline = {
        "data": {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "id": "smoke-1",
                    "geometry": {"type": "Point", "coordinates": [121.5, 25.03]},
                    "properties": {"lineid": "smoke", "SpeedValue": 1, "OverSpeed": 1},
                }
            ],
        },
        "filters": {"OverSpeed": 1},
    }
    status, queried = call_json("/data/query", "POST", inline)
    assert status == 200 and queried.get("type") == "FeatureCollection"

    status, aggregate = call_json("/data/aggregate", "POST", {"metrics": ["count"], **inline})
    assert status == 200 and "count" in aggregate

    status, ranges = call_json("/ranges/tree")
    assert status == 200 and "ranges" in ranges and "summary" in ranges

    tile_req = request.Request(f"{BASE_URL}/tiles/__missing__/0/0/0.pbf", method="GET")
    try:
        request.urlopen(tile_req)
        raise AssertionError("tiles smoke check expected 404 for missing dataset")
    except Exception as err:
        if getattr(err, "code", None) != 404:
            raise

    print("smoke check passed")


if __name__ == "__main__":
    main()
