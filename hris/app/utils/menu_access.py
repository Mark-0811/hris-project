from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timedelta
import json

from flask import request
from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError, ProgrammingError

from ..extensions import db
from ..models import AuditLog, MenuAccessRequest, MenuAccessTemplate, User, UserMenuAccess
from .constants import (
    ROLE_BIOMETRICS_API,
    ROLE_EMPLOYEE,
    ROLE_HR_ADMIN,
    ROLE_MANAGER,
    ROLE_PAYROLL_ADMIN,
    ROLE_SUPER_ADMIN,
    USER_ADMIN_ROLES,
)

MENU_CATALOG = (
    {
        "key": "dashboard",
        "label": "Dashboard",
        "icon": "bi bi-grid-fill",
        "endpoint": "admin.dashboard",
        "section": "Overview",
        "default_roles": (
            ROLE_SUPER_ADMIN,
            ROLE_HR_ADMIN,
            ROLE_PAYROLL_ADMIN,
            ROLE_MANAGER,
            ROLE_EMPLOYEE,
            ROLE_BIOMETRICS_API,
        ),
        "active_endpoints": ("admin.dashboard",),
    },
    {
        "key": "my_workspace",
        "label": "My Workspace",
        "icon": "bi bi-house-heart-fill",
        "endpoint": "experience.workspace",
        "section": "My Workspace",
        "default_roles": (
            ROLE_MANAGER,
            ROLE_EMPLOYEE,
        ),
        "active_endpoints": (
            "experience.workspace",
            "experience.timeline",
            "experience.onboarding",
            "experience.exit_center",
        ),
        "protected_endpoints": (
            "experience.workspace",
            "experience.timeline",
            "experience.onboarding",
            "experience.exit_center",
        ),
    },
    {
        "key": "my_schedule",
        "label": "My Schedule",
        "icon": "bi bi-calendar3-week-fill",
        "endpoint": "experience.schedule",
        "section": "My Workspace",
        "default_roles": (
            ROLE_MANAGER,
            ROLE_EMPLOYEE,
        ),
        "active_endpoints": ("experience.schedule",),
        "protected_endpoints": ("experience.schedule",),
    },
    {
        "key": "my_requests",
        "label": "My Requests",
        "icon": "bi bi-inboxes-fill",
        "endpoint": "experience.requests_home",
        "section": "My Workspace",
        "default_roles": (
            ROLE_MANAGER,
            ROLE_EMPLOYEE,
        ),
        "active_endpoints": (
            "experience.requests_home",
            "experience.cancel_leave_request",
        ),
        "protected_endpoints": (
            "experience.requests_home",
            "experience.cancel_leave_request",
        ),
    },
    {
        "key": "my_documents",
        "label": "My Documents",
        "icon": "bi bi-folder2-open",
        "endpoint": "experience.documents",
        "section": "My Workspace",
        "default_roles": (
            ROLE_MANAGER,
            ROLE_EMPLOYEE,
        ),
        "active_endpoints": (
            "experience.documents",
            "experience.download_document",
        ),
        "protected_endpoints": (
            "experience.documents",
            "experience.download_document",
        ),
    },
    {
        "key": "help_center",
        "label": "Help Center",
        "icon": "bi bi-life-preserver",
        "endpoint": "experience.help_center",
        "section": "My Workspace",
        "default_roles": (
            ROLE_MANAGER,
            ROLE_EMPLOYEE,
        ),
        "active_endpoints": ("experience.help_center",),
        "protected_endpoints": ("experience.help_center",),
    },
    {
        "key": "learning",
        "label": "Learning",
        "icon": "bi bi-mortarboard-fill",
        "endpoint": "experience.learning",
        "section": "My Workspace",
        "default_roles": (
            ROLE_MANAGER,
            ROLE_EMPLOYEE,
        ),
        "active_endpoints": ("experience.learning",),
        "protected_endpoints": ("experience.learning",),
    },
    {
        "key": "surveys",
        "label": "Surveys",
        "icon": "bi bi-clipboard2-pulse-fill",
        "endpoint": "experience.surveys",
        "section": "My Workspace",
        "default_roles": (
            ROLE_MANAGER,
            ROLE_EMPLOYEE,
        ),
        "active_endpoints": (
            "experience.surveys",
            "experience.respond_survey",
        ),
        "protected_endpoints": (
            "experience.surveys",
            "experience.respond_survey",
        ),
    },
    {
        "key": "attendance",
        "label": "Attendance",
        "icon": "bi bi-clock-history",
        "endpoint": "attendance.index",
        "section": "My Workspace",
        "default_roles": (
            ROLE_SUPER_ADMIN,
            ROLE_HR_ADMIN,
            ROLE_PAYROLL_ADMIN,
            ROLE_MANAGER,
            ROLE_EMPLOYEE,
        ),
        "active_endpoints": (
            "attendance.index",
            "attendance.my_logs",
            "attendance.create_record",
            "attendance.edit_record",
            "attendance.create_adjustment",
            "attendance.approve",
        ),
        "protected_endpoints": (
            "attendance.index",
            "attendance.my_logs",
            "attendance.create_record",
            "attendance.edit_record",
            "attendance.create_adjustment",
            "attendance.approve",
            "attendance.api_summary",
            "attendance.api_records",
        ),
    },
    {
        "key": "attendance_anomalies",
        "label": "Attendance Anomalies",
        "icon": "bi bi-exclamation-triangle",
        "endpoint": "attendance.anomalies",
        "section": "My Workspace",
        "default_roles": (
            ROLE_SUPER_ADMIN,
            ROLE_HR_ADMIN,
            ROLE_PAYROLL_ADMIN,
            ROLE_MANAGER,
        ),
        "active_endpoints": ("attendance.anomalies",),
        "protected_endpoints": ("attendance.anomalies", "attendance.scan_anomalies"),
    },
    {
        "key": "leave",
        "label": "Leave",
        "icon": "bi bi-calendar-check-fill",
        "endpoint": "leave.index",
        "section": "My Workspace",
        "default_roles": (
            ROLE_SUPER_ADMIN,
            ROLE_HR_ADMIN,
            ROLE_PAYROLL_ADMIN,
            ROLE_MANAGER,
            ROLE_EMPLOYEE,
        ),
        "active_endpoints": (
            "leave.index",
            "leave.create_type",
            "leave.create_balance",
            "leave.adjust_balance",
            "leave.create_request",
            "leave.approve_request",
            "leave.disapprove_request",
        ),
        "protected_endpoints": (
            "leave.index",
            "leave.create_type",
            "leave.create_balance",
            "leave.adjust_balance",
            "leave.create_request",
            "leave.approve_request",
            "leave.disapprove_request",
            "leave.api_summary",
            "leave.api_requests",
        ),
    },
    {
        "key": "reports",
        "label": "Reports",
        "icon": "bi bi-bar-chart-line-fill",
        "endpoint": "reports.index",
        "section": "My Workspace",
        "default_roles": (
            ROLE_SUPER_ADMIN,
            ROLE_HR_ADMIN,
            ROLE_PAYROLL_ADMIN,
            ROLE_MANAGER,
        ),
        "active_endpoints": ("reports.index", "reports.scheduler"),
        "protected_endpoints": ("reports.index", "reports.scheduler", "reports.api_reports"),
    },
    {
        "key": "tasks",
        "label": "Task Inbox",
        "icon": "bi bi-list-check",
        "endpoint": "admin.tasks",
        "section": "My Workspace",
        "default_roles": (
            ROLE_SUPER_ADMIN,
            ROLE_HR_ADMIN,
            ROLE_PAYROLL_ADMIN,
            ROLE_MANAGER,
        ),
        "active_endpoints": ("admin.tasks",),
    },
    {
        "key": "messages",
        "label": "Messages",
        "icon": "bi bi-chat-dots-fill",
        "endpoint": "chat.index",
        "section": "My Workspace",
        "default_roles": (
            ROLE_SUPER_ADMIN,
            ROLE_HR_ADMIN,
            ROLE_PAYROLL_ADMIN,
            ROLE_MANAGER,
        ),
        "active_endpoints": ("chat.index", "chat.send_attachment_message"),
        "protected_endpoints": ("chat.index", "chat.send_attachment_message"),
    },
    {
        "key": "profile",
        "label": "Profile",
        "icon": "bi bi-person-circle",
        "endpoint": "auth.profile",
        "section": "My Workspace",
        "default_roles": (
            ROLE_SUPER_ADMIN,
            ROLE_HR_ADMIN,
            ROLE_PAYROLL_ADMIN,
            ROLE_MANAGER,
            ROLE_EMPLOYEE,
            ROLE_BIOMETRICS_API,
        ),
        "active_endpoints": ("auth.profile",),
        "protected_endpoints": ("auth.profile",),
    },
    {
        "key": "team_approvals",
        "label": "Approvals",
        "icon": "bi bi-check2-square",
        "endpoint": "leave.index",
        "section": "Team",
        "default_roles": (ROLE_MANAGER,),
        "active_endpoints": (
            "leave.index",
            "leave.approve_request",
            "leave.disapprove_request",
        ),
    },
    {
        "key": "team_attendance",
        "label": "Team Attendance",
        "icon": "bi bi-people-fill",
        "endpoint": "attendance.index",
        "section": "Team",
        "default_roles": (ROLE_MANAGER,),
        "active_endpoints": (
            "attendance.index",
            "attendance.create_record",
            "attendance.edit_record",
            "attendance.create_adjustment",
            "attendance.approve",
        ),
    },
    {
        "key": "employees",
        "label": "Employees",
        "endpoint": "employees.list_employee",
        "section": "HR Admin",
        "group": "People",
        "group_icon": "bi bi-people-fill",
        "default_roles": (ROLE_SUPER_ADMIN, ROLE_HR_ADMIN),
        "active_endpoints": (
            "employees.list_employee",
            "employees.create_employee",
            "employees.edit_employee",
            "employees.detail_employee",
            "employees.toggle_employee",
        ),
        "protected_endpoints": (
            "employees.list_employee",
            "employees.create_employee",
            "employees.edit_employee",
            "employees.detail_employee",
            "employees.toggle_employee",
        ),
    },
    {
        "key": "departments",
        "label": "Departments",
        "endpoint": "employees.list_department",
        "section": "HR Admin",
        "group": "People",
        "group_icon": "bi bi-people-fill",
        "default_roles": (ROLE_SUPER_ADMIN, ROLE_HR_ADMIN),
        "active_endpoints": (
            "employees.list_department",
            "employees.create_department",
            "employees.edit_department",
        ),
        "protected_endpoints": (
            "employees.list_department",
            "employees.create_department",
            "employees.edit_department",
        ),
    },
    {
        "key": "positions",
        "label": "Positions",
        "endpoint": "employees.list_position",
        "section": "HR Admin",
        "group": "People",
        "group_icon": "bi bi-people-fill",
        "default_roles": (ROLE_SUPER_ADMIN, ROLE_HR_ADMIN),
        "active_endpoints": (
            "employees.list_position",
            "employees.create_position",
            "employees.edit_position",
        ),
        "protected_endpoints": (
            "employees.list_position",
            "employees.create_position",
            "employees.edit_position",
        ),
    },
    {
        "key": "schedules",
        "label": "Schedules",
        "endpoint": "employees.list_schedule",
        "section": "HR Admin",
        "group": "People",
        "group_icon": "bi bi-people-fill",
        "default_roles": (ROLE_SUPER_ADMIN, ROLE_HR_ADMIN),
        "active_endpoints": (
            "employees.list_schedule",
            "employees.create_schedule",
            "employees.edit_schedule",
        ),
        "protected_endpoints": (
            "employees.list_schedule",
            "employees.create_schedule",
            "employees.edit_schedule",
        ),
    },
    {
        "key": "users",
        "label": "User Access",
        "endpoint": "admin.users",
        "section": "HR Admin",
        "group": "HR Workspace",
        "group_icon": "bi bi-sliders",
        "default_roles": (ROLE_SUPER_ADMIN, ROLE_HR_ADMIN),
        "active_endpoints": (
            "admin.users",
            "admin.create_user",
            "admin.edit_user",
            "admin.reset_password",
            "admin.manage_user_menus",
        ),
        "protected_endpoints": (
            "admin.users",
            "admin.create_user",
            "admin.edit_user",
            "admin.reset_password",
            "admin.manage_user_menus",
            "admin.toggle_user",
        ),
    },
    {
        "key": "news",
        "label": "News",
        "endpoint": "admin.news",
        "section": "HR Admin",
        "group": "HR Workspace",
        "group_icon": "bi bi-sliders",
        "default_roles": (ROLE_SUPER_ADMIN, ROLE_HR_ADMIN),
        "active_endpoints": (
            "admin.news",
            "admin.create_news",
            "admin.edit_news",
        ),
        "protected_endpoints": (
            "admin.news",
            "admin.create_news",
            "admin.edit_news",
        ),
    },
    {
        "key": "bulk_actions",
        "label": "Bulk Actions",
        "endpoint": "admin.bulk_actions",
        "section": "HR Admin",
        "group": "HR Workspace",
        "group_icon": "bi bi-sliders",
        "default_roles": (ROLE_SUPER_ADMIN, ROLE_HR_ADMIN),
        "active_endpoints": ("admin.bulk_actions",),
        "protected_endpoints": ("admin.bulk_actions",),
    },
    {
        "key": "enterprise",
        "label": "Enterprise Center",
        "endpoint": "enterprise.index",
        "section": "HR Admin",
        "group": "HR Workspace",
        "group_icon": "bi bi-sliders",
        "default_roles": (ROLE_SUPER_ADMIN, ROLE_HR_ADMIN),
        "active_endpoints": (
            "enterprise.index",
            "enterprise.compliance",
            "enterprise.integrations",
            "enterprise.data_health",
            "enterprise.tickets",
            "enterprise.compliance_records",
            "enterprise.integrations_manage",
            "enterprise.data_health_checks",
        ),
        "protected_endpoints": (
            "enterprise.index",
            "enterprise.compliance",
            "enterprise.integrations",
            "enterprise.data_health",
            "enterprise.tickets",
            "enterprise.update_ticket_status",
            "enterprise.compliance_records",
            "enterprise.integrations_manage",
            "enterprise.data_health_checks",
            "enterprise.api_search",
        ),
    },
    {
        "key": "access_governance",
        "label": "Access Governance",
        "endpoint": "admin.access_governance",
        "section": "HR Admin",
        "group": "HR Workspace",
        "group_icon": "bi bi-sliders",
        "default_roles": (ROLE_SUPER_ADMIN, ROLE_HR_ADMIN),
        "active_endpoints": (
            "admin.access_governance",
            "admin.approve_access_request",
        ),
        "protected_endpoints": (
            "admin.access_governance",
            "admin.approve_access_request",
            "admin.review_profile_request",
        ),
    },
    {
        "key": "payroll",
        "label": "Payroll",
        "icon": "bi bi-cash-coin",
        "endpoint": "payroll.index",
        "section": "Payroll",
        "default_roles": (
            ROLE_SUPER_ADMIN,
            ROLE_HR_ADMIN,
            ROLE_PAYROLL_ADMIN,
        ),
        "active_endpoints": (
            "payroll.index",
            "payroll.create_cutoff",
            "payroll.create_salary",
            "payroll.create_allowance",
            "payroll.create_deduction",
            "payroll.generate",
            "payroll.post_payroll",
            "payroll.download_entry_pdf",
        ),
        "protected_endpoints": (
            "payroll.index",
            "payroll.create_cutoff",
            "payroll.create_salary",
            "payroll.create_allowance",
            "payroll.create_deduction",
            "payroll.generate",
            "payroll.post_payroll",
            "payroll.api_summary",
            "payroll.api_entries",
            "payroll.download_entry_pdf",
        ),
    },
    {
        "key": "kiosk",
        "label": "Kiosk Terminal",
        "icon": "bi bi-credit-card-2-front-fill",
        "endpoint": "attendance.kiosk",
        "section": "Platform",
        "default_roles": (ROLE_SUPER_ADMIN,),
        "active_endpoints": ("attendance.kiosk",),
        "protected_endpoints": ("attendance.kiosk",),
    },
    {
        "key": "api_requests",
        "label": "API Requests",
        "icon": "bi bi-cloud-arrow-up-fill",
        "endpoint": "admin.api_requests",
        "section": "Platform",
        "default_roles": (ROLE_SUPER_ADMIN,),
        "active_endpoints": ("admin.api_requests",),
        "protected_endpoints": ("admin.api_requests",),
    },
)

