"""add employee manager id

Revision ID: d2aa9f7f5f44
Revises: c4e0dfad12aa
Create Date: 2026-03-19 09:40:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "d2aa9f7f5f44"
down_revision = "c4e0dfad12aa"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("employees", sa.Column("manager_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_employees_manager_id_employees",
        "employees",
        "employees",
        ["manager_id"],
        ["id"],
    )


def downgrade():
    op.drop_constraint("fk_employees_manager_id_employees", "employees", type_="foreignkey")
    op.drop_column("employees", "manager_id")
