"""add leave request is paid

Revision ID: c4e0dfad12aa
Revises: a3dce6d91b42
Create Date: 2026-03-19 09:15:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "c4e0dfad12aa"
down_revision = "a3dce6d91b42"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "leave_requests",
        sa.Column("is_paid", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.alter_column("leave_requests", "is_paid", server_default=None)


def downgrade():
    op.drop_column("leave_requests", "is_paid")
