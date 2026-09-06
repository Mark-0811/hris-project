from ..extensions import db
from .base import TimestampMixin


class MobileSession(TimestampMixin, db.Model):
    __tablename__ = "mobile_sessions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    access_token_hash = db.Column(db.String(128), nullable=False, unique=True, index=True)
    refresh_token_hash = db.Column(db.String(128), nullable=False, unique=True, index=True)
    access_expires_at = db.Column(db.DateTime, nullable=False, index=True)
    refresh_expires_at = db.Column(db.DateTime, nullable=False, index=True)
    last_used_at = db.Column(db.DateTime)
    device_name = db.Column(db.String(120))
    platform = db.Column(db.String(40), nullable=False, default="android")
    app_version = db.Column(db.String(40))
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)


class MobileDevice(TimestampMixin, db.Model):
    __tablename__ = "mobile_devices"
    __table_args__ = (
        db.UniqueConstraint("user_id", "fcm_token", name="uq_mobile_device_user_token"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    fcm_token = db.Column(db.String(255), nullable=False, index=True)
    platform = db.Column(db.String(40), nullable=False, default="android")
    device_name = db.Column(db.String(120))
    device_model = db.Column(db.String(120))
    app_version = db.Column(db.String(40))
    last_seen_at = db.Column(db.DateTime, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