MENU_BY_KEY = {item["key"]: item for item in MENU_CATALOG}
PROTECTED_ENDPOINTS: dict[str, tuple[str, ...]] = {}
for menu_item in MENU_CATALOG:
    for protected_endpoint in menu_item.get("protected_endpoints", (menu_item["endpoint"],)):
        PROTECTED_ENDPOINTS.setdefault(protected_endpoint, tuple())
        PROTECTED_ENDPOINTS[protected_endpoint] = tuple(
            OrderedDict.fromkeys(PROTECTED_ENDPOINTS[protected_endpoint] + (menu_item["key"],))
        )


def menu_catalog() -> tuple[dict, ...]:
    return MENU_CATALOG


def menu_catalog_keys() -> set[str]:
    return set(MENU_BY_KEY)


def default_menu_keys_for_role(role_name: str | None) -> list[str]:
    if not role_name:
        return []
    return [item["key"] for item in MENU_CATALOG if role_name in item.get("default_roles", ())]


def _menu_access_table_available() -> bool:
    try:
        return inspect(db.engine).has_table(UserMenuAccess.__tablename__)
    except Exception:
        return False


def _user_role_name(user) -> str:
    return user.role.name if user and getattr(user, "role", None) else ""


def get_user_menu_keys(user) -> set[str]:
    if not user or not getattr(user, "is_authenticated", False):
        return set()

    if not _menu_access_table_available():
        return set(default_menu_keys_for_role(_user_role_name(user)))

    if not getattr(user, "menu_access_initialized", False):
        return set(default_menu_keys_for_role(_user_role_name(user)))

    try:
        rows = (
            UserMenuAccess.query.filter_by(user_id=user.id)
            .order_by(UserMenuAccess.menu_key.asc())
            .all()
        )
    except (OperationalError, ProgrammingError):
        return set(default_menu_keys_for_role(_user_role_name(user)))
    now = datetime.utcnow()
    return {
        row.menu_key
        for row in rows
        if row.menu_key in MENU_BY_KEY and (row.expires_at is None or row.expires_at > now)
    }


