"""Assembly of the public ``solve_garbage_vrp`` response payload."""


def _build_response(
    solved,
    pickup_nodes,
    aggregated,
    disposal_nodes,
    raw_node_count,
    snapped_node_count,
    aggregated_node_count,
    start_coord=None,
    end_coord=None,
):
    total_demand_kg = int(round(sum(node["demand_kg"] for node in pickup_nodes)))
    dropped_demand_kg = int(round(sum(node.get("demand_kg", 0) for node in solved["dropped_nodes"])))
    served_demand_kg = max(0, total_demand_kg - dropped_demand_kg)

    return {
        "status": "success",
        "depot": {
            "start": list(start_coord) if start_coord else None,
            "end": list(end_coord) if end_coord else None,
        },
        "summary": {
            "totalDistanceM": solved["total_distance"],
            "totalDurationS": solved["total_duration"],
            "totalDemandKg": total_demand_kg,
            "servedDemandKg": served_demand_kg,
            "droppedDemandKg": dropped_demand_kg,
            "vehicleUsed": len(solved["routes"]),
            "aggregated": aggregated,
            "geometryFallbackRouteCount": int(solved.get("geometry_fallback_route_count", 0)),
        },
        "routes": solved["routes"],
        "droppedNodes": [
            {
                "id": node["id"],
                "name": node.get("name", node["id"]),
                "lng": node["lng"],
                "lat": node["lat"],
                "demandKg": int(round(node.get("demand_kg", 0))),
                "memberCount": int(node.get("member_count", 1)),
            }
            for node in solved["dropped_nodes"]
        ],
        "inputStats": {
            "rawNodeCount": raw_node_count,
            "snappedNodeCount": snapped_node_count,
            "aggregatedNodeCount": aggregated_node_count,
            "disposalCount": len(disposal_nodes),
        },
    }
