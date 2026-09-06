from datetime import date, datetime, timedelta
import secrets
from pathlib import Path
import re

from flask import current_app
from sqlalchemy import func
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import Announcement, AttendanceRecord, Department, Employee, LeaveBalance, LeaveRequest, Notification, Role, User, UserMenuAccess
from ..utils.constants import ADMIN_ROLES, ROLE_BIOMETRICS_API, ROLE_EMPLOYEE, ROLE_HR_ADMIN, ROLE_MANAGER, ROLE_SUPER_ADMIN
from ..utils.menu_access import can_access_endpoint, recommended_menu_keys_for_user, save_user_menu_access, seed_user_menu_access


def get_admin_dashboard_metrics(user):
    metrics = {
        "total_employees": Employee.query.count(),
        "active_users": User.query.filter_by(is_active=True).count(),
        "departments": Department.query.count(),
        "pending_leave_requests": LeaveRequest.query.filter_by(status="pending").count(),
        "today_attendance_count": AttendanceRecord.query.filter(
            AttendanceRecord.date == date.today(),
            AttendanceRecord.status.in_(["present", "late", "approved"]),
        ).count(),
    }

    if user.role and user.role.name not in ADMIN_ROLES:
        metrics.pop("active_users", None)
        metrics.pop("departments", None)

    return metrics


def get_dashboard_cards(user):
    labels = {
        "total_employees": "Employees",
        "active_users": "Active Users",
        "departments": "Departments",
        "pending_leave_requests": "Pending Leave Requests",
        "today_attendance_count": "Attendance Today",
    }
    metrics = get_admin_dashboard_metrics(user)
    return [{"label": labels[key], "value": value} for key, value in metrics.items()]


def _role_name(user) -> str:
    return user.role.name if user and user.role else ""


def _employee_leave_balance_total(employee: Employee | None) -> float:
    if not employee:
        return 0.0
    total = (
        db.session.query(func.coalesce(func.sum(LeaveBalance.remaining_credits), 0))
        .filter(
            LeaveBalance.employee_id == employee.id,
            LeaveBalance.year == date.today().year,
        )
        .scalar()
    )
    return float(total or 0)


def _employee_today_status(employee: Employee | None) -> dict:
    if not employee:
        return {
            "status": "Employee profile missing",
            "detail": "Ask HR to link your account so attendance and leave widgets can work.",
        }

    record = (
        AttendanceRecord.query.filter_by(employee_id=employee.id, date=date.today())
        .order_by(AttendanceRecord.id.desc())
        .first()
    )
    if not record:
        return {
            "status": "No time-in yet",
            "detail": "Use the kiosk or attendance page to start your workday.",
        }
    if record.status == "late":
        return {
            "status": "Late arrival",
            "detail": f"Arrival is {record.late_minutes} minute(s) later than schedule.",
        }
    if record.status == "undertime":
        return {
            "status": "Possible undertime",
            "detail": f"Current undertime is {record.undertime_minutes} minute(s).",
        }
    if record.status == "incomplete":
        return {
            "status": "Time-out pending",
            "detail": "Time-in is recorded. Complete your time-out before end of shift.",
        }
    return {"status": "Attendance on track", "detail": "Today's attendance looks complete."}


def _manager_direct_reports(user) -> list[Employee]:
    employee = getattr(user, "employee", None)
    if not employee:
        return []
    return (
        Employee.query.filter_by(manager_id=employee.id)
        .order_by(Employee.last_name.asc(), Employee.first_name.asc())
        .all()
    )


