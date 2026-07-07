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
    # Optional repeatable `key` narrows the build to those entities, so a
    # single-track request doesn't OSRM-route the whole dataset.
    keys = [k for k in request.args.getlist("key") if k] or None
    try:
        tracks = service.history_tracks(data_id, frm, to, keys=keys)
    except KeyError as err:
        abort(404, description=str(err))
    return {
        "dataId": data_id,
        "from": iso_utc(frm),
        "to": iso_utc(to),
        "tracks": tracks,
    }


def _sse(event, payload):
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


@bp.get("/data/history/<data_id>/track/stream")
def history_track_stream(data_id):
    """Same payload as /track, but streamed as Server-Sent Events.

    Emits `progress` events ({done, total}) as each entity's road-following
    track is built, then one `track` event per entity, then a final `result`
    event with the metadata (or an `error` event). Streaming each entity
    separately keeps the peak memory bounded to one entity's JSON — a single
    result event for a large dataset (tens of MB) piled a giant string on top
    of the track dicts and got the worker OOM-killed.
    """
    service = _service()
    frm = _parse_param("from")
    to = _parse_param("to")

    # Bounded so the worker thread cannot pile every serialized track into the
    # queue faster than the client drains it; `cancelled` unblocks the worker
    # when the client disconnects mid-stream.
    events = queue.Queue(maxsize=8)
    cancelled = threading.Event()
    done = object()

    def put_event(item):
        while not cancelled.is_set():
            try:
                events.put(item, timeout=1)
                return True
            except queue.Full:
                continue
        return False

    def on_progress(built, total):
        put_event(_sse("progress", {"done": built, "total": total}))

    def worker():
        try:
            tracks = service.history_tracks(data_id, frm, to, progress_cb=on_progress)
            # pop() releases each track (dict + serialized string) as soon as
            # the generator has flushed it to the client.
            while tracks:
                if not put_event(_sse("track", tracks.pop())):
                    return
            put_event(
                _sse(
                    "result",
                    {
                        "dataId": data_id,
                        "from": iso_utc(frm),
                        "to": iso_utc(to),
                    },
                )
            )
        except KeyError as err:
            put_event(_sse("error", {"message": str(err)}))
        except Exception:  # pragma: no cover - defensive: surface failure to client
            put_event(_sse("error", {"message": "Failed to build tracks"}))
        finally:
            put_event(done)

    @stream_with_context
    def generate():
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        try:
            while True:
                item = events.get()
                if item is done:
                    break
                yield item
        finally:
            cancelled.set()

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
