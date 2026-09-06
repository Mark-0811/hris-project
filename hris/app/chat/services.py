import secrets
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

from flask import current_app, url_for
from flask_login import current_user
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import ChatMessage, ChatThread, HrTicket, LeaveRequest, LeaveType, Notification, PayslipDispute, PayrollEntry, Role, User
from ..utils.constants import ROLE_EMPLOYEE, ROLE_HR_ADMIN, ROLE_SUPER_ADMIN

CHAT_ADMIN_ROLES = {ROLE_SUPER_ADMIN, ROLE_HR_ADMIN}
AI_ASSISTANT_USERNAME = "ai_assistant"
FOUL_WORDS = {
    "fuck",
    "fucking",
    "shit",
    "bitch",
    "asshole",
    "puta",
    "gago",
    "tangina",
    "putangina",
}


def is_chat_admin(user) -> bool:
    return bool(
        user
        and getattr(user, "is_authenticated", False)
        and user.role
        and user.role.name in CHAT_ADMIN_ROLES
    )


def can_access_thread(user, thread: ChatThread | None) -> bool:
    if not user or not getattr(user, "is_authenticated", False) or thread is None:
        return False
    if is_chat_admin(user):
        return True
    return bool(user.role and user.role.name == ROLE_EMPLOYEE and thread.employee_user_id == user.id)


def get_or_create_employee_thread(user) -> ChatThread | None:
    if not user or not getattr(user, "is_authenticated", False):
        return None
    if not user.role or user.role.name != ROLE_EMPLOYEE:
        return None
    thread = user.chat_thread
    if thread is None:
        thread = ChatThread(employee_user_id=user.id)
        db.session.add(thread)
        db.session.commit()
    return thread


def list_threads_for_user(user):
    if not user or not getattr(user, "is_authenticated", False):
        return []
    if is_chat_admin(user):
        return ChatThread.query.order_by(ChatThread.updated_at.desc(), ChatThread.id.desc()).all()
    thread = get_or_create_employee_thread(user)
    return [thread] if thread else []


def get_thread_for_user(user, thread_id: int | None = None):
    if is_chat_admin(user):
        if thread_id:
            return db.session.get(ChatThread, thread_id)
        return ChatThread.query.order_by(ChatThread.updated_at.desc(), ChatThread.id.desc()).first()
    return get_or_create_employee_thread(user)


def list_messages(thread: ChatThread | None):
    if thread is None:
        return []
    return thread.messages.order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc()).all()


def mark_thread_read(thread: ChatThread | None, user) -> None:
    if thread is None or not user or not getattr(user, "is_authenticated", False):
        return
    if is_chat_admin(user):
        ChatMessage.query.filter(
            ChatMessage.thread_id == thread.id,
            ChatMessage.sender_id != user.id,
            ChatMessage.is_read_by_admin.is_(False),
        ).update(
            {"is_read_by_admin": True},
            synchronize_session=False,
        )
    else:
        ChatMessage.query.filter(
            ChatMessage.thread_id == thread.id,
            ChatMessage.sender_id != user.id,
            ChatMessage.is_read_by_employee.is_(False),
        ).update(
            {"is_read_by_employee": True},
            synchronize_session=False,
        )
    db.session.commit()


def serialize_message(message: ChatMessage):
    attachment_url = None
    attachment_is_image = False
    if message.attachment_filename:
        attachment_url = url_for("static", filename=f"uploads/chat/{message.attachment_filename}")
        attachment_is_image = bool(message.attachment_mime_type and message.attachment_mime_type.startswith("image/"))
    return {
        "id": message.id,
        "thread_id": message.thread_id,
        "sender_id": message.sender_id,
        "sender_name": message.sender.display_name if message.sender else "Unknown",
        "sender_role": message.sender.role.name if message.sender and message.sender.role else "User",
        "is_ai_assistant": bool(message.sender and message.sender.username == AI_ASSISTANT_USERNAME),
        "body": message.body,
        "attachment_url": attachment_url,
        "attachment_name": message.attachment_original_name,
        "attachment_is_image": attachment_is_image,
        "created_at": message.created_at.isoformat() if message.created_at else None,
        "is_mine": bool(current_user.is_authenticated and message.sender_id == current_user.id),
    }


def normalize_for_moderation(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else " " for char in (value or ""))


def contains_foul_language(value: str) -> bool:
    terms = set(normalize_for_moderation(value).split())
    return any(word in terms for word in FOUL_WORDS)


def get_manager_user_for_sender(sender):
    employee = getattr(sender, "employee", None)
    department = getattr(employee, "department", None)
    manager = getattr(department, "manager", None)
    return manager.user if manager and manager.user and manager.user.is_active else None


