from __future__ import annotations

from datetime import date, datetime, timedelta
from functools import wraps
import hashlib
import secrets

from flask import current_app, g, jsonify, request, url_for
from flask_login import login_user
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from ..admin.services import (
    get_dashboard_context,
    get_task_inbox,
    list_user_notifications,
    serialize_notification,
    unread_notification_count,
)
from ..attendance.services import attendance_summary, list_employee_attendance_records, serialize_record
from ..auth.services import (
    authenticate_user,
    create_profile_update_request,
    current_profile_request_values,
    list_profile_update_requests,
    profile_request_changes,
)
from ..chat.services import (
    can_access_thread,
    get_or_create_employee_thread,
    get_thread_for_user,
    is_chat_admin,
    list_messages,
    list_threads_for_user,
    mark_thread_read,
    send_message,
)
from ..extensions import db
from ..experience.services import (
    acknowledge_document,
    current_employee,
    document_download_path,
    documents_context,
    exit_context,
    help_center_context,
    learning_context,
    onboarding_context,
    requests_context,
    schedule_context,
    submit_attendance_correction,
    submit_document_request,
    submit_exit_request,
    submit_leave_modification_request,
    submit_privacy_request_for_employee,
    submit_suggestion,
    submit_survey_response,
    surveys_context,
    timeline_context,
    workspace_context,
    create_support_ticket,
)
from ..leave.services import list_leave_type_balances_for_user, save_leave_request, serialize_leave_request
from ..models import ChatMessage, ChatThread, DocumentRecord, HrTicket, LeaveRequest, MobileDevice, MobileSession, PayrollEntry, User
from ..utils.menu_access import get_user_menu_keys

ADMIN_WEBVIEW_MODULES = {
    "user_access": {"label": "User Access", "menu_key": "users", "endpoint": "admin.users"},
    "payroll": {"label": "Payroll", "menu_key": "payroll", "endpoint": "payroll.index"},
    "bulk_actions": {"label": "Bulk Actions", "menu_key": "bulk_actions", "endpoint": "admin.bulk_actions"},
    "enterprise": {"label": "Enterprise Center", "menu_key": "enterprise", "endpoint": "enterprise.index"},
    "reports": {"label": "Reports", "menu_key": "reports", "endpoint": "reports.index"},
}

MOBILE_NATIVE_MENU_KEYS = {
    "my_workspace",
    "my_schedule",
    "my_requests",
    "my_documents",
    "help_center",
    "learning",
    "surveys",
    "attendance",
    "leave",
    "messages",
    "profile",
    "team_approvals",
    "team_attendance",
}


def _utcnow() -> datetime:
    return datetime.utcnow()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _safe_iso(value) -> str | None:
    return value.isoformat() if value else None


def _user_photo_url(user: User | None) -> str | None:
    if not user:
        return None
    employee = current_employee(user)
    if user.photo_url:
        return user.photo_url
    if employee and employee.profile_image:
        if employee.profile_image.startswith(("http://", "https://", "/")):
            return employee.profile_image
        return url_for("static", filename=employee.profile_image, _external=False)
    return None


def _role_name(user: User) -> str:
    return user.role.name if user.role else ""


def _bearer_token() -> str | None:
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header.split(" ", 1)[1].strip() or None
    return request.args.get("access_token")


def _webview_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="mobile-webview-bridge")


def _session_user(session: MobileSession | None) -> User | None:
    if not session:
        return None
    user = db.session.get(User, session.user_id)
    if not user or not user.is_active:
        return None
    return user


def _active_session_from_access_token(token: str | None) -> MobileSession | None:
    if not token:
        return None
    session = MobileSession.query.filter_by(access_token_hash=_hash_token(token), is_active=True).first()
    if not session or session.access_expires_at <= _utcnow():
        return None
    return session


def _active_session_from_refresh_token(token: str | None) -> MobileSession | None:
    if not token:
        return None
    session = MobileSession.query.filter_by(refresh_token_hash=_hash_token(token), is_active=True).first()
    if not session or session.refresh_expires_at <= _utcnow():
        return None
    return session


