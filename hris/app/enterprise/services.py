from __future__ import annotations

from datetime import datetime, timedelta
import json

from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError, ProgrammingError

from ..extensions import db
from ..models import (
    AiAgentAction,
    AiAgentJob,
    ApiIntegration,
    ApprovalDecision,
    ApprovalInstance,
    AttendanceAdjustment,
    AttendanceAnomaly,
    AttendanceRecord,
    BackupJobLog,
    ConsentLog,
    DataHealthCheck,
    DocumentRecord,
    Employee,
    ExitInterview,
    HelpArticle,
    HrTicket,
    LeaveRequest,
    LocalizationSetting,
    NotificationPreference,
    Notification,
    PayrollCutoff,
    PayrollEntry,
    PayslipDispute,
    PermissionOverride,
    PrivacyRequest,
    PulseSurvey,
    SessionDevice,
    SuccessionCandidate,
    TrainingCourse,
    TaskInboxItem,
    User,
    WebhookSubscription,
    DeviceHealthLog,
)


def _table_exists(table_name: str) -> bool:
    try:
        return inspect(db.engine).has_table(table_name)
    except Exception:
        return False


def _safe_count(table_name: str, query_fn) -> int:
    if not _table_exists(table_name):
        return 0
    try:
        return int(query_fn())
    except (ProgrammingError, OperationalError):
        db.session.rollback()
        return 0


def _safe_list(table_name: str, query_fn) -> list:
    if not _table_exists(table_name):
        return []
    try:
        return query_fn()
    except (ProgrammingError, OperationalError):
        db.session.rollback()
        return []


def enterprise_status_cards() -> list[dict]:
    return [
        {
            "label": "Open HR Tickets",
            "value": _safe_count(
                HrTicket.__tablename__,
                lambda: HrTicket.query.filter(HrTicket.status.in_(["open", "in_progress"])).count(),
            ),
        },
        {
            "label": "Expiring Documents",
            "value": _safe_count(
                DocumentRecord.__tablename__,
                lambda: DocumentRecord.query.filter(DocumentRecord.status == "active").count(),
            ),
        },
        {
            "label": "Active Integrations",
            "value": _safe_count(
                ApiIntegration.__tablename__,
                lambda: ApiIntegration.query.filter_by(status="active").count(),
            ),
        },
        {
            "label": "Open Data Checks",
            "value": _safe_count(
                DataHealthCheck.__tablename__,
                lambda: DataHealthCheck.query.filter(DataHealthCheck.status != "resolved").count(),
            ),
        },
    ]


def enterprise_feature_groups() -> list[dict]:
    return [
        {
            "title": "People Operations",
            "items": [
                "Org chart hierarchy",
                "Onboarding and offboarding checklists",
                "Compensation history workflow",
                "Employee profile timeline",
                "Internal HR ticketing",
            ],
        },
        {
            "title": "Workforce Intelligence",
            "items": [
                "Succession planning and talent pool tags",
                "Performance calibration and 9-box",
                "Training and certification tracking",
                "Pulse surveys and sentiment insights",
                "Exit interview analytics",
            ],
        },
        {
            "title": "Governance and Platform",
            "items": [
                "Leave policy versioning",
                "Compliance and consent logging",
                "Backup and recovery audit logs",
                "Fine-grained permission overrides",
                "Localization and timezone settings",
            ],
        },
    ]


def compliance_summary() -> dict:
    return {
        "consent_logs": _safe_count(ConsentLog.__tablename__, lambda: ConsentLog.query.count()),
        "backup_runs": _safe_count(BackupJobLog.__tablename__, lambda: BackupJobLog.query.count()),
        "permission_overrides": _safe_count(
            PermissionOverride.__tablename__, lambda: PermissionOverride.query.count()
        ),
        "active_locales": _safe_count(
            LocalizationSetting.__tablename__, lambda: LocalizationSetting.query.count()
        ),
        "connected_sessions": _safe_count(
            SessionDevice.__tablename__, lambda: SessionDevice.query.filter_by(is_active=True).count()
        ),
    }


def integration_summary() -> dict:
    return {
        "integrations": _safe_count(ApiIntegration.__tablename__, lambda: ApiIntegration.query.count()),
        "active_integrations": _safe_count(
            ApiIntegration.__tablename__,
            lambda: ApiIntegration.query.filter_by(status="active").count(),
        ),
        "webhooks": _safe_count(WebhookSubscription.__tablename__, lambda: WebhookSubscription.query.count()),
        "help_articles": _safe_count(
            HelpArticle.__tablename__, lambda: HelpArticle.query.filter_by(is_active=True).count()
        ),
    }


