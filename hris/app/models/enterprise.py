from ..extensions import db
from .base import TimestampMixin


class HrTicket(TimestampMixin, db.Model):
    __tablename__ = "hr_tickets"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False)
    category = db.Column(db.String(80), nullable=False, index=True)
    subject = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(40), nullable=False, default="open", index=True)
    priority = db.Column(db.String(20), nullable=False, default="normal")
    assigned_to_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    due_date = db.Column(db.Date)


class CompensationChange(TimestampMixin, db.Model):
    __tablename__ = "compensation_changes"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    previous_salary = db.Column(db.Numeric(12, 2), nullable=False)
    new_salary = db.Column(db.Numeric(12, 2), nullable=False)
    effective_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.Text)
    status = db.Column(db.String(40), nullable=False, default="pending")
    approved_by = db.Column(db.Integer, db.ForeignKey("users.id"))


class LeavePolicyVersion(TimestampMixin, db.Model):
    __tablename__ = "leave_policy_versions"

    id = db.Column(db.Integer, primary_key=True)
    leave_type_id = db.Column(db.Integer, db.ForeignKey("leave_types.id"), nullable=False)
    version_name = db.Column(db.String(120), nullable=False)
    effective_from = db.Column(db.Date, nullable=False)
    effective_to = db.Column(db.Date)
    rules_json = db.Column(db.Text, nullable=False, default="{}")
    is_active = db.Column(db.Boolean, nullable=False, default=True)


class BranchHolidayRule(TimestampMixin, db.Model):
    __tablename__ = "branch_holiday_rules"

    id = db.Column(db.Integer, primary_key=True)
    holiday_id = db.Column(db.Integer, db.ForeignKey("holidays.id"), nullable=False)
    branch_name = db.Column(db.String(120), nullable=False)
    is_working_day = db.Column(db.Boolean, nullable=False, default=False)


class DocumentRecord(TimestampMixin, db.Model):
    __tablename__ = "document_records"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    document_type = db.Column(db.String(80), nullable=False)
    file_path = db.Column(db.String(255))
    expiry_date = db.Column(db.Date, index=True)
    status = db.Column(db.String(40), nullable=False, default="active")


class GeoAttendanceRule(TimestampMixin, db.Model):
    __tablename__ = "geo_attendance_rules"

    id = db.Column(db.Integer, primary_key=True)
    branch_name = db.Column(db.String(120), nullable=False, unique=True)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    radius_meters = db.Column(db.Integer, nullable=False, default=150)
    anti_spoof_required = db.Column(db.Boolean, nullable=False, default=True)


class AttendanceGeoLog(TimestampMixin, db.Model):
    __tablename__ = "attendance_geo_logs"

    id = db.Column(db.Integer, primary_key=True)
    attendance_record_id = db.Column(db.Integer, db.ForeignKey("attendance_records.id"), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    within_geofence = db.Column(db.Boolean, nullable=False, default=False)
    spoof_risk_score = db.Column(db.Float, nullable=False, default=0.0)


class TimeBankEntry(TimestampMixin, db.Model):
    __tablename__ = "timebank_entries"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    source_type = db.Column(db.String(40), nullable=False, default="overtime")
    hours = db.Column(db.Numeric(8, 2), nullable=False, default=0)
    direction = db.Column(db.String(10), nullable=False, default="credit")
    reference_id = db.Column(db.String(80))


class OnboardingChecklistTemplate(TimestampMixin, db.Model):
    __tablename__ = "onboarding_checklist_templates"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    checklist_type = db.Column(db.String(40), nullable=False, default="onboarding")
    steps_json = db.Column(db.Text, nullable=False, default="[]")
    is_active = db.Column(db.Boolean, nullable=False, default=True)


class EmployeeChecklistItem(TimestampMixin, db.Model):
    __tablename__ = "employee_checklist_items"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    checklist_type = db.Column(db.String(40), nullable=False, default="onboarding")
    step_name = db.Column(db.String(255), nullable=False)
    owner_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    due_date = db.Column(db.Date)
    status = db.Column(db.String(40), nullable=False, default="pending")


class SuccessionCandidate(TimestampMixin, db.Model):
    __tablename__ = "succession_candidates"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    target_position_id = db.Column(db.Integer, db.ForeignKey("positions.id"), nullable=False)
    readiness_level = db.Column(db.String(40), nullable=False, default="1_year")
    notes = db.Column(db.Text)


class PerformanceCalibration(TimestampMixin, db.Model):
    __tablename__ = "performance_calibrations"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    review_cycle = db.Column(db.String(80), nullable=False)
    nine_box = db.Column(db.String(30))
    calibrated_rating = db.Column(db.String(30))
    facilitator_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    notes = db.Column(db.Text)


class TrainingCourse(TimestampMixin, db.Model):
    __tablename__ = "training_courses"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(60), nullable=False, unique=True)
    title = db.Column(db.String(255), nullable=False)
    required_for_role = db.Column(db.String(80))
    renewal_months = db.Column(db.Integer)
    is_active = db.Column(db.Boolean, nullable=False, default=True)