def _build_tasks_for_employee(user, employee) -> list[dict]:
    tasks = []
    if not employee:
        tasks.append(
            {
                "title": "Link your employee profile",
                "detail": "Your account is not yet connected to an employee record.",
                "priority": "high",
                "action_label": "Open profile",
                "endpoint": "auth.profile",
                "modal": False,
                "status": "needs_action",
            }
        )
        return tasks

    pending_leave = LeaveRequest.query.filter_by(employee_id=employee.id, status="pending").count()
    if pending_leave:
        tasks.append(
            {
                "title": f"{pending_leave} leave request(s) waiting",
                "detail": "Track your pending leave approvals and check updates.",
                "priority": "medium",
                "action_label": "View leave requests",
                "endpoint": "leave.index",
                "modal": False,
                "status": "waiting",
            }
        )

    today_record = AttendanceRecord.query.filter_by(employee_id=employee.id, date=date.today()).first()
    if not today_record or today_record.status == "incomplete":
        tasks.append(
            {
                "title": "Complete attendance log",
                "detail": "Time-in/time-out is missing for today.",
                "priority": "high",
                "action_label": "Open attendance",
                "endpoint": "attendance.my_logs",
                "modal": False,
                "status": "needs_action",
            }
        )

    if not tasks:
        tasks.append(
            {
                "title": "No urgent tasks",
                "detail": "Everything for today looks up to date.",
                "priority": "low",
                "action_label": "View dashboard",
                "endpoint": "admin.dashboard",
                "modal": False,
                "status": "done_today",
            }
        )
    return tasks


def _build_tasks_for_manager(user) -> list[dict]:
    reports = _manager_direct_reports(user)
    report_ids = [employee.id for employee in reports]
    tasks = []

    pending_approvals = (
        LeaveRequest.query.filter(LeaveRequest.employee_id.in_(report_ids), LeaveRequest.status == "pending").count()
        if report_ids
        else 0
    )
    if pending_approvals:
        tasks.append(
            {
                "title": f"{pending_approvals} team leave request(s) to review",
                "detail": "Approvals are waiting and may affect shift planning.",
                "priority": "high",
                "action_label": "Review leave",
                "endpoint": "leave.index",
                "modal": False,
                "status": "needs_action",
            }
        )

    missing_attendance = (
        AttendanceRecord.query.filter(
            AttendanceRecord.employee_id.in_(report_ids),
            AttendanceRecord.date == date.today(),
            AttendanceRecord.status == "incomplete",
        ).count()
        if report_ids
        else 0
    )
    if missing_attendance:
        tasks.append(
            {
                "title": f"{missing_attendance} attendance log(s) incomplete",
                "detail": "Some team members may need reminders for correct time logs.",
                "priority": "medium",
                "action_label": "Open attendance",
                "endpoint": "attendance.index",
                "modal": False,
                "status": "waiting",
            }
        )

    if not tasks:
        tasks.append(
            {
                "title": "No urgent approvals",
                "detail": "Team approvals and attendance are currently clear.",
                "priority": "low",
                "action_label": "View dashboard",
                "endpoint": "admin.dashboard",
                "modal": False,
                "status": "done_today",
            }
        )
    return tasks


def _build_tasks_for_admin(user) -> list[dict]:
    tasks = []

    pending_leave = LeaveRequest.query.filter_by(status="pending").count()
    if pending_leave:
        tasks.append(
            {
                "title": f"{pending_leave} leave request(s) in queue",
                "detail": "Unresolved requests can affect payroll and scheduling.",
                "priority": "high",
                "action_label": "Review leave queue",
                "endpoint": "leave.index",
                "modal": False,
                "status": "needs_action",
            }
        )

    inactive_users = User.query.filter_by(is_active=False).count()
    if inactive_users:
        tasks.append(
            {
                "title": f"{inactive_users} inactive account(s)",
                "detail": "Check if these accounts should remain inactive or be reactivated.",
                "priority": "low",
                "action_label": "Open user access",
                "endpoint": "admin.users",
                "modal": False,
                "status": "waiting",
            }
        )

    tasks.append(
        {
            "title": "Post a weekly HR update",
            "detail": "Announcements keep employees aligned and reduce repeated questions.",
            "priority": "medium",
            "action_label": "Publish news",
            "endpoint": "admin.create_news",
            "modal": True,
            "status": "needs_action",
        }
    )
    return tasks


def get_task_inbox(user, status_filter: str = "all") -> list[dict]:
    role_name = _role_name(user)
    employee = getattr(user, "employee", None)
    if role_name == ROLE_EMPLOYEE:
        tasks = _build_tasks_for_employee(user, employee)
    elif role_name == ROLE_MANAGER:
        tasks = _build_tasks_for_manager(user)
    else:
        tasks = _build_tasks_for_admin(user)

    tasks = [task for task in tasks if can_access_endpoint(user, task.get("endpoint"))]
    if status_filter == "all":
        return tasks
    return [task for task in tasks if task.get("status") == status_filter]