def user_has_menu_access(user, *menu_keys: str) -> bool:
    if not menu_keys:
        return True
    assigned_keys = get_user_menu_keys(user)
    return any(menu_key in assigned_keys for menu_key in menu_keys)


def can_access_endpoint(user, endpoint: str | None) -> bool:
    if not endpoint:
        return True
    required_menu_keys = PROTECTED_ENDPOINTS.get(endpoint)
    if not required_menu_keys:
        return True
    return user_has_menu_access(user, *required_menu_keys)


def first_accessible_endpoint(user) -> str | None:
    for item in MENU_CATALOG:
        if user_has_menu_access(user, item["key"]):
            return item["endpoint"]
    return None


def build_sidebar_sections(user, current_endpoint: str | None = None) -> list[dict]:
    visible_keys = get_user_menu_keys(user)
    sections: list[dict] = []
    section_lookup: dict[str, dict] = {}

    for item in MENU_CATALOG:
        if item["key"] not in visible_keys:
            continue

        section = section_lookup.get(item["section"])
        if section is None:
            section = {"title": item["section"], "items": [], "groups": OrderedDict()}
            section_lookup[item["section"]] = section
            sections.append(section)

        item_is_active = current_endpoint in item.get("active_endpoints", (item["endpoint"],))
        group_name = item.get("group")
        if group_name:
            group_entry = section["groups"].get(group_name)
            if group_entry is None:
                group_entry = {
                    "type": "group",
                    "label": group_name,
                    "icon": item.get("group_icon", "bi bi-circle"),
                    "children": [],
                    "active": False,
                }
                section["groups"][group_name] = group_entry
                section["items"].append(group_entry)
            group_entry["children"].append(
                {
                    "type": "link",
                    "key": item["key"],
                    "label": item["label"],
                    "endpoint": item["endpoint"],
                    "active": item_is_active,
                }
            )
            if item_is_active:
                group_entry["active"] = True
            continue

        section["items"].append(
            {
                "type": "link",
                "key": item["key"],
                "label": item["label"],
                "icon": item["icon"],
                "endpoint": item["endpoint"],
                "active": item_is_active,
            }
        )

    return sections