def data_health_summary() -> dict:
    unlinked_users = _safe_count(User.__tablename__, lambda: User.query.filter(User.employee_id.is_(None)).count())
    missing_emails = _safe_count(
        Employee.__tablename__, lambda: Employee.query.filter(Employee.company_email.is_(None)).count()
    )
    pending_leave = _safe_count(
        LeaveRequest.__tablename__, lambda: LeaveRequest.query.filter_by(status="pending").count()
    )
    unresolved_checks = _safe_count(
        DataHealthCheck.__tablename__,
        lambda: DataHealthCheck.query.filter(DataHealthCheck.status != "resolved").count(),
    )
    return {
        "unlinked_users": unlinked_users,
        "missing_company_emails": missing_emails,
        "pending_leave_requests": pending_leave,
        "unresolved_data_checks": unresolved_checks,
    }


def command_search(term: str, limit: int = 8) -> dict:
    token = (term or "").strip()
    if not token:
        return {"employees": [], "tickets": [], "notifications": []}
    like = f"%{token}%"
    employees = _safe_list(
        Employee.__tablename__,
        lambda: Employee.query.filter(
            Employee.first_name.ilike(like)
            | Employee.last_name.ilike(like)
            | Employee.employee_code.ilike(like)
        )
        .limit(limit)
        .all(),
    )
    tickets = _safe_list(
        HrTicket.__tablename__, lambda: HrTicket.query.filter(HrTicket.subject.ilike(like)).limit(limit).all()
    )
    notifications = _safe_list(
        Notification.__tablename__,
        lambda: Notification.query.filter(Notification.title.ilike(like)).limit(limit).all(),
    )
    return {
        "employees": [
            {"id": item.id, "label": f"{item.employee_code} - {item.full_name}", "kind": "employee"}
            for item in employees
        ],
        "tickets": [
            {"id": item.id, "label": item.subject, "kind": "ticket", "status": item.status}
            for item in tickets
        ],
        "notifications": [
            {"id": item.id, "label": item.title, "kind": "notification"}
            for item in notifications
        ],
    }


def analytics_snapshot() -> dict:
    return {
        "succession_candidates": _safe_count(
            SuccessionCandidate.__tablename__, lambda: SuccessionCandidate.query.count()
        ),
        "active_surveys": _safe_count(
            PulseSurvey.__tablename__,
            lambda: PulseSurvey.query.filter(PulseSurvey.status.in_(["launched", "open"])).count(),
        ),
        "training_courses": _safe_count(TrainingCourse.__tablename__, lambda: TrainingCourse.query.count()),
        "exit_interviews": _safe_count(ExitInterview.__tablename__, lambda: ExitInterview.query.count()),
    }


def list_hr_tickets():
    return _safe_list(
        HrTicket.__tablename__,
        lambda: HrTicket.query.order_by(HrTicket.created_at.desc()).all(),
    )


def create_hr_ticket(employee_id: int, category: str, subject: str, description: str, priority: str = "normal"):
    if not _table_exists(HrTicket.__tablename__):
        return None
    ticket = HrTicket(
        employee_id=employee_id,
        category=category,
        subject=subject,
        description=description,
        priority=priority,
        status="open",
    )
    db.session.add(ticket)
    db.session.commit()
    return ticket


def update_hr_ticket_status(ticket_id: int, status: str, assignee_id: int | None = None):
    if not _table_exists(HrTicket.__tablename__):
        return None
    ticket = HrTicket.query.get(ticket_id)
    if not ticket:
        return None
    ticket.status = status
    ticket.assigned_to_user_id = assignee_id
    db.session.commit()
    return ticket


def list_consent_logs(limit: int = 200):
    return _safe_list(
        ConsentLog.__tablename__,
        lambda: ConsentLog.query.order_by(ConsentLog.consented_at.desc()).limit(limit).all(),
    )


def create_consent_log(employee_id: int, consent_type: str, notes: str = ""):
    if not _table_exists(ConsentLog.__tablename__):
        return None
    item = ConsentLog(
        employee_id=employee_id,
        consent_type=consent_type,
        consented_at=datetime.utcnow(),
        notes=notes,
    )
    db.session.add(item)
    db.session.commit()
    return item


