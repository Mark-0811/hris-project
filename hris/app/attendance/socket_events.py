from flask_socketio import emit

from .services import process_employee_punch, serialize_record


def register_socket_handlers(socketio):
    @socketio.on("connect", namespace="/attendance-live")
    def attendance_live_connect():
        return True

    @socketio.on("attendance_punch", namespace="/kiosk")
    def attendance_punch(data):
        identifier = (data or {}).get("identifier", "").strip()
        source = (data or {}).get("source", "manual")
        action = (data or {}).get("action", "auto")
        if not identifier:
            emit(
                "punch_result",
                {"ok": False, "message": "Employee ID, badge ID, or NFC UID is required."},
            )
            return

        record, message = process_employee_punch(identifier, source, action)
        if record is None:
            emit("punch_result", {"ok": False, "message": message})
            return

        emit(
            "punch_result",
            {
                "ok": True,
                "message": message,
                "record": serialize_record(record),
            },
        )
        socketio.emit(
            "attendance_updated",
            {
                "employee_id": record.employee_id,
                "record": serialize_record(record),
                "message": message,
            },
            namespace="/attendance-live",
        )