def build_manageable_menu_sections() -> list[dict]:
    sections: list[dict] = []
    section_lookup: dict[str, dict] = {}

    for item in MENU_CATALOG:
        section = section_lookup.get(item["section"])
        if section is None:
            section = {"title": item["section"], "groups": OrderedDict(), "items": []}
            section_lookup[item["section"]] = section
            sections.append(section)

        group_name = item.get("group")
        if group_name:
            group = section["groups"].get(group_name)
            if group is None:
                group = {"label": group_name, "items": []}
                section["groups"][group_name] = group
                section["items"].append(group)
            group["items"].append(item)
            continue

        section["items"].append({"label": None, "items": [item]})

    return sections


def save_user_menu_access(user, menu_keys: list[str] | set[str] | tuple[str, ...]) -> None:
    save_user_menu_access_with_metadata(user, menu_keys)


def save_user_menu_access_with_metadata(
    user,
    menu_keys: list[str] | set[str] | tuple[str, ...],
    assigned_by_user_id: int | None = None,
    expires_at: datetime | None = None,
    commit: bool = True,
) -> None:
    normalized_keys = sorted(set(menu_keys) & menu_catalog_keys())
    previous_keys = sorted(get_user_menu_keys(user))
    UserMenuAccess.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    for menu_key in normalized_keys:
        db.session.add(
            UserMenuAccess(
                user_id=user.id,
                menu_key=menu_key,
                assigned_by_user_id=assigned_by_user_id,
                expires_at=expires_at,
            )
        )
    user.menu_access_initialized = True
    log_menu_change(
        actor_user_id=assigned_by_user_id,
        target_user_id=user.id,
        action="update",
        description=f"Menu access changed from {previous_keys} to {normalized_keys}",
    )
    if commit:
        db.session.commit()


