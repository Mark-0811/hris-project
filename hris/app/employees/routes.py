from datetime import date

from flask import flash, redirect, render_template, send_file, url_for
from flask_login import current_user, login_required

from . import bp
from .forms import DepartmentForm, EmployeeBulkImportForm, EmployeeForm, PositionForm, ShiftForm
from .services import (
    get_active_shift_assignment,
    list_departments,
    list_employees,
    list_manager_candidates,
    list_positions,
    list_shifts,
    save_department,
    save_employee,
    save_position,
    save_shift,
    toggle_employee_active,
)
from ..models import AttendanceRecord, Department, Employee, Position, Shift
from ..utils.excel_bulk import build_employee_import_template, parse_employee_import
from ..utils.constants import ADMIN_ROLES
from ..utils.decorators import role_required


def populate_department_form(form):
    form.manager_id.choices = [(0, "No manager assigned")] + [
        (employee.id, f"{employee.employee_code} - {employee.full_name}")
        for employee in list_employees()
    ]


def populate_position_form(form):
    form.department_id.choices = [
        (department.id, f"{department.code} - {department.name}") for department in list_departments()
    ]


def populate_employee_form(form):
    form.department_id.choices = [(0, "No department assigned")] + [
        (department.id, f"{department.code} - {department.name}") for department in list_departments()
    ]
    form.position_id.choices = [(0, "No position assigned")] + [
        (position.id, position.name) for position in list_positions()
    ]
    form.manager_id.choices = [(0, "No manager assigned")] + [
        (employee.id, f"{employee.employee_code} - {employee.full_name}")
        for employee in list_manager_candidates()
    ]
    form.shift_id.choices = [(0, "Default office shift (8:30 AM to 5:30 PM)")] + [
        (
            shift.id,
            f"{shift.shift_name} ({shift.start_time.strftime('%I:%M %p')} to {shift.end_time.strftime('%I:%M %p')})",
        )
        for shift in list_shifts()
    ]


def validate_employee_uniques(form, employee=None):
    duplicate_checks = [
        ("personal_email", "Personal email"),
        ("company_email", "Company email"),
        ("sss_no", "SSS number"),
        ("tin_no", "TIN number"),
        ("philhealth_no", "PhilHealth number"),
        ("pagibig_no", "Pag-IBIG number"),
        ("badge_id", "Badge ID"),
        ("nfc_uid", "NFC UID"),
    ]

    for field_name, label in duplicate_checks:
        raw_value = getattr(form, field_name).data
        value = raw_value.strip() if isinstance(raw_value, str) else raw_value
        if not value:
            continue

        query = Employee.query.filter(getattr(Employee, field_name) == value)
        if employee is not None:
            query = query.filter(Employee.id != employee.id)
        if query.first():
            getattr(form, field_name).errors.append(f"{label} is already assigned to another employee.")

    if form.manager_id.data and employee and form.manager_id.data == employee.id:
        form.manager_id.errors.append("An employee cannot be their own manager.")

    return not any(getattr(form, field_name).errors for field_name, _label in duplicate_checks) and not form.manager_id.errors


@bp.route("/")
@login_required
@role_required(*ADMIN_ROLES)
def index():
    return redirect(url_for("employees.list_employee"))


@bp.route("/departments")
@login_required
@role_required(*ADMIN_ROLES)
def list_department():
    return render_template("employees/departments/index.html", departments=list_departments())


@bp.route("/departments/create", methods=["GET", "POST"])
@login_required
@role_required(*ADMIN_ROLES)
def create_department():
    form = DepartmentForm()
    populate_department_form(form)
    if form.validate_on_submit():
        existing_code = Department.query.filter_by(code=form.code.data.strip().upper()).first()
        existing_name = Department.query.filter_by(name=form.name.data.strip()).first()
        if existing_code:
            form.code.errors.append("Department code already exists.")
        elif existing_name:
            form.name.errors.append("Department name already exists.")
        else:
            save_department(form)
            flash("Department created successfully.", "success")
            return redirect(url_for("employees.list_department"))

    return render_template("employees/departments/form.html", form=form, page_title="Create Department")


