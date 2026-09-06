"""add security cv monitoring tables

Revision ID: a9f5c2d8e401
Revises: f91d2b8c7e13
Create Date: 2026-03-27 14:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a9f5c2d8e401"
down_revision = "f91d2b8c7e13"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "person_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("image_filename", sa.String(length=255), nullable=True),
        sa.Column("face_embedding", sa.Text(), nullable=True),
        sa.Column("body_embedding", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_person_profiles_status"), "person_profiles", ["status"], unique=False)

    op.create_table(
        "intruder_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("person_profile_id", sa.Integer(), nullable=True),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["person_profile_id"], ["person_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("person_profile_id"),
    )

    op.create_table(
        "detection_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("detected_at", sa.DateTime(), nullable=False),
        sa.Column("result_class", sa.String(length=40), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source_camera", sa.String(length=120), nullable=False),
        sa.Column("image_filename", sa.String(length=255), nullable=False),
        sa.Column("rule_trace", sa.String(length=255), nullable=False),
        sa.Column("face_confidence", sa.Float(), nullable=True),
        sa.Column("body_confidence", sa.Float(), nullable=True),
        sa.Column("matched_profile_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["matched_profile_id"], ["person_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_detection_events_detected_at"), "detection_events", ["detected_at"], unique=False)
    op.create_index(op.f("ix_detection_events_result_class"), "detection_events", ["result_class"], unique=False)

    op.create_table(
        "alert_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("detection_event_id", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=30), nullable=False),
        sa.Column("recipient", sa.String(length=255), nullable=False),
        sa.Column("send_status", sa.String(length=40), nullable=False),
        sa.Column("provider_response_id", sa.String(length=255), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["detection_event_id"], ["detection_events.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_alert_events_detection_event_id"), "alert_events", ["detection_event_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_alert_events_detection_event_id"), table_name="alert_events")
    op.drop_table("alert_events")
    op.drop_index(op.f("ix_detection_events_result_class"), table_name="detection_events")
    op.drop_index(op.f("ix_detection_events_detected_at"), table_name="detection_events")
    op.drop_table("detection_events")
    op.drop_table("intruder_profiles")
    op.drop_index(op.f("ix_person_profiles_status"), table_name="person_profiles")
    op.drop_table("person_profiles")