def seed_user_menu_access(user, force: bool = False) -> None:
    if not user:
        return
    if not force and getattr(user, "menu_access_initialized", False):
        return
    default_keys = default_menu_keys_for_role(_user_role_name(user))
    UserMenuAccess.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    for menu_key in default_keys:
        db.session.add(UserMenuAccess(user_id=user.id, menu_key=menu_key))
    user.menu_access_initialized = True


def recommended_menu_keys_for_user(user) -> list[str]:
    return default_menu_keys_for_role(_user_role_name(user))


def backfill_all_user_menu_access() -> None:
    if not _menu_access_table_available():
        return
    from ..models import User

    users = User.query.order_by(User.id.asc()).all()
    for user in users:
        if getattr(user, "menu_access_initialized", False):
            continue
        seed_user_menu_access(user)
    db.session.commit()


def user_can_manage_menu_assignments(user) -> bool:
    return bool(
        user
        and getattr(user, "is_authenticated", False)
        and getattr(user, "role", None)
        and user.role.name in USER_ADMIN_ROLES
    )


def log_menu_change(actor_user_id: int | None, target_user_id: int, action: str, description: str) -> None:
    ip_address = None
    try:
        ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)
    except RuntimeError:
        ip_address = None
    db.session.add(
        AuditLog(
            user_id=actor_user_id,
            module="menu_access",
            action=action,
            record_id=str(target_user_id),
            description=description,
            ip_address=ip_address,
        )
    )