def list_privacy_requests(limit: int = 200):
    return _safe_list(
        PrivacyRequest.__tablename__,
        lambda: PrivacyRequest.query.order_by(PrivacyRequest.created_at.desc()).limit(limit).all(),
    )


def create_privacy_request(employee_id: int, request_type: str, details: str):
    if not _table_exists(PrivacyRequest.__tablename__):
        return None
    item = PrivacyRequest(
        employee_id=employee_id,
        request_type=request_type,
        details=details,
        status="open",
    )
    db.session.add(item)
    db.session.commit()
    return item


def update_privacy_request_status(request_id: int, status: str, handled_by_user_id: int):
    if not _table_exists(PrivacyRequest.__tablename__):
        return None
    item = PrivacyRequest.query.get(request_id)
    if not item:
        return None
    item.status = status
    item.handled_by_user_id = handled_by_user_id
    if status in {"resolved", "closed"}:
        item.resolved_at = datetime.utcnow()
    db.session.commit()
    return item


def list_integrations():
    return _safe_list(
        ApiIntegration.__tablename__,
        lambda: ApiIntegration.query.order_by(ApiIntegration.created_at.desc()).all(),
    )


def create_integration(name: str, provider: str, base_url: str, status: str = "inactive"):
    if not _table_exists(ApiIntegration.__tablename__):
        return None
    item = ApiIntegration(
        name=name,
        provider=provider,
        base_url=base_url,
        status=status,
    )
    db.session.add(item)
    db.session.commit()
    return item


def toggle_integration_status(integration_id: int):
    if not _table_exists(ApiIntegration.__tablename__):
        return None
    item = ApiIntegration.query.get(integration_id)
    if not item:
        return None
    item.status = "active" if item.status != "active" else "inactive"
    db.session.commit()
    return item


def list_webhooks():
    return _safe_list(
        WebhookSubscription.__tablename__,
        lambda: WebhookSubscription.query.order_by(WebhookSubscription.created_at.desc()).all(),
    )


def create_webhook(integration_id: int, event_name: str, endpoint_url: str):
    if not _table_exists(WebhookSubscription.__tablename__):
        return None
    item = WebhookSubscription(
        integration_id=integration_id,
        event_name=event_name,
        endpoint_url=endpoint_url,
        is_active=True,
    )
    db.session.add(item)
    db.session.commit()
    return item


def toggle_webhook_status(webhook_id: int):
    if not _table_exists(WebhookSubscription.__tablename__):
        return None
    item = WebhookSubscription.query.get(webhook_id)
    if not item:
        return None
    item.is_active = not item.is_active
    db.session.commit()
    return item


def list_data_health_checks(limit: int = 200):
    return _safe_list(
        DataHealthCheck.__tablename__,
        lambda: DataHealthCheck.query.order_by(DataHealthCheck.created_at.desc()).limit(limit).all(),
    )


def run_data_health_checks() -> dict:
    if not _table_exists(DataHealthCheck.__tablename__):
        return {"created": 0}

    checks = [
        (
            "unlinked_users",
            "high",
            _safe_count(User.__tablename__, lambda: User.query.filter(User.employee_id.is_(None)).count()),
            "Users without linked employee records.",
        ),
        (
            "missing_company_emails",
            "medium",
            _safe_count(Employee.__tablename__, lambda: Employee.query.filter(Employee.company_email.is_(None)).count()),
            "Employees missing company email addresses.",
        ),
        (
            "pending_leave_requests",
            "medium",
            _safe_count(LeaveRequest.__tablename__, lambda: LeaveRequest.query.filter_by(status="pending").count()),
            "Leave requests waiting for action.",
        ),
    ]
    created = 0
    for check_name, severity, affected_records, details in checks:
        db.session.add(
            DataHealthCheck(
                check_name=check_name,
                severity=severity,
                affected_records=affected_records,
                details=details,
                status="open" if affected_records else "resolved",
            )
        )
        created += 1
    db.session.commit()
    return {"created": created}


def resolve_data_health_check(check_id: int):
    if not _table_exists(DataHealthCheck.__tablename__):
        return None
    item = DataHealthCheck.query.get(check_id)
    if not item:
        return None
    item.status = "resolved"
    db.session.commit()
    return item


