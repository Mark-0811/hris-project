from datetime import date

from hris.app.extensions import db
from hris.app.models import AttendanceRecord, EmployeeShift, MobileDevice, Shift, User


def mobile_login(client, username, password):
    response = client.post(
        "/api/mobile/auth/login",
        json={
            "username": username,
            "password": password,
            "device_name": "Pixel Test",
            "platform": "android",
            "app_version": "1.0.0",
        },
    )
    assert response.status_code == 200
    return response.get_json()


def auth_headers(token: str):
    return {"Authorization": f"Bearer {token}"}


def test_mobile_login_and_me(client, seeded_data):
    payload = mobile_login(client, "employee1", "Password123!")
    assert payload["role_name"] == "Employee"
    assert "access_token" in payload
    response = client.get("/api/mobile/auth/me", headers=auth_headers(payload["access_token"]))
    assert response.status_code == 200
    assert response.get_json()["user_profile"]["username"] == "employee1"


def test_mobile_workspace_and_device_registration(client, seeded_data):
    payload = mobile_login(client, "employee1", "Password123!")
    workspace = client.get("/api/mobile/workspace", headers=auth_headers(payload["access_token"]))
    assert workspace.status_code == 200
    assert "cards" in workspace.get_json()

    device_response = client.post(
        "/api/mobile/auth/register-device-token",
        headers=auth_headers(payload["access_token"]),
        json={
            "fcm_token": "token-123",
            "platform": "android",
            "device_name": "Pixel Test",
            "device_model": "Pixel 9",
            "app_version": "1.0.0",
        },
    )
    assert device_response.status_code == 200
    with client.application.app_context():
        assert MobileDevice.query.filter_by(fcm_token="token-123").count() == 1


def test_mobile_employee_can_submit_attendance_correction(client, seeded_data):
    payload = mobile_login(client, "employee1", "Password123!")
    with client.application.app_context():
        employee_id = User.query.filter_by(username="employee1").first().employee_id
        shift_id = Shift.query.filter_by(shift_name="Default Office Shift").first().id
        if EmployeeShift.query.filter_by(employee_id=employee_id).count() == 0:
            db.session.add(EmployeeShift(employee_id=employee_id, shift_id=shift_id, effective_date=date.today()))
        record = AttendanceRecord(employee_id=employee_id, date=date.today(), status="incomplete")
        db.session.add(record)
        db.session.commit()
        record_id = record.id

    response = client.post(
        "/api/mobile/attendance/corrections",
        headers=auth_headers(payload["access_token"]),
        json={
            "attendance_record_id": record_id,
            "reason_template": "missed_punch",
            "details": "Forgot to time out after site visit.",
            "new_time_out": "2026-04-10T17:30:00",
        },
    )
    assert response.status_code == 201
    assert response.get_json()["status"] == "pending"


def test_mobile_employee_cannot_access_admin_summary(client, seeded_data):
    payload = mobile_login(client, "employee1", "Password123!")
    response = client.get("/api/mobile/admin/summary", headers=auth_headers(payload["access_token"]))
    assert response.status_code == 403


def test_mobile_admin_webview_bridge_launches_session(client, seeded_data):
    payload = mobile_login(client, "hradmin", "Password123!")
    modules_response = client.get("/api/mobile/admin/webview/modules", headers=auth_headers(payload["access_token"]))
    assert modules_response.status_code == 200
    assert any(item["slug"] == "user_access" for item in modules_response.get_json()["items"])

    bridge_response = client.post(
        "/api/mobile/admin/webview/bridge",
        headers=auth_headers(payload["access_token"]),
        json={"module_slug": "user_access"},
    )
    assert bridge_response.status_code == 200
    launch_url = bridge_response.get_json()["launch_url"]
    launch_response = client.get(launch_url)
    assert launch_response.status_code == 302
    assert "/users" in launch_response.headers["Location"]