@bp.route("/departments/<int:department_id>/edit", methods=["GET", "POST"])
@login_required
@role_required(*ADMIN_ROLES)
def edit_department(department_id: int):
    department = Department.query.get_or_404(department_id)
    form = DepartmentForm(obj=department)
    populate_department_form(form)
    if not form.is_submitted():
        form.manager_id.data = department.manager_id or 0

    if form.validate_on_submit():
        existing_code = Department.query.filter(
            Department.code == form.code.data.strip().upper(), Department.id != department.id
        ).first()
        existing_name = Department.query.filter(
            Department.name == form.name.data.strip(), Department.id != department.id
        ).first()
        if existing_code:
            form.code.errors.append("Department code already exists.")
        elif existing_name:
            form.name.errors.append("Department name already exists.")
        else:
            save_department(form, department=department)
            flash("Department updated successfully.", "success")
            return redirect(url_for("employees.list_department"))

    return render_template(
        "employees/departments/form.html",
        form=form,
        page_title="Edit Department",
        department=department,
    )


@bp.route("/positions")
@login_required
@role_required(*ADMIN_ROLES)
def list_position():
    return render_template("employees/positions/index.html", positions=list_positions())


@bp.route("/positions/create", methods=["GET", "POST"])
@login_required
@role_required(*ADMIN_ROLES)
def create_position():
    form = PositionForm()
    populate_position_form(form)
    if form.validate_on_submit():
        existing_position = Position.query.filter_by(
            department_id=form.department_id.data, name=form.name.data.strip()
        ).first()
        if existing_position:
            form.name.errors.append("Position already exists in this department.")
        else:
            save_position(form)
            flash("Position created successfully.", "success")
            return redirect(url_for("employees.list_position"))

    return render_template("employees/positions/form.html", form=form, page_title="Create Position")


@bp.route("/positions/<int:position_id>/edit", methods=["GET", "POST"])
@login_required
@role_required(*ADMIN_ROLES)
def edit_position(position_id: int):
    position = Position.query.get_or_404(position_id)
    form = PositionForm(obj=position)
    populate_position_form(form)
    if not form.is_submitted():
        form.department_id.data = position.department_id

    if form.validate_on_submit():
        existing_position = Position.query.filter(
            Position.department_id == form.department_id.data,
            Position.name == form.name.data.strip(),
            Position.id != position.id,
        ).first()
        if existing_position:
            form.name.errors.append("Position already exists in this department.")
        else:
            save_position(form, position=position)
            flash("Position updated successfully.", "success")
            return redirect(url_for("employees.list_position"))

    return render_template(
        "employees/positions/form.html",
        form=form,
        page_title="Edit Position",
        position=position,
    )


@bp.route("/schedules")
@login_required
@role_required(*ADMIN_ROLES)
def list_schedule():
    return render_template("employees/schedules/index.html", schedules=list_shifts())


@bp.route("/schedules/create", methods=["GET", "POST"])
@login_required
@role_required(*ADMIN_ROLES)
def create_schedule():
    form = ShiftForm()
    if form.validate_on_submit():
        existing_shift = Shift.query.filter_by(shift_name=form.shift_name.data.strip()).first()
        if existing_shift:
            form.shift_name.errors.append("Schedule name already exists.")
        else:
            save_shift(form)
            flash("Schedule created successfully.", "success")
            return redirect(url_for("employees.list_schedule"))

    return render_template("employees/schedules/form.html", form=form, page_title="Create Schedule")


@bp.route("/schedules/<int:shift_id>/edit", methods=["GET", "POST"])
@login_required
@role_required(*ADMIN_ROLES)
def edit_schedule(shift_id: int):
    shift = Shift.query.get_or_404(shift_id)
    form = ShiftForm(obj=shift)
    if form.validate_on_submit():
        existing_shift = Shift.query.filter(
            Shift.shift_name == form.shift_name.data.strip(),
            Shift.id != shift.id,
        ).first()
        if existing_shift:
            form.shift_name.errors.append("Schedule name already exists.")
        else:
            save_shift(form, shift=shift)
            flash("Schedule updated successfully.", "success")
            return redirect(url_for("employees.list_schedule"))

    return render_template(
        "employees/schedules/form.html",
        form=form,
        page_title="Edit Schedule",
        shift=shift,
    )


