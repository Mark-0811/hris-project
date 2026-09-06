"""add menu governance tables

Revision ID: 8a1d9f34c2be
Revises: 7e7a0c2b4f11
Create Date: 2026-04-07 16:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "8a1d9f34c2be"
down_revision = "7e7a0c2b4f11"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("user_menu_access", schema=None) as batch_op:
        batch_op.add_column(sa.Column("assigned_by_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("expires_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("last_seen_at", sa.DateTime(), nullable=True))
        batch_op.create_index(batch_op.f("ix_user_menu_access_expires_at"), ["expires_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_user_menu_access_last_seen_at"), ["last_seen_at"], unique=False)
        batch_op.create_foreign_key("fk_user_menu_access_assigned_by_user_id", "users", ["assigned_by_user_id"], ["id"])

    op.create_table(
        "menu_access_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("role_name", sa.String(length=80), nullable=True),
        sa.Column("menu_keys_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "menu_access_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("requested_menu_keys_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("reviewer_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("decision_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_menu_access_requests_status"), "menu_access_requests", ["status"], unique=False)
    op.create_index(op.f("ix_menu_access_requests_user_id"), "menu_access_requests", ["user_id"], unique=False)

    connection = op.get_bind()
    admin_rows = connection.execute(
        sa.text(
            """
            SELECT users.id
            FROM users
            JOIN roles ON roles.id = users.role_id
            WHERE roles.name IN ('Super Admin', 'HR Admin')
            """
        )
    ).fetchall()
    if admin_rows:
        access_table = sa.table(
            "user_menu_access",
            sa.column("user_id", sa.Integer()),
            sa.column("menu_key", sa.String()),
        )
        op.bulk_insert(
            access_table,
            [{"user_id": row.id, "menu_key": "access_governance"} for row in admin_rows],
        )


def downgrade():
    op.drop_index(op.f("ix_menu_access_requests_user_id"), table_name="menu_access_requests")
    op.drop_index(op.f("ix_menu_access_requests_status"), table_name="menu_access_requests")
    op.drop_table("menu_access_requests")
    op.drop_table("menu_access_templates")

    with op.batch_alter_table("user_menu_access", schema=None) as batch_op:
        batch_op.drop_constraint("fk_user_menu_access_assigned_by_user_id", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_user_menu_access_last_seen_at"))
        batch_op.drop_index(batch_op.f("ix_user_menu_access_expires_at"))
        batch_op.drop_column("last_seen_at")
        batch_op.drop_column("expires_at")
        batch_op.drop_column("assigned_by_user_id")
