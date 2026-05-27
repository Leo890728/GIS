from backend.schemas.data_points import is_number


def aggregate_features(features, metrics):
    result = {"count": len(features), "sum": {}, "avg": {}}

    for metric in metrics:
        if metric == "count":
            continue
        if not isinstance(metric, str) or ":" not in metric:
            raise ValueError(f"Unsupported metric: {metric}")

        operation, field = metric.split(":", 1)
        if not field:
            raise ValueError(f"Metric field is required: {metric}")

        values = [
            feature.get("properties", {}).get(field)
            for feature in features
            if is_number(feature.get("properties", {}).get(field))
        ]

        if operation == "sum":
            result["sum"][field] = sum(values)
        elif operation == "avg":
            result["avg"][field] = sum(values) / len(values) if values else None
        else:
            raise ValueError(f"Unsupported metric operation: {operation}")

    if not result["sum"]:
        result.pop("sum")
    if not result["avg"]:
        result.pop("avg")
    return result


def aggregate_grouped(features, metrics, group_by):
    result = aggregate_features(features, metrics)
    if not group_by:
        return result

    groups = {}
    for feature in features:
        group_value = feature.get("properties", {}).get(group_by)
        group_key = str(group_value) if group_value not in (None, "") else "__ungrouped__"
        groups.setdefault(group_key, []).append(feature)

    result["groups"] = {
        group_key: aggregate_features(group_features, metrics)
        for group_key, group_features in groups.items()
    }
    return result
