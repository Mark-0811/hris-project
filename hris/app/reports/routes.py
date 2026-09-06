from datetime import datetime

from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from . import bp
from .services import (
    available_reports,
    build_report_payload,
    create_filter_preset,
    create_report_schedule,
    list_filter_presets_for_user,
    list_report_schedules_for_user,
    preset_filters,
    scheduler_summary_for_user,
)


@bp.route("/")
@login_required
def index():
    filters = {}
    department_id = (request.args.get("department_id") or "").strip()
    status = (request.args.get("status") or "").strip()
    date_from_raw = (request.args.get("date_from") or "").strip()
    date_to_raw = (request.args.get("date_to") or "").strip()
    if department_id:
        filters["department_id"] = department_id
    if status:
        filters["status"] = status
    if date_from_raw:
        try:
            filters["date_from"] = datetime.fromisoformat(date_from_raw).date()
        except ValueError:
            pass
    if date_to_raw:
        try:
            filters["date_to"] = datetime.fromisoformat(date_to_raw).date()
        except ValueError:
            pass
    payload = build_report_payload(current_user, filters=filters)
    return render_template("reports/index.html", available=available_reports(), payload=payload, filters=filters)


@bp.route("/api")
@login_required
def api_reports():
    payload = build_report_payload(current_user)
    return jsonify(
        {
            "summary": payload["summary"],
            "employee_scope": payload["employee_scope"],
            "employees": [
                {
                    "employee_code": employee.employee_code,
                    "full_name": employee.full_name,
                    "department": employee.department.name if employee.department else None,
                    "position": employee.position.name if employee.position else None,
                    "status": employee.employment_status,
                }
                for employee in payload["employees"]
            ],
            "attendance": [
                {
                    "employee_name": row.employee.full_name if row.employee else None,
                    "date": row.date.isoformat(),
                    "status": row.status,
                    "late_minutes": row.late_minutes,
                    "overtime_minutes": row.overtime_minutes,
                }
                for row in payload["attendance"]
            ],
            "leave": [
                {
                    "employee_name": row.employee.full_name if row.employee else None,
                    "leave_type": row.leave_type.name if row.leave_type else None,
                    "status": row.status,
                    "days": float(row.days),
                }
                for row in payload["leave"]
            ],
            "payroll": [
                {
                    "employee_name": row.employee.full_name if row.employee else None,
                    "cutoff": row.cutoff.cutoff_name if row.cutoff else None,
                    "net_pay": float(row.net_pay),
                    "status": row.status,
                }
                for row in payload["payroll"]
            ],
        }
    )


@bp.route("/scheduler", methods=["GET", "POST"])
@login_required
def scheduler():
    if request.method == "POST":
        action = (request.form.get("action") or "").strip()
        if action == "create_preset":
            preset_name = (request.form.get("preset_name") or "").strip()
            if not preset_name:
                flash("Preset name is required.", "warning")
            else:
                filters = {
                    "department_id": (request.form.get("department_id") or "").strip(),
                    "status": (request.form.get("status") or "").strip(),
                    "date_from": (request.form.get("date_from") or "").strip(),
                    "date_to": (request.form.get("date_to") or "").strip(),
                }
                create_filter_preset(current_user, preset_name, "all", filters)
                flash("Report filter preset saved.", "success")
            return redirect(url_for("reports.scheduler"))
        if action == "create_schedule":
            schedule_name = (request.form.get("schedule_name") or "").strip()
            delivery_target = (request.form.get("delivery_target") or "").strip()
            cadence = (request.form.get("cadence") or "daily").strip()
            preset_id_raw = (request.form.get("preset_id") or "").strip()
            preset_id = int(preset_id_raw) if preset_id_raw.isdigit() else None
            if not schedule_name or not delivery_target:
                flash("Schedule name and delivery target are required.", "warning")
            else:
                create_report_schedule(
                    current_user,
                    schedule_name,
                    "all",
                    delivery_target,
                    cadence,
                    preset_id,
                )
                flash("Report schedule created.", "success")
            return redirect(url_for("reports.scheduler"))

    presets = list_filter_presets_for_user(current_user)
    schedules = list_report_schedules_for_user(current_user)
    return render_template(
        "reports/scheduler.html",
        presets=presets,
        schedules=schedules,
        preset_filters=preset_filters,
        summary=scheduler_summary_for_user(current_user),
    )