class EmployeeTraining(TimestampMixin, db.Model):
    __tablename__ = "employee_trainings"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    course_id = db.Column(db.Integer, db.ForeignKey("training_courses.id"), nullable=False, index=True)
    completed_at = db.Column(db.Date)
    expires_at = db.Column(db.Date, index=True)
    status = db.Column(db.String(40), nullable=False, default="required")


class PulseSurvey(TimestampMixin, db.Model):
    __tablename__ = "pulse_surveys"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    question_set_json = db.Column(db.Text, nullable=False, default="[]")
    status = db.Column(db.String(40), nullable=False, default="draft")
    launched_at = db.Column(db.DateTime)
    closed_at = db.Column(db.DateTime)


class SurveyResponse(TimestampMixin, db.Model):
    __tablename__ = "survey_responses"

    id = db.Column(db.Integer, primary_key=True)
    survey_id = db.Column(db.Integer, db.ForeignKey("pulse_surveys.id"), nullable=False, index=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    sentiment_score = db.Column(db.Float)
    answers_json = db.Column(db.Text, nullable=False, default="{}")


class ExitInterview(TimestampMixin, db.Model):
    __tablename__ = "exit_interviews"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    resignation_date = db.Column(db.Date)
    last_day = db.Column(db.Date)
    reason = db.Column(db.String(255))
    interview_notes = db.Column(db.Text)
    risk_tag = db.Column(db.String(40))


class BackupJobLog(TimestampMixin, db.Model):
    __tablename__ = "backup_job_logs"

    id = db.Column(db.Integer, primary_key=True)
    job_name = db.Column(db.String(120), nullable=False)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    status = db.Column(db.String(40), nullable=False, default="queued")
    storage_location = db.Column(db.String(255))
    details = db.Column(db.Text)


class ConsentLog(TimestampMixin, db.Model):
    __tablename__ = "consent_logs"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    consent_type = db.Column(db.String(80), nullable=False)
    consented_at = db.Column(db.DateTime, nullable=False)
    revoked_at = db.Column(db.DateTime)
    notes = db.Column(db.Text)


class PrivacyRequest(TimestampMixin, db.Model):
    __tablename__ = "privacy_requests"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    request_type = db.Column(db.String(80), nullable=False)
    status = db.Column(db.String(40), nullable=False, default="open")
    details = db.Column(db.Text)
    resolved_at = db.Column(db.DateTime)
    handled_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))


class ApiIntegration(TimestampMixin, db.Model):
    __tablename__ = "api_integrations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    provider = db.Column(db.String(80), nullable=False)
    base_url = db.Column(db.String(255))
    status = db.Column(db.String(40), nullable=False, default="inactive")
    config_json = db.Column(db.Text, nullable=False, default="{}")


class WebhookSubscription(TimestampMixin, db.Model):
    __tablename__ = "webhook_subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    integration_id = db.Column(db.Integer, db.ForeignKey("api_integrations.id"), nullable=False)
    event_name = db.Column(db.String(120), nullable=False)
    endpoint_url = db.Column(db.String(255), nullable=False)
    secret = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, nullable=False, default=True)


class SessionDevice(TimestampMixin, db.Model):
    __tablename__ = "session_devices"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    device_name = db.Column(db.String(120))
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(255))
    last_seen_at = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, nullable=False, default=True)


