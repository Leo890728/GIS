import json
import queue
import threading

from flask import Blueprint, Response, abort, current_app, request, stream_with_context

from backend.schemas.data_points import parse_timestamp
from backend.services.dataset_service import iso_utc
from backend.services.point_query import feature_collection


bp = Blueprint("history_api", __name__)


def _service():
    return current_app.config["DATASET_SERVICE"]


def _parse_param(name, required=False):
    raw = request.args.get(name)
    if raw is None or raw == "":
        if required:
            abort(400, description=f"Query param '{name}' is required")
        return None
    parsed = parse_timestamp(raw)
    if parsed is None:
        abort(400, description=f"Query param '{name}' must be an ISO8601 timestamp")
    return parsed


@bp.get("/data/history/<data_id>/range")
def history_range(data_id):
    service = _service()
    try:
        span = service.history_range(data_id)
        interval = service.get_meta(data_id).get("refreshSeconds")
    except KeyError as err:
        abort(404, description=str(err))
    if not span:
        return {"dataId": data_id, "from": None, "to": None, "count": 0, "intervalSeconds": interval}
    return {
        "dataId": data_id,
        "from": iso_utc(span["from"]),
        "to": iso_utc(span["to"]),
        "count": span["count"],
        "intervalSeconds": interval,
    }


@bp.get("/data/history/<data_id>/frames")
def history_frames(data_id):
    service = _service()
    frm = _parse_param("from")
    to = _parse_param("to")
    try:
        frames = service.history_frames(data_id, frm, to)
    except KeyError as err:
        abort(404, description=str(err))
    return {"dataId": data_id, "frames": [iso_utc(t) for t in frames]}


@bp.get("/data/history/<data_id>/at")
def history_at(data_id):
    service = _service()
    t = _parse_param("t", required=True)
    try:
        features = service.history_state_at(data_id, t)
    except KeyError as err:
        abort(404, description=str(err))
    return feature_collection(features)


@bp.get("/data/history/<data_id>/track")
def history_track(data_id):
    service = _service()
    frm = _parse_param("from")
    to = _parse_param("to")
    try:
        tracks = service.history_tracks(data_id, frm, to)
    except KeyError as err:
        abort(404, description=str(err))
    return {
        "dataId": data_id,
        "from": iso_utc(frm),
        "to": iso_utc(to),
        "tracks": tracks,
    }


@bp.get("/data/history/<data_id>/coverage")
def history_coverage(data_id):
    service = _service()
    regions_service = current_app.config.get("REGIONS_SERVICE")
    frm = _parse_param("from")
    to = _parse_param("to")
    try:
        result = service.history_coverage(data_id, frm, to, regions_service=regions_service)
    except KeyError as err:
        abort(404, description=str(err))
    return {"dataId": data_id, "from": iso_utc(frm), "to": iso_utc(to), **result}


def _sse(event, payload):
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


@bp.get("/data/history/<data_id>/track/stream")
def history_track_stream(data_id):
    """Same payload as /track, but streamed as Server-Sent Events.

    Emits `progress` events ({done, total}) as each entity's road-following
    track is built, then a final `result` event carrying the full track payload
    (or an `error` event). Lets the frontend show OSRM smoothing progress.
    """
    service = _service()
    frm = _parse_param("from")
    to = _parse_param("to")

    events = queue.Queue()
    done = object()

    def on_progress(built, total):
        events.put(_sse("progress", {"done": built, "total": total}))

    def worker():
        try:
            tracks = service.history_tracks(data_id, frm, to, progress_cb=on_progress)
            events.put(
                _sse(
                    "result",
                    {
                        "dataId": data_id,
                        "from": iso_utc(frm),
                        "to": iso_utc(to),
                        "tracks": tracks,
                    },
                )
            )
        except KeyError as err:
            events.put(_sse("error", {"message": str(err)}))
        except Exception:  # pragma: no cover - defensive: surface failure to client
            events.put(_sse("error", {"message": "Failed to build tracks"}))
        finally:
            events.put(done)

    @stream_with_context
    def generate():
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        while True:
            item = events.get()
            if item is done:
                break
            yield item

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
