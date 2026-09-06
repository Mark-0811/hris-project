"""add employee profile update requests

Revision ID: c1f4e2ab9d77
Revises: 8a1d9f34c2be
Create Date: 2026-04-07 18:20:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "c1f4e2ab9d77"
down_revision = "8a1d9f34c2be"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "employee_profile_update_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("requested_data_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("reviewer_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("decision_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_employee_profile_update_requests_employee_id"),
        "employee_profile_update_requests",
        ["employee_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_employee_profile_update_requests_status"),
        "employee_profile_update_requests",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_employee_profile_update_requests_user_id"),
        "employee_profile_update_requests",
        ["user_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_employee_profile_update_requests_user_id"), table_name="employee_profile_update_requests")
    op.drop_index(op.f("ix_employee_profile_update_requests_status"), table_name="employee_profile_update_requests")
    op.drop_index(op.f("ix_employee_profile_update_requests_employee_id"), table_name="employee_profile_update_requests")
    op.drop_table("employee_profile_update_requests")
