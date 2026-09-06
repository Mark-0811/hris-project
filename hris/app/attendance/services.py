from datetime import date, datetime, time, timedelta

from flask import url_for

from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError, ProgrammingError

from ..extensions import db
from ..models import AttendanceAdjustment, AttendanceAnomaly, AttendanceRecord, BiometricLog, Employee
from ..employees.services import get_active_shift_assignment


def classify_punch_window(punch_time):
    if punch_time.hour < 12:
        return "time_in"
    return "time_out"


def _table_exists(table_name: str) -> bool:
    try:
        return inspect(db.engine).has_table(table_name)
    except Exception:
        return False


def list_attendance_records():
    return (
        AttendanceRecord.query.order_by(AttendanceRecord.date.desc(), AttendanceRecord.id.desc()).all()
    )


def list_today_attendance_board():
    today = date.today()
    records = (
        AttendanceRecord.query.filter_by(date=today)
        .order_by(AttendanceRecord.id.desc())
        .all()
    )
    latest_by_employee = {}
    for record in records:
        latest_by_employee.setdefault(record.employee_id, record)

    rows = []
    for employee in Employee.query.order_by(Employee.last_name.asc(), Employee.first_name.asc()).all():
        record = latest_by_employee.get(employee.id)
        if record:
            apply_attendance_policy(record)
        today_status = determine_today_status(employee, record, today=today)
        rows.append(
            {
                "employee": employee,
                "date": today,
                "record": record,
                "time_in": record.time_in if record else None,
                "time_out": record.time_out if record else None,
                "late_minutes": record.late_minutes if record else 0,
                "undertime_minutes": record.undertime_minutes if record else 0,
                "is_absent": today_status == "absent",
                "today_status": today_status,
            }
        )
    return rows


def list_employee_attendance_records(employee_id: int):
    return (
        AttendanceRecord.query.filter_by(employee_id=employee_id)
        .order_by(AttendanceRecord.date.desc(), AttendanceRecord.id.desc())
        .all()
    )


def list_attendance_adjustments():
    return AttendanceAdjustment.query.order_by(AttendanceAdjustment.created_at.desc()).all()


def attendance_summary():
    today = date.today()
    records = AttendanceRecord.query.filter_by(date=today).all()
    for record in records:
        apply_attendance_policy(record)
    db.session.flush()
    anomalies_open = 0
    if _table_exists(AttendanceAnomaly.__tablename__):
        try:
            anomalies_open = AttendanceAnomaly.query.filter_by(status="open").count()
        except (ProgrammingError, OperationalError):
            db.session.rollback()
            anomalies_open = 0
    return {
        "records_today": len(records),
        "present_today": sum(1 for record in records if record.status in {"present", "late", "undertime"}),
        "pending_adjustments": AttendanceAdjustment.query.filter_by(status="pending").count(),
        "employees": Employee.query.count(),
        "open_anomalies": anomalies_open,
    }


def detect_attendance_anomalies(days_back: int = 30) -> dict:
    if not _table_exists(AttendanceAnomaly.__tablename__):
        return {"created": 0, "existing": 0}

    start_date = date.today() - timedelta(days=max(1, days_back))
    records = (
        AttendanceRecord.query.filter(AttendanceRecord.date >= start_date)
        .order_by(AttendanceRecord.date.desc(), AttendanceRecord.employee_id.asc())
        .all()
    )
    existing = 0
    created = 0

    daily_counts: dict[tuple[int, date], int] = {}
    for row in records:
        key = (row.employee_id, row.date)
        daily_counts[key] = daily_counts.get(key, 0) + 1

    for row in records:
        candidates = []
        if row.time_in and not row.time_out and row.date < date.today():
            candidates.append(("missed_time_out", "high", 0.9, "Timed in but missing time-out on a past date."))
        if row.time_out and not row.time_in:
            candidates.append(("missing_time_in", "high", 0.95, "Timed out without a valid time-in."))
        if (row.overtime_minutes or 0) >= 240:
            candidates.append(("unusual_overtime", "medium", 0.75, "Overtime exceeds 4 hours."))
        if daily_counts.get((row.employee_id, row.date), 0) > 1:
            candidates.append(("duplicate_record", "medium", 0.7, "Multiple attendance records were created for the same day."))

        for anomaly_type, severity, score, details in candidates:
            found = AttendanceAnomaly.query.filter_by(
                attendance_record_id=row.id,
                anomaly_type=anomaly_type,
            ).first()
            if found:
                existing += 1
                continue
            db.session.add(
                AttendanceAnomaly(
                    attendance_record_id=row.id,
                    employee_id=row.employee_id,
                    date=row.date,
                    anomaly_type=anomaly_type,
                    severity=severity,
                    score=score,
                    status="open",
                    details=details,
                )
            )
            created += 1

    db.session.commit()
    return {"created": created, "existing": existing}


