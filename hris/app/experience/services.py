from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
import json
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

from flask import current_app
from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError, ProgrammingError

from ..admin.services import list_announcements, list_user_notifications, unread_notification_count
from ..attendance.services import process_employee_punch
from ..extensions import db
from ..models import (
    ApprovalDecision,
    ApprovalInstance,
    AttendanceAdjustment,
    AttendanceGeoLog,
    AttendanceRecord,
    BranchHolidayRule,
    CompensationChange,
    ConsentLog,
    DocumentRecord,
    EmployeeChecklistItem,
    EmployeeProfileUpdateRequest,
    EmployeeShift,
    EmployeeTraining,
    ExitInterview,
    GeoAttendanceRule,
    HelpArticle,
    Holiday,
    HrTicket,
    LeavePolicyVersion,
    LeaveRequest,
    MenuAccessRequest,
    Notification,
    PayrollEntry,
    PerformanceCalibration,
    PrivacyRequest,
    PulseSurvey,
    SuccessionCandidate,
    SurveyResponse,
    TimeBankEntry,
    TrainingCourse,
    User,
)
from ..utils.constants import ROLE_HR_ADMIN, ROLE_SUPER_ADMIN


def _table_exists(table_name: str) -> bool:
    try:
        return inspect(db.engine).has_table(table_name)
    except Exception:
        return False


def _safe_list(table_name: str, query_fn):
    if not _table_exists(table_name):
        return []
    try:
        return query_fn()
    except (OperationalError, ProgrammingError):
        db.session.rollback()
        return []


def _safe_first(table_name: str, query_fn):
    rows = _safe_list(table_name, query_fn)
    return rows[0] if rows else None


def current_employee(user):
    return getattr(user, "employee", None)


def _employee_branch(employee) -> str:
    if not employee or not employee.department:
        return "Head Office"
    return employee.department.branch or "Head Office"


def _active_shift_assignment(employee):
    if not employee:
        return None
    return (
        EmployeeShift.query.filter_by(employee_id=employee.id)
        .filter((EmployeeShift.end_date.is_(None)) | (EmployeeShift.end_date >= date.today()))
        .order_by(EmployeeShift.effective_date.desc())
        .first()
    )


def _today_record(employee):
    if not employee:
        return None
    return (
        AttendanceRecord.query.filter_by(employee_id=employee.id, date=date.today())
        .order_by(AttendanceRecord.id.desc())
        .first()
    )


def _attendance_explanation(record: AttendanceRecord | None, shift_assignment=None) -> str:
    if not record:
        return "No attendance record yet today."
    if record.late_minutes:
        grace = shift_assignment.shift.grace_period_minutes if shift_assignment and shift_assignment.shift else 0
        return f"You were marked late because your time in passed the shift start plus {grace} minute(s) grace."
    if record.undertime_minutes:
        return "Undertime was detected because your time out is earlier than the scheduled shift end."
    if record.status == "incomplete":
        return "Your record is incomplete because only part of the required punches were captured."
    return "Attendance status is aligned with the punches recorded for today."


def _employee_documents(employee):
    if not employee:
        return []
    return _safe_list(
        DocumentRecord.__tablename__,
        lambda: DocumentRecord.query.filter_by(employee_id=employee.id)
        .order_by(DocumentRecord.expiry_date.asc().nullslast(), DocumentRecord.created_at.desc())
        .all(),
    )


def _employee_payslips(employee):
    if not employee:
        return []
    return (
        PayrollEntry.query.filter_by(employee_id=employee.id)
        .order_by(PayrollEntry.created_at.desc())
        .limit(10)
        .all()
    )


def _employee_tickets(employee):
    if not employee:
        return []
    return _safe_list(
        HrTicket.__tablename__,
        lambda: HrTicket.query.filter_by(employee_id=employee.id).order_by(HrTicket.created_at.desc()).all(),
    )


def _employee_privacy_requests(employee):
    if not employee:
        return []
    return _safe_list(
        PrivacyRequest.__tablename__,
        lambda: PrivacyRequest.query.filter_by(employee_id=employee.id).order_by(PrivacyRequest.created_at.desc()).all(),
    )