class PermissionOverride(TimestampMixin, db.Model):
    __tablename__ = "permission_overrides"

    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)
    module = db.Column(db.String(80), nullable=False)
    action = db.Column(db.String(80), nullable=False)
    ui_element = db.Column(db.String(120))
    is_allowed = db.Column(db.Boolean, nullable=False, default=True)


class LocalizationSetting(TimestampMixin, db.Model):
    __tablename__ = "localization_settings"

    id = db.Column(db.Integer, primary_key=True)
    language_code = db.Column(db.String(12), nullable=False, unique=True)
    timezone_name = db.Column(db.String(80), nullable=False, default="Asia/Singapore")
    date_format = db.Column(db.String(40), nullable=False, default="YYYY-MM-DD")
    is_default = db.Column(db.Boolean, nullable=False, default=False)


class DataHealthCheck(TimestampMixin, db.Model):
    __tablename__ = "data_health_checks"

    id = db.Column(db.Integer, primary_key=True)
    check_name = db.Column(db.String(120), nullable=False)
    severity = db.Column(db.String(30), nullable=False, default="info")
    affected_records = db.Column(db.Integer, nullable=False, default=0)
    details = db.Column(db.Text)
    status = db.Column(db.String(30), nullable=False, default="open")


class HelpArticle(TimestampMixin, db.Model):
    __tablename__ = "help_articles"

    id = db.Column(db.Integer, primary_key=True)
    module = db.Column(db.String(80), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)