def record_menu_access(endpoint: str | None, user) -> None:
    if not endpoint or not user or not getattr(user, "is_authenticated", False):
        return
    menu_keys = PROTECTED_ENDPOINTS.get(endpoint, ())
    if not menu_keys:
        return
    now = datetime.utcnow()
    updated = False
    for row in UserMenuAccess.query.filter(UserMenuAccess.user_id == user.id, UserMenuAccess.menu_key.in_(menu_keys)).all():
        row.last_seen_at = now
        updated = True
    if updated:
        db.session.commit()


def _json_keys(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    try:
        data = json.loads(raw_value)
    except (TypeError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if item in MENU_BY_KEY]


def _dump_keys(menu_keys: list[str] | set[str] | tuple[str, ...]) -> str:
    return json.dumps(sorted(set(menu_keys) & menu_catalog_keys()))


def list_menu_access_templates() -> list[MenuAccessTemplate]:
    return MenuAccessTemplate.query.order_by(MenuAccessTemplate.name.asc()).all()


def create_menu_access_template(name: str, description: str, role_name: str, menu_keys, created_by_user_id: int | None):
    template = MenuAccessTemplate.query.filter_by(name=name).first()
    if template is None:
        template = MenuAccessTemplate(name=name)
        db.session.add(template)
    template.description = description or None
    template.role_name = role_name or None
    template.menu_keys_json = _dump_keys(menu_keys)
    template.created_by_user_id = created_by_user_id
    log_menu_change(created_by_user_id, 0, "template_save", f"Saved template {name} with keys {sorted(set(menu_keys))}")
    db.session.commit()
    return template


def template_menu_keys(template: MenuAccessTemplate) -> list[str]:
    return _json_keys(template.menu_keys_json)


def create_access_request(user, menu_keys, reason: str) -> MenuAccessRequest:
    request_obj = MenuAccessRequest(
        user_id=user.id,
        requested_menu_keys_json=_dump_keys(menu_keys),
        reason=(reason or "").strip() or None,
    )
    db.session.add(request_obj)
    log_menu_change(user.id, user.id, "request_create", f"Requested menu access for {sorted(set(menu_keys))}")
    db.session.commit()
    return request_obj


def list_access_requests(status: str | None = None) -> list[MenuAccessRequest]:
    query = MenuAccessRequest.query.order_by(MenuAccessRequest.created_at.desc())
    if status:
        query = query.filter_by(status=status)
    return query.all()


def access_request_menu_keys(request_obj: MenuAccessRequest) -> list[str]:
    return _json_keys(request_obj.requested_menu_keys_json)


def review_access_request(request_obj: MenuAccessRequest, reviewer_id: int, approved: bool, decision_notes: str = "") -> None:
    request_obj.status = "approved" if approved else "rejected"
    request_obj.reviewer_id = reviewer_id
    request_obj.reviewed_at = datetime.utcnow()
    request_obj.decision_notes = (decision_notes or "").strip() or None
    if approved:
        requester = db.session.get(User, request_obj.user_id)
        if requester:
            save_user_menu_access_with_metadata(
                requester,
                access_request_menu_keys(request_obj),
                assigned_by_user_id=reviewer_id,
            )
            return
    log_menu_change(reviewer_id, request_obj.user_id, request_obj.status, f"Access request #{request_obj.id} reviewed")
    db.session.commit()


def apply_template_to_user(user, template: MenuAccessTemplate, actor_user_id: int | None = None, expires_in_days: int | None = None):
    expires_at = None
    if expires_in_days and expires_in_days > 0:
        expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
    save_user_menu_access_with_metadata(
        user,
        template_menu_keys(template),
        assigned_by_user_id=actor_user_id,
        expires_at=expires_at,
    )


def bulk_apply_template(template_id: int, actor_user_id: int | None = None, role_name: str | None = None, source_user_id: int | None = None):
    template = db.session.get(MenuAccessTemplate, template_id) if template_id else None
    if source_user_id:
        source_user = db.session.get(User, source_user_id)
        menu_keys = get_user_menu_keys(source_user) if source_user else set()
        description = f"Bulk copied menu access from user {source_user_id}"
    else:
        menu_keys = template_menu_keys(template) if template else []
        description = f"Bulk applied template {template.name if template else template_id}"
    query = User.query
    if role_name:
        query = query.join(User.role).filter_by(name=role_name)
    targets = query.order_by(User.id.asc()).all()
    updated_count = 0
    for user in targets:
        save_user_menu_access_with_metadata(user, menu_keys, assigned_by_user_id=actor_user_id)
        updated_count += 1
    log_menu_change(actor_user_id, 0, "bulk_apply", f"{description} to {updated_count} user(s)")
    db.session.commit()
    return updated_count


def emergency_lock_user(user, actor_user_id: int | None = None):
    save_user_menu_access_with_metadata(
        user,
        ["profile"],
        assigned_by_user_id=actor_user_id,
    )


def access_summary_for_user(user) -> dict:
    assigned_keys = sorted(get_user_menu_keys(user))
    recommended_keys = set(recommended_menu_keys_for_user(user))
    custom_only = [key for key in assigned_keys if key not in recommended_keys]
    missing_recommended = [key for key in sorted(recommended_keys) if key not in assigned_keys]
    return {
        "assigned_count": len(assigned_keys),
        "assigned_keys": assigned_keys,
        "custom_only": custom_only,
        "missing_recommended": missing_recommended,
    }


def dormant_access_rows(days: int = 30) -> list[UserMenuAccess]:
    if not _menu_access_table_available():
        return []
    cutoff = datetime.utcnow() - timedelta(days=days)
    return (
        UserMenuAccess.query.filter(
            UserMenuAccess.expires_at.is_(None) | (UserMenuAccess.expires_at > datetime.utcnow())
        )
        .filter((UserMenuAccess.last_seen_at.is_(None)) | (UserMenuAccess.last_seen_at < cutoff))
        .order_by(UserMenuAccess.last_seen_at.asc().nullsfirst(), UserMenuAccess.user_id.asc())
        .all()
    )


def recent_menu_audit_logs(limit: int = 25) -> list[AuditLog]:
    return (
        AuditLog.query.filter_by(module="menu_access")
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )


def backfill_default_templates() -> None:
    for role_name in {item for entry in MENU_CATALOG for item in entry.get("default_roles", ())}:
        template_name = f"{role_name} Default"
        template = MenuAccessTemplate.query.filter_by(name=template_name).first()
        if template is None:
            db.session.add(
                MenuAccessTemplate(
                    name=template_name,
                    role_name=role_name,
                    description=f"Recommended menu set for {role_name}.",
                    menu_keys_json=_dump_keys(default_menu_keys_for_role(role_name)),
                )
            )
    db.session.commit()
