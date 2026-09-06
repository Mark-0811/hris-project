from ..extensions import db
from .base import TimestampMixin
from flask import url_for


class Notification(TimestampMixin, db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(50), default="info", nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)

    user = db.relationship("User", back_populates="notifications")


class Announcement(TimestampMixin, db.Model):
    __tablename__ = "announcements"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    image_filename = db.Column(db.String(255))
    posted_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    author = db.relationship("User")

    @property
    def image_url(self) -> str | None:
        if not self.image_filename:
            return None
        return url_for("static", filename=f"uploads/news/{self.image_filename}")