class ApprovalWorkflowDefinition(TimestampMixin, db.Model):
    __tablename__ = "approval_workflow_definitions"

    id = db.Column(db.Integer, primary_key=True)
    module = db.Column(db.String(80), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    steps = db.relationship(
        "ApprovalWorkflowStep",
        back_populates="definition",
        lazy="dynamic",
        order_by="ApprovalWorkflowStep.step_order.asc()",
    )


class ApprovalWorkflowStep(TimestampMixin, db.Model):
    __tablename__ = "approval_workflow_steps"

    id = db.Column(db.Integer, primary_key=True)
    definition_id = db.Column(
        db.Integer, db.ForeignKey("approval_workflow_definitions.id"), nullable=False, index=True
    )
    step_order = db.Column(db.Integer, nullable=False)
    approver_role = db.Column(db.String(80), nullable=False)
    fallback_role = db.Column(db.String(80))
    conditions_json = db.Column(db.Text, nullable=False, default="{}")

    definition = db.relationship("ApprovalWorkflowDefinition", back_populates="steps")


class ApprovalInstance(TimestampMixin, db.Model):
    __tablename__ = "approval_instances"

    id = db.Column(db.Integer, primary_key=True)
    module = db.Column(db.String(80), nullable=False, index=True)
    record_id = db.Column(db.Integer, nullable=False, index=True)
    definition_id = db.Column(db.Integer, db.ForeignKey("approval_workflow_definitions.id"))
    current_step = db.Column(db.Integer, nullable=False, default=1)
    total_steps = db.Column(db.Integer, nullable=False, default=1)
    status = db.Column(db.String(40), nullable=False, default="pending")

    decisions = db.relationship("ApprovalDecision", back_populates="instance", lazy="dynamic")


class ApprovalDecision(TimestampMixin, db.Model):
    __tablename__ = "approval_decisions"

    id = db.Column(db.Integer, primary_key=True)
    instance_id = db.Column(db.Integer, db.ForeignKey("approval_instances.id"), nullable=False, index=True)
    step_order = db.Column(db.Integer, nullable=False)
    approver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    approver_role = db.Column(db.String(80), nullable=False)
    is_fallback = db.Column(db.Boolean, nullable=False, default=False)
    decision = db.Column(db.String(40), nullable=False, default="approved")
    remarks = db.Column(db.Text)

    instance = db.relationship("ApprovalInstance", back_populates="decisions")


class AttendanceAnomaly(TimestampMixin, db.Model):
    __tablename__ = "attendance_anomalies"
    __table_args__ = (
        db.UniqueConstraint("attendance_record_id", "anomaly_type", name="uq_attendance_anomaly_record_type"),
    )

    id = db.Column(db.Integer, primary_key=True)
    attendance_record_id = db.Column(db.Integer, db.ForeignKey("attendance_records.id"), nullable=False, index=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    anomaly_type = db.Column(db.String(80), nullable=False, index=True)
    severity = db.Column(db.String(20), nullable=False, default="medium")
    score = db.Column(db.Float, nullable=False, default=0.0)
    status = db.Column(db.String(30), nullable=False, default="open")
    details = db.Column(db.Text)


class ReportFilterPreset(TimestampMixin, db.Model):
    __tablename__ = "report_filter_presets"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    report_type = db.Column(db.String(80), nullable=False, default="all")
    filters_json = db.Column(db.Text, nullable=False, default="{}")
    is_default = db.Column(db.Boolean, nullable=False, default=False)


class ReportSchedule(TimestampMixin, db.Model):
    __tablename__ = "report_schedules"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    report_type = db.Column(db.String(80), nullable=False)
    preset_id = db.Column(db.Integer, db.ForeignKey("report_filter_presets.id"))
    delivery_channel = db.Column(db.String(30), nullable=False, default="email")
    delivery_target = db.Column(db.String(255), nullable=False)
    cadence = db.Column(db.String(30), nullable=False, default="daily")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    last_run_at = db.Column(db.DateTime)
    next_run_at = db.Column(db.DateTime)


class TaskInboxItem(TimestampMixin, db.Model):
    __tablename__ = "task_inbox_items"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    task_type = db.Column(db.String(80), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(30), nullable=False, default="open", index=True)
    due_at = db.Column(db.DateTime)
    reference_module = db.Column(db.String(80))
    reference_id = db.Column(db.Integer, index=True)
    metadata_json = db.Column(db.Text, nullable=False, default="{}")


class NotificationPreference(TimestampMixin, db.Model):
    __tablename__ = "notification_preferences"
    __table_args__ = (
        db.UniqueConstraint("user_id", "event_type", name="uq_notification_pref_user_event"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    event_type = db.Column(db.String(80), nullable=False, index=True)
    in_app_enabled = db.Column(db.Boolean, nullable=False, default=True)
    email_enabled = db.Column(db.Boolean, nullable=False, default=False)
    sms_enabled = db.Column(db.Boolean, nullable=False, default=False)


class DeviceHealthLog(TimestampMixin, db.Model):
    __tablename__ = "device_health_logs"

    id = db.Column(db.Integer, primary_key=True)
    device_code = db.Column(db.String(80), nullable=False, index=True)
    source = db.Column(db.String(40), nullable=False, default="kiosk")
    status = db.Column(db.String(30), nullable=False, default="online", index=True)
    message = db.Column(db.String(255))
    last_seen_at = db.Column(db.DateTime, nullable=False)
    retry_queue_count = db.Column(db.Integer, nullable=False, default=0)


class PayslipDispute(TimestampMixin, db.Model):
    __tablename__ = "payslip_disputes"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employees.id"), nullable=False, index=True)
    payroll_entry_id = db.Column(db.Integer, db.ForeignKey("payroll_entries.id"), nullable=False, index=True)
    subject = db.Column(db.String(255), nullable=False)
    details = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), nullable=False, default="open", index=True)
    resolved_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    resolved_at = db.Column(db.DateTime)


class AiAgentJob(TimestampMixin, db.Model):
    __tablename__ = "ai_agent_jobs"

    id = db.Column(db.Integer, primary_key=True)
    requested_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    prompt = db.Column(db.Text, nullable=False)
    mode = db.Column(db.String(20), nullable=False, default="suggest")
    status = db.Column(db.String(20), nullable=False, default="completed", index=True)
    summary = db.Column(db.String(255))
    result_json = db.Column(db.Text, nullable=False, default="{}")


class AiAgentAction(TimestampMixin, db.Model):
    __tablename__ = "ai_agent_actions"

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("ai_agent_jobs.id"), nullable=False, index=True)
    action_type = db.Column(db.String(80), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    details = db.Column(db.Text)
    risk_level = db.Column(db.String(20), nullable=False, default="low")
    status = db.Column(db.String(20), nullable=False, default="proposed", index=True)
    execution_result = db.Column(db.Text)
