from uuid import uuid4

from flask import jsonify, request


def api_response(status: str, message: str, data=None, errors=None, http_status: int = 200):
    trace_id = request.headers.get("X-Trace-Id") or uuid4().hex
    payload = {
        "status": status,
        "message": message,
        "data": data,
        "errors": errors or [],
        "trace_id": trace_id,
    }
    return jsonify(payload), http_status
