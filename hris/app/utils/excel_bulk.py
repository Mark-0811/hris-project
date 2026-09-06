from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from io import BytesIO

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font

from ..extensions import db
from ..models import Department, Employee, MenuAccessTemplate, Position, Role, Shift, User
from ..utils.helpers import generate_next_employee_code
from ..utils.menu_access import apply_template_to_user, seed_user_menu_access


@dataclass
class BulkImportResult:
    created: int
    errors: list[str]


def _sheet_headers(sheet) -> dict[str, int]:
    headers = {}
    for index, cell in enumerate(sheet[1], start=1):
        value = str(cell.value or "").strip()
        if value:
            headers[value] = index
    return headers


def _cell_value(row, headers: dict[str, int], key: str):
    index = headers.get(key)
    if not index:
        return None
    return row[index - 1].value


def _string(value) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _bool(value, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "enabled", "active"}


def _date(value):
    if value in (None, ""):
        return None
    if hasattr(value, "date"):
        return value.date()
    return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()


def _autosize_columns(sheet):
    for column in sheet.columns:
        max_length = 0
        letter = column[0].column_letter
        for cell in column:
            max_length = max(max_length, len(str(cell.value or "")))
        sheet.column_dimensions[letter].width = min(max(max_length + 2, 14), 28)


def _workbook_response_bytes(workbook: Workbook) -> BytesIO:
    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer


def build_employee_import_template() -> BytesIO:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Employees"
    headers = [
        "employee_code",
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
        "department_code",
        "position_name",
        "manager_employee_code",
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
        "shift_name",
    ]
    sheet.append(headers)
    sheet.append([
        "EMP-01000",
        "Maria",
        "Santos",
        "Dela Cruz",
        "",
        "1995-01-14",
        "female",
        "single",
        "Quezon City",
        "09171234567",
        "maria.personal@example.com",
        "maria@company.com",
        "IT",
        "PROGRAMMER",
        "",
        "regular",
        "2026-04-01",
        "",
        "active",
        "",
        "",
        "",
        "",
        "",
        "Ana Cruz",
        "09170000000",
        "BADGE-1000",
        "NFC-1000",
        "Default Office Shift",
    ])
    for cell in sheet[1]:
        cell.font = Font(bold=True)

    notes = workbook.create_sheet("Instructions")
    notes.append(["Column", "Notes"])
    instructions = [
        ("employee_code", "Optional. Leave blank to auto-generate."),
        ("first_name / last_name", "Required."),
        ("date_hired", "Required. Use YYYY-MM-DD."),
        ("employment_status", "Required. Example: active, probationary, inactive, resigned."),
        ("department_code", "Must match an existing department code."),
        ("position_name", "Optional. Must match an existing position name if provided."),
        ("manager_employee_code", "Optional. Must match an existing employee code."),
        ("shift_name", "Optional. Must match an existing shift name."),
    ]
    for row in instructions:
        notes.append(row)
    for cell in notes[1]:
        cell.font = Font(bold=True)
    _autosize_columns(sheet)
    _autosize_columns(notes)
    return _workbook_response_bytes(workbook)


def build_user_import_template() -> BytesIO:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Users"
    headers = [
        "username",
        "email",
        "role_name",
        "employee_code",
        "temporary_password",
        "is_active",
        "force_password_change",
        "can_access_api",
        "menu_template_name",
        "photo_filename",
    ]
    sheet.append(headers)
    sheet.append([
        "maria.user",
        "maria@company.com",
        "Employee",
        "EMP-01000",
        "TempPass123!",
        "yes",
        "yes",
        "no",
        "",
        "",
    ])
    for cell in sheet[1]:
        cell.font = Font(bold=True)

    notes = workbook.create_sheet("Instructions")
    notes.append(["Column", "Notes"])
    instructions = [
        ("username / email / role_name / temporary_password", "Required."),
        ("employee_code", "Optional, but recommended to link to an employee."),
        ("role_name", "Must match an existing role exactly."),
        ("menu_template_name", "Optional. Applies a saved access template after user creation."),
        ("photo_filename", "Optional existing file name from static/uploads/users."),
    ]
    for row in instructions:
        notes.append(row)
    for cell in notes[1]:
        cell.font = Font(bold=True)
    _autosize_columns(sheet)
    _autosize_columns(notes)
    return _workbook_response_bytes(workbook)


