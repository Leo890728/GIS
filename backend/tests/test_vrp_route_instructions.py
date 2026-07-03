import unittest
from unittest import mock

from backend.services.vrp import solver as solver_module
from backend.services.vrp.config import _SolveConfig
from backend.services.vrp.solver import _solve_vrp


def _config():
    return _SolveConfig(
        vehicle_count=1,
        capacity_kg=1000,
        time_limit_sec=1,
        random_seed=1,
        metric="duration",
        profile="driving",
        osrm_base_url="http://osrm",
        route_max_waypoints_per_call=100,
        route_max_url_length=7800,
        disposal_visit_cost=0,
        disposal_max_candidates=1,
        aggregate_enabled=False,
        aggregate_cell_meters=500.0,
        aggregate_threshold=500,
        snap_to_road_enabled=False,
        snap_to_road_max_distance_m=200.0,
    )


def _fake_route_geometry(coordinates, **_kwargs):
    """One leg per consecutive stop pair; each leg is a single left turn.

    Mirrors the OSRM ``steps=true`` shape closely enough for the solver's
    per-leg instruction attachment.
    """
    legs = []
    for i in range(len(coordinates) - 1):
        legs.append(
            {
                "distance": 100.0,
                "duration": 60.0,
                "steps": [
                    {
                        "name": f"路{i}",
                        "distance": 100.0,
                        "maneuver": {"type": "turn", "modifier": "left", "location": list(coordinates[i])},
                    }
                ],
            }
        )
    geometry = {"type": "LineString", "coordinates": [list(c) for c in coordinates]}
    return geometry, legs


class VrpRouteInstructionsTestCase(unittest.TestCase):
    def test_instructions_attached_per_stop(self):
        # 0=start depot, 1=pickup, 2=disposal, 3=end depot
        nodes = [
            {"id": "depot-start", "type": "depot", "name": "Start", "lng": 120.0, "lat": 24.0, "demand_int": 0},
            {"id": "p1", "type": "pickup", "name": "P1", "lng": 120.01, "lat": 24.0, "demand_int": 10, "member_count": 1},
            {"id": "d1", "type": "disposal", "name": "D1", "lng": 120.02, "lat": 24.0, "demand_int": -1000},
            {"id": "depot-end", "type": "depot", "name": "End", "lng": 120.03, "lat": 24.0, "demand_int": 0},
        ]
        size = len(nodes)
        # Costs increasing with index so PATH_CHEAPEST_ARC walks 0->1->2->3.
        matrix = [[abs(i - j) * 100 for j in range(size)] for i in range(size)]

        with mock.patch.object(solver_module, "_build_route_geometry_from_osrm", side_effect=_fake_route_geometry):
            result = _solve_vrp(
                nodes=nodes,
                pickup_indices=[1],
                disposal_indices=[2],
                start_node_index=0,
                end_node_index=3,
                config=_config(),
                duration_matrix=matrix,
                distance_matrix=matrix,
            )

        self.assertEqual(1, len(result["routes"]))
        stops = result["routes"][0]["stops"]
        # First stop (depot start) has no inbound leg -> empty instructions.
        self.assertEqual([], stops[0]["instructions"])
        # Every later stop carries the left-turn instruction from its inbound leg.
        for stop in stops[1:]:
            self.assertTrue(stop["instructions"])
            self.assertTrue(stop["instructions"][0]["text"].startswith("左轉進入路"))
            self.assertEqual("left", stop["instructions"][0]["modifier"])


if __name__ == "__main__":
    unittest.main()
