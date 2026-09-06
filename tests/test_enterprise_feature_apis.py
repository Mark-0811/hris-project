from datetime import date

from hris.app.extensions import db
from hris.app.models import (
    ApprovalInstance,
    AttendanceAnomaly,
    AttendanceRecord,
    PayrollCutoff,
    PayrollEntry,
    TaskInboxItem,
    User,
)

from .conftest import login


def test_task_inbox_api_uses_standard_envelope(client, app, seeded_data):
    with app.app_context():
        user = User.query.filter_by(username="employee1").first()
        db.session.add(
            TaskInboxItem(
                user_id=user.id,
                task_type="leave",
                title="Submit leave attachment",
                description="Upload supporting document.",
                status="open",
                reference_module="leave",
                reference_id=1,
            )
        )
        db.session.commit()

    login(client, username="employee1")
    response = client.get("/enterprise/api/tasks")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["status"] == "success"
    assert payload["trace_id"]
    assert len(payload["data"]) >= 1


def test_attendance_exception_api_allows_admin_resolution(client, app, seeded_data):
    with app.app_context():
        employee = seeded_data["staff_employee"]
        record = AttendanceRecord(employee_id=employee.id, date=date.today(), status="incomplete")
        db.session.add(record)
        db.session.flush()
        anomaly = AttendanceAnomaly(
            attendance_record_id=record.id,
            employee_id=employee.id,
            date=record.date,
            anomaly_type="missing_time_in",
            severity="high",
            score=0.9,
            status="open",
            details="Missing time in",
        )
        db.session.add(anomaly)
        db.session.commit()
        anomaly_id = anomaly.id

    login(client, username="hradmin")
    response = client.post(
        f"/enterprise/api/attendance-exceptions/{anomaly_id}/resolve",
        json={"action": "resolve", "remarks": "Validated."},
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["status"] == "success"
    assert payload["data"]["status"] == "resolved"


def test_notification_preferences_upsert(client, app, seeded_data):
    login(client, username="employee1")
    response = client.post(
        "/enterprise/api/notification-preferences",
        json={
            "event_type": "leave_updates",
            "in_app_enabled": True,
            "email_enabled": True,
            "sms_enabled": False,
        },
    )
    payload = response.get_json()
    assert response.status_code == 201
    assert payload["status"] == "success"
    assert payload["data"]["event_type"] == "leave_updates"


def test_payroll_validation_reports_blockers(client, app, seeded_data):
    with app.app_context():
        cutoff = PayrollCutoff(
            cutoff_name="April A",
            start_date=date.today(),
            end_date=date.today(),
            status="open",
        )
        db.session.add(cutoff)
        db.session.commit()
        cutoff_id = cutoff.id

    login(client, username="hradmin")
    response = client.get(f"/enterprise/api/payroll/validation/{cutoff_id}")
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["status"] == "error"
    assert payload["data"]["blockers"]


def test_payslip_dispute_created_by_employee(client, app, seeded_data):
    with app.app_context():
        employee = seeded_data["staff_employee"]
        cutoff = PayrollCutoff(
            cutoff_name="April B",
            start_date=date.today(),
            end_date=date.today(),
            status="open",
        )
        db.session.add(cutoff)
        db.session.flush()
        entry = PayrollEntry(
            employee_id=employee.id,
            cutoff_id=cutoff.id,
            basic_pay=1000,
            net_pay=900,
            status="released",
        )
        db.session.add(entry)
        db.session.commit()
        entry_id = entry.id

    login(client, username="employee1")
    response = client.post(
        "/enterprise/api/payroll/disputes",
        json={
            "payroll_entry_id": entry_id,
            "subject": "Net pay mismatch",
            "details": "Please review overtime amount.",
        },
    )
    payload = response.get_json()
    assert response.status_code == 201
    assert payload["status"] == "success"


def test_approval_escalation_endpoint(client, app, seeded_data):
    with app.app_context():
        row = ApprovalInstance(module="leave", record_id=99, current_step=1, total_steps=2, status="submitted")
        db.session.add(row)
        db.session.commit()

    login(client, username="hradmin")
    response = client.post("/enterprise/api/approval-workflows/escalate", json={"hours": 1})
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["status"] == "success"
    assert "escalated_count" in payload["data"]


def test_ai_assist_endpoint_generates_actions(client, app, seeded_data):
    login(client, username="hradmin")
    response = client.post(
        "/enterprise/api/ai/assist",
        json={
            "prompt": "Review attendance anomalies and create follow-up tasks",
            "execute": True,
        },
    )
    payload = response.get_json()
    assert response.status_code == 201
    assert payload["status"] == "success"
    assert payload["data"]["actions"]
