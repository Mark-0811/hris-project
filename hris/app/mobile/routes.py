from io import BytesIO

from flask import Response, g, jsonify, redirect, request, send_file
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from . import bp
from .services import (
    allowed_admin_modules_for_user,
    admin_summary_payload,
    attendance_payload,
    authenticate_mobile_login,
    cancel_leave_request_for_mobile,
    chat_messages_payload,
    chat_threads_payload,
    create_attendance_correction_for_mobile,
    create_document_request_for_mobile,
    create_exit_request_for_mobile,
    create_leave_request_for_mobile,
    create_privacy_request_for_mobile,
    create_profile_request_for_mobile,
    create_support_request_for_mobile,
    create_webview_bridge,
    documents_payload,
    download_document_record_for_mobile,
    download_payslip_record_for_mobile,
    exit_payload,
    help_center_payload,
    launch_webview_from_token,
    learning_payload,
    leave_payload,
    logout_mobile_session,
    modify_leave_request_for_mobile,
    notifications_payload,
    onboarding_payload,
    profile_payload,
    refresh_mobile_session,
    register_mobile_device,
    require_mobile_auth,
    requests_payload,
    respond_to_survey_for_mobile,
    role_required_mobile,
    schedule_payload,
    send_chat_message_for_mobile,
    submit_suggestion_for_mobile,
    surveys_payload,
    timeline_payload,
    workspace_payload,
    build_auth_payload,
)
from ..admin.services import mark_notifications_read
from ..utils.constants import ROLE_HR_ADMIN, ROLE_MANAGER, ROLE_PAYROLL_ADMIN, ROLE_SUPER_ADMIN


@bp.post("/auth/login")
def login():
    payload = request.get_json(silent=True) or {}
    auth_payload = authenticate_mobile_login(payload)
    if not auth_payload:
        return jsonify({"message": "Invalid username or password."}), 401
    return jsonify(auth_payload)


@bp.post("/auth/refresh")
def refresh():
    payload = request.get_json(silent=True) or {}
    auth_payload = refresh_mobile_session(payload)
    if not auth_payload:
        return jsonify({"message": "Refresh token is invalid or expired."}), 401
    return jsonify(auth_payload)


@bp.post("/auth/logout")
@require_mobile_auth
def logout():
    payload = request.get_json(silent=True) or {}
    logout_mobile_session(request.headers.get("Authorization", "").replace("Bearer ", "").strip(), payload.get("refresh_token"))
    return jsonify({"message": "Mobile session closed."})


@bp.get("/auth/me")
@require_mobile_auth
def me():
    session = g.mobile_session
    user = g.mobile_user
    return jsonify(build_auth_payload(user, request.headers.get("Authorization", "").replace("Bearer ", "").strip(), "", session.access_expires_at))


@bp.post("/auth/register-device-token")
@require_mobile_auth
def register_device_token():
    payload = request.get_json(silent=True) or {}
    device = register_mobile_device(g.mobile_user, payload)
    return jsonify({"id": device.id, "fcm_token": device.fcm_token, "platform": device.platform, "last_seen_at": device.last_seen_at.isoformat() if device.last_seen_at else None})


@bp.get("/workspace")
@require_mobile_auth
def workspace():
    return jsonify(workspace_payload(g.mobile_user))


@bp.get("/schedule")
@require_mobile_auth
def schedule():
    return jsonify(schedule_payload(g.mobile_user))


@bp.get("/notifications")
@require_mobile_auth
def notifications():
    return jsonify(notifications_payload(g.mobile_user))


@bp.post("/notifications/read")
@require_mobile_auth
def read_notifications():
    mark_notifications_read(g.mobile_user)
    return jsonify({"message": "Notifications marked as read."})


@bp.get("/attendance")
@require_mobile_auth
def attendance():
    return jsonify(attendance_payload(g.mobile_user))


@bp.post("/attendance/corrections")
@require_mobile_auth
def create_attendance_correction():
    payload = request.get_json(silent=True) or {}
    try:
        item = create_attendance_correction_for_mobile(g.mobile_user, payload)
    except (KeyError, ValueError) as exc:
        return jsonify({"message": str(exc)}), 400
    return jsonify({"id": item.id, "status": item.status, "created_at": item.created_at.isoformat() if item.created_at else None}), 201