def require_mobile_auth(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        session = _active_session_from_access_token(_bearer_token())
        user = _session_user(session)
        if not session or not user:
            return jsonify({"message": "Authentication required."}), 401
        session.last_used_at = _utcnow()
        db.session.commit()
        g.mobile_session = session
        g.mobile_user = user
        return view_func(*args, **kwargs)

    return wrapped


def role_required_mobile(*allowed_roles: str):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            user = getattr(g, "mobile_user", None)
            if _role_name(user) not in allowed_roles:
                return jsonify({"message": "You do not have access to this resource."}), 403
            return view_func(*args, **kwargs)

        return wrapped

    return decorator


def _issue_session_tokens(user: User, payload: dict) -> dict:
    access_token = secrets.token_urlsafe(32)
    refresh_token = secrets.token_urlsafe(48)
    access_expires_at = _utcnow() + timedelta(hours=current_app.config["MOBILE_ACCESS_TOKEN_HOURS"])
    refresh_expires_at = _utcnow() + timedelta(days=current_app.config["MOBILE_REFRESH_TOKEN_DAYS"])
    session = MobileSession(
        user_id=user.id,
        access_token_hash=_hash_token(access_token),
        refresh_token_hash=_hash_token(refresh_token),
        access_expires_at=access_expires_at,
        refresh_expires_at=refresh_expires_at,
        last_used_at=_utcnow(),
        device_name=(payload.get("device_name") or "").strip() or None,
        platform=(payload.get("platform") or "android").strip() or "android",
        app_version=(payload.get("app_version") or "").strip() or None,
        is_active=True,
    )
    db.session.add(session)
    db.session.commit()
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "access_expires_at": access_expires_at,
    }


def _allowed_webview_modules(user: User) -> list[dict]:
    keys = get_user_menu_keys(user)
    items = []
    for slug, meta in ADMIN_WEBVIEW_MODULES.items():
        if meta["menu_key"] in keys:
            items.append({"slug": slug, "label": meta["label"], "endpoint": meta["endpoint"]})
    return items


def _mobile_capabilities(user: User) -> dict:
    menu_keys = sorted(get_user_menu_keys(user))
    return {
        "native_modules": sorted(set(menu_keys) & MOBILE_NATIVE_MENU_KEYS),
        "webview_modules": _allowed_webview_modules(user),
        "supports_push": True,
        "supports_live_updates": True,
        "supports_mobile_punch": False,
    }


def build_auth_payload(user: User, access_token: str, refresh_token: str, access_expires_at: datetime) -> dict:
    employee = current_employee(user)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": access_expires_at.isoformat(),
        "role_name": _role_name(user),
        "menu_keys": sorted(get_user_menu_keys(user)),
        "mobile_capabilities": _mobile_capabilities(user),
        "user_profile": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "display_name": user.display_name,
            "photo_url": _user_photo_url(user),
            "employee_id": employee.id if employee else None,
            "employee_code": employee.employee_code if employee else None,
            "department": employee.department.name if employee and employee.department else None,
            "position": employee.position.name if employee and employee.position else None,
        },
    }


def authenticate_mobile_login(payload: dict) -> dict | None:
    user = authenticate_user((payload.get("username") or "").strip(), payload.get("password") or "")
    if not user:
        return None
    tokens = _issue_session_tokens(user, payload)
    return build_auth_payload(user, tokens["access_token"], tokens["refresh_token"], tokens["access_expires_at"])


def refresh_mobile_session(payload: dict) -> dict | None:
    refresh_token = payload.get("refresh_token")
    session = _active_session_from_refresh_token(refresh_token)
    user = _session_user(session)
    if not session or not user:
        return None
    access_token = secrets.token_urlsafe(32)
    session.access_token_hash = _hash_token(access_token)
    session.access_expires_at = _utcnow() + timedelta(hours=current_app.config["MOBILE_ACCESS_TOKEN_HOURS"])
    session.last_used_at = _utcnow()
    db.session.commit()
    return build_auth_payload(user, access_token, refresh_token, session.access_expires_at)


def logout_mobile_session(access_token: str | None, refresh_token: str | None = None) -> None:
    session = _active_session_from_access_token(access_token)
    if session is None and refresh_token:
        session = _active_session_from_refresh_token(refresh_token)
    if session:
        session.is_active = False
        db.session.commit()


