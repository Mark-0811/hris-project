from datetime import date

import pytest

from hris.app import create_app
from hris.app.extensions import db
from hris.app.models import (
    Announcement,
    AttendanceRecord,
    Department,
    Employee,
    EmployeeShift,
    LeaveRequest,
    LeaveType,
    Position,
    Role,
    Shift,
    User,
)
from hris.app.seed import seed_roles_and_permissions, seed_reference_data
from hris.app.utils.constants import ROLE_EMPLOYEE, ROLE_HR_ADMIN, ROLE_SUPER_ADMIN


@pytest.fixture
def app():
    app = create_app("testing")
    app.config.update(
        SECRET_KEY="test-secret",
        BIOMETRIC_API_TOKEN="test-biometric-token",
        FIRST_SUPERADMIN_USERNAME="superadmin",
        FIRST_SUPERADMIN_EMAIL="superadmin@example.com",
        FIRST_SUPERADMIN_PASSWORD="ChangeMe123!",
    )

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


@pytest.fixture
def seeded_data(app):
    with app.app_context():
        seed_roles_and_permissions()
        seed_reference_data()

        hr_role = Role.query.filter_by(name=ROLE_HR_ADMIN).first()
        employee_role = Role.query.filter_by(name=ROLE_EMPLOYEE).first()

        department = Department.query.filter_by(code="HR").first()
        position = Position.query.filter_by(name="HR Administrator").first()

        admin_employee = Employee(
            employee_code="EMP-00001",
            first_name="Alice",
            last_name="Admin",
            badge_id="BADGE-0001",
            nfc_uid="NFC-ADMIN-001",
            date_hired=date(2024, 1, 1),
            employment_status="active",
            department=department,
            position=position,
        )
        staff_employee = Employee(
            employee_code="EMP-00002",
            first_name="Evan",
            last_name="Employee",
            badge_id="BADGE-0002",
            nfc_uid="NFC-EMP-002",
            date_hired=date(2024, 1, 15),
            employment_status="active",
            department=department,
            position=position,
        )
        db.session.add_all([admin_employee, staff_employee])
        db.session.flush()

        admin_user = User(
            username="hradmin",
            email="hradmin@example.com",
            role=hr_role,
            employee=admin_employee,
            is_active=True,
            force_password_change=False,
        )
        admin_user.set_password("Password123!")

        employee_user = User(
            username="employee1",
            email="employee1@example.com",
            role=employee_role,
            employee=staff_employee,
            is_active=True,
            force_password_change=False,
        )
        employee_user.set_password("Password123!")

        inactive_user = User(
            username="inactive",
            email="inactive@example.com",
            role=employee_role,
            is_active=False,
            force_password_change=False,
        )
        inactive_user.set_password("Password123!")

        db.session.add_all([admin_user, employee_user, inactive_user])
        db.session.flush()
        db.session.add(
            Announcement(
                title="Welcome to HRIS",
                body="Your HR dashboard is now live.",
                posted_by=admin_user.id,
                is_active=True,
            )
        )
        leave_type = LeaveType.query.filter_by(name="Vacation Leave").first()
        db.session.add(
            LeaveRequest(
                employee=admin_employee,
                leave_type_id=leave_type.id,
                start_date=date(2025, 1, 10),
                end_date=date(2025, 1, 10),
                days=1,
                reason="Medical",
                status="pending",
            )
        )
        db.session.add(
            AttendanceRecord(
                employee=admin_employee,
                date=date.today(),
                status="present",
            )
        )
        seed_reference_data()
        db.session.commit()

        return {
            "admin_user": admin_user,
            "employee_user": employee_user,
            "inactive_user": inactive_user,
            "department": department,
            "position": position,
            "admin_employee": admin_employee,
            "staff_employee": staff_employee,
            "default_shift": Shift.query.filter_by(shift_name="Default Office Shift").first(),
            "default_shift_assignments": EmployeeShift.query.count(),
        }


def login(client, username="hradmin", password="Password123!"):
    return client.post(
        "/auth/login",
        data={"username": username, "password": password, "remember_me": "y"},
        follow_redirects=True,
    )
