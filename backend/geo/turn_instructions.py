"""將 OSRM 路線的轉彎資訊轉為人類可讀（繁體中文）的逐步導航指示。

OSRM 標準的 ``osrm-routed`` 只回傳結構化的 ``maneuver``（type / modifier /
bearing）與道路名稱 ``name``，並不會產生「在中山路左轉」這種完整句子。本模組
負責把 ``steps=true`` 取回的每個 step 組成繁體中文的一句話。

主要入口：

* :func:`step_to_instruction` —— 純函式，單一 step -> 一句指示；不需連線 OSRM，
  方便測試。
* :func:`route_instructions` —— 呼叫 OSRM 取得 ``steps=true`` 的路線，回傳整段
  路線攤平後的指示清單（含距離、道路名、maneuver 原始欄位）。
"""

from backend.geo.osrm import DEFAULT_TIMEOUT_SECONDS, fetch_route

# maneuver.modifier -> 轉向中文（含車道方向）
_MODIFIER_ZH = {
    "uturn": "迴轉",
    "sharp right": "向右急轉",
    "right": "右轉",
    "slight right": "靠右",
    "straight": "直行",
    "slight left": "靠左",
    "left": "左轉",
    "sharp left": "向左急轉",
}


def _road_phrase(name, prefix):
    """``prefix`` + 道路名，道路名為空時退回只有動作的說法。"""
    name = (name or "").strip()
    return f"{prefix}進入{name}" if name else prefix


def step_to_instruction(step):
    """把單一 OSRM step 轉成一句繁體中文指示。

    ``step`` 需來自 ``steps=true`` 的 ``/route`` 回應。無法辨識的 maneuver 會退回
    一個保守但不會出錯的說法（例如「繼續直行」）。
    """
    maneuver = step.get("maneuver") or {}
    m_type = maneuver.get("type") or ""
    modifier = maneuver.get("modifier") or ""
    name = (step.get("name") or "").strip()
    turn_zh = _MODIFIER_ZH.get(modifier, "")

    if m_type == "depart":
        return f"從{name}出發" if name else "出發"
    if m_type == "arrive":
        side = {"left": "左", "right": "右"}.get(modifier)
        return f"抵達目的地（在{side}側）" if side else "抵達目的地"
    if m_type in ("turn", "end of road"):
        prefix = turn_zh or "轉彎"
        return _road_phrase(name, prefix)
    if m_type in ("new name", "continue"):
        if modifier and modifier != "straight" and turn_zh:
            return _road_phrase(name, turn_zh)
        return f"繼續直行沿{name}" if name else "繼續直行"
    if m_type == "merge":
        return _road_phrase(name, "匯入")
    if m_type == "on ramp":
        return _road_phrase(name, "上匝道")
    if m_type == "off ramp":
        return _road_phrase(name, "下匝道")
    if m_type == "fork":
        prefix = f"在分岔路{turn_zh}" if turn_zh else "在分岔路口沿主線"
        return _road_phrase(name, prefix)
    if m_type in ("roundabout", "rotary"):
        exit_no = maneuver.get("exit")
        exit_zh = f"從第{exit_no}個出口離開" if exit_no else "離開"
        return _road_phrase(name, f"進入圓環後{exit_zh}")
    if m_type in ("exit roundabout", "exit rotary"):
        return _road_phrase(name, "離開圓環")
    if m_type == "roundabout turn":
        prefix = turn_zh or "通過圓環"
        return _road_phrase(name, prefix)

    # 未知 maneuver：盡量給出方向，否則保守直行。
    if turn_zh and turn_zh != "直行":
        return _road_phrase(name, turn_zh)
    return f"繼續直行沿{name}" if name else "繼續直行"


def leg_instructions(leg):
    """攤平單一 leg 的每個 step 為指示 dict。

    ``leg`` 需來自 ``steps=true`` 的 ``/route`` 回應。每個元素含 ``text``（人類可讀
    句子）、``name``、``distance_m``、``type``、``modifier`` 與 ``location``。
    """
    items = []
    for step in leg.get("steps") or []:
        maneuver = step.get("maneuver") or {}
        distance = step.get("distance")
        items.append(
            {
                "text": step_to_instruction(step),
                "name": (step.get("name") or "").strip(),
                "distance_m": float(distance) if isinstance(distance, (int, float)) else 0.0,
                "type": maneuver.get("type") or "",
                "modifier": maneuver.get("modifier") or "",
                "location": maneuver.get("location"),
            }
        )
    return items


def route_instructions(
    base_url,
    profile,
    coordinates,
    *,
    timeout=DEFAULT_TIMEOUT_SECONDS,
):
    """取得 ``coordinates`` 路線的逐步（繁中）導航指示。

    以 ``steps=true`` 呼叫一次 OSRM ``/route``，把所有 leg 的 step 攤平成一個清單，
    每個元素含 ``text``（人類可讀句子）、``name``、``distance_m``、``type``、
    ``modifier`` 與 ``location``。
    """
    if len(coordinates) < 2:
        raise RuntimeError("route_instructions requires at least two coordinates")

    _coords, legs = fetch_route(base_url, profile, coordinates, steps=True, timeout=timeout)
    instructions = []
    for leg in legs:
        instructions.extend(leg_instructions(leg))
    return instructions
