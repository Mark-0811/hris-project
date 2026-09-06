from flask import abort, jsonify, render_template, request
from flask_login import current_user, login_required

from . import bp
from .services import (
    can_access_thread,
    get_thread_for_user,
    list_messages,
    list_threads_for_user,
    mark_thread_read,
    maybe_generate_ai_reply,
    send_message,
    serialize_message,
)
from ..extensions import socketio


@bp.route("/", defaults={"thread_id": None})
@bp.route("/<int:thread_id>")
@login_required
def index(thread_id: int | None = None):
    threads = list_threads_for_user(current_user)
    active_thread = get_thread_for_user(current_user, thread_id)
    if thread_id and not can_access_thread(current_user, active_thread):
        abort(403)
    if active_thread and not can_access_thread(current_user, active_thread):
        active_thread = None

    mark_thread_read(active_thread, current_user)
    return render_template(
        "chat/index.html",
        threads=threads,
        active_thread=active_thread,
        messages=list_messages(active_thread),
    )


@bp.route("/send", methods=["POST"])
@login_required
def send_attachment_message():
    thread_id = request.form.get("thread_id", type=int)
    body = request.form.get("body", "")
    attachment = request.files.get("attachment")
    thread = get_thread_for_user(current_user, thread_id)
    if not can_access_thread(current_user, thread):
        abort(403)
    try:
        message, moderation = send_message(thread, current_user, body, attachment=attachment)
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400

    payload = {"thread_id": thread.id, "message": serialize_message(message)}
    socketio.emit("chat_message", payload, namespace="/chat", room=f"chat_thread_{thread.id}")
    ai_message = maybe_generate_ai_reply(thread, current_user, body)
    if ai_message:
        socketio.emit(
            "chat_message",
            {"thread_id": thread.id, "message": serialize_message(ai_message)},
            namespace="/chat",
            room=f"chat_thread_{thread.id}",
        )
    response = {"thread_id": thread.id, "message": serialize_message(message)}
    if moderation.get("contains_foul_language"):
        response["warning"] = "Foul language was detected in your message. This has been reported to your manager."
    return jsonify(response), 201