def _employee_profile_requests(user):
    return _safe_list(
        EmployeeProfileUpdateRequest.__tablename__,
        lambda: EmployeeProfileUpdateRequest.query.filter_by(user_id=user.id)
        .order_by(EmployeeProfileUpdateRequest.created_at.desc())
        .all(),
    )


def _employee_leave_requests(employee):
    if not employee:
        return []
    return (
        LeaveRequest.query.filter_by(employee_id=employee.id)
        .order_by(LeaveRequest.created_at.desc())
        .all()
    )


def _employee_document_requests(employee):
    return [ticket for ticket in _employee_tickets(employee) if ticket.category == "document_request"]


def _leave_approval_timeline(request_obj: LeaveRequest) -> list[dict]:
    timeline = [
        {
            "label": "Submitted",
            "detail": request_obj.created_at.strftime("%Y-%m-%d %H:%M") if request_obj.created_at else "Pending",
            "tone": "info",
        }
    ]
    if _table_exists(ApprovalInstance.__tablename__):
        instance = ApprovalInstance.query.filter_by(module="leave", record_id=request_obj.id).first()
        if instance:
            decisions = (
                ApprovalDecision.query.filter_by(instance_id=instance.id)
                .order_by(ApprovalDecision.step_order.asc(), ApprovalDecision.created_at.asc())
                .all()
            )
            for decision in decisions:
                timeline.append(
                    {
                        "label": f"Step {decision.step_order}: {decision.decision.title()}",
                        "detail": decision.approver_role,
                        "tone": "success" if decision.decision == "approved" else "danger",
                    }
                )
            if instance.status == "pending":
                timeline.append(
                    {
                        "label": f"Waiting for step {instance.current_step}",
                        "detail": "Approval is still in progress.",
                        "tone": "warning",
                    }
                )
    elif request_obj.status.startswith("pending"):
        timeline.append({"label": "Waiting for approval", "detail": "Your request is under review.", "tone": "warning"})
    elif request_obj.status == "approved":
        timeline.append({"label": "Approved", "detail": "Leave has been approved.", "tone": "success"})
    elif request_obj.status in {"disapproved", "cancelled"}:
        timeline.append({"label": request_obj.status.title(), "detail": "This request is closed.", "tone": "danger"})
    return timeline


def _team_leave_calendar(employee):
    if not employee or not employee.department_id:
        return []
    return (
        LeaveRequest.query.join(LeaveRequest.employee)
        .filter_by(department_id=employee.department_id)
        .filter(LeaveRequest.status == "approved")
        .filter(LeaveRequest.end_date >= date.today())
        .order_by(LeaveRequest.start_date.asc())
        .limit(8)
        .all()
    )


def _holiday_calendar(employee, days_ahead: int = 21):
    branch_name = _employee_branch(employee)
    end_day = date.today() + timedelta(days=days_ahead)
    holidays = Holiday.query.filter(Holiday.date >= date.today(), Holiday.date <= end_day).order_by(Holiday.date.asc()).all()
    branch_rules = {
        item.holiday_id: item
        for item in _safe_list(
            BranchHolidayRule.__tablename__,
            lambda: BranchHolidayRule.query.filter_by(branch_name=branch_name).all(),
        )
    }
    rows = []
    for holiday in holidays:
        branch_rule = branch_rules.get(holiday.id)
        rows.append(
            {
                "holiday": holiday,
                "branch_rule": branch_rule,
                "working_day": bool(branch_rule.is_working_day) if branch_rule else False,
            }
        )
    return rows


def _geo_rule_for_employee(employee):
    branch_name = _employee_branch(employee)
    return _safe_first(
        GeoAttendanceRule.__tablename__,
        lambda: GeoAttendanceRule.query.filter_by(branch_name=branch_name).limit(1).all(),
    )


def _geo_logs_for_employee(employee):
    if not employee:
        return []
    return _safe_list(
        AttendanceGeoLog.__tablename__,
        lambda: AttendanceGeoLog.query.filter_by(employee_id=employee.id)
        .order_by(AttendanceGeoLog.created_at.desc())
        .limit(5)
        .all(),
    )


