from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from . import bp
from .services import (
    approval_summary,
    analytics_snapshot,
    command_search,
    compliance_summary,
    create_payslip_dispute,
    create_consent_log,
    create_hr_ticket,
    create_integration,
    create_privacy_request,
    create_webhook,
    data_health_summary,
    escalate_stale_approvals,
    enterprise_feature_groups,
    enterprise_status_cards,
    integration_summary,
    list_attendance_exceptions,
    list_consent_logs,
    list_data_health_checks,
    list_hr_tickets,
    list_integrations,
    list_privacy_requests,
    list_notification_preferences,
    list_task_inbox,
    list_webhooks,
    log_device_health,
    payroll_validation,
    run_ai_assistant,
    resolve_data_health_check,
    resolve_attendance_exception,
    run_data_health_checks,
    toggle_integration_status,
    toggle_webhook_status,
    upsert_notification_preference,
    update_hr_ticket_status,
    update_privacy_request_status,
)
from ..models import Employee, User
from ..utils.api import api_response
from ..utils.constants import USER_ADMIN_ROLES
from ..utils.decorators import role_required


@bp.route("/")
@login_required
@role_required(*USER_ADMIN_ROLES)
def index():
    return render_template(
        "enterprise/index.html",
        cards=enterprise_status_cards(),
        groups=enterprise_feature_groups(),
        analytics=analytics_snapshot(),
    )


@bp.route("/compliance")
@login_required
@role_required(*USER_ADMIN_ROLES)
def compliance():
    return render_template("enterprise/compliance.html", summary=compliance_summary())


@bp.route("/integrations")
@login_required
@role_required(*USER_ADMIN_ROLES)
def integrations():
    return render_template("enterprise/integrations.html", summary=integration_summary())


@bp.route("/data-health")
@login_required
@role_required(*USER_ADMIN_ROLES)
def data_health():
    return render_template("enterprise/data_health.html", summary=data_health_summary())


@bp.route("/api/search")
@login_required
@role_required(*USER_ADMIN_ROLES)
def api_search():
    term = (request.args.get("q") or "").strip()
    return jsonify(command_search(term))


@bp.route("/tickets", methods=["GET", "POST"])
@login_required
@role_required(*USER_ADMIN_ROLES)
def tickets():
    if request.method == "POST":
        employee_id = int(request.form.get("employee_id") or 0)
        category = (request.form.get("category") or "general").strip()
        subject = (request.form.get("subject") or "").strip()
        description = (request.form.get("description") or "").strip()
        priority = (request.form.get("priority") or "normal").strip()
        if employee_id and subject and description:
            create_hr_ticket(employee_id, category, subject, description, priority)
            flash("HR ticket created.", "success")
        else:
            flash("Employee, subject, and description are required.", "warning")
        return redirect(url_for("enterprise.tickets"))
    return render_template(
        "enterprise/tickets.html",
        tickets=list_hr_tickets(),
        employees=Employee.query.order_by(Employee.last_name.asc(), Employee.first_name.asc()).all(),
        users=User.query.order_by(User.username.asc()).all(),
    )


@bp.route("/tickets/<int:ticket_id>/status", methods=["POST"])
@login_required
@role_required(*USER_ADMIN_ROLES)
def update_ticket_status(ticket_id: int):
    status = (request.form.get("status") or "open").strip()
    assignee_id_raw = (request.form.get("assigned_to_user_id") or "").strip()
    assignee_id = int(assignee_id_raw) if assignee_id_raw.isdigit() else None
    update_hr_ticket_status(ticket_id, status, assignee_id)
    flash("Ticket updated.", "success")
    return redirect(url_for("enterprise.tickets"))


@bp.route("/compliance/records", methods=["GET", "POST"])
@login_required
@role_required(*USER_ADMIN_ROLES)
def compliance_records():
    if request.method == "POST":
        action = (request.form.get("action") or "").strip()
        if action == "create_consent":
            employee_id = int(request.form.get("employee_id") or 0)
            consent_type = (request.form.get("consent_type") or "").strip()
            notes = (request.form.get("notes") or "").strip()
            if employee_id and consent_type:
                create_consent_log(employee_id, consent_type, notes)
                flash("Consent log created.", "success")
            else:
                flash("Employee and consent type are required.", "warning")
        elif action == "create_privacy":
            employee_id = int(request.form.get("employee_id") or 0)
            request_type = (request.form.get("request_type") or "").strip()
            details = (request.form.get("details") or "").strip()
            if employee_id and request_type:
                create_privacy_request(employee_id, request_type, details)
                flash("Privacy request created.", "success")
            else:
                flash("Employee and request type are required.", "warning")
        elif action == "update_privacy":
            request_id = int(request.form.get("request_id") or 0)
            status = (request.form.get("status") or "open").strip()
            if request_id:
                update_privacy_request_status(request_id, status, current_user.id)
                flash("Privacy request updated.", "success")
        return redirect(url_for("enterprise.compliance_records"))
    return render_template(
        "enterprise/compliance_records.html",
        consent_logs=list_consent_logs(),
        privacy_requests=list_privacy_requests(),
        employees=Employee.query.order_by(Employee.last_name.asc(), Employee.first_name.asc()).all(),
    )