def register_mobile_device(user: User, payload: dict) -> MobileDevice:
    fcm_token = (payload.get("fcm_token") or "").strip()
    if not fcm_token:
        raise ValueError("fcm_token is required.")
    device = MobileDevice.query.filter_by(user_id=user.id, fcm_token=fcm_token).first()
    if device is None:
        device = MobileDevice(user_id=user.id, fcm_token=fcm_token)
        db.session.add(device)
    device.platform = (payload.get("platform") or device.platform or "android").strip() or "android"
    device.device_name = (payload.get("device_name") or "").strip() or None
    device.device_model = (payload.get("device_model") or "").strip() or None
    device.app_version = (payload.get("app_version") or "").strip() or None
    device.last_seen_at = _utcnow()
    device.is_active = True
    db.session.commit()
    return device


def _serialize_announcement(item) -> dict:
    return {
        "id": item.id,
        "title": item.title,
        "body": item.body,
        "created_at": _safe_iso(item.created_at),
        "image_url": url_for("static", filename=f"uploads/news/{item.image_filename}", _external=False)
        if getattr(item, "image_filename", None)
        else None,
    }


def _serialize_ticket(item: HrTicket) -> dict:
    return {
        "id": item.id,
        "category": item.category,
        "subject": item.subject,
        "description": item.description,
        "priority": item.priority,
        "status": item.status,
        "due_date": _safe_iso(item.due_date),
        "created_at": _safe_iso(item.created_at),
    }


def _serialize_profile_request(item) -> dict:
    return {
        "id": item.id,
        "status": item.status,
        "reason": item.reason,
        "created_at": _safe_iso(item.created_at),
        "reviewed_at": _safe_iso(item.reviewed_at),
        "decision_notes": item.decision_notes,
        "changes": profile_request_changes(item),
    }


def _serialize_leave_balance(row: dict) -> dict:
    leave_type = row["leave_type"]
    return {
        "leave_type_id": leave_type.id,
        "leave_type_name": leave_type.name,
        "year": row["year"],
        "total_credits": float(row["total_credits"]),
        "used_credits": float(row["used_credits"]),
        "remaining_credits": float(row["remaining_credits"]),
    }


def _serialize_document(item: dict) -> dict:
    record = item["record"]
    return {
        "id": record.id,
        "document_type": record.document_type,
        "display_name": item["display_name"],
        "status": item["status_label"],
        "expiry_date": _safe_iso(record.expiry_date),
        "downloadable": item["downloadable"],
        "acknowledged": item["acknowledged"],
        "download_url": url_for("mobile.download_document", document_id=record.id, _external=False) if item["downloadable"] else None,
    }


def _serialize_payslip(entry: PayrollEntry) -> dict:
    return {
        "id": entry.id,
        "cutoff": entry.cutoff.cutoff_name if entry.cutoff else None,
        "status": entry.status,
        "net_pay": float(entry.net_pay),
        "download_url": url_for("mobile.download_payslip", entry_id=entry.id, _external=False),
        "created_at": _safe_iso(entry.created_at),
    }


def _serialize_chat_message(message, viewer_id: int) -> dict:
    attachment_url = None
    attachment_is_image = False
    if message and message.attachment_filename:
        attachment_url = url_for("static", filename=f"uploads/chat/{message.attachment_filename}", _external=False)
        attachment_is_image = bool(message.attachment_mime_type and message.attachment_mime_type.startswith("image/"))
    return {
        "id": message.id if message else None,
        "thread_id": message.thread_id if message else None,
        "sender_id": message.sender_id if message else None,
        "sender_name": message.sender.display_name if message and message.sender else None,
        "sender_role": message.sender.role.name if message and message.sender and message.sender.role else None,
        "body": message.body if message else None,
        "attachment_url": attachment_url,
        "attachment_name": message.attachment_original_name if message else None,
        "attachment_is_image": attachment_is_image,
        "created_at": _safe_iso(message.created_at) if message else None,
        "is_mine": bool(message and message.sender_id == viewer_id),
    }


def _serialize_chat_thread(thread: ChatThread, viewer: User) -> dict:
    latest = thread.messages.order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc()).first()
    unread = (
        thread.messages.filter_by(is_read_by_admin=False).count()
        if is_chat_admin(viewer)
        else thread.messages.filter_by(is_read_by_employee=False).count()
    )
    return {
        "id": thread.id,
        "employee_user_id": thread.employee_user_id,
        "title": thread.employee_user.display_name if thread.employee_user else f"Thread {thread.id}",
        "photo_url": _user_photo_url(thread.employee_user),
        "updated_at": _safe_iso(thread.updated_at),
        "unread_count": unread,
        "latest_message": _serialize_chat_message(latest, viewer.id) if latest else None,
    }