def _document_status_label(item: DocumentRecord) -> str:
    if item.expiry_date and item.expiry_date <= date.today():
        return "Expired"
    if item.expiry_date and item.expiry_date <= (date.today() + timedelta(days=30)):
        return "Expiring soon"
    return (item.status or "active").replace("_", " ").title()


def _document_downloadable(item: DocumentRecord) -> bool:
    if not item.file_path:
        return False
    file_path = Path(item.file_path)
    if file_path.is_absolute():
        return file_path.exists()
    static_path = Path(current_app.static_folder) / item.file_path
    upload_path = Path(current_app.config["UPLOAD_FOLDER"]) / item.file_path
    return static_path.exists() or upload_path.exists()


def _document_display_name(item: DocumentRecord) -> str:
    if item.file_path:
        return Path(item.file_path).name
    return item.document_type.replace("_", " ").title()


def _default_empty_help_articles():
    return [
        {
            "module": "general",
            "title": "How to use My Workspace",
            "content": "Use the workspace to check attendance, leave, documents, and actions that still need your attention.",
        },
        {
            "module": "attendance",
            "title": "How mobile punch works",
            "content": "Use your current location and device name, then review the preview before you submit your punch.",
        },
    ]


def _employee_checklist(employee, checklist_type: str):
    if not employee:
        return []
    return _safe_list(
        EmployeeChecklistItem.__tablename__,
        lambda: EmployeeChecklistItem.query.filter_by(employee_id=employee.id, checklist_type=checklist_type)
        .order_by(EmployeeChecklistItem.due_date.asc().nullslast(), EmployeeChecklistItem.created_at.asc())
        .all(),
    )


def _employee_timebank_entries(employee):
    if not employee:
        return []
    return _safe_list(
        TimeBankEntry.__tablename__,
        lambda: TimeBankEntry.query.filter_by(employee_id=employee.id).order_by(TimeBankEntry.created_at.desc()).limit(8).all(),
    )


def _leave_policy_versions():
    return _safe_list(
        LeavePolicyVersion.__tablename__,
        lambda: LeavePolicyVersion.query.filter_by(is_active=True)
        .order_by(LeavePolicyVersion.effective_from.desc())
        .limit(8)
        .all(),
    )


def _employee_trainings(employee):
    if not employee:
        return []
    trainings = _safe_list(
        EmployeeTraining.__tablename__,
        lambda: EmployeeTraining.query.filter_by(employee_id=employee.id).order_by(EmployeeTraining.created_at.desc()).all(),
    )
    courses = {
        item.id: item
        for item in _safe_list(
            TrainingCourse.__tablename__,
            lambda: TrainingCourse.query.filter_by(is_active=True).all(),
        )
    }
    return [{"training": training, "course": courses.get(training.course_id)} for training in trainings]


def _active_surveys(employee):
    if not employee:
        return []
    surveys = _safe_list(
        PulseSurvey.__tablename__,
        lambda: PulseSurvey.query.filter(PulseSurvey.status.in_(["open", "launched"]))
        .order_by(PulseSurvey.created_at.desc())
        .all(),
    )
    responded_ids = {
        item.survey_id
        for item in _safe_list(
            SurveyResponse.__tablename__,
            lambda: SurveyResponse.query.filter_by(employee_id=employee.id).all(),
        )
    }
    return [
        {
            "survey": survey,
            "questions": _parse_json_list(survey.question_set_json),
            "answered": survey.id in responded_ids,
        }
        for survey in surveys
    ]


