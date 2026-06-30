import unittest

from backend.services.regions_presentation import (
    assemble_regions_tree,
    range_feature_from_row,
    regions_tree_to_ranges,
    stat_zone_point_feature_from_row,
    stat_zone_rows_to_range_nodes,
)


class AssembleRegionsTreeTestCase(unittest.TestCase):
    def _rows(self):
        county_rows = [
            {"countyid": "C1", "countycode": "10", "countyname": "County A", "countyeng": "A"},
        ]
        township_rows = [
            {"townid": "T1", "towncode": "1001", "countycode": "10", "townname": "Town A", "towneng": "TA"},
            {"townid": "T9", "towncode": "9999", "countycode": "NOPE", "townname": "Orphan", "towneng": "O"},
        ]
        village_rows = [
            {"villcode": "V1", "countycode": "10", "towncode": "1001", "villname": "Vil A", "villeng": "VA"},
            {"villcode": "V9", "countycode": "10", "towncode": "NOPE", "villname": "Orphan", "villeng": "O"},
        ]
        sz_count_rows = [{"villcode": "V1", "cnt": 7}]
        return county_rows, township_rows, village_rows, sz_count_rows

    def test_nests_counties_townships_villages(self):
        tree = assemble_regions_tree(*self._rows())
        self.assertEqual(1, len(tree["counties"]))
        county = tree["counties"][0]
        self.assertEqual("County A", county["countyName"])
        self.assertEqual(1, len(county["townships"]))  # orphan township skipped
        village = county["townships"][0]["villages"][0]
        self.assertEqual("V1", village["villageCode"])
        self.assertEqual(7, village["statZoneCount"])  # from sz_count map

    def test_summary_counts_only_attached_nodes(self):
        tree = assemble_regions_tree(*self._rows())
        self.assertEqual({"countyCount": 1, "townshipCount": 1, "villageCount": 1}, tree["summary"])

    def test_missing_stat_zone_count_defaults_to_zero(self):
        county_rows, township_rows, village_rows, _ = self._rows()
        tree = assemble_regions_tree(county_rows, township_rows, village_rows, [])
        self.assertEqual(0, tree["counties"][0]["townships"][0]["villages"][0]["statZoneCount"])


class RegionsTreeToRangesTestCase(unittest.TestCase):
    def test_builds_nested_selectable_nodes(self):
        regions = {
            "counties": [
                {
                    "countyCode": "10",
                    "countyName": "County A",
                    "countyEng": "A",
                    "townships": [
                        {
                            "townCode": "1001",
                            "townName": "Town A",
                            "townEng": "TA",
                            "villages": [
                                {"villageCode": "V1", "villageName": "Vil A", "villageEng": "VA", "statZoneCount": 3}
                            ],
                        }
                    ],
                }
            ],
            "summary": {"countyCount": 1, "townshipCount": 1, "villageCount": 1},
        }
        result = regions_tree_to_ranges(regions)
        county = result["ranges"][0]
        self.assertEqual("county-10", county["id"])
        township = county["children"][0]
        self.assertEqual("township-1001", township["id"])
        village = township["children"][0]
        self.assertEqual("village-V1", village["id"])
        self.assertEqual(3, village["metadata"]["statZoneCount"])
        self.assertEqual(regions["summary"], result["summary"])

    def test_skips_nodes_without_codes(self):
        regions = {
            "counties": [{"countyCode": "", "townships": []}],
            "summary": {},
        }
        self.assertEqual([], regions_tree_to_ranges(regions)["ranges"])


class StatZoneRangeNodesTestCase(unittest.TestCase):
    def test_formats_population_text(self):
        nodes = stat_zone_rows_to_range_nodes([{"codebase": "A0001", "p_cnt": 12345}], "#abc", "V1")
        self.assertEqual("stat_zone-A0001", nodes[0]["id"])
        self.assertEqual("Population 12,345", nodes[0]["description"])
        self.assertEqual("V1", nodes[0]["metadata"]["parentVillageCode"])

    def test_handles_missing_population(self):
        nodes = stat_zone_rows_to_range_nodes([{"codebase": "A0001", "p_cnt": None}], "#abc", "V1")
        self.assertEqual("", nodes[0]["description"])


class RangeFeatureFromRowTestCase(unittest.TestCase):
    def test_returns_none_without_geometry(self):
        row = {"countycode": "10", "_geom": None}
        self.assertIsNone(range_feature_from_row(row, "county", "countycode", "#fff"))

    def test_builds_feature_with_range_props_and_drops_geometry_columns(self):
        row = {"countycode": "10", "countyname": "A", "GEOMETRY": b"blob", "_geom": '{"type":"Point","coordinates":[1,2]}'}
        feature = range_feature_from_row(row, "county", "countycode", "#7fb3ff")
        self.assertEqual({"type": "Point", "coordinates": [1, 2]}, feature["geometry"])
        props = feature["properties"]
        self.assertNotIn("GEOMETRY", props)
        self.assertNotIn("_geom", props)
        self.assertEqual("county:10", props["rangeId"])
        self.assertEqual("#7fb3ff", props["rangeColor"])
        self.assertEqual("county", props["rangeLevel"])
        self.assertEqual("A", props["countyname"])


class StatZonePointFeatureTestCase(unittest.TestCase):
    def test_maps_row_to_point_feature(self):
        row = {
            "codebase": "A0001",
            "villcode": "V1",
            "county_id": "10",
            "town_id": "1001",
            "p_cnt": 50,
            "lng": 120.5,
            "lat": 24.1,
        }
        feature = stat_zone_point_feature_from_row(row)
        self.assertEqual("A0001", feature["id"])
        self.assertEqual([120.5, 24.1], feature["geometry"]["coordinates"])
        self.assertEqual("V1", feature["properties"]["VILLAGE_CODE"])
        self.assertEqual(50, feature["properties"]["P_CNT"])


if __name__ == "__main__":
    unittest.main()
