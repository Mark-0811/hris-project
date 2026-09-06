from datetime import datetime
import json

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from flask import current_app

from ..extensions import db
from ..models import AuditLog, EmployeeProfileUpdateRequest, Notification, User
from ..utils.constants import USER_ADMIN_ROLES

SELF_SERVICE_PROFILE_FIELDS = {
    "birthdate": "Birthdate",
    "gender": "Gender",
    "civil_status": "Civil status",
    "address": "Address",
    "emergency_contact_name": "Emergency contact name",
}


def _profile_change_labels(changes: list[dict]) -> list[str]:
    return [item["label"] for item in changes] or ["profile details"]


def _active_admin_users() -> list[User]:
    users = User.query.filter(User.is_active.is_(True)).all()
    return [item for item in users if item.role and item.role.name in USER_ADMIN_ROLES]


def _notify_admin_users(title: str, message: str, notification_type: str, *, exclude_user_ids: set[int] | None = None) -> None:
    excluded = exclude_user_ids or set()
    for admin_user in _active_admin_users():
        if admin_user.id in excluded:
            continue
        db.session.add(
            Notification(
                user_id=admin_user.id,
                title=title,
                message=message,
                type=notification_type,
                is_read=False,
            )
        )


def authenticate_user(username: str, password: str):
    user = User.query.filter_by(username=username, is_active=True).first()
    if user and user.check_password(password):
        user.mark_login()
        db.session.commit()
        return user
    return None


def change_user_password(user: User, new_password: str, *, require_change: bool = False) -> None:
    user.set_password(new_password)
    user.force_password_change = require_change
    db.session.commit()


def _reset_password_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="auth-reset-password")


def generate_password_reset_token(user: User) -> str:
    return _reset_password_serializer().dumps({"user_id": user.id, "email": user.email})


def verify_password_reset_token(token: str, max_age: int = 3600) -> User | None:
    try:
        payload = _reset_password_serializer().loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None

    user = db.session.get(User, payload.get("user_id"))
    if not user or not user.is_active or user.email != payload.get("email"):
        return None
    return user


def profile_request_field_labels() -> dict[str, str]:
    return SELF_SERVICE_PROFILE_FIELDS


def pending_profile_update_request_for_user(user: User) -> EmployeeProfileUpdateRequest | None:
    if not user or not user.employee_id:
        return None
    return (
        EmployeeProfileUpdateRequest.query.filter_by(user_id=user.id, status="pending")
        .order_by(EmployeeProfileUpdateRequest.created_at.desc())
        .first()
    )


def list_profile_update_requests(*, user_id: int | None = None, status: str | None = None, limit: int | None = None) -> list[EmployeeProfileUpdateRequest]:
    query = EmployeeProfileUpdateRequest.query.order_by(EmployeeProfileUpdateRequest.created_at.desc())
    if user_id:
        query = query.filter_by(user_id=user_id)
    if status:
        query = query.filter_by(status=status)
    if limit:
        query = query.limit(limit)
    return query.all()


def _serialize_profile_value(value):
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def current_profile_request_values(user: User) -> dict[str, str]:
    employee = getattr(user, "employee", None)
    if not employee:
        return {field_name: "" for field_name in SELF_SERVICE_PROFILE_FIELDS}
    return {
        field_name: _serialize_profile_value(getattr(employee, field_name, ""))
        for field_name in SELF_SERVICE_PROFILE_FIELDS
    }


def _normalized_profile_payload(form) -> dict[str, str]:
    payload = {}
    for field_name in SELF_SERVICE_PROFILE_FIELDS:
        value = getattr(form, field_name).data
        if value is None:
            payload[field_name] = ""
        elif hasattr(value, "isoformat"):
            payload[field_name] = value.isoformat()
        else:
            payload[field_name] = str(value).strip()
    return payload


def profile_request_payload(request_obj: EmployeeProfileUpdateRequest) -> dict[str, str]:
    try:
        payload = json.loads(request_obj.requested_data_json or "{}")
    except (TypeError, ValueError):
        payload = {}
    if not isinstance(payload, dict):
        return {}
    return {
        field_name: str(payload.get(field_name, "") or "")
        for field_name in SELF_SERVICE_PROFILE_FIELDS
    }