def workspace_context(user) -> dict:
    employee = current_employee(user)
    today_record = _today_record(employee)
    active_shift = _active_shift_assignment(employee)
    tickets = _employee_tickets(employee)
    documents = _employee_documents(employee)
    payslips = _employee_payslips(employee)
    profile_requests = _employee_profile_requests(user)
    onboarding_items = _employee_checklist(employee, "onboarding")
    exit_items = _employee_checklist(employee, "offboarding")
    learning_items = _employee_trainings(employee)
    open_surveys = _active_surveys(employee)
    notifications = list_user_notifications(user, limit=6)

    unresolved = []
    if today_record is None or today_record.status == "incomplete":
        unresolved.append({"label": "Attendance needs attention", "endpoint": "experience.schedule"})
    if any(item.status == "pending" for item in profile_requests):
        unresolved.append({"label": "Profile update waiting for review", "endpoint": "auth.profile"})
    if any(item.status in {"open", "in_progress"} for item in tickets):
        unresolved.append({"label": "HR request still in progress", "endpoint": "experience.requests_home"})
    if onboarding_items and any(item.status != "completed" for item in onboarding_items):
        unresolved.append({"label": "Onboarding checklist has pending steps", "endpoint": "experience.onboarding"})

    cards = [
        {
            "label": "Today's attendance",
            "value": (today_record.status.replace("_", " ").title() if today_record else "No log yet"),
            "detail": _attendance_explanation(today_record, active_shift),
        },
        {
            "label": "Leave requests",
            "value": len(_employee_leave_requests(employee)),
            "detail": "Quick view of your latest leave activity.",
        },
        {
            "label": "Open requests",
            "value": len([item for item in tickets if item.status in {'open', 'in_progress'}]) + len([item for item in profile_requests if item.status == 'pending']),
            "detail": "Support, privacy, and profile-related requests still in progress.",
        },
        {
            "label": "Documents & payslips",
            "value": len(documents) + len(payslips),
            "detail": "Files you can review or download from your locker.",
        },
    ]

    quick_actions = [
        {"label": "Punch attendance", "endpoint": "experience.schedule", "icon": "bi bi-phone"},
        {"label": "File leave", "endpoint": "experience.requests_home", "icon": "bi bi-calendar-plus"},
        {"label": "Open requests", "endpoint": "experience.requests_home", "icon": "bi bi-life-preserver"},
        {"label": "View documents", "endpoint": "experience.documents", "icon": "bi bi-folder2-open"},
    ]

    return {
        "employee": employee,
        "today_record": today_record,
        "active_shift": active_shift,
        "cards": cards,
        "notifications": notifications,
        "announcements": list_announcements(limit=4),
        "quick_actions": quick_actions,
        "unresolved": unresolved,
        "profile_requests": profile_requests[:3],
        "leave_requests": _employee_leave_requests(employee)[:4],
        "documents": documents[:4],
        "payslips": payslips[:3],
        "learning_items": learning_items[:3],
        "onboarding_items": onboarding_items[:3],
        "exit_items": exit_items[:3],
        "open_surveys": open_surveys[:2],
        "unread_notifications": unread_notification_count(user),
    }


def schedule_context(user) -> dict:
    employee = current_employee(user)
    active_shift = _active_shift_assignment(employee)
    recent_records = (
        AttendanceRecord.query.filter_by(employee_id=employee.id).order_by(AttendanceRecord.date.desc()).limit(7).all()
        if employee
        else []
    )
    return {
        "employee": employee,
        "active_shift": active_shift,
        "today_record": _today_record(employee),
        "attendance_explanation": _attendance_explanation(_today_record(employee), active_shift),
        "holidays": _holiday_calendar(employee),
        "team_leave_calendar": _team_leave_calendar(employee),
        "geo_rule": _geo_rule_for_employee(employee),
        "geo_logs": _geo_logs_for_employee(employee),
        "recent_records": recent_records,
        "timebank_entries": _employee_timebank_entries(employee),
    }


def requests_context(user) -> dict:
    employee = current_employee(user)
    leave_requests = _employee_leave_requests(employee)
    return {
        "employee": employee,
        "leave_requests": leave_requests,
        "leave_timelines": {item.id: _leave_approval_timeline(item) for item in leave_requests[:5]},
        "tickets": _employee_tickets(employee),
        "privacy_requests": _employee_privacy_requests(employee),
        "profile_requests": _employee_profile_requests(user),
        "access_requests": _safe_list(
            MenuAccessRequest.__tablename__,
            lambda: MenuAccessRequest.query.filter_by(user_id=user.id).order_by(MenuAccessRequest.created_at.desc()).all(),
        ),
        "document_requests": _employee_document_requests(employee),
        "team_leave_calendar": _team_leave_calendar(employee),
        "leave_policies": _leave_policy_versions(),
    }


