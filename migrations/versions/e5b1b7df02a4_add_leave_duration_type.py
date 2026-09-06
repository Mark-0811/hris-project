"""add leave duration type

Revision ID: e5b1b7df02a4
Revises: d2aa9f7f5f44
Create Date: 2026-03-19 16:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "e5b1b7df02a4"
down_revision = "d2aa9f7f5f44"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "leave_requests",
        sa.Column("duration_type", sa.String(length=20), nullable=False, server_default="whole_day"),
    )
    op.alter_column("leave_requests", "duration_type", server_default=None)


def downgrade():
    op.drop_column("leave_requests", "duration_type")
