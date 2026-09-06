from datetime import date, datetime

from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from . import bp
from .forms import AttendanceAdjustmentForm, AttendanceRecordForm, KioskPunchForm
from .services import (
    approve_adjustment,
    attendance_summary,
    detect_attendance_anomalies,
    find_employee_by_identifier,
    list_attendance_anomalies,
    list_today_attendance_board,
    list_employee_attendance_records,
    list_attendance_adjustments,
    list_attendance_records,
    process_employee_punch,
    save_attendance_adjustment,
    save_attendance_record,
    serialize_employee_preview,
    serialize_record,
)
from ..extensions import socketio
from ..models import AttendanceRecord, Employee
from ..utils.decorators import role_required

ATTENDANCE_ADMIN_ROLES = ("Super Admin", "HR Admin", "Manager")


def emit_attendance_update(record, message: str):
    socketio.emit(
        "attendance_updated",
        {
            "employee_id": record.employee_id,
            "record": serialize_record(record),
            "message": message,
        },
        namespace="/attendance-live",
    )


def populate_record_form(form):
    form.employee_id.choices = [
        (employee.id, f"{employee.employee_code} - {employee.full_name}")
        for employee in Employee.query.order_by(Employee.last_name.asc(), Employee.first_name.asc()).all()
    ]


def populate_adjustment_form(form):
    form.attendance_record_id.choices = [
        (record.id, f"{record.employee.full_name} · {record.date}")
        for record in list_attendance_records()
    ]


@bp.route("/")
@login_required
def index():
    if current_user.role and current_user.role.name == "Employee" and current_user.employee_id:
        return render_template(
            "attendance/my_logs.html",
            records=list_employee_attendance_records(current_user.employee_id),
            employee=current_user.employee,
        )
    return render_template(
        "attendance/index.html",
        summary=attendance_summary(),
        records=list_today_attendance_board(),
        adjustments=list_attendance_adjustments(),
    )


@bp.route("/anomalies")
@login_required
@role_required(*ATTENDANCE_ADMIN_ROLES)
def anomalies():
    return render_template(
        "attendance/anomalies.html",
        summary=attendance_summary(),
        anomalies=list_attendance_anomalies(),
    )


@bp.route("/anomalies/scan", methods=["POST"])
@login_required
@role_required(*ATTENDANCE_ADMIN_ROLES)
def scan_anomalies():
    result = detect_attendance_anomalies(days_back=30)
    flash(
        f"Anomaly scan completed. New: {result['created']}, Existing: {result['existing']}.",
        "success",
    )
    return redirect(url_for("attendance.anomalies"))


@bp.route("/records/create", methods=["GET", "POST"])
@login_required
@role_required(*ATTENDANCE_ADMIN_ROLES)
def create_record():
    form = AttendanceRecordForm()
    populate_record_form(form)
    if form.validate_on_submit():
        record = save_attendance_record(form)
        emit_attendance_update(record, "Attendance record saved successfully.")
        flash("Attendance record saved successfully.", "success")
        return redirect(url_for("attendance.index"))

    return render_template("attendance/form.html", form=form, page_title="Create Attendance Record")


@bp.route("/records/<int:record_id>/edit", methods=["GET", "POST"])
@login_required
@role_required(*ATTENDANCE_ADMIN_ROLES)
def edit_record(record_id: int):
    record = AttendanceRecord.query.get_or_404(record_id)
    form = AttendanceRecordForm(obj=record)
    populate_record_form(form)
    if not form.is_submitted():
        form.employee_id.data = record.employee_id
    if form.validate_on_submit():
        record = save_attendance_record(form, record=record)
        emit_attendance_update(record, "Attendance record updated successfully.")
        flash("Attendance record updated successfully.", "success")
        return redirect(url_for("attendance.index"))

    return render_template("attendance/form.html", form=form, page_title="Edit Attendance Record")


@bp.route("/adjustments/create", methods=["GET", "POST"])
@login_required
def create_adjustment():
    form = AttendanceAdjustmentForm()
    populate_adjustment_form(form)
    if form.validate_on_submit():
        save_attendance_adjustment(form, current_user.id)
        flash("Attendance adjustment submitted.", "success")
        return redirect(url_for("attendance.index"))

    return render_template("attendance/adjustment_form.html", form=form)


@bp.route("/my-logs")
@login_required
def my_logs():
    employee = current_user.employee
    records = list_employee_attendance_records(employee.id) if employee else []
    return render_template("attendance/my_logs.html", records=records, employee=employee)


@bp.route("/kiosk", methods=["GET"])
def kiosk():
    form = KioskPunchForm()
    return render_template("attendance/kiosk.html", form=form)


@bp.route("/adjustments/<int:adjustment_id>/approve", methods=["GET", "POST"])
@login_required
@role_required(*ATTENDANCE_ADMIN_ROLES)
def approve(adjustment_id: int):
    if request.method == "GET":
        return render_template(
            "confirm_action.html",
            page_title="Confirm Attendance Adjustment Approval",
            modal_intro="Approve this attendance adjustment after reviewing the requested correction.",
            confirm_heading="Approve attendance adjustment",
            confirm_message="This will update the related attendance record using the approved correction.",
            confirm_button_label="Approve Adjustment",
            form_action=url_for("attendance.approve", adjustment_id=adjustment_id),
            hidden_fields={},
            cancel_url=url_for("attendance.index"),
        )
    adjustment = approve_adjustment(adjustment_id, current_user.id)
    if adjustment and adjustment.attendance_record:
        emit_attendance_update(adjustment.attendance_record, "Attendance adjustment approved.")
    flash("Attendance adjustment approved.", "success")
    return redirect(url_for("attendance.index"))


@bp.route("/api/summary")
@login_required
def api_summary():
    return jsonify(attendance_summary())


@bp.route("/api/records", methods=["GET", "POST"])
@login_required
def api_records():
    if request.method == "GET":
        return jsonify([serialize_record(record) for record in list_attendance_records()])

    payload = request.get_json(silent=True) or {}
    record = AttendanceRecord(
        employee_id=payload["employee_id"],
        date=datetime.fromisoformat(payload["date"]).date(),
        late_minutes=payload.get("late_minutes", 0),
        undertime_minutes=payload.get("undertime_minutes", 0),
        overtime_minutes=payload.get("overtime_minutes", 0),
        status=payload.get("status", "present"),
        remarks=payload.get("remarks"),
    )
    from ..extensions import db

    db.session.add(record)
    db.session.commit()
    emit_attendance_update(record, "Attendance record saved successfully.")
    return jsonify(serialize_record(record)), 201


@bp.route("/api/punch", methods=["POST"])
def api_punch():
    payload = request.get_json(silent=True) or {}
    identifier = payload.get("identifier")
    source = payload.get("source", "manual")
    action = payload.get("action", "auto")
    if not identifier:
        return jsonify({"message": "identifier is required"}), 400

    record, message = process_employee_punch(identifier, source, action)
    if record is None:
        return jsonify({"message": message}), 404

    emit_attendance_update(record, message)
    return jsonify({"message": message, "record": serialize_record(record)})


@bp.route("/api/employee-lookup")
def api_employee_lookup():
    identifier = (request.args.get("identifier") or "").strip()
    if not identifier:
        return jsonify({"employee": None})

    employee = find_employee_by_identifier(identifier)
    return jsonify({"employee": serialize_employee_preview(employee)})