def documents_context(user) -> dict:
    employee = current_employee(user)
    documents = _employee_documents(employee)
    acknowledgement_tokens = (
        {item.consent_type for item in _safe_list(ConsentLog.__tablename__, lambda: ConsentLog.query.filter_by(employee_id=employee.id).all())}
        if employee
        else set()
    )
    return {
        "employee": employee,
        "documents": [
            {
                "record": item,
                "display_name": _document_display_name(item),
                "status_label": _document_status_label(item),
                "downloadable": _document_downloadable(item),
                "acknowledged": f"document:{item.id}" in acknowledgement_tokens,
            }
            for item in documents
        ],
        "payslips": _employee_payslips(employee),
        "document_requests": _employee_document_requests(employee),
    }


def help_center_context(user) -> dict:
    employee = current_employee(user)
    articles = _safe_list(
        HelpArticle.__tablename__,
        lambda: HelpArticle.query.filter_by(is_active=True).order_by(HelpArticle.module.asc(), HelpArticle.title.asc()).all(),
    )
    return {
        "employee": employee,
        "articles": articles or _default_empty_help_articles(),
        "open_tickets": [item for item in _employee_tickets(employee) if item.status in {"open", "in_progress"}],
    }


def learning_context(user) -> dict:
    employee = current_employee(user)
    position_name = employee.position.name if employee and employee.position else None
    all_courses = _safe_list(
        TrainingCourse.__tablename__,
        lambda: TrainingCourse.query.filter_by(is_active=True).order_by(TrainingCourse.title.asc()).all(),
    )
    suggested_courses = [item for item in all_courses if not item.required_for_role or item.required_for_role == position_name]
    return {
        "employee": employee,
        "trainings": _employee_trainings(employee),
        "suggested_courses": suggested_courses[:8],
        "calibrations": _safe_list(
            PerformanceCalibration.__tablename__,
            lambda: PerformanceCalibration.query.filter_by(employee_id=employee.id)
            .order_by(PerformanceCalibration.created_at.desc())
            .all(),
        ) if employee else [],
        "succession_candidates": _safe_list(
            SuccessionCandidate.__tablename__,
            lambda: SuccessionCandidate.query.filter_by(employee_id=employee.id)
            .order_by(SuccessionCandidate.created_at.desc())
            .all(),
        ) if employee else [],
        "compensation_changes": _safe_list(
            CompensationChange.__tablename__,
            lambda: CompensationChange.query.filter_by(employee_id=employee.id)
            .order_by(CompensationChange.effective_date.desc())
            .all(),
        ) if employee else [],
    }


def surveys_context(user) -> dict:
    employee = current_employee(user)
    return {
        "employee": employee,
        "surveys": _active_surveys(employee),
        "announcements": list_announcements(limit=6),
        "responses": _safe_list(
            SurveyResponse.__tablename__,
            lambda: SurveyResponse.query.filter_by(employee_id=employee.id)
            .order_by(SurveyResponse.created_at.desc())
            .all(),
        ) if employee else [],
    }


def onboarding_context(user) -> dict:
    employee = current_employee(user)
    items = _employee_checklist(employee, "onboarding")
    completed = len([item for item in items if item.status == "completed"])
    progress = int((completed / len(items)) * 100) if items else 0
    return {
        "employee": employee,
        "items": items,
        "progress": progress,
    }


def exit_context(user) -> dict:
    employee = current_employee(user)
    exit_record = _safe_first(
        ExitInterview.__tablename__,
        lambda: ExitInterview.query.filter_by(employee_id=employee.id).order_by(ExitInterview.created_at.desc()).limit(1).all(),
    ) if employee else None
    return {
        "employee": employee,
        "exit_record": exit_record,
        "offboarding_items": _employee_checklist(employee, "offboarding"),
    }


