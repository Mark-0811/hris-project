"""add mobile api sessions and devices

Revision ID: e8c91f4a2b61
Revises: d4f6b8e1a2c3
Create Date: 2026-04-10 17:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "e8c91f4a2b61"
down_revision = "d4f6b8e1a2c3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "mobile_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("access_token_hash", sa.String(length=128), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=128), nullable=False),
        sa.Column("access_expires_at", sa.DateTime(), nullable=False),
        sa.Column("refresh_expires_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("device_name", sa.String(length=120), nullable=True),
        sa.Column("platform", sa.String(length=40), nullable=False, server_default="android"),
        sa.Column("app_version", sa.String(length=40), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("access_token_hash"),
        sa.UniqueConstraint("refresh_token_hash"),
    )
    op.create_index(op.f("ix_mobile_sessions_user_id"), "mobile_sessions", ["user_id"], unique=False)
    op.create_index(op.f("ix_mobile_sessions_is_active"), "mobile_sessions", ["is_active"], unique=False)
    op.create_index(op.f("ix_mobile_sessions_access_expires_at"), "mobile_sessions", ["access_expires_at"], unique=False)
    op.create_index(op.f("ix_mobile_sessions_refresh_expires_at"), "mobile_sessions", ["refresh_expires_at"], unique=False)

    op.create_table(
        "mobile_devices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("fcm_token", sa.String(length=255), nullable=False),
        sa.Column("platform", sa.String(length=40), nullable=False, server_default="android"),
        sa.Column("device_name", sa.String(length=120), nullable=True),
        sa.Column("device_model", sa.String(length=120), nullable=True),
        sa.Column("app_version", sa.String(length=40), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "fcm_token", name="uq_mobile_device_user_token"),
    )
    op.create_index(op.f("ix_mobile_devices_user_id"), "mobile_devices", ["user_id"], unique=False)
    op.create_index(op.f("ix_mobile_devices_fcm_token"), "mobile_devices", ["fcm_token"], unique=False)
    op.create_index(op.f("ix_mobile_devices_is_active"), "mobile_devices", ["is_active"], unique=False)
    op.create_index(op.f("ix_mobile_devices_last_seen_at"), "mobile_devices", ["last_seen_at"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_mobile_devices_last_seen_at"), table_name="mobile_devices")
    op.drop_index(op.f("ix_mobile_devices_is_active"), table_name="mobile_devices")
    op.drop_index(op.f("ix_mobile_devices_fcm_token"), table_name="mobile_devices")
    op.drop_index(op.f("ix_mobile_devices_user_id"), table_name="mobile_devices")
    op.drop_table("mobile_devices")

    op.drop_index(op.f("ix_mobile_sessions_refresh_expires_at"), table_name="mobile_sessions")
    op.drop_index(op.f("ix_mobile_sessions_access_expires_at"), table_name="mobile_sessions")
    op.drop_index(op.f("ix_mobile_sessions_is_active"), table_name="mobile_sessions")
    op.drop_index(op.f("ix_mobile_sessions_user_id"), table_name="mobile_sessions")
    op.drop_table("mobile_sessions")