def list_task_inbox(user_id: int, status: str | None = None, limit: int = 100):
    if not _table_exists(TaskInboxItem.__tablename__):
        return []
    query = TaskInboxItem.query.filter_by(user_id=user_id)
    if status:
        query = query.filter_by(status=status)
    return query.order_by(TaskInboxItem.due_at.asc().nullslast(), TaskInboxItem.created_at.desc()).limit(limit).all()


def list_attendance_exceptions(status: str | None = None, limit: int = 200):
    if not _table_exists(AttendanceAnomaly.__tablename__):
        return []
    query = AttendanceAnomaly.query
    if status:
        query = query.filter_by(status=status)
    return query.order_by(AttendanceAnomaly.date.desc(), AttendanceAnomaly.created_at.desc()).limit(limit).all()


def resolve_attendance_exception(exception_id: int, resolver_id: int, action: str, remarks: str | None = None):
    if not _table_exists(AttendanceAnomaly.__tablename__):
        return None
    item = AttendanceAnomaly.query.get(exception_id)
    if not item:
        return None
    item.status = "resolved" if action == "resolve" else "dismissed"
    detail_suffix = f" Action by user {resolver_id}."
    if remarks:
        detail_suffix += f" Remarks: {remarks}"
    item.details = (item.details or "") + detail_suffix
    db.session.commit()
    return item


def approval_summary(module: str | None = None, status: str | None = None, limit: int = 200):
    if not _table_exists(ApprovalInstance.__tablename__):
        return []
    query = ApprovalInstance.query
    if module:
        query = query.filter_by(module=module)
    if status:
        query = query.filter_by(status=status)
    return query.order_by(ApprovalInstance.created_at.desc()).limit(limit).all()


def escalate_stale_approvals(hours: int = 24) -> int:
    if not _table_exists(ApprovalInstance.__tablename__):
        return 0
    threshold = datetime.utcnow() - timedelta(hours=max(1, hours))
    rows = (
        ApprovalInstance.query.filter(ApprovalInstance.status == "submitted")
        .filter(ApprovalInstance.updated_at <= threshold)
        .all()
    )
    for row in rows:
        row.status = "escalated"
    if rows:
        db.session.commit()
    return len(rows)


def upsert_notification_preference(user_id: int, event_type: str, in_app_enabled: bool, email_enabled: bool, sms_enabled: bool):
    if not _table_exists(NotificationPreference.__tablename__):
        return None
    row = NotificationPreference.query.filter_by(user_id=user_id, event_type=event_type).first()
    if row is None:
        row = NotificationPreference(user_id=user_id, event_type=event_type)
        db.session.add(row)
    row.in_app_enabled = in_app_enabled
    row.email_enabled = email_enabled
    row.sms_enabled = sms_enabled
    db.session.commit()
    return row


def list_notification_preferences(user_id: int):
    if not _table_exists(NotificationPreference.__tablename__):
        return []
    return NotificationPreference.query.filter_by(user_id=user_id).order_by(NotificationPreference.event_type.asc()).all()


def payroll_validation(cutoff_id: int) -> dict:
    blockers: list[str] = []
    warnings: list[str] = []
    cutoff = PayrollCutoff.query.get(cutoff_id) if _table_exists(PayrollCutoff.__tablename__) else None
    if cutoff is None:
        blockers.append("Payroll cutoff not found.")
        return {"blockers": blockers, "warnings": warnings}

    records = AttendanceRecord.query.filter(AttendanceRecord.date >= cutoff.start_date, AttendanceRecord.date <= cutoff.end_date).all()
    incomplete = [row for row in records if row.status == "incomplete"]
    if incomplete:
        blockers.append(f"{len(incomplete)} attendance record(s) are incomplete within the selected cutoff.")

    pending_leaves = LeaveRequest.query.filter(LeaveRequest.status.like("pending%"), LeaveRequest.start_date <= cutoff.end_date, LeaveRequest.end_date >= cutoff.start_date).count()
    if pending_leaves:
        warnings.append(f"{pending_leaves} leave request(s) are still pending in this cutoff range.")

    entries_count = PayrollEntry.query.filter_by(cutoff_id=cutoff_id).count()
    if entries_count == 0:
        blockers.append("No payroll entries have been generated for this cutoff.")
    return {"blockers": blockers, "warnings": warnings}


def create_payslip_dispute(employee_id: int, payroll_entry_id: int, subject: str, details: str):
    if not _table_exists(PayslipDispute.__tablename__):
        return None
    item = PayslipDispute(
        employee_id=employee_id,
        payroll_entry_id=payroll_entry_id,
        subject=subject,
        details=details,
        status="open",
    )
    db.session.add(item)
    db.session.commit()
    return item