def timeline_context(user) -> dict:
    employee = current_employee(user)
    if not employee:
        return {"employee": None, "entries": []}

    entries = []
    for record in AttendanceRecord.query.filter_by(employee_id=employee.id).order_by(AttendanceRecord.date.desc()).limit(8).all():
        entries.append(
            {
                "date": record.date,
                "title": f"Attendance: {record.status.replace('_', ' ').title()}",
                "detail": _attendance_explanation(record, _active_shift_assignment(employee)),
                "kind": "attendance",
            }
        )
    for request_obj in _employee_leave_requests(employee)[:8]:
        entries.append(
            {
                "date": request_obj.start_date,
                "title": f"Leave request: {request_obj.leave_type.name if request_obj.leave_type else 'Leave'}",
                "detail": f"{request_obj.status.replace('_', ' ').title()} from {request_obj.start_date} to {request_obj.end_date}.",
                "kind": "leave",
            }
        )
    for request_obj in _employee_profile_requests(user)[:6]:
        entries.append(
            {
                "date": request_obj.created_at.date() if request_obj.created_at else date.today(),
                "title": "Profile update request",
                "detail": f"{request_obj.status.replace('_', ' ').title()} profile change request.",
                "kind": "profile",
            }
        )
    for item in _safe_list(
        CompensationChange.__tablename__,
        lambda: CompensationChange.query.filter_by(employee_id=employee.id)
        .order_by(CompensationChange.effective_date.desc())
        .limit(5)
        .all(),
    ):
        entries.append(
            {
                "date": item.effective_date,
                "title": "Compensation update",
                "detail": f"Status: {item.status.replace('_', ' ').title()}.",
                "kind": "compensation",
            }
        )
    for item in _employee_tickets(employee)[:6]:
        entries.append(
            {
                "date": item.created_at.date() if item.created_at else date.today(),
                "title": f"HR request: {item.subject}",
                "detail": f"{item.category.replace('_', ' ').title()} · {item.status.replace('_', ' ').title()}",
                "kind": "support",
            }
        )
    entries.sort(key=lambda entry: entry["date"], reverse=True)
    return {"employee": employee, "entries": entries[:20]}


def _parse_json_list(raw_value: str | None):
    if not raw_value:
        return []
    try:
        payload = json.loads(raw_value)
    except (ValueError, TypeError):
        return []
    return payload if isinstance(payload, list) else []


def notify_employee_experience_admins(title: str, message: str, notification_type: str) -> None:
    recipients = (
        User.query.join(User.role)
        .filter(User.is_active.is_(True))
        .all()
    )
    recipients = [item for item in recipients if item.role and item.role.name in {ROLE_SUPER_ADMIN, ROLE_HR_ADMIN}]
    for user in recipients:
        db.session.add(
            Notification(
                user_id=user.id,
                title=title,
                message=message,
                type=notification_type,
                is_read=False,
            )
        )
    db.session.commit()


def create_support_ticket(user, form, anonymous: bool = False):
    employee = current_employee(user)
    if not employee:
        raise ValueError("Your account is not linked to an employee profile.")
    if not _table_exists(HrTicket.__tablename__):
        raise ValueError("Support center tables are not available yet.")
    subject = form.subject.data.strip()
    if anonymous:
        subject = "Anonymous suggestion"
    ticket = HrTicket(
        employee_id=employee.id,
        category=form.category.data,
        subject=subject,
        description=form.description.data.strip(),
        priority=form.priority.data,
        status="open",
    )
    db.session.add(ticket)
    db.session.commit()
    notify_employee_experience_admins(
        "New employee request",
        f"{employee.full_name} submitted a {form.category.data.replace('_', ' ')} request.",
        "employee_request",
    )
    return ticket


def submit_privacy_request_for_employee(user, form):
    employee = current_employee(user)
    if not employee:
        raise ValueError("Your account is not linked to an employee profile.")
    if not _table_exists(PrivacyRequest.__tablename__):
        raise ValueError("Privacy request tables are not available yet.")
    item = PrivacyRequest(
        employee_id=employee.id,
        request_type=form.request_type.data,
        details=form.details.data.strip(),
        status="open",
    )
    db.session.add(item)
    db.session.commit()
    notify_employee_experience_admins(
        "New privacy request",
        f"{employee.full_name} submitted a {form.request_type.data.replace('_', ' ')} request.",
        "privacy_request",
    )
    return item