@bp.route("/list")
@login_required
@role_required(*ADMIN_ROLES)
def list_employee():
    return render_template("employees/index.html", employees=list_employees())


@bp.route("/import/template")
@login_required
@role_required(*ADMIN_ROLES)
def download_employee_import_template():
    return send_file(
        build_employee_import_template(),
        as_attachment=True,
        download_name="hris_employee_import_template.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@bp.route("/import", methods=["GET", "POST"])
@login_required
@role_required(*ADMIN_ROLES)
def import_employees():
    form = EmployeeBulkImportForm()
    result = None
    if form.validate_on_submit():
        result = parse_employee_import(form.workbook.data)
        flash(
            f"Employee import completed. Created {result.created} employee(s), {len(result.errors)} issue(s).",
            "success" if not result.errors else "warning",
        )
    return render_template(
        "employees/bulk_import.html",
        form=form,
        result=result,
        page_title="Import Employees",
        modal_intro="Upload an Excel file to create many employees in one pass.",
        template_url=url_for("employees.download_employee_import_template"),
        cancel_url=url_for("employees.list_employee"),
    )


@bp.route("/create", methods=["GET", "POST"])
@login_required
@role_required(*ADMIN_ROLES)
def create_employee():
    form = EmployeeForm()
    populate_employee_form(form)
    if form.validate_on_submit():
        if validate_employee_uniques(form):
            save_employee(form)
            flash("Employee created successfully.", "success")
            return redirect(url_for("employees.list_employee"))

    return render_template("employees/form.html", form=form, page_title="Create Employee")


@bp.route("/<int:employee_id>")
@login_required
def detail_employee(employee_id: int):
    employee = Employee.query.get_or_404(employee_id)
    today_record = (
        AttendanceRecord.query.filter_by(employee_id=employee.id, date=date.today())
        .order_by(AttendanceRecord.id.desc())
        .first()
    )
    recent_attendance = (
        AttendanceRecord.query.filter_by(employee_id=employee.id)
        .order_by(AttendanceRecord.date.desc(), AttendanceRecord.id.desc())
        .limit(7)
        .all()
    )
    today_status = "absent" if today_record is None else today_record.status
    return render_template(
        "employees/detail.html",
        employee=employee,
        active_shift=get_active_shift_assignment(employee),
        today_attendance=today_record,
        today_status=today_status,
        recent_attendance=recent_attendance,
    )


@bp.route("/<int:employee_id>/edit", methods=["GET", "POST"])
@login_required
@role_required(*ADMIN_ROLES)
def edit_employee(employee_id: int):
    employee = Employee.query.get_or_404(employee_id)
    form = EmployeeForm(obj=employee)
    populate_employee_form(form)
    if not form.is_submitted():
        form.department_id.data = employee.department_id or 0
        form.position_id.data = employee.position_id or 0
        form.manager_id.data = employee.manager_id or 0
        active_shift = get_active_shift_assignment(employee)
        form.shift_id.data = active_shift.shift_id if active_shift else 0

    if form.validate_on_submit():
        if validate_employee_uniques(form, employee=employee):
            save_employee(form, employee=employee)
            flash("Employee updated successfully.", "success")
            return redirect(url_for("employees.detail_employee", employee_id=employee.id))

    return render_template(
        "employees/form.html",
        form=form,
        employee=employee,
        page_title="Edit Employee",
    )


@bp.route("/<int:employee_id>/toggle", methods=["POST"])
@login_required
@role_required(*ADMIN_ROLES)
def toggle_employee(employee_id: int):
    employee = Employee.query.get_or_404(employee_id)
    if current_user.employee_id and employee.id == current_user.employee_id:
        flash("You cannot disable your own employee profile while you are logged in.", "warning")
        return redirect(url_for("employees.list_employee"))
    new_status = toggle_employee_active(employee)
    flash(
        f"Employee {'enabled' if new_status == 'active' else 'disabled'} successfully.",
        "success",
    )
    return redirect(url_for("employees.list_employee"))
