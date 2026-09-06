"""add announcement image filename

Revision ID: a3dce6d91b42
Revises: f2bcd4a1e921
Create Date: 2026-03-18 22:05:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "a3dce6d91b42"
down_revision = "f2bcd4a1e921"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("announcements", sa.Column("image_filename", sa.String(length=255), nullable=True))


def downgrade():
    op.drop_column("announcements", "image_filename")