def _serialize_timeline_entry(item: dict) -> dict:
    return {
        "date": item["date"].isoformat() if hasattr(item["date"], "isoformat") else str(item["date"]),
        "title": item["title"],
        "detail": item["detail"],
        "kind": item["kind"],
    }


def _serialize_training_row(item: dict) -> dict:
    training = item["training"]
    course = item["course"]
    return {
        "id": training.id,
        "status": training.status,
        "completed_at": _safe_iso(training.completed_at),
        "expires_at": _safe_iso(training.expires_at),
        "course": {
            "id": course.id if course else training.course_id,
            "code": course.code if course else None,
            "title": course.title if course else "Unknown course",
            "renewal_months": course.renewal_months if course else None,
        },
    }


def _serialize_survey_row(item: dict) -> dict:
    survey = item["survey"]
    return {
        "id": survey.id,
        "title": survey.title,
        "status": survey.status,
        "launched_at": _safe_iso(survey.launched_at),
        "closed_at": _safe_iso(survey.closed_at),
        "questions": item["questions"],
        "answered": item["answered"],
    }


def _serialize_checklist_items(items) -> list[dict]:
    return [
        {
            "id": item.id,
            "step_name": item.step_name,
            "status": item.status,
            "due_date": _safe_iso(item.due_date),
        }
        for item in items
    ]


def _form_proxy(**fields):
    class Proxy:
        pass

    obj = Proxy()
    for key, value in fields.items():
        setattr(obj, key, type("Field", (), {"data": value})())
    return obj


def workspace_payload(user: User) -> dict:
    context = workspace_context(user)
    return {
        "cards": context["cards"],
        "quick_actions": context["quick_actions"],
        "unresolved_items": context["unresolved"],
        "recent_notifications": [serialize_notification(item) for item in context["notifications"]],
        "announcements": [_serialize_announcement(item) for item in context["announcements"]],
        "recent_requests": {
            "profile": [_serialize_profile_request(item) for item in context["profile_requests"]],
            "leave": [serialize_leave_request(item) for item in context["leave_requests"]],
        },
        "documents": [_serialize_document(item) for item in context["documents"]],
        "payslips": [_serialize_payslip(item) for item in context["payslips"]],
        "summary": {
            "unread_notifications": context["unread_notifications"],
            "employee_code": context["employee"].employee_code if context["employee"] else None,
        },
    }


def schedule_payload(user: User) -> dict:
    context = schedule_context(user)
    employee = context["employee"]
    return {
        "employee": {
            "id": employee.id,
            "employee_code": employee.employee_code,
            "full_name": employee.full_name,
        } if employee else None,
        "today_record": serialize_record(context["today_record"]) if context["today_record"] else None,
        "attendance_explanation": context["attendance_explanation"],
        "active_shift": {
            "name": context["active_shift"].shift.shift_name if context["active_shift"] and context["active_shift"].shift else None,
            "effective_date": _safe_iso(context["active_shift"].effective_date) if context["active_shift"] else None,
        } if context["active_shift"] else None,
        "holidays": [
            {
                "holiday_name": row["holiday"].holiday_name,
                "date": row["holiday"].date.isoformat(),
                "holiday_type": row["holiday"].holiday_type,
                "working_day": row["working_day"],
            }
            for row in context["holidays"]
        ],
        "team_leave_calendar": [serialize_leave_request(item) for item in context["team_leave_calendar"]],
        "geo_rule": {
            "branch_name": context["geo_rule"].branch_name,
            "radius_meters": context["geo_rule"].radius_meters,
            "anti_spoof_required": context["geo_rule"].anti_spoof_required,
        } if context["geo_rule"] else None,
        "geo_logs": [
            {
                "id": item.id,
                "created_at": _safe_iso(item.created_at),
                "within_geofence": item.within_geofence,
                "spoof_risk_score": item.spoof_risk_score,
            }
            for item in context["geo_logs"]
        ],
        "recent_records": [serialize_record(item) for item in context["recent_records"]],
    }


