"""add chat message attachments

Revision ID: f91d2b8c7e13
Revises: e5b1b7df02a4
Create Date: 2026-03-19 22:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "f91d2b8c7e13"
down_revision = "e5b1b7df02a4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("chat_messages", sa.Column("attachment_filename", sa.String(length=255), nullable=True))
    op.add_column("chat_messages", sa.Column("attachment_original_name", sa.String(length=255), nullable=True))
    op.add_column("chat_messages", sa.Column("attachment_mime_type", sa.String(length=255), nullable=True))


def downgrade():
    op.drop_column("chat_messages", "attachment_mime_type")
    op.drop_column("chat_messages", "attachment_original_name")
    op.drop_column("chat_messages", "attachment_filename")
