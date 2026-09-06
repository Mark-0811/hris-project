"""add announcements

Revision ID: d7ee2e3a9c11
Revises: b6fd0c1f4a12
Create Date: 2026-03-18 23:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "d7ee2e3a9c11"
down_revision = "b6fd0c1f4a12"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "announcements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("posted_by", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["posted_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("announcements")