@bp.get("/leave")
@require_mobile_auth
def leave():
    return jsonify(leave_payload(g.mobile_user))


@bp.post("/leave/requests")
@require_mobile_auth
def create_leave_request():
    payload = request.get_json(silent=True) or {}
    try:
        item = create_leave_request_for_mobile(g.mobile_user, payload)
    except (KeyError, ValueError) as exc:
        return jsonify({"message": str(exc)}), 400
    return jsonify(serialize_leave_request(item)), 201


@bp.post("/leave/requests/<int:request_id>/cancel")
@require_mobile_auth
def cancel_leave_request(request_id: int):
    try:
        item = cancel_leave_request_for_mobile(g.mobile_user, request_id)
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    return jsonify(serialize_leave_request(item))


@bp.post("/leave/requests/<int:request_id>/modify")
@require_mobile_auth
def modify_leave_request(request_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        ticket = modify_leave_request_for_mobile(g.mobile_user, request_id, payload.get("details", ""))
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    return jsonify({"id": ticket.id, "status": ticket.status, "subject": ticket.subject}), 201


@bp.get("/requests")
@require_mobile_auth
def requests_home():
    return jsonify(requests_payload(g.mobile_user))


@bp.post("/requests/support")
@require_mobile_auth
def create_support_request():
    payload = request.get_json(silent=True) or {}
    try:
        item = create_support_request_for_mobile(g.mobile_user, payload)
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    return jsonify({"id": item.id, "status": item.status, "subject": item.subject}), 201


@bp.post("/requests/privacy")
@require_mobile_auth
def create_privacy_request():
    payload = request.get_json(silent=True) or {}
    try:
        item = create_privacy_request_for_mobile(g.mobile_user, payload)
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    return jsonify({"id": item.id, "status": item.status, "request_type": item.request_type}), 201


@bp.post("/requests/document")
@require_mobile_auth
def create_document_request():
    payload = request.get_json(silent=True) or {}
    try:
        item = create_document_request_for_mobile(g.mobile_user, payload)
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    return jsonify({"id": item.id, "status": item.status, "subject": item.subject}), 201


@bp.get("/documents")
@require_mobile_auth
def documents():
    return jsonify(documents_payload(g.mobile_user))


@bp.post("/documents/<int:document_id>/acknowledge")
@require_mobile_auth
def acknowledge_document_route(document_id: int):
    try:
        item = acknowledge_document(g.mobile_user, document_id)
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    return jsonify({"id": item.id, "consented_at": item.consented_at.isoformat() if item.consented_at else None})


@bp.get("/documents/<int:document_id>/download")
@require_mobile_auth
def download_document(document_id: int):
    file_path = download_document_record_for_mobile(g.mobile_user, document_id)
    if not file_path:
        return jsonify({"message": "Document not found."}), 404
    return send_file(file_path, as_attachment=True, download_name=file_path.name)


@bp.get("/payslips/<int:entry_id>/download")
@require_mobile_auth
def download_payslip(entry_id: int):
    entry = download_payslip_record_for_mobile(g.mobile_user, entry_id)
    if not entry:
        return jsonify({"message": "Payslip not found."}), 404
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 60
    pdf.setTitle(f"Payroll Slip - {entry.employee.full_name if entry.employee else 'Employee'}")
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(50, y, "HRIS Payroll Slip")
    y -= 30
    pdf.setFont("Helvetica", 11)
    for line in [
        f"Employee: {entry.employee.full_name if entry.employee else 'Unknown'}",
        f"Employee Code: {entry.employee.employee_code if entry.employee else 'N/A'}",
        f"Cutoff: {entry.cutoff.cutoff_name if entry.cutoff else 'N/A'}",
        f"Status: {entry.status.title()}",
        "",
        f"Basic Pay: {entry.basic_pay}",
        f"Overtime Pay: {entry.overtime_pay}",
        f"Late Deduction: {entry.late_deduction}",
        f"Undertime Deduction: {entry.undertime_deduction}",
        f"Allowance Total: {entry.allowance_total}",
        f"Deduction Total: {entry.deduction_total}",
        "",
        f"Net Pay: {entry.net_pay}",
    ]:
        pdf.drawString(50, y, line)
        y -= 20
    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    filename = f"payroll_{entry.employee.employee_code if entry.employee else entry.id}_{entry.cutoff_id}.pdf"
    return send_file(buffer, mimetype="application/pdf", as_attachment=True, download_name=filename)


@bp.get("/help-center")
@require_mobile_auth
def help_center():
    return jsonify(help_center_payload(g.mobile_user))


@bp.get("/learning")
@require_mobile_auth
def learning():
    return jsonify(learning_payload(g.mobile_user))


@bp.get("/surveys")
@require_mobile_auth
def surveys():
    return jsonify(surveys_payload(g.mobile_user))


@bp.post("/surveys/<int:survey_id>/respond")
@require_mobile_auth
def respond_survey(survey_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        item = respond_to_survey_for_mobile(g.mobile_user, survey_id, payload)
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    return jsonify({"id": item.id, "survey_id": item.survey_id}), 201


@bp.post("/suggestions")
@require_mobile_auth
def suggestions():
    payload = request.get_json(silent=True) or {}
    try:
        item = submit_suggestion_for_mobile(g.mobile_user, payload)
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    return jsonify({"id": item.id, "status": item.status}), 201


@bp.get("/onboarding")
@require_mobile_auth
def onboarding():
    return jsonify(onboarding_payload(g.mobile_user))


@bp.get("/timeline")
@require_mobile_auth
def timeline():
    return jsonify(timeline_payload(g.mobile_user))


@bp.get("/profile")
@require_mobile_auth
def profile():
    return jsonify(profile_payload(g.mobile_user))


@bp.post("/profile/update-request")
@require_mobile_auth
def create_profile_request():
    payload = request.get_json(silent=True) or {}
    try:
        item = create_profile_request_for_mobile(g.mobile_user, payload)
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    return jsonify({"id": item.id, "status": item.status}), 201


@bp.get("/chat/threads")
@require_mobile_auth
def chat_threads():
    return jsonify(chat_threads_payload(g.mobile_user))


@bp.get("/chat/threads/<int:thread_id>/messages")
@require_mobile_auth
def chat_messages(thread_id: int):
    try:
        return jsonify(chat_messages_payload(g.mobile_user, thread_id))
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 404


@bp.post("/chat/threads/<int:thread_id>/messages")
@require_mobile_auth
def send_chat_message(thread_id: int):
    body = request.form.get("body", "") if request.content_type and "multipart/form-data" in request.content_type else (request.get_json(silent=True) or {}).get("body", "")
    attachment = request.files.get("attachment")
    try:
        return jsonify(send_chat_message_for_mobile(g.mobile_user, thread_id, body, attachment)), 201
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400


@bp.get("/exit")
@require_mobile_auth
def exit_center():
    return jsonify(exit_payload(g.mobile_user))


@bp.post("/exit")
@require_mobile_auth
def create_exit():
    payload = request.get_json(silent=True) or {}
    try:
        item = create_exit_request_for_mobile(g.mobile_user, payload)
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    return jsonify({"id": item.id, "last_day": item.last_day.isoformat() if item.last_day else None}), 201


@bp.get("/admin/summary")
@require_mobile_auth
@role_required_mobile(ROLE_SUPER_ADMIN, ROLE_HR_ADMIN, ROLE_PAYROLL_ADMIN, ROLE_MANAGER)
def admin_summary():
    return jsonify(admin_summary_payload(g.mobile_user))


@bp.get("/admin/webview/modules")
@require_mobile_auth
@role_required_mobile(ROLE_SUPER_ADMIN, ROLE_HR_ADMIN, ROLE_PAYROLL_ADMIN, ROLE_MANAGER)
def admin_webview_modules():
    return jsonify({"items": allowed_admin_modules_for_user(g.mobile_user)})


@bp.post("/admin/webview/bridge")
@require_mobile_auth
@role_required_mobile(ROLE_SUPER_ADMIN, ROLE_HR_ADMIN, ROLE_PAYROLL_ADMIN, ROLE_MANAGER)
def admin_webview_bridge():
    payload = request.get_json(silent=True) or {}
    try:
        return jsonify(create_webview_bridge(g.mobile_user, payload.get("module_slug", "")))
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400


@bp.get("/webview/launch/<token>")
def launch_webview(token: str):
    target_url = launch_webview_from_token(token)
    if not target_url:
        return Response("Invalid or expired bridge token.", status=403)
    return redirect(target_url)