def get_leave_sla_summary(sla_hours: int = 24) -> dict:
    pending_requests = (
        LeaveRequest.query.filter(LeaveRequest.status == "pending")
        .order_by(LeaveRequest.created_at.asc())
        .all()
    )
    now = datetime.utcnow()
    cutoff = now - timedelta(hours=sla_hours)
    overdue = [item for item in pending_requests if item.created_at and item.created_at <= cutoff]
    oldest = pending_requests[0] if pending_requests else None
    oldest_age_hours = 0
    if oldest and oldest.created_at:
        oldest_age_hours = int((now - oldest.created_at).total_seconds() // 3600)
    return {
        "sla_hours": sla_hours,
        "pending_count": len(pending_requests),
        "overdue_count": len(overdue),
        "oldest_age_hours": oldest_age_hours,
    }


def get_bulk_action_panel(user) -> list[dict]:
    role_name = _role_name(user)
    if role_name not in {ROLE_SUPER_ADMIN, ROLE_HR_ADMIN}:
        return []
    actions = [
        {
            "title": "Bulk shift assignment",
            "detail": "Assign one schedule to many employees quickly.",
            "action_label": "Open schedules",
            "endpoint": "employees.list_schedule",
            "icon": "bi-calendar3-week",
        },
        {
            "title": "Bulk leave credit update",
            "detail": "Apply leave grants or adjustments in fewer steps.",
            "action_label": "Adjust leave balances",
            "endpoint": "leave.adjust_balance",
            "icon": "bi-plus-slash-minus",
            "modal": True,
        },
        {
            "title": "Bulk account setup",
            "detail": "Create and manage employee user accounts from one area.",
            "action_label": "Open user access",
            "endpoint": "admin.users",
            "icon": "bi-people",
        },
    ]
    return [action for action in actions if can_access_endpoint(user, action.get("endpoint"))]


def get_dashboard_context(user):
    role_name = _role_name(user)
    employee = getattr(user, "employee", None)
    greeting = "Good day"
    if role_name == ROLE_EMPLOYEE:
        attendance_state = _employee_today_status(employee)
        pending_leave_count = (
            LeaveRequest.query.filter_by(employee_id=employee.id, status="pending").count()
            if employee
            else 0
        )
        cards = [
            {"label": "Leave Balance", "value": f"{_employee_leave_balance_total(employee):.1f}"},
            {"label": "Pending Leave", "value": pending_leave_count},
            {"label": "Unread Alerts", "value": unread_notification_count(user)},
        ]
        quick_actions = [
            {"label": "View My Attendance", "endpoint": "attendance.my_logs", "icon": "bi-clock-history", "tone": "primary"},
            {"label": "File Leave", "endpoint": "leave.create_request", "icon": "bi-calendar-plus", "tone": "success", "modal": True},
            {"label": "Open Profile", "endpoint": "auth.profile", "icon": "bi-person-circle", "tone": "light-primary"},
        ]
        quick_actions = [action for action in quick_actions if can_access_endpoint(user, action["endpoint"])]
        return {
            "greeting": greeting,
            "title": f"Welcome back, {user.display_name}",
            "subtitle": "Everything you need for today is one click away.",
            "cards": cards,
            "quick_actions": quick_actions,
            "spotlight": attendance_state,
            "secondary_title": "Latest Company Updates",
            "task_title": "My tasks",
            "tasks": _build_tasks_for_employee(user, employee),
            "task_overview": {
                "needs_action": len(get_task_inbox(user, "needs_action")),
                "waiting": len(get_task_inbox(user, "waiting")),
                "done_today": len(get_task_inbox(user, "done_today")),
            },
            "sla_summary": get_leave_sla_summary(),
            "bulk_actions": [],
        }

    if role_name == ROLE_MANAGER:
        reports = _manager_direct_reports(user)
        report_ids = [item.id for item in reports]
        pending_approvals = (
            LeaveRequest.query.filter(
                LeaveRequest.employee_id.in_(report_ids),
                LeaveRequest.status == "pending",
            ).count()
            if report_ids
            else 0
        )
        present_today = (
            AttendanceRecord.query.filter(
                AttendanceRecord.employee_id.in_(report_ids),
                AttendanceRecord.date == date.today(),
                AttendanceRecord.status.in_(["present", "late", "undertime"]),
            ).count()
            if report_ids
            else 0
        )
        cards = [
            {"label": "Team Members", "value": len(reports)},
            {"label": "Pending Approvals", "value": pending_approvals},
            {"label": "Team Present Today", "value": present_today},
        ]
        quick_actions = [
            {"label": "Review Leave", "endpoint": "leave.index", "icon": "bi-check2-square", "tone": "warning"},
            {"label": "Open Team Chat", "endpoint": "chat.index", "icon": "bi-chat-dots", "tone": "primary"},
            {"label": "View Attendance", "endpoint": "attendance.index", "icon": "bi-people", "tone": "light-primary"},
        ]
        quick_actions = [action for action in quick_actions if can_access_endpoint(user, action["endpoint"])]
        return {
            "greeting": greeting,
            "title": f"Manage your team, {user.display_name}",
            "subtitle": "Keep approvals, attendance, and support conversations moving.",
            "cards": cards,
            "quick_actions": quick_actions,
            "spotlight": {
                "status": f"{pending_approvals} approval(s) waiting",
                "detail": "Review leave and attendance items from your direct reports.",
            },
            "secondary_title": "Team and Company Updates",
            "task_title": "Team actions",
            "tasks": _build_tasks_for_manager(user),
            "task_overview": {
                "needs_action": len(get_task_inbox(user, "needs_action")),
                "waiting": len(get_task_inbox(user, "waiting")),
                "done_today": len(get_task_inbox(user, "done_today")),
            },
            "sla_summary": get_leave_sla_summary(),
            "bulk_actions": [],
        }

    cards = get_dashboard_cards(user)
    quick_actions = []
    if role_name in {ROLE_SUPER_ADMIN, ROLE_HR_ADMIN}:
        quick_actions.extend(
            [
                {"label": "Add Employee", "endpoint": "employees.create_employee", "icon": "bi-person-plus", "tone": "primary", "modal": True},
                {"label": "Create User", "endpoint": "admin.create_user", "icon": "bi-person-badge", "tone": "success", "modal": True},
                {"label": "Publish News", "endpoint": "admin.create_news", "icon": "bi-megaphone", "tone": "warning", "modal": True},
                {"label": "Enterprise Center", "endpoint": "enterprise.index", "icon": "bi-building-gear", "tone": "light-primary"},
            ]
        )
    if role_name not in {ROLE_EMPLOYEE}:
        quick_actions.append({"label": "Review Leave Queue", "endpoint": "leave.index", "icon": "bi-card-checklist", "tone": "light-primary"})
    quick_actions = [action for action in quick_actions if can_access_endpoint(user, action["endpoint"])]

    spotlight = {
        "status": "HRIS command center",
        "detail": "Track approvals, staffing, announcements, and employee activity from one place.",
    }
    return {
        "greeting": greeting,
        "title": "HRIS Dashboard",
        "subtitle": "A live command center for people, approvals, and company updates.",
        "cards": cards,
        "quick_actions": quick_actions,
        "spotlight": spotlight,
        "secondary_title": "Company Updates",
        "task_title": "Priority tasks",
        "tasks": _build_tasks_for_admin(user),
        "task_overview": {
            "needs_action": len(get_task_inbox(user, "needs_action")),
            "waiting": len(get_task_inbox(user, "waiting")),
            "done_today": len(get_task_inbox(user, "done_today")),
        },
        "sla_summary": get_leave_sla_summary(),
        "bulk_actions": get_bulk_action_panel(user),
    }


def list_announcements(limit: int | None = None):
    query = Announcement.query.filter_by(is_active=True).order_by(Announcement.created_at.desc())
    if limit:
        query = query.limit(limit)
    return query.all()


def strip_html(value: str) -> str:
    return re.sub(r"<[^>]+>", "", value or "").strip()


def sanitize_news_html(value: str) -> str:
    cleaned = (value or "").strip()
    cleaned = re.sub(r"(?is)<script.*?>.*?</script>", "", cleaned)
    cleaned = re.sub(r"(?is)<iframe.*?>.*?</iframe>", "", cleaned)
    cleaned = re.sub(r"on\w+\s*=\s*(['\"]).*?\1", "", cleaned)
    cleaned = re.sub(r"javascript\s*:", "", cleaned, flags=re.IGNORECASE)
    return cleaned


def list_user_notifications(user, limit: int | None = None, unread_only: bool = False):
    if not user or not getattr(user, "is_authenticated", False):
        return []
    query = user.notifications
    if unread_only:
        query = query.filter_by(is_read=False)
    query = query.order_by(Notification.created_at.desc())
    if limit:
        query = query.limit(limit)
    return query.all()


def notification_destination(item) -> str:
    if item.type == "leave_request":
        return "leave.index"
    if item.type in {"profile_update_request", "profile_update_status"}:
        return "admin.access_governance" if item.type == "profile_update_request" else "auth.profile"
    if item.type == "employee_request":
        return "enterprise.tickets"
    if item.type == "privacy_request":
        return "enterprise.compliance_records"
    if item.type == "attendance_adjustment":
        return "attendance.index"
    if item.type == "exit_request":
        return "enterprise.tickets"
    if item.type == "announcement":
        return "admin.dashboard"
    if item.type == "chat_report":
        return "chat.index"
    if item.type == "payroll":
        return "reports.index"
    if item.type == "security_alert":
        return "admin.api_requests"
    return "admin.notifications"


def serialize_notification(item) -> dict:
    return {
        "id": item.id,
        "title": item.title,
        "message": item.message,
        "type": item.type,
        "is_read": item.is_read,
        "created_at": item.created_at.strftime("%Y-%m-%d %H:%M") if item.created_at else "",
        "endpoint": notification_destination(item),
    }


def unread_notification_count(user):
    if not user or not getattr(user, "is_authenticated", False):
        return 0
    return user.notifications.filter_by(is_read=False).count()


def mark_notifications_read(user) -> None:
    if not user or not getattr(user, "is_authenticated", False):
        return
    user.notifications.filter_by(is_read=False).update({"is_read": True}, synchronize_session=False)
    db.session.commit()


def list_users():
    return User.query.order_by(User.username.asc()).all()


def list_roles():
    return Role.query.order_by(Role.name.asc()).all()


def list_employee_choices():
    return Employee.query.order_by(Employee.last_name.asc(), Employee.first_name.asc()).all()


def save_user(form, user=None, allow_manage_api_access: bool = True):
    is_new_user = user is None
    if user is None:
        user = User()
        db.session.add(user)

    user.username = form.username.data.strip()
    user.email = form.email.data.strip().lower()
    user.role_id = form.role_id.data
    user.employee_id = form.employee_id.data or None
    if allow_manage_api_access:
        user.can_access_api = bool(form.can_access_api.data)
    user.is_active = form.is_active.data
    user.force_password_change = form.force_password_change.data
    if form.photo.data:
        filename = secure_filename(form.photo.data.filename or "")
        if filename:
            unique_name = f"{secrets.token_hex(8)}_{filename}"
            upload_dir = Path(current_app.static_folder) / "uploads" / "users"
            upload_dir.mkdir(parents=True, exist_ok=True)
            form.photo.data.save(upload_dir / unique_name)
            user.photo_filename = unique_name
    if form.password.data:
        user.set_password(form.password.data)
    role = db.session.get(Role, user.role_id)
    if role and role.name == ROLE_BIOMETRICS_API:
        user.can_access_api = True
        user.ensure_api_token()
        user.employee_id = None
    elif user.can_access_api:
        user.ensure_api_token()
    else:
        user.revoke_api_token()

    db.session.flush()
    if is_new_user:
        user.menu_access_initialized = True
        for menu_key in recommended_menu_keys_for_user(user):
            db.session.add(UserMenuAccess(user_id=user.id, menu_key=menu_key))
        db.session.commit()
        return user
    if not user.menu_access_initialized:
        seed_user_menu_access(user)
    db.session.commit()
    return user


def get_api_endpoint_catalog():
    return [
        {
            "group": "Biometrics",
            "description": "Endpoints for biometric devices, validation, and punch ingestion.",
            "endpoints": [
                {"method": "GET", "path": "/api/biometric/health", "auth": "Public", "purpose": "Health check for biometric connectivity."},
                {"method": "POST", "path": "/api/biometric/punch", "auth": "X-API-Token", "purpose": "Submit biometric punch payloads."},
                {"method": "POST", "path": "/api/biometric/validate-employee", "auth": "X-API-Token", "purpose": "Validate an employee code before device punch."},
                {"method": "POST", "path": "/api/biometric/device-sync", "auth": "X-API-Token", "purpose": "Sync device metadata or cached payloads."},
            ],
        },
        {
            "group": "Security",
            "description": "Endpoints for computer-vision enrollment, event monitoring, and intruder tagging.",
            "endpoints": [
                {"method": "POST", "path": "/api/security/enroll", "auth": "Session", "purpose": "Enroll known people using profile images."},
                {"method": "GET", "path": "/api/security/events", "auth": "Session", "purpose": "Fetch detection event history with optional filters."},
                {"method": "POST", "path": "/api/security/events/<id>/mark-intruder", "auth": "Session", "purpose": "Tag a detection profile as intruder/blacklisted."},
                {"method": "POST", "path": "/api/security/events/<id>/unmark-intruder", "auth": "Session", "purpose": "Remove intruder marking and return profile to allowed."},
            ],
        },
        {
            "group": "Attendance",
            "description": "Endpoints for attendance summaries, records, and kiosk punches.",
            "endpoints": [
                {"method": "GET", "path": "/attendance/api/summary", "auth": "Session", "purpose": "Fetch attendance summary metrics."},
                {"method": "GET", "path": "/attendance/api/records", "auth": "Session", "purpose": "List attendance records."},
                {"method": "POST", "path": "/attendance/api/records", "auth": "Session", "purpose": "Create an attendance record."},
                {"method": "POST", "path": "/attendance/api/punch", "auth": "Public/Internal", "purpose": "Submit badge, NFC, or employee-ID punches."},
            ],
        },
        {
            "group": "Leave",
            "description": "Endpoints for leave balances and leave request access.",
            "endpoints": [
                {"method": "GET", "path": "/leave/api/summary", "auth": "Session", "purpose": "Fetch leave summary counts."},
                {"method": "GET", "path": "/leave/api/requests", "auth": "Session", "purpose": "List leave requests."},
                {"method": "POST", "path": "/leave/api/requests", "auth": "Session", "purpose": "Submit a leave request."},
            ],
        },
        {
            "group": "Payroll",
            "description": "Endpoints for payroll summaries and generated entries.",
            "endpoints": [
                {"method": "GET", "path": "/payroll/api/summary", "auth": "Session", "purpose": "Fetch payroll summary metrics."},
                {"method": "GET", "path": "/payroll/api/entries", "auth": "Session", "purpose": "List payroll entries."},
            ],
        },
        {
            "group": "Reports",
            "description": "Endpoint for the consolidated reporting payload.",
            "endpoints": [
                {"method": "GET", "path": "/reports/api", "auth": "Session", "purpose": "Fetch reporting summary data."},
            ],
        },
    ]


def reset_user_password(user, password: str, force_password_change: bool = True) -> None:
    user.set_password(password)
    user.force_password_change = force_password_change
    db.session.commit()


def toggle_user_active(user):
    user.is_active = not user.is_active
    db.session.commit()
    return user.is_active


def save_announcement(form, author_id: int, announcement=None):
    if announcement is None:
        announcement = Announcement()
        db.session.add(announcement)

    announcement.title = form.title.data.strip()
    announcement.body = sanitize_news_html(form.body.data)
    announcement.posted_by = author_id
    announcement.is_active = bool(form.is_active.data)
    if form.image.data:
        filename = secure_filename(form.image.data.filename or "")
        if filename:
            unique_name = f"{secrets.token_hex(8)}_{filename}"
            upload_dir = Path(current_app.static_folder) / "uploads" / "news"
            upload_dir.mkdir(parents=True, exist_ok=True)
            form.image.data.save(upload_dir / unique_name)
            announcement.image_filename = unique_name
    db.session.flush()

    if announcement.is_active:
        plain_message = strip_html(announcement.body)
        users = User.query.filter_by(is_active=True).all()
        for user in users:
            db.session.add(
                Notification(
                    user_id=user.id,
                    title=announcement.title,
                    message=plain_message,
                    type="announcement",
                    is_read=False,
                )
            )

    db.session.commit()
    return announcement
