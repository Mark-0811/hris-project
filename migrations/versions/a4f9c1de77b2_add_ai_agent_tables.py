"""add ai agent tables

Revision ID: a4f9c1de77b2
Revises: 9f3c7a21b6de
Create Date: 2026-05-08 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "a4f9c1de77b2"
down_revision = "9f3c7a21b6de"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_agent_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("summary", sa.String(length=255), nullable=True),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_agent_jobs_requested_by_user_id"), "ai_agent_jobs", ["requested_by_user_id"], unique=False)
    op.create_index(op.f("ix_ai_agent_jobs_status"), "ai_agent_jobs", ["status"], unique=False)

    op.create_table(
        "ai_agent_actions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("action_type", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("execution_result", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["ai_agent_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ai_agent_actions_action_type"), "ai_agent_actions", ["action_type"], unique=False)
    op.create_index(op.f("ix_ai_agent_actions_job_id"), "ai_agent_actions", ["job_id"], unique=False)
    op.create_index(op.f("ix_ai_agent_actions_status"), "ai_agent_actions", ["status"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_ai_agent_actions_status"), table_name="ai_agent_actions")
    op.drop_index(op.f("ix_ai_agent_actions_job_id"), table_name="ai_agent_actions")
    op.drop_index(op.f("ix_ai_agent_actions_action_type"), table_name="ai_agent_actions")
    op.drop_table("ai_agent_actions")

    op.drop_index(op.f("ix_ai_agent_jobs_status"), table_name="ai_agent_jobs")
    op.drop_index(op.f("ix_ai_agent_jobs_requested_by_user_id"), table_name="ai_agent_jobs")
    op.drop_table("ai_agent_jobs")
