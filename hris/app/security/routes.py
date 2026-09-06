from __future__ import annotations

from flask import Response, flash, jsonify, redirect, request, url_for
from flask_login import login_required

from . import bp
from .services import (
    create_or_update_profile_from_upload,
    event_to_dict,
    intruder_to_dict,
    list_intruder_profiles,
    list_security_events,
    mark_event_as_intruder,
    unmark_event_intruder,
)
from .worker import stream_generator
from ..extensions import csrf
from ..utils.constants import USER_ADMIN_ROLES
from ..utils.decorators import role_required


@bp.route("/security/stream")
@login_required
@role_required(*USER_ADMIN_ROLES)
def stream():
    return Response(stream_generator(), mimetype="multipart/x-mixed-replace; boundary=frame")


@bp.route("/security/enroll", methods=["POST"])
@login_required
@role_required(*USER_ADMIN_ROLES)
def enroll_from_form():
    name = (request.form.get("name") or "").strip()
    notes = (request.form.get("notes") or "").strip()
    upload = request.files.get("image")

    if not name or upload is None:
        flash("Name and profile image are required for enrollment.", "warning")
        return redirect(url_for("admin.api_requests"))

    try:
        create_or_update_profile_from_upload(name=name, file_storage=upload, notes=notes, status="allowed")
    except Exception as exc:
        flash(f"Enrollment failed: {exc}", "danger")
        return redirect(url_for("admin.api_requests"))

    flash("Person profile enrolled successfully.", "success")
    return redirect(url_for("admin.api_requests"))


@bp.route("/api/security/enroll", methods=["POST"])
@login_required
@role_required(*USER_ADMIN_ROLES)
@csrf.exempt
def api_enroll():
    name = (request.form.get("name") or "").strip()
    notes = (request.form.get("notes") or "").strip()
    status = (request.form.get("status") or "allowed").strip() or "allowed"
    upload = request.files.get("image")

    if not name or upload is None:
        return jsonify({"message": "Fields `name` and `image` are required."}), 400

    profile = create_or_update_profile_from_upload(name=name, file_storage=upload, notes=notes, status=status)
    return jsonify(
        {
            "id": profile.id,
            "name": profile.name,
            "status": profile.status,
            "notes": profile.notes,
            "image_url": profile.image_url,
            "is_active": profile.is_active,
        }
    ), 201


@bp.route("/api/security/events", methods=["GET"])
@login_required
@role_required(*USER_ADMIN_ROLES)
def api_events():
    try:
        limit = int(request.args.get("limit", 100))
    except ValueError:
        limit = 100
    limit = max(1, min(limit, 500))

    result_class = (request.args.get("result_class") or "").strip() or None
    events = list_security_events(limit=limit, result_class=result_class)
    return jsonify([event_to_dict(event) for event in events])


@bp.route("/api/security/events/<int:event_id>/mark-intruder", methods=["POST"])
@login_required
@role_required(*USER_ADMIN_ROLES)
@csrf.exempt
def api_mark_intruder(event_id: int):
    payload = request.get_json(silent=True) or {}
    label = (payload.get("label") or "").strip() or None
    notes = (payload.get("notes") or "").strip()

    event = mark_event_as_intruder(event_id=event_id, label=label, notes=notes)
    return jsonify(event_to_dict(event))


@bp.route("/api/security/events/<int:event_id>/unmark-intruder", methods=["POST"])
@login_required
@role_required(*USER_ADMIN_ROLES)
@csrf.exempt
def api_unmark_intruder(event_id: int):
    event = unmark_event_intruder(event_id=event_id)
    return jsonify(event_to_dict(event))


@bp.route("/api/security/intruders", methods=["GET"])
@login_required
@role_required(*USER_ADMIN_ROLES)
def api_intruders():
    intruders = list_intruder_profiles()
    return jsonify([intruder_to_dict(profile) for profile in intruders])


@bp.app_template_filter("security_badge_class")
def security_badge_class(value: str) -> str:
    mapping = {
        "known_person": "success",
        "unknown_person": "warning",
        "blacklisted_person": "danger",
    }
    return mapping.get(value, "secondary")
