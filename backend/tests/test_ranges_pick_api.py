import unittest

from backend.app import create_app


class FakeRegionsService:
    def __init__(self, response=None, error=None):
        self.calls = []
        self.response = response or {"hit": True, "level": "township", "code": "T001", "name": "Demo"}
        self.error = error

    def pick_range_by_point(self, lng, lat, level):
        self.calls.append((lng, lat, level))
        if self.error:
            raise self.error
        return self.response


class RangePickApiTestCase(unittest.TestCase):
    def make_client(self, regions_service):
        app = create_app(
            {
                "TESTING": True,
                "REGIONS_SERVICE": regions_service,
                "DATASET_SERVICE": object(),
            }
        )
        return app.test_client()

    def test_range_pick_forwards_point_to_regions_service(self):
        service = FakeRegionsService()
        client = self.make_client(service)

        response = client.post(
            "/regions/pick",
            json={"level": "township", "lng": 120.6512349, "lat": 24.1478901},
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            {"hit": True, "level": "township", "code": "T001", "name": "Demo"},
            response.get_json(),
        )
        self.assertEqual([(120.6512349, 24.1478901, "township")], service.calls)

    def test_range_pick_rejects_invalid_coordinates(self):
        service = FakeRegionsService()
        client = self.make_client(service)

        response = client.post("/regions/pick", json={"level": "township", "lng": "x", "lat": 24})

        self.assertEqual(400, response.status_code)
        self.assertEqual([], service.calls)

    def test_range_pick_rejects_service_level_error(self):
        service = FakeRegionsService(error=ValueError("unsupported range pick level: nope"))
        client = self.make_client(service)

        response = client.post("/regions/pick", json={"level": "nope", "lng": 120, "lat": 24})

        self.assertEqual(400, response.status_code)
        self.assertEqual([(120.0, 24.0, "nope")], service.calls)


if __name__ == "__main__":
    unittest.main()
