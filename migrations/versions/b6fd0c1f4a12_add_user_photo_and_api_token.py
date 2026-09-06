"""add user photo and api token

Revision ID: b6fd0c1f4a12
Revises: aa966a094805
Create Date: 2026-03-18 23:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b6fd0c1f4a12"
down_revision = "aa966a094805"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("photo_filename", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("api_token", sa.String(length=255), nullable=True))
        batch_op.create_unique_constraint("uq_users_api_token", ["api_token"])


def downgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_constraint("uq_users_api_token", type_="unique")
        batch_op.drop_column("api_token")
        batch_op.drop_column("photo_filename")