def requests_payload(user: User) -> dict:
    context = requests_context(user)
    return {
        "leave_requests": [serialize_leave_request(item) for item in context["leave_requests"]],
        "leave_timelines": context["leave_timelines"],
        "tickets": [_serialize_ticket(item) for item in context["tickets"]],
        "privacy_requests": [
            {
                "id": item.id,
                "request_type": item.request_type,
                "details": item.details,
                "status": item.status,
                "created_at": _safe_iso(item.created_at),
            }
            for item in context["privacy_requests"]
        ],
        "profile_requests": [_serialize_profile_request(item) for item in context["profile_requests"]],
        "access_requests": [
            {
                "id": item.id,
                "status": item.status,
                "reason": item.reason,
                "created_at": _safe_iso(item.created_at),
            }
            for item in context["access_requests"]
        ],
        "document_requests": [_serialize_ticket(item) for item in context["document_requests"]],
        "team_leave_calendar": [serialize_leave_request(item) for item in context["team_leave_calendar"]],
    }


def documents_payload(user: User) -> dict:
    context = documents_context(user)
    return {
        "documents": [_serialize_document(item) for item in context["documents"]],
        "payslips": [_serialize_payslip(item) for item in context["payslips"]],
        "document_requests": [_serialize_ticket(item) for item in context["document_requests"]],
    }


def help_center_payload(user: User) -> dict:
    context = help_center_context(user)
    return {
        "articles": [
            {
                "id": getattr(item, "id", None),
                "module": getattr(item, "module", "general"),
                "title": item.title if hasattr(item, "title") else item["title"],
                "content": item.content if hasattr(item, "content") else item["content"],
            }
            for item in context["articles"]
        ],
        "open_tickets": [_serialize_ticket(item) for item in context["open_tickets"]],
    }


def learning_payload(user: User) -> dict:
    context = learning_context(user)
    return {
        "trainings": [_serialize_training_row(item) for item in context["trainings"]],
        "suggested_courses": [
            {
                "id": item.id,
                "code": item.code,
                "title": item.title,
                "renewal_months": item.renewal_months,
            }
            for item in context["suggested_courses"]
        ],
        "calibrations": [
            {
                "id": item.id,
                "review_cycle": item.review_cycle,
                "nine_box": item.nine_box,
                "calibrated_rating": item.calibrated_rating,
                "notes": item.notes,
            }
            for item in context["calibrations"]
        ],
        "succession_candidates": [
            {
                "id": item.id,
                "readiness_level": item.readiness_level,
                "notes": item.notes,
            }
            for item in context["succession_candidates"]
        ],
        "compensation_changes": [
            {
                "id": item.id,
                "effective_date": _safe_iso(item.effective_date),
                "status": item.status,
            }
            for item in context["compensation_changes"]
        ],
    }


def surveys_payload(user: User) -> dict:
    context = surveys_context(user)
    return {
        "surveys": [_serialize_survey_row(item) for item in context["surveys"]],
        "announcements": [_serialize_announcement(item) for item in context["announcements"]],
        "responses": [
            {
                "id": item.id,
                "survey_id": item.survey_id,
                "sentiment_score": item.sentiment_score,
                "answers_json": item.answers_json,
                "created_at": _safe_iso(item.created_at),
            }
            for item in context["responses"]
        ],
    }


def onboarding_payload(user: User) -> dict:
    context = onboarding_context(user)
    return {"progress": context["progress"], "items": _serialize_checklist_items(context["items"])}


def exit_payload(user: User) -> dict:
    context = exit_context(user)
    return {
        "exit_record": {
            "id": context["exit_record"].id,
            "resignation_date": _safe_iso(context["exit_record"].resignation_date),
            "last_day": _safe_iso(context["exit_record"].last_day),
            "reason": context["exit_record"].reason,
            "interview_notes": context["exit_record"].interview_notes,
            "risk_tag": context["exit_record"].risk_tag,
        } if context["exit_record"] else None,
        "offboarding_items": _serialize_checklist_items(context["offboarding_items"]),
    }


def timeline_payload(user: User) -> dict:
    return {"entries": [_serialize_timeline_entry(item) for item in timeline_context(user)["entries"]]}


def notifications_payload(user: User) -> dict:
    items = list_user_notifications(user, limit=50)
    return {"items": [serialize_notification(item) for item in items], "unread_count": unread_notification_count(user)}


