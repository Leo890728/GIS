"""Primitive request-payload validators shared across the VRP package."""


def _as_dict(value, field_name):
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be an object")
    return value


def _as_string(value, field_name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} is required")
    return value.strip()


def _as_bool(value, default=False):
    if value is None:
        return default
    return value is True


def _as_int(value, field_name, minimum=None, default=None):
    if value is None:
        if default is not None:
            return default
        raise ValueError(f"{field_name} is required")
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be an integer")
    if minimum is not None and parsed < minimum:
        raise ValueError(f"{field_name} must be >= {minimum}")
    return parsed


def _as_float(value, field_name, minimum=None, default=None):
    if value is None:
        if default is not None:
            return default
        raise ValueError(f"{field_name} is required")
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a number")
    if minimum is not None and parsed < minimum:
        raise ValueError(f"{field_name} must be >= {minimum}")
    return parsed


def _parse_coord(value, field_name):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{field_name} must be [lng, lat]")
    lng = _as_float(value[0], f"{field_name}[0]")
    lat = _as_float(value[1], f"{field_name}[1]")
    if not -180 <= lng <= 180:
        raise ValueError(f"{field_name}[0] must be a valid longitude")
    if not -90 <= lat <= 90:
        raise ValueError(f"{field_name}[1] must be a valid latitude")
    return [lng, lat]
