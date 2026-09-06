from flask import url_for

from ..extensions import db
from .base import TimestampMixin


class PersonProfile(TimestampMixin, db.Model):
    __tablename__ = "person_profiles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    status = db.Column(db.String(30), default="allowed", nullable=False, index=True)
    notes = db.Column(db.Text)
    image_filename = db.Column(db.String(255))
    face_embedding = db.Column(db.Text)
    body_embedding = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    events = db.relationship("DetectionEvent", back_populates="matched_profile", lazy="dynamic")
    intruder_profile = db.relationship("IntruderProfile", back_populates="person_profile", uselist=False)

    @property
    def image_url(self) -> str | None:
        if not self.image_filename:
            return None
        return url_for("static", filename=f"uploads/security/profiles/{self.image_filename}")


class IntruderProfile(TimestampMixin, db.Model):
    __tablename__ = "intruder_profiles"

    id = db.Column(db.Integer, primary_key=True)
    person_profile_id = db.Column(db.Integer, db.ForeignKey("person_profiles.id"), unique=True)
    label = db.Column(db.String(120), nullable=False)
    notes = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    person_profile = db.relationship("PersonProfile", back_populates="intruder_profile")


class DetectionEvent(TimestampMixin, db.Model):
    __tablename__ = "detection_events"

    id = db.Column(db.Integer, primary_key=True)
    detected_at = db.Column(db.DateTime, nullable=False, index=True)
    result_class = db.Column(db.String(40), nullable=False, index=True)
    confidence = db.Column(db.Float, nullable=False, default=0.0)
    source_camera = db.Column(db.String(120), nullable=False, default="usb_cam_0")
    image_filename = db.Column(db.String(255), nullable=False)
    rule_trace = db.Column(db.String(255), nullable=False)
    face_confidence = db.Column(db.Float)
    body_confidence = db.Column(db.Float)
    matched_profile_id = db.Column(db.Integer, db.ForeignKey("person_profiles.id"))

    matched_profile = db.relationship("PersonProfile", back_populates="events")
    alerts = db.relationship("AlertEvent", back_populates="detection_event", lazy="dynamic")

    @property
    def image_url(self) -> str:
        return url_for("static", filename=f"uploads/security/events/{self.image_filename}")


class AlertEvent(TimestampMixin, db.Model):
    __tablename__ = "alert_events"

    id = db.Column(db.Integer, primary_key=True)
    detection_event_id = db.Column(db.Integer, db.ForeignKey("detection_events.id"), nullable=False, index=True)
    channel = db.Column(db.String(30), nullable=False)
    recipient = db.Column(db.String(255), nullable=False)
    send_status = db.Column(db.String(40), nullable=False, default="pending")
    provider_response_id = db.Column(db.String(255))
    retry_count = db.Column(db.Integer, nullable=False, default=0)
    error_message = db.Column(db.Text)

    detection_event = db.relationship("DetectionEvent", back_populates="alerts")
