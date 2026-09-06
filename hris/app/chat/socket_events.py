from flask_login import current_user
from flask_socketio import emit, join_room

from .services import can_access_thread, get_thread_for_user, maybe_generate_ai_reply, send_message, serialize_message


def register_chat_socket_handlers(socketio):
    @socketio.on("join_chat_thread", namespace="/chat")
    def join_chat_thread(data):
        thread_id = (data or {}).get("thread_id")
        thread = get_thread_for_user(current_user, thread_id)
        if not can_access_thread(current_user, thread):
            emit("chat_error", {"message": "You cannot access this chat thread."})
            return
        join_room(f"chat_thread_{thread.id}")
        emit("chat_joined", {"thread_id": thread.id})

    @socketio.on("chat_message", namespace="/chat")
    def chat_message(data):
        thread_id = (data or {}).get("thread_id")
        body = (data or {}).get("body", "")
        thread = get_thread_for_user(current_user, thread_id)
        if not can_access_thread(current_user, thread):
            emit("chat_error", {"message": "You cannot send to this chat thread."})
            return
        try:
            message, moderation = send_message(thread, current_user, body)
        except ValueError as exc:
            emit("chat_error", {"message": str(exc)})
            return

        socketio.emit(
            "chat_message",
            {"thread_id": thread.id, "message": serialize_message(message)},
            namespace="/chat",
            room=f"chat_thread_{thread.id}",
        )
        ai_message = maybe_generate_ai_reply(thread, current_user, body)
        if ai_message:
            socketio.emit(
                "chat_message",
                {"thread_id": thread.id, "message": serialize_message(ai_message)},
                namespace="/chat",
                room=f"chat_thread_{thread.id}",
            )
        if moderation.get("contains_foul_language"):
            emit(
                "chat_warning",
                {
                    "message": "Foul language was detected in your message. This has been reported to your manager.",
                },
            )
