import unittest
from unittest import mock

from backend.geo import turn_instructions
from backend.geo.turn_instructions import (
    leg_instructions,
    route_instructions,
    step_to_instruction,
)


def _step(m_type, modifier=None, name="", exit_no=None, distance=100.0):
    maneuver = {"type": m_type, "location": [120.0, 24.0]}
    if modifier is not None:
        maneuver["modifier"] = modifier
    if exit_no is not None:
        maneuver["exit"] = exit_no
    return {"name": name, "distance": distance, "maneuver": maneuver}


class StepToInstructionTestCase(unittest.TestCase):
    def test_depart_with_and_without_name(self):
        self.assertEqual("從中山路出發", step_to_instruction(_step("depart", name="中山路")))
        self.assertEqual("出發", step_to_instruction(_step("depart", name="")))

    def test_turn_uses_modifier_and_name(self):
        self.assertEqual("左轉進入民權路", step_to_instruction(_step("turn", "left", "民權路")))
        self.assertEqual("右轉進入民權路", step_to_instruction(_step("turn", "right", "民權路")))
        self.assertEqual("靠右進入民權路", step_to_instruction(_step("turn", "slight right", "民權路")))

    def test_turn_without_road_name_falls_back_to_action_only(self):
        self.assertEqual("左轉", step_to_instruction(_step("turn", "left", "")))

    def test_arrive_with_side(self):
        self.assertEqual("抵達目的地", step_to_instruction(_step("arrive")))
        self.assertEqual(
            "抵達目的地（在右側）", step_to_instruction(_step("arrive", "right"))
        )

    def test_continue_and_new_name_are_straight(self):
        self.assertEqual("繼續直行沿文心路", step_to_instruction(_step("continue", "straight", "文心路")))
        self.assertEqual("繼續直行沿文心路", step_to_instruction(_step("new name", "straight", "文心路")))

    def test_roundabout_exit(self):
        self.assertEqual(
            "進入圓環後從第2個出口離開進入自由路",
            step_to_instruction(_step("roundabout", exit_no=2, name="自由路")),
        )

    def test_ramps_and_merge(self):
        self.assertEqual("上匝道進入國道一號", step_to_instruction(_step("on ramp", name="國道一號")))
        self.assertEqual("下匝道", step_to_instruction(_step("off ramp", name="")))
        self.assertEqual("匯入進入國道三號", step_to_instruction(_step("merge", name="國道三號")))

    def test_unknown_maneuver_is_safe(self):
        self.assertEqual("繼續直行", step_to_instruction(_step("notification")))
        self.assertEqual("繼續直行沿A路", step_to_instruction(_step("notification", name="A路")))

    def test_missing_maneuver_object(self):
        self.assertEqual("繼續直行", step_to_instruction({"name": ""}))


class RouteInstructionsTestCase(unittest.TestCase):
    def test_flattens_legs_and_extracts_fields(self):
        legs = [
            {"steps": [_step("depart", name="A路", distance=50.0), _step("turn", "left", "B路", distance=120.0)]},
            {"steps": [_step("arrive", distance=0.0)]},
        ]
        with mock.patch.object(
            turn_instructions, "fetch_route", return_value=([], legs)
        ) as fetched:
            result = route_instructions("http://osrm", "driving", [[120.0, 24.0], [120.1, 24.1]])

        fetched.assert_called_once()
        # steps=True 必須被帶入，否則不會有 maneuver 可用
        self.assertTrue(fetched.call_args.kwargs.get("steps"))
        self.assertEqual(["從A路出發", "左轉進入B路", "抵達目的地"], [i["text"] for i in result])
        self.assertEqual(120.0, result[1]["distance_m"])
        self.assertEqual("left", result[1]["modifier"])

    def test_requires_two_coordinates(self):
        with self.assertRaises(RuntimeError):
            route_instructions("http://osrm", "driving", [[120.0, 24.0]])


if __name__ == "__main__":
    unittest.main()
