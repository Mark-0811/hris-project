from hris.app.extensions import db
from hris.app.models import AuditLog, MenuAccessRequest, MenuAccessTemplate, User, UserMenuAccess

from .conftest import login


def test_admin_can_save_exact_user_menu_assignments(client, app, seeded_data):
    login(client, username="hradmin", password="Password123!")
    with app.app_context():
        employee = User.query.filter_by(username="employee1").first()
        employee_id = employee.id

    response = client.post(
        f"/users/{employee_id}/menus",
        data={"menu_keys": ["dashboard", "profile"], "menu_action": "save"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Menu access updated successfully." in response.data

    with app.app_context():
        employee = db.session.get(User, employee_id)
        rows = UserMenuAccess.query.filter_by(user_id=employee_id).order_by(UserMenuAccess.menu_key.asc()).all()
        assert employee.menu_access_initialized is True
        assert [row.menu_key for row in rows] == ["dashboard", "profile"]


def test_menu_assignment_replaces_previous_values(client, app, seeded_data):
    login(client, username="hradmin", password="Password123!")
    with app.app_context():
        employee = User.query.filter_by(username="employee1").first()
        employee_id = employee.id

    client.post(
        f"/users/{employee_id}/menus",
        data={"menu_keys": ["dashboard", "profile", "leave"], "menu_action": "save"},
        follow_redirects=True,
    )
    client.post(
        f"/users/{employee_id}/menus",
        data={"menu_keys": ["profile"], "menu_action": "save"},
        follow_redirects=True,
    )

    with app.app_context():
        rows = UserMenuAccess.query.filter_by(user_id=employee_id).order_by(UserMenuAccess.menu_key.asc()).all()
        assert [row.menu_key for row in rows] == ["profile"]


def test_unassigned_menu_route_is_blocked_and_sidebar_updates(client, app, seeded_data):
    with app.app_context():
        employee = User.query.filter_by(username="employee1").first()
        employee.menu_access_initialized = True
        UserMenuAccess.query.filter_by(user_id=employee.id).delete()
        db.session.add(UserMenuAccess(user_id=employee.id, menu_key="dashboard"))
        db.session.add(UserMenuAccess(user_id=employee.id, menu_key="profile"))
        db.session.commit()

    response = login(client, username="employee1", password="Password123!")
    assert response.status_code == 200
    assert b'href="/auth/profile"' in response.data
    assert b'href="/leave/" class="sidebar-link"' not in response.data

    blocked = client.get("/leave/")
    assert blocked.status_code == 403

    allowed = client.get("/auth/profile")
    assert allowed.status_code == 200


def test_only_user_admin_roles_can_manage_user_menus(client, seeded_data):
    login(client, username="employee1", password="Password123!")
    response = client.get("/users/1/menus")
    assert response.status_code == 403


def test_access_governance_page_supports_templates_and_requests(client, app, seeded_data):
    login(client, username="hradmin", password="Password123!")

    template_response = client.post(
        "/users/access-governance",
        data={
            "access_action": "create_template",
            "template_name": "Manager Lite",
            "template_description": "Reduced manager access",
            "template_role_name": "Manager",
            "template_menu_keys": ["dashboard", "profile", "team_attendance"],
        },
        follow_redirects=True,
    )
    assert template_response.status_code == 200
    assert b"Access template saved." in template_response.data

    with app.app_context():
        template = MenuAccessTemplate.query.filter_by(name="Manager Lite").first()
        assert template is not None

        employee = User.query.filter_by(username="employee1").first()
        employee_id = employee.id

    request_response = client.post(
        f"/users/{employee_id}/menus",
        data={
            "menu_action": "request_access",
            "menu_keys": ["dashboard", "profile", "leave"],
            "request_reason": "Need leave access",
        },
        follow_redirects=True,
    )
    assert request_response.status_code == 200
    assert b"Access request submitted for review." in request_response.data

    with app.app_context():
        request_obj = MenuAccessRequest.query.filter_by(user_id=employee_id).first()
        assert request_obj is not None
        assert request_obj.status == "pending"


def test_emergency_lock_and_audit_log_are_recorded(client, app, seeded_data):
    login(client, username="hradmin", password="Password123!")
    with app.app_context():
        employee = User.query.filter_by(username="employee1").first()
        employee_id = employee.id

    response = client.post(
        f"/users/{employee_id}/menus",
        data={"menu_action": "emergency_lock"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Emergency lock applied" in response.data

    with app.app_context():
        keys = sorted(row.menu_key for row in UserMenuAccess.query.filter_by(user_id=employee_id).all())
        assert keys == ["profile"]
        assert AuditLog.query.filter_by(module="menu_access").count() > 0
