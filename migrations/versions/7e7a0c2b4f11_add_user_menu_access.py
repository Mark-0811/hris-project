"""add user menu access

Revision ID: 7e7a0c2b4f11
Revises: f91d2b8c7e13
Create Date: 2026-04-07 14:15:00.000000

"""

from collections import OrderedDict

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7e7a0c2b4f11"
down_revision = "a9f5c2d8e401"
branch_labels = None
depends_on = None


ROLE_DEFAULTS = {
    "Super Admin": (
        "dashboard",
        "attendance",
        "attendance_anomalies",
        "leave",
        "reports",
        "tasks",
        "messages",
        "profile",
        "employees",
        "departments",
        "positions",
        "schedules",
        "users",
        "news",
        "bulk_actions",
        "enterprise",
        "payroll",
        "kiosk",
        "api_requests",
    ),
    "HR Admin": (
        "dashboard",
        "attendance",
        "attendance_anomalies",
        "leave",
        "reports",
        "tasks",
        "messages",
        "profile",
        "employees",
        "departments",
        "positions",
        "schedules",
        "users",
        "news",
        "bulk_actions",
        "enterprise",
        "payroll",
    ),
    "Payroll Admin": (
        "dashboard",
        "attendance",
        "attendance_anomalies",
        "leave",
        "reports",
        "tasks",
        "messages",
        "profile",
        "payroll",
    ),
    "Manager": (
        "dashboard",
        "attendance",
        "attendance_anomalies",
        "leave",
        "reports",
        "tasks",
        "messages",
        "profile",
        "team_approvals",
        "team_attendance",
    ),
    "Employee": (
        "dashboard",
        "attendance",
        "leave",
        "profile",
    ),
    "Biometrics API User": (
        "dashboard",
        "profile",
    ),
}


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("menu_access_initialized", sa.Boolean(), nullable=False, server_default=sa.false())
        )

    op.create_table(
        "user_menu_access",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("menu_key", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "menu_key", name="uq_user_menu_access_user_key"),
    )
    op.create_index(op.f("ix_user_menu_access_menu_key"), "user_menu_access", ["menu_key"], unique=False)
    op.create_index(op.f("ix_user_menu_access_user_id"), "user_menu_access", ["user_id"], unique=False)

    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            """
            SELECT users.id AS user_id, roles.name AS role_name
            FROM users
            JOIN roles ON roles.id = users.role_id
            """
        )
    ).fetchall()

    inserts = []
    for row in rows:
        menu_keys = ROLE_DEFAULTS.get(row.role_name, ())
        for menu_key in menu_keys:
            inserts.append({"user_id": row.user_id, "menu_key": menu_key})

    if inserts:
        access_table = sa.table(
            "user_menu_access",
            sa.column("user_id", sa.Integer()),
            sa.column("menu_key", sa.String()),
        )
        unique_inserts = list(
            OrderedDict(((item["user_id"], item["menu_key"]), item) for item in inserts).values()
        )
        op.bulk_insert(access_table, unique_inserts)

    connection.execute(sa.text("UPDATE users SET menu_access_initialized = TRUE"))

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column("menu_access_initialized", server_default=None)


def downgrade():
    op.drop_index(op.f("ix_user_menu_access_user_id"), table_name="user_menu_access")
    op.drop_index(op.f("ix_user_menu_access_menu_key"), table_name="user_menu_access")
    op.drop_table("user_menu_access")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("menu_access_initialized")