def attendance_payload(user: User) -> dict:
    employee = current_employee(user)
    records = list_employee_attendance_records(employee.id) if employee else []
    return {
        "summary": attendance_summary(),
        "today": schedule_payload(user),
        "history": [serialize_record(item) for item in records[:30]],
    }


def leave_payload(user: User) -> dict:
    employee = current_employee(user)
    leave_requests = (
        LeaveRequest.query.filter_by(employee_id=employee.id).order_by(LeaveRequest.created_at.desc()).all()
        if employee
        else []
    )
    return {
        "balances": [_serialize_leave_balance(item) for item in list_leave_type_balances_for_user(user)],
        "requests": [serialize_leave_request(item) for item in leave_requests],
    }


def profile_payload(user: User) -> dict:
    employee = current_employee(user)
    return {
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "display_name": user.display_name,
            "photo_url": _user_photo_url(user),
        },
        "employee": {
            "id": employee.id,
            "employee_code": employee.employee_code,
            "first_name": employee.first_name,
            "last_name": employee.last_name,
            "birthdate": _safe_iso(employee.birthdate),
            "gender": employee.gender,
            "civil_status": employee.civil_status,
            "address": employee.address,
            "emergency_contact_name": employee.emergency_contact_name,
            "department": employee.department.name if employee.department else None,
            "position": employee.position.name if employee.position else None,
        } if employee else None,
        "editable_fields": current_profile_request_values(user),
        "update_requests": [_serialize_profile_request(item) for item in list_profile_update_requests(user_id=user.id, limit=10)],
    }


def chat_threads_payload(user: User) -> dict:
    threads = [item for item in list_threads_for_user(user) if item]
    return {"threads": [_serialize_chat_thread(item, user) for item in threads]}


def chat_messages_payload(user: User, thread_id: int) -> dict:
    thread = get_thread_for_user(user, thread_id)
    if not can_access_thread(user, thread):
        raise ValueError("Thread not found.")
    mark_thread_read(thread, user)
    return {
        "thread": _serialize_chat_thread(thread, user),
        "messages": [_serialize_chat_message(item, user.id) for item in list_messages(thread)],
    }


def create_leave_request_for_mobile(user: User, payload: dict):
    employee = current_employee(user)
    if not employee:
        raise ValueError("A linked employee profile is required.")
    proxy = _form_proxy(
        employee_id=employee.id,
        leave_type_id=int(payload["leave_type_id"]),
        start_date=date.fromisoformat(payload["start_date"]),
        end_date=date.fromisoformat(payload["end_date"]),
        duration_type=(payload.get("duration_type") or "full_day"),
        reason=(payload.get("reason") or "").strip(),
    )
    return save_leave_request(proxy)


def create_profile_request_for_mobile(user: User, payload: dict):
    proxy = _form_proxy(
        birthdate=date.fromisoformat(payload["birthdate"]) if payload.get("birthdate") else None,
        gender=payload.get("gender"),
        civil_status=payload.get("civil_status"),
        address=payload.get("address"),
        emergency_contact_name=payload.get("emergency_contact_name"),
        reason=payload.get("reason"),
    )
    return create_profile_update_request(user, proxy)


def create_support_request_for_mobile(user: User, payload: dict):
    proxy = _form_proxy(
        category=payload.get("category"),
        subject=payload.get("subject"),
        description=payload.get("description"),
        priority=payload.get("priority") or "normal",
    )
    return create_support_ticket(user, proxy)


def create_privacy_request_for_mobile(user: User, payload: dict):
    proxy = _form_proxy(request_type=payload.get("request_type"), details=payload.get("details"))
    return submit_privacy_request_for_employee(user, proxy)


def create_document_request_for_mobile(user: User, payload: dict):
    proxy = _form_proxy(document_type=payload.get("document_type"), notes=payload.get("notes"))
    return submit_document_request(user, proxy)


def create_attendance_correction_for_mobile(user: User, payload: dict):
    proxy = _form_proxy(
        attendance_record_id=int(payload["attendance_record_id"]),
        reason_template=payload.get("reason_template") or "manual_adjustment",
        details=payload.get("details") or "",
        new_time_in=payload.get("new_time_in"),
        new_time_out=payload.get("new_time_out"),
    )
    return submit_attendance_correction(user, proxy)