def parse_employee_import(file_storage) -> BulkImportResult:
    from ..employees.services import ensure_employee_shift

    workbook = load_workbook(file_storage, data_only=True)
    sheet = workbook.active
    headers = _sheet_headers(sheet)
    errors: list[str] = []
    created = 0

    for row_number, row in enumerate(sheet.iter_rows(min_row=2), start=2):
        if all(cell.value in (None, "") for cell in row):
            continue
        try:
            first_name = _string(_cell_value(row, headers, "first_name"))
            last_name = _string(_cell_value(row, headers, "last_name"))
            date_hired = _date(_cell_value(row, headers, "date_hired"))
            employment_status = _string(_cell_value(row, headers, "employment_status")) or "active"
            if not first_name or not last_name or not date_hired:
                raise ValueError("first_name, last_name, and date_hired are required.")

            employee_code = _string(_cell_value(row, headers, "employee_code")) or generate_next_employee_code()
            if Employee.query.filter_by(employee_code=employee_code).first():
                raise ValueError(f"Employee code '{employee_code}' already exists.")

            department = None
            department_code = _string(_cell_value(row, headers, "department_code"))
            if department_code:
                department = Department.query.filter_by(code=department_code.upper()).first()
                if department is None:
                    raise ValueError(f"Department code '{department_code}' was not found.")

            position = None
            position_name = _string(_cell_value(row, headers, "position_name"))
            if position_name:
                query = Position.query.filter_by(name=position_name)
                if department:
                    query = query.filter_by(department_id=department.id)
                position = query.first()
                if position is None:
                    raise ValueError(f"Position '{position_name}' was not found.")

            manager = None
            manager_code = _string(_cell_value(row, headers, "manager_employee_code"))
            if manager_code:
                manager = Employee.query.filter_by(employee_code=manager_code).first()
                if manager is None:
                    raise ValueError(f"Manager employee code '{manager_code}' was not found.")

            shift = None
            shift_name = _string(_cell_value(row, headers, "shift_name"))
            if shift_name:
                shift = Shift.query.filter_by(shift_name=shift_name).first()
                if shift is None:
                    raise ValueError(f"Shift '{shift_name}' was not found.")

            employee = Employee(
                employee_code=employee_code,
                first_name=first_name,
                middle_name=_string(_cell_value(row, headers, "middle_name")),
                last_name=last_name,
                suffix=_string(_cell_value(row, headers, "suffix")),
                birthdate=_date(_cell_value(row, headers, "birthdate")),
                gender=_string(_cell_value(row, headers, "gender")),
                civil_status=_string(_cell_value(row, headers, "civil_status")),
                address=_string(_cell_value(row, headers, "address")),
                contact_number=_string(_cell_value(row, headers, "contact_number")),
                personal_email=_string(_cell_value(row, headers, "personal_email")),
                company_email=_string(_cell_value(row, headers, "company_email")),
                department_id=department.id if department else None,
                position_id=position.id if position else None,
                manager_id=manager.id if manager else None,
                employment_type=_string(_cell_value(row, headers, "employment_type")),
                date_hired=date_hired,
                date_regularized=_date(_cell_value(row, headers, "date_regularized")),
                employment_status=employment_status,
                sss_no=_string(_cell_value(row, headers, "sss_no")),
                tin_no=_string(_cell_value(row, headers, "tin_no")),
                philhealth_no=_string(_cell_value(row, headers, "philhealth_no")),
                pagibig_no=_string(_cell_value(row, headers, "pagibig_no")),
                profile_image=_string(_cell_value(row, headers, "profile_image")),
                emergency_contact_name=_string(_cell_value(row, headers, "emergency_contact_name")),
                emergency_contact_number=_string(_cell_value(row, headers, "emergency_contact_number")),
                badge_id=_string(_cell_value(row, headers, "badge_id")),
                nfc_uid=_string(_cell_value(row, headers, "nfc_uid")),
            )
            db.session.add(employee)
            db.session.flush()
            ensure_employee_shift(employee, shift.id if shift else None)
            db.session.commit()
            created += 1
        except Exception as exc:
            db.session.rollback()
            errors.append(f"Row {row_number}: {exc}")

    return BulkImportResult(created=created, errors=errors)


def parse_user_import(file_storage, actor_user_id: int | None = None) -> BulkImportResult:
    workbook = load_workbook(file_storage, data_only=True)
    sheet = workbook.active
    headers = _sheet_headers(sheet)
    errors: list[str] = []
    created = 0

    for row_number, row in enumerate(sheet.iter_rows(min_row=2), start=2):
        if all(cell.value in (None, "") for cell in row):
            continue
        try:
            username = _string(_cell_value(row, headers, "username"))
            email = _string(_cell_value(row, headers, "email"))
            role_name = _string(_cell_value(row, headers, "role_name"))
            password = _string(_cell_value(row, headers, "temporary_password"))
            if not username or not email or not role_name or not password:
                raise ValueError("username, email, role_name, and temporary_password are required.")
            if User.query.filter_by(username=username).first():
                raise ValueError(f"Username '{username}' already exists.")
            if User.query.filter_by(email=email.lower()).first():
                raise ValueError(f"Email '{email}' already exists.")

            role = Role.query.filter_by(name=role_name).first()
            if role is None:
                raise ValueError(f"Role '{role_name}' was not found.")

            employee = None
            employee_code = _string(_cell_value(row, headers, "employee_code"))
            if employee_code:
                employee = Employee.query.filter_by(employee_code=employee_code).first()
                if employee is None:
                    raise ValueError(f"Employee code '{employee_code}' was not found.")
                if User.query.filter_by(employee_id=employee.id).first():
                    raise ValueError(f"Employee code '{employee_code}' is already linked to another user.")

            template_name = _string(_cell_value(row, headers, "menu_template_name"))
            template = None
            if template_name:
                template = MenuAccessTemplate.query.filter_by(name=template_name).first()
                if template is None:
                    raise ValueError(f"Menu template '{template_name}' was not found.")

            user = User(
                username=username,
                email=email.lower(),
                role_id=role.id,
                employee_id=employee.id if employee else None,
                is_active=_bool(_cell_value(row, headers, "is_active"), default=True),
                force_password_change=_bool(_cell_value(row, headers, "force_password_change"), default=True),
                can_access_api=_bool(_cell_value(row, headers, "can_access_api"), default=False),
                photo_filename=_string(_cell_value(row, headers, "photo_filename")),
            )
            user.set_password(password)
            if user.can_access_api:
                user.ensure_api_token()
            db.session.add(user)
            db.session.flush()
            user.menu_access_initialized = False
            db.session.commit()

            if template:
                apply_template_to_user(user, template, actor_user_id=actor_user_id)
            else:
                seed_user_menu_access(user)

            created += 1
        except Exception as exc:
            db.session.rollback()
            errors.append(f"Row {row_number}: {exc}")

    return BulkImportResult(created=created, errors=errors)
