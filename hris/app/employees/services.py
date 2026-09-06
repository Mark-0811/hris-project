from datetime import date, timedelta

from sqlalchemy import func

from ..extensions import db
from ..models import Department, Employee, EmployeeShift, Position, Shift
from ..utils.helpers import generate_next_employee_code

DEFAULT_SHIFT_NAME = "Default Office Shift"


def get_employee_by_code(employee_code: str):
    return Employee.query.filter_by(employee_code=employee_code).first()


def list_departments():
    return Department.query.order_by(Department.name.asc()).all()


def list_positions():
    return Position.query.order_by(Position.name.asc()).all()


def list_employees():
    return Employee.query.order_by(Employee.last_name.asc(), Employee.first_name.asc()).all()


def list_manager_candidates():
    return (
        Employee.query.join(Position, Employee.position_id == Position.id)
        .filter(func.lower(Position.name).like("%manager%"))
        .order_by(Employee.last_name.asc(), Employee.first_name.asc())
        .all()
    )


def list_shifts():
    return Shift.query.order_by(Shift.shift_name.asc()).all()


def get_default_shift():
    return Shift.query.filter_by(shift_name=DEFAULT_SHIFT_NAME).first()


def get_active_shift_assignment(employee: Employee, on_date: date | None = None):
    target_date = on_date or date.today()
    return (
        employee.shift_assignments.filter(EmployeeShift.effective_date <= target_date)
        .filter((EmployeeShift.end_date.is_(None)) | (EmployeeShift.end_date >= target_date))
        .order_by(EmployeeShift.effective_date.desc(), EmployeeShift.id.desc())
        .first()
    )


def ensure_employee_shift(employee: Employee, shift_id: int | None):
    if not shift_id:
        default_shift = get_default_shift()
        shift_id = default_shift.id if default_shift else None

    if not shift_id:
        return None

    active_assignment = get_active_shift_assignment(employee)
    if active_assignment and active_assignment.shift_id == shift_id:
        return active_assignment

    effective_date = employee.date_hired or date.today()
    if active_assignment:
        active_assignment.end_date = max(date.today() - timedelta(days=1), active_assignment.effective_date)
        effective_date = date.today()

    new_assignment = EmployeeShift(
        employee=employee,
        shift_id=shift_id,
        effective_date=effective_date,
    )
    db.session.add(new_assignment)
    return new_assignment


def save_department(form, department=None):
    if department is None:
        department = Department()
        db.session.add(department)

    department.name = form.name.data.strip()
    department.code = form.code.data.strip().upper()
    department.manager_id = form.manager_id.data or None
    department.branch = form.branch.data.strip() if form.branch.data else None
    department.cost_center = form.cost_center.data.strip() if form.cost_center.data else None
    db.session.commit()
    return department


def save_position(form, position=None):
    if position is None:
        position = Position()
        db.session.add(position)

    position.name = form.name.data.strip()
    position.department_id = form.department_id.data
    position.description = form.description.data.strip() if form.description.data else None
    db.session.commit()
    return position


def save_shift(form, shift=None):
    if shift is None:
        shift = Shift()
        db.session.add(shift)

    shift.shift_name = form.shift_name.data.strip()
    shift.start_time = form.start_time.data
    shift.end_time = form.end_time.data
    shift.grace_period_minutes = form.grace_period_minutes.data or 0
    shift.break_start = form.break_start.data
    shift.break_end = form.break_end.data
    shift.is_flexible = bool(form.is_flexible.data)
    db.session.commit()
    return shift


def save_employee(form, employee=None):
    if employee is None:
        employee = Employee(employee_code=generate_next_employee_code())
        db.session.add(employee)

    for field_name in (
        "first_name",
        "middle_name",
        "last_name",
        "suffix",
        "birthdate",
        "gender",
        "civil_status",
        "address",
        "contact_number",
        "personal_email",
        "company_email",
        "employment_type",
        "date_hired",
        "date_regularized",
        "employment_status",
        "sss_no",
        "tin_no",
        "philhealth_no",
        "pagibig_no",
        "profile_image",
        "emergency_contact_name",
        "emergency_contact_number",
        "badge_id",
        "nfc_uid",
    ):
        value = getattr(form, field_name).data
        if isinstance(value, str):
            value = value.strip() or None
        setattr(employee, field_name, value)

    employee.department_id = form.department_id.data or None
    employee.position_id = form.position_id.data or None
    employee.manager_id = form.manager_id.data or None
    db.session.flush()
    ensure_employee_shift(employee, form.shift_id.data or None)
    db.session.commit()
    return employee


def toggle_employee_active(employee: Employee) -> str:
    employee.employment_status = "inactive" if employee.employment_status == "active" else "active"
    db.session.commit()
    return employee.employment_status
