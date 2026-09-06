from datetime import date, datetime
import io
from openpyxl import Workbook

from hris.app.extensions import db
from hris.app.extensions import mail, socketio
from hris.app.payroll.services import generate_payroll_for_cutoff
from hris.app.models import (
    Announcement,
    AttendanceRecord,
    ChatMessage,
    ChatThread,
    Department,
    Employee,
    EmployeeProfileUpdateRequest,
    EmployeeSalary,
    EmployeeShift,
    ExitInterview,
    HrTicket,
    LeaveBalance,
    LeaveRequest,
    LeaveType,
    Notification,
    PayrollCutoff,
    PayrollEntry,
    Permission,
    Position,
    PrivacyRequest,
    PulseSurvey,
    Role,
    Shift,
    SurveyResponse,
    RolePermission,
    User,
)

from .conftest import login


def create_super_admin(app, username="superadmin_test", email="superadmin_test@example.com", password="Password123!"):
    with app.app_context():
        role = Role.query.filter_by(name="Super Admin").first()
        user = User(
            username=username,
            email=email,
            role=role,
            is_active=True,
            force_password_change=False,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return username, password


def test_app_factory_uses_testing_config(app):
    assert app.config["TESTING"] is True
    assert app.config["WTF_CSRF_ENABLED"] is False
    assert app.config["CONFIG_NAME"] == "testing"


def test_login_and_logout_flow(client, seeded_data):
    response = login(client)
    assert response.status_code == 200
    assert b"Welcome back." in response.data
    assert b"HRIS Dashboard" in response.data

    logout_response = client.get("/auth/logout", follow_redirects=True)
    assert logout_response.status_code == 200
    assert b"You have been logged out." in logout_response.data


def test_inactive_user_cannot_log_in(client, seeded_data):
    response = login(client, username="inactive")
    assert b"Invalid username or password." in response.data


def test_forgot_password_sends_reset_email_and_allows_password_reset(client, app, seeded_data):
    with app.app_context():
        with mail.record_messages() as outbox:
            response = client.post(
                "/auth/forgot-password",
                data={"email": "employee1@example.com"},
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"password reset link has been sent" in response.data
            assert len(outbox) == 1
            body = outbox[0].body
            reset_link = next(line.strip() for line in body.splitlines() if "/auth/reset-password/" in line)

    token = reset_link.rsplit("/", 1)[-1]
    reset_response = client.post(
        f"/auth/reset-password/{token}",
        data={"new_password": "NewPassword123!", "confirm_password": "NewPassword123!"},
        follow_redirects=True,
    )
    assert reset_response.status_code == 200
    assert b"Your password has been reset successfully" in reset_response.data

    login_response = login(client, username="employee1", password="NewPassword123!")
    assert login_response.status_code == 200
    assert b"My Attendance" in login_response.data


def test_role_protected_route_access(client, seeded_data):
    login(client, username="employee1")
    response = client.get("/users")
    assert response.status_code == 403
    assert b"Access denied" in response.data


def test_employee_login_redirects_to_own_logs(client, seeded_data):
    response = login(client, username="employee1")
    assert response.status_code == 200
    assert b"My Workspace" in response.data
    assert b"Evan Employee" in response.data


def test_authenticated_user_can_view_profile_page(client, seeded_data):
    login(client, username="employee1")
    response = client.get("/auth/profile")
    assert response.status_code == 200
    assert b"My Profile" in response.data
    assert b"Evan Employee" in response.data
    assert b"Account Information" in response.data


def test_employee_workspace_pages_render(client, seeded_data):
    login(client, username="employee1")

    workspace = client.get("/me/")
    schedule = client.get("/me/schedule")
    requests_page = client.get("/me/requests")
    documents_page = client.get("/me/documents")
    learning_page = client.get("/me/learning")
    surveys_page = client.get("/me/surveys")

    assert workspace.status_code == 200
    assert b"My Workspace" in workspace.data
    assert schedule.status_code == 200
    assert b"Mobile Punch" in schedule.data
    assert requests_page.status_code == 200
    assert b"Leave request wizard" in requests_page.data
    assert documents_page.status_code == 200
    assert b"Document locker" in documents_page.data
    assert learning_page.status_code == 200
    assert b"Assigned learning and certifications" in learning_page.data
    assert surveys_page.status_code == 200
    assert b"Pulse surveys" in surveys_page.data


def test_employee_can_submit_support_ticket_and_privacy_request(client, app, seeded_data):
    login(client, username="employee1")

    ticket_response = client.post(
        "/me/requests",
        data={
            "ticket-category": "benefits",
            "ticket-subject": "Benefits concern",
            "ticket-description": "Need help reviewing a benefits item.",
            "ticket-priority": "normal",
            "ticket-submit": "1",
        },
        follow_redirects=True,
    )
    assert ticket_response.status_code == 200
    assert b"HR request submitted." in ticket_response.data

    privacy_response = client.post(
        "/me/requests",
        data={
            "privacy-request_type": "data_access",
            "privacy-details": "Please share the HR data stored for my account.",
            "privacy-submit": "1",
        },
        follow_redirects=True,
    )
    assert privacy_response.status_code == 200
    assert b"Privacy request submitted." in privacy_response.data

    with app.app_context():
        employee = Employee.query.filter_by(employee_code="EMP-00002").first()
        assert HrTicket.query.filter_by(employee_id=employee.id, category="benefits").count() == 1
        assert PrivacyRequest.query.filter_by(employee_id=employee.id, request_type="data_access").count() == 1


def test_employee_can_submit_survey_response_and_exit_request(client, app, seeded_data):
    login(client, username="employee1")

    with app.app_context():
        survey = PulseSurvey.query.filter_by(title="Weekly Employee Pulse").first()
        assert survey is not None

    survey_response = client.post(
        f"/me/surveys/{survey.id}/respond",
        data={
            "survey-survey_id": str(survey.id),
            "survey-sentiment_score": "4",
            "survey-feedback": "The new workspace is easier to follow.",
        },
        follow_redirects=True,
    )
    assert survey_response.status_code == 200
    assert b"Survey response submitted." in survey_response.data

    exit_response = client.post(
        "/me/exit",
        data={
            "resignation_date": "2026-04-01",
            "last_day": "2026-04-30",
            "reason": "Career growth",
            "interview_notes": "Happy to support a clean handoff.",
        },
        follow_redirects=True,
    )
    assert exit_response.status_code == 200
    assert b"Exit request submitted." in exit_response.data

    with app.app_context():
        employee = Employee.query.filter_by(employee_code="EMP-00002").first()
        assert SurveyResponse.query.filter_by(employee_id=employee.id, survey_id=survey.id).count() == 1
        assert ExitInterview.query.filter_by(employee_id=employee.id).count() == 1


def test_employee_can_submit_profile_update_request(client, app, seeded_data):
    login(client, username="employee1", password="Password123!")
    response = client.post(
        "/auth/profile",
        data={
            "birthdate": "1995-04-20",
            "gender": "female",
            "civil_status": "single",
            "address": "123 Updated Address",
            "emergency_contact_name": "Jane Emergency",
            "reason": "Moved to a new address.",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"submitted for verification" in response.data

    with app.app_context():
        employee_user = User.query.filter_by(username="employee1").first()
        request_obj = EmployeeProfileUpdateRequest.query.filter_by(user_id=employee_user.id).first()
        assert request_obj is not None
        assert request_obj.status == "pending"
        assert Notification.query.filter_by(type="profile_update_request").count() >= 1


def test_admin_can_approve_profile_update_request(client, app, seeded_data):
    with app.app_context():
        employee_user = User.query.filter_by(username="employee1").first()
        employee = employee_user.employee
        employee.personal_email = "locked@example.com"
        employee.contact_number = "09170000000"
        request_obj = EmployeeProfileUpdateRequest(
            user_id=employee_user.id,
            employee_id=employee.id,
            requested_data_json='{"birthdate":"1994-01-15","gender":"female","civil_status":"married","address":"45 New Street","emergency_contact_name":"Jamie Contact"}',
            reason="Need updated records",
        )
        db.session.add(request_obj)
        db.session.commit()
        request_id = request_obj.id
        employee_id = employee.id

    login(client, username="hradmin", password="Password123!")
    response = client.post(
        f"/users/profile-update-requests/{request_id}/review",
        data={"decision": "approve"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Profile update request approved." in response.data

    with app.app_context():
        employee = db.session.get(Employee, employee_id)
        request_obj = db.session.get(EmployeeProfileUpdateRequest, request_id)
        assert request_obj.status == "approved"
        assert employee.address == "45 New Street"
        assert employee.emergency_contact_name == "Jamie Contact"
        assert employee.personal_email == "locked@example.com"
        assert employee.contact_number == "09170000000"


def test_super_admin_can_approve_profile_update_and_admins_get_notified(client, app, seeded_data):
    username, password = create_super_admin(app, username="profile_super", email="profile_super@example.com")

    login(client, username="employee1", password="Password123!")
    request_response = client.post(
        "/auth/profile",
        data={
            "birthdate": "1996-03-18",
            "gender": "female",
            "civil_status": "single",
            "address": "789 Admin Review Avenue",
            "emergency_contact_name": "Morgan Contact",
            "reason": "Updating profile details for records.",
        },
        follow_redirects=True,
    )
    assert request_response.status_code == 200

    with app.app_context():
        employee_user = User.query.filter_by(username="employee1").first()
        request_obj = EmployeeProfileUpdateRequest.query.filter_by(user_id=employee_user.id).order_by(EmployeeProfileUpdateRequest.id.desc()).first()
        hr_admin = User.query.filter_by(username="hradmin").first()
        super_admin = User.query.filter_by(username=username).first()
        request_id = request_obj.id

        request_notifications = Notification.query.filter_by(type="profile_update_request").all()
        assert {item.user_id for item in request_notifications} >= {hr_admin.id, super_admin.id}

    client.get("/auth/logout", follow_redirects=True)
    login(client, username=username, password=password)
    approve_response = client.post(
        f"/users/profile-update-requests/{request_id}/review",
        data={"decision": "approve"},
        follow_redirects=True,
    )
    assert approve_response.status_code == 200
    assert b"Profile update request approved." in approve_response.data

    with app.app_context():
        hr_admin = User.query.filter_by(username="hradmin").first()
        super_admin = User.query.filter_by(username=username).first()
        status_notifications = Notification.query.filter_by(type="profile_update_status").all()
        assert {item.user_id for item in status_notifications} >= {employee_user.id, hr_admin.id, super_admin.id}


def test_live_notification_endpoint_includes_new_profile_requests(client, app, seeded_data):
    username, password = create_super_admin(app, username="notify_super", email="notify_super@example.com")

    login(client, username="employee1", password="Password123!")
    client.post(
        "/auth/profile",
        data={
            "birthdate": "1997-01-05",
            "gender": "female",
            "civil_status": "single",
            "address": "Realtime Notification Street",
            "emergency_contact_name": "Realtime Contact",
            "reason": "Testing live bell notification.",
        },
        follow_redirects=True,
    )

    client.get("/auth/logout", follow_redirects=True)
    login(client, username=username, password=password)
    response = client.get("/notifications/live")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["count"] >= 1
    assert any(item["type"] == "profile_update_request" for item in payload["items"])


def test_kiosk_page_renders_enhanced_ui(client, seeded_data):
    response = client.get("/attendance/kiosk")
    assert response.status_code == 200
    assert b"Last Punch Result" in response.data
    assert b"Ready for next punch" in response.data
    assert b"Waiting for employee" in response.data
    assert b"Employee Code" in response.data


def test_kiosk_employee_lookup_returns_employee_preview(client, seeded_data):
    response = client.get("/attendance/api/employee-lookup?identifier=EMP-00002")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["employee"]["employee_name"] == "Evan Employee"
    assert payload["employee"]["employee_code"] == "EMP-00002"


def test_user_import_template_download(client, seeded_data):
    login(client)
    response = client.get("/users/import/template")
    assert response.status_code == 200
    assert "hris_user_import_template.xlsx" in response.headers["Content-Disposition"]


def test_employee_bulk_import_creates_employee(client, app, seeded_data):
    login(client)
    workbook = Workbook()
    sheet = workbook.active
    sheet.append([
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
    ])
    sheet.append([
        "EMP-00999",
        "Rica",
        "",
        "Template",
        "",
        "",
        "female",
        "single",
        "",
        "",
        "",
        "rica.template@example.com",
        "HR",
        "HR Administrator",
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
        "",
        "",
        "",
        "",
        "Default Office Shift",
    ])
    payload = io.BytesIO()
    workbook.save(payload)
    payload.seek(0)

    response = client.post(
        "/employees/import",
        data={"workbook": (payload, "employees.xlsx")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        assert Employee.query.filter_by(employee_code="EMP-00999").first() is not None


def test_user_bulk_import_creates_user(client, app, seeded_data):
    login(client)
    workbook = Workbook()
    sheet = workbook.active
    sheet.append([
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
    ])
    sheet.append([
        "template.user",
        "template.user@example.com",
        "Employee",
        "",
        "TempPass123!",
        "yes",
        "yes",
        "no",
        "",
        "",
    ])
    payload = io.BytesIO()
    workbook.save(payload)
    payload.seek(0)

    response = client.post(
        "/users/import",
        data={"workbook": (payload, "users.xlsx")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        user = User.query.filter_by(username="template.user").first()
        assert user is not None
        assert user.email == "template.user@example.com"


def test_leave_approve_route_get_shows_confirmation_instead_of_405(client, app, seeded_data):
    login(client)
    with app.app_context():
        employee = Employee.query.filter_by(employee_code="EMP-00002").first()
        leave_type = LeaveType.query.filter_by(name="Vacation Leave").first()
        request_obj = LeaveRequest(
            employee_id=employee.id,
            leave_type_id=leave_type.id,
            start_date=date(2025, 6, 1),
            end_date=date(2025, 6, 1),
            days=1,
            reason="Confirmation screen test",
            status="pending",
        )
        db.session.add(request_obj)
        db.session.commit()
        request_id = request_obj.id

    response = client.get(f"/leave/requests/{request_id}/approve")
    assert response.status_code == 200
    assert b"Approve leave request" in response.data


def test_profile_request_review_get_shows_confirmation_instead_of_405(client, app, seeded_data):
    login(client)
    with app.app_context():
        employee_user = User.query.filter_by(username="employee1").first()
        request_obj = EmployeeProfileUpdateRequest(
            user_id=employee_user.id,
            employee_id=employee_user.employee_id,
            requested_data_json='{"birthdate":"1994-01-15","gender":"female","civil_status":"married","address":"45 New Street","emergency_contact_name":"Jamie Contact"}',
            reason="Approval page fallback test",
        )
        db.session.add(request_obj)
        db.session.commit()
        request_id = request_obj.id

    response = client.get(f"/users/profile-update-requests/{request_id}/review?decision=approve")
    assert response.status_code == 200
    assert b"Approve profile update request" in response.data


def test_seed_command_is_idempotent(app, runner):
    with app.app_context():
        result_one = runner.invoke(args=["seed"])
        result_two = runner.invoke(args=["seed"])

        assert result_one.exit_code == 0
        assert result_two.exit_code == 0
        assert Role.query.count() == 6
        assert User.query.filter_by(username="superadmin").count() == 1
        assert Permission.query.count() > 0
        assert RolePermission.query.count() > 0
        default_shift = Shift.query.filter_by(shift_name="Default Office Shift").first()
        assert default_shift is not None
        assert LeaveType.query.filter_by(name="Vacation Leave").first() is not None
        assert LeaveType.query.filter_by(name="Birthday Leave").first() is not None


def test_admin_can_create_user(client, app, seeded_data):
    username, password = create_super_admin(app, username="super_creator", email="super_creator@example.com")
    login(client, username=username, password=password)
    with app.app_context():
        role = Role.query.filter_by(name="Employee").first()

    response = client.post(
        "/users/create",
        data={
            "username": "newuser",
            "email": "newuser@example.com",
            "role_id": role.id,
            "employee_id": 0,
            "password": "Password123!",
            "can_access_api": "y",
            "is_active": "y",
            "force_password_change": "y",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"User account created successfully." in response.data
    with app.app_context():
        created = User.query.filter_by(username="newuser").first()
        assert created is not None
        assert created.role.name == "Employee"
        assert created.can_access_api is True
        assert created.api_token is not None


def test_biometric_api_user_gets_token_and_can_authenticate(client, app, seeded_data):
    login(client)
    with app.app_context():
        biometric_role = Role.query.filter_by(name="Biometrics API User").first()

    response = client.post(
        "/users/create",
        data={
            "username": "biometricbot",
            "email": "biometricbot@example.com",
            "role_id": biometric_role.id,
            "employee_id": 0,
            "password": "Password123!",
            "is_active": "y",
            "force_password_change": "",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    with app.app_context():
        created = User.query.filter_by(username="biometricbot").first()
        assert created is not None
        assert created.api_token is not None
        assert created.can_access_api is True

        auth_response = client.post(
            "/api/biometric/validate-employee",
            json={"employee_code": "EMP-00001"},
            headers={"X-API-Token": created.api_token},
        )
        assert auth_response.status_code == 200
        assert auth_response.json["authorized_as"]["auth_type"] == "user"


def test_api_access_flag_controls_personal_token_auth(client, app, seeded_data):
    username, password = create_super_admin(app, username="super_api", email="super_api@example.com")
    login(client, username=username, password=password)
    with app.app_context():
        employee_role = Role.query.filter_by(name="Employee").first()

    client.post(
        "/users/create",
        data={
            "username": "apiuser",
            "email": "apiuser@example.com",
            "role_id": employee_role.id,
            "employee_id": 0,
            "password": "Password123!",
            "can_access_api": "y",
            "is_active": "y",
            "force_password_change": "",
        },
        follow_redirects=True,
    )

    with app.app_context():
        created = User.query.filter_by(username="apiuser").first()
        token = created.api_token
        assert created.can_access_api is True

    allowed = client.post(
        "/api/biometric/validate-employee",
        json={"employee_code": "EMP-00001"},
        headers={"X-API-Token": token},
    )
    assert allowed.status_code == 200

    with app.app_context():
        created = User.query.filter_by(username="apiuser").first()
        created.can_access_api = False
        db.session.commit()

    denied = client.post(
        "/api/biometric/validate-employee",
        json={"employee_code": "EMP-00001"},
        headers={"X-API-Token": token},
    )
    assert denied.status_code == 401


def test_only_superadmin_can_set_api_access(client, app, seeded_data):
    login(client)
    with app.app_context():
        employee_role = Role.query.filter_by(name="Employee").first()

    create_page = client.get("/users/create")
    assert b"Can access API" not in create_page.data

    client.post(
        "/users/create",
        data={
            "username": "hrmadeapi",
            "email": "hrmadeapi@example.com",
            "role_id": employee_role.id,
            "employee_id": 0,
            "password": "Password123!",
            "can_access_api": "y",
            "is_active": "y",
            "force_password_change": "",
        },
        follow_redirects=True,
    )

    with app.app_context():
        created = User.query.filter_by(username="hrmadeapi").first()
        assert created is not None
        assert created.can_access_api is False
        assert created.api_token is None

        super_role = Role.query.filter_by(name="Super Admin").first()
        super_user = User(
            username="superapi",
            email="superapi@example.com",
            role=super_role,
            is_active=True,
            force_password_change=False,
        )
        super_user.set_password("Password123!")
        db.session.add(super_user)
        db.session.commit()

    client.get("/auth/logout", follow_redirects=True)
    login(client, username="superapi")
    super_page = client.get("/users/create")
    assert b"Can access API" in super_page.data


def test_admin_can_toggle_and_reset_user_password(client, app, seeded_data):
    login(client)
    with app.app_context():
        user = User.query.filter_by(username="employee1").first()
        user_id = user.id

    toggle_response = client.post(f"/users/{user_id}/toggle", follow_redirects=True)
    assert b"deactivated successfully" in toggle_response.data

    reset_response = client.post(
        f"/users/{user_id}/reset-password",
        data={"password": "ResetPass123!", "force_password_change": "y"},
        follow_redirects=True,
    )
    assert b"Password reset successfully." in reset_response.data

    with app.app_context():
        updated = db.session.get(User, user_id)
        assert updated.is_active is False
        assert updated.check_password("ResetPass123!")
        assert updated.force_password_change is True


def test_department_and_position_crud_validation(client, app, seeded_data):
    login(client)

    duplicate_department = client.post(
        "/employees/departments/create",
        data={"name": "Human Resources", "code": "HR", "manager_id": 0, "branch": "", "cost_center": ""},
        follow_redirects=True,
    )
    assert b"Department code already exists." in duplicate_department.data

    create_department = client.post(
        "/employees/departments/create",
        data={
            "name": "Information Technology",
            "code": "IT",
            "manager_id": 0,
            "branch": "Main",
            "cost_center": "IT-001",
        },
        follow_redirects=True,
    )
    assert b"Department created successfully." in create_department.data

    with app.app_context():
        department = Department.query.filter_by(code="IT").first()
        assert department is not None

    create_position = client.post(
        "/employees/positions/create",
        data={"name": "Developer", "department_id": department.id, "description": "Writes code"},
        follow_redirects=True,
    )
    assert b"Position created successfully." in create_position.data

    duplicate_position = client.post(
        "/employees/positions/create",
        data={"name": "Developer", "department_id": department.id, "description": ""},
        follow_redirects=True,
    )
    assert b"Position already exists in this department." in duplicate_position.data


def test_schedule_crud_and_custom_assignment(client, app, seeded_data):
    login(client)

    create_schedule = client.post(
        "/employees/schedules/create",
        data={
            "shift_name": "Night Shift",
            "start_time": "21:00",
            "end_time": "06:00",
            "grace_period_minutes": 10,
            "break_start": "",
            "break_end": "",
            "is_flexible": "",
        },
        follow_redirects=True,
    )
    assert b"Schedule created successfully." in create_schedule.data

    with app.app_context():
        employee = Employee.query.filter_by(employee_code="EMP-00002").first()
        schedule = Shift.query.filter_by(shift_name="Night Shift").first()

    update_employee = client.post(
        f"/employees/{employee.id}/edit",
        data={
            "first_name": employee.first_name,
            "middle_name": "",
            "last_name": employee.last_name,
            "suffix": "",
            "birthdate": "",
            "gender": "",
            "civil_status": "",
            "address": "",
            "contact_number": "",
            "personal_email": "",
            "company_email": "",
            "department_id": employee.department_id,
            "position_id": employee.position_id,
            "employment_type": "",
            "date_hired": employee.date_hired.isoformat(),
            "date_regularized": "",
            "employment_status": employee.employment_status,
            "sss_no": "",
            "tin_no": "",
            "philhealth_no": "",
            "pagibig_no": "",
            "profile_image": "",
            "emergency_contact_name": "",
            "emergency_contact_number": "",
            "badge_id": employee.badge_id,
            "nfc_uid": employee.nfc_uid,
            "shift_id": schedule.id,
        },
        follow_redirects=True,
    )
    assert b"Employee updated successfully." in update_employee.data

    with app.app_context():
        active_shift = EmployeeShift.query.filter_by(employee_id=employee.id, end_date=None).first()
        assert active_shift is not None
        assert active_shift.shift_id == schedule.id


def test_employee_crud_and_required_field_validation(client, app, seeded_data):
    login(client)

    invalid_response = client.post(
        "/employees/create",
        data={
            "first_name": "John",
            "last_name": "Doe",
            "department_id": 0,
            "position_id": 0,
            "employment_status": "active",
        },
        follow_redirects=True,
    )
    assert b"This field is required." in invalid_response.data

    with app.app_context():
        department = Department.query.filter_by(code="HR").first()
        position = Position.query.filter_by(name="HR Administrator").first()

    create_response = client.post(
        "/employees/create",
        data={
            "first_name": "John",
            "middle_name": "",
            "last_name": "Doe",
            "suffix": "",
            "birthdate": "",
            "gender": "male",
            "civil_status": "single",
            "address": "123 Main St",
            "contact_number": "09171234567",
            "personal_email": "john@example.com",
            "company_email": "john.doe@example.com",
            "department_id": department.id,
            "position_id": position.id,
            "employment_type": "regular",
            "date_hired": "2025-01-01",
            "date_regularized": "",
            "employment_status": "active",
            "sss_no": "",
            "tin_no": "",
            "philhealth_no": "",
            "pagibig_no": "",
            "profile_image": "",
            "emergency_contact_name": "Jane Doe",
            "emergency_contact_number": "09998887777",
        },
        follow_redirects=True,
    )
    assert b"Employee created successfully." in create_response.data

    with app.app_context():
        employee = Employee.query.filter_by(last_name="Doe").first()
        assert employee is not None
        assert employee.employee_code == "EMP-00003"
        shift_assignment = EmployeeShift.query.filter_by(employee_id=employee.id).first()
        assert shift_assignment is not None
        assert shift_assignment.shift.shift_name == "Default Office Shift"


def test_employee_duplicate_fields_are_rejected(client, app, seeded_data):
    login(client)
    with app.app_context():
        department = Department.query.filter_by(code="HR").first()
        position = Position.query.filter_by(name="HR Administrator").first()
        existing_employee = Employee.query.filter_by(employee_code="EMP-00002").first()

    response = client.post(
        "/employees/create",
        data={
            "first_name": "Duplicate",
            "middle_name": "",
            "last_name": "Employee",
            "suffix": "",
            "birthdate": "",
            "gender": "",
            "civil_status": "",
            "address": "",
            "contact_number": "",
            "personal_email": "",
            "company_email": "",
            "department_id": department.id,
            "position_id": position.id,
            "manager_id": 0,
            "employment_type": "regular",
            "date_hired": "2025-02-01",
            "date_regularized": "",
            "employment_status": "active",
            "sss_no": "",
            "tin_no": "",
            "philhealth_no": "",
            "pagibig_no": "",
            "profile_image": "",
            "emergency_contact_name": "",
            "emergency_contact_number": "",
            "badge_id": existing_employee.badge_id,
            "nfc_uid": existing_employee.nfc_uid,
            "shift_id": 0,
        },
        follow_redirects=True,
    )

    assert b"Badge ID is already assigned to another employee." in response.data
    assert b"NFC UID is already assigned to another employee." in response.data


def test_admin_can_toggle_employee_status(client, app, seeded_data):
    login(client)
    with app.app_context():
        employee = Employee.query.filter_by(employee_code="EMP-00002").first()
        employee_id = employee.id
        assert employee.employment_status == "active"

    disable_response = client.post(f"/employees/{employee_id}/toggle", follow_redirects=True)
    assert b"Employee disabled successfully." in disable_response.data

    with app.app_context():
        updated = db.session.get(Employee, employee_id)
        assert updated.employment_status == "inactive"

    enable_response = client.post(f"/employees/{employee_id}/toggle", follow_redirects=True)
    assert b"Employee enabled successfully." in enable_response.data

    with app.app_context():
        updated = db.session.get(Employee, employee_id)
        assert updated.employment_status == "active"


def test_logged_in_user_cannot_disable_own_account_or_employee_profile(client, app, seeded_data):
    login(client)
    with app.app_context():
        current_user_obj = User.query.filter_by(username="hradmin").first()
        current_employee_id = current_user_obj.employee_id
        current_user_id = current_user_obj.id

    user_toggle_response = client.post(f"/users/{current_user_id}/toggle", follow_redirects=True)
    assert b"You cannot deactivate your own account while you are logged in." in user_toggle_response.data

    employee_toggle_response = client.post(f"/employees/{current_employee_id}/toggle", follow_redirects=True)
    assert b"You cannot disable your own employee profile while you are logged in." in employee_toggle_response.data

    with app.app_context():
        refreshed_user = db.session.get(User, current_user_id)
        refreshed_employee = db.session.get(Employee, current_employee_id)
        assert refreshed_user.is_active is True
        assert refreshed_employee.employment_status == "active"


def test_employee_detail_shows_timekeeping_snapshot(client, app, seeded_data):
    login(client)
    with app.app_context():
        employee = Employee.query.filter_by(employee_code="EMP-00001").first()

    response = client.get(f"/employees/{employee.id}")
    assert response.status_code == 200
    assert b"Attendance Today" in response.data
    assert b"Time In" in response.data
    assert b"Time Out" in response.data
    assert b"Undertime" in response.data
    assert b"Recent Time Logs" in response.data


def test_dashboard_metrics_render(client, seeded_data):
    response = login(client)
    assert b"Employees" in response.data
    assert b"Active Users" in response.data
    assert b"Pending Leave Requests" in response.data
    assert b"Attendance Today" in response.data
    assert b"Welcome to HRIS" in response.data
    assert b"Quick Access" not in response.data
    assert b"MVP Scope" not in response.data


def test_fixed_schedule_respects_grace_period_and_marks_late_afterwards(app, seeded_data):
    with app.app_context():
        employee = Employee.query.filter_by(employee_code="EMP-00001").first()
        grace_record = AttendanceRecord(
            employee_id=employee.id,
            date=date(2025, 3, 18),
            time_in=datetime(2025, 3, 18, 8, 40),
            time_out=datetime(2025, 3, 18, 17, 30),
            status="present",
        )
        db.session.add(grace_record)
        db.session.flush()

        from hris.app.attendance.services import apply_attendance_policy

        apply_attendance_policy(grace_record)
        assert grace_record.late_minutes == 0
        assert grace_record.status == "present"

        late_record = AttendanceRecord(
            employee_id=employee.id,
            date=date(2025, 3, 19),
            time_in=datetime(2025, 3, 19, 8, 50),
            time_out=datetime(2025, 3, 19, 17, 30),
            status="present",
        )
        db.session.add(late_record)
        db.session.flush()
        apply_attendance_policy(late_record)
        assert late_record.late_minutes == 20
        assert late_record.status == "late"


def test_flexible_schedule_requires_eight_working_hours_excluding_break(app, seeded_data):
    with app.app_context():
        employee = Employee.query.filter_by(employee_code="EMP-00002").first()
        flexible_shift = Shift(
            shift_name="Field Flexible Shift",
            start_time=datetime(2025, 3, 18, 8, 30).time(),
            end_time=datetime(2025, 3, 18, 17, 30).time(),
            grace_period_minutes=0,
            is_flexible=True,
        )
        db.session.add(flexible_shift)
        db.session.flush()
        db.session.add(
            EmployeeShift(
                employee_id=employee.id,
                shift_id=flexible_shift.id,
                effective_date=date(2025, 3, 18),
            )
        )
        db.session.flush()

        from hris.app.attendance.services import apply_attendance_policy

        record = AttendanceRecord(
            employee_id=employee.id,
            date=date(2025, 3, 18),
            time_in=datetime(2025, 3, 18, 9, 0),
            time_out=datetime(2025, 3, 18, 18, 0),
            status="present",
        )
        db.session.add(record)
        db.session.flush()
        apply_attendance_policy(record)

        assert record.late_minutes == 0
        assert record.undertime_minutes == 0
        assert record.overtime_minutes == 0
        assert record.status == "present"


def test_fixed_schedule_marks_undertime_when_timeout_is_before_shift_end(app, seeded_data):
    with app.app_context():
        employee = Employee.query.filter_by(employee_code="EMP-00001").first()

        from hris.app.attendance.services import apply_attendance_policy

        record = AttendanceRecord(
            employee_id=employee.id,
            date=date(2025, 3, 20),
            time_in=datetime(2025, 3, 20, 8, 30),
            time_out=datetime(2025, 3, 20, 17, 0),
            status="present",
        )
        db.session.add(record)
        db.session.flush()
        apply_attendance_policy(record)

        assert record.late_minutes == 0
        assert record.undertime_minutes == 30
        assert record.status == "undertime"


def test_admin_can_post_news_and_user_can_see_notifications(client, app, seeded_data):
    login(client)
    response = client.post(
        "/news/create",
        data={"title": "Payroll Notice", "body": "Payroll will be released this Friday.", "is_active": "y"},
        follow_redirects=True,
    )
    assert b"News published successfully." in response.data

    with app.app_context():
        assert Announcement.query.filter_by(title="Payroll Notice").first() is not None
        assert Notification.query.filter_by(title="Payroll Notice").count() >= 1

    login(client, username="employee1")
    notifications_page = client.get("/notifications")
    assert notifications_page.status_code == 200
    assert b"Payroll Notice" in notifications_page.data
    dashboard_again = client.get("/")
    assert b'badge-notification bg-danger">1<' not in dashboard_again.data


def test_admin_can_edit_html_news_with_image(client, app, seeded_data):
    login(client)
    with app.app_context():
        announcement = Announcement.query.filter_by(title="Welcome to HRIS").first()

    response = client.post(
        f"/news/{announcement.id}/edit",
        data={
            "title": "Welcome to HRIS",
            "body": "<h3>Important Update</h3><p><strong>Payroll</strong> moved to Friday.</p>",
            "image": (io.BytesIO(b"fakepngdata"), "news.png"),
            "is_active": "y",
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert b"News updated successfully." in response.data
    with app.app_context():
        updated = Announcement.query.get(announcement.id)
        assert "<h3>Important Update</h3>" in updated.body
        assert updated.image_filename is not None


def test_kiosk_and_api_request_menu_are_superadmin_only(client, app, seeded_data):
    login(client)
    hr_admin_dashboard = client.get("/")
    assert b"Kiosk Terminal" not in hr_admin_dashboard.data
    assert b"API Requests" not in hr_admin_dashboard.data
    assert client.get("/api-requests").status_code == 403

    with app.app_context():
        role = Role.query.filter_by(name="Super Admin").first()
        super_user = User(
            username="supermenu",
            email="supermenu@example.com",
            role=role,
            is_active=True,
            force_password_change=False,
        )
        super_user.set_password("Password123!")
        db.session.add(super_user)
        db.session.commit()

    client.get("/auth/logout", follow_redirects=True)
    login(client, username="supermenu")
    super_dashboard = client.get("/")
    assert b"Kiosk Terminal" in super_dashboard.data
    assert b"API Requests" in super_dashboard.data
    assert client.get("/api-requests").status_code == 200
    assert b"/api/biometric/punch" in client.get("/api-requests").data


def test_module_stub_pages_and_biometric_contract(client, seeded_data):
    login(client)
    assert client.get("/attendance/").status_code == 200
    assert client.get("/leave/").status_code == 200
    assert client.get("/payroll/").status_code == 200
    assert client.get("/reports/").status_code == 200

    unauthorized = client.post("/api/biometric/punch", json={"employee_code": "EMP-00001"})
    assert unauthorized.status_code == 401

    authorized = client.post(
        "/api/biometric/validate-employee",
        json={"employee_code": "EMP-00001"},
        headers={"X-API-Token": "test-biometric-token"},
    )
    assert authorized.status_code == 200
    assert authorized.json["valid"] is True


def test_attendance_module_ui_and_api(client, app, seeded_data):
    login(client)
    with app.app_context():
        employee = Employee.query.filter_by(employee_code="EMP-00001").first()

    attendance_page = client.get("/attendance/")
    assert b"Timekeeping" in attendance_page.data
    assert b"Time In" in attendance_page.data
    assert b"Undertime" in attendance_page.data
    assert b"Edit" not in attendance_page.data

    create_response = client.post(
        "/attendance/records/create",
        data={
            "employee_id": employee.id,
            "date": "2025-02-01",
            "time_in": "",
            "time_out": "",
            "break_in": "",
            "break_out": "",
            "late_minutes": 5,
            "undertime_minutes": 0,
            "overtime_minutes": 30,
            "status": "present",
            "remarks": "Manual entry",
        },
        follow_redirects=True,
    )
    assert b"Attendance record saved successfully." in create_response.data

    summary_response = client.get("/attendance/api/summary")
    assert summary_response.status_code == 200
    assert "records_today" in summary_response.json

    records_response = client.get("/attendance/api/records")
    assert records_response.status_code == 200
    assert any(item["employee_name"] == "Alice Admin" for item in records_response.json)

    kiosk_response = client.post(
        "/attendance/api/punch",
        json={"identifier": "BADGE-0002", "source": "badge", "action": "time_in"},
    )
    assert kiosk_response.status_code == 200
    assert "timed in successfully" in kiosk_response.json["message"].lower()

    kiosk_timeout = client.post(
        "/attendance/api/punch",
        json={"identifier": "BADGE-0002", "source": "badge", "action": "time_out"},
    )
    assert kiosk_timeout.status_code == 200
    assert "timed out successfully" in kiosk_timeout.json["message"].lower()

    with app.app_context():
        updated_record = AttendanceRecord.query.filter_by(employee_id=employee.id, date=date.today()).first()
        assert updated_record.late_minutes == 0

    self_view = client.get("/attendance/my-logs")
    assert self_view.status_code == 200


def test_public_kiosk_page_and_socket_punch(app, client, seeded_data):
    with app.app_context():
        expected_employee_id = Employee.query.filter_by(employee_code="EMP-00002").first().id

    kiosk_page = client.get("/attendance/kiosk")
    assert kiosk_page.status_code == 200
    assert b"Focused attendance terminal" in kiosk_page.data
    assert b"Time in" in kiosk_page.data
    assert b"Time out" in kiosk_page.data

    socket_client = socketio.test_client(app, namespace="/kiosk")
    live_client = socketio.test_client(app, namespace="/attendance-live")
    socket_client.emit(
        "attendance_punch",
        {"identifier": "NFC-EMP-002", "source": "nfc", "action": "time_in"},
        namespace="/kiosk",
    )
    events = socket_client.get_received("/kiosk")
    assert events
    payload = events[-1]["args"][0]
    assert payload["ok"] is True
    assert payload["record"]["employee_name"] == "Evan Employee"

    live_events = live_client.get_received("/attendance-live")
    assert live_events
    live_payload = live_events[-1]["args"][0]
    assert live_payload["employee_id"] == expected_employee_id
    assert live_payload["record"]["employee_name"] == "Evan Employee"
    socket_client.disconnect(namespace="/kiosk")
    live_client.disconnect(namespace="/attendance-live")


def test_http_punch_api_emits_live_attendance_update(app, client, seeded_data):
    with app.app_context():
        expected_employee_id = Employee.query.filter_by(employee_code="EMP-00002").first().id

    live_client = socketio.test_client(app, namespace="/attendance-live")
    response = client.post(
        "/attendance/api/punch",
        json={"identifier": "BADGE-0002", "source": "badge", "action": "time_in"},
    )

    assert response.status_code == 200
    live_events = live_client.get_received("/attendance-live")
    assert live_events
    payload = live_events[-1]["args"][0]
    assert payload["employee_id"] == expected_employee_id
    assert payload["record"]["employee_name"] == "Evan Employee"
    live_client.disconnect(namespace="/attendance-live")


def test_leave_module_ui_and_api(client, app, seeded_data):
    login(client)
    with app.app_context():
        employee = Employee.query.filter_by(employee_code="EMP-00002").first()
        leave_type = LeaveType.query.filter_by(name="Vacation Leave").first()

    grant_response = client.post(
        "/leave/balances/create",
        data={
            "employee_id": employee.id,
            "leave_type_id": leave_type.id,
            "year": "2025",
            "total_credits": "5",
            "used_credits": "0",
        },
        follow_redirects=True,
    )
    assert b"Leave granted successfully." in grant_response.data

    create_response = client.post(
        "/leave/requests/create",
        data={
            "employee_id": employee.id,
            "leave_type_id": leave_type.id,
            "duration_type": "whole_day",
            "start_date": "2025-03-01",
            "end_date": "2025-03-02",
            "reason": "Family trip",
        },
        follow_redirects=True,
    )
    assert b"Leave request submitted successfully." in create_response.data

    requests_response = client.get("/leave/api/requests")
    assert requests_response.status_code == 200
    assert any(item["employee_name"] == "Evan Employee" for item in requests_response.json)

    with app.app_context():
        balance = LeaveBalance.query.filter_by(
            employee_id=employee.id,
            leave_type_id=leave_type.id,
            year=2025,
        ).first()
        assert balance is not None
        assert float(balance.remaining_credits) == 5.0

    leave_page = client.get("/leave/")
    assert b"Grant Leave" in leave_page.data
    assert b"Approve" in leave_page.data
    assert b"Disapprove" in leave_page.data


def test_employee_does_not_see_grant_leave_or_payroll_menu(client, seeded_data):
    login(client, username="employee1")
    leave_page = client.get("/leave/")
    assert leave_page.status_code == 200
    assert b"Grant Leave" not in leave_page.data
    assert b"New Leave Type" not in leave_page.data

    dashboard = client.get("/")
    assert b"Payroll" not in dashboard.data


def test_employee_leave_page_only_shows_own_requests_and_granted_balances(client, app, seeded_data):
    with app.app_context():
        employee = Employee.query.filter_by(employee_code="EMP-00002").first()
        admin_employee = Employee.query.filter_by(employee_code="EMP-00001").first()
        vacation_leave = LeaveType.query.filter_by(name="Vacation Leave").first()

        db.session.add_all(
            [
                LeaveBalance(
                    employee_id=employee.id,
                    leave_type_id=vacation_leave.id,
                    year=2025,
                    total_credits=5,
                    used_credits=1,
                    remaining_credits=4,
                ),
                LeaveBalance(
                    employee_id=admin_employee.id,
                    leave_type_id=vacation_leave.id,
                    year=2025,
                    total_credits=10,
                    used_credits=0,
                    remaining_credits=10,
                ),
                LeaveRequest(
                    employee_id=employee.id,
                    leave_type_id=vacation_leave.id,
                    start_date=date(2025, 6, 2),
                    end_date=date(2025, 6, 2),
                    duration_type="whole_day",
                    days=1,
                    reason="Employee leave",
                    status="pending",
                ),
                LeaveRequest(
                    employee_id=admin_employee.id,
                    leave_type_id=vacation_leave.id,
                    start_date=date(2025, 6, 3),
                    end_date=date(2025, 6, 3),
                    duration_type="whole_day",
                    days=1,
                    reason="Admin leave",
                    status="pending",
                ),
            ]
        )
        db.session.commit()

    login(client, username="employee1")
    leave_page = client.get("/leave/")
    assert leave_page.status_code == 200
    assert b"My Granted Leave Balances" in leave_page.data
    assert b"Evan Employee" in leave_page.data
    assert b"Admin leave" not in leave_page.data
    assert b"Alice Admin" not in leave_page.data

    leave_api = client.get("/leave/api/requests")
    assert leave_api.status_code == 200
    assert all(item["employee_name"] == "Evan Employee" for item in leave_api.json)


def test_employee_leave_page_shows_zero_for_ungranted_leave_types(client, app, seeded_data):
    with app.app_context():
        employee = Employee.query.filter_by(employee_code="EMP-00002").first()
        vacation_leave = LeaveType.query.filter_by(name="Vacation Leave").first()
        current_year = datetime.utcnow().year
        db.session.add(
            LeaveBalance(
                employee_id=employee.id,
                leave_type_id=vacation_leave.id,
                year=current_year,
                total_credits=3,
                used_credits=1,
                remaining_credits=2,
            )
        )
        db.session.commit()

    login(client, username="employee1")
    leave_page = client.get("/leave/")
    assert leave_page.status_code == 200
    assert b"Vacation Leave" in leave_page.data
    assert b"2 remaining" in leave_page.data or b"2.00 remaining" in leave_page.data
    assert b"Sick Leave" in leave_page.data
    assert b"0 remaining" in leave_page.data


def test_admin_can_adjust_leave_balance_up_or_down(client, app, seeded_data):
    login(client)
    with app.app_context():
        employee = Employee.query.filter_by(employee_code="EMP-00002").first()
        leave_type = LeaveType.query.filter_by(name="Vacation Leave").first()
        db.session.add(
            LeaveBalance(
                employee_id=employee.id,
                leave_type_id=leave_type.id,
                year=2025,
                total_credits=5,
                used_credits=1,
                remaining_credits=4,
            )
        )
        db.session.commit()
        employee_id = employee.id
        leave_type_id = leave_type.id

    increase_response = client.post(
        "/leave/balances/adjust",
        data={
            "employee_id": employee_id,
            "leave_type_id": leave_type_id,
            "year": 2025,
            "adjustment_credits": "2",
            "reason": "Manual addition",
        },
        follow_redirects=True,
    )
    assert b"Leave balance adjusted successfully." in increase_response.data

    reduce_response = client.post(
        "/leave/balances/adjust",
        data={
            "employee_id": employee_id,
            "leave_type_id": leave_type_id,
            "year": 2025,
            "adjustment_credits": "-1",
            "reason": "Manual reduction",
        },
        follow_redirects=True,
    )
    assert b"Leave balance adjusted successfully." in reduce_response.data

    with app.app_context():
        balance = LeaveBalance.query.filter_by(employee_id=employee_id, leave_type_id=leave_type_id, year=2025).first()
        assert float(balance.total_credits) == 6.0
        assert float(balance.remaining_credits) == 5.0


def test_leave_request_without_credits_becomes_unpaid(client, app, seeded_data):
    login(client)
    with app.app_context():
        employee = Employee.query.filter_by(employee_code="EMP-00002").first()
        leave_type = LeaveType.query.filter_by(name="Sick Leave").first()

    response = client.post(
        "/leave/requests/create",
        data={
            "employee_id": employee.id,
            "leave_type_id": leave_type.id,
            "duration_type": "whole_day",
            "start_date": "2025-04-01",
            "end_date": "2025-04-02",
            "reason": "Need rest",
        },
        follow_redirects=True,
    )

    assert b"Leave request submitted successfully." in response.data
    assert b"Unpaid" in response.data

    with app.app_context():
        request_obj = (
            LeaveRequest.query.filter_by(employee_id=employee.id, leave_type_id=leave_type.id)
            .order_by(LeaveRequest.id.desc())
            .first()
        )
        assert request_obj is not None
        assert request_obj.is_paid is False


def test_half_day_leave_request_is_saved_as_half_credit_and_notifies_approvers(client, app, seeded_data):
    login(client)
    with app.app_context():
        employee = Employee.query.filter_by(employee_code="EMP-00002").first()
        leave_type = LeaveType.query.filter_by(name="Vacation Leave").first()

        manager_role = Role.query.filter_by(name="Manager").first()
        manager_employee = Employee(
            employee_code="EMP-00992",
            first_name="Lara",
            last_name="Lead",
            date_hired=date(2024, 2, 1),
            employment_status="active",
            department=employee.department,
            position=employee.position,
        )
        db.session.add(manager_employee)
        db.session.flush()
        manager_user = User(
            username="manager_leave",
            email="manager_leave@example.com",
            role=manager_role,
            employee=manager_employee,
            is_active=True,
            force_password_change=False,
        )
        manager_user.set_password("Password123!")
        db.session.add(manager_user)
        employee.manager = manager_employee
        db.session.commit()
        manager_user_id = manager_user.id
        employee_id = employee.id
        leave_type_id = leave_type.id

    response = client.post(
        "/leave/requests/create",
        data={
            "employee_id": employee_id,
            "leave_type_id": leave_type_id,
            "duration_type": "half_day",
            "start_date": "2025-04-15",
            "end_date": "2025-04-15",
            "reason": "Medical appointment",
        },
        follow_redirects=True,
    )

    assert b"Leave request submitted successfully." in response.data
    with app.app_context():
        request_obj = (
            LeaveRequest.query.filter_by(employee_id=employee_id, leave_type_id=leave_type_id)
            .order_by(LeaveRequest.id.desc())
            .first()
        )
        assert request_obj is not None
        assert float(request_obj.days) == 0.5
        assert request_obj.duration_type == "half_day"
        assert Notification.query.filter_by(user_id=manager_user_id, type="leave_request").count() == 1
        assert Notification.query.filter_by(type="leave_request").count() >= 2


def test_leave_admin_can_disapprove_request(client, app, seeded_data):
    login(client)
    with app.app_context():
        employee = Employee.query.filter_by(employee_code="EMP-00002").first()
        leave_type = LeaveType.query.filter_by(name="Vacation Leave").first()

    client.post(
        "/leave/requests/create",
        data={
            "employee_id": employee.id,
            "leave_type_id": leave_type.id,
            "duration_type": "whole_day",
            "start_date": "2025-05-01",
            "end_date": "2025-05-01",
            "reason": "Personal",
        },
        follow_redirects=True,
    )

    with app.app_context():
        request_obj = LeaveRequest.query.filter_by(employee_id=employee.id, leave_type_id=leave_type.id).order_by(LeaveRequest.id.desc()).first()
        request_id = request_obj.id

    response = client.post(f"/leave/requests/{request_id}/disapprove", follow_redirects=True)
    assert b"Leave request disapproved." in response.data

    with app.app_context():
        updated = db.session.get(LeaveRequest, request_id)
        assert updated.status == "disapproved"


def test_manager_can_approve_direct_report_leave_only(client, app, seeded_data):
    with app.app_context():
        employee = Employee.query.filter_by(employee_code="EMP-00002").first()
        leave_type = LeaveType.query.filter_by(name="Vacation Leave").first()
        manager_role = Role.query.filter_by(name="Manager").first()
        department = employee.department
        manager_position = Position(name="Operations Manager", department=department, description="Handles approvals")
        db.session.add(manager_position)
        db.session.flush()

        manager_employee = Employee(
            employee_code="EMP-00993",
            first_name="Milo",
            last_name="Manager",
            date_hired=date(2024, 3, 1),
            employment_status="active",
            department=department,
            position=manager_position,
        )
        db.session.add(manager_employee)
        db.session.flush()
        manager_user = User(
            username="manager_approver",
            email="manager_approver@example.com",
            role=manager_role,
            employee=manager_employee,
            is_active=True,
            force_password_change=False,
        )
        manager_user.set_password("Password123!")
        db.session.add(manager_user)
        employee.manager = manager_employee
        db.session.commit()
        employee_id = employee.id
        leave_type_id = leave_type.id

    login(client)
    client.post(
        "/leave/requests/create",
        data={
            "employee_id": employee_id,
            "leave_type_id": leave_type_id,
            "duration_type": "whole_day",
            "start_date": "2025-05-10",
            "end_date": "2025-05-10",
            "reason": "Direct report leave",
        },
        follow_redirects=True,
    )
    with app.app_context():
        request_obj = LeaveRequest.query.filter_by(employee_id=employee_id).order_by(LeaveRequest.id.desc()).first()
        request_id = request_obj.id

    client.get("/auth/logout", follow_redirects=True)
    login(client, username="manager_approver")
    approve_response = client.post(f"/leave/requests/{request_id}/approve", follow_redirects=True)
    assert b"Leave request approved." in approve_response.data

    with app.app_context():
        updated = db.session.get(LeaveRequest, request_id)
        assert updated.status == "approved"


def test_employee_does_not_see_leave_decision_buttons(client, seeded_data):
    login(client, username="employee1")
    leave_page = client.get("/leave/")
    assert b'btn btn-sm btn-light-success' not in leave_page.data
    assert b'btn btn-sm btn-light-danger' not in leave_page.data


def test_employee_manager_assignment_only_allows_manager_position(app, client, seeded_data):
    login(client)
    with app.app_context():
        department = Department.query.filter_by(code="HR").first()
        manager_position = Position(name="Team Manager", department=department, description="Manages staff")
        staff_position = Position(name="Coordinator", department=department, description="Supports staff")
        db.session.add_all([manager_position, staff_position])
        db.session.flush()

        manager_employee = Employee(
            employee_code="EMP-00990",
            first_name="Manny",
            last_name="Manager",
            date_hired=date(2024, 5, 1),
            employment_status="active",
            department=department,
            position=manager_position,
        )
        non_manager_employee = Employee(
            employee_code="EMP-00991",
            first_name="Nina",
            last_name="Staff",
            date_hired=date(2024, 5, 1),
            employment_status="active",
            department=department,
            position=staff_position,
        )
        db.session.add_all([manager_employee, non_manager_employee])
        db.session.commit()
        manager_id = manager_employee.id

    form_page = client.get("/employees/create")
    assert b"Manny Manager" in form_page.data
    assert b"Nina Staff" not in form_page.data

    with app.app_context():
        employee = Employee.query.filter_by(employee_code="EMP-00002").first()

    response = client.post(
        f"/employees/{employee.id}/edit",
        data={
            "first_name": employee.first_name,
            "middle_name": "",
            "last_name": employee.last_name,
            "suffix": "",
            "birthdate": "",
            "gender": "",
            "civil_status": "",
            "address": "",
            "contact_number": "",
            "personal_email": "",
            "company_email": "",
            "department_id": employee.department_id,
            "position_id": employee.position_id,
            "manager_id": manager_id,
            "employment_type": "",
            "date_hired": employee.date_hired.isoformat(),
            "date_regularized": "",
            "employment_status": employee.employment_status,
            "sss_no": "",
            "tin_no": "",
            "philhealth_no": "",
            "pagibig_no": "",
            "profile_image": "",
            "emergency_contact_name": "",
            "emergency_contact_number": "",
            "badge_id": employee.badge_id,
            "nfc_uid": employee.nfc_uid,
            "shift_id": 0,
        },
        follow_redirects=True,
    )
    assert b"Employee updated successfully." in response.data

    with app.app_context():
        updated = Employee.query.filter_by(employee_code="EMP-00002").first()
        assert updated.manager_id == manager_id


def test_chat_thread_and_realtime_message_flow(app, client, seeded_data):
    login(client, username="employee1")
    employee_chat_page = client.get("/chat/")
    assert employee_chat_page.status_code == 200
    assert b"Realtime employee-to-admin chat" in employee_chat_page.data
    assert b"HR Support" in employee_chat_page.data

    with app.app_context():
        employee_user = User.query.filter_by(username="employee1").first()
        thread = employee_user.chat_thread
        assert thread is not None

    employee_socket = socketio.test_client(app, flask_test_client=client, namespace="/chat")
    employee_socket.emit("join_chat_thread", {"thread_id": thread.id}, namespace="/chat")
    employee_socket.emit("chat_message", {"thread_id": thread.id, "body": "Hello HR"}, namespace="/chat")
    employee_events = employee_socket.get_received("/chat")
    assert any(event["name"] == "chat_message" for event in employee_events)
    employee_socket.disconnect(namespace="/chat")

    client.get("/auth/logout", follow_redirects=True)
    login(client)
    admin_chat_page = client.get(f"/chat/{thread.id}")
    assert admin_chat_page.status_code == 200
    assert b"Hello HR" in admin_chat_page.data

    with app.app_context():
        assert ChatThread.query.count() >= 1
        assert ChatMessage.query.filter_by(thread_id=thread.id).count() >= 1


def test_foul_language_chat_prompts_warning_and_reports_to_manager(app, client, seeded_data):
    with app.app_context():
        employee_user = User.query.filter_by(username="employee1").first()
        employee = employee_user.employee
        department = employee.department
        manager_role = Role.query.filter_by(name="Manager").first()
        manager_employee = Employee(
            employee_code="EMP-00003",
            first_name="Mara",
            last_name="Manager",
            date_hired=date(2024, 2, 1),
            employment_status="active",
            department=department,
            position=employee.position,
        )
        db.session.add(manager_employee)
        db.session.flush()
        manager_user = User(
            username="manager1",
            email="manager1@example.com",
            role=manager_role,
            employee=manager_employee,
            is_active=True,
            force_password_change=False,
        )
        manager_user.set_password("Password123!")
        db.session.add(manager_user)
        department.manager_id = manager_employee.id
        db.session.commit()
        manager_user_id = manager_user.id

    login(client, username="employee1")
    with app.app_context():
        thread = User.query.filter_by(username="employee1").first().chat_thread
        if thread is None:
            from hris.app.chat.services import get_or_create_employee_thread

            thread = get_or_create_employee_thread(User.query.filter_by(username="employee1").first())

    socket_client = socketio.test_client(app, flask_test_client=client, namespace="/chat")
    socket_client.emit("join_chat_thread", {"thread_id": thread.id}, namespace="/chat")
    socket_client.emit("chat_message", {"thread_id": thread.id, "body": "fuck this process"}, namespace="/chat")
    events = socket_client.get_received("/chat")
    assert any(event["name"] == "chat_warning" for event in events)
    socket_client.disconnect(namespace="/chat")

    with app.app_context():
        report = Notification.query.filter_by(user_id=manager_user_id, type="chat_report").first()
        assert report is not None
        assert "flagged chat message" in report.message


def test_chat_attachment_upload_sends_image_message(client, app, seeded_data):
    login(client, username="employee1")
    with app.app_context():
        thread = User.query.filter_by(username="employee1").first().chat_thread
        if thread is None:
            from hris.app.chat.services import get_or_create_employee_thread

            thread = get_or_create_employee_thread(User.query.filter_by(username="employee1").first())
        thread_id = thread.id

    response = client.post(
        "/chat/send",
        data={
            "thread_id": str(thread_id),
            "body": "See attached image",
            "attachment": (io.BytesIO(b"fake-image-data"), "proof.png"),
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 201
    payload = response.get_json()
    assert payload["message"]["attachment_name"] == "proof.png"
    assert payload["message"]["attachment_is_image"] is True

    with app.app_context():
        message = ChatMessage.query.filter_by(thread_id=thread_id).order_by(ChatMessage.id.desc()).first()
        assert message is not None
        assert message.attachment_filename is not None
        assert message.attachment_original_name == "proof.png"


def test_payroll_and_reports_modules(client, app, seeded_data):
    login(client)
    with app.app_context():
        employee = Employee.query.filter_by(employee_code="EMP-00001").first()
        employee_user = User.query.filter_by(username="hradmin").first()
        staff_employee = Employee.query.filter_by(employee_code="EMP-00002").first()
        staff_user = User.query.filter_by(username="employee1").first()
        employee_id = employee.id
        employee_user_id = employee_user.id
        staff_user_id = staff_user.id
        db.session.add_all(
            [
                AttendanceRecord(
                    employee=employee,
                    date=date(2025, 2, 1),
                    status="late",
                    late_minutes=10,
                ),
                AttendanceRecord(
                    employee=staff_employee,
                    date=date(2025, 2, 2),
                    status="undertime",
                    undertime_minutes=30,
                ),
            ]
        )
        db.session.commit()

    cutoff_response = client.post(
        "/payroll/cutoffs/create",
        data={
            "cutoff_name": "February 1-15",
            "start_date": "2025-02-01",
            "end_date": "2025-02-15",
            "status": "open",
        },
        follow_redirects=True,
    )
    assert b"Payroll cutoff saved successfully." in cutoff_response.data

    salary_response = client.post(
        "/payroll/salary/create",
        data={
            "employee_id": employee_id,
            "basic_salary": "22000",
            "daily_rate": "1000",
            "hourly_rate": "125",
            "effective_date": "2025-01-01",
        },
        follow_redirects=True,
    )
    assert b"Salary setup saved successfully." in salary_response.data

    with app.app_context():
        from hris.app.models import PayrollCutoff

        cutoff = PayrollCutoff.query.filter_by(cutoff_name="February 1-15").first()
        assert Notification.query.filter_by(type="payroll", user_id=employee_user_id).count() >= 1
        assert Notification.query.filter_by(type="payroll", user_id=staff_user_id).count() >= 1

    generate_response = client.post(
        "/payroll/generate",
        data={"cutoff_id": cutoff.id},
        follow_redirects=True,
    )
    assert b"Generated" in generate_response.data

    entries_response = client.get("/payroll/api/entries")
    assert entries_response.status_code == 200
    assert len(entries_response.json) >= 1
    assert all(item["status"] == "generated" for item in entries_response.json)

    reports_page = client.get("/reports/")
    reports_api = client.get("/reports/api")
    assert reports_page.status_code == 200
    assert reports_api.status_code == 200
    assert "summary" in reports_api.json


def test_payroll_generate_warns_when_no_salary_matches_cutoff(client, app, seeded_data):
    login(client)
    client.post(
        "/payroll/cutoffs/create",
        data={
            "cutoff_name": "January 1-15",
            "start_date": "2024-01-01",
            "end_date": "2024-01-15",
            "status": "open",
        },
        follow_redirects=True,
    )

    with app.app_context():
        from hris.app.models import PayrollCutoff

        cutoff = PayrollCutoff.query.filter_by(cutoff_name="January 1-15").first()

    response = client.post(
        "/payroll/generate",
        data={"cutoff_id": cutoff.id},
        follow_redirects=True,
    )
    assert b"No payroll entries were generated" in response.data


def test_employee_can_download_own_payroll_pdf_from_reports(client, app, seeded_data):
    login(client)
    with app.app_context():
        employee = Employee.query.filter_by(employee_code="EMP-00002").first()
        db.session.add(
            EmployeeSalary(
                employee_id=employee.id,
                basic_salary=20000,
                daily_rate=1000,
                hourly_rate=125,
                effective_date=date(2025, 1, 1),
            )
        )
        cutoff = PayrollCutoff(
            cutoff_name="Employee PDF Cutoff",
            start_date=date(2025, 2, 1),
            end_date=date(2025, 2, 15),
            status="open",
        )
        db.session.add(cutoff)
        db.session.flush()
        db.session.add(
            AttendanceRecord(
                employee_id=employee.id,
                date=date(2025, 2, 5),
                status="present",
            )
        )
        db.session.commit()
        generate_payroll_for_cutoff(cutoff.id)
        entry = PayrollEntry.query.filter_by(employee_id=employee.id, cutoff_id=cutoff.id).first()
        entry_id = entry.id

    client.get("/auth/logout", follow_redirects=True)
    login(client, username="employee1")
    response = client.get(f"/payroll/entries/{entry_id}/pdf")
    assert response.status_code == 200
    assert response.mimetype == "application/pdf"


def test_admin_can_post_generated_payroll(client, app, seeded_data):
    login(client)
    with app.app_context():
        employee = Employee.query.filter_by(employee_code="EMP-00001").first()
        employee_user = User.query.filter_by(username="hradmin").first()
        db.session.add(
            EmployeeSalary(
                employee_id=employee.id,
                basic_salary=22000,
                daily_rate=1000,
                hourly_rate=125,
                effective_date=date(2025, 1, 1),
            )
        )
        cutoff = PayrollCutoff(
            cutoff_name="Posting Cutoff",
            start_date=date(2025, 2, 1),
            end_date=date(2025, 2, 15),
            status="open",
        )
        db.session.add(cutoff)
        db.session.flush()
        db.session.add(
            AttendanceRecord(
                employee_id=employee.id,
                date=date(2025, 2, 7),
                status="present",
            )
        )
        db.session.commit()
        generate_payroll_for_cutoff(cutoff.id)
        cutoff_id = cutoff.id
        employee_user_id = employee_user.id

    response = client.post(
        "/payroll/post",
        data={"cutoff_id": cutoff_id},
        follow_redirects=True,
    )
    assert b"Posted" in response.data

    with app.app_context():
        entry = PayrollEntry.query.filter_by(cutoff_id=cutoff_id).first()
        cutoff = PayrollCutoff.query.get(cutoff_id)
        assert entry.status == "posted"
        assert cutoff.status == "closed"
        assert Notification.query.filter_by(user_id=employee_user_id, type="payroll").count() >= 1


def test_employee_reports_are_scoped_to_logged_in_employee(client, app, seeded_data):
    login(client, username="employee1")

    reports_page = client.get("/reports/")
    assert reports_page.status_code == 200
    assert b"Review your personal attendance, leave, and payroll reports." in reports_page.data
    assert b"Evan Employee" in reports_page.data
    assert b"Alice Admin" not in reports_page.data

    reports_api = client.get("/reports/api")
    assert reports_api.status_code == 200
    assert reports_api.json["employee_scope"] is True
    assert all(item["full_name"] == "Evan Employee" for item in reports_api.json["employees"])
    assert all(item["employee_name"] == "Evan Employee" for item in reports_api.json["attendance"])
