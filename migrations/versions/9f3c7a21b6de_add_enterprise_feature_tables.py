"""add enterprise feature tables

Revision ID: 9f3c7a21b6de
Revises: e8c91f4a2b61
Create Date: 2026-05-08 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "9f3c7a21b6de"
down_revision = "e8c91f4a2b61"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "task_inbox_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("task_type", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("due_at", sa.DateTime(), nullable=True),
        sa.Column("reference_module", sa.String(length=80), nullable=True),
        sa.Column("reference_id", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_task_inbox_items_reference_id"), "task_inbox_items", ["reference_id"], unique=False)
    op.create_index(op.f("ix_task_inbox_items_status"), "task_inbox_items", ["status"], unique=False)
    op.create_index(op.f("ix_task_inbox_items_task_type"), "task_inbox_items", ["task_type"], unique=False)
    op.create_index(op.f("ix_task_inbox_items_user_id"), "task_inbox_items", ["user_id"], unique=False)

    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("in_app_enabled", sa.Boolean(), nullable=False),
        sa.Column("email_enabled", sa.Boolean(), nullable=False),
        sa.Column("sms_enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "event_type", name="uq_notification_pref_user_event"),
    )
    op.create_index(op.f("ix_notification_preferences_event_type"), "notification_preferences", ["event_type"], unique=False)
    op.create_index(op.f("ix_notification_preferences_user_id"), "notification_preferences", ["user_id"], unique=False)

    op.create_table(
        "device_health_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_code", sa.String(length=80), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("message", sa.String(length=255), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("retry_queue_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_device_health_logs_device_code"), "device_health_logs", ["device_code"], unique=False)
    op.create_index(op.f("ix_device_health_logs_status"), "device_health_logs", ["status"], unique=False)

    op.create_table(
        "payslip_disputes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("payroll_entry_id", sa.Integer(), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("details", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("resolved_by", sa.Integer(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["payroll_entry_id"], ["payroll_entries.id"]),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_payslip_disputes_employee_id"), "payslip_disputes", ["employee_id"], unique=False)
    op.create_index(op.f("ix_payslip_disputes_payroll_entry_id"), "payslip_disputes", ["payroll_entry_id"], unique=False)
    op.create_index(op.f("ix_payslip_disputes_status"), "payslip_disputes", ["status"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_payslip_disputes_status"), table_name="payslip_disputes")
    op.drop_index(op.f("ix_payslip_disputes_payroll_entry_id"), table_name="payslip_disputes")
    op.drop_index(op.f("ix_payslip_disputes_employee_id"), table_name="payslip_disputes")
    op.drop_table("payslip_disputes")

    op.drop_index(op.f("ix_device_health_logs_status"), table_name="device_health_logs")
    op.drop_index(op.f("ix_device_health_logs_device_code"), table_name="device_health_logs")
    op.drop_table("device_health_logs")

    op.drop_index(op.f("ix_notification_preferences_user_id"), table_name="notification_preferences")
    op.drop_index(op.f("ix_notification_preferences_event_type"), table_name="notification_preferences")
    op.drop_table("notification_preferences")

    op.drop_index(op.f("ix_task_inbox_items_user_id"), table_name="task_inbox_items")
    op.drop_index(op.f("ix_task_inbox_items_task_type"), table_name="task_inbox_items")
    op.drop_index(op.f("ix_task_inbox_items_status"), table_name="task_inbox_items")
    op.drop_index(op.f("ix_task_inbox_items_reference_id"), table_name="task_inbox_items")
    op.drop_table("task_inbox_items")