def notify_foul_language_report(message: ChatMessage):
    manager_user = get_manager_user_for_sender(message.sender)
    if manager_user:
        db.session.add(
            Notification(
                user_id=manager_user.id,
                title="Foul language report",
                message=f"{message.sender.display_name} sent a flagged chat message: {message.body[:160]}",
                type="chat_report",
                is_read=False,
            )
        )
    db.session.commit()


def save_chat_attachment(file_storage):
    if not file_storage or not getattr(file_storage, "filename", ""):
        return None
    filename = secure_filename(file_storage.filename)
    if not filename:
        return None
    unique_name = f"{secrets.token_hex(8)}_{filename}"
    upload_dir = Path(current_app.static_folder) / "uploads" / "chat"
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_storage.save(upload_dir / unique_name)
    return {
        "filename": unique_name,
        "original_name": filename,
        "mime_type": getattr(file_storage, "mimetype", None),
    }


def send_message(thread: ChatThread, sender, body: str, attachment=None):
    clean_body = (body or "").strip()
    attachment_meta = save_chat_attachment(attachment)
    if not clean_body and not attachment_meta:
        raise ValueError("Message cannot be empty.")

    message = ChatMessage(
        thread_id=thread.id,
        sender_id=sender.id,
        body=clean_body,
        attachment_filename=attachment_meta["filename"] if attachment_meta else None,
        attachment_original_name=attachment_meta["original_name"] if attachment_meta else None,
        attachment_mime_type=attachment_meta["mime_type"] if attachment_meta else None,
        is_read_by_employee=sender.role.name == ROLE_EMPLOYEE,
        is_read_by_admin=is_chat_admin(sender),
    )
    db.session.add(message)
    db.session.commit()
    moderation = {"contains_foul_language": contains_foul_language(clean_body)}
    if moderation["contains_foul_language"]:
        notify_foul_language_report(message)
    return message, moderation


def is_ai_assistant_enabled() -> bool:
    return bool(current_app.config.get("AI_ASSISTANT_ENABLED", False))


def get_ai_assistant_user() -> User | None:
    if not is_ai_assistant_enabled():
        return None

    user = User.query.filter_by(username=AI_ASSISTANT_USERNAME).first()
    if user:
        return user

    role = Role.query.filter_by(name=ROLE_HR_ADMIN).first() or Role.query.filter_by(name=ROLE_SUPER_ADMIN).first()
    if role is None:
        return None

    user = User(
        username=AI_ASSISTANT_USERNAME,
        email=current_app.config.get("AI_ASSISTANT_EMAIL", "ai-assistant@hris.local"),
        role_id=role.id,
        is_active=True,
        force_password_change=False,
    )
    user.set_password(secrets.token_urlsafe(32))
    db.session.add(user)
    db.session.commit()
    return user


def build_ai_fallback_reply(user_message: str) -> str:
    clean = (user_message or "").strip()
    if not clean:
        return "I can help with HR concerns, leave requests, attendance clarifications, and payroll-related questions."
    return (
        "I am currently running in local fallback mode without an AI API key. "
        f"I received: \"{clean[:220]}\". "
        "Please set AI_ASSISTANT_API_KEY in your environment to enable full assistant answers."
    )


def build_ai_error_reply(user_message: str, reason: str) -> str:
    clean = (user_message or "").strip()
    details = (reason or "Unknown OpenAI API error").strip()
    return (
        "I could not reach the AI provider right now. "
        f"Error: {details[:260]}. "
        f"I received: \"{clean[:180]}\"."
    )


def build_ai_reply(user_message: str, thread: ChatThread) -> str:
    api_key = (current_app.config.get("AI_ASSISTANT_API_KEY") or "").strip()
    model = current_app.config.get("AI_ASSISTANT_MODEL", "gpt-4o-mini")
    system_prompt = current_app.config.get(
        "AI_ASSISTANT_SYSTEM_PROMPT",
        "You are an HR assistant. Give concise, practical answers about attendance, leave, payroll, and company policies.",
    )
    if not api_key:
        return build_ai_fallback_reply(user_message)

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        response = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"Thread employee_user_id={thread.employee_user_id}. "
                        f"Question: {user_message}"
                    ),
                },
            ],
            max_output_tokens=500,
        )
        text = (response.output_text or "").strip()
        return text or "I could not generate a response right now. Please try again."
    except Exception as exc:
        return build_ai_error_reply(user_message, str(exc))