def cancel_leave_request_for_mobile(user: User, request_id: int):
    employee = current_employee(user)
    request_obj = db.session.get(LeaveRequest, request_id)
    if not employee or not request_obj or request_obj.employee_id != employee.id:
        raise ValueError("Leave request not found.")
    if request_obj.status not in {"pending", "pending_step_1", "pending_step_2"}:
        raise ValueError("Only pending leave requests can be cancelled.")
    request_obj.status = "cancelled"
    db.session.commit()
    return request_obj


def modify_leave_request_for_mobile(user: User, request_id: int, details: str):
    return submit_leave_modification_request(user, request_id, details)


def respond_to_survey_for_mobile(user: User, survey_id: int, payload: dict):
    proxy = _form_proxy(sentiment_score=float(payload.get("sentiment_score", 0)), feedback=payload.get("feedback") or "")
    return submit_survey_response(user, survey_id, proxy)


def submit_suggestion_for_mobile(user: User, payload: dict):
    proxy = _form_proxy(message=payload.get("message"), is_anonymous=bool(payload.get("is_anonymous")))
    return submit_suggestion(user, proxy)


def create_exit_request_for_mobile(user: User, payload: dict):
    proxy = _form_proxy(
        resignation_date=date.fromisoformat(payload["resignation_date"]) if payload.get("resignation_date") else None,
        last_day=date.fromisoformat(payload["last_day"]) if payload.get("last_day") else None,
        reason=payload.get("reason"),
        interview_notes=payload.get("interview_notes"),
    )
    return submit_exit_request(user, proxy)


def send_chat_message_for_mobile(user: User, thread_id: int, body: str, attachment):
    thread = get_thread_for_user(user, thread_id)
    if thread is None and _role_name(user) == "Employee":
        thread = get_or_create_employee_thread(user)
    if not can_access_thread(user, thread):
        raise ValueError("Thread not found.")
    message, moderation = send_message(thread, user, body, attachment=attachment)
    return {"thread": _serialize_chat_thread(thread, user), "message": _serialize_chat_message(message, user.id), "moderation": moderation}


def admin_summary_payload(user: User) -> dict:
    dashboard = get_dashboard_context(user)
    return {
        "cards": dashboard["cards"],
        "quick_actions": dashboard["quick_actions"],
        "spotlight": dashboard["spotlight"],
        "tasks": get_task_inbox(user),
        "notifications": [serialize_notification(item) for item in list_user_notifications(user, limit=5)],
    }


def create_webview_bridge(user: User, module_slug: str) -> dict:
    meta = ADMIN_WEBVIEW_MODULES.get(module_slug)
    if not meta or meta["menu_key"] not in get_user_menu_keys(user):
        raise ValueError("Module is not available.")
    target_url = url_for(meta["endpoint"], _external=False)
    token = _webview_serializer().dumps({"user_id": user.id, "module_slug": module_slug, "target_url": target_url})
    return {
        "allowed_module_slug": module_slug,
        "target_url": target_url,
        "launch_url": url_for("mobile.launch_webview", token=token, _external=False),
    }


def allowed_admin_modules_for_user(user: User) -> list[dict]:
    return _allowed_webview_modules(user)


def launch_webview_from_token(token: str) -> str | None:
    try:
        payload = _webview_serializer().loads(token, max_age=current_app.config["MOBILE_WEBVIEW_BRIDGE_MINUTES"] * 60)
    except (BadSignature, SignatureExpired):
        return None
    user = db.session.get(User, payload.get("user_id"))
    meta = ADMIN_WEBVIEW_MODULES.get(payload.get("module_slug"))
    if not user or not user.is_active or not meta or meta["menu_key"] not in get_user_menu_keys(user):
        return None
    login_user(user, remember=False, force=True)
    return payload.get("target_url") or url_for(meta["endpoint"], _external=False)


def download_document_record_for_mobile(user: User, document_id: int):
    document = db.session.get(DocumentRecord, document_id)
    employee = current_employee(user)
    if not document or not employee or document.employee_id != employee.id:
        return None
    return document_download_path(document)


def download_payslip_record_for_mobile(user: User, entry_id: int):
    entry = db.session.get(PayrollEntry, entry_id)
    employee = current_employee(user)
    if not entry or not employee or entry.employee_id != employee.id:
        return None
    return entry