def submit_document_request(user, form):
    class _DocumentRequestProxy:
        category = type("Category", (), {"data": "document_request"})
        subject = type("Subject", (), {"data": f"Document request: {form.document_type.data.replace('_', ' ').title()}"})
        description = type("Description", (), {"data": (form.notes.data or "").strip() or "Employee requested a copy of a document."})
        priority = type("Priority", (), {"data": "normal"})

    return create_support_ticket(user, _DocumentRequestProxy)


def acknowledge_document(user, document_id: int):
    employee = current_employee(user)
    if not employee:
        raise ValueError("Your account is not linked to an employee profile.")
    if not _table_exists(ConsentLog.__tablename__):
        raise ValueError("Document acknowledgement is not available yet.")
    existing = ConsentLog.query.filter_by(employee_id=employee.id, consent_type=f"document:{document_id}").first()
    if existing:
        return existing
    item = ConsentLog(
        employee_id=employee.id,
        consent_type=f"document:{document_id}",
        consented_at=datetime.utcnow(),
        notes="Employee acknowledged a document in the locker.",
    )
    db.session.add(item)
    db.session.commit()
    return item


def submit_mobile_punch(user, form):
    employee = current_employee(user)
    if not employee:
        raise ValueError("Your account is not linked to an employee profile.")

    latitude = float(form.latitude.data) if form.latitude.data is not None else None
    longitude = float(form.longitude.data) if form.longitude.data is not None else None
    geo_rule = _geo_rule_for_employee(employee)
    within_geofence = True
    if geo_rule and latitude is not None and longitude is not None:
        within_geofence = _distance_meters(latitude, longitude, geo_rule.latitude, geo_rule.longitude) <= geo_rule.radius_meters
        if not within_geofence:
            raise ValueError("You are outside the allowed attendance area for your branch.")

    record, message = process_employee_punch(employee.employee_code, "mobile", form.action.data)
    if record is None:
        raise ValueError(message)

    if _table_exists(AttendanceGeoLog.__tablename__):
        db.session.add(
            AttendanceGeoLog(
                attendance_record_id=record.id,
                employee_id=employee.id,
                latitude=latitude,
                longitude=longitude,
                within_geofence=within_geofence,
                spoof_risk_score=0.0 if form.anti_spoof_confirmed.data else 0.6,
            )
        )
        db.session.commit()

    return record, message


def submit_attendance_correction(user, form):
    employee = current_employee(user)
    if not employee:
        raise ValueError("Your account is not linked to an employee profile.")
    record = db.session.get(AttendanceRecord, form.attendance_record_id.data)
    if not record or record.employee_id != employee.id:
        raise ValueError("The selected attendance record is not available.")

    def _parse_dt(raw_value: str | None):
        if not raw_value:
            return None
        return datetime.fromisoformat(raw_value)

    reason = f"[{form.reason_template.data}] {form.details.data.strip()}"
    adjustment = AttendanceAdjustment(
        employee_id=employee.id,
        attendance_record_id=record.id,
        requested_by=user.id,
        reason=reason,
        old_time_in=record.time_in,
        new_time_in=_parse_dt(form.new_time_in.data),
        old_time_out=record.time_out,
        new_time_out=_parse_dt(form.new_time_out.data),
        status="pending",
    )
    db.session.add(adjustment)
    db.session.commit()
    notify_employee_experience_admins(
        "Attendance correction request",
        f"{employee.full_name} submitted an attendance correction for {record.date}.",
        "attendance_adjustment",
    )
    return adjustment


def cancel_leave_request_for_employee(user, request_id: int):
    employee = current_employee(user)
    request_obj = db.session.get(LeaveRequest, request_id)
    if not employee or not request_obj or request_obj.employee_id != employee.id:
        raise ValueError("Leave request not found.")
    if request_obj.status not in {"pending", "pending_step_1", "pending_step_2"}:
        raise ValueError("Only pending leave requests can be cancelled.")
    request_obj.status = "cancelled"
    db.session.commit()
    notify_employee_experience_admins(
        "Leave request cancelled",
        f"{employee.full_name} cancelled a leave request from {request_obj.start_date} to {request_obj.end_date}.",
        "leave_request",
    )
    return request_obj