def log_device_health(device_code: str, source: str, status: str, message: str, retry_queue_count: int = 0):
    if not _table_exists(DeviceHealthLog.__tablename__):
        return None
    item = DeviceHealthLog(
        device_code=device_code,
        source=source or "kiosk",
        status=status,
        message=message,
        last_seen_at=datetime.utcnow(),
        retry_queue_count=max(0, int(retry_queue_count or 0)),
    )
    db.session.add(item)
    db.session.commit()
    return item


def _ai_action_plan_from_prompt(prompt: str) -> list[dict]:
    text = (prompt or "").strip().lower()
    actions: list[dict] = []
    if not text:
        return actions

    if "leave" in text:
        actions.append(
            {
                "action_type": "leave_review",
                "title": "Review pending leave requests",
                "details": "Open leave queue and process pending requests.",
                "risk_level": "medium",
            }
        )
    if "attendance" in text or "late" in text or "anomaly" in text:
        actions.append(
            {
                "action_type": "attendance_followup",
                "title": "Follow up attendance exceptions",
                "details": "Check unresolved attendance exceptions and notify approvers.",
                "risk_level": "low",
            }
        )
    if "payroll" in text or "payslip" in text:
        actions.append(
            {
                "action_type": "payroll_validation",
                "title": "Run payroll pre-validation",
                "details": "Validate attendance and leave blockers before posting payroll.",
                "risk_level": "high",
            }
        )
    if "onboard" in text or "offboard" in text:
        actions.append(
            {
                "action_type": "checklist_followup",
                "title": "Check onboarding/offboarding checklist",
                "details": "Review pending checklist items and assigned owners.",
                "risk_level": "low",
            }
        )
    if not actions:
        actions.append(
            {
                "action_type": "general_triage",
                "title": "General HR operations triage",
                "details": "Review open HR tickets and prioritize urgent work.",
                "risk_level": "low",
            }
        )
    return actions[:6]


def run_ai_assistant(prompt: str, requested_by_user_id: int, execute: bool = False) -> dict:
    if not _table_exists(AiAgentJob.__tablename__) or not _table_exists(AiAgentAction.__tablename__):
        return {"error": "ai tables are not available"}

    plan = _ai_action_plan_from_prompt(prompt)
    mode = "execute" if execute else "suggest"
    job = AiAgentJob(
        requested_by_user_id=requested_by_user_id,
        prompt=prompt.strip(),
        mode=mode,
        status="completed",
        summary=f"{len(plan)} action(s) generated.",
        result_json="{}",
    )
    db.session.add(job)
    db.session.flush()

    created_task_ids: list[int] = []
    actions_payload: list[dict] = []
    for item in plan:
        action_status = "proposed"
        execution_result = "Suggestion generated."
        if execute and item["risk_level"] == "low" and _table_exists(TaskInboxItem.__tablename__):
            task = TaskInboxItem(
                user_id=requested_by_user_id,
                task_type=item["action_type"],
                title=f"AI: {item['title']}",
                description=item["details"],
                status="open",
                reference_module="ai_assistant",
                metadata_json='{"source":"ai_assistant"}',
            )
            db.session.add(task)
            db.session.flush()
            created_task_ids.append(task.id)
            action_status = "executed"
            execution_result = f"Created task inbox item #{task.id}."
        elif execute and item["risk_level"] != "low":
            action_status = "needs_approval"
            execution_result = "Not auto-executed because this action is medium/high risk."

        action_row = AiAgentAction(
            job_id=job.id,
            action_type=item["action_type"],
            title=item["title"],
            details=item["details"],
            risk_level=item["risk_level"],
            status=action_status,
            execution_result=execution_result,
        )
        db.session.add(action_row)
        actions_payload.append(
            {
                "action_type": item["action_type"],
                "title": item["title"],
                "details": item["details"],
                "risk_level": item["risk_level"],
                "status": action_status,
                "execution_result": execution_result,
            }
        )

    job.result_json = json.dumps({"actions": actions_payload, "created_task_ids": created_task_ids})
    db.session.commit()
    return {
        "job_id": job.id,
        "mode": mode,
        "summary": job.summary,
        "actions": actions_payload,
        "created_task_ids": created_task_ids,
    }