@bp.route("/integrations/manage", methods=["GET", "POST"])
@login_required
@role_required(*USER_ADMIN_ROLES)
def integrations_manage():
    if request.method == "POST":
        action = (request.form.get("action") or "").strip()
        if action == "create_integration":
            name = (request.form.get("name") or "").strip()
            provider = (request.form.get("provider") or "").strip()
            base_url = (request.form.get("base_url") or "").strip()
            if name and provider:
                create_integration(name, provider, base_url, "active")
                flash("Integration created.", "success")
            else:
                flash("Integration name and provider are required.", "warning")
        elif action == "toggle_integration":
            integration_id = int(request.form.get("integration_id") or 0)
            if integration_id:
                toggle_integration_status(integration_id)
                flash("Integration status updated.", "success")
        elif action == "create_webhook":
            integration_id = int(request.form.get("integration_id") or 0)
            event_name = (request.form.get("event_name") or "").strip()
            endpoint_url = (request.form.get("endpoint_url") or "").strip()
            if integration_id and event_name and endpoint_url:
                create_webhook(integration_id, event_name, endpoint_url)
                flash("Webhook created.", "success")
            else:
                flash("Integration, event, and endpoint are required.", "warning")
        elif action == "toggle_webhook":
            webhook_id = int(request.form.get("webhook_id") or 0)
            if webhook_id:
                toggle_webhook_status(webhook_id)
                flash("Webhook status updated.", "success")
        return redirect(url_for("enterprise.integrations_manage"))
    return render_template(
        "enterprise/integrations_manage.html",
        integrations=list_integrations(),
        webhooks=list_webhooks(),
    )


@bp.route("/data-health/checks", methods=["GET", "POST"])
@login_required
@role_required(*USER_ADMIN_ROLES)
def data_health_checks():
    if request.method == "POST":
        action = (request.form.get("action") or "").strip()
        if action == "run_checks":
            result = run_data_health_checks()
            flash(f"Data health checks executed. Created: {result['created']}.", "success")
        elif action == "resolve_check":
            check_id = int(request.form.get("check_id") or 0)
            if check_id:
                resolve_data_health_check(check_id)
                flash("Data health check resolved.", "success")
        return redirect(url_for("enterprise.data_health_checks"))
    return render_template(
        "enterprise/data_health_checks.html",
        checks=list_data_health_checks(),
    )


@bp.route("/api/tasks")
@login_required
def api_tasks():
    status = (request.args.get("status") or "").strip() or None
    rows = list_task_inbox(current_user.id, status=status)
    return api_response(
        "success",
        "Task inbox fetched.",
        data=[
            {
                "id": row.id,
                "task_type": row.task_type,
                "title": row.title,
                "description": row.description,
                "status": row.status,
                "due_at": row.due_at.isoformat() if row.due_at else None,
                "reference_module": row.reference_module,
                "reference_id": row.reference_id,
            }
            for row in rows
        ],
    )


@bp.route("/api/attendance-exceptions")
@login_required
@role_required(*USER_ADMIN_ROLES)
def api_attendance_exceptions():
    status = (request.args.get("status") or "").strip() or None
    rows = list_attendance_exceptions(status=status)
    return api_response(
        "success",
        "Attendance exceptions fetched.",
        data=[
            {
                "id": row.id,
                "attendance_record_id": row.attendance_record_id,
                "employee_id": row.employee_id,
                "date": row.date.isoformat() if row.date else None,
                "anomaly_type": row.anomaly_type,
                "severity": row.severity,
                "score": row.score,
                "status": row.status,
                "details": row.details,
            }
            for row in rows
        ],
    )


@bp.route("/api/attendance-exceptions/<int:exception_id>/resolve", methods=["POST"])
@login_required
@role_required(*USER_ADMIN_ROLES)
def api_resolve_attendance_exception(exception_id: int):
    payload = request.get_json(silent=True) or {}
    action = (payload.get("action") or "resolve").strip()
    if action not in {"resolve", "dismiss"}:
        return api_response("error", "Invalid action.", errors=["action must be resolve or dismiss"], http_status=400)
    item = resolve_attendance_exception(exception_id, current_user.id, action, payload.get("remarks"))
    if item is None:
        return api_response("error", "Attendance exception not found.", errors=["not_found"], http_status=404)
    return api_response("success", "Attendance exception updated.", data={"id": item.id, "status": item.status})