def submit_leave_modification_request(user, request_id: int, details: str):
    employee = current_employee(user)
    request_obj = db.session.get(LeaveRequest, request_id)
    if not employee or not request_obj or request_obj.employee_id != employee.id:
        raise ValueError("Leave request not found.")

    class _LeaveModificationProxy:
        category = type("Category", (), {"data": "leave_modification"})
        subject = type("Subject", (), {"data": f"Leave modification request #{request_obj.id}"})
        description = type(
            "Description",
            (),
            {"data": f"Requested modification for leave {request_obj.start_date} to {request_obj.end_date}.\n\n{details.strip()}"},
        )
        priority = type("Priority", (), {"data": "normal"})

    return create_support_ticket(user, _LeaveModificationProxy)


def submit_survey_response(user, survey_id: int, form):
    employee = current_employee(user)
    if not employee:
        raise ValueError("Your account is not linked to an employee profile.")
    if not _table_exists(SurveyResponse.__tablename__):
        raise ValueError("Survey tables are not available yet.")

    existing = SurveyResponse.query.filter_by(survey_id=survey_id, employee_id=employee.id).first()
    if existing:
        existing.sentiment_score = float(form.sentiment_score.data)
        existing.answers_json = json.dumps({"feedback": form.feedback.data.strip()})
        response = existing
    else:
        response = SurveyResponse(
            survey_id=survey_id,
            employee_id=employee.id,
            sentiment_score=float(form.sentiment_score.data),
            answers_json=json.dumps({"feedback": form.feedback.data.strip()}),
        )
        db.session.add(response)
    db.session.commit()
    return response


def submit_suggestion(user, form):
    employee = current_employee(user)
    if not employee:
        raise ValueError("Your account is not linked to an employee profile.")

    class _SuggestionProxy:
        category = type("Category", (), {"data": "suggestion"})
        subject = type("Subject", (), {"data": "Anonymous suggestion" if form.is_anonymous.data else f"Suggestion from {employee.full_name}"})
        description = type("Description", (), {"data": form.message.data.strip()})
        priority = type("Priority", (), {"data": "normal"})

    return create_support_ticket(user, _SuggestionProxy, anonymous=form.is_anonymous.data)


def submit_exit_request(user, form):
    employee = current_employee(user)
    if not employee:
        raise ValueError("Your account is not linked to an employee profile.")
    if not _table_exists(ExitInterview.__tablename__):
        raise ValueError("Exit workflow tables are not available yet.")
    exit_record = ExitInterview.query.filter_by(employee_id=employee.id).order_by(ExitInterview.created_at.desc()).first()
    if exit_record is None:
        exit_record = ExitInterview(employee_id=employee.id)
        db.session.add(exit_record)
    exit_record.resignation_date = form.resignation_date.data
    exit_record.last_day = form.last_day.data
    exit_record.reason = form.reason.data.strip()
    exit_record.interview_notes = form.interview_notes.data.strip() if form.interview_notes.data else None
    exit_record.risk_tag = "submitted"
    db.session.commit()
    notify_employee_experience_admins(
        "Exit request submitted",
        f"{employee.full_name} submitted an exit request with last day {form.last_day.data}.",
        "exit_request",
    )
    return exit_record


def document_download_path(record: DocumentRecord):
    if not record.file_path:
        return None
    file_path = Path(record.file_path)
    if file_path.is_absolute() and file_path.exists():
        return file_path
    static_path = Path(current_app.static_folder) / record.file_path
    if static_path.exists():
        return static_path
    upload_path = Path(current_app.config["UPLOAD_FOLDER"]) / record.file_path
    if upload_path.exists():
        return upload_path
    return None


def _distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371000
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    start_lat = radians(lat1)
    end_lat = radians(lat2)
    hav = sin(d_lat / 2) ** 2 + cos(start_lat) * cos(end_lat) * sin(d_lon / 2) ** 2
    return 2 * radius * asin(sqrt(hav))