def list_attendance_anomalies(limit: int = 200):
    if not _table_exists(AttendanceAnomaly.__tablename__):
        return []
    try:
        return (
            AttendanceAnomaly.query.order_by(AttendanceAnomaly.date.desc(), AttendanceAnomaly.created_at.desc())
            .limit(limit)
            .all()
        )
    except (ProgrammingError, OperationalError):
        db.session.rollback()
        return []


def _minutes_between(start_dt, end_dt):
    if not start_dt or not end_dt:
        return 0
    if end_dt < start_dt:
        end_dt = end_dt + timedelta(days=1)
    return max(0, int((end_dt - start_dt).total_seconds() // 60))


def _combine_shift_datetime(record_date, clock_value: time):
    return datetime.combine(record_date, clock_value)


def _resolve_shift_window(record_date, start_time: time, end_time: time):
    start_dt = _combine_shift_datetime(record_date, start_time)
    end_dt = _combine_shift_datetime(record_date, end_time)
    if end_dt <= start_dt:
        end_dt += timedelta(days=1)
    return start_dt, end_dt


def _get_break_minutes(record, shift):
    if record.break_out and record.break_in:
        return _minutes_between(record.break_out, record.break_in)
    if shift and shift.break_start and shift.break_end:
        break_start, break_end = _resolve_shift_window(record.date, shift.break_start, shift.break_end)
        return _minutes_between(
            break_start,
            break_end,
        )
    return 60


def apply_attendance_policy(record: AttendanceRecord):
    employee = record.employee or db.session.get(Employee, record.employee_id)
    if not employee:
        return record

    assignment = get_active_shift_assignment(employee, on_date=record.date)
    shift = assignment.shift if assignment else None
    if not shift:
        return record

    break_minutes = _get_break_minutes(record, shift)

    if record.time_in:
        if shift.is_flexible:
            record.late_minutes = 0
            if record.status not in {"absent", "incomplete"}:
                record.status = "present"
        else:
            shift_start = _combine_shift_datetime(record.date, shift.start_time)
            grace_limit = shift_start + timedelta(minutes=shift.grace_period_minutes or 0)
            if record.time_in <= grace_limit:
                record.late_minutes = 0
                if record.status not in {"absent", "incomplete"}:
                    record.status = "present"
            else:
                record.late_minutes = _minutes_between(shift_start, record.time_in)
                if record.status not in {"absent", "incomplete"}:
                    record.status = "late"
    else:
        if _scheduled_start_has_passed(record, shift):
            record.status = "absent"

    if record.time_in and record.time_out:
        worked_minutes = max(0, _minutes_between(record.time_in, record.time_out) - break_minutes)
        if shift.is_flexible:
            target_minutes = 8 * 60
            record.undertime_minutes = max(0, target_minutes - worked_minutes)
            record.overtime_minutes = max(0, worked_minutes - target_minutes)
        else:
            shift_start, shift_end = _resolve_shift_window(record.date, shift.start_time, shift.end_time)
            scheduled_minutes = _minutes_between(shift_start, shift_end)
            target_minutes = max(0, scheduled_minutes - break_minutes)
            undertime_threshold = shift_end - timedelta(minutes=shift.grace_period_minutes or 0)
            if record.time_out >= undertime_threshold:
                record.undertime_minutes = 0
            else:
                record.undertime_minutes = max(0, _minutes_between(record.time_out, shift_end))
            record.overtime_minutes = max(0, worked_minutes - target_minutes)

        if record.undertime_minutes > 0 and record.status not in {"absent", "incomplete"}:
            record.status = "undertime" if record.late_minutes == 0 else "late"
        elif record.late_minutes == 0 and record.status not in {"absent", "incomplete"}:
            record.status = "present"
    elif record.time_in and record.time_out is None:
        record.status = "incomplete"
    return record


def _scheduled_start_has_passed(record: AttendanceRecord, shift) -> bool:
    if shift.is_flexible:
        return False
    shift_start = _combine_shift_datetime(record.date, shift.start_time)
    grace_limit = shift_start + timedelta(minutes=shift.grace_period_minutes or 0)
    return datetime.now() >= grace_limit


def determine_today_status(employee: Employee, record: AttendanceRecord | None, today: date | None = None) -> str:
    today = today or date.today()
    if record:
        apply_attendance_policy(record)
        return record.status or "present"

    assignment = get_active_shift_assignment(employee, on_date=today)
    shift = assignment.shift if assignment else None
    if shift and not shift.is_flexible:
        shift_start = _combine_shift_datetime(today, shift.start_time)
        grace_limit = shift_start + timedelta(minutes=shift.grace_period_minutes or 0)
        if datetime.now() >= grace_limit:
            return "absent"
    return "pending"


def save_attendance_record(form, record=None):
    if record is None:
        record = AttendanceRecord()
        db.session.add(record)

    record.employee_id = form.employee_id.data
    record.date = form.date.data
    record.time_in = form.time_in.data
    record.time_out = form.time_out.data
    record.break_in = form.break_in.data
    record.break_out = form.break_out.data
    record.late_minutes = form.late_minutes.data or 0
    record.undertime_minutes = form.undertime_minutes.data or 0
    record.overtime_minutes = form.overtime_minutes.data or 0
    record.status = form.status.data
    record.remarks = form.remarks.data.strip() if form.remarks.data else None
    db.session.flush()
    apply_attendance_policy(record)
    db.session.commit()
    return record


def save_attendance_adjustment(form, requested_by_id: int):
    record = db.session.get(AttendanceRecord, form.attendance_record_id.data)
    adjustment = AttendanceAdjustment(
        employee_id=record.employee_id,
        attendance_record_id=record.id,
        requested_by=requested_by_id,
        reason=form.reason.data.strip(),
        old_time_in=record.time_in,
        new_time_in=form.new_time_in.data,
        old_time_out=record.time_out,
        new_time_out=form.new_time_out.data,
        status="pending",
    )
    db.session.add(adjustment)
    db.session.commit()
    return adjustment


def approve_adjustment(adjustment_id: int, approved_by_id: int):
    adjustment = db.session.get(AttendanceAdjustment, adjustment_id)
    if adjustment is None:
        return None

    adjustment.status = "approved"
    adjustment.approved_by = approved_by_id
    if adjustment.new_time_in:
        adjustment.attendance_record.time_in = adjustment.new_time_in
    if adjustment.new_time_out:
        adjustment.attendance_record.time_out = adjustment.new_time_out
    adjustment.attendance_record.status = "approved"
    apply_attendance_policy(adjustment.attendance_record)
    db.session.commit()
    return adjustment


def employee_photo_url(employee):
    photo_url = None
    if employee:
        if employee.user and employee.user.photo_url:
            photo_url = employee.user.photo_url
        elif employee.profile_image:
            if employee.profile_image.startswith(("http://", "https://", "/")):
                photo_url = employee.profile_image
            else:
                photo_url = url_for("static", filename=employee.profile_image)
    return photo_url


def serialize_employee_preview(employee):
    if employee is None:
        return None
    return {
        "employee_id": employee.id,
        "employee_name": employee.full_name,
        "employee_code": employee.employee_code,
        "employee_photo_url": employee_photo_url(employee),
        "employee_department": employee.department.name if employee.department else None,
        "employee_position": employee.position.name if employee.position else None,
        "employee_status_label": employee.status_label,
    }


def serialize_record(record):
    employee = record.employee
    return {
        "id": record.id,
        "employee_id": record.employee_id,
        "employee_name": employee.full_name if employee else None,
        "employee_code": employee.employee_code if employee else None,
        "employee_photo_url": employee_photo_url(employee),
        "employee_department": employee.department.name if employee and employee.department else None,
        "employee_position": employee.position.name if employee and employee.position else None,
        "employee_status_label": employee.status_label if employee else None,
        "date": record.date.isoformat(),
        "time_in": record.time_in.isoformat() if record.time_in else None,
        "time_out": record.time_out.isoformat() if record.time_out else None,
        "late_minutes": record.late_minutes,
        "undertime_minutes": record.undertime_minutes,
        "overtime_minutes": record.overtime_minutes,
        "status": record.status,
        "remarks": record.remarks,
    }


def find_employee_by_identifier(identifier: str):
    identifier = identifier.strip()
    return Employee.query.filter(
        (Employee.employee_code == identifier)
        | (Employee.badge_id == identifier)
        | (Employee.nfc_uid == identifier)
    ).first()


def process_employee_punch(identifier: str, source: str = "manual", action: str = "auto"):
    employee = find_employee_by_identifier(identifier)
    if employee is None:
        return None, "Employee identifier not found."

    action = (action or "auto").strip().lower()
    if action not in {"auto", "time_in", "time_out"}:
        return None, "Unsupported punch action."

    today = date.today()
    current_record = (
        AttendanceRecord.query.filter_by(employee_id=employee.id, date=today)
        .order_by(AttendanceRecord.id.desc())
        .first()
    )

    if current_record is None:
        current_record = AttendanceRecord(
            employee_id=employee.id,
            date=today,
            status="present",
        )
        db.session.add(current_record)
        db.session.flush()

    resolved_action = action
    if action == "auto":
        resolved_action = "time_in" if current_record.time_in is None or current_record.time_out else "time_out"

    if resolved_action == "time_in" and current_record.time_in is None:
        current_record.time_in = db.func.now()
        current_record.status = "present"
        message = f"{employee.full_name} timed in successfully."
    elif resolved_action == "time_out" and current_record.time_in and current_record.time_out is None:
        current_record.time_out = db.func.now()
        current_record.status = "present"
        message = f"{employee.full_name} timed out successfully."
    elif resolved_action == "time_in" and current_record.time_in and current_record.time_out is None:
        return None, f"{employee.full_name} is already timed in for today."
    elif resolved_action == "time_out" and current_record.time_in is None:
        return None, f"{employee.full_name} must time in before timing out."
    elif resolved_action == "time_out" and current_record.time_out is not None:
        return None, f"{employee.full_name} is already timed out for today."
    else:
        follow_up_record = AttendanceRecord(
            employee_id=employee.id,
            date=today,
            time_in=db.func.now(),
            status="present",
            remarks="New attendance entry started after completed record.",
        )
        db.session.add(follow_up_record)
        current_record = follow_up_record
        resolved_action = "time_in"
        message = f"{employee.full_name} started a new attendance entry."

    biometric_log = BiometricLog(
        employee_id=employee.id,
        punch_time=db.func.now(),
        punch_type=resolved_action,
        raw_data=identifier,
        source=source,
    )
    db.session.add(biometric_log)
    db.session.flush()
    apply_attendance_policy(current_record)
    db.session.commit()
    db.session.refresh(current_record)
    return current_record, message