@bp.route("/api/approval-workflows")
@login_required
@role_required(*USER_ADMIN_ROLES)
def api_approval_workflows():
    module = (request.args.get("module") or "").strip() or None
    status = (request.args.get("status") or "").strip() or None
    rows = approval_summary(module=module, status=status)
    return api_response(
        "success",
        "Approval workflows fetched.",
        data=[
            {
                "id": row.id,
                "module": row.module,
                "record_id": row.record_id,
                "current_step": row.current_step,
                "total_steps": row.total_steps,
                "status": row.status,
            }
            for row in rows
        ],
    )


@bp.route("/api/approval-workflows/escalate", methods=["POST"])
@login_required
@role_required(*USER_ADMIN_ROLES)
def api_approval_escalate():
    payload = request.get_json(silent=True) or {}
    affected = escalate_stale_approvals(int(payload.get("hours") or 24))
    return api_response("success", "Stale approvals escalated.", data={"escalated_count": affected})


@bp.route("/api/notification-preferences", methods=["GET", "POST"])
@login_required
def api_notification_preferences():
    if request.method == "GET":
        rows = list_notification_preferences(current_user.id)
        return api_response(
            "success",
            "Notification preferences fetched.",
            data=[
                {
                    "event_type": row.event_type,
                    "in_app_enabled": row.in_app_enabled,
                    "email_enabled": row.email_enabled,
                    "sms_enabled": row.sms_enabled,
                }
                for row in rows
            ],
        )

    payload = request.get_json(silent=True) or {}
    event_type = (payload.get("event_type") or "").strip()
    if not event_type:
        return api_response("error", "Event type is required.", errors=["event_type is required"], http_status=400)
    row = upsert_notification_preference(
        current_user.id,
        event_type,
        bool(payload.get("in_app_enabled", True)),
        bool(payload.get("email_enabled", False)),
        bool(payload.get("sms_enabled", False)),
    )
    if row is None:
        return api_response("error", "Notification preferences table is unavailable.", errors=["table_not_ready"], http_status=503)
    return api_response(
        "success",
        "Notification preference saved.",
        data={
            "event_type": row.event_type,
            "in_app_enabled": row.in_app_enabled,
            "email_enabled": row.email_enabled,
            "sms_enabled": row.sms_enabled,
        },
        http_status=201,
    )


@bp.route("/api/payroll/validation/<int:cutoff_id>")
@login_required
@role_required(*USER_ADMIN_ROLES)
def api_payroll_validation(cutoff_id: int):
    data = payroll_validation(cutoff_id)
    return api_response("error" if data["blockers"] else "success", "Payroll validation completed.", data=data)


@bp.route("/api/payroll/disputes", methods=["POST"])
@login_required
def api_payroll_dispute_create():
    payload = request.get_json(silent=True) or {}
    payroll_entry_id = int(payload.get("payroll_entry_id") or 0)
    subject = (payload.get("subject") or "").strip()
    details = (payload.get("details") or "").strip()
    if not current_user.employee_id:
        return api_response("error", "Only linked employees can file disputes.", errors=["employee_link_required"], http_status=403)
    if payroll_entry_id <= 0 or not subject or not details:
        return api_response("error", "Missing required fields.", errors=["payroll_entry_id, subject, details are required"], http_status=400)
    item = create_payslip_dispute(current_user.employee_id, payroll_entry_id, subject, details)
    if item is None:
        return api_response("error", "Payslip dispute table is unavailable.", errors=["table_not_ready"], http_status=503)
    return api_response("success", "Payslip dispute created.", data={"id": item.id, "status": item.status}, http_status=201)


@bp.route("/api/device-health", methods=["POST"])
@login_required
@role_required(*USER_ADMIN_ROLES)
def api_device_health():
    payload = request.get_json(silent=True) or {}
    device_code = (payload.get("device_code") or "").strip()
    status = (payload.get("status") or "").strip()
    if not device_code or not status:
        return api_response("error", "device_code and status are required.", errors=["device_code and status are required"], http_status=400)
    item = log_device_health(
        device_code=device_code,
        source=(payload.get("source") or "kiosk").strip(),
        status=status,
        message=(payload.get("message") or "").strip(),
        retry_queue_count=payload.get("retry_queue_count") or 0,
    )
    if item is None:
        return api_response("error", "Device health table is unavailable.", errors=["table_not_ready"], http_status=503)
    return api_response("success", "Device health logged.", data={"id": item.id, "device_code": item.device_code}, http_status=201)


@bp.route("/api/ai/assist", methods=["POST"])
@login_required
def api_ai_assist():
    payload = request.get_json(silent=True) or {}
    prompt = (payload.get("prompt") or "").strip()
    if not prompt:
        return api_response("error", "Prompt is required.", errors=["prompt is required"], http_status=400)
    execute = bool(payload.get("execute", False))
    result = run_ai_assistant(prompt=prompt, requested_by_user_id=current_user.id, execute=execute)
    if result.get("error"):
        return api_response("error", "AI assistant is not ready yet.", errors=[result["error"]], http_status=503)
    return api_response("success", "AI assistant completed.", data=result, http_status=201)
