"""add user api access flag

Revision ID: f2bcd4a1e921
Revises: e1b5d89d0f77
Create Date: 2026-03-18 20:55:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f2bcd4a1e921"
down_revision = "e1b5d89d0f77"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("can_access_api", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute("UPDATE users SET can_access_api = TRUE WHERE api_token IS NOT NULL")
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("users") as batch_op:
            batch_op.alter_column(
                "can_access_api",
                existing_type=sa.Boolean(),
                server_default=None,
            )
    else:
        op.alter_column("users", "can_access_api", server_default=None)


def downgrade():
    op.drop_column("users", "can_access_api")
