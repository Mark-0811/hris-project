import json
from datetime import datetime, timedelta

from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError, ProgrammingError

from ..extensions import db
from ..models import (
    AttendanceRecord,
    Department,
    Employee,
    LeaveRequest,
    PayrollEntry,
    ReportFilterPreset,
    ReportSchedule,
)
from ..utils.constants import ROLE_EMPLOYEE


def available_reports():
    return [
        "employee_master_list",
        "attendance_report",
        "leave_report",
        "payroll_summary",
    ]


def _table_exists(table_name: str) -> bool:
    try:
        return inspect(db.engine).has_table(table_name)
    except Exception:
        return False


def _safe_list(table_name: str, query_fn):
    if not _table_exists(table_name):
        return []
    try:
        return query_fn()
    except (ProgrammingError, OperationalError):
        db.session.rollback()
        return []


def _safe_count(table_name: str, query_fn) -> int:
    if not _table_exists(table_name):
        return 0
    try:
        return int(query_fn())
    except (ProgrammingError, OperationalError):
        db.session.rollback()
        return 0


def build_report_payload(user=None, filters: dict | None = None):
    filters = filters or {}
    is_employee_scope = bool(
        user
        and getattr(user, "role", None)
        and user.role.name == ROLE_EMPLOYEE
        and getattr(user, "employee_id", None)
    )

    employee_query = Employee.query.order_by(Employee.last_name.asc())
    attendance_query = AttendanceRecord.query.order_by(AttendanceRecord.date.desc())
    leave_query = LeaveRequest.query.order_by(LeaveRequest.created_at.desc())
    payroll_query = PayrollEntry.query.order_by(PayrollEntry.created_at.desc())

    department_id = filters.get("department_id")
    status = filters.get("status")
    date_from = filters.get("date_from")
    date_to = filters.get("date_to")

    if is_employee_scope:
        employee_query = employee_query.filter(Employee.id == user.employee_id)
        attendance_query = attendance_query.filter(AttendanceRecord.employee_id == user.employee_id)
        leave_query = leave_query.filter(LeaveRequest.employee_id == user.employee_id)
        payroll_query = payroll_query.filter(PayrollEntry.employee_id == user.employee_id)
    else:
        if department_id:
            employee_query = employee_query.filter(Employee.department_id == int(department_id))
        if status:
            employee_query = employee_query.filter(Employee.employment_status == status)

    if date_from:
        attendance_query = attendance_query.filter(AttendanceRecord.date >= date_from)
        leave_query = leave_query.filter(LeaveRequest.start_date >= date_from)
    if date_to:
        attendance_query = attendance_query.filter(AttendanceRecord.date <= date_to)
        leave_query = leave_query.filter(LeaveRequest.end_date <= date_to)

    employee_rows = employee_query.all()
    attendance_rows = attendance_query.limit(20).all()
    leave_rows = leave_query.limit(20).all()
    payroll_rows = payroll_query.limit(20).all()

    summary = {
        "employees": employee_query.count(),
        "departments": Department.query.count() if not is_employee_scope else len({row.department_id for row in employee_rows if row.department_id}),
        "attendance_records": attendance_query.count(),
        "pending_leave_requests": leave_query.filter_by(status="pending").count(),
        "payroll_entries": payroll_query.count(),
    }
    return {
        "summary": summary,
        "employees": employee_rows,
        "attendance": attendance_rows,
        "leave": leave_rows,
        "payroll": payroll_rows,
        "employee_scope": is_employee_scope,
        "filters": filters,
    }


def list_filter_presets_for_user(user):
    if not user or not getattr(user, "is_authenticated", False):
        return []
    return _safe_list(
        ReportFilterPreset.__tablename__,
        lambda: ReportFilterPreset.query.filter_by(user_id=user.id).order_by(ReportFilterPreset.name.asc()).all(),
    )


def create_filter_preset(user, name: str, report_type: str, filters: dict):
    if not user or not getattr(user, "is_authenticated", False):
        return None
    if not _table_exists(ReportFilterPreset.__tablename__):
        return None
    preset = ReportFilterPreset(
        user_id=user.id,
        name=name.strip(),
        report_type=report_type or "all",
        filters_json=json.dumps(filters or {}),
    )
    db.session.add(preset)
    db.session.commit()
    return preset


def preset_filters(preset: ReportFilterPreset | None) -> dict:
    if not preset:
        return {}
    try:
        return json.loads(preset.filters_json or "{}")
    except Exception:
        return {}


def list_report_schedules_for_user(user):
    if not user or not getattr(user, "is_authenticated", False):
        return []
    return _safe_list(
        ReportSchedule.__tablename__,
        lambda: ReportSchedule.query.filter_by(user_id=user.id).order_by(ReportSchedule.created_at.desc()).all(),
    )


def create_report_schedule(user, name: str, report_type: str, delivery_target: str, cadence: str, preset_id: int | None):
    if not user or not getattr(user, "is_authenticated", False):
        return None
    if not _table_exists(ReportSchedule.__tablename__):
        return None
    next_run = datetime.utcnow() + timedelta(days=1)
    if cadence == "weekly":
        next_run = datetime.utcnow() + timedelta(days=7)
    schedule = ReportSchedule(
        user_id=user.id,
        name=name.strip(),
        report_type=report_type,
        preset_id=preset_id,
        delivery_target=delivery_target.strip(),
        cadence=cadence,
        next_run_at=next_run,
        delivery_channel="email",
    )
    db.session.add(schedule)
    db.session.commit()
    return schedule


def scheduler_summary_for_user(user):
    return {
        "presets": _safe_count(
            ReportFilterPreset.__tablename__,
            lambda: ReportFilterPreset.query.filter_by(user_id=user.id).count(),
        )
        if user and getattr(user, "is_authenticated", False)
        else 0,
        "schedules": _safe_count(
            ReportSchedule.__tablename__,
            lambda: ReportSchedule.query.filter_by(user_id=user.id).count(),
        )
        if user and getattr(user, "is_authenticated", False)
        else 0,
    }