def profile_request_changes(request_obj: EmployeeProfileUpdateRequest) -> list[dict]:
    employee = getattr(request_obj, "employee", None)
    payload = profile_request_payload(request_obj)
    changes = []
    for field_name, label in SELF_SERVICE_PROFILE_FIELDS.items():
        current_value = _serialize_profile_value(getattr(employee, field_name, "")) if employee else ""
        requested_value = payload.get(field_name, "")
        if current_value != requested_value:
            changes.append(
                {
                    "field_name": field_name,
                    "label": label,
                    "current_value": current_value or "Not set",
                    "requested_value": requested_value or "Not set",
                }
            )
    return changes


def create_profile_update_request(user: User, form) -> EmployeeProfileUpdateRequest:
    employee = getattr(user, "employee", None)
    if not employee:
        raise ValueError("A linked employee profile is required.")

    if pending_profile_update_request_for_user(user):
        raise ValueError("A pending profile update request already exists.")

    payload = _normalized_profile_payload(form)
    request_obj = EmployeeProfileUpdateRequest(
        user_id=user.id,
        employee_id=employee.id,
        requested_data_json=json.dumps(payload),
        reason=(form.reason.data or "").strip() or None,
    )
    request_obj.employee = employee
    change_rows = profile_request_changes(request_obj)
    if not change_rows:
        raise ValueError("No changes were detected in the submitted profile update request.")
    db.session.add(request_obj)

    change_labels = _profile_change_labels(change_rows)
    _notify_admin_users(
        "Profile update request pending",
        f"{user.display_name} requested updates for {', '.join(change_labels)}.",
        "profile_update_request",
    )
    db.session.add(
        AuditLog(
            user_id=user.id,
            module="profile_update",
            action="request_create",
            record_id=str(user.id),
            description=f"Submitted profile update request for {', '.join(change_labels)}",
        )
    )
    db.session.commit()
    return request_obj


def review_profile_update_request(request_obj: EmployeeProfileUpdateRequest, reviewer: User, approved: bool, decision_notes: str = "") -> None:
    employee = getattr(request_obj, "employee", None)
    if employee is None:
        employee = getattr(db.session.get(User, request_obj.user_id), "employee", None)
    requester = db.session.get(User, request_obj.user_id)

    request_obj.status = "approved" if approved else "rejected"
    request_obj.reviewer_id = reviewer.id
    request_obj.reviewed_at = datetime.utcnow()
    request_obj.decision_notes = (decision_notes or "").strip() or None

    changes = profile_request_changes(request_obj)
    change_labels = _profile_change_labels(changes)
    if approved and employee:
        payload = profile_request_payload(request_obj)
        for field_name in SELF_SERVICE_PROFILE_FIELDS:
            value = payload.get(field_name, "")
            if field_name == "birthdate":
                setattr(employee, field_name, datetime.strptime(value, "%Y-%m-%d").date() if value else None)
            else:
                setattr(employee, field_name, value or None)

    db.session.add(
        Notification(
            user_id=request_obj.user_id,
            title=f"Profile update request {request_obj.status}",
            message=(
                f"Your request to update {', '.join(change_labels)} "
                f"was {request_obj.status}."
            ),
            type="profile_update_status",
            is_read=False,
        )
    )
    _notify_admin_users(
        f"Profile update request {request_obj.status}",
        (
            f"{reviewer.display_name} {request_obj.status} "
            f"{requester.display_name if requester else f'user {request_obj.user_id}'}'s profile request for {', '.join(change_labels)}."
        ),
        "profile_update_status",
    )
    db.session.add(
        AuditLog(
            user_id=reviewer.id,
            module="profile_update",
            action=request_obj.status,
            record_id=str(request_obj.id),
            description=f"{request_obj.status.title()} profile update request for user {request_obj.user_id}",
        )
    )
    db.session.commit()
