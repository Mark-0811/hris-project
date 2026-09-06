"""add chat tables

Revision ID: e1b5d89d0f77
Revises: d7ee2e3a9c11
Create Date: 2026-03-18 15:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "e1b5d89d0f77"
down_revision = "d7ee2e3a9c11"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "chat_threads",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("employee_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["employee_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_user_id"),
    )
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("thread_id", sa.Integer(), nullable=False),
        sa.Column("sender_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_read_by_employee", sa.Boolean(), nullable=False),
        sa.Column("is_read_by_admin", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["thread_id"], ["chat_threads.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("chat_messages", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_chat_messages_thread_id"), ["thread_id"], unique=False)


def downgrade():
    with op.batch_alter_table("chat_messages", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_chat_messages_thread_id"))

    op.drop_table("chat_messages")
    op.drop_table("chat_threads")