def _extract_leave_request_intent(user_message: str):
    pattern = re.compile(
        r"(?:file|create|submit)\s+(?:a\s+)?leave(?:\s+request)?(?:\s+for)?\s+(\d{4}-\d{2}-\d{2})(?:\s+to\s+(\d{4}-\d{2}-\d{2}))?",
        re.IGNORECASE,
    )
    match = pattern.search(user_message or "")
    if not match:
        return None
    start_raw = match.group(1)
    end_raw = match.group(2) or start_raw
    try:
        start_date = date.fromisoformat(start_raw)
        end_date = date.fromisoformat(end_raw)
    except ValueError:
        return None
    if end_date < start_date:
        return None
    day_count = Decimal((end_date - start_date).days + 1)

    leave_type = None
    if re.search(r"\bsick\b", user_message or "", re.IGNORECASE):
        leave_type = LeaveType.query.filter(LeaveType.name.ilike("%sick%")).first()
    elif re.search(r"\bvacation\b|\bannual\b", user_message or "", re.IGNORECASE):
        leave_type = LeaveType.query.filter(LeaveType.name.ilike("%vac%")).first() or LeaveType.query.first()
    else:
        leave_type = LeaveType.query.first()
    if not leave_type:
        return None
    reason = (user_message or "").strip()[:500] or "Requested via AI assistant"
    return {
        "leave_type": leave_type,
        "start_date": start_date,
        "end_date": end_date,
        "days": day_count,
        "reason": reason,
    }


def _extract_payroll_dispute_intent(user_message: str):
    if not re.search(r"\bpayroll\b|\bpayslip\b|\bsalary\b|\bdispute\b", user_message or "", re.IGNORECASE):
        return None
    entry_match = re.search(r"(?:payroll\s*entry\s*#?|entry\s*#?|entry\s+id\s*)(\d+)", user_message or "", re.IGNORECASE)
    payroll_entry_id = int(entry_match.group(1)) if entry_match else None
    return {"payroll_entry_id": payroll_entry_id}


def run_ai_automations(thread: ChatThread, sender, user_message: str) -> list[str]:
    if not current_app.config.get("AI_ASSISTANT_AUTOMATION_ENABLED", True):
        return []
    if not sender or not getattr(sender, "employee", None):
        return []
    notes: list[str] = []

    leave_intent = _extract_leave_request_intent(user_message)
    if leave_intent:
        leave_request = LeaveRequest(
            employee_id=sender.employee.id,
            leave_type_id=leave_intent["leave_type"].id,
            start_date=leave_intent["start_date"],
            end_date=leave_intent["end_date"],
            duration_type="whole_day",
            days=leave_intent["days"],
            reason=leave_intent["reason"],
            is_paid=bool(leave_intent["leave_type"].is_paid),
            status="pending",
        )
        db.session.add(leave_request)
        db.session.commit()
        notes.append(f"Leave request #{leave_request.id} was auto-created ({leave_request.start_date} to {leave_request.end_date}).")

    payroll_intent = _extract_payroll_dispute_intent(user_message)
    if payroll_intent:
        payroll_ticket = HrTicket(
            employee_id=sender.employee.id,
            category="payroll",
            subject="Payroll support request from AI assistant",
            description=(user_message or "").strip()[:1500] or "Payroll help requested via AI assistant.",
            status="open",
            priority="normal",
        )
        db.session.add(payroll_ticket)
        db.session.commit()
        notes.append(f"Payroll ticket #{payroll_ticket.id} was auto-created for HR follow-up.")

        payroll_entry_id = payroll_intent["payroll_entry_id"]
        if payroll_entry_id:
            payroll_entry = db.session.get(PayrollEntry, payroll_entry_id)
            if payroll_entry and payroll_entry.employee_id == sender.employee.id:
                dispute = PayslipDispute(
                    employee_id=sender.employee.id,
                    payroll_entry_id=payroll_entry.id,
                    subject="AI-assisted payslip dispute",
                    details=(user_message or "").strip()[:1500] or "Payslip dispute raised via AI assistant.",
                    status="open",
                )
                db.session.add(dispute)
                db.session.commit()
                notes.append(f"Payslip dispute #{dispute.id} was opened for payroll entry #{payroll_entry.id}.")

    return notes


def maybe_generate_ai_reply(thread: ChatThread, sender, user_message: str) -> ChatMessage | None:
    if not is_ai_assistant_enabled():
        return None
    if not sender or not sender.role:
        return None
    if getattr(sender, "username", None) == AI_ASSISTANT_USERNAME:
        return None

    assistant_user = get_ai_assistant_user()
    if assistant_user is None:
        return None

    automation_notes = run_ai_automations(thread, sender, user_message)
    ai_reply_text = build_ai_reply(user_message, thread)
    if automation_notes:
        ai_reply_text = f"{ai_reply_text}\n\nAutomation updates:\n- " + "\n- ".join(automation_notes)
    ai_message, _moderation = send_message(thread, assistant_user, ai_reply_text)
    return ai_message


def unread_chat_count_for_user(user) -> int:
    if not user or not getattr(user, "is_authenticated", False):
        return 0
    if is_chat_admin(user):
        return ChatMessage.query.join(ChatThread).filter(ChatMessage.is_read_by_admin.is_(False)).count()
    thread = get_or_create_employee_thread(user)
    if thread is None:
        return 0
    return thread.messages.filter(ChatMessage.is_read_by_employee.is_(False)).count()
