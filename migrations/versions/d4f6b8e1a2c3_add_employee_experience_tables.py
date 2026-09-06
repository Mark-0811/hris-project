"""add employee experience tables

Revision ID: d4f6b8e1a2c3
Revises: c1f4e2ab9d77
Create Date: 2026-04-08 15:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "d4f6b8e1a2c3"
down_revision = "c1f4e2ab9d77"
branch_labels = None
depends_on = None


def _has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _timestamps():
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    ]


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, "hr_tickets"):
        op.create_table(
            "hr_tickets",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
            sa.Column("category", sa.String(length=80), nullable=False),
            sa.Column("subject", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=40), nullable=False, server_default="open"),
            sa.Column("priority", sa.String(length=20), nullable=False, server_default="normal"),
            sa.Column("assigned_to_user_id", sa.Integer(), sa.ForeignKey("users.id")),
            sa.Column("due_date", sa.Date()),
            *_timestamps(),
        )

    if not _has_table(inspector, "compensation_changes"):
        op.create_table(
            "compensation_changes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
            sa.Column("previous_salary", sa.Numeric(12, 2), nullable=False),
            sa.Column("new_salary", sa.Numeric(12, 2), nullable=False),
            sa.Column("effective_date", sa.Date(), nullable=False),
            sa.Column("reason", sa.Text()),
            sa.Column("status", sa.String(length=40), nullable=False, server_default="pending"),
            sa.Column("approved_by", sa.Integer(), sa.ForeignKey("users.id")),
            *_timestamps(),
        )

    if not _has_table(inspector, "leave_policy_versions"):
        op.create_table(
            "leave_policy_versions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("leave_type_id", sa.Integer(), sa.ForeignKey("leave_types.id"), nullable=False),
            sa.Column("version_name", sa.String(length=120), nullable=False),
            sa.Column("effective_from", sa.Date(), nullable=False),
            sa.Column("effective_to", sa.Date()),
            sa.Column("rules_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            *_timestamps(),
        )

    if not _has_table(inspector, "branch_holiday_rules"):
        op.create_table(
            "branch_holiday_rules",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("holiday_id", sa.Integer(), sa.ForeignKey("holidays.id"), nullable=False),
            sa.Column("branch_name", sa.String(length=120), nullable=False),
            sa.Column("is_working_day", sa.Boolean(), nullable=False, server_default=sa.false()),
            *_timestamps(),
        )

    if not _has_table(inspector, "document_records"):
        op.create_table(
            "document_records",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
            sa.Column("document_type", sa.String(length=80), nullable=False),
            sa.Column("file_path", sa.String(length=255)),
            sa.Column("expiry_date", sa.Date()),
            sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
            *_timestamps(),
        )

    if not _has_table(inspector, "geo_attendance_rules"):
        op.create_table(
            "geo_attendance_rules",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("branch_name", sa.String(length=120), nullable=False, unique=True),
            sa.Column("latitude", sa.Float(), nullable=False),
            sa.Column("longitude", sa.Float(), nullable=False),
            sa.Column("radius_meters", sa.Integer(), nullable=False, server_default="150"),
            sa.Column("anti_spoof_required", sa.Boolean(), nullable=False, server_default=sa.true()),
            *_timestamps(),
        )

    if not _has_table(inspector, "attendance_geo_logs"):
        op.create_table(
            "attendance_geo_logs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("attendance_record_id", sa.Integer(), sa.ForeignKey("attendance_records.id"), nullable=False),
            sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
            sa.Column("latitude", sa.Float()),
            sa.Column("longitude", sa.Float()),
            sa.Column("within_geofence", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("spoof_risk_score", sa.Float(), nullable=False, server_default="0"),
            *_timestamps(),
        )

    if not _has_table(inspector, "timebank_entries"):
        op.create_table(
            "timebank_entries",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
            sa.Column("source_type", sa.String(length=40), nullable=False, server_default="overtime"),
            sa.Column("hours", sa.Numeric(8, 2), nullable=False, server_default="0"),
            sa.Column("direction", sa.String(length=10), nullable=False, server_default="credit"),
            sa.Column("reference_id", sa.String(length=80)),
            *_timestamps(),
        )

    if not _has_table(inspector, "onboarding_checklist_templates"):
        op.create_table(
            "onboarding_checklist_templates",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=120), nullable=False, unique=True),
            sa.Column("checklist_type", sa.String(length=40), nullable=False, server_default="onboarding"),
            sa.Column("steps_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            *_timestamps(),
        )

    if not _has_table(inspector, "employee_checklist_items"):
        op.create_table(
            "employee_checklist_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
            sa.Column("checklist_type", sa.String(length=40), nullable=False, server_default="onboarding"),
            sa.Column("step_name", sa.String(length=255), nullable=False),
            sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id")),
            sa.Column("due_date", sa.Date()),
            sa.Column("status", sa.String(length=40), nullable=False, server_default="pending"),
            *_timestamps(),
        )

    if not _has_table(inspector, "succession_candidates"):
        op.create_table(
            "succession_candidates",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
            sa.Column("target_position_id", sa.Integer(), sa.ForeignKey("positions.id"), nullable=False),
            sa.Column("readiness_level", sa.String(length=40), nullable=False, server_default="1_year"),
            sa.Column("notes", sa.Text()),
            *_timestamps(),
        )

    if not _has_table(inspector, "performance_calibrations"):
        op.create_table(
            "performance_calibrations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
            sa.Column("review_cycle", sa.String(length=80), nullable=False),
            sa.Column("nine_box", sa.String(length=30)),
            sa.Column("calibrated_rating", sa.String(length=30)),
            sa.Column("facilitator_user_id", sa.Integer(), sa.ForeignKey("users.id")),
            sa.Column("notes", sa.Text()),
            *_timestamps(),
        )

    if not _has_table(inspector, "training_courses"):
        op.create_table(
            "training_courses",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("code", sa.String(length=60), nullable=False, unique=True),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("required_for_role", sa.String(length=80)),
            sa.Column("renewal_months", sa.Integer()),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            *_timestamps(),
        )

    if not _has_table(inspector, "employee_trainings"):
        op.create_table(
            "employee_trainings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
            sa.Column("course_id", sa.Integer(), sa.ForeignKey("training_courses.id"), nullable=False),
            sa.Column("completed_at", sa.Date()),
            sa.Column("expires_at", sa.Date()),
            sa.Column("status", sa.String(length=40), nullable=False, server_default="required"),
            *_timestamps(),
        )

    if not _has_table(inspector, "pulse_surveys"):
        op.create_table(
            "pulse_surveys",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("question_set_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("status", sa.String(length=40), nullable=False, server_default="draft"),
            sa.Column("launched_at", sa.DateTime()),
            sa.Column("closed_at", sa.DateTime()),
            *_timestamps(),
        )

    if not _has_table(inspector, "survey_responses"):
        op.create_table(
            "survey_responses",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("survey_id", sa.Integer(), sa.ForeignKey("pulse_surveys.id"), nullable=False),
            sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
            sa.Column("sentiment_score", sa.Float()),
            sa.Column("answers_json", sa.Text(), nullable=False, server_default="{}"),
            *_timestamps(),
        )

    if not _has_table(inspector, "exit_interviews"):
        op.create_table(
            "exit_interviews",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
            sa.Column("resignation_date", sa.Date()),
            sa.Column("last_day", sa.Date()),
            sa.Column("reason", sa.String(length=255)),
            sa.Column("interview_notes", sa.Text()),
            sa.Column("risk_tag", sa.String(length=40)),
            *_timestamps(),
        )

    if not _has_table(inspector, "backup_job_logs"):
        op.create_table(
            "backup_job_logs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("job_name", sa.String(length=120), nullable=False),
            sa.Column("started_at", sa.DateTime()),
            sa.Column("completed_at", sa.DateTime()),
            sa.Column("status", sa.String(length=40), nullable=False, server_default="queued"),
            sa.Column("storage_location", sa.String(length=255)),
            sa.Column("details", sa.Text()),
            *_timestamps(),
        )

    if not _has_table(inspector, "consent_logs"):
        op.create_table(
            "consent_logs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
            sa.Column("consent_type", sa.String(length=80), nullable=False),
            sa.Column("consented_at", sa.DateTime(), nullable=False),
            sa.Column("revoked_at", sa.DateTime()),
            sa.Column("notes", sa.Text()),
            *_timestamps(),
        )

    if not _has_table(inspector, "privacy_requests"):
        op.create_table(
            "privacy_requests",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
            sa.Column("request_type", sa.String(length=80), nullable=False),
            sa.Column("status", sa.String(length=40), nullable=False, server_default="open"),
            sa.Column("details", sa.Text()),
            sa.Column("resolved_at", sa.DateTime()),
            sa.Column("handled_by_user_id", sa.Integer(), sa.ForeignKey("users.id")),
            *_timestamps(),
        )

    if not _has_table(inspector, "api_integrations"):
        op.create_table(
            "api_integrations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=120), nullable=False, unique=True),
            sa.Column("provider", sa.String(length=80), nullable=False),
            sa.Column("base_url", sa.String(length=255)),
            sa.Column("status", sa.String(length=40), nullable=False, server_default="inactive"),
            sa.Column("config_json", sa.Text(), nullable=False, server_default="{}"),
            *_timestamps(),
        )

    if not _has_table(inspector, "webhook_subscriptions"):
        op.create_table(
            "webhook_subscriptions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("integration_id", sa.Integer(), sa.ForeignKey("api_integrations.id"), nullable=False),
            sa.Column("event_name", sa.String(length=120), nullable=False),
            sa.Column("endpoint_url", sa.String(length=255), nullable=False),
            sa.Column("secret", sa.String(length=255)),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            *_timestamps(),
        )

    if not _has_table(inspector, "session_devices"):
        op.create_table(
            "session_devices",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("device_name", sa.String(length=120)),
            sa.Column("ip_address", sa.String(length=45)),
            sa.Column("user_agent", sa.String(length=255)),
            sa.Column("last_seen_at", sa.DateTime()),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            *_timestamps(),
        )

    if not _has_table(inspector, "permission_overrides"):
        op.create_table(
            "permission_overrides",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id"), nullable=False),
            sa.Column("module", sa.String(length=80), nullable=False),
            sa.Column("action", sa.String(length=80), nullable=False),
            sa.Column("ui_element", sa.String(length=120)),
            sa.Column("is_allowed", sa.Boolean(), nullable=False, server_default=sa.true()),
            *_timestamps(),
        )

    if not _has_table(inspector, "localization_settings"):
        op.create_table(
            "localization_settings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("language_code", sa.String(length=12), nullable=False, unique=True),
            sa.Column("timezone_name", sa.String(length=80), nullable=False, server_default="Asia/Singapore"),
            sa.Column("date_format", sa.String(length=40), nullable=False, server_default="YYYY-MM-DD"),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
            *_timestamps(),
        )

    if not _has_table(inspector, "data_health_checks"):
        op.create_table(
            "data_health_checks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("check_name", sa.String(length=120), nullable=False),
            sa.Column("severity", sa.String(length=30), nullable=False, server_default="info"),
            sa.Column("affected_records", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("details", sa.Text()),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="open"),
            *_timestamps(),
        )

    if not _has_table(inspector, "help_articles"):
        op.create_table(
            "help_articles",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("module", sa.String(length=80), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            *_timestamps(),
        )

    if not _has_table(inspector, "approval_workflow_definitions"):
        op.create_table(
            "approval_workflow_definitions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("module", sa.String(length=80), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            *_timestamps(),
        )

    if not _has_table(inspector, "approval_workflow_steps"):
        op.create_table(
            "approval_workflow_steps",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("definition_id", sa.Integer(), sa.ForeignKey("approval_workflow_definitions.id"), nullable=False),
            sa.Column("step_order", sa.Integer(), nullable=False),
            sa.Column("approver_role", sa.String(length=80), nullable=False),
            sa.Column("fallback_role", sa.String(length=80)),
            sa.Column("conditions_json", sa.Text(), nullable=False, server_default="{}"),
            *_timestamps(),
        )

    if not _has_table(inspector, "approval_instances"):
        op.create_table(
            "approval_instances",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("module", sa.String(length=80), nullable=False),
            sa.Column("record_id", sa.Integer(), nullable=False),
            sa.Column("definition_id", sa.Integer(), sa.ForeignKey("approval_workflow_definitions.id")),
            sa.Column("current_step", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("total_steps", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("status", sa.String(length=40), nullable=False, server_default="pending"),
            *_timestamps(),
        )

    if not _has_table(inspector, "approval_decisions"):
        op.create_table(
            "approval_decisions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("instance_id", sa.Integer(), sa.ForeignKey("approval_instances.id"), nullable=False),
            sa.Column("step_order", sa.Integer(), nullable=False),
            sa.Column("approver_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("approver_role", sa.String(length=80), nullable=False),
            sa.Column("is_fallback", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("decision", sa.String(length=40), nullable=False, server_default="approved"),
            sa.Column("remarks", sa.Text()),
            *_timestamps(),
        )

    if not _has_table(inspector, "attendance_anomalies"):
        op.create_table(
            "attendance_anomalies",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("attendance_record_id", sa.Integer(), sa.ForeignKey("attendance_records.id"), nullable=False),
            sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("anomaly_type", sa.String(length=80), nullable=False),
            sa.Column("severity", sa.String(length=20), nullable=False, server_default="medium"),
            sa.Column("score", sa.Float(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="open"),
            sa.Column("details", sa.Text()),
            sa.UniqueConstraint("attendance_record_id", "anomaly_type", name="uq_attendance_anomaly_record_type"),
            *_timestamps(),
        )

    if not _has_table(inspector, "report_filter_presets"):
        op.create_table(
            "report_filter_presets",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("report_type", sa.String(length=80), nullable=False, server_default="all"),
            sa.Column("filters_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
            *_timestamps(),
        )

    if not _has_table(inspector, "report_schedules"):
        op.create_table(
            "report_schedules",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("report_type", sa.String(length=80), nullable=False),
            sa.Column("preset_id", sa.Integer(), sa.ForeignKey("report_filter_presets.id")),
            sa.Column("delivery_channel", sa.String(length=30), nullable=False, server_default="email"),
            sa.Column("delivery_target", sa.String(length=255), nullable=False),
            sa.Column("cadence", sa.String(length=30), nullable=False, server_default="daily"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("last_run_at", sa.DateTime()),
            sa.Column("next_run_at", sa.DateTime()),
            *_timestamps(),
        )

    inspector = sa.inspect(bind)
    if _has_table(inspector, "user_menu_access") and _has_table(inspector, "roles") and _has_table(inspector, "users"):
        menu_role_map = {
            "my_workspace": ["Manager", "Employee"],
            "my_schedule": ["Manager", "Employee"],
            "my_requests": ["Manager", "Employee"],
            "my_documents": ["Manager", "Employee"],
            "help_center": ["Manager", "Employee"],
            "learning": ["Manager", "Employee"],
            "surveys": ["Manager", "Employee"],
        }
        for menu_key, role_names in menu_role_map.items():
            bind.execute(
                sa.text(
                    """
                    INSERT INTO user_menu_access (user_id, menu_key, created_at, updated_at)
                    SELECT users.id, :menu_key, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    FROM users
                    JOIN roles ON roles.id = users.role_id
                    WHERE roles.name IN :role_names
                      AND NOT EXISTS (
                        SELECT 1
                        FROM user_menu_access
                        WHERE user_menu_access.user_id = users.id
                          AND user_menu_access.menu_key = :menu_key
                      )
                    """
                ).bindparams(sa.bindparam("role_names", expanding=True)),
                {"menu_key": menu_key, "role_names": role_names},
            )


def downgrade():
    pass
